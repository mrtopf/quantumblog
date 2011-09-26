import datetime
import copy
import uuid
import pprint
import mongoquery
import time

import pymongo.objectid

from remix.db import *

from starflyer.processors import *
from starflyer import processors as p
import starflyer

__all__ = ['DataError', 'Record', 'Collection', 'View']

class DataError(Exception):
    """an error for the database classes"""

    def __init__(self, errors={}, results={}):
        """in case a processing call fails we raise an ``DataError`` which 
        stores the ``errors`` dictionary, mapping names to list of errors.
        Moreover we store the results in ``results`` as far as they are 
        available at this point.

        :param errors: A dictionary with a mapping from field name to a list of 
            errors.  An error will be a dictionary itself storing ``code`` 
            and ``msg``.
        :param results: A dictionary containing the results as far as they 
            have been processed. 
        """
        self.errors = errors
        self.results = results

    def __str__(self):
        """print the error"""
        e = ['%s: "%s"' %(a,v) for a,v in self.errors.items()]
        return "<DataError: %s>" %e

class Record(dict):
    """base class for all records. In order to use this class you have to derive
    from it and define the ``fields`` dict as class variable."""

    fields = {} # name -> Field()
    in_processors = [] # runs when data enters mongodb
    out_processors = [] # runs when data leaves mongodb


    workflow_states = {
        u'active' : [u'deleted'],
        u'deleted' : [],
    }
    initial_workflow_state = u"active"

    def __init__(self, data = None, 
                       coll = None, 
                       settings = starflyer.AttributeMapper(), 
                       *args, **kw):
        """initialize a record. You can adjust newly created instances by
        overriding ``init()``. This will only be called if no id is set yet and
        we assume that we use a new instance.
        
        If a object is retrieved from a collection we also need to pass in 
        the ``Collection`` instance itself."""

        self._old = {}
        self._coll = coll
        self.settings = settings

        super(Record, self).__init__()
        if data is None:
            data = {}
        if not data.has_key('_id'):
            self.init(**kw)
            if "workflow" in self.fields:
                self['workflow'] = self.initial_workflow_state
        self.update(data)
        self.update(kw)

        self._old = {} # remember old values and delete new ones

    def gen_id(self):
        """generate a new id in case we do not use objectids"""
        return unicode(uuid.uuid4())

    def init(self, **kw):
        """initialize the record. You can override this in your own types
        and basically do what you want here to initialize it properly."""

    def set_collection(self, coll):
        """set the collection object e.g. when saving a new Record"""
        self._coll = coll
        self.settings = coll.settings

    def put(self):
        """save outselves"""
        if self._coll is not None:
            self._coll.put(self)

    def to_mongo(self, **ctx_attrs):
        """process the object's data and return a dictionary to be store in 
        MongoDB.
        
        :param **ctx_attrs: additional keyword arguments to be passed as 
            additional attributes to the ``ProcessorContext`` instance.
        :return: returns a dictionary with the resulting values. If an error 
            occurs it will raise a ``DataError`` with all catched error in 
            ``errors``.
        """
        results = {}
        errors = {}
        for name,field in self.fields.items():
            v = self.get(name, None)
            try: 
                results[name] = field.to_mongo(name, v, 
                                    record = self, **ctx_attrs)
            except starflyer.processors.Error, e:
                errors[name] = e
                continue
        if errors != {}:
            raise DataError(errors, results)

        # now handle dates
        results['_updated'] = datetime.datetime.now()
        if not self.has_key('_created'):
            self['_created'] = datetime.datetime.now()
        results['_created'] = self['_created']
        if self.has_key('_id'):
            results['_id'] = self['_id']
        return results

    @classmethod
    def from_mongo(cls, data, coll = None, **ctx_attrs):
        """process the database data and convert it to an object to be returned.
        
        :param data: the data from the database
        :param coll: the ``Collection`` instance to use
        :param **ctx_attrs: additional keyword arguments to be passed as 
                additional attributes to the ``ProcessorContext`` instance.
        :return: a new object or it will raise a ``DataError`` with all catched 
                error in ``errors``.
        """
        results = {}
        errors = {}
        for name,field in cls.fields.items():
            v = data.get(name, None)
            try: 
                results[name] = field.from_mongo(name, v, coll, **ctx_attrs)
            except starflyer.processors.Error, e:
                errors[name] = e
                continue
        if errors != {}:
            raise DataError(errors, results)

        # now handle dates
        results['_updated'] = data.get('_updated', None)
        results['_created'] = data.get('_created', None)
        results['_id'] = data.get('_id', None)
        return cls(results, coll = coll, settings = coll.settings)

    def __getitem__(self, a):
        """return a value from this document. If it's ``id``, return a unicode
        object instead of the ObjectId. You can still access the original id
        via ``obj['_id']``"""
        if a=="id":
            return unicode(self['_id'])
        else:
            return super(Record, self).__getitem__(a)

    def set(self, a, v):
        """set a value without storing it's old value (for initializing)"""
        super(Record, self)[a] = v

    def __setitem__(self, a, v):
        """set a value. We store it's old value in the old dict"""
        if a in self:
            self._old[a] = self[a]
        super(Record, self).__setitem__(a,v)

    def get_old(self, a, default=None):
        """return an old value or the default value if it's not existing"""
        return self._old.get(a, default)

    def get_oldest(self, a, default=None):
        """return either the old value or the new one, in this order"""
        return self.get_old(a, self.get(a, default))

    def update(self, d=None, **kwargs):
        if d is None:
            pass
        for k, v in d.items():
            self[k] = v
        if len(kwargs):
            self.update(kwargs)

    def set_workflow(self, new_state):
        """set the workflow to a new state"""
        old_state = self['workflow']
        if old_state is None:
            old_state=self.initial_workflow_state
        allowed_states = self.workflow_states[old_state]
        if new_state not in allowed_states:
            e = p.Error("transition_not_allowed", 
                        "Transition to %s not allowed from state %s" %(new_state, old_state))
            raise DataError(errors={'workflow' : e})

        # Trigger 
        if hasattr(self, "on_wf_"+new_state):
            m = getattr(self, "on_wf_"+new_state)
            m(old_state=old_state)
        self['workflow'] = new_state

    def save(self):
        """save this object"""
        self._coll.put(self)
        

class Collection(object):
    """base class for collections. You have to provide the data class
    as ``data_cls`` in your own subclass. You can also add additional
    methods to it of course. """

    data_cls = None
    in_processors = []
    use_objectids = True # we use ObjectIds for identifying, not strings

    def __init__(self, collection, storages={}, settings = {}, **kw):
        """initialize the Collection class with a ``collection`` object and
        the ``storages`` dict for looking up storages for file fields."""
        self.collection = collection
        self.storages = storages
        self.settings = settings
        self.kw = kw

    def _mkobjid(self, _id):
        """convert string to object id if it is not already one"""
        if not isinstance(_id, pymongo.objectid.ObjectId):
            _id = pymongo.objectid.ObjectId(_id)
        return _id

    def get(self, _id):
        """return an object by id or ``None`` if the object wasn't found"""
        if self.use_objectids:
            _id = self._mkobjid(_id)
        values = self.collection.find_one({'_id' : _id})
        if values is None:
            return None
        # now pass values through processors and fields
        obj = self.data_cls.from_mongo(values, self)
        obj.set_collection(self)
        return obj

    __getitem__ = get

    @property
    def query(self):
        """return a mongoquery.Query object with collection and instantiation pre-filled"""
        return mongoquery.Query().coll(self.collection).call(self.data_cls.from_mongo, coll=self)

    @property
    def all(self):
        """return all items for now"""
        data = self.collection.find({})
        objs = []
        for values in data:
            obj = self.data_cls.from_mongo(values, self)
            obj.set_collection(self)
            objs.append(obj)
        return objs

    def put(self, obj, **ctx_attrs):
        """store an object inside mongodb. This will use upserts."""
        # run in processors
        obj.set_collection(self)
        values = obj.to_mongo()
        if not self.use_objectids and '_id' not in values:
            values['_id'] = obj.gen_id()

        # run any general processors
        errors = {}
        try: 
            values =  process(values, self.in_processors, 
                record = obj, settings = self.settings, **ctx_attrs).data
        except starflyer.processors.Error, e:
            errors[e.name] = e
        if errors != {}:
            raise DataError(errors, values)
        n = self.__class__.__name__.lower()
        self.trigger("db.%s.put:before" %n, {'coll' : self, 'values': values})
        values['_id'] = self.collection.save(values, True)
        obj = self.data_cls.from_mongo(values, self)
        obj.set_collection(self)
        self.trigger("db.%s.put:after" %n, {'coll' : self, 'obj': obj})
        return obj

    def trigger(self, name, e={}):
        """trigger an event"""
        self.settings.events.handle(name, e, self.settings)

    def remove(self, _id):
        """remove a given object from the database"""
        self.collection.remove({'_id' : _id})


class View(object):
    """a view is a composition of multiple database objects.

    An example:

    An entry has a user attached but not directly stored inside
    the entry object. In order to retrieve the user's fullname
    you'd have to make a database query per entry. This is not
    efficient though. Instead you might want to do one query and
    get the users for all the entries in the batch.

    This is what a view can do. A view will return a list of dictionaries
    which contain the original entry in one slot and additional related
    objects (like the user) in other slots. 

    All you usually have to do is to create a mapping from the field
    in the original object to a foreign collection and the name of the
    field to query there. 
    
    Here is an example of the View for the above example::

        entry_view = View( 'entry', user = ('username', self.settings.users, 'username') )

    Here ``user`` is the field under which we later can retrieve the user
    object for an entry. The first username is the field in the original object
    (entry) we want to use, the last one the field in the secondary collection.

    ``entry`` is the name under which we want to retrieve the original entry.

    Then to actually call the view you pass it a ``mongoquery`` query object::
        
        q = self.entries.query.limit(10)
        result = entry_view(q)

        print result[0]['entry'] # print the original entry object
        print result[0]['user'] # print the user for this entry 


    """

    def __init__(self, name, **mapping):
        """initialize a view

        :param name: the name under which the original entry should be accessible
        :param **mapping: A dictionary containing mappings from a name to a 3-tuple 
            explained above
        """

        self.name = name
        self.mapping = mapping

    def __call__(self, query):
        """call a query and process the result"""

        # TODO: this is not correct but find out how to do that in mongoquery. clone() or rewind() should work.
        # but only really a problem with big sets to fit in memory
        # also we'd need to inject some different function into the query
        results = list(query()) # unfortunately we cannot rewind a cursor
        map_results = {}
        for name, info in self.mapping.items():
            n1, coll, n2 = info
            values = [o[n1] for o in results]
            q = {n2 : {'$in': values}}
            sub_docs = coll.query.update(**q)()
            objs = {}
            for doc in sub_docs:
                objs[doc[n2]] = doc
            map_results[name] = objs

        # now combine all the mappings
        final_results = []
        for r in results:
            d = {
               self.name : r
            }
            for name, info in self.mapping.items():
                n1, coll, n2 = info
                d[name] = map_results[name][r[n1]]
            final_results.append(d)
        return final_results



            


            

