# OpenEXA — website

The source of the OpenEXA website: an AI agentic company building the end-to-end infrastructure on which swarms of
domain-specific AI agents run the world's high-value lifecycles.

- **Live:** <https://timely-quokka-fa2399.netlify.app/> (Netlify; `openexa.com` will point here once the domain moves)
- **Current version:** v17 (2026-09-29). Every deployed version, v1 onwards, is archived in
  [barnet-c/openexa-website-versions](https://github.com/barnet-c/openexa-website-versions).
- `site/` is byte-for-byte what is deployed. Running the builders in `tools/` reproduces it exactly.

## Layout

```
site/     the website: static HTML/CSS/JS, no build step, no framework, no tracking (see site/README.md)
tools/    Python scripts that generate parts of site/ and verify it
data/     their inputs: the old openexa.com blog and team (scraped), the research posts, v1 portraits
```

## Preview

```
python -m http.server 8125 --directory site
# open http://127.0.0.1:8125/
```

## Rebuild the generated parts

Most pages are hand-written. These are generated; edit the script or its data, not the output:

| Script | Writes | From |
|---|---|---|
| `tools/build_blog.py` | `site/research/blog/`, blog images, `site/_redirects`, `data/blog_summary.json` | `data/oldblog/` (old openexa.com blog) |
| `tools/build_research.py` | `site/research.html`, `site/research/01-…10-*.html` | `data/openexa-research-blogs.md`, `data/blog_summary.json` |
| `tools/build_team.py` | team section of `site/company.html`, `site/assets/img/team/` | `data/oldteam/` (old About page), `data/v1-team/` |
| `tools/launch_meta_v9.py` | `site/sitemap.xml`, `robots.txt`, `site.webmanifest`, `404.html` | the pages in `site/` |

Run them in that order (the research page reads the blog summary):

```
python tools/build_blog.py
python tools/build_research.py
python tools/build_team.py
python tools/launch_meta_v9.py
```

Requirements: Python 3.11+, `pip install pillow ftfy playwright` and `playwright install chromium` for the checks.

## Check

```
python tools/linkcheck_tree.py          # every internal link and anchor resolves
python tools/verify_v9.py               # all key pages at 1440 and 390 in a real browser (needs the preview server)
python tools/verify_editorial.py        # research figures, articles, company modes (needs the preview server)
python tools/verify_live.py <netlify-site-or-draft> <archive-folder>   # a deploy matches an archived version
python tools/verify_redirects.py <host>                                # every old openexa.com URL redirects correctly
python tools/smoke_live.py <netlify-site | https://draft-url>          # browser smoke test of a deploy
```

## Deploy

Netlify site `timely-quokka-fa2399` (id `8fcb0298-9b64-4eb3-a7fe-9a60da4c0176`), via the Netlify CLI. Always draft first,
check it, then promote that same deploy, so production gets exactly what was reviewed:

```
netlify deploy --dir site --site 8fcb0298-9b64-4eb3-a7fe-9a60da4c0176 --message "…"      # draft URL
netlify api restoreSiteDeploy --data '{"site_id": "8fcb0298-9b64-4eb3-a7fe-9a60da4c0176", "deploy_id": "<id>"}'
```

Then archive it: `python tools/archive_version.py <n> <slug> <date> <provenance.txt>` (needs the versions repo
checked out next to this one as `openexa-versions`).

## Content rules

- No exchange, broker or clearing-house names (NASDAQ, NYSE, TradeStation, Interactive Brokers, DTCC) anywhere.
- People's names and photos appear only on the Company page (team and advisors) and in blog bylines. No phone
  numbers, office address or personal email. Barnet Sherman is a customer, not part of the team.
- The 2023–24 crypto/token-product posts of the old blog are held back (`EXCLUDE` in `tools/build_blog.py`).
- Native cursor; every object readable without JavaScript and without WebGL.

`tools/verify_v9.py` enforces the first three.
