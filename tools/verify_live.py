"""Compare a deploy with what is deployed, byte for byte (Azure Static Web Apps serves files unmodified).

Since award a3 (live since PR #6) Azure serves dist/site, the copy tools/build_deploy.py writes from site/ (CSS
minified, scripts stripped, a versioned copy of each and every page pointing at it), so a deploy is compared with that
build, made here into a temporary folder exactly as the deploy job makes it (`python tools/build_deploy.py`, default
options). hc30r (integrate, on the main thread's request of 10 Nov): before, this compared with site/ itself and
reported every minified or versioned file of a correct deploy as different.
Usage: verify_live.py <base-url> [--source]
    <base-url>   e.g. https://www.openexa.com or https://thankful-mushroom-0dd42611e.3.azurestaticapps.net
    --source     compare with site/ as written instead (a server of the source itself: tools/serve.py, or a deploy
                 made with app_location "./site")"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import SITE
import concurrent.futures as cf, hashlib, shutil, sys, tempfile, urllib.error, urllib.parse, urllib.request
from pathlib import Path

args = [a for a in sys.argv[1:] if not a.startswith("--")]
SOURCE = "--source" in sys.argv[1:]
BASE = args[0].rstrip("/") if args else "https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"
NOT_SERVED = {"staticwebapp.config.json"}  # Azure reads it; it is never served

def fetch(path):
    req = urllib.request.Request(f"{BASE}/{urllib.parse.quote(path)}", headers={"User-Agent": "openexa-deploy-check/1.0", "Cache-Control": "no-cache"})
    for attempt in range(3):  # a deploy check must not fail on one dropped connection
        try:
            with urllib.request.urlopen(req, timeout=40) as r: return r.status, r.read()
        except urllib.error.HTTPError as e: return e.code, b""
        except Exception:
            if attempt == 2: return 0, b""

tmp = None
if SOURCE:
    ROOT, what = Path(str(SITE)), "site/"
else:
    import build_deploy
    tmp = Path(tempfile.mkdtemp(prefix="oxa-verify-live-"))
    ROOT, what = tmp / "site", "the deploy build of site/ (tools/build_deploy.py)"
    build_deploy.build(ROOT.resolve())
    if build_deploy.problems:
        for p in build_deploy.problems: print("PROBLEM", p)
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit("verify_live: the deploy build has findings; nothing compared")
try:
    files = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*") if p.is_file() and p.name not in NOT_SERVED)
    def check(rel):
        status, body = fetch(rel)
        return rel, status, hashlib.sha256(body).hexdigest() == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    with cf.ThreadPoolExecutor(12) as ex:
        results = list(ex.map(check, files))
finally:
    if tmp: shutil.rmtree(tmp, ignore_errors=True)
diff = [(r, s) for r, s, same in results if not same]
clean = {p: fetch(p)[0] for p in ("company", "research", "research/01-compounding-error", "blog/", "blog/leveraged-etfs-price-dynamics-and-options-valuation.html", "access", "")}
print(f"{BASE}: {len(results) - len(diff)}/{len(results)} files byte-identical to {what}")
print("clean urls:", clean)
for r, s in diff[:15]: print("  DIFF", s, r)
ok = not diff and all(s == 200 for s in clean.values())
print(f"DEPLOY MATCHES {what}" if ok else "DEPLOY DIFFERS")
sys.exit(0 if ok else 1)
