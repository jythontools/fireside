# Generic support of servlet/filter testing
import sys

from wsgiref.validate import validator
from collections import defaultdict
from jythonlib import dict_builder

from nose.tools import assert_equal, assert_in, assert_is_instance, assert_not_in, assert_raises
from mock import Mock

from javax.servlet import ServletConfig, ServletInputStream
from javax.servlet.http import HttpServletResponse, HttpServletRequest
from org.python.tools.fireside import RequestBridge, CaptureServletOutputStream
from org.python.google.common.collect import Iterators


class ServletConfigMock(ServletConfig):
    def __init__(self, params):
        self.params = params   

    def getInitParameter(self, name):
        return self.params[name]


class RequestMock(HttpServletRequest):
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

    def getContentLength(self):
        return -1

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
        return "/baz&blah"

    def getServletPath(self):
        return "/foobar"

    def getHeaderNames(self):
        return Iterators.asEnumeration(Iterators.forArray([])) # Iterators.asEnumeration(Iterators.forArray(["Set-Baz", "Read-Foo", "BAR"]))

    def getHeaders(self, name):
        return None # Iterators.asEnumeration(Iterators.forArray(["abc", "xyz"]))

    def getHeader(self, name):
        return None


class ResponseMock(HttpServletResponse):

    def __init__(self):
        def assert_chunk_is_str(chunk):
            if chunk is not None:
                assert_is_instance(chunk, str)

        self.my_status = (200, "OK")
        self.headers = defaultdict(list)
        self.stream = CaptureServletOutputStream(assert_chunk_is_str)

    reset = __init__

    def getOutputStream(self):
        return self.stream

    def setStatus(self, code, msg):
        self.my_status = code, msg

    def getStatus(self):
        return self.my_status[0]

    # The following header methods should be case insensitive. While
    # we are at it, it would be nice if we preserved insertion
    # ordering of headers :)
    #
    # But for now, just do something simple because we are testing.

    def addHeader(self, name, header):
        self.headers[name].append(header)

    def getHeaderNames(self):
        return self.headers.keys()

    def getHeader(self, name):
        values = self.headers.get(name)
        if values is not None:
            return str(values[0])
        else:
            return None

    def getHeaders(self, name):
        values = self.headers.get(name)
        if not values:
            return None
        else:
            # FIXME return values should probably suffice
            return [str(value) for value in  values]


# fill in the following mocks

class AdaptedInputStream(object):
    pass


class AdaptedErrLog(object):
    pass


# FIXME it would be worthwhile to parameterize these app functions so
# we can generate a family of apps generating various headers, status
# codes, and streaming/or not output

@validator
def simple_app(environ, start_response):
    """Simplest possible application object"""
    status = '200 OK'
    response_headers = [('Content-Type', 'text/plain')]
    start_response(status, response_headers)
    return [b"Hello world!\n"]


@validator
def incremental_app(environ, start_response):
    """Simplest possible incremental application object"""
    status = '200 OK'
    response_headers = [('Content-Type', 'text/plain')]
    start_response(status, response_headers)
    for chunk in [b"Hello", b" ", b"world!", b"\n"]:
        yield chunk


# FIXME also need simple apps that consume input stream (via POST);
# supplied headers; what else?

