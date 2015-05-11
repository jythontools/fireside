# Fireside - Blazing fast WSGI Servlet bridge.
#
# Named after a hot whiskey drink often made with coffee.

"""FIXME
Implement the following
If a call to len(iterable) succeeds, the server must be able to rely on the result being accurate. That is, if the iterable returned by the application provides a working __len__() method, it must return an accurate result. (See the Handling the Content-Length Header section for information on how this would normally be used.)
"""

import array
import sys


BASE_ENVIRONMENT = {
    "wsgi.version": (1, 0),
    "wsgi.multithread": True,
    "wsgi.multiprocess": False,
    "wsgi.run_once": False,
}


def empty_string_if_none(s):
    if s is None:
        return ""
    else:
        return str(s)


# FIXME move WSGIServlet, WSGIFilter to __init__ so we can get it named
# org.python.tools.fireside.WSGIServlet, ...

# Factor our generic servlet/filter code - maybe HttpBase? sounds good

# Copied with minimal adaptation from the spec:
# https://www.python.org/dev/peps/pep-3333/

# Need additional verifications; see
# https://github.com/Pylons/waitress/blob/master/waitress/task.py#L143 for some guidance here


class WSGICall(object):

    def __init__(self, environ, req, resp, before_write_callback=None):
        self.environ = environ
        self.req = req
        self.resp = resp
        self.before_write_callback = before_write_callback
        self.headers_set = []
        self.headers_sent = []

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
        out.write(array.array("b", data))
        out.flush()

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

        if self.before_write_callback:
            self.req.setAttribute("org.python.tools.fireside.environ", self.environ)
            self.before_write_callback()

        return self.write


class WSGIBase(object):

    def do_init(self, config):
        # FIXME add more error checking on application setup
        application_name = config.getInitParameter("wsgi.handler")
        parts = application_name.split(".")
        if len(parts) < 2 or not all(parts):
            # FIXME better exception class
            raise Exception("wsgi.handler not configured properly", application_name)
        module_name = ".".join(parts[:-1])
        module = __import__(module_name)
        self.application = getattr(module, parts[-1])
        self.servlet_environ = dict(BASE_ENVIRONMENT)
        self.servlet_environ.update({
            "wsgi.errors": AdaptedErrLog(self)
            })

    def get_environ(self, req):
        environ = req.getAttribute("org.python.tools.fireside.environ")
        if environ is not None:
            return environ
        environ = dict(self.servlet_environ)
        environ.update({
            "REQUEST_METHOD":  str(req.getMethod()),
            "SCRIPT_NAME": str(req.getServletPath()),
            "PATH_INFO": empty_string_if_none(req.getPathInfo()),
            "QUERY_STRING": empty_string_if_none(req.getQueryString()),  # per WSGI validation spec
            "CONTENT_TYPE": empty_string_if_none(req.getContentType()),
            "REMOTE_ADDR": str(req.getRemoteAddr()),
            "REMOTE_HOST": str(req.getRemoteHost()),
            "REMOTE_PORT": str(req.getRemotePort()),
            "SERVER_NAME": str(req.getLocalName()),
            "SERVER_PORT": str(req.getLocalPort()),
            "SERVER_PROTOCOL": str(req.getProtocol()),
            "wsgi.url_scheme": str(req.getScheme()),
            "wsgi.input": AdaptedInputStream(req.getInputStream())
            })
        content_length = req.getContentLength()
        if content_length != -1:
            environ["CONTENT_LENGTH"] = str(content_length)
        for header_name in req.getHeaderNames():
            headers = req.getHeaders(header_name)
            if headers:
                cgi_header_name = "HTTP_%s" % str(header_name).replace('-', '_').upper()
                environ[cgi_header_name] = ",".join([header.encode("latin1") for header in headers])
        return environ

    def do_wsgi_call(self, call):
        # refactor - the write loop needs to go in WSGICall
        result = self.application(call.environ, call.start_response)
        try:
            for data in result:
                if data:    # don't send headers until body appears
                    call.write(data)
            if not call.headers_sent:
                call.write("")   # send headers now if body was empty
        finally:
            if hasattr(result, "close"):
                result.close()


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
