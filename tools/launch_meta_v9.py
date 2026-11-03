import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE, og_image
from meta import HOME, ORG, WEBSITE, FEED_LINKS, ROBOTS, ld, crumbs, lastmod, save_lastmod
# -*- coding: utf-8 -*-
"""Launch metadata for the OpenEXA site: canonical + Open Graph + Twitter tags, manifest, icons, JSON-LD,
robots.txt, sitemap.xml and a branded 404 page (header/footer templated from index.html).
Also: each top-level page's schema.org graph (<script id="ld-page">; research.html's is build_research.py's), the feed
links and robots preview hint in every head, sitemap lastmod (data/lastmod.json, see meta.py), and /favicon.ico from the 512 px icon."""
import os, re, io, glob, html, json
from PIL import Image

ROOT = str(SITE)
SITE = "https://www.openexa.com/"
def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)

def meta(s, name, prop=False):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % ("property" if prop else "name", re.escape(name)), s)
    return m.group(1) if m else ""

KIND = {"company.html": "AboutPage", "access.html": "ContactPage"}
CRUMB = {"platform.html": "Platform", "lifecycles.html": "Lifecycles", "evidence.html": "Proof", "trust.html": "Trust & governance",
         "company.html": "Company", "access.html": "Request access"}
def card_alt(s, name=""):
    """award a1: the share card's alt text describes the card (build_og.py): the page's headline, then its picture, the
    page's hero plate in the plate's own words (its aria-label), else the dotted globe of the mark."""
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    h1 = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h1.group(1)))).replace("‐", "-").strip() if h1 else ""
    m = re.search(r'<figure class="hero-plate[^"]*"[^>]*\baria-label="([^"]*)"', s)
    pic = html.unescape(m.group(1)).strip() if m else ""
    pic = "Beside it, the page’s plate: " + pic[0].lower() + pic[1:] if pic else STILL_PIC.get(name, "Beside it, the dotted globe of the OpenEXA mark")
    return (h1 + " " if h1 else "") + (pic if pic.endswith(".") else pic + ".")
# award a2: the cards of Research and Company carry their page's own still (build_og.py); Home and Access keep the globe
STILL_PIC = {"research.html": "Beside it, the page’s library figure: the notes as an open book of stippled leaves",
             "company.html": "Beside it, the page’s figure, the swarm as one body: a dotted sphere inside its rings"}

pages = []
for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
    name = os.path.basename(path)
    if name in ("404.html", "insights.html"): continue
    s = read(path); before = s
    s = re.sub(r'\n  <link rel="canonical".*?<link rel="manifest" href="site.webmanifest">', "", s, flags=re.S)  # idempotent
    s = re.sub(r'\n  <script type="application/ld\+json" id="ld-page">.*?</script>', "", s, flags=re.S)
    s = re.sub(r'\n  <script type="application/ld\+json">{"@context":"https://schema.org","@type":"Organization".*?</script>', "", s, flags=re.S)  # pre-graph home JSON-LD
    title = html.unescape(re.search(r"<title>(.*?)</title>", s, re.S).group(1)).strip()
    desc = meta(s, "description")
    url = SITE if name == "index.html" else SITE + name
    og_title = meta(s, "og:title", True) or title
    og_desc = meta(s, "og:description", True) or desc
    block = [
        f'<link rel="canonical" href="{url}">',
        f'<meta property="og:url" content="{url}">',
        '<meta property="og:site_name" content="OpenEXA">',
    ]
    if not meta(s, "og:type", True): block.append('<meta property="og:type" content="website">')
    if not meta(s, "og:title", True): block.append(f'<meta property="og:title" content="{html.escape(og_title, quote=True)}">')
    if not meta(s, "og:description", True): block.append(f'<meta property="og:description" content="{html.escape(og_desc, quote=True)}">')
    block += [
        f'<meta property="og:image" content="{og_image(url)}">',
        f'<meta property="og:image:alt" content="{html.escape(card_alt(s, name), quote=True)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:locale" content="en_US">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{html.escape(og_title, quote=True)}">',
        f'<meta name="twitter:description" content="{html.escape(og_desc, quote=True)}">',
        f'<meta name="twitter:image" content="{og_image(url)}">',
        f'<meta name="twitter:image:alt" content="{html.escape(card_alt(s, name), quote=True)}">',
        ROBOTS, *FEED_LINKS,
        '<link rel="apple-touch-icon" href="assets/img/apple-touch-icon.png">',
        '<link rel="manifest" href="site.webmanifest">',
    ]
    s, hits = re.subn(r'(<meta name="theme-color" content="#[0-9A-Fa-f]{6}">)', lambda m: m.group(1) + "\n  " + "\n  ".join(block), s, count=1)
    assert hits == 1, name
    if name != "research.html":  # build_research.py writes research.html's graph (CollectionPage + the ten notes)
        page = {"@type": KIND.get(name, "WebPage"), "@id": url + "#webpage", "url": url, "name": title, "description": html.unescape(desc),
                "isPartOf": WEBSITE, "primaryImageOfPage": og_image(url), "inLanguage": "en"}
        if name == "index.html":
            org = dict(ORG, legalName="OpenEXA Inc.", image=og_image(url), description="OpenEXA is an AI agentic company. It builds the "
                       "end-to-end infrastructure on which swarms of domain-specific AI agents run high-value lifecycles end to end. "
                       "Lifecycle 01 is live on real capital.",
                       address={"@type": "PostalAddress", "addressLocality": "Seattle", "addressRegion": "WA", "addressCountry": "US"})
            nodes = [org, dict(WEBSITE, inLanguage="en", publisher={"@id": ORG["@id"]}), dict(page, isPartOf={"@id": WEBSITE["@id"]}, about={"@id": ORG["@id"]})]
        else:
            nodes = [page, crumbs((CRUMB[name], url))]
        s = s.replace("</head>", "  " + ld(*nodes, id="ld-page") + "\n</head>", 1)
    if s != before: write(path, s); print("meta ->", name)
    pages.append(name)

# manifest · robots · sitemap
MANIFEST = {"id": "/", "name": "OpenEXA", "short_name": "OpenEXA", "description": "Infrastructure for agentic lifecycles.", "lang": "en",
            "start_url": "/", "scope": "/", "display": "standalone", "background_color": "#0E1512", "theme_color": "#0E1512",
            "icons": [{"src": "assets/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "assets/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
                      # the globe sits inside the maskable safe zone (radius 40%) on a full-bleed ink tile
                      {"src": "assets/img/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
write(os.path.join(ROOT, "site.webmanifest"), json.dumps(MANIFEST, indent=2) + "\n")
Image.open(os.path.join(ROOT, "assets", "img", "icon-512.png")).save(os.path.join(ROOT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
write(os.path.join(ROOT, "robots.txt"), "User-agent: *\nAllow: /\n\nSitemap: https://www.openexa.com/sitemap.xml\n")
pages += sorted("research/" + os.path.basename(a) for a in glob.glob(os.path.join(ROOT, "research", "*.html")))
pages += ["blog/"] + sorted("blog/" + os.path.basename(a) for a in glob.glob(os.path.join(ROOT, "blog", "*.html")) if os.path.basename(a) != "index.html")
page_file = lambda p: os.path.join(ROOT, *(p + "index.html" if p.endswith("/") else p).split("/"))
urls = "".join(f"  <url><loc>{SITE if p == 'index.html' else SITE + p}</loc><lastmod>{lastmod(page_file(p))}</lastmod><changefreq>{'weekly' if p == 'index.html' else 'monthly'}</changefreq><priority>{'1.0' if p == 'index.html' else '0.7'}</priority></url>\n" for p in pages)
write(os.path.join(ROOT, "sitemap.xml"), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
save_lastmod(page_file(p) for p in pages)

# 404 — header/footer from index.html; the plate (the lane carrying the address that was asked for): nf_plate.py
from nf_plate import plate as nf_plate
PLATE = nf_plate()
index = read(os.path.join(ROOT, "index.html"))
head_common = re.search(r'  <link rel="icon".*?<link rel="stylesheet" href="assets/css/site.css">\n', index, re.S).group(0)
# award a3: Home also preloads the italic serif (its eyebrow is in the first screen); the 404 sets none
head_common = re.sub(r'  <link rel="preload" href="assets/fonts/instrument-serif-400i-latin\.woff2"[^>]*>\n', "", head_common)
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?</div>\n', index, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index, re.S).group(0)
page404 = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Not found — OpenEXA</title>
  <meta name="description" content="This page did not pass the gate.">
  <meta name="robots" content="noindex">
  <meta name="theme-color" content="#0E1512">
{head_common}  <link rel="stylesheet" href="assets/css/notfound.css">
</head>
<body data-page="404" data-nav="dark-start">
  <a class="skip" href="#main">Skip to content</a>

{NAV}
  <main id="main">
    <section class="notfound is-dark grain">
      <div class="container">
        <div class="nf-copy">
          <div class="nf-title">
            <h1 class="display-1">This page didn’t pass.</h1>
          </div>
          <div class="nf-next">
            <p class="lede">The address is wrong, has moved, or never existed. Nothing&nbsp;was&nbsp;executed.</p>
            <div class="row mt-3">
              <a class="btn" href="index.html">Back to the start <svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg></a>
              <a class="btn btn--ghost" href="platform.html">The platform</a>
            </div>
            <nav class="nf-more" aria-label="More of the site">
              <ul>
                <li><a href="evidence.html">Proof</a></li>
                <li><a href="trust.html">Trust</a></li>
                <li><a href="research.html">Research</a></li>
                <li><a href="blog/index.html">Blog</a></li>
              </ul>
            </nav>
          </div>
        </div>
        {PLATE}
        <p class="notfound-log"><span>REJECTED</span>&nbsp;· gate&nbsp;04&nbsp;· reason:&nbsp;unknown&nbsp;route</p>
      </div>
    </section>
  </main>

{FOOTER}
  <script src="assets/js/site.js" defer></script>
  <script src="assets/js/notfound.js" defer></script>
</body>
</html>
'''
# Azure serves this page for any missing URL, at any depth (/blog/x/y), so every local link must be root-relative
page404 = re.sub(r'(href|src)="(?!https?:|mailto:|#|/)', r'\1="/', page404)
write(os.path.join(ROOT, "404.html"), page404)
print("wrote site.webmanifest, robots.txt, sitemap.xml, 404.html;", len(pages), "pages in sitemap")


