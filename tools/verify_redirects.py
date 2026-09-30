"""Check that every old or moved URL is handled correctly on a deploy (no redirect following).
Usage: verify_redirects.py <base-url>        e.g. https://thankful-mushroom-0dd42611e.3.azurestaticapps.net
Rules come from data/blog_redirects.txt (written by build_blog.py): "<path>  <target>  <status>", where status 200
means the path is served as-is (a rewrite) and must show the target page's content."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import DATA
import http.client, re, sys, urllib.parse

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"
U = urllib.parse.urlsplit(BASE)

def get(path):
    c = (http.client.HTTPSConnection if U.scheme == "https" else http.client.HTTPConnection)(U.netloc, timeout=30)
    c.request("GET", path, headers={"User-Agent": "openexa-redirect-check/1.0"})
    r = c.getresponse(); body = r.read()
    loc = r.getheader("Location") or ""
    if loc.startswith(("http://", "https://")) and urllib.parse.urlsplit(loc).netloc == U.netloc:
        loc = urllib.parse.urlsplit(loc)._replace(scheme="", netloc="").geturl()
    return r.status, loc, body

rules = [l.split() for l in (DATA / "blog_redirects.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
bad = []
for src, dst, status in rules:
    st, loc, body = get(src)
    if status == "200":
        want = get(dst)[2]
        if st != 200 or body != want: bad.append((src, st, loc, f"expected the content of {dst}"))
    elif st != int(status) or loc.rstrip("/") != dst.rstrip("/"):
        bad.append((src, st, loc, f"expected {status} -> {dst}"))
targets = sorted({d.split("#")[0] for _, d, s in rules if d.startswith("/")})
dead = [t for t in targets if get(t)[0] != 200]
print(f"{BASE}: {len(rules) - len(bad)}/{len(rules)} old/moved URLs handled correctly; {len(targets)} targets, dead: {dead}")
for b in bad[:15]: print("  BAD", b)
sys.exit(1 if bad or dead else 0)
