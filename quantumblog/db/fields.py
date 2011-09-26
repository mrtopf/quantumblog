import copy
import uuid
from cStringIO import StringIO
from starflyer.processors import *
import PIL
import PIL.Image
from PIL import ImageFilter
from PIL import ImageOps

__all__ = ['Field', 'FileField', 'ImageField', 'FileProxy']

class Field(object):
    """a field instance for processing data in and out mongodb"""

    def __init__(self, in_processors=[], out_processors=[]):
        """initialize the field with processors for incoming and
        outcoming data (to the database)"""
        self.in_processors = in_processors
        self.out_processors = out_processors

    def to_mongo(self, name, data, record = None, **ctx_attrs):
        """process data on the way to mongo. You can pass in additional 
        keyword arguments which will be passed to the ``ProcessorContext`` and
        is available as ``kw``. 
        
        :param name: the name under which this field is stored in the record.
        :param data: the value to process.
        :param record: the record this field belongs to. This is not used in the
            default implementation but can be used if you need to access
            e.g. old values or even the collection.
        :param **ctx_attrs: optional attributes to be passed to the 
            processor context
        :return: an eventually processed value or an ``Error`` exception
            in case one of the processor encountered an error.
        """
        return process(data, self.in_processors, **ctx_attrs).data

    def from_mongo(self, name, data, coll, **ctx_attrs):
        """process data from the database to python. You can pass in additional 
        keyword arguments which will be passed to the ``ProcessorContext`` and
        is available as ``kw``.

        :param name: the name of the field we process
        :param data: The value to process
        :param coll: The ``Collection`` instance we indirectly belong to.
        :return: the resulting value or an ``Error`` exception raised from a 
            processor.
        """
        return process(data, self.out_processors, **ctx_attrs).data

# TODO: storages should be more generic, e.g. additional data stored in
# a collection to be retrieved, more like **kw. The field should then be able
# to retrieve it.
# TODO: should the name of an field not stored inside the field aswell?

class FileField(Field):
    """it's a field being able to handle uploads to a file storage"""

    def __init__(self, storage_name = None, 
                       content_type="application/octet-stream", 
                       *args, **kwargs):
        """initialize the FileField with a file storage"""
        super(FileField, self).__init__(*args, **kwargs)
        self.storage_name = storage_name
        self.content_type = content_type # default

    def from_mongo(self, name, data, coll, **ctx_attrs):
        """convert a value from mongo to a ``FileProxy`` instance (or None)"""
        if data is not None:
            return FileProxy(coll.settings['storages'][name], data)
        return None

    def to_mongo(self, name, data, record, **ctx_attrs): 
        """process a file on the way to Mongo. It can either be a file pointer,
        a ``FileProxy`` instance or None, in which case it means to delete the
        file
        """

        # if it's a ``FileProxy`` instance simply take it's file data and 
        # return it we also don't call processors
        if isinstance(data, FileProxy):
            return data.filedata

        # check if it's a dictionary or a file pointer
        if not isinstance(data, dict):
            data= {'fp' : data}

        # now process the data as some manipulations to the file are still
        # possible (or validation)
        data =  process(data, self.in_processors, **ctx_attrs).data

        # copy data and pop the fp and type, keep the rest for the storage
        new_data = copy.copy(data)
        fp = new_data.pop("fp", None)
        content_type = new_data.pop("content_type", self.content_type)

        old = record.get_old(name) # retrieve the old value

        # get the storage to use
        sn = self.storage_name if self.storage_name is not None else name
        storage = record._coll.settings['storages'][sn]

        # check if it's a file pointer, then wrap it
        if hasattr(fp, "read") and hasattr(fp, "seek"):
            if old is not None: # replace
                storage.delete(old)
            r = storage.put(fp, 
                content_type = content_type,
                **new_data)
            return r
           
        # delete it? 
        if fp is None and old is not None:
            storage.delete(old)
            return None

        return None

class FileProxy(object):
    """a file proxy for files being just referenced from mongodb.
    This proxy is only to be used for "outgoing" files, meaning
    that the ``FileField`` will instantiate them itself but they
    should not be passed in to a field.

    To update, simply replace the field's content either by a filepointer,
    a dict with an ``fp`` key or None.
    """

    def __init__(self, storage, filedata):
        """initialize the ``FileProxy`` instance

        :param storage: The storage object the data belongs to
        :param filedata: a dict containing information of the file as 
            produced by the storage on upload and stored in the database.
        """

        self.storage = storage
        self.filedata = filedata

    @property
    def url(self):
        """return the URL to this file, usually delegated to the storage"""
        return self.storage.url_for(self.filedata)

    def __getitem__(self, a):
        """return something from the filedata"""
        return self.filedata.get(a, None)


class Image(object):
    """an invidiual image coming from MongoDB.
    
    :param data: the image record for one size
    :param storage: the storage to use to retrieve the URL for the image
    """

    def __init__(self, data, storage):
        self.data = data
        self.storage = storage

    @property
    def url(self):
        """return the URL to this file, usually delegated to the storage"""
        if self.data is None:
            return None
        return self.storage.url_for(self.data)

    def get_url(self, default=""):
        """return the URL to this file, usually delegated to the storage. 
        If the image is None, return the default value"""
        if self.data is not None:
            return self.storage.url_for(self.data)
        else:
            return default

class ImageProxy(object):
    """an image proxy for images being just referenced from mongodb.
    This proxy is only to be used for "outgoing" images, meaning
    that the ``ImageField`` will instantiate them itself but they
    should not be passed in to a field.

    To update, simply replace the field's content either by a filepointer,
    a dict with an ``fp`` key or None.
    """

    def __init__(self, storage, imagedata):
        """initialize the ``ImageProxy`` instance

        :param storage: The storage object the data belongs to
        :param imagedata: a dict containing information of the image as 
            produced by the storage on upload and stored in the database.
        """

        self.storage = storage
        self.imagedata = imagedata

        # this flag is used in case we feed the image proxy into
        # the field again. We can then decide whether we want the whole
        # image to be deleted or not
        # use the ``delete()`` method for this.
        self.to_delete = False

    def __getitem__(self, a, default=None):
        """return something from the filedata"""
        return Image(self.imagedata.get(a, None), self.storage)

    get = __getitem__

    def has_key(self, item):
        return self.imagedata.has_key(item)

    def delete(self):
        """flag this Image set as to be deleted"""
        self.to_delete = True

    def items(self):
        return self.imagedata.items()



class ImageField(Field):
    """an ImageField stores an image and resizes it to different sizes
    defined in ``imgspecs``. 

    You can pass the following data into it:

    * a file pointer pointing to an image
    * a dictionary containgin at least an ``fp`` field as returned
      by some widget. Additonally it might contain ``content_length``, 
      ``content_type`` or ``filename``.
    * an ``ImageProxy`` instance (e.g. returned from an existing field). In
      this case the images are resizes already and we only need to store
      the image data in mongodb

    Outgoing you will always receive a ``ImageProxy`` instance.

    """

    def __init__(self, 
        storage_name = None, 
        content_type="image/png", 
        suffix = "png",
        dest = "PNG", 
        keep_original = False, 
        imgspecs = {
            'thumb' : dict(width=130),
            'bigteaser' : dict(width=460, height=460, force=True),
            'smallteaser' : dict(width=220, height=115, force=True),
            'small' : dict(width=30, height=30, force=True),
            'medium' : dict(width=60, height=60, force=True),
            'title' : dict(width=680, height=250, force=True)
        },
        *args, **kwargs):
        """initialize the FileField with a file storage

        :param storage_name: The name of the storage to store the images in
        :param content_type: The default content type to use for images
        :param suffix: The suffix to use for image filenames
        :param dest: The destination format for resized images
        :param keep_original: A flag defining if the original image is kept or not
        :param imgspecs: The sizes to use for resizing the image
        """
        super(ImageField, self).__init__(*args, **kwargs)
        self.storage_name = storage_name
        self.imgspecs = imgspecs
        self.suffix = suffix
        self.content_type = content_type
        self.dest = dest
        if keep_original:
            imgspecs['ORIGINAL'] = dict(keep_original=True)

    def from_mongo(self, name, data, coll, **ctx_attrs):
        """convert a value from mongo to a ``FileProxy`` instance (or None)"""
        if data is not None and data!={}:
            sn = self.storage_name if self.storage_name is not None else name
            return ImageProxy(coll.settings['storages'][sn], data)
        return None

    def to_mongo(self, name, data, record, **ctx_attrs): 
        """process an image on the way to Mongo. It can either be a file
        pointer, a ``FileProxy`` instance or None, in which case it means to
        delete the file """

        # if it's a ``ImageProxy`` instance simply take it's image data and 
        # return it we also don't call processors
        # the image data is usually what was returned by this field and what
        # is stored in MongoDB.
        if isinstance(data, ImageProxy):
            return data.imagedata

        # check if it's a dictionary. If not assume we have a file pointer
        if not isinstance(data, dict):
            data= {'fp' : data}

        # no fp or ImageProxy means deleting the field
        if data['fp'] is None: 
            return {}

        # now process the data as some manipulations to the image are still
        # possible (or validation)
        data =  process(data, self.in_processors, **ctx_attrs).data

        # copy data and pop the fp and type, keep the rest for the storage
        base_data = copy.copy(data)
        fp = base_data.pop("fp", None) # remove fp from dict
        content_type = base_data.pop("content_type", self.content_type)

        # retrieve the value which is stored in mongodb right now
        old = record.get_old(name)

        # get the storage to use
        sn = self.storage_name if self.storage_name is not None else name
        storage = record.settings['storages'][sn]

        # iterate through the image specs and resize and store each image
        sizes = {}
        filename = unicode(uuid.uuid4())
        fp.seek(0)
        try:
            image = PIL.Image.open(fp)
        except Exception, e:
            # TODO: what to raise here (was: Error(wrong_type))
            raise

        for name, spec in self.imgspecs.items():
            if spec.get("keep_original", False):
                new_image = image
            elif spec.get("force", False):
                new_image = self._square(image, **spec)
            else:
                new_image = self._scale(image, **spec)

            fp2 = StringIO()
            new_image.save(fp2, self.dest)
            w,h = new_image.size

            img = {
                'width' : str(w),
                'height' : str(h),
                'content_length' : len(fp2.getvalue()),
                'content_type' : self.content_type,
                'filename' : "%s_%s.%s" %(filename, name, self.suffix)
            }

            # store in some storage
            r = storage.put(fp2, **img)

            img['asset_id'] = r['asset_id']
            img['created'] = r['created']

            sizes[name] = img
        
        return sizes

            
        # TODO: check for deletion on replacement and deleting


        # check if it's a file pointer, then wrap it
        if hasattr(fp, "read") and hasattr(fp, "seek"):
            if old is not None: # replace
                storage.delete(old)
            r = storage.put(fp, 
                content_type = content_type,
                **new_data)
            return r
           
        # delete it? 
        if fp is None and old is not None:
            storage.delete(old)
            return None

        return None

    def _square(self, img, 
                     width=None, height=None, 
                     method=PIL.Image.ANTIALIAS, 
                     bleed=0.0, centering=(0.5,0.5), **kw):
        """return a an image of exactly the size ``width`` and ``height`` by 
        resizing and cropping it"""
        assert width is not None, "please provide a width"
        if height is None:
            height = width

        return ImageOps.fit(img, 
                            (width, height), 
                            method=method, 
                            bleed=bleed, 
                            centering=centering)

    def _scale(self, img, width=None, height=None, **kw):
        """scale an image to fit to either width or height. 
        If you give both the biggest possible resize will be done. 
        Aspect ratio is always maintained"""
        
        w,h = img.size
        aspect = h/w
        
        if height is None and width is not None:
            factor = w/float(width)
            new_height = int(round(h/factor))
            return img.resize((width, new_height), PIL.Image.ANTIALIAS)
            
        elif width is None and height is not None:
            factor = h/float(height)
            new_width = int(round(w/factor))
            return img.resize((new_width, height), PIL.Image.ANTIALIAS)
            
        elif width is not None and height is not None:
            img2 = img.copy()
            img2.thumbnail((width, height), PIL.Image.ANTIALIAS)
            return img2 
        return img
    
