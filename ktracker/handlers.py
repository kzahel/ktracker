import tornado.web
import logging
import tornado.httpclient
httpclient = tornado.httpclient.AsyncHTTPClient()
from tornado import gen
import base64

class Handler(tornado.web.RequestHandler):
    @gen.engine
    @tornado.web.asynchronous
    def get(self):
        if '_tracker_url' in self.request.arguments:
            tracker_url = self.get_argument('_tracker_url')
            response = yield gen.Task( httpclient.fetch, '%s%s' % (tracker_url, self.request.uri ) )
            if response.code == 200:
                self.write(self.get_argument('callback'))
                self.write('("')
                self.write(base64.b64encode(response.body))
                self.write('")')
        self.finish()
