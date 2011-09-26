from starflyer import Application, Handler, asjson
from werkzeug.routing import Map, Rule, NotFound, RequestRedirect

import werkzeug.wsgi
import os

import setup

# for logging setup
from starflyer.contrib import MongoHandler
from logbook import NestedSetup, FileHandler

class App(Application):

    def setup_handlers(self, map):
        """setup the mapper"""
        #self.add_rule('/', 'index', IndexHandler)

    def setup_logger(self):
        """override this method to define your own log handlers. Usually it
        will return a ``NestedSetup`` object to be used"""

        return NestedSetup([
            FileHandler(self.settings.log_filename, bubble=True),
            MongoHandler(self.settings.logdb)
        ])
    
        

def app_factory(**local_conf):
    settings = setup.setup(**local_conf)
    app = App(settings)
    app = werkzeug.wsgi.SharedDataMiddleware(app, {
        '/css': os.path.join(settings.static_file_path, 'css'),
        '/js': os.path.join(settings.static_file_path, 'js'),
        '/img': os.path.join(settings.static_file_path, 'img'),
    })
    return app



