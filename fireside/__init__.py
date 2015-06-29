# FIXME add param to select level of debugging!

import sys

from jythonlib import dict_builder
from clamp import clamp_base
from javax.servlet import Filter
from javax.servlet.http import HttpServlet

from .servlet import WSGIBase, WSGICall


ToolBase = clamp_base("org.python.tools")


class WSGIServlet(ToolBase, HttpServlet, WSGIBase):

    filter = False

    def init(self, config):
        self.do_init(config)

    def service(self, req, resp):
        #print >> sys.stderr, "service req=%s, resp=%s" % (req, resp)
        bridge = self.get_bridge(req)
        environ = dict_builder(bridge.asMap)()
        print >> sys.stderr, "environ=%s" % (environ,)
        self.do_wsgi_call(WSGICall(environ, req, resp))


class WSGIFilter(ToolBase, Filter, WSGIBase):

    filter = True

    def init(self, config):
        self.do_init(config)
    
    def doFilter(self, req, resp, chain):
        print >> sys.stderr, "service req=%s, resp=%s chain=%s" % (req, resp, chain)
        bridge = self.get_bridge(req)
        environ = dict_builder(bridge.asMap)()
        print >> sys.stderr, "environ=%s" % (environ,)
        wrapped_req = bridge.asWrapper()
        print >> sys.stderr, "wrapped=%s" % (wrapped_req,)

        def call_next_filter():
            print >> sys.stderr, "Call next filter..."
            chain.doFilter(wrapped_req, resp)
            print >> sys.stderr, "Called next filter"

        self.do_wsgi_call(WSGICall(environ, req, resp, call_next_filter))
