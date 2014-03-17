from cyanbird import GET, response, run, Response

@GET("/cookie")
def get_coo(request):
    return request.get_cookie("name") or "no cookies"

@GET("/")
def index(request):
    resp = Response()
    resp.set_cookie("a", 100)
    resp.set_cookie("b", 10, expires=9999999999)
    resp.delete_cookie("b")
    resp.set_cookie("name", "jude")
    return resp

run()
