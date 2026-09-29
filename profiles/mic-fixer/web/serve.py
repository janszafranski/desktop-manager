#!/usr/bin/env python3
"""Static server for the Mic Fixer page, bound to loopback only.

Chromium refuses getUserMedia() on file:// pages, so the app has to come off an
http://127.0.0.1 origin to be a secure context. This is the smallest server that
does that with nothing but the stdlib.

It tries a preferred port first: browser permissions are keyed on scheme+host+
port, so a stable origin means Jan grants the mic once instead of every launch.
If that port is busy it falls back to a kernel-chosen free one. The port that was
actually bound is written to a file, so the launcher never has to pre-flight a
bind of its own and race against whatever grabs the port in between.
"""

import functools
import http.server
import os
import socketserver
import sys


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "mic-fixer"

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: serve.py <root-dir> <port-file> <preferred-port>")
    root, port_file, preferred = sys.argv[1], sys.argv[2], int(sys.argv[3])
    handler = functools.partial(Handler, directory=root)

    httpd = None
    for port in (preferred, 0):
        try:
            httpd = Server(("127.0.0.1", port), handler)
            break
        except OSError as exc:
            sys.stderr.write("[serve] port %d unavailable (%s)\n" % (port, exc))
    if httpd is None:
        sys.exit("mic-fixer: could not bind a loopback port")

    # Written atomically so the launcher never reads a half-written port.
    tmp = port_file + ".tmp"
    with open(tmp, "w") as fh:
        fh.write(str(httpd.server_address[1]))
    os.replace(tmp, port_file)
    sys.stderr.write("[serve] listening on http://127.0.0.1:%d/\n" % httpd.server_address[1])

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


main()
