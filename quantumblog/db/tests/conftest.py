import py.path
import shutil
import uuid, os
import StringIO
import datetime
from pymongo.objectid import ObjectId

def _oid():
    return unicode(ObjectId())

from quantumblog.db import Record, Collection, Field

def pytest_configure(config):
    if config.getvalue("runall"):
        collect_ignore[:] = []

def pytest_funcarg__testimage(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/image.png")

def pytest_funcarg__testfilename(request):
    p = py.path.local(request.fspath)
    return p.dirpath().join("assets/file").strpath

def pytest_funcarg__fp(request):
    return StringIO.StringIO("foobar")

def pytest_funcarg__fp2(request):
    return StringIO.StringIO("barfoo")

def pytest_funcarg__example_db(request):
    """return a database object"""
    settings = request.getfuncargvalue("settings")
    settings.db.examples.remove({})
    return Examples(settings.db.examples, 
        settings = settings)
