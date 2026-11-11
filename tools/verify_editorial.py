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
        # company: the hero figure + timeline (1 Nov cut: the manifesto and #mission left the page, see .shots/v2x/TESTS.md
        # section 16). hc30r (COMP-1; integrate, standing in for tests, on company's request; TESTS.md section 53): the hero
        # is one act now, drawn by company-hero.js on a 2D canvas (no figure.js stage, no modes, no live readout). The walk
        # holds what it held, for the new figure: the figure is drawn (live, its bitmap the box in device pixels, marks in
        # paper and signal green only, nothing blended), it comes to rest, its caption names and hedges it, and its one
        # control changes the picture and brings the same picture back (it was: each mode switches the formation and caption)
        await pg.goto(f"{BASE}/company.html", wait_until="load")
        CO = r"""() => { const st = document.getElementById('company-figure'), c = st && st.querySelector('canvas'); if (!c || !c.width) return null;
          const rgba = v => { const g = document.createElement('canvas').getContext('2d'); g.fillStyle = v; g.fillRect(0, 0, 1, 1); return [...g.getImageData(0, 0, 1, 1).data].join(','); };
          const cs = getComputedStyle(document.documentElement), paper = rgba(cs.getPropertyValue('--paper').trim()), green = rgba(cs.getPropertyValue('--signal-bright').trim());
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data, n = { paper: 0, green: 0, clear: 0, other: 0 }; let h = 0;
          for (let i = 0; i < d.length; i += 4) { const k = d[i] + ',' + d[i + 1] + ',' + d[i + 2] + ',' + d[i + 3];
            n[k === paper ? 'paper' : k === green ? 'green' : d[i + 3] === 0 ? 'clear' : 'other']++; h = (h * 31 + d[i] * 65536 + d[i + 1] * 256 + d[i + 2] + d[i + 3]) | 0; }
          const r = c.getBoundingClientRect(), t = s => { const e = document.querySelector(s); return e ? e.textContent.replace(/\s+/g, ' ').trim() : null; }, b = document.querySelector('[data-co-replay]');
          return { live: st.classList.contains('is-live'), w: c.width, h: c.height, bw: r.width * devicePixelRatio, bh: r.height * devicePixelRatio, n, hash: h,
                   label: t('.company-readout .fc-t'), hedge: t('.company-readout .fc-h'), replay: !!b && !b.hidden && !!b.getClientRects().length, buttons: st.querySelectorAll('button').length,
                   tag: (() => { const g = st.querySelector('.co-tag:not(.co-tag--hot)'); return g && !g.hidden ? (g.querySelector('.stage-tag b') || g).textContent.trim() : ''; })(), say: t('#company-figure [role=status]'),
                   old: document.querySelectorAll('[data-figure], .company-modes, [data-plate-label], script[src$="figure.js"]').length }; }"""
        async def co_rest(why, first=None):
            """the figure once two readings 600 ms apart are the same picture (the act has ended), within 12 s"""
            last, t0 = None, time.monotonic()
            while time.monotonic() - t0 < 12 * max(1.0, V.MODE["throttle"]):
                now = await pg.evaluate(CO)
                if now and last and now["hash"] == last["hash"] and (first is None or now["hash"] == first): return now
                last = now; await pg.wait_for_timeout(600)
            raise AssertionError((why, last))
        # hc31r (integrate, standing in for tests; company's request, LEAP-hc31 COMP-1): after its opening act the sheet is a
        # camera on the run (an agent is green while it proposes), so with the model running it does not come to rest and
        # there is no Replay. "It comes to rest" reads: the header's pause holds it (two readings 600 ms apart the same
        # picture); "its one control changes the picture and brings the same picture back" reads: the figure's one control
        # is following (Enter on the focused figure follows a proposal and says so, Escape lets go), and the header's pause
        # and resume change nothing but the motion: paused again the sheet holds the same marks' colours, nothing blended
        assert await V.until(pg, "!!(window.OXA && OXA.run) && document.getElementById('company-figure').classList.contains('is-live')", 15000), "company's hero never went live on the run"
        await pg.wait_for_timeout(2600)   # its opening act (the disc becomes the sheet)
        seen = [await pg.evaluate(CO) for _ in range(1)]
        for _ in range(11):
            await pg.wait_for_timeout(210); seen.append(await pg.evaluate(CO))
        assert all(x and x["n"]["other"] == 0 for x in seen), ("company's hero: a frame of the running sheet is blended", [x and x["n"] for x in seen][:3])
        assert len({x["hash"] for x in seen}) > 1 and sum(1 for x in seen if x["n"]["green"] > 0) >= 6, ("company's hero does not light as agents propose (twelve readings 210 ms apart)", [x["n"]["green"] for x in seen])
        await pg.evaluate("OXA.run.pause(true)")
        co = await co_rest("paused in the header, company's hero figure never came to rest")
        assert co["live"] and co["old"] == 0, ("company's hero: the canvas is live and nothing of the old stage is left", co)
        assert abs(co["w"] - co["bw"]) <= 1 and abs(co["h"] - co["bh"]) <= 1, ("company's hero canvas is not its box in device pixels", co)
        assert co["n"]["paper"] > 0 and co["n"]["green"] > 0 and co["n"]["other"] == 0, ("company's hero: marks in paper and signal green only, nothing blended", co["n"])
        assert co["label"] == "Narrow agents, one job each" and co["hedge"] == "Illustrative", ("company's hero caption", co["label"], co["hedge"])
        await pg.screenshot(path=shot(f"company-hero.png"))
        assert not co["replay"] and co["buttons"] == 0, ("company's hero: it has no Replay and no button of its own (it obeys the header's)", co)
        await pg.evaluate("OXA.run.pause(false)"); await pg.wait_for_timeout(700)
        mid = await pg.evaluate(CO)
        assert mid["hash"] != co["hash"] and mid["n"]["other"] == 0, ("resumed in the header, the sheet did not move, or a frame of it is blended", mid["n"])
        await pg.screenshot(path=shot(f"company-act.png"))
        await pg.locator("#company-figure").focus(); await pg.keyboard.press("Enter")
        fo = await V.until(pg, "(() => { const s = document.querySelector('#company-figure [role=status]'); return s && /^Following P-\\d+\\.$/.test(s.textContent.trim()) ? s.textContent.trim() : ''; })()", 3000)
        assert fo, ("Enter on the focused figure did not follow a proposal and say so", (await pg.evaluate(CO))["say"])
        await pg.keyboard.press("Escape")
        assert await V.until(pg, "document.querySelector('#company-figure [role=status]').textContent.trim() === 'Stopped following.'", 3000), ("Escape did not let the proposal go and say so", (await pg.evaluate(CO))["say"])
        await pg.evaluate("OXA.run.pause(true)")
        back = await co_rest("paused again, the sheet did not come to rest")
        assert back["n"]["other"] == 0 and back["n"]["paper"] + back["n"]["green"] == co["n"]["paper"] + co["n"]["green"], ("paused again the sheet holds other marks", co["n"], back["n"])
        await pg.evaluate("OXA.run.pause(false)")
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
        # (7 until hc11, 6 since Home's §02 left, 5 since hc13r when §03 #proof left, 4 since hc31r when the lab's chapter left with the lab)
        nch = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
        assert nch == 4 and await pg.locator(".nav-ch-list a").count() == nch and await pg.locator(".chapters").count() == 0, nch
        # insights redirect
        await pg.goto(f"{BASE}/insights.html", wait_until="load"); await pg.wait_for_timeout(800)
        assert pg.url.endswith("/research.html"), pg.url
        assert not errs, errs
        print(f"desktop: research index morphs on hover, 10 articles render with TOC + figure, company's hero is live on the run (agents light as they propose, none blended), the header's pause holds it on its sheet ({co['n']['paper']} paper and {co['n']['green']} green pixels), Enter follows a proposal and Escape lets it go, the timeline reveals, {nch} chapters, insights redirects")
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
        # page heroes' 142-172; it was 303-526), and a note's hedge stands below the meta line and inside the hero (the
        # order: title, meta, drawing, hedge). hc30r (RES-1; integrate, on research's request): the hedge hangs from the
        # lattice's box by CSS (.fg > .figcap); no script places it and no class says so, so there is nothing to wait for
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
