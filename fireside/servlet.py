from javax.servlet.http import HttpServlet

from clamp import clamp_base


ToolBase = clamp_base("org.python.tools")


class WSGIServlet(ToolBase, HttpServlet):

    def init(self, *args):
        print "init", args

    def doGet(self, req, resp):
        print "doGet", req, resp
        resp.setStatus(200)
        resp.setHeader("Content-type", "text/plain")
        resp.getOutputStream().println("Hello, world")

