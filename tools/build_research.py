import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
# -*- coding: utf-8 -*-
"""Build the OpenEXA research section from openexa-research-blogs.md:
   research.html (index) + research/NN-slug.html (ten articles), in the requested order 9 · 10 · 1 … 8."""
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
]

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
    words = sum(len(t.split()) for k, t in blocks if k == "p") + (len(dek.split()) if dek else 0)
    posts[int(num)] = {"num": int(num), "title": title, "dek": dek, "blocks": blocks, "minutes": max(3, round(words / 210))}
assert sorted(posts) == list(range(1, 11)), sorted(posts)

def inline(t):
    t = H.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = t.replace(" -- ", " — ")
    return t
def slugify(t): return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")

# ---------------- templates from the live homepage ----------------
index_html = read(os.path.join(ROOT, "index.html"))
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?\n  </div>\n', index_html, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index_html, re.S).group(0)
HEAD_LINKS = '''  <link rel="apple-touch-icon" href="{p}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{p}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{p}assets/img/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{p}assets/css/site.css">'''
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
  <meta property="og:image" content="https://www.openexa.com/assets/img/og.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{H.escape(title, quote=True)}">
  <meta name="twitter:description" content="{H.escape(desc, quote=True)}">
  <meta name="twitter:image" content="https://www.openexa.com/assets/img/og.png">
{HEAD_LINKS.format(p=prefix)}'''

# ---------------- articles ----------------
ordered = [posts[n] for n in ORDER]
for i, post in enumerate(ordered):
    slug, fig, label, dek_short = META[post["num"]]
    post.update({"slug": slug, "fig": fig, "label": label, "short": dek_short, "order": i + 1, "file": f"research/{i + 1:02d}-{slug}.html"})

for i, post in enumerate(ordered):
    prev = ordered[i - 1] if i else None
    nxt = ordered[i + 1] if i + 1 < len(ordered) else None
    nav, foot = chrome("../", "research")
    heads = [(slugify(t), t) for k, t in post["blocks"] if k == "h"]
    toc = "".join(f'<li><a href="#{a}">{inline(t)}</a></li>' for a, t in heads)
    body = []
    first_p = True
    for k, t in post["blocks"]:
        if k == "h": body.append(f'<h2 id="{slugify(t)}">{inline(t)}</h2>')
        else:
            body.append(f'<p{" class=\"lead\"" if first_p else ""}>{inline(t)}</p>'); first_p = False
    dek = post["dek"] or post["short"]
    title = post["title"]
    url = f"https://www.openexa.com/{post['file']}"
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{H.escape(title)} — OpenEXA Research</title>
{og("../", url, title + " — OpenEXA Research", dek)}
  <script type="application/ld+json">{{"@context":"https://schema.org","@type":"TechArticle","headline":{json.dumps(title)},"description":{json.dumps(dek)},"url":"{url}","isPartOf":{{"@type":"Blog","name":"OpenEXA Research","url":"https://www.openexa.com/research.html"}},"publisher":{{"@type":"Organization","name":"OpenEXA","url":"https://www.openexa.com/"}},"author":{{"@type":"Organization","name":"OpenEXA"}},"wordCount":{post["minutes"] * 210}}}</script>
</head>
<body data-nav="dark-start" class="article-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero">
      <div class="figure-stage article-figure" data-figure="{post['fig']}" data-spin="0.10" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="article-hero-grid">
          <div>
            <div class="eyebrow" data-reveal>Research · {post['order']:02d} of {len(ordered):02d} · {H.escape(post['label'])}</div>
            <h1 class="display-1 article-title" data-reveal data-split style="--d:60ms">{inline(title)}</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">{inline(dek)}</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>Founder's notes</span><span>{post['minutes']} min read</span><span>Fig. {post['order']:02d} — {H.escape(post['fig'])}</span></div>
          </div>
        </div>
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <aside class="col-3 article-side">
            <div class="sticky">
              <div class="eyebrow mb-2">In this note</div>
              <ol class="toc" data-toc>{toc}</ol>
              <div class="article-share mt-3"><a class="link-arrow" href="../research.html">All research {ARROW}</a></div>
            </div>
          </aside>
          <article class="col-7 offset-5 article">
            {"".join(body)}
            <div class="article-end"><span class="mark" aria-hidden="true"></span><span>OpenEXA Research · Founder's notes · {post['order']:02d} / {len(ordered):02d}</span></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container">
        <div class="pager">
          {"<a class='pager-card' href='" + os.path.basename(prev['file']) + "'><span class='k'>← Previous · " + f"{prev['order']:02d}" + "</span><h3>" + inline(prev['title']) + "</h3><p>" + inline(prev['short']) + "</p></a>" if prev else "<a class='pager-card' href='../research.html'><span class='k'>← Research</span><h3>All ten notes</h3><p>The research behind swarm-based agentic lifecycles, in reading order.</p></a>"}
          {"<a class='pager-card next' href='" + os.path.basename(nxt['file']) + "'><span class='k'>Next · " + f"{nxt['order']:02d}" + " →</span><h3>" + inline(nxt['title']) + "</h3><p>" + inline(nxt['short']) + "</p></a>" if nxt else "<a class='pager-card next' href='../access.html'><span class='k'>Next →</span><h3>Bring us a lifecycle.</h3><p>For institutions running high-value lifecycles and partners building on agentic infrastructure.</p></a>"}
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="../assets/js/figure.js" defer></script>
  <script src="../assets/js/site.js" defer></script>
</body>
</html>
'''
    write(os.path.join(ROOT, post["file"].replace("/", os.sep)), page)
    print("wrote", post["file"], f"({post['minutes']} min)")

# ---------------- index ----------------
nav, foot = chrome("", "research")
rows = []
for post in ordered:
    rows.append(f'''          <li class="post" data-figure-target="{post['fig']}" data-figure-stage="research-figure">
            <a href="{post['file']}">
              <span class="post-n">{post['order']:02d}</span>
              <div class="post-main">
                <div class="post-kind">{H.escape(post['label'])}</div>
                <h3>{inline(post['title'])}</h3>
                <p>{inline(post['short'])}</p>
              </div>
              <div class="post-meta"><span>{post['minutes']} min</span><span class="post-fig">Fig. {post['order']:02d}</span>{ARROW}</div>
            </a>
          </li>''')
notes = [p for p in ordered if p["label"] == "Research note"]
url = "https://www.openexa.com/research.html"
desc = "Ten notes on the research behind swarm-based agentic lifecycles: compounding error and decomposition, post-training a model to a rulebook, the execution council, the hash-chained ledger, and ten sessions on real capital."
index_page = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research — OpenEXA · The thinking behind agentic lifecycles</title>
{og("", url, "Research — OpenEXA", desc).replace('content="article"', 'content="website"')}
</head>
<body data-nav="dark-start" class="research-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain research-hero">
      <div class="figure-stage research-figure" id="research-figure" data-figure="library" data-spin="0.08" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="grid">
          <div class="col-7">
            <div class="eyebrow" data-reveal>Research · Founder's notes</div>
            <h1 class="display-1" data-reveal data-split style="--d:60ms">The thinking behind the swarm.</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">Ten notes on why high-stakes work should be run by thousands of narrow agents behind one deterministic boundary — from the mathematics of compounding error to what ten sessions on real capital taught us. Point at a note and the figure becomes its idea.</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>{len(ordered)} notes</span><span>{sum(p['minutes'] for p in ordered)} min in total</span><span>Two research notes · an eight-part series</span></div>
          </div>
        </div>
      </div>
    </section>

    <section class="section" id="notes">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">01</span><span class="lab">Research notes</span><span class="aside">Start here · the argument from first principles</span></div>
        <ol class="posts-list" data-reveal>
{chr(10).join(rows[:2])}
        </ol>
      </div>
    </section>

    <section class="section is-paper-2" id="series">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">02</span><span class="lab">The series</span><span class="aside">Eight posts · the system, gate by gate</span></div>
        <div class="grid mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>From the unit of work to the open platform.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">Read in order, the eight posts walk the architecture from the lifecycle test to the master-and-copy model — each one describing the research idea behind a layer of the stack.</p></div>
        </div>
        <ol class="posts-list" data-reveal start="3">
{chr(10).join(rows[2:])}
        </ol>
      </div>
    </section>

    <section class="section" id="blog">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">03</span><span class="lab">The blog</span><span class="aside">{BLOG['total']} posts · {BLOG['years'][0]}–{BLOG['years'][1]}</span></div>
        <div class="grid mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>Before the swarm, the research.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">Research summaries, market-structure economics and the first notes on AI agents in finance, from the people behind OpenEXA and the researchers they work with.</p><a class="link-arrow mt-3 scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">More on financial markets research {OUTB}</a></div>
        </div>
        <div class="card-grid card-grid--{len(BLOG['collections'])}" data-reveal style="--d:120ms">
{chr(10).join(f'          <a class="card research-card" href="research/blog/index.html#{c["key"]}"><div class="n"><span>{c["count"]} posts</span><span>{c["years"][0] if c["years"][0] == c["years"][1] else str(c["years"][0]) + "–" + str(c["years"][1])}</span></div><h3 class="h4">{H.escape(c["label"])}</h3><p>{H.escape(c["lede"])}</p><span class="link-arrow mt-3">Browse {ARROW}</span></a>' for c in BLOG['collections'])}
        </div>
        <div class="mt-4 row-links" data-reveal><a class="link-arrow" href="research/blog/index.html#series">Start with {BLOG['series']['name']}: from business model to AI agents {ARROW}</a><a class="link-arrow" href="research/blog/index.html">All {BLOG['total']} posts {ARROW}</a></div>
      </div>
    </section>

    <section class="section is-paper-2" id="principles">
      <div class="container">
        <div class="grid">
          <div class="col-5"><div class="eyebrow mb-2" data-reveal>Four things that never change</div><h2 class="display-2" data-reveal data-split>The research contribution is four constants.</h2></div>
          <div class="col-6 offset-7">
            <ol class="num-list" data-reveal style="--d:80ms">
              <li><h3>Agents decide. Code executes.</h3><p>The top four layers estimate and reason; the bottom four are deterministic. The boundary between them is a typed schema.</p></li>
              <li><h3>No single agent sees the whole job.</h3><p>Each agent is scoped to one gate and does one thing. Its failure is local and its output is a proposal until something downstream permits it.</p></li>
              <li><h3>Nothing an agent believes can move what it is not permitted to.</h3><p>Capabilities are held per agent and per tool, enforced by the runtime rather than by the model's good behaviour.</p></li>
              <li><h3>Anything that settles is written to a ledger nobody can edit.</h3><p>Append-only, hash-chained, replayable — and written only after an independent counterparty confirms.</p></li>
            </ol>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-band is-dark grain">
      <i class="mark globe" aria-hidden="true"></i>
      <div class="container">
        <div class="eyebrow" data-reveal>See it run</div>
        <h2 class="display-2 mt-2" data-reveal data-split style="--d:60ms">The ideas, as working objects.</h2>
        <p class="lede mt-3" data-reveal style="--d:120ms">Tighten the council on the live swarm. Edit a record and watch the chain break. Run one simulated session of Lifecycle 01.</p>
        <div class="row" data-reveal style="--d:180ms">
          <a class="btn" href="index.html#lc01">The swarm, live {ARROW}</a>
          <a class="btn btn--ghost" href="index.html#governance">Break the chain</a>
          <a class="btn btn--ghost" href="lifecycles.html#lc01">Run the desk</a>
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="assets/js/figure.js" defer></script>
  <script src="assets/js/site.js" defer></script>
</body>
</html>
'''
write(os.path.join(ROOT, "research.html"), index_page)
print("wrote research.html")

# homepage teaser cards (three featured) → printed for the caller to insert
featured = [ordered[0], ordered[1], ordered[2]]
cards = "\n".join(f'''          <a class="card research-card" href="{p['file']}" data-figure-target="{p['fig']}"><div class="n"><span>{p['order']:02d}</span><span>{H.escape(p['label'])}</span></div><h3 class="h4">{inline(p['title'])}</h3><p>{inline(p['short'])}</p><span class="link-arrow mt-3">{p['minutes']} min read {ARROW}</span></a>''' for p in featured)
write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_cards.html"), cards)
print("featured cards written")
