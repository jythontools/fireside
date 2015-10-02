from fireside import WSGIServlet
from jythonlib import dict_builder
from nose.tools import assert_equal, assert_in, assert_is_instance, assert_not_in, assert_raises

from org.python.tools.fireside import RequestBridge
from servlet_support import AdaptedErrLog, AdaptedInputStream, ResponseMock, RequestMock, ServletConfigMock


def test_servlet():
    req_mock = RequestMock()
    resp_mock = ResponseMock()
    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    req_wrapper = bridge.asWrapper()
    servlet = WSGIServlet()
    servlet.init(ServletConfigMock(
        { "wsgi.handler": "servlet_support.simple_app" }))
    servlet.service(req_wrapper, resp_mock)
    assert next(resp_mock.outputStream) == b"Hello world!\n"
    assert resp_mock.getHeader('Content-Type') == 'text/plain'
    assert resp_mock.getStatus() == 200


def test_incremental_servlet():
    req_mock = RequestMock()
    resp_mock = ResponseMock()
    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    req_wrapper = bridge.asWrapper()
    servlet = WSGIServlet()
    servlet.init(ServletConfigMock(
        { "wsgi.handler": "servlet_support.incremental_app" }))
    servlet.service(req_wrapper, resp_mock)
    assert next(resp_mock.outputStream) == b"Hello"
    assert next(resp_mock.outputStream) == b" "
    assert next(resp_mock.outputStream) == b"world!"
    assert next(resp_mock.outputStream) == b"\n"
    assert resp_mock.getHeader('Content-Type') == 'text/plain'
    assert resp_mock.getStatus() == 200


# write other tests - need to send in headers, etc

