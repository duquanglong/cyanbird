from cyanbird import GET, run, serve_file

@GET("/license")
def index(request):
    return serve_file("LICENSE", dir="static")

run()
