# Fireside - Blazing fast WSGI Servlet bridge.
#
# Named after a hot whiskey drink often made with coffee. So this
# means you can have some WSGI with your Java.

"""FIXME
Implement the following from PEP 3333

If a call to len(iterable) succeeds, the server must be able to rely on the result being accurate. That is, if the iterable returned by the application provides a working __len__() method, it must return an accurate result. (See the Handling the Content-Length Header section for information on how this would normally be used.)

And, if the server and client both support HTTP/1.1 "chunked encoding" [3] , then the server may use chunked encoding to send a chunk for each write() call or bytestring yielded by the iterable, thus generating a Content-Length header for each chunk. This allows the server to keep the client connection alive, if it wishes to do so. Note that the server must comply fully with RFC 2616 when doing this, or else fall back to one of the other strategies for dealing with the absence of Content-Length .
"""

import array
import itertools
import sys

from jythonlib import dict_builder
from org.python.tools.fireside import RequestBridge, CaptureHttpServletResponse


# FIXME perform additional verifications; see
# https://github.com/Pylons/waitress/blob/master/waitress/task.py#L143 for some guidance here


class WSGICall(object):

    def __init__(self, environ, req, resp):
        self.environ = environ
        self.req = req
        self.resp = resp
        self.headers_set = []
        self.headers_sent = []
        self.wrapped_resp = None

    def __repr__(self):
        return "WSGICall(id=%s, environ=%s, req=%s, resp=%s, set=%s, sent=%s, wrapped_resp=%s)" % (
            id(self), self.environ, self.req, self.resp, self.headers_set, self.headers_sent, self.wrapped_resp)

    def set_status(self, status):
        # convert from such usage as "404 Not Found"
        split = status.find(" ")
        code = status[:split]
        msg = status[split:]
        # HttpServletResponse.setStatus(int, String) is deprecated, but still useful for REST :)
        # (setError does the wrong thing in comparison)
        # see https://github.com/http4s/http4s/issues/32
        # sometimes things are wrongly deprecated!
        self.resp.setStatus(int(code), msg)

    def write(self, data):
        if not self.headers_set:
             raise AssertionError("write() before start_response()")

        if not self.headers_sent:
             # Before the first output, send the stored headers
             status, response_headers = self.headers_sent[:] = self.headers_set
             self.set_status(status)
             for name, value in response_headers:
                 self.resp.addHeader(name, value.encode("latin1"))

        out = self.resp.getOutputStream()
        print >> sys.stderr, "Writing data %r to output stream" % (data,)
        out.write(array.array("b", data))
        out.flush()

    def close(self):
        print >> sys.stderr, "Would close output stream... FIXME"
        self.resp.getOutputStream().close()

    def start_response(self, status, response_headers, exc_info=None):
        if exc_info:
            try:
                if self.headers_sent:
                    # Re-raise original exception if headers sent
                    raise exc_info[1].with_traceback(exc_info[2])
            finally:
                exc_info = None     # avoid dangling circular ref
        elif self.headers_set:
            raise AssertionError("Headers already set!")

        self.headers_set[:] = [status, response_headers]

        # Note: error checking on the headers should happen here,
        # *after* the headers are set.  That way, if an error
        # occurs, start_response can only be re-called with
        # exc_info set.

        # FIXME ok do that err checking! need to check what other
        # WSGI servers do here;
        # http://waitress.readthedocs.org/en/latest/ might be a
        # good choice
        return self.write


def get_application(config):
    # FIXME add more error checking on application setup
    application_name = config.getInitParameter("wsgi.handler")
    parts = application_name.split(".")
    if len(parts) < 2 or not all(parts):
        # FIXME better exception class
        raise Exception("wsgi.handler not configured properly", application_name)
    module_name = ".".join(parts[:-1])
    module = __import__(module_name)
    return getattr(module, parts[-1])


class ServletBase(object):

    def do_init(self, config):
        self.application = get_application(config)
        self.err_log = AdaptedErrLog(self)

    def get_bridge(self, req):
        return RequestBridge(req, self.err_log, AdaptedInputStream(req.getInputStream()))

    def do_wsgi_call(self, call):
        print >> sys.stderr, "About to make call WSGI app=%s" % (self.application,)
        result = self.application(call.environ, call.start_response)

        print >> sys.stderr, "result=%s" % (result,)
        try:
            for data in result:
                if data:    # don't send headers until body appears
                    print >> sys.stderr, "Writing data %r" % (data,)
                    call.write(data)
            if not call.headers_sent:
                call.write("")   # send headers now if body was empty
        finally:
            #print >> sys.stderr, "Closing call %s" % (call,)
            #call.close()
            # FIXME restore, but currently closing here causes an issue when part of a filter chain
            if hasattr(result, "close"):
                print >> sys.stderr, "Closing result %s" % (result,)
                result.close()
            

class FilterBase(object):

    def do_init(self, config):
        self.application = get_application(config)
        self.err_log = AdaptedErrLog(self)

    def filter_wsgi_call(self, req, resp, chain):
        bridge = RequestBridge(req, self.err_log, AdaptedInputStream(req.getInputStream()))
        environ = dict_builder(bridge.asMap)()
        # Can only set up the actual wrapped response once the filter coroutine is set up
        wrapped_req = bridge.asWrapper()
        call = WSGICall(environ, req, resp)

        progress = []
        call_filter = None

        def setup_puller():
            (yield)

            def null_app(environ, start_response):
                print "null_app environ=%s start_response=%s" % (environ, start_response)
                #for name in call.wrapped_resp.getHeaders():
                #    ...
                response_headers = [('Content-type', 'text/plain')]
                # status = call.wrapped_resp.getStatus()
                print >> sys.stderr, "null_app calling start_response"
                start_response("200 OK", response_headers)
                print >> sys.stderr, "null_app returning iter on output stream"

                output_stream = call.wrapped_resp.getOutputStream()
                for i, chunk in enumerate(output_stream):
                    print >> sys.stderr, "Got this chunk %d %r (%r)" % (i, chunk, progress)

                    # check if stalled (is there no progress in the below while loop?)
                    # if stalled, we have to wait until the filter chain is complete before
                    # we can return another chunk

                    yield chunk

                    if not progress:
                        print >> sys.stderr, "No progress being made, move the call to the filter chain to here"
                        progress[:] = [False]  # need three states! FIXME

                        def f(s):
                            print "null_app stalled value %r" % (s,)

                        output_stream.callback = f
                        call_filter()
                        print >> sys.stderr, "Filter chain completed"
                        for chunk in output_stream.getChunks():
                            yield chunk
                        return

                    if i > 100:  # FIXME remove this debugging stopgap (obviously)
                        print >> sys.stderr, "Stopping, obviously we are broken!!!!!"
                        break
                #return ["this is the fake response text"]

            wsgi_filter = self.application(null_app)
            result = wsgi_filter(call.environ, call.start_response)
            print >> sys.stderr, "got result from wsgi_filter %s" % (result,)
            it = iter(result)
            print >> sys.stderr, "got iterator %s" % (it,)
            while True:
                try:
                    print >> sys.stderr, "waiting on yield"
                    if not progress or progress[0] != False:
                        data = (yield)
                    else:
                        data = None
                    print >> sys.stderr, "completed yield, waiting on next of %s" % (it,)
                    filtered = next(it)
                    progress[:] = [True]
                    print >> sys.stderr, "%r -> %r" % (data, filtered)
                    print >> sys.stderr, "call %r" % (call,)
                    call.write(filtered)
                except StopIteration:
                    break
            if not call.headers_sent:
                call.write("")   # send headers now if body was empty

        puller = setup_puller()
        # fill in the wrapping servlet response
        call.wrapped_resp = CaptureHttpServletResponse(resp, puller.send)
        call_filter = lambda: chain.doFilter(wrapped_req, call.wrapped_resp)
        puller.send(None)  # advance the coroutine to before filtering
        puller.send(None)  # advance one more time to after sending the response
        if not progress or progress[0] != False:
            print >> sys.stderr, "Calling filter"
            call_filter()
        else:
            print >> sys.stderr, "Not calling filter, should be done in null_app"

        print >> sys.stderr, "Closing puller"
        puller.close() # put in a try-finally context


class AdaptedInputStream(object):

    # FIXME can we use available to be smarter/more responsive? related to supporting async ops

    def __init__(self, input_stream):
        self.input_stream = input_stream

    def _read_chunk(self, size):
        # Read a chunk of data from input, or None
        chunk = bytearray(size)
        result = self.input_stream.read(chunk)
        if result > 0:
            if result < size:
                chunk = buffer(chunk, 0, result)
            return chunk
        return None

    def read(self, size=None):
        if size is None:
            chunks = []
            while True:
                chunk = self._read_chunk(8192)
                if chunk is None:
                    break
                chunks.append(chunk)
            return "".join((str(chunk) for chunk in chunks))
        else:
            chunk = self._read_chunk(size)
            if chunk is None:
                return ""
            else:
                return str(chunk)

    def readline(self, size=None):
        if size is not None:
            chunk = bytearray(size)
            result = self.input_stream.readLine(chunk, 0, size)
            if result == -1:
                return ""
            else:
                return str(buffer(chunk, 0, result))
        else:
            chunks = []
            while True:
                # just assume relatively long lines, although there's
                # a probably a better heuristic amount to allocate
                chunk = bytearray(512)
                result = self.input_stream.readLine(chunk, 0, 512)
                if result == -1:
                    break
                chunks.append(chunk)
                if result < 512 or chunk[511] == "\n":
                    break
            return "".join((str(chunk) for chunk in chunks))

    def readlines(self, hint=None):
        # According to WSGI spec, can just ignore hint, so this will
        # suffice
        return [self.readline()]

    def next(self):
        line = self.readline()
        if line is "":
            raise StopIteration
        else:
            return line

    __next__ = next   # a nod to Python 3

    def __iter__(self):
        return self


class AdaptedErrLog(object):

    def __init__(self, servlet):
        self.servlet = servlet

    def flush(self):
	pass

    def write(self, msg):
        if not self.servlet.getServletConfig():
            sys.stderr.write("Servlet not configured: {}".format(msg))
        else:
            self.servlet.log(msg)

    def writelines(self, seq):
        for msg in seq:
            self.write(msg)
