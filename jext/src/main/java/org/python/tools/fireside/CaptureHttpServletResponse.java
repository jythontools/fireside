// from http://www.java-forums.org/java-servlet/20631-how-get-content-httpservletresponse.html
// most likely have to rewrite given lack of licensing info!

package org.python.tools.fireside;

import org.python.core.PyObject;

import java.io.IOException;
import java.io.OutputStreamWriter;
import java.io.PrintWriter;

import javax.servlet.ServletOutputStream;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpServletResponseWrapper;


public class CaptureHttpServletResponse extends HttpServletResponseWrapper {
    private final CaptureServletOutputStream stream;

    public CaptureHttpServletResponse(HttpServletResponse response, PyObject callback) {
        super(response);
        stream = new CaptureServletOutputStream(callback);
    }

    @Override
    public ServletOutputStream getOutputStream() {
        return stream;
    }

    @Override
    public PrintWriter getWriter() throws IOException {
        return new PrintWriter(new OutputStreamWriter(stream, "UTF-8"));
    }

}
