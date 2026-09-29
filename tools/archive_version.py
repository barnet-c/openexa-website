"""Archive the current build as a numbered version: copy the source folder, write the checksum manifest, build the ZIP.
usage: python archive_version.py <n> <slug> <date> <provenance-file>   e.g. 11 team-resolution 2026-09-23 prov.txt
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import hashlib, html, json, os, re, shutil, sys, zipfile
from pathlib import Path

VERSION, SLUG, DATE = int(sys.argv[1]), sys.argv[2], sys.argv[3]
PROVENANCE = Path(sys.argv[4]).read_text(encoding="utf-8").strip()
SRC = Path(str(SITE))
ARCHIVE = Path(str(ARCHIVE))
FOLDER = f"v{VERSION}-{DATE}-{SLUG}"
DST = ARCHIVE / FOLDER
ZIP = DIST / f"OpenEXA-v{VERSION}-{SLUG}.zip"

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# ---- copy (clean) ----
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "Thumbs.db", ".DS_Store"))

# ---- manifest ----
files = sorted(p for p in DST.rglob("*") if p.is_file())
rel = lambda p: p.relative_to(DST).as_posix()
index = (DST / "index.html").read_text(encoding="utf-8")
title = html.unescape(re.search(r"<title>(.*?)</title>", index, re.S).group(1).strip())
h1 = re.search(r"<h1[^>]*>(.*?)</h1>", index, re.S).group(1)
headline = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h1))).strip()
pages = [rel(p) for p in files if p.suffix == ".html"]
hosts = set()
for p in files:
    if p.suffix in (".html", ".css", ".js", ".xml", ".webmanifest", ".txt"):
        hosts.update(re.findall(r"https?://([a-z0-9.-]+\.[a-z]{2,})", p.read_text(encoding="utf-8", errors="ignore"), re.I))
manifest = {
    "version": VERSION,
    "date_published": DATE,
    "netlify_site": "",
    "url": "",
    "folder": FOLDER,
    "title": title,
    "headline": headline,
    "pages": pages,
    "file_count": len(files),
    "total_bytes": sum(p.stat().st_size for p in files),
    "links_restored": {},
    "redirects": {},
    "server_404": [],
    "unresolved_references": [],
    "external_hosts": sorted(h.lower() for h in hosts if h.lower() not in ("schema.org", "www.sitemaps.org", "www.w3.org")),  # namespaces, never fetched
    "files": {rel(p): {"bytes": p.stat().st_size, "sha256": sha(p)} for p in files},
    "provenance": PROVENANCE,
}
(ARCHIVE / "_manifests" / f"v{VERSION}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

# ---- zip from the source, verify against the manifest ----
if ZIP.exists():
    ZIP.unlink()
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        z.write(SRC / p.relative_to(DST), rel(p))
with zipfile.ZipFile(ZIP) as z:
    names = sorted(z.namelist())
    assert names == sorted(manifest["files"]), set(names) ^ set(manifest["files"])
    for n in names:
        assert hashlib.sha256(z.read(n)).hexdigest() == manifest["files"][n]["sha256"], n
print(f"archived {len(files)} files / {manifest['total_bytes']:,} bytes -> {DST.name}")
print(f"pages: {len(pages)}  hosts: {manifest['external_hosts']}")
print(f"zip: {ZIP.name}  {ZIP.stat().st_size:,} bytes  sha256 {sha(ZIP)}")
