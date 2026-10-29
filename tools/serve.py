"""Local preview that behaves like the Azure Static Web App, so a change can be checked against the real headers.

Serves site/ on http://127.0.0.1:8125 (the port the browser checks expect) with staticwebapp.config.json applied:
globalHeaders (the Content-Security-Policy included, so a policy violation shows up in the browser console locally),
per-route headers, redirect routes, clean URLs (/company -> company.html, /blog/ -> blog/index.html), the 404 rewrite
and the extra mimeTypes. Use it instead of `python -m http.server 8125 --directory site`.
    python tools/serve.py [port]
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import fnmatch, http.server, io, json, sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(str(SITE)).resolve()
CFG = json.loads((ROOT / "staticwebapp.config.json").read_text(encoding="utf-8"))
HIDDEN = {"/staticwebapp.config.json"}  # Azure never serves its own config

def matches(rule, path):
    r = rule["route"]
    return fnmatch.fnmatchcase(path, r) if "*" in r else path.rstrip("/") == r.rstrip("/")

def resolve(path):
    """The file Azure would serve for `path`, or None (-> 404)."""
    p = (ROOT / unquote(path).lstrip("/")).resolve()
    if p != ROOT and ROOT not in p.parents: return None
    if not path.endswith("/") and not p.suffix and p.with_suffix(".html").is_file(): p = p.with_suffix(".html")  # /research
    elif p.is_dir(): p = p / "index.html"
    return p if p.is_file() and path not in HIDDEN else None

class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript", ".css": "text/css",
                      ".svg": "image/svg+xml", ".webp": "image/webp", ".woff2": "font/woff2", ".xml": "text/xml",
                      ".json": "application/json", ".ico": "image/x-icon", **CFG.get("mimeTypes", {})}

    def __init__(self, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
    def log_message(self, *a): pass

    def send_head(self):
        path = urlsplit(self.path).path
        rule = next((r for r in CFG["routes"] if matches(r, path)), {})
        self.extra = rule.get("headers", {})
        if "redirect" in rule:
            self.send_response(rule.get("statusCode", 302)); self.send_header("Location", rule["redirect"])
            self.send_header("Content-Length", "0"); self.end_headers(); return None
        f = resolve(path)
        if f is None:  # responseOverrides: 404 -> /404.html with status 404
            body = (ROOT / "404.html").read_bytes()
            self.send_response(404); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); return io.BytesIO(body)
        self.path = "/" + f.relative_to(ROOT).as_posix()
        return super().send_head()

    def end_headers(self):
        for k, v in {**CFG.get("globalHeaders", {}), **getattr(self, "extra", {})}.items():
            if k == "Content-Security-Policy": v = v.replace("; upgrade-insecure-requests", "")  # local is plain http
            self.send_header(k, v)
        super().end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8125
    print(f"serving site/ like Azure at http://127.0.0.1:{port}/  (Ctrl+C to stop)", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
