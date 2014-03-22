# -*- coding: utf-8 -*-
__license__ = "MIT"
__version__ = "0.20"
__author__ = "Zhao Wei <kaihaosw@gmail.com>"
import re
import os
from functools import wraps
from cgi import FieldStorage
from datetime import datetime
import time
import mimetypes
from urlparse import parse_qs
from urllib import quote
from Cookie import SimpleCookie
from cStringIO import StringIO as BytesIO
from string import Template


##,-------------------------------
##| Cyanbird Exceptions and Errors
##`-------------------------------
class CyanBirdException(Exception):
    """ Basic Exception for cyanbird. """
    pass


class HTTPError(CyanBirdException):
    def __init__(self, code, msg):
        self.status_code, self.msg = code, msg

    def __str__(self):
        return self.status_code, self.msg


##,---------------
##| Cyanbird utils
##`---------------
class MultiValueDict(dict):
    """ MultiValueDict from Django. """
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
    """ Class decorator which evals only once. """
    attr_name = "_lazy_" + f.__name__

    @property
    @wraps(f)
    def wrapper(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, f(self))
        return getattr(self, attr_name)
    return wrapper


def _parse_qs(s):
    """ Parse a query_string and return a MultidictValue type dict. """
    qs = parse_qs(s, keep_blank_values=True)
    return MultiValueDict(qs)


def _parse_multipart(fp, ctype, clength):
    """ Parse multipart/form-data request. Returns a tuple (form, files). """
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
    """ Parse a time to `Weekday, DD-Mon-YY HH:MM:SS GMT`. """
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
    """ Add a slash at the end or front of the url. """
    if end:
        if not url.endswith("/"):
            url += "/"
    else:
        if not url.startswith("/"):
            url = "/" + url
    return url


##,--------------
##| Cyanbird main
##`--------------
class Cyanbird(object):
    def __init__(self, path=""):
        self.path = os.path.abspath(path)
        self.routes = []
        self.errors = {}

    def route(self, url, method="GET"):
        def wrapper(f):
            self.routes.append(Route(url, f, method))
            return f
        return wrapper

    def error(self, code):
        def wrapper(f):
            self.errors[code] = (Error(code, f))
            return f
        return wrapper

    def wsgi(self, env, start_response):
        request = Request(env)
        for route in self.routes:
            if route.match(request) is not None:
                resp = route.dispatch(request)
                if not isinstance(resp, Response):
                    response = Response()
                    response.write(resp)
                    return response(start_response)
                return resp(start_response)
        resp = self.errors[404]()
        response = Response(404)
        response.write(resp)
        return response(start_response)

    def __call__(self, env, start_response):
        return self.wsgi(env, start_response)

    def run(self, host="127.0.0.1", port=8080, debug=False, reload=False):
        from wsgiref.simple_server import make_server
        make_server(app=self, host=host, port=port).serve_forever()


##,------------------
##| Cyanbird Requests
##`------------------
class Request(object):
    """ Request object which handlers the `environ`. """
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
        return self.env.get("REQUEST_METHOD", "GET").upper()

    @lazyproperty
    def path(self):
        return _add_slash(quote(self.env.get("SCRIPT_NAME", "")) +
                          quote(self.env.get("PATH_INFO", "")))

    @lazyproperty
    def args(self):
        return _parse_qs(self.env.get("QUERY_STRING", ""))

    @lazyproperty
    def cookies(self):
        if not hasattr(self, "_cookies"):
            self._cookies = SimpleCookie()
            if self.env.get("HTTP_COOKIE", None):
                try:
                    self._cookies.load(self.env["HTTP_COOKIE"])
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


##,-------------------
##| Cyanbird Responses
##`-------------------
_HTTP_STATUS = {
    200: "200 OK",
    201: "201 Created",
    300: "300 Multiple Choices",
    301: "301 Moved Permanently",
    302: "302 Found",
    303: "303 See Other",
    304: "304 Not Modified",
    307: "307 Temporary Redirect",
    400: "400 Bad Request",
    403: "403 Forbidden",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    410: "410 Gone",
    500: "500 Internal Server Error"}


class Response(object):
    def __init__(self, code=200, content_type="text/html; charset=UTF-8"):
        self.status = _HTTP_STATUS.get(code, "UNKNOWN")
        self.headers = [("Content-Type", content_type)]
        self._response = []

    def redirect(self, url):
        self.headers.append(("Location", url))

    def write(self, msg):
        self._response.append(msg)

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


def http_error(code, body=""):
    """ Return a error based on the status_code.
    """
    assert code >= 400 and code <= 505
    resp = Response(code=code)
    if code == 404:
        resp.write(body)
    return resp

bad_request = http_error(400)
forbidden = http_error(403)
not_found = http_error(404, body="Not Found")
abort = http_error(500)


##,---------------
##| Cyanbird Route
##`---------------
class Route(object):
    def __init__(self, re_url, f, method="GET"):
        self.url = re_url
        self.re_url = re.compile(r"^%s$" % _add_slash(re_url))
        self.f = f
        self.method = method
        self.params = {}

    def match(self, request):
        if isinstance(self.method, str):
            if self.method.upper() != request.method:
                raise Exception("Method %s not allowed." % self.method)
        if isinstance(self.method, list):
            if request.method not in self.method:
                raise Exception("Methods %s not allowed." % self.method)
        match = self.re_url.search(request.path)
        if match is not None:
            self.params.update(match.groupdict())
            return True
        return None

    def dispatch(self, request):
        return self.f(request, **self.params)


##,-----------------------
##| Cyanbird Errors Object
##`-----------------------
class Error(object):
    def __init__(self, code, f):
        self.status_code = code
        self.f = f

    def __call__(self):
        return self.f()

# handler
_REQUEST_MAPPINGS = {
    "GET": [],
    "POST": []
}

_ERROR_MAPPINGS = {}


# app
def _match_url(request):
    if request.method not in _REQUEST_MAPPINGS:
        raise Exception("The request method: %s is not supported." %
                        request.method)
    for re_url, callback in _REQUEST_MAPPINGS[request.method]:
        match = re_url.search(request.path)
        if match is not None:
            return re_url, callback, match.groupdict()
    raise HTTPError(404, "Not Found")


def application_handler(env, start_response):
    """ The handler for request and response.
    """
    request = Request(env)
    try:
        re_url, callback, kwargs = _match_url(request)
        if callback is not None:
            resp = callback(request, **kwargs)
            if not isinstance(resp, Response):
                response = Response()
                response.write(resp)
                return response(start_response)
            return resp(start_response)
    except Exception as e:
        if isinstance(e, HTTPError):
            status_code = getattr(e, "status_code", 404)
        else:
            status_code = 500
        if status_code in _ERROR_MAPPINGS:
            resp = Response(code=404)
            resp.write(_ERROR_MAPPINGS[status_code]())
            return resp(start_response)
    return not_found(start_response)


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
    """ The `GET` wrapper.
    """
    return _route_abstract("GET", url, base=base)


def POST(url, base=""):
    """ The `POST` wrapper.
    """
    return _route_abstract("POST", url, base=base)


def error(code):
    """ The 'error' wrapper.
    """
    def wrapper(f):
        _ERROR_MAPPINGS[code] = f
    return wrapper


# serve static files
def _check_file(file, dir):
    """ Check if the given file has the permission.
    """
    base_path = os.path.abspath(dir)
    serve_file = os.path.realpath(os.path.join(base_path, file))
    if not serve_file.startswith(base_path):
        raise Exception("Operation denied.")
    if not os.path.exists(serve_file):
        raise Exception("File %s not exists." % file)
    if not os.access(serve_file, os.R_OK):
        raise Exception("Have no access to read %s." % file)
    return serve_file


def serve_file(file, dir, mimetype=""):
    """ Serve a static file.
    """
    serve_file = _check_file(file, dir)
    ctype = mimetype or mimetypes.guess_type(serve_file)[0] or "text/plain"
    f = BytesIO()
    f.write(open(serve_file, "r").read())
    resp = Response(content_type=ctype)
    resp.write(f.getvalue())
    return resp


def render(file, params):
    """ Simple template using the built-in string.Template
    """
    dirname, filename = os.path.split(file)
    serve_file = _check_file(filename, dirname)
    ctype = mimetypes.guess_type(serve_file)[0] or "text/plain"
    s = Template(open(serve_file, "r").read()).substitute(params)
    resp = Response(content_type=ctype)
    resp.write(s)
    return resp


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
def run(host="127.0.0.1", port=8080, server="wsgiref"):
    try:
        f = _ADAPTER[server]
    except KeyError:
        raise KeyError("The server %s is not exists!" % server)
    try:
        print("Please visit http//:%s:%s" % (host, port))
        print("Press Ctrl+c Ctrl+c to interrupt")
        f(application_handler, host, port)
    except KeyboardInterrupt:
        print("Shuting down.")
