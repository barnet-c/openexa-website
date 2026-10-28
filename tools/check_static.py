"""Fast checks over site/ - no browser, no network. Run before every commit; CI runs it on every pull request.

- the content rules (rules.py) on the visible text of every page: no exchange/broker names, contact details or ARR
  figures; people's names only on company.html (the whole team) and in the blog; the removed person nowhere;
- every page has one <h1>; every indexable page a canonical URL, parseable JSON-LD and an og:image that exists;
- the sitemap lists exactly the indexable pages; both Atom feeds parse and link only to pages that exist;
- staticwebapp.config.json parses and every redirect target that is a site path exists;
- markup integrity on every page: no duplicate id, and every label for= / aria-labelledby / aria-describedby /
  aria-controls points at an id that exists (a broken one silently mutes a control for screen readers);
- the Lifecycle 01 sessions: one #oxa-sessions record, identical on the home and Proof pages, and every static count,
  list and table (what readers without JavaScript get) says what that record says; the retired 6/4 split nowhere.
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

# ---- the Lifecycle 01 sessions: ONE record (<script type="application/json" id="oxa-sessions"> on the home and Proof
# pages) draws the chart and derives every session count (assets/js/proof.js, story.js). The static text that readers
# without JavaScript get must say exactly what the record says, and the retired 6/4 split must not come back anywhere.
NUMW = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
words = lambda n: NUMW[n] if 0 <= n < len(NUMW) else str(n)
capw = lambda t: t[:1].upper() + t[1:]
records = {}
for rel in ("index.html", "evidence.html"):
    s = (ROOT / rel).read_text(encoding="utf-8")
    found = re.findall(r'<script type="application/json" id="oxa-sessions">(.*?)</script>', s, re.S)
    if len(found) != 1: fail(rel, "needs exactly one #oxa-sessions record, found", len(found)); continue
    try: records[rel] = (json.loads(found[0]), s)
    except ValueError as e: fail(rel, "#oxa-sessions does not parse:", e)
if len(records) == 2 and records["index.html"][0] != records["evidence.html"][0]:
    fail("#oxa-sessions: the home and Proof pages carry different records")
for rel, (rec, s) in records.items():
    S, floor, unit = rec.get("sessions"), rec.get("floor"), rec.get("unit") or "bps"
    if not isinstance(S, list) or not S or not isinstance(floor, (int, float)) or floor <= 0:
        fail(rel, "#oxa-sessions needs a list of sessions and a positive floor"); continue
    def above(v):  # the rule proof.js and story.js apply: ">N" with N >= floor is above it; a bare N must exceed it
        m = re.fullmatch(r"(>=|≥|>)?\s*(\d+(?:\.\d+)?)", str(v or "").strip())
        return bool(m) and (float(m[2]) >= floor if m[1] == ">" else float(m[2]) > floor)
    field = lambda x, k: str(x.get(k) or "").strip()
    C = {"total": len(S), "above": sum(above(x.get("value")) for x in S),
         "premium": sum(field(x, "regime").lower().startswith("prem") for x in S),
         "discount": sum(field(x, "regime").lower().startswith("disc") for x in S),
         "confirmed": sum(bool(re.search(r"confirm", field(x, "confirmation"), re.I)) and not re.search(r"pending|awaiting|unconfirm|^not\b", field(x, "confirmation"), re.I) for x in S),
         "settled": sum(bool(re.fullmatch(r"settled", field(x, "status"), re.I)) for x in S), "floor": floor}
    if C["premium"] + C["discount"] != C["total"]: fail(rel, "#oxa-sessions: every session needs a Premium or Discount regime")
    if C["above"] != C["total"]: fail(rel, "#oxa-sessions: a session is not above the floor; the copy says every session is")
    fmtn = lambda n: str(int(n)) if float(n).is_integer() else str(n)
    def derived(key, as_):
        if key == "regimes": return capw(words(C["premium"])) + " premium, " + words(C["discount"]) + " discount."
        if key not in C: return None
        n = C[key]
        return words(int(n)) if as_ == "words" else capw(words(int(n))) if as_ == "Words" else fmtn(n)
    for tag, text in re.findall(r'(<[a-z]+\b[^>]*\sdata-proof="[^"]*"[^>]*>)([^<]*)<', s):
        key = re.search(r'\sdata-proof="([^"]*)"', tag)[1]
        as_ = (re.search(r'\sdata-proof-as="([^"]*)"', tag) or [None, None])[1]
        want = derived(key, as_)
        if want is None: fail(rel, f'unknown data-proof="{key}"')
        elif H.unescape(text).strip() != want: fail(rel, f'static data-proof="{key}" reads {text.strip()!r}; the record says {want!r}')
        cnt = re.search(r'\sdata-count="([^"]*)"', tag)
        if cnt and want is not None and cnt[1] != fmtn(C[key]): fail(rel, f'data-count="{cnt[1]}" on data-proof="{key}"; the record says {fmtn(C[key])}')
    if rel == "index.html":
        # the overture's copy (story.js derives the same words before it splits them)
        n_all, n_ab = C["total"], C["above"]
        story_n = {"every": "every one of " + words(n_all) if n_ab == n_all else words(n_ab) + " of " + words(n_all),
                   "tally": capw(words(n_ab)) + " for " + words(n_all) + ".", "lifecycle": str(rec.get("lifecycle") or "")}
        for tag, text in re.findall(r'(<[a-z]+\b[^>]*\sdata-story-n="[^"]*"[^>]*>)([^<]*)<', s):
            key = re.search(r'\sdata-story-n="([^"]*)"', tag)[1]
            as_ = (re.search(r'\sdata-story-as="([^"]*)"', tag) or [None, None])[1]
            want = story_n.get(key) if key in story_n else derived(key, as_)
            if want is None: fail(rel, f'unknown data-story-n="{key}"')
            elif H.unescape(text).strip() != want: fail(rel, f'static data-story-n="{key}" reads {text.strip()!r}; the record says {want!r}')
        rows = [tuple(H.unescape(c).strip() for c in r) for r in re.findall(r'<li><b>([^<]*)</b><span>([^<]*)</span><span>([^<]*)</span></li>', s.split('class="proof-list"', 1)[-1].split("</ol>", 1)[0])]
        want_rows = [(field(x, "day"), field(x, "value") + " " + unit, field(x, "regime")) for x in S]
        if rows != want_rows: fail(rel, "the no-JS session list (.proof-list) differs from #oxa-sessions:", rows[:3], "...")
    if rel == "evidence.html":
        body = s.split("data-proof-table", 1)[-1].split("</tbody>", 1)[0]
        rows = [tuple(H.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)) for r in re.findall(r"<tr>(.*?)</tr>", body.split("<tbody>", 1)[-1], re.S)]
        want_rows = [(field(x, "day"), field(x, "regime"), field(x, "value") + " " + unit, field(x, "confirmation"), field(x, "status")) for x in S]
        if rows != want_rows: fail(rel, "the static session table differs from #oxa-sessions:", rows[:2], "...")
    if C["premium"] or C["discount"]:
        sentence = derived("regimes", None)
        if sentence not in visible(s): fail(rel, "the visible text does not state the regime split", repr(sentence))
for rel in pages:  # the 6/4 split was a mistake against the per-session table; it must not return in any page or note
    t = visible((ROOT / rel).read_text(encoding="utf-8"))
    if re.search(r"six premium|four discount|six sessions were in premium|four in discount", t, re.I): fail(rel, "states the retired six premium / four discount split")

for f in fails: print("FAIL", f)
print(f"check_static: {len(pages)} pages, {len(listed)} sitemap URLs - {'OK' if not fails else f'{len(fails)} problem(s)'}")
sys.exit(1 if fails else 0)
