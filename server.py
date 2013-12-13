from functools import partial
import redis
import threading

from django.core.handlers.wsgi import WSGIHandler
from tornado.options import options, define
import tornado.httpserver
import tornado.ioloop
import tornado.web
import tornado.wsgi
import tornado.websocket

define('port', type=int, default=8088)
tornado.options.parse_command_line()

LISTENERS = []


class TasksWebSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        LISTENERS.append(self)

    def on_message(self, message):
        self.write_message(message['data'])

    def on_close(self):
        LISTENERS.remove(self)


class WebSocketServer(object):
    ''' To communicate between django and tornado here used redis.
    Server subscribe to redis channel and django just sending messages to that
    redis channel.
    All requests to /websocket URL are handling by tornado websocket handler,
    all requests to other urls are handling by django.
    '''

    def redis_listener(self):
        r = redis.Redis()
        ps = r.pubsub()
        ps.subscribe('websocket')
        io_loop = tornado.ioloop.IOLoop.instance()
        for message in ps.listen():
            for element in LISTENERS:
                io_loop.add_callback(partial(element.on_message, message))

    def run(self):
        listener_thread = threading.Thread(target=self.redis_listener)
        listener_thread.daemon = True
        listener_thread.start()
        wsgi_app = tornado.wsgi.WSGIContainer(WSGIHandler())
        tornado_app = tornado.web.Application(
            [
                ('/websocket', TasksWebSocketHandler),
                ('.*', tornado.web.FallbackHandler, dict(fallback=wsgi_app)),
            ], debug=True)
        http_server = tornado.httpserver.HTTPServer(tornado_app)
        http_server.listen(options.port)
        tornado.ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    '''
    to run this server in command line we should add path for django project to sys.path
    and set up environment variable DJANGO_SETTINGS_MODULE, see example below:

    import os
    import sys

    path = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    sys.path.append(path)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'dcmanager.settings'
    '''

    server = WebSocketServer()
    server.run()
