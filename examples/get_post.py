from cyanbird import GET, POST, response, run

@GET("/")
def index(request):
    return response("hello cyanbird")

@GET("/index")
def pt(request):
    html = """
    <form method='post' action='/index'>
    <p>name: <input type='text', name='t'></p>
    <p>password: <input type='password', name='p'></p>
    <input type='submit'>
    </form>
    """
    return response(html)

@POST("/index")
def pt2(request):
    t = request.forms.get("t", None)
    p = request.forms.get("p", None)
    return response("text and password are %s and %s" % (t, p))

@GET("/(?P<name>.+)")
def hello(request, name):
    return response("hello %s" % name)

if __name__ == "__main__":
    run()
