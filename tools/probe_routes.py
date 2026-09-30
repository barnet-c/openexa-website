"""Probe how a host serves the moved and legacy URLs (no redirect following). Usage: probe_routes.py <base-url>"""
import http.client, sys, urllib.parse

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
bad = 0
for path, st, loc, needle in CASES:
    c = (http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection)(u.netloc, timeout=30)
    c.request("GET", path, headers={"User-Agent": "openexa-route-probe/1.0"})
    r = c.getresponse(); body = r.read().decode("utf-8", "replace"); got_loc = r.getheader("Location") or ""
    got_loc_path = urllib.parse.urlsplit(got_loc)._replace(scheme="", netloc="").geturl() if got_loc else ""
    ok = r.status == st and (loc is None or got_loc_path == loc) and (needle is None or needle in body)
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {path[:70]:70} {r.status} {got_loc_path[:40]}" + ("" if ok else f"   expected {st} {loc or ''} {needle or ''}"))
print(f"{len(CASES) - bad}/{len(CASES)} as expected")
sys.exit(1 if bad else 0)
