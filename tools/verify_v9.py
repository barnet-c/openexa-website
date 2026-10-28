"""Visual + functional pass over v9: every page at 1440/390, story beats, live objects, form, no forbidden strings.
The homepage systems are checked as one page: the overture reads the sessions record, the nav's chapter readout, the
architecture explorer, the swarm lab's events reaching the ledger trace, the chain, the proof chart; then Proof, Trust
and Platform, a phone, reduced motion, a starved requestAnimationFrame, no JavaScript and no WebGL.

Round 1 (v2) adds one named check per guard from the director's list; each asserts an invariant that must hold in every
sample (no tight wall-clock timings: those live in tools/verify_budget.py). Every check runs in its own context (a few
share one homepage at 1440, each setting its own preconditions), and a failure names the check, the page, the viewport
and the offending values; the run goes on to the next check and exits non-zero if any failed.
    python tools/verify_v9.py [http://127.0.0.1:8125] [--only name1,name2] [--list]
The site's CSP has no 'unsafe-eval': conditions are polled with page.evaluate (until()), never wait_for_function(<string>).
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, json, re, sys, time, traceback
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = "http://127.0.0.1:8125"  # the URL argument replaces it
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
# every 'oxa:settled' / 'oxa:rejected' (swarm lab) and 'oxa:recorded' (ledger trace) on the page, with the time it was heard
EVENTS = """(() => { const ev = window.__oxaEv = {settled: [], rejected: [], recorded: []};
  document.addEventListener('oxa:settled', e => ev.settled.push(Object.assign({at: performance.now()}, e.detail)));
  document.addEventListener('oxa:rejected', e => ev.rejected.push(Object.assign({at: performance.now()}, e.detail)));
  document.addEventListener('oxa:recorded', e => ev.recorded.push(Object.assign({at: performance.now()}, e.detail))); })();"""
from rules import FORBIDDEN, PEOPLE, TEAM_NAMES, GONE  # the site's content rules (tools/rules.py)
LAYOUT = """() => {
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('.beat[aria-hidden="true"]') && !el.closest('details:not([open]) > :not(summary)') && !el.closest('.table-scroll') && !el.closest('.blog-chips'); };
  const over = [...document.querySelectorAll('main h1, main h2, main h3, main p, main a, main button, main canvas, main table')].filter(vis).filter(el => { const r = el.getBoundingClientRect(); return r.left < -2 || r.right > innerWidth + 2; }).map(el => el.tagName + '.' + el.className);
  return { scrollWidth: document.documentElement.scrollWidth, overflow: over.slice(0, 6), text: document.body.innerText };
}"""

# ---------------------------------------------------------------- shared helpers for the checks
LOADED = "(() => { const l = document.querySelector('.loader'); return !l || document.documentElement.classList.contains('is-loaded'); })()"
NUMW = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
words = lambda n: NUMW[n] if 0 <= n < len(NUMW) else str(n)
capw = lambda t: t[:1].upper() + t[1:]
# the record's counts by the rule check_static, proof.js and story.js apply ('>N' with N >= floor is above it; a bare N must exceed it)
RECORD = """(() => { const el = document.getElementById('oxa-sessions'); if (!el) return null; const rec = JSON.parse(el.textContent);
  const S = rec.sessions || [], floor = +rec.floor, f = (x, k) => String(x[k] == null ? '' : x[k]).trim();
  const above = S.filter(x => { const m = f(x, 'value').match(/^(>=|≥|>)?\\s*(\\d+(?:\\.\\d+)?)$/); return !!m && (m[1] === '>' ? +m[2] >= floor : +m[2] > floor); }).length;
  return { total: S.length, above, floor, unit: rec.unit || 'bps', premium: S.filter(x => /^prem/i.test(f(x, 'regime'))).length,
    discount: S.filter(x => /^disc/i.test(f(x, 'regime'))).length }; })()"""
# statements pasted at the top of a function body: eff() = effective opacity (0 when hidden) of an element up to (not
# including) `stop`; frames(n) = a promise for n animation frames
EFF = "const eff = (el, stop) => { let o = 1; for (let e = el; e && e !== stop && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };"
FRAMES = "const frames = n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); });"
SHARED = {}


async def open_page(b, path, w, h, *, dpr=1, touch=False, reduced=False, js=True, init=None, errs=None, loaded=True):
    """a fresh context at w x h, the page loaded (for the home page: until the loader has finished)"""
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, has_touch=touch, is_mobile=touch,
                              reduced_motion="reduce" if reduced else "no-preference", java_script_enabled=js)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
    pg.set_default_timeout(45000); pg.set_default_navigation_timeout(90000)
    if errs is not None: pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
    await pg.goto(f"{BASE}/{path}", wait_until="load")
    if js and loaded: await until(pg, LOADED, 15000)
    return ctx, pg


async def shared_home(b):
    """one homepage at 1440x900 that several checks borrow; each sets its own preconditions (scroll, scene)"""
    if "home" not in SHARED: SHARED["home"] = await open_page(b, "index.html", 1440, 900)
    return SHARED["home"][1]


async def to_top_settled(pg):
    """scroll to the top and wait until the overture rests on scene 00 (beat-0 whole, the index on 00)"""
    await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    ok = await until(pg, "(() => { const b = document.querySelector('.beat-0'), i = document.querySelector('.story-idx [aria-current]'); return +getComputedStyle(b).opacity > 0.98 && (!i || i.dataset.n === '00'); })()", 8000)
    await pg.wait_for_timeout(500)
    return ok


async def scene_rest(pg, n, timeout=12000):
    """click the overture's index button for scene n and wait until it rests there (callouts no longer moving)"""
    await pg.evaluate(f"document.querySelector('.story-idx [data-n=\"0{n}\"]').click()")
    snap = """(() => { const i = document.querySelector('.story-idx [aria-current]'); const b = document.querySelector('.beat-%d');
      return JSON.stringify([i && i.dataset.n, +(+getComputedStyle(b).opacity).toFixed(2), [...document.querySelectorAll('.story-labels .story-lab.is-on')].map(l => l.style.transform + '|' + getComputedStyle(l).opacity)]); })()""" % n
    t0, last, same = time.monotonic(), None, 0
    while time.monotonic() - t0 < timeout / 1000:
        s = await pg.evaluate(snap)
        st = json.loads(s)
        if st[0] == f"0{n}" and st[1] >= 0.95 and s == last: same += 1
        else: same = 0
        if same >= 2: return True
        last = s
        await pg.wait_for_timeout(180)
    return False


async def story_end(pg):
    return await pg.evaluate("(() => { const s = document.querySelector('.story'); return s.offsetTop + s.offsetHeight; })()")


# ---------------------------------------------------------------- the checks
CHECKS = []
def check(fn): CHECKS.append(fn); return fn


@check
async def pages(b):
    """every page at 1440 and 390: 0 console errors, no horizontal overflow, no forbidden strings, the team only on Company"""
    report = {}
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
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("pages: 0 console errors, no horizontal overflow, no forbidden strings at 1440 and 390")


@check
async def home(b):
    """the homepage systems as one page at 1440: beats, record-driven overture, nav, explorer, swarm, ledger, chain, proof"""
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
    # the overture reads the sessions record (#oxa-sessions): a column, a day tag and an ink copy per session; derived copy.
    # Round 1 (OV4): the coda states the derived summary instead of repeating the tally, so the tally is checked against
    # the record wherever it is written (at least once: the beat-4 headline) instead of against two literal copies.
    st = await pg.evaluate("""(() => ({ days: document.querySelectorAll('.story-labels .story-lab.day').length,
        prem: document.querySelectorAll('.story-labels .story-lab.day.is-prem').length, ink: document.querySelectorAll('.story-ink .story-lab').length,
        tally: [...document.querySelectorAll('[data-story-n=tally]')].map(e => e.textContent) }))()""")
    rc = await pg.evaluate(RECORD)
    tally = capw(words(rc["above"])) + " for " + words(rc["total"]) + "."
    assert st["days"] == rc["total"] and st["prem"] == rc["premium"] and st["ink"] == rc["total"] and st["tally"] and all(t == tally for t in st["tally"]), (st, "record", rc, "tally", tally)
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
    await pg.evaluate("document.querySelector('#stack .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
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
    await pg.wait_for_timeout(4500)
    s1 = await pg.evaluate("({inflight: document.querySelector('[data-sw-inflight]').textContent, recorded: document.querySelector('[data-sw-recorded]').textContent})")
    assert int(s1["recorded"].replace(",", "")) > 0, s1
    # a stream of announcements (how many a second depends on the frame rate: software GL in CI is slow), never two within 250 ms
    assert await until(pg, f"window.__oxaEv.settled.length - {n0} >= 8", 15000, 200), ("oxa:settled events in view", await pg.evaluate(f"window.__oxaEv.settled.length - {n0}"))
    ev = await pg.evaluate(f"window.__oxaEv.settled.slice({n0})")
    gaps = [e2["at"] - e1["at"] for e1, e2 in zip(ev, ev[1:])]
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
    # the ledger trace (home 06) recorded what the swarm announced, answering each announcement with a hash-linked record.
    # Round 1 (SW2/LG4): the ledger also answers 'oxa:rejected', so an answered id comes from the settled or the rejected stream.
    await pg.evaluate("document.querySelector('[data-ledger=live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(1200)
    await expect(pg.locator("[data-ledger-stream] .ln").first).to_be_visible()
    rec = await until(pg, "(() => { const r = window.__oxaEv.recorded, ids = new Set(window.__oxaEv.settled.concat(window.__oxaEv.rejected).map(e => e.id)); return r.length && r.every(x => /^[0-9a-f]{64}$/.test(x.hash) && /^#[0-9a-f]{4}$/.test(x.record) && ids.has(x.id)) ? r.length : 0; })()", 12000, 200)
    assert rec, ("swarm announcements were not recorded by the ledger", await pg.evaluate("window.__oxaEv.recorded.slice(0, 3)"))
    await expect(pg.locator("[data-lt-swarm]")).to_contain_text("from the swarm above")
    await expect(pg.locator("[data-ledger=live] .lt-rec.is-swarm").first).to_be_visible()
    # Round 1 (LG4): in view the ledger seals swarm announcements into at most one record per 2 s, so five announcements
    # dispatched together are all answered with real hashes but may share one record (>= 1 distinct record, not 5)
    await pg.evaluate("for (let i = 0; i < 5; i++) document.dispatchEvent(new CustomEvent('oxa:settled', {detail: {id: 'P-9990' + i, lane: i + 1, ts: Date.now()}}))")
    five = await until(pg, "(() => { const r = window.__oxaEv.recorded.filter(x => /^P-9990\\d$/.test(x.id)); return new Set(r.map(x => x.id)).size === 5 && new Set(r.map(x => x.record)).size >= 1 && r.every(x => /^[0-9a-f]{64}$/.test(x.hash) && /^#[0-9a-f]{4}$/.test(x.record)) ? 5 : 0; })()", 9000)
    assert five, ("5 announcements -> 5 answers with hashes (>= 1 record)", await pg.evaluate("window.__oxaEv.recorded.filter(x => /^P-9990/.test(x.id))"))
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
    # (the pointer leaves the page first: a resting pointer over a lane previews that session ahead of the keyboard's)
    await pg.mouse.move(5, 450)
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
    print(f"home: 5 beats navigable, stats clear of the globe, motion pause, overture reads the record ({rc['total']} columns, {rc['premium']} premium), last beat clear of the bar, "
          f"7 chapters in the nav list (no rail), explorer keys/hover, swarm {len(ev)} events in view (gaps >= {min(gaps):.0f} ms), follow by keyboard, halt drains, "
          f"{rec} swarm announcements recorded with hashes, stream keyboard, chain breaks (typed and one-tap) + restores, proof listbox")
    await ctx.close()


@check
async def interior(b):
    """Proof: table rows light their sessions; Trust: the replay verifies; Platform: the explorer is ready"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
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
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-wide.is-ready')", 10000), "platform explorer not ready"
    assert await pg.locator("#architecture .arch-layer").count() == 8
    assert not errs, errs
    print("proof: table rows light their sessions; trust: 9-record trace verifies 8 of 8 links; platform: explorer ready with 8 layers")
    await ctx.close()


@check
async def desk(b):
    """the desk on Lifecycles runs after a deep link (its clock has left 09:30)"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/lifecycles.html#lc01", wait_until="load")
    await pg.locator("[data-gap]").scroll_into_view_if_needed()
    await pg.wait_for_timeout(5000)
    info = await pg.evaluate("({time: document.querySelector('[data-gap-time]').textContent, log: document.querySelectorAll('.desk-log li').length, state: document.querySelector('[data-gap-state]').textContent})")
    assert info["time"] != "09:30 ET", info
    await pg.locator("[data-gap]").screenshot(path=str(OUT / "desk.png"))
    assert not errs, errs
    print("desk:", info)
    await ctx.close()


@check
async def access(b):
    """the access form: a linked path preselected, a mailto draft prepared, edit restores the input"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
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
    await ctx.close()


@check
async def company(b):
    """company team: thirteen portraits load, monochrome at rest, colour on hover; the exact roster; no patent count"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/company.html#team", wait_until="load")
    await pg.locator(".crew--team").scroll_into_view_if_needed()
    # the advisors' portraits are loading="lazy": walk the page so every one is fetched before counting them
    for y in range(0, await pg.evaluate("document.body.scrollHeight"), 400):
        await pg.evaluate(f"scrollTo(0, {y})"); await pg.wait_for_timeout(120)
    await pg.locator(".crew--team").scroll_into_view_if_needed()
    assert await until(pg, "[...document.querySelectorAll('.crew img')].every(i => i.complete && i.naturalWidth === 560)", 15000), "team portraits did not load"
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
    assert not errs, errs
    await ctx.close()


@check
async def blog(b):
    """blog: collections filter, hash deep link, the featured series, 29 cards"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
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


@check
async def resolution(b):
    """canvases render at device resolution (2x here), within the UHD budget"""
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


@check
async def phone(b):
    """phone: the explorer is an accordion, a chapter lands under the 64 px bar, the menu sheet is a popover over an inert page"""
    ctx = await b.new_context(viewport={"width": 390, "height": 844})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/index.html", wait_until="load")
    await pg.locator(".loader").wait_for(state="detached", timeout=15000)
    await pg.evaluate("document.querySelector('#stack .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
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


@check
async def reduced_motion(b):
    """reduced motion: the explorer is open and still; the ledger stream starts paused; Trust verifies at once"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/index.html", wait_until="load")
    await pg.locator(".loader").wait_for(state="detached", timeout=15000)
    await pg.evaluate("document.querySelector('#stack .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#stack .arch.is-ready')", 1500), "explorer not open at once under reduced motion"
    await expect(pg.locator("#stack .arch-motion")).to_be_hidden()
    await expect(pg.locator("[data-ledger=live] [data-lt-state]")).to_have_text("Paused · illustrative stream")
    await pg.goto(f"{BASE}/trust.html", wait_until="load")
    await pg.locator("[data-lt-verify]").click()
    await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Verified here · 8 of 8 links hold", timeout=1500)
    assert not errs, errs
    await ctx.close()
    print("reduced motion: explorer open and still (no motion control), stream paused, Trust verifies at once")


@check
async def loader(b):
    """the loader finishes on elapsed time, not on frames: with requestAnimationFrame starved it still lifts"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script("window.requestAnimationFrame = () => 0;")
    pg = await ctx.new_page()
    await pg.goto(f"{BASE}/index.html", wait_until="commit")
    gone = await until(pg, "(() => { const l = document.querySelector('.loader'); return document.readyState !== 'loading' && (!l || !l.isConnected) ? performance.now() : 0; })()", 9000, 50)
    assert gone and gone <= 4500, ("loader still up with requestAnimationFrame starved", gone)
    await ctx.close()
    print(f"loader: removed {gone / 1000:.1f}s after navigation with requestAnimationFrame starved")


@check
async def no_js(b):
    """no JavaScript: every page readable at 390 (h1 shown, no overflow); the homepage's static objects; the menu popover"""
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
    print("fallbacks: readable without JS on every page (sessions list, ledger and chain records, six gates, eight layers with the boundary after 04, menu sheet as a popover, no loader)")


@check
async def no_webgl(b):
    """no WebGL: the homepage falls back (html.no-webgl) and every figure stage falls back"""
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
    print("fallbacks: no-WebGL homepage + figure stages fall back")


# ================================================================ round 1 (v2) guards, one per item of the director's list
# ---- counters: never a value other than the final one (NV1, PF1, SW3, PG10; D13)
COUNT_ROWS = [  # page, viewport, the row's value cells, the record-derived cells (home/Proof) or the director's literals
    ("index.html", (1440, 900), "#proof .stats .v", "record"),
    ("evidence.html", (390, 844), ".page-hero .stats .v", "record"),
    ("platform.html", (1440, 900), "#swarm .stats .v", ["50k"]),
    ("company.html", (1440, 900), ".crew-stats b", ["5", "8", "100+"]),
]
STATIC_TEXTS = """async (sel) => { const norm = s => s.replace(/\\s+/g, ' ').trim();
  const html = await (await fetch(location.pathname, {cache: 'no-store'})).text();
  const doc = new DOMParser().parseFromString(html, 'text/html');
  return { now: [...document.querySelectorAll(sel)].map(e => norm(e.textContent)), markup: [...doc.querySelectorAll(sel)].map(e => norm(e.textContent)) }; }"""
SAMPLE_TEXTS = """async (sel) => { const norm = s => s.replace(/\\s+/g, ' ').trim(), out = [];
  for (let k = 0; k <= 16; k++) { out.push([...document.querySelectorAll(sel)].map(e => norm(e.textContent))); await new Promise(r => setTimeout(r, 100)); }
  return out; }"""


@check
async def counters(b):
    """every stats figure shows its final value at load (before any scroll), and at every 100 ms sample over 1.6 s after
    its row scrolls into view: the markup's value, which for the proof rows is derived from #oxa-sessions"""
    bad = []
    for path, (w, h), sel, want in COUNT_ROWS:
        ctx, pg = await open_page(b, path, w, h)
        await pg.wait_for_timeout(300)
        t = await pg.evaluate(STATIC_TEXTS, sel)
        ref = t["markup"]
        if want == "record":
            rc = await pg.evaluate(RECORD)
            derived = [f">{rc['floor']:g}{rc['unit']}", f"{rc['above']}/{rc['total']}"]
            if ref[:2] != derived: bad.append(f"{path}@{w}x{h}: the markup's stats {ref[:2]} are not the record's {derived}")
        elif ref[:len(want)] != want: bad.append(f"{path}@{w}x{h}: the markup's stats {ref} do not start {want}")
        if not ref: bad.append(f"{path}@{w}x{h}: no stats cells for {sel}"); await ctx.close(); continue
        if t["now"] != ref: bad.append(f"{path}@{w}x{h}: at load (row not yet in view) {sel} reads {t['now']}; final {ref}")
        await pg.evaluate("(sel) => document.querySelector(sel).scrollIntoView({block: 'center', behavior: 'instant'})", sel)
        rows = await pg.evaluate(SAMPLE_TEXTS, sel)
        off = [(k * 100, r) for k, r in enumerate(rows) if r != ref]
        if off: bad.append(f"{path}@{w}x{h}: {len(off)} of {len(rows)} samples after scrolling the row in differ from {ref}, e.g. {off[:3]}")
        await ctx.close()
    assert not bad, "counters:\n  " + "\n  ".join(bad)
    print(f"counters: {len(COUNT_ROWS)} stats rows read their final values at load and in 17 samples after their reveal")


# ---- the bar at the paper hand-off (NV3, cross: paper hand-off)
HANDOFF = "async (n) => { " + FRAMES + """ await frames(n);
  const nav = document.querySelector('header.nav') || document.querySelector('.nav'), sp = document.querySelector('.story-paper');
  const nb = nav.getBoundingClientRect().bottom, r = sp ? sp.getBoundingClientRect() : null;
  const vis = !!sp && getComputedStyle(sp).visibility !== 'hidden' && r.height > 0.5;
  return { y: Math.round(scrollY), dark: nav.classList.contains('nav--dark'), vis, top: r ? +r.top.toFixed(1) : null, nb: +nb.toFixed(1) }; }"""


@check
async def nav_handoff(b):
    """at 1440, 768 and 390, from story end - innerHeight - 120 to story end + 60 in 20 px steps: the bar is never ink
    (.nav--dark) while the rising .story-paper is visible with its top at or above the bar's bottom (a one-frame lag that
    clears within six frames is not counted)"""
    bad, n = [], 0
    for w, h in ((1440, 900), (768, 1024), (390, 844)):
        ctx, pg = await open_page(b, "index.html", w, h)
        end = await story_end(pg)
        seen = 0
        for y in range(end - h - 120, end + 61, 20):
            await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
            s = await pg.evaluate(HANDOFF, 2); n += 1
            viol = lambda s: s["dark"] and s["vis"] and s["top"] <= s["nb"]
            if s["vis"] and s["top"] <= s["nb"]: seen += 1
            if viol(s):
                s2 = await pg.evaluate(HANDOFF, 6)
                if viol(s2): bad.append(f"index.html@{w}x{h} y={y}: nav--dark with the paper's top at {s2['top']} <= bar bottom {s2['nb']}")
        if not seen: bad.append(f"index.html@{w}x{h}: the paper never reached the bar in the hand-off window (nothing was tested)")
        await ctx.close()
    assert not bad, f"nav_handoff: {len(bad)} ink samples over the paper:\n  " + "\n  ".join(bad[:12])
    print(f"nav_handoff: {n} samples at 1440, 768, 390; the bar is never ink over the rising paper")


# ---- the ledger panel never moves the page (LG2)
@check
async def ledger_height(b):
    """with [data-ledger=live] centred and its stream running, document.body.scrollHeight stays within 1 px for 6 s,
    at 1440 and at 390"""
    bad = []
    for w, h in ((1440, 900), (390, 844)):
        ctx, pg = await open_page(b, "index.html", w, h)
        await pg.evaluate("document.querySelector('[data-ledger=live]').scrollIntoView({block: 'center', behavior: 'instant'})")
        running = await until(pg, "(() => { const t = document.querySelector('[data-ledger=live] [data-lt-state]').textContent; return /running|live/i.test(t) && !/paus/i.test(t) ? t : ''; })()", 8000)
        if not running: bad.append(f"index.html@{w}x{h}: the stream is not running: {await pg.evaluate('document.querySelector(\"[data-ledger=live] [data-lt-state]\").textContent')!r}")
        await pg.wait_for_timeout(1500)
        hs = await pg.evaluate("async () => { const out = []; for (let k = 0; k < 60; k++) { out.push(document.body.scrollHeight); await new Promise(r => setTimeout(r, 100)); } return out; }")
        moved = [(k * 100, v) for k, v in enumerate(hs) if abs(v - hs[0]) > 1]
        if moved: bad.append(f"index.html@{w}x{h}: body.scrollHeight {hs[0]} moved {len(moved)} times in 6 s (range {min(hs)}-{max(hs)}), e.g. {moved[:4]}")
        await ctx.close()
    assert not bad, "ledger_height:\n  " + "\n  ".join(bad)
    print("ledger_height: body.scrollHeight constant (±1 px) over 6 s with the stream running, at 1440 and 390")


# ---- the overture: re-entry, the copy relay, the numeral (OV8, OV4)
REENTRY_REC = """(() => { const r = window.__rec = []; const st = document.querySelector('.story'), beats = [...st.querySelectorAll('.beat')];
  const f = () => { const sr = st.getBoundingClientRect(); r.push({ y: Math.round(scrollY), on: sr.bottom > 0 && sr.top < innerHeight, b: beats.map(b => +(+getComputedStyle(b).opacity).toFixed(2)) });
    if (window.__recOn) requestAnimationFrame(f); }; window.__recOn = true; requestAnimationFrame(f); })()"""


@check
async def overture_reentry(b):
    """from a settled S0, jump to story end + 500, wait 800 ms, then wheel back up (300 px, then 8 x 120 px into the
    story; the stage's destination is the S4 exit throughout): no frame with the stage on screen shows .beat-0, or any
    beat but beat-4 (opacity >= 0.05): no stale scene, no replay. (Which stale scene the old code shows depends on the
    frame rate, S0 on a GPU and S1-S3 under SwiftShader, so every beat but the destination's is watched.)"""
    pg = await shared_home(b)
    await to_top_settled(pg)
    end = await story_end(pg)
    await pg.evaluate(f"window.scrollTo({{top: {end + 500}, behavior: 'instant'}})"); await pg.wait_for_timeout(800)
    await pg.mouse.move(700, 450); await pg.evaluate(REENTRY_REC)
    await pg.mouse.wheel(0, -300); await pg.wait_for_timeout(300)
    for _ in range(8): await pg.mouse.wheel(0, -120); await pg.wait_for_timeout(90)
    await pg.wait_for_timeout(700)
    await pg.evaluate("window.__recOn = false"); rec = await pg.evaluate("window.__rec")
    on = [r for r in rec if r["on"]]
    assert len(on) >= 3, f"overture_reentry index.html@1440x900: only {len(on)} frames with the stage on screen after wheeling back up ({len(rec)} frames)"
    stale = [r for r in on if any(o >= 0.05 for o in r["b"][:4])]
    assert not stale, f"overture_reentry index.html@1440x900: {len(stale)} of {len(on)} on-screen frames show a beat other than the destination's (stale scene / replay; beat opacities 0-4), first {stale[:3]}"
    print(f"overture_reentry: {len(on)} on-screen frames after re-entry, only the destination scene shown")


RELAY_REC = "(() => { " + EFF + """ const story = document.querySelector('.story'), beats = [...story.querySelectorAll('.beat')];
  const ty = w => { const t = getComputedStyle(w).transform; if (!t || t === 'none') return 0; return new DOMMatrixReadOnly(t).m42; };
  const rise = h => { const ws = [...h.querySelectorAll('.wi')]; if (!ws.length) return 1; let s = 0;
    for (const w of ws) { const hh = w.offsetHeight || 1; s += Math.max(0, Math.min(1, 1 - ty(w) / (hh * 1.12))); } return s / ws.length; };
  const R = window.__relay = { n: 0, bad: [], on: true };
  const f = () => { R.n++;
    beats.forEach((b, i) => { const body = b.querySelector('.body-lg'), h = b.querySelector('h1, h2'); if (!body || !h) return;
      const bo = eff(body, story); if (bo <= 0.3) return; const r = rise(h);
      if (r < 0.5 && R.bad.length < 30) R.bad.push({ beat: i, y: Math.round(scrollY), body: +bo.toFixed(2), rise: +r.toFixed(2) }); });
    if (R.on) requestAnimationFrame(f); };
  requestAnimationFrame(f); })()"""


@check
async def overture_relay(b):
    """a slow wheel pass through the overture at 1440 (120 px every 80 ms): no frame shows a beat's .body-lg above 0.3
    opacity while its headline's words have risen less than half way (mean rise < 0.5): the headline leads its scene"""
    pg = await shared_home(b)
    await to_top_settled(pg)
    pin = await pg.evaluate("document.querySelector('.story').offsetHeight - innerHeight")
    await pg.mouse.move(720, 450)
    await pg.evaluate(RELAY_REC)
    for _ in range(int(pin / 120) + 3):
        await pg.mouse.wheel(0, 120); await pg.wait_for_timeout(80)
    await pg.wait_for_timeout(1200)
    await pg.evaluate("window.__relay.on = false"); r = await pg.evaluate("window.__relay")
    assert r["n"] >= 5, f"overture_relay index.html@1440x900: only {r['n']} frames sampled"
    assert not r["bad"], f"overture_relay index.html@1440x900: {len(r['bad'])}+ frames with a paragraph before its headline, e.g. {r['bad'][:4]}"
    print(f"overture_relay: {r['n']} frames over a slow wheel pass, every visible paragraph under a risen headline")


@check
async def overture_numeral(b):
    """at s ~ 0.02 (scrollY 260 at 1440, from a settled S0) the ghost numeral .story-num stays under 0.05 opacity in
    every frame: it never pops in above the S0 eyebrow"""
    pg = await shared_home(b)
    await to_top_settled(pg)
    await pg.evaluate("""(() => { const n = document.querySelector('.story-num'), story = document.querySelector('.story'); const R = window.__num = { max: 0, n: 0, on: true };
      const eff = el => { let o = 1; for (let e = el; e && e !== story; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
      const f = () => { R.n++; R.max = Math.max(R.max, n ? eff(n) : 0); if (R.on) requestAnimationFrame(f); }; requestAnimationFrame(f); })()""")
    await pg.evaluate("window.scrollTo({top: 260, behavior: 'instant'})")
    await pg.wait_for_timeout(1800)
    await pg.evaluate("window.__num.on = false"); r = await pg.evaluate("window.__num")
    assert r["max"] < 0.05, f"overture_numeral index.html@1440x900 y=260: .story-num reached opacity {r['max']:.2f} ({r['n']} frames)"
    print(f"overture_numeral: .story-num stays at {r['max']:.2f} at s~0.02 ({r['n']} frames)")


# ---- the overture on phones: nothing prints over anything; the illustrative caption reads (OV1, OV10, D14)
PHONE_LAB = "(() => { " + EFF + """
  const box = el => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom }; };
  const ov = (a, b) => Math.min(a.r, b.r) - Math.max(a.l, b.l) > 1 && Math.min(a.b, b.b) - Math.max(a.t, b.t) > 1;
  const shown = el => eff(el, document.documentElement) > 0.3 && el.getBoundingClientRect().width > 0;
  const labs = [...document.querySelectorAll('.story-labels .story-lab')].filter(shown).map(l => ({ t: l.textContent.replace(/\\s+/g, ' ').trim().slice(0, 44), bx: box(l) }));
  const obst = [];
  const idx = document.querySelector('.story-idx'); if (idx && shown(idx)) obst.push(['the scene index', box(idx)]);
  const mo = document.querySelector('.story-motion'); if (mo && shown(mo)) obst.push(['Pause motion', box(mo)]);
  obst.push(['the nav', box(document.querySelector('header.nav') || document.querySelector('.nav'))]);
  // a beat's text: each visible part of its copy (eyebrow, headline, paragraph, buttons, figures), not the column's box,
  // so a callout over the room a hidden paragraph leaves is not counted; a part shows at effective opacity > 0.3
  document.querySelectorAll('.story .beat').forEach((b, i) => { if (eff(b, document.documentElement) <= 0.3) return;
    b.querySelectorAll('.beat-text > *, .hero-stats').forEach(p => { if (p.getBoundingClientRect().height > 0 && eff(p, document.documentElement) > 0.3) obst.push(['beat ' + i + ' ' + (p.className || p.tagName.toLowerCase()).toString().split(' ')[0], box(p)]); }); });
  const issues = [];
  labs.forEach((l, i) => { obst.forEach(([n, bx]) => { if (ov(l.bx, bx)) issues.push(`'${l.t}' x ${n}`); });
    for (let j = i + 1; j < labs.length; j++) if (ov(l.bx, labs[j].bx)) issues.push(`'${l.t}' x '${labs[j].t}'`); });
  const c3 = labs.find(l => /^(Plate|Fig\\.)\\s*0?3\\b/.test(l.t));
  return { issues, labs: labs.length, cap3: c3 ? { t: c3.t, inside: c3.bx.l >= 0 && c3.bx.t >= 0 && c3.bx.r <= innerWidth && c3.bx.b <= innerHeight, bx: [c3.bx.l, c3.bx.t, c3.bx.r, c3.bx.b].map(Math.round) } : null };
})()"""
PHONES = [(390, 664), (375, 667), (360, 780), (320, 640), (844, 390)]


@check
async def overture_phones(b):
    """at 390x664, 375x667, 360x780, 320x640 and 844x390 with touch, at each scene's rest: no visible callout box crosses
    the scene index, 'Pause motion', the nav, a visible beat's text or another callout; Plate 03's caption lies inside the
    viewport and says 'Illustrative'"""
    bad = []
    for w, h in PHONES:
        ctx, pg = await open_page(b, "index.html", w, h, touch=True)
        for i in range(5):
            if not await scene_rest(pg, i): bad.append(f"index.html@{w}x{h} scene 0{i}: did not come to rest")
            m = await pg.evaluate(PHONE_LAB)
            bad += [f"index.html@{w}x{h} scene 0{i}: {x}" for x in m["issues"]]
            if i == 3:
                c = m["cap3"]
                if not c: bad.append(f"index.html@{w}x{h} scene 03: no visible Plate 03 caption")
                elif not c["inside"] or "Illustrative" not in c["t"]: bad.append(f"index.html@{w}x{h} scene 03: caption {c['t']!r} at {c['bx']} (inside: {c['inside']}; must lie in the viewport and say 'Illustrative')")
        await ctx.close()
    assert not bad, f"overture_phones: {len(bad)} problems:\n  " + "\n  ".join(bad[:30])
    print(f"overture_phones: {len(PHONES)} phone viewports x 5 scenes, no callout over the index, the nav, the copy or another callout")


# ---- S1 on a phone: a tap opens its own lifecycle; a swipe never inspects (OV2)
RING_POINT = """(() => { const lab = document.querySelector('.story-labels .story-lab.ring.is-on'); const p = document.querySelector('.story-leaders path.ring.is-on');
  if (!lab || !p) return null; const m = p.getScreenCTM(), L = p.getTotalLength();
  const a = p.getPointAtLength(0).matrixTransform(m), z = p.getPointAtLength(L).matrixTransform(m), r = lab.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2, d = q => Math.hypot(q.x - cx, q.y - cy);
  const q = d(a) > d(z) ? a : z; return { x: q.x, y: q.y }; })()"""
INSP = "(() => { const i = document.querySelector('.story-insp'); return i && i.classList.contains('is-on') ? i.textContent.replace(/\\s+/g, ' ').trim() : ''; })()"


async def touch_drag(cdp, x0, y0, x1, y1, steps=10, dt=16):
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    for i in range(1, steps + 1):
        await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]})
        await asyncio.sleep(dt / 1000)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


@check
async def overture_tap(b):
    """S1 at 390x844@3 with touch: a 150 px vertical drag that starts on a ring leaves no inspector open; tapping each
    visible ring callout opens an inspector whose text starts with that callout's LC code (6 of 6)"""
    ctx, pg = await open_page(b, "index.html", 390, 844, dpr=3, touch=True)
    cdp = await ctx.new_cdp_session(pg)
    bad = []
    if not await scene_rest(pg, 1): bad.append("S1 did not come to rest")
    pt = await pg.evaluate(RING_POINT)
    if not pt: bad.append("no visible ring callout with a leader in S1")
    else:
        await touch_drag(cdp, pt["x"], pt["y"], pt["x"], pt["y"] - 150)
        await pg.wait_for_timeout(150); i1 = await pg.evaluate(INSP)
        await pg.wait_for_timeout(900); i2 = await pg.evaluate(INSP)
        if i1 or i2: bad.append(f"a drag from the ring at ({pt['x']:.0f}, {pt['y']:.0f}) left the inspector open: {(i1 or i2)[:50]!r}")
    if not await scene_rest(pg, 1): bad.append("S1 did not come to rest again")
    n = await pg.locator(".story-lab.ring.is-on").count()
    ok = 0
    for k in range(n):
        lab = pg.locator(".story-lab.ring.is-on").nth(k)
        code = re.search(r"LC-\d\d", (await lab.text_content()) or "")
        bb = await lab.bounding_box()
        await pg.touchscreen.tap(bb["x"] + bb["width"] * 0.25, bb["y"] + bb["height"] / 2)
        got = await until(pg, INSP, 1500)
        if code and got.startswith(code[0]): ok += 1
        else: bad.append(f"tapped {code[0] if code else '?'} at ({bb['x'] + bb['width'] * 0.25:.0f}, {bb['y'] + bb['height'] / 2:.0f}); the inspector reads {got[:40]!r}")
    if n != 6: bad.append(f"{n} visible ring callouts in S1 (6 expected)")
    await ctx.close()
    assert not bad, f"overture_tap index.html@390x844@3 ({ok}/{n} taps right):\n  " + "\n  ".join(bad)
    print(f"overture_tap: {ok}/{n} ring taps open their own lifecycle; a drag from a ring inspects nothing")


# ---- resizing and rotation keep the reader's scene (OV8)
CUR = "(() => { const i = document.querySelector('.story-idx [aria-current]'); return i ? i.dataset.n : ''; })()"


async def settled_scene(pg, timeout=5000):
    """the index's current scene once it has stopped changing (three equal reads 200 ms apart)"""
    t0, last, same = time.monotonic(), None, 0
    while time.monotonic() - t0 < timeout / 1000:
        c = await pg.evaluate(CUR)
        same = same + 1 if c == last else 0
        if same >= 2: return c
        last = c; await pg.wait_for_timeout(200)
    return last


@check
async def overture_resize(b):
    """S2 at 390x844 -> 844x390 -> 390x844 (touch) keeps aria-current on 02; S4 at 1440x900 -> 768x1024 keeps 04 with
    .beat-4 whole (opacity >= 0.9)"""
    bad = []
    ctx, pg = await open_page(b, "index.html", 390, 844, touch=True)
    await scene_rest(pg, 2)
    seq = [await settled_scene(pg)]
    for w, h in ((844, 390), (390, 844)):
        await pg.set_viewport_size({"width": w, "height": h}); await pg.wait_for_timeout(600)
        seq.append(await settled_scene(pg))
    if seq != ["02", "02", "02"]: bad.append(f"S2 at 390x844 -> 844x390 -> 390x844 reads scenes {seq}")
    await ctx.close()
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await scene_rest(pg, 4)
    s0 = await settled_scene(pg)
    await pg.set_viewport_size({"width": 768, "height": 1024}); await pg.wait_for_timeout(600)
    s1 = await settled_scene(pg)
    o4 = await pg.evaluate("+getComputedStyle(document.querySelector('.beat-4')).opacity")
    if [s0, s1] != ["04", "04"] or o4 < 0.9: bad.append(f"S4 at 1440x900 -> 768x1024 reads scenes {[s0, s1]}, .beat-4 opacity {o4:.2f}")
    await ctx.close()
    assert not bad, "overture_resize index.html:\n  " + "\n  ".join(bad)
    print("overture_resize: S2 survives a rotation and back; S4 survives 1440 -> 768")


# ---- the swarm lab and the ledger (SW1, SW2, LG4, LG3)
@check
async def swarm_rate(b):
    """after Halt, once in flight reads 0, 'Settled / s' ([data-sw-rate]) reads 0 within 0.5 s and stays 0 (it is the
    model's own rate, not a trailing window)"""
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    num = "(s => +((document.querySelector(s) || {}).textContent || 'NaN').replace(/[^\\d.]/g, ''))"
    assert await until(pg, f"{num}('[data-sw-inflight]') > 0 && {num}('[data-sw-recorded]') > 0", 25000, 200), "swarm_rate index.html@1440x900: the lab never ran"
    await pg.evaluate("""(() => { const q = s => (document.querySelector(s) || {}).textContent || ''; const R = window.__rate = { f: [], on: true }; const t0 = performance.now();
      const f = () => { R.f.push([Math.round(performance.now() - t0), q('[data-sw-inflight]').trim(), q('[data-sw-rate]').trim()]); if (R.on) requestAnimationFrame(f); }; requestAnimationFrame(f); })()""")
    await pg.locator("[data-sw-halt]").click()
    drained = await until(pg, "document.querySelector('[data-sw-inflight]').textContent.trim() === '0'", 45000, 200)
    await pg.wait_for_timeout(1200)
    await pg.evaluate("window.__rate.on = false"); fr = (await pg.evaluate("window.__rate"))["f"]
    await ctx.close()
    assert drained, f"swarm_rate index.html@1440x900: Halt never drained (in flight {fr[-1][1] if fr else '?'})"
    zero = lambda t: re.sub(r"[^\d.]", "", t or "x") in ("0", "0.0", "0.00")
    i0 = next((i for i, x in enumerate(fr) if x[1] == "0"), None)
    assert i0 is not None, f"swarm_rate index.html@1440x900: no frame recorded in flight 0 ({len(fr)} frames)"
    i1 = next((i for i in range(i0, len(fr)) if zero(fr[i][2])), None)
    late = None if i1 is None else fr[i1][0] - fr[i0][0]
    after = [x for x in fr[i1 or len(fr):] if not zero(x[2])]
    assert i1 is not None and late <= 500 and not after, f"swarm_rate index.html@1440x900: in flight reached 0 at {fr[i0][0]} ms; the rate read {[x[2] for x in fr[i0:i0 + 8]]}... (zero after {late} ms; non-zero afterwards: {after[:3]})"
    print(f"swarm_rate: Settled / s read 0 {late} ms after in flight reached 0, and stayed 0")


BLOCK_WATCH = """(() => { const hit = window.__blk = []; const sel = ['#sw-trace', '[data-sw-callout]', '[data-sw-agent]', '[data-sw-say]'];
  const look = () => sel.forEach(s => document.querySelectorAll(s).forEach(el => { const t = (el.textContent || '').replace(/\\s+/g, ' '), m = /\\bblock\\b/i.exec(t);
    if (m && hit.length < 10) hit.push(s + ': ...' + t.slice(Math.max(0, m.index - 40), m.index + 30)); }));
  new MutationObserver(look).observe(document.querySelector('[data-swarm-live]'), { subtree: true, childList: true, characterData: true }); look(); })()"""


@check
async def swarm_trace_to_ledger(b):
    """follow one proposal to Settled (council strictness 0): the trace's ledger row becomes a button naming the same
    '#id' as the ledger's .lt-rec.is-followed; clicking it brings [data-ledger=live] into view with that record .is-sel;
    on the homepage the trace, its stage tag and its live region never print 'block'"""
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=EVENTS)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "+document.querySelector('[data-sw-inflight]').textContent.replace(/\\D/g, '') > 0", 25000, 200), "swarm_trace_to_ledger index.html@1440x900: the lab never ran"
    await pg.evaluate("(() => { const s = document.querySelector('[data-sw-strict]'); s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    await pg.evaluate(BLOCK_WATCH)
    await pg.mouse.move(5, 450)
    await pg.locator("[data-sw-follow]").click()
    t0 = time.monotonic()
    got = await until(pg, """(() => { const b = document.querySelector('[data-sw-log] [data-sw-rec]'); if (b) return 'button';
        const t = (document.querySelector('[data-sw-log]') || {}).textContent || ''; return /record #[0-9a-f]{4}/.test(t) ? 'text:' + t.replace(/\\s+/g, ' ').slice(-80) : ''; })()""", 60000, 250)
    bad = []
    if got != "button":
        bad.append(f"the trace's ledger row is no button after {time.monotonic() - t0:.0f} s: {got or (await pg.evaluate('(document.querySelector(\"[data-sw-log]\") || {}).textContent || \"\"'))[-120:]!r}")
    else:
        ids = await pg.evaluate("({ btn: document.querySelector('[data-sw-log] [data-sw-rec]').dataset.swRec || document.querySelector('[data-sw-log] [data-sw-rec]').textContent, followed: [...document.querySelectorAll('[data-ledger=live] .lt-rec.is-followed')].map(li => (li.querySelector('.lt-id') || li).textContent.trim()) })")
        rid = re.search(r"#[0-9a-f]{4}", ids["btn"] or "")
        if not rid or ids["followed"] != [rid[0]]: bad.append(f"the trace's button names {ids['btn']!r}; the ledger's .lt-rec.is-followed: {ids['followed']}")
        else:
            await pg.locator("[data-sw-log] [data-sw-rec]").click()
            t1 = time.monotonic()
            sel = await until(pg, """(() => { const l = document.querySelector('[data-ledger=live]'), r = l.getBoundingClientRect(), li = l.querySelector('.lt-rec.is-followed');
                return r.top < innerHeight && r.bottom > 0 && li && li.classList.contains('is-sel') ? 1 : 0; })()""", 8000, 100)
            if not sel: bad.append(f"after the click the ledger is not in view with {rid[0]} selected: {await pg.evaluate('(() => { const r = document.querySelector(\"[data-ledger=live]\").getBoundingClientRect(); return [Math.round(r.top), Math.round(r.bottom), [...document.querySelectorAll(\"[data-ledger=live] .lt-rec.is-sel\")].map(li => li.textContent.slice(0, 20))]; })()')}")
            else: print(f"swarm_trace_to_ledger: record {rid[0]} selected in the ledger {time.monotonic() - t1:.1f} s after the click")
    blk = await pg.evaluate("window.__blk")
    if blk: bad.append(f"the trace printed 'block': {blk[:3]}")
    await ctx.close()
    assert not bad, "swarm_trace_to_ledger index.html@1440x900:\n  " + "\n  ".join(bad)


@check
async def ledger_wheel(b):
    """with the pointer over the ledger strip, 6 vertical wheel steps of 120 px (3 down, 3 up; up to 3 trials) never
    turn [data-lt-state] to 'browsing'"""
    pg = await shared_home(b)
    await pg.evaluate("document.querySelector('[data-ledger=live] .lt-view').scrollIntoView({block: 'center', behavior: 'instant'})")
    await until(pg, "/running|live/i.test(document.querySelector('[data-ledger=live] [data-lt-state]').textContent)", 6000)
    await pg.evaluate("""(() => { const s = document.querySelector('[data-ledger=live] [data-lt-state]'); const R = window.__lts = [s.textContent];
      new MutationObserver(() => R.push(s.textContent)).observe(s, { subtree: true, childList: true, characterData: true }); })()""")
    for trial in range(3):
        await pg.evaluate("document.querySelector('[data-ledger=live] .lt-view').scrollIntoView({block: 'center', behavior: 'instant'})")
        await pg.wait_for_timeout(700)
        x, y = await pg.evaluate(f"(() => {{ const r = document.querySelector('[data-ledger=live] .lt-view').getBoundingClientRect(); return [r.left + r.width * {0.3 + 0.2 * trial}, r.top + r.height / 2]; }})()")
        await pg.mouse.move(x, y)
        for k in range(6):
            await pg.mouse.wheel(0, 120 if k < 3 else -120); await pg.wait_for_timeout(180)
        await pg.wait_for_timeout(600)
        states = await pg.evaluate("window.__lts")
        if any("browsing" in s.lower() for s in states): break
    await pg.mouse.move(5, 450)
    states = await pg.evaluate("window.__lts")
    browsing = [s for s in states if "browsing" in s.lower()]
    assert not browsing, f"ledger_wheel index.html@1440x900 (trial {trial + 1}): a vertical wheel over the strip stopped following: {sorted(set(states))}"
    print(f"ledger_wheel: {trial + 1} trials of 6 vertical wheel steps over the strip, states {sorted(set(states))}")


# ---- the proof chart's entrance from above: all sessions rise together (PF2)
# samples every 50 ms and on every animation frame, from before the arrival until 1.5 s after the chart turns .is-in
PROOF_SAMPLER = """(dur) => { const host = document.querySelector('#proof [data-proof-chart]'); const lanes = [...host.querySelectorAll('.pf-lane')];
  const S = window.__pe = { s: [], done: false }; const t0 = performance.now(); let inAt = null;
  const sample = () => { const now = performance.now(), isIn = host.classList.contains('is-in'); if (isIn && inAt === null) inAt = now;
    S.s.push({ t: Math.round(now - t0), in: isIn, c: lanes.map(l => [...l.querySelectorAll('.pf-c i:not(.is-void), .pf-g i')].filter(i => +getComputedStyle(i).opacity >= 0.5).length) });
    if (inAt === null ? now - t0 > 6000 : now - inAt > dur) S.done = true; };
  const tick = () => { if (S.done) return; sample(); setTimeout(tick, 50); };
  const raf = () => { if (S.done) return; sample(); requestAnimationFrame(raf); };
  tick(); requestAnimationFrame(raf); return lanes.length; }"""


@check
async def proof_entrance(b):
    """arriving at home §04's chart from above at 1440 (about 38% of it in view), sampled every 50 ms for 1.5 s: the ten
    lanes' lit block counts never differ by more than one (no staircase, no session below another); the entrance played"""
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    g = await pg.evaluate("(() => { const r = document.querySelector('#proof [data-proof-chart]').getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; })()")
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 - 60}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
    pre = await pg.evaluate("document.querySelector('#proof [data-proof-chart]').classList.contains('is-in')")
    n = await pg.evaluate(PROOF_SAMPLER, 1500)
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 + g['h'] * 0.38:.0f}, behavior: 'instant'}})")
    await until(pg, "window.__pe.done", 9000)
    s = (await pg.evaluate("window.__pe"))["s"]
    await ctx.close()
    total = max((sum(x["c"]) for x in s), default=0)
    spread = [(x["t"], max(x["c"]) - min(x["c"]), x["c"]) for x in s if x["c"]]
    worst = max(spread, key=lambda v: v[1]) if spread else None
    played = any(0 < sum(x["c"]) < total for x in s)
    assert n == 10 and not pre and played and worst and worst[1] <= 1, (f"proof_entrance index.html@1440x900: {n} lanes; revealed before arrival: {pre}; entrance observed: {played}; "
                                                                         f"worst lane spread {worst[1] if worst else '?'} at {worst[0] if worst else '?'} ms: {worst[2] if worst else ''}")
    print(f"proof_entrance: {len(s)} samples, lanes never differ by more than {worst[1]} block")


# ---- the lifecycle lane (LC1, LC2, D2) and the desk (LC2b)
GATES = ["Signal", "Predict", "Decide", "Approve", "Execute", "Settle"]  # the canonical gate vocabulary (_cross)
STEPS = [  # Lifecycles §03, kept verbatim (D2): the six gates plus 07 Reconcile, with their texts
    ("Signal", "Data agents run real-time analysis of price, NAV, basket composition and venue depth across the ETF universe."),
    ("Predict", "Proprietary AI-ML models score the persistence of each gap and the risk of moving against it."),
    ("Decide", "Strategy agents propose create or redeem, size and timing under portfolio-level constraints."),
    ("Approve", "The Execution Council approves or rejects — automatic, with approval, or manual. Rejected proposals are logged too."),
    ("Execute", "Execution agents route across clearing-and-settlement, OTC and dark-pool rails, HFT automation and dealer-brokers."),
    ("Settle", "Clearing and settlement tracked to completion, with counterparty exposure engineered out of the design."),
    ("Reconcile", "Every fill matched to broker truth; every transition hash-chained into the ledger."),
]
LANE_HOME = """(() => { const q = s => document.querySelectorAll(s); const items = [...q('#lc01 [data-lane-key] > li[data-g]')];
  return { flow: q('.flow').length, lane: q('#lc01 [data-lane]').length, gates: items.map(li => [li.dataset.g, li.textContent.replace(/\\s+/g, ' ').trim()]) }; })()"""
LANE_STEPS = """(() => { const sec = document.querySelector('#lc01'), ol = sec && (sec.querySelector('.lane-v--steps') || sec.querySelector('.lane-v')); const items = ol ? [...ol.querySelectorAll(':scope > li[data-g]')] : [];
  return { wall: document.querySelectorAll('.wall').length, lane: !!ol, steps: items.map(li => [li.dataset.g, ((li.querySelector('h3') || li).textContent || '').replace(/\\s+/g, ' ').trim()]),
    text: sec ? sec.textContent.replace(/\\s+/g, ' ') : '' }; })()"""


@check
async def lifecycle_lane_home(b):
    """home: no .flow; #lc01 holds the lane figure whose key lists the six gates 01 Signal ... 06 Settle, with and
    without JavaScript"""
    bad = []
    for js in (True, False):
        ctx, pg = await open_page(b, "index.html", 1440, 900, js=js, reduced=True)
        m = await pg.evaluate(LANE_HOME)
        ok = [g for g, t in m["gates"]] == [str(k + 1) for k in range(6)] and all(f"0{k + 1}" in t and GATES[k] in t for k, (g, t) in enumerate(m["gates"]))
        if m["flow"] or not m["lane"] or not ok: bad.append(f"index.html@1440x900 js={'on' if js else 'off'}: .flow {m['flow']}, lane figures {m['lane']}, gates {[(g, t[:28]) for g, t in m['gates']]}")
        await ctx.close()
    assert not bad, "lifecycle_lane_home:\n  " + "\n  ".join(bad)
    print("lifecycle_lane_home: no .flow; the lane's key lists 01 Signal ... 06 Settle, with and without JavaScript")


@check
async def lifecycle_lane_steps(b):
    """Lifecycles §03: the vertical lane draws the six gates plus the 07 Reconcile station (D2), each with its step text
    unchanged, and the eyebrow 'Seven steps · one swarm · vertical execution'; no .wall on the page; with and without
    JavaScript"""
    bad = []
    for js in (True, False):
        ctx, pg = await open_page(b, "lifecycles.html", 1440, 900, js=js, reduced=True)
        m = await pg.evaluate(LANE_STEPS)
        names = [re.sub(r"^\d+\s*", "", t) for g, t in m["steps"]]
        gs = [g for g, t in m["steps"]]
        tag = f"lifecycles.html@1440x900 js={'on' if js else 'off'}"
        if m["wall"]: bad.append(f"{tag}: {m['wall']} .wall element(s)")
        if not m["lane"] or names != [s for s, _ in STEPS] or gs != [str(k) for k in range(1, 8)]: bad.append(f"{tag}: the lane's stations read {m['steps']} (lane: {m['lane']})")
        missing = [s for s, t in STEPS if t not in m["text"]]
        if missing: bad.append(f"{tag}: step texts missing for {missing}")
        if "Seven steps · one swarm · vertical execution" not in m["text"]: bad.append(f"{tag}: the eyebrow 'Seven steps · one swarm · vertical execution' is gone")
        await ctx.close()
    assert not bad, "lifecycle_lane_steps:\n  " + "\n  ".join(bad)
    print("lifecycle_lane_steps: six gates + 07 Reconcile with their seven texts, no .wall, with and without JavaScript")


@check
async def desk_warm_start(b):
    """the desk opens with history: once [data-gap] is scrolled into view its clock reads 11:00 ET or later and its
    ledger strip (.desk-log) holds a record (polled up to 4 s here; the 1.2 s budget is verify_budget's desk_warm_time)"""
    ctx, pg = await open_page(b, "lifecycles.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-gap]').scrollIntoView({block: 'center', behavior: 'instant'})")
    t0 = time.monotonic()
    ok = await until(pg, "(() => { const m = (document.querySelector('[data-gap-time]').textContent || '').match(/(\\d\\d):(\\d\\d)/); return !!m && (+m[1] * 60 + +m[2]) >= 660 && document.querySelectorAll('.desk-log li').length >= 1; })()", 4000)
    info = await pg.evaluate("({time: document.querySelector('[data-gap-time]').textContent, log: document.querySelectorAll('.desk-log li').length})")
    await ctx.close()
    assert ok, f"desk_warm_start lifecycles.html@1440x900: {time.monotonic() - t0:.1f} s after the reveal the desk reads {info} (>= 11:00 ET and >= 1 record expected)"
    print(f"desk_warm_start: {info} within {time.monotonic() - t0:.1f} s of the reveal")


# ---- the phone chapter readout is never cut (NV5)
READOUT_PAGES = ["index", "platform", "lifecycles", "evidence", "trust", "company", "research", "research/01-compounding-error", "blog/index", "access"]
READOUT = "async () => { " + FRAMES + """ await frames(3); const lines = [...document.querySelectorAll('.nav-ch-btn .nav-ch-line')];
  const l = lines[0]; if (!l) return null;
  return { txt: l.textContent.replace(/\\s+/g, ' ').trim(), sw: l.scrollWidth, cw: l.clientWidth, cur: (document.querySelector('.nav-ch-list a[aria-current]') || {}).textContent || '' }; }"""


@check
async def nav_readout(b):
    """at 390 and 360, on every page with chapters and for every chapter: the readout's line in .nav-ch-btn has
    scrollWidth <= clientWidth (+1 px rounding): no chapter title is cut"""
    bad, n = [], 0
    for w, h in ((390, 844), (360, 780)):
        for name in READOUT_PAGES:
            ctx, pg = await open_page(b, f"{name}.html", w, h, reduced=True)
            hrefs = await pg.evaluate("[...document.querySelectorAll('.nav-ch-list a')].filter(a => !a.closest('li').hidden).map(a => a.getAttribute('href'))")
            for href in hrefs:
                await pg.evaluate("(h) => { const el = document.getElementById(decodeURIComponent(h.slice(1))); if (el) window.scrollTo({top: el.getBoundingClientRect().top + scrollY - 40, behavior: 'instant'}); }", href)
                r = await pg.evaluate(READOUT); n += 1
                if r and r["sw"] > r["cw"] + 1: bad.append(f"{name}.html@{w}x{h} {href}: '{r['txt']}' needs {r['sw']} px, has {r['cw']}")
            await ctx.close()
    assert not bad, f"nav_readout: {len(bad)} cut readouts:\n  " + "\n  ".join(bad[:20])
    print(f"nav_readout: {n} chapter readouts at 390 and 360, none cut")


@check
async def tables_phone(b):
    """at 390, 360 and 320, every .table-scroll on /platform.html and /evidence.html has scrollWidth <= clientWidth + 1"""
    bad = []
    for w, h in ((390, 844), (360, 780), (320, 640)):
        for name in ("platform", "evidence"):
            ctx, pg = await open_page(b, f"{name}.html", w, h, reduced=True)
            m = await pg.evaluate("[...document.querySelectorAll('.table-scroll')].map(t => [t.scrollWidth, t.clientWidth])")
            over = [x for x in m if x[0] > x[1] + 1]
            if not m or over: bad.append(f"{name}.html@{w}x{h}: .table-scroll [scrollWidth, clientWidth] {m}")
            await ctx.close()
    assert not bad, "tables_phone:\n  " + "\n  ".join(bad)
    print("tables_phone: every Platform and Proof table fits at 390, 360 and 320")


# ---- type craft: no synthesized bold (PG2)
FAUX = """(() => { const bad = []; for (const el of document.querySelectorAll('body *')) {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) continue;
    const cs = getComputedStyle(el); if (!/^\\s*["']?Instrument Serif/i.test(cs.fontFamily) || +cs.fontWeight <= 400) continue;
    if (bad.length < 6) bad.push(el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/).join('.') : '') + ' ' + cs.fontWeight + ' ' + JSON.stringify(el.textContent.trim().slice(0, 30)));
    else bad.push(1); }
  return { serif: bad, footer: [...document.querySelectorAll('.footer h2')].map(h => +getComputedStyle(h).fontWeight) }; })()"""


@check
async def faux_bold(b):
    """at 1440 on the eight pages (home, Platform, Lifecycles, Proof, Trust, Research, Company, Access): no element whose
    computed font-family starts with Instrument Serif has a computed font-weight above 400, and the footer h2 is <= 500"""
    bad = []
    for name in ("index", "platform", "lifecycles", "evidence", "trust", "research", "company", "access"):
        ctx, pg = await open_page(b, f"{name}.html", 1440, 900, reduced=True)
        m = await pg.evaluate(FAUX)
        if m["serif"]: bad.append(f"{name}.html@1440: {len(m['serif'])} Instrument Serif element(s) above 400, e.g. {[x for x in m['serif'] if x != 1][:3]}")
        if any(x > 500 for x in m["footer"]): bad.append(f"{name}.html@1440: footer h2 weights {m['footer']}")
        await ctx.close()
    assert not bad, "faux_bold:\n  " + "\n  ".join(bad)
    print("faux_bold: no synthesized serif bold on the eight pages; footer h2 <= 500")


# ---- Platform: the full spec without interaction (AR1); the swarm lab in §03 (SW3)
SPEC = """async () => { const norm = s => s.replace(/\\s+/g, ' ').trim();
  const doc = new DOMParser().parseFromString(await (await fetch(location.pathname, {cache: 'no-store'})).text(), 'text/html');
  const layers = [...doc.querySelectorAll('#architecture .layers .layer')], want = [];
  layers.forEach((l, i) => { const p = l.querySelector('p'); if (p) want.push(['0' + (i + 1) + ' paragraph', norm(p.textContent)]);
    l.querySelectorAll('dl.io dd').forEach((dd, j) => want.push(['0' + (i + 1) + (j ? ' Out' : ' In'), norm(dd.textContent)])); });
  const inner = norm(document.body.innerText), els = [...document.querySelectorAll('#architecture p, #architecture dd')];
  const shown = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'; };
  const missing = want.filter(([k, t]) => !(inner.includes(t) && els.some(e => norm(e.textContent) === t && shown(e)))).map(([k, t]) => k + ': ' + t.slice(0, 40));
  return { layers: layers.length, want: want.length, missing }; }"""


@check
async def platform_spec(b):
    """Platform at 1440, without any interaction: all eight layer paragraphs of §01 and their In/Out lines (from the
    page's own markup) are in innerText with non-zero boxes"""
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    await pg.wait_for_timeout(1500)
    m = await pg.evaluate(SPEC)
    await ctx.close()
    assert m["layers"] == 8 and m["want"] == 24 and not m["missing"], f"platform_spec platform.html@1440x900: {m['layers']} layers, {m['want']} texts; not shown: {m['missing'][:6]}"
    print("platform_spec: 8 layer paragraphs and 16 In/Out lines shown without interaction")


@check
async def platform_lab(b):
    """Platform §03 holds a running swarm lab (.sw-on, agents in flight and settling once in view) and an 'Illustrative'
    marking that is visible, >= 10 px and inside the viewport"""
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    has = await pg.evaluate("!!document.querySelector('#swarm [data-swarm-live].sw-on')")
    bad = []
    if not has: bad.append("no #swarm [data-swarm-live].sw-on")
    else:
        await pg.evaluate("document.querySelector('#swarm [data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
        num = "(s => +((document.querySelector('#swarm ' + s) || {}).textContent || 'NaN').replace(/[^\\d.]/g, ''))"
        if not await until(pg, f"{num}('[data-sw-inflight]') > 0 && {num}('[data-sw-recorded]') > 0", 25000, 200): bad.append("the lab has nothing in flight and nothing settled 25 s after it came into view")
        a = await pg.evaluate(f"{num}('[data-sw-recorded]')")
        if not await until(pg, f"{num}('[data-sw-recorded]') > {a or 0}", 12000, 200): bad.append(f"the lab's Settled counter did not move in 12 s ({a})")
    il = await pg.evaluate("""(() => { const out = []; document.querySelectorAll('#swarm *').forEach(e => {
        if (![...e.childNodes].some(n => n.nodeType === 3 && n.textContent.includes('Illustrative'))) return;
        e.scrollIntoView({block: 'center', behavior: 'instant'}); const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
        out.push({ t: e.textContent.trim().slice(0, 40), ok: r.width > 0 && cs.visibility !== 'hidden' && parseFloat(cs.fontSize) >= 10 && r.left >= 0 && r.right <= innerWidth, fs: cs.fontSize }); });
      return out; })()""")
    if not any(x["ok"] for x in il): bad.append(f"no readable 'Illustrative' in §03: {il[:3]}")
    await ctx.close()
    assert not bad, "platform_lab platform.html@1440x900:\n  " + "\n  ".join(bad)
    print(f"platform_lab: a running lab in Platform §03, marked {il[0]['t']!r}")


# ---------------------------------------------------------------- runner
def parse_args(argv):
    base, only, listing, i = None, None, False, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--only="): only = a.split("=", 1)[1]
        elif a == "--only" and i + 1 < len(argv): only = argv[i + 1]; i += 1
        elif a == "--list": listing = True
        elif re.match(r"https?://", a): base = a.rstrip("/")
        i += 1
    return base, ([n.strip() for n in only.split(",") if n.strip()] if only else None), listing


async def main():
    global BASE
    base, only, listing = parse_args(sys.argv[1:])
    if base: BASE = base
    names = [c.__name__ for c in CHECKS]
    if listing:
        for c in CHECKS: print(f"{c.__name__:24} {(c.__doc__ or '').strip().splitlines()[0]}")
        return 0
    unknown = [n for n in (only or []) if n not in names]
    if unknown: print("unknown check(s):", unknown, "- known:", ", ".join(names)); return 2
    todo = [c for c in CHECKS if only is None or c.__name__ in only]
    failed = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for c in todo:
            t0 = time.monotonic()
            try:
                await c(b)
                print(f"PASS {c.__name__} ({time.monotonic() - t0:.0f}s)", flush=True)
            except Exception as e:
                msg = str(e) if isinstance(e, AssertionError) and str(e) else "".join(traceback.format_exception_only(type(e), e)).strip()
                failed.append(c.__name__)
                print(f"FAIL {c.__name__} ({time.monotonic() - t0:.0f}s): {msg}", flush=True)
                if not isinstance(e, AssertionError): traceback.print_exc(limit=3)
        for ctx, pg in SHARED.values():
            try: await ctx.close()
            except Exception: pass
        await b.close()
    if failed:
        print(f"V9 CHECKS FAILED: {len(failed)} of {len(todo)}: {', '.join(failed)}")
        return 1
    print("V9 CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
