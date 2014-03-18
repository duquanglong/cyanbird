from cyanbird import render, GET, run

@GET("/")
def index(request):
    return render("index.html", "templates",
                  dict(title="built-in template", page="main"))

run()
