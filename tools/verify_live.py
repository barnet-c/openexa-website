"""Compare a live Netlify deploy against an archived version folder: exact bytes for assets, link-rewrite-normalised HTML."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import hashlib, json, re, sys, urllib.request
from pathlib import Path

SITE = sys.argv[1] if len(sys.argv) > 1 else "silly-gelato-17a75a"
FOLDER = sys.argv[2] if len(sys.argv) > 2 else "v10-2026-09-21-research-company"
ROOT = Path(str(ARCHIVE)) / FOLDER
BASE = f"https://{SITE}.netlify.app"

def fetch(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": "openexa-archive-check/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()

ATTR = re.compile(r"""([a-zA-Z:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?""")

def norm_href(h, depth, page_dir=""):
    """Local .html links -> the clean form Netlify serves them in (resolved against the page's folder)."""
    if re.match(r"^(https?:|mailto:|#|tel:)", h) or h.startswith("/"):
        return h
    base, _, frag = h.partition("#")
    if not base.endswith(".html"):
        return h
    import posixpath
    path = "/" + posixpath.normpath(posixpath.join(page_dir, base))[:-5].lstrip("/")
    if path.endswith("/index"): path = path[:-5]
    if path == "/index": path = "/"
    return path + ("#" + frag if frag else "")

def normalise_html(src, depth, page_dir=""):
    def repl(m):
        attrs = {}
        for k, a, b, c in ATTR.findall(m.group(1)):
            attrs[k.lower()] = a or b or c or ""
        if "href" in attrs:
            attrs["href"] = norm_href(attrs["href"], depth, page_dir)
        return "<a " + " ".join(f'{k}="{attrs[k]}"' for k in sorted(attrs)) + ">"
    return re.sub(r"<a\s+([^>]*?)/?>", repl, src, flags=re.S)

manifest = json.load(open(ROOT.parent / "_manifests" / f"{FOLDER.split('-')[0]}.json", encoding="utf-8"))
same_bytes, same_html, diffs, skipped = [], [], [], []
for rel, info in manifest["files"].items():
    if rel in ("_redirects", "README.md"):
        skipped.append(rel)  # Netlify never serves _redirects; README is not part of the site
        continue
    try:
        status, body = fetch(rel)
    except Exception as e:
        diffs.append((rel, f"fetch failed: {e}"))
        continue
    local = (ROOT / rel).read_bytes()
    if hashlib.sha256(body).hexdigest() == info["sha256"]:
        same_bytes.append(rel)
        continue
    if rel.endswith(".html"):
        depth = rel.count("/")
        pdir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        a = normalise_html(local.decode("utf-8"), depth, pdir)
        b = normalise_html(body.decode("utf-8"), depth, pdir)
        if a == b:
            same_html.append(rel)
        else:
            # report the first differing region
            i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            diffs.append((rel, f"local[{i}]: {a[max(0,i-80):i+120]!r}\n   live[{i}]: {b[max(0,i-80):i+120]!r}"))
    else:
        diffs.append((rel, f"bytes differ: local {len(local)} vs live {len(body)}"))

# clean URLs the site relies on
clean = {}
for path in ["company", "research", "research/01-compounding-error", "research/10-master-and-copy", "insights", "access", ""]:
    status, body = fetch(path)
    clean[path or "/"] = status
try:
    fetch("definitely-not-a-page")
    clean["missing -> 404"] = "served 200 (!)"
except urllib.error.HTTPError as e:
    clean["missing -> 404"] = e.code

print(f"{BASE}  vs  {FOLDER}")
print(f"byte-identical: {len(same_bytes)}   html identical after link normalisation: {len(same_html)}   skipped: {skipped}")
print("clean urls:", clean)
if diffs:
    print(f"DIFFERENCES ({len(diffs)}):")
    for rel, why in diffs:
        print(" -", rel, "\n  ", why)
    sys.exit(1)
print("LIVE DEPLOY MATCHES THE ARCHIVE")
