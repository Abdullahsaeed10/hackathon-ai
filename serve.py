"""
Minimal static dev server — serves the Verdict frontend on port 5173.
Maps /static/* → static/* and routes SPA paths to index.html.
Run: python serve.py
"""
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SPA_PATHS = {"/", "/scout", "/judgment", "/doctor"}


class VerdictDevHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def translate_path(self, path):
        # Strip /static/ prefix
        if path.startswith("/static/"):
            path = path[len("/static/"):]
        # SPA routes → index.html
        p = path.split("?")[0].split("#")[0]
        if p in SPA_PATHS or p.startswith("/v/"):
            path = "/index.html"
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        pass  # quiet


if __name__ == "__main__":
    server = HTTPServer(("", 5173), VerdictDevHandler)
    print("Verdict dev server: http://localhost:5173")
    server.serve_forever()
