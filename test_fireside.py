# Change into a true test of the wrapper/map bridge code
# verify cases like read-after-delete
# need to test all methods, but let's make that data-driven, as opposed to being tedious

# also, let's use a standard interesting test runner. nose is probably a good choice

from nose.tools import assert_raises
from mock import Mock

from javax.servlet import ServletInputStream
from javax.servlet.http import HttpServletRequest
from org.python.google.common.collect import Iterators
from jythonlib import dict_builder

from org.python.tools.fireside import RequestBridge, CaptureServletOutputStream


# FIXME rename
class BogusServletInputStream(ServletInputStream):
    def read(self):
        return "X"


class HttpServletRequestMock(HttpServletRequest):
    # NB must define all methods OR we will get an unimplemented error upon a load all (!)
    # probably should make some aspects of this integration more robust!

    # maybe use 3-arg type() to build this mock? then again, below doesn't seem so bad

    def getInputStream(self):
        return BogusServletInputStream()

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



# NEED TO FIGURE OUT how to use mock to make this be a true subclass, with proxy generated;
# probably need to turn on proxy debugging to see what is going on
#mock = Mock(spec=HttpServletRequest)

def test_request_bridge():
    mock = HttpServletRequestMock()
    mock.getMethod = Mock(return_value="GET")

    assert isinstance(mock, HttpServletRequest)

    bridge = RequestBridge(mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    wrapper = bridge.asWrapper()
    #print type(bridge_map)
    #print bridge_map["REQUEST_METHOD"]

    #del bridge_map["REQUEST_METHOD"]
    #print bridge_map


def test_capture_output_stream():

    def assert_chunk_is_str(chunk):
        assert isinstance(chunk, str)

    c = CaptureServletOutputStream(assert_chunk_is_str)
    c.write(bytearray("foo"))
    assert next(c) == "foo"
    assert next(c) == ""
    assert next(c) == ""
    c.write(bytearray("foo2"))
    assert next(c) == "foo2"
    assert next(c) == ""
    c.close()
    assert_raises(StopIteration, next, c)
