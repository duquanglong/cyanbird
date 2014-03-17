from cyanbird import error, GET, run

@GET("/")
def index(request):
    return "hello again"

@error(404)
def not_found():
    return "<h1>Not Found this page.</h1>"

run()
