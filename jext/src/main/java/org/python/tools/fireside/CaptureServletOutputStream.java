package org.python.tools.fireside;

import org.python.core.Py;
import org.python.core.PyObject;
import org.python.core.PyString;

import java.io.IOException;
import java.util.Collection;
import java.util.Deque;
import java.util.Iterator;
import java.util.concurrent.ConcurrentLinkedDeque;

import javax.servlet.ServletOutputStream;
import javax.servlet.WriteListener;

public class CaptureServletOutputStream extends ServletOutputStream implements Iterator<PyString> {
    private volatile boolean closed = false;
    private final Deque<PyString> chunks = new ConcurrentLinkedDeque<>();
    private PyObject callback;

    public CaptureServletOutputStream(PyObject callback) {
        this.callback = callback;
    }

    public void setCallback(PyObject callback) {
        this.callback = callback;
    }

    public Iterator<PyString> getChunks() {
        return chunks.iterator();
    }

    @Override
    public void close() {
        closed = true;
    }

    private void checkClosed() throws IOException {
        if (closed) {
            throw new IOException("Output stream is closed");
        };
    }

    private void write(PyString s) throws IOException {
        System.err.println("append chunk=" + s);
        chunks.addLast(s);
        callback.__call__(s);
    }

    @Override
    public void write(int b) throws IOException {
        checkClosed();
        // Writing one byte at a time is going to be inefficient.
        // Of course it will be. :)
        write(Py.newString((char) (b & 0x7ff)));
    }

    @Override
    public void write(byte b[]) throws IOException {
        write(b, 0, b.length);
    }

    @Override
    public void write(byte b[], int off, int len) throws IOException {
        checkClosed();
        StringBuilder builder = new StringBuilder(len - off);
        for (int i = off; i < len; i++) {
            builder.append((char)b[i]);
        }
        write(Py.newString(builder.toString()));
    }

    @Override
    public boolean isReady() {
        return true;
    }

    @Override
    public void setWriteListener(WriteListener listener) {
        try {
            // writes are immediately and always possible due to the
            // use of the chunks deque
            listener.onWritePossible();
        } catch (IOException ioe) {
            // doesn't make sense to do anything but ignore if
            // the coupled listener fails
        }
    }

    @Override
    public boolean hasNext() {
        return !closed;
    }

    @Override
    public PyString next() {
        if (closed) {
            throw Py.StopIteration("");
        }
        PyString chunk = chunks.pollFirst();
        if (chunk == null) {
//            System.err.println("CaptureServletOutputStream has no data, returning empty string");
//            throw Py.StopIteration("");
            return Py.EmptyString;
        } else {
            return chunk;
        }
    }

    @Override
    public void remove() {
        throw new UnsupportedOperationException();
    }
}
