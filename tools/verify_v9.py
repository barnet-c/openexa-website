"""Visual + functional pass over v9: every page at 1440/390, story beats, live objects, form, no forbidden strings."""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, json, re, sys
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = "http://127.0.0.1:8125"
OUT = Path(str(SHOTS / 'v9'))
OUT.mkdir(exist_ok=True)
PAGES = ["index", "platform", "lifecycles", "evidence", "trust", "company", "research",
         "research/01-compounding-error", "research/10-master-and-copy", "blog/index",
         "blog/examining-the-drawdown-risk-of-sector-etfs-2022", "blog/empowering-the-future-ai-copilots-and-autonomous-intelligent-agents-leading-the-way",
         "access", "404"]
FIGURE_PAGES = ["company", "research", "research/01-compounding-error"]
fname = lambda name: name.replace("/", "_")[:60]
FORBIDDEN = re.compile(r"NASDAQ|NYSE|TradeStation|Interactive Brokers|DTCC|704 458|Campus Pkwy|ajit@|\$100M\+ ARR|\$1B\+ ARR", re.I)
# the team is public on company.html; blog bylines (blog/) are the only other place names may appear.
# Barnet Sherman left the team (now a customer) and must not appear anywhere.
PEOPLE = re.compile(r"Ajit|Dubey|Leung|Lockhart|Gamolsky|Choudhri|Schuster|Parekh|Sinha|Ekeroma|Nanawati|Mehta|Kannan|Philip Bond", re.I)
TEAM_NAMES = ["Ajit K Dubey", "Dr. Tim Leung", "Mike Lockhart", "Victor Gamolsky", "Shalabh Choudhri", "John Schuster", "Subuddh Parekh",
              "Abhishek Sinha", "Dr. Julius E. Ekeroma", "Dipit Nanawati", "Kumar Mehta", "Sreeram Kannan", "Dr. Philip Bond"]
GONE = re.compile(r"Barnet|Sherman|Braintree|TIAA", re.I)
LAYOUT = """() => {
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('.beat[aria-hidden="true"]') && !el.closest('details:not([open]) > :not(summary)') && !el.closest('.table-scroll') && !el.closest('.blog-chips'); };
  const over = [...document.querySelectorAll('main h1, main h2, main h3, main p, main a, main button, main canvas, main table')].filter(vis).filter(el => { const r = el.getBoundingClientRect(); return r.left < -2 || r.right > innerWidth + 2; }).map(el => el.tagName + '.' + el.className);
  return { scrollWidth: document.documentElement.scrollWidth, overflow: over.slice(0, 6), text: document.body.innerText };
}"""

async def main():
    args = sys.argv[1:]
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        report = {}
        # ---- pages ----
        for w, h in ((1440, 1000), (390, 844)):
            ctx = await b.new_context(viewport={"width": w, "height": h})
            pg = await ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and r.url.startswith(BASE) and "/404.html" not in r.url else None)
            for name in PAGES:
                await pg.goto(f"{BASE}/{name}.html", wait_until="load")
                await pg.evaluate("document.fonts.ready")
                await pg.wait_for_timeout(2600 if name == "index" else 1200)
                m = await pg.evaluate(LAYOUT)
                bad = sorted(set(FORBIDDEN.findall(m["text"])))
                people = sorted(set(p.lower() for p in PEOPLE.findall(m["text"])))
                assert not GONE.search(m["text"]), (name, w, "Barnet Sherman must not appear", GONE.findall(m["text"]))
                if name == "company":
                    missing = [n for n in TEAM_NAMES if n not in m["text"]]
                    assert not missing, ("company page must carry the whole team", missing)
                elif not name.startswith("blog/"):
                    assert not people, (name, w, "team names outside company.html and the blog", people)
                await pg.evaluate("if (document.activeElement instanceof HTMLElement) document.activeElement.blur()")
                await pg.screenshot(path=str(OUT / f"{fname(name)}-{w}.png"))
                if w == 1440 and name != "index":
                    await pg.screenshot(path=str(OUT / f"{fname(name)}-full.png"), full_page=True)
                report[f"{name}@{w}"] = {"scrollWidth": m["scrollWidth"], "overflow": m["overflow"], "forbidden": bad, "errors": errs[:]}
                assert m["scrollWidth"] <= w + 1, (name, w, m["scrollWidth"])
                assert not m["overflow"], (name, w, m["overflow"])
                assert not bad, (name, w, bad)
                assert not errs, (name, w, errs)
                errs.clear()
            await ctx.close()
        print("pages: 0 console errors, no horizontal overflow, no forbidden strings at 1440 and 390")

        # ---- homepage story beats + objects ----
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.wait_for_timeout(2600)
        assert await pg.evaluate("document.documentElement.classList.contains('story-ready')")
        t_loader = await pg.evaluate("performance.now()")
        await pg.locator(".loader").wait_for(state="detached", timeout=15000)  # generous: CPU contention delays timers
        t_loader = (await pg.evaluate("performance.now()")) - t_loader
        print(f"loader removed within {t_loader / 1000 + 2.6:.1f}s of load")
        for i in range(5):
            await pg.locator(f'.story-idx [data-n="0{i}"]').click()
            await pg.wait_for_timeout(1400)
            await expect(pg.locator(f'.story-idx [data-n="0{i}"]')).to_have_attribute("aria-current", "step")
            await pg.screenshot(path=str(OUT / f"story-b{i}.png"))
        # hero stats must not overlap the globe canvas region: check they sit under the copy (left half)
        box = await pg.locator(".beat-0 .hero-stats").bounding_box()
        assert box and box["x"] + box["width"] < 1440 * 0.56, ("hero stats intrude on the globe", box)
        await pg.locator("[data-story-motion]").click()
        await expect(pg.locator("[data-story-motion]")).to_have_attribute("aria-pressed", "true")
        await pg.locator("[data-story-motion]").click()
        # swarm
        await pg.locator("[data-swarm-live]").scroll_into_view_if_needed()
        await pg.wait_for_timeout(4500)
        s1 = await pg.evaluate("({inflight: document.querySelector('[data-sw-inflight]').textContent, recorded: document.querySelector('[data-sw-recorded]').textContent})")
        assert int(s1["recorded"].replace(",", "")) > 0, s1
        await pg.locator("[data-swarm-live]").screenshot(path=str(OUT / "swarm.png"))
        await pg.locator("[data-sw-halt]").click()
        await expect(pg.locator("[data-sw-state]")).to_have_text("Halted")
        # chain
        await pg.locator("[data-chain]").scroll_into_view_if_needed()
        await pg.wait_for_timeout(800)
        await expect(pg.locator(".chain-list li")).to_have_count(8)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        await pg.locator(".chain-list li:nth-child(3) .ev").fill("REJECTED")
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(6)
        await pg.locator("[data-chain]").screenshot(path=str(OUT / "chain-broken.png"))
        await pg.locator("[data-chain-restore]").click()
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(0)
        # ledger stream running
        await expect(pg.locator("[data-ledger-stream] .ln").first).to_be_visible()
        # chapter rail present (7 chapters incl. Research)
        assert await pg.locator(".chapters a").count() == 7
        assert not errs, errs
        print("home: 5 beats navigable, stats clear of the globe, motion pause, swarm runs+halts, chain breaks+restores, rail has 7 chapters")

        # ---- desk on lifecycles ----
        await pg.goto(f"{BASE}/lifecycles.html#lc01", wait_until="load")
        await pg.locator("[data-gap]").scroll_into_view_if_needed()
        await pg.wait_for_timeout(5000)
        info = await pg.evaluate("({time: document.querySelector('[data-gap-time]').textContent, log: document.querySelectorAll('.desk-log li').length, state: document.querySelector('[data-gap-state]').textContent})")
        assert info["time"] != "09:30 ET", info
        await pg.locator("[data-gap]").screenshot(path=str(OUT / "desk.png"))
        print("desk:", info)

        # ---- access form ----
        await pg.goto(f"{BASE}/access.html#managers", wait_until="load")
        await expect(pg.locator('input[value="Manager platform"]')).to_be_checked()
        await pg.locator("#name").fill("Test Person"); await pg.locator("#email").fill("t@example.com")
        await pg.locator('button[type="submit"]').click()
        await expect(pg.locator("form[data-access]")).to_be_hidden()
        href = await pg.locator("[data-mailto]").get_attribute("href")
        assert href.startswith("mailto:ajit@openexa.com?subject=") and "Manager%20platform" in href, href
        await pg.locator("[data-form-edit]").click()
        await expect(pg.locator("#name")).to_have_value("Test Person")
        print("access: linked path preselected, draft prepared, edit restores input")
        assert not errs, errs

        # ---- company team: six portraits load, monochrome at rest, colour on hover ----
        await pg.goto(f"{BASE}/company.html#team", wait_until="load")
        await pg.locator(".crew--team").scroll_into_view_if_needed()
        await pg.wait_for_timeout(1500)
        team = await pg.evaluate("[...document.querySelectorAll('.crew img')].map(i => ({ok: i.complete && i.naturalWidth === 560, filter: getComputedStyle(i).filter}))")
        assert len(team) == 13 and all(t["ok"] for t in team), team
        assert all("grayscale(1)" in t["filter"] for t in team), team
        await pg.locator(".crew > li").nth(2).hover()
        await pg.wait_for_timeout(900)
        hovered = await pg.locator(".crew > li").nth(2).locator("img").evaluate("i => getComputedStyle(i).filter")
        assert hovered == "none", hovered
        assert await pg.locator(".sec-head .idx").all_inner_texts() == ["01", "02", "03", "04", "05"]
        assert await pg.locator(".crew--team > li").count() == 5 and await pg.locator(".crew--advisors > li").count() == 8
        names_team = await pg.locator(".crew--team > li h3").all_inner_texts()
        names_adv = await pg.locator(".crew--advisors > li h3").all_inner_texts()
        # Victor and Subuddh swapped places on 2026-10-02: Subuddh holds Victor's old team slot (4th), Victor Subuddh's old advisor slot (5th)
        assert names_team == ["Ajit K Dubey", "Dr. Tim Leung", "Mike Lockhart", "Subuddh Parekh", "Shalabh Choudhri"], names_team
        assert names_adv == ["Kumar Mehta", "Sreeram Kannan", "Dr. Philip Bond", "John Schuster", "Victor Gamolsky", "Abhishek Sinha", "Dr. Julius E. Ekeroma", "Dipit Nanawati"], names_adv
        roles = await pg.locator(".crew--advisors > li .role").all_inner_texts()
        assert all(r.upper().startswith("ADVISOR") for r in roles), roles
        assert not any("CHIEF PRODUCT" in r.upper() for r in roles), roles
        team_ids = await pg.locator(".crew--team > li .n").all_inner_texts()
        adv_ids = await pg.locator(".crew--advisors > li .n").all_inner_texts()
        assert team_ids[3] == "T-04" and adv_ids[4] == "A-05", (team_ids, adv_ids)
        ajit = await pg.locator(".crew--team > li").first.inner_text()
        assert "Ajit K Dubey" in ajit and not re.search(r"patent|fourteen", ajit, re.I), ajit
        more = pg.locator(".crew--team > li:nth-child(2) details.crew-more")
        assert await more.evaluate("d => !d.open")
        await more.locator("summary").click(); await pg.wait_for_timeout(300)
        assert await more.evaluate("d => d.open && d.querySelector('.crew-bio').innerText.length > 400")
        stats = await pg.locator(".crew-stats").inner_text()
        assert "PATENT" not in stats.upper() and "100+" in stats, stats
        print("company: 5 team + 8 advisors (Victor and Subuddh swapped places), 13 portraits (560px masters), monochrome at rest, colour on hover, full descriptions expand, no patent count, sections 01-05")
        assert await pg.locator('.crew a[href*="scholar.google.com/citations?user=P40aOHIAAAAJ"]').count() == 1
        # ---- blog: collections filter, hash deep link, cards resolve ----
        await pg.goto(f"{BASE}/blog/index.html#markets", wait_until="load")
        await pg.wait_for_timeout(900)
        shown = await pg.evaluate("[...document.querySelectorAll('[data-blog-collection]')].filter(s => !s.hidden).map(s => s.id)")
        assert shown == ["markets"], shown
        await pg.locator('.blog-chips [data-blog-filter="all"]').click()
        await pg.wait_for_timeout(600)
        shown = await pg.evaluate("[...document.querySelectorAll('[data-blog-collection]')].filter(s => !s.hidden).length")
        assert shown == 3, shown
        assert await pg.locator("#munis").count() == 0
        cards = await pg.locator(".blog-card").count()
        assert cards == 29, cards
        assert await pg.locator('#markets a[href*="scholar.google.com"]').count() == 1
        assert await pg.locator("#series .series-card").count() == 4
        await pg.locator('.blog-chips [data-blog-filter="markets"]').click(); await pg.wait_for_timeout(400)
        assert await pg.evaluate("document.querySelector('[data-blog-series]').hidden")
        await pg.locator('.blog-chips [data-blog-filter="ai"]').click(); await pg.wait_for_timeout(400)
        assert not await pg.evaluate("document.querySelector('[data-blog-series]').hidden")
        await pg.goto(f"{BASE}/blog/rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies.html", wait_until="load")
        assert await pg.evaluate("document.querySelector('.series-box li[aria-current=\"true\"] b').textContent") == "Part 1"
        assert await pg.locator(".series-box li").count() == 4
        print("blog: featured Gen-AI series (4 parts) shows under All/AI, hides under other filters; series nav marks the current part")
        print(f"blog: {cards} cards in 3 collections, filter + #hash deep link work, scholar link present")
        assert not errs, errs
        await ctx.close()

        # ---- resolution: canvases render at device resolution (2x here), within the UHD budget ----
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.wait_for_timeout(3000)
        story = await pg.evaluate("(c => ({w: c.width, cw: c.clientWidth}))(document.querySelector('canvas'))")
        assert story["w"] == story["cw"] * 2, story
        await pg.goto(f"{BASE}/company.html", wait_until="load")
        await pg.wait_for_timeout(2500)
        figs = await pg.evaluate("[...document.querySelectorAll('[data-figure] canvas')].map(c => ({w: c.width, cw: c.clientWidth}))")
        assert figs and all(abs(f["w"] - f["cw"] * 2) <= 2 for f in figs), figs
        print(f"resolution: story canvas {story['w']}px for {story['cw']}css px; figures {[(f['cw'], f['w']) for f in figs]}")
        await ctx.close()

        # ---- no JS / no WebGL ----
        ctx = await b.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
        pg = await ctx.new_page()
        for name in PAGES:
            await pg.goto(f"{BASE}/{name}.html", wait_until="load")
            op = await pg.locator("main h1").first.evaluate("el => getComputedStyle(el).opacity")
            assert op != "0", (name, "h1 hidden without JS")
            sw = await pg.evaluate("document.documentElement.scrollWidth")
            assert sw <= 391, (name, sw)
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.screenshot(path=str(OUT / "index-nojs-390.png"), full_page=False)
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script("(() => { const o = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(k, ...a) { return /webgl/.test(k) ? null : o.call(this, k, ...a); }; })();")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert await pg.evaluate("document.documentElement.classList.contains('no-webgl')")
        await pg.screenshot(path=str(OUT / "index-nowebgl.png"))
        for name in FIGURE_PAGES:
            await pg.goto(f"{BASE}/{name}.html", wait_until="load")
            await pg.wait_for_timeout(1200)
            st = await pg.evaluate("[...document.querySelectorAll('[data-figure]')].map(s => s.classList.contains('no-figure'))")
            assert st and all(st), (name, "figure stage did not fall back without WebGL", st)
        await pg.screenshot(path=str(OUT / "article-nowebgl.png"))
        await ctx.close()
        print("fallbacks: readable without JS on every page; no-WebGL homepage + figure stages fall back")
        await b.close()
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("V9 CHECKS PASSED")

asyncio.run(main())
