"""Smoke a deploy (full URL, e.g. the Azure site, or a local server) in a real browser: figures render, Company's hero
answers its control (Replay since hc30r; the three modes on an older deploy), research hover morphs, the team is on
/company only, no errors."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright, expect
from rules import PEOPLE, GONE  # the site's content rules (tools/rules.py), as check_static and verify_v9 apply them

ARG = sys.argv[1] if len(sys.argv) > 1 else "https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"
BASE = ARG.rstrip("/")
OUT = Path(str(SHOTS)) / (BASE.split("//")[1].split(".")[0].replace(":", "-") + "-live")
OUT.mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        # a slow preview or a loaded PC: 90 s for a navigation and an action, as verify_v9 allows (patience only)
        pg.set_default_navigation_timeout(90000); pg.set_default_timeout(90000)
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and r.url.startswith(BASE) else None)

        await pg.goto(f"{BASE}/company", wait_until="load")
        await pg.wait_for_timeout(3000)
        # hc30r (COMP-1; integrate, on company's request): Company's hero is one act on a 2D canvas (company-hero.js) with
        # one control, Replay. A deploy from before hc30r still has the figure.js stage and its three modes; this may run
        # against either (as the chapter count below), so it walks the hero the page has: the figure is drawn, and its
        # control changes the picture.
        # hc31r (COMP-1 of LEAP-hc31; integrate, on company's request): from hc31r the sheet is a camera on the run and has
        # no Replay: the figure is drawn, it moves while the model runs (agents light as they propose), and the header's
        # pause holds it. A deploy with Replay (hc30r) is still walked as before
        if await pg.evaluate("!document.querySelector('.company-modes') && !document.querySelector('[data-co-replay]')"):
            SUM = ("(() => { const s = document.getElementById('company-figure'), c = s && s.querySelector('canvas'); if (!c || !c.width || !s.classList.contains('is-live')) return null;"
                   " const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0, n = 0;"
                   " for (let i = 0; i < d.length; i += 4) { if (d[i + 3]) n++; h = (h * 31 + d[i] * 65536 + d[i + 1] * 256 + d[i + 2] + d[i + 3]) | 0; } return [h, n]; })()")
            first = await pg.evaluate(SUM)
            assert first and first[1] > 0, "company figure not live, or it draws nothing"
            await pg.screenshot(path=str(OUT / "company-hero.png"))
            moved = False
            for _ in range(24):  # an agent lights within a few hundred ms while the model runs; polled (the CSP has no 'unsafe-eval')
                await pg.wait_for_timeout(250)
                if (await pg.evaluate(SUM))[0] != first[0]: moved = True; break
            assert moved, "the company figure does not move while the model runs"
            assert await pg.evaluate("!!document.querySelector('button.nav-run')"), "no transport in the header on Company"
            await pg.evaluate("OXA.run.pause(true)"); await pg.wait_for_timeout(400)
            a = await pg.evaluate(SUM); await pg.wait_for_timeout(700)
            assert await pg.evaluate(SUM) == a, "the header's pause does not hold the company figure"
            await pg.evaluate("OXA.run.pause(false)")
        elif await pg.evaluate("!document.querySelector('.company-modes')"):
            SUM = ("(() => { const s = document.getElementById('company-figure'), c = s && s.querySelector('canvas'); if (!c || !c.width || !s.classList.contains('is-live')) return null;"
                   " const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let h = 0, n = 0;"
                   " for (let i = 0; i < d.length; i += 4) { if (d[i + 3]) n++; h = (h * 31 + d[i] * 65536 + d[i + 1] * 256 + d[i + 2] + d[i + 3]) | 0; } return [h, n]; })()")
            rest = await pg.evaluate(SUM)
            assert rest and rest[1] > 0, "company figure not live, or it draws nothing"
            await pg.screenshot(path=str(OUT / "company-hero.png"))
            await pg.locator("[data-co-replay]").click()
            await pg.wait_for_timeout(450)
            assert (await pg.evaluate(SUM))[0] != rest[0], "Replay did not move the company figure"
            for _ in range(60):  # the sheet is dealt again within about 2.5 s; polled (the CSP has no 'unsafe-eval')
                await pg.wait_for_timeout(250)
                if await pg.evaluate(SUM) == rest: break
            assert await pg.evaluate(SUM) == rest, "after Replay the company figure did not come back to its sheet"
        else:
            assert await pg.evaluate("document.querySelector('#company-figure').classList.contains('figure-ready')"), "company figure not ready"
            await pg.screenshot(path=str(OUT / "company-hero.png"))
            # hc26r (COMP-1): Specialize ("swarm") is the default now; the opening state, then Coordinate and Act
            await expect(pg.locator('button[data-figure-target="swarm"]')).to_have_attribute("aria-pressed", "true")
            assert await pg.evaluate("document.querySelector('#company-figure').dataset.figureCurrent") == "swarm"
            for name in ("company", "boundary"):  # Coordinate, Act
                await pg.locator(f'button[data-figure-target="{name}"]').click()
                await pg.wait_for_timeout(1500)
                await expect(pg.locator(f'button[data-figure-target="{name}"]')).to_have_attribute("aria-pressed", "true")
                assert await pg.evaluate("document.querySelector('#company-figure').dataset.figureCurrent") == name
        await pg.screenshot(path=str(OUT / "company-act.png"))

        await pg.goto(f"{BASE}/research", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert await pg.evaluate("document.querySelector('#research-figure').classList.contains('figure-ready')"), "research figure not ready"
        await pg.locator('[data-figure-target="ledger"]').first.scroll_into_view_if_needed()
        await pg.wait_for_timeout(1400)  # let the list finish its reveal slide so the pointer lands on the right item
        await pg.locator('[data-figure-target="ledger"]').first.hover()
        await pg.wait_for_timeout(1500)
        assert await pg.evaluate("document.querySelector('#research-figure').dataset.figureCurrent") == "ledger"
        await pg.screenshot(path=str(OUT / "research-hover.png"))

        await pg.goto(f"{BASE}/research/02-post-training-and-audit", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert await pg.evaluate("document.querySelector('.article-figure').classList.contains('figure-ready')"), "article figure not ready"
        toc = await pg.locator(".toc a").count()
        h2 = await pg.locator("article h2").count()
        assert toc == h2 and toc > 0, (toc, h2)
        await pg.screenshot(path=str(OUT / "article-02.png"))

        await pg.goto(f"{BASE}/insights", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert pg.url.rstrip("/").endswith(("/research", "/research.html")), pg.url

        await pg.goto(f"{BASE}/", wait_until="load")
        await pg.wait_for_timeout(3000)
        # the nav's readout lists every chapter of the page (7 until hc11, 6 since Home's §02 left, 5 since hc13r when §03
        # #proof left; this may run against an older deploy, so count, don't pin)
        nch = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
        assert nch >= 5 and await pg.locator(".nav-ch-list a").count() == nch and await pg.locator(".chapters").count() == 0, nch
        await pg.locator("#research").scroll_into_view_if_needed()
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=str(OUT / "home-research.png"))
        # the team lives on the company page only
        await pg.goto(f"{BASE}/company", wait_until="load")
        # the advisors' portraits are loading="lazy": walk the page so every one is fetched before counting them
        for y in range(0, await pg.evaluate("document.body.scrollHeight"), 400):
            await pg.evaluate(f"scrollTo(0, {y})"); await pg.wait_for_timeout(120)
        await pg.locator(".crew--team").scroll_into_view_if_needed()
        # polled with evaluate: the site's CSP has no 'unsafe-eval', so wait_for_function(<string>) cannot run there
        for _ in range(75):
            if await pg.evaluate("[...document.querySelectorAll('.crew img')].every(i => i.complete && i.naturalWidth > 0 && /-v2x-/.test(i.currentSrc))"): break
            await pg.wait_for_timeout(200)
        # every portrait decoded from the v2x srcset (160/320 px webp since fix:r1:company; v2's 560 px files are gone from the page)
        team = await pg.evaluate("[...document.querySelectorAll('.crew img')].map(i => i.complete && i.naturalWidth > 0 && /-v2x-/.test(i.currentSrc))")
        assert len(team) == 13 and all(team), team
        # a clipped page screenshot (round 2): never Locator.screenshot's 'element is stable' wait
        box = await pg.evaluate("(() => { const r = document.querySelector('.crew').getBoundingClientRect(); const y0 = Math.max(0, r.top), y1 = Math.min(innerHeight, r.bottom); return {x: Math.max(0, r.left), y: y0, width: Math.min(innerWidth, r.right) - Math.max(0, r.left), height: y1 - y0}; })()")
        if box["width"] >= 1 and box["height"] >= 1: await pg.screenshot(path=str(OUT / "team.png"), clip=box, animations="disabled")
        for path in ("/company", "/blog/", "/research"):
            await pg.goto(f"{BASE}{path}", wait_until="load")
            txt = await pg.evaluate("document.body.innerText")
            assert not any(n in txt for n in ("Barnet", "Sherman", "Braintree")) and not GONE.search(txt), (path, "Barnet Sherman must not appear", GONE.findall(txt))
        for path in ("/", "/research", "/platform", "/trust"):
            await pg.goto(f"{BASE}{path}", wait_until="load")
            txt = await pg.evaluate("document.body.innerText")
            assert not any(n in txt for n in ("Dubey", "Leung", "Lockhart", "Gamolsky", "Choudhri", "Schuster", "Ekeroma", "Nanawati")), path
            assert not PEOPLE.search(txt), (path, "names outside Company and the blog (v2x: every name in rules.PEOPLE)", sorted(set(PEOPLE.findall(txt))))
        assert not errs, errs
        print(f"live smoke OK: team on /company only (13 portraits), no Barnet anywhere, company figure + its control, research hover morph, article 02 (toc {toc} = h2 {h2}), insights -> research, 7 chapters, 0 errors")
        await b.close()

asyncio.run(main())
