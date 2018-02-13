Simple HTTP server
===========================

This is a simple asyncronous HTTP server, implemented with Python 3.6 asyncio
 library. It is capable of handling GET and HEAD requests and scale between
 multiple workers.

Usage:

To start server use the following command:

    python diy_http_server/httpd.py

available flags:

    -w (int) - number of workers
    -r (str) - path to document root
    -l (str) - path to logfile

To shutdown working server and workers gracefully use Ctrl+C.

To trigger static lint check invoke `tox`.