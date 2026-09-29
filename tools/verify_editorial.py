import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, json, sys
from playwright.async_api import async_playwright, expect
OUT = str(SHOTS / 'v9')
BASE = "http://127.0.0.1:8125"

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        # research index: figure ready, hover morphs
        await pg.goto(f"{BASE}/research.html", wait_until="load"); await pg.wait_for_timeout(2500)
        assert await pg.locator("#research-figure").evaluate("el => el.classList.contains('figure-ready')"), "figure not ready"
        await pg.screenshot(path=f"{OUT}\\research-hero.png")
        await pg.locator(".posts-list .post").first.hover(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#research-figure").get_attribute("data-figure-current") == "horizon"
        await pg.screenshot(path=f"{OUT}\\research-hover.png")
        await pg.locator(".posts-list .post").nth(4).hover(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#research-figure").get_attribute("data-figure-current") == "boundary"
        await pg.evaluate("document.querySelector('#series').scrollIntoView()"); await pg.wait_for_timeout(1200)
        await pg.screenshot(path=f"{OUT}\\research-list.png")
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
                await pg.screenshot(path=f"{OUT}\\article-{i+1:02d}-hero.png")
                await pg.evaluate("document.querySelector('.article').scrollIntoView()"); await pg.wait_for_timeout(600)
                await pg.screenshot(path=f"{OUT}\\article-{i+1:02d}-body.png")
            print(f"article {i+1:02d} {fig['name']:11} toc={toc} ok")
        # company: sculpture + modes + manifesto + timeline
        await pg.goto(f"{BASE}/company.html", wait_until="load"); await pg.wait_for_timeout(2500)
        assert await pg.locator("#company-figure").evaluate("el => el.classList.contains('figure-ready')")
        await pg.screenshot(path=f"{OUT}\\company-hero.png")
        await pg.locator('.company-modes button[data-figure-target="swarm"]').click(); await pg.wait_for_timeout(1500)
        assert await pg.locator("#company-figure").get_attribute("data-figure-current") == "swarm"
        assert (await pg.locator("#company-mode-copy").inner_text()).startswith("Thousands of narrow agents")
        await pg.screenshot(path=f"{OUT}\\company-specialize.png")
        await pg.locator('.company-modes button[data-figure-target="boundary"]').click(); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f"{OUT}\\company-act.png")
        for sel, name in (("#mission", "mission"), ("#story", "story"), ("#constants", "constants"), ("#lifecycles", "lifecycles")):
            await pg.evaluate(f"document.querySelector('{sel}').scrollIntoView()"); await pg.wait_for_timeout(1800)
            await pg.screenshot(path=f"{OUT}\\company-{name}.png")
        lit = await pg.evaluate("document.querySelectorAll('.manifesto .mw.is-lit').length")
        assert lit > 10, ("manifesto did not light", lit)
        assert await pg.locator(".timeline").evaluate("el => el.classList.contains('is-in')")
        # homepage research chapter
        await pg.goto(f"{BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(3000)
        await pg.evaluate("document.querySelector('#research').scrollIntoView()"); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=f"{OUT}\\home-research.png")
        assert await pg.locator(".chapters a").count() == 7
        # insights redirect
        await pg.goto(f"{BASE}/insights.html", wait_until="load"); await pg.wait_for_timeout(800)
        assert pg.url.endswith("/research.html"), pg.url
        assert not errs, errs
        print("desktop: research index morphs on hover, 10 articles render with TOC + figure, company modes switch, manifesto lights, 7 chapters, insights redirects")
        await ctx.close()
        # mobile
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for name in ("research.html", links[0], "company.html"):
            await pg.goto(f"{BASE}/{name}", wait_until="load"); await pg.wait_for_timeout(1800)
            sw = await pg.evaluate("document.documentElement.scrollWidth"); assert sw <= 391, (name, sw)
            await pg.screenshot(path=f"{OUT}\\m-{name.replace('/', '-').replace('.html', '')}.png")
            await pg.evaluate("scrollTo(0, 900)"); await pg.wait_for_timeout(800)
            await pg.screenshot(path=f"{OUT}\\m-{name.replace('/', '-').replace('.html', '')}-2.png")
        assert not errs, errs
        print("mobile: no overflow on research, article, company")
        await b.close()
    print("EDITORIAL CHECKS PASSED")
asyncio.run(main())
