# FIXME add param to select level of debugging!

import sys
from jythonlib import dict_builder

from clamp import clamp_base
from javax.servlet import Filter
from javax.servlet.http import HttpServlet

from .servlet import ServletBase, FilterBase, WSGICall


ToolBase = clamp_base("org.python.tools")


class WSGIServlet(ToolBase, HttpServlet, ServletBase):

    def init(self, config):
        self.do_init(config)

    def service(self, req, resp):
        bridge = self.get_bridge(req)
        environ = dict_builder(bridge.asMap)()
        self.do_wsgi_call(WSGICall(environ, req, resp))


class WSGIFilter(ToolBase, Filter, FilterBase):

    def init(self, config):
        self.do_init(config)
    
    def doFilter(self, req, resp, chain):
        self.filter_wsgi_call(req, resp, chain)
