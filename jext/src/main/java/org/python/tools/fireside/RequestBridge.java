// FIXME we may have an issue with concurrent usage. presumably such usage should be sequenced via a mutex of some kind,
// so it's just a question of ensuring tracking structures are not corrupted

package org.python.tools.fireside;

import java.util.Collections;
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
import org.python.core.codecs;
import org.python.google.common.base.CharMatcher;
import org.python.google.common.cache.CacheBuilder;
import org.python.google.common.cache.CacheLoader;
import org.python.google.common.cache.LoadingCache;
import org.python.google.common.collect.ForwardingConcurrentMap;
import org.python.google.common.collect.ImmutableList;
import org.python.google.common.collect.Iterators;


public class RequestBridge {
    private final HttpServletRequest request;
    private final LoadingCache<PyObject, PyObject> cache;
    private final Set<PyObject> changed = Collections.newSetFromMap(new ConcurrentHashMap());
    private static final PyObject TOMBSTONE = new PyObject();

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
    private static final String WSGI_URL_SCHEME = "wsgi.url_scheme";
    private static final PyString PY_WSGI_URL_SCHEME = Py.newString(WSGI_URL_SCHEME);

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

    public RequestBridge(final HttpServletRequest request) {
        this.request = request;
        cache = CacheBuilder.newBuilder().build(
                new CacheLoader<PyObject, PyObject>() {
                    public PyObject load(PyObject key) {
                        if (changed.contains(key)) {
                            System.err.println("Do not load key=" + key);
                            return Py.None; // acts as a tombstone
                        }
                        System.err.println("Loading key=" + key);
                        String k = key.toString();
                        switch (k) {
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
                                return latin1(request.getServerName());
                            case SERVER_PORT:
                                return Py.newString(String.valueOf(request.getServerPort()));
                            case SERVER_PROTOCOL:
                                return latin1(request.getProtocol());
                            case WSGI_URL_SCHEME:
                                return latin1(request.getScheme());
                            default:
                                return Py.None;
                        }
                    }
                });
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

    Iterable<String> settings() {
        return ImmutableList.copyOf(Iterators.concat(
                Iterators.forArray(REQUEST_METHOD, SCRIPT_NAME, PATH_INFO), // FIXME add remaining keys
                Iterators.forEnumeration(request.getHeaderNames())));
    }

    public void loadAll() {
        System.err.println("loadAll changed=" + changed);
        for (String k : settings()) {
            try {
                if (!changed.contains(Py.newString(k))) {
                    System.err.println("getting key=" + k);
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
                if (value == Py.None || value == TOMBSTONE) {
                    return null;
                } else {
                    return value.toString(); // FIXME decode from latin1 to unicode
                }
            } catch (ExecutionException e) {
                return null;
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
                return bridge.request.getMethod();
            } else {
                return intercept(PY_SCRIPT_NAME);
            }
        }

        public String getPathInfo() {
            if (!bridge.changed.contains(PY_PATH_INFO)) {
                return bridge.request.getMethod();
            } else {
                return intercept(PY_PATH_INFO);
            }
        }


    }

//
//        "PY_REQUEST_METHOD":  str(req.getMethod()),
//                "PY_SCRIPT_NAME": str(req.getServletPath()),
//                "PY_PATH_INFO": empty_string_if_none(req.getPathInfo()),
//                "QUERY_STRING": empty_string_if_none(req.getQueryString()),  # per WSGI validation spec
//        "CONTENT_TYPE": empty_string_if_none(req.getContentType()),
//                "REMOTE_ADDR": str(req.getRemoteAddr()),
//                "REMOTE_HOST": str(req.getRemoteHost()),
//                "REMOTE_PORT": str(req.getRemotePort()),
//                "SERVER_NAME": str(req.getLocalName()),
//                "SERVER_PORT": str(req.getLocalPort()),
//                "SERVER_PROTOCOL": str(req.getProtocol()),
//                "wsgi.url_scheme": str(req.getScheme()),
//                "wsgi.input": AdaptedInputStream(req.getInputStream())


    static class BridgeMap extends ForwardingConcurrentMap {

        private final RequestBridge bridge;

        public BridgeMap(RequestBridge bridge) {
            this.bridge = bridge;
        }

        public Object get(Object key) {
            System.err.println("Getting key=" + key);
            try {
                return bridge.cache().get(key);
            } catch (ExecutionException e) {
                throw Py.KeyError((PyObject) key);
            }
        }

        public Object put(Object key, Object value) {
            System.err.println("Updating key=" + key + ", value=" + value);
            bridge.changed.add((PyObject) key);
            return super.put(key, value);
        }

        public void clear() {
            System.err.println("Clearing changes");
            // most likely need to add all keys to changed! FIXME
            super.clear();
        }

        public Object remove(Object key) {
            PyObject pyKey = (PyObject) key;
            System.err.println("Removing key=" + (pyKey.__repr__()));
            bridge.changed.add(pyKey);
            // what if we remove a key that we haven't lazily loaded FIXME
            return bridge.cache().asMap().remove(key);
        }

        protected ConcurrentMap delegate() {
            return bridge.cache().asMap();
        }

        // also override put, putAll, clear, remove; for now, let's just implement something that says we are recording this


        // probably do not have to override iterator remove, although I suppose if passed into Java this could cause issues;
        // presumably we can just override the Iterator in this case

        public Set keySet() {
            System.err.println("keySet");
            // does not imply loadAll! so need to come up with a class that allows works with these keys, including removal, without doing the entrySet implied by ForwardingMap.StandardKeySet - DO NOT USE THAT!
            // something like the following might work
            return new StandardKeySet() {
            };
        }

        //
        public Set<Map.Entry> entrySet() {
            System.err.println("entrySet" + bridge.cache().asMap());
            bridge.loadAll();
            return bridge.cache().asMap().entrySet();
//            return new StandardEntrySet() {
//
//                @Override
//                public Iterator<Entry<Object, Object>> iterator() {
//                    bridge.cache().asMap().entrySet().iterator();
//                }
//            };
        }
//
//        Collection<V> values() {
//            bridge.loadAll();
//            return new StandardValues(delegate());
//        }

    }

}