#!/usr/bin/env python3
"""本地预览服务器：python3 scripts/serve.py [--port 8080]"""
from __future__ import annotations

import argparse
import http.server
import os
import socketserver

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "/data/" in (args[0] if args else ""):
            return
        super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    args = ap.parse_args()
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", args.port), Handler) as httpd:
        print(f"本地预览： http://127.0.0.1:{args.port}/  （Ctrl+C 退出）")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
