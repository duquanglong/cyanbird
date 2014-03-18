from cyanbird import render, GET, run

@GET("/")
def index(request):
    return render("templates/index.html", dict(title="built-in template", page="main"))

run()
