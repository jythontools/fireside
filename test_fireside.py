# Change into a true test of the wrapper/map bridge code
# verify cases like read-after-delete
# need to test all methods, but let's make that data-driven, as opposed to being tedious

from nose.tools import assert_equal, assert_in, assert_is_instance, assert_not_in, assert_raises
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

    # note that we should be able to record that loadAll in fact touches each of these methods! FIXME

    def getInputStream(self):
        return BogusServletInputStream()

    # def getMethod(self):
    #     return "GET"

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

def test_content_length():
    mock = HttpServletRequestMock()
    mock.getContentLength = Mock(return_value=-1)
    assert_is_instance(mock, HttpServletRequest)

    bridge = RequestBridge(mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    wrapper = bridge.asWrapper()
    
    assert_not_in("CONTENT_LENGTH", bridge_map)


def test_request_bridge():
    # test generation requires correspondence between WSGI keys and request method names
    yield check_request_bridge, "getMethod",      "REQUEST_METHOD",  "FAKEGET"
    yield check_request_bridge, "getQueryString", "QUERY_STRING",    "?q=foo"
    yield check_request_bridge, "getContentType", "CONTENT_TYPE",    "text/html"
    yield check_request_bridge, "getRemoteAddr",  "REMOTE_ADDR",     "127.0.0.1"
    yield check_request_bridge, "getRemoteHost",  "REMOTE_HOST",     "client.example.com"
    yield check_request_bridge, "getRemotePort",  "REMOTE_PORT",     4567
    yield check_request_bridge, "getLocalName",   "SERVER_NAME",     "service.example.com"
    yield check_request_bridge, "getLocalPort",   "SERVER_PORT",     443
    yield check_request_bridge, "getProtocol",    "SERVER_PROTOCOL", "HTTP/1.1"
    yield check_request_bridge, "getScheme",      "wsgi.url_scheme", "http"
    yield check_request_bridge, "getPathInfo",    "PATH_INFO",       "foo&baz"
    yield check_request_bridge, "getServletPath", "SCRIPT_NAME",     "/foobar"
    
    # checking headers is a bit different FIXME
    #yield check_request_bridge, "getHeaderNames", 
    #     return Iterators.asEnumeration(Iterators.forArray(["Set-Baz", "Read-Foo", "BAR"]))

    # def getHeaders(self, name):
    #     print "Getting headers for", name
    #     return Iterators.asEnumeration(Iterators.forArray(["abc", "xyz"]))
    

# let's define a type constructor that fills in and returns appropriate values (maybe "some-value", 47, or maybe None);
# note that we need to dispatch on the type! could do this by hand of course, but it seems like this generally useful;
# 
class XHttpServletRequestMock(HttpServletRequest):
    pass


def check_request_bridge(method, key, value):
    mock = HttpServletRequestMock()
    assert_is_instance(mock, HttpServletRequest)
    bridge = RequestBridge(mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    wrapper = bridge.asWrapper()

    # Setup the mock servlet request with a value
    setattr(mock, method, Mock(return_value=value))
    # Verify this value is visible
    assert_equal(getattr(mock, method)(), value)
    assert_equal(bridge_map[key], value if isinstance(value, str) else str(value))
    assert_equal(getattr(wrapper, method)(), value)
    # Deleting a key works, and is seen in the request wrapper
    del bridge_map[key]
    assert_not_in(key, bridge_map)
    assert_equal(getattr(wrapper, method)(), None if isinstance(value, str) else -1)
    # But mock servlet request is not changed
    assert_equal(getattr(mock, method)(), value)

    # FIXME add tests with respect to other dictionary methods
    # that bridge_map should support, including views


def test_capture_output_stream():

    def assert_chunk_is_str(chunk):
        assert_is_instance(chunk, str)

    stream = CaptureServletOutputStream(assert_chunk_is_str)
    stream.write(bytearray("foo"))
    assert next(stream) == "foo"
    assert next(stream) == ""
    assert next(stream) == ""
    stream.write(bytearray("foo2"))
    assert next(stream) == "foo2"
    assert next(stream) == ""
    stream.close()
    assert_raises(StopIteration, next, stream)
