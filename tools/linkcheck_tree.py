"""Check every internal href/src across the site, including subfolders, resolving relative paths and anchors."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import io, os, re, sys
from urllib.parse import urlsplit, unquote
ROOT = str(SITE)
pages = {}
for d, _, ns in os.walk(ROOT):
    for n in ns:
        if n.endswith(".html"):
            rel = os.path.relpath(os.path.join(d, n), ROOT).replace("\\", "/")
            pages[rel] = io.open(os.path.join(d, n), encoding="utf-8").read()
ids = {f: set(re.findall(r'\sid="([^"]+)"', s)) for f, s in pages.items()}
bad, total = [], 0
for f, s in pages.items():
    base = os.path.dirname(f)
    for attr, ref in re.findall(r'(href|src)="([^"]+)"', s):
        if ref.startswith(("http", "mailto:", "tel:", "data:")): continue
        total += 1
        u = urlsplit(ref); path, anchor = unquote(u.path), u.fragment
        target = f if not path else os.path.normpath(os.path.join(base, path)).replace("\\", "/")
        if target.startswith("./"): target = target[2:]
        if path and target not in pages and not os.path.exists(os.path.join(ROOT, *target.split("/"))):
            bad.append((f, ref, "missing")); continue
        if anchor and target in ids and anchor not in ids[target]:
            bad.append((f, ref, "missing anchor"))
print("checked", total, "refs in", len(pages), "pages; bad:", len(bad))
for b in bad: print("  ", b)
for f, s in pages.items():
    if "\ufffd" in s or " ? " in re.sub(r"<[^>]+>", "", s): print("ENCODING?", f)
sys.exit(1 if bad else 0)
