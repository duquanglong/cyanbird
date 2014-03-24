# -*- coding: utf-8 -*-
__license__ = "MIT"
__version__ = "0.20"
__author__ = "Zhao Wei <kaihaosw@gmail.com>"
import re
import os
from cgi import FieldStorage
from datetime import datetime
import time
import mimetypes
from urlparse import parse_qs
from urllib import quote
from Cookie import SimpleCookie
from cStringIO import StringIO as BytesIO


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
        return "HTTPError %s: %s" % (self.status_code, self.msg)


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


##,-----------------
##| Cyanbird Servers
##`-----------------
class ServerAdapter(object):
    def __init__(self, host="127.0.0.1", port=8080, debug=False, reload=False):
        self.host, self.port = host, port
        self.debug, self.reload = debug, reload

    def __repl__(self):
        return "Cyanbird runs at http://%s:%s" % (self.host, self.port)

    def run(self):
        pass


class WSGIRefServer(ServerAdapter):
    """ WSGIRef server from the built-in wsgiref library. """
    def run(self, handler):
        from wsgiref.simple_server import make_server
        server = make_server(app=handler, host=self.host, port=self.port)
        server.serve_forever()


##,--------------
##| Cyanbird main
##`--------------
class Cyanbird(object):
    """ Cyanbird """
    def __init__(self, path=""):
        self.path = os.path.abspath(path)
        self.routes = []
        self.errors = {}

    def route(self, url, method="GET"):
        def wrapper(f):
            self.routes.append(Route(url, f, method))
            return f
        return wrapper

    def get(self, url):
        return self.route(url, method="GET")

    def post(self, url):
        return self.route(url, method="POST")

    def put(self, url):
        return self.route(url, method="PUT")

    def delete(self, url):
        return self.route(url, method="DELETE")

    def error(self, code):
        def wrapper(f):
            self.errors[code] = (Error(code, f))
            return f
        return wrapper

    def _routes_match(self, request):
        for route in self.routes:
            if route.match(request) is not None:
                return route.dispatch(request)
        raise HTTPError(404, "Not Found")

    def _wsgi(self, env, start_response):
        _request.bind(env)
        try:
            resp = self._routes_match(_request)
            if not isinstance(resp, Response):
                return response(resp)(start_response)
            return resp(start_response)
        except Exception as e:
            if isinstance(e, HTTPError):
                status_code = int(e.status_code)
            else:
                status_code = 500
            try:
                resp = self.errors[status_code]()
                if not isinstance(resp, Response):
                    return http_error(status_code, resp)(start_response)
                return resp(start_response)
            except Exception:
                pass
        return http_error(404, "Not Found")(start_response)

    def __call__(self, env, start_response):
        return self._wsgi(env, start_response)

    def serve_file(self, file, dir, mimetype=""):
        s = ServeFile(file=file, dir=dir, mimetype=mimetype)
        try:
            if s.check():
                return s.serve()
        # TODO abstract
        except Exception as e:
            print e

    def run(self, server=WSGIRefServer, host="127.0.0.1", port=8080,
            debug=False, reload=False):
        return run(app=self, server=server, host=host, port=port,
                   debug=debug, reload=reload)


##,------------------
##| Cyanbird Requests
##`------------------
class Request(object):
    """ Request object which handlers the `environ`. """
    def __setitem__(self, key, value):
        self.env[key] = value

    def bind(self, env):
        self.env = env

    @property
    def ctype(self):
        return self.env["CONTENT_TYPE"]

    @property
    def clength(self):
        return int(self.env.get("CONTENT_LENGTH", "0"))

    @property
    def method(self):
        return self.env.get("REQUEST_METHOD", "GET").upper()

    @property
    def path(self):
        return _add_slash(quote(self.env.get("SCRIPT_NAME", "")) +
                          quote(self.env.get("PATH_INFO", "")))

    @property
    def args(self):
        return _parse_qs(self.env.get("QUERY_STRING", ""))

    @property
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

    @property
    def forms(self):
        if not hasattr(self, "_forms"):
            self._load_body()
        return self._forms

    @property
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
    401: "401 Unauthorized",
    403: "403 Forbidden",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    410: "410 Gone",
    500: "500 Internal Server Error"}


class Response(object):
    """ Response object which `start_response`. """
    def bind(self, code=200, content_type="text/html; charset=UTF-8"):
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


##,---------------
##| Cyanbird Route
##`---------------
class Route(object):
    """ Single route object. """
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
    """ Single error object. """
    def __init__(self, code, f):
        self.status_code = code
        self.f = f

    def __call__(self):
        return self.f()


# TODO WSGIHandler


##,----------------------------
##| Cyanbird Serve Static Files
##`----------------------------
class ServeFile(object):
    """ Serve the static file. """
    def __init__(self, file, dir, mimetype=""):
        self.file = file
        self.dir = os.path.abspath(dir)
        self.serve_file = os.path.realpath(os.path.join(self.dir, self.file))
        self.ctype = mimetype or mimetypes.guess_type(self.serve_file)[0] or "text/plain"

    def check(self):
        if not self.serve_file.startswith(self.dir):
            raise HTTPError(401, "Access denied.")
        if not os.path.exists(self.serve_file):
            raise HTTPError(404, "File not exists.")
        if not os.access(self.serve_file, os.R_OK):
            raise HTTPError(403, "No Permission.")
        return True

    def serve(self):
        f = BytesIO()
        f.write(open(self.serve_file, "rb").read())
        _response.bind(content_type=self.ctype)
        _response.write(f.getvalue())
        return _response


# TODO Template


##,---------------------------
##| Cyanbird application basic
##`---------------------------
_request = Request()
_response = Response()
_app = Cyanbird()


def route(url, method="GET"):
    """ Route decorator. """
    return _app.route(url, method=method)


def get(url):
    """ Get decorator. """
    return _app.get(url)


def post(url):
    """ Post decorator. """
    return _app.post(url)


def put(url):
    """ Put decorator. """
    return _app.put(url)


def delete(url):
    """ Delete decorator. """
    return _app.delete(url)


def error(code):
    """ Error decorator. """
    return _app.error(code)


def response(body):
    """ Return a response for `200 OK` response. """
    _response.bind()
    _response.write(body)
    return _response


def redirect(url):
    """ Return a response for an HTTP `302 redirect`. """
    _response.bind(302)
    _response.redirect(url)
    return _response


def http_error(code, body=""):
    """ Return a error based on the status_code. """
    assert code >= 400 and code <= 505
    _response.bind(code)
    if code == 404:
        _response.write(body)
    return _response


def serve_file(file, dir, mimetype=""):
    """ Serve the static file. """
    return _app.serve_file(file=file, dir=dir, mimetype=mimetype)


# def render(file, params):
#     """ Simple template using the built-in string.Template """
#     dirname, filename = os.path.split(file)
#     serve_file = _check_file(filename, dirname)
#     ctype = mimetypes.guess_type(serve_file)[0] or "text/plain"
#     s = Template(open(serve_file, "r").read()).substitute(params)
#     resp = Response(content_type=ctype)
#     resp.write(s)
#     return resp


def run(app=_app, server=WSGIRefServer, host="127.0.0.1", port=8080,
        debug=False, reload=False):
    """ Run the application with the giver params. """
    try:
        print("Cyanbird v%s is running." % __version__)
        print("Please visit http://%s:%s" % (host, port))
        print("Press Ctrl-c Ctrl-c to interrupt.")
        server = server(host=host, port=port, debug=debug, reload=reload)
        server.run(app)
    except KeyboardInterrupt:
        print("Shuting down.")
