# OpenEXA — website (v11 · the team, at full resolution)

The public site for [openexa.com](https://www.openexa.com). This build is v10 (the CEO's cut plus
Research and Company) with the team restored to the Company page and every object on the site
rendered at full device resolution. v9 started from the version the CEO preferred (v1,
*timely-quokka*, 3 Sep 2026) and keeps its identity — the dark WebGL overture, the paper-and-ink
"Ledger" chapters, the numbered sections, the full eight-layer story — while removing what should
never have been public, removing every exchange name, and giving the whole thing the engineering it
deserved.

Static HTML/CSS/JS. No build step, no framework, no tracking, no dependencies. Deploy the folder to
any static host (Netlify Drop, Vercel, S3/CloudFront, GitHub Pages).

```
openexa-v9/
├── index.html          Home — five-beat WebGL overture, then seven chapters: the work · the stack · Lifecycle 01 (with the live swarm) · proof · why agents · trust & governance (with the SHA-256 chain) · research
├── platform.html       The agentic stack: eight layers, one boundary, the swarm, execution pipeline, customer MCP servers, operating modes
├── lifecycles.html     The lifecycle test, six lifecycle classes, Lifecycle 01 in depth (with the desk simulator), next lifecycles
├── evidence.html       Proof: ten-session ledger, broker verification, the cost/risk stack
├── trust.html          Trust & governance: the Council gate, permissions, ledger, control plane, does/does-not
├── company.html        Company: the sculpture (Specialize · Coordinate · Act), mission, the story in four moves, the team, four constants, where the work is
├── research.html       Research: ten notes, one point-cloud figure that becomes the idea you point at
├── research/           01–10 articles, each with its own figure, sticky table of contents and prev/next pager
├── research/blog/      The blog: index (four collections, filter chips) + 34 imported posts from the old site
├── insights.html       Redirect stub → research.html (kept so old links resolve; noindex)
├── access.html         Request-access form: bring a lifecycle · manager platform · partnership · qualified investor
├── 404.html            "This page didn't pass." (noindex)
├── site.webmanifest · robots.txt · sitemap.xml (53 URLs) · _redirects (old openexa.com URLs → new pages)
└── assets/
    ├── css/site.css    The "Ledger" design system (paper + ink) + story stage, chapters, objects, forms, editorial layer, team
    ├── js/story.js     WebGL story engine — one 20k-point swarm morphing through five formations, two-pass glow, full device resolution
    ├── js/figure.js    WebGL figure engine — 15k-point cloud, twelve named formations, morphs on hover/click (research, company)
    ├── js/swarm.js     The swarm, live — agents through six gates, a council you can tighten, a halt switch (index.html)
    ├── js/chain.js     The chain — eight SHA-256-chained records you can edit and watch break (index.html)
    ├── js/gap.js       The desk — an illustrative model of one session of Lifecycle 01 (lifecycles.html)
    ├── js/site.js      Nav, clocks, chapter rail, loader, split text, reveals, counters, calculator, form, ledger stream, 2D fallback
    ├── js/blog.js      Blog collection filter (chips, #hash deep links; plain jump links without JS)
    └── img/            globe.svg, favicon.svg, og.png (1200×630), icon-192/512.png, apple-touch-icon.png, team/*.webp (six 560px portraits)
```

## What changed from v1

**Removed.**
- The old Company page's office address, phone and personal email, and the Investors page (the deck
  in the open, the ask). The only location given is "Seattle, WA"; the access form's inbox lives in
  one place, as `data-contact` on the body of `access.html`. The team itself returned in v11 — on
  the Company page only (see below); no name or photograph appears anywhere else on the site.
- The homepage team section, the contact block in the closing band, phone and address in every footer.
- Every mention of NASDAQ and NYSE, everywhere. "Live on NASDAQ and NYSE" became "live on real
  capital"; the hero sub-line is now exactly *"OpenEXA builds the end-to-end infrastructure on which
  swarms of domain-specific AI agents run the world's high-value lifecycles."* Broker names on the
  Proof page became "broker confirmations" and "reconciliation reports"; clearing-house names became
  "clearing & settlement". Third-party marks are no longer listed in the disclaimer.
- Investor-deck figures that read as a pitch: revenue capacity (ARR), AUM capacity, the BTC-yield
  "why now" section and the go-to-market section on the Lifecycles page, the "$15B managed" team line.
- The custom cursor and magnetic buttons. The pointer is the native one.

**Kept.** Everything the CEO liked: the headline, the dark overture into paper chapters, the eight
layers, the vertical execution diagram, the ten-session proof, the 90% economics table, the roadmap,
Reg D 506(c) disclosures, the loader, the numbered prospectus structure.

**Added.**
- The three interactive objects built after v1: the **live swarm** (chapter 03 — tighten the
  council, halt the lane), the **SHA-256 chain** (chapter 06 — edit a record, watch the chain break,
  restore it) and the **desk** (Lifecycles — one simulated session of Lifecycle 01).
- Story engine upgrades: two-pass additive glow, scroll inertia so the cloud flocks rather than
  snaps, a pause control, real buttons for the five chapter marks (keyboard-navigable, `aria-current`),
  inert inactive beats, a still frame painted before the engine is ready, rendering suspended
  off-screen and in hidden tabs, `prefers-reduced-motion` honoured at runtime.
- The hero figures moved out of the globe and under the copy, so nothing overlaps the mark at any width.
- Chapter rail (fixed, right edge) and giant faint chapter numerals on the homepage; legal disclosures
  behind a keyboard-operable disclosure in every footer (fully visible without JavaScript).
- Accessible mobile menu (Escape, focus return, contained tabbing); current page marked at runtime so
  clean URLs and `.html` both work.
- Access form: native validation, percent-encoded mail draft that explicitly says nothing has been
  sent, an edit action that preserves input, endpoint mode with real error handling, deep links
  (`#lifecycles`, `#managers`, `#partners`, `#investors`) preselecting the right path.
- Time-based loader (never stretched by a slow GPU; hard cap 1.8 s), `[hidden]` made authoritative,
  wide tables wrapped in scrollable regions for phones, canonical/OG/Twitter tags, JSON-LD, manifest,
  robots, sitemap, share card.

## Research and Company (added 21 Sep)

**Research** (`research.html` + `research/`). Ten notes from the OpenEXA research blog, published in
this order: the two research notes first (*Compounding Error and the Case for Decomposition*,
*Post-training and Audit*), then the eight-part series (*Not tasks — lifecycles* through *Master and
copy*). Each article has a hero figure drawn from its idea, a sticky table of contents generated from
its headings, a drop-cap lead, a prev/next pager and `TechArticle` JSON-LD. The index page carries
one figure that morphs into the idea of whichever note you point at or focus. The homepage gained
chapter 07 with the three featured notes; `insights.html` now redirects here. Two sentences that
named brokers were rewritten to "broker-confirmed", in line with the rule above.

**Company** (`company.html`). "Intelligence, put to work." A point-cloud sculpture that you can put
into its three modes — *Specialize* (thousands of narrow agents), *Coordinate* (the council),
*Act* (the deterministic boundary) — with a live caption; the mission as a manifesto that lights as
you read; the story in four moves; the team (v11, below); the four constants on a dark ground over a
faint lifecycle figure; where the work is. No address, no phone, no personal email.

**Figure engine** (`assets/js/figure.js`). One compact WebGL renderer for every `[data-figure]`
stage: 15,000 points (7,000 on phones), twelve named formations (horizon, weights, lifecycle, swarm,
boundary, rulebook, council, ledger, sessions, mastercopy, library, company), spring morphs between
them, pointer tilt, two-pass glow, rendering suspended off-screen and in hidden tabs,
`prefers-reduced-motion` honoured, and a static SVG-mask fallback when WebGL is unavailable.
Wiring is declarative: `data-figure-target` on a list item or button names the formation to show,
`data-figure-stage` names the stage, `data-copy` swaps a caption.

## The team and the resolution pass (v11, 23 Sep)

**The team** — section 03 of the Company page, and nowhere else. The six people from the original
site (founder & CEO, chief analyst, chief scientist, chief technology, chief product, chief AI
agents) with their roles, biographies and professional links, in the same hairline-cell grammar as
the four constants: mono index, credential tag, disc portrait, serif name. The portraits are the
original background-removed cut-outs, framed consistently (subject anchored to the baseline),
resampled with Lanczos and a light unsharp mask to 560 px WebP masters (~45 KB each), shown at
176 px so they stay crisp on 2x and 3x displays. At rest they sit in warm monochrome over a faint
point grid — the swarm at rest — and come to colour when pointed at or focused; a signal-green ring
and the corner circle answer the hover. Three stats (`data-count`) count up on scroll. Office address,
phone and personal email stay off the site. `verify_v9.py` enforces the rule both ways: the seven
team strings must all appear on `company.html` and must appear on no other page.

**Resolution.** Every canvas now renders at the device's real pixel ratio, up to 3x, inside a UHD
pixel budget (3840 x 2160) so a full-viewport stage on a 3x laptop stays fluid: the story engine,
the figure engine, the live swarm, the desk and the 2D fallbacks (previously capped at 1.5x / 2x).
Point budgets rose from 12k to 20k on the homepage and 8.4k to 15k on the figures, with the brand
mark's lat/long grid drawn finer in proportion; sprites are a third smaller so the density reads as
detail rather than clumps. The sprites themselves are resolution-aware: the disc edge is exactly one
device pixel wide at any size (no shimmer, no jaggies at 3x), points carry a soft bead shading, the
halo pass is a true gaussian with no visible rim, fragment shaders run at `highp` where the GPU
offers it, and point sizes are clamped to the hardware's `ALIASED_POINT_SIZE_RANGE`.

## Verification

*v12 (24 Sep), homepage edits:* the Lifecycle 01 headline reads "Trillions in 17,000 ETFs…" (the Lifecycles
page matches); the fourth proof stat is now **5 runs, lifecycle executions** (it was $5M in committed assets);
chapter 07 "Agentic platform evolution" (the three-phase roadmap) is gone, so Research moves up to chapter 07 on
the paper-2 ground to keep the sections alternating. The homepage now has seven chapters.

*v13 (24 Sep), page edits:* Lifecycles drops the four-figure market strip ($22T in ETFs · 17k ETFs · the
4–8% band · $0.0002 per dollar per day); its intro already says "Trillions". Proof drops 04 Platform economics
(the ARR slider and table) and 05 Addressable market (the TAM rings), and now ends at 03 Why agents win. Trust
drops 05 Risk factors and ends at 04 Plain language. Research is unchanged.

*v14 (24 Sep), Company edits:* the hero's "put to work." is white instead of signal green (italic kept; hero
only). In the team section the third stat is now **100+ research papers** (it was 90% of Microsoft's revenue),
alongside 14 patents and 5 books.

*v15 (28 Sep), the blog:* `research/blog/` imports the old openexa.com blog — 36 of its 51 posts in four
collections (AI & agents · Financial markets research · Market structure & economics · Municipal markets &
commentary), each post at `research/blog/<old-slug>.html` with its byline, date, hero image, body images and a
link to the original source; two link-only posts (columns hosted elsewhere) are outbound cards. The 15 held-back
posts are the 2023–24 crypto/token-product posts (OXA, AUT, stable credit, wallets, NFTs, a crypto margin
account); they are listed in `EXCLUDE` in `build_blog.py` and redirect to the blog index. Content was repaired
(double-encoded punctuation), sanitised, images localised and downscaled (≤1800 px), and exchange/broker names
rewritten per the site rule. Bylines are the one place outside Company where people's names appear. The Research
page gains "03 The blog" (collection cards) and a "More on financial markets research" link to Google Scholar,
which also sits on Dr. Tim Leung's team card and in the blog's markets collection. Every footer links the blog.
`_redirects` now maps the old site's URLs (`/blog/<slug>`, `/strategies`, `/trust-risk`, `/status`,
`/for-managers`, `/for-investors`, `/beta`) to their new homes, so the domain can move without breaking links.
Built by `build_blog.py` (then `build_research.py`, `launch_meta_v9.py`); sitemap has 53 URLs.

*v16 (28 Sep), featured series:* Ajit's four 2024 posts, which cross-link one another (an introduction on the
Gen-AI business model, then a three-part finance series on relative value analysis, guardrails and tearsheets,
and AI copilots and agents), are now **The Gen-AI series**. It's featured at the top of the blog (shown under
"All" and "AI & agents"), each post carries its part, a series list in the side column with the current part
marked, and a pager that walks the series in order. The Research page's blog section links to it.

*v17 (29 Sep), the team from the old About page:* the Company team section is rebuilt from openexa.com/status/
by `build_team.py`. It now has **ten team members and three advisors**, each with a title, a short line, a
"Read full description" that expands to the full bio (native `<details>`, so it works without JavaScript) and
their links. Portraits are the About page's cut-outs (or the v1 crop where that had more pixels), framed the same way.
**Barnet Sherman is removed** (he is now a customer), along with blog collection 04 "Municipal markets &
commentary" (his columns and two OpenEXA posts), which redirect to the blog index; the blog has 29 posts in three
collections. **Ajit's profile no longer gives a patent count**, and the team stats read ten team members · three
advisors · 100+ research papers. Sentences in three bios that described OpenEXA's former crypto business as current
work were dropped. On the Proof page the fourth stat is now **5 runs · lifecycle executions**, and "$5M committed"
is gone from its meta descriptions and the homepage story.

`verify_v9.py` (session tooling, Playwright + SwiftShader) passes: 11 pages (including Company, the
Research index and two articles) at 1440 and 390 with zero console errors, no horizontal overflow
and none of the forbidden strings (exchange names, broker names, phone, address, ARR figures), with
the team names present on Company and absent everywhere else; five story beats navigable with the
hero figures clear of the globe; swarm runs and halts; chain breaks at record 03 and restores; the
desk runs; the access form preselects from the hash, prepares a draft and restores input on edit;
the six portraits load from their 560 px masters, are monochrome at rest and colour on hover; the
story canvas and both company figures render at 2x device resolution in a 2x context; every page is
readable without JavaScript; the homepage and every figure stage fall back without WebGL.
`verify_editorial.py` covers the figure morphs (hover on the research index, mode buttons on
Company), all ten articles (figure ready, table of contents matches the headings), the manifesto
lighting, the timeline reveal and the insights redirect. `linkcheck_tree.py`: 718 internal
references across 20 pages, none broken.

## Local preview

```
cd openexa-v9
python -m http.server 8125
# open http://127.0.0.1:8125/
```

## Blog moved to /blog/, hosting moved to Azure (30 Sep)

At Ajit's request the blog moved out of the Research folder: `research/blog/` is now `blog/`, the same path the
old openexa.com blog used, so its `/blog/<slug>/` links resolve directly. The site is now hosted on Azure Static Web
Apps (deployed from GitHub on every push to `main`); Netlify is no longer used. Netlify's `_redirects` became
`staticwebapp.config.json`: redirects for the old openexa.com pages and held-back posts, `/research/blog/...` →
`/blog/...` for links shared before the move, and `404.html` for missing pages (its links are now root-relative so
it renders at any depth). This file moved out of `site/` so it is no longer published.

## Five people move from the team to the advisors (2 Oct)

At Ajit's request John Schuster, Subuddh Parekh, Abhishek Sinha, Dr. Julius E. Ekeroma and Dipit Nanawati moved from the team
to the advisors. The Company page now shows five team members (Ajit, Tim, Mike, Victor, Shalabh) and eight advisors in a
4x2 grid of the same compact cards. Advisor kickers read `Advisor - <area>`, the area taken from each person's own bio, so
no advisor card carries an employee title. The section heading, lede and counters (5 / 8 / 100+) follow the roster, and
`verify_v9.py` now pins the exact names in each group.

## Closing a pull request now removes its Azure preview (2 Oct)

The workflow's close job failed on every merged PR, so each PR's preview environment stayed behind (the free plan allows three).
First it lacked the deployment token; then, with the token, Azure answered "No matching static site found". This Static Web App
authorizes deployments with GitHub (OIDC), and in that mode the close step also needs the id token, which the deploy step
already had. The close job now installs the OIDC client, gets the id token and passes it as `github_id_token`.
