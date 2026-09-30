"""Smoke a deploy (full URL, e.g. the Azure site, or a local server) in a real browser: figures render, company modes switch,
research hover morphs, the team is on /company only, no errors."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, sys
from pathlib import Path
from playwright.async_api import async_playwright, expect

ARG = sys.argv[1] if len(sys.argv) > 1 else "https://thankful-mushroom-0dd42611e.3.azurestaticapps.net"
BASE = ARG.rstrip("/")
OUT = Path(str(SHOTS)) / (BASE.split("//")[1].split(".")[0].replace(":", "-") + "-live")
OUT.mkdir(exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and r.url.startswith(BASE) else None)

        await pg.goto(f"{BASE}/company", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert await pg.evaluate("document.querySelector('#company-figure').classList.contains('figure-ready')"), "company figure not ready"
        await pg.screenshot(path=str(OUT / "company-hero.png"))
        for name in ("swarm", "boundary"):  # Specialize, Act (Coordinate = "company" is the default)
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
        assert await pg.locator(".chapters a").count() == 7
        await pg.locator("#research").scroll_into_view_if_needed()
        await pg.wait_for_timeout(1200)
        await pg.screenshot(path=str(OUT / "home-research.png"))
        # the team lives on the company page only
        await pg.goto(f"{BASE}/company", wait_until="load")
        await pg.locator(".crew--team").scroll_into_view_if_needed(); await pg.wait_for_timeout(1500)
        team = await pg.evaluate("[...document.querySelectorAll('.crew img')].map(i => i.complete && i.naturalWidth === 560)")
        assert len(team) == 13 and all(team), team
        await pg.locator(".crew").first.screenshot(path=str(OUT / "team.png"))
        for path in ("/company", "/blog/", "/research"):
            await pg.goto(f"{BASE}{path}", wait_until="load")
            txt = await pg.evaluate("document.body.innerText")
            assert not any(n in txt for n in ("Barnet", "Sherman", "Braintree")), (path, "Barnet Sherman must not appear")
        for path in ("/", "/research", "/platform", "/trust"):
            await pg.goto(f"{BASE}{path}", wait_until="load")
            txt = await pg.evaluate("document.body.innerText")
            assert not any(n in txt for n in ("Dubey", "Leung", "Lockhart", "Gamolsky", "Choudhri", "Schuster", "Ekeroma", "Nanawati")), path
        assert not errs, errs
        print(f"live smoke OK: team on /company only (13 portraits), no Barnet anywhere, company figure + modes, research hover morph, article 02 (toc {toc} = h2 {h2}), insights -> research, 7 chapters, 0 errors")
        await b.close()

asyncio.run(main())
