"""Visual + functional pass over v9: every page at 1440/390, story beats, live objects, form, no forbidden strings.
The homepage systems are checked as one page: the overture reads the sessions record, the nav's chapter readout, the
architecture explorer, the swarm lab's events reaching the ledger trace, the chain, the proof chart; then Proof, Trust
and Platform, a phone, reduced motion, a starved requestAnimationFrame, no JavaScript and no WebGL."""
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
# the site's CSP has no 'unsafe-eval', so Playwright's wait_for_function(<string>) cannot compile there: poll instead
async def until(pg, expr, timeout=10000, every=100):
    waited = 0
    while True:
        v = await pg.evaluate(expr)
        if v or waited >= timeout: return v
        await pg.wait_for_timeout(every); waited += every
# every 'oxa:settled' (swarm lab) and 'oxa:recorded' (ledger trace) on the page, with the time it was heard
EVENTS = """(() => { const ev = window.__oxaEv = {settled: [], recorded: []};
  document.addEventListener('oxa:settled', e => ev.settled.push(Object.assign({at: performance.now()}, e.detail)));
  document.addEventListener('oxa:recorded', e => ev.recorded.push(Object.assign({at: performance.now()}, e.detail))); })();"""
from rules import FORBIDDEN, PEOPLE, TEAM_NAMES, GONE  # the site's content rules (tools/rules.py)
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
        await ctx.add_init_script(EVENTS)
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
        await expect(pg.locator("[data-story-motion]")).to_have_text("Resume motion")
        await pg.locator("[data-story-motion]").click()
        # the overture reads the sessions record (#oxa-sessions): a column, a day tag and an ink copy per session; derived copy
        st = await pg.evaluate("""(() => ({ days: document.querySelectorAll('.story-labels .story-lab.day').length,
            prem: document.querySelectorAll('.story-labels .story-lab.day.is-prem').length, ink: document.querySelectorAll('.story-ink .story-lab').length,
            tally: [...document.querySelectorAll('[data-story-n=tally]')].map(e => e.textContent) }))()""")
        assert st == {"days": 10, "prem": 5, "ink": 10, "tally": ["Ten for ten.", "Ten for ten."]}, st
        # the last beat has faded before the stage's exit could carry it under the bar
        await pg.evaluate("(() => { const s = document.querySelector('.story'); window.scrollTo({top: s.offsetTop + s.offsetHeight - innerHeight * 0.5, behavior: 'instant'}); })()")
        op = await until(pg, "(() => { const o = +getComputedStyle(document.querySelector('.beat-4')).opacity; return o < 0.05 ? String(o) : ''; })()", 4000)
        assert op, ("beat 4 still visible past the stage's end", await pg.evaluate("getComputedStyle(document.querySelector('.beat-4')).opacity"))
        # the nav: the chapter readout replaced the fixed rail; its list has the 7 chapters; the bar takes a dark band's tone
        assert await pg.locator(".nav-ch-list a").count() == 7 and await pg.locator(".chapters").count() == 0
        await pg.evaluate("document.querySelector('#proof').scrollIntoView({behavior: 'instant'})")
        lab = await until(pg, "(() => { const l = document.querySelector('.nav-ch-btn').getAttribute('aria-label') || ''; return l.includes('Proof') && document.querySelector('.nav').classList.contains('nav--dark') ? l : ''; })()", 4000)
        assert lab, ("chapter readout / dark bar over #proof", await pg.locator(".nav-ch-btn").get_attribute("aria-label"))
        # architecture explorer (home 02): eight layer buttons, the boundary after 04; arrows, Enter, Escape, Home/End, hover readout
        await pg.evaluate("document.querySelector('#stack').scrollIntoView({behavior: 'instant'})")
        assert await until(pg, "!!document.querySelector('#stack .arch.is-wide.is-ready')", 10000), "architecture explorer not ready at 1440"
        assert await pg.locator("#stack .arch-layer").count() == 8
        assert await pg.evaluate("[...document.querySelector('#stack .arch-list').children].filter(e => !e.classList.contains('arch-panel')).findIndex(e => e.classList.contains('arch-bound'))") == 4
        await pg.locator("#arch0-b1").focus()
        for _ in range(3): await pg.keyboard.press("ArrowDown")
        assert await pg.evaluate("document.activeElement.id") == "arch0-b4"
        await expect(pg.locator("#arch0-b4")).to_have_class(re.compile(r"\bis-hot\b"))
        await pg.keyboard.press("Enter")
        await expect(pg.locator("#arch0-b4")).to_have_attribute("aria-expanded", "true")
        await expect(pg.locator(".arch-card #arch0-p4")).to_be_visible()
        await pg.keyboard.press("Escape")
        await expect(pg.locator("#arch0-b4")).to_have_attribute("aria-expanded", "false")
        assert await pg.evaluate("document.activeElement.id") == "arch0-b4"
        await pg.keyboard.press("End"); assert await pg.evaluate("document.activeElement.id") == "arch0-b8"
        await pg.keyboard.press("Home"); assert await pg.evaluate("document.activeElement.id") == "arch0-b1"
        await pg.locator("#arch0-b5").hover()
        await expect(pg.locator("#stack .arch")).to_have_class(re.compile(r"\bhas-hot\b"))
        await expect(pg.locator("#stack .arch-card .sum-nm")).to_have_text("Routing Layer")
        assert await until(pg, "getComputedStyle(document.querySelector('#stack .arch-card')).opacity === '1'", 3000), "readout card not shown on hover"
        await pg.mouse.move(5, 450)
        # swarm lab: runs, announces settlements (at most 4 a second, in the agreed shape), follows by keyboard, halts and drains
        await pg.locator("[data-swarm-live]").scroll_into_view_if_needed()
        n0 = await pg.evaluate("window.__oxaEv.settled.length")
        await pg.wait_for_timeout(5000)
        s1 = await pg.evaluate("({inflight: document.querySelector('[data-sw-inflight]').textContent, recorded: document.querySelector('[data-sw-recorded]').textContent})")
        assert int(s1["recorded"].replace(",", "")) > 0, s1
        ev = await pg.evaluate(f"window.__oxaEv.settled.slice({n0})")
        gaps = [e2["at"] - e1["at"] for e1, e2 in zip(ev, ev[1:])]
        assert len(ev) >= 10, ("oxa:settled events in 5 s in view", len(ev))
        assert min(gaps) >= 245, ("oxa:settled closer than 250 ms", min(gaps))
        assert all(re.fullmatch(r"P-\d{5}", e["id"]) and 1 <= e["lane"] <= 5 and isinstance(e["ts"], (int, float)) for e in ev), ev[:3]
        await pg.locator("[data-swarm-live]").screenshot(path=str(OUT / "swarm.png"))
        await pg.locator("[data-sw-follow]").focus(); await pg.keyboard.press("Enter")
        await expect(pg.locator("[data-sw-follow]")).to_have_attribute("aria-pressed", "true")
        await expect(pg.locator("[data-sw-callout]")).to_be_visible()
        await pg.keyboard.press("Escape")
        await expect(pg.locator("[data-sw-callout]")).to_be_hidden()
        assert await pg.evaluate("document.activeElement === document.querySelector('[data-sw-follow]')")
        await pg.locator("[data-sw-halt]").click()
        await expect(pg.locator("[data-sw-state]")).to_have_text("Halted")
        drained = await until(pg, "document.querySelector('[data-sw-inflight]').textContent.trim() === '0' && document.querySelector('[data-sw-banner]').textContent.includes('drained')", 30000, 250)
        assert drained, ("halt did not drain", await pg.evaluate("[document.querySelector('[data-sw-inflight]').textContent, document.querySelector('[data-sw-banner]').textContent]"))
        # the ledger trace (home 06) recorded what the swarm settled, answering each announcement with a hash-linked record
        await pg.evaluate("document.querySelector('[data-ledger=live]').scrollIntoView({block: 'center', behavior: 'instant'})")
        await pg.wait_for_timeout(1200)
        await expect(pg.locator("[data-ledger-stream] .ln").first).to_be_visible()
        rec = await until(pg, "(() => { const r = window.__oxaEv.recorded, ids = new Set(window.__oxaEv.settled.map(e => e.id)); return r.length && r.every(x => /^[0-9a-f]{64}$/.test(x.hash) && /^#[0-9a-f]{4}$/.test(x.record) && ids.has(x.id)) ? r.length : 0; })()", 12000, 200)
        assert rec, ("swarm announcements were not recorded by the ledger", await pg.evaluate("window.__oxaEv.recorded.slice(0, 3)"))
        await expect(pg.locator("[data-lt-swarm]")).to_contain_text("from the swarm above")
        await expect(pg.locator("[data-ledger=live] .lt-rec.is-swarm").first).to_be_visible()
        await pg.evaluate("for (let i = 0; i < 5; i++) document.dispatchEvent(new CustomEvent('oxa:settled', {detail: {id: 'P-9990' + i, lane: i + 1, ts: Date.now()}}))")
        five = await until(pg, "(() => { const r = window.__oxaEv.recorded.filter(x => /^P-9990\\d$/.test(x.id)); return r.length === 5 && new Set(r.map(x => x.record)).size === 5 && r.every(x => /^[0-9a-f]{64}$/.test(x.hash)) ? 5 : 0; })()", 6000)
        assert five, ("5 announcements -> 5 records", await pg.evaluate("window.__oxaEv.recorded.filter(x => /^P-9990/.test(x.id))"))
        # the stream is one tab stop; arrows inspect; Escape returns to the head and focuses Pause
        await pg.locator('[data-ledger=live] .lt-rec[tabindex="0"]').focus()
        await expect(pg.locator("[data-ledger=live] [data-lt-state]")).to_contain_text("Inspecting #")
        sel0 = await pg.evaluate("[...document.querySelectorAll('[data-ledger=live] .lt-rec')].findIndex(li => li.getAttribute('aria-selected') === 'true')")
        await pg.keyboard.press("ArrowLeft")
        sel1 = await pg.evaluate("[...document.querySelectorAll('[data-ledger=live] .lt-rec')].findIndex(li => li.getAttribute('aria-selected') === 'true')")
        assert sel1 >= 0 and sel1 == sel0 - 1, (sel0, sel1)
        await pg.keyboard.press("Escape")
        assert await pg.evaluate("document.activeElement === document.querySelector('[data-ledger=live] [data-lt-play]')")
        # chain
        await pg.locator("[data-chain]").scroll_into_view_if_needed()
        await pg.wait_for_timeout(800)
        await expect(pg.locator(".chain-list li")).to_have_count(8)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        await pg.locator(".chain-list li:nth-child(3) .ev").fill("REJECTED")
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(6)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain broken at record 03")
        await pg.locator("[data-chain]").screenshot(path=str(OUT / "chain-broken.png"))
        await pg.locator("[data-chain-restore]").click()
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(0)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        await pg.locator("[data-chain-try]").click()
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(6)
        await pg.locator("[data-chain-restore]").click()
        await expect(pg.locator(".chain-list .is-broken")).to_have_count(0)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        # proof: the chart is a listbox of the ten sessions with one tab stop; arrows select, the inspector follows, Escape clears
        await expect(pg.locator("#proof .proof.is-built")).to_have_count(1)
        opts = pg.locator("#proof [role=listbox] [role=option]")
        await expect(opts).to_have_count(10)
        assert await pg.locator('#proof [role=option][tabindex="0"]').count() == 1
        await opts.nth(0).focus(); await pg.keyboard.press("ArrowRight")
        await expect(opts.nth(1)).to_have_attribute("aria-selected", "true")
        await expect(pg.locator("#proof .pf-read")).to_contain_text("Day 02")
        await pg.keyboard.press("Escape")
        await expect(pg.locator('#proof [role=option][aria-selected="true"]')).to_have_count(0)
        assert not errs, errs
        print(f"home: 5 beats navigable, stats clear of the globe, motion pause, overture reads the record (10 columns, 5 premium), last beat clear of the bar, "
              f"7 chapters in the nav list (no rail), explorer keys/hover, swarm {len(ev)} events/5 s (gaps >= {min(gaps):.0f} ms), follow by keyboard, halt drains, "
              f"{rec} swarm announcements recorded with hashes, stream keyboard, chain breaks (typed and one-tap) + restores, proof listbox")

        # ---- Proof, Trust, Platform ----
        await pg.goto(f"{BASE}/evidence.html", wait_until="load")
        await expect(pg.locator("#performance [role=option]")).to_have_count(10)
        await pg.locator("table[data-proof-table] tbody tr:nth-child(3)").hover()
        await expect(pg.locator("#performance .pf-lane").nth(2)).to_have_class(re.compile(r"\bis-on\b"))
        await expect(pg.locator("table[data-proof-table] tbody tr:nth-child(3)")).to_have_class(re.compile(r"\bis-hot\b"))
        await pg.goto(f"{BASE}/trust.html", wait_until="load")
        await expect(pg.locator("[data-ledger=replay] .lt-rec")).to_have_count(9)
        await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("9 records verify")
        await pg.locator("[data-lt-verify]").click()
        await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Verified here · 8 of 8 links hold", timeout=10000)
        await pg.goto(f"{BASE}/platform.html", wait_until="load")
        await pg.evaluate("document.querySelector('#architecture').scrollIntoView({behavior: 'instant'})")
        assert await until(pg, "!!document.querySelector('#architecture .arch.is-wide.is-ready')", 10000), "platform explorer not ready"
        assert await pg.locator("#architecture .arch-layer").count() == 8
        assert not errs, errs
        print("proof: table rows light their sessions; trust: 9-record trace verifies 8 of 8 links; platform: explorer ready with 8 layers")

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
        # the advisors' portraits are loading="lazy": walk the page so every one is fetched before counting them
        for y in range(0, await pg.evaluate("document.body.scrollHeight"), 400):
            await pg.evaluate(f"scrollTo(0, {y})"); await pg.wait_for_timeout(120)
        await pg.locator(".crew--team").scroll_into_view_if_needed()
        await pg.wait_for_function("[...document.querySelectorAll('.crew img')].every(i => i.complete && i.naturalWidth === 560)", timeout=15000)
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

        # ---- phone: the explorer is an accordion, a chapter lands under the 64 px bar, the menu sheet is a popover over an inert page ----
        ctx = await b.new_context(viewport={"width": 390, "height": 844})
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.locator(".loader").wait_for(state="detached", timeout=15000)
        await pg.evaluate("document.querySelector('#stack').scrollIntoView({behavior: 'instant'})")
        assert await until(pg, "!!document.querySelector('#stack .arch.is-narrow')", 10000), "explorer not narrow at 390"
        await pg.locator("#arch0-b4").click()
        await expect(pg.locator("#arch0-p4")).to_be_visible()
        assert await pg.evaluate("document.querySelector('#arch0-p4').previousElementSibling === document.querySelectorAll('#stack h3.arch-h')[3]")
        assert await pg.evaluate("document.documentElement.scrollWidth") == 390
        await pg.locator(".nav-ch-btn").click()
        await pg.locator(".nav-ch-list a").nth(3).click()
        land = await until(pg, "(() => { const t = document.querySelector('#proof').getBoundingClientRect().top, b = document.querySelector('.nav').getBoundingClientRect().bottom; return Math.abs(t - b) <= 2 ? [t, b] : null; })()", 6000)
        assert land, ("chapter 04 did not land under the bar at 390", await pg.evaluate("[document.querySelector('#proof').getBoundingClientRect().top, document.querySelector('.nav').getBoundingClientRect().bottom]"))
        await pg.locator(".nav-toggle").click()
        assert await until(pg, "document.querySelector('#site-menu').matches(':popover-open') && document.querySelector('main').inert", 3000), "menu sheet did not open"
        await pg.keyboard.press("Escape")
        assert await until(pg, "!document.querySelector('#site-menu').matches(':popover-open') && !document.querySelector('main').inert", 3000), "menu sheet did not close"
        assert not errs, errs
        await ctx.close()
        print("phone: explorer accordion opens inline, chapter 04 lands under the bar, menu sheet opens (page inert) and Escape closes it")

        # ---- reduced motion: the explorer is open and still; the ledger stream starts paused; Trust verifies at once ----
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.locator(".loader").wait_for(state="detached", timeout=15000)
        assert await pg.locator("#stack .arch.is-ready").count() == 1
        await expect(pg.locator("#stack .arch-motion")).to_be_hidden()
        await expect(pg.locator("[data-ledger=live] [data-lt-state]")).to_have_text("Paused · illustrative stream")
        await pg.goto(f"{BASE}/trust.html", wait_until="load")
        await pg.locator("[data-lt-verify]").click()
        await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Verified here · 8 of 8 links hold", timeout=1500)
        assert not errs, errs
        await ctx.close()
        print("reduced motion: explorer open and still (no motion control), stream paused, Trust verifies at once")

        # ---- the loader finishes on elapsed time, not on frames: with requestAnimationFrame starved it still lifts ----
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script("window.requestAnimationFrame = () => 0;")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/index.html", wait_until="commit")
        gone = await until(pg, "(() => { const l = document.querySelector('.loader'); return document.readyState !== 'loading' && (!l || !l.isConnected) ? performance.now() : 0; })()", 9000, 50)
        assert gone and gone <= 4500, ("loader still up with requestAnimationFrame starved", gone)
        await ctx.close()
        print(f"loader: removed {gone / 1000:.1f}s after navigation with requestAnimationFrame starved")

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
        nj = await pg.evaluate("""(() => { const q = s => document.querySelectorAll(s).length, kids = [...document.querySelectorAll('#stack .layers > *')];
          const bi = kids.findIndex(e => e.classList.contains('layer-boundary'));
          return { loader: getComputedStyle(document.querySelector('.loader')).display, proof: q('.proof-list li'), stream: q('[data-ledger-stream] .lt-rec'),
            chain: q('.chain-list li'), gates: q('[data-sw-gates] li'), bar: getComputedStyle(document.querySelector('.swarm-bar')).display,
            layers: q('#stack .layers .layer'), before: bi < 0 ? -1 : kids.slice(0, bi).filter(e => e.classList.contains('layer')).length,
            io: [...document.querySelectorAll('#stack .layers .layer')].every(l => l.querySelectorAll('dl.io dd').length === 2) }; })()""")
        assert nj["loader"] == "none" and nj["proof"] == 10 and nj["stream"] == 8 and nj["chain"] == 8 and nj["gates"] == 6 and nj["bar"] == "none", nj
        assert nj["layers"] == 8 and nj["before"] == 4 and nj["io"], nj
        await pg.locator(".nav-toggle").click()
        assert await pg.evaluate("document.querySelector('#site-menu').matches(':popover-open')"), "menu sheet does not open without JavaScript"
        await pg.goto(f"{BASE}/evidence.html", wait_until="load")
        assert await pg.locator("[data-proof-fig]").is_hidden() and await pg.locator("table[data-proof-table] tbody tr").count() == 10
        await pg.goto(f"{BASE}/trust.html", wait_until="load")
        assert await pg.locator(".lt-rec").count() == 9
        await pg.goto(f"{BASE}/platform.html", wait_until="load")
        assert await pg.locator("#architecture .layers .layer").count() == 8
        await ctx.close()
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script("(() => { const o = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(k, ...a) { return /webgl/.test(k) ? null : o.call(this, k, ...a); }; })();")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        await pg.wait_for_timeout(2500)
        assert await pg.evaluate("document.documentElement.classList.contains('no-webgl')")
        t_shot = asyncio.get_running_loop().time()
        await pg.screenshot(path=str(OUT / "index-nowebgl.png"))
        print(f"no-WebGL homepage screenshot: {asyncio.get_running_loop().time() - t_shot:.1f}s")
        for name in FIGURE_PAGES:
            await pg.goto(f"{BASE}/{name}.html", wait_until="load")
            await pg.wait_for_timeout(1200)
            st = await pg.evaluate("[...document.querySelectorAll('[data-figure]')].map(s => s.classList.contains('no-figure'))")
            assert st and all(st), (name, "figure stage did not fall back without WebGL", st)
        await pg.screenshot(path=str(OUT / "article-nowebgl.png"))
        await ctx.close()
        print("fallbacks: readable without JS on every page (sessions list, ledger and chain records, six gates, eight layers with the boundary after 04, "
              "menu sheet as a popover, no loader); no-WebGL homepage + figure stages fall back")
        await b.close()
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("V9 CHECKS PASSED")

asyncio.run(main())
