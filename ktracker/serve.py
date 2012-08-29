import tornado.ioloop
import tornado.options
import tornado.netutil
import tornado.httpserver
import tornado.web
import functools
import logging
import os

from tornado.options import define, options

define('debug',default=True, type=bool)
define('asserts',default=True, type=bool)
define('verbose',default=1, type=int)
define('port',default=6969, type=int)

tornado.options.parse_command_line()
settings = dict( (k, v.value()) for k,v in options.items() )

from tornado.autoreload import add_reload_hook

ioloop = tornado.ioloop.IOLoop()
ioloop.install()

from handlers import Handler, AnnounceHandler, DebugHandler

routes = [ 
    ('/announce/?', AnnounceHandler),
    ('.?', Handler),
    ('/status/?',DebugHandler)
    ]

application = tornado.web.Application(routes, **settings)
http_server = tornado.httpserver.HTTPServer(application, io_loop=ioloop)
http_server.bind(options.port,'')
http_server.start()
logging.info('tracker started on :%s' % options.port)
ioloop.start()
