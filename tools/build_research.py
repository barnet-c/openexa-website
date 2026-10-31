import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE, og_image
from meta import HOME, ORG, WEBSITE, FEED_LINKS, ROBOTS, ld, crumbs, atom
# -*- coding: utf-8 -*-
"""Build the OpenEXA research section from openexa-research-blogs.md:
   research.html (index) + research/NN-slug.html (ten articles), in the requested order 9 · 10 · 1 … 8.
   v2x (30 Oct 2026, group "research"): the index's plate beside the list shows the pointed or read note's figure with a
   caption from that note's own words (CAPTIONS; research.js, research.css); one number per row; every note gets its
   figure caption, links to the instruments it describes (RUN) and the series disclosure (moved, words verbatim, out of
   note 02's body). Bodies, titles and read times are unchanged."""
import html as H, io, json, math, os, re

MD = str(DATA / 'openexa-research-blogs.md')
ROOT = str(SITE)
OUT_DIR = os.path.join(ROOT, "research")
ORDER = [9, 10, 1, 2, 3, 4, 5, 6, 7, 8]
META = {  # post number → slug, figure, short label, one-line dek used on the index and cards
    9:  ("compounding-error", "horizon", "Research note", "Why long-horizon autonomous work must be decomposed into narrow agents behind a deterministic boundary."),
    10: ("post-training-and-audit", "weights", "Research note", "How a general model comes to follow one rulebook, and how a hash-chained ledger proves what it did."),
    1:  ("not-tasks-lifecycles", "lifecycle", "Series · 01", "Why we stopped building assistants and changed the unit of work to the lifecycle."),
    2:  ("five-thousand-small-agents", "swarm", "Series · 02", "Failure analysis, not a taste for scale: why thousands of narrow agents beat one large one."),
    3:  ("agents-decide-code-executes", "boundary", "Series · 03", "Eight layers, one boundary. The top four estimate; the bottom four are deterministic code."),
    4:  ("post-training-on-a-rulebook", "rulebook", "Series · 04", "Closing the gap between a model that knows finance and one that knows this lifecycle."),
    5:  ("the-execution-council", "council", "Series · 05", "Governance in milliseconds: what the council checks, three operating modes, and the kill switch."),
    6:  ("a-ledger-nobody-can-edit", "ledger", "Series · 06", "Append-only, hash-chained, replayable. Why a record an administrator can edit is only a claim."),
    7:  ("lifecycle-01-ten-sessions", "sessions", "Series · 07", "What ten live sessions on real capital showed, precisely what they did not, and where the cost goes."),
    8:  ("master-and-copy", "mastercopy", "Series · 08", "How a proven agent becomes a platform: prove one, master and copy, then open the rails."),
}
# your standing rule: no exchange or broker names anywhere on the site
FIXES = [
    ("Every fill in our ten live sessions was confirmed through TradeStation or Interactive Brokers before it entered the ledger.",
     "Every fill in our ten live sessions was confirmed by the executing broker before it entered the ledger."),
    ("The execution layer routed to NASDAQ and NYSE.", "The execution layer routed each action to the venue and counterparty the routing layer scored best."),
    # 2026-10-27: a unit slip (5% a year is ~$0.0002 a day per dollar - a ten-thousandth of a dollar, not of a cent) and
    # the site-wide rule "Trillions", never $22 trillion
    ("a dollar earns roughly two ten-thousandths of a cent per day", "a dollar earns roughly two ten-thousandths of a dollar per day"),
    ("roughly seventeen thousand ETFs holding about twenty-two trillion dollars.", "roughly seventeen thousand ETFs holding trillions of dollars."),
    # 2026-10-27: the regime split follows the per-session record (Days 03-06 and 08 premium; 01, 02, 07, 09 and 10
    # discount) that the homepage and the Proof page draw from (#oxa-sessions); the source note says six and four
    ("Six sessions were in premium regimes, four in discount regimes.", "Five sessions were in premium regimes, five in discount regimes."),
]
PUBLISHED = "2026-09-21"  # the research section went live with v10 (docs/site-history.md); the markdown has no dates

# v2x (30 Oct): every figure has a caption written from its own note (PAGES.md §6.3, FC-01..FC-10; owner approval is
# pending, so they are listed in REPORT.md). Per formation: the line that says what is drawn, the note's own words
# (each “quoted” passage must occur verbatim in that note: the build stops otherwise), and the hedge line.
NB = " "
CAPTIONS = {
    "horizon": ("Two runs of dependent steps, one of them gated.",
                "The red curve decays as p to the power n. The green run has a gate after every step. “An error at step k is caught at the verification gate after step k.”",
                "Illustrative"),
    "weights": ("One base model, rings of adapters, the record below.",
                "“One base model, many adapters.” Each record in the chain below holds “the hash of the previous record.”",
                "Illustrative"),
    "lifecycle": ("A lifecycle as one loop of gates, the last one lit.",
                  "A lifecycle “starts with a signal, moves through a series of decisions and approvals, executes against an external counterparty, and ends with a record”.",
                  "Illustrative"),
    "swarm": ("One large agent beside a lattice of small ones.",
              "“No single agent sees the whole trade. Each agent is scoped to exactly one gate in the lifecycle and does exactly one job.”",
              "Illustrative"),
    "boundary": ("Eight layers and one bright plane between them.",
                 "“The top four decide.” Under the plane: “The bottom four execute, and they are deterministic code.”",
                 "Illustrative"),
    "rulebook": ("A dense core, with documents drifting in.",
                 "“The most valuable data in any lifecycle is its exception history.”",
                 "Illustrative"),
    "council": ("Proposals arrive from above; rejected ones leave to the side.",
                "Approved proposals continue down. “If any check fails, the proposal exits at the gate and is logged.”",
                "Illustrative"),
    "ledger": ("Eight blocks in a chain, each linked to the one before.",
               "The newest block is lit. “Editing any entry breaks verification for every entry after it.”",
               "Illustrative"),
    # note 09: the colours are the record's (data-regimes, from #oxa-sessions); the floor line is not a scale
    "sessions": ("Ten sessions, one column each, in the order of the record.",
                 f"Green for a premium regime, ivory for discount. Each column fills to the khaki line, the 10{NB}bps floor, and every one rises past it; the scatter above the line does not show by how much, which is not published.",
                 "Illustrative · heights not to scale · regimes read from the record"),
    "mastercopy": ("One proven agent above, its copies below, on one control plane.",
                   "Phase two, on the roadmap. “A copy is a replication of that agent onto a new asset or strategy under the same control plane.”",
                   "Illustrative · roadmap"),
}
LIBRARY_CAPTION = ("Ten notes as ten leaves; the two research notes are lit.", "Illustrative")
# v2x: notes link to the instruments they describe (PAGES.md §6.4, NL-01..NL-10); targets are relative to research/
RUN = {
    "horizon": [("Watch the Council verify proposals in the swarm lab", "../index.html#lc01")],
    "weights": [("Edit a record and watch the chain fail", "../index.html#governance")],
    "lifecycle": [("The lifecycle test, trait by trait", "../lifecycles.html#test")],
    "swarm": [("See the swarm by role in the swarm lab", "../platform.html#swarm")],
    "boundary": [("Explore the eight layers and the boundary", "../platform.html#architecture")],
    "rulebook": [("Find the model layer in the architecture explorer", "../platform.html#architecture")],
    "council": [("Adjust the Council’s strictness and watch the approval rate change", "../index.html#lc01")],
    "ledger": [("Replay a ledger excerpt, then try to change the past", "../trust.html#ledger")],
    "sessions": [("See the ten sessions on the Proof page", "../evidence.html"), ("Run one simulated session on the desk", "../lifecycles.html#lc01")],
    "mastercopy": [("The six lifecycle classes, status by ring", "../lifecycles.html#classes")],
}
SERIES_DISCLOSURE_RE = r"^\*Disclosures: (.+)\*$"  # the series disclosure at the end of the markdown (Post 10): one block, every note
SERIES_LD = {"@type": "CreativeWorkSeries", "@id": HOME + "research.html#series", "name": "OpenEXA Research", "url": HOME + "research.html"}

def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)

# ---------------- parse ----------------
src = read(MD)
for a, b in FIXES:
    assert src.count(a) == 1, a[:60]
    src = src.replace(a, b)
for bad in ("NASDAQ", "NYSE", "TradeStation", "Interactive Brokers"):
    assert bad not in src, bad
chunks = re.split(r"\n## Post (\d+): ", src)[1:]
posts = {}
SERIES_DISCLOSURE = None
for num, body in zip(chunks[0::2], chunks[1::2]):
    lines = body.strip().split("\n")
    title = lines[0].strip()
    rest = "\n".join(lines[1:]).strip().rstrip("-").strip()
    dek = None
    m = re.match(r"^\*(.+?)\*\s*\n", rest, re.S)
    if m: dek = m.group(1).strip(); rest = rest[m.end():].strip()
    blocks = []
    for para in re.split(r"\n\s*\n", rest):
        para = para.strip()
        if not para: continue
        if para.startswith("### "): blocks.append(("h", para[4:].strip()))
        else: blocks.append(("p", " ".join(l.strip() for l in para.split("\n"))))
    # word count and read time as published since v10 (C-122: 6 · 7 · 3 min ×8, 37 in total): counted before the move below
    words = sum(len(t.split()) for k, t in blocks if k == "p") + (len(dek.split()) if dek else 0)
    # v2x: the markdown's last post (note 02) ends on a "---" rule and the series disclosure. Neither belongs to that
    # note's body: the rule goes, and the disclosure (words verbatim) is set once per note after the body (PAGES N-07)
    if len(blocks) >= 2 and blocks[-2] == ("p", "---") and re.match(SERIES_DISCLOSURE_RE, blocks[-1][1]):
        SERIES_DISCLOSURE = re.match(SERIES_DISCLOSURE_RE, blocks[-1][1]).group(1).strip()
        blocks = blocks[:-2]
    assert ("p", "---") not in blocks, f"Post {num}: a literal '---' paragraph in the body"
    posts[int(num)] = {"num": int(num), "title": title, "dek": dek, "blocks": blocks, "words": words, "minutes": max(3, round(words / 210))}
assert sorted(posts) == list(range(1, 11)), sorted(posts)
assert SERIES_DISCLOSURE, "the series disclosure (the markdown's closing '*Disclosures: …*') was not found"
for _fig, (_t, _d, _h) in CAPTIONS.items():  # every quoted passage of a caption is its note's own words
    _num = next(n for n, m in META.items() if m[1] == _fig)
    _text = " ".join(t for k, t in posts[_num]["blocks"])
    for _q in re.findall(r"“(.+?)”", _d):
        assert _q in _text, f"caption {_fig}: “{_q}” is not in Post {_num}"

def inline(t):
    t = H.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = t.replace(" -- ", " — ")
    return t
def slugify(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")
# v2x (SYSTEM.md §2): Instrument Serif draws U+002D wide ("Post – Training"); its U+2010 is tight. Visible serif text gets
# U+2010 between letters at source (titles in <title>, meta and JSON-LD keep ASCII)
def serif(t): return re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "‐", t)
def us(t):  # US spelling in site-written copy (VOICE §6.3); the blog collection ledes come from build_blog.py's summary
    return re.sub(r"\blabour\b", "labor", re.sub(r"\bbehaviour\b", "behavior", t))
def kind(post):  # one number per row (PAGES E-5): the reading-order number is the row's; the kind is said in words
    return "Research note" if post["label"] == "Research note" else f"Series, part {int(post['label'].split('·')[1])} of 8"
def title_html(t):
    """an authored title, words and capitals kept (E-4): the two research notes' 'A Research Note on …' is set as the
    title's second line, smaller, so no title runs past three lines"""
    m = re.match(r"^(.+?\.) (A Research Note on .+)$", t)
    return f'{inline(serif(m.group(1)))} <span class="title-sub">{inline(serif(m.group(2)))}</span>' if m else inline(serif(t))
def cap_html(fig, n, cls="figcap"):
    t, d, h = CAPTIONS[fig]
    return (f'<p class="{cls}"><span class="figcap-n">Fig.{NB}{n}</span><span class="figcap-t">{H.escape(t, quote=False)}</span>'
            f'<span class="figcap-d">{H.escape(d, quote=False)}</span><span class="figcap-h">{H.escape(h, quote=False)}</span></p>')

# ---------------- templates from the live homepage ----------------
index_html = read(os.path.join(ROOT, "index.html"))
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?\n  </div>\n', index_html, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index_html, re.S).group(0)
# the Lifecycle 01 sessions: ONE record (#oxa-sessions, on the home and Proof pages) that the chart and every session count
# are drawn from. The 'sessions' figure (note 09) reads each column's NAV regime from it: data-regimes on its stage, one
# letter per session (p = premium, d = discount), so the note carries no second copy of the record. Its ten columns are
# drawn for ten sessions: a record with another count needs that figure and the note looked at, so the build stops.
SESSIONS = json.loads(re.search(r'<script type="application/json" id="oxa-sessions">(.*?)</script>', index_html, re.S).group(1))["sessions"]
REGIMES = "".join({"prem": "p", "disc": "d"}.get(str(x.get("regime", "")).strip().lower()[:4], "?") for x in SESSIONS)
assert len(REGIMES) == 10 and set(REGIMES) <= {"p", "d"}, f"#oxa-sessions: note 09's figure draws ten sessions, each premium or discount; the record gives {REGIMES!r}"
def stage_data(fig): return f' data-regimes="{REGIMES}"' if fig == "sessions" else ""
HEAD_LINKS = '''  <link rel="apple-touch-icon" href="{p}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{p}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{p}assets/img/favicon.svg">
  <link rel="preload" href="{p}assets/fonts/instrument-serif-400-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{p}assets/fonts/inter-var-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{p}assets/css/site.css">
  <link rel="stylesheet" href="{p}assets/css/research.css">'''
ARROW = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'
OUTB = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 11L11 5M6 5h5v5"/></svg>'
SCHOLAR = "https://scholar.google.com/citations?user=P40aOHIAAAAJ"
BLOG = json.load(open(os.path.join(str(DATA), "blog_summary.json"), encoding="utf-8"))  # written by build_blog.py

def chrome(prefix, current):
    nav = NAV.replace('href="', f'href="{prefix}').replace(f'href="{prefix}#', 'href="#')
    nav = nav.replace(f'<a href="{prefix}research.html">Research</a>', f'<a href="{prefix}research.html" aria-current="page">Research</a>') if current == "research" else nav
    foot = FOOTER.replace('href="', f'href="{prefix}').replace(f'href="{prefix}http', 'href="http').replace(f'href="{prefix}mailto', 'href="mailto')
    return nav, foot

def og(prefix, url, title, desc):
    return f'''  <meta name="description" content="{H.escape(desc, quote=True)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{H.escape(title, quote=True)}">
  <meta property="og:description" content="{H.escape(desc, quote=True)}">
  <meta property="og:image" content="{og_image(url)}">
  <meta property="og:image:alt" content="{H.escape(title, quote=True)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{H.escape(title, quote=True)}">
  <meta name="twitter:description" content="{H.escape(desc, quote=True)}">
  <meta name="twitter:image" content="{og_image(url)}">
  {ROBOTS}
  {FEED_LINKS[0]}
  {FEED_LINKS[1]}
{HEAD_LINKS.format(p=prefix)}'''

# ---------------- articles ----------------
ordered = [posts[n] for n in ORDER]
for i, post in enumerate(ordered):
    slug, fig, label, dek_short = META[post["num"]]
    post.update({"slug": slug, "fig": fig, "label": label, "short": dek_short, "order": i + 1, "file": f"research/{i + 1:02d}-{slug}.html"})

def pager_card(p, k, cls=""):
    return (f"<a class='pager-card{cls}' href='{os.path.basename(p['file'])}'><span class='k'>{k}</span>"
            f"<h3>{inline(serif(p['title']))}</h3><p>{inline(p['short'])}</p></a>")

for i, post in enumerate(ordered):
    prev = ordered[i - 1] if i else None
    nxt = ordered[i + 1] if i + 1 < len(ordered) else None
    nav, foot = chrome("../", "research")
    heads = [(slugify(t), t) for k, t in post["blocks"] if k == "h"]
    toc = "".join(f'<li><a href="#{a}">{inline(t)}</a></li>' for a, t in heads)
    body = []
    first_p = True
    for k, t in post["blocks"]:
        if k == "h": body.append(f'<h2 id="{slugify(t)}">{inline(serif(t))}</h2>')
        else:
            body.append(f'<p{" class=\"lead\"" if first_p else ""}>{inline(t)}</p>'); first_p = False
    dek = post["dek"] or post["short"]
    title = post["title"]
    url = f"https://www.openexa.com/{post['file']}"
    n = f"{post['order']:02d}"
    run = "".join(f'<li><a class="link-arrow" href="{href}">{H.escape(text, quote=False)}{NB}{ARROW}</a></li>' for text, href in RUN[post["fig"]])
    long_title = len(re.sub(r" A Research Note on .+$", "", title)) > 52
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{H.escape(title)} — OpenEXA Research</title>
{og("../", url, title + " — OpenEXA Research", dek)}
  {ld({"@type": "TechArticle", "@id": url + "#article", "headline": title, "description": dek, "url": url, "mainEntityOfPage": url,
        "datePublished": PUBLISHED, "inLanguage": "en", "image": [og_image(url)], "author": ORG, "publisher": ORG,
        "isPartOf": SERIES_LD, "position": post["order"], "wordCount": post["words"], "timeRequired": f"PT{post['minutes']}M"},
       crumbs(("Research", HOME + "research.html"), (title, url)))}
</head>
<body data-page="note" data-nav="dark-start" class="article-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero">
      <div class="figure-stage article-figure" data-figure="{post['fig']}"{stage_data(post['fig'])} data-spin="0.10" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="article-hero-grid">
          <div>
            <div class="eyebrow" data-reveal>Research · Note {n} of {len(ordered):02d} · {H.escape(kind(post))}</div>
            <h1 class="display-1 article-title{' article-title--long' if long_title else ''}" data-reveal data-split style="--d:60ms">{title_html(title)}</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">{inline(dek)}</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>Founder’s notes</span><span>{post['minutes']}{NB}min read</span></div>
          </div>
          {cap_html(post['fig'], n, "figcap article-figcap")}
        </div>
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <nav class="col-3 article-side" aria-label="In this note">
            <div class="sticky">
              <div class="eyebrow mb-2">In this note</div>
              <ol class="toc" data-toc>{toc}</ol>
              <div class="article-share mt-3"><a class="link-arrow" href="../research.html">All research {ARROW}</a></div>
            </div>
          </nav>
          <article class="col-7 offset-5 article">
            {"".join(body)}
            <div class="article-end"><span class="mark" aria-hidden="true"></span><span>OpenEXA Research · Founder’s notes · {n} / {len(ordered):02d}</span></div>
            <div class="note-run"><p class="note-k">See it run</p><ul>{run}</ul></div>
            <div class="note-disc"><p class="note-k">Series disclosure</p><p>{H.escape(SERIES_DISCLOSURE, quote=False)}</p><p><a href="#disclosures">See the disclosures.</a></p></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container">
        <div class="pager">
          {pager_card(prev, f"← Previous · {prev['order']:02d}") if prev else "<a class='pager-card' href='../research.html'><span class='k'>← Research</span><h3>All ten notes</h3><p>The research behind swarm-based agentic lifecycles, in reading order.</p></a>"}
          {pager_card(nxt, f"Next · {nxt['order']:02d} →", " next") if nxt else "<a class='pager-card next' href='../access.html'><span class='k'>Next →</span><h3>Bring us a lifecycle.</h3><p>For institutions running high-value lifecycles and partners building on agentic infrastructure.</p></a>"}
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="../assets/js/figure.js" defer></script>
  <script src="../assets/js/site.js" defer></script>
  <script src="../assets/js/research.js" defer></script>
</body>
</html>
'''
    write(os.path.join(ROOT, post["file"].replace("/", os.sep)), page)
    print("wrote", post["file"], f"({post['minutes']} min)")

# ---------------- index ----------------
nav, foot = chrome("", "research")
rows = []
for post in ordered:
    t, d, h = CAPTIONS[post["fig"]]
    cap = " ".join(f'data-cap-{k}="{H.escape(v, quote=True)}"' for k, v in (("n", f"Fig.{NB}{post['order']:02d}"), ("t", t), ("d", d), ("h", h)))
    rows.append(f'''          <li class="post" data-figure-target="{post['fig']}" data-figure-stage="research-figure" {cap}>
            <a href="{post['file']}">
              <span class="post-n">{post['order']:02d}</span>
              <div class="post-main">
                <div class="post-kind">{H.escape(kind(post))}</div>
                <h3>{title_html(post['title'])}</h3>
                <p>{inline(post['short'])}</p>
              </div>
              <div class="post-meta"><span>{post['minutes']}{NB}min</span>{ARROW}</div>
            </a>
          </li>''')
notes = [p for p in ordered if p["label"] == "Research note"]
url = "https://www.openexa.com/research.html"
desc = "Ten notes on the research behind swarm-based agentic lifecycles: compounding error and decomposition, post-training a model to a rulebook, the execution council, the hash-chained ledger, and ten sessions on real capital."
index_page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Research — OpenEXA · The thinking behind agentic lifecycles</title>
{og("", url, "Research — OpenEXA", desc).replace('content="article"', 'content="website"')}
  {ld({"@type": "CollectionPage", "@id": url + "#webpage", "url": url, "name": "Research — OpenEXA", "description": desc,
       "isPartOf": WEBSITE, "primaryImageOfPage": og_image(url), "inLanguage": "en",
       "mainEntity": {"@type": "ItemList", "itemListElement": [
           {"@type": "ListItem", "position": p["order"], "url": HOME + p["file"], "name": p["title"]} for p in ordered]}},
      crumbs(("Research", url)), id="ld-research")}
</head>
<body data-page="research" data-nav="dark-start" class="research-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain research-hero">
      <div class="figure-stage research-figure" id="research-library" data-figure="library" data-spin="0.08" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="grid">
          <div class="col-7">
            <div class="eyebrow" data-reveal>Research · Founder’s notes</div>
            <h1 class="display-1" data-reveal data-split style="--d:60ms">The thinking behind the swarm.</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">Ten notes on why high-stakes work should be run by thousands of narrow agents behind one deterministic boundary, from the mathematics of compounding error to what ten sessions on real capital taught us.</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>{len(ordered)} notes</span><span>{sum(p['minutes'] for p in ordered)}{NB}min in total</span><span>Two research notes · an eight-part series</span></div>
          </div>
        </div>
        <p class="figcap rs-herocap"><span class="figcap-t">{LIBRARY_CAPTION[0]}</span><span class="figcap-h">{LIBRARY_CAPTION[1]}</span></p>
      </div>
    </section>

    <!-- v2x: the shelf. The ten notes, and beside them (pinned below them on phones) one plate that shows the figure of
         the note pointed at, focused or, on touch screens, read: research.js. Without JavaScript the plate is not drawn
         and the list takes the full width (research.css, @media (scripting: none)). -->
    <div class="rs-shelf">
      <section class="section" id="notes">
        <div class="container">
          <div class="rs-col">
            <div class="sec-head" data-reveal role="heading" aria-level="2"><span class="idx">01</span><span class="lab">Research notes</span><span class="aside">Start here · the argument from first principles</span></div>
            <ol class="posts-list" data-reveal>
{chr(10).join(rows[:2])}
            </ol>
          </div>
        </div>
      </section>

      <section class="section is-paper-2" id="series">
        <div class="container">
          <div class="rs-col">
            <div class="sec-head" data-reveal><span class="idx">02</span><span class="lab">The series</span><span class="aside">Eight notes · the system, gate by gate</span></div>
            <div class="rs-intro">
              <h2 class="display-2" data-reveal data-split>From the unit of work to the open platform.</h2>
              <p class="body-lg" data-reveal style="--d:80ms">Read in order, the series goes from the lifecycle test to master and copy.</p>
            </div>
            <ol class="posts-list" data-reveal start="3">
{chr(10).join(rows[2:])}
            </ol>
          </div>
        </div>
      </section>

      <div class="rs-rail" aria-hidden="true">
        <div class="container rs-rail-in">
          <figure class="rs-plate">
            <div class="rs-stage is-dark grain"><div class="figure-stage" id="research-figure" data-figure="{ordered[0]['fig']}" data-spin="0.07" data-rest="5"><canvas></canvas></div></div>
            <figcaption class="rs-caption">
              <p class="rs-hint"><span class="rs-hint-p">Point at a note and the figure becomes its idea.</span><span class="rs-hint-t">Scroll the list and the figure follows the note you are on.</span></p>
              {cap_html(ordered[0]['fig'], '01', 'figcap rs-cap')}
            </figcaption>
          </figure>
        </div>
      </div>
    </div>

    <section class="section" id="blog">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">03</span><span class="lab">The blog</span><span class="aside">{BLOG['total']} posts · {BLOG['years'][0]}–{BLOG['years'][1]}</span></div>
        <div class="grid t-2 mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>Three collections, from market structure to AI agents.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">Research summaries, market-structure economics and the first notes on AI agents in finance, from the people behind OpenEXA and the researchers they work with.</p><a class="link-arrow mt-3 scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">More on financial markets research {OUTB}</a></div>
        </div>
        <div class="card-grid card-grid--{len(BLOG['collections'])}" data-reveal style="--d:120ms">
{chr(10).join(f'          <a class="card research-card" href="blog/index.html#{c["key"]}"><div class="n"><span>{c["count"]} posts</span><span>{c["years"][0] if c["years"][0] == c["years"][1] else str(c["years"][0]) + "–" + str(c["years"][1])}</span></div><h3 class="h4">{H.escape(c["label"])}</h3><p>{H.escape(us(c["lede"]))}</p><span class="link-arrow mt-3">Browse the collection{NB}{ARROW}</span></a>' for c in BLOG['collections'])}
        </div>
        <div class="mt-4 row-links" data-reveal><a class="link-arrow" href="blog/index.html#series">Start with {BLOG['series']['name']}: from business model to AI agents {ARROW}</a><a class="link-arrow" href="blog/index.html">All {BLOG['total']} posts {ARROW}</a></div>
      </div>
    </section>

    <section class="section is-paper-2" id="principles">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">04</span><span class="lab">Four constants</span><span class="aside">Four things that never change</span></div>
        <div class="grid t-2">
          <div class="col-5"><h2 class="display-2" data-reveal data-split>The research contribution is four constants.</h2></div>
          <div class="col-6 offset-7">
            <ol class="num-list" data-reveal style="--d:80ms">
              <li><h3>Agents decide. Code executes.</h3><p>The top four layers estimate and reason; the bottom four are deterministic. The boundary between them is a typed schema.</p></li>
              <li><h3>No single agent sees the whole job.</h3><p>Each agent is scoped to one gate and does one thing. Its failure is local and its output is a proposal until something downstream permits it.</p></li>
              <li><h3>Nothing an agent believes can move what it is not permitted to.</h3><p>Capabilities are held per agent and per tool, enforced by the runtime rather than by the model’s good behavior.</p></li>
              <li><h3>Anything that settles is written to a ledger nobody can edit.</h3><p>Append-only, hash-chained, replayable{NB}— and written only after an independent counterparty confirms.</p></li>
            </ol>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-band is-dark grain">
      <i class="mark globe" aria-hidden="true"></i>
      <div class="container">
        <div class="eyebrow" data-reveal>See it run</div>
        <h2 class="display-2 mt-2" data-reveal data-split style="--d:60ms">Three of these ideas run in your browser.</h2>
        <p class="lede mt-3" data-reveal style="--d:120ms">Tighten the Council in the swarm lab. Edit a record and watch the chain break. Run one simulated session of Lifecycle{NB}01.</p>
        <div class="row" data-reveal style="--d:180ms">
          <a class="btn" href="index.html#lc01">Open the swarm lab {ARROW}</a>
          <a class="btn btn--ghost" href="index.html#governance">Break the chain</a>
          <a class="btn btn--ghost" href="lifecycles.html#lc01">Run the desk</a>
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="assets/js/figure.js" defer></script>
  <script src="assets/js/site.js" defer></script>
  <script src="assets/js/research.js" defer></script>
</body>
</html>
'''
write(os.path.join(ROOT, "research.html"), index_page)
print("wrote research.html")
atom(os.path.join(OUT_DIR, "feed.xml"), "OpenEXA Research", "Research notes and the series behind OpenEXA's agentic infrastructure.",
     url, [{"url": HOME + p["file"], "title": p["title"], "published": PUBLISHED, "updated": PUBLISHED, "author": "OpenEXA",
            "summary": p["short"]} for p in ordered])
print("wrote research/feed.xml")

# homepage teaser cards (three featured) → printed for the caller to insert
featured = [ordered[0], ordered[1], ordered[2]]
cards = "\n".join(f'''          <a class="card research-card" href="{p['file']}" data-figure-target="{p['fig']}"><div class="n"><span>{p['order']:02d}</span><span>{H.escape(p['label'])}</span></div><h3 class="h4">{inline(p['title'])}</h3><p>{inline(p['short'])}</p><span class="link-arrow mt-3">{p['minutes']} min read {ARROW}</span></a>''' for p in featured)
write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_cards.html"), cards)
print("featured cards written")
