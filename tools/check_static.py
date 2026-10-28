"""Fast checks over site/ - no browser, no network. Run before every commit; CI runs it on every pull request.

- the content rules (rules.py) on the visible text of every page: no exchange/broker names, contact details or ARR
  figures; people's names only on company.html (the whole team) and in the blog; the removed person nowhere;
- every page has one <h1>; every indexable page a canonical URL, parseable JSON-LD and an og:image that exists;
- the sitemap lists exactly the indexable pages; both Atom feeds parse and link only to pages that exist;
- staticwebapp.config.json parses and every redirect target that is a site path exists;
- markup integrity on every page: no duplicate id, and every label for= / aria-labelledby / aria-describedby /
  aria-controls points at an id that exists (a broken one silently mutes a control for screen readers);
- the Lifecycle 01 sessions: one #oxa-sessions record, identical on the home and Proof pages, and every static count,
  list and table (what readers without JavaScript get) says what that record says;
- numbers are never shown untrue: no [data-count] on a record-derived [data-proof] figure, and any [data-count] left
  holds its final value in the markup; every premium/discount split stated anywhere (research 09 included) is the
  record's; research 09's figure reads its regimes from the record; the Proof hero plate draws one record per session;
- craft guards: no :has() in site.css that restyles a subtree or keys on nothing (outside @media (scripting: none)),
  and none in the ledger and nav regions; 'Fig.' / 'Table' / 'Plate' labels unique on every hand-written page (the
  overture's captions in story.js count for the home page); the misspelled blog placeholder referenced nowhere; every
  body cell of the Platform and Proof tables names its column (td[data-th]) for the phone restack.
    python tools/check_static.py [--only=count_not_on_proof,regime_split,...]   (--only limits the round-1 guards)
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
        # (data-count on a data-proof figure is no longer compared with the record: it may not be there at all, see
        # check_count_not_on_proof below; NV1/PF1 make [data-count] inert, so no count-up can show an untrue number)
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


# ---- round-1 guards (v2). One function per check; each names the page and the offending values when it fails. ----
def counts_of(rec):
    """the record's counts, by the rule proof.js, story.js and the block above apply"""
    S, floor = rec.get("sessions") or [], rec.get("floor") or 0
    field = lambda x, k: str(x.get(k) or "").strip()
    conf = lambda x: bool(re.search(r"confirm", field(x, "confirmation"), re.I)) and not re.search(r"pending|awaiting|unconfirm|^not\b", field(x, "confirmation"), re.I)
    return {"total": len(S), "premium": sum(field(x, "regime").lower().startswith("prem") for x in S),
            "discount": sum(field(x, "regime").lower().startswith("disc") for x in S),
            "confirmed": sum(conf(x) for x in S), "floor": floor,
            "regimes": "".join("p" if field(x, "regime").lower().startswith("prem") else "d" if field(x, "regime").lower().startswith("disc") else "?" for x in S)}
RECORD = (records.get("index.html") or records.get("evidence.html") or (None,))[0]
HAND = ["index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "company.html", "access.html"]
TEXT_SUFFIXES = {".html", ".xml", ".json", ".js", ".css", ".txt", ".svg", ".webmanifest"}


def check_count_not_on_proof():
    """No element that carries data-proof (a figure derived from #oxa-sessions) may also carry data-count: a count-up
    would show it untrue on the way to its value (NV1, PF1; replaces the old data-count == record comparison)."""
    for rel in pages:
        s = (ROOT / rel).read_text(encoding="utf-8")
        for tag in re.findall(r"<[a-z]+\b[^>]*>", s):
            if re.search(r"\sdata-proof=", tag) and re.search(r"\sdata-count=", tag):
                fail(rel, "count_not_on_proof: a data-proof figure carries data-count (counts up through untrue values):", tag[:120])


def check_count_static_final():
    """Every [data-count] element still in the markup holds its final formatted value (prefix + value + suffix, as
    site.js formats it), so the static text is never a number the page would not end on."""
    for rel in pages:
        s = (ROOT / rel).read_text(encoding="utf-8")
        for tag, text in re.findall(r'(<[a-z]+\b[^>]*\sdata-count="[^"]*"[^>]*>)([^<]*)<', s):
            a = lambda k: H.unescape((re.search(r'\s' + k + r'="([^"]*)"', tag) or [None, ""])[1])
            try: val = float(a("data-count"))
            except ValueError: fail(rel, "count_static_final: data-count is not a number:", tag[:120]); continue
            dec = int(a("data-decimals") or 0)
            want = a("data-prefix") + f"{val:,.{dec}f}" + a("data-suffix")
            if H.unescape(text).strip() != want: fail(rel, f"count_static_final: [data-count] reads {text.strip()!r}; its final value is {want!r}:", tag[:100])


def check_regime_split():
    """Every premium/discount split the site states, research 09 included, equals the record's counts (in words or
    digits). Pending the CEO's confirmation, the per-session record is the one source: the CEO's research note says six
    premium / four discount, the record and the whole site say five / five (D15). Any mismatch fails, so the check is
    never weaker than the retired 'six premium | four discount' ban it replaces."""
    if not RECORD: fail("regime_split: no #oxa-sessions record to check the premium/discount splits against"); return
    c = counts_of(RECORD)
    num = r"(\d+|" + "|".join(NUMW) + r")"
    value = lambda t: int(t) if t.isdigit() else NUMW.index(t.lower())
    both = [r"(?i:\b%s) premium, (?i:%s) discount\b" % (num, num),  # 'Five premium, five discount.'
            r"(?i)\b%s sessions? (?:were|was) in (?:a )?premium regimes?, %s (?:sessions? )?(?:were |was )?in (?:a )?discount\b" % (num, num)]
    one = [(r"(?<![Dd]ay )(?i:\b%s) premium\b" % num, "premium"), (r"(?<![Dd]ay )(?i:\b%s) discount\b" % num, "discount"),
           (r"(?i)\b%s (?:sessions? )?(?:were |was )?in (?:a )?premium\b" % num, "premium"),
           (r"(?i)\b%s (?:sessions? )?(?:were |was )?in (?:a )?discount\b" % num, "discount")]
    seen = 0
    for rel in pages:  # every page and note, research/09-* included
        t = visible((ROOT / rel).read_text(encoding="utf-8"))
        for pat in both:
            for m in re.finditer(pat, t):
                seen += 1
                if (value(m[1]), value(m[2])) != (c["premium"], c["discount"]):
                    fail(rel, f"regime_split: {m[0]!r} says {value(m[1])} premium / {value(m[2])} discount; the record says {c['premium']} / {c['discount']}")
        for pat, key in one:  # a split stated in other words ('five premium sessions and five discount sessions')
            for m in re.finditer(pat, t):
                if value(m[1]) != c[key]: fail(rel, f"regime_split: {t[max(0, m.start() - 30):m.end() + 20]!r} says {value(m[1])} {key}; the record says {c[key]}")
    if not seen: fail("regime_split: no page states the premium/discount split at all (expected at least the proof stats)")


def check_research09_regimes():
    """Research 09's figure draws the sessions' regimes from the record, not from a second copy: build_research.py writes
    data-regimes on its figure stage (PF5) and it equals #oxa-sessions; figure.js's fallback literal, if any, agrees."""
    if not RECORD: fail("research09_regimes: no #oxa-sessions record"); return
    want = counts_of(RECORD)["regimes"]
    notes = sorted(p for p in pages if re.match(r"research/09-", p))
    if not notes: fail("research09_regimes: research/09-* not found"); return
    for rel in notes:
        s = (ROOT / rel).read_text(encoding="utf-8")
        stage = re.search(r'<[a-z]+\b[^>]*\sdata-figure="sessions"[^>]*>', s)
        if not stage: fail(rel, "research09_regimes: no data-figure=\"sessions\" stage"); continue
        attr = re.search(r'\sdata-regimes="([^"]*)"', stage[0])
        if not attr: fail(rel, f"research09_regimes: the figure stage has no data-regimes (figure.js keeps its own copy of the record); the record says {want!r}"); continue
        v = attr[1].strip()
        got = v.lower() if re.fullmatch(r"[pdPD]+", v) else "".join("p" if w.startswith("prem") else "d" if w.startswith("disc") else "?" for w in re.findall(r"[a-z]+", v.lower()))
        if got != want: fail(rel, f"research09_regimes: data-regimes={v!r} reads {got!r}; the record says {want!r}")
    js = (ROOT / "assets/js/figure.js").read_text(encoding="utf-8")
    for lit in re.findall(r"['\"]([pd]{%d})['\"]" % len(want), js):
        if lit != want: fail("assets/js/figure.js", f"research09_regimes: the fallback regime literal {lit!r} differs from the record {want!r}")


def css_style_rules(css, first_line=1):
    """(selector list, enclosing at-rule preludes, line) for every style rule; comments and strings are skipped"""
    css = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m[0]), css, flags=re.S)  # same length: offsets keep their lines
    out, stack, i, n, start = [], [], 0, len(css), 0
    def skip_string(j):
        q = css[j]; j += 1
        while j < n and css[j] != q: j += 2 if css[j] == "\\" else 1
        return j + 1
    while i < n:
        ch = css[i]
        if ch in "\"'": i = skip_string(i); continue
        if ch == "{":
            prelude = css[start:i].strip()
            if prelude.startswith("@"): stack.append(prelude); i += 1; start = i; continue
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] in "\"'": j = skip_string(j); continue
                depth += {"{": 1, "}": -1}.get(css[j], 0); j += 1
            lead = len(css[start:i]) - len(css[start:i].lstrip())
            out.append((prelude, list(stack), first_line + css.count("\n", 0, start + lead))); i = start = j; continue
        if ch == "}":
            if stack: stack.pop()
            i += 1; start = i; continue
        if ch == ";": start = i + 1
        i += 1
    return out


def split_top(s, seps):
    """split s at characters in seps that are outside (), [] and strings; returns (parts, separators)"""
    parts, found, depth, cur, i = [], [], 0, "", 0
    while i < len(s):
        ch = s[i]
        if ch in "([": depth += 1
        elif ch in ")]": depth -= 1
        if depth == 0 and ch in seps: parts.append(cur); found.append(ch); cur = ""
        else: cur += ch
        i += 1
    parts.append(cur)
    return parts, found


def compounds(sel):
    """the compound selectors of one complex selector, in order (combinators: whitespace, >, +, ~)"""
    s = re.sub(r"\s*([>+~])\s*", r"\1", sel.strip())
    parts, _ = split_top(s, " >+~")
    return [p for p in parts if p]


def has_args(compound):
    """the argument of every :has( in a compound, nested ones included (e.g. :not(:has(...)))"""
    out = []
    for m in re.finditer(r":has\(", compound):
        depth, j = 1, m.end()
        while j < len(compound) and depth:
            depth += {"(": 1, ")": -1}.get(compound[j], 0); j += 1
        out.append(compound[m.end():j - 1])
    return out


def check_has_guard():
    """No :has() in site.css that restyles a subtree on every change (a :has() followed by another compound) or keys on
    nothing (its argument names no class, id, attribute or element type), except inside @media (scripting: none).
    Rules that end in the :has() itself stay allowed ('.seg label:has(input:checked)'). (LG1, NV2: one footer-clock tick
    restyled 1,108 of 2,440 elements on the home page.)"""
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    for prelude, ats, _line in css_style_rules(css):
        if ":has(" not in prelude: continue
        if any(re.search(r"\(\s*scripting\s*:\s*none\s*\)", a) for a in ats): continue
        sels, _ = split_top(prelude, ",")
        for sel in sels:
            if ":has(" not in sel: continue
            cs = compounds(sel)
            where = [k for k, c in enumerate(cs) if ":has(" in c]
            if where and where[0] < len(cs) - 1:
                fail("assets/css/site.css", f"has_guard: :has() followed by another compound (restyles a subtree): {sel.strip()!r}" + (f" inside {ats}" if ats else ""))
                continue
            for c in (cs[k] for k in where):
                for arg in has_args(c):
                    plain = re.sub(r"::?[\w-]+(\([^)]*\))?", " ", arg)  # pseudo-classes/elements name no element
                    if not re.search(r"[.#\[]", arg) and not re.search(r"(^|[\s>+~(])[a-zA-Z][\w-]*", plain):
                        fail("assets/css/site.css", f"has_guard: :has({arg}) names no class, id, attribute or element: {sel.strip()!r}")


def check_has_regions():
    """The two owners' greps (LG1, NV2): no ':has(' anywhere in v2:ledger, none in v2:nav outside @media (scripting:
    none). With either set left the storm remains, so both are required."""
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    for region in ("ledger", "nav"):
        m = re.search(r"/\* v2:%s:start \*/(.*?)/\* v2:%s:end \*/" % (region, region), css, re.S)
        if not m: fail("assets/css/site.css", f"has_regions: the v2:{region} region markers are missing"); continue
        for prelude, ats, _line in css_style_rules(m[1]):
            if ":has(" not in prelude: continue
            if region == "nav" and any(re.search(r"\(\s*scripting\s*:\s*none\s*\)", a) for a in ats): continue
            fail("assets/css/site.css", f"has_regions: ':has(' in v2:{region}" + (" outside @media (scripting: none)" if region == "nav" else "") + f": {prelude[:110]!r}")


def check_figure_labels():
    """Every 'Fig. N', 'Table N' and 'Plate N' label is unique on each hand-written page: its visible text, the captions
    its scripts draw from data-*-label attributes, and for the home page the overture's own captions (story.js
    label() strings). Research and blog pages keep their own numbering and are not checked."""
    LABEL = re.compile(r"\b(Fig\.|Table|Plate)\s+(\d+(?:\.\d+)?)")
    key = lambda kind, n: kind + " " + ".".join(str(int(x)) for x in n.split("."))
    story = (ROOT / "assets/js/story.js").read_text(encoding="utf-8")
    story = re.sub(r"/\*.*?\*/", " ", story, flags=re.S)
    story = re.sub(r"(?m)(^|[\s;{}(),])//.*$", r"\1", story)
    story_caps = [re.sub(r"<[^>]+>", "", m[2]) for m in re.finditer(r"(['\"`])((?:\\.|(?!\1).)*?)\1", story, re.S) if LABEL.search(re.sub(r"<[^>]+>", "", m[2]))]
    for rel in HAND:
        s = (ROOT / rel).read_text(encoding="utf-8")
        body = re.sub(r"<head\b.*?</head>|<(title|desc)\b.*?</\1>", " ", s, flags=re.S | re.I)
        sources = [("text", visible(body))] + [("attr " + a, H.unescape(v)) for a, v in re.findall(r"\s(data-[\w-]*label)=\"([^\"]*)\"", s)]
        if rel == "index.html": sources += [("story.js", t) for t in story_caps]
        seen = {}
        for where, text in sources:
            for m in LABEL.finditer(text):
                seen.setdefault(key(m[1], m[2]), []).append(f"{where}: {text[m.start():m.end() + 28].strip()!r}")
        for k, hits in seen.items():
            if len(hits) > 1: fail(rel, f"figure_labels: '{k}' labels {len(hits)} figures:", "; ".join(hits))


def check_blog_placeholder():
    """The misspelled legacy placeholder ('RESERCH IN FINANCE') is referenced by no file under site/ (PG1, D8)."""
    name = "blog-028-649e320f57bee709f474e657-research-0fc3c7b1.webp"
    hits = {}
    for f in ROOT.rglob("*"):
        if f.is_file() and f.suffix.lower() in TEXT_SUFFIXES:
            n = f.read_text(encoding="utf-8", errors="replace").count(name)
            if n: hits[f.relative_to(ROOT).as_posix()] = n
    if hits: fail(f"blog_placeholder: {name} is referenced {sum(hits.values())} times:", sorted(hits.items())[:6], "..." if len(hits) > 6 else "")


def check_proof_plate():
    """The Proof page's hero plate draws the record: one [data-plate-rec] per session and one [data-plate-tick] per
    broker-confirmed session in #oxa-sessions (PG3)."""
    if "evidence.html" not in records: fail("evidence.html", "proof_plate: no #oxa-sessions record"); return
    c = counts_of(records["evidence.html"][0])
    s = records["evidence.html"][1]
    # the hero is the first <section> whose class names page-hero (any attribute order); the plate lives inside it
    hero = re.search(r'<section\b(?=[^>]*\sclass="[^"]*\bpage-hero\b)[^>]*>.*?</section>', s, re.S)
    if not hero: fail("evidence.html", "proof_plate: no hero section (section.page-hero)"); return
    mark = lambda a: len(re.findall(r"\s%s(?=[\s=>/])" % a, hero[0]))
    rec, tick = mark("data-plate-rec"), mark("data-plate-tick")
    if rec != c["total"]: fail("evidence.html", f"proof_plate: the hero plate has {rec} [data-plate-rec]; the record has {c['total']} sessions")
    if tick != c["confirmed"]: fail("evidence.html", f"proof_plate: the hero plate has {tick} [data-plate-tick]; the record has {c['confirmed']} broker-confirmed sessions")


def check_table_th():
    """Every body cell of every table in a .table-scroll on Platform and Proof names its column (td[data-th]), so the
    phone restack (pages' <= 600 px rule keyed on td[data-th]) labels each value (PG5, PF4)."""
    for rel in ("platform.html", "evidence.html"):
        s = (ROOT / rel).read_text(encoding="utf-8")
        boxes = re.findall(r'<div\b(?=[^>]*\sclass="[^"]*\btable-scroll\b)[^>]*>(.*?)</table>', s, re.S)
        if not boxes: fail(rel, "table_th: no .table-scroll table"); continue
        for k, box in enumerate(boxes, 1):
            body = box.split("<tbody", 1)[-1]
            cells = re.findall(r"<td\b[^>]*>", body)
            bare = [c for c in cells if not re.search(r'\sdata-th="[^"]+"', c)]
            if not cells: fail(rel, f"table_th: table {k} has no body cells")
            elif bare: fail(rel, f"table_th: table {k}: {len(bare)} of {len(cells)} body cells carry no data-th:", bare[0][:80])


# ---- round-2 guards (director's test list, 28 Oct) ----
def check_hover_guard():
    """Every ':hover' selector inside a v2 region of site.css (/* v2:<owner>:start */ ... end) sits inside
    @media (hover: hover), so a tap never leaves a stuck hover state on touch screens ('Follow a proposal' kept its green
    fill after Stop). ':not(:hover)' dimming counts too. Base rules outside the regions stay as pages gated them in round 1.
    (cross: hover gating, every owner; SW-R2-7, LG-R2-5, LC-R2-7, AR-R2-5, OV-R2-11.)"""
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    regions = list(re.finditer(r"/\* v2:([\w-]+):start \*/(.*?)/\* v2:\1:end \*/", css, re.S))
    if not regions: fail("assets/css/site.css", "hover_guard: no v2 region markers"); return
    for m in regions:
        first = css.count("\n", 0, m.start(2)) + 1
        for prelude, ats, line in css_style_rules(m[2], first):
            if ":hover" not in prelude or any(re.search(r"\(\s*hover\s*:\s*hover\s*\)", a) for a in ats): continue
            sels, _ = split_top(prelude, ",")
            for sel in (x.strip() for x in sels if ":hover" in x):
                fail("assets/css/site.css", f"hover_guard: v2:{m[1]} line {line}: {sel[:110]!r} is outside @media (hover: hover)" + (f" (inside {ats})" if ats else ""))


WEIGHT = {"assets/css/site.css": 66000, "index.html scripts": 151000}  # gzip -9 bytes: 28 Oct's size plus 10%


def check_weight():
    """Transfer weight cannot grow unnoticed while the CSS split is deferred: gzip -9 of site.css <= 66,000 bytes and the
    sum of gzip -9 over the scripts index.html loads (<script src>) <= 151,000 bytes: 59,799 and 137,253 at 1a6b9fb,
    plus 10% (director's test list; _cross 'rejected': the split is deferred)."""
    import gzip
    gz = lambda rel: len(gzip.compress((ROOT / rel).read_bytes(), 9))
    css = gz("assets/css/site.css")
    if css > WEIGHT["assets/css/site.css"]: fail("assets/css/site.css", f"weight: gzip {css:,} bytes; budget {WEIGHT['assets/css/site.css']:,} (1a6b9fb's 59,799 + 10%)")
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    srcs = [u.split("?")[0].lstrip("/") for u in re.findall(r'<script\b[^>]*\ssrc="([^"]+)"', s)]
    missing = [u for u in srcs if not (ROOT / u).is_file()]
    if missing: fail("index.html", "weight: scripts not found:", missing)
    js = {u: gz(u) for u in srcs if (ROOT / u).is_file()}
    total = sum(js.values())
    if total > WEIGHT["index.html scripts"]:
        fail("index.html", f"weight: its {len(js)} scripts are {total:,} bytes gzipped; budget {WEIGHT['index.html scripts']:,} (1a6b9fb's 137,253 + 10%):",
             ", ".join(f"{Path(u).name} {n:,}" for u, n in sorted(js.items(), key=lambda kv: -kv[1])))


def check_story_fallback():
    """story.js's fallback table (used only when #oxa-sessions cannot be read) is the record too: its regime literal
    (/'([PD]{10})'.split/) equals the record's regimes in order (figure.js's literal is research09_regimes'; D15)."""
    if not RECORD: fail("story_fallback: no #oxa-sessions record"); return
    want = counts_of(RECORD)["regimes"].upper()
    js = (ROOT / "assets/js/story.js").read_text(encoding="utf-8")
    lits = re.findall(r"'([PD]{%d})'\.split" % len(want), js, re.I)
    if not lits: fail("assets/js/story.js", f"story_fallback: no fallback regime literal of {len(want)} P/D letters followed by .split (the record has {len(want)} sessions)")
    for lit in lits:
        if lit.upper() != want: fail("assets/js/story.js", f"story_fallback: the fallback literal {lit!r} differs from the record {want!r}")


COST_DEFS = ["working capital", "credit exposure", "routing, reconciliation", "oversight, operations"]


def check_cost_definitions():
    """Production's definitions of the four cost components are back on both pages that draw the cost figure (D1, PF-R2-1):
    the visible text (no JavaScript needed) of index.html and evidence.html each contains 'working capital', 'credit
    exposure', 'routing, reconciliation' and 'oversight, operations' (case-insensitive)."""
    for rel in ("index.html", "evidence.html"):
        t = re.sub(r"\s+", " ", visible((ROOT / rel).read_text(encoding="utf-8"))).lower()
        missing = [d for d in COST_DEFS if d not in t]
        if missing: fail(rel, f"cost_definitions: production's cost definitions missing from the visible text: {missing}")


def chapter(s, idx):
    """the markup of the chapter whose sec-head index reads idx, up to the next chapter's sec-head (or '')"""
    parts = re.split(r'(?=<span class="idx">\d\d</span>)', s)
    hit = [p for p in parts if p.startswith(f'<span class="idx">{idx}</span>')]
    return hit[0] if hit else ""


def check_platform04():
    """Platform §04 agrees with its h2 'Every action passes three gates.' (D3): no tag or drawing label in the chapter
    reads 'Gate 05' (or 'Gate 06'); the tags say 'In 05 · Execute' / 'In 06 · Settle' (LC-R2-1)."""
    s = (ROOT / "platform.html").read_text(encoding="utf-8")
    sec = chapter(s, "04")
    if not sec: fail("platform.html", "platform04: no §04 (sec-head idx 04)"); return
    hits = sorted(set(m[0] for m in re.finditer(r"(?i)\bgate\s+0[56]\b[^<]{0,14}", H.unescape(sec))))
    if hits: fail("platform.html", f"platform04: §04 still labels gates by number: {hits}")


GUARDS = [check_count_not_on_proof, check_count_static_final, check_regime_split, check_research09_regimes, check_has_guard,
          check_has_regions, check_figure_labels, check_blog_placeholder, check_proof_plate, check_table_th,
          check_hover_guard, check_weight, check_story_fallback, check_cost_definitions, check_platform04]
only = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), None)
if "--only" in sys.argv[1:-1]: only = sys.argv[sys.argv.index("--only") + 1]
for g in GUARDS:
    if only is None or g.__name__[len("check_"):] in only.split(","): g()

for f in fails: print("FAIL", f)
print(f"check_static: {len(pages)} pages, {len(listed)} sitemap URLs - {'OK' if not fails else f'{len(fails)} problem(s)'}")
sys.exit(1 if fails else 0)
