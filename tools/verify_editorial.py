"""Research, articles, Company and the homepage's research chapter in a browser (SwiftShader, as CI).
    python tools/verify_editorial.py [http://127.0.0.1:8125] [--swiftshader | --gpu] [--cpu-throttle N] [--cores N]
CI runs it as a job of its own (.github/workflows/checks.yml). The run modes are verify_v9's (round 2): --cpu-throttle N
slows every page's main thread N times and --cores N pins the browser, so CI's conditions reproduce on a PC; the run
header prints them with the host's CPU load."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, json, os, sys, time
from playwright.async_api import async_playwright, expect, TimeoutError as PlaywrightTimeoutError
import verify_v9 as V  # the run modes (--swiftshader / --gpu, --cpu-throttle, --cores) and the throttled browser
OUT = str(SHOTS / 'v9')
shot = lambda name: os.path.join(OUT, name)  # (round 1 wrote Windows separators into the file names on Linux)
BASE = next((a.rstrip("/") for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8125")

async def figure_ready(pg, sel):
    """the figure stage's ready flag; under SwiftShader the first WebGL frame can hold the page past Playwright's 30 s, so a
    timed-out evaluate is retried once (and its time printed); the assertion on the flag is the caller's, unchanged"""
    t0 = time.monotonic()
    for attempt in (1, 2):
        try:
            ready = await pg.locator(sel).evaluate("el => el.classList.contains('figure-ready')", timeout=30000)
            if attempt > 1: print(f"{sel}: figure evaluate answered on the retry, {time.monotonic() - t0:.1f}s after the first try")
            return ready
        except PlaywrightTimeoutError:
            print(f"{sel}: figure evaluate timed out after {time.monotonic() - t0:.1f}s (attempt {attempt} of 2)")
            if attempt == 2: raise

async def main():
    V.parse_modes(sys.argv[1:])
    if V.MODE["cores"]: V.MODE["cores"] = V.pin_cores(V.MODE["cores"]) or f"(pinning to {V.MODE['cores']} failed)"
    t_run = time.monotonic()
    async with async_playwright() as p:
        raw = await p.chromium.launch(args=V.launch_args())
        print(f"verify_editorial against {BASE} · {V.mode_line()} · Chromium {raw.version}", flush=True)
        b = V.TrackedBrowser(raw)
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        # research index: figure ready, hover morphs
        await pg.goto(f"{BASE}/research.html", wait_until="load"); await pg.wait_for_timeout(2500)
        assert await figure_ready(pg, "#research-figure"), "figure not ready"
        await pg.screenshot(path=shot(f"research-hero.png"))
        await pg.locator(".posts-list .post").first.hover(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#research-figure").get_attribute("data-figure-current") == "horizon"
        await pg.screenshot(path=shot(f"research-hover.png"))
        await pg.locator(".posts-list .post").nth(4).hover(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#research-figure").get_attribute("data-figure-current") == "boundary"
        await pg.evaluate("document.querySelector('#series').scrollIntoView()"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=shot(f"research-list.png"))
        # each article: renders, TOC present, figure ready
        for i in range(1, 11):
            href = await pg.locator(f".posts-list .post >> nth={i-1} >> a").get_attribute("href") if False else None
        links = await pg.evaluate("[...document.querySelectorAll('.posts-list .post > a')].map(a => a.getAttribute('href'))")
        assert len(links) == 10, links
        for i, href in enumerate(links):
            await pg.goto(f"{BASE}/{href}", wait_until="load"); await pg.wait_for_timeout(1800)
            fig = await pg.locator(".article-figure").evaluate("el => ({ready: el.classList.contains('figure-ready'), name: el.dataset.figure})")
            toc = await pg.locator(".toc li").count()
            h2 = await pg.locator(".article h2").count()
            assert fig["ready"], (href, fig)
            assert toc == h2 and h2 > 0, (href, toc, h2)
            if i in (0, 2, 8):
                await pg.screenshot(path=shot(f"article-{i+1:02d}-hero.png"))
                await pg.evaluate("document.querySelector('.article').scrollIntoView()"); await pg.wait_for_timeout(600)
                await pg.screenshot(path=shot(f"article-{i+1:02d}-body.png"))
            print(f"article {i+1:02d} {fig['name']:11} toc={toc} ok")
        # award a4 (research): the margin plate (from 1440 px) lights the part of the drawing that the marked contents entry
        # names: on note 09, "The result" lights the floor's rule; "The setup" lights nothing
        await pg.goto(f"{BASE}/research/09-lifecycle-01-ten-sessions.html", wait_until="load"); await pg.wait_for_timeout(1200)
        lit = {}
        for head in ("the-result", "the-setup"):
            await pg.evaluate(f"(() => {{ const h = document.getElementById('{head}'); scrollTo(0, scrollY + h.getBoundingClientRect().top - innerHeight / 4); }})()")
            await pg.wait_for_timeout(500)
            lit[head] = await pg.evaluate("(() => { const s = document.querySelector('.np-stage'); return s ? { has: s.classList.contains('has-lit'), rule: !!s.querySelector('.np-rule.is-lit'), n: s.querySelectorAll('.is-lit').length, shown: !!s.getClientRects().length } : null; })()")
        assert lit["the-result"] and lit["the-result"]["shown"] and lit["the-result"]["has"] and lit["the-result"]["rule"], ("note 09 at 'The result': the plate's rule lit", lit)
        assert not lit["the-setup"]["has"] and lit["the-setup"]["n"] == 0, ("note 09 at 'The setup': nothing lit", lit)
        print(f"note 09: the margin plate lights its rule at 'The result' ({lit['the-result']['n']} parts) and nothing at 'The setup'")
        # company: sculpture + modes + timeline (1 Nov cut: the mode's copy is the plate's caption, the mode's name; the
        # manifesto and #mission left the page, see .shots/v2x/TESTS.md section 16)
        await pg.goto(f"{BASE}/company.html", wait_until="load"); await pg.wait_for_timeout(2500)
        assert await pg.locator("#company-figure").evaluate("el => el.classList.contains('figure-ready')")
        await pg.screenshot(path=shot(f"company-hero.png"))
        await pg.locator('.company-modes button[data-figure-target="swarm"]').click(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#company-figure").get_attribute("data-figure-current") == "swarm"
        assert (await pg.locator("[data-plate-label]").inner_text()).startswith("Narrow agents"), await pg.locator("[data-plate-label]").inner_text()
        await pg.screenshot(path=shot(f"company-specialize.png"))
        await pg.locator('.company-modes button[data-figure-target="boundary"]').click(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#company-figure").get_attribute("data-figure-current") == "boundary"
        assert (await pg.locator("[data-plate-label]").inner_text()).startswith("Decide above"), await pg.locator("[data-plate-label]").inner_text()
        await pg.screenshot(path=shot(f"company-act.png"))
        # (hc14) the walk visits every chapter the page lists, whatever their number (§04 #lifecycles left with its heading;
        # its line is §01's): the three chapters, in order. (hc15) "How we build" comes before the team (why, how, who)
        cids = await pg.evaluate("[...document.querySelectorAll('main section[data-chapter]')].map(s => s.id)")
        assert cids == ["story", "constants", "team"], ("company chapters", cids)
        for name in cids:
            await pg.evaluate(f"document.getElementById('{name}').scrollIntoView()"); await pg.wait_for_timeout(1800)
            await pg.screenshot(path=shot(f"company-{name}.png"))
        assert await pg.locator(".timeline").evaluate("el => el.classList.contains('is-in')")
        # homepage research chapter
        await pg.goto(f"{BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('#research').scrollIntoView()"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=shot(f"home-research.png"))
        # the chapters live in the nav's readout list now (the fixed right rail is gone); it lists every chapter of the page
        # (7 until hc11, 6 since Home's §02 left, 5 since hc13r when §03 #proof left)
        nch = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
        assert nch == 5 and await pg.locator(".nav-ch-list a").count() == nch and await pg.locator(".chapters").count() == 0, nch
        # insights redirect
        await pg.goto(f"{BASE}/insights.html", wait_until="load"); await pg.wait_for_timeout(800)
        assert pg.url.endswith("/research.html"), pg.url
        assert not errs, errs
        print(f"desktop: research index morphs on hover, 10 articles render with TOC + figure, company modes switch the formation and its caption, the timeline reveals, {nch} chapters, insights redirects")
        await ctx.close()
        # mobile
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for name in ("research.html", links[0], "company.html"):
            await pg.goto(f"{BASE}/{name}", wait_until="load"); await pg.wait_for_timeout(1800)
            sw = await pg.evaluate("document.documentElement.scrollWidth"); assert sw <= 391, (name, sw)
            await pg.screenshot(path=shot(f"m-{name.replace('/', '-').replace('.html', '')}.png"))
            await pg.evaluate("scrollTo(0, 900)"); await pg.wait_for_timeout(800)
            await pg.screenshot(path=shot(f"m-{name.replace('/', '-').replace('.html', '')}-2.png"))
        assert not errs, errs
        print("mobile: no overflow on research, article, company")
        await ctx.close()
        # hc21 (integrate, standing in for tests; research's optional pins, the director's HC21 4.1): on phones and upright
        # tablets the research pages lead with their words, as every page does: the h1 starts within 160 px of the top (the
        # page heroes' 142-172; it was 303-526), and a note's hedge, once figure.js hangs it under the drawing, stands below
        # the meta line and inside the hero (the order: title, meta, drawing, hedge)
        tops = []
        for vw, vh in ((390, 844), (768, 1024)):
            ctx = await b.new_context(viewport={"width": vw, "height": vh})
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            for name in ("research.html", links[0], links[8]):
                await pg.goto(f"{BASE}/{name}", wait_until="load"); await pg.wait_for_timeout(1800)
                top = await pg.evaluate("Math.round(document.querySelector('main h1').getBoundingClientRect().top + scrollY)")
                assert top <= 160, (name, vw, "the h1 starts too far down", top)
                tops.append(top)
                if name == "research.html": continue
                await pg.wait_for_function("!!document.querySelector('.article-hero .article-figcap.is-hung')", timeout=10000)
                box = await pg.evaluate("(() => { const r = s => document.querySelector(s).getBoundingClientRect(); const m = r('.article-hero .article-meta'), c = r('.article-hero .article-figcap'), h = r('.article-hero'); return { meta: m.bottom, cap: c.top, foot: c.bottom, hero: h.bottom }; })()")
                assert box["meta"] <= box["cap"] and box["foot"] <= box["hero"] + 1, (name, vw, "the hedge is not under the meta line, in the hero", box)
            assert not errs, errs
            await ctx.close()
        print(f"research heroes at 390 and 768: the words first (h1 at {min(tops)}-{max(tops)} px), a note's hedge under its meta line")
        # hc21 (integrate, standing in for tests; system's HC21 4.3): the notes and the posts end on one pager, drawn one way:
        # both cells on one left edge, the same title measure, and the green top rule drawn on hover (at one speed) with the
        # label lit; every value read on a note equals the post's
        PAGER = r"""async (hover) => { const cs = (e, p) => getComputedStyle(e, p || null); const c = document.querySelector('.pager .pager-card.next');
          const k = c.querySelector('.k'), h = c.querySelector('h3'), b = cs(c, '::before');
          return { align: cs(c).textAlign, justify: cs(c).justifyItems, measure: cs(h).maxWidth, rule: b.content !== 'none' && b.content !== 'normal', origin: b.transformOrigin,
                   rest: b.transform, ruleColor: b.backgroundColor, label: cs(k).color, draw: b.transitionDuration + ' ' + b.transitionTimingFunction, fade: cs(k).transitionDuration }; }"""
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        seen = {}
        for name in (links[4], "blog/in-search-gen-ai-business-model.html"):
            await pg.goto(f"{BASE}/{name}", wait_until="load"); await pg.wait_for_timeout(800)
            await pg.evaluate("document.querySelector('.pager').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(500)
            rest = await pg.evaluate(PAGER, False)
            for _ in range(3):  # the pointer on the card once the page has stopped moving (a late layout can carry it off)
                await pg.mouse.move(5, 5); await pg.locator(".pager .pager-card.next").hover(); await pg.wait_for_timeout(1200)
                if await pg.evaluate("document.querySelector('.pager .pager-card.next').matches(':hover')"): break
            hov = await pg.evaluate(PAGER, True)
            assert rest["align"] in ("start", "left") and rest["justify"] in ("normal", "start", "stretch", "legacy"), (name, "Next is not set on the left edge", rest)
            assert rest["rule"] and rest["rest"] != "none" and hov["rest"] == "none", (name, "the green rule does not draw on hover", rest, hov)
            assert hov["label"] != rest["label"], (name, "the label does not light on hover", rest, hov)
            seen[name] = (rest, hov)
        a, c = seen.values()
        assert a == c, ("the notes' and the posts' pagers differ", seen)
        print(f"one pager on notes and posts: Next on the left edge, titles at {a[0]['measure']}, the rule draws on hover, the label lights")
        await ctx.close()
        # award a4 (research): without JavaScript note 09's hero still carries its key: floor, 10 bps, 01 and 10 shown, the
        # minor numerals not. hc3 (research): the particle plates' words are in the caption register, sentence case
        # ("Floor" / "10 bps"), so the floor label is matched without regard to case
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, java_script_enabled=False)
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/research/09-lifecycle-01-ten-sessions.html", wait_until="load"); await pg.wait_for_timeout(600)
        keys = await pg.evaluate(r"[...document.querySelectorAll('.fs-keys .fl')].map(e => ({ t: e.textContent.replace(/\s+/g, ' ').trim(), minor: e.classList.contains('fl--minor'), on: !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none' }))")
        shown = [k["t"] for k in keys if k["on"]]
        assert any(t.lower().startswith("floor") and "10 bps" in t for t in shown) and "01" in shown and "10" in shown, ("no-JS note 09 key", shown)
        assert not [k for k in keys if k["minor"] and k["on"]], ("no-JS note 09: a minor numeral shown", keys)
        print(f"no-JS note 09 at 390: the still's key shown ({', '.join(shown)}), no minor numeral")
        await raw.close()
    print(f"EDITORIAL CHECKS PASSED in {time.monotonic() - t_run:.0f} s")
asyncio.run(main())
