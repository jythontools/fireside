# Generic WSGI support

from nose.tools import assert_equal, assert_in, assert_is_instance, assert_not_in, assert_raises
from mock import Mock
from jythonlib import dict_builder

from javax.servlet import ServletInputStream
from javax.servlet.http import HttpServletRequest
from org.python.google.common.collect import Iterators
from org.python.tools.fireside import RequestBridge, CaptureServletOutputStream


class HttpServletRequestMock(HttpServletRequest):
    # NB must define all methods OR we will get an unimplemented error upon a load all (!)
    # probably should make some aspects of this integration more robust!

    # note that we should be able to record that loadAll in fact touches each of these methods! FIXME

    def getInputStream(self):
        class OnlyXsInputStream(ServletInputStream):
            def read(self):
                return "X"
        return OnlyXsInputStream()

    def getMethod(self):
        return "GET"

    def getQueryString(self):
        return "?q=foo"

    def getContentType(self):
        return "text/html"

    def getRemoteAddr(self):
        return "127.0.0.1"

    def getRemoteHost(self):
        return "foo.baz.com"

    def getRemotePort(self):
        return 9876

    def getLocalName(self):
        return "service.example.com"

    def getLocalPort(self):
        return 80

    def getProtocol(self):
        return "HTTP/1.1"

    def getScheme(self):
        return "http"

    def getPathInfo(self):
        return "baz&blah"

    def getServletPath(self):
        return "/foobar"

    def getHeaderNames(self):
        return Iterators.asEnumeration(Iterators.forArray(["Set-Baz", "Read-Foo", "BAR"]))

    def getHeaders(self, name):
        print "Getting headers for", name
        return Iterators.asEnumeration(Iterators.forArray(["abc", "xyz"]))


# mock the following

class AdaptedInputStream(object):
    pass

class AdaptedErrLog(object):
    pass
