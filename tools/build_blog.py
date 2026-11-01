"""Build blog/ from the old openexa.com blog (scraped by scrape_oldblog.py into oldblog/posts.json).

Curation: the research and AI posts are imported; the 2023-24 crypto/token-product posts (OXA, AUT, stable credit,
wallets, NFTs, a crypto margin account) are held back - they describe a business OpenEXA no longer runs. Held-back posts
are listed in EXCLUDE and redirected to the blog index; flip one out of EXCLUDE to publish it.
Posts keep their old openexa.com slugs at /blog/<slug>. Redirects and routes for Azure Static Web Apps are written to
site/staticwebapp.config.json (old site pages, held-back posts, trailing slashes, and the earlier /research/blog/ location).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE, og_image
from meta import HOME, ORG, FEED_LINKS, ROBOTS, ld, crumbs, atom
from blog_plates import PLATES, plate_svg, collection_svg, library_svg
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
    ("economics", "Market structure & economics", "Summaries of academic research on how financial markets shape real decisions — information, contracting, credit, automation and the labor share."),
]
# Collection 04 "Municipal markets & commentary" (Barnet Sherman's columns and two OpenEXA posts) was removed on
# 2026-09-29: Barnet is now a customer rather than part of the team. Its posts redirect to the blog index.
REMOVED_COLLECTIONS = {"munis"}
# short names for the phone bar's chapter readout (data-chapter-short; site.js uses them only where the label does not fit).
# Each must fit the readout line at 360 px (126 px), or the whole bar falls back to '§NN / 03'
SHORT = {"ai": "AI & agents", "markets": "Markets", "economics": "Economics"}
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
# descriptions broken in the old site's data (they feed the cards, meta descriptions and feeds), replaced with each
# post's own words: one cut off mid-word, one copied from another post, one that was just the book's title
DESC = {
    "buying-high-and-selling-low-stock-repurchases-and-persistent-asymmetric-information":
        "Analyzes a dynamic version of Myers and Majluf's classic model. Equilibria feature repurchases, even though all firms want to raise cash.",
    "the-real-effects-of-financial-markets":
        "An essential topic in financial economics is investigating whether financial markets exert an influence on the actual economy.",
    "employee-stock-options-exercise-timing-hedging-and-valuation":
        "Employee stock options (ESOs) are an integral component of compensation in the US. In fact, almost all S&P 500 companies grant options to their top executives.",
    # v2x (30 Oct, PAGES B-05 / E-9): the old CMS gave the Gen-AI series cards their own titles back as excerpts, a
    # pipe-joined headline and a superlative; one markets card lost the start of its sentence. Each now opens with its
    # post's own first sentence (asserted against the body below).
    "in-search-gen-ai-business-model":
        "Over the past year, generative AI's ability to create content has dominated headlines, showcasing its potential to instantly generate text, images, and videos.",
    "rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies":
        "In today's investment landscape, traditional methods of analyzing company fundamentals may overlook key drivers of value.",
    "tearsheet-how-to-use-tearsheet-in-the-face-of-volatile-crypto-and-bond-markets-as-a-means-of-capital-preservation-and-asset-appreciation":
        "In financial markets, there are two main variables: your strategy and the unpredictable nature of the market.",
    "empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way":
        "Creating a Copilot or AI agent for financial markets is a complex and challenging endeavor.",
    "modern-trends-in-financial-engineering":
        "This new book series, Modern Trends in Financial Engineering, publishes monographs on important contemporary topics in theory and practice of Financial Engineering.",
}
# v2x: the two hero images that are screenshots of the author's own 2024 work (the relative-value map; the create and
# redeem loop) stay in their articles as the first figure. Every other hero image (stock photos, a 3D render, a logo,
# clip-art) leaves the page: cards and post heroes are drawn as plates (blog_plates.py). The files stay in assets.
KEEP_HERO = {"rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies",
             "tearsheet-how-to-use-tearsheet-in-the-face-of-volatile-crypto-and-bond-markets-as-a-means-of-capital-preservation-and-asset-appreciation"}
ALT = json.load(open(DATA / "blog_alt.json", encoding="utf-8")) if (DATA / "blog_alt.json").exists() else {}  # body-image alt text, written by looking at each image
# The old site's stand-in hero for research summaries: clip-art (a cap, a book and stars) over a misspelled
# 'RESERCH IN FINANCE · BY OUR TEAM' (legacy content, as scraped). It is never published: those cards are drawn as
# plates instead (.blog-card--plate: the collection label over the collection's mark), and those posts open on their
# article hero with no image. Images inside article bodies are untouched.
PLACEHOLDER = {"blog-028-649e320f57bee709f474e657-research-0fc3c7b1.webp"}

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
        if alt == "__wf_reserved_inherit": alt = ""  # a Webflow placeholder, not a description: screen readers read it out
        name = src.rsplit("/", 1)[-1]
        alt = alt or ALT.get(name, "")
        shutil.copyfile(OLD / "img" / name, IMG / name) if (OLD / "img" / name).exists() else None
        return f'<img src="../assets/img/blog/{name}"{body_srcset(name)} alt="{esc(alt)}"{size(name)} loading="lazy" decoding="async">'
    b = re.sub(r'<img[^>]*src="(/graphics/[^"]+)"[^>]*>', img, b)
    b = re.sub(r"<figure>\s*(<img[^>]+>)\s*</figure>", r"<figure>\1</figure>", b)
    b = re.sub(r"<p>\s*(<img[^>]+>)\s*</p>", r"<figure>\1</figure>", b)
    b = re.sub(r"(?<!<figure>)(<img[^>]+>)(?!</figure>)", r"<figure>\1</figure>", b)
    levels = [int(n) for n in re.findall(r"<h([2-6])[\s>]", b)]
    if levels and min(levels) > 2:  # no h2 under the page's h1: shift the post's headings up, class keeps the old look
        k = min(levels) - 2
        assert not re.search(r"<h[3-6]\s", b), (p["slug"], "heading with attributes")
        b = re.sub(r"<h([3-6])>", lambda m: f'<h{int(m.group(1)) - k} class="h{m.group(1)}">', b)
        b = re.sub(r"</h([3-6])>", lambda m: f"</h{int(m.group(1)) - k}>", b)
    return b.strip()

def dims(name):
    """(width, height) of a blog image as optimise() will leave it (at most 1800 px wide), or None."""
    from PIL import Image
    if not (OLD / "img" / name).exists(): return None
    w, h = Image.open(OLD / "img" / name).size
    return (1800, round(h * 1800 / w)) if w > 1800 else (w, h)
def size(name):
    """width/height attributes for a blog image, so the page reserves its box."""
    d = dims(name)
    return f' width="{d[0]}" height="{d[1]}"' if d else ""
# v2x r1 (r1-mobile 15): an 800 px copy of every wide in-body figure (new names, written after optimise() below), so a
# phone and a 1x screen stop loading the 1800 px original into a ~330-603 px exhibit. The mat holds the image at most
# 39.2rem - 24px (603 px) wide from 961 px, 36rem - 24px (552 px) on tablets (r2: the notes' reading column); on phones it
# is the column less the gutters and the mat.
BODY_W = 800
BODY_SIZES = "(max-width: 660px) calc(100vw - 64px), (max-width: 960px) 552px, 603px"
BODY_COPIES = set()
def body_srcset(name):
    d = dims(name)
    if not d or d[0] <= BODY_W * 1.1: return ""
    BODY_COPIES.add(name)
    stem = name.rsplit(".", 1)[0]; src = "../assets/img/blog/"
    return f' srcset="{src}{stem}-{BODY_W}w.webp {BODY_W}w, {src}{name} {d[0]}w" sizes="{BODY_SIZES}"'
# card-size copies of each hero image for the blog cards' srcset: a card is ~440 px wide, a hero up to 1800
THUMB_W = (480, 800)
# one sizes value for the cards and the (smaller) series rail, so a post shown in both loads the same file once
CARD_SIZES = "(max-width: 640px) calc(100vw - 40px), (max-width: 1080px) calc(50vw - 40px), min(440px, 31vw)"
def card_widths(name):
    """Widths of the card-size copies made for a hero: none for transparent images (a lossy copy comes out larger than
    the original) or for images wider than the 16:9 card (object-fit: cover crops them, so they need full width)."""
    from PIL import Image
    d = dims(name)
    if not d: return []
    im = Image.open(OLD / "img" / name)
    if im.mode in ("RGBA", "LA", "P") or d[0] / d[1] > 16 / 9 * 1.02: return []
    return [t for t in THUMB_W if t < d[0]]
def thumb(name, sizes):
    d = dims(name); stem = name.rsplit(".", 1)[0]
    ws = card_widths(name)
    src = f"{PFX}assets/img/blog/"
    if not ws: return f'<img src="{src}{name}" alt=""{size(name)} loading="lazy" decoding="async">'
    srcset = ", ".join([f"{src}{stem}-{t}w.webp {t}w" for t in ws] + [f"{src}{name} {d[0]}w"])
    return f'<img src="{src}{stem}-{ws[-1]}w.webp" srcset="{srcset}" sizes="{sizes}" alt=""{size(name)} loading="lazy" decoding="async">'
# The plates (v2x, 30 Oct 2026; tools/blog_plates.py draws them). Every card and every post hero carries its post's own
# engraved plate instead of a stock photo, the CMS's 3D art or a WebGL formation borrowed from Research (EVOLVE, Blog):
# the plate draws what the post says in its own words, schematically. Market structure & economics keeps v2's mark
# (six inclined rings, one green), turned a few degrees from card to card so a row reads as one family (PG-R2-8).
# The old image files stay in assets/img/blog/ (the owner may want them back); only the markup stops using them.
def pos_in_col(p): return [q["slug"] for q in by_col[p["col"]]].index(p["slug"])
def turn(p): return (-8, -2, 4, 10)[pos_in_col(p) % 4]
def plate_label(p): return PLATES[p["slug"]][0] if p["col"] != "economics" and p["slug"] in PLATES else LABEL[p["col"]]
def plate(p, cls="blog-thumb"):
    """A card's plate: the plate's name (mono) over the drawing. aria-hidden: the card's h3 names the post."""
    return f'<div class="{cls} blog-plate" aria-hidden="true"><span class="bp-k">Plate · {esc(plate_label(p))}</span>{plate_svg(p["slug"], p["col"], turn(p))}</div>'
SERIF_HY = re.compile(r"(?<=[^\W\d_])-(?=[^\W\d_])")
# v2x lab (blog-editorial, 31 Oct): typography on the page, never words (VOICE §7; r1-art M8, r1-copy 31). The old CMS
# kept typewriter marks: straight quotes and apostrophes, a spaced hyphen for a dash, three dots. What the page shows
# is set with the real characters; titles in <title>, meta, feeds and JSON-LD keep the ASCII the CMS had.
OPENERS = set(" \t\n ([{‘“—–-/")
def smart(t, prev=" "):
    """one run of text: ’ ‘ “ ” by the character before (prev carries it across tags), a spaced hyphen as the house
    dash (no-break space before), ... as …"""
    t = re.sub(r" +-{1,2} +", " — ", t.replace("...", "…")).replace(" —", " —")
    out = []
    for i, ch in enumerate(t):
        before = out[-1] if out else prev
        after = t[i + 1] if i + 1 < len(t) else " "
        if ch == '"': ch = "“" if before in OPENERS else "”"
        elif ch == "'": ch = "’" if before.isalnum() or before in ".,;:!?”’)" else ("‘" if after.isalnum() else "’")
        out.append(ch)
    return "".join(out)
SKIP_TAGS = re.compile(r"<(code|pre|script|style)\b.*?</\1>", re.S)
def smart_html(h):
    """smart() over the text of an HTML fragment: tags, attributes and code untouched; the character before a run is
    the last one written before it, so a quote that closes after </a> still closes"""
    parts, prev = re.split(r"(<[^>]+>)", h), " "
    out, skip, head_, quote_ = [], 0, 0, 0
    for part in parts:
        if part.startswith("<"):
            if re.match(r"<(code|pre|script|style)\b", part): skip += 1
            elif re.match(r"</(code|pre|script|style)>", part): skip = max(0, skip - 1)
            # the article sets headings and blockquotes in Instrument Serif, whose U+002D reads 'Gen - AI'. In both the
            # ASCII hyphen stays (find-in-page matches a typed '-') inside span.hy, which takes the bearings in (site.css;
            # SYSTEM.md §3, r2: never U+2010, which the serif's file lacks, so it fell back to a system serif). site.js
            # does the same to h1-h3 at load; written here, they read right without JS too
            if re.match(r"<(h2|h3)\b", part): head_ += 1
            elif re.match(r"</(h2|h3)>", part): head_ = max(0, head_ - 1)
            if re.match(r"<blockquote\b", part): quote_ += 1
            elif re.match(r"</blockquote>", part): quote_ = max(0, quote_ - 1)
            if re.match(r"</?(p|li|h[1-6]|blockquote|figure|figcaption|br|div|td|th|ul|ol)\b", part): prev = " "  # a block starts afresh
            out.append(part); continue
        if not part or skip: out.append(part); continue
        # entities stay entities: decode for the decision, write back what the CMS wrote otherwise
        txt = H.unescape(part)
        s = smart(txt, prev)
        out.append(tight_hy(esc_text(s)) if head_ or quote_ else esc_text(s)); prev = s[-1] if s else prev
    return "".join(out)
def tight_hy(escaped):
    """a serif line: the ASCII hyphen between letters (still found by find-in-page), set tight (site.css .hy)"""
    return SERIF_HY.sub('<span class="hy">-</span>', escaped)
def esc_text(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def serif(s):
    """escaped text for a serif line: real quotes and dashes, and the hyphen between letters in span.hy (Instrument
    Serif draws U+002D as 'Domain – Specific'; SYSTEM.md §3, r2). Titles, meta, feeds and JSON-LD keep plain ASCII."""
    return tight_hy(esc(smart(s)))
def prose(s): return esc(smart(s))
def hang(h):
    """a paragraph that opens on a quote mark hangs it in the margin, so the text's left edge stays straight"""
    return re.sub(r'<p( class="[^"]*")?>([“‘])', r'<p\1><span class="hang">\2</span>', h)
def lead(h):
    """the post's lead (larger, with the notes' drop initial): its first paragraph, unless a heading or list comes
    first. Jury (blog): a label line is not a lead. A one-line bold subhead ('Regime-Switching Market') passes the lead
    to the paragraph after it; a short first paragraph ('Book Title: ...') means the post has none."""
    blocks = list(re.finditer(r"<(p|h2|h3|ul|ol)\b([^>]*)>(.*?)</\1>", h, re.S))[:2]
    for i, m in enumerate(blocks):
        if m.group(1) != "p" or m.group(2): return h
        inner = m.group(3).strip()
        if len(re.sub(r"<[^>]+>", " ", inner).split()) >= 15:
            return h[:m.start()] + '<p class="lead">' + h[m.start() + 3:]
        if i or not re.fullmatch(r"<strong>[^<]*</strong>", inner): return h
    return h
def said(p):
    """the post's own text, normalised for quoting: tags out, entities decoded, whitespace collapsed, no space before
    punctuation (the old CMS left 'Engineering , publishes')"""
    t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", p["body"])))
    return re.sub(r"\s+([,.;:)])", r"\1", t)

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
    p["description"] = DESC.get(p["slug"], p["description"])
    if p["slug"] in KEEP_HERO or p["slug"] in ("in-search-gen-ai-business-model", "empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way", "modern-trends-in-financial-engineering"):
        assert p["description"] in said(p), (p["slug"], "the card's excerpt must be the post's own sentence")
    p["title"] = re.sub(r"\s+", " ", p["title"]).strip()
    for pat, rep in FIXES: p["title"] = re.sub(pat, rep, p["title"]); p["description"] = re.sub(pat, rep, p["description"])
    assert not FORBIDDEN.search(p["body"] + p["title"] + p["description"]), (p["slug"], FORBIDDEN.findall(p["body"]))
    if p.get("hero_file") in PLACEHOLDER: p["hero_file"], p["plate"] = None, True
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
# decorative arrows: hidden from assistive technology (the link's words name it), as the chrome's (a11y r1 m1)
ARROW = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg>'
OUTB = '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M5 11L11 5M6 5h5v5"/></svg>'
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
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="{kind}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="{og_image(url)}">
  <meta property="og:image:alt" content="{esc(title)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(desc)}">
  <meta name="twitter:image" content="{og_image(url)}">
  {ROBOTS}
  {FEED_LINKS[0]}
  {FEED_LINKS[1]}
  <link rel="apple-touch-icon" href="{PFX}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{PFX}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{PFX}assets/img/favicon.svg">
  <link rel="preload" href="{PFX}assets/fonts/instrument-serif-400-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{PFX}assets/fonts/inter-var-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{PFX}assets/css/site.css">
  <link rel="stylesheet" href="{PFX}assets/css/blog.css">
{extra}</head>'''
span = lambda a, b: f"{a}" if a == b else f"{a}–{b}"
fmt = lambda d: d.strftime("%b %-d, %Y") if os.name != "nt" else d.strftime("%b %#d, %Y")
LABEL = {k: l for k, l, _ in COLLECTIONS}
FIG = {"ai": "swarm", "markets": "horizon", "economics": "council", "munis": "ledger"}  # figure.js formations
BASE = "https://www.openexa.com/blog/"
BLOG_LD = {"@type": "Blog", "@id": BASE + "#blog", "name": "OpenEXA Blog", "url": BASE}
# v2x: each byline lands on its person on Company (company.html gives everyone an anchor since 30 Oct)
PEOPLE_ID = {"Ajit K Dubey": "ajit-dubey", "Tim Leung": "tim-leung", "Philip Bond": "philip-bond"}
assert all(f'id="{i}"' in read(ROOT / "company.html") for i in PEOPLE_ID.values()), "company.html lost a person's anchor"
def person(byline):
    """schema.org author for a byline ("Tim Leung, Ph.D." -> a Person with the credential as honorificSuffix)."""
    if byline == "OpenEXA": return ORG
    m = re.match(r"^(.*?), *(Ph[.]D[.])$", byline)
    name = m.group(1) if m else byline
    who = {"@type": "Person", "name": name, "url": HOME + "company.html#" + PEOPLE_ID.get(name, "team")}
    if m: who["honorificSuffix"] = m.group(2)
    return who
def shown(byline):
    """the name a reader sees: one name per person (VOICE 5.9, r2-copy), the form Company uses ('Tim Leung, Ph.D.' ->
    'Dr. Tim Leung'). JSON-LD keeps the name and the credential apart (person()); the feed keeps the byline as published"""
    m = re.match(r"^(.*?), *Ph[.]D[.]$", byline)
    return f"Dr. {m.group(1)}" if m else byline
assert all(shown(a) in read(ROOT / "company.html") for a in ("Ajit K Dubey", "Tim Leung, Ph.D.", "Philip Bond, Ph.D.")), "a byline's name is not the one Company uses"
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
# v2x (30 Oct 2026): every post appears once. The Gen-AI series is AI & agents' own lead (it is four of the
# collection's five posts), drawn as a dated rail; v2 showed it as a featured band and then again as four cards of the
# AI grid. The chips stick only over the collections (a wrapper ends them before the closing band and the footer).
nav, foot = chrome()
def iso(p): return p["dt"].strftime("%Y-%m-%d")
def card(p):
    # v2x lab (blog-editorial): a collection is one author's (collection() assigns by author), so the byline is said
    # once, in the collection's head; the card keeps its dateline
    ext = p["stub"]
    host = re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) if ext else ""
    return f'''          <a class="blog-card" href="{esc(href(p))}"{' target="_blank" rel="noopener"' if ext else ''}>
            {plate(p)}<div class="blog-card-body"><div class="k"><time datetime="{iso(p)}">{fmt(p["dt"])}</time></div>
            <h3>{serif(p["title"])}</h3><p>{prose(p["excerpt"])}</p>
            <span class="link-arrow">{("Read on " + host + " " + OUTB) if ext else (str(p["minutes"]) + "&nbsp;min read " + ARROW)}</span></div>
          </a>'''
def row(p):
    """a post as a line of the register (Market structure & economics): dateline, title and abstract, read time"""
    ext = ' target="_blank" rel="noopener"' if p["stub"] else ""
    return f'''          <li><a class="blog-card blog-row" href="{esc(href(p))}"{ext}>
            <time class="br-date" datetime="{iso(p)}">{fmt(p["dt"])}</time>
            <div class="br-main"><h3>{serif(p["title"])}</h3><p>{prose(p["excerpt"])}</p></div>
            <span class="br-min">{p["minutes"]}&nbsp;min read {OUTB if p["stub"] else ARROW}</span>
          </a></li>'''
rail = []
for i, (s, part, short) in enumerate(SERIES):
    p = SLUGS[s]
    rail.append(f'''          <li><a class="series-card blog-card" href="{s}.html">
            <span class="sr-date"><time datetime="{iso(p)}">{fmt(p["dt"])}</time></span>
            <span class="series-n">{i:02d}</span>{plate(p)}
            <div class="k"><span>{esc(part)} · {esc(short)}</span></div>
            <h3>{serif(p["title"])}</h3>
            <span class="link-arrow">{p["minutes"]}&nbsp;min read {ARROW}</span>
          </a></li>''')
series_minutes = sum(SLUGS[s]["minutes"] for s, _, _ in SERIES)
# the index's plates carry the hedge the post heroes carry (r1-fidelity 6): beside the series and above the markets grid
PLATES_HEDGE = "Plates are schematic · no data is plotted"
in_series = {s for s, _, _ in SERIES}
SERIES_BLOCK = f'''        <div class="grid t-2 blog-series-head">
          <div class="col-6"><h2 class="display-2" data-reveal data-split>{serif(SERIES_NAME)}: <span class="sh-sub">from business&nbsp;model to AI agents.</span></h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal>Four posts by Ajit K Dubey, written in 2024. They set out where generative AI creates value, then work one financial use case end to end: relative value analysis, guardrails and tearsheets, and the AI copilots and autonomous agents they make possible. It’s the line of thinking that became OpenEXA.</p><a class="link-arrow mt-3" href="{SERIES[0][0]}.html">Start with the introduction {ARROW}</a></div>
        </div>
        <div class="blog-series" id="series" data-blog-series>
          <div class="series-k"><span><span aria-hidden="true">★</span> Featured series</span><span>4 posts · {series_minutes}&nbsp;min · 2024</span></div>
          <ol class="series-rail" role="list" aria-label="{SERIES_NAME}, in order" data-reveal>
{chr(10).join(rail)}
          </ol>
        </div>
'''
def chip(k, label, n):
    # phones show the short name; the rest of the name stays in the link for assistive technology (label in name)
    parts = {"markets": '<span class="chip-x">Financial </span>markets<span class="chip-x"> research </span>',
             "economics": '<span class="chip-x">Market structure &amp; </span>economics '}
    return f'<a class="chip" href="#{k}" data-blog-filter="{k}">{parts[k] if k in parts else esc(label) + " "}<b>{n}</b></a>'
chips = "".join(chip(k, l, len(by_col[k])) for k, l, _ in COLLECTIONS)
sections = []
for n, (k, label, lede) in enumerate(COLLECTIONS, 1):
    span_ = span(by_col[k][-1]["dt"].year, by_col[k][0]["dt"].year)
    authors = {p["author"] for p in by_col[k]}
    assert len(authors) == 1, (k, authors)  # collections are assigned by author: the head can carry the byline once
    shead = f'''        <div class="sec-head" data-reveal><span class="idx">{n:02d}</span><span class="lab">{esc(label)}</span><span class="aside"><span class="by">{esc(shown(authors.pop()))}</span> · {len(by_col[k])} posts · {span_}</span></div>
''' + (f'''        <figure class="blog-headplate"><div class="bh-art" aria-hidden="true">{collection_svg(k)}</div><figcaption><span class="pp-k">Plate · {esc(label)}</span><span class="pp-h">Schematic · no data is plotted</span></figcaption></figure>
''' if k in ("markets", "ai") else "")  # r3-art: the phone's one plate per collection carries the register's mark and hedge, as the cards do wider
    if k == "economics":
        # v2x lab (blog-editorial): eight cards carried one mark eight times (r1-art M6, r1-mobile 9). The collection
        # is set as a register, the way Research lists its notes, beside its plate, shown once.
        body = f'''        <div class="grid t-2 mb-3">
          <div class="col-6"><h2 class="display-3" data-reveal>{serif(label)}.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal>{prose(lede)}</p></div>
        </div>
        <div class="blog-econ">
          <ol class="blog-register" role="list" data-reveal>
{chr(10).join(row(p) for p in by_col[k])}
          </ol>
          <figure class="blog-econ-plate" aria-hidden="true">
            <div class="blog-econ-art">{collection_svg(k)}</div>
            <figcaption><span class="pp-k">Plate · {esc(label)}</span><span class="pp-h">The collection’s mark</span></figcaption>
          </figure>
        </div>
'''
    elif k == "ai":
        rest = [p for p in by_col[k] if p["slug"] not in in_series]
        body = SERIES_BLOCK + f'''        <div class="blog-also">
          <div class="blog-also-k"><span class="eyebrow">Also in {esc(label)}</span></div>
          <div class="blog-grid blog-grid--wide" data-reveal>
{chr(10).join(card(p) for p in rest)}
          </div>
        </div>
'''
    else:
        more = f'<a class="link-arrow mt-3 scholar-link" href="{SCHOLAR}" target="_blank" rel="noopener">The papers on Google Scholar {OUTB}</a>' if k == "markets" else ""
        body = f'''        <div class="grid t-2 mb-3">
          <div class="col-6"><h2 class="display-3" data-reveal>{serif(label)}.</h2></div>
          <div class="col-5 offset-7"><p class="body-lg" data-reveal>{prose(lede)}</p>{more}</div>
        </div>
        <p class="blog-legend"><span class="plates-hedge">{PLATES_HEDGE}</span></p>
        <div class="blog-grid" data-reveal>
{chr(10).join(card(p) for p in by_col[k])}
        </div>
'''
    sections.append(f'''    <section class="section{' is-paper-2' if n % 2 else ''} blog-collection" id="{k}" data-blog-collection="{k}" data-chapter-short="{esc(SHORT[k])}">
      <div class="container">
{shead}{body}      </div>
    </section>''')
years = sorted(p["dt"].year for p in kept)
# lab blog-moment: the hero's plate is the blog itself (blog_plates.library_svg): one leaf per post, filed by
# collection, the Gen-AI series in green; v2/v2x borrowed Research's WebGL library ("ten leaves, two lit"), which on
# this page drew the wrong library. The leaf counts come from the collections, so a new post adds a leaf.
assert sum(1 for p in by_col["ai"] if p["slug"] in in_series) == 4
LIBRARY = f'''<figure class="lib-plate">
          <div class="lib-stage">{library_svg((SHORT["markets"], SHORT["ai"], SHORT["economics"]), tuple(len(by_col[k]) for k in ("markets", "ai", "economics")), sum(1 for p in by_col["ai"] if p["slug"] in in_series))}</div>
          <figcaption><span class="pp-k">Plate · The library</span><p class="pp-q">Every post is a leaf, filed in its collection; the four green leaves are the Gen-AI series.</p><span class="pp-h">Schematic · no plate on this page plots data</span></figcaption>
        </figure>'''
desc = f"The OpenEXA blog: {len(kept)} posts from {years[0]} to {years[-1]} on AI agents in finance, financial markets research and market structure."
blog_ld = ld(dict(BLOG_LD, description=desc, inLanguage="en", publisher=ORG, blogPost=[
    {"@type": "BlogPosting", "headline": p["title"], "url": BASE + p["slug"] + ".html", "datePublished": p["dt"].strftime("%Y-%m-%d"),
     "author": person(p["author"])} for p in sorted(kept, key=lambda p: p["dt"], reverse=True) if not p["stub"]]),
    crumbs(("Blog", BASE)))
page = head(BASE, "Blog — OpenEXA", desc, "website", f"  {blog_ld}\n").replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n  <base href="/blog/">\n', 1) + f'''
<body data-page="blog" data-nav="dark-start" class="blog-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain blog-hero">
      <div class="container blog-hero-grid">
        <div class="blog-hero-copy">
          <div class="eyebrow" data-reveal>The OpenEXA blog</div>
          <h1 class="display-1 blog-h1" data-reveal>Research summaries and our first notes on AI&nbsp;agents.</h1>
          <p class="lede mt-3" data-reveal>Written by the people behind OpenEXA and the researchers they work with.</p>
          <div class="article-meta" data-reveal><span>{len(kept)} posts</span><span>{years[0]}–{years[-1]}</span><span>{len(COLLECTIONS)} collections</span></div>
        </div>
        {LIBRARY}
      </div>
    </section>

    <div class="blog-index">
    <nav class="blog-chips-bar" aria-label="Collections">
      <div class="container"><div class="blog-chips"><a class="chip" href="index.html" data-blog-filter="all" aria-current="true">All <b>{len(kept)}</b></a>{chips}</div></div>
    </nav>

{chr(10).join(sections)}
    </div>

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
  <script src="{PFX}assets/js/site.js" defer></script>
  <script src="{PFX}assets/js/blog.js" defer></script>
</body>
</html>
'''
if OUT.exists(): shutil.rmtree(OUT)
if (ROOT / "research" / "blog").exists(): shutil.rmtree(ROOT / "research" / "blog")  # the blog lived here until 2026-09-30
write(OUT / "index.html", page)

# ---------------- posts ----------------
# v2x: the dark hero carries the post's plate and a sentence from the post that it draws (no WebGL formation: v2 paired
# a research note's figure with each collection, e.g. a decaying curve over a grains-futures summary). The CMS's hero
# image leaves the top of the article, except the two 2024 screenshots of the author's own work (KEEP_HERO), which stay
# as the article's first figure. Figures are numbered (Fig. N) in the site's register; their captions keep their words.
def post_plate(p):
    econ = p["col"] == "economics" or p["slug"] not in PLATES
    quote = "" if econ else f'<p class="pp-q"><a href="#plate-src"><span class="hang">“</span>{tight_hy(prose(PLATES[p["slug"]][2]))}”</a></p>'
    hedge = "The collection’s mark" if econ else "Schematic · no data is plotted"
    return f'''<figure class="post-plate" id="plate">
          <div class="post-plate-art" aria-hidden="true">{plate_svg(p["slug"], p["col"], turn(p))}</div>
          <figcaption><span class="pp-k">Plate · {esc(plate_label(p))}</span>{quote}<span class="pp-h">{hedge}</span></figcaption>
        </figure>'''
MARKED = []  # jury (blog): every plate's sentence is found and marked, or the build stops (checked after the posts)
BLOCK = re.compile(r"</?(?:p|li|ul|ol|h[2-6]|blockquote|figure|figcaption)\b[^>]*>")
def mark_source(html_, quote):
    """lab blog-moment: the sentence the hero plate draws, marked where the post says it (words unchanged), with a link
    back to the plate. A sentence that runs across paragraphs (Exercise timing: '(i) ... (iii)') is marked piece by piece;
    the first piece carries the anchor, the last the way back. Returns the article unchanged if the sentence is not found."""
    words = re.findall(r"\w+|[^\w\s]", quote)
    gap = r"(?:\s|<[^>]+>|&nbsp;)*"
    pat = gap.join("(?:'|’|&#x27;|&#39;)" if w in "'’" else re.escape(H.escape(w, quote=False)) if w in "&<>" else re.escape(w) for w in words)
    m = re.search(pat, html_)
    if not m: return html_
    seg, pieces, at = m.group(0), [], 0
    for b in BLOCK.finditer(seg):  # split at block boundaries: only inline markup is wrapped
        pieces.append((seg[at:b.start()], True)); pieces.append((b.group(0), False)); at = b.end()
    pieces.append((seg[at:], True))
    text = [i for i, (t, inline) in enumerate(pieces) if inline and re.sub(r"<[^>]+>|\s", "", t)]
    out = []
    for i, (t, inline) in enumerate(pieces):
        if i in text:
            out.append(f'<mark class="plate-src"{' id="plate-src"' if i == text[0] else ''}>{t}</mark>')
            if i == text[-1]: out.append('\u2060<a class="plate-back" href="#plate" aria-label="Back to the plate"></a>')
        else: out.append(t)
    MARKED.append(quote)
    return html_[:m.start()] + "".join(out) + html_[m.end():]
def numbered(html_):
    """'Fig. N' on every figure of an article, in order: inside its caption, or as a caption of its own"""
    k = [0]
    def one(m):
        k[0] += 1
        fig, tag = m.group(0), f'<span class="fig-n">Fig. {k[0]}</span>'
        if "<figcaption>" in fig: return fig.replace("<figcaption>", f"<figcaption>{tag}", 1)
        return fig.replace("</figure>", f"<figcaption>{tag}</figcaption></figure>")
    return re.sub(r"<figure\b.*?</figure>", one, html_, flags=re.S)
for p in order:
    if p["stub"]: continue
    if p["col"] != "economics":
        assert p["slug"] in PLATES, (p["slug"], "no plate")
        assert PLATES[p["slug"]][2] in said(p), (p["slug"], "the plate's quote is not the post's own sentence")
    sib = [q for q in by_col[p["col"]] if not q["stub"]]
    i = sib.index(p); prev = sib[i - 1] if i else None; nxt = sib[i + 1] if i + 1 < len(sib) else None
    src_host = re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) if p["source"] else ""
    url = BASE + p["slug"] + ".html"
    post_ld = {"@type": "BlogPosting", "@id": url + "#article", "headline": p["title"], "description": p["excerpt"], "url": url,
               "mainEntityOfPage": url, "datePublished": p["dt"].strftime("%Y-%m-%d"), "inLanguage": "en", "image": [og_image(url)],
               "author": person(p["author"]), "publisher": ORG, "isPartOf": BLOG_LD, "articleSection": LABEL[p["col"]],
               "timeRequired": f"PT{p['minutes']}M"}
    if p["source"]: post_ld["isBasedOn"] = p["source"]
    # the eyebrow above names the collection; the link says where it goes (v2 repeated the name as the link)
    side_links = [f'<a class="link-arrow" href="index.html#{p["col"]}">{len(by_col[p["col"]])} posts in this collection {ARROW}</a>', f'<a class="link-arrow" href="index.html">All {len(kept)} posts {ARROW}</a>']
    if p["source"]: side_links.insert(0, f'<a class="link-arrow" href="{esc(p["source"])}" target="_blank" rel="noopener">Original on {esc(src_host)} {OUTB}</a>')
    if p["col"] == "markets": side_links.insert(1, f'<a class="link-arrow" href="{SCHOLAR}" target="_blank" rel="noopener">The papers on Google Scholar {OUTB}</a>')
    hero_img = (f'<figure class="blog-hero-img"><img src="{PFX}assets/img/blog/{p["hero_file"]}"{body_srcset(p["hero_file"])} alt=""{size(p["hero_file"])} decoding="async"></figure>\n            '
                if p.get("hero_file") and p["slug"] in KEEP_HERO else "")
    pager = "".join([
        f"<a class='pager-card prev' href='{prev['slug']}.html'><span class='k'>← Newer</span><h3>{serif(prev['title'])}</h3><p>{fmt(prev['dt'])}</p></a>" if prev else f"<a class='pager-card prev' href='index.html'><span class='k'>← The blog</span><h3>All {len(kept)} posts</h3><p>{esc(LABEL[p['col']])} and {len(COLLECTIONS) - 1} more collections.</p></a>",
        f"<a class='pager-card next' href='{nxt['slug']}.html'><span class='k'>Older →</span><h3>{serif(nxt['title'])}</h3><p>{fmt(nxt['dt'])}</p></a>" if nxt else f"<a class='pager-card next' href='{PFX}research.html'><span class='k'>Research →</span><h3>The thinking behind the swarm.</h3><p>Two research notes and an eight-part series.</p></a>",
    ])
    crumb, meta_extra, series_box = esc(LABEL[p["col"]]), "", ""
    if p["slug"] in SERIES_POS:  # series posts read in order, with the series listed alongside
        j = SERIES_POS[p["slug"]]; part = SERIES[j][1]
        crumb = f'<a href="index.html#series">{SERIES_NAME}</a>'
        # r2-copy: the rail and the side list number the introduction 00 and the parts 01-03; 'post 1 of 4' counted
        # another way. The line now says what the rail says: the introduction comes before Part 1; a part is n of 3
        meta_extra = f"<span>{esc(part)} · before {esc(SERIES[1][1])}</span>" if j == 0 else f"<span>{esc(part)} of {len(SERIES) - 1}</span>"
        items = "".join(f'<li{" aria-current=\"true\"" if s == p["slug"] else ""}><a href="{s}.html"><span>{i:02d}</span><span><b>{esc(pt)}</b>{esc(sh)}</span></a></li>' for i, (s, pt, sh) in enumerate(SERIES))
        series_box = f'<div class="series-box"><div class="eyebrow mb-2">{SERIES_NAME}</div><ol role="list">{items}</ol></div>'
        sp = SLUGS[SERIES[j - 1][0]] if j else None; sn = SLUGS[SERIES[j + 1][0]] if j + 1 < len(SERIES) else None
        pager = "".join([
            f"<a class='pager-card prev' href='{sp['slug']}.html'><span class='k'>← {esc(SERIES[j - 1][1])}</span><h3>{serif(sp['title'])}</h3><p>{fmt(sp['dt'])}</p></a>" if sp else f"<a class='pager-card prev' href='index.html#series'><span class='k'>← {SERIES_NAME}</span><h3>Four posts, from business model to AI agents.</h3><p>2024 · {series_minutes} min in total</p></a>",
            f"<a class='pager-card next' href='{sn['slug']}.html'><span class='k'>{esc(SERIES[j + 1][1])} →</span><h3>{serif(sn['title'])}</h3><p>{fmt(sn['dt'])}</p></a>" if sn else f"<a class='pager-card next' href='{PFX}research.html'><span class='k'>What came next →</span><h3>The thinking behind the swarm.</h3><p>The research notes and eight-part series behind OpenEXA's agentic infrastructure.</p></a>",
        ])
        post_ld["isPartOf"] = [BLOG_LD, {"@type": "CreativeWorkSeries", "name": f"{SERIES_NAME} - OpenEXA Blog", "url": BASE + "#series"}]
        post_ld["position"] = j + 1
    note = f"Originally published on openexa.com, {fmt(p['dt'])}." + (f" A summary of work first published on {src_host}." if p["source"] else "")
    original = f'<a class="link-arrow" href="{esc(p["source"])}" target="_blank" rel="noopener">The original on {esc(src_host)} {OUTB}</a>' if p["source"] else ""
    byline = f'<a href="{PFX}company.html#{PEOPLE_ID[person(p["author"])["name"]]}">{esc(shown(p["author"]))}</a>' if person(p["author"]).get("name") in PEOPLE_ID else esc(shown(p["author"]))
    page = head(url, f'{p["title"]} — OpenEXA Blog', p["excerpt"], "article", f'  {ld(post_ld, crumbs(("Blog", BASE), (p["title"], url)))}\n') + f'''
<body data-page="post" data-nav="dark-start" class="article-page blog-post">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero blog-post-hero">
      <div class="container post-hero">
        <div class="post-hero-copy">
          <div class="eyebrow" data-reveal><a href="index.html">Blog</a> · {crumb}</div>
          <h1 class="display-2 article-title blog-title" data-reveal>{serif(p["title"])}</h1>
          <p class="post-byline" data-reveal>{byline}</p>
          <div class="article-meta" data-reveal><span><time datetime="{iso(p)}">{fmt(p["dt"])}</time></span><span>{p["minutes"]}&nbsp;min read</span>{meta_extra}</div>
        </div>
        {post_plate(p)}
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid">
          <article class="col-7 offset-5 article blog-article">
            {mark_source(numbered(hero_img + lead(hang(smart_html(p["body"])))), PLATES[p["slug"]][2]) if p["col"] != "economics" and p["slug"] in PLATES else numbered(hero_img + lead(hang(smart_html(p["body"]))))}
            <div class="article-end"><span class="mark" aria-hidden="true"></span><p>{esc(note)}</p>{original}</div>
          </article>
          <div class="col-3 article-side">
            <div class="sticky blog-side">
              {series_box}
              <div class="eyebrow mb-2">{esc(LABEL[p["col"]])}</div>
              {"".join(side_links)}
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container"><h2 class="sr-only">More posts</h2><div class="pager">{pager}</div></div>
    </section>
  </main>

{foot}
  <script src="{PFX}assets/js/site.js" defer></script>
</body>
</html>
'''
    write(OUT / f'{p["slug"]}.html', page)
assert len(MARKED) == sum(1 for p in order if p["col"] != "economics" and p["slug"] in PLATES), "a plate's sentence was not found in its post"
atom(OUT / "feed.xml", "OpenEXA Blog", "AI agents in finance, financial markets research and market structure.", BASE,
     [{"url": BASE + p["slug"] + ".html", "title": p["title"], "published": p["dt"].strftime("%Y-%m-%d"), "updated": p["dt"].strftime("%Y-%m-%d"),
       "author": p["author"], "summary": p["excerpt"]} for p in sorted(kept, key=lambda p: p["dt"], reverse=True) if not p["stub"]])

# ---------------- summary for the research index ----------------
json.dump({"total": len(kept), "years": [years[0], years[-1]],
           "series": {"name": SERIES_NAME, "first": SERIES[0][0], "count": len(SERIES), "minutes": series_minutes},
           "collections": [{"key": k, "label": l, "count": len(by_col[k]), "years": [by_col[k][-1]["dt"].year, by_col[k][0]["dt"].year], "lede": lede} for k, l, lede in COLLECTIONS]},
          open(FILES / "blog_summary.json", "w", encoding="utf-8", newline="\n"), indent=2, ensure_ascii=False)

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
# Security headers for every response. Nothing inline executes (the JSON-LD blocks are data, which CSP does not govern)
# and every font, image and script is same-origin, so the policy is strict; the pages' style="" attributes (and the
# ones the engines set) need style-src-attr. form-action 'none': the access form only builds a mailto draft in JS, and
# without JS it must not submit itself (its fields would land in a GET URL). Add a form endpoint's origin to
# connect-src if one is ever configured (data-endpoint, see site.js). No Cross-Origin-Opener-Policy: it makes Lighthouse
# (and so PageSpeed Insights) fail with NO_NAVSTART, and a static site with no sessions gains next to nothing from it.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; font-src 'self'; "
       "img-src 'self' data:; connect-src 'self'; manifest-src 'self'; base-uri 'self'; form-action 'none'; "
       "frame-ancestors 'none'; object-src 'none'; upgrade-insecure-requests")
HEADERS = {
    "Content-Security-Policy": CSP,
    "Permissions-Policy": "accelerometer=(), browsing-topics=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), "
                          "hid=(), magnetometer=(), microphone=(), midi=(), payment=(), serial=(), usb=(), xr-spatial-tracking=()",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    # instant navigation: Chrome/Edge prefetch a page's HTML when a link is hovered (prefetch only - no script runs early)
    "Speculation-Rules": '"/speculation.specrules"',
}
# Longer caching for assets whose content rarely changes; HTML, CSS and JS keep Azure's revalidate-after-30 s default
# because their URLs carry no version. Most specific first: the first matching route wins.
CACHE = [
    ("/assets/fonts/*", "public, max-age=2592000, stale-while-revalidate=86400"),   # rename the files if the fonts change
    ("/assets/img/blog/*", "public, max-age=2592000, stale-while-revalidate=86400"),
    ("/assets/img/team/*", "public, max-age=86400, stale-while-revalidate=604800"),
    ("/assets/img/og/*", "public, max-age=604800, stale-while-revalidate=86400"),
    ("/assets/img/*", "public, max-age=604800, stale-while-revalidate=86400"),
]
CONFIG = {
    "routes": [{"route": r, "headers": {"Cache-Control": c}} for r, c in CACHE] + routes,
    "responseOverrides": {"404": {"rewrite": "/404.html", "statusCode": 404}},
    "globalHeaders": HEADERS,
    "mimeTypes": {".webmanifest": "application/manifest+json", ".specrules": "application/speculationrules+json"},
}
ONE = lambda o: json.dumps(o, ensure_ascii=False, separators=(", ", ": "))  # one route per line: compact but diffable
io.open(ROOT / "staticwebapp.config.json", "w", encoding="utf-8", newline="\n").write("{\n  \"routes\": [\n" + ",\n".join("    " + ONE(r) for r in CONFIG["routes"]) + "\n  ],\n" + "".join(f'  "{k}": {ONE(CONFIG[k])},\n' for k in ("responseOverrides", "globalHeaders")) + "  \"mimeTypes\": " + ONE(CONFIG["mimeTypes"]) + "\n}\n")
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
(FILES / "blog_redirects.txt").write_text("\n".join(rules) + "\n", encoding="utf-8", newline="\n")

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
for p in kept:  # the card-size copies thumb() refers to
    if not p.get("hero_file"): continue
    im = Image.open(IMG / p["hero_file"]).convert("RGB"); w, h = im.size; stem = p["hero_file"].rsplit(".", 1)[0]
    for t in card_widths(p["hero_file"]):
        im.resize((t, round(h * t / w)), Image.LANCZOS).save(IMG / f"{stem}-{t}w.webp", "WEBP", quality=82, method=6)
for name in sorted(BODY_COPIES):  # the in-body figures' 800 px copies (body_srcset); a card copy of the same file is the same image
    stem = name.rsplit(".", 1)[0]; out = IMG / f"{stem}-{BODY_W}w.webp"
    if out.exists(): continue
    im = Image.open(IMG / name); w, h = im.size
    im = im.convert("RGBA" if "A" in im.mode or "transparency" in im.info else "RGB")
    im.resize((BODY_W, round(h * BODY_W / w)), Image.LANCZOS).save(out, "WEBP", quality=82, method=6)
    assert out.stat().st_size < (IMG / name).stat().st_size, (name, "the 800 px copy is not smaller")

# ---------------- report ----------------
imgs = list(IMG.iterdir())
print(f"kept {len(kept)} ({sum(1 for p in kept if p['stub'])} outbound stubs), held back {len(EXCLUDE)}; pages {len(list(OUT.glob('*.html')))}; images {len(imgs)} / {sum(f.stat().st_size for f in imgs) // 1024} KB")
for k, l, _ in COLLECTIONS: print(f"  {l}: {len(by_col[k])}")
print("crypto mentions in kept posts:", {p["slug"][:40]: len(re.findall(r"crypto|bitcoin|token", plain(p["body"]), re.I)) for p in kept if re.search(r"crypto|bitcoin|token", plain(p["body"]), re.I)})
print("old product names (OXA/AUT) in kept posts:", [p["slug"][:40] for p in kept if re.search(r"\b(OXA|AUT)\b", plain(p["body"]))])
