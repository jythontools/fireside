package org.python.tools.fireside;

import java.util.Collections;
import java.util.Iterator;
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
import org.python.google.common.cache.CacheBuilder;
import org.python.google.common.cache.CacheLoader;
import org.python.google.common.cache.LoadingCache;
import org.python.google.common.collect.ForwardingConcurrentMap;
import org.python.google.common.collect.ImmutableList;
import org.python.google.common.collect.Iterators;


public class RequestBridge {
    private final HttpServletRequest request;
    private final LoadingCache<PyObject, PyObject> cache;
    static final PyObject TOMBSTONE = new PyObject();
    private final Set<PyObject> changed = Collections.newSetFromMap(new ConcurrentHashMap());

    public RequestBridge(final HttpServletRequest request) {
        this.request = request;
        cache = CacheBuilder.newBuilder().build(
                new CacheLoader<PyObject, PyObject>() {
                    public PyObject load(PyObject key) {
                        if (changed.contains(key)) {
                            System.err.println("Do not load key=" + key);
                            return Py.None; //  TOMBSTONE;
                        }
                        System.err.println("Loading key=" + key);
                        String k = key.toString();
                        if (k.equals("REQUEST_METHOD")) {
                            return Py.newString(request.getMethod());
                        } else if (k.equals("SCRIPT_NAME")) {
                            return Py.newString(request.getServletPath());
                        }
                        return Py.None;
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
                Iterators.forArray("REQUEST_METHOD", "SCRIPT_NAME"), // etc
                Iterators.forEnumeration(request.getHeaderNames())));

        // canonical CGI settings from supported methods in HttpServletRequest, plus those in getHeaderNames (Enumeration)
// use http://docs.guava-libraries.googlecode.com/git/javadoc/com/google/common/collect/Iterators.html#forEnumeration(java.util.Enumeration)
    }

    public void loadAll() {
        for (String k : settings()) {
            try {
                if (!changed.contains(k)) {
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

        public String getMethod() {
            PyString requestMethodKey = Py.newString("REQUEST_METHOD");
            if (!bridge.changed.contains(requestMethodKey)) {
                return bridge.request.getMethod();
            }
            try {
                System.err.println("Intercepted key for REQUEST_METHOD");
                PyObject requestMethod = (PyObject)bridge.cache().get(requestMethodKey);
                if (requestMethod == TOMBSTONE) {
                    return null;
                } else {
                    return requestMethod.toString();
                }
            } catch (ExecutionException e) {
                return null;
            }

        }
    }
//
//        public String getServletPath() {
//            String servletPath = bridge.changes.get("SCRIPT_NAME");
//            if (servletPath != null) {
//                return servletPath;
//            } else {
//                return bridge.request.getServletPath();
//            }
//        }
//
//        public String getPathInfo() {
//            String pathInfo = bridge.changes.get("PATH_INFO");
//            if (pathInfo != null) {
//                return pathInfo;
//            } else {
//                return bridge.request.getPathInfo();
//            }
//        }
//
//        public String getQueryString() {
//            String queryString = bridge.changes.get("QUERY_STRING");
//            if (queryString != null) {
//                return queryString;
//            } else {
//                return bridge.request.getQueryString();
//            }
//        }
//
//        public String getContentType() {
//            String contentType = bridge.changes.get("CONTENT_TYPE");
//            if (contentType != null) {
//                return contentType;
//            } else {
//                return bridge.request.getContentType();
//            }
//        }

//
//        "REQUEST_METHOD":  str(req.getMethod()),
//                "SCRIPT_NAME": str(req.getServletPath()),
//                "PATH_INFO": empty_string_if_none(req.getPathInfo()),
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
                Object value = bridge.cache().get(key);
                if (value == TOMBSTONE) {
                    return null;
                } else {
                    return value;
                }
            } catch (ExecutionException e) {
                throw Py.KeyError((PyObject) key);
            }
        }

        public Object put(Object key, Object value) {
            System.err.println("Updating key=" + key + ", value=" + value);
            bridge.changed.add((PyObject)key);
            return super.put(key, value);
        }

        public void clear() {
            System.err.println("Clearing changes");
            super.clear();
        }

        public Object remove(Object key) {
            System.err.println("Removing key=" + key);
            bridge.changed.add((PyObject) key);
            return bridge.cache().asMap().remove(key);
        }

        protected ConcurrentMap delegate() {
            return bridge.cache().asMap();
        }

        // also override put, putAll, clear, remove; for now, let's just implement something that says we are recording this


        // probably do not have to override iterator remove, although I suppose if passed into Java this could cause issues;
        // presumably we can just override the Iterator in this case

        public Set keySet() {
            // does not imply loadAll! so need to come up with a class that allows works with these keys, including removal, without doing the entrySet implied by ForwardingMap.StandardKeySet - DO NOT USE THAT!
            // something like the following might work
            return new StandardKeySet() {
            };
        }
//
        public Set<Map.Entry> entrySet() {
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