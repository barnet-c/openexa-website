"""Fail while any placeholder remains on the site, so a page with a gap cannot be published by accident (V2X-D2: the
site stays publishable at every commit; CI's static job runs this on every pull request).

Every gap the owner still has to fill is marked one way, and only this way:
    <span class="tbs" data-placeholder="founding-year">To be supplied by OpenEXA: founding year</span>
(any element; `data-placeholder` names the gap, the visible text starts with "To be supplied by OpenEXA").
What fails:
- an open marker (a gap still on a page);
- a malformed marker: a data-placeholder with no name or without the phrase, or the phrase without data-placeholder
  (anywhere under site/: pages, feeds, the manifest, scripts), so one search always finds every gap;
- the usual leftovers of unfinished copy in a page's visible text or in the attributes a reader or a share card sees
  (alt, title, aria-label, placeholder, meta content): lorem ipsum, TODO / FIXME / TBD / TBC / XXX, an unfilled
  template ({{ ... }}) and bracketed stand-ins ("[insert ...]", "[placeholder]").
Before it scans the site it runs itself on a sample with one gap of each kind and on a clean sample; if it would miss
one, it fails (exit 2), so the check cannot pass by being broken.
    python tools/check_placeholders.py [--list]      (--list: the open gaps as a Markdown checklist; exit 0)
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import html, io, os, re, sys

PHRASE = "To be supplied by OpenEXA"
MARKER = re.compile(r'<([a-z][a-z0-9]*)\b[^>]*\sdata-placeholder="([^"]*)"[^>]*>(.*?)</\1>', re.S | re.I)
BARE_ATTR = re.compile(r"\sdata-placeholder(?:\s*=|[\s>/])", re.I)
TEXT = re.compile(re.escape(PHRASE), re.I)
# leftovers of unfinished copy; the all-caps words are matched as written (a sentence may say "todo" in prose)
LEFTOVER = re.compile(r"\b(?:TODO|FIXME|TBD|TBC|XXX+)\b|(?i:lorem ipsum|dolor sit amet|\{\{|\}\}|\[\s*(?:insert|placeholder|tbd|tk)\b[^\]]*\])")
SEEN_ATTRS = re.compile(r'\s(alt|title|aria-label|placeholder|content)="([^"]*)"', re.I)
TEXT_SUFFIXES = {".html", ".xml", ".json", ".js", ".txt", ".webmanifest", ".svg"}


def visible(s):
    s = re.sub(r"<(script|style|noscript)\b.*?</\1>|<!--.*?-->", " ", s, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s)))


def scan_page(rel, s):
    """(open, malformed, leftovers) for one HTML page: lists of (rel, line, id, text)"""
    found, malformed, leftovers, spans = [], [], [], []
    line = lambda pos: s.count("\n", 0, pos) + 1
    for m in MARKER.finditer(s):
        text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", m.group(3))).split())
        spans.append((m.start(), m.end()))
        if not m.group(2).strip() or not text.startswith(PHRASE): malformed.append((rel, line(m.start()), m.group(2), text or "(empty)"))
        else: found.append((rel, line(m.start()), m.group(2), text))
    for m in BARE_ATTR.finditer(s):  # data-placeholder on an element the marker pattern did not take (no closing tag, no value)
        if not any(a <= m.start() < b for a, b in spans): malformed.append((rel, line(m.start()), "", "data-placeholder without a marked element"))
    for m in TEXT.finditer(s):  # the phrase outside a marked element
        if not any(a <= m.start() < b for a, b in spans): malformed.append((rel, line(m.start()), "", "phrase without data-placeholder"))
    body = re.sub(r"<(script|style)\b.*?</\1>", lambda m: "\n" * m[0].count("\n"), s, flags=re.S | re.I)
    for m in LEFTOVER.finditer(visible(body)):
        leftovers.append((rel, 0, m.group(0), "visible text: ..." + visible(body)[max(0, m.start() - 40):m.end() + 30].strip() + "..."))
    for m in SEEN_ATTRS.finditer(body):
        v = html.unescape(m.group(2))
        for k in LEFTOVER.finditer(v): leftovers.append((rel, line(m.start()), k.group(0), f'{m.group(1)}="{v[:80]}"'))
    return found, malformed, leftovers


def scan(root=SITE):
    found, malformed, leftovers = [], [], []
    for d, _, names in os.walk(str(root)):
        for n in sorted(names):
            path = os.path.join(d, n)
            rel = os.path.relpath(path, str(root)).replace("\\", "/")
            if os.path.splitext(n)[1].lower() not in TEXT_SUFFIXES: continue
            s = io.open(path, encoding="utf-8", errors="replace").read()
            if n.endswith(".html"):
                f, m, l = scan_page(rel, s)
                found += f; malformed += m; leftovers += l
            else:  # feeds, the manifest, scripts: the phrase may not appear unmarked there either
                for m in TEXT.finditer(s):
                    malformed.append((rel, s.count("\n", 0, m.start()) + 1, "", "phrase outside a page"))
    return found, malformed, leftovers


def self_test():
    """the detector finds one gap of each kind in a sample, and nothing in a clean one; a list of what it missed"""
    bad = {
        "open marker": '<p>Founded in <span class="tbs" data-placeholder="founding-year">To be supplied by OpenEXA: founding year</span>.</p>',
        "marker without the phrase": '<p><span data-placeholder="x">2019</span></p>',
        "marker without a name": '<p><span data-placeholder="">To be supplied by OpenEXA: x</span></p>',
        "phrase without marker": "<p>To be supplied by OpenEXA: the year.</p>",
        "lorem ipsum": "<p>Lorem ipsum dolor sit amet.</p>",
        "TODO": "<p>Revenue: TODO</p>",
        "TBD in alt": '<img alt="Portrait TBD" src="x.webp">',
        "unfilled template": "<h2>{{ title }}</h2>",
        "bracketed stand-in": "<p>[Insert customer quote]</p>",
    }
    missed = []
    for what, sample in bad.items():
        f, m, l = scan_page("self-test.html", "<main>" + sample + "</main>")
        if not (f or m or l): missed.append(what)
    clean = ('<main><h1>Agents decide. Code executes.</h1><p>Ten sessions, every one confirmed by the broker.</p>'
             '<textarea placeholder="Mandate, timeline, custody arrangements, questions…"></textarea>'
             '<script type="application/json" id="d">{"a": {"b": 1}}</script><p>A todo list is not a lifecycle.</p></main>')
    if any(scan_page("self-test.html", clean)): missed.append("a false alarm on the clean sample")
    return missed


def main():
    try: sys.stdout.reconfigure(errors="replace")  # page text may hold characters a Windows console cannot print
    except (AttributeError, ValueError): pass
    missed = self_test()
    if missed:
        print("check_placeholders: the detector is broken; its self-test missed:", ", ".join(missed))
        return 2
    found, malformed, leftovers = scan()
    if "--list" in sys.argv:
        for rel, line, pid, text in found:
            print(f"- [ ] `{pid}`: {text[len(PHRASE):].lstrip(' :')} ({rel}:{line})")
        return 0
    for rel, line, pid, text in found: print(f"  OPEN      {rel}:{line}  {pid}  {text}")
    for rel, line, pid, text in malformed: print(f"  MALFORMED {rel}:{line}  {pid or '-'}  {text}")
    for rel, line, what, where in leftovers: print(f"  LEFTOVER  {rel}{':' + str(line) if line else ''}  {what!r}  {where}")
    n = len(found) + len(malformed) + len(leftovers)
    print(f"check_placeholders: {len(found)} open, {len(malformed)} malformed, {len(leftovers)} leftover - {'OK' if not n else 'the site has gaps'}")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main())
