"""Visual + functional pass over v9: every page at 1440/390, story beats, live objects, form, no forbidden strings.
The homepage systems are checked as one page: the overture reads the sessions record, the nav's chapter readout, the
architecture explorer, the swarm lab's events reaching the ledger trace, the chain, the proof chart; then Proof, Trust
and Platform, a phone, reduced motion, a starved requestAnimationFrame, no JavaScript and no WebGL.

Round 1 (v2) adds one named check per guard from the director's list; each asserts an invariant that must hold in every
sample (no tight wall-clock timings: those live in tools/verify_budget.py). Every check runs in its own context (a few
share one homepage at 1440, each setting its own preconditions), and a failure names the check, the page, the viewport
and the offending values; the run goes on to the next check and exits non-zero if any failed.
    python tools/verify_v9.py [http://127.0.0.1:8125] [--only name1,name2] [--list] [--swiftshader | --gpu]
                              [--cpu-throttle N] [--cores N] [--check-timeout S] [--shards .github/workflows/checks.yml]
The site's CSP has no 'unsafe-eval': conditions are polled with page.evaluate (until()), never wait_for_function(<string>).

Round 2: CI (.github/workflows/checks.yml) runs this file in shards, one job per `--only` group, each with its own
tools/serve.py; `--shards <workflow>` checks that every check sits in exactly one shard (the static job runs it).
Reproducing CI on this machine. GitHub's ubuntu-latest runner renders WebGL with SwiftShader (no GPU) on 4 vCPUs that
are several times slower than a laptop; reproduce that with
    python tools/serve.py 8125                                     (another terminal)
    python tools/verify_v9.py --swiftshader --cpu-throttle 4 [--only <a shard's list>]
--swiftshader (the default; CI's renderer) launches Chromium on ANGLE's SwiftShader; --gpu uses the real GPU instead (local
only, to compare). --cpu-throttle N slows every page's main thread N times (CDP Emulation.setCPUThrottlingRate, applied
before the first navigation). --cores N pins the browser to N logical CPUs (inherited CPU affinity), as a small runner.
Both modes are printed in the run header with the host's CPU load. Calibrated against CI run 40731155926 (1a6b9fb): with
--cpu-throttle 4 this PC reproduced its 'home' failure (Locator.screenshot, 'waiting for element to be stable'), its
load-dependent loader (5-7.7 s) and the overture's labels never coming to rest on phones; a shard's CI time is about
1.2x its local --swiftshader --cpu-throttle 4 time plus a minute of set-up. Each check has a hard limit (--check-timeout, 600 s by
default; 1200 s for the two long overture checks): a hung step becomes a named FAIL with the line it hung on, the check's contexts are closed (a leaked page running
WebGL slows every later check), and the run goes on. Screenshots of moving instruments are clipped page screenshots taken
after that instrument's Pause control (or two equal boxes), with animations disabled, never Locator.screenshot.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from paths import REPO, SITE, DATA, SHOTS, DIST, ARCHIVE
import asyncio, json, linecache, os, platform, re, subprocess, sys, time, traceback
from pathlib import Path
from playwright.async_api import async_playwright, expect
# CI's runner is several times slower than a laptop: an expect() without its own timeout waits up to 20 s (Playwright's
# default is 5 s; under 6x throttling on two cores the chain's SHA-256 recheck of 'REJECTED' took longer). The same
# condition is asserted; only the patience changes. An expect() that names its own timeout (a deliberate 'at once') keeps it.
expect.set_options(timeout=20000)

BASE = "http://127.0.0.1:8125"  # the URL argument replaces it
SWIFTSHADER_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]  # CI's renderer
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]  # the real GPU (Windows; local comparison only)
MODE = {"gl": "swiftshader", "throttle": 1.0, "cores": None, "check_timeout": 600.0}
LIMITS = {"overture_phones": 1200, "overture_rest": 1200}  # checks that run long on CI by design (s); the rest use the default
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

# ---------------------------------------------------------------- run modes: every page throttled, every context tracked
OPEN = []      # the real contexts the running check opened; the runner closes whatever it leaves open
CDP_KEEP = []  # the CDP sessions that hold each page's CPU throttling (a detached session would drop it)


async def throttle_page(ctx, pg):
    """--cpu-throttle N: slow this page's main thread N times, before its first navigation"""
    if MODE["throttle"] > 1:
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": MODE["throttle"]})
        CDP_KEEP.append(cdp)


class ThrottledContext:
    """a BrowserContext whose new pages run at the --cpu-throttle rate; everything else passes through"""
    def __init__(self, ctx): self._ctx = ctx
    def __getattr__(self, k): return getattr(self._ctx, k)
    async def new_page(self):
        pg = await self._ctx.new_page()
        # a navigation or an action (a screenshot, a click, a locator read) may take long on a slow runner (CI) or a
        # loaded PC: 90 s each (Playwright's 30 s defaults failed home's first goto at 100% host load, and on the
        # round-2 merge at 4x a full-page screenshot in `pages` and a locator read in `no_js`); patience only, every
        # condition is the same, and a check's own limit still bounds it
        pg.set_default_navigation_timeout(90000)
        pg.set_default_timeout(90000)
        await throttle_page(self._ctx, pg)
        return pg


class TrackedBrowser:
    """the Browser the checks get: its contexts are throttled and tracked, so the runner closes any a check leaves open"""
    def __init__(self, b): self._b = b
    def __getattr__(self, k): return getattr(self._b, k)
    async def new_context(self, **kw):
        c = await self._b.new_context(**kw)
        OPEN.append(c)
        return ThrottledContext(c)


def host_load():
    """the host's CPU load now (Windows: busy share over 0.5 s from GetSystemTimes; elsewhere the 1-minute load average)"""
    n = os.cpu_count() or 1
    try:
        if platform.system() == "Windows":
            import ctypes
            from ctypes import wintypes
            def times():
                i, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
                v = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime
                return v(i), v(k), v(u)
            i0, k0, u0 = times(); time.sleep(0.5); i1, k1, u1 = times()
            total = (k1 - k0) + (u1 - u0)  # kernel time includes idle time
            return f"{n} logical CPUs, load {100 * (1 - (i1 - i0) / total) if total else 0:.0f}%"
        la = os.getloadavg()[0]
        return f"{n} logical CPUs, 1-min load average {la:.2f} ({la / n * 100:.0f}% of them)"
    except Exception as e:
        return f"{n} logical CPUs, load unknown ({type(e).__name__})"


def pin_cores(n):
    """--cores N: this process (and so the Playwright driver and Chromium it starts) runs on the last N logical CPUs"""
    total = os.cpu_count() or 1
    cpus = list(range(max(0, total - n), total))
    if hasattr(os, "sched_setaffinity"): os.sched_setaffinity(0, set(cpus)); return cpus
    if platform.system() == "Windows":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        if k32.SetProcessAffinityMask(ctypes.c_void_p(k32.GetCurrentProcess()), ctypes.c_size_t(sum(1 << c for c in cpus))): return cpus
    return None


def launch_args():
    return GPU_ARGS if MODE["gl"] == "gpu" else SWIFTSHADER_ARGS


def mode_line():
    gl = "real GPU (" + " ".join(GPU_ARGS) + ")" if MODE["gl"] == "gpu" else "SwiftShader (ANGLE; CI's software GL)"
    th = f"{MODE['throttle']:g}x (CDP Emulation.setCPUThrottlingRate on every page)" if MODE["throttle"] > 1 else "off"
    cores = f" · browser pinned to logical CPUs {MODE['cores']}" if MODE["cores"] else ""
    return f"renderer {gl} · CPU throttle {th}{cores} · check limit {MODE['check_timeout']:.0f} s · host: {host_load()}"


class CheckTimeout(Exception):
    pass


async def bounded(aw, what, limit=20):
    """an input dispatch (CDP touch, a tap) that must answer within `limit` s: CI's run hung 25 minutes in overture_tap,
    the first check that dispatches touches; a stuck dispatch now fails at once with its name instead of eating the job"""
    try:
        return await asyncio.wait_for(aw, limit)
    except asyncio.TimeoutError:
        raise AssertionError(f"{what} did not return in {limit} s (the renderer did not acknowledge the input)")


async def run_one(c, b):
    """run one check under the hard limit; on a hang, name the line it hung on and cancel it"""
    task = asyncio.ensure_future(c(b))
    limit = max(MODE["check_timeout"], LIMITS.get(c.__name__, 0))
    done, _ = await asyncio.wait({task}, timeout=limit)
    if task in done: return task.result()
    where = ""
    for f in task.get_stack(limit=1):
        where = f" at {Path(f.f_code.co_filename).name}:{f.f_lineno} `{linecache.getline(f.f_code.co_filename, f.f_lineno).strip()[:140]}`"
    task.cancel()
    await asyncio.wait({task}, timeout=20)
    raise CheckTimeout(f"timed out after {limit:.0f} s{where}")


async def close_leftovers(drop_shared=False):
    """close every context the last check left open (the shared homepage stays unless it may be wedged); False if one hung"""
    if drop_shared:
        SHARED.clear()
    keep = {id(v[0]._ctx) for v in SHARED.values() if isinstance(v[0], ThrottledContext)}
    ok = True
    for c in OPEN:
        if id(c) in keep: continue
        try: await asyncio.wait_for(c.close(), 25)
        except asyncio.TimeoutError: ok = False
        except Exception: pass
    OPEN[:] = [c for c in OPEN if id(c) in keep]
    if not OPEN: CDP_KEEP.clear()
    return ok


async def open_page(b, path, w, h, *, dpr=1, touch=False, reduced=False, js=True, init=None, errs=None, loaded=True):
    """a fresh context at w x h, the page loaded (for the home page: until the loader has finished)"""
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, has_touch=touch, is_mobile=touch,
                              reduced_motion="reduce" if reduced else "no-preference", java_script_enabled=js)
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
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


# a frame counter the rest waits use (installed on demand): equal reads only count as 'at rest' when frames ran between
# them, so a page whose frames take longer than the poll interval (CI's software GL) is never mistaken for one at rest
FRAME_COUNTER = "(() => { if (window.__oxaF === undefined) { window.__oxaF = 0; const f = () => { window.__oxaF++; requestAnimationFrame(f); }; requestAnimationFrame(f); } return window.__oxaF; })()"
SETTLED_SUPPORT = {}  # base URL -> whether its story.js exposes .story[data-settled] (OV-R2-1)


async def has_settled(pg=None):
    """does the overture under test expose .story[data-settled] (OV-R2-1)? Read once from its story.js"""
    if BASE not in SETTLED_SUPPORT:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{BASE}/assets/js/story.js", timeout=30) as r: js = r.read().decode("utf-8", "replace")
            SETTLED_SUPPORT[BASE] = bool(re.search(r"data-settled|dataset\.settled", js))
        except Exception:
            SETTLED_SUPPORT[BASE] = False
    return SETTLED_SUPPORT[BASE]


async def scene_rest(pg, n, timeout=None):
    """click the overture's index button for scene n and wait until it rests there: the index on n, beat n whole and,
    where the overture exposes it, .story[data-settled] (OV-R2-1); then the callouts unchanged across two reads with
    at least two frames between them (round 2: under CI's software GL a frame can take longer than the poll, and three
    equal reads with no frame between them passed a scene that was still moving). The limit is generous (30 s; 60 s
    with --cpu-throttle): no wall-clock assertion here."""
    timeout = timeout or (60000 if MODE["throttle"] > 1 else 30000)
    settled = await has_settled(pg)
    await pg.evaluate(FRAME_COUNTER)
    await pg.evaluate(f"document.querySelector('.story-idx [data-n=\"0{n}\"]').click()")
    snap = """(() => { const i = document.querySelector('.story-idx [aria-current]'); const b = document.querySelector('.beat-%d');
      return JSON.stringify([i && i.dataset.n, +(+getComputedStyle(b).opacity).toFixed(2), !!document.querySelector('.story[data-settled]'),
        [...document.querySelectorAll('.story-labels .story-lab.is-on')].map(l => l.style.transform + '|' + getComputedStyle(l).opacity), window.__oxaF]); })()""" % n
    t0, prev, same = time.monotonic(), None, 0
    await pg.wait_for_timeout(250)  # the click's own frame
    while time.monotonic() - t0 < timeout / 1000:
        st = json.loads(await pg.evaluate(snap))
        key, frames = json.dumps(st[:4]), st[4]
        if not (st[0] == f"0{n}" and st[1] >= 0.95 and (st[2] or not settled)): same, prev = 0, (key, frames)
        elif prev and key == prev[0]:
            if frames - prev[1] >= 2: same, prev = same + 1, (key, frames)  # unchanged across frames: one step of rest
        else: same, prev = 0, (key, frames)
        if same >= 2: return True
        await pg.wait_for_timeout(180)
    return False


async def story_end(pg):
    return await pg.evaluate("(() => { const s = document.querySelector('.story'); return s.offsetTop + s.offsetHeight; })()")


BOX = """(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect();
  const x0 = Math.max(0, r.left), y0 = Math.max(0, r.top), x1 = Math.min(innerWidth, r.right), y1 = Math.min(innerHeight, r.bottom);
  return [x0, y0, x1 - x0, y1 - y0].map(v => Math.round(v * 2) / 2); }"""


async def still_shot(pg, sel, path, pause=None):
    """a screenshot of an instrument that may be moving (round 2, CI): press its Pause control if it has one showing,
    wait for two equal boxes 150 ms apart, then a clipped page.screenshot with animations disabled; motion resumes
    afterwards. Never Locator.screenshot, whose 'element is stable' wait never ends on a running instrument under
    software GL (CI: 'waiting for element to be stable', 30 s). Returns whether it paused."""
    await pg.evaluate("(s) => document.querySelector(s).scrollIntoView({block: 'center', behavior: 'instant'})", sel)
    btn = pg.locator(pause).first if pause else None
    paused = bool(btn and await btn.count() and await btn.is_visible())
    if paused: await btn.click()
    box, last = None, None
    for _ in range(40):
        box = await pg.evaluate(BOX, sel)
        if box == last: break
        last = box; await pg.wait_for_timeout(150)
    if box and box[2] >= 1 and box[3] >= 1:
        await pg.screenshot(path=str(path), clip={"x": box[0], "y": box[1], "width": box[2], "height": box[3]}, animations="disabled", timeout=60000)
    if paused: await btn.click()
    return paused


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
    await still_shot(pg, "[data-swarm-live]", OUT / "swarm.png", pause="[data-sw-motion]")  # round 2 (CI): never Locator.screenshot on the running lab
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
    # Round 2 (LG-R2-3): the foot names the swarm's rows as digests ('M swarm digests covering S settled ...'); round 1
    # said '... from the swarm above, carrying S settled ...'
    await expect(pg.locator("[data-lt-swarm]")).to_contain_text(re.compile(r"from the swarm above|swarm digests?"))
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
    await still_shot(pg, "[data-chain]", OUT / "chain-broken.png")
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
    # Round 2 (PF-R2-3a): home no longer shows the chart's summary row (the stats row says it); where the inspector row is
    # gone, the selected option itself carries the session's record
    if await pg.locator("#proof .pf-read").count() and await pg.locator("#proof .pf-read").first.is_visible():
        await expect(pg.locator("#proof .pf-read")).to_contain_text("Day 02")
    else:
        await expect(opts.nth(1)).to_contain_text("Day 02")
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
    await still_shot(pg, "[data-gap]", OUT / "desk.png", pause="[data-gap-motion]")
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


# where the loader is, read in the page: [performance.now(), 'parsing' | 'shown' | 'hidden' | 'removed', opacity, visibility]
LOADER_STATE = """(() => { const t = performance.now(), l = document.querySelector('.loader');
  if (!l || !l.isConnected) return [t, document.readyState === 'loading' ? 'parsing' : 'removed', 0, ''];
  const cs = getComputedStyle(l), o = +cs.opacity;
  return [t, cs.display === 'none' || cs.visibility === 'hidden' || o < 0.05 ? 'hidden' : 'shown', +o.toFixed(3), cs.visibility]; })()"""


# when the main thread was too busy to answer, the moment an animation took the loader's opacity under .05, from its own
# timing and keyframes. Only an animation the compositor can run by itself (keyframes of opacity / transform / filter
# only) counts: it shows on time while scripts hold the main thread, so a poll sees it late. One that also animates
# visibility or pointer-events runs on the main thread, so the reader sees what the poll sees.
LOADER_ANIM = r"""(() => { const l = document.querySelector('.loader'); if (!l || !l.isConnected) return null;
  const bez = (x1, y1, x2, y2) => t => { let lo = 0, hi = 1, s = t; for (let i = 0; i < 24; i++) { s = (lo + hi) / 2; const x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3; if (x < t) lo = s; else hi = s; }
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3; };
  const EASE = { linear: t => t, ease: bez(.25, .1, .25, 1), 'ease-in': bez(.42, 0, 1, 1), 'ease-out': bez(0, 0, .58, 1), 'ease-in-out': bez(.42, 0, .58, 1) };
  const easing = e => { const m = /cubic-bezier\(([^)]+)\)/.exec(e || ''); return m ? bez(...m[1].split(',').map(Number)) : EASE[e] || EASE.linear; };
  let best = null;
  const OK = new Set(['opacity', 'transform', 'translate', 'rotate', 'scale', 'filter', 'offset', 'computedOffset', 'easing', 'composite']);
  for (const a of l.getAnimations()) { const all = a.effect.getKeyframes(), k = all.filter(f => f.opacity !== undefined), tm = a.effect.getComputedTiming();
    if (!k.length || a.startTime == null || all.some(f => Object.keys(f).some(p => !OK.has(p)))) continue; const pts = [...k];
    if (pts[0].computedOffset > 0) pts.unshift({ computedOffset: 0, opacity: getComputedStyle(l).opacity, easing: 'linear' });
    const at = p => { for (let i = 0; i < pts.length - 1; i++) { const a0 = pts[i], a1 = pts[i + 1]; if (p >= a0.computedOffset && p <= a1.computedOffset) { const u = a1.computedOffset > a0.computedOffset ? (p - a0.computedOffset) / (a1.computedOffset - a0.computedOffset) : 1; return +a0.opacity + (+a1.opacity - +a0.opacity) * easing(a0.easing)(u); } } return +pts[pts.length - 1].opacity; };
    const dur = +tm.duration || 0;
    for (let t = 0; t <= dur; t += Math.max(1, dur / 400)) if (at(t / (dur || 1)) < 0.05) { const when = a.startTime + (+tm.delay || 0) + t; if (best === null || when < best) best = when; break; } }
  return best; })()"""


# the opacity steps of a @keyframes rule by name, from the page's style sheets: [[offsets], {property: value}] per keyframe
KEYFRAMES = r"""(name) => { let out = null;
  const walk = rules => { for (const r of rules) { if (r.type === CSSRule.KEYFRAMES_RULE && r.name === name) out = [...r.cssRules].map(k => [k.keyText.split(',').map(x => x.trim() === 'from' ? 0 : x.trim() === 'to' ? 100 : parseFloat(x)), Object.fromEntries([...k.style].map(p => [p, k.style.getPropertyValue(p)]))]);
    else if (r.cssRules) walk(r.cssRules); } };
  for (const s of document.styleSheets) { try { walk(s.cssRules); } catch (e) {} } return out; }"""
COMPOSITED = {"opacity", "transform", "translate", "rotate", "scale", "filter", "backdrop-filter", "animation-timing-function"}


def cubic(e):
    """a CSS easing keyword or cubic-bezier() as a function of progress"""
    pts = {"linear": None, "ease": (.25, .1, .25, 1), "ease-in": (.42, 0, 1, 1), "ease-out": (0, 0, .58, 1), "ease-in-out": (.42, 0, .58, 1)}
    m = re.match(r"cubic-bezier\(([^)]+)\)", e or "")
    p = tuple(float(v) for v in m[1].split(",")) if m else pts.get((e or "linear").strip(), None)
    if not p: return lambda t: t
    x1, y1, x2, y2 = p
    def f(t):
        lo, hi, s = 0.0, 1.0, t
        for _ in range(30):
            s = (lo + hi) / 2
            x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3
            lo, hi = (s, hi) if x < t else (lo, s)
        return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3
    return f


def fade_crossing(anim, kfs):
    """for a CSS animation reported by CDP (Animation.animationStarted) and its @keyframes: (the document-timeline ms at
    which it takes opacity under .05, or None; whether the compositor can run it alone; the other properties it animates)"""
    src, steps = anim.get("source") or {}, []
    easings = {float(k["offset"].rstrip("%")): k.get("easing") for k in ((src.get("keyframesRule") or {}).get("keyframes") or []) if k.get("offset", "").rstrip("%").replace(".", "", 1).isdigit()}
    # an implicit 0% keyframe eases by the animation's timing function, which CDP repeats on every keyframe it lists
    fn = easings.get(0.0) or (next(iter(easings.values())) if easings else "ease")
    num = lambda v: float(v.strip().rstrip("%")) / (100 if v.strip().endswith("%") else 1)
    for offs, props in kfs or []:
        for o in offs:
            if "opacity" in props: steps.append((o, num(props["opacity"]), easings.get(o, fn)))
    others = sorted({p for _, props in kfs or [] for p in props} - COMPOSITED)
    if not steps or anim.get("startTime") is None: return None, not others, others
    steps.sort()
    if steps[0][0] > 0: steps.insert(0, (0.0, 1.0, fn))  # the loader's own opacity is 1
    if steps[-1][0] < 100: steps.append((100.0, 1.0, "linear"))
    dur, delay = float(src.get("duration") or 0), float(src.get("delay") or 0)
    for k in range(401):
        p = k / 400 * 100
        for (o0, v0, e0), (o1, v1, _) in zip(steps, steps[1:]):
            if o0 <= p <= o1:
                v = v0 + (v1 - v0) * cubic(e0)((p - o0) / (o1 - o0) if o1 > o0 else 1)
                if v < 0.05: return anim["startTime"] + delay + dur * p / 100, not others, others
                break
    return None, not others, others


@check
async def loader(b):
    """the loader finishes on elapsed time, not on frames: with requestAnimationFrame starved it is not visible
    (removed, or computed visibility hidden / opacity < .05) by 4.5 s after navigation, and removed by 9 s"""
    # Round 2 (NV-R2-1, director's test list): 'removed by 4.5 s' became 'not visible by 4.5 s, removed by 9 s'. What a
    # reader sees is the same criterion (no loader on screen after 4.5 s); the DOM removal may follow the late scripts.
    # While scripts hold the main thread the page cannot answer a poll, but the compositor still runs a fade whose
    # keyframes animate only opacity (or transform/filter): such a fade is credited from its own timing (CDP's Animation
    # domain gives its start, delay and duration; the page's style sheet its keyframes). A fade that also animates
    # visibility or pointer-events runs on the main thread and freezes with it, so the reader sees what the poll sees.
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script("window.requestAnimationFrame = () => 0;")
    pg = await ctx.new_page()
    cdp = await ctx.new_cdp_session(pg)
    started = []
    cdp.on("Animation.animationStarted", lambda e: started.append(e.get("animation") or {}))
    await cdp.send("Animation.enable")
    await pg.goto(f"{BASE}/index.html", wait_until="commit")
    samples, t_end, anim_at, node = [], time.monotonic() + 60, None, None
    while time.monotonic() < t_end:
        s = await pg.evaluate(LOADER_STATE)
        samples.append(s)
        if s[1] in ("shown", "hidden"):
            a = await pg.evaluate(LOADER_ANIM)  # a compositor fade's crossing, read while the loader still exists
            if a is not None: anim_at = a if anim_at is None else min(anim_at, a)
            if node is None:  # the loader's node, to know which of CDP's animations are its own
                try:
                    doc = await cdp.send("DOM.getDocument", {"depth": 0})
                    q = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": ".loader"})
                    if q.get("nodeId"): node = (await cdp.send("DOM.describeNode", {"nodeId": q["nodeId"]}))["node"]["backendNodeId"]
                except Exception: pass
        if s[1] == "removed" or s[0] > 9600: break
        await pg.wait_for_timeout(50)
    fades = []  # (name, start, crossing, compositor-only, other properties) of the loader's own CSS animations
    for a in started:
        if a.get("type") != "CSSAnimation" or node is None or (a.get("source") or {}).get("backendNodeId") != node: continue
        try: kfs = await pg.evaluate(KEYFRAMES, a.get("name") or "")
        except Exception: kfs = None
        at, comp, others = fade_crossing(a, kfs)
        if at is not None: fades.append((a.get("name"), a.get("startTime"), at, comp, others))
    await ctx.close()
    first = lambda states: next((i for i, s in enumerate(samples) if s[1] in states), None)
    ih, ir = first(("hidden", "removed")), first(("removed",))
    t_seen = samples[ih][0] if ih is not None else None
    shown = [s for s in samples if s[1] == "shown"]
    last_shown = max((s[0] for s in samples[:ih] if s[1] == "shown"), default=0) if ih is not None else None
    # credited: the earliest compositor-only crossing that no later poll contradicts (the page saw it shown afterwards)
    cands = [x[2] for x in fades if x[3]] + ([anim_at] if anim_at is not None else [])
    credit = min((c for c in cands if t_seen is not None and last_shown <= c <= t_seen), default=None)
    t_hid = credit if credit is not None else t_seen
    t_rem = samples[ir][0] if ir is not None else None
    gap = samples[ih][0] - samples[ih - 1][0] if ih else 0  # a long gap: the page could not answer (busy main thread)
    detail = (f"not visible at {t_hid:.0f} ms" if t_hid is not None else f"still visible at {samples[-1][0]:.0f} ms (opacity {samples[-1][2]}, {samples[-1][3]})") + \
             (f" (a compositor fade crossed opacity .05 then; the page first answered at {t_seen:.0f} ms)" if t_hid is not None and t_hid != t_seen else "") + \
             (f", removed at {t_rem:.0f} ms" if t_rem is not None else ", never removed") + f"; {len(samples)} samples, last visible one at {shown[-1][0]:.0f} ms" * bool(shown) + \
             (f"; the page did not answer for {gap:.0f} ms before it was seen hidden" if gap > 400 else "") + \
             "".join(f"; its animation '{n}' starts at {st:.0f} ms on the page's clock (the loader's first frame, unless the page sets it) and takes opacity under .05 at {at:.0f} ms, " +
                     ("on the compositor" if comp else f"on the main thread (it also animates {', '.join(o)}), so it froze while scripts held the page") for n, st, at, comp, o in fades)
    assert t_hid is not None and t_hid <= 4500 and t_rem is not None and t_rem <= 9000, \
        f"loader index.html@1440x900, requestAnimationFrame starved: {detail} (must be not visible by 4500 ms and removed by 9000 ms)"
    print(f"loader: with requestAnimationFrame starved, {detail}")


LINK_PAGES = ["index", "platform", "lifecycles", "evidence", "trust", "company", "access", "research"]
LINKS = "(() => [...document.querySelectorAll('main a[href]')].filter(a => { const r = a.getBoundingClientRect(), cs = getComputedStyle(a); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && !a.closest('[hidden]'); }).length)()"
POSTS = "(() => [...document.querySelectorAll('li.post a')].filter(a => { const r = a.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(a).visibility !== 'hidden'; }).length)()"


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
    # Round 2 (PG-R2-1, director's test list): without JavaScript the reader keeps the links. On each hand-written page
    # and research.html the visible a[href] in main are at least 90% of those with JavaScript; research.html shows its
    # ten notes ('li.post a'), which a no-JS rule hid at 1a6b9fb
    nojs = {}
    for name in LINK_PAGES:
        await pg.goto(f"{BASE}/{name}.html", wait_until="load")
        nojs[name] = await pg.evaluate(LINKS)
    await pg.goto(f"{BASE}/research.html", wait_until="load")
    posts = await pg.evaluate(POSTS)
    await ctx.close()
    ctx = await b.new_context(viewport={"width": 390, "height": 844})
    pg = await ctx.new_page()
    low = []
    for name in LINK_PAGES:
        await pg.goto(f"{BASE}/{name}.html", wait_until="load"); await pg.wait_for_timeout(900)
        withjs = await pg.evaluate(LINKS)
        if nojs[name] < 0.9 * withjs: low.append(f"{name}.html@390: {nojs[name]} visible links in main without JavaScript, {withjs} with it")
    await ctx.close()
    assert not low and posts == 10, f"no_js: {low}; research.html shows {posts} visible 'li.post a' without JavaScript (10 expected)"
    print(f"fallbacks: readable without JS on every page (sessions list, ledger and chain records, six gates, eight layers with the boundary after 04, menu sheet as a popover, no loader); "
          f"links kept without JS on {len(LINK_PAGES)} pages, research.html lists its {posts} notes")


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
  const days = [...document.querySelectorAll('.story-labels .story-lab.day')].filter(shown).map(l => box(l)).sort((a, b) => a.l - b.l);
  return { issues, labs: labs.length, boxes: labs.map(l => [l.t, l.bx]), dayGaps: days.slice(1).map((d, k) => +(d.l - days[k].r).toFixed(1)),
    cap3: c3 ? { t: c3.t, inside: c3.bx.l >= 0 && c3.bx.t >= 0 && c3.bx.r <= innerWidth && c3.bx.b <= innerHeight, bx: [c3.bx.l, c3.bx.t, c3.bx.r, c3.bx.b].map(Math.round) } : null };
})()"""
PHONES = [(390, 664), (375, 667), (360, 780), (320, 640), (844, 390), (320, 568), (667, 375), (740, 360)]  # round 2 adds the last three
INSP_BOX = r"""(tapped) => { const vis = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
  const bx = el => { const r = el.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const hit = (a, c) => Math.min(a[2], c[2]) - Math.max(a[0], c[0]) > 1 && Math.min(a[3], c[3]) - Math.max(a[1], c[1]) > 1;
  const i = document.querySelector('.story-insp'); if (!i || !i.classList.contains('is-on') || vis(i) < 0.3) return null;
  const ib = bx(i), out = [];
  for (const s of ['.story-bar', '.story-idx', '.story-motion']) { const e = document.querySelector(s); if (e && vis(e) > 0.3 && hit(ib, bx(e))) out.push(s); }
  document.querySelectorAll('.story-labels .story-lab').forEach((l, k) => { if (k !== tapped && vis(l) > 0.3 && l.getBoundingClientRect().width > 0 && hit(ib, bx(l))) out.push("'" + l.textContent.replace(/\s+/g, ' ').trim().slice(0, 20) + "'"); });
  return { text: i.textContent.replace(/\s+/g, ' ').trim().slice(0, 30), box: ib.map(Math.round), hits: out }; }"""


async def callout_pixels(pg, boxes):
    """with .story-labels hidden (callouts and leaders), the share of stage pixels brighter than luminance 120 inside
    each callout's box: [(text, share)] for the boxes at 2% or more"""
    from PIL import Image
    import io
    await pg.evaluate("document.querySelector('.story-labels').style.visibility = 'hidden'")
    await pg.wait_for_timeout(350)
    img = Image.open(io.BytesIO(await pg.screenshot(animations="disabled"))).convert("L")
    await pg.evaluate("document.querySelector('.story-labels').style.visibility = ''")
    out = []
    for t, bx in boxes:
        c = img.crop((max(0, int(bx["l"])), max(0, int(bx["t"])), min(img.size[0], int(round(bx["r"]))), min(img.size[1], int(round(bx["b"])))))
        n = c.size[0] * c.size[1]
        if n <= 0: continue
        lit = c.point(lambda v: 255 if v > 120 else 0).histogram()[255] / n
        if lit >= 0.02: out.append((t[:24], f"{lit * 100:.1f}%"))
    return out


@check
async def overture_phones(b):
    """at 390x664, 375x667, 360x780, 320x640, 844x390, 320x568, 667x375 and 740x360 with touch, at each scene's rest: no
    visible callout box crosses the scene index, 'Pause motion', the nav, a visible beat's text or another callout; with
    the callouts hidden, under 2% of the stage's pixels inside each callout's box are brighter than luminance 120 (no
    structure under a callout); Plate 03's caption lies inside the viewport and says 'Illustrative'; at 320x640 adjacent
    S4 day tags are at least 3 px apart; at 844x390 and 667x375, the inspector opened by tapping each S1 ring and S2
    plate callout crosses none of .story-bar, .story-idx, .story-motion or another callout (OV1, OV10, D14; round 2:
    OV-R2-1, OV-R2-4, OV-R2-5)"""
    bad = []
    for w, h in PHONES:
        ctx, pg = await open_page(b, "index.html", w, h, touch=True)
        for i in range(5):
            if not await scene_rest(pg, i): bad.append(f"index.html@{w}x{h} scene 0{i}: did not come to rest")
            m = await pg.evaluate(PHONE_LAB)
            bad += [f"index.html@{w}x{h} scene 0{i}: {x}" for x in m["issues"]]
            lit = await callout_pixels(pg, m["boxes"])
            if lit: bad.append(f"index.html@{w}x{h} scene 0{i}: a structure under callouts (share of pixels > 120 in the box, callouts hidden): {lit[:4]}")
            if i == 3:
                c = m["cap3"]
                if not c: bad.append(f"index.html@{w}x{h} scene 03: no visible Plate 03 caption")
                elif not c["inside"] or "Illustrative" not in c["t"]: bad.append(f"index.html@{w}x{h} scene 03: caption {c['t']!r} at {c['bx']} (inside: {c['inside']}; must lie in the viewport and say 'Illustrative')")
            if i == 4 and (w, h) == (320, 640):
                tight = [g for g in m["dayGaps"] if g < 3]
                if tight: bad.append(f"index.html@320x640 scene 04: adjacent day tags closer than 3 px {len(tight)} times (gaps {m['dayGaps']})")
            if i in (1, 2) and (w, h) in ((844, 390), (667, 375)):
                sel = ".story-labels .story-lab.ring.is-on" if i == 1 else ".story-labels .story-lab.layer.is-on"
                for k in range(await pg.locator(sel).count()):
                    lab = pg.locator(sel).nth(k)
                    bb = await lab.bounding_box()
                    if not bb: continue
                    idx = await lab.evaluate("l => [...document.querySelectorAll('.story-labels .story-lab')].indexOf(l)")
                    await bounded(pg.touchscreen.tap(bb["x"] + bb["width"] * 0.3, bb["y"] + bb["height"] / 2), f"a tap on callout {k + 1} at {w}x{h}")
                    await until(pg, "!!document.querySelector('.story-insp.is-on')", 3000)
                    await pg.wait_for_timeout(400)
                    r = await until(pg, f"(() => {{ const r = ({INSP_BOX})({idx}); return r ? JSON.stringify(r) : ''; }})()", 3000, 150)
                    r = json.loads(r) if r else None
                    # a tap must open its inspector (OV-R2-4: ring_tap opens 6/6 at 844x390 and 667x375), or nothing was tested
                    if not r: bad.append(f"index.html@{w}x{h} scene 0{i}: callout {k + 1} tapped at ({bb['x'] + bb['width'] * 0.3:.0f}, {bb['y'] + bb['height'] / 2:.0f}): no inspector opened")
                    elif r["hits"]: bad.append(f"index.html@{w}x{h} scene 0{i}: the inspector {r['text']!r} at {r['box']} (callout {k + 1} tapped) crosses {r['hits']}")
                    await bounded(pg.touchscreen.tap(6, h * 0.5), "a tap on empty stage"); await pg.wait_for_timeout(400)  # a tap on empty stage closes it
        await ctx.close()
    by = {}
    for x in bad:
        m = re.match(r"index\.html@(\S+) scene 0(\d)", x)
        if m: by[f"{m[1]} S{m[2]}"] = by.get(f"{m[1]} S{m[2]}", 0) + 1
    assert not bad, f"overture_phones: {len(bad)} problems (by viewport and scene: {', '.join(f'{k} {v}' for k, v in by.items())}):\n  " + "\n  ".join(bad[:30])
    print(f"overture_phones: {len(PHONES)} phone viewports x 5 scenes, no callout over the index, the nav, the copy, a structure or another callout")


# ---- S1 on a phone: a tap opens its own lifecycle; a swipe never inspects (OV2)
RING_POINT = """(() => { const lab = document.querySelector('.story-labels .story-lab.ring.is-on'); const p = document.querySelector('.story-leaders path.ring.is-on');
  if (!lab || !p) return null; const m = p.getScreenCTM(), L = p.getTotalLength();
  const a = p.getPointAtLength(0).matrixTransform(m), z = p.getPointAtLength(L).matrixTransform(m), r = lab.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2, d = q => Math.hypot(q.x - cx, q.y - cy);
  const q = d(a) > d(z) ? a : z; return { x: q.x, y: q.y }; })()"""
INSP = "(() => { const i = document.querySelector('.story-insp'); return i && i.classList.contains('is-on') ? i.textContent.replace(/\\s+/g, ' ').trim() : ''; })()"


async def touch_drag(cdp, x0, y0, x1, y1, steps=10, dt=16):
    await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]}), "touchStart")
    for i in range(1, steps + 1):
        await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]}), "touchMove")
        await asyncio.sleep(dt / 1000)
    await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}), "touchEnd")


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
        await bounded(pg.touchscreen.tap(bb["x"] + bb["width"] * 0.25, bb["y"] + bb["height"] / 2), f"a tap on ring callout {k + 1}")
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
    rest = await scene_rest(pg, 2)
    seq = [await settled_scene(pg)]
    for w, h in ((844, 390), (390, 844)):
        await pg.set_viewport_size({"width": w, "height": h}); await pg.wait_for_timeout(600)
        seq.append(await settled_scene(pg))
    if seq != ["02", "02", "02"]: bad.append(f"S2 at 390x844 -> 844x390 -> 390x844 reads scenes {seq}" + ("" if rest else " (S2 never came to rest after its index click)"))
    await ctx.close()
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    rest = await scene_rest(pg, 4)
    s0 = await settled_scene(pg)
    await pg.set_viewport_size({"width": 768, "height": 1024}); await pg.wait_for_timeout(600)
    s1 = await settled_scene(pg)
    o4 = await pg.evaluate("+getComputedStyle(document.querySelector('.beat-4')).opacity")
    if [s0, s1] != ["04", "04"] or o4 < 0.9: bad.append(f"S4 at 1440x900 -> 768x1024 reads scenes {[s0, s1]}, .beat-4 opacity {o4:.2f}" + ("" if rest else " (S4 never came to rest after its index click)"))
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


# each counted block tagged with its lane (data-pe), and the moments the chart turns .is-in and drops .is-armed (which
# ends any transition still running: proof.js's ENTRANCE_MS), on the page's clock
PROOF_MARK = """(() => { const host = document.querySelector('#proof [data-proof-chart]'); const R = window.__pem = { inAt: null, cutAt: null }; let k = 0;
  [...host.querySelectorAll('.pf-lane')].forEach((l, i) => l.querySelectorAll('.pf-c i:not(.is-void), .pf-g i').forEach(b => b.setAttribute('data-pe', i + ':' + (k++))));
  new MutationObserver(() => { const c = host.classList, t = performance.now(); if (R.inAt === null && c.contains('is-in')) R.inAt = t; if (R.inAt !== null && R.cutAt === null && !c.contains('is-armed')) R.cutAt = t; })
    .observe(host, { attributes: true, attributeFilter: ['class'] }); })()"""
PROOF_FINAL = "(() => Object.fromEntries([...document.querySelectorAll('[data-pe]')].map(b => [b.dataset.pe, +getComputedStyle(b).opacity])))()"


def lane_nodes(tree):
    """backendNodeId -> its data-pe ('lane:block') for every element of a CDP DOM tree carrying one"""
    out, stack = {}, [tree]
    while stack:
        n = stack.pop()
        a = n.get("attributes") or []
        d = dict(zip(a[::2], a[1::2]))
        if "data-pe" in d: out[n.get("backendNodeId")] = d["data-pe"]
        stack.extend(n.get("children") or [])
    return out


def entrance_timeline(started, lanes, finals, in_at, cut_at):
    """the lit moment (opacity >= .5, the sampler's rule) of every counted block, from its opacity transition's own timing
    (start, delay, duration, easing; a transition still running when .is-armed drops ends then); a block with no
    transition is lit from .is-in, one whose final opacity is under .5 never. Returns (blocks with a transition,
    [(t, counts per lane)] after every step)"""
    tr = {}
    for a in started:
        src = a.get("source") or {}
        if a.get("type") == "CSSTransition" and a.get("name") == "opacity" and src.get("backendNodeId") in lanes and a.get("startTime") is not None:
            tr[src["backendNodeId"]] = a
    lit, nlane = [], max([int(pe.split(":")[0]) for pe in lanes.values()], default=-1) + 1
    for node, pe in lanes.items():
        lane, target = int(pe.split(":")[0]), finals.get(pe, 1.0)
        if target < 0.5: continue
        a = tr.get(node)
        if a is None: at = in_at
        else:
            src = a["source"]; ease = cubic(src.get("easing") or "linear")
            p = next((k / 200 for k in range(201) if target * ease(k / 200) >= 0.5), 1.0)
            at = a["startTime"] + float(src.get("delay") or 0) + float(src.get("duration") or 0) * p
        if cut_at is not None and at is not None and at > cut_at: at = cut_at
        if at is not None: lit.append((at, lane))
    lit.sort()
    counts, steps = [0] * nlane, []
    for k, (t, lane) in enumerate(lit):
        counts[lane] += 1
        if k + 1 == len(lit) or lit[k + 1][0] > t + 0.5: steps.append((t, counts[:]))  # simultaneous lights are one step
    return len(tr), steps


@check
async def proof_entrance(b):
    """arriving at home §04's chart from above at 1440 (about 38% of it in view), sampled every 50 ms for 1.5 s: the ten
    lanes' lit block counts never differ by more than one (no staircase, no session below another); the entrance played.
    Round 2 (CI): the same invariant is also checked at every instant of the entrance rebuilt from each block's opacity
    transition (CDP Animation domain), so a main thread too busy to sample during the 1.1 s entrance (CI's software GL
    at 4x) neither hides a staircase nor fails a correct chart for want of a sample"""
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    cdp = await ctx.new_cdp_session(pg)
    started = []
    cdp.on("Animation.animationStarted", lambda e: started.append(e.get("animation") or {}))
    g = await pg.evaluate("(() => { const r = document.querySelector('#proof [data-proof-chart]').getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; })()")
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 - 60}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
    pre = await pg.evaluate("document.querySelector('#proof [data-proof-chart]').classList.contains('is-in')")
    await pg.evaluate(PROOF_MARK)
    lanes = lane_nodes((await cdp.send("DOM.getDocument", {"depth": -1}))["root"])
    await cdp.send("Animation.enable")
    n = await pg.evaluate(PROOF_SAMPLER, 1500)
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 + g['h'] * 0.38:.0f}, behavior: 'instant'}})")
    await until(pg, "window.__pe.done", 9000 if MODE["throttle"] <= 1 else 30000)
    await pg.wait_for_timeout(1600)  # past ENTRANCE_MS: every block final
    s = (await pg.evaluate("window.__pe"))["s"]
    mk, finals = await pg.evaluate("window.__pem"), await pg.evaluate(PROOF_FINAL)
    await ctx.close()
    total = max((sum(x["c"]) for x in s), default=0)
    spread = [(x["t"], max(x["c"]) - min(x["c"]), x["c"]) for x in s if x["c"]]
    worst = max(spread, key=lambda v: v[1]) if spread else None
    ntr, steps = entrance_timeline(started, lanes, finals, mk["inAt"], mk["cutAt"])
    rworst = max(((t, max(c) - min(c), c) for t, c in steps), key=lambda v: v[1], default=None)
    played = any(0 < sum(x["c"]) < total for x in s) or ntr > 0  # seen mid-way, or its transitions ran after the arrival
    ok = n == 10 and not pre and played and worst and worst[1] <= 1 and (rworst is None or rworst[1] <= 1)
    rel = lambda t: f"{t - mk['inAt']:.0f} ms after .is-in" if mk["inAt"] is not None else f"{t:.0f} ms"
    assert ok, (f"proof_entrance index.html@1440x900: {n} lanes; revealed before arrival: {pre}; entrance observed: {played} ({ntr} block transitions); "
                f"worst lane spread {worst[1] if worst else '?'} at {worst[0] if worst else '?'} ms in the samples: {worst[2] if worst else ''}; "
                f"rebuilt from the transitions: worst spread {rworst[1] if rworst else '-'}" + (f" at {rel(rworst[0])}: {rworst[2]}" if rworst else ""))
    print(f"proof_entrance: {len(s)} samples and {len(steps)} steps rebuilt from {ntr} block transitions; lanes never differ by more than {max(worst[1], rworst[1] if rworst else 0)} block")


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
    # LC-R2-6a adds a leading '+N earlier records' row (li.dk-more): it is not a record, so it is not counted
    ok = await until(pg, "(() => { const m = (document.querySelector('[data-gap-time]').textContent || '').match(/(\\d\\d):(\\d\\d)/); return !!m && (+m[1] * 60 + +m[2]) >= 660 && document.querySelectorAll('.desk-log li:not(.dk-more)').length >= 1; })()", 4000)
    info = await pg.evaluate("({time: document.querySelector('[data-gap-time]').textContent, log: document.querySelectorAll('.desk-log li:not(.dk-more)').length})")
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


# ================================================================ round 2 (v2) guards: the director's test list of 28 Oct
# ---- the swarm lab: the trace says where its record went (SW-R2-1); gate labels never collide (SW-R2-2)
TEXT_WATCH = r"""(pat) => { const hit = window.__tw = window.__tw || []; const re = new RegExp(pat, 'i');
  const sel = ['#sw-trace', '[data-sw-callout]', '[data-sw-agent]', '[data-sw-say]'];
  const look = () => sel.forEach(s => document.querySelectorAll(s).forEach(el => { const t = (el.textContent || '').replace(/\s+/g, ' '), m = re.exec(t);
    if (m && hit.length < 12) hit.push(s + ': ...' + t.slice(Math.max(0, m.index - 40), m.index + 40)); }));
  new MutationObserver(look).observe(document.querySelector('[data-swarm-live]'), { subtree: true, childList: true, characterData: true }); look(); }"""
SET_RANGE = "([s, v]) => { const i = document.querySelector(s); i.value = String(v); i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true})); }"
TRACE_STATE = "(() => ((document.querySelector('[data-sw-trace-state]') || {}).textContent || '').trim())()"


async def follow_once(pg, want=None, tries=1, limit=45000):
    """press Follow and wait for the followed proposal's outcome ('Settled' / 'Rejected ...'), then 5 s for its record
    step; with want='rejected' / 'settled', follow again (up to tries) until that outcome. Returns the outcomes seen."""
    seen = []
    for _ in range(tries):
        await pg.locator("[data-swarm-live] [data-sw-follow]").click()
        out = await until(pg, f"(() => {{ const s = {TRACE_STATE}; return /^(settled|rejected)/i.test(s) ? s : ''; }})()", limit, 250)
        seen.append(out or "no outcome")
        await pg.wait_for_timeout(5000)  # the outcome's announcement and the trace's ledger step
        if not want or (out and out.lower().startswith(want)): break
        if await pg.evaluate("(document.querySelector('[data-sw-follow]') || {}).getAttribute && document.querySelector('[data-sw-follow]').getAttribute('aria-pressed') === 'true'"):
            await pg.locator("[data-swarm-live] [data-sw-follow]").click()  # stop before following the next one
    return seen


@check
async def platform_trace(b):
    """a followed proposal never says the page has no ledger while the lab draws one: on Platform (no inspectable
    ledger) the trace, its stage tag and its live region never print 'no ledger', for a settled proposal at 1440 and 390
    and a rejected one at 1440 (SW-R2-1); on home at 390 the trace still never prints 'block' (SW2)"""
    bad = []
    for path, (w, h), touch, wants in (("platform.html", (1440, 900), False, ("settled", "rejected")), ("platform.html", (390, 844), True, ("settled",)),
                                         ("index.html", (390, 844), True, ("settled",))):
        tag = f"{path}@{w}x{h}"
        ctx, pg = await open_page(b, path, w, h, touch=touch)
        await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
        if not await until(pg, "+((document.querySelector('[data-sw-inflight]') || {}).textContent || '0').replace(/\\D/g, '') > 0", 25000, 200):
            bad.append(f"{tag}: the lab never ran"); await ctx.close(); continue
        await pg.evaluate(TEXT_WATCH, r"no ledger|\bblock\b" if path == "index.html" else r"no ledger")
        await pg.mouse.move(2, 2)
        for want in wants:
            await pg.evaluate(SET_RANGE, ["[data-sw-strict]", 0 if want == "settled" else 60])
            seen = await follow_once(pg, want, tries=1 if want == "settled" else 6)
            log = re.sub(r"\s+", " ", await pg.evaluate("(document.querySelector('[data-sw-log]') || {}).textContent || ''"))
            if not seen[-1].lower().startswith(want): bad.append(f"{tag}: no {want} proposal to follow (outcomes {seen})")
            elif not re.search(r"seal|record|rejection|ledger", log, re.I): bad.append(f"{tag}: the {want} trace never reached its record step: {log[-140:]!r}")
            if await pg.evaluate("document.querySelector('[data-sw-follow]').getAttribute('aria-pressed') === 'true'"):
                await pg.locator("[data-swarm-live] [data-sw-follow]").click()
        hits = await pg.evaluate("window.__tw")
        if hits: bad.append(f"{tag}: {hits[:3]}")
        await ctx.close()
    assert not bad, "platform_trace:\n  " + "\n  ".join(bad)
    print("platform_trace: Platform's trace never says 'no ledger' (settled at 1440 and 390, rejected at 1440); home's never says 'block'")


GATE_BOXES = r"""(() => { const labs = [...document.querySelectorAll('[data-sw-gates] > li')].map(li => { const r = li.getBoundingClientRect(), cs = getComputedStyle(li);
    return { t: li.textContent.replace(/\s+/g, ' ').trim().slice(0, 24), b: [r.left, r.top, r.right, r.bottom], v: r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' }; }).filter(l => l.v);
  const ov = []; for (let i = 0; i < labs.length; i++) for (let j = i + 1; j < labs.length; j++) { const a = labs[i].b, c = labs[j].b;
    const w = Math.min(a[2], c[2]) - Math.max(a[0], c[0]), h = Math.min(a[3], c[3]) - Math.max(a[1], c[1]);
    if (w > 0.5 && h > 0.5) ov.push(`'${labs[i].t}' x '${labs[j].t}' (${w.toFixed(1)} x ${h.toFixed(1)} px)`); }
  return { n: labs.length, ov }; })()"""


@check
async def lab_gate_labels(b):
    """at 667x375, 844x390, 390x844 and 320x640 (touch), on home and Platform: no two [data-sw-gates] > li boxes of the
    swarm lab intersect (no 'SIGN02ALPREDICT'; SW-R2-2: the label mode follows the measured fit)"""
    bad, n = [], 0
    for w, h in ((667, 375), (844, 390), (390, 844), (320, 640)):
        for path in ("index.html", "platform.html"):
            ctx, pg = await open_page(b, path, w, h, touch=True)
            await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
            await pg.evaluate("document.fonts.ready.then(() => 1)")
            await until(pg, "document.querySelectorAll('[data-sw-gates] > li').length >= 6", 10000)
            await pg.wait_for_timeout(1500)
            m = await pg.evaluate(GATE_BOXES); n += 1
            if m["n"] < 6: bad.append(f"{path}@{w}x{h}: only {m['n']} visible gate labels")
            if m["ov"]: bad.append(f"{path}@{w}x{h}: {'; '.join(m['ov'][:4])}")
            await ctx.close()
    assert not bad, "lab_gate_labels:\n  " + "\n  ".join(bad)
    print(f"lab_gate_labels: {n} layouts, no two gate labels intersect")


# ---- the ledger: time only moves forward; digests add up (LG-R2-2, LG-R2-3)
LEDGER_READ = r"""(() => [...document.querySelectorAll('[data-ledger=live] .lt-rec')].map(li => { const t = s => ((li.querySelector(s) || {}).textContent || '').replace(/\s+/g, ' ').trim();
  return { id: t('.lt-id'), t: t('.lt-t'), ev: t('.lt-ev'), lc: t('.lt-lc'), sub: t('.lt-sub'), swarm: li.classList.contains('is-swarm') || /swarm|followed/i.test(t('.lt-lc')) }; }))()"""
num = lambda s: int(s.replace(",", "")) if s else 0


def digest_n(r):
    """how many proposals a swarm record carries: 'SETTLED ×1,741' (LG-R2-3), else 'P-49000 +1,740 more' / 'proposal P-1' / '12 proposals'"""
    m = re.search(r"[×xX]\s*([\d,]+)", r["ev"])  # 'SETTLED ×1,741' (or a plain 'x'); no event word contains an x
    if m: return num(m[1])
    m = re.search(r"\+([\d,]+) more", r["sub"])
    if m: return num(m[1]) + 1
    m = re.search(r"\b([\d,]+) proposals?\b", r["sub"])
    return num(m[1]) if m else 1


def stamp_ms(t):
    m = re.fullmatch(r"(\d\d):(\d\d):(\d\d)(?:\.(\d{1,3}))?", t)
    return None if not m else ((int(m[1]) * 60 + int(m[2])) * 60 + int(m[3])) * 1000 + int((m[4] or "0").ljust(3, "0"))


@check
async def ledger_time(b):
    """home's live ledger at 1440, fed by the swarm lab (strictness 40%, so settled and rejected digests interleave):
    across 40 consecutive new records the timestamps strictly increase (LG-R2-2), and the foot's swarm totals equal the
    sum of n over the swarm digests seen (LG-R2-3; 'SETTLED xN' or the round-1 '+N more' wording)"""
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    ran = await until(pg, "+((document.querySelector('[data-sw-inflight]') || {}).textContent || '0').replace(/\\D/g, '') > 0", 25000, 200)
    await pg.evaluate(SET_RANGE, ["[data-sw-strict]", 40])
    first = {r["id"] for r in await pg.evaluate(LEDGER_READ)}  # the page's own excerpt: not part of the stream
    await pg.wait_for_timeout(4000)
    await pg.evaluate("document.querySelector('[data-ledger=live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    # follows from the ledger (the lab, off screen, keeps stepping while the ledger is near): a followed proposal's
    # answer seals both waiting kinds at once, where a record stamped with its group's last announcement ran backwards
    seen, order, t0, t_follow, follows = {}, [], time.monotonic(), 0, 0
    while time.monotonic() - t0 < (180 if MODE["throttle"] > 1 else 120):
        for r in await pg.evaluate(LEDGER_READ):
            if r["id"] and r["id"] not in first and r["id"] not in seen: seen[r["id"]] = r; order.append(r["id"])
        if len(order) >= 44 and follows >= 3: break
        if time.monotonic() - t_follow > 9 and await pg.evaluate("(() => { const f = document.querySelector('[data-sw-follow]'); if (!f || f.getAttribute('aria-pressed') === 'true') return false; f.click(); return true; })()"):
            t_follow, follows = time.monotonic(), follows + 1
        await pg.wait_for_timeout(400)
    foot = re.sub(r"\s+", " ", await pg.evaluate("(document.querySelector('[data-ledger=live] .lt-foot') || {}).textContent || ''"))
    await ctx.close()
    bad = []
    if not ran: bad.append("the swarm lab never ran")
    recs = [seen[i] for i in order]
    if len(recs) < 40: bad.append(f"only {len(recs)} new records in {time.monotonic() - t0:.0f} s (40 needed)")
    back = [(a["id"], a["t"], b2["id"], b2["t"]) for a, b2 in zip(recs, recs[1:]) if (stamp_ms(b2["t"]) or 0) <= (stamp_ms(a["t"]) or 0)]
    if back: bad.append(f"{len(back)} of {len(recs) - 1} steps do not move forward in time, e.g. {back[:3]}")
    if any(stamp_ms(r["t"]) is None for r in recs): bad.append(f"unreadable timestamps: {[r['t'] for r in recs if stamp_ms(r['t']) is None][:3]}")
    dig = [r for r in seen.values() if r["swarm"]]
    s_set = sum(digest_n(r) for r in dig if re.match(r"settled", r["ev"], re.I))
    s_rej = sum(digest_n(r) for r in dig if re.match(r"rejected", r["ev"], re.I))
    fs, fr = re.search(r"([\d,]+) settled", foot), re.search(r"([\d,]+) rejected", foot)
    if not dig: bad.append("no swarm digests reached the ledger")
    elif not fs: bad.append(f"the foot names no settled total: {foot!r}")
    elif (num(fs[1]), num(fr[1]) if fr else 0) != (s_set, s_rej):
        bad.append(f"the foot says {num(fs[1])} settled / {num(fr[1]) if fr else 0} rejected; the {len(dig)} digests carry {s_set} / {s_rej}: {foot!r}")
    assert not bad, "ledger_time index.html@1440x900:\n  " + "\n  ".join(bad)
    print(f"ledger_time: {len(recs)} consecutive records ({follows} follows) move forward in time; {len(dig)} digests carry {s_set} settled + {s_rej} rejected, as the foot says")


# ---- the home page prints as text on white (OV-R2-6)
PRINT_BEATS = r"""(() => { const out = [];
  const lum = c => { const m = (c.match(/[\d.]+/g) || []).map(Number); if (m.length < 3) return null; const f = v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; };
    return { L: .2126 * f(m[0]) + .7152 * f(m[1]) + .0722 * f(m[2]), a: m.length > 3 ? m[3] : 1 }; };
  document.querySelectorAll('.story .beat').forEach((b, i) => b.querySelectorAll('.eyebrow, .hero-kicker, h1, h2, .body-lg, .hero-sub').forEach(el => {
    let o = 1, hidden = false, bg = null, img = false;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); o *= +cs.opacity; if (cs.visibility === 'hidden' || cs.display === 'none') hidden = true;
      if (!bg) { const l = lum(cs.backgroundColor); if (l && l.a > 0.05) bg = l; } if (cs.backgroundImage !== 'none' && e !== document.documentElement && e !== document.body) img = true; }
    const fg = lum(getComputedStyle(el).color), back = bg ? bg.L : 1, cr = fg ? (Math.max(fg.L, back) + .05) / (Math.min(fg.L, back) + .05) : 0;
    const r = el.getBoundingClientRect();
    out.push({ beat: i, el: el.tagName.toLowerCase() + '.' + String(el.className).split(' ')[0], t: el.textContent.trim().slice(0, 28), o: +o.toFixed(2), hidden, w: r.width,
      fg: fg ? +fg.L.toFixed(3) : null, bg: +back.toFixed(3), img, cr: +cr.toFixed(1) }); }));
  return out; })()"""


@check
async def print_home(b):
    """printing /: every overture beat's eyebrow, h1/h2 and .body-lg (S0: its lede) prints at opacity 1, visible, as dark
    text (at least 4.5:1) on white (no dark background colour or image behind it) (OV-R2-6)"""
    ctx, pg = await open_page(b, "index.html", 1280, 900)
    await pg.emulate_media(media="print"); await pg.wait_for_timeout(800)
    els = await pg.evaluate(PRINT_BEATS)
    await ctx.close()
    bad = [e for e in els if e["o"] < 0.99 or e["hidden"] or not e["w"] or e["bg"] < 0.8 or e["img"] or e["cr"] < 4.5]
    beats = {e["beat"] for e in els if e["el"].startswith(("h1", "h2"))} & {e["beat"] for e in els if re.search(r"eyebrow|kicker", e["el"])}
    assert beats == set(range(5)) and not bad, f"print_home index.html@1280 (print): beats with an eyebrow and a headline {sorted(beats)}; {len(bad)} of {len(els)} overture text elements do not print as dark text on white (opacity 1, contrast >= 4.5, no dark background or image behind), e.g. {bad[:4]}"
    print(f"print_home: {len(els)} overture text elements print at opacity 1, dark on white")


# ---- 400% zoom: 320x256 reflows (PG-R2-5b, OV-R2-5c)
@check
async def reflow_400(b):
    """at 320x256 (a 1280x1024 screen at 400%): no horizontal scroll on the seven hand-written pages
    (scrollWidth <= 320), and the overture either shows its static sequence (html.story-tiny) or, at each scene's rest,
    no visible callout crosses the copy"""
    bad = []
    for name in ("index", "platform", "lifecycles", "evidence", "trust", "company", "access"):
        ctx, pg = await open_page(b, f"{name}.html", 320, 256)
        await pg.wait_for_timeout(800)
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        if sw > 320: bad.append(f"{name}.html@320x256: scrollWidth {sw}")
        if name == "index" and not await pg.evaluate("document.documentElement.classList.contains('story-tiny')"):
            for i in range(5):
                if not await scene_rest(pg, i): bad.append(f"index.html@320x256 scene 0{i}: no story-tiny and the scene did not come to rest"); continue
                m = await pg.evaluate(PHONE_LAB)
                hits = [x for x in m["issues"] if " x beat " in x]
                if hits: bad.append(f"index.html@320x256 scene 0{i} (no story-tiny): {hits[:3]}")
        await ctx.close()
    assert not bad, "reflow_400:\n  " + "\n  ".join(bad)
    print("reflow_400: the seven pages reflow at 320x256; the overture is the static sequence or keeps its callouts off the copy")


# ---- accessible names contain the visible label (WCAG 2.5.3; SW-R2-3, LC-R2-3, NV-R2-5)
LIN_MARK = r"""(() => { const out = []; let k = 0;
  const shown = el => { if (el.closest('[hidden], [inert], [aria-hidden="true"]')) return false; const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden'; };
  // the text a sighted reader sees in an element: rendered text nodes (not display:none / visibility:hidden, not
  // visually hidden, not inside an <output>, a live value); with stop, the text before the first <output> only
  const seen = (root, stop) => { let s = ''; const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) { const p = n.parentElement; if (!p) continue;
      if (p.closest('output')) { if (stop) break; continue; }
      if (p.closest('input, select, textarea, svg, .sr-only, .visually-hidden')) continue;
      if (p.checkVisibility && !p.checkVisibility({ visibilityProperty: true })) continue;
      s += ' ' + n.textContent; }
    return s; };
  document.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=slider], [role=switch], [role=tab]').forEach(el => {
    if (!shown(el)) return;
    let vis = '';
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) {
      if (/^(button|submit|reset)$/i.test(el.type)) vis = el.value;
      else { const lab = el.labels && el.labels[0]; if (!lab) return;
        vis = seen(lab, true); } } // a label with a live value reads up to it: 'Act past <output>6</output> bps' -> 'Act past'
    else vis = seen(el, false);
    el.setAttribute('data-lin', String(k)); out.push({ k: k++, tag: el.tagName.toLowerCase(), vis: vis.replace(/\s+/g, ' ').trim().slice(0, 120),
      sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/)[0] : '') +
        [...el.attributes].filter(a => a.name.startsWith('data-') && a.name !== 'data-lin').slice(0, 1).map(a => `[${a.name}]`).join('') });
  });
  return out; })()"""
# both sides lower-cased, with digits, punctuation and spaces removed ('01Signal IntelligencePerceive' in the rendered text
# is '01 Signal Intelligence PERCEIVE' in the name)
LIN_NORM = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())


async def names_by_mark(pg, cdp):
    """the accessible name of every element marked data-lin, from Chromium's accessibility tree (CDP), by mark"""
    await cdp.send("Accessibility.enable")
    doc = await cdp.send("DOM.getDocument", {"depth": 0})
    ids = (await cdp.send("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": "[data-lin]"}))["nodeIds"]
    out = {}
    for nid in ids:
        attrs = (await cdp.send("DOM.getAttributes", {"nodeId": nid}))["attributes"]
        k = dict(zip(attrs[::2], attrs[1::2])).get("data-lin")
        ax = (await cdp.send("Accessibility.getPartialAXTree", {"nodeId": nid, "fetchRelatives": False}))["nodes"]
        node = next((x for x in ax if not x.get("ignored")), None)
        out[k] = None if node is None else (node.get("name") or {}).get("value", "")
    return out


@check
async def label_in_name(b):
    """on the seven hand-written pages at 1440, plus the lab's record button after a followed proposal settles: every
    visible control's visible text (a label with an <output> read up to its value; digits and punctuation stripped on
    both sides) is a case-insensitive substring of its accessible name (WCAG 2.5.3): the nav readout, the lab's sliders
    and record button, the desk's threshold slider among them (NV-R2-5, SW-R2-3, LC-R2-3)"""
    bad, n = [], 0
    for name in ("index", "platform", "lifecycles", "evidence", "trust", "company", "access"):
        ctx, pg = await open_page(b, f"{name}.html", 1440, 900)
        cdp = await ctx.new_cdp_session(pg)
        if name == "index":  # the record button exists once a followed proposal is answered by the ledger
            await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
            await until(pg, "+((document.querySelector('[data-sw-inflight]') || {}).textContent || '0').replace(/\\D/g, '') > 0", 25000, 200)
            await pg.evaluate(SET_RANGE, ["[data-sw-strict]", 0]); await pg.mouse.move(2, 2)
            await pg.locator("[data-swarm-live] [data-sw-follow]").click()
            if not await until(pg, "!!document.querySelector('[data-sw-log] [data-sw-rec]')", 60000, 250): bad.append("index.html: no record button in the trace after 60 s (nothing to check)")
        ctrls = await pg.evaluate(LIN_MARK)
        names = await names_by_mark(pg, cdp)
        for c in ctrls:
            vis, name_ = LIN_NORM(c["vis"]), names.get(str(c["k"]))
            if not vis or name_ is None: continue
            n += 1
            if vis not in LIN_NORM(name_): bad.append(f"{name}.html@1440 {c['sel']}: visible {c['vis']!r}, accessible name {name_!r}")
        await ctx.close()
    assert not bad, f"label_in_name: {len(bad)} of {n} controls:\n  " + "\n  ".join(bad[:24])
    print(f"label_in_name: {n} visible controls on 7 pages carry their visible text in their accessible names")


# ---- focus survives forced colours (SW-R2-3, NV-R2-4b, LC-R2-3)
FOCUS_PREP = r"""(sel) => { const el = document.querySelector(sel); if (!el) return null; el.scrollIntoView({block: 'center', behavior: 'instant'});
  const f = [...document.querySelectorAll('a[href], button:not([disabled]), input:not([type=hidden]), select, textarea, summary, [tabindex]:not([tabindex="-1"])')]
    .filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden' && !e.closest('[inert], [hidden]'));
  const i = f.indexOf(el); if (i > 0) f[i - 1].focus({preventScroll: true}); else document.activeElement && document.activeElement.blur && document.activeElement.blur();
  return i; }"""


def contrast(c1, c2):
    def L(c):
        f = lambda v: (v / 255) / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])
    a, b2 = L(c1), L(c2)
    return (max(a, b2) + 0.05) / (min(a, b2) + 0.05)


@check
async def forced_focus(b):
    """in forced colours (Windows High Contrast), a Tab onto the lab's strictness slider (home), Access's #name and the
    desk's threshold slider (Lifecycles) changes at least 100 pixels by 3:1 or more around the control (the focus ring
    in the system colours; method of r2/a11y/focus_pix.py)"""
    from PIL import Image
    import io
    bad, got = [], []
    for path, sel in (("index.html", "[data-sw-strict]"), ("access.html", "#name"), ("lifecycles.html", "[data-gap-thr]")):
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, forced_colors="active", reduced_motion="reduce")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/{path}", wait_until="load"); await until(pg, LOADED, 15000); await pg.wait_for_timeout(1200)
        await pg.mouse.move(2, 898)
        if await pg.evaluate(FOCUS_PREP, sel) is None: bad.append(f"{path}: no {sel}"); await ctx.close(); continue
        await pg.wait_for_timeout(500); await pg.keyboard.press("Tab"); await pg.wait_for_timeout(600)
        on = await pg.evaluate("(s) => document.activeElement === document.querySelector(s)", sel)
        r = await pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", sel)
        x0, y0 = max(0, r[0] - 10), max(0, r[1] - 10)
        clip = {"x": x0, "y": y0, "width": min(1440, r[0] + r[2] + 10) - x0, "height": min(900, r[1] + r[3] + 10) - y0}
        fimg = Image.open(io.BytesIO(await pg.screenshot(clip=clip, animations="disabled"))).convert("RGB")
        await pg.evaluate("document.activeElement && document.activeElement.blur()"); await pg.wait_for_timeout(600)
        uimg = Image.open(io.BytesIO(await pg.screenshot(clip=clip, animations="disabled"))).convert("RGB")
        await ctx.close()
        fb, ub = fimg.tobytes(), uimg.tobytes()
        fp, up = [tuple(fb[i:i + 3]) for i in range(0, len(fb), 3)], [tuple(ub[i:i + 3]) for i in range(0, len(ub), 3)]
        changed = [(a, c) for a, c in zip(fp, up) if max(abs(a[0] - c[0]), abs(a[1] - c[1]), abs(a[2] - c[2])) > 10]
        good = sum(1 for a, c in changed if contrast(a, c) >= 3)
        got.append(f"{path} {sel}: {good}")
        if not on: bad.append(f"{path}@1440 (forced colours): Tab did not land on {sel}")
        elif good < 100: bad.append(f"{path}@1440 (forced colours): focusing {sel} changes {len(changed)} px, {good} of them by 3:1 or more (100 needed)")
    assert not bad, "forced_focus:\n  " + "\n  ".join(bad)
    print(f"forced_focus: focus shows in forced colours ({'; '.join(got)} px at 3:1)")


# ---- no grey slab where a card grid has no card (PG-R2-2)
SLAB = (14, 21, 18, 0.14)


def slab_areas(img, bg, holes=()):
    """the pixels of a 14%-ink fill over `bg` that sit in a 3x3 block (an area, not a 1 px rule), outside the boxes in
    holes (images): (count, first (x, y), the fill's colour)"""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter
    a = SLAB[3]; want = tuple(round(c * (1 - a) + s * a) for c, s in zip(bg, SLAB[:3]))
    r_, g_, b_ = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, want)).split()
    mask = ImageChops.lighter(ImageChops.lighter(r_, g_), b_).point(lambda v: 255 if v <= 3 else 0)
    if holes:
        d = ImageDraw.Draw(mask)
        for x0, y0, x1, y1 in holes: d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], fill=0)
    core = mask.filter(ImageFilter.MinFilter(3))
    bbox = core.getbbox()
    return (core.histogram()[255], bbox[:2] if bbox else None, want)


GRID_CHUNK = r"""([sel, k, y0]) => { const g = document.querySelectorAll(sel)[k]; if (!g) return null; const r = g.getBoundingClientRect();
  const top = 80, h = Math.min(r.height - y0, innerHeight - top); if (h < 4) return null;
  window.scrollTo({top: r.top + scrollY + y0 - top, behavior: 'instant'}); const q = g.getBoundingClientRect();
  const clip = { x: Math.max(0, q.left), y: top, width: Math.min(q.width, innerWidth - Math.max(0, q.left)), height: h };
  const holes = [...g.querySelectorAll('img, picture, video, canvas, svg')].map(e => e.getBoundingClientRect()).filter(b => b.width && b.height)
    .map(b => [b.left - clip.x, b.top - clip.y, b.right - clip.x, b.bottom - clip.y]);
  return { clip, holes, more: y0 + h < r.height - 1 }; }"""


async def grid_slabs(pg, sel, where, hold=False):
    """the slab areas in every grid matching sel, chunk by chunk under the bar; with hold, animations are frozen at
    their start (CDP Animation.setPlaybackRate 0) before the grid scrolls in, so the shot is t=0 of its reveal"""
    from PIL import Image
    import io
    out, n = [], await pg.evaluate("(s) => document.querySelectorAll(s).length", sel)
    for k in range(n):
        y0 = 0
        while True:
            c = await pg.evaluate(GRID_CHUNK, [sel, k, y0])
            if not c: break
            await pg.wait_for_timeout(700 if hold else 300)
            img = Image.open(io.BytesIO(await pg.screenshot(clip=c["clip"], animations="allow"))).convert("RGB")
            for bg in ((245, 242, 236), (236, 232, 223)):
                cnt, at, want = slab_areas(img, bg, c["holes"])
                if cnt: out.append(f"{where} grid {k + 1} ({sel}): {cnt} px of {want} (14% ink over {bg}) in areas wider than a rule, first at ({c['clip']['x'] + at[0]:.0f}, {c['clip']['y'] + at[1]:.0f}) in the viewport")
            if not c["more"]: break
            y0 += c["clip"]["height"]
    return out, n


@check
async def grid_slab(b):
    """no grey slab: on /blog/ at 1440 (incomplete last rows) and on Trust §02 at t=0 of its reveal (animations held at
    their start), no area of rgba(14,21,18,.14) over the paper wider than a rule (a 3x3 block; images excluded) shows in
    a card grid (PG-R2-2: the rules are drawn on the cells, not as the container's background between them)"""
    bad = []
    ctx, pg = await open_page(b, "blog/index.html", 1440, 900, reduced=True)
    out, n = await grid_slabs(pg, ".blog-grid", "blog/index.html@1440")
    bad += out
    if not n: bad.append("blog/index.html: no .blog-grid")
    await ctx.close()
    ctx, pg = await open_page(b, "trust.html", 1440, 900)
    cdp = await ctx.new_cdp_session(pg)
    await cdp.send("Animation.enable"); await cdp.send("Animation.setPlaybackRate", {"playbackRate": 0})
    await pg.evaluate("(() => { const s = [...document.querySelectorAll('.sec-head .idx')].find(e => e.textContent.trim() === '02'); const g = s && s.closest('section').querySelector('.card-grid'); if (g) g.setAttribute('data-oxa-grid', ''); })()")
    out, n = await grid_slabs(pg, "[data-oxa-grid]", "trust.html@1440 §02 at t=0 of its reveal", hold=True)
    await cdp.send("Animation.setPlaybackRate", {"playbackRate": 1})
    bad += out
    if not n: bad.append("trust.html: no .card-grid in §02")
    await ctx.close()
    assert not bad, "grid_slab:\n  " + "\n  ".join(bad[:10])
    print("grid_slab: no grey slab in the blog's grids or in Trust §02 before its cards arrive")


# ---- the overture without its context (OV-R2-3a)
LOSE = r"""(restore) => { const c = document.querySelector('canvas.story-gl'); if (!c) return 'no canvas.story-gl';
  const gl = c.getContext('webgl2') || c.getContext('webgl'); const x = gl && gl.getExtension('WEBGL_lose_context'); if (!x) return 'no WEBGL_lose_context';
  const R = window.__lost = { ev: 0, cls: 0, restored: 0 }; const root = document.documentElement;
  c.addEventListener('webglcontextlost', () => { R.ev = performance.now(); }, { once: true });
  new MutationObserver(() => { if (!R.cls && root.classList.contains('no-webgl')) R.cls = performance.now(); }).observe(root, { attributes: true, attributeFilter: ['class'] });
  x.loseContext(); if (restore) setTimeout(() => { R.restored = performance.now(); x.restoreContext(); }, 600); return ''; }"""
BEAT_READ = r"""(i) => { const b = document.querySelector('.beat-' + i); if (!b) return null; const eff = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
  return [...b.querySelectorAll('.eyebrow, .hero-kicker, h1, h2, .body-lg')].map(e => { const r = e.getBoundingClientRect(); return { t: e.textContent.trim().slice(0, 24), o: +eff(e).toFixed(2), in: r.width > 0 && r.bottom > 0 && r.top < innerHeight }; }); }"""


@check
async def overture_ctx_lost(b):
    """the overture's WebGL context lost and never restored: html.no-webgl within 3 s of the loss (page time) and beat 2
    readable at S2 (its eyebrow, h2 and paragraph at opacity >= .9, on screen); lost and restored after 0.6 s: no
    fallback, and every scene comes to rest as before (OV-R2-3a)"""
    bad = []
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await pg.wait_for_timeout(1500)
    err = await pg.evaluate(LOSE, False)
    if err: bad.append(f"lost: {err}")
    else:
        await until(pg, "document.documentElement.classList.contains('no-webgl')", 10000, 100)
        L = await pg.evaluate("window.__lost")
        if not L["cls"]: bad.append(f"lost, not restored: no html.no-webgl {(await pg.evaluate('performance.now()') - L['ev']) / 1000:.1f} s after the loss (the stage freezes on S0)")
        elif L["cls"] - L["ev"] > 3000: bad.append(f"lost, not restored: html.no-webgl came {L['cls'] - L['ev']:.0f} ms after the loss (3000 allowed)")
        else:
            idx = await pg.locator('.story-idx [data-n="02"]').count() and await pg.locator('.story-idx [data-n="02"]').is_visible()
            if idx: await pg.evaluate("document.querySelector('.story-idx [data-n=\"02\"]').click()")
            else: await pg.evaluate("document.querySelector('.beat-2').scrollIntoView({block: 'center', behavior: 'instant'})")
            await pg.wait_for_timeout(2000)
            r = await pg.evaluate(BEAT_READ, 2)
            if not r or any(x["o"] < 0.9 or not x["in"] for x in r): bad.append(f"lost, not restored: beat 2 at S2 reads {r}")
    await ctx.close()
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await pg.wait_for_timeout(1500)
    err = await pg.evaluate(LOSE, True)
    if err: bad.append(f"restored: {err}")
    else:
        await pg.wait_for_timeout(4000)
        if await pg.evaluate("document.documentElement.classList.contains('no-webgl')"): bad.append("lost and restored after 0.6 s: the page fell back to no-WebGL anyway")
        for i in range(5):
            if not await scene_rest(pg, i): bad.append(f"lost and restored: scene 0{i} did not come to rest")
    await ctx.close()
    assert not bad, "overture_ctx_lost index.html@1440x900:\n  " + "\n  ".join(bad)
    print("overture_ctx_lost: a lost context falls back within 3 s with beat 2 readable; a restored one recovers every scene")


# ---- the overture comes to rest on one complete headline wherever the reader stops (OV-R2-2)
TOTAL_U = 4.6  # story.js: four scenes plus the 0.6 exit, spread over the story's scroll run
STORY_Y = """(s) => { const st = document.querySelector('.story'), stage = st.querySelector('.story-stage') || st.firstElementChild;
  return Math.round(st.getBoundingClientRect().top + scrollY + Math.max(1, st.offsetHeight - (stage ? stage.offsetHeight : innerHeight)) * s / %s); }""" % TOTAL_U
REST_STATE = "(() => { " + EFF + r""" const st = document.querySelector('.story');
  return [...st.querySelectorAll('.beat')].map((b, i) => { const ws = [...b.querySelectorAll('h1 .wi, h2 .wi')];
    const up = ws.filter(w => { const t = getComputedStyle(w).transform; const ty = !t || t === 'none' ? 0 : new DOMMatrixReadOnly(t).m42; return ty <= 0.06 * (w.offsetHeight || 1); }).length;
    const body = b.querySelector('.body-lg, .hero-sub'), eye = b.querySelector('.eyebrow, .hero-kicker'); // S0's paragraph is its lede (.hero-sub)
    return { i, n: ws.length, up, body: body ? +eff(body, st).toFixed(2) : null, eye: eye ? +eff(eye, st).toFixed(2) : 0 }; }); })()"""
NUM_REC = "(() => { " + EFF + r""" const n = document.querySelector('.story-num'), st = document.querySelector('.story'); const R = window.__nr = { bad: [], n: 0, on: true };
  const f = () => { R.n++; if (n) { const o = eff(n, st), t = ((n.querySelector('b') || n).textContent || '').trim(); if (o > 0.02 && /^0?0\b|^00/.test(t) && R.bad.length < 8) R.bad.push({ y: Math.round(scrollY), t: n.textContent.replace(/\s+/g, ' ').trim().slice(0, 30), o: +o.toFixed(2) }); }
    if (R.on) requestAnimationFrame(f); }; requestAnimationFrame(f); })()"""


async def touch_scroll(cdp, x, y, dy):
    """a finger drag that rests before lifting (no fling); positive dy scrolls the page down (r2/motion/stopmid.py)"""
    left = dy
    while abs(left) > 4:
        d = max(-380, min(380, left))
        y0 = max(90, min(y + (abs(d) / 2 + 10 if d > 0 else -(abs(d) / 2 + 10)), 2 * y - 90))
        await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]}), "touchStart")
        n = max(2, int(abs(d) / 20))
        for k in range(1, n + 1):
            await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y0 - (d + (16 if d > 0 else -16)) * k / n}]}), "touchMove")
            await asyncio.sleep(0.016)
        await asyncio.sleep(0.15)
        await bounded(cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}), "touchEnd")
        await asyncio.sleep(0.05)
        left -= d


async def scroll_stopped(pg, limit=8000):
    """until scrollY has not changed across three reads 120 ms apart"""
    last, same, t0 = None, 0, time.monotonic()
    while time.monotonic() - t0 < limit / 1000:
        v = await pg.evaluate("scrollY")
        same = same + 1 if v == last else 0
        if same >= 2: return v
        last = v; await pg.wait_for_timeout(120)
    return last


async def stop_at(pg, cdp, y, touch, w, h):
    """move the page to y the way a reader does (wheel ticks, or a touch drag without fling) and stop"""
    cur = await pg.evaluate("scrollY")
    if touch:
        await touch_scroll(cdp, w * 0.5, h * 0.55, y - cur)
        cur = await scroll_stopped(pg)
        if abs(y - cur) > 12: await touch_scroll(cdp, w * 0.5, h * 0.55, y - cur)
    else:
        await pg.mouse.move(w * 0.72, h * 0.55)
        step = 100 if y > cur else -100
        for _ in range(int(abs(y - cur) // 100)): await pg.mouse.wheel(0, step); await pg.wait_for_timeout(40)
        rest = (y - cur) - int(abs(y - cur) // 100) * step
        if abs(rest) >= 1: await pg.mouse.wheel(0, rest)
    return await scroll_stopped(pg)


@check
async def overture_rest(b):
    """where the reader stops, the copy settles: at 1440 (wheel) and 390x844 (touch), stopping at 25, 50 and 75% of each
    of the four hand-overs, the frame 1 s later (or later, once the copy has stopped changing) shows exactly one beat with
    every headline word risen (translateY <= 6%) and its .body-lg (S0: its lede) at >= .9, and no other beat's eyebrow
    above .1; from S0 to S1 .story-num never shows '00' (every frame) (OV-R2-2)"""
    bad, n = [], 0
    for w, h, touch in ((1440, 900, False), (390, 844, True)):
        tag = f"index.html@{w}x{h}" + (" touch" if touch else " wheel")
        ctx, pg = await open_page(b, "index.html", w, h, touch=touch)
        cdp = await ctx.new_cdp_session(pg)
        await scene_rest(pg, 0)
        await pg.evaluate(NUM_REC)
        await stop_at(pg, cdp, await pg.evaluate(STORY_Y, 1.0), touch, w, h)
        await pg.wait_for_timeout(1200)
        await pg.evaluate("window.__nr.on = false"); nr = await pg.evaluate("window.__nr")
        if nr["bad"]: bad.append(f"{tag} S0 -> S1: .story-num shows '00' in {len(nr['bad'])}+ of {nr['n']} frames, e.g. {nr['bad'][:2]}")
        # the reader moves on from each stop to the next (forward through the four hand-overs, 25/50/75% of each relay
        # window [i+.32, i+.68]); each stop is judged where it settles
        await pg.evaluate(FRAME_COUNTER)
        for i in range(4):
            for f in (0.25, 0.5, 0.75):
                s = i + 0.32 + 0.36 * f
                y = await stop_at(pg, cdp, await pg.evaluate(STORY_Y, s), touch, w, h)
                await pg.wait_for_timeout(1000)
                # then the copy as it stays: two equal reads with at least two frames between them (up to 8 s; 16 s
                # throttled). Not .story[data-settled]: story.js sets it only at a scene's rest, never mid-hand-over
                # (86db818), so waiting for it cost 20 s a stop and timed the check out at 1200 s
                st, last, t_w = None, None, time.monotonic()
                while time.monotonic() - t_w < (16 if MODE["throttle"] > 1 else 8):
                    st, fr = await pg.evaluate(f"[{REST_STATE}, window.__oxaF]")
                    if last and st == last[0] and fr - last[1] >= 2: break
                    if not last or st != last[0]: last = (st, fr)
                    await pg.wait_for_timeout(150)
                n += 1
                whole = [x["i"] for x in st if x["n"] and x["up"] == x["n"] and (x["body"] or 0) >= 0.9]
                eyes = [(x["i"], x["eye"]) for x in st if x["i"] not in whole and x["eye"] > 0.1]
                if len(whole) != 1 or eyes:
                    bad.append(f"{tag} S{i}->S{i + 1} stop at {int(f * 100)}% (s={s:.2f}, y={y}): complete beats {whole}, other eyebrows {eyes}; "
                               f"beats [words up/n, body, eyebrow] {[(x['up'], x['n'], x['body'], x['eye']) for x in st]}")
        await ctx.close()
    assert not bad, f"overture_rest: {len(bad)} problems ({n} stops):\n  " + "\n  ".join(bad[:16])
    print(f"overture_rest: {n} stops mid-hand-over at 1440 (wheel) and 390 (touch) each settle on one complete headline; no '00'")


# ---- the desk on a phone: the walk happens in view; a restart keeps its morning; the strip counts every fill (LC-R2-2, LC-R2-6)
DESK = r"""(() => { const q = s => document.querySelector(s), t = s => ((q(s) || {}).textContent || '').replace(/\s+/g, ' ').trim(), num = s => +(t(s).replace(/[^\d]/g, '') || 0);
  const more = q('[data-gap-log] .dk-more'), N = more ? +(((more.textContent.match(/([\d,]+)/) || [0, '0'])[1]).replace(/,/g, '')) : 0;
  const lane = q('[data-gap-lane]'), r = lane ? lane.getBoundingClientRect() : null;
  return { time: t('[data-gap-time]'), state: t('[data-gap-state]'), recs: [...document.querySelectorAll('[data-gap-log] > li')].filter(li => !li.classList.contains('dk-more')).length, more: N,
    creates: num('[data-gap-creates]'), redeems: num('[data-gap-redeems]'), on: lane ? lane.dataset.on || '' : null, lane: r ? [Math.round(r.top), Math.round(r.bottom)] : null, vh: innerHeight }; })()"""
mins = lambda t: (lambda m: int(m[1]) * 60 + int(m[2]) if m else None)(re.search(r"(\d\d):(\d\d)", t or ""))


@check
async def desk_phone_follow(b):
    """the desk at 390x844 with touch, agents at the maximum and the threshold at its minimum: while 'Follow the next
    action' walks its gates, [data-gap-lane] stays inside the viewport once its scroll-in (during gate 01) has landed
    (LC-R2-2); the strip's records plus its '+N
    earlier records' equal Creates + Redeems (read while paused, and at 'Session complete'; LC-R2-6a); Follow pressed
    during 'Session complete' restarts the session at 11:00 ET or later with at least 3 records (LC-R2-6b)"""
    bad = []
    ctx, pg = await open_page(b, "lifecycles.html", 390, 844, touch=True)
    await pg.evaluate("document.querySelector('[data-gap]').scrollIntoView({block: 'start', behavior: 'instant'})")
    await pg.wait_for_timeout(800)
    await pg.evaluate("(() => { const n = document.querySelector('[data-gap-n]'), t = document.querySelector('[data-gap-thr]'); for (const [i, v] of [[n, n.max], [t, t.min]]) { i.value = v; i.dispatchEvent(new Event('input', {bubbles: true})); i.dispatchEvent(new Event('change', {bubbles: true})); } })()")
    await pg.wait_for_timeout(1500)
    # (a) the walk, in view
    await pg.evaluate("document.querySelector('[data-gap-follow]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(400)
    await bounded(pg.locator("[data-gap-follow]").tap(), "a tap on Follow the next action", 60)
    walk, t0 = [], time.monotonic()
    while time.monotonic() - t0 < 40:
        d = await pg.evaluate(DESK)
        if d["on"]: walk.append(d)
        if walk and d["state"] != "Following an action": break
        await pg.wait_for_timeout(150)
    if len(walk) < 3: bad.append(f"lifecycles.html@390x844: the follow walk was not seen ({len(walk)} samples with a lit gate in 40 s; state {d['state']!r})")
    # LC-R2-2 brings the lane in with a smooth scrollIntoView as the follow starts, during the walk's first gate (one
    # second): from gate 02 on, and at the last sample of gate 01, the lane is inside the viewport
    outside = lambda x: not x["lane"] or x["lane"][0] < 0 or x["lane"][1] > x["vh"]
    last1 = max((k for k, x in enumerate(walk) if x["on"] == "1"), default=None)
    out = [(x["on"], x["lane"]) for k, x in enumerate(walk) if outside(x) and (x["on"] != "1" or k == last1)]
    if out: bad.append(f"lifecycles.html@390x844: the lane is outside the viewport during the walk in {len(out)} of {len(walk)} samples (after its scroll-in), e.g. (gate, [top, bottom]) {out[:3]} (viewport 0-844)")
    # (c) the strip accounts for every fill: read while paused (the counters and the strip from the same instant)
    async def strip_vs_counts(when):
        await pg.evaluate("document.querySelector('[data-gap-motion]').click()"); await pg.wait_for_timeout(400)
        d = await pg.evaluate(DESK)
        await pg.evaluate("document.querySelector('[data-gap-motion]').click()")
        if d["recs"] + d["more"] != d["creates"] + d["redeems"]:
            bad.append(f"lifecycles.html@390x844 {when}: the strip holds {d['recs']} records + '+{d['more']}' while Creates + Redeems read {d['creates']} + {d['redeems']} ({d['time']})")
        return d
    await strip_vs_counts("after the walk")
    # to the end of the session
    done = await until(pg, "(document.querySelector('[data-gap-state]') || {}).textContent === 'Session complete'", 240000 if MODE["throttle"] > 1 else 150000, 150)
    if not done: bad.append(f"lifecycles.html@390x844: no 'Session complete' ({(await pg.evaluate(DESK))['time']})")
    else:
        d = await pg.evaluate(DESK)
        if d["recs"] + d["more"] != d["creates"] + d["redeems"]:
            bad.append(f"lifecycles.html@390x844 at 'Session complete': the strip holds {d['recs']} records + '+{d['more']}' while Creates + Redeems read {d['creates']} + {d['redeems']}")
        # (b) Follow during 'Session complete': the restarted session opens warm
        await pg.evaluate("document.querySelector('[data-gap-follow]').click()")
        first, t0 = None, time.monotonic()
        while time.monotonic() - t0 < 20:
            d = await pg.evaluate(DESK)
            if d["time"] and mins(d["time"]) is not None and mins(d["time"]) < 16 * 60: first = d; break
            await pg.wait_for_timeout(100)
        if not first: bad.append("lifecycles.html@390x844: Follow during 'Session complete' did not restart the session in 20 s")
        elif mins(first["time"]) < 11 * 60 or first["recs"] < 3:
            bad.append(f"lifecycles.html@390x844: Follow during 'Session complete' restarted the session at {first['time']} with {first['recs']} record(s) (>= 11:00 ET and >= 3 expected)")
    await ctx.close()
    assert not bad, "desk_phone_follow:\n  " + "\n  ".join(bad)
    print("desk_phone_follow: the walk stays in view at 390, the strip accounts for every fill, a restart opens warm")


# ---- long jumps on a phone: never a blank frame, an ink band or two readouts (NV-R2-2)
VT_REC = r"""(() => { const R = window.__vt = { f: [], on: true }; const root = document.documentElement;
  const pe = (n) => { try { const cs = getComputedStyle(root, n); return cs.display === 'none' ? 0 : +cs.opacity; } catch (e) { return -1; } };
  const f = () => { const anims = document.getAnimations().filter(a => a.effect && a.effect.pseudoElement && a.effect.pseudoElement.startsWith('::view-transition'));
    const names = [...new Set(anims.map(a => a.effect.pseudoElement))];
    const vt = anims.length > 0, nav = names.some(n => /site-nav/.test(n));
    R.f.push({ t: performance.timeOrigin + performance.now(), vt, old: vt && names.includes('::view-transition-old(site-nav)') ? pe('::view-transition-old(site-nav)') : (vt && nav ? pe('::view-transition-old(site-nav)') : 0),
      neu: vt && nav ? pe('::view-transition-new(site-nav)') : 1, jump: root.dataset.jump || '' });
    if (R.on && R.f.length < 900) requestAnimationFrame(f); }; requestAnimationFrame(f); })()"""


def frame_issues(png, bar_h):
    """for one screencast frame: (the lit share below the bar, the band: [first row, rows] of a run of at least 4
    full-width rows of the ink root #0B110F (+-2) below the bar in a frame that also shows a paper view, else None).
    The band sits between the bar and the paper on a jump up, and between the paper and the incoming sheet on a jump
    down (1a6b9fb: rows 724-844 at 390 for 280 ms on 01 -> 06), so both places count."""
    from PIL import Image, ImageChops
    import io
    im = Image.open(io.BytesIO(png)).convert("RGB")
    W, H = im.size
    below = im.crop((0, bar_h, W, H))
    luma = below.convert("L")
    lit = luma.point(lambda v: 255 if v > 64 else 0).histogram()[255] / max(1, below.size[0] * below.size[1])
    r_, g_, b_ = ImageChops.difference(below, Image.new("RGB", below.size, (11, 17, 15))).split()
    ink = ImageChops.lighter(ImageChops.lighter(r_, g_), b_).point(lambda v: 255 if v <= 2 else 0)
    ink_rows = [v >= 0.98 * 255 for v in ink.resize((1, below.size[1]), Image.BOX).tobytes()]
    paper = any(v >= 0.9 * 255 for v in luma.point(lambda v: 255 if v > 200 else 0).resize((1, below.size[1]), Image.BOX).tobytes())
    band, run = None, 0
    for y, full in enumerate(ink_rows + [False]):
        if full: run += 1; continue
        if run >= 4 and paper and band is None: band = [bar_h + y - run, run]
        run = 0
    return lit, band


@check
async def jump_touch(b):
    """at 390x844 with touch, every screencast frame of Back to top (from the footer) and of a chapter jump from 01 to 06
    on home: at least 2% lit pixels below the bar (no blank frame), no band (4+ full-width rows) of the ink root #0B110F
    beside a paper view (between the bar and the paper, or between the paper and the incoming sheet), and one chapter
    readout (never the old and the new bar both drawn) (NV-R2-2)"""
    bad, summary = [], []
    for case in ("top", "06"):
        ctx, pg = await open_page(b, "index.html", 390, 844, touch=True)
        cdp = await ctx.new_cdp_session(pg)
        if case == "top": await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
        else: await pg.evaluate("(() => { const a = document.querySelectorAll('.nav-ch-list a')[0]; const el = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))); window.scrollTo({top: el.getBoundingClientRect().top + scrollY, behavior: 'instant'}); })()")
        await pg.wait_for_timeout(1800)
        await bounded(pg.locator(".nav-ch-btn").tap(), "a tap on the chapter readout", 60); await pg.wait_for_timeout(700)
        bar_h = int(await pg.evaluate("Math.ceil((document.querySelector('header.nav') || document.querySelector('.nav')).getBoundingClientRect().bottom)"))
        frames = []
        def on(ev):
            frames.append((ev["metadata"].get("timestamp", 0) * 1000.0, ev["data"]))
            asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))
        cdp.on("Page.screencastFrame", on)
        await cdp.send("Page.startScreencast", {"format": "png", "maxWidth": 390, "maxHeight": 844, "everyNthFrame": 1})
        await pg.evaluate(VT_REC); await pg.wait_for_timeout(300)
        t_click = await pg.evaluate("performance.timeOrigin + performance.now()")
        target = ".nav-ch-top" if case == "top" else ".nav-ch-list a[href='#governance']"
        if not await pg.locator(target).count(): bad.append(f"index.html@390x844 {case}: no {target}"); await ctx.close(); continue
        await bounded(pg.locator(target).first.tap(), f"a tap on {target}", 60)
        await pg.wait_for_timeout(2500 if MODE["throttle"] <= 1 else 6000)
        await cdp.send("Page.stopScreencast")
        await pg.evaluate("window.__vt.on = false"); vt = (await pg.evaluate("window.__vt"))["f"]
        landed = await pg.evaluate("scrollY")
        await ctx.close()
        import base64
        shots = [(t, base64.b64decode(d)) for t, d in frames if t >= t_click - 50]
        name = "Back to top" if case == "top" else "chapter 01 -> 06"
        if len(shots) < 3: bad.append(f"index.html@390x844 {name}: only {len(shots)} screencast frames after the tap")
        dark, bands = [], []
        for t, png in shots:
            lit, band = frame_issues(png, bar_h)
            if lit < 0.02: dark.append((int(t - t_click), f"{lit * 100:.1f}%"))
            if band: bands.append((int(t - t_click), band))
        two = [(int(x["t"] - t_click), x["old"], x["neu"]) for x in vt if x["vt"] and x["old"] > 0.05 and x["neu"] > 0.05]
        if dark: bad.append(f"index.html@390x844 {name}: {len(dark)} of {len(shots)} frames have under 2% lit pixels below the bar, e.g. (ms, lit) {dark[:4]}")
        if bands: bad.append(f"index.html@390x844 {name}: {len(bands)} frames show a band of the ink root #0B110F beside a paper view, e.g. (ms, [first row, rows]) {bands[:4]}")
        if two: bad.append(f"index.html@390x844 {name}: the old and the new bar are both drawn in {len(two)} frames (two readouts), e.g. (ms, old opacity, new opacity) {two[:4]}")
        summary.append(f"{name}: {len(shots)} frames, landed at {landed}")
    assert not bad, "jump_touch:\n  " + "\n  ".join(bad)
    print(f"jump_touch: {'; '.join(summary)}; every frame lit, no ink band, one readout")


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


def parse_modes(argv):
    """the run modes (into MODE): --swiftshader | --gpu, --cpu-throttle N, --cores N, --check-timeout S; returns the
    --shards workflow path, if any"""
    shards = None
    for i, a in enumerate(argv):
        nxt = argv[i + 1] if i + 1 < len(argv) else ""
        val = lambda name: a.split("=", 1)[1] if a.startswith(name + "=") else nxt if a == name else None
        if a == "--gpu": MODE["gl"] = "gpu"
        elif a == "--swiftshader": MODE["gl"] = "swiftshader"
        elif val("--cpu-throttle") is not None: MODE["throttle"] = max(1.0, float(val("--cpu-throttle")))
        elif val("--cores") is not None: MODE["cores"] = int(val("--cores"))
        elif val("--check-timeout") is not None: MODE["check_timeout"] = float(val("--check-timeout"))
        elif val("--shards") is not None: shards = val("--shards")
    return shards


def check_shards(path):
    """every check sits in exactly one shard of the workflow's browser matrix ('- shard: NAME' followed by 'only: a,b,c');
    prints the shards; exit status 1 if a check is in no shard or in two, or a shard names an unknown check"""
    shards, cur = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*-\s*shard:\s*([\w-]+)\s*$", line)
        if m: cur = m[1]; continue
        m = re.match(r"\s*only:\s*([\w,\s]+?)\s*$", line)
        if m and cur: shards[cur] = [n.strip() for n in m[1].split(",") if n.strip()]; cur = None
    names = [c.__name__ for c in CHECKS]
    seen = [(n, s) for s, lst in shards.items() for n in lst]
    problems = [f"'{n}' is in no shard" for n in names if not any(x == n for x, _ in seen)]
    problems += [f"'{n}' is listed {k} times: {[s for x, s in seen if x == n]}" for n in names for k in [sum(1 for x, _ in seen if x == n)] if k > 1]
    problems += [f"shard '{s}' names an unknown check '{n}'" for n, s in seen if n not in names]
    for s, lst in shards.items(): print(f"shard {s:14} {len(lst):2} checks: {', '.join(lst)}")
    if not shards: problems.append(f"no '- shard:' / 'only:' matrix entries found in {path}")
    for p in problems: print("SHARDS:", p)
    print(f"shards: {len(names)} checks in {len(shards)} shards - {'OK' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


async def main():
    global BASE
    base, only, listing = parse_args(sys.argv[1:])
    shards = parse_modes(sys.argv[1:])
    if base: BASE = base
    names = [c.__name__ for c in CHECKS]
    if shards: return check_shards(shards)
    if listing:
        for c in CHECKS: print(f"{c.__name__:24} {(c.__doc__ or '').strip().splitlines()[0]}")
        return 0
    unknown = [n for n in (only or []) if n not in names]
    if unknown: print("unknown check(s):", unknown, "- known:", ", ".join(names)); return 2
    todo = [c for c in CHECKS if only is None or c.__name__ in only]
    if MODE["cores"]: MODE["cores"] = pin_cores(MODE["cores"]) or f"(pinning to {MODE['cores']} failed)"
    failed, t_run = [], time.monotonic()
    async with async_playwright() as p:
        raw = await p.chromium.launch(args=launch_args())
        print(f"verify_v9 against {BASE}: {len(todo)} check(s) · {mode_line()} · Chromium {raw.version}", flush=True)
        b = TrackedBrowser(raw)
        for c in todo:
            t0, hung = time.monotonic(), False
            try:
                await run_one(c, b)
                print(f"PASS {c.__name__} ({time.monotonic() - t0:.0f}s)", flush=True)
            except Exception as e:
                hung = isinstance(e, CheckTimeout)
                msg = str(e) if isinstance(e, (AssertionError, CheckTimeout)) and str(e) else "".join(traceback.format_exception_only(type(e), e)).strip()
                failed.append(c.__name__)
                print(f"FAIL {c.__name__} ({time.monotonic() - t0:.0f}s): {msg}", flush=True)
                if not isinstance(e, (AssertionError, CheckTimeout)): traceback.print_exc(limit=3)
            if not await close_leftovers(drop_shared=hung):
                print(f"(a context of {c.__name__} would not close: restarting the browser)", flush=True)
                try: await asyncio.wait_for(raw.close(), 30)
                except Exception: pass
                SHARED.clear(); OPEN.clear(); CDP_KEEP.clear()
                raw = await p.chromium.launch(args=launch_args()); b = TrackedBrowser(raw)
        for ctx, pg in SHARED.values():
            try: await asyncio.wait_for(ctx.close(), 25)
            except Exception: pass
        try: await asyncio.wait_for(raw.close(), 30)
        except Exception: pass
    took = f"{time.monotonic() - t_run:.0f} s"
    if failed:
        print(f"V9 CHECKS FAILED: {len(failed)} of {len(todo)} in {took}: {', '.join(failed)}")
        return 1
    print(f"V9 CHECKS PASSED: {len(todo)} in {took}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
