from fireside import WSGIFilter
from webob.dec import wsgify
from servlet_support import *  # FIXME be explicit
from javax.servlet import FilterChain


# Derived from the Latinator example in PEP3333, but without requiring
# a piglatin module ;)

class UppercaseIter(object):

    """Transform iterated output to uppercase, if it's okay to do so

    Note that the "okayness" can change until the application yields
    its first non-empty bytestring, so 'transform_ok' has to be a mutable
    truth value.
    """

    def __init__(self, result, transform_ok):
        if hasattr(result, 'close'):
            self.close = result.close
        self._next = iter(result).next
        self.transform_ok = transform_ok

    def __iter__(self):
        return self

    def next(self):
        if self.transform_ok:
            return self._next().upper()
        else:
            return self._next()

    __next__ = next


class Uppercaser(object):

    # by default, don't transform output
    transform = False

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):

        transform_ok = []

        def start_uppercasing(status, response_headers, exc_info=None):

            # Reset ok flag, in case this is a repeat call
            del transform_ok[:]

            for name, value in response_headers:
                if name.lower() == 'content-type' and value == 'text/plain':
                    transform_ok.append(True)
                    # Strip content-length if present, else it'll be wrong
                    response_headers = [(name, value)
                        for name, value in response_headers
                            if name.lower() != 'content-length'
                    ]
                    break

            write = start_response(status, response_headers, exc_info)

            if transform_ok:
                def write_uppercase(data):
                    write(data.upper())
                return write_uppercase
            else:
                return write

        return UppercaseIter(self.application(environ, start_uppercasing), transform_ok)


# Heavily modified from the example in
# http://rufuspollock.org/2006/09/28/wsgi-middleware/

class AuthenticationMiddleware(object):
    def __init__(self, app):
        self.app = app
        self.allowed_addresses = {"0:0:0:0:0:0:0:1", "UNKNOWN"}

    def __call__(self, environ, start_response):
        """The standard WSGI interface"""
        addr = environ.get('REMOTE_ADDR','UNKNOWN') 

        if True: #addr in self.allowed_addresses: # pass through to the next app
            def custom_start_response(status, response_headers, exc_info=None):
                new_response_headers = []
                for name, value in response_headers:
                    if name.lower() != 'content-type':
                        new_response_headers.append((name, value))
                new_response_headers.append(('Content-Type', 'text/foobar'))
                start_response('203 Cannot say I know', new_response_headers, exc_info)

            data = self.app(environ, custom_start_response)
            for datum in data:
                yield datum.upper()

        else: # put up a response denied
            start_response(
                '403 Forbidden', [('Content-Type', 'text/html')])
            yield 'You are forbidden to view this resource' 


def test_generic_filter():
    req_mock = RequestMock()
    resp_mock = ResponseMock()
    bridge = RequestBridge(req_mock, AdaptedInputStream(), AdaptedErrLog())
    bridge_map = dict_builder(bridge.asMap)()
    req_wrapper = bridge.asWrapper()

    filter = WSGIFilter()
    filter.init(ServletConfigMock(
        #{ "wsgi.handler": "test_generic_middleware.AuthenticationMiddleware" }))
        { "wsgi.handler": "test_generic_middleware.Uppercaser" }))
    class UnitChain(FilterChain):
        def doFilter(self, req, resp):
            resp.addHeader("Content-Type", "text/plain")
            resp.outputStream.write("hi, ")
            resp.outputStream.write("there!\n")
            resp.outputStream.close()

    filter.doFilter(req_wrapper, resp_mock, UnitChain())
    assert next(resp_mock.outputStream) == b"hi, "
    assert next(resp_mock.outputStream) == b"THERE!\n"
    assert resp_mock.getHeaders("Content-Type") == ["text/plain"]
    assert resp_mock.getStatus() == 200




