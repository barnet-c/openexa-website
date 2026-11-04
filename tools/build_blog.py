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
from blog_plates import PLATES, plate_svg, collection_svg, library_svg, rings_tall
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
    # ai's lede prints only on Research §03's card (blog_summary.json); r4-copy point 5 (VOICE 6.1): no dash pivot, C-141 as strong
    ("ai", "AI & agents", "The first notes on AI copilots, guardrails and autonomous agents in financial markets. The thinking in them became OpenEXA's agentic infrastructure."),
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
# award a3 (a3-dev 12): a meta description is at most 160 characters. One excerpt is the post's own 164-character
# sentence; its meta (description, og:, twitter:) drops "new", a word dated by the post (May 2022; no claim gets stronger). The
# card text, the feed and JSON-LD keep the sentence as the post has it
META_DESC = {"modern-trends-in-financial-engineering":
    "This book series, Modern Trends in Financial Engineering, publishes monographs on important contemporary topics in theory and practice of Financial Engineering."}
assert all(len(v) <= 160 for v in META_DESC.values())
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
        alt = smart(alt or ALT.get(name, ""))   # award a3: the alt text's apostrophes and quotes as the page sets them
        shutil.copyfile(OLD / "img" / name, IMG / name) if (OLD / "img" / name).exists() else None
        return f'<img src="../assets/img/blog/{name}"{body_srcset(name)} alt="{esc(alt)}"{size(name)}{body_cap(name)} loading="lazy" decoding="async">'
    b = re.sub(r'<img[^>]*src="(/graphics/[^"]+)"[^>]*>', img, b)
    b = re.sub(r"<figure>\s*(<img[^>]+>)\s*</figure>", r"<figure>\1</figure>", b)
    b = re.sub(r"<p>\s*(<img[^>]+>)\s*</p>", r"<figure>\1</figure>", b)
    b = re.sub(r"(?<!<figure>)(<img[^>]+>)(?!</figure>)", r"<figure>\1</figure>", b)
    # award a3 (4K inspector): a picture capped at its own pixels (body_cap) names its cap on its figure, so the caption
    # under it starts on the picture's edge, not the mat's
    b = re.sub(r'<figure><img([^>]*) style="max-width:(\d+px)"', r'<figure style="--cap:\2"><img\1 style="max-width:\2"', b)
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
# award a1 (4K inspector, art director, a1-dev): from 1921 px the root grows with the window (site.css: 100vw / 120), so
# the mat is 39.2rem = 32.67vw and the picture in it 37.7rem = 31.4vw (1,206 px at 3840): 4K and 1920 at 2x now load
# the 1,800 px file instead of stretching the 800 px copy 1.5 times
BODY_SIZES = "(min-width: 1921px) 31.4vw, (max-width: 660px) calc(100vw - 64px), (max-width: 960px) 552px, 603px"
BODY_COPIES = set()
def body_srcset(name):
    d = dims(name)
    if not d or d[0] <= BODY_W * 1.1: return ""
    BODY_COPIES.add(name)
    stem = name.rsplit(".", 1)[0]; src = "../assets/img/blog/"
    return f' srcset="{src}{stem}-{BODY_W}w.webp {BODY_W}w, {src}{name} {d[0]}w" sizes="{BODY_SIZES}"'
def fig_cap(name):
    """the cap of body_cap() on its figure, for the caption (award a3)"""
    m = re.search(r"max-width:(\d+px)", body_cap(name) if name else "")
    return f' style="--cap:{m.group(1)}"' if m else ""
def body_cap(name):
    """award a1 (4K inspector): a picture is never drawn wider than its pixels. Its widest file in CSS px (so a 1x screen
    never stretches it: the 700 px Medium figures at 2560 and 3840); a macOS screenshot (a 2x capture) at half its
    captured width, the size its interface had (the two tall tearsheet tables: 368 and 364 px, not 603). Centred on its
    mat. Nothing for a picture that fills the mat up to a 5K screen"""
    d = dims(name)
    if not d: return ""
    w = d[0]
    if "screenshot-" in name:
        from PIL import Image
        w = min(w, Image.open(OLD / "img" / name).size[0] // 2)
    return f' style="max-width:{w}px"' if w < 1400 else ""
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
def plate(p, cls="blog-thumb"):
    """A card's plate: the drawing alone (cut, 1 Nov: the 'Plate · <name>' label over it went; the title names the
    post). aria-hidden: the card's h3 names the post."""
    return f'<div class="{cls} blog-plate" aria-hidden="true">{plate_svg(p["slug"], p["col"], turn(p))}</div>'
SERIF_HY = re.compile(r"(?<=[^\W\d_])-(?=[^\W\d_])")
# v2x lab (blog-editorial, 31 Oct): typography on the page, never words (VOICE §7; r1-art M8, r1-copy 31). The old CMS
# kept typewriter marks: straight quotes and apostrophes, a spaced hyphen for a dash, three dots. What the page shows
# is set with the real characters, and so are a post's <title> and share text (r4-copy); feeds and JSON-LD keep the
# ASCII the CMS had.
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
        # r5: an article's headings are display lines too; they bind their function words as the titles do (post_title)
        # award a1: in the article's serif lines (blockquotes at the heading step since a1, and its heads) a hyphenated
        # compound is never split at its hyphen ("The Next Phase of Gen- / AI's" at 390): it is one unbreakable word
        out.append(keep_compounds(tight_hy(esc_text(bind(s) if head_ else s))) if head_ or quote_ else esc_text(s)); prev = s[-1] if s else prev
    return "".join(out)
def tight_hy(escaped):
    """a serif line: the ASCII hyphen between letters (still found by find-in-page), set tight (site.css .hy)"""
    return SERIF_HY.sub('<span class="hy">-</span>', escaped)
def esc_text(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
COMPOUND = re.compile(r"[^\W\d_][\w’']*(?:<span class=\"hy\">-</span>[^\W\d_][\w’']*)+")
def keep_compounds(h):
    """a tight_hy() line's hyphenated words in site.css .nowrap (short words in the article's serif lines only; titles
    keep their break opportunities, where a long compound must still fit a phone's column)"""
    return COMPOUND.sub(lambda m: f'<span class="nowrap">{m.group(0)}</span>', h)
def serif(s):
    """escaped text for a serif line: real quotes and dashes, and the hyphen between letters in span.hy (Instrument
    Serif draws U+002D as 'Domain – Specific'; SYSTEM.md §3, r2). Feeds and JSON-LD keep plain ASCII."""
    return tight_hy(esc(smart(s)))
# r5-art (minor): a post title on the page never ends a line on a short function word ("Contracting in the / presence
# of judicial agency"): the word is bound to the one after it with a no-break space, the rule research's titles take in
# r5, so text-wrap: balance can only break by sense ("Contracting / in the presence of judicial agency"). Typography
# only: same words; find-in-page and copying read a space. <title>, meta, JSON-LD and the feed keep plain spaces
BIND = re.compile(r"(?<![\w’'‐-])(a|an|the|of|on|in|to|for|and|or|as|at|by|is|via|with|from|under) +(?=[^\s—–-])", re.I)
# A sentence inside a title also keeps its last word with the one before it, so no line opens on "System. Why Banks
# Exist?" (r5 probe: that post's H1 at 1440, 1024 and 390, its card at 320). The longest chain this makes, "in the
# Financial System.", is 253 px in the H1 at 320 (column 280): measured, no overflow at any width
INNER_END = re.compile(r" (?=[^\s]+[.?!] [A-Z])")
# The titles' compound terms are never split across lines ("Optimal Execution for High / Frequency Trading", "Price /
# Dynamics"), a typesetter's keep-together list, as an exception list is for hyphenation. A term whose chain would run
# past a phone's 280 px column in its H1 stays off the list ("and Portfolio Concentration", ~285 px at 35 px). So the
# list holds "High Frequency", not "High Frequency Trading": bound to its "for", the whole term ran 10 px past the H1's
# column at 320 (r5 probe p6); at 320 alone the title takes a third line ("Trading"), at every other width it is two
CHAIN_MAX = 24  # characters in one bound run: "in the Financial System." (24) is 253 px in the H1 at 320, the widest that fits
KEEP = ("High Frequency", "Generative AI","Drawdown Risk", "Price Dynamics", "Exercise Timing", "True Potential", "Relative Value Analysis",
        "Volatility Asymmetry", "Storage Cost Model", "Value Creation")
KEEP_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in KEEP) + r")\b")
def bind(t):
    t = INNER_END.sub("\u00a0", BIND.sub(lambda m: m.group(1) + "\u00a0", t))
    return KEEP_RE.sub(lambda m: m.group(1).replace(" ", "\u00a0"), t)
def post_title(s):
    """a post's title as a display line (index cards, the register, the series rail, the H1, the pager)"""
    return tight_hy(esc(bind(smart(s))))
# r5-copy (minor): JSON-LD now sets a title and an excerpt as the page does (’, the house dash), as r4 did for <title> and
# the share text, with plain spaces (a no-break space is for line breaking, which structured data has none of). The feed
# alone keeps the text as published (every subscriber's copy of an entry would change)
def ld_text(s): return smart(s).replace("\u00a0", " ")
def prose(s): return esc(smart(s))
def hang(h):
    """a paragraph that opens on a quote mark hangs it in the margin, so the text's left edge stays straight (also when
    the mark opens an italic quotation: marks_in_em)"""
    return re.sub(r'<p( class="[^"]*")?>(<em>)?([“‘])', r'<p\1>\2<span class="hang">\3</span>', h)
def marks_in_em(h):
    """award a3 (4K inspector): a quotation set in italic between quote marks (“<em>...</em>”) takes its marks into the
    italic, so they are drawn in the quotation's face (Instrument Serif italic, blog.css), not in upright Inter beside it,
    where the closing mark read as a straight one. Typography only: the same characters in the same order"""
    return re.sub(r"</em>”", "”</em>", re.sub(r"“<em>", "<em>“", h))
def bare_marks(h):
    """award a4 (blog's own find): the CMS left bold or italic round a lone mark: a bold comma in the Gen-AI introduction,
    an italic full stop, italic and bold spaces, bold zero-width joiners (6 posts). Since a3 an italic is Instrument Serif
    at 1.08em, so such a mark showed in another face. The tags go; the characters stay, in the same order"""
    return re.sub(r"<(strong|b|em|i)>([^<\w]*)</\1>", r"\2", h)
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
    # award a1 (a1-ux 22, C-146): the read time is counted from the words on the page (220 a minute), for every post; the
    # old CMS's minutes understated the long posts (the Gen-AI introduction, ~1,380 words, said 3) and overstated the
    # excerpts (5-6 for ~160-330 words). Claim-level: listed for the owner's second sign-off
    p["cms_minutes"] = int(re.sub(r"\D", "", p["minutes"]) or 0)
    p["minutes"] = max(1, round(words / 220))
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
    # award budgets: the section mark site.js set at start (aria-current="true" on Research, in the bar and the sheet)
    nav = nav.replace(f'<a href="{PFX}research.html">Research</a>', f'<a href="{PFX}research.html" aria-current="true">Research</a>')
    return nav, foot
# award a1 (system's request, ~18:00): the share card's alt says what the card shows, as launch_meta_v9's card_alt() does
# for the top pages: the page's H1 (plain spaces), then its picture; og:locale too.
# award a2 (system's request, ~23:30): build_og.py now draws the blog index's card with its open book (svg.lib-art) and
# each post's with its own plate (the post's first svg.bp-art), not the globe. The book has one leaf per post, filed in
# its three collections (library_svg), so the alt says "one leaf for each post" (system's draft: "each collection")
CARD_PIC = {"index": "Beside it, the blog’s open book, one leaf for each post.", "post": "Beside it, the post’s engraved plate."}
def card_alt(h1, pic):
    t = re.sub(r"\s+", " ", h1.replace(" ", " ")).strip()
    return t + ("" if t[-1:] in ".?!" else ".") + " " + CARD_PIC[pic]  # a title without closing punctuation still ends its sentence
# award budgets (the guard's big item for the post, system's lines): a post whose article sets text in em/i (blog.css a3:
# Instrument Serif italic) preloads that face as Home and Company do. Found in the CSS during layout, it loaded at
# VeryHigh at the end of the render chain (site.css -> the face), +300 ms on mobile FCP and LCP. Only where it is used:
# a preload nobody uses is a warning and 23 KB of a phone's first second
ITALIC_PRE = f'  <link rel="preload" href="{PFX}assets/fonts/instrument-serif-400i-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
def sets_italic(article):
    return bool(re.search(r"<(em|i)\b[^>]*>(?:\s|<[^>]*>)*[^\s<]", article))  # an em or i with something to set
# award budgets: the scripts start after the first paint (system's afterpaint.js: site.js at the paint, then the rest on
# oxa:loaded), as Lifecycles, Trust and Research do. As defer tags their download and evaluation were counted into
# Lighthouse's simulated first paint. Without JavaScript nothing changes; with it the first screen is the same
def after_paint(scripts):
    return f'  <script src="{PFX}assets/js/afterpaint.js" defer data-after-paint="{" ".join(PFX + "assets/js/" + n for n in scripts)}"></script>'
def head(url, title, desc, kind="article", extra="", h1="", links="", pic="post", italic=False):
    alt = esc(card_alt(h1 or title, pic))
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">
  <meta name="theme-color" content="#0E1512">
  <link rel="canonical" href="{url}">
{links}  <meta property="og:url" content="{url}">
  <meta property="og:site_name" content="OpenEXA">
  <meta property="og:type" content="{kind}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:image" content="{og_image(url)}">
  <meta property="og:image:alt" content="{alt}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(desc)}">
  <meta name="twitter:image" content="{og_image(url)}">
  <meta name="twitter:image:alt" content="{alt}">
  {ROBOTS}
  {FEED_LINKS[0]}
  {FEED_LINKS[1]}
  <link rel="apple-touch-icon" href="{PFX}assets/img/apple-touch-icon.png">
  <link rel="manifest" href="{PFX}site.webmanifest">
  <link rel="icon" type="image/svg+xml" href="{PFX}assets/img/favicon.svg">
  <link rel="preload" href="{PFX}assets/fonts/instrument-serif-400-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{PFX}assets/fonts/inter-var-latin.woff2" as="font" type="font/woff2" crossorigin>
{ITALIC_PRE if italic else ""}  <link rel="stylesheet" href="{PFX}assets/css/site.css">
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
# award a1: "Business model" (was "The business model"): the four short names in one form, none with an article
SERIES = [("in-search-gen-ai-business-model", "Introduction", "Business model"),
          ("rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies", "Part 1", "Relative value"),
          ("tearsheet-how-to-use-tearsheet-in-the-face-of-volatile-crypto-and-bond-markets-as-a-means-of-capital-preservation-and-asset-appreciation", "Part 2", "Guardrails & tearsheets"),
          ("empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way", "Part 3", "AI agents")]
SERIES_NAME = "The Gen-AI series"
SERIES_POS = {s: i for i, (s, _, _) in enumerate(SERIES)}
def part_name(i):
    """award a2 (a2-ux 16: one post carried three names, "Introduction" in the crumb, "Business model" in the rails, and
    "Part 1" in the pager for the post the rail calls "Relative value"): on a post, the series rail and the pager name a
    part by both, "Part 1 · Relative value", so the crumb's word and the index rail's word are each in it. The part leads
    in the small step's grey (span.ps-p), the name follows in the link's colour"""
    return f'<span class="ps-p">{esc(SERIES[i][1])}</span> · {esc(SERIES[i][2])}'
assert all(s in SLUGS and not SLUGS[s]["stub"] for s, _, _ in SERIES)
assert all(any(k in p["title"] for p in kept) for k in KEEP), [k for k in KEEP if not any(k in p["title"] for p in kept)]  # a stale keep-together term
_runs = [(max(bind(smart(p["title"])).split(" "), key=len), p["slug"]) for p in kept]
assert all(len(r) <= CHAIN_MAX for r, _ in _runs), [(r, s) for r, s in _runs if len(r) > CHAIN_MAX]  # a bound run too wide for a phone's H1

# ---------------- index ----------------
# v2x (30 Oct 2026): every post appears once. The Gen-AI series is AI & agents' own lead (it is four of the
# collection's five posts), drawn as a dated rail; v2 showed it as a featured band and then again as four cards of the
# AI grid. The chips stick only over the collections (a wrapper ends them before the closing band and the footer).
nav, foot = chrome()
assert nav.count('aria-current="true"') == 2, "the bar and the sheet each mark Research once"
# the index is the footer's Blog page (site.js marked it at start, as the footer marks its own page everywhere)
foot_index = foot.replace(f'<a href="{PFX}blog/index.html">Blog</a>', f'<a href="{PFX}blog/index.html" aria-current="page">Blog</a>', 1)
assert foot_index != foot
def iso(p): return p["dt"].strftime("%Y-%m-%d")
# cut (1 Nov, the owner: "so many words everywhere"; the index's budget is 250 words and the 29 titles alone are 242):
# a card is its plate and its title. The dateline, the excerpt and the read time left the index (each post page keeps
# its date and read time; the excerpt stays the post's meta description and feed summary). A collection says its
# author and years once, in its head
day = lambda d: d.strftime("%b %-d") if os.name != "nt" else d.strftime("%b %#d")
def card(p, lead=False, kicker=""):
    """lead (award a1, art director + a1-ux 16): a collection's newest post leads its grid, two columns by two rows, its
    plate drawn larger; the rest stay compact. Same plate, same title: no new words. kicker: a line over the title (the
    fifth AI post's "Also in AI & agents"); a post with a short name (SHORT_TITLE) shows it, as the rail's parts do"""
    ext = ' target="_blank" rel="noopener"' if p["stub"] else ""
    k = f'<span class="k">{esc(kicker)}</span>' if kicker else ""
    t = esc(SHORT_TITLE[p["slug"]]) if p["slug"] in SHORT_TITLE else post_title(p["title"])
    return f'''          <a class="blog-card{' blog-card--lead' if lead else ''}" href="{esc(href(p))}"{ext}>
            {plate(p)}<div class="blog-card-body">{k}<h3>{t}{(" " + OUTB) if p["stub"] else ""}</h3></div>
          </a>'''
# award a1 (art director, a1-ux 21): the AI collection's fifth post sat under the series rail with no word saying what it
# was. It is marked as S-42 signed it off ("Also in AI & agents"), and the index names it by the question its own title
# and its slug lead with (as the rail names the series' parts; its page's H1 keeps the full title). 13 words -> 3 + 4
SHORT_TITLE = {"why-banks-exist-unveiling-the-vital-role-of-credit-in-the-financial-system": "Why Banks Exist?"}
assert all(v in SLUGS[k]["title"] for k, v in SHORT_TITLE.items()), "a short title must be the post's own words"
ALSO_AI = "Also in AI & agents"
def register(posts, col, after=None):
    """posts as the lines of a register (both research collections since award a2): the year, the title, the arrow.
    award a2 (a2-ux 8: "give every card its year"; the index has a 250-word budget): the year is said once, at the head of
    its rows, as an archive sets it (Financial markets research: 3 years for 15 rows, not 15; Market structure &
    economics: 6 for 8), and a new year opens on a darker rule. The rows under it keep their date for machines (an
    empty <time datetime>) and are described by it (aria-describedby), so a list of links still says each post's year.
    after: the year said just above the list (the markets lead's): on a phone the lead is the list's first row, so a first
    year equal to it is not shown twice there (.br-cont: still read out)"""
    out, last = [], None
    for i, p in enumerate(posts):
        y = p["dt"].year; first = y != last; last = y
        yid = f"y-{col}-{y}"
        ext = ' target="_blank" rel="noopener"' if p["stub"] else ""
        cont = ' br-cont' if not i and y == after else ''
        when = (f'<time class="br-date{cont}" id="{yid}" datetime="{iso(p)}">{y}</time>' if first
                else f'<time class="br-date" datetime="{iso(p)}"></time>')
        out.append(f'''          <li{' class="br-g"' if first and i else ''}><a class="blog-card blog-row" href="{esc(href(p))}"{ext}{'' if first else f' aria-describedby="{yid}"'}>
            {when}
            <h3>{post_title(p["title"])}</h3>
            <span class="br-min">{OUTB if p["stub"] else ARROW}</span>
          </a></li>''')
    return "\n".join(out)
def lead_card(p):
    """award a2: Financial markets research opens on its newest post as a card across the collection, its plate on the
    register's seven columns and its year and title beside it (a1's two-by-two lead, kept as the lead; the grid it led
    is now the register below)"""
    return f'''        <a class="blog-card blog-lead" href="{esc(href(p))}" data-reveal>
          {plate(p)}<div class="blog-card-body"><time class="br-date" datetime="{iso(p)}">{p["dt"].year}</time><h3>{post_title(p["title"])}</h3><span class="br-min">{OUTB if p["stub"] else ARROW}</span></div>
        </a>
'''
rail = []
for i, (s, part, short) in enumerate(SERIES):
    p = SLUGS[s]
    # the rail names each part by the series' own short name (the post's full title is its page's H1); the date on its
    # node (the year is in the head); the first node filled: start here
    rail.append(f'''          <li><a class="series-card blog-card" href="{s}.html">
            <span class="sr-date"><time datetime="{iso(p)}">{day(p["dt"])}</time></span>{plate(p)}
            <h3>{esc(short)}</h3>
          </a></li>''')
series_minutes = sum(SLUGS[s]["minutes"] for s, _, _ in SERIES)
# a post hero's plate carries this hedge. The index says it once for all its plates, under the first one (cut, 1 Nov:
# the markets grid's and the phone head plates' copies went with their caption lines)
PLATES_HEDGE = "Schematic · no data is plotted"
in_series = {s for s, _, _ in SERIES}
# cut (1 Nov): the series' two-line head, its paragraph, "Start with the introduction", the "Featured series" row and
# the "Also in AI & agents" label went. The head is the series' name; the rail says the rest (four dated nodes, the
# first filled)
SERIES_BLOCK = f'''        <div class="blog-series" id="series" data-blog-series>
          <ol class="series-rail" role="list" aria-label="{SERIES_NAME}, in order" data-reveal>
{chr(10).join(rail)}
          </ol>
        </div>
'''
# the collection's one head: its name (the series' name for AI & agents), then its author and years on one line. The
# author is the collection's (collection() assigns by author); Tim Leung's name leads to his papers on Google Scholar
# (v2x's "The papers on Google Scholar" link), the others to their place on Company, as a post's byline does
HEADS = {"ai": SERIES_NAME + ".", "markets": "Financial markets research.", "economics": "Market structure & economics."}
def byline_link(author):
    name = person(author)["name"]
    if name == "Tim Leung":
        return f'<a href="{SCHOLAR}" target="_blank" rel="noopener">{esc(shown(author))} {OUTB}</a>'
    return f'<a href="{PFX}company.html#{PEOPLE_ID[name]}">{esc(shown(author))}</a>' if name in PEOPLE_ID else esc(shown(author))
sections = []
for n, (k, label, lede) in enumerate(COLLECTIONS, 1):
    span_ = span(by_col[k][-1]["dt"].year, by_col[k][0]["dt"].year)
    authors = {p["author"] for p in by_col[k]}
    assert len(authors) == 1, (k, authors)  # collections are assigned by author: the head can carry the byline once
    # award a1: the phone's markets head plate (collection_svg) went: the lead card's own plate heads the list on a phone
    # as on a desk, so the collection opens on one post's drawing everywhere
    shead = f'''        <div class="blog-head" data-reveal><h2 class="display-2">{serif(HEADS[k])}</h2><p class="blog-by">{byline_link(authors.pop())}<span>{span_}</span></p></div>
'''
    if k == "economics":
        # v2x lab (blog-editorial): eight cards carried one mark eight times (r1-art M6, r1-mobile 9). The collection
        # is set as a register, the way Research lists its notes, beside its plate, shown once.
        # award a2 (art director, medium): the plate stands at the register's full height, the rings risen on a diagonal
        # to fill it (blog_plates.rings_tall); tablets and phones keep the wide mark over the list. blog.js turns the
        # rings a step for each paper pointed at, focused or read (v2's hover turn, per row)
        body = f'''        <div class="blog-reg blog-econ" data-blog-turn>
          <ol class="blog-register" role="list" data-reveal>
{register(by_col[k], k)}
          </ol>
          <div class="blog-econ-plate" aria-hidden="true"><div class="blog-econ-art">{rings_tall(len(by_col[k]))}{collection_svg(k)}</div></div>
        </div>
'''
    elif k == "ai":
        rest = [p for p in by_col[k] if p["slug"] not in in_series]
        body = SERIES_BLOCK + f'''        <div class="blog-grid blog-grid--wide" data-reveal>
{chr(10).join(card(p, kicker=ALSO_AI) for p in rest)}
        </div>
'''
    else:
        # award a2 (art director, medium: the grid ended on an orphan card with ~70% of its row empty; a2-ux 8: fifteen
        # title-only cards ran ~3.5 screens at 1440 with no years). The lead card stays; the other fifteen are the
        # economics register's pattern (year, title, arrow) beside one plate that shows the drawing of the post pointed
        # at, focused or read (blog.js; Research's sticky figure, in the blog's plates). Every post's own plate is still
        # on the index, drawn larger than its card was; without JavaScript the plate shows the first row's. Phones and
        # tablets: the lead's plate heads the list, as the phone did since a1
        lead_p, rest_ = by_col[k][0], by_col[k][1:]  # not "lead": that name is the posts' lead() below
        panel = "".join(f'<div class="bpn{" is-on" if i == 0 else ""}">{plate_svg(p["slug"], p["col"])}</div>' for i, p in enumerate(rest_))
        body = lead_card(lead_p) + f'''        <div class="blog-reg blog-mkt" data-blog-follow>
          <ol class="blog-register" role="list" data-reveal>
{register(rest_, k, after=lead_p["dt"].year)}
          </ol>
          <div class="blog-panel" aria-hidden="true"><div class="blog-panel-art">{panel}</div></div>
        </div>
'''
    # chapters for the nav readout come from the section's own attributes (site.js), as on Home since the cut: no
    # numbered row over the head
    sections.append(f'''    <section class="section{' is-paper-2' if n % 2 else ''} blog-collection" id="{k}" data-blog-collection="{k}" data-chapter="{esc(label)}" data-n="{n:02d}" data-chapter-short="{esc(SHORT[k])}">
      <div class="container">
{shead}{body}      </div>
    </section>''')
years = sorted(p["dt"].year for p in kept)
# lab blog-moment: the hero's plate is the blog itself (blog_plates.library_svg): one leaf per post, filed by
# collection, the Gen-AI series in green; v2/v2x borrowed Research's WebGL library ("ten leaves, two lit"), which on
# this page drew the wrong library. The leaf counts come from the collections, so a new post adds a leaf.
assert sum(1 for p in by_col["ai"] if p["slug"] in in_series) == 4
# cut (1 Nov): the plate's title ("The library") and its sentence went (the drawing shows it: three bundles, the
# series in green; since award a3 the collections' names are links under the H1, HERO_INDEX). The page's one hedge for every plate on it stays, short
# (award a1: "Schematic · no data plotted", was "Schematic · no plate plots data": same hedge, one word shorter, so the
# specific H1 fits the index's 250 words)
INDEX_HEDGE = "Schematic · no data plotted"
# award a1 (art director, a1-ux 15): "The blog." was the site's last template headline. The H1 says what the blog is,
# with its count bound to the posts (C-139). One text box (verify_v9 reflow_400 reads phrase spans that wrap as crossing
# boxes): the count keeps its noun and bind() its function words, so it breaks only by sense ("29 posts on AI / and
# markets." from 1024 up)
INDEX_H1 = (f"{len(kept)} posts", "on AI and markets.")
LIBRARY = f'''<figure class="lib-plate">
          <div class="lib-stage">{library_svg(tuple(len(by_col[k]) for k in ("markets", "ai", "economics")), sum(1 for p in by_col["ai"] if p["slug"] in in_series))}</div>
          <figcaption><span class="pp-h">{INDEX_HEDGE}</span></figcaption>
        </figure>'''
# award a3 (a3-ux 6: "a 29-post page whose hero offers no way in"; the plate's lettering looked like tabs and did nothing):
# the collections' short names (SHORT, the bar's readout words) as links under the H1, in the page's order, the first
# stops after the skip link and the bar. They replace the plate's lettering, so each name is on the page once there.
# Under the H1, not the plate: the plate files Markets left, AI & agents at the spine, Economics right; a row in the
# page's order under it would put each name under another bundle. Hovering or focusing a name lights its bundle (CSS)
HERO_INDEX = (f'<nav class="blog-idx" aria-label="Collections" data-reveal style="--d:120ms">'
              + "".join(f'<a href="#{k}">{esc(SHORT[k])}{ARROW}</a>' for k, _, _ in COLLECTIONS) + "</nav>")
desc = f"The OpenEXA blog: {len(kept)} posts from {years[0]} to {years[-1]} on AI agents in finance, financial markets research and market structure."
blog_ld = ld(dict(BLOG_LD, description=desc, inLanguage="en", publisher=ORG, blogPost=[
    {"@type": "BlogPosting", "headline": ld_text(p["title"]), "url": BASE + p["slug"] + ".html", "datePublished": p["dt"].strftime("%Y-%m-%d"),
     "author": person(p["author"])} for p in sorted(kept, key=lambda p: p["dt"], reverse=True) if not p["stub"]]),
    crumbs(("Blog", BASE)))
page = head(BASE, "Blog — OpenEXA", desc, "website", f"  {blog_ld}\n", h1=" ".join(INDEX_H1), pic="index").replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n  <base href="/blog/">\n', 1) + f'''
<body data-page="blog" data-nav="dark-start" class="blog-page">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain blog-hero">
      <div class="container blog-hero-grid">
        <div class="blog-hero-copy">
          <h1 class="display-1 blog-h1" data-reveal>{esc(bind(INDEX_H1[0].replace(" ", chr(0xA0)) + " " + INDEX_H1[1]))}</h1>
          {HERO_INDEX}
        </div>
        {LIBRARY}
      </div>
    </section>

{chr(10).join(sections)}

    <section class="cta-band is-dark grain">
      <i class="mark globe" aria-hidden="true"></i>
      <div class="container">
        <h2 class="display-2" data-reveal data-split>The thinking behind the swarm.</h2>
        <div class="row" data-reveal style="--d:120ms">
          <a class="btn" href="{PFX}research.html">Read the research {ARROW}</a>
        </div>
      </div>
    </section>
  </main>

{foot_index}
{after_paint(("site.js", "blog.js"))}
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
# as the article's first figure. Figures keep their own captions (cut, 1 Nov: the added 'Fig. N' labels went).
def post_plate(p):
    """cut (1 Nov): the plate's title line and the quoted sentence under it went (the drawing is the post's idea; the
    title says what the post is). A drawn plate keeps its hedge; the economics collection's mark (rings) has none to keep"""
    econ = p["col"] == "economics" or p["slug"] not in PLATES
    cap = "" if econ else f'\n          <figcaption class="pp-h">{PLATES_HEDGE}</figcaption>'
    return f'''<figure class="post-plate" id="plate">
          <div class="post-plate-art" aria-hidden="true">{plate_svg(p["slug"], p["col"], turn(p))}{REG}</div>{cap}
        </figure>'''
# award a3 (4K inspector, polish; AWARD_BAR L7): the post's hero plate was the site's one box-framed hero plate. It takes
# the hero plates' registration marks (site.css .hp-reg, the same four corners; blog.css places them on the old box)
REG = '<span class="hp-reg" aria-hidden="true"><i></i><i></i><i></i><i></i></span>'
# a long read: words, and a figure as about 150 words of column (the 8 longest posts; the others end within about a screen)
LONG_READ = 600
def long_read(p): return len(plain(p["body"]).split()) + 150 * p["body"].count("<figure") >= LONG_READ
def margin_plate(p):
    """award a3 (art director, medium: "at 1920 the body runs 31-64% with the right 36% empty for about nine screens"):
    on a long read (long_read), from 1440 px the reading grid has three parts, as a note's: the post's wayfinding
    (columns 1-3), the text (4-9) and, sticky beside it, the post's own plate (10-12) on the index's sheet (the same plate
    as the hero's, the same hedge under it; the economics rings carry none, as in the hero). aria-hidden: the hero's plate
    and hedge are the ones read out. It starts half a screen down the column and rises with the text until it sticks
    (blog.css), so one screen never shows the hero's drawing and this one together. A short post ends within about a
    screen: no plate, its a2 layout"""
    if not long_read(p): return ""
    econ = p["col"] == "economics" or p["slug"] not in PLATES
    cap = "" if econ else f'<p class="pp-h">{PLATES_HEDGE}</p>'
    return f'''
          <div class="post-mp" aria-hidden="true"><div class="post-mp-in"><div class="post-mp-art">{plate_svg(p["slug"], p["col"], turn(p))}</div>{cap}</div></div>'''
for p in order:
    if p["stub"]: continue
    if p["col"] != "economics":
        assert p["slug"] in PLATES, (p["slug"], "no plate")
        assert PLATES[p["slug"]][2] in said(p), (p["slug"], "the plate's quote is not the post's own sentence")
    sib = [q for q in by_col[p["col"]] if not q["stub"]]
    i = sib.index(p); prev = sib[i - 1] if i else None; nxt = sib[i + 1] if i + 1 < len(sib) else None
    src_host = re.sub(r"^www\.", "", re.search(r"//([^/]+)", p["source"]).group(1)) if p["source"] else ""
    url = BASE + p["slug"] + ".html"
    post_ld = {"@type": "BlogPosting", "@id": url + "#article", "headline": ld_text(p["title"]), "description": ld_text(p["excerpt"]), "url": url,
               "mainEntityOfPage": url, "datePublished": p["dt"].strftime("%Y-%m-%d"), "inLanguage": "en", "image": [og_image(url)],
               "author": person(p["author"]), "publisher": ORG, "isPartOf": BLOG_LD, "articleSection": LABEL[p["col"]],
               "timeRequired": f"PT{p['minutes']}M"}
    if p["source"]: post_ld["isBasedOn"] = p["source"]
    # cut (1 Nov): the side column went (its links repeated the crumb, the pager and the article end: "N posts in this
    # collection", "All 29 posts", "The original on <host>", "The papers on Google Scholar", and the series list, which
    # the crumb and the pager now carry)
    hero_img = (f'<figure class="blog-hero-img"{fig_cap(p["hero_file"])}><img src="{PFX}assets/img/blog/{p["hero_file"]}"{body_srcset(p["hero_file"])} alt=""{size(p["hero_file"])}{body_cap(p["hero_file"])} decoding="async"></figure>\n            '
                if p.get("hero_file") and p["slug"] in KEEP_HERO else "")
    # the pager: where it goes and the title (cut: the dates under the titles, and the end cards' second lines)
    pcard = lambda cls, url, k, h: f"<a class='pager-card {cls}' href='{url}'><span class='k'>{k}</span><h3>{h}</h3></a>"
    pager = "".join([
        pcard("prev", f"{prev['slug']}.html", "← Newer", post_title(prev["title"])) if prev else pcard("prev", "index.html", "← The blog", f"All {len(kept)} posts"),
        pcard("next", f"{nxt['slug']}.html", "Older →", post_title(nxt["title"])) if nxt else pcard("next", f"{PFX}research.html", "Research →", "The thinking behind the swarm."),
    ])
    # the crumb: the way back to the blog; a series post names its series and its place in it there (the rail's words)
    crumb = ""
    if p["slug"] in SERIES_POS:
        j = SERIES_POS[p["slug"]]; part = SERIES[j][1]
        crumb = f' · <a href="index.html#series">{SERIES_NAME}</a> · {esc(part)}'
        sp = SLUGS[SERIES[j - 1][0]] if j else None; sn = SLUGS[SERIES[j + 1][0]] if j + 1 < len(SERIES) else None
        pager = "".join([
            pcard("prev", f"{sp['slug']}.html", f"← {part_name(j - 1)}", post_title(sp["title"])) if sp else pcard("prev", "index.html#series", "← The blog", f"{SERIES_NAME}."),
            pcard("next", f"{sn['slug']}.html", f"{part_name(j + 1)} →", post_title(sn["title"])) if sn else pcard("next", f"{PFX}research.html", "Research →", "The thinking behind the swarm."),
        ])
        post_ld["isPartOf"] = [BLOG_LD, {"@type": "CreativeWorkSeries", "name": f"{SERIES_NAME} — OpenEXA Blog", "url": BASE + "#series"}]
        post_ld["position"] = j + 1
    # cut (1 Nov): "Originally published on openexa.com, <date>." (C-147: likely false for the pre-2023 posts) and the
    # separate "The original on <host>" link. A post that summarises work published elsewhere keeps saying so, with the link
    original = (f'<p class="ps-src">A summary of work first published on <a href="{esc(p["source"])}" target="_blank" rel="noopener">{esc(src_host)}{OUTB}</a>.</p>'
                if p["source"] else "")
    # award a1 (art director, big; AWARD_BAR post 2): the reading column's left side carries the post's wayfinding, as a
    # note's "In this note" does, so posts and notes are one long-read template. The bodies have no section heads to
    # list (one h2 in 29 posts), so: the Gen-AI series as an upright rail (the index rail's grammar: a node per part,
    # the part being read filled green), on the series' four posts and on Ajit's fifth (no part filled there); and where
    # the post summarises work published elsewhere, that line, moved here from the article's end so it is read first.
    # In the source it follows the article (keyboard order = reading order); placed beside it from 961 px and sticky;
    # on tablets and phones the line follows the article as before and the rail is left to the crumb and the pager
    side = ""
    if p["col"] == "ai":
        rail_ = "".join(
            (f'<li class="is-on"><span aria-current="page">{part_name(i)}</span></li>' if s == p["slug"]
             else f'<li><a href="{s}.html">{part_name(i)}</a></li>') for i, (s, _, _) in enumerate(SERIES))
        side += f'<nav class="ps-series" aria-label="{SERIES_NAME}"><p class="ps-k">{SERIES_NAME}</p><ol class="ps-rail" role="list">{rail_}</ol></nav>'
    side += original
    # (a post whose column holds the series alone shows nothing there on tablets and phones: no empty row after the text)
    side = f'''
          <div class="post-side{'' if original else ' post-side--nav'}"><div class="ps-in">{side}</div></div>''' if side else ""
    byline = f'<a href="{PFX}company.html#{PEOPLE_ID[person(p["author"])["name"]]}">{esc(shown(p["author"]))}</a>' if person(p["author"]).get("name") in PEOPLE_ID else esc(shown(p["author"]))
    # r4-copy (r3 point 12): what search results and link previews show is set as the H1 is (’, and the house dash with a
    # no-break space before it); JSON-LD and the feed keep the title as published
    # award a1 (a1-dev 23): the series is a sequence for crawlers too: rel prev / next between its four parts (isPartOf
    # is already the CreativeWorkSeries, with its position)
    rel_links = ""
    if p["slug"] in SERIES_POS:
        j = SERIES_POS[p["slug"]]
        if j: rel_links += f'  <link rel="prev" href="{BASE}{SERIES[j - 1][0]}.html">\n'
        if j + 1 < len(SERIES): rel_links += f'  <link rel="next" href="{BASE}{SERIES[j + 1][0]}.html">\n'
    article = hero_img + lead(hang(marks_in_em(bare_marks(smart_html(p["body"])))))
    # award a4 (a4-ux medium, a4-design polish): a long read with figures loads blog.js for one thing, the margin
    # plate's rest while a figure is on screen (blog.js; the other posts load no script of their own)
    post_js = ("site.js",) + (("blog.js",) if long_read(p) and "<figure" in article else ())
    page = head(url, f'{smart(p["title"])} — OpenEXA Blog', smart(META_DESC.get(p["slug"], p["excerpt"])), "article", f'  {ld(post_ld, crumbs(("Blog", BASE), (ld_text(p["title"]), url)))}\n',
                h1=ld_text(p["title"]), links=rel_links, italic=sets_italic(article)) + f'''
<body data-page="post" data-nav="dark-start" class="article-page blog-post">
  <a class="skip" href="#main">Skip to content</a>

{nav}
  <main id="main">
    <section class="page-hero page-hero--dark is-dark grain article-hero blog-post-hero">
      <div class="container post-hero">
        <div class="post-hero-copy">
          <p class="post-crumb" data-reveal><a href="index.html">Blog</a>{crumb}</p>
          <h1 class="display-2 article-title blog-title" data-reveal>{post_title(p["title"])}</h1>
          <p class="post-byline" data-reveal>{byline}<span><time datetime="{iso(p)}">{fmt(p["dt"])}</time></span><span>{p["minutes"]}&nbsp;min read</span></p>
        </div>
        {post_plate(p)}
      </div>
    </section>

    <section class="section article-body-section">
      <div class="container">
        <div class="grid{' has-mp' if long_read(p) else ''}">
          <article class="col-7 article blog-article">
            {article}
            <div class="article-end"><span class="mark" aria-hidden="true"></span></div>
          </article>{side}{margin_plate(p)}
        </div>
      </div>
    </section>

    <section class="section is-paper-2 section--tight">
      <div class="container"><h2 class="sr-only">More posts</h2><div class="pager">{pager}</div></div>
    </section>
  </main>

{foot}
{after_paint(post_js)}
</body>
</html>
'''
    write(OUT / f'{p["slug"]}.html', page)
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
# award a4 (a4-dev polish 11): the bar, the footer and the share card say "Proof"; the page's file is evidence.html (its
# old route, /status, above). A visitor who types the name gets the page, not the 404
ALIASES = [("/proof", "/evidence"), ("/proof.html", "/evidence")]
routes = [rd(src, dst) for src, dst in OLD_PAGES + ALIASES]
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
    # award a2 (a2-dev polish 18; system's request ~23:30, with system's consent to the header change): HTTPS only, for a
    # year. No includeSubDomains and no preload: those commit every subdomain and the browsers' lists, the owner's call
    "Strict-Transport-Security": "max-age=31536000",
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
for src, dst in ALIASES: rules.append(f"{src}  {dst}  301")
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
