import pkg_resources
import pymongo
import starflyer

from jinja2 import Environment, PackageLoader, PrefixLoader
from logbook import Logger

def setup(**kw):
    """initialize the setup"""
    settings = starflyer.AttributeMapper()
    
    settings.dbname = "quantumblog"
    settings.log_name = "quantumblog"
    settings.static_file_path = pkg_resources.resource_filename(__name__, 'static')

    # cookie related
    # TODO: add expiration dates, domains etc. maybe make it a dict?
    settings.cookie_secret = "cw98c79ew87we987cw9c8w79e87"
    settings.session_cookie_name = "s"
    settings.message_cookie_name = "m"
    settings.update(kw)

    settings.log = Logger(settings.log_name)

    settings.templates = Environment(loader=PrefixLoader({
        "framework" : PackageLoader("starflyer","templates"),
        "master" : PackageLoader("quantumblog","templates"),
    }))
    db = settings.db = pymongo.Connection()[settings.dbname]
    settings.logdb = db.logging
    return settings

