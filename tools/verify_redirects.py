"""Check that every URL of the old openexa.com site redirects to the right place on a deploy (no redirect following)."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import http.client, json, sys, urllib.parse
from pathlib import Path

HOST = sys.argv[1] if len(sys.argv) > 1 else "timely-quokka-fa2399.netlify.app"
FILES = Path(str(DATA))

def head(path):
    c = http.client.HTTPSConnection(HOST, timeout=30)
    c.request("GET", path, headers={"User-Agent": "openexa-redirect-check/1.0"})
    r = c.getresponse(); r.read()
    return r.status, r.getheader("Location")

expect = {"/strategies/": "/lifecycles", "/trust-risk/": "/trust", "/status/": "/evidence", "/for-managers/": "/access#managers",
          "/for-investors/": "/access#investors", "/beta/": "/access", "/blog/": "/research/blog/", "/blog": "/research/blog/"}
for line in (FILES / "blog_redirects.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("/blog/"):
        src, dst, _ = line.split()
        expect[src + "/"] = dst  # the old site's URLs carried a trailing slash
bad, ok = [], 0
for src, dst in expect.items():
    status, loc = head(src)
    loc_path = urllib.parse.urlsplit(loc or "")
    got = loc if (loc or "").startswith("http") and not loc.startswith(f"https://{HOST}") else (loc_path.path + ("#" + loc_path.fragment if loc_path.fragment else ""))
    if status != 301 or got.rstrip("/") != dst.rstrip("/"):
        bad.append((src, status, loc, dst))
    else:
        ok += 1
# and each redirect target that lives on this site must resolve
targets = sorted({d for d in expect.values() if d.startswith("/")})
dead = [t for t in targets if head(t.split("#")[0])[0] not in (200, 301, 308)]
print(f"{HOST}: {ok}/{len(expect)} old URLs redirect correctly; {len(targets)} on-site targets, dead: {dead}")
for b in bad[:12]: print("  BAD", b)
sys.exit(1 if bad or dead else 0)
