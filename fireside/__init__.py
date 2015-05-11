from clamp import clamp_base
from javax.servlet import Filter
from javax.servlet.http import HttpServlet

from .servlet import WSGIBase, WSGICall


ToolBase = clamp_base("org.python.tools")


class WSGIServlet(ToolBase, HttpServlet, WSGIBase):

    def init(self, config):
        self.do_init(config)

    def service(self, req, resp):
        environ = self.get_environ(req)
        self.do_wsgi_call(WSGICall(environ, req, resp))


class WSGIFilter(ToolBase, Filter, WSGIBase):

    def init(self, config):
        self.do_init(config)
    
    def doFilter(self, req, resp, chain):
        def call_next_filter():
            chain.doFilter(req, resp)

        environ = self.get_environ(req)
        self.do_wsgi_call(WSGICall(environ, req, resp, call_next_filter))
