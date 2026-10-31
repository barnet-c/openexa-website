"""Probe how a host serves the moved and legacy URLs (no redirect following), and the headers it sends.
Usage: probe_routes.py <base-url>
v2x tests pass (30 Oct): every 200 and 404 answer also carries the security headers exactly as
site/staticwebapp.config.json declares them (check_static `headers` pins that file to the contract, so together they
pin what a visitor's browser gets); over plain http (tools/serve.py) the CSP is the same without
'upgrade-insecure-requests'. The cache routes and the two extra MIME types are probed on one file each."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import SITE
import http.client, json, sys, urllib.parse

BASE = sys.argv[1].rstrip("/")
u = urllib.parse.urlsplit(BASE)
KEEP = "leveraged-etfs-price-dynamics-and-options-valuation"
HELD = "what-is-an-nft-non-fungible-tokens-and-how-you-can-buy-one"
GONE = "municipal-bonds-and-esg-all-hat-no-cattle"
CASES = [  # path, expected status, expected Location (or None), body must contain
    ("/", 200, None, "Infrastructure for"),
    ("/company", 200, None, "Dipit Nanawati"),
    ("/company.html", 200, None, "Dipit Nanawati"),
    ("/blog/", 200, None, "The Gen-AI series"),
    ("/blog/index.html", 200, None, "The Gen-AI series"),
    (f"/blog/{KEEP}.html", 200, None, "Leveraged ETFs"),
    (f"/blog/{KEEP}", 301, f"/blog/{KEEP}.html", None),
    (f"/blog/{KEEP}/", 301, f"/blog/{KEEP}.html", None),             # old openexa.com form
    ("/blog", 200, None, "The Gen-AI series"),                         # served with <base href="/blog/">
    (f"/blog/{HELD}/", 301, "/blog/", None),
    (f"/blog/{GONE}/", 301, "/blog/", None),
    (f"/research/blog/{KEEP}.html", 301, f"/blog/{KEEP}.html", None),     # the blog's previous home
    ("/research/blog/index.html", 301, "/blog/", None),
    ("/research/blog/", 301, "/blog/", None),
    ("/research", 200, None, "The thinking behind the swarm"),
    ("/research.html", 200, None, "The thinking behind the swarm"),
    ("/research/01-compounding-error.html", 200, None, "Compounding"),
    ("/strategies/", 301, "/lifecycles", None),
    ("/for-managers/", 301, "/access#managers", None),
    ("/definitely-missing/x/y", 404, None, "This page didn"),
    ("/README.md", 404, None, None),
    ("/_redirects", 404, None, None),
    ("/staticwebapp.config.json", 404, None, None),
]
CFG = json.loads((SITE / "staticwebapp.config.json").read_text(encoding="utf-8"))
WANT = dict(CFG["globalHeaders"])
if u.scheme == "http": WANT["Content-Security-Policy"] = WANT["Content-Security-Policy"].replace("; upgrade-insecure-requests", "")
CACHE = {r["route"]: r["headers"]["Cache-Control"] for r in CFG["routes"] if "headers" in r}
FILES = [  # one file per cache route and per extra MIME type: path, header, expected value
    ("/assets/fonts/inter-var-latin.woff2", "Cache-Control", CACHE.get("/assets/fonts/*")),
    ("/assets/img/og/index.jpg", "Cache-Control", CACHE.get("/assets/img/og/*")),
    ("/assets/img/favicon.svg", "Cache-Control", CACHE.get("/assets/img/*")),
    ("/site.webmanifest", "Content-Type", CFG["mimeTypes"][".webmanifest"]),
    ("/speculation.specrules", "Content-Type", CFG["mimeTypes"][".specrules"]),
]


def get(path):
    c = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(u.netloc, timeout=30)
    c.request("GET", path, headers={"User-Agent": "openexa-route-probe/1.0"})
    r = c.getresponse(); body = r.read().decode("utf-8", "replace")
    return r, body


def header_faults(r):
    return [f"{k}: {r.getheader(k)!r}" for k, v in WANT.items() if r.getheader(k) != v]


bad = 0
for path, st, loc, needle in CASES:
    r, body = get(path); got_loc = r.getheader("Location") or ""
    got_loc_path = urllib.parse.urlsplit(got_loc)._replace(scheme="", netloc="").geturl() if got_loc else ""
    hdr = header_faults(r) if r.status in (200, 404) else []
    ok = r.status == st and (loc is None or got_loc_path == loc) and (needle is None or needle in body) and not hdr
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {path[:70]:70} {r.status} {got_loc_path[:40]}" + ("" if ok else f"   expected {st} {loc or ''} {needle or ''}" + (f"; headers differ: {hdr}" if hdr else "")))
for path, k, v in FILES:
    r, _ = get(path)
    got = (r.getheader(k) or "").split(";")[0].strip() if k == "Content-Type" else r.getheader(k)
    ok = r.status == 200 and got == v and not header_faults(r)
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {path[:70]:70} {r.status} {k}: {got}" + ("" if ok else f"   expected {v!r}" + (f"; headers differ: {header_faults(r)}" if header_faults(r) else "")))
n = len(CASES) + len(FILES)
print(f"{n - bad}/{n} as expected (routes, security headers on every page and 404, cache and MIME rules)")
sys.exit(1 if bad else 0)
