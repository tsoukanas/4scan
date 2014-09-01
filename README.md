4scan
=====

Asynchronous keyword searcher for active 4chan threads. Takes a configuration file with lists of keywords to search, and runs a user-supplied callback function on each post that matches. Currently only searches the bodies of posts (so the actual text comment, not subject or user fields). Can be configured to search only thread topics / OPs (the default setting), or can search all posts.

All boards are scanned roughly simultaneously, but scans are staggered to not overload 4chan's API.

Requires my [4chan4py](https://github.com/Anorov/4chan4py) API wrapper library as well as [gevent](https://pypi.python.org/pypi/gevent).

Dependencies
============

* Python 2.6 - 2.7
* gevent >= 1.0
* 4chan4py >= 0.1

Usage
=====

    import fourscan

    def show_first_line(post, scan):
        print post.body.splitlines()[0]

    # Config defaults to config.yaml
    fourscan.scan_forever(callback=show_first_line)

See `config.yaml.example` and the `examples/` directory for more information on how to write configs and callbacks.

Install
=======

Drop `fourscan.py` in your Python packages directory or any project directory.
