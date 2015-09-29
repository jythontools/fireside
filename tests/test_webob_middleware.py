# Test various types of WebOb middleware

import sys

from fireside import WSGIFilter
from webob.dec import wsgify
from servlet_support import *  # FIXME be explicit
from javax.servlet import FilterChain


@wsgify.middleware
def all_caps(req, app):
    print "app %s %s" % (type(app), app)
    print "req %s %s" % (type(req), req)

    print "before response for app"
    resp = req.get_response(app)
    print "resp %s %s" % (type(resp), resp)
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
            resp.outputStream.write("hi, there!\n")

    filter.doFilter(req_wrapper, resp_mock, UnitChain())
    assert next(resp_mock.outputStream) == b"HI, THERE!\n"
    assert resp_mock.headers == {'Content-Length': '11', 'Content-type': 'text/plain'}
    assert resp_mock.my_status == (200, "OK")

