"""Compare a deploy with site/ byte for byte (Azure Static Web Apps serves files unmodified).
Usage: verify_live.py <base-url>        e.g. https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import SITE
import concurrent.futures as cf, hashlib, sys, urllib.error, urllib.parse, urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"
NOT_SERVED = {"staticwebapp.config.json"}  # Azure reads it; it is never served

def fetch(path):
    req = urllib.request.Request(f"{BASE}/{urllib.parse.quote(path)}", headers={"User-Agent": "openexa-deploy-check/1.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, b""

files = sorted(p.relative_to(SITE).as_posix() for p in SITE.rglob("*") if p.is_file() and p.name not in NOT_SERVED)
def check(rel):
    status, body = fetch(rel)
    return rel, status, hashlib.sha256(body).hexdigest() == hashlib.sha256((SITE / rel).read_bytes()).hexdigest()
with cf.ThreadPoolExecutor(12) as ex:
    results = list(ex.map(check, files))
diff = [(r, s) for r, s, same in results if not same]
clean = {p: fetch(p)[0] for p in ("company", "research", "research/01-compounding-error", "blog/", "blog/leveraged-etfs-price-dynamics-and-options-valuation", "access", "")}
print(f"{BASE}: {len(results) - len(diff)}/{len(results)} files byte-identical to site/")
print("clean urls:", clean)
for r, s in diff[:15]: print("  DIFF", s, r)
ok = not diff and all(s == 200 for s in clean.values())
print("DEPLOY MATCHES site/" if ok else "DEPLOY DIFFERS")
sys.exit(0 if ok else 1)
