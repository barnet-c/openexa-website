"""Scrape every post on the old openexa.com blog into oldblog/posts.json (+ hero images) for curation and import."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import concurrent.futures as cf, html, json, re, urllib.request
from pathlib import Path

BASE = "https://www.openexa.com"
OUT = Path(str(DATA / 'oldblog'))
(OUT / "img").mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 openexa-archive/1.0"}

def get(url, binary=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", errors="replace")

index = get(f"{BASE}/blog/")
slugs = list(dict.fromkeys(re.findall(r'href="/blog/([^"/#?]+)/"', index)))
text = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).replace("\u00a0", " ").strip()

def scrape(slug):
    h = get(f"{BASE}/blog/{slug}/")
    main = h[h.index("<main>"): h.index("</main>")]
    m = lambda pat: (re.search(pat, main, re.S) or [None, ""])[1]
    meta = text(m(r'<p class="post-meta">(.*?)</p>'))
    parts = [p.strip() for p in meta.split("·")]
    hero = m(r'<img class="article-hero-image" src="([^"]+)"')
    body = m(r'<div class="rich-text">(.*)</div></article>')
    post = {
        "slug": slug,
        "title": text(m(r"<h1>(.*?)</h1>")),
        "tags": [t.strip() for t in text(m(r'<p class="eyebrow">(.*?)</p>')).split(";") if t.strip()],
        "author": parts[0] if parts else "",
        "date": parts[1] if len(parts) > 1 else "",
        "minutes": parts[2] if len(parts) > 2 else "",
        "source": html.unescape(m(r'<a class="button ghost source-link" href="([^"]+)"')),
        "hero": hero,
        "description": html.unescape(m(r'<meta name="description" content="([^"]*)"')) if False else html.unescape((re.search(r'<meta name="description" content="([^"]*)"', h) or [None, ""])[1]),
        "body_html": body,
        "words": len(text(body).split()),
        "links_out": sorted(set(re.findall(r'href="(https?://[^"]+)"', body))),
        "images_in_body": re.findall(r'<img[^>]+src="([^"]+)"', body),
    }
    if hero:
        name = hero.rsplit("/", 1)[-1]
        p = OUT / "img" / name
        if not p.exists():
            p.write_bytes(get(BASE + hero if hero.startswith("/") else hero, binary=True))
        post["hero_file"] = name
    return post

with cf.ThreadPoolExecutor(8) as ex:
    posts = list(ex.map(scrape, slugs))
(OUT / "posts.json").write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"scraped {len(posts)} posts; images {len(list((OUT / 'img').iterdir()))}")
