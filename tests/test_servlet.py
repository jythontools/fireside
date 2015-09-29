from fireside import WSGIServlet
from jythonlib import dict_builder
from nose.tools import assert_equal, assert_in, assert_is_instance, assert_not_in, assert_raises
from javax.servlet import ServletConfig
from javax.servlet.http import HttpServletResponse

from org.python.tools.fireside import RequestBridge, CaptureServletOutputStream
from servlet_support import AdaptedErrLog, AdaptedInputStream, HttpServletRequestMock


class ServletConfigMock(ServletConfig):
    def __init__(self, params):
        self.params = params   

    def getInitParameter(self, name):
        return self.params[name]


class ResponseMock(HttpServletResponse):

    def __init__(self):
        def assert_chunk_is_str(chunk):
            if chunk is not None:
                assert_is_instance(chunk, str)

        self.stream = CaptureServletOutputStream(assert_chunk_is_str)

    def getOutputStream(self):
        return self.stream

    def setStatus(self, code, msg):
        print "status %s (%r)" % (code, msg)

    def addHeader(self, name, header):
        print "header %r=%r" % (name, header)


def test_servlet():
    request_mock = HttpServletRequestMock()
    mocked_resp = ResponseMock()  # FIXME fix inconsistency in names!

    bridge = RequestBridge(request_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    wrapper = bridge.asWrapper()  # FIXME request_wrapper? mocked_request_wrapper?
    
    servlet = WSGIServlet()
    servlet.init(ServletConfigMock(
        { "wsgi.handler": "servlet_support.simple_app" }))
    servlet.service(wrapper, mocked_resp)
    assert next(mocked_resp.outputStream) == b"Hello world!\n"


# write other tests - need to send in headers, etc

