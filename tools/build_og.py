"""Social cards: one 1200x630 Open Graph image per page, in the style of the original assets/img/og.png.

For every page in the sitemap (top-level pages, research notes, the blog index and posts) renders a card: the page's
<h1> as the headline (the homepage's .thin phrase in signal green; an <em> stays white italic, as on the site), its
og:description as the sub-line, a mono kicker naming the section, over the dark field and dotted globe of the brand
mark, set in the site's own fonts. Rendered in headless Chromium (Playwright) and saved as JPEG to
site/assets/img/og/<page path with / as ->.jpg; launch_meta_v9.py, build_research.py and build_blog.py point each page's
og:image / twitter:image there. No names appear on a card (people stay on Company and in blog bylines).
Run last, after the other builders. Cards are cached by a hash of their inputs (data/og_cards.json), so a rerun only
re-renders the pages whose headline, description or kicker changed and leaves every other JPEG byte-identical.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE, og_name
import asyncio, base64, hashlib, html as H, io, json, re
from pathlib import Path
from PIL import Image
from playwright.async_api import async_playwright

ROOT = Path(str(SITE))
OUT = ROOT / "assets" / "img" / "og"
CACHE = Path(str(DATA)) / "og_cards.json"
TOP = {"index.html": "Agent swarms", "platform.html": "Platform", "lifecycles.html": "Lifecycles", "evidence.html": "Proof",
       "trust.html": "Trust & governance", "research.html": "Research", "company.html": "Company", "access.html": "Request access"}
TAGLINE = "An AI agentic company · Lifecycle 01 live on real capital"  # v2x: the CEO's descriptor; C-009's status wording
# v2x r2 (copy): each top-level card has its own sub-line, written to fit two lines and taken from the page's own words
# (no claim stronger than the page; the foot already says Lifecycle 01 is live). Notes and posts keep their og:description,
# clamped at a word boundary with an ellipsis.
SUB = {"index.html": "A lifecycle runs from the first signal to a record a regulator can audit.",
       "platform.html": "A typed schema between the agents that decide and the code that executes.",
       "lifecycles.html": "In between, it is multi-party, regulated, structured, exception-heavy, gated and audit-bound.",
       "evidence.html": "Lifecycle 01: a limited proof of concept on live capital. Not a forecast.",
       "trust.html": "Custody never moves, and every transition is written to a ledger you can replay.",
       "research.html": "Ten notes on the research behind swarm-based agentic lifecycles.",
       "company.html": "We build the end-to-end infrastructure on which swarms of domain-specific AI agents run the world’s high-value lifecycles.",
       "access.html": "Four paths. This page writes the email from what you enter."}

def text(s): return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
# v2x r2 (integrate): the pages write a display hyphen as <span class="hy">-</span> (system r2, a11y); text() turns tags into
# spaces, which printed "Post - Training" on seven cards: the span is unwrapped first, so the card reads "Post-Training"
def unhy(s): return re.sub(r'<span class="hy">([^<]*)</span>', lambda m: m.group(1), s)
def meta(s, prop):
    m = re.search(r'<meta property="%s" content="([^"]*)">' % re.escape(prop), s)
    return H.unescape(m.group(1)) if m else ""

def headline(s):
    """The page's <h1>, keeping only what the card styles: .thin (green), <em> (italic) and .hy (the serif hyphen, set tight
    as on the page: a bare U+002D in Instrument Serif reads as an en dash, "Gen–AI"; r5)."""
    h = re.sub(r'<span class="hy">([^<]*)</span>', lambda m: "\x06" + m.group(1) + "\x07", re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S).group(1))
    h = re.sub(r'<span class="nowrap">(.*?)</span>', lambda m: m.group(1).replace(" ", "\x05"), h, flags=re.S)  # the page's own unbreakable phrases
    h = re.sub(r'<span class="thin">(.*?)</span>', lambda m: "\x01" + m.group(1) + "\x02", h, flags=re.S)
    h = re.sub(r"<em>(.*?)</em>", lambda m: "\x03" + m.group(1) + "\x04", h, flags=re.S)
    h = H.escape(text(h), quote=False)
    return (h.replace("\x01", '<span class="g">').replace("\x02", "</span>").replace("\x03", "<em>").replace("\x04", "</em>").replace("\x05", "\u00a0")
            .replace("\x06", '<span class="hy">').replace("\x07", "</span>"))

def note_kicker(rel):
    """A note's card kicker, "Research · Note 03 of 10 · Series, part 1 of 8". The notes' eyebrow said this until the 1 Nov
    cut took it off the page (cut-research); the card keeps it, derived from the site itself: the notes in file order and
    the series as the research index lists it (its #series section), so the cards stay byte-identical."""
    notes = sorted(p.name for p in (ROOT / "research").glob("*.html"))
    name = rel.split("/", 1)[1]
    k = f"Research · Note {notes.index(name) + 1:02d} of {len(notes)}"
    m = re.search(r'<section\b[^>]*\bid="series"[^>]*>(.*?)</section>', (ROOT / "research.html").read_text(encoding="utf-8"), re.S)
    series = list(dict.fromkeys(re.findall(r'href="research/([^"#]+\.html)"', m.group(1)))) if m else []
    return k + (f" · Series, part {series.index(name) + 1} of {len(series)}" if name in series else "")

def card(rel):
    s = (ROOT / rel).read_text(encoding="utf-8")
    mins = re.search(r"(\d+)(?:\s|&nbsp;)min read", s)  # v2x: the pages tie the number to "min" with a no-break space
    if rel in TOP:
        kicker, foot = TOP[rel], TAGLINE
    elif rel.startswith("research/"):
        kicker = note_kicker(rel)
        foot = "OpenEXA Research" + (f" · {mins.group(1)} min read" if mins else "")
    elif rel == "blog/index.html":
        kicker, foot = "Blog", "OpenEXA Blog · AI agents · Markets research · Market structure"
    else:
        kicker = "Blog"
        foot = "OpenEXA Blog" + (f" · {mins.group(1)} min read" if mins else "")
    # v2x: a description that opens with the page's h1 (Lifecycles) would print it twice; the sub-line starts after it
    flat = lambda x: x.replace("‐", "-").replace(" ", " ")
    sub, h1 = meta(s, "og:description"), flat(text(unhy(re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S).group(1))))
    if flat(sub).startswith(h1) and len(sub) > len(h1): sub = sub[len(h1):].lstrip()
    sub = SUB.get(rel, sub)
    return {"rel": rel, "kicker": kicker, "headline": headline(s), "sub": sub, "foot": foot}

def pages():
    out = list(TOP)
    out += sorted("research/" + p.name for p in (ROOT / "research").glob("*.html"))
    out += ["blog/index.html"] + sorted("blog/" + p.name for p in (ROOT / "blog").glob("*.html") if p.name != "index.html")
    return out

FONT = (ROOT / "assets" / "fonts").as_uri()
# inlined: Chromium won't use a file:// image as a CSS mask (masks are CORS fetches)
GLOBE = "data:image/svg+xml;base64," + base64.b64encode((ROOT / "assets" / "img" / "globe.svg").read_bytes()).decode("ascii")
TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@font-face { font-family: 'Instrument Serif'; font-style: normal; src: url(%(F)s/instrument-serif-400-latin.woff2); }
@font-face { font-family: 'Instrument Serif'; font-style: italic; src: url(%(F)s/instrument-serif-400i-latin.woff2); }
@font-face { font-family: 'Inter'; font-weight: 400 600; src: url(%(F)s/inter-var-latin.woff2); }
@font-face { font-family: 'IBM Plex Mono'; font-weight: 400; src: url(%(F)s/ibm-plex-mono-400-latin.woff2); }
* { box-sizing: border-box; margin: 0; }
html, body { width: 1200px; height: 630px; overflow: hidden; }
body { position: relative; background: #0E1512; color: #F5F2EC; font-family: 'Inter', sans-serif; -webkit-font-smoothing: antialiased; }
.glow { position: absolute; left: 520px; top: -165px; width: 960px; height: 960px; border-radius: 50%%;
  background: radial-gradient(closest-side, rgba(30,122,90,.30), rgba(30,122,90,.10) 52%%, rgba(14,21,18,0) 100%%); }
.disc { position: absolute; left: 690px; top: 105px; width: 420px; height: 420px; border-radius: 50%%; background: rgba(9,15,12,.55); }
.globe { position: absolute; left: 808px; top: 58px; width: 514px; height: 514px; background: rgba(245,242,236,.52);
  -webkit-mask: url(%(G)s) center / contain no-repeat; }
.top { position: absolute; left: 72px; top: 62px; display: flex; align-items: center; gap: 14px; }
.top .m { width: 40px; height: 40px; background: rgba(245,242,236,.78); -webkit-mask: url(%(G)s) center / contain no-repeat; }
.top .w { font-family: 'Instrument Serif'; font-size: 36px; letter-spacing: -.01em; }
.top .sep { width: 1px; height: 18px; background: rgba(245,242,236,.32); margin: 0 8px 0 10px; }
.k, .foot { font-family: 'IBM Plex Mono', monospace; font-size: 14px; letter-spacing: .17em; text-transform: uppercase; color: #9A9EA0; }
.copy { position: absolute; left: 72px; top: 168px; width: 700px; height: 372px; display: flex; flex-direction: column; justify-content: flex-start; }
.h { font-family: 'Instrument Serif', serif; font-weight: 400; line-height: 1; letter-spacing: -.012em; text-wrap: balance; }
.h .g { color: #4FCB93; }
.h em { font-style: italic; }
.h .hy { margin-inline: -.045em; }
.s { margin-top: 30px; width: 640px; font-size: 25px; line-height: 1.4; color: rgba(245,242,236,.78); text-wrap: pretty; }
.foot { position: absolute; left: 72px; right: 72px; bottom: 48px; display: flex; justify-content: space-between; }
.foot i { display: inline-block; width: 7px; height: 7px; border-radius: 50%%; background: #4FCB93; margin-right: 14px; vertical-align: 2px; }
</style></head><body>
<div class="glow"></div><div class="disc"></div><div class="globe"></div>
<div class="top"><i class="m"></i><span class="w">OpenEXA</span><i class="sep"></i><span class="k">%(kicker)s</span></div>
<div class="copy"><h1 class="h">%(headline)s</h1><p class="s">%(sub)s</p></div>
<div class="foot"><span><i></i>%(foot)s</span><span>openexa.com</span></div>
<script>
  // measured once the faces are in: the largest headline size that fits in three lines (four once it is small); a sub-line
  // written to fit two lines stays whole (the headline gives up a little size for it, never under 72 px); a longer one
  // takes the height left, up to three lines, cut at a word with an ellipsis (never mid-word, never "...")
  document.fonts.ready.then(() => {
    const h = document.querySelector('.h'), s = document.querySelector('.s'), box = document.querySelector('.copy');
    const lh = 25 * 1.4, set = (v) => { size = v; h.style.fontSize = v + 'px'; };
    let size = 96; set(96);
    const lines = () => Math.round(h.getBoundingClientRect().height / size);
    const room = () => Math.floor((box.clientHeight - h.getBoundingClientRect().height - 30) / lh);
    while (size > 44 && (lines() > (size > 70 ? 3 : 4) || h.scrollWidth > h.clientWidth)) set(size - 2);
    const need = Math.round(s.getBoundingClientRect().height / lh);
    if (need <= 2) while (size > 72 && room() < need) set(size - 2);
    const n = Math.max(0, Math.min(3, room()));
    if (n === 0) s.remove();
    else if (need > n) {
      const full = s.textContent, words = full.split(' ');
      while (words.length > 1 && s.getBoundingClientRect().height > n * lh + 1) { words.pop(); s.textContent = words.join(' ').replace(/[ ,;:·—–-]+$/, '') + '…'; }
      // a whole sentence that fits reads better than a clipped one ("… any particular product. It…"): take the longest
      // that fits when it keeps at least half of the clipped text (a sentence end: lower-case letter or digit, then a capital)
      const cut = s.textContent, fits = (t) => { s.textContent = t; return s.getBoundingClientRect().height <= n * lh + 1; };
      const whole = [...full.matchAll(/[a-z0-9)’”][.?!](?=\\s+[A-Z“‘])/g)].map(m => full.slice(0, m.index + 2)).reverse().find(fits);
      s.textContent = whole && whole.length >= cut.length / 2 ? whole : cut;
    }
    document.body.dataset.ready = '1';
  });
</script>
</body></html>"""

async def main():
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)
    cards = [card(p) for p in pages()]
    todo = []
    for c in cards:
        c["key"] = hashlib.sha256((TEMPLATE + GLOBE + json.dumps(c, sort_keys=True)).encode("utf-8")).hexdigest()[:16]
        if cache.get(c["rel"]) != c["key"] or not (OUT / og_name(c["rel"])).exists(): todo.append(c)
    if todo:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            pg = await browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            for c in todo:
                fill = {k: (c[k] if k == "headline" else H.escape(c[k], quote=False)) for k in ("kicker", "headline", "sub", "foot")}
                src = SHOTS / "og-card.html"
                src.write_text(TEMPLATE % dict(fill, F=FONT, G=GLOBE), encoding="utf-8")
                await pg.goto(src.as_uri()); await pg.wait_for_selector("body[data-ready]")
                img = Image.open(io.BytesIO(await pg.screenshot(type="png"))).convert("RGB")
                img.save(OUT / og_name(c["rel"]), "JPEG", quality=90, subsampling=0, optimize=True, progressive=True)
                cache[c["rel"]] = c["key"]
                print("card ->", og_name(c["rel"]))
            await browser.close()
    live = {og_name(c["rel"]) for c in cards}
    for stale in OUT.glob("*.jpg"):
        if stale.name not in live: stale.unlink(); print("removed", stale.name)
    cache = {c["rel"]: cache[c["rel"]] for c in cards}
    CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(cards)} cards, {len(todo)} rendered")

asyncio.run(main())
