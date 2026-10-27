"""Fast checks over site/ - no browser, no network. Run before every commit; CI runs it on every pull request.

- the content rules (rules.py) on the visible text of every page: no exchange/broker names, contact details or ARR
  figures; people's names only on company.html (the whole team) and in the blog; the removed person nowhere;
- every page has one <h1>; every indexable page a canonical URL, parseable JSON-LD and an og:image that exists;
- the sitemap lists exactly the indexable pages; both Atom feeds parse and link only to pages that exist;
- staticwebapp.config.json parses and every redirect target that is a site path exists;
- markup integrity on every page: no duplicate id, and every label for= / aria-labelledby / aria-describedby /
  aria-controls points at an id that exists (a broken one silently mutes a control for screen readers).
    python tools/check_static.py
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
from rules import FORBIDDEN, PEOPLE, TEAM_NAMES, GONE
import html as H, json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(str(SITE)); HOME = "https://www.openexa.com/"
NOT_INDEXED = {"404.html", "insights.html"}  # the 404 page and the old Insights redirect stub
fails = []
def fail(*a): fails.append(" ".join(str(x) for x in a))
def visible(s):
    s = re.sub(r"<(script|style|noscript)\b.*?</\1>|<!--.*?-->", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s)))
def exists(url):  # a site URL (absolute on www, or root-relative) -> its file is in site/
    path = url.split("#")[0].split("?")[0].replace(HOME, "/")
    f = ROOT / path.lstrip("/")
    return f.is_file() or (f / "index.html").is_file() or f.with_suffix(".html").is_file()

pages = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.html"))
for rel in pages:
    s = (ROOT / rel).read_text(encoding="utf-8"); text = visible(s)
    if FORBIDDEN.search(text): fail(rel, "forbidden strings:", sorted(set(FORBIDDEN.findall(text))))
    if GONE.search(text): fail(rel, "the removed person:", sorted(set(GONE.findall(text))))
    people = sorted(set(m.lower() for m in PEOPLE.findall(text)))
    if rel == "company.html":
        missing = [n for n in TEAM_NAMES if n not in text]
        if missing: fail(rel, "team names missing:", missing)
    elif not rel.startswith("blog/") and people: fail(rel, "names outside Company and the blog:", people)
    markup = re.sub(r"<(script|style)\b.*?</\1>", "", s, flags=re.S | re.I)
    ids = re.findall(r'\sid="([^"]+)"', markup)
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes: fail(rel, "duplicate ids:", dupes)
    for attr, refs in re.findall(r'\s(for|aria-labelledby|aria-describedby|aria-controls)="([^"]+)"', markup):
        missing = [r for r in refs.split() if r not in ids]
        if missing: fail(rel, f"{attr} points at missing ids:", missing)
    if rel == "insights.html": continue
    if len(re.findall(r"<h1[\s>]", s)) != 1: fail(rel, "needs exactly one <h1>")
    if rel in NOT_INDEXED: continue
    canon = re.search(r'<link rel="canonical" href="([^"]+)">', s)
    if not canon: fail(rel, "no canonical")
    blocks = re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', s, re.S)
    if not blocks: fail(rel, "no JSON-LD")
    for b in blocks:
        try: json.loads(b)
        except ValueError as e: fail(rel, "JSON-LD does not parse:", e)
    for img in re.findall(r'<meta (?:property="og:image"|name="twitter:image") content="([^"]+)">', s):
        if not exists(img): fail(rel, "missing share image", img)

sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
listed = set(re.findall(r"<loc>" + re.escape(HOME) + r"([^<]*)</loc>", sitemap))
want = {"" if p == "index.html" else p[:-10] if p.endswith("index.html") else p for p in pages if p not in NOT_INDEXED}
if listed != want: fail("sitemap.xml: missing", sorted(want - listed), "extra", sorted(listed - want))

atom = {"a": "http://www.w3.org/2005/Atom"}
for feed in ("blog/feed.xml", "research/feed.xml"):
    try:
        root = ET.parse(ROOT / feed).getroot()
        links = [e.find("a:link", atom).get("href") for e in root.findall("a:entry", atom)]
        if not links: fail(feed, "has no entries")
        for u in links:
            if not exists(u): fail(feed, "links to a missing page", u)
    except (ET.ParseError, OSError) as e: fail(feed, "does not parse:", e)

try:
    config = json.loads((ROOT / "staticwebapp.config.json").read_text(encoding="utf-8"))
    for r in config["routes"]:
        target = r.get("redirect", "")
        if target.startswith("/") and not exists(target): fail("staticwebapp.config.json: redirect to a missing page", r["route"], "->", target)
except ValueError as e: fail("staticwebapp.config.json does not parse:", e)

for f in fails: print("FAIL", f)
print(f"check_static: {len(pages)} pages, {len(listed)} sitemap URLs - {'OK' if not fails else f'{len(fails)} problem(s)'}")
sys.exit(1 if fails else 0)
