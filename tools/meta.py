"""Metadata shared by the builders: the schema.org publisher node and breadcrumbs, Atom feeds, and the date a page's
content last changed (sitemap lastmod).

Used by launch_meta_v9.py (page graphs, sitemap, the feed links in every head), build_research.py (TechArticle,
CollectionPage, research/feed.xml) and build_blog.py (BlogPosting, Blog, blog/feed.xml). People stay out of the
site-wide graph: authors appear only on blog posts, as their bylines do.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA
import datetime, hashlib, html as H, io, json, subprocess
from pathlib import Path

HOME = "https://www.openexa.com/"
LOGO = {"@type": "ImageObject", "url": HOME + "assets/img/icon-512.png", "width": 512, "height": 512}
ORG = {"@type": "Organization", "@id": HOME + "#organization", "name": "OpenEXA", "url": HOME, "logo": LOGO}
WEBSITE = {"@type": "WebSite", "@id": HOME + "#website", "name": "OpenEXA", "url": HOME}
FEEDS = [("OpenEXA Blog", "/blog/feed.xml"), ("OpenEXA Research", "/research/feed.xml")]
FEED_LINKS = [f'<link rel="alternate" type="application/atom+xml" title="{t}" href="{h}">' for t, h in FEEDS]
ROBOTS = '<meta name="robots" content="max-image-preview:large">'

def ld(*nodes, id=None):
    """A <script type="application/ld+json"> holding one @graph of `nodes` (compact; "</" escaped)."""
    body = json.dumps({"@context": "https://schema.org", "@graph": list(nodes)}, ensure_ascii=False, separators=(",", ":"))
    attr = f' id="{id}"' if id else ""
    return f'<script type="application/ld+json"{attr}>' + body.replace("</", "<\\/") + "</script>"

def crumbs(*trail):
    """BreadcrumbList from (name, url) pairs after the home page."""
    items = [("OpenEXA", HOME), *trail]
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": n, "item": u} for i, (n, u) in enumerate(items, 1)]}

STAMPS = Path(str(DATA)) / "lastmod.json"
_stamps = json.loads(STAMPS.read_text(encoding="utf-8")) if STAMPS.exists() else {}

def lastmod(path):
    """YYYY-MM-DD the content of `path` (inside site/) last changed. data/lastmod.json records a hash and a date per page;
    the date moves to today only when the bytes change. Recorded rather than read from git history, so the dates survive
    squash merges and a rebuild in CI reproduces them exactly. A page seen for the first time takes its last commit's date."""
    key = Path(path).relative_to(SITE).as_posix()
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    seen = _stamps.get(key)
    if not seen or seen["sha"] != digest:
        run = lambda *a: subprocess.run(["git", *a, "--", str(path)], cwd=REPO, capture_output=True, text=True).stdout.strip()
        first = not seen and not run("status", "--porcelain") and run("log", "-1", "--format=%cs")
        _stamps[key] = {"sha": digest, "date": first or datetime.date.today().isoformat()}
    return _stamps[key]["date"]

def save_lastmod(keep):
    """Write data/lastmod.json, keeping only the pages in `keep` (paths inside site/)."""
    live = {Path(p).relative_to(SITE).as_posix() for p in keep}
    STAMPS.write_text(json.dumps({k: v for k, v in _stamps.items() if k in live}, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

def atom(path, title, subtitle, page_url, entries):
    """Write an Atom 1.0 feed to `path` (inside site/). entries: url, title, published, updated (YYYY-MM-DD), author, summary."""
    path = Path(path); x = lambda s: H.escape(s, quote=True); t = lambda d: d + "T00:00:00Z"
    out = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en">',
           f"  <title>{x(title)}</title>", f"  <subtitle>{x(subtitle)}</subtitle>",
           f'  <link rel="self" type="application/atom+xml" href="{HOME}{path.relative_to(SITE).as_posix()}"/>',
           f'  <link rel="alternate" type="text/html" href="{page_url}"/>',
           f"  <id>{page_url}</id>", f"  <updated>{t(max(e['updated'] for e in entries))}</updated>",
           f"  <author><name>OpenEXA</name><uri>{HOME}</uri></author>",
           f"  <icon>{HOME}assets/img/icon-192.png</icon>", f"  <logo>{HOME}assets/img/icon-512.png</logo>"]
    for e in entries:
        out += ["  <entry>", f"    <title>{x(e['title'])}</title>", f'    <link rel="alternate" type="text/html" href="{e["url"]}"/>',
                f"    <id>{e['url']}</id>", f"    <published>{t(e['published'])}</published>", f"    <updated>{t(e['updated'])}</updated>",
                f"    <author><name>{x(e['author'])}</name></author>", f"    <summary>{x(e['summary'])}</summary>", "  </entry>"]
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out + ["</feed>"]) + "\n")
