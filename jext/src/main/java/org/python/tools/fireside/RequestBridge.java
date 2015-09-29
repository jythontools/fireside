// FIXME audit for any concurrency issues. It seems highly likely that the
// invalidation implied by the changed dict is robust, but need to verify
// via scenario analysis.
// However, current structures should be resilient against corruption.

// FIXME replace commented-out prints with appropriate logging, or remove

package org.python.tools.fireside;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletRequestWrapper;

import org.python.core.Py;
import org.python.core.PyObject;
import org.python.core.PyString;
import org.python.core.PyTuple;
import org.python.core.codecs;
import org.python.google.common.base.CharMatcher;
import org.python.google.common.cache.CacheBuilder;
import org.python.google.common.cache.CacheLoader;
import org.python.google.common.cache.LoadingCache;
import org.python.google.common.collect.ForwardingConcurrentMap;


public class RequestBridge {
    private final HttpServletRequest request;
    private final LoadingCache<PyObject, PyObject> cache;
    private final Set<PyObject> changed = Collections.newSetFromMap(new ConcurrentHashMap());
    private final Map<String, String> mapCGI;

    // keys
    private static final String WSGI_VERSION = "wsgi.version";
    private static final String WSGI_MULTITHREAD = "wsgi.multithread";
    private static final String WSGI_MULTIPROCESS = "wsgi.multiprocess";
    private static final String WSGI_RUN_ONCE = "wsgi.run_once";
    private static final String WSGI_ERRORS = "wsgi.errors";
    private static final String WSGI_INPUT = "wsgi.input";

    private static final String WSGI_URL_SCHEME = "wsgi.url_scheme";
    private static final PyString PY_WSGI_URL_SCHEME = Py.newString(WSGI_URL_SCHEME);

    private static final String REQUEST_METHOD = "REQUEST_METHOD";
    private static final PyString PY_REQUEST_METHOD = Py.newString(REQUEST_METHOD);
    private static final String SCRIPT_NAME = "SCRIPT_NAME";
    private static final PyString PY_SCRIPT_NAME = Py.newString(SCRIPT_NAME);
    private static final String PATH_INFO = "PATH_INFO";
    private static final PyString PY_PATH_INFO = Py.newString(PATH_INFO);
    private static final String QUERY_STRING = "QUERY_STRING";
    private static final PyString PY_QUERY_STRING = Py.newString(QUERY_STRING);
    private static final String CONTENT_TYPE = "CONTENT_TYPE";
    private static final PyString PY_CONTENT_TYPE = Py.newString(CONTENT_TYPE);
    private static final String REMOTE_ADDR = "REMOTE_ADDR";
    private static final PyString PY_REMOTE_ADDR = Py.newString(REMOTE_ADDR);
    private static final String REMOTE_HOST = "REMOTE_HOST";
    private static final PyString PY_REMOTE_HOST = Py.newString(REMOTE_HOST);
    private static final String REMOTE_PORT = "REMOTE_PORT";
    private static final PyString PY_REMOTE_PORT = Py.newString(REMOTE_PORT);
    private static final String SERVER_NAME = "SERVER_NAME";
    private static final PyString PY_SERVER_NAME = Py.newString(SERVER_NAME);
    private static final String SERVER_PORT = "SERVER_PORT";
    private static final PyString PY_SERVER_PORT = Py.newString(SERVER_PORT);
    private static final String SERVER_PROTOCOL = "SERVER_PROTOCOL";
    private static final PyString PY_SERVER_PROTOCOL = Py.newString(SERVER_PROTOCOL);
    private static final String CONTENT_LENGTH = "CONTENT_LENGTH";
    private static final PyString PY_CONTENT_LENGTH = Py.newString(CONTENT_LENGTH);

    public RequestBridge(final HttpServletRequest request, final PyObject errLog, final PyObject wsgiInputStream) {
        this.request = request;
        mapCGI = getMappingForCGI(request);
        // Cache all keys for a request - we are effectively building up the environ lazily,
        // while using updates to track for the request wrapper.
        //
        // This reduces overhead if not all keys are used, because of rewrites to/from latin1
        // encoding and other conversions and especially if not all keys are rewritten
        // in a servlet filter.
        cache = CacheBuilder.newBuilder().build(
                new CacheLoader<PyObject, PyObject>() {
                    public PyObject load(PyObject key) throws ExecutionException {
                        if (changed.contains(key)) {
//                            System.err.println("Do not load key=" + key);
                            throw new ExecutionException(null);
                        }
//                        System.err.println("Loading key=" + key);
                        // Unwrap so we can take advantage of Java 7's support for
                        // efficient string switch, via hashing. Effectively the below switch
                        // is a hash table.
                        String k = key.toString();
                        switch (k) {
                            case WSGI_VERSION:
                                return new PyTuple(Py.One, Py.Zero);
                            case WSGI_MULTITHREAD:
                                return Py.True;
                            case WSGI_MULTIPROCESS:
                                return Py.False;
                            case WSGI_RUN_ONCE:
                                return Py.False;
                            case WSGI_ERRORS:
                                return errLog;
                            case WSGI_INPUT:
                                return wsgiInputStream;
                            case WSGI_URL_SCHEME:
                                return latin1(request.getScheme());
                            case REQUEST_METHOD:
                                return latin1(request.getMethod());
                            case SCRIPT_NAME:
                                return latin1(request.getServletPath());
                            case PATH_INFO:
                                return emptyIfNull(request.getPathInfo());
                            case QUERY_STRING:
                                return emptyIfNull(request.getQueryString());
                            case CONTENT_TYPE:
                                return emptyIfNull(request.getContentType());
                            case REMOTE_ADDR:
                                return latin1(request.getRemoteAddr());
                            case REMOTE_HOST:
                                return latin1(request.getRemoteHost());
                            case REMOTE_PORT:
                                return Py.newString(String.valueOf(request.getRemotePort()));
                            case SERVER_NAME:
                                return latin1(request.getLocalName());
                            case SERVER_PORT:
                                return Py.newString(String.valueOf(request.getLocalPort()));
                            case SERVER_PROTOCOL:
                                return latin1(request.getProtocol());
                            case CONTENT_LENGTH:
                                return getContentLength();
                            default:
                                return getHeader(k);
                        }
                    }
                });
    }

    static private PyString latin1(String s) {
        if (CharMatcher.ASCII.matchesAllOf(s)) {
            return Py.newString(s);
        } else {
            return Py.newString(codecs.PyUnicode_EncodeLatin1(s, s.length(), null));
        }
    }

    static private PyString emptyIfNull(String s) {
        if (s == null) {
            return Py.EmptyString;
        } else {
            return latin1(s);
        }
    }

    private PyString getContentLength() throws ExecutionException {
        int length = request.getContentLength();
        if (length != -1) {
            return Py.newString(String.valueOf(length));
        } else {
            throw new ExecutionException(null);
        }
    }

    private static Map<String, String> getMappingForCGI(HttpServletRequest request) {
        Enumeration<String> names = request.getHeaderNames();
        Map<String, String> mapping = new LinkedHashMap();
        while (names.hasMoreElements()) {
            String name = names.nextElement();
            // It is possible that this mapping is not bijective, but that's just a basic
            // problem with CGI/WSGI naming. Also I would assume that real usage of HTTP headers
            // are not going to do that.
            //
            // Regardless, we preserve the ordering of entries via the LinkedHashMap.
            String cgiName = "HTTP_" + name.replace('-', '_').toUpperCase();
            mapping.put(cgiName, name);
        }
        return Collections.unmodifiableMap(mapping);
    }

    private PyString getHeader(String wsgiName) throws ExecutionException {
        // FIXME does this handle HTTP_COOKIE, or do we need to dispatch through on that as well?
//        System.err.println("mapCGI=" + mapCGI + ", wsgiName=" + wsgiName);
        String name = mapCGI.get(wsgiName);
        if (name != null) {
            // Referenced CGI specs are not directly available (FIXME add wayback archive URLs?)
            // One source is https://www.ietf.org/rfc/rfc3875, but does not specify actual concatenation!
            // but this seems reasonable:
            // http://stackoverflow.com/questions/1801124/how-does-wsgi-handle-multiple-request-headers-with-the-same-name
            Enumeration<String> values = request.getHeaders(name);
            if (values == null) {
                throw new ExecutionException(null);
            }
            StringBuilder builder = new StringBuilder();
            boolean firstThru = true;
            while (values.hasMoreElements()) {
                if (!firstThru) {
                    builder.append(";");
                }
                String value = values.nextElement();
                builder.append(latin1(value));
                firstThru = false;
            }
            if (firstThru) {
                // no header at all
                throw new ExecutionException(null);
            }
            return Py.newString(builder.toString());
        }
        // FIXME support THE_REQUEST, which also needs query params
        // FIXME support SSL_ prefixed headers by parsing req.getAttribute("javax.servlet.request.X509Certificate")
        // FIXME need to add both types of headers to getSettings()
        throw new ExecutionException(null);
    }

    // to be wrapped using jythonlib so it looks like a dict
    public ConcurrentMap asMap() {
        return new BridgeMap(this);
    }

    public HttpServletRequest asWrapper() {
        return new BridgeWrapper(this);
    }

    public LoadingCache cache() {
        return cache;
    }

    private Iterable<String> getSettings() {
        final List<String> settings = new ArrayList<>(
                Arrays.asList(WSGI_VERSION, WSGI_MULTITHREAD, WSGI_MULTIPROCESS, WSGI_RUN_ONCE,
                        WSGI_ERRORS, WSGI_INPUT, WSGI_URL_SCHEME,
                        REQUEST_METHOD, SCRIPT_NAME, PATH_INFO, QUERY_STRING, CONTENT_TYPE,
                        REMOTE_ADDR, REMOTE_HOST, REMOTE_PORT,
                        SERVER_NAME, SERVER_PORT, SERVER_PROTOCOL));
        if (request.getContentLength() != -1) {
            settings.add(CONTENT_LENGTH);
        }
        settings.addAll(mapCGI.keySet());
        return settings;
    }

    public void loadAll() {
//        System.err.println("loadAll changed=" + changed);
        for (String k : getSettings()) {
            try {
                if (!changed.contains(Py.newString(k))) {
//                    System.err.println("getting key=" + k);
                    cache.get(Py.newString(k));
                }
            } catch (ExecutionException e) {
                e.printStackTrace();
            }
        }
    }

    static class BridgeWrapper extends HttpServletRequestWrapper {
        RequestBridge bridge;

        public BridgeWrapper(RequestBridge bridge) {
            super(bridge.request);
            this.bridge = bridge;
        }

        public String intercept(PyString key) {
            try {
                PyObject value = (PyObject) bridge.cache().get(key);
                if (value == Py.None) {
                    return null;
                } else {
                    String s = value.toString();
                    return codecs.PyUnicode_DecodeLatin1(s, s.length(), null);
                }
            } catch (ExecutionException e) {
                return null;
            }
        }

        public int intercept_int(PyString key) {
            try {
                PyObject value = (PyObject) bridge.cache().get(key);
                if (value == Py.None) {
                    return -1;
                } else {
                    return value.asInt();
                }
            } catch (ExecutionException e) {
                return -1;
            }
        }

        public String getScheme() {
            if (!bridge.changed.contains(PY_WSGI_URL_SCHEME)) {
                return bridge.request.getScheme();
            } else {
                return intercept(PY_WSGI_URL_SCHEME);
            }
        }

        public String getMethod() {
            if (!bridge.changed.contains(PY_REQUEST_METHOD)) {
                return bridge.request.getMethod();
            } else {
                return intercept(PY_REQUEST_METHOD);
            }
        }

        public String getServletPath() {
            if (!bridge.changed.contains(PY_SCRIPT_NAME)) {
                return bridge.request.getServletPath();
            } else {
                return intercept(PY_SCRIPT_NAME);
            }
        }

        public String getPathInfo() {
            if (!bridge.changed.contains(PY_PATH_INFO)) {
                return bridge.request.getPathInfo();
            } else {
                return intercept(PY_PATH_INFO);
            }
        }

        public String getQueryString() {
            if (!bridge.changed.contains(PY_QUERY_STRING)) {
                return bridge.request.getQueryString();
            } else {
                return intercept(PY_QUERY_STRING);
            }
        }

        public String getContentType() {
            if (!bridge.changed.contains(PY_CONTENT_TYPE)) {
                return bridge.request.getContentType();
            } else {
                return intercept(PY_CONTENT_TYPE);
            }
        }

        public String getRemoteAddr() {
            if (!bridge.changed.contains(PY_REMOTE_ADDR)) {
                return bridge.request.getRemoteAddr();
            } else {
                return intercept(PY_REMOTE_ADDR);
            }
        }

        public String getRemoteHost() {
            if (!bridge.changed.contains(PY_REMOTE_HOST)) {
                return bridge.request.getRemoteHost();
            } else {
                return intercept(PY_REMOTE_HOST);
            }
        }

        public int getRemotePort() {
            if (!bridge.changed.contains(PY_REMOTE_PORT)) {
                return bridge.request.getRemotePort();
            } else {
                return intercept_int(PY_REMOTE_PORT);
            }
        }

        public String getLocalName() {
            if (!bridge.changed.contains(PY_SERVER_NAME)) {
                return bridge.request.getLocalName();
            } else {
                return intercept(PY_SERVER_NAME);
            }
        }

        public int getLocalPort() {
            if (!bridge.changed.contains(PY_SERVER_PORT)) {
                return bridge.request.getLocalPort();
            } else {
                return intercept_int(PY_SERVER_PORT);
            }
        }

        public String getProtocol() {
            if (!bridge.changed.contains(PY_SERVER_PROTOCOL)) {
                return bridge.request.getProtocol();
            } else {
                return intercept(PY_SERVER_PROTOCOL);
            }
        }

        public int getContentLength() {
            if (!bridge.changed.contains(PY_CONTENT_LENGTH)) {
                return bridge.request.getContentLength();
            } else {
                return intercept_int(PY_CONTENT_LENGTH);
            }
        }

        // FIXME
        // fill in additional methods from above
        // also return HTTP_* headers that are set via getHeader, getHeaderNames;
        // also support getDateHeader, getIntHeader helper methods
        // getCookies should also work
        // presumably we need to consider normalizing new HTTP_ headers, although we
        // can retain existing names. Ahh, the complexity of it all!

    }

    static class BridgeMap extends ForwardingConcurrentMap {

        private final RequestBridge bridge;

        public BridgeMap(RequestBridge bridge) {
            this.bridge = bridge;
        }

        public Object get(Object key) {
//            System.err.println("Getting key=" + key);
            try {
                return bridge.cache().get(key);
            } catch (ExecutionException e) {
                return null; // throw Py.KeyError((PyObject) key);
            }
        }

        public Object put(Object key, Object value) {
//            System.err.println("Updating key=" + key + ", value=" + value);
            bridge.changed.add((PyObject) key);
            return super.put(key, value);
        }

        public void clear() {
//            System.err.println("Clearing changes");
            for (Object key : bridge.cache().asMap().keySet()) {
                bridge.changed.add((PyObject) key);
            }
            super.clear();
        }

        public Object remove(Object key) {
            PyObject pyKey = (PyObject) key;
//            System.err.println("Removing key=" + (pyKey.__repr__()));
            bridge.changed.add(pyKey);
            // what if we remove a key that we haven't lazily loaded FIXME
            return bridge.cache().asMap().remove(key);
        }

        // FIXME override putAll... any others?

        protected ConcurrentMap delegate() {
            return bridge.cache().asMap();
        }

        // FIXME
        // probably do not have to override iterator remove, although I suppose if passed into Java this could cause issues;
        // presumably we can just override the Iterator in this case

        public Set keySet() {
//            System.err.println("keySet");
            // NB does not imply loadAll!
            return new StandardKeySet() {
            };
        }

        public Set<Map.Entry> entrySet() {
//            System.err.println("entrySet" + bridge.cache().asMap());
            bridge.loadAll();
            return bridge.cache().asMap().entrySet();
        }

    }

}
