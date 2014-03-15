Cyanbird
========
Cyanbird is a mythical bird in the book *Classic of Mountains and Seas*. It's the messenger of happiness.  
It is aslo a microframework written in Python.  

Examples
--------
    from cyanbird import GET, response, run

    @GET("/")
    def index(request):
        return response("Hello Cyanbird!")

    run()

Installation
------------

Documentation
------------

TODO
----
It is still under development. Please join me.

* cookie
* cache
* serve static files
* some other adapters

Thanks
------
[Ring](https://github.com/ring-clojure/ring)  
[wheezy.http](https://bitbucket.org/akorn/wheezy.http)  
[itty](https://github.com/toastdriven/itty)  
[CherryPy](https://bitbucket.org/cherrypy/cherrypy/wiki/Home)  
[Django](https://github.com/django/django)  
[getting-started-with-wsgi](http://lucumr.pocoo.org/2007/5/21/getting-started-with-wsgi/)

License
-------
Copyright © 2014 Zhao Wei and released under an MIT license.
