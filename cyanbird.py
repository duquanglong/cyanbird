# -*- coding: utf-8 -*-
__license__ = "MIT"
__version__ = "0.1"
__author__ = "Zhao Wei <kaihaosw@gmail.com>"
__all__ = ["GET", "POST", "Response", "response", "redirect", "not_found", "run"]
import re
from functools import wraps
from urlparse import parse_qs
from urllib import quote
from cgi import FieldStorage
from datetime import datetime
import time

if type("") is not type(b""):  # PY3
    bytestr = bytes
    unicodestr = str
    nativestr = unicodestr

    def ntob(n, encoding='ISO-8859-1'):
        assert_native(n)
        return n.encode(encoding)

    def ntou(n, encoding='ISO-8859-1'):
        assert_native(n)
        return n

    def tonative(n, encoding='ISO-8859-1'):
        if isinstance(n, bytes):
            return n.decode(encoding)
        return n

    from Cookie import SimpleCookie
else:
    bytestr = str
    unicodestr = unicode
    nativestr = bytestr

    def ntob(n, encoding='ISO-8859-1'):
        assert_native(n)
        return n

    def ntou(n, encoding='ISO-8859-1'):
        assert_native(n)
        if encoding == 'escape':
            return unicode(
                re.sub(r'\\u([0-9a-zA-Z]{4})',
                       lambda m: unichr(int(m.group(1), 16)),
                       n.decode('ISO-8859-1')))
        return n.decode(encoding)

    def tonative(n, encoding='ISO-8859-1'):
        if isinstance(n, unicode):
            return n.encode(encoding)
        return n

    from Cookie import SimpleCookie


def assert_native(n):
    if not isinstance(n, nativestr):
        raise TypeError("n must be a native str (got %s)" % type(n).__name__)


_HTTP_STATUS = {
    100: "100 Continue",
    101: "101 Switching Protocols",
    200: "200 OK",
    201: "201 Created",
    202: "202 Accepted",
    203: "203 Non-Authoritative Information",
    204: "204 No Content",
    205: "205 Reset Content",
    206: "206 Partial Content",
    207: "207 Multi-Status",
    300: "300 Multiple Choices",
    301: "301 Moved Permanently",
    302: "302 Found",
    303: "303 See Other",
    304: "304 Not Modified",
    305: "305 Use Proxy",
    307: "307 Temporary Redirect",
    400: "400 Bad Request",
    401: "401 Unauthorized",
    402: "402 Payment Required",
    403: "403 Forbidden",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    406: "406 Not Acceptable",
    407: "407 Proxy Authentication Required",
    408: "408 Request Timeout",
    409: "409 Conflict",
    410: "410 Gone",
    411: "411 Length Required",
    412: "412 Precondition Failed",
    413: "413 Request Entity Too Large",
    414: "414 Request-Uri Too Long",
    415: "415 Unsupported Media Type",
    416: "416 Requested Range Not Satisfiable",
    417: "417 Expectation Failed",
    500: "500 Internal Server Error",
    501: "501 Not Implemented",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
    504: "504 Gateway Timeout",
    505: "505 Http Version Not Supported"
}


class MultiValueDict(dict):
    """ MultiValueDict from Django.
    """
    def __init__(self, key_to_list_mapping=()):
        super(MultiValueDict, self).__init__(key_to_list_mapping)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__,
                             super(MultiValueDict, self).__repr__())

    def __getitem__(self, key):
        try:
            _list = super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            raise KeyError
        try:
            return _list[-1]
        except IndexError:
            return []

    def __setitem__(self, key, value):
        super(MultiValueDict, self).__setitem__(key, [value])

    def get(self, key, default=None):
        try:
            val = self[key]
        except KeyError:
            return default
        if val == []:
            return default
        return val

    def getlist(self, key, default=None):
        try:
            return super(MultiValueDict, self).__getitem__(key)
        except KeyError:
            if default is None:
                return []
            return default

    def setlist(self, key, list_):
        super(MultiValueDict, self).__setitem__(key, list_)

    def setdefault(self, key, default=None):
        if key not in self:
            self[key] = default
        return self[key]

    def setlistdefault(self, key, default_list=None):
        if key not in self:
            if default_list is None:
                default_list = []
            self.setlist(key, default_list)
        return self.getlist(key)

    def appendlist(self, key, val):
        self.setlistdefault(key).append(val)

    def _iteritems(self):
        for key in self:
            yield key, self[key]

    def _itervalues(self):
        for key in self:
            yield self[key]

    iteritems = _iteritems
    itervalues = _itervalues

    def items(self):
        return list(self.iteritems())

    def values(self):
        return list(self.itervalues())


def lazyproperty(f):
    """ Class decorator which evals only once.
    """
    attr_name = "_lazy_" + f.__name__

    @property
    @wraps(f)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, f(self))
        return getattr(self, attr_name)
    return wrapper


def _parse_qs(s):
    """ Parse a query_string and return a MultidictValue type dict.
    """
    qs = parse_qs(s, keep_blank_values=True)
    return MultiValueDict(qs)


def _parse_multipart(fp, ctype, clength):
    """ Parse multipart/form-data request. Returns a tuple (form, files).
    """
    fs = FieldStorage(fp=fp,
                      environ={"REQUEST_METHOD": "POST"},
                      headers={"content-type": ctype,
                               "content-length": clength},
                      keep_blank_values=True)

    form = MultiValueDict()
    files = MultiValueDict()
    for f in fs.list:
        if f.filename:
            files.appendlist(f.name, f)
        else:
            form.appendlist(f.name, f.value)
    return form, files


def _format_gmt_time(t):
    """ Parse a time to `Weekday, DD-Mon-YY HH:MM:SS GMT`.
    """
    if isinstance(t, time.struct_time):
        pass
    elif isinstance(t, datetime):
        t = t.utctimetuple()
    elif isinstance(t, (int, long)):
        t = time.gmtime(t)
    else:
        raise Exception("Expires format is illegal.")
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", t)


def _add_slash(url, end=True):
    """ Add a slash at the end or front of the url.
    """
    if end:
        if not url.endswith("/"):
            url += "/"
        return url
    else:
        if not url.startswith("/"):
            url = "/" + url
        return url


class Request(object):
    """ Request object which handlers the `environ`.
    """
    def __init__(self, env):
        self.env = env

    def __setitem__(self, key, value):
        self.env[key] = value

    @lazyproperty
    def ctype(self):
        return self.env["CONTENT_TYPE"]

    @lazyproperty
    def clength(self):
        return int(self.env.get("CONTENT_LENGTH", "0"))

    @lazyproperty
    def method(self):
        return self.env["REQUEST_METHOD"].upper()

    @lazyproperty
    def path(self):
        return _add_slash(quote(self.env.get("SCRIPT_NAME", "")) +
                          quote(self.env.get("PATH_INFO", "")))

    @lazyproperty
    def args(self):
        return _parse_qs(tonative(self.env.get("QUERY_STRING", "")))

    @lazyproperty
    def cookies(self):
        if not hasattr(self, "_cookies"):
            self._cookies = SimpleCookie()
            if self.env.get("HTTP_COOKIE", None):
                try:
                    self._cookies.load(tonative(self.env["HTTP_COOKIE"]))
                except Exception:
                    self._cookies = None
        return self._cookies

    def get_cookie(self, key, default=None):
        if self.cookies and key in self.cookies:
            return self.cookies[key].value
        return default

    @lazyproperty
    def forms(self):
        if not hasattr(self, "_forms"):
            self._load_body()
        return self._forms

    @lazyproperty
    def file(self):
        if not hasattr(self, "_file"):
            self._load_body()
        return self._file

    def _load_body(self):
        wi = self.env["wsgi.input"]
        if self.ctype.startswith("application/x"):
            self._forms, self._file = _parse_qs(wi.read(self.clength)), None
        elif self.ctype.startswith("multipart"):
            self._forms, self._file = _parse_multipart(wi, self.ctype,
                                                       self.clength)
        else:
            self._forms, self._file = None, None


class Response(object):
    def __init__(self, code=200, content_type="text/html; charset=UTF-8"):
        self.status = _HTTP_STATUS.get(code, "UNKNOWN")
        self.headers = [("Content-Type", content_type)]
        self._response = []

    def redirect(self, url):
        self.headers.append(("Location", url))

    def write(self, msg):
        self._response.append(tonative(msg))

    def set_cookie(self, key, value="", max_age=None, expires=None,
                   path="/", domain=None, secure=None):
        if not hasattr(self, "_cookies"):
            self._cookies = SimpleCookie()
        self._cookies[key] = value
        if max_age:
            self._cookies[key]["max-age"] = max_age
        if expires:
            self._cookies[key]["expires"] = _format_gmt_time(expires)
        if path:
            self._cookies[key]["path"] = path
        if domain:
            self._cookies[key]["domain"] = domain
        if secure:
            self._cookies[key]["secure"] = secure
        print self._cookies

    def delete_cookie(self, key):
        if self._cookies is None:
            self._cookies = SimpleCookie()
        if not key in self._cookies:
            self._cookies[key] = ""
        self._cookies[key]["max-age"] = 0

    def __call__(self, start_response):
        self.headers.append(("Content-Length",
                             str(sum(len(n) for n in self._response))))
        if hasattr(self, "_cookies"):
            for morsel in self._cookies.values():
                self.headers.append(("Set-Cookie", morsel.output(header="")))
        start_response(self.status, self.headers)
        return self._response


def response(body):
    """ Return a response for `200 OK` response.
    """
    resp = Response()
    resp.write(body)
    return resp


def redirect(url):
    """ Return a response for an HTTP `302 redirect`.
    """
    resp = Response(code=302)
    resp.redirect(url)
    return resp


def not_found(body="Not Found"):
    """ Return a response for an HTTP `404 not found`.
    """
    resp = Response(code=404, content_type="text/plain")
    resp.write(body)
    return resp


# handler
_REQUEST_MAPPINGS = {
    "GET": [],
    "POST": []
}


def application_handler(env, start_response):
    """ The handler for request and response.
    """
    request = Request(env)
    for re_url, callback in _REQUEST_MAPPINGS[request.method]:
        match = re_url.search(request.path)
        if match:
            kwargs = match.groupdict()
            resp = callback(request, **kwargs)
            if not isinstance(resp, Response):
                response = Response()
                response.write(resp)
                return response(start_response)
            return resp(start_response)
    return not_found()(start_response)


# route decorators
def _route_abstract(method, url, base=""):
    if base:
        url = _add_slash(base, end=False) + _add_slash(url)
    else:
        url = _add_slash(url)

    def wrapper(f):
        re_url = re.compile(r"^%s$" % url)
        _REQUEST_MAPPINGS[method].append((re_url, f))
    return wrapper


def GET(url, base=""):
    """ The `GET` decorator.
    """
    return _route_abstract("GET", url, base=base)


def POST(url, base=""):
    """ The `POST` decorator.
    """
    return _route_abstract("POST", url, base=base)


# adapter
def wsgiref_adapter(app, host, port):
    """ The standard built-in wsgiref adapter.
    """
    from wsgiref.simple_server import make_server
    make_server(app=app, host=host, port=port).serve_forever()

_ADAPTER = {
    "wsgiref": wsgiref_adapter,
}


# server
def run(host="127.0.0.1", port=8080, adapter="wsgiref"):
    try:
        f = _ADAPTER[adapter]
    except KeyError:
        raise KeyError("The adapter %s is not exists!" % adapter)
    try:
        print("Please visit http//:%s:%s" % (host, port))
        print("Press Ctrl+c Ctrl+c to interrupt")
        f(application_handler, host, port)
    except KeyboardInterrupt:
        print("Shuting down.")
