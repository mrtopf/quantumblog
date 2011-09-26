import py.path
import shutil
import uuid, os
import StringIO
import datetime
from pymongo.objectid import ObjectId

def _oid():
    return unicode(ObjectId())

from remix.db import Record, Collection, FileField, Field, Contest, User, Entry, Admin

collect_ignore = ['test_s3.py', 'test_entry_s3.py']

def pytest_configure(config):
    if config.getvalue("runall"):
        collect_ignore[:] = []

def pytest_funcarg__testfile(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/file")

def pytest_funcarg__testimage(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/image.png")

def pytest_funcarg__testfilename(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/file").strpath

def pytest_funcarg__mp3filename(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/test.mp3").strpath

class DummyStore(object):
    """a dummy file store"""

    def __init__(self, path="/tmp"):
        """initialize the store with a filesystem path"""
        self.path = path

    def delete(self, asset):
        """delete a file defined by the ``asset`` dict"""
        p = asset['asset_id']
        os.remove(p)
        return None
    
    def put(self, fp, 
            filename=None, 
            content_length = 0,
            content_type="application/octet-stream",
            **metadata):
        """store a file and return a metadata dict"""
        if filename is None:
            filename = unicode(uuid.uuid4())
        p = os.path.join(self.path, filename)
        fp2 = open(p, "wb")
        fp.seek(0)
        shutil.copyfileobj(fp, fp2)
        fp2.close()
        r = {
            'filename' : filename,
            'content_length' : os.path.getsize(p),
            'content_type' : content_type,
            'asset_id' : p,
            'created' : datetime.datetime.now(),
        }
        r.update(metadata)
        return r

    def url_for(self, asset):
        """return the url for an asset"""
        return "file://"+asset['asset_id']


class Example(Record):
    fields = {
        'title' : Field([]),
        'payload' : FileField(),
    }

    storage_mapping = {
        'payload' : 'payload_store'
    }


class Examples(Collection):
    """list of examples"""

    data_cls = Example

def pytest_funcarg__fp(request):
    return StringIO.StringIO("foobar")

def pytest_funcarg__fp2(request):
    return StringIO.StringIO("barfoo")

def pytest_funcarg__example_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.examples.remove({})
    settings.storages['payload'] = DummyStore()
    return Examples(settings.db.examples, 
        settings = settings)

def pytest_funcarg__entry_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.entries.remove({})
    return settings.entries

def pytest_funcarg__comment_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.comments.remove({})
    return settings.comments

def pytest_funcarg__banner_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.banners.remove({})
    return settings.banners

def pytest_funcarg__contests(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.contests.collection.remove({})
    return settings.contests

def pytest_funcarg__vote_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.votes.remove({})
    return settings.votes

def pytest_funcarg__dummy_entry_db(request):
    """return a entry database object with a dummy store"""
    settings = request.getfuncargvalue("settings")
    settings.db.entries.remove({})
    from remix import db
    entries = db.Entries(settings.db.entries, 
        storages = dict(mp3 = DummyStore()), settings=settings)
    return entries

def pytest_funcarg__contest(request):
    """return a contest"""
    c = Contest(
        title="Test Contest",
        slug="example",
        description="description",
        prize_description="prize description",
        source_id="8360",
        rules = ""
    )
    settings = request.getfuncargvalue("settings")
    c = settings.contests.put(c)
    return c

def pytest_funcarg__contest2(request):
    """return a contest"""
    c = Contest(
        title="Test Contest 2",
        slug="example 2",
        description="description",
        prize_description="prize description",
        source_id="8360",
        rules = ""
    )
    settings = request.getfuncargvalue("settings")
    c = settings.contests.put(c)
    return c

def pytest_funcarg__user(request):
    """return a user"""
    u = User(
        _id = "12345",
        first_name = "Foo",
        last_name = "Bar",
        username = "foobar"
    )
    settings = request.getfuncargvalue("settings")
    u = settings.users.put(u)
    return u

def pytest_funcarg__admin(request):
    """return an admin user"""
    u = Admin(
        name = "Administrator",
        username = "admin",
        email = "foobar@example.org",
    )
    settings = request.getfuncargvalue("settings")
    u = settings.admins.put(u)
    return u

def pytest_funcarg__entry(request):
    """create a dummy entry"""
    entries = request.getfuncargvalue("dummy_entry_db")
    fp = request.getfuncargvalue("fp")
    entry = Entry(
    )
    e = Entry(
            cid=_oid(), 
            username="123", 
            title="track title", 
            mp3=fp)
    e = entries.put(e)
    return e

def pytest_funcarg__extractor(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    return settings.mp3extractor
