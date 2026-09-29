import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
# -*- coding: utf-8 -*-
"""Launch metadata for the OpenEXA site: canonical + Open Graph + Twitter tags, manifest, icons, JSON-LD,
robots.txt, sitemap.xml and a branded 404 page (header/footer templated from index.html)."""
import os, re, io, glob, html

ROOT = str(SITE)
SITE = "https://www.openexa.com/"
def read(p): return io.open(p, encoding="utf-8").read()
def write(p, s): io.open(p, "w", encoding="utf-8", newline="\n").write(s)

def meta(s, name, prop=False):
    m = re.search(r'<meta %s="%s" content="([^"]*)">' % ("property" if prop else "name", re.escape(name)), s)
    return m.group(1) if m else ""

pages = []
for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
    name = os.path.basename(path)
    if name in ("404.html", "insights.html"): continue
    s = read(path); before = s
    s = re.sub(r'\n  <link rel="canonical".*?<link rel="manifest" href="site.webmanifest">', "", s, flags=re.S)  # idempotent
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
        f'<meta property="og:image" content="{SITE}assets/img/og.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{html.escape(og_title, quote=True)}">',
        f'<meta name="twitter:description" content="{html.escape(og_desc, quote=True)}">',
        f'<meta name="twitter:image" content="{SITE}assets/img/og.png">',
        '<link rel="apple-touch-icon" href="assets/img/apple-touch-icon.png">',
        '<link rel="manifest" href="site.webmanifest">',
    ]
    s, hits = re.subn(r'(<meta name="theme-color" content="#[0-9A-Fa-f]{6}">)', lambda m: m.group(1) + "\n  " + "\n  ".join(block), s, count=1)
    assert hits == 1, name
    if name == "index.html" and "application/ld+json" not in s:
        ld = ('<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"OpenEXA","url":"https://www.openexa.com/",'
              '"logo":"https://www.openexa.com/assets/img/icon-512.png","description":"OpenEXA is an AI agentic company. It builds the end-to-end infrastructure on which swarms of domain-specific AI agents run high-value lifecycles end to end. Lifecycle 01 is live on real capital.",'
              '"address":{"@type":"PostalAddress","addressLocality":"Seattle","addressRegion":"WA","addressCountry":"US"},"sameAs":["https://sentiment.openexa.com/"]}</script>')
        s = s.replace("</head>", "  " + ld + "\n</head>", 1)
    if s != before: write(path, s); print("meta ->", name)
    pages.append(name)

# manifest · robots · sitemap
write(os.path.join(ROOT, "site.webmanifest"), '{\n  "name": "OpenEXA",\n  "short_name": "OpenEXA",\n  "description": "Infrastructure for agentic lifecycles.",\n  "start_url": "/",\n  "display": "standalone",\n  "background_color": "#0E1512",\n  "theme_color": "#0E1512",\n  "icons": [\n    { "src": "assets/img/icon-192.png", "sizes": "192x192", "type": "image/png" },\n    { "src": "assets/img/icon-512.png", "sizes": "512x512", "type": "image/png" }\n  ]\n}\n')
write(os.path.join(ROOT, "robots.txt"), "User-agent: *\nAllow: /\n\nSitemap: https://www.openexa.com/sitemap.xml\n")
pages += sorted("research/" + os.path.basename(a) for a in glob.glob(os.path.join(ROOT, "research", "*.html")))
pages += ["research/blog/"] + sorted("research/blog/" + os.path.basename(a) for a in glob.glob(os.path.join(ROOT, "research", "blog", "*.html")) if os.path.basename(a) != "index.html")
urls = "".join(f"  <url><loc>{SITE if p == 'index.html' else SITE + p}</loc><lastmod>2026-09-23</lastmod><changefreq>{'weekly' if p == 'index.html' else 'monthly'}</changefreq><priority>{'1.0' if p == 'index.html' else '0.7'}</priority></url>\n" for p in pages)
write(os.path.join(ROOT, "sitemap.xml"), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")

# 404 — header/footer from index.html
index = read(os.path.join(ROOT, "index.html"))
head_common = re.search(r'  <link rel="icon".*?<link rel="stylesheet" href="assets/css/site.css">\n', index, re.S).group(0)
NAV = re.search(r'  <header class="nav">.*?</header>\n  <div class="nav-menu">.*?</div>\n', index, re.S).group(0)
FOOTER = re.search(r'  <footer class="footer">.*?</footer>\n', index, re.S).group(0)
page404 = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Not found — OpenEXA</title>
  <meta name="description" content="This page did not pass the gate.">
  <meta name="robots" content="noindex">
  <meta name="theme-color" content="#0E1512">
{head_common}</head>
<body data-nav="dark-start">
  <a class="skip" href="#main">Skip to content</a>

{NAV}
  <main id="main">
    <section class="notfound is-dark grain">
      <canvas class="notfound-swarm" data-swarm aria-hidden="true"></canvas>
      <div class="container">
        <div class="eyebrow" data-reveal>404 · Rejected at the gate</div>
        <h1 class="display-1" data-reveal data-split style="--d:60ms">This page didn't pass.</h1>
        <p class="lede mt-3" data-reveal style="--d:120ms">The address is wrong, has moved, or never existed. Nothing was executed. The attempt is on the record.</p>
        <div class="row mt-3" data-reveal style="--d:180ms">
          <a class="btn" href="index.html">Back to the start <svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 8h11M9 4l4 4-4 4"/></svg></a>
          <a class="btn btn--ghost" href="platform.html">The platform</a>
        </div>
        <p class="notfound-log" data-reveal style="--d:240ms"><span>REJECTED</span> · gate 04 · reason: unknown route · logged</p>
      </div>
    </section>
  </main>

{FOOTER}
  <script src="assets/js/site.js" defer></script>
</body>
</html>
'''
write(os.path.join(ROOT, "404.html"), page404)
print("wrote site.webmanifest, robots.txt, sitemap.xml, 404.html;", len(pages), "pages in sitemap")


