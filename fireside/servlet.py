# Fireside - Blazing fast WSGI Servlet bridge.
#
# Named after a hot whiskey drink often made with coffee.

import array
from javax.servlet.http import HttpServlet

from clamp import clamp_base


ToolBase = clamp_base("org.python.tools")


# FIXME benchmark w/ ab


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
        return s


class WSGIServlet(ToolBase, HttpServlet):

    def init(self, config):
        # print "config", config
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
            "wsgi.errors": AdaptedErrLog(self.log)
            })
        # print "init", self.application, self.servlet_environ

    def service(self, req, resp):
        environ = dict(self.servlet_environ)
        environ.update({
            # For now, assume that we only pass strings, not unicode
            "REQUEST_METHOD":  str(req.getMethod()),
            "SCRIPT_NAME": str(req.getServletPath()),
            "PATH_INFO": str(empty_string_if_none(req.getPathInfo())),
            "QUERY_STRING": str(empty_string_if_none(req.getQueryString())),  # per WSGI validation spec
            "CONTENT_TYPE": str(empty_string_if_none(req.getContentType())),
            "SERVER_NAME": str(req.getLocalName()),
            "SERVER_PORT": str(req.getLocalPort()),
            "wsgi.url_scheme": str(req.getScheme()),
            "wsgi.input": AdaptedInputStream(req.getInputStream())
            })
        content_length = req.getContentLength()
        if content_length != -1:
            environ["CONTENT_LENGTH"] = str(content_length)

        # print "Processing request", environ, self.application
                                               
        # Copied with minimal adaptation from the spec:
        # http://legacy.python.org/dev/peps/pep-3333/#the-server-gateway-side

        headers_set = []
        headers_sent = []

        def write(data):
            out = resp.getOutputStream()

            if not headers_set:
                 raise AssertionError("write() before start_response()")

            elif not headers_sent:
                 # Before the first output, send the stored headers
                 status, response_headers = headers_sent[:] = headers_set

                 # FIXME any specific req for cookie support? probably just headers
                 resp.setStatus(int(status.split()[0]))  # convert from such usage as "200 OK"
                 for header in response_headers:
                     # FIXME what encoding if any to be applied here?
                     resp.setHeader(*header)

            out.write(array.array("b", data))  # FIXME probably impossible to avoid copy in Jython
            out.flush()  # FIXME implies flushBuffer?

        def start_response(status, response_headers, exc_info=None):
            if exc_info:
                try:
                    if headers_sent:
                        # Re-raise original exception if headers sent
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None     # avoid dangling circular ref
            elif headers_set:
                raise AssertionError("Headers already set!")

            headers_set[:] = [status, response_headers]

            # Note: error checking on the headers should happen here,
            # *after* the headers are set.  That way, if an error
            # occurs, start_response can only be re-called with
            # exc_info set.

            # FIXME ok do that err checking!

            return write

        result = self.application(environ, start_response)
        try:
            for data in result:
                if data:    # don't send headers until body appears
                    write(data)
            if not headers_sent:
                write("")   # send headers now if body was empty
        finally:
            if hasattr(result, "close"):
                result.close()


class AdaptedInputStream(object):

    # FIXME obviously need to figure out mocks necessary to model a ServletInputStream,
    # including extra functionality like readLine

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
        # FIXME apparently we can just ignore hint; for now this should suffice
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

    def __init__(self, logger):
        self.logger = logger

    def flush(self):
	pass

    def write(self, msg):
        self.logger(msg)

    def writelines(self, seq):
        for msg in seq:
            self.logger(msg)

