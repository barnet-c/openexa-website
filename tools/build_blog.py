"""Build blog/ from the old openexa.com blog (scraped by scrape_oldblog.py into oldblog/posts.json).

Curation: the research and AI posts are imported; the 2023-24 crypto/token-product posts (OXA, AUT, stable credit,
wallets, NFTs, a crypto margin account) are held back - they describe a business OpenEXA no longer runs. Held-back posts
are listed in EXCLUDE and redirected to the blog index; flip one out of EXCLUDE to publish it.
Posts keep their old openexa.com slugs at /blog/<slug>. Redirects and routes for Azure Static Web Apps are written to
site/staticwebapp.config.json (old site pages, held-back posts, trailing slashes, and the earlier /research/blog/ location).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import html as H, io, json, os, re, shutil
from datetime import datetime
from pathlib import Path
import ftfy

FILES = Path(str(DATA))
OLD = FILES / "oldblog"
ROOT = Path(str(SITE))
OUT = ROOT / "blog"
IMG = ROOT / "assets" / "img" / "blog"
SCHOLAR = "https://scholar.google.com/citations?user=P40aOHIAAAAJ"

EXCLUDE = {  # crypto / token-product era - held back pending review
    "now-is-the-right-time-for-cryptocurrency-to-emerge", "the-critical-role-of-liquidity",
    "what-is-an-oxa-stable-credit-tokens-and-how-you-can-mint-one", "6-great-cryptowallets-you-should-try-to-keep-your-crypto-assets-secure",
    "is-crypto-secure-what-factors-to-consider-if-yo-will-start-investing-in-crypto", "what-is-an-nft-non-fungible-tokens-and-how-you-can-buy-one",
    "the-new-cryptocurrency-x-crypto-debit-card-is-live-here-is-how-to-claim-yours-now", "the-new-cryptocurrency-x-2-0-app-is-now-available-to-download-on-ios-and-android",
    "5-new-interesting-ethereum-tokens-you-should-pay-attention-to-in-2024", "unidirectional-swaps-how-unidirectional-swaps-expand-the-circulation-of-tokens-in-the-market",
    "aut-and-oxa-are-better-than-bitcoin-and-ether-as-a-collateral-for-crypto-lending", "network-effect-the-economic-engine-of-oxa-that-will-drive-the-adoption-of-oxa",
    "how-chatgpt-can-change-the-future-of-cryptocurrency", "five-generative-ai-technologies-in-cryptocurrency", "history-of-ai-and-cryptocurrency",
}
COLLECTIONS = [  # key, label, lede
    ("ai", "AI & agents", "The first notes on AI copilots, guardrails and autonomous agents in financial markets — the thinking that became OpenEXA's agentic infrastructure."),
    ("markets", "Financial markets research", "Summaries of peer-reviewed research in computational finance: ETF price dynamics and drawdown risk, optimal execution, futures portfolios, sparse mean-reverting portfolios and multiscale signal processing."),
    ("economics", "Market structure & economics", "Summaries of academic research on how financial markets shape real decisions — information, contracting, credit, automation and the labour share."),
]
# Collection 04 "Municipal markets & commentary" (Barnet Sherman's columns and two OpenEXA posts) was removed on
# 2026-09-29: Barnet is now a customer rather than part of the team. Its posts redirect to the blog index.
REMOVED_COLLECTIONS = {"munis"}
def collection(p):
    a = p["author"]
    if a.startswith("Ajit"): return "ai"
    if a.startswith("Tim Leung"): return "markets"
    if a.startswith("Philip Bond"): return "economics"
    return "munis"
AUTHOR = {"OpenEXA": "OpenEXA"}  # display names are taken from the old byline otherwise

# rules that apply site-wide: no exchange or broker names
FIXES = [
    (r"the Nasdaq ETF \(QQQ\)", "the QQQ ETF"), (r"Nasdaq ETF \(QQQ\)", "QQQ ETF"),
    (r"from multiple market sources including NYSE Arca ETF market data, Cboe BZX ETF market data, NASDAQ ETF market data, Coinbase spot market data, CF Benchmarks'[^.,;]*",
     "from multiple exchange and market-data sources"),
    (r",? such as Interactive Brokers,?", ""),
]
FORBIDDEN = re.compile(r"NASDAQ|NYSE|TradeStation|Interactive Brokers|DTCC", re.I)

def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s):
    p.parent.mkdir(parents=True, exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
def esc(s): return H.escape(s, quote=True)
def plain(s): return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

# ---------------- load, repair, curate ----------------
posts = json.load(open(OLD / "posts.json", encoding="utf-8"))
kept, removed = [], []
for p in posts:
    if p["slug"] in EXCLUDE: continue
    for k in ("title", "description", "author", "body_html"):
        p[k] = ftfy.fix_text(p[k], unescape_html=False)
    p["dt"] = datetime.strptime(p["date"], "%B %d, %Y")
    p["col"] = collection(p)
    (removed if p["col"] in REMOVED_COLLECTIONS else kept).append(p)
assert len(kept) + len(removed) + len(EXCLUDE) == len(posts), (len(kept), len(removed), len(EXCLUDE), len(posts))
REMOVED = {p["slug"] for p in removed}
assert not any(re.search(r"Barnet|Sherman|Braintree", p["author"] + p["title"]) for p in kept)
for p in kept: p["stub_raw"] = len(plain(p["body_html"]).split()) < 40
SLUGS = {p["slug"]: p for p in kept}

def clean_body(p):
    b = p["body_html"]
    for pat, rep in FIXES: b = re.sub(pat, rep, b)
    b = re.sub(r'\s(id|class|style|data-[a-z-]+)="[^"]*"', "", b)
    b = re.sub(r"<(/?)h[1-2]>", r"<\1h2>", b)
    b = re.sub(r"<(/?)h[4-6]>", r"<\1h3>", b)
    b = re.sub(r"<br\s*/?>\s*</p>", "</p>", b)
    b = re.sub(r"<p>\s*(&nbsp;|\u00a0|<br\s*/?>)?\s*</p>", "", b)
    b = re.sub(r"<(/?)div>", "", b)
    b = re.sub(r'<a href="(https?://[^"]+)"[^>]*>', lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">', b)
    def internal(m):  # the old site's cross-links between posts
        s = m.group(1)
        if s in EXCLUDE or s not in SLUGS: return 'href="index.html"'
        q = SLUGS[s]
        return f'href="{q["source"]}" target="_blank" rel="noopener"' if q["stub_raw"] else f'href="{s}.html"'
    b = re.sub(r'href="/blog/([^"/#?]+)/?"', internal, b)
    assert not re.search(r'href="/', b), (p["slug"], re.findall(r'href="(/[^"]*)"', b))
    def img(m):
        src = m.group(1); alt = (re.search(r'alt="([^"]*)"', m.group(0)) or [None, ""])[1]
        name = src.rsplit("/", 1)[-1]
        shutil.copyfile(OLD / "img" / name, IMG / name) if (OLD / "img" / name).exists() else None
        return f'<img src="../assets/img/blog/{name}" alt="{esc(alt)}" loading="lazy" decoding="async">'
    b = re.sub(r'<img[^>]*src="(/graphics/[^"]+)"[^>]*>', img, b)
    b = re.sub(r"<figure>\s*(<img[^>]+>)\s*</figure>", r"<figure>\1</figure>", b)
    b = re.sub(r"<p>\s*(<img[^>]+>)\s*</p>", r"<figure>\1</figure>", b)
    b = re.sub(r"(?<!<figure>)(<img[^>]+>)(?!</figure>)", r"<figure>\1</figure>", b)
    return b.strip()

if IMG.exists(): shutil.rmtree(IMG)  # rebuilt from the scraped originals every time
IMG.mkdir(parents=True, exist_ok=True)
for p in kept:
    # body images referenced but not yet downloaded
    for src in re.findall(r'src="(/graphics/[^"]+)"', p["body_html"]):
        name = src.rsplit("/", 1)[-1]
        if not (OLD / "img" / name).exists():
            import urllib.request
            req = urllib.request.Request("https://www.openexa.com" + src, headers={"User-Agent": "Mozilla/5.0 openexa-archive/1.0"})
            (OLD / "img" / name).write_bytes(urllib.request.urlopen(req, timeout=40).read())
    p["body"] = clean_body(p)
    p["title"] = re.sub(r"\s+", " ", p["title"]).strip()
    for pat, rep in FIXES: p["title"] = re.sub(pat, rep, p["title"]); p["description"] = re.sub(pat, rep, p["description"])
    assert not FORBIDDEN.search(p["body"] + p["title"] + p["description"]), (p["slug"], FORBIDDEN.findall(p["body"]))
    if p.get("hero_file"):
        shutil.copyfile(OLD / "img" / p["hero_file"], IMG / p["hero_file"])
    words = len(plain(p["body"]).split())
    p["stub"] = words < 40  # link-only posts (e.g. a column hosted elsewhere) become outbound cards
    p["minutes"] = max(1, int(re.sub(r"\D", "", p["minutes"]) or round(words / 220)))
    ex = p["description"] or plain(p["body"])
    p["excerpt"] = (ex[:190].rsplit(" ", 1)[0] + "…") if len(ex) > 190 else ex
    if p["stub"]: p["excerpt"] = "Published on " + re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) + "."

by_col = {k: sorted([p for p in kept if p["col"] == k], key=lambda p: p["dt"], reverse=True) for k, _, _ in COLLECTIONS}
order = [p for k, _, _ in COLLECTIONS for p in by_col[k]]

# ---------------- shared chrome (from the live homepage) ----------------
index_html = read(ROOT / "index.html")
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?\n  </div>\n', index_html, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index_html, re.S).group(0)
ARROW = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'
OUTB = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M5 11L11 5M6 5h5v5"/></svg>'
PFX = "../"
def chrome():
    nav = NAV.replace('href="', f'href="{PFX}').replace(f'href="{PFX}#', 'href="#')
    foot = FOOTER.replace('href="', f'href="{PFX}').replace(f'href="{PFX}http', 'href="http').replace(f'href="{PFX}mailto', 'href="mailto')
    return nav, foot
def head(url, title, desc, kind="article", extra=""):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="{kind}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="https://www.openexa.com/assets/img/og.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(desc)}">
  <meta name="twitter:image" content="https://www.openexa.com/assets/img/og.png">
  <link rel="apple-touch-icon" href="{PFX}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{PFX}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{PFX}assets/img/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="{PFX}assets/css/site.css">
{extra}</head>'''
span = lambda a, b: f"{a}" if a == b else f"{a}–{b}"
fmt = lambda d: d.strftime("%b %-d, %Y") if os.name != "nt" else d.strftime("%b %#d, %Y")
LABEL = {k: l for k, l, _ in COLLECTIONS}
FIG = {"ai": "swarm", "markets": "horizon", "economics": "council", "munis": "ledger"}  # figure.js formations
BASE = "https://www.openexa.com/blog/"
def href(p): return p["source"] if p["stub"] else f'{p["slug"]}.html'

# the 2024 Gen-AI series (Ajit): an introduction and a three-part finance series that cross-link one another
SERIES = [("in-search-gen-ai-business-model", "Introduction", "The business model"),
          ("rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies", "Part 1", "Relative value"),
          ("tearsheet-how-to-use-tearsheet-in-the-face-of-volatile-crypto-and-bond-markets-as-a-means-of-capital-preservation-and-asset-appreciation", "Part 2", "Guardrails & tearsheets"),
          ("empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way", "Part 3", "AI agents")]
SERIES_NAME = "The Gen-AI series"
SERIES_POS = {s: i for i, (s, _, _) in enumerate(SERIES)}
assert all(s in SLUGS and not SLUGS[s]["stub"] for s, _, _ in SERIES)

# ---------------- index ----------------
nav, foot = chrome()
series_cards = []
for i, (s, part, short) in enumerate(SERIES):
    p = SLUGS[s]
    thumb = f'<div class="blog-thumb"><img src="{PFX}assets/img/blog/{p["hero_file"]}" alt="" loading="lazy" decoding="async"></div>' if p.get("hero_file") else ""
    series_cards.append(f'''          <li><a class="series-card" href="{s}.html">
            <span class="series-n">{i:02d}</span>{thumb}
            <div class="k"><span>{esc(part)} · {esc(short)}</span><span>{p["minutes"]} min</span></div>
            <h3>{esc(p["title"])}</h3>
            <span class="link-arrow">{fmt(p["dt"])} {ARROW}</span>
          </a></li>''')
series_minutes = sum(SLUGS[s]["minutes"] for s, _, _ in SERIES)
FEATURED = f'''    <section class="section is-paper-2 blog-series" id="series" data-blog-series>
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">★</span><span class="lab">Featured series</span><span class="aside">4 posts · {series_minutes} min · 2024</span></div>
        <div class="grid mb-3">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>{SERIES_NAME}: from business model to AI agents.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">Four posts by Ajit K Dubey, written in 2024. They set out where generative AI creates value, then work one financial use case end to end: relative value analysis, guardrails and tearsheets, and the AI copilots and autonomous agents they make possible. It's the line of thinking that became OpenEXA.</p><a class="link-arrow mt-3" href="{SERIES[0][0]}.html">Start with the introduction {ARROW}</a></div>
        </div>
        <ol class="series-rail" data-reveal style="--d:120ms">
{chr(10).join(series_cards)}
        </ol>
      </div>
    </section>
'''
chips = "".join(f'<a class="chip" href="#{k}" data-blog-filter="{k}">{esc(l)} <b>{len(by_col[k])}</b></a>' for k, l, _ in COLLECTIONS)
sections = []
for n, (k, label, lede) in enumerate(COLLECTIONS, 1):
    cards = []
    for p in by_col[k]:
        ext = p["stub"]
        thumb = f'<div class="blog-thumb"><img src="{PFX}assets/img/blog/{p["hero_file"]}" alt="" loading="lazy" decoding="async"></div>' if p.get("hero_file") else ""
        cards.append(f'''          <a class="blog-card" href="{esc(href(p))}"{' target="_blank" rel="noopener"' if ext else ''}>
            {thumb}<div class="blog-card-body"><div class="k"><span>{fmt(p["dt"])}</span><span>{esc(p["author"])}</span></div>
            <h3>{esc(p["title"])}</h3><p>{esc(p["excerpt"])}</p>
            <span class="link-arrow">{("Read on " + re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) + " " + OUTB) if ext else (str(p["minutes"]) + " min read " + ARROW)}</span></div>
          </a>''')
    more = f'<a class="link-arrow mt-3 scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">More on financial markets research {OUTB}</a>' if k == "markets" else ""
    sections.append(f'''    <section class="section{' is-paper-2' if n % 2 == 0 else ''} blog-collection" id="{k}" data-blog-collection="{k}">
      <div class="container">
        <div class="sec-head" data-reveal><span class="idx">{n:02d}</span><span class="lab">{esc(label)}</span><span class="aside">{len(by_col[k])} posts · {span(by_col[k][-1]["dt"].year, by_col[k][0]["dt"].year)}</span></div>
        <div class="grid mb-3">
          <div class="col-6"><h2 class="display-3" data-reveal>{esc(label)}.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal style="--d:80ms">{esc(lede)}</p>{more}</div>
        </div>
        <div class="blog-grid" data-reveal style="--d:120ms">
{chr(10).join(cards)}
        </div>
      </div>
    </section>''')
years = sorted(p["dt"].year for p in kept)
desc = f"The OpenEXA blog: {len(kept)} posts from {years[0]} to {years[-1]} on AI agents in finance, financial markets research and market structure."
page = head(BASE, "Blog — OpenEXA", desc, "website").replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n  <base href="/blog/">\n', 1) + f'''
<body data-nav="dark-start" class="blog-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain research-hero blog-hero">
      <div class="figure-stage research-figure" data-figure="library" data-spin="0.06" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="grid">
          <div class="col-7">
            <div class="eyebrow" data-reveal>The OpenEXA blog</div>
            <h1 class="display-1" data-reveal data-split style="--d:60ms">The blog.</h1>
            <p class="lede mt-3" data-reveal style="--d:120ms">Research summaries and the first notes on AI agents in finance — {len(kept)} posts from the people behind OpenEXA and the researchers they work with.</p>
            <div class="article-meta" data-reveal style="--d:180ms"><span>{len(kept)} posts</span><span>{years[0]}–{years[-1]}</span><span>{len(COLLECTIONS)} collections</span></div>
          </div>
        </div>
      </div>
    </section>

    <nav class="blog-chips-bar" aria-label="Collections">
      <div class="container"><div class="blog-chips"><a class="chip" href="index.html" data-blog-filter="all" aria-current="true">All <b>{len(kept)}</b></a>{chips}</div></div>
    </nav>

{FEATURED}
{chr(10).join(sections)}

    <section class="cta-band is-dark grain">
      <i class="mark globe" aria-hidden="true"></i>
      <div class="container">
        <div class="eyebrow" data-reveal>Research</div>
        <h2 class="display-2 mt-2" data-reveal data-split style="--d:60ms">The thinking behind the swarm.</h2>
        <p class="lede mt-3" data-reveal style="--d:120ms">Two research notes and an eight-part series on why high-stakes work should be run by thousands of narrow agents behind one deterministic boundary.</p>
        <div class="row" data-reveal style="--d:180ms">
          <a class="btn" href="{PFX}research.html">Read the research {ARROW}</a>
          <a class="btn btn--ghost" href="{PFX}access.html">Request access</a>
        </div>
      </div>
    </section>
  </main>

{foot}
  <script src="{PFX}assets/js/figure.js" defer></script>
  <script src="{PFX}assets/js/site.js" defer></script>
  <script src="{PFX}assets/js/blog.js" defer></script>
</body>
</html>
'''
if OUT.exists(): shutil.rmtree(OUT)
if (ROOT / "research" / "blog").exists(): shutil.rmtree(ROOT / "research" / "blog")  # the blog lived here until 2026-09-30
write(OUT / "index.html", page)

# ---------------- posts ----------------
for p in order:
    if p["stub"]: continue
    sib = [q for q in by_col[p["col"]] if not q["stub"]]
    i = sib.index(p); prev = sib[i - 1] if i else None; nxt = sib[i + 1] if i + 1 < len(sib) else None
    src_host = re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) if p["source"] else ""
    url = BASE + p["slug"] + ".html"
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"], "description": p["excerpt"], "url": url,
          "datePublished": p["dt"].strftime("%Y-%m-%d"), "author": {"@type": "Person" if p["author"] != "OpenEXA" else "Organization", "name": p["author"]},
          "publisher": {"@type": "Organization", "name": "OpenEXA", "url": "https://www.openexa.com/"}, "isPartOf": {"@type": "Blog", "name": "OpenEXA Blog", "url": BASE}}
    if p["source"]: ld["isBasedOn"] = p["source"]
    side_links = [f'<a class="link-arrow" href="index.html#{p["col"]}">{esc(LABEL[p["col"]])} {ARROW}</a>', f'<a class="link-arrow" href="index.html">All posts {ARROW}</a>']
    if p["source"]: side_links.insert(0, f'<a class="link-arrow" href="{esc(p["source"])}" target="_blank" rel="noopener">Original on {esc(src_host)} {OUTB}</a>')
    if p["col"] == "markets": side_links.insert(1, f'<a class="link-arrow" href="{SCHOLAR}" target="_blank" rel="noopener">More on financial markets research {OUTB}</a>')
    hero_img = f'<figure class="blog-hero-img"><img src="{PFX}assets/img/blog/{p["hero_file"]}" alt="" decoding="async"></figure>' if p.get("hero_file") else ""
    pager = "".join([
        f"<a class='pager-card prev' href='{prev['slug']}.html'><span class='k'>← Newer</span><h3>{esc(prev['title'])}</h3><p>{fmt(prev['dt'])}</p></a>" if prev else f"<a class='pager-card prev' href='index.html'><span class='k'>← The blog</span><h3>All {len(kept)} posts</h3><p>{esc(LABEL[p['col']])} and {len(COLLECTIONS) - 1} more collections.</p></a>",
        f"<a class='pager-card next' href='{nxt['slug']}.html'><span class='k'>Older →</span><h3>{esc(nxt['title'])}</h3><p>{fmt(nxt['dt'])}</p></a>" if nxt else f"<a class='pager-card next' href='{PFX}research.html'><span class='k'>Research →</span><h3>The thinking behind the swarm.</h3><p>Two research notes and an eight-part series.</p></a>",
    ])
    crumb, meta_extra, series_box = esc(LABEL[p["col"]]), "", ""
    if p["slug"] in SERIES_POS:  # series posts read in order, with the series listed alongside
        j = SERIES_POS[p["slug"]]; part = SERIES[j][1]
        crumb = f'<a href="index.html#series">{SERIES_NAME}</a>'
        meta_extra = f"<span>{esc(part)} · post {j + 1} of {len(SERIES)}</span>"
        items = "".join(f'<li{" aria-current=\"true\"" if s == p["slug"] else ""}><a href="{s}.html"><span>{i:02d}</span><span><b>{esc(pt)}</b>{esc(sh)}</span></a></li>' for i, (s, pt, sh) in enumerate(SERIES))
        series_box = f'<div class="series-box"><div class="eyebrow mb-2">{SERIES_NAME}</div><ol>{items}</ol></div>'
        sp = SLUGS[SERIES[j - 1][0]] if j else None; sn = SLUGS[SERIES[j + 1][0]] if j + 1 < len(SERIES) else None
        pager = "".join([
            f"<a class='pager-card prev' href='{sp['slug']}.html'><span class='k'>← {esc(SERIES[j - 1][1])}</span><h3>{esc(sp['title'])}</h3><p>{fmt(sp['dt'])}</p></a>" if sp else f"<a class='pager-card prev' href='index.html#series'><span class='k'>← {SERIES_NAME}</span><h3>Four posts, from business model to AI agents.</h3><p>2024 · {series_minutes} min in total</p></a>",
            f"<a class='pager-card next' href='{sn['slug']}.html'><span class='k'>{esc(SERIES[j + 1][1])} →</span><h3>{esc(sn['title'])}</h3><p>{fmt(sn['dt'])}</p></a>" if sn else f"<a class='pager-card next' href='{PFX}research.html'><span class='k'>What came next →</span><h3>The thinking behind the swarm.</h3><p>The research notes and eight-part series behind OpenEXA's agentic infrastructure.</p></a>",
        ])
        ld["isPartOf"] = {"@type": "CreativeWorkSeries", "name": f"{SERIES_NAME} - OpenEXA Blog", "url": BASE + "#series"}; ld["position"] = j
    note = f"Originally published on openexa.com, {fmt(p['dt'])}." + (f" A summary of work first published on {src_host}." if p["source"] else "")
    page = head(url, f'{p["title"]} — OpenEXA Blog', p["excerpt"], "article", f'  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n') + f'''
<body data-nav="dark-start" class="article-page blog-post">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero blog-post-hero">
      <div class="figure-stage article-figure" data-figure="{FIG[p["col"]]}" data-spin="0.08" aria-hidden="true"><canvas></canvas></div>
      <div class="container">
        <div class="eyebrow" data-reveal><a href="index.html">Blog</a> · {crumb}</div>
        <h1 class="display-2 article-title blog-title" data-reveal data-split style="--d:60ms">{esc(p["title"])}</h1>
        <div class="article-meta" data-reveal style="--d:140ms"><span>{esc(p["author"])}</span><span>{fmt(p["dt"])}</span><span>{p["minutes"]} min read</span>{meta_extra}</div>
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <aside class="col-3 article-side">
            <div class="sticky blog-side">
              {series_box}
              <div class="eyebrow mb-2">{esc(LABEL[p["col"]])}</div>
              {"".join(side_links)}
            </div>
          </aside>
          <article class="col-7 offset-5 article blog-article">
            {hero_img}
            {p["body"]}
            <div class="article-end"><span class="mark" aria-hidden="true"></span><span>{esc(note)}</span></div>
          </article>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container"><div class="pager">{pager}</div></div>
    </section>
  </main>

{foot}
  <script src="{PFX}assets/js/figure.js" defer></script>
  <script src="{PFX}assets/js/site.js" defer></script>
</body>
</html>
'''
    write(OUT / f'{p["slug"]}.html', page)

# ---------------- summary for the research index ----------------
json.dump({"total": len(kept), "years": [years[0], years[-1]],
           "series": {"name": SERIES_NAME, "first": SERIES[0][0], "count": len(SERIES), "minutes": series_minutes},
           "collections": [{"key": k, "label": l, "count": len(by_col[k]), "years": [by_col[k][-1]["dt"].year, by_col[k][0]["dt"].year], "lede": lede} for k, l, lede in COLLECTIONS]},
          open(FILES / "blog_summary.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)

# ---------------- routes for Azure Static Web Apps (site/staticwebapp.config.json) ----------------
# Azure serves /company as company.html and /blog as blog/index.html on its own. These rules only cover URLs that
# moved: the old openexa.com site (its pages and /blog/<slug>/ with a trailing slash), held-back and removed posts,
# and /research/blog/, where the blog lived before 2026-09-30. Rules are evaluated in order; the first match wins.
# Azure ignores a trailing slash when matching ("/x" and "/x/" are the same route, and listing both is rejected), so:
#   - each legacy path gets one rule;
#   - a kept post's /blog/<slug> rule also catches the old /blog/<slug>/ form; it redirects to /blog/<slug>.html (the
#     form every link on the site uses) rather than serving in place, because the page's relative links would resolve
#     against the wrong folder under a trailing slash.
def rd(route, to): return {"route": route, "redirect": to, "statusCode": 301}
OLD_PAGES = [("/strategies", "/lifecycles"), ("/trust-risk", "/trust"), ("/status", "/evidence"),
             ("/for-managers", "/access#managers"), ("/for-investors", "/access#investors"), ("/beta", "/access")]
routes = [rd(src, dst) for src, dst in OLD_PAGES]
# the blog's previous home (a link to it was shared on 2026-09-30); longest slugs first so no prefix shadows another
for p in sorted(kept, key=lambda q: -len(q["slug"])):
    routes.append(rd(f'/research/blog/{p["slug"]}*', p["source"] if p["stub"] else f'/blog/{p["slug"]}.html'))
routes.append(rd("/research/blog*", "/blog/"))
# old openexa.com blog URLs: held-back and removed posts go to the index; kept posts to their page
for p in posts:
    s = p["slug"]
    if s in EXCLUDE or s in REMOVED: routes.append(rd(f"/blog/{s}", "/blog/"))
    elif SLUGS[s]["stub"]: routes.append(rd(f"/blog/{s}", SLUGS[s]["source"]))
    else: routes.append(rd(f"/blog/{s}", f"/blog/{s}.html"))
_norm = [r["route"].rstrip("/").rstrip("*").lower() for r in routes]
assert len(set(_norm)) == len(_norm), "Azure rejects routes that differ only by a trailing slash"
CONFIG = {
    "routes": routes,
    "responseOverrides": {"404": {"rewrite": "/404.html", "statusCode": 404}},
    "mimeTypes": {".webmanifest": "application/manifest+json"},
}
ONE = lambda o: json.dumps(o, ensure_ascii=False, separators=(", ", ": "))  # one route per line: compact but diffable
io.open(ROOT / "staticwebapp.config.json", "w", encoding="utf-8", newline="\n").write("{\n  \"routes\": [\n" + ",\n".join("    " + ONE(r) for r in routes) + "\n  ],\n  \"responseOverrides\": " + ONE(CONFIG["responseOverrides"]) + ",\n  \"mimeTypes\": " + ONE(CONFIG["mimeTypes"]) + "\n}\n")
if (ROOT / "_redirects").exists(): (ROOT / "_redirects").unlink()  # Netlify-only; Azure would serve it as a public file
# the same old-URL map, for tools/verify_redirects.py
rules = []
for src, dst in OLD_PAGES: rules.append(f"{src}/  {dst}  301")
for p in posts:
    s = p["slug"]
    if s in EXCLUDE or s in REMOVED: rules.append(f"/blog/{s}/  /blog/  301")
    elif SLUGS[s]["stub"]: rules.append(f'/blog/{s}/  {SLUGS[s]["source"]}  301')
    else: rules.append(f"/blog/{s}/  /blog/{s}.html  301")
for p in kept: rules.append(f'/research/blog/{p["slug"]}.html  /blog/{p["slug"]}.html  301')
rules.append("/research/blog/  /blog/  301")
(FILES / "blog_redirects.txt").write_text("\n".join(rules) + "\n", encoding="utf-8")

# ---------------- image optimisation (in place; deterministic) ----------------
from PIL import Image
def optimise(path):
    if path.suffix.lower() not in (".webp", ".jpg", ".jpeg", ".png"): return
    im = Image.open(path); w, h = im.size
    if w <= 1800 and path.stat().st_size <= 160 * 1024: return
    if w > 1800: im = im.resize((1800, round(h * 1800 / w)), Image.LANCZOS)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fmt_ = {".webp": "WEBP", ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}[path.suffix.lower()]
    kw = {"WEBP": {"quality": 84, "method": 6}, "JPEG": {"quality": 86, "optimize": True, "progressive": True}, "PNG": {"optimize": True}}[fmt_]
    (im.convert("RGB") if fmt_ == "JPEG" else im).save(tmp, fmt_, **kw)
    if tmp.stat().st_size < path.stat().st_size: tmp.replace(path)
    else: tmp.unlink()
for f in IMG.iterdir(): optimise(f)

# ---------------- report ----------------
imgs = list(IMG.iterdir())
print(f"kept {len(kept)} ({sum(1 for p in kept if p['stub'])} outbound stubs), held back {len(EXCLUDE)}; pages {len(list(OUT.glob('*.html')))}; images {len(imgs)} / {sum(f.stat().st_size for f in imgs) // 1024} KB")
for k, l, _ in COLLECTIONS: print(f"  {l}: {len(by_col[k])}")
print("crypto mentions in kept posts:", {p["slug"][:40]: len(re.findall(r"crypto|bitcoin|token", plain(p["body"]), re.I)) for p in kept if re.search(r"crypto|bitcoin|token", plain(p["body"]), re.I)})
print("old product names (OXA/AUT) in kept posts:", [p["slug"][:40] for p in kept if re.search(r"\b(OXA|AUT)\b", plain(p["body"]))])
