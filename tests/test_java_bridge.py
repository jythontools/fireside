from servlet_support import *

# Change into a true test of the wrapper/map bridge code
# verify cases like read-after-delete - DONE
# need to test all methods, but let's make that data-driven, as opposed to being tedious

def test_content_length():
    req_mock = RequestMock()
    req_mock.getContentLength = Mock(return_value=-1)
    assert_is_instance(req_mock, HttpServletRequest)

    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
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
    

def check_request_bridge(method, key, value):
    req_mock = RequestMock()
    assert_is_instance(req_mock, HttpServletRequest)
    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    wrapper = bridge.asWrapper()

    # Setup the mock servlet request with a value
    setattr(req_mock, method, Mock(return_value=value))
    # Verify this value is visible
    assert_equal(getattr(req_mock, method)(), value)
    assert_equal(bridge_map[key], value if isinstance(value, str) else str(value))
    assert_equal(getattr(wrapper, method)(), value)
    # Deleting a key works, and is seen in the request wrapper
    del bridge_map[key]
    assert_not_in(key, bridge_map)
    assert_equal(getattr(wrapper, method)(), None if isinstance(value, str) else -1)
    # FIXME what about adding a new value in?
    # But mock servlet request is not changed
    assert_equal(getattr(req_mock, method)(), value)

    # FIXME add tests with respect to other dictionary methods
    # that bridge_map should support, including views


def test_capture_output_stream():

    def assert_chunk_is_str(chunk):
        if chunk is not None:
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
