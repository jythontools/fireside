# Test various types of WebOb middleware

import sys
from wsgiref.validate import validator

from fireside import WSGIFilter
from webob.dec import wsgify
from servlet_support import *  # FIXME be explicit
from javax.servlet import FilterChain


@wsgify.middleware
def all_caps(req, app):
    resp = req.get_response(validator(app))
    resp.body = resp.body.upper()
    return resp


def test_webob_filter():
    req_mock = RequestMock()
    resp_mock = ResponseMock()
    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    req_wrapper = bridge.asWrapper()

    filter = WSGIFilter()
    filter.init(ServletConfigMock(
        { "wsgi.handler": "test_webob_middleware.all_caps" }))

    class UnitChain(FilterChain):
        def doFilter(self, req, resp):
            resp.outputStream.write("hi, ")
            resp.outputStream.write("there!\n")

    filter.doFilter(req_wrapper, resp_mock, UnitChain())
    assert next(resp_mock.outputStream) == b"HI, THERE!\n"
    assert resp_mock.headers == {'Content-Length': '11', 'Content-type': 'text/plain'}
    assert resp_mock.my_status == (200, "OK")
