"""Social cards: one 1200x630 Open Graph image per page, in the style of the original assets/img/og.png.

For every page in the sitemap (top-level pages, research notes, the blog index and posts) renders a card: the page's
<h1> as the headline (the homepage's .thin phrase in signal green; an <em> stays white italic, as on the site), its
og:description as the sub-line, a mono kicker naming the section, over the dark field and dotted globe of the brand
mark, set in the site's own fonts. Rendered in headless Chromium (Playwright) and saved as JPEG to
site/assets/img/og/<page path with / as ->.jpg; launch_meta_v9.py, build_research.py and build_blog.py point each page's
og:image / twitter:image there. No names appear on a card (people stay on Company and in blog bylines).
award a1 (system): the four pages with an engraved hero plate (Platform's stack, Lifecycles' rings, Proof's ten ticks,
Trust's Council) carry that plate on their card, cut from the page itself and drawn with the site's own stylesheets
(finished state: reduced motion), in place of the dotted globe every other card keeps; its hedge ("Schematic") rides
under it. PLATE_ALT is the picture's description, the plate's own aria-label (launch_meta_v9.py writes og:image:alt).
award a2 (system): every other card carries its page's own drawing too, cut from the page as the page draws it without
script: Research its library still, the blog index its open book, Company its plate still, each note its formation still,
each post its own plate; Home and Access (no drawing of their own in the first screen) the site's fine-dot globe (the chunky
globe.svg was off the mark). STILL_ALT describes each for og:image:alt.
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
    return {"rel": rel, "kicker": kicker, "headline": headline(s), "sub": sub, "foot": foot, "plate": plate(rel), "still": still(rel),
            "hedge": still_hedge(rel)}

# award a1: the cards that carry their page's hero plate; group sheet and the data-page their selectors key on
PLATE_PAGES = {"platform.html": ("platform", "platform.css"), "lifecycles.html": ("lifecycles", "platform.css"),
               "evidence.html": ("proof", "proof.css"), "trust.html": ("trust", "proof.css")}
CSS = (ROOT / "assets" / "css")

def plate(rel):
    """The page's hero plate (its <figure class="hero-plate ...">), as on the page: the drawing and its labels, the
    hedge kept, the controls (Replay) and the key left out. '' for a page without one."""
    if rel not in PLATE_PAGES: return ""
    s = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r'<figure class="hero-plate[^"]*"[^>]*>.*?</figure>', s, re.S)
    if not m: return ""
    f = m.group(0)
    f = re.sub(r'<button\b[^>]*>.*?</button>', "", f, flags=re.S)
    f = re.sub(r'<span class="hp-key"[^>]*>.*?</span></span></span>', "", f, flags=re.S)
    f = re.sub(r'<span class="sr-only"[^>]*>.*?</span>', "", f, flags=re.S)
    f = re.sub(r'\s(?:data-reveal|data-plate-replay)(?:="[^"]*")?', "", f)
    if rel == "evidence.html": f = '<div class="pf-record">' + f + "</div>"
    return f

def plate_alt(rel):
    """The plate's own description (its aria-label), for the card's alt text; '' without a plate."""
    if rel not in PLATE_PAGES: return ""
    s = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r'<figure class="hero-plate[^"]*"[^>]*\baria-label="([^"]*)"', s)
    return H.unescape(m.group(1)) if m else ""

# award a2: the page's own still drawing (the svg the page shows before and without WebGL), its sheet and the selectors'
# context. (cut, sheet, data-page, body class). Posts: the post's own plate; notes: the note's formation still.
def still_spec(rel):
    if rel in PLATE_PAGES: return None
    if rel == "research.html": return ("rs-still", "research.css", "research", "")
    if rel == "company.html": return ("plate-still", "company.css", "company", "")
    if rel == "blog/index.html": return ("lib-art", "blog.css", "blog", "blog-page")
    if rel.startswith("research/"): return ("fs-still", "research.css", "note", "")
    if rel.startswith("blog/"): return ("bp-art", "blog.css", "post", "blog-post")
    return None

def still(rel):
    """The page's still drawing as the card shows it, '' where the card keeps the fine-dot globe."""
    spec = still_spec(rel)
    if not spec: return ""
    s = (ROOT / rel).read_text(encoding="utf-8")
    m = re.search(r'<svg class="%s[^"]*"[^>]*>.*?</svg>' % spec[0], s, re.S)
    if not m: return ""
    svg = re.sub(r"</?a[^>]*>", "", m.group(0))  # the open book's leaves are links on the page: on a card, a drawing
    return svg

def still_hedge(rel):
    """The hedge the page sets beside the drawing ("Illustrative", "Illustrative · heights not to scale"): a card keeps it
    under the still, as the plate cards keep "Schematic". '' where the page sets none (the blog's book and plates)."""
    spec = still_spec(rel)
    if not spec: return ""
    s = (ROOT / rel).read_text(encoding="utf-8")
    m = (re.search(r'company-readout">.*?class="fc-h">([^<]*)<', s, re.S) if rel == "company.html"
         else re.search(r'figcap-h">([^<]*)<', s) if spec[0] in ("rs-still", "fs-still") else None)
    return H.unescape(m.group(1)).strip() if m else ""

# what each still shows, for og:image:alt (launch_meta_v9 for the top pages; build_research and build_blog for theirs)
STILL_ALT = {"research.html": "the page’s library figure, the notes drawn as stippled leaves",
             "company.html": "the page’s figure, a dotted sphere in its rings",
             "blog/index.html": "the page’s open book, one leaf for each collection"}

def pages():
    out = list(TOP)
    out += sorted("research/" + p.name for p in (ROOT / "research").glob("*.html"))
    out += ["blog/index.html"] + sorted("blog/" + p.name for p in (ROOT / "blog").glob("*.html") if p.name != "index.html")
    return out

FONT = (ROOT / "assets" / "fonts").as_uri()
# inlined: Chromium won't use a file:// image as a CSS mask (masks are CORS fetches)
GLOBE = "data:image/svg+xml;base64," + base64.b64encode((ROOT / "assets" / "img" / "globe.svg").read_bytes()).decode("ascii")
# a2: the field's globe is the site's own fine-dot mark (the CTA band's and the overture's static globe), not the chunky one
FINE = "data:image/svg+xml;base64," + base64.b64encode((ROOT / "assets" / "img" / "globe-fine.svg").read_bytes()).decode("ascii")
TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">%(links)s<style>
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
.globe { position: absolute; left: 790px; top: 40px; width: 550px; height: 550px; background: url(%(FG)s) center / contain no-repeat, url(%(FG)s) center / contain no-repeat; } /* twice: the mark's hairlines at the old globe's presence */
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
/* award a1: a plate card: the copy keeps 600 px, the page's own hero plate stands in the right-hand field */
.has-plate .copy { width: 590px; }
.has-plate .s { width: 590px; }
.card-plate { position: absolute; left: 700px; top: 118px; width: 440px; height: 410px; display: flex; flex-direction: column; justify-content: center; font-family: 'Inter', sans-serif; }
.card-plate .hero-plate, .card-plate .pf-record { width: 100%% !important; max-width: none !important; margin: 0 !important; }
.card-plate .hp-cap { margin-top: 10px; }
.card-plate .hp-cap .fc-h { font-size: 15px; text-align: left; color: rgba(245,242,236,.56); }
.card-plate .pf-record::before { content: none; } /* a2: Proof's record line runs edge to edge on the H1's baseline; a card has no such baseline (it struck through the headline) */
/* a2: a still card: the page's drawing in the right-hand field, where the globe was; the copy keeps its 700 px */
.card-still { position: absolute; left: 800px; top: 112px; width: 344px; height: 420px; display: grid; place-items: center; }
.card-still > svg { position: static !important; inset: auto !important; width: 100%% !important; height: 100%% !important; scale: 1 !important; opacity: 1 !important; overflow: visible; }
.card-still.is-wide { left: 784px; width: 392px; }
.card-hedge { position: absolute; left: 800px; top: 538px; font-size: 15px; color: rgba(245,242,236,.56); }

</style></head><body%(bodyattr)s>
%(art)s
<div class="top"><i class="m"></i><span class="w">OpenEXA</span><i class="sep"></i><span class="k">%(kicker)s</span></div>
<div class="copy"><h1 class="h">%(headline)s</h1><p class="s">%(sub)s</p></div>
%(plate)s
<div class="foot"><span><i></i>%(foot)s</span><span>openexa.com</span></div>
<script>
  // measured once the faces are in: the largest headline size that fits in three lines (four once it is small); a sub-line
  // written to fit two lines stays whole (the headline gives up a little size for it, never under 72 px); a longer one
  // takes the height left, up to three lines, cut at a word with an ellipsis (never mid-word, never "...")
  document.fonts.ready.then(() => {
    // a2: a still is fitted to what it draws (its viewBox becomes the drawing's own box, a 4 per cent margin), so every page's
    // drawing fills the field whatever room its page gave it
    document.querySelectorAll('.card-still > svg').forEach((svg) => {
      const b = svg.getBBox(), m = Math.max(b.width, b.height) * .04;
      if (b.width > 0 && b.height > 0) { svg.setAttribute('viewBox', [b.x - m, b.y - m, b.width + 2 * m, b.height + 2 * m].join(' ')); svg.setAttribute('preserveAspectRatio', 'xMidYMid meet'); }
      // its hedge sits under the drawing's own lower-left corner, as "Schematic" does under a plate
      const hedge = document.querySelector('.card-hedge'), r = svg.getBoundingClientRect(), a = (b.width + 2 * m) / (b.height + 2 * m);
      if (hedge && b.width > 0) {
        const w = Math.min(r.width, r.height * a), hh = w / a;
        hedge.style.left = (r.left + (r.width - w) / 2) + 'px'; hedge.style.top = Math.min(548, r.top + (r.height + hh) / 2 + 10) + 'px';
      }
    });
    const h = document.querySelector('.h'), s = document.querySelector('.s'), box = document.querySelector('.copy');
    const lh = 25 * 1.4, set = (v) => { size = v; h.style.fontSize = v + 'px'; };
    let size = 96; set(96);
    const lines = () => Math.round(h.getBoundingClientRect().height / size);
    const room = () => Math.floor((box.clientHeight - h.getBoundingClientRect().height - 30) / lh);
    while (size > 44 && (lines() > (size > 70 ? 3 : 4) || h.scrollWidth > h.clientWidth)) set(size - 2);
    const need = Math.round(s.getBoundingClientRect().height / lh);
    // a plate card's copy is narrower (590 px): its sub-line stays whole up to three lines, the headline giving way to 60 px
    const plate = document.body.classList.contains('has-plate');
    if (need <= 2 || (plate && need <= 3)) while (size > (plate ? 60 : 72) && room() < need) set(size - 2);
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
        spec = still_spec(c["rel"]) if c["still"] else None
        sheets = "".join((CSS / f).read_text(encoding="utf-8") for f in (["site.css", PLATE_PAGES[c["rel"]][1]] if c["plate"] else ["site.css", spec[1]] if spec else []))
        c["key"] = hashlib.sha256((TEMPLATE + GLOBE + FINE + sheets + json.dumps(c, sort_keys=True)).encode("utf-8")).hexdigest()[:16]
        if cache.get(c["rel"]) != c["key"] or not (OUT / og_name(c["rel"])).exists(): todo.append(c)
    if todo:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            # reduced motion: a plate is drawn finished (its draw-in runs only for motion)
            pg = await browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1, reduced_motion="reduce")
            for c in todo:
                fill = {k: (c[k] if k == "headline" else H.escape(c[k], quote=False)) for k in ("kicker", "headline", "sub", "foot")}
                if c["plate"]:
                    page, sheet = PLATE_PAGES[c["rel"]]
                    links = "".join(f'<link rel="stylesheet" href="{(CSS / f).as_uri()}">' for f in ("site.css", sheet))
                    extra = dict(links=links, bodyattr=f' class="has-plate" data-page="{page}"', art='<div class="glow"></div>',
                                 plate=f'<div class="card-plate is-dark" style="background:none">{c["plate"]}</div>')
                elif c["still"]:
                    cut, sheet, page, bcls = still_spec(c["rel"])
                    links = "".join(f'<link rel="stylesheet" href="{(CSS / f).as_uri()}">' for f in ("site.css", sheet))
                    wide = (" is-wide" if cut in ("lib-art", "bp-art") else "") + " k-" + cut
                    extra = dict(links=links, bodyattr=f' class="has-still {bcls}" data-page="{page}"', art='<div class="glow"></div>',
                                 plate=f'<div class="card-still is-dark{wide}" style="background:none">{c["still"]}</div>'
                                       + (f'<p class="card-hedge">{H.escape(c["hedge"], quote=False)}</p>' if c["hedge"] else ""))
                else:
                    extra = dict(links="", bodyattr="", art='<div class="glow"></div><div class="globe"></div>', plate="")
                src = SHOTS / "og-card.html"
                src.write_text(TEMPLATE % dict(fill, F=FONT, G=GLOBE, FG=FINE, **extra), encoding="utf-8")
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

# importable (proof's a3 request: previewing a card imported this module and re-rendered every stale card)
if __name__ == "__main__":
    asyncio.run(main())
