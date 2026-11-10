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
--swiftshader (the default; CI's renderer) launches Chromium with WebGL on ANGLE's SwiftShader and 2D canvases on the CPU
(as on a device without a GPU); --gpu uses the real GPU instead (local only, to compare). Calibrated against CI run
40862747954 (2173b49): with the browser pinned to 4 CPUs (--cores 4) this PC reproduced its swarm failures (2 frames a
second with SwiftShader also drawing 2D canvases; Halt's drain and the record button's trip ran out of time). --cpu-throttle N slows every page's main thread N times (CDP Emulation.setCPUThrottlingRate, applied
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
import asyncio, json, linecache, os, platform, re, subprocess, sys, time, traceback, urllib.parse
from pathlib import Path
from playwright.async_api import async_playwright, expect
# CI's runner is several times slower than a laptop: an expect() without its own timeout waits up to 20 s (Playwright's
# default is 5 s; under 6x throttling on two cores the chain's SHA-256 recheck of 'REJECTED' took longer). The same
# condition is asserted; only the patience changes. An expect() that names its own timeout (a deliberate 'at once') keeps it.
expect.set_options(timeout=20000)

BASE = "http://127.0.0.1:8125"  # the URL argument replaces it
# CI's renderer: WebGL on ANGLE's SwiftShader, 2D canvases rasterized on the CPU, as Chrome does on a device without a GPU.
# Round 2: with SwiftShader also drawing the 2D canvases (an arrangement no visitor's browser uses), the homepage's swarm
# lab took 0.5 s or more a frame on CI's 4 vCPUs, and Halt's drain and the record button's trip ran out of time there.
SWIFTSHADER_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-accelerated-2d-canvas"]
GPU_ARGS = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]  # the real GPU (Windows; local comparison only)
MODE = {"gl": "swiftshader", "throttle": 1.0, "cores": None, "check_timeout": 600.0}
LIMITS = {"overture_phones": 1200, "overture_rest": 1200, "page_type_sizes": 1200}  # checks that run long on CI by design (s); the rest use the default
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
  return { scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth, innerWidth, overflow: over.slice(0, 6), text: document.body.innerText };
}"""

# ---------------------------------------------------------------- shared helpers for the checks
LOADED = "(() => { const l = document.querySelector('.loader'); return !l || document.documentElement.classList.contains('is-loaded'); })()"
# v2x r2 (home, two-phase start): home.js adds loader, story and site at the first paint and the six instruments (swarm,
# ledger, chain, arch, lane, proof) on 'oxa:loaded', so 'is-loaded' comes before they have run. A check that acts on an
# instrument right after load waits for them: every script home.js lists has run (its load event, or failed). The live
# ledger mounts only when it comes within 1.5 screens (ledger.js), so a check that uses it waits for its .lt-ready there.
SCRIPTS_RAN = """(() => { const R = window.__oxaRan = window.__oxaRan || [];
  const on = e => { const t = e.target; if (t && t.tagName === 'SCRIPT' && t.getAttribute('src')) R.push(t.getAttribute('src')); };
  document.addEventListener('load', on, true); document.addEventListener('error', on, true); })();"""
HOME_ENGINES = """(() => { const tag = document.querySelector('script[data-after-paint]'); if (!tag) return true;
  const want = tag.getAttribute('data-after-paint').split(/\\s+/).filter(Boolean), ran = window.__oxaRan || [];
  return want.every(s => ran.includes(s)); })()"""
NUMW ="zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
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
    gl = "real GPU (" + " ".join(GPU_ARGS) + ")" if MODE["gl"] == "gpu" else "SwiftShader (ANGLE; CI's software GL; 2D canvas on the CPU)"
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
    """a fresh context at w x h, the page loaded: until the loader has finished and, on any page whose HTML starts its
    scripts after the first paint (`script[data-after-paint]`: Home's six instruments, Lifecycles' gap.js and site.js),
    until every script that tag lists has run (HOME_ENGINES; true at once on a page without the tag). v2x r3: was Home
    only; Lifecycles moved its scripts after the paint (system r3, r3-perf), so a check acting on the desk right after
    'load' must not run before gap.js."""
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, has_touch=touch, is_mobile=touch,
                              reduced_motion="reduce" if reduced else "no-preference", java_script_enabled=js)
    if js: await ctx.add_init_script(SCRIPTS_RAN)  # cheap; records every <script src> that loads or fails, on any page
    if init: await ctx.add_init_script(init)
    pg = await ctx.new_page()
    if errs is not None: pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
    await pg.goto(f"{BASE}/{path}", wait_until="load")
    if js and loaded: await until(pg, LOADED, 15000)
    if js and loaded: await until(pg, HOME_ENGINES, int(15000 * max(1.0, MODE["throttle"])))  # a check that needs them asserts them
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
    # v2x (30 Oct): story.js wires the index once its WebGL scene is built (begin(), after html.gl-ready), and since v2x it
    # builds in slices after the first paint, so on a slow runner the loader (capped at 1.2 s) can lift first and an
    # index click sent at once is lost. Wait for the overture to be wired (gl-ready, or the static no-webgl sequence);
    # if it never is, the click goes anyway and the check fails as before. (Requested of home: wire the index earlier.)
    await until(pg, "['gl-ready', 'no-webgl'].some(c => document.documentElement.classList.contains(c))", timeout)
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


# round 2 (CI): what a swarm lab is doing when a check of it fails (its counters, visibility, quality, the page's frames)
LAB_STATE = """(async () => { const r = document.querySelector('[data-swarm-live]'); if (!r) return null; const c = r.querySelector('canvas'), b = (c || r).getBoundingClientRect(), q = s => (r.querySelector(s) || {}).textContent || '';
  const n = await new Promise(res => { let k = 0; const t0 = performance.now(); const f = () => { k++; if (performance.now() - t0 < 1000) requestAnimationFrame(f); else res(k); }; requestAnimationFrame(f); });
  return { inflight: q('[data-sw-inflight]').trim(), state: q('[data-sw-state]').trim(), cls: r.className, quality: r.dataset.swQuality, cap: r.dataset.swCap || null,
    hidden: document.hidden, canvas: [Math.round(b.top), Math.round(b.bottom)], vh: innerHeight, y: Math.round(scrollY), raf_per_s: n }; })()"""


def lab_why(st, errs, fr=None):
    """round 2 (CI): a swarm lab failure, explained from the page: the frames after the action, the lab's state, page errors"""
    s = []
    if fr: s.append(f"{len(fr)} page frames over {fr[-1][0] - fr[0][0]} ms, in flight {fr[0][1]} -> {fr[-1][1]} ({len({x[1] for x in fr})} distinct values)")
    s.append(f"lab {st}")
    s.append(f"page errors {errs[:3] if errs else 'none'}")
    return "; ".join(s)


# ---------------------------------------------------------------- the checks
CHECKS = []
def check(fn): CHECKS.append(fn); return fn


@check
async def pages(b):
    """every page at 1440 and 390: 0 console errors, no horizontal overflow and no empty gutter, no forbidden strings, the team only on Company"""
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
            # (integrate hc15) and the page fills the window: where no scrollbar takes width (this browser hides them, as
            # phones and overlay scrollbars do) nothing may reserve an empty gutter (Home's gutter kept for every browser
            # stood as a 15 px strip of paper beside every band: scrollWidth 1425 at 1440, 375 at 390)
            if m["clientWidth"] >= m["innerWidth"]:
                assert m["scrollWidth"] >= m["innerWidth"] - 1, (name, w, "an empty gutter: the layout is narrower than the window", m["scrollWidth"], m["innerWidth"])
            assert not m["overflow"], (name, w, m["overflow"])
            assert not bad, (name, w, bad)
            assert not errs, (name, w, errs)
            errs.clear()
        await ctx.close()
    (OUT / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("pages: 0 console errors, no horizontal overflow, no empty gutter, no forbidden strings at 1440 and 390")


@check
async def home(b):
    """the homepage systems as one page at 1440: beats, record-driven overture, nav, swarm, chain, proof (the running ledger
    left Home on 1 Nov; hc5: §02 drew Platform's plate, still; hc11: that chapter left Home, whose hero's "See the stack"
    goes to Platform: the explorer's keys, boundary and readout are checked on Platform §01, its one page: platform_spec;
    hc13r: §03 #proof left Home, its parts closing the overture's scene 4 (the count with its hedge, the record, the regime
    split, the way to Proof), and the chart's keyboard is checked on Proof, its one page: interior; Home's lab follows one
    proposal by itself, quietly, once it is well in view, and rests in its follow view: HOME-2, also lab_act)"""
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
        if i == 4:  # hc12: the ten columns above the floor stand with their hedge (HEDGE_S4)
            assert await until(pg, HEDGE_S4, 3000), "scene 04 at 1440: no shown label says 'Exact value not published' inside the viewport"
        await pg.screenshot(path=str(OUT / f"story-b{i}.png"))
    # hero stats must not overlap the globe canvas region: check they sit under the copy (left half)
    box = await pg.locator(".beat-0 .hero-stats").bounding_box()
    assert box and box["x"] + box["width"] < 1440 * 0.56, ("hero stats intrude on the globe", box)
    await pg.locator("[data-story-motion]").click()
    await expect(pg.locator("[data-story-motion]")).to_have_text("Resume motion")
    await pg.locator("[data-story-motion]").click()
    # the overture reads the sessions record (#oxa-sessions): a column, a day tag and an ink copy per session; derived copy.
    # Round 1 (OV4): the coda states the derived summary instead of repeating the tally, so the tally is checked against
    # the record wherever it is written instead of against two literal copies. v2x cut (1 Nov): the beat-4 tally "Ten for
    # ten." left the page; the derived count is now written as the coda ("Ten of ten above the floor.") and the first
    # screen's fact ("ten sessions above 10 bps"), so every derived number the page writes ([data-story-n] above / total /
    # floor / tally, in the case its data-story-as asks for) must equal the record, and the coda's above and total must be
    # there at least once. hc6 (home, HC6 item 1): the coda is gone (no [data-story-n] is left on Home; the derive code
    # stays for any future one); the derived count is written as §04's heading ("Ten of ten above the floor."), whose
    # above and total must equal the record, in the case it is set (Words / words).
    # hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1): the ink copy of each day tag on
    # the paper (.story-ink) went with the paper's record row (§01 itself is the paper now), so there is no ink copy to
    # count (any ink copy the overture draws again must still be one per session); the day tags (one per session), the
    # premium count and the derived copy stay checked against the record
    st = await pg.evaluate("""(() => ({ days: document.querySelectorAll('.story-labels .story-lab.day').length,
        prem: document.querySelectorAll('.story-labels .story-lab.day.is-prem').length, ink: document.querySelectorAll('.story-ink .story-lab').length,
        n: [...document.querySelectorAll('[data-story-n]')].map(e => [e.dataset.storyN, e.dataset.storyAs || '', e.textContent]) }))()""")
    rc = await pg.evaluate(RECORD)
    tally = capw(words(rc["above"])) + " for " + words(rc["total"]) + "."
    def story_want(k, as_):
        if k == "tally": return tally
        v = rc.get(k)
        if k not in ("above", "total", "floor") or v is None: return None
        v = int(v) if float(v).is_integer() else v
        return words(v) if as_ == "words" else capw(words(v)) if as_ == "Words" else str(v)
    wrong = [(k, a, t, story_want(k, a)) for k, a, t in st["n"] if story_want(k, a) is not None and t != story_want(k, a)]
    assert st["days"] == rc["total"] and st["prem"] == rc["premium"] and st["ink"] in (0, rc["total"]) and not wrong, (st, "record", rc, "differ", wrong)
    # hc13r (home, HOME-1): §03's heading left with its band; the derived count is scene 4's lede, which must equal the record
    h = await pg.evaluate("[...document.querySelectorAll('.beat-4 .body-lg [data-proof]')].map(e => [e.dataset.proof, e.textContent])")
    assert h == [["above", capw(words(rc["above"]))], ["total", words(rc["total"])]], ("scene 4's lede: the derived count", h, "record", rc)
    # hc13r (HOME-1): the overture carries the record (#oxa-sessions), the hedge inside the claim's own sentence (proof-of-concept,
    # "not a forecast" -> #disclosures), the regime split in its static HTML and the way to Proof; Home draws no second chart
    p4 = await pg.evaluate("""(() => { const b = document.querySelector('.beat-4'), l = b.querySelector('.body-lg');
      return { rec: !!b.querySelector('#oxa-sessions'), charts: document.querySelectorAll('[data-proof-chart]').length,
        hedge: !!l && /proof-of-concept/.test(l.textContent) && !!l.querySelector('a[href="#disclosures"]'), split: /Five premium, five discount\\./.test(b.textContent),
        proof: !!b.querySelector('a[href="evidence.html"]') }; })()""")
    assert p4 == {"rec": True, "charts": 0, "hedge": True, "split": True, "proof": True}, ("scene 4 carries the record, its hedge, the split and the way to Proof; no chart on Home", p4)
    # the last beat is never carried under the bar by the stage's exit: it has faded, or (hc26r, home's HOME-3: it leaves by
    # being clipped at the bar's edge, never faded) what still shows of it starts at the bar's foot (integrate hc26r)
    await pg.evaluate("(() => { const s = document.querySelector('.story'); window.scrollTo({top: s.offsetTop + s.offsetHeight - innerHeight * 0.5, behavior: 'instant'}); })()")
    B4 = r"""(() => { const b = document.querySelector('.beat-4'), o = +getComputedStyle(b).opacity, r = b.getBoundingClientRect(), nb = document.querySelector('.nav').getBoundingClientRect().bottom;
      const k = +((getComputedStyle(b).clipPath.match(/inset\(\s*(-?[\d.]+)px/) || [0, 0])[1]), top = r.top + k;
      return { o, top: Math.round(top * 10) / 10, bottom: Math.round(r.bottom), nb: Math.round(nb * 10) / 10, ok: o < 0.05 || r.bottom <= nb + 0.5 || top >= nb - 1 }; })()"""
    op = await until(pg, f"({B4}).ok ? 'ok' : ''", 4000)
    assert op, ("beat 4 drawn under the bar past the stage's end (faded, or clipped at the bar's foot)", await pg.evaluate(B4))
    under = []
    for f in (1.0, .9, .8, .7, .6, .5, .4, .3):  # through the stage's exit, where the beat crosses the bar
        await pg.evaluate(f"(() => {{ const s = document.querySelector('.story'); window.scrollTo({{top: s.offsetTop + s.offsetHeight - innerHeight * {f}, behavior: 'instant'}}); }})()")
        await pg.wait_for_timeout(450)
        q = await pg.evaluate(B4)
        if not q["ok"]: under.append((f, q))
    assert not under, ("beat 4 drawn under the bar during the stage's exit (faded, or clipped at the bar's foot)", under[:3])
    # the nav: the chapter readout replaced the fixed rail; its list names every chapter of the page (7 until hc11, 6 since
    # §02 left, 5 since hc13r when §03 #proof left: counted from the page and pinned at 5); the readout names the chapter
    # under the bar, and the bar takes a dark band's tone (hc13r: Home has no dark chapter now; its dark band is the close)
    nch = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
    assert nch == 5 and await pg.locator(".nav-ch-list a").count() == nch and await pg.locator(".chapters").count() == 0, ("the readout lists every chapter", nch)
    await pg.evaluate("document.querySelector('#economics').scrollIntoView({behavior: 'instant'})")
    lab = await until(pg, "(() => { const l = document.querySelector('.nav-ch-btn').getAttribute('aria-label') || ''; return l.includes('Why agents') ? l : ''; })()", 4000)
    assert lab, ("chapter readout over #economics", await pg.locator(".nav-ch-btn").get_attribute("aria-label"))
    await pg.evaluate("document.querySelector('.cta-band').scrollIntoView({behavior: 'instant'})")
    assert await until(pg, "document.querySelector('.nav').classList.contains('nav--dark')", 4000), "the bar over the dark close (.cta-band) is not dark"
    # hc5 (home, HC5 item 1): Home §02 drew Platform's engraved stack plate, still, with no explorer on Home. hc11 (home,
    # HC11 item 1): that chapter left Home; the principle stays: Home draws no explorer and does not fetch its engine
    # (arch.js), and the stack is one click away: the hero's "See the stack" goes to Platform, whose hero is the plate and
    # whose §01 is the explorer (its keys and readout: platform_spec)
    plate = await pg.evaluate("""(() => ({ stack: !!document.querySelector('#stack'),
        see: (document.querySelector('.beat-0 .hero-cta a.btn--ghost') || { getAttribute: () => null }).getAttribute('href'),
        arch: document.querySelectorAll('[data-arch], .arch').length,
        fetched: performance.getEntriesByType('resource').map(e => e.name).filter(n => /\\/arch\\.js(\\?|$)/.test(n)) }))()""")
    assert not plate["stack"] and plate["see"] == "platform.html" and plate["arch"] == 0 and not plate["fetched"], ("home: no stack chapter, 'See the stack' goes to Platform, no explorer on Home, arch.js not fetched", plate)
    # swarm lab: runs, announces settlements (at most 4 a second, in the agreed shape), follows by keyboard, halts and drains
    await pg.locator("[data-swarm-live]").scroll_into_view_if_needed()
    # hc13r (home, HOME-2): the lab follows one proposal by itself, quietly (its live region stays empty), then rests;
    # hc22 (home, HC22 4.4): the act leaves the Follow control alone, so it is read from the lab root's data-sw-act
    assert await until(pg, "document.querySelector('[data-swarm-live]').dataset.swAct === 'on'", 4000), "the lab did not follow a proposal by itself"
    assert await pg.evaluate("document.querySelector('[data-sw-say]').textContent === ''"), "the lab's own act announced itself"
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
    # hc13r (HOME-2): the act rests in its follow view: the six gates hit, the trace shown (1440); hc22 (HC22 4.4): the
    # control was never pressed and still reads "Follow a proposal" (it answers a reader's own follow only)
    rest = await until(pg, "(() => { const f = document.querySelector('[data-sw-follow]'); return document.querySelector('[data-swarm-live]').dataset.swAct === 'rest' && f.getAttribute('aria-pressed') === 'false' && f.textContent === 'Follow a proposal' && document.querySelectorAll('[data-sw-gates] li.is-hit').length === 6 && !document.querySelector('[data-sw-callout]').hidden; })()", 15000, 200)
    assert rest, ("the lab's act did not rest in its follow view", await pg.evaluate("[document.querySelector('[data-sw-follow]').textContent, document.querySelectorAll('[data-sw-gates] li.is-hit').length]"))
    await pg.locator("[data-sw-follow]").focus(); await pg.keyboard.press("Enter")
    await expect(pg.locator("[data-sw-follow]")).to_have_attribute("aria-pressed", "true")
    await expect(pg.locator("[data-sw-callout]")).to_be_visible()
    await pg.keyboard.press("Escape")
    await expect(pg.locator("[data-sw-callout]")).to_be_hidden()
    assert await pg.evaluate("document.activeElement === document.querySelector('[data-sw-follow]')")
    await pg.locator("[data-sw-halt]").click()
    await expect(pg.locator("[data-sw-state]")).to_have_text("Halted")
    drained = await until(pg, "document.querySelector('[data-sw-inflight]').textContent.trim() === '0' && document.querySelector('[data-sw-banner]').textContent.includes('drained')", 30000, 250)
    assert drained, ("halt did not drain", await pg.evaluate("[document.querySelector('[data-sw-inflight]').textContent, document.querySelector('[data-sw-banner]').textContent]"), lab_why(await pg.evaluate(LAB_STATE), errs))
    # v2x cut, owner's-eye fix (1 Nov): Home's running agent log ("[data-ledger=live]", once home 06) left the page with
    # its stream keyboard; the swarm's announcements are no longer sealed on Home (the lab's trace links to Trust's ledger:
    # swarm_trace_to_ledger), so the ledger answers, the five-announcement test and the stream's keys are not read here.
    assert await pg.locator("[data-ledger=live]").count() == 0, "Home draws a running ledger again: restore its block in `home` (git show e5720dc:tools/verify_v9.py)"
    # chain
    await pg.locator("[data-chain]").scroll_into_view_if_needed()
    await pg.wait_for_timeout(800)
    await expect(pg.locator(".chain-list li")).to_have_count(8)
    await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
    broken3 = await chain_broken_3(pg, "home")
    await pg.locator(".chain-list li:nth-child(3) .ev").fill("REJECTED")
    await expect(pg.locator(".chain-list .is-broken")).to_have_count(6)
    await expect(pg.locator("[data-chain-status]")).to_contain_text(broken3)
    await still_shot(pg, "[data-chain]", OUT / "chain-broken.png")
    await pg.locator("[data-chain-restore]").click()
    await expect(pg.locator(".chain-list .is-broken")).to_have_count(0)
    await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
    await pg.locator("[data-chain-try]").click()
    await expect(pg.locator(".chain-list .is-broken")).to_have_count(6)
    await pg.locator("[data-chain-restore]").click()
    await expect(pg.locator(".chain-list .is-broken")).to_have_count(0)
    await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
    # hc13r (home, HOME-1): Home draws no proof chart (asserted above); its listbox, keyboard and caption readout are
    # checked on Proof, the chart's one page (interior)
    assert not errs, errs
    print(f"home: 5 beats navigable, stats clear of the globe, motion pause, overture reads the record ({rc['total']} columns, {rc['premium']} premium), last beat clear of the bar, "
          f"{nch} chapters in the nav list (no rail), 'See the stack' to Platform (no explorer, arch.js not fetched), swarm {len(ev)} events in view (gaps >= {min(gaps):.0f} ms), follow by keyboard, halt drains, "
          f"chain breaks (typed and one-tap) + restores; the lab acted once, quietly, and rested in its follow view; scene 4 carries the record (count, hedge, split, link; no chart on Home)")
    await ctx.close()


@check
async def interior(b):
    """Proof: pointing at a session lights it (and only it) and the lane names its record; Trust: the replay verifies;
    Platform: the explorer is ready. (v2x cut, 1 Nov: Table 1.1 left Proof for readers with JavaScript, it is the <noscript>
    record now; the chart's lanes carry each session, so the hover is on the lane, not on a table row. hc4: the chart is
    the hero and its inspector is gone, so the lane's own text is read.)"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/evidence.html", wait_until="load")
    await expect(pg.locator("#performance [role=option]")).to_have_count(10)
    await pg.locator("#performance .pf-lane").nth(2).scroll_into_view_if_needed()
    await expect(pg.locator("#performance .figure-cap--stack.pf-cap")).to_have_count(1)
    cap0 = await pg.evaluate("document.querySelector('#performance .figure-cap--stack.pf-cap').getBoundingClientRect().height")
    await pg.locator("#performance .pf-lane").nth(2).hover()
    await expect(pg.locator("#performance .pf-lane").nth(2)).to_have_class(re.compile(r"\bis-on\b"))
    # hc4 (proof, HC4 item 1): the chart is Proof's hero and has no inspector; the lane in hand names its record (its
    # accessible text) and is the one lit, the others dimmed
    await expect(pg.locator("#performance .pf-lane").nth(2).locator(".sr-only")).to_contain_text("Day 03")
    assert await pg.locator("#performance .pf-lane.is-on").count() == 1 and await pg.locator("#performance [data-proof-chart].has-on").count() == 1
    # hc11 (proof, HC11 item 2): the caption reads the session in hand for sighted visitors (aria-hidden: the lane speaks),
    # its own words step aside, "See the disclosures." stays, and the caption keeps its height (a hidden copy of the
    # longest record holds it)
    await expect(pg.locator("#performance .pf-cap-r")).to_contain_text("Day 03")
    await expect(pg.locator("#performance .pf-cap-r")).to_be_visible()
    await expect(pg.locator("#performance .pf-cap a")).to_be_visible()
    assert await pg.locator("#performance .pf-cap-r").get_attribute("aria-hidden") == "true"
    assert abs(await pg.evaluate("document.querySelector('#performance .figure-cap--stack.pf-cap').getBoundingClientRect().height") - cap0) < 0.5, "proof: the caption's readout changed its height"
    # hc13r (integrate; home's HOME-1 took the chart off Home §03, where its keyboard was checked until hc12): the chart is a
    # listbox of the ten sessions with one tab stop; arrows select (the selected option carries its record; no inspector
    # row), the caption reads it with its height held, Escape clears and the caption returns to its height
    await pg.mouse.move(5, 450)
    opts = pg.locator("#performance [role=listbox] [role=option]")
    await expect(opts).to_have_count(10)
    assert await pg.locator('#performance [role=option][tabindex="0"]').count() == 1, "proof: the listbox has more or fewer than one tab stop"
    await opts.nth(0).focus(); await pg.keyboard.press("ArrowRight")
    await expect(opts.nth(1)).to_have_attribute("aria-selected", "true")
    await expect(opts.nth(1)).to_contain_text("Day 02")
    await expect(pg.locator("#performance .pf-cap-r")).to_be_visible()
    await expect(pg.locator("#performance .pf-cap-r")).to_contain_text("Day 02")
    assert abs(await pg.evaluate("document.querySelector('#performance .figure-cap--stack.pf-cap').getBoundingClientRect().height") - cap0) < 0.5, "proof: the caption's readout (keyboard) changed its height"
    assert await pg.locator(".pf-read").count() == 0
    await pg.keyboard.press("Escape")
    await expect(pg.locator('#performance [role=option][aria-selected="true"]')).to_have_count(0)
    await expect(pg.locator("#performance .pf-cap-r")).to_be_hidden()
    assert abs(await pg.evaluate("document.querySelector('#performance .figure-cap--stack.pf-cap').getBoundingClientRect().height") - cap0) < 0.5, "proof: the caption did not return to its height"
    await pg.goto(f"{BASE}/trust.html", wait_until="load")
    await expect(pg.locator("[data-ledger=replay] .lt-rec")).to_have_count(9)
    await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Chain intact")  # hc2: Home's words (was "Chain ✓ · 9 records verify")
    await pg.locator("[data-lt-verify]").click()
    await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Verified here · 8 of 8 links hold", timeout=10000)
    await pg.goto(f"{BASE}/platform.html", wait_until="load")
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-wide.is-ready')", 10000), "platform explorer not ready"
    assert await pg.locator("#architecture .arch-layer").count() == 8
    assert not errs, errs
    print("proof: a session lights on hover (one lane lit), its lane names Day 03 and the caption reads it (height held); the listbox: one tab stop, ArrowRight selects Day 02 (the caption reads it, height held), Escape clears; trust: 9-record trace verifies 8 of 8 links; platform: explorer ready with 8 layers")
    await ctx.close()


# the replay's selected record and its first broken one (ids), and whether that one lies inside the strip's view
TT_FIRST = """(() => { const l = document.querySelector('[data-ledger=replay]'), v = l.querySelector('.lt-view'), f = l.querySelector('.lt-rec.is-broken'), s = l.querySelector('.lt-rec.is-sel');
  const id = el => el ? ((el.querySelector('.lt-id') || {}).textContent || '').trim() : null, vr = v.getBoundingClientRect(), fr = f ? f.getBoundingClientRect() : null;
  return { first: id(f), sel: id(s), inView: !!fr && fr.left >= vr.left - 1 && fr.right <= vr.right + 1 }; })()"""


@check
async def trust_tamper(b):
    """Trust's record can be broken and Verify shows it (v2x tests pass, 30 Oct; EVOLVE Trust: 'Try to change the past'):
    typing over a record voids the verdict ('Edited · not verified'); Verify then fails from the edited record on (the
    state names the first broken record; every record from it on, the last ones in order, is marked broken) and selects
    that first broken record; Restore puts the excerpt back and Verify holds again ('8 of 8 links hold'). v2x r2: at
    1024x768, from the hero's way in, Enter in the edited field verifies,
    the cause is selected inside the strip's view, and Tab from the edited field reaches Verify.
    The hashes are real SHA-256 computed in the page, so this is the chain's own tamper evidence, not a canned state.
    v2x r5 (system r5, r5-perf issue 4): Trust starts ledger.js and trust.js after its first paint (afterpaint.js), so
    'load' no longer means they have run, and the hero's "Try to change the past" is the plain #ledger link (no edit)
    until trust.js arrives, by design. Each leg waits, as open_page does, until every script the after-paint tag lists
    has run before it acts (integrate r5: the 1024 leg clicked the link ~40 ms before trust.js, 3 of 8 runs).
    v2x hc2 (proof; HC2 director item 5, one chain vocabulary): the resting state reads "Chain intact" and a break reads
    "Chain broken at #<id> · every later link fails" (Home's words; no count), so the check reads the id from the state and
    asserts from the marks that the chain breaks at the edited record and every record after it is marked."""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script(SCRIPTS_RAN)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/trust.html#ledger", wait_until="load")
    assert await until(pg, HOME_ENGINES, int(15000 * max(1.0, MODE["throttle"]))), "trust.html: the after-paint scripts (ledger.js, site.js, trust.js) did not all run"
    lt, state = pg.locator("[data-ledger=replay]"), pg.locator("[data-ledger=replay] [data-lt-state]")
    await expect(lt.locator(".lt-rec")).to_have_count(9)
    await expect(state).to_contain_text("Chain intact")  # hc2 (proof): one chain vocabulary with Home
    await pg.locator("[data-lt-edit]").click()
    await pg.wait_for_timeout(300)
    await pg.keyboard.type("council · approved", delay=15)
    await expect(state).to_contain_text(re.compile(r"edited · not verified", re.I))
    await expect(pg.locator("[data-lt-restore]")).to_be_visible()
    await pg.locator("[data-lt-verify]").click()
    await expect(state).to_contain_text(re.compile(r"Chain broken at #[0-9a-f]{4} · every later link fails", re.I), timeout=15000)
    said = await state.text_content()
    m = re.search(r"#([0-9a-f]{4})", said, re.I)
    marks = await pg.evaluate("[...document.querySelectorAll('[data-ledger=replay] .lt-rec')].map(li => ({ id: (li.querySelector('.lt-id') || {}).textContent, broken: li.classList.contains('is-broken'), edited: li.classList.contains('is-edited') }))")
    broken = [k for k, x in enumerate(marks) if x["broken"]]
    first = next((k for k, x in enumerate(marks) if x["edited"]), None)
    assert m and broken and broken == list(range(broken[0], 9)), ("the broken marks do not match the verdict: every record from the first broken one on must be marked", said, marks)
    assert first is not None and broken[0] == first and marks[first]["id"].lower().lstrip("#") == m[1].lower(), ("the chain must break at the edited record", said, marks)
    # v2x r2 (proof; r2-mobile): Verify selects the cause, the first broken record (the inspector opens on it)
    fb = await pg.evaluate(TT_FIRST)
    assert fb["sel"] and fb["sel"] == fb["first"], ("after a failing Verify the selected record must be the first broken one", fb)
    # v2x r1 (proof; jury A11, Trust's screenshot moment): every broken record shows the hash it produces now beside its
    # seal, and the inspector, on a broken record, shows that same hash
    nw = await pg.evaluate("""(() => { const l = document.querySelector('[data-ledger=replay]'), s = l.querySelector('.lt-rec.is-sel.is-broken'), t = s && s.querySelector('.lt-now');
      return { now: l.querySelectorAll('.lt-now').length, broken: l.querySelectorAll('.lt-rec.is-broken').length, sel: t ? t.textContent.trim() : null,
               insp: (l.querySelector('[data-f="hash"] b') || {}).textContent || null }; })()""")
    assert nw["now"] == nw["broken"] and nw["sel"] and nw["insp"] == nw["sel"], ("sealed vs now: one '.lt-now' per broken record, and the inspector's hash on a broken record is its '.lt-now'", nw)
    await pg.locator("[data-lt-restore]").click()
    await expect(lt.locator(".lt-rec.is-edited")).to_have_count(0)
    await expect(lt.locator(".lt-now")).to_have_count(0)
    await pg.locator("[data-lt-verify]").click()
    await expect(state).to_contain_text("Verified here · 8 of 8 links hold", timeout=15000)
    await expect(lt.locator(".lt-rec.is-broken")).to_have_count(0)
    assert not errs, errs
    await ctx.close()
    # v2x r2 (proof; r2-mobile, r2-a11y): at 1024x768, from the hero's way in: Enter in the edited field verifies; the cause
    # (the first broken record) is selected and lies inside the strip's view (it had scrolled off the left edge); Restore
    # holds; then Tab from the edited field reaches Verify
    ctx = await b.new_context(viewport={"width": 1024, "height": 768}, has_touch=True)
    await ctx.add_init_script(SCRIPTS_RAN)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/trust.html", wait_until="load")
    assert await until(pg, HOME_ENGINES, int(15000 * max(1.0, MODE["throttle"]))), "trust.html@1024x768: the after-paint scripts did not all run"
    lt, state = pg.locator("[data-ledger=replay]"), pg.locator("[data-ledger=replay] [data-lt-state]")
    await expect(lt.locator(".lt-rec")).to_have_count(9)
    await pg.locator("a[data-lt-go]").click(); await pg.wait_for_timeout(1500)
    await pg.keyboard.type("council · approved", delay=15)
    await expect(state).to_contain_text(re.compile(r"edited · not verified", re.I))
    await pg.keyboard.press("Enter")
    await expect(state).to_contain_text(re.compile(r"Chain broken at #[0-9a-f]{4}", re.I), timeout=15000)
    await pg.wait_for_timeout(900)  # the strip scrolls the cause into view
    fb2 = await pg.evaluate(TT_FIRST)
    assert fb2["sel"] and fb2["sel"] == fb2["first"] and fb2["inView"], ("1024x768: Enter verifies, and the first broken record is selected inside the strip's view", fb2)
    await pg.locator("[data-lt-restore]").click()
    await expect(lt.locator(".lt-rec.is-edited")).to_have_count(0)
    await pg.locator("[data-lt-edit]").focus(); await pg.keyboard.press("Enter"); await pg.wait_for_timeout(400)
    await pg.keyboard.type("x", delay=10); await pg.keyboard.press("Tab"); await pg.wait_for_timeout(200)
    tab = await pg.evaluate("(() => { const a = document.activeElement; return !!a && a.hasAttribute('data-lt-verify'); })()")
    assert tab, "1024x768: Tab from the edited field does not reach Verify"
    # v2x r3 (proof; r3-a11y S1, r3-motion): no trap inside the record. From Verify, four more Tabs (a record, Event,
    # Detail, then out) leave [data-ledger]; r2's fields were Tab stops that cycled inside it
    left = []
    for _ in range(4):
        await pg.keyboard.press("Tab"); await pg.wait_for_timeout(80)
        left.append(await pg.evaluate(TAB_STEP))
    assert not left[-1]["inLedger"], ("1024x768: four Tabs after Verify must leave the record ([data-ledger])", [x["d"] for x in left])
    assert not errs, errs
    await ctx.close()
    print(f"trust_tamper: an edit voids the verdict; Verify fails from the edited record ({said.strip()}) and selects it; {nw['now']} records show the hash they produce now, the inspector the same {nw['sel']}; "
          f"Restore clears them, then Verify: 8 of 8 links hold; 1024x768: Enter verifies, the cause {fb2['sel']} selected inside the strip, Tab reaches Verify, four more leave the record ({left[-1]['d']})")


# ---- the keyboard can always leave: a Tab walk reaches the footer, and no stop repeats within one cycle (v2x r3)
TAB_STEP = r"""(() => { const a = document.activeElement; if (!a || a === document.body) return { id: 0, d: 'BODY', skip: false, legal: false, inLedger: false };
  window.__twN = window.__twN || 0; if (!a.__tw) a.__tw = ++window.__twN;
  const t = (a.getAttribute('aria-label') || a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
  return { id: a.__tw, d: a.tagName.toLowerCase() + (a.id ? '#' + a.id : '') + ' ' + JSON.stringify(t),
    skip: /^Skip to content/i.test(t), legal: a.matches('.footer-legal > summary'), inLedger: !!a.closest('[data-ledger]') }; })()"""
TAB_PAGES = [("trust.html", 80, 60), ("index.html", 120, 90)]  # (page, presses, 'Legal & disclosures' reached by)
# v2x r4 (platform; r4-a11y moderate, WCAG 2.4.11): the desk's sticky head never hides the control Shift+Tab lands on
DESK_SIZES = ((1440, 900), (1024, 900), (1024, 768))
DESK_LIST = r"""() => { const d = document.querySelector('.desk');
  const f = [...d.querySelectorAll('a[href], button, input, [tabindex]')].filter(e => e.tabIndex >= 0 && !e.disabled && e.checkVisibility());
  f.forEach((e, i) => e.setAttribute('data-tw', i)); return f.map(e => (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30)); }"""
DESK_PLACE = r"""([i, where]) => { const e = document.querySelector(`[data-tw="${i}"]`), r = e.getBoundingClientRect();
  const nav = document.querySelector('header.nav').getBoundingClientRect();
  scrollTo({ top: scrollY + (where === 'head' ? r.top - nav.bottom - 8 : r.bottom - nav.bottom - 6), behavior: 'instant' }); }"""
DESK_COVER = r"""() => { const e = document.activeElement, r = e.getBoundingClientRect(), hr = document.querySelector('.desk-head').getBoundingClientRect();
  let covered = 0;
  for (const fx of [0.1, 0.5, 0.9]) for (const fy of [0.1, 0.5, 0.9]) { const x = r.left + r.width * fx, y = r.top + r.height * fy;
    if (y < 0 || y > innerHeight) { covered++; continue; } const h = document.elementFromPoint(x, y); if (!(h === e || e.contains(h))) covered++; }
  return { focus: (e.getAttribute('aria-label') || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30), i: e.getAttribute('data-tw'), covered,
           stuck: Math.abs(hr.top - document.querySelector('header.nav').getBoundingClientRect().bottom) < 2 }; }"""


@check
async def tab_walk(b):
    """v2x r3 (proof; r3-a11y S1 and r3-motion, WCAG 2.1.1/2.1.2): from a fresh page, Tab up to N times. 'Legal &
    disclosures' (the footer's last summary) is reached within the budget, and between two visits of 'Skip to content'
    (one cycle) no element takes focus twice. Trust: 80 presses, the footer by 60 (31-stop cycle at 1440, 25 at 390;
    r2's record trapped focus and never reached the footer in 140). Home: v2x r4 (proof; r4-a11y minor) the chain is one
    roving Tab stop (the record numbers) and its sixteen fields are out of the Tab order until used, so the footer by 90
    in 120 presses (press 70 at 1440 and 66 at 390 when tightened; r3's chain fields made it 85 / 73, budget 160 in 200).
    Not 'no element focused more than twice in 80 presses': the skip link correctly comes round three or four times in
    80 on a short page.
    v2x r4 (platform; r4-a11y moderate, WCAG 2.4.11): Lifecycles at 1440x900, 1024x900 and 1024x768: with each desk
    control just under the sticky head (its top 8 px under the bar) or its bottom 6 px under the bar, focus the next
    control without scrolling and press Shift+Tab: the control that takes focus is never covered at all nine sample
    points (by the head, the bar or the screen's edge). Based on platform's .shots/v2x/work/platform/r4/desk_probe.py
    (0 of 9 points covered at every size)."""
    bad, said = [], []
    for path, n, by in TAB_PAGES:
        for w, h in ((1440, 900), (390, 844)):
            ctx, pg = await open_page(b, path, w, h)
            await pg.wait_for_timeout(1000)
            seq = []
            for _ in range(n):
                await pg.keyboard.press("Tab"); await pg.wait_for_timeout(40)
                seq.append(await pg.evaluate(TAB_STEP))
            await ctx.close()
            legal = next((k + 1 for k, x in enumerate(seq) if x["legal"]), None)
            skips = [k + 1 for k, x in enumerate(seq) if x["skip"]]
            rep, seen = [], {}
            for k, x in enumerate(seq):
                if x["skip"]: seen = {}
                if x["id"] and x["id"] in seen: rep.append(f"{x['d']} at presses {seen[x['id']]} and {k + 1}")
                if x["id"]: seen[x["id"]] = k + 1
            if legal is None or legal > by: bad.append(f"{path}@{w}x{h}: 'Legal & disclosures' reached at press {legal} (by {by} expected); skip link at {skips[:4]}; last stops {[x['d'] for x in seq[-4:]]}")
            if rep: bad.append(f"{path}@{w}x{h}: {len(rep)} element(s) took focus twice within one cycle, e.g. {rep[:3]}")
            said.append(f"{path}@{w}: footer at {legal}, cycle {skips[1] - 1 if len(skips) > 1 else '?'}")
    for w, h in DESK_SIZES:
        ctx, pg = await open_page(b, "lifecycles.html", w, h)
        await pg.evaluate("document.querySelector('.desk').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(1000)
        names = await pg.evaluate(DESK_LIST)
        legs, worst, other = 0, 0, 0
        for i in range(len(names) - 1):
            for where in ("head", "edge"):
                await pg.evaluate(DESK_PLACE, [i, where]); await pg.wait_for_timeout(250)
                await pg.evaluate(f"document.querySelector('[data-tw=\"{i + 1}\"]').focus({{preventScroll: true}})")
                await pg.keyboard.press("Shift+Tab"); await pg.wait_for_timeout(900)
                s = await pg.evaluate(DESK_COVER); legs += 1; worst = max(worst, s["covered"]); other += s["i"] != str(i)
                if s["covered"] >= 9: bad.append(f"lifecycles.html@{w}x{h} ({where}): Shift+Tab from {names[i + 1]!r} focused {s['focus']!r} hidden at all 9 points (head stuck: {s['stuck']})")
        await ctx.close()
        if len(names) < 2: bad.append(f"lifecycles.html@{w}x{h}: {len(names)} desk controls found")
        said.append(f"lifecycles@{w}x{h}: {legs} Shift+Tab legs over {len(names)} desk controls, worst {worst} of 9 points covered"
                    + (f" ({other} landed outside the listed controls)" if other else ""))
    assert not bad, "tab_walk:\n  " + "\n  ".join(bad)
    print("tab_walk: " + "; ".join(said) + "; no stop twice in a cycle")


# hc3 (proof, home): Home §06's records carry Trust's ids (#4f23 ... #4f2a) and the break speaks Trust's words: it names
# the record where the chain broke by its id and says every later link fails (was "Chain broken at record 03"). The
# checks below break the third record, so they read its id from the page and expect the sentence that names it.
CHAIN_ID3 = "(() => { const e = document.querySelector('.chain-list li:nth-child(3) .i'); return e ? e.textContent.trim() : ''; })()"


async def chain_broken_3(pg, tag):
    """the sentence the status must read once the third record is changed: 'Chain broken at #4f25 · every later link
    fails' (the id read from the page; Home's ids start with '#', as Trust's)"""
    i3 = await pg.evaluate(CHAIN_ID3)
    assert i3.startswith("#") and len(i3) > 1, f"{tag}: the third record's id reads {i3!r} (Trust's ids, '#4f25', expected)"
    return f"Chain broken at {i3} · every later link fails"


CHAIN_AT = """(sel) => { const e = document.querySelector(sel); return !!e && document.activeElement === e; }"""
CHAIN_STOPS = """() => ({ fields: [...document.querySelectorAll('.chain-list .ev, .chain-list .what')].filter(f => f.tabIndex >= 0).length,
  stops: [...document.querySelectorAll('.chain-list .i[role="button"]')].filter(i => i.tabIndex === 0).length,
  numbers: document.querySelectorAll('.chain-list .i[role="button"]').length })"""


@check
async def chain_keys(b):
    """v2x r4 (proof; r4-a11y minor, Home §06): the chain is one roving Tab stop. On a fresh Home no record's Event or
    Detail is a Tab stop and exactly one record number ('Edit #4f23') is; ArrowDown twice reaches the third record's
    number (#4f25), Enter puts the caret in its Detail, typing breaks the chain there (the status names #4f25; hc3: Trust's
    ids), Escape returns to the number; after Restore and 'Change a record' (the third), Tab from Restore lands on the
    third record's number. At 1440 and 390 (where 05-08 are folded and the
    arrows skip them). Based on proof's .shots/v2x/work/proof/r4/chain_probe.py. verify_v9 `home` keeps the pointer path
    (fill 'REJECTED' into record 03's Event, the one-tap Alter, Restore)."""
    said = []
    for w, h, touch in ((1440, 900, False), (390, 844, True)):
        ctx, pg = await open_page(b, "index.html", w, h, dpr=2 if touch else 1, touch=touch)
        await pg.locator("[data-chain]").scroll_into_view_if_needed()
        await expect(pg.locator("[data-chain].chain-ready")).to_have_count(1)
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        st = await pg.evaluate(CHAIN_STOPS)
        assert st["fields"] == 0 and st["stops"] == 1 and st["numbers"] == 8, f"chain_keys@{w}: {st} (want no field in the Tab order, one roving stop of 8 record numbers)"
        r1, r3 = ".chain-list li:nth-child(1) .i", ".chain-list li:nth-child(3) .i"
        broken3 = await chain_broken_3(pg, f"chain_keys@{w}")
        await pg.focus(r1)
        await pg.keyboard.press("ArrowDown"); await pg.keyboard.press("ArrowDown"); await pg.wait_for_timeout(80)
        assert await pg.evaluate(CHAIN_AT, r3), f"chain_keys@{w}: ArrowDown x2 from record 01 did not reach record 03's number"
        await pg.keyboard.press("Enter"); await pg.wait_for_timeout(120)
        assert await pg.evaluate(CHAIN_AT, ".chain-list li:nth-child(3) .what"), f"chain_keys@{w}: Enter on record 03's number did not put the caret in its Detail"
        await pg.keyboard.type("altered", delay=15)
        await expect(pg.locator("[data-chain-status]")).to_contain_text(broken3)
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(80)
        assert await pg.evaluate(CHAIN_AT, r3), f"chain_keys@{w}: Escape in record 03's Detail did not return to its number"
        await pg.locator("[data-chain-restore]").click()
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        await pg.locator("[data-chain-try]").click()
        await expect(pg.locator("[data-chain-status]")).to_contain_text(broken3)
        await pg.focus("[data-chain-restore]"); await pg.keyboard.press("Tab"); await pg.wait_for_timeout(80)
        assert await pg.evaluate(CHAIN_AT, r3), f"chain_keys@{w}: Tab from Restore after 'Alter record 03' did not land on record 03's number"
        st2 = await pg.evaluate(CHAIN_STOPS)
        await pg.locator("[data-chain-restore]").click()
        await expect(pg.locator("[data-chain-status]")).to_contain_text("Chain intact")
        await ctx.close()
        assert st2["stops"] == 1, f"chain_keys@{w}: {st2['stops']} record numbers are Tab stops after the walk (want 1)"
        said.append(f"{w}: 0 fields and 1 of 8 numbers in the Tab order; Down x2, Enter, type, Escape, Alter, Tab from Restore all land on the third record ({broken3.split()[3]}, named by the break)")
    print("chain_keys: " + "; ".join(said))


# the contrast of every visible text run in the chain's broken records against the colour actually under it: the
# element's own and its ancestors' backgrounds composited from the first opaque one up (a translucent tint counts), the
# text colour composited over that; 4.5:1, or 3:1 for large text (24 px, or 18.66 px at 600+)
CHAIN_BROKEN_CONTRAST = """() => { const P = c => { const m = (c || '').match(/[\\d.]+/g); if (!m || m.length < 3) return null; const v = m.map(Number); return [v[0], v[1], v[2], v.length > 3 ? v[3] : 1]; };
  const over = (t, u) => [0, 1, 2].map(i => t[i] * t[3] + u[i] * (1 - t[3])).concat(1);
  const lin = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); };
  const L = c => .2126 * lin(c[0]) + .7152 * lin(c[1]) + .0722 * lin(c[2]);
  const under = el => { const ls = []; for (let e = el; e; e = e.parentElement) { const c = P(getComputedStyle(e).backgroundColor); if (c && c[3] > 0) { ls.push(c); if (c[3] >= .999) break; } }
    let base = [255, 255, 255, 1]; for (let i = ls.length - 1; i >= 0; i--) base = ls[i][3] >= .999 ? ls[i] : over(ls[i], base); return base; };
  const rows = [...document.querySelectorAll('.chain-list > li.is-broken')].filter(li => li.getClientRects().length);
  const out = [], seen = new Set();
  for (const li of rows) { const tw = document.createTreeWalker(li, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) { const el = n.parentElement; if (!n.data.trim() || seen.has(el)) continue; seen.add(el);
      if (!el.checkVisibility({opacityProperty: true, visibilityProperty: true})) continue;
      const r = el.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
      const s = getComputedStyle(el); if (s.clipPath && s.clipPath !== 'none') continue;
      const bg = under(el), fg0 = P(s.color); if (!fg0) continue; const fg = fg0[3] < .999 ? over(fg0, bg) : fg0;
      const a = L(fg), b = L(bg), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      const px = parseFloat(s.fontSize), large = px >= 24 || (px >= 18.66 && +s.fontWeight >= 600);
      out.push({row: li.querySelector('.i') ? li.querySelector('.i').textContent.trim() : '?', el: el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''),
                text: n.data.trim().slice(0, 24), color: s.color, under: 'rgb(' + bg.slice(0, 3).map(Math.round).join(', ') + ')', ratio: Math.round(ratio * 100) / 100, need: large ? 3 : 4.5}); } }
  return {rows: rows.length, runs: out}; }"""


@check
async def chain_contrast(b):
    """v2x r5 (system; r5-a11y moderate, Home §06): after 'Alter record 03' every visible text run in a broken record
    (number, agent, event, detail, flag, new hash) reads at 4.5:1 or better (3:1 if large) against the colour actually
    under it, translucent fills composited (v2's rgba(217,103,93,.055) tint put the red text at 4.39:1); and a broken
    record is still marked as broken by something other than its text colour (a fill, an edge or an outline). At 1440 and
    390. Based on system's .shots/v2x/work/system-r5/probe1.py chain()."""
    said = []
    for w, h, touch in ((1440, 900, False), (390, 844, True)):
        ctx, pg = await open_page(b, "index.html", w, h, dpr=2 if touch else 1, touch=touch)
        await pg.locator("[data-chain]").scroll_into_view_if_needed()
        await expect(pg.locator("[data-chain].chain-ready")).to_have_count(1)
        await pg.locator("[data-chain-try]").click()
        await expect(pg.locator("[data-chain-status]")).to_contain_text(await chain_broken_3(pg, f"chain_contrast@{w}"))
        await pg.wait_for_timeout(600)  # the row's own transitions (colour, edge) settle
        r = await pg.evaluate(CHAIN_BROKEN_CONTRAST)
        mark = await pg.evaluate("""() => { const li = document.querySelector('.chain-list > li.is-broken'); if (!li) return null; const s = getComputedStyle(li);
          const clear = c => !c || /^rgba\\(\\d+, \\d+, \\d+, 0\\)$/.test(c) || c === 'transparent';
          return {fill: !clear(s.backgroundColor), edge: s.boxShadow !== 'none' || ['Top', 'Right', 'Bottom', 'Left'].some(k => parseFloat(s['border' + k + 'Width']) > 0 && !clear(s['border' + k + 'Color'])),
                  outline: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0}; }""")
        await pg.locator("[data-chain-restore]").click()
        await ctx.close()
        low = [x for x in r["runs"] if x["ratio"] < x["need"]]
        assert r["rows"] >= 1 and r["runs"], f"chain_contrast@{w}: no broken record to read after 'Alter record 03' ({r['rows']} rows)"
        assert not low, f"chain_contrast@{w}: {len(low)} text runs in broken records under their minimum: " + "; ".join(
            f"record {x['row']} {x['el']} '{x['text']}' {x['color']} on {x['under']} = {x['ratio']}:1 (need {x['need']})" for x in low[:6])
        assert mark and (mark["fill"] or mark["edge"] or mark["outline"]), f"chain_contrast@{w}: a broken record has no fill, edge or outline of its own ({mark}): only its text colour says it is broken"
        said.append(f"{w}: {r['rows']} broken records, {len(r['runs'])} text runs, lowest {min(x['ratio'] for x in r['runs'])}:1, marked by {'/'.join(k for k, v in mark.items() if v)}")
    print("chain_contrast: " + "; ".join(said))


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
    # v2x r3 (platform; r3-motion minor): with Follow centred in the viewport, Pause is on screen under the bar and answers
    # at its centre (it had sat under the bar or off screen while the walk ran)
    await pg.evaluate("document.querySelector('[data-gap-follow]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(600)
    mo = await pg.evaluate(GAP_MOTION)
    assert mo["inside"] and mo["hit"], ("1440x900: with Follow centred, Pause must lie under the bar inside the viewport and answer at its centre", mo)
    await still_shot(pg, "[data-gap]", OUT / "desk.png", pause="[data-gap-motion]")
    assert not errs, errs
    print("desk:", info, "; Pause in view under the bar with Follow centred")
    await ctx.close()


GAP_MOTION = r"""(() => { const m = document.querySelector('[data-gap-motion]'), n = document.querySelector('header.nav') || document.querySelector('.nav');
  const r = m.getBoundingClientRect(), bar = n.getBoundingClientRect().bottom, e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return { box: [Math.round(r.left), Math.round(r.top), Math.round(r.right), Math.round(r.bottom)], bar: Math.round(bar), vh: innerHeight,
    inside: r.top >= bar - 1 && r.bottom <= innerHeight + 1 && r.left >= 0 && r.right <= innerWidth, hit: !!e && (e === m || m.contains(e)) }; })()"""
DESK_HEAD = "(() => Math.round(document.querySelector('.desk-head').getBoundingClientRect().height))()"


@check
async def access(b):
    """the access form: every linked path preselects its choice (on load and on hashchange); the draft goes to the
    data-contact inbox with the path in its subject and a letter for a body (greeting, who and what, the reply address,
    the name last; the attestation only when the box is ticked; no 'key: value' lines); the whole mailto URL stays within
    1,900 characters, a long message shortened with its note; the result panel takes focus and shows the letter
    addressed to 'OpenEXA' (the inbox is never visible text); edit restores the input; on a phone the four choices are
    shown by name (the path list above is not drawn), a link to a path lands on its choice and the letter's ask line says
    what that path asks for (v2x cut, 1 Nov: the four descriptions left the page at every width); on a phone held
    sideways (844x390) the letter beside the form fits the screen and the line being typed stays in view (v2x r2)"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/access.html#managers", wait_until="load")
    await expect(pg.locator('input[value="Manager platform"]')).to_be_checked()
    # v2x tests pass (30 Oct): the other three paths, by hashchange (the footer, /for-investors and the pages link to them)
    for hid, val in (("partners", "Platform partnership"), ("investors", "Qualified investor"), ("lifecycles", "Bring a lifecycle"), ("managers", "Manager platform")):
        await pg.evaluate(f"location.hash = '{hid}'")
        await expect(pg.locator(f'input[name="interest"][value="{val}"]')).to_be_checked()
    inbox = await pg.evaluate("document.body.dataset.contact")
    attest = await pg.evaluate("document.querySelector('input[name=\"accredited\"]').closest('label').textContent.replace(/\\s+/g, ' ').trim()")
    blank = await pg.evaluate("(() => { const l = document.querySelector('[data-letter]'); return l && l.getClientRects().length ? l.querySelector('[data-letter-body]').textContent : null; })()")
    assert blank and "I am your name" in blank and "Please reply to your work email." in blank, ("the letter is not on the page before typing", blank)
    await pg.locator("#name").fill("Test Person"); await pg.locator("#email").fill("t@example.com")
    lv = await pg.evaluate("(() => { const b = document.querySelector('[data-letter-body]'); return { text: b.textContent, here: [...b.querySelectorAll('.slot.is-here')].map(s => s.dataset.slot) }; })()")
    assert "I am Test Person" in lv["text"] and "Please reply to t@example.com." in lv["text"] and lv["here"] == ["email"], ("the letter does not follow the typing", lv)
    await pg.locator('button[type="submit"]').click()
    await expect(pg.locator("form[data-access]")).to_be_hidden()
    href = await pg.locator("[data-mailto]").get_attribute("href")
    assert inbox == "ajit@openexa.com" and href.startswith(f"mailto:{inbox}?subject=") and "Manager%20platform" in href, href
    body = urllib.parse.unquote(href.split("&body=", 1)[1])
    parts = body.split("\r\n\r\n")
    assert parts[0] == "Hello OpenEXA," and parts[-1] == "Test Person" and "Please reply to t@example.com." in parts, ("the draft is not a letter", body)
    assert parts[1].startswith("I am Test Person.") and "I would like to" in parts[1], body
    assert attest not in body and not re.search(r"(?m)^(interest|name|email|organization|role|assets|message|accredited): ", body), ("attestation unticked / key: value lines", body)
    panel = await pg.evaluate("""(() => { const r = document.querySelector('.form-ok'), l = document.querySelector('[data-letter]');
      return { focused: document.activeElement === r, shown: !!l && !l.hidden && l.getClientRects().length > 0,
        to: (document.querySelector('[data-letter-to]') || {}).textContent, body: (document.querySelector('[data-letter-body]') || {}).textContent,
        text: document.body.innerText }; })()""")
    assert panel["focused"] and panel["shown"] and panel["to"] == "OpenEXA", ("result panel", {k: v for k, v in panel.items() if k != "text"})
    assert panel["body"] == body.replace("\r\n", "\n"), ("the panel's letter is not the draft", panel["body"][:120])
    assert inbox not in panel["text"] and "ajit@" not in panel["text"].lower(), "the inbox address is visible"
    await pg.locator("[data-form-edit]").click()
    await expect(pg.locator("#name")).to_have_value("Test Person")
    await expect(pg.locator("#name")).to_be_focused()
    # a long message (1,200 characters, the field's limit; dashes and spaces grow 3-9x when encoded) with the box ticked
    await pg.locator("#msg").fill(("Custody — timeline — mandate. " * 40)[:1200])
    await pg.locator('input[name="accredited"]').check()
    await pg.locator('button[type="submit"]').click()
    await expect(pg.locator("form[data-access]")).to_be_hidden()
    href = await pg.locator("[data-mailto]").get_attribute("href")
    body = urllib.parse.unquote(href.split("&body=", 1)[1])
    assert len(href) <= 1900, ("the mailto URL is longer than 1,900 characters", len(href))
    assert "[shortened to fit an email link: paste the rest here]" in body and attest in body and body.endswith("\r\n\r\nTest Person") and "Please reply to t@example.com." in body, ("long draft", len(href), body[-300:])
    assert not errs, errs
    await ctx.close()
    # a phone: the four choices by name; a link to a path (/for-investors) lands on its choice; the letter says what it asks
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/access.html#investors", wait_until="load")
    await expect(pg.locator('input[name="interest"][value="Qualified investor"]')).to_be_checked()
    await pg.wait_for_timeout(600)
    ph = await pg.evaluate("""(() => { const opt = document.querySelector('input[value="Qualified investor"]').closest('.opt').getBoundingClientRect();
      return { paths: (document.querySelector('.access-paths') || { getClientRects: () => [] }).getClientRects().length,
        names: [...document.querySelectorAll('.seg .opt label')].filter(l => l.getClientRects().length > 0 && getComputedStyle(l).visibility !== 'hidden').map(l => l.textContent.trim()),
        ask: ((document.querySelector('[data-letter-body] [data-slot=ask]') || {}).textContent || '').trim(),
        top: Math.round(opt.top), bottom: Math.round(opt.bottom), vh: innerHeight, sw: document.documentElement.scrollWidth }; })()""")
    assert ph["paths"] == 0 and ph["names"] == ["Bring a lifecycle", "Manager platform", "Platform partnership", "Qualified investor"], ("phone: the path list should fold into the four choices", ph)
    assert "qualified-investor path" in ph["ask"], ("phone: the letter does not say what the chosen path asks for", ph)
    assert ph["bottom"] > 0 and ph["top"] < ph["vh"] and ph["sw"] <= 391, ("phone: #investors did not land on its choice", ph)
    assert not errs, errs
    await ctx.close()
    # v2x r2 (company; r2-mobile): a phone on its side (844x390): the letter beside the form never outgrows the screen, and
    # the line being typed stays inside the letter's body and on screen (the letter was 527-547 px tall in a 390 px screen)
    ctx = await b.new_context(viewport={"width": 844, "height": 390}, has_touch=True, is_mobile=True, device_scale_factor=2)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/access.html", wait_until="load"); await pg.wait_for_timeout(600)
    side = []
    for sel, txt in (("#name", "Jordan Avery"), ("#email", "jordan@fund.example")):
        await pg.locator(sel).click(); await pg.keyboard.type(txt, delay=5); await pg.wait_for_timeout(250)
        side.append(await pg.evaluate("""(() => { const s = document.querySelector('.access-letter .sticky'), b = document.querySelector('[data-letter-body]'), h = b && b.querySelector('.slot.is-here');
          const sr = s ? s.getBoundingClientRect() : null, br = b.getBoundingClientRect(), hr = h ? h.getBoundingClientRect() : null;
          return { vh: innerHeight, sticky: sr && sr.height ? [Math.round(sr.top), Math.round(sr.bottom)] : null, here: h ? h.dataset.slot : null,
            inView: !!hr && hr.top >= br.top - 1 && hr.bottom <= br.bottom + 1 && hr.top >= -1 && hr.bottom <= innerHeight + 1 }; })()"""))
    s1, s2 = side
    assert s1["sticky"] and s2["sticky"] and all(x["sticky"][1] <= x["vh"] + 1 for x in side), ("844x390: the letter beside the form is taller than the screen", side)
    assert s2["here"] == "email" and s2["inView"], ("844x390: after typing the email, the line being filled is not inside the letter's body and the screen", side)
    assert not errs, errs
    await ctx.close()
    print(f"access: four paths preselect (load + hashchange); the draft to the data-contact inbox is a letter (attestation only when ticked), "
          f"{len(href)} of 1,900 characters with a long message shortened; the panel shows it to 'OpenEXA', focus moves, no inbox on screen; "
          f"edit restores; 390: the four choices by name, #investors lands on its choice and the letter says what it asks; 844x390: the letter fits the screen and keeps the typed line in view")


@check
async def company(b):
    """company team: thirteen portraits load (the v2x masters), one treatment at rest and on hover (baked into the image by
    build_team.py; the hover shows the green ring); the exact roster; no patent count"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/company.html#team", wait_until="load")
    await pg.locator(".crew--team").scroll_into_view_if_needed()
    # the advisors' portraits are loading="lazy": walk the page so every one is fetched before counting them
    for y in range(0, await pg.evaluate("document.body.scrollHeight"), 400):
        await pg.evaluate(f"scrollTo(0, {y})"); await pg.wait_for_timeout(120)
    await pg.locator(".crew--team").scroll_into_view_if_needed()
    assert await until(pg, "[...document.querySelectorAll('.crew img')].every(i => i.complete && i.naturalWidth > 0 && i.naturalWidth >= i.clientWidth)", 15000), "team portraits did not load"
    team = await pg.evaluate("[...document.querySelectorAll('.crew img')].map(i => ({ok: i.complete && i.naturalWidth >= i.clientWidth && /-v2x\\.webp$/.test(i.getAttribute('src')) && /-v2x(-160|-320)?\\.webp$/.test(i.currentSrc) && /160w.*320w.*560w/.test(i.getAttribute('srcset')), filter: getComputedStyle(i).filter}))")
    assert len(team) == 13 and all(t["ok"] for t in team), team
    # v2x: one portrait treatment, the same at rest and on hover (colour on hover showed how mismatched the photos are)
    third = pg.locator(".crew > li").nth(2)
    rest = await third.evaluate("li => ({ f: getComputedStyle(li.querySelector('img')).filter, r: getComputedStyle(li.querySelector('.ph')).boxShadow })")
    await third.hover()
    await pg.wait_for_timeout(900)
    hovered = await third.evaluate("li => ({ f: getComputedStyle(li.querySelector('img')).filter, r: getComputedStyle(li.querySelector('.ph')).boxShadow })")
    assert hovered["f"] == rest["f"] == team[2]["filter"], (rest, hovered)
    assert hovered["r"] not in ("none", rest["r"]), ("no ring on hover", rest, hovered)
    # v2x cut (1 Nov): the chapters name themselves with data-chapter / data-n (the .sec-head rows left the pages; §01
    # Mission left Company). hc14 (company, the director's 4.3): the heading-only §04 "Where the work is" left; its line
    # stands whole in §01 as the chapter's one line, right after the story's heading, so three chapters now and the
    # page still says where the work goes next. hc15 (company, the director's 4.3): "How we build" (dark) moved between the
    # story and the team, so the page alternates dark, paper-2, dark, paper and its close arrives from paper: why, how, who
    ch = await pg.evaluate("[...document.querySelectorAll('main section[data-chapter]')].map(s => s.dataset.n + ' ' + s.dataset.chapter)")
    assert ch == ["01 The story so far", "02 How we build", "03 The team"], ("company chapters", ch)
    # hc15 (the same item): the grounds alternate, so no two dark bands touch and the close ("Put us to work.") arrives
    # from paper, as on the other pages (read from the computed grounds, a transparent band showing the body's)
    tones = await pg.evaluate("""(() => { const lum = (c) => { const m = c.match(/[0-9.]+/g); if (!m || (m.length > 3 && +m[3] === 0)) return null;
      return (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255; };
      const body = lum(getComputedStyle(document.body).backgroundColor);
      return [...document.querySelectorAll('main > section')].map(s => { const l = lum(getComputedStyle(s).backgroundColor); return (l == null ? body : l) < 0.5 ? 'dark' : 'paper'; }); })()""")
    assert len(tones) == 5 and tones[-1] == "dark" and tones[-2] == "paper" and not any(a == b == "dark" for a, b in zip(tones, tones[1:])), ("company grounds", tones)
    line = await pg.evaluate("(() => { const p = document.querySelector('#story .story-h + p.ch-line'); return p ? p.textContent.replace(/\\s+/g, ' ').trim() : null; })()")
    assert line == "Finance was the proving ground. It will not be the last.", ("company §01: the chapter's line after its heading", line)
    assert await pg.locator(".crew--team > li").count() == 4 and await pg.locator(".crew--advisors > li").count() == 9
    names_team = await pg.locator(".crew--team > li h3").all_inner_texts()
    names_adv = await pg.locator(".crew--advisors > li h3").all_inner_texts()
    # Victor and Subuddh swapped places on 2026-10-02; 2026-10-30: Subuddh Parekh moved from the team to the advisors (owner's request), last (A-09)
    assert names_team == ["Ajit K Dubey", "Dr. Tim Leung", "Mike Lockhart", "Shalabh Choudhri"], names_team
    assert names_adv == ["Kumar Mehta", "Sreeram Kannan", "Dr. Philip Bond", "John Schuster", "Victor Gamolsky", "Abhishek Sinha", "Dr. Julius E. Ekeroma", "Dipit Nanawati", "Subuddh Parekh"], names_adv
    roles = await pg.locator(".crew--advisors > li .role").all_inner_texts()
    assert all(r.upper().startswith("ADVISOR") for r in roles), roles
    assert not any("CHIEF PRODUCT" in r.upper() for r in roles), roles
    # v2x cut (1 Nov): the register codes (T-04, A-05) are gone with the label noise; the order stays pinned by the names
    # above, and no code may come back half-way (a row with a code and a row without)
    assert await pg.locator(".crew .n").count() == 0, await pg.locator(".crew .n").all_inner_texts()
    ajit = await pg.locator(".crew--team > li").first.inner_text()
    assert "Ajit K Dubey" in ajit and not re.search(r"patent|fourteen", ajit, re.I), ajit
    more = pg.locator(".crew--team > li:nth-child(2) details.crew-more")
    assert await more.evaluate("d => !d.open")
    await more.locator("summary").click(); await pg.wait_for_timeout(300)
    assert await more.evaluate("d => d.open && d.querySelector('.crew-bio').innerText.length > 400")
    # the expander's name says whose bio it opens (the visible word is "Bio"; v2x cut)
    bio_name = await more.locator("summary").evaluate(r"s => s.textContent.replace(/\s+/g, ' ').trim()")
    assert bio_name == "Bio of Dr. Tim Leung", ("the bio expander's name", bio_name)
    stats = await pg.locator(".crew-stats").inner_text()
    assert "PATENT" not in stats.upper() and "100+" in stats, stats
    print("company: 4 team + 9 advisors (Subuddh Parekh with the advisors, 30 Oct), 13 portraits (v2x, srcset 160/320/560), one treatment at rest and on hover with the green ring, full descriptions expand ('Bio of <name>'), no patent count, chapters 01-03 with §01's line, no register codes")
    assert await pg.locator('.crew a[href*="scholar.google.com/citations?user=P40aOHIAAAAJ"]').count() == 1
    # v2x tests pass (30 Oct): the CEO's hero, 'Intelligence, put to work.', with 'put to work.' in white italic (the
    # heading's own colour, never the signal green; CLAUDE.md)
    hero = await pg.evaluate("""(() => { const h = document.querySelector('main h1'), em = h && h.querySelector('em'); if (!em) return null;
      const a = getComputedStyle(h), e = getComputedStyle(em); return { text: h.textContent.replace(/\\s+/g, ' ').trim(), h: a.color, em: e.color, style: e.fontStyle }; })()""")
    assert hero and hero["text"] == "Intelligence, put to work." and hero["em"] == hero["h"] and hero["style"] == "italic", ("company hero", hero)
    # lab (31 Oct): §03 draws its idea, one loop of gates and the four constants; it runs on screen (a record is written
    # within a pass), has Pause motion, and pointing at a constant marks it. v2x cut, owner's-eye fix (1 Nov): the
    # register codes C-01...C-04 left the list and the plate (label noise); the four constants are their lines, in order,
    # and the plate's own words carry them: pointing at the third lights its label ('Custody'), not the boundary words.
    await pg.evaluate("document.documentElement.style.scrollBehavior = 'auto'; document.querySelector('[data-kplate]').scrollIntoView({ block: 'center', behavior: 'instant' })")
    kp = await pg.evaluate("(() => { const f = document.querySelector('[data-kplate]'); return { codes: (document.querySelector('#constants').textContent.match(/C-0[0-9]/g) || []).length, recs: f.querySelectorAll('.k-recs rect').length, pause: !!f.querySelector('button.figure-motion:not([hidden])'), list: [...document.querySelectorAll('#constants [data-k]')].map(d => d.dataset.k + ':' + d.textContent.replace(/\\s+/g, ' ').trim()) }; })()")
    assert kp["codes"] == 0 and [x.split(":")[0] for x in kp["list"]] == ["c1", "c2", "c3", "c4"] and kp["list"][0] == "c1:Agents decide. Code executes." and kp["recs"] >= 10 and kp["pause"], ("the constants plate", kp)
    first = await pg.evaluate("[...document.querySelectorAll('.k-recs rect')].map(r => r.getAttribute('class')).join()")
    assert await until(pg, f"[...document.querySelectorAll('.k-recs rect')].map(r => r.getAttribute('class')).join() !== {first!r} || document.querySelectorAll('.k-recs rect').length > {kp['recs']}", 12000), "the plate wrote no record"
    await pg.locator('#constants [data-k="c3"]').hover(); await pg.wait_for_timeout(500)
    assert await pg.evaluate("document.querySelector('[data-kplate]').dataset.on") == "c3", "pointing at the third constant did not mark it on the plate"
    # a4 (company): the plate's labels are HTML now (.kl-labs), so their ink is `color`, not the SVG's `fill`
    lit = await pg.evaluate("(() => { const t = document.querySelector('[data-kplate] .k-c3 .kl--box'), r = document.querySelector('[data-kplate] .k-c1 .kl--word'); return t && r ? [getComputedStyle(t).color, getComputedStyle(r).color] : null; })()")
    assert lit and lit[0] != lit[1], ("pointing at the third constant should light 'Custody' on the plate, not the boundary words", lit)
    assert not errs, errs
    await ctx.close()


DISC = """() => { const t = document.getElementById('disclosures'), d = t && t.closest('details'), a = document.activeElement;
  return { open: d ? d.open : null, top: t ? Math.round(t.getBoundingClientRect().top) : null, focus_in: !!t && (a === t || t.contains(a)), vh: innerHeight }; }"""


# (hc14, integrate) at the first paint: does the footer's legal fold exist, and how tall is the footer; and every layout
# shift (no recent input) with its sources, for a reload at a page's foot
FOLD_AT_PAINT = """(() => { window.__fold = null; window.__shifts = [];
  new PerformanceObserver(l => { if (!window.__fold && l.getEntriesByName('first-contentful-paint').length) { const f = document.querySelector('.footer');
    window.__fold = { fold: !!document.querySelector('.footer details.footer-legal'), h: f ? Math.round(f.getBoundingClientRect().height) : null }; } }).observe({ type: 'paint', buffered: true });
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__shifts.push({ t: Math.round(e.startTime), v: e.value,
    src: (e.sources || []).map(x => x.node ? (x.node.className || x.node.nodeName) + '' : null) }); }).observe({ type: 'layout-shift', buffered: true }); })();"""


@check
async def disclosures(b):
    """the legal text is on every page and reachable (v2x tests pass, 30 Oct; CLAUDE.md: the disclosures in every
    footer): with JavaScript each page folds #disclosures into a closed 'Legal & disclosures' <details> in its footer;
    Proof's 'See the disclosures.' (a link to #disclosures), clicked at 1440 and tapped on a 390 phone, and a direct load
    of evidence.html#disclosures open the fold, bring the text into view and move focus into it (site.js; G-11).
    (hc14, integrate) the fold is there at the first paint on every page, also where site.js starts after the paint
    (afterpaint.js / home.js make it), so the footer never changes height after it (it took ~190 px out of the footer and
    moved the foot of a page reloaded there); and Trust (an after-paint page) reloaded at its foot at 1440 does not move"""
    errs = []
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script(FOLD_AT_PAINT)
    pg = await ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    folds, early = {}, {}
    for name in PAGES:
        await pg.goto(f"{BASE}/{name}.html", wait_until="load")
        await until(pg, "!!document.querySelector('.footer details.footer-legal #disclosures')", 15000)
        folds[name] = await pg.evaluate("""(() => { const d = document.querySelector('.footer details.footer-legal'), s = d && d.querySelector(':scope > summary');
          return d ? { closed: !d.open, summary: s ? s.textContent.trim() : null, text: (d.querySelector('#disclosures') || {}).textContent || '' } : null; })()""")
        await until(pg, "!!window.__fold", 5000); await pg.wait_for_timeout(1500)
        early[name] = await pg.evaluate("(() => { const f = document.querySelector('.footer'); return Object.assign({}, window.__fold, { rest: f ? Math.round(f.getBoundingClientRect().height) : null }); })()")
    bad = {k: v and {kk: vv for kk, vv in v.items() if kk != "text"} for k, v in folds.items()
           if not v or not v["closed"] or v["summary"] != "Legal & disclosures" or "Rule 506(c) of Regulation D" not in v["text"]}
    assert not bad, ("footer fold", bad)
    late = {k: v for k, v in early.items() if not v.get("fold") or v.get("h") != v.get("rest")}
    assert not late, ("the footer's fold must exist at the first paint and the footer keep its height after it (1440)", late)
    # Trust reloaded at its foot (the browser restores the place; site.js comes after the paint there): nothing shifts
    await pg.goto(f"{BASE}/trust.html", wait_until="load"); await pg.wait_for_timeout(2500)
    await pg.evaluate("scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })"); await pg.wait_for_timeout(1400)
    await pg.mouse.move(3, 300)
    await pg.reload(wait_until="load"); await pg.wait_for_timeout(3000)
    foot = await pg.evaluate("({ y: scrollY, max: document.documentElement.scrollHeight - innerHeight, shifts: window.__shifts })")
    assert foot["y"] >= foot["max"] - 2 and sum(x["v"] for x in foot["shifts"]) <= 0.001, ("trust.html@1440x900 reloaded at its foot: layout shifts", foot)
    await ctx.close()
    seen = {}
    for w, mode in ((1440, "click"), (390, "tap"), (1440, "direct"), (390, "direct")):
        phone = w == 390
        ctx = await b.new_context(viewport={"width": w, "height": 900 if not phone else 844}, has_touch=phone, is_mobile=phone, device_scale_factor=2 if phone else 1)
        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/evidence.html" + ("#disclosures" if mode == "direct" else ""), wait_until="load")
        await until(pg, "!!document.querySelector('.footer details.footer-legal')", 15000)
        if mode != "direct":
            link = pg.locator('main a[href="#disclosures"]').first
            await expect(link).to_have_text(re.compile(r"disclosures", re.I))
            await link.scroll_into_view_if_needed(); await pg.wait_for_timeout(500)  # a click in the same moment as the scroll is not followed
            await (link.tap() if mode == "tap" else link.click())
        # the page may still be scrolling (smooth scroll) when the fold opens and focus moves: wait for all three
        await until(pg, f"(r => r.open && r.focus_in && r.top >= 0 && r.top < r.vh)(({DISC})())", 8000)
        r, t_w = await pg.evaluate(DISC), time.monotonic()
        while time.monotonic() - t_w < 8:  # then where it comes to rest: two equal reads 250 ms apart
            await pg.wait_for_timeout(250)
            r2 = await pg.evaluate(DISC)
            if r2["top"] == r["top"]: break
            r = r2
        seen[f"{mode}@{w}"] = r
        assert r["open"] and r["focus_in"] and 0 <= r["top"] <= r["vh"] - 48, (f"{mode} at {w}: the fold must open, the text come to rest in view (its first lines) and focus move into it", r)
        await ctx.close()
    assert not errs, errs
    print(f"disclosures: {len(folds)} pages fold the legal text into a closed 'Legal & disclosures', there at the first paint (the footer's height held); Trust reloaded at its foot moves nothing; Proof's link (click 1440, tap 390) and a direct "
          f"load open it, the text in view (top {', '.join(str(v['top']) for v in seen.values())}) and focus inside")


@check
async def blog(b):
    """blog: the hash deep link lands on its collection, the featured series, 29 cards, the scholar link; a series post
    names its part and links back to the series. (v2x cut, 1 Nov: the filter chips and the post's side list of the
    series left the pages by design, so /blog/#markets is a jump to Markets with all three collections shown, and a
    series post says 'The Gen-AI series · Part N' in its crumb instead of marking a side list.)"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/blog/index.html#markets", wait_until="load")
    await pg.wait_for_timeout(900)
    shown = await pg.evaluate("[...document.querySelectorAll('[data-blog-collection]')].filter(s => !s.hidden && s.getClientRects().length > 0).map(s => s.id)")
    assert sorted(shown) == ["ai", "economics", "markets"], shown
    land = await pg.evaluate("(() => { const r = document.getElementById('markets').getBoundingClientRect(); return { top: Math.round(r.top), vh: innerHeight }; })()")
    assert -2 <= land["top"] < land["vh"] / 2, ("/blog/#markets did not land on Markets", land)
    assert await pg.locator("#munis").count() == 0
    assert await pg.locator(".blog-chips").count() == 0  # no filter row came back half-way (its script is not loaded)
    cards = await pg.locator(".blog-card").count()
    assert cards == 29, cards
    assert await pg.locator('#markets a[href*="scholar.google.com"]').count() == 1
    assert await pg.locator("#series .series-card").count() == 4
    await pg.goto(f"{BASE}/blog/rel-val-a-new-approach-to-relative-value-analysis-of-securities-and-cryptocurrencies.html", wait_until="load")
    crumb = await pg.evaluate("(() => { const c = document.querySelector('.post-crumb'); return c ? { text: c.textContent.replace(/\\s+/g, ' ').trim(), series: !!c.querySelector('a[href=\"index.html#series\"]') } : null; })()")
    assert crumb and crumb["series"] and crumb["text"].endswith("Part 1"), ("the series post's crumb", crumb)
    print(f"blog: {cards} cards in 3 collections, #markets lands on Markets, the Gen-AI series (4 parts), scholar link present; a series post names its part and links to the series")
    assert not errs, errs
    await ctx.close()


@check
async def resolution(b):
    """canvases render at device resolution (2x here), within the UHD budget.
    hc30r (COMP-1, RES-1; integrate, standing in for tests, on company's and research's requests; TESTS.md section 53):
    Company's hero dropped its figure.js stage (`[data-figure] canvas` found nothing there) and figure.js draws lattices
    on a 2D canvas, so the figure clause reads the two figure canvases the site has now: Company's hero
    (#company-figure canvas, company-hero.js) and the research index's plate (#research-figure canvas, figure.js). The
    principle is the same and held tighter: each canvas's bitmap is its box in device pixels, in width and in height
    (within 1; it was the width within 2)."""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    pg = await ctx.new_page()
    await pg.goto(f"{BASE}/index.html", wait_until="load")
    await pg.wait_for_timeout(3000)
    story = await pg.evaluate("(c => ({w: c.width, cw: c.clientWidth}))(document.querySelector('canvas'))")
    assert story["w"] == story["cw"] * 2, story
    figs = []
    for path, sel in (("company.html", "#company-figure canvas"), ("research.html", "#research-figure canvas")):
        await pg.goto(f"{BASE}/{path}", wait_until="load")
        await pg.wait_for_timeout(2500)
        f = await pg.evaluate("(sel) => [...document.querySelectorAll(sel)].map(c => { const r = c.getBoundingClientRect(); return {w: c.width, h: c.height, bw: +(r.width * devicePixelRatio).toFixed(2), bh: +(r.height * devicePixelRatio).toFixed(2), cw: Math.round(r.width)}; })", sel)
        assert len(f) == 1 and f[0]["w"] > 0 and abs(f[0]["w"] - f[0]["bw"]) <= 1 and abs(f[0]["h"] - f[0]["bh"]) <= 1, (path, sel, "the canvas's bitmap is not its box in device pixels", f)
        figs += f
    print(f"resolution: story canvas {story['w']}px for {story['cw']}css px; figures {[(f['cw'], f['w'], f['h']) for f in figs]}")
    await ctx.close()


# a2 (system's request): the draw-ins rest whole at any scale. Every [pathLength] element shown at rest, after the page
# has been scrolled through (each reveal drawn) and the 404's walk waited out: its stroke-dasharray, its vector-effect and
# its on-screen scale (getScreenCTM). From award/a2-design/dashprobe.py and work/system-a2/dashprobe_a2.py.
DRAW_REST = r"""async () => {
  const H = document.documentElement.scrollHeight;
  for (let y = 0; y < H; y += innerHeight * .6) { scrollTo(0, y); await new Promise(r => setTimeout(r, 250)); }
  scrollTo(0, H); await new Promise(r => setTimeout(r, 3500));
  const out = { n: 0, ns: 0, bad: [] };
  document.querySelectorAll('[pathLength]').forEach(e => {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return;
    const m = e.getScreenCTM(); if (!m) return;
    // at rest = after its draw: a band that left the screen pauses its draw-in mid-line (site.css .is-offscreen), so
    // finish the element's own animations and read the style it keeps
    e.getAnimations().forEach(a => { try { a.finish(); } catch (_) {} });
    out.n++;
    if (cs.vectorEffect !== 'non-scaling-stroke') return;
    out.ns++;
    const sc = Math.hypot(m.a, m.b);
    if (cs.strokeDasharray !== 'none' && sc > 1.01) out.bad.push([e.getAttribute('class') || e.tagName, +sc.toFixed(2), cs.strokeDasharray, cs.animationName]);
  });
  return out;
}"""
# hc13r (integrate; home's HOME-1): Home's drawn trace was Proof's chart in its §03, which left Home; Proof is read where
# that chart draws now, and Home is still read (a [pathLength] it draws again is held to the rule) without requiring one
DRAW_MAY_BE_EMPTY = {"Home"}
DRAW_PAGES = [("index.html", "Home"), ("evidence.html", "Proof"), ("platform.html", "Platform"), ("lifecycles.html", "Lifecycles"), ("blog/index.html", "the blog"),
              ("this-page-does-not-exist", "the 404")]


@check
async def draw_rest(b):
    """a2 (system's request; the 4K bar: a line is whole at any width): at 1440, 2048, 2560 and 3840 (16:9), on Home,
    Platform, Lifecycles, the blog index and the 404, once the page has been scrolled through and every draw-in has had
    3.5 s to finish (an element's own animations are then finished: a band that leaves the screen pauses its draw-in
    mid-line), no [pathLength] element whose stroke is non-scaling and which is drawn above 1:1 rests with a
    stroke-dasharray (a dash sized for the 1920 drawing stopped the line at 1/scale of its length above 1920). Never
    vacuous: [pathLength] elements are read on every page, and non-scaling ones above 1:1 at 2560 and 3840. hc13r: Proof
    is read too (the chart Home drew in §03 draws only there now); Home is still read but may draw none."""
    bad, seen, wide = [], 0, 0
    for w in (1440, 2048, 2560, 3840):
        h = round(w * 9 / 16)
        for path, label in DRAW_PAGES:
            ctx, pg = await open_page(b, path, w, h, loaded=path != "this-page-does-not-exist")
            r = await pg.evaluate(DRAW_REST)
            await ctx.close()
            seen += r["n"]
            if w >= 2560: wide += r["ns"]
            if not r["n"] and label not in DRAW_MAY_BE_EMPTY: bad.append(f"{label}@{w}: no [pathLength] element read")
            bad += [f"{label}@{w}: .{c} at scale {sc} rests with stroke-dasharray {da} (animation {an})" for c, sc, da, an in r["bad"][:6]]
    assert seen and wide, f"draw_rest: vacuous ({seen} [pathLength] elements read, {wide} non-scaling at 2560/3840)"
    assert not bad, f"draw_rest: {len(bad)} problems:\n  " + "\n  ".join(bad[:20])
    print(f"draw_rest: {seen} [pathLength] elements read over {len(DRAW_PAGES)} pages at 1440/2048/2560/3840 ({wide} non-scaling at 2560+), every one at rest whole")


NAV_H = """(() => { const v = getComputedStyle(document.documentElement).getPropertyValue('--nav-h'), n = document.querySelector('header.nav, .nav');
  return { raw: v.trim(), px: parseFloat(v), bar: n ? Math.round(n.getBoundingClientRect().height * 100) / 100 : null }; })()"""


@check
async def nav_h_px(b):
    """a2 (home's request): every script reads the bar's height as parseFloat(getComputedStyle(root).getPropertyValue(
    '--nav-h')). Above 1920 the wide step sets it in rem, and an unregistered custom property's computed value is its
    token ("4.5rem" read as 4.5 px against a 144 px bar at 3840). site.css registers it as a <length>, so the value read
    is resolved: at 3840x2160, 2560x1440, 1440x900 and 390x844, on Home, Lifecycles and Trust, the number read equals the
    bar's height within 0.5 px."""
    bad, n = [], 0
    for w, h in ((3840, 2160), (2560, 1440), (1440, 900), (390, 844)):
        for path in ("index.html", "lifecycles.html", "trust.html"):
            ctx, pg = await open_page(b, path, w, h, loaded=False)
            r = await pg.evaluate(NAV_H)
            await ctx.close()
            n += 1
            if r["bar"] is None or not (abs(r["px"] - r["bar"]) <= 0.5): bad.append(f"{path}@{w}x{h}: --nav-h reads {r['raw']!r} ({r['px']}), the bar is {r['bar']} px")
    assert n == 12 and not bad, "nav_h_px:\n  " + "\n  ".join(bad)
    print(f"nav_h_px: --nav-h reads the bar's height in px on {n} page/width pairs (3840, 2560, 1440, 390)")


# a3 (system's request, the 4K inspector's dom.py): hairlines at device pixels. Every CSS border drawn in the bar, <main>
# and the footer, on every page, in device px; and the arrows' and carets' non-scaling strokes (--icon-stroke).
CRISP_BORDERS = r"""() => {
  const dpr = devicePixelRatio, wide = dpr * innerWidth >= 2880, out = {n: 0, frac: [], one: []};
  for (const el of document.querySelectorAll('header.nav, header.nav *, main, main *, footer, footer *')) {
    const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1) continue;
    for (const s of ['Top', 'Bottom', 'Left', 'Right']) {
      const w = parseFloat(cs['border' + s + 'Width']);
      if (!(w > 0) || cs['border' + s + 'Style'] === 'none' || /rgba\(0, 0, 0, 0\)|transparent/.test(cs['border' + s + 'Color'])) continue;
      out.n++;
      const d = w * dpr, k = (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : el.tagName.toLowerCase()).slice(0, 48) + ' ' + s.toLowerCase();
      if (Math.abs(d - Math.round(d)) > 0.02) out.frac.push(k + ' ' + d.toFixed(2) + ' dpx');
      else if (wide && Math.round(d) < 2) out.one.push(k + ' ' + d.toFixed(2) + ' dpx');
    }
  }
  out.arrows = [...document.querySelectorAll('.arr path, .nav-ch-caret path, .nav-ch-top svg path')].filter(p => p.getClientRects().length).map(p => getComputedStyle(p).strokeWidth);
  // a4: the shift that puts an even-sized arrow's shaft (y 8 of 16) on whole device rows (.arr down, Back to top's across)
  const off = (e, i) => { const t = getComputedStyle(e).translate; if (!t || t === 'none') return 0; const v = t.split(' ').map(parseFloat); return v[i] || 0; };
  out.shifts = [...[...document.querySelectorAll('.arr')].filter(e => e.getClientRects().length).map(e => off(e, 1)),
                ...[...document.querySelectorAll('.nav-ch-top svg')].filter(e => e.getClientRects().length).map(e => off(e, 0))].map(v => +v.toFixed(3));
  return out;
}"""
CRISP_PAGES = ["index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "research.html",
               "research/09-lifecycle-01-ten-sessions.html", "company.html", "access.html", "blog/index.html",
               "blog/in-search-gen-ai-business-model.html", "this-page-does-not-exist"]


@check
async def crisp_4k(b):
    """a3 (system's request; the 4K bar: hairlines at device pixels). On all twelve page kinds at 1440x900@1, 3840x2160@1
    and 1920x1080@2: every CSS border drawn in the bar, <main> and the footer is a whole number of device pixels, and at
    3840 and 1920@2 none is a single device pixel (the 1920 page doubled: a 1 px hairline is 2); the arrows', the
    readout caret's and Back to top's non-scaling strokes compute --icon-stroke on whole device pixels: 1 px at 1440@1,
    2 px at 3840@1 (1440's doubled), 1 px (2 device px) at 1920@2 (a4: was a3's 3 / 1.5 px); and each arrow sits on whole
    device rows: an odd device-px stroke (1440@1) is shifted half a pixel (--icon-shift .5 px: the shaft of an even-sized
    arrow on one row), an even one (3840@1, 1920@2) is not shifted. Never vacuous: borders and arrows are read on every
    page at every size."""
    want = {(1440, 1): "1px", (3840, 1): "2px", (1920, 2): "1px"}
    shift = {(1440, 1): 0.5, (3840, 1): 0.0, (1920, 2): 0.0}
    bad, nb, na, ns = [], 0, 0, 0
    for (w, dpr), stroke in want.items():
        h = round(w * 9 / 16) if w != 1440 else 900
        for path in CRISP_PAGES:
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, loaded=path != "this-page-does-not-exist")
            r = await pg.evaluate(CRISP_BORDERS)
            await ctx.close()
            nb += r["n"]; na += len(r["arrows"])
            if not r["n"]: bad.append(f"{path}@{w}x{dpr}: no border read")
            bad += [f"{path}@{w}x{dpr}: fractional border {x}" for x in r["frac"][:4]]
            bad += [f"{path}@{w}x{dpr}: a one-device-pixel border at 4K {x}" for x in r["one"][:4]]
            odd = sorted(set(r["arrows"]) - {stroke})
            if odd: bad.append(f"{path}@{w}x{dpr}: arrow strokes {odd}, want {stroke}")
            ns += len(r["shifts"])
            off = sorted(set(x for x in r["shifts"] if abs(x - shift[(w, dpr)]) > 0.01))
            if off: bad.append(f"{path}@{w}x{dpr}: arrow shifts {off} px, want {shift[(w, dpr)]} (the shaft on whole device rows)")
    assert nb and na and ns, f"crisp_4k: vacuous ({nb} borders, {na} arrow strokes, {ns} arrow shifts read)"
    assert not bad, f"crisp_4k: {len(bad)} problems:\n  " + "\n  ".join(bad[:24])
    print(f"crisp_4k: {nb} CSS borders on 12 pages at 1440@1, 3840@1 and 1920@2 at whole device pixels (none single at 4K); {na} arrow strokes on --icon-stroke; {ns} arrows on whole device rows")


# a4 (system's optional request; a4-dev item 1): browser zoom on wide screens. A monitor of M screen points at zoom z is a
# CSS window of M/z at devicePixelRatio z (scale 1); Chromium reports outerWidth in screen points (emulated here).
ZOOM_READ = r"""() => { const p = [...document.querySelectorAll('main p')].find(e => e.getClientRects().length && getComputedStyle(e).fontFamily.includes('Inter'));
  return { uz: document.documentElement.classList.contains('uz'), body: p ? parseFloat(getComputedStyle(p).fontSize) * devicePixelRatio : 0,
           sw: document.documentElement.scrollWidth - innerWidth }; }"""


@check
async def zoom_wide(b):
    """a4 (system; WCAG 1.4.4 above 1920): a browser zoom step enlarges the page on a wide screen. At 200 % on a 2560 and a
    3840 monitor, body text is at least 1.9x its size at 100 % in device pixels and html.uz is set; at 100 % html.uz is
    absent; a side panel (2560 window, 2200 page at 1x) and docked developer tools (2560 / 1800 at 2x) never read as a
    zoom. No sideways scroll in any case. Platform and a blog post (the plate pages' and the prose template's root)."""
    cases = [("2560@100%", 2560, 2560, 1, False), ("2560@200%", 2560, 1280, 2, True), ("3840@100%", 3840, 3840, 1, False),
             ("3840@200%", 3840, 1920, 2, True), ("side panel", 2560, 2200, 1, False), ("devtools 2x", 2560, 1800, 2, False)]
    bad, n, ratios = [], 0, []
    for path in ["platform.html", "blog/in-search-gen-ai-business-model.html"]:
        got = {}
        for name, mon, w, dpr, zoomed in cases:
            ctx, pg = await open_page(b, path, w, round(w * 9 / 16), dpr=dpr, reduced=True,
                                      init=f"Object.defineProperty(window, 'outerWidth', {{ get: () => {mon} }});")
            r = got[name] = await pg.evaluate(ZOOM_READ)
            await ctx.close(); n += 1
            if not r["body"]: bad.append(f"{path} {name}: no body paragraph read")
            if r["uz"] != zoomed: bad.append(f"{path} {name}: html.uz {r['uz']}, want {zoomed}")
            if r["sw"] > 1: bad.append(f"{path} {name}: scrolls sideways by {r['sw']} px")
        for mon in (2560, 3840):
            a, z = got[f"{mon}@100%"]["body"], got[f"{mon}@200%"]["body"]
            if a: ratios.append(f"{path.split('/')[-1].split('.')[0][:12]} {mon} {z / a:.2f}x")
            if not (a and round(z / a, 2) >= 1.9): bad.append(f"{path} {mon}: body text {a:.1f} -> {z:.1f} device px at 200 % (want >= 1.9x)")  # (the ratio to 2 places: 45.6 / 24 is 1.9)
    assert not bad, "zoom_wide:\n  " + "\n  ".join(bad)
    print(f"zoom_wide: {n} windows; 200 % on 2560 and 3840 enlarges body text >= 1.9x (html.uz; {', '.join(ratios)}); 100 %, a side panel and docked devtools read no zoom; no sideways scroll")

READOUT_END = r"""async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const nav = document.querySelector('header.nav'), navH = nav.getBoundingClientRect().height, line = navH + (innerHeight - navH) * 0.3;
  const band = document.querySelector('main .cta-band');
  let last = band && band.previousElementSibling; while (last && last.tagName !== 'SECTION') last = last.previousElementSibling;
  if (!document.querySelector('.nav-ch-btn') || !last || !band) return null;
  const at = async y => { scrollTo({top: y, behavior: 'instant'}); await wait(450); dispatchEvent(new Event('scroll')); await wait(350);
    const b = document.querySelector('.nav-ch-btn'); return {intro: b.classList.contains('is-intro'), txt: (b.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40)}; };
  const lr = last.getBoundingClientRect();
  const inLast = await at(scrollY + lr.top + Math.min(lr.height * .5, 300) - line);
  const inBand = await at(scrollY + band.getBoundingClientRect().top + 40 - line);
  return {inLast, inBand, last: last.id};
}"""


@check
async def readout_end(b):
    """a3 (system's request): past the last chapter the bar's readout shows the wordmark only (it named the wrong place
    over the closing band). On Home, Platform, Lifecycles, Proof, Trust, Company and Research at 1440x900 and 3840x2160:
    with the reading line inside the last chapter the readout names it (.nav-ch-btn without .is-intro, text shown), and
    with the closing band at the reading line it is .is-intro and empty."""
    bad, n = [], 0
    for w, h in ((1440, 900), (3840, 2160)):
        for path in ("index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "company.html", "research.html"):
            ctx, pg = await open_page(b, path, w, h, reduced=True)
            r = await pg.evaluate(READOUT_END)
            await ctx.close()
            if not r: bad.append(f"{path}@{w}: no readout, last chapter or closing band"); continue
            n += 1
            if r["inLast"]["intro"] or not r["inLast"]["txt"]: bad.append(f"{path}@{w}: in its last chapter (#{r['last']}) the readout shows {r['inLast']}")
            if not r["inBand"]["intro"] or r["inBand"]["txt"]: bad.append(f"{path}@{w}: over the closing band the readout shows {r['inBand']}")
    assert n == 14 and not bad, "readout_end:\n  " + "\n  ".join(bad)
    print(f"readout_end: on 7 pages at 1440 and 3840 the readout names the last chapter and shows the wordmark only over the closing band")


DEEP_OFF = """(id => { const el = document.getElementById(id), sp = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
  return el ? Math.round(el.getBoundingClientRect().top - sp) : null; })"""
# award budgets (integrate): every scroll position the page passes through, and where it stood at its first paint
DEEP_GLIDE = """(() => { window.__sc = []; window.__fcp = null;
  addEventListener('scroll', () => window.__sc.push(Math.round(scrollY)), { passive: true });
  new PerformanceObserver(l => l.getEntries().forEach(e => { if (e.name === 'first-contentful-paint') window.__fcp = Math.round(scrollY); }))
    .observe({ type: 'paint', buffered: true }); })();"""
# pages whose scripts start after the first paint (afterpaint.js), one deep link each
DEEP_AFTER_PAINT = (("lifecycles.html", "desk"), ("trust.html", "ledger"), ("research.html", "series"), ("blog/index.html", "series"))


@check
async def deep_links(b):
    """v2x r1 (qa-hostile S2, qa-firefox D3): a link lands where it points and no address can break the page's script.
    /#lc01 and /#governance at 390x844 (touch) and 1440x900, no input: once the page has had 6 s to land, the target's top
    comes to within 2 px of scroll-padding-top and stays there for four samples 0.75 s apart (v2's site.js read the
    overture's own scrolling as the reader's and stopped 3,355 px past or 535 px short). /platform#%E0%A4%A and /#% (a
    malformed escape threw URIError and stopped site.js) load with no page error, and the footer's clocks and legal fold,
    which site.js builds, exist.
    award budgets (integrate): on the pages that start their scripts after the first paint (Lifecycles, Trust, Research,
    the blog index) a deep link lands at once, not in a glide from the top: at 1440x900 every scroll position the page
    passes through, and its position at the first paint, are within 40 px of where it settles; the target's top within
    2 px of scroll-padding-top; and once site.js has run, html scrolls smoothly again (an in-page link still glides).
    (site.css: scroll-behavior auto until html.is-loaded; before it, the browser's own fragment scroll ran under smooth
    and the page painted at 172 px of Lifecycles' 2,527 and slid there.)"""
    bad, got = [], []
    for path, hid in DEEP_AFTER_PAINT:
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script(DEEP_GLIDE)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/{path}#{hid}", wait_until="load")
        loaded = await until(pg, "document.documentElement.classList.contains('is-loaded')", 8000)
        await pg.wait_for_timeout(1500)
        r = await pg.evaluate(f"""(() => ({{ y: Math.round(scrollY), sc: window.__sc, fcp: window.__fcp, off: {DEEP_OFF}({hid!r}),
          sb: getComputedStyle(document.documentElement).scrollBehavior }}))()""")
        far = [y for y in r["sc"] if abs(y - r["y"]) > 40]
        if far or r["fcp"] is None or abs(r["fcp"] - r["y"]) > 40:
            bad.append(f"{path}#{hid}@1440: a glide: scroll positions {r['sc'][:8]} (settled {r['y']}), first paint at {r['fcp']} (within 40 px of the settled position wanted)")
        if r["off"] is None or abs(r["off"]) > 2: bad.append(f"{path}#{hid}@1440: the target's top against scroll-padding-top {r['off']} px (within 2 wanted)")
        if not loaded or r["sb"] != "smooth": bad.append(f"{path}#{hid}@1440: after site.js (is-loaded {bool(loaded)}) html's scroll-behavior is {r['sb']!r}, want 'smooth'")
        if errs: bad.append(f"{path}#{hid}@1440: page errors {errs[:2]}")
        got.append(f"{path.split('.')[0]}#{hid} {r['off']}")
        await ctx.close()
    for w, h, touch in ((390, 844, True), (1440, 900, False)):
        for hid in ("lc01", "governance"):
            ctx = await b.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(f"{BASE}/index.html#{hid}", wait_until="commit")
            await pg.wait_for_timeout(6000)
            off = None
            for _ in range(40):  # it may still be landing on a slow machine: wait for it (up to 10 s more), then it must stay
                off = await pg.evaluate(f"{DEEP_OFF}({hid!r})")
                if off is not None and abs(off) <= 2: break
                await pg.wait_for_timeout(250)
            seq = [off]
            for _ in range(4):
                await pg.wait_for_timeout(750); seq.append(await pg.evaluate(f"{DEEP_OFF}({hid!r})"))
            if any(v is None or abs(v) > 2 for v in seq): bad.append(f"index.html#{hid}@{w}x{h}: the target's top against scroll-padding-top {seq} (px; within 2 wanted, and staying)")
            if errs: bad.append(f"index.html#{hid}@{w}x{h}: page errors {errs[:2]}")
            got.append(f"#{hid}@{w} {seq[-1]}")
            await ctx.close()
    for path in ("platform.html#%E0%A4%A", "index.html#%"):
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        pg = await ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(f"{BASE}/{path}", wait_until="load")
        ok = await until(pg, "!!document.querySelector('.footer .clocks') && !!document.querySelector('.footer-legal')", 8000)
        if errs or not ok: bad.append(f"{path}@390: page errors {errs[:2]}; footer clocks and legal fold built: {bool(ok)}")
        await ctx.close()
    assert not bad, "deep_links:\n  " + "\n  ".join(bad)
    print(f"deep_links: the after-paint pages' deep links paint at their target, no glide, and Home's land under the bar and stay ({'; '.join(got)} px); two malformed addresses load with site.js running (clocks, legal fold) and no page error")


@check
async def overture_net(b):
    """v2x r1 (qa-hostile S7): a failed overture engine leaves a readable page at once. With assets/js/story.js aborted,
    html.story-failed is set and the overture's stage is no longer pinned (.story-stage position: relative) within 1.5 s
    of 'load' (x the CPU throttle), at 390 and 1440: no waiting for the safety net's clock (20 s while story.js is
    expected) and no pinned dark screen."""
    bad = []
    limit = int(1500 * max(1.0, MODE["throttle"]))
    for w, h, touch in ((390, 844, True), (1440, 900, False)):
        ctx = await b.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
        pg = await ctx.new_page()
        # path-agnostic (a3): the deploy copy (tools/build_deploy.py) serves it at /assets/v/<hash>/js/story.js
        await pg.route("**/js/story.js*", lambda r: r.abort())
        await pg.goto(f"{BASE}/index.html", wait_until="load")
        ok = await until(pg, "document.documentElement.classList.contains('story-failed') && getComputedStyle(document.querySelector('.story-stage')).position === 'relative'", limit)
        if not ok:
            st = await pg.evaluate("({ cls: document.documentElement.className, pos: getComputedStyle(document.querySelector('.story-stage')).position })")
            bad.append(f"index.html@{w}x{h} with story.js aborted: not static within {limit} ms of load: {st}")
        await ctx.close()
    assert not bad, "overture_net:\n  " + "\n  ".join(bad)
    print(f"overture_net: with story.js aborted the overture is static (html.story-failed, stage unpinned) within {limit} ms of load at 390 and 1440")


@check
async def phone(b):
    """phone: the explorer is an accordion (hc5: on Platform §01, its one page), Home's lab (§02 since hc11, when the still
    stack plate left Home) is drawn inside the 390 px page, a chapter lands under the 64 px bar, the menu sheet is a popover
    over an inert page"""
    # v2x r3: open_page, not 'loader detached': since home r3 the instruments are added as the curtain lifts, so at CI
    # speed arch.js had not built `#stack .arch` yet when the loader left (TypeError on null); open_page waits until
    # every script home.js lists has run
    errs = []
    ctx, pg = await open_page(b, "index.html", 390, 844, errs=errs)
    await pg.locator(".loader").wait_for(state="detached", timeout=15000)
    # hc11: Home's first chapter drawing after the overture's lifecycles is the swarm lab (#lc01; the still plate left)
    await pg.evaluate("document.querySelector('#lc01').scrollIntoView({block: 'center', behavior: 'instant'})")
    await expect(pg.locator("#lc01 [data-swarm-live]")).to_be_visible()
    assert await pg.evaluate("document.documentElement.scrollWidth") == 390
    await pg.locator(".nav-toggle").click()  # v2x cut (1 Nov): on phones the toggle opens the sheet; its first items are the chapters
    # a4 (system): the sheet names this page's chapters ("On this page", the list labelled by it) and numbers them, so
    # they never read as the site's pages below them
    await pg.locator("#site-menu .nav-ch-head").wait_for(state="visible", timeout=3000)
    sheet = await pg.evaluate("""(() => { const h = document.querySelector('#site-menu .nav-ch-head'), l = document.querySelector('#site-menu .nav-ch-list');
      const ns = [...l.querySelectorAll('a .n')].filter(n => n.getClientRects().length && getComputedStyle(n).visibility !== 'hidden' && n.textContent.trim());
      return { head: h.textContent.trim(), by: l.getAttribute('aria-labelledby') === h.id, links: l.querySelectorAll('a').length, nums: ns.map(n => n.textContent.trim()) }; })()""")
    assert sheet["head"] == "On this page" and sheet["by"] and sheet["links"] >= 3 and len(sheet["nums"]) == sheet["links"], ("390: the sheet's chapter head and numbers", sheet)
    # hc11: by its target; hc13r: #proof left Home, so the chapter after the lab, §03 #economics (Why agents)
    await pg.locator("#site-menu .nav-ch-list a[href='#economics']").click()
    land = await until(pg, "(() => { const t = document.querySelector('#economics').getBoundingClientRect().top, b = document.querySelector('.nav').getBoundingClientRect().bottom; return Math.abs(t - b) <= 2 ? [t, b] : null; })()", 6000)
    assert land, ("the Why agents chapter (#economics) did not land under the bar at 390", await pg.evaluate("[document.querySelector('#economics').getBoundingClientRect().top, document.querySelector('.nav').getBoundingClientRect().bottom]"))
    await pg.locator(".nav-toggle").click()
    assert await until(pg, "document.querySelector('#site-menu').matches(':popover-open') && document.querySelector('main').inert", 3000), "menu sheet did not open"
    await pg.keyboard.press("Escape")
    assert await until(pg, "!document.querySelector('#site-menu').matches(':popover-open') && !document.querySelector('main').inert", 3000), "menu sheet did not close"
    # v2x r1 (system; motion critic r1): Escape pressed on a link inside the sheet (Tab once after opening it) closes the
    # sheet, the page is no longer inert and focus is back on the toggle that opened it
    await pg.locator(".nav-toggle").click()
    assert await until(pg, "document.querySelector('#site-menu').matches(':popover-open')", 3000), "menu sheet did not open a second time"
    await pg.keyboard.press("Tab"); await pg.wait_for_timeout(200)
    inside = await pg.evaluate("(() => { const a = document.activeElement; return a && a.closest('#site-menu') ? a.textContent.trim().slice(0, 30) : null; })()")
    await pg.keyboard.press("Escape")
    back = await until(pg, "!document.querySelector('#site-menu').matches(':popover-open') && !document.querySelector('main').inert && document.activeElement === document.querySelector('.nav-toggle')", 3000)
    assert inside and back, ("Escape from a link inside the sheet", inside, await pg.evaluate("({ open: document.querySelector('#site-menu').matches(':popover-open'), inert: document.querySelector('main').inert, focus: document.activeElement.className })"))
    # v2x r3 (system; r3-mobile minor): every footer list link answers a tap over at least 32 px of height (site.css
    # widens the hit area 5 px above and below without changing the look); read with elementFromPoint at 390
    foot = await pg.evaluate(FOOT_HIT)
    short = [x for x in foot if x["span"] < 32]
    assert foot and not short, ("390: footer links that answer over less than 32 px (text, box height, span)", short, len(foot))
    await ctx.close()
    # hc5 (integrate): the explorer's accordion at 390, on Platform §01 (it ran on Home §02 until HC5 item 1): layer 04's
    # panel opens inline, right after its heading, and nothing overflows the phone
    ctx, pg = await open_page(b, "platform.html", 390, 844, errs=errs)
    assert await until(pg, "!!document.querySelector('#architecture .arch')", 10000), "390: Platform's explorer (#architecture .arch) was not built"
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-narrow')", 10000), "Platform's explorer not narrow at 390"
    await pg.locator("#arch0-b4").click()
    await expect(pg.locator("#arch0-p4")).to_be_visible()
    assert await pg.evaluate("document.querySelector('#arch0-p4').previousElementSibling === document.querySelectorAll('#architecture h3.arch-h')[3]")
    assert await pg.evaluate("document.documentElement.scrollWidth") == 390
    assert not errs, errs
    await ctx.close()
    print(f"phone: Home's lab drawn inside 390, Platform's explorer accordion opens inline, the sheet's chapters headed \"On this page\" and numbered ({', '.join(sheet['nums'])}), the Why agents chapter lands under the bar, menu sheet opens (page inert) and Escape closes it, also from a link inside it ({inside!r}: focus back on the toggle); "
          f"{len(foot)} footer links answer over >= 32 px (least {min(x['span'] for x in foot)})")


FOOT_HIT = r"""(async () => { const out = [];
  const links = [...document.querySelectorAll('footer ul li a')].filter(a => { const r = a.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(a).visibility !== 'hidden'; });
  for (const a of links) { a.scrollIntoView({ block: 'center', behavior: 'instant' }); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    const r = a.getBoundingClientRect(), cx = r.left + Math.min(r.width / 2, 12), cy = r.top + r.height / 2;
    const at = y => { const e = document.elementFromPoint(cx, y); return !!e && (e === a || a.contains(e)); };
    let up = 0, dn = 0; while (up < 40 && at(cy - up - 1)) up++; while (dn < 40 && at(cy + dn + 1)) dn++;
    out.push({ t: a.textContent.replace(/\s+/g, ' ').trim().slice(0, 30), h: Math.round(r.height), span: up + dn + 1 }); }
  return out; })()"""


@check
async def reduced_motion(b):
    """reduced motion: the explorer is open and still (hc5: on Platform §01, its one page); Home's swarm lab is a still study with no motion control (until
    the 1 Nov cut: Home's ledger stream started paused; the stream left the site); Trust verifies at once"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"{BASE}/index.html", wait_until="load")
    await pg.locator(".loader").wait_for(state="detached", timeout=15000)
    # v2x cut (1 Nov): Home's running instrument is the swarm lab (the agent log left the page); under reduced motion it is
    # drawn as a still study and offers no Pause motion
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await expect(pg.locator("[data-swarm-live] [data-sw-state]")).to_have_text("Static study")
    await expect(pg.locator("[data-swarm-live] [data-sw-motion]")).to_be_hidden()
    # hc5 (integrate): the explorer runs on Platform §01 only (Home §02 draws its plate, still): open at once, no Pause
    await pg.goto(f"{BASE}/platform.html", wait_until="load")
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-ready')", 1500), "Platform's explorer not open at once under reduced motion"
    await expect(pg.locator("#architecture .arch-motion")).to_be_hidden()
    await pg.goto(f"{BASE}/trust.html", wait_until="load")
    await pg.locator("[data-lt-verify]").click()
    await expect(pg.locator("[data-ledger=replay] [data-lt-state]")).to_contain_text("Verified here · 8 of 8 links hold", timeout=1500)
    assert not errs, errs
    await ctx.close()
    print("reduced motion: explorer open and still (no motion control), the swarm lab a still study (no motion control), Trust verifies at once")


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
             (f", removed at {t_rem:.0f} ms" if t_rem is not None else ", never removed") + f"; {len(samples)} samples" + \
             (f", last visible one at {shown[-1][0]:.0f} ms" if shown else f", the first at {samples[0][0]:.0f} ms ({samples[0][1]})") + \
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
    nj = await pg.evaluate("""(() => { const q = s => document.querySelectorAll(s).length;
      return { loader: getComputedStyle(document.querySelector('.loader')).display, proof: q('.proof-list li'), stream: q('[data-ledger-stream] .lt-rec'),
        chain: q('.chain-list li'), gates: q('[data-sw-gates] li'), bar: getComputedStyle(document.querySelector('.swarm-bar')).display,
        stack: q('#stack'), see: (document.querySelector('.beat-0 .hero-cta a.btn--ghost') || { getAttribute: () => null }).getAttribute('href') }; })()""")
    # v2x cut (1 Nov): each layer of the stack shows its name (the In / Out pairs left the page; the job line is the
    # explorer's, with JavaScript); integrate hc1 (4 Nov): the name alone, no verb column (HC1 item 2: the name says it, as
    # on Platform), so a stray <small> verb fails; the session list is the <noscript> record now, drawn as scripts are off.
    # Owner's-eye fix (1 Nov): Home's agent log left the page (stream 0; it started from four records); the chain stays.
    # hc5 (integrate): Home §02 drew Platform's plate as static markup; hc11: that chapter left Home, and its hero's "See the
    # stack" reaches Platform without JS. The eight layers with the boundary after 04, each name readable, are checked on
    # Platform §01 below (the list is the explorer's, Platform's)
    assert nj["loader"] == "none" and nj["proof"] == 10 and nj["stream"] == 0 and nj["chain"] == 8 and nj["gates"] == 6 and nj["bar"] == "none", nj
    assert nj["stack"] == 0 and nj["see"] == "platform.html", nj
    await pg.locator(".nav-toggle").click()
    assert await pg.evaluate("document.querySelector('#site-menu').matches(':popover-open')"), "menu sheet does not open without JavaScript"
    await pg.goto(f"{BASE}/evidence.html", wait_until="load")
    assert await pg.locator("[data-proof-fig]").is_hidden() and await pg.locator("table[data-proof-table] tbody tr").count() == 10
    await pg.goto(f"{BASE}/trust.html", wait_until="load")
    assert await pg.locator(".lt-rec").count() == 9
    await pg.goto(f"{BASE}/platform.html", wait_until="load")
    pl = await pg.evaluate("""(() => { const kids = [...document.querySelectorAll('#architecture .layers > *')], bi = kids.findIndex(e => e.classList.contains('layer-boundary'));
      return { layers: document.querySelectorAll('#architecture .layers .layer').length, before: bi < 0 ? -1 : kids.slice(0, bi).filter(e => e.classList.contains('layer')).length,
        io: [...document.querySelectorAll('#architecture .layers .layer')].every(l => { const h = l.querySelector('h3');
          return !!h && h.textContent.trim().length > 0 && !h.querySelector('small') && h.getClientRects().length > 0; }) }; })()""")
    assert pl["layers"] == 8 and pl["before"] == 4 and pl["io"], ("platform.html@390 without JavaScript: the eight layers, the boundary after 04, each name shown", pl)
    # v2x r1 (qa-hostile S3): no dead controls without JavaScript: on Lifecycles the desk and its caption are not drawn
    # and its no-JS note is, at 390 here and at 768 below
    DESK_NOJS = "(() => { const d = s => { const e = document.querySelector(s); return e ? getComputedStyle(e).display : null; }; return { desk: d('.desk'), cap: d('.desk-cap'), note: d('.desk-nojs') }; })()"
    await pg.goto(f"{BASE}/lifecycles.html", wait_until="load")
    dn = await pg.evaluate(DESK_NOJS)
    assert dn["desk"] == "none" and dn["cap"] in ("none", None) and dn["note"] not in ("none", None), ("lifecycles.html@390 without JavaScript: the desk", dn)
    c768 = await b.new_context(java_script_enabled=False, viewport={"width": 768, "height": 1024})
    p768 = await c768.new_page(); await p768.goto(f"{BASE}/lifecycles.html", wait_until="load")
    dn768 = await p768.evaluate(DESK_NOJS); await c768.close()
    assert dn768["desk"] == "none" and dn768["cap"] in ("none", None) and dn768["note"] not in ("none", None), ("lifecycles.html@768 without JavaScript: the desk", dn768)
    # v2x tests pass (30 Oct): Access without JavaScript says the form needs it and that nothing was sent (contracts §1.14)
    await pg.goto(f"{BASE}/access.html", wait_until="load")
    await expect(pg.locator("form[data-access] p.form-error", has_text="The request form needs JavaScript to prepare the email. Enable it and reload. Nothing has been submitted.")).to_be_visible()
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
    print(f"fallbacks: readable without JS on every page (sessions list, chain records, Trust's ledger excerpt, six gates, Home's See the stack to Platform, Platform's eight layers with the boundary after 04, menu sheet as a popover, no loader, the desk's note instead of a dead desk at 390 and 768); "
          f"links kept without JS on {len(LINK_PAGES)} pages, research.html lists its {posts} notes")


@check
async def no_webgl(b):
    """no WebGL: the homepage falls back (html.no-webgl), and every page with a figure still shows a complete picture.
    hc30r (RES-1, COMP-1; integrate, standing in for tests, on research's and company's requests; TESTS.md section 53):
    the figures use no WebGL now (figure.js draws lattices on a 2D canvas, a note's hero is its generated still, Company's
    hero is a 2D canvas of its own), so "every figure stage falls back (.no-figure)" would now assert a fault. The
    principle, "a page that cannot draw shows a complete picture", is held in both of its cases. Without WebGL the
    figures are drawn as ever: the index's stage is figure-ready and not no-figure, a note's hero shows its still
    (svg.fs-still, laid out) and is figure-ready, Company's hero is live. Without any canvas context (getContext
    returning null for every kind) the pages fall back whole: the index's stage is no-figure, its shelf is no-plate and
    the list is wider than beside the plate; a note is unchanged (it has no canvas); Company's hero shows its still
    (company.css brings it in 4 s after the page shows where the script has not gone live) and never says it is live."""
    FIGS = r"""(() => { const q = s => document.querySelector(s), on = e => !!e && !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
      const idx = q('#research-figure'), art = q('.article-figure'), co = q('#company-figure'), shelf = q('.rs-shelf'), list = q('.posts-list');
      return { idx: idx && { ready: idx.classList.contains('figure-ready'), none: idx.classList.contains('no-figure'), canvas: on(idx.querySelector('canvas')),
                             noPlate: !!shelf && shelf.classList.contains('no-plate'), listW: list ? Math.round(list.getBoundingClientRect().width) : 0 },
               art: art && { ready: art.classList.contains('figure-ready'), none: art.classList.contains('no-figure'), still: on(art.querySelector('svg.fs-still')), canvas: !!art.querySelector('canvas') },
               co: co && { live: co.classList.contains('is-live'), still: on(co.querySelector('svg.plate-still')), canvas: on(co.querySelector('canvas')) } }; })()"""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script("(() => { const o = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(k, ...a) { return /webgl/.test(k) ? null : o.call(this, k, ...a); }; })();")
    pg = await ctx.new_page()
    await pg.goto(f"{BASE}/index.html", wait_until="load")
    await pg.wait_for_timeout(2500)
    assert await pg.evaluate("document.documentElement.classList.contains('no-webgl')")
    t_shot = asyncio.get_running_loop().time()
    await pg.screenshot(path=str(OUT / "index-nowebgl.png"))
    print(f"no-WebGL homepage screenshot: {asyncio.get_running_loop().time() - t_shot:.1f}s")
    seen = {}
    for name in FIGURE_PAGES:
        await pg.goto(f"{BASE}/{name}.html", wait_until="load")
        await pg.wait_for_timeout(1500)
        st = seen[name] = await pg.evaluate(FIGS)
        if name == "company": assert st["co"] and st["co"]["live"] and st["co"]["canvas"], (name, "without WebGL Company's hero is not live on its 2D canvas", st)
        elif name == "research": assert st["idx"] and st["idx"]["ready"] and not st["idx"]["none"] and st["idx"]["canvas"] and not st["idx"]["noPlate"], (name, "without WebGL the index's plate is not drawn", st)
        else: assert st["art"] and st["art"]["ready"] and not st["art"]["none"] and st["art"]["still"], (name, "without WebGL the note's hero does not show its still", st)
    await pg.screenshot(path=str(OUT / "article-nowebgl.png"))
    await ctx.close()
    # no canvas context of any kind
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script("HTMLCanvasElement.prototype.getContext = function () { return null; };")
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    for name in FIGURE_PAGES:
        await pg.goto(f"{BASE}/{name}.html", wait_until="load")
        await pg.wait_for_timeout(1500)
        st = await pg.evaluate(FIGS)
        if name == "company":
            # the still comes in 4 s after the page shows (company.css: transition: visibility 0s 4s), not before
            for _ in range(40):
                if st["co"] and st["co"]["still"]: break
                await pg.wait_for_timeout(250); st = await pg.evaluate(FIGS)
            assert st["co"] and st["co"]["still"] and not st["co"]["live"], (name, "without a canvas context Company's hero does not show its still", st)
        elif name == "research":
            assert st["idx"] and st["idx"]["none"] and st["idx"]["noPlate"] and not st["idx"]["canvas"], (name, "without a canvas context the index's stage did not fall back (no-figure, the shelf no-plate)", st)
            assert st["idx"]["listW"] > seen[name]["idx"]["listW"], (name, "without its plate the list is no wider than beside it", st["idx"]["listW"], seen[name]["idx"]["listW"])
        else:
            assert st["art"] and st["art"]["still"] and not st["art"]["canvas"] and st["art"] == seen[name]["art"], (name, "a note's hero changed without a canvas context (it has no canvas)", st, seen[name])
    await pg.screenshot(path=str(OUT / "company-nocanvas.png"))
    assert not errs, ("a page threw without a canvas context", errs)
    await ctx.close()
    print("fallbacks: the no-WebGL homepage falls back; without WebGL the figures are drawn (the index's plate, a note's still, Company's hero); without any canvas context the index's stage and shelf fall back, a note keeps its still and Company shows its still")


# ================================================================ round 1 (v2) guards, one per item of the director's list
# ---- counters: never a value other than the final one (NV1, PF1, SW3, PG10; D13)
COUNT_ROWS = [  # page, viewport, the row's value cells, the record-derived cells ("record") or the director's literals
    # v2x cut (1 Nov): every stats row the site still has. Home's row lost ">10 bps" and "10/10" (the chart and the heading
    # say them; check_static compares those with #oxa-sessions) and keeps the CEO's 3 and 5; Proof's hero row and
    # Platform's swarm row left the pages. The principle is unchanged: no figure ever shows a value it does not end on.
    # hc5 (integrate): Home §04's 3 and 5 left the site (HC5 item 2); Home's figures are the first screen's four (owner,
    # 2 Nov: exactly as v2 set them), read here in their place
    ("index.html", (1440, 900), ".hero-stats b", ["5k–50k", "90%", "6", "01"]),
    ("company.html", (1440, 900), ".crew-stats b", ["4", "9", "100+"]),
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
  // hc30r: what lies under the bar, read with the bar out of the way at three heights round site.js's own probe line
  // (1.1 bar heights): the top-level band (a child of <main>, or the footer) that is drawn there, and whether it is ink
  const band = (y) => { let e = document.elementFromPoint(innerWidth / 2, y); while (e && e.parentElement && e.parentElement.id !== 'main' && e.parentElement !== document.body) e = e.parentElement;
    return e ? { id: e.id || (e.className && String(e.className).split(' ')[0]) || e.tagName, dark: e.classList.contains('is-dark') } : null; };
  nav.style.visibility = 'hidden'; const under = [nb * 1.1 - 8, nb * 1.1, nb * 1.1 + 8].map(band); nav.style.visibility = '';
  return { y: Math.round(scrollY), dark: nav.classList.contains('nav--dark'), vis, top: r ? +r.top.toFixed(1) : null, bot: r ? +r.bottom.toFixed(1) : null, nb: +nb.toFixed(1), under }; }"""


@check
async def nav_handoff(b):
    """at 1440, 768 and 390, from story end - innerHeight - 120 to story end + 60 in 20 px steps: the bar is never ink
    (.nav--dark) while the rising .story-paper lies under it (a one-frame lag that clears within six frames is not
    counted). hc16 (system's request): and after a one-shot jump, at 1440 x 900 and 3840 x 2160: from story end - 2h (the
    paper hidden, 400 ms), one scrollTo to story end - h + k h / 6 (k = 2..6), read 30 frames later: never ink over the
    paper (20 px steps re-read the paper on every scroll and could not catch a single stale read after a jump; the render
    frames did).
    hc30r (HOME-2; integrate, standing in for tests, on home's request; TESTS.md section 53): the paper is §01 itself and
    §01 is shorter than the stage it covers, so the lab (an ink chapter since HOME-2) rises over the stage's foot behind
    it: .story-paper now ends at §01's foot (story.js sets its bottom) and the bar turns to ink there, which is right.
    "The paper lies under the bar" therefore reads the marker's foot too: its top at or above the bar's foot and its foot
    below the bar's probe line (1.1 bar heights, site.js's own edge). And the other half of the same principle, which
    home's fix needed and nothing held (the bar stayed paper over the lab's first 172 px at 1440 x 900): wherever the
    band under the bar is plainly ink or plainly paper (the same band 8 px above and below the probe line) and the
    paper's marker is not the thing under the bar, the bar's tone is that band's."""
    bad, n = [], 0
    over = lambda s: s["vis"] and s["top"] <= s["nb"] and s["bot"] > s["nb"] * 1.1          # the paper under the bar
    viol = lambda s: s["dark"] and over(s)
    def tone(s):
        """the tone the bar should have from the band under it, None where that is the paper's own business or a boundary"""
        u = s["under"]
        if over(s) or (s["vis"] and s["top"] <= s["nb"] * 1.1 + 8 and s["bot"] > s["nb"] * 1.1 - 8): return None   # the marker at the probe line
        if not all(u) or len({(x["id"], x["dark"]) for x in u}) != 1: return None                                   # a boundary between two bands
        return u[0]["dark"]
    def wrong(s): t = tone(s); return t is not None and t != s["dark"]
    for w, h in ((1440, 900), (3840, 2160)):
        ctx, pg = await open_page(b, "index.html", w, h)
        end = await story_end(pg)
        seen = 0
        for k in range(2, 7):
            y = round(end - h + k * h / 6)
            await pg.evaluate(f"window.scrollTo({{top: {end - 2 * h}, behavior: 'instant'}})"); await pg.wait_for_timeout(400)
            await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
            s = await pg.evaluate(HANDOFF, 30); n += 1
            if over(s): seen += 1
            if viol(s): bad.append(f"index.html@{w}x{h} jump to y={y}: nav--dark 30 frames after the jump with the paper under the bar (its top at {s['top']}, its foot at {s['bot']}; bar bottom {s['nb']})")
            elif wrong(s): bad.append(f"index.html@{w}x{h} jump to y={y}: the bar is {'ink' if s['dark'] else 'paper'} 30 frames after the jump over {s['under'][1]['id']!r}, {'an ink' if s['under'][1]['dark'] else 'a paper'} band")
        if not seen: bad.append(f"index.html@{w}x{h}: no jump landed with the paper under the bar (nothing was tested)")
        await ctx.close()
    for w, h in ((1440, 900), (768, 1024), (390, 844)):
        ctx, pg = await open_page(b, "index.html", w, h)
        end = await story_end(pg)
        seen, tones = 0, set()
        for y in range(end - h - 120, end + 61, 20):
            await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})")
            s = await pg.evaluate(HANDOFF, 2); n += 1
            if over(s): seen += 1
            if tone(s) is not None: tones.add(tone(s))
            if viol(s) or wrong(s):
                s2 = await pg.evaluate(HANDOFF, 6)
                if viol(s2): bad.append(f"index.html@{w}x{h} y={y}: nav--dark with the paper under the bar (its top at {s2['top']}, its foot at {s2['bot']}; bar bottom {s2['nb']})")
                elif wrong(s2): bad.append(f"index.html@{w}x{h} y={y}: the bar is {'ink' if s2['dark'] else 'paper'} over {s2['under'][1]['id']!r}, {'an ink' if s2['under'][1]['dark'] else 'a paper'} band")
        if not seen: bad.append(f"index.html@{w}x{h}: the paper never lay under the bar in the hand-off window (nothing was tested)")
        if True not in tones: bad.append(f"index.html@{w}x{h}: no ink band stood under the bar in the hand-off window (the bar's tone over ink was not tested)")
        await ctx.close()
    assert not bad, f"nav_handoff: {len(bad)} samples with the bar in the wrong tone:\n  " + "\n  ".join(bad[:12])
    print(f"nav_handoff: {n} samples (steps at 1440, 768, 390; one-shot jumps at 1440 and 3840); the bar is never ink over the rising paper, and it takes the tone of the band under it on either side of the paper")


# ---- the ledger panel never moves the page (LG2)
@check
async def ledger_height(b):
    """a ledger being written never moves the page: on Trust, with the excerpt [data-ledger=replay] centred and Replay
    pressed, document.body.scrollHeight stays within 1 px until the nine records are written again, and the layout
    shifts in that time (no input after the press) sum to < 0.01, at 1440 (a horizontal strip) and at 390 (a column).
    v2x cut, owner's-eye fix (1 Nov): until then this read Home's running stream ([data-ledger=live]), which left the site
    with Home's agent log; Trust's replay is the one ledger still written while the reader watches.
    hc3 (proof, HC3 item 5): on phones (<= 600 px) the replay shows its first four records and a "Show all nine records"
    control ([data-lt-more], aria-expanded) from the first paint; at 1440 there is no fold. At 390 the check asserts the
    fold is drawn and closed, opens it (input: the page grows once, by the reader's press), then asks its question of the
    open column: writing the nine records again never moves the page."""
    bad = []
    for w, h, orient in ((1440, 900, "horizontal"), (390, 844, "vertical")):
        ctx, pg = await open_page(b, "trust.html", w, h)
        await pg.evaluate("document.querySelector('[data-ledger=replay]').scrollIntoView({block: 'center', behavior: 'instant'})")
        if not await until(pg, "(() => { const l = document.querySelector('[data-ledger=replay]'), r = l.querySelector('[data-lt-replay]'); return l.classList.contains('lt-ready') && r && !r.hidden; })()", 8000 if MODE["throttle"] <= 1 else 30000):
            bad.append(f"trust.html@{w}x{h}: the excerpt did not mount with its Replay control"); await ctx.close(); continue
        fold = await pg.evaluate("(() => { const m = document.querySelector('[data-ledger=replay] [data-lt-more]'); if (!m || !m.getClientRects().length) return null; const was = m.getAttribute('aria-expanded'); if (was === 'false') m.click(); return was; })()")
        if orient == "vertical" and fold != "false": bad.append(f"trust.html@{w}x{h}: the phone replay's fold ([data-lt-more]) is {'not drawn' if fold is None else 'aria-expanded=' + repr(fold)} at load (drawn and closed expected)")
        if orient == "horizontal" and fold is not None: bad.append(f"trust.html@{w}x{h}: the replay draws a fold ([data-lt-more]) at {w} px (phones only)")
        await pg.wait_for_timeout(1200)
        o = await pg.evaluate("(() => { const t = document.querySelector('[data-ledger=replay] .lt-track'); return t && t.getAttribute('aria-orientation'); })()")
        if o != orient: bad.append(f"trust.html@{w}x{h}: the excerpt's track is {o!r}, expected {orient!r}")
        await pg.evaluate("""(() => { const S = window.__lsh = []; new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput)
          S.push([Math.round(e.startTime), +e.value.toFixed(4), (e.sources || []).slice(0, 2).map(s => s.node && s.node.nodeType === 1 ? s.node.tagName + '.' + String(s.node.className || '').split(' ')[0] : '?')]); })).observe({ type: 'layout-shift', buffered: false }); })()""")
        h0 = await pg.evaluate("document.body.scrollHeight")
        await pg.locator("[data-ledger=replay] [data-lt-replay]").click()
        # sampled every 100 ms until a second after the state says 'Replayed' (a replay of nine records takes about 6 s)
        hs = await pg.evaluate("""async () => { const out = [], st = document.querySelector('[data-ledger=replay] [data-lt-state]'); let done = 0;
          for (let k = 0; k < 200 && done < 10; k++) { out.push([document.body.scrollHeight, st.textContent]); if (/^Replayed/.test(st.textContent)) done++; await new Promise(r => setTimeout(r, 100)); } return out; }""")
        states = [t for _, t in hs]
        if not any(t.startswith("Replaying") for t in states) or not states[-1].startswith("Replayed"):
            bad.append(f"trust.html@{w}x{h}: the replay did not run to its end: {sorted(set(states))[:4]} ... {states[-1]!r}")
        moved = [(k * 100, v) for k, (v, _) in enumerate(hs) if abs(v - h0) > 1]
        if moved: bad.append(f"trust.html@{w}x{h}: body.scrollHeight {h0} moved {len(moved)} times during the replay (range {min(v for v, _ in hs)}-{max(v for v, _ in hs)}), e.g. {moved[:4]}")
        lsh = await pg.evaluate("window.__lsh")
        cls = sum(x[1] for x in lsh)
        if cls >= 0.01: bad.append(f"trust.html@{w}x{h}: layout shifts during the replay sum to {cls:.4f} (budget < 0.01): {sorted(lsh, key=lambda x: -x[1])[:4]}")
        await ctx.close()
    assert not bad, "ledger_height:\n  " + "\n  ".join(bad)
    print("ledger_height: Trust's replay writes its nine records again with body.scrollHeight constant (±1 px) and layout shifts < 0.01, at 1440 (strip, no fold) and 390 (column, its four-record fold drawn closed at load, opened first)")


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
  const labs = [...document.querySelectorAll('.story-labels .story-lab')].filter(shown).map(l => ({ t: l.textContent.replace(/\\s+/g, ' ').trim().slice(0, 44), full: l.textContent.replace(/\\s+/g, ' ').trim(), bx: box(l), cap: l.classList.contains('cap') }));
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
  // v2x cut (1 Nov): the scene captions lost their 'Plate 03' mark (scene 3's reads 'Illustrative' only), so the caption is
  // the scene's shown .story-lab.cap (one per scene; at scene 3's rest only its own shows), or a marked one as before
  const c3 = labs.find(l => l.cap) || labs.find(l => /^(Plate|Fig\\.)\\s*0?3\\b/.test(l.t));
  const days = [...document.querySelectorAll('.story-labels .story-lab.day')].filter(shown).map(l => box(l)).sort((a, b) => a.l - b.l);
  return { issues, labs: labs.length, boxes: labs.map(l => [l.t, l.bx]), dayGaps: days.slice(1).map((d, k) => +(d.l - days[k].r).toFixed(1)),
    cap3: c3 ? { t: c3.full, inside: c3.bx.l >= 0 && c3.bx.t >= 0 && c3.bx.r <= innerWidth && c3.bx.b <= innerHeight, bx: [c3.bx.l, c3.bx.t, c3.bx.r, c3.bx.b].map(Math.round) } : null };
})()"""
PHONES = [(390, 664), (375, 667), (360, 780), (320, 640), (844, 390), (320, 568), (667, 375), (740, 360), (568, 320)]  # round 2 adds 320x568, 667x375, 740x360; v2x r2 568x320 (an iPhone SE on its side)
# hc12 (integrate, from home's hc12 entry): scene 4 draws the ten columns above the floor, so at its rest a shown
# overture label carries their hedge in the ledger's words (C-022), inside the viewport. Keyed on the words, not on a
# class: hc12 moved the hedge from the scene's caption to a tag on the chart, and a later design may move it again
HEDGE_S4 = "(() => { " + EFF + """
  const h = [...document.querySelectorAll('.story-labels .story-lab')].find(l => /Exact value not published/i.test(l.textContent)
    && eff(l, document.documentElement) > 0.3 && l.getBoundingClientRect().width > 0);
  if (!h) return ''; const r = h.getBoundingClientRect();
  return r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 0.5 && r.bottom <= innerHeight + 0.5 ? h.textContent.replace(/\\s+/g, ' ').trim() : '';
})()"""
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
    """at 390x664, 375x667, 360x780, 320x640, 844x390, 320x568, 667x375, 740x360 and 568x320 with touch, at each scene's rest: no
    visible callout box crosses the scene index, 'Pause motion', the nav, a visible beat's text or another callout; with
    the callouts hidden, under 2% of the stage's pixels inside each callout's box are brighter than luminance 120 (no
    structure under a callout); Plate 03's caption lies inside the viewport and says 'Illustrative' (its full text: v2x r3 sets
    the hedge after the mark and title, past the 44 characters the messages quote); at 320x640 adjacent
    S4 day tags are at least 3 px apart; at scene 4's rest a shown label carries the columns' hedge "Exact value not
    published" inside the viewport (hc12); at 844x390 and 667x375, the inspector opened by tapping each S1 ring and S2
    plate callout crosses none of .story-bar, .story-idx, .story-motion or another callout (OV1, OV10, D14; round 2:
    OV-R2-1, OV-R2-4, OV-R2-5; v2x r2: 568x320, where a plate caption crossed the headline, r2-a11y M)"""
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
            if i == 4 and not await until(pg, HEDGE_S4, 3000):
                bad.append(f"index.html@{w}x{h} scene 04: no shown label says 'Exact value not published' inside the viewport (the ten columns above the floor without their hedge)")
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
    if n != 1: bad.append(f"{n} visible ring callouts in S1 (1 expected: LC-01's; the other five left at hc13r, HOME-1)")
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
    errs = []
    ctx, pg = await open_page(b, "index.html", 1440, 900, errs=errs)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    num = "(s => +((document.querySelector(s) || {}).textContent || 'NaN').replace(/[^\\d.]/g, ''))"
    assert await until(pg, f"{num}('[data-sw-inflight]') > 0 && {num}('[data-sw-recorded]') > 0", 25000, 200), "swarm_rate index.html@1440x900: the lab never ran"
    await pg.evaluate("""(() => { const q = s => (document.querySelector(s) || {}).textContent || ''; const R = window.__rate = { f: [], on: true }; const t0 = performance.now();
      const f = () => { R.f.push([Math.round(performance.now() - t0), q('[data-sw-inflight]').trim(), q('[data-sw-rate]').trim()]); if (R.on) requestAnimationFrame(f); }; requestAnimationFrame(f); })()""")
    await pg.locator("[data-sw-halt]").click()
    drained = await until(pg, "document.querySelector('[data-sw-inflight]').textContent.trim() === '0'", 45000, 200)
    await pg.wait_for_timeout(1200)
    await pg.evaluate("window.__rate.on = false"); fr = (await pg.evaluate("window.__rate"))["f"]
    st = None if drained else await pg.evaluate(LAB_STATE)
    await ctx.close()
    assert drained, f"swarm_rate index.html@1440x900: Halt never drained (in flight {fr[-1][1] if fr else '?'}); " + lab_why(st, errs, fr)
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


# hc22 (home, HC22 4.4): the act's rest is the lab root's data-sw-act="rest"; the control stays unpressed, "Follow a proposal"
LAB_ACT_REST = "(() => { const f = document.querySelector('[data-sw-follow]'); return !!f && document.querySelector('[data-swarm-live]').dataset.swAct === 'rest' && f.getAttribute('aria-pressed') === 'false' && f.textContent.trim() === 'Follow a proposal'; })()"
SW_LINK = "(() => { const a = document.querySelector('[data-sw-log] a.sw-led-a'); return a ? { href: a.getAttribute('href'), name: a.getAttribute('aria-label'), text: a.textContent.replace(/\\s+/g, ' ').trim() } : null; })()"


@check
async def swarm_trace_to_ledger(b):
    """follow one proposal to Settled on Home (council strictness 0): the trace ends at a ledger the reader can inspect.
    v2x cut, owner's-eye fix (1 Nov): Home has no ledger of its own any more (its agent log left the page), so the
    trace's ledger row becomes a link to Trust's (a.sw-led-a, href trust.html#ledger, named 'The ledger on the Trust
    page'), never a record button; following it lands on Trust with the ledger in view and its nine records. On the
    homepage the trace, its stage tag and its live region never print 'block' or 'no ledger'. (Until then the row became
    a button naming the record, which Home's own ledger selected when it was clicked.) hc13r (home, HOME-2): Home's lab
    follows one proposal the Council passes by itself, once it is well in view, and rests in its follow view: that trace
    ends on the same link without a click. hc22 (home, HC22 4.4): the act leaves the Follow control at rest ("Follow a
    proposal", not pressed); the reader's own follow starts from it at the act's rest; that trace too must end at the
    link, which is followed to Trust."""
    errs = []
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=EVENTS, errs=errs)
    await pg.evaluate(BLOCK_WATCH)
    await pg.evaluate(TEXT_WATCH, r"no ledger")
    await pg.mouse.move(5, 450)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "+document.querySelector('[data-sw-inflight]').textContent.replace(/\\D/g, '') > 0", 25000, 200), "swarm_trace_to_ledger index.html@1440x900: the lab never ran"
    bad, t0 = [], time.monotonic()
    want = lambda a: bool(a) and a["href"] == "trust.html#ledger" and a["name"] == "The ledger on the Trust page" and a["text"].startswith("Ledger")
    if not await until(pg, LAB_ACT_REST + " && !!document.querySelector('[data-sw-log] a.sw-led-a')", 40000, 250):
        bad.append(f"the lab's own act did not rest on the trace's ledger link within 40 s: link {await pg.evaluate(SW_LINK)}, at rest {await pg.evaluate(LAB_ACT_REST)}")
    else:
        a = await pg.evaluate(SW_LINK)
        if not want(a): bad.append(f"the act's trace ends on a ledger link that reads {a}")
    t_act = time.monotonic() - t0
    # the reader's own follow, from the act's rest
    await pg.evaluate(SET_RANGE, ["[data-sw-strict]", 0])
    await pg.evaluate("document.querySelectorAll('[data-sw-log] a.sw-led-a').forEach(a => a.setAttribute('data-oxa-old', ''))")
    await pg.locator("[data-sw-follow]").click()
    t0 = time.monotonic()
    got = await until(pg, """(() => { if (document.querySelector('[data-sw-log] a.sw-led-a:not([data-oxa-old])')) return 'link';
        return document.querySelector('[data-sw-log] [data-sw-rec]') ? 'button' : ''; })()""", 60000, 250)
    blk, tw = await pg.evaluate("window.__blk || []"), await pg.evaluate("window.__tw || []")
    if blk: bad.append(f"the trace printed 'block': {blk[:3]}")
    if tw: bad.append(f"the trace printed 'no ledger': {tw[:3]}")
    if got != "link":
        log = await pg.evaluate("(document.querySelector('[data-sw-log]') || {}).textContent || ''")
        bad.append(f"the reader's follow: the trace's ledger row is no link to Trust's ledger after {time.monotonic() - t0:.0f} s ({got or 'nothing'}): {log[-120:]!r}")
    else:
        a = await pg.evaluate(SW_LINK)
        if not want(a):
            bad.append(f"the trace's ledger link reads {a}")
        elif not bad:
            await pg.locator("[data-sw-log] a.sw-led-a").click()
            await pg.wait_for_url(re.compile(r"/trust(\.html)?#ledger$"), timeout=15000)
            await pg.wait_for_load_state("load")
            land = await until(pg, """(() => { const s = document.getElementById('ledger'); if (!s) return null; const r = s.getBoundingClientRect();
                return r.top < innerHeight * 0.5 && r.bottom > innerHeight * 0.5 && document.querySelectorAll('[data-ledger=replay] .lt-rec').length === 9 ? [Math.round(r.top), Math.round(r.bottom)] : null; })()""", 8000, 100)
            if not land:
                where = await pg.evaluate("(() => { const s = document.getElementById('ledger'); return [location.href, s ? Math.round(s.getBoundingClientRect().top) : null, document.querySelectorAll('[data-ledger=replay] .lt-rec').length]; })()")
                bad.append(f"after the link Trust's ledger is not in view with its nine records: {where}")
            else: print(f"swarm_trace_to_ledger: the lab's own act rested on the ledger link after {t_act:.1f} s; the reader's follow ('Follow a proposal') links to Trust's ledger after {time.monotonic() - t0:.1f} s; it lands in view (top {land[0]} px) with nine records")
    if bad and not got == "link": bad.append(lab_why(await pg.evaluate(LAB_STATE), errs))
    await ctx.close()
    assert not bad, "swarm_trace_to_ledger index.html@1440x900:\n  " + "\n  ".join(bad)


@check
async def ledger_wheel(b):
    """a vertical wheel over a ledger strip belongs to the page: on Trust at 1440, while Replay writes the excerpt again,
    6 vertical wheel steps of 120 px with the pointer over the strip (3 down, 3 up) scroll the page and never take the
    strip off the record being written: the replay runs to 'Replayed · 9 records' with the strip at its newest record.
    v2x cut, owner's-eye fix (1 Nov): until then this read Home's running stream ([data-ledger=live]: the wheel never
    turned it to 'browsing'), which left the site with Home's agent log."""
    ctx, pg = await open_page(b, "trust.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-ledger=replay] .lt-view').scrollIntoView({block: 'center', behavior: 'instant'})")
    await until(pg, "(() => { const r = document.querySelector('[data-ledger=replay] [data-lt-replay]'); return !!r && !r.hidden; })()", 8000 if MODE["throttle"] <= 1 else 30000)
    await pg.wait_for_timeout(900)
    await pg.locator("[data-ledger=replay] [data-lt-replay]").click()
    await pg.evaluate("document.querySelector('[data-ledger=replay] .lt-view').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(300)
    x, y = await pg.evaluate("(() => { const r = document.querySelector('[data-ledger=replay] .lt-view').getBoundingClientRect(); return [r.left + r.width * 0.5, r.top + r.height / 2]; })()")
    await pg.mouse.move(x, y)
    ys = [await pg.evaluate("scrollY")]
    for k in range(6):
        await pg.mouse.wheel(0, 120 if k < 3 else -120); await pg.wait_for_timeout(180)
        ys.append(await pg.evaluate("scrollY"))
    end = await until(pg, "/^Replayed/.test(document.querySelector('[data-ledger=replay] [data-lt-state]').textContent) ? document.querySelector('[data-ledger=replay] [data-lt-state]').textContent : ''", 20000, 100)
    await pg.wait_for_timeout(1500)  # the strip's last glide
    v = await pg.evaluate("(() => { const v = document.querySelector('[data-ledger=replay] .lt-view'); return { sl: Math.round(v.scrollLeft), max: v.scrollWidth - v.clientWidth, recs: document.querySelectorAll('[data-ledger=replay] .lt-rec').length }; })()")
    await pg.mouse.move(5, 450)
    await ctx.close()
    bad = []
    if max(ys) - ys[0] < 120: bad.append(f"the page did not scroll under a vertical wheel over the strip: scrollY {ys}")
    if not end or "9" not in end or v["recs"] != 9: bad.append(f"the replay did not run to its end: state {end!r}, {v['recs']} records")
    if v["max"] > 2 and v["sl"] < v["max"] - 2: bad.append(f"the strip left the record being written: scrollLeft {v['sl']} of {v['max']}")
    assert not bad, "ledger_wheel trust.html@1440x900:\n  " + "\n  ".join(bad)
    print(f"ledger_wheel: 6 vertical wheel steps over Trust's strip during a replay scrolled the page (scrollY {ys[0]} -> {max(ys)} -> {ys[-1]}); the replay ended '{end}', the strip at {v['sl']} of {v['max']} px")


# ---- the proof chart's entrance: all sessions rise together (PF2); hc13r: Proof's hero chart (#performance), at load
# samples every 50 ms and on every animation frame, from before the arrival until 1.5 s after the chart turns .is-in
PROOF_SAMPLER = """(dur) => { const host = document.querySelector('#performance [data-proof-chart]'); const lanes = [...host.querySelectorAll('.pf-lane')];
  const S = window.__pe = { s: [], done: false }; const t0 = performance.now(); let inAt = null;
  const sample = () => { const now = performance.now(), isIn = host.classList.contains('is-in'); if (isIn && inAt === null) inAt = now;
    S.s.push({ t: Math.round(now - t0), in: isIn, c: lanes.map(l => [...l.querySelectorAll('.pf-c i:not(.is-void), .pf-g i')].filter(i => +getComputedStyle(i).opacity >= 0.5).length) });
    if (inAt === null ? now - t0 > 6000 : now - inAt > dur) S.done = true; };
  const tick = () => { if (S.done) return; sample(); setTimeout(tick, 50); };
  const raf = () => { if (S.done) return; sample(); requestAnimationFrame(raf); };
  tick(); requestAnimationFrame(raf); return lanes.length; }"""


# each counted block tagged with its lane (data-pe), and the moments the chart turns .is-in and drops .is-armed (which
# ends any transition still running: proof.js's ENTRANCE_MS), on the page's clock
PROOF_MARK = """(() => { const host = document.querySelector('#performance [data-proof-chart]'); const R = window.__pem = { inAt: null, cutAt: null }; let k = 0;
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


# hc13r: Proof's chart is the hero, in the first screen at load, where its entrance is the page's opening (proof.js). The
# hook runs from the document's start: once proof.js has built the ten lanes (a mutation callback, before the
# IntersectionObserver's first report can set .is-in), it notes whether the chart was already in, tags the blocks
# (PROOF_MARK) and starts the sampler (PROOF_SAMPLER), so the whole entrance is seen from its first frame
PROOF_LOAD_HOOK = """(() => { const W = window; W.__peHook = { built: null, wasIn: null, n: 0 };
  const arm = () => { const host = document.querySelector('#performance [data-proof-chart]'); if (!host || host.querySelectorAll('.pf-lane').length < 10) return false;
    W.__peHook.built = performance.now(); W.__peHook.wasIn = host.classList.contains('is-in');
    """ + PROOF_MARK + """;
    W.__peHook.n = (""" + PROOF_SAMPLER + """)(1500); return true; };
  const mo = new MutationObserver(() => { if (arm()) mo.disconnect(); });
  mo.observe(document, { subtree: true, childList: true }); })();"""


@check
async def proof_entrance(b):
    """the proof chart's entrance at 1440, sampled every 50 ms and on every frame until 1.5 s after the chart turns .is-in:
    the ten lanes' lit block counts never differ by more than one (no staircase, no session below another); the entrance
    played and the chart was not revealed before it. Round 2 (CI): the same invariant is also checked at every instant of
    the entrance rebuilt from each block's opacity transition (CDP Animation domain), so a main thread too busy to sample
    during the 1.1 s entrance (CI's software GL at 4x) neither hides a staircase nor fails a correct chart for want of a
    sample. hc13r (home, HOME-1): the chart left Home §03 (where it was arrived at from above, about 38% in view); it
    draws only on Proof, as the hero, whose entrance plays at load in the first screen: read there from the document's
    start (PROOF_LOAD_HOOK); that Home draws no [data-proof-chart] is asserted in `home`."""
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    pg = await ctx.new_page()
    cdp = await ctx.new_cdp_session(pg)
    started = []
    cdp.on("Animation.animationStarted", lambda e: started.append(e.get("animation") or {}))
    await cdp.send("Animation.enable")
    await ctx.add_init_script(PROOF_LOAD_HOOK)
    await pg.goto(f"{BASE}/evidence.html", wait_until="load")
    hooked = await until(pg, "!!(window.__pe && window.__pe.done)", 12000 if MODE["throttle"] <= 1 else 40000)
    hk = await pg.evaluate("window.__peHook")
    await pg.wait_for_timeout(1600)  # past ENTRANCE_MS: every block final
    lanes = lane_nodes((await cdp.send("DOM.getDocument", {"depth": -1}))["root"])
    s = await pg.evaluate("window.__pe ? window.__pe.s : []")
    mk, finals = await pg.evaluate("window.__pem || { inAt: null, cutAt: null }"), await pg.evaluate(PROOF_FINAL)
    await ctx.close()
    n, pre = hk["n"], hk["wasIn"]
    total = max((sum(x["c"]) for x in s), default=0)
    spread = [(x["t"], max(x["c"]) - min(x["c"]), x["c"]) for x in s if x["c"]]
    worst = max(spread, key=lambda v: v[1]) if spread else None
    ntr, steps = entrance_timeline(started, lanes, finals, mk["inAt"], mk["cutAt"])
    rworst = max(((t, max(c) - min(c), c) for t, c in steps), key=lambda v: v[1], default=None)
    played = any(0 < sum(x["c"]) < total for x in s) or ntr > 0  # seen mid-way, or its transitions ran after .is-in
    ok = hooked and n == 10 and pre is False and played and worst and worst[1] <= 1 and (rworst is None or rworst[1] <= 1)
    rel = lambda t: f"{t - mk['inAt']:.0f} ms after .is-in" if mk["inAt"] is not None else f"{t:.0f} ms"
    assert ok, (f"proof_entrance evidence.html@1440x900 (at load): hook {hk}, sampler done: {hooked}; {n} lanes; revealed before the entrance: {pre}; entrance observed: {played} ({ntr} block transitions); "
                f"worst lane spread {worst[1] if worst else '?'} at {worst[0] if worst else '?'} ms in the samples: {worst[2] if worst else ''}; "
                f"rebuilt from the transitions: worst spread {rworst[1] if rworst else '-'}" + (f" at {rel(rworst[0])}: {rworst[2]}" if rworst else ""))
    print(f"proof_entrance: Proof's hero at load, {len(s)} samples and {len(steps)} steps rebuilt from {ntr} block transitions; lanes never differ by more than {max(worst[1], rworst[1] if rworst else 0)} block")


# ---- the lifecycle lane (LC1, LC2, D2) and the desk (LC2b)
GATES = ["Signal", "Predict", "Decide", "Approve", "Execute", "Settle"]  # the canonical gate vocabulary (_cross)
STEPS = [  # Lifecycles §02 (§03 before the cut): the six gates, by name. v2x cut (1 Nov): the seven step sentences and the
    # eyebrow left the page (one heading and one sentence per section; the stations name the gates). hc3 (platform, HC3
    # item 1): the station "07 Reconcile" went; its marks (the check and the two record blocks) are drawn under 06 Settle,
    # as Platform §03 draws "06 Settle" over "Reconcile and report" (C-072; C-074 on the owner's sign-off list)
    "Signal", "Predict", "Decide", "Approve", "Execute", "Settle",
]
LANE_HOME = """(() => { const q = s => document.querySelectorAll(s); const items = [...q('#lc01 [data-sw-gates] > li')];
  return { flow: q('.flow').length, lane: q('#lc01 [data-lane]').length, gates: items.map(li => li.textContent.replace(/\\s+/g, ' ').trim()) }; })()"""
LANE_STEPS = """(() => { const sec = document.querySelector('#lc01'), ol = sec && (sec.querySelector('.lane-v--steps') || sec.querySelector('.lane-v')); const items = ol ? [...ol.querySelectorAll(':scope > li[data-g]')] : [];
  const last = items[items.length - 1], g = last && last.querySelector('svg');
  return { wall: document.querySelectorAll('.wall').length, lane: !!ol, steps: items.map(li => [li.dataset.g, ((li.querySelector('h3') || li).textContent || '').replace(/\\s+/g, ' ').trim()]),
    recon: g ? { check: g.querySelectorAll('.g').length, blocks: g.querySelectorAll('rect.blk').length } : null,
    text: sec ? sec.textContent.replace(/\\s+/g, ' ') : '' }; })()"""


@check
async def lifecycle_lane_home(b):
    """home: no .flow; Lifecycle 01 (#lc01) names the six gates 01 Signal ... 06 Settle in order, with and without
    JavaScript. v2x cut, owner's-eye fix (1 Nov): the lane figure (ex Fig. 3.1, [data-lane]) left Home, where the six
    gates were told twice; they are named once, by the swarm lab's gate list ([data-sw-gates]). Lifecycles keeps the lane
    (lifecycle_lane_steps)."""
    bad = []
    for js in (True, False):
        ctx, pg = await open_page(b, "index.html", 1440, 900, js=js, reduced=True)
        m = await pg.evaluate(LANE_HOME)
        ok = len(m["gates"]) == 6 and all(re.match(rf"0{k + 1}\b", t) and GATES[k] in t for k, t in enumerate(m["gates"]))
        if m["flow"] or m["lane"] or not ok: bad.append(f"index.html@1440x900 js={'on' if js else 'off'}: .flow {m['flow']}, lane figures {m['lane']} (none expected), gates {[t[:28] for t in m['gates']]}")
        await ctx.close()
    assert not bad, "lifecycle_lane_home:\n  " + "\n  ".join(bad)
    print("lifecycle_lane_home: no .flow, no second lane; Lifecycle 01's lab names 01 Signal ... 06 Settle, with and without JavaScript")


@check
async def lifecycle_lane_steps(b):
    """Lifecycles #lc01: the vertical lane draws the six gates, 01 Signal ... 06 Settle in order, and the last station's
    glyph still draws the reconciliation (D2: its check and its two record blocks, hc3: under 06 Settle); no .wall on the
    page; with and without JavaScript. (v2x cut, 1 Nov: the seven step sentences and the eyebrow 'Seven steps · one swarm
    · vertical execution' left the page by design; the stations stay. hc3, platform: '07 Reconcile' went as a station,
    so the lane agrees with lifecycle_lane_home and C-072.)"""
    bad = []
    for js in (True, False):
        ctx, pg = await open_page(b, "lifecycles.html", 1440, 900, js=js, reduced=True)
        m = await pg.evaluate(LANE_STEPS)
        names = [re.sub(r"^\d+\s*", "", t) for g, t in m["steps"]]
        gs = [g for g, t in m["steps"]]
        tag = f"lifecycles.html@1440x900 js={'on' if js else 'off'}"
        if m["wall"]: bad.append(f"{tag}: {m['wall']} .wall element(s)")
        if not m["lane"] or names != STEPS or gs != [str(k) for k in range(1, 7)]: bad.append(f"{tag}: the lane's stations read {m['steps']} (lane: {m['lane']})")
        if not m["recon"] or m["recon"]["check"] < 1 or m["recon"]["blocks"] < 2: bad.append(f"{tag}: 06 Settle's glyph does not draw the reconciliation (a check and two record blocks): {m['recon']}")
        await ctx.close()
    assert not bad, "lifecycle_lane_steps:\n  " + "\n  ".join(bad)
    print("lifecycle_lane_steps: the six gates by name, 01 Signal ... 06 Settle in order, the reconciliation drawn under 06, no .wall, with and without JavaScript")


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
SHEET_TITLES = """() => [...document.querySelectorAll('#site-menu .nav-ch-list a')].filter(a => !a.closest('li').hidden && a.getClientRects().length).map(a => { const t = a.querySelector('.t') || a; return [t.textContent.trim(), t.scrollWidth, t.clientWidth]; })"""
READOUT_PAGES = ["index", "platform", "lifecycles", "evidence", "trust", "company", "research", "research/01-compounding-error", "blog/index", "access"]
READOUT = "async () => { " + FRAMES + """ await frames(3); const lines = [...document.querySelectorAll('.nav-ch-btn .nav-ch-line')];
  const l = lines[0]; if (!l) return null;
  return { txt: l.textContent.replace(/\\s+/g, ' ').trim(), sw: l.scrollWidth, cw: l.clientWidth, cur: (document.querySelector('.nav-ch-list a[aria-current]') || {}).textContent || '' }; }"""


@check
async def nav_readout(b):
    """no chapter name is cut. v2x cut (1 Nov): under 961 px the bar has no readout (the menu toggle opens the sheet, whose
    first items are this page's chapters), so at 390 and 360, on every page with chapters, the open sheet's chapter
    titles each have scrollWidth <= clientWidth (+1 px rounding); and at 1024 (the narrowest desktop bar), for every
    chapter, the readout's line in .nav-ch-btn fits as before (it shows the chapter's number since the cut).
    Never vacuous. Until the owner's-eye fix (1 Nov) a fixed floor said so (>= 60 sheet names, >= 30 readouts); the cut
    and that fix took the pages to 27 chapters, under it. Now each page is held to its own markup: where the page names
    its chapters (main section[data-chapter], two or more), the sheet lays out and measures every one of them at both
    phone widths and the desktop bar reads every one at 1024; and at least six of the pages read have chapters."""
    bad, n, m, have = [], 0, 0, set()
    for w, h in ((390, 844), (360, 780)):
        for name in READOUT_PAGES:
            ctx, pg = await open_page(b, f"{name}.html", w, h, reduced=True)
            await pg.locator(".nav-toggle").click()
            await until(pg, "document.querySelector('#site-menu').matches(':popover-open')", 3000)
            r = await pg.evaluate(SHEET_TITLES); n += len(r)
            marked = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
            if marked >= 2:
                have.add(name)
                if len(r) != marked: bad.append(f"{name}.html@{w}x{h} sheet: {len(r)} chapter names laid out, the page has {marked} chapters")
            bad += [f"{name}.html@{w}x{h} sheet: '{t}' needs {sw} px, has {cw}" for t, sw, cw in r if sw > cw + 1]
            await ctx.close()
    for w, h in ((1024, 768),):
        for name in READOUT_PAGES:
            ctx, pg = await open_page(b, f"{name}.html", w, h, reduced=True)
            hrefs = await pg.evaluate("[...document.querySelectorAll('.nav-ch-list a')].filter(a => !a.closest('li').hidden).map(a => a.getAttribute('href'))")
            marked = await pg.evaluate("document.querySelectorAll('main section[data-chapter]').length")
            read = 0
            for href in hrefs:
                await pg.evaluate("(h) => { const el = document.getElementById(decodeURIComponent(h.slice(1))); if (el) window.scrollTo({top: el.getBoundingClientRect().top + scrollY - 40, behavior: 'instant'}); }", href)
                r = await pg.evaluate(READOUT)
                if r: m += 1; read += 1
                if r and r["sw"] > r["cw"] + 1: bad.append(f"{name}.html@{w}x{h} {href}: '{r['txt']}' needs {r['sw']} px, has {r['cw']}")
            if marked >= 2 and read != marked: bad.append(f"{name}.html@{w}x{h}: the readout was read for {read} of the page's {marked} chapters")
            await ctx.close()
    # never vacuous: every page that names chapters had each one read, and enough pages name them to mean something
    assert len(have) >= 6 and n and m, f"nav_readout: only {sorted(have)} have chapters ({n} sheet names, {m} desktop readouts read)"
    assert not bad, f"nav_readout: {len(bad)} problems:\n  " + "\n  ".join(bad[:20])
    print(f"nav_readout: {n} chapter names in the phones' sheet at 390 and 360 and {m} desktop readouts at 1024 over {len(have)} pages with chapters (every chapter of each), none cut")


PILL_ACTIVE = """() => { const a = document.activeElement, sh = document.querySelector('.nav-sheet');
  return a ? {tag: a.tagName, pill: a.matches('.nav-ch-btn'), inSheet: !!(sh && sh.contains(a)), current: a.getAttribute('aria-current'),
              ring: a.matches(':focus-visible'), text: (a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 32)} : null; }"""


@check
async def pill_focus(b):
    """v2x r5 (system; r5-a11y moderate), re-expressed for the 1 Nov cut: under 961 px there is one menu control. The
    readout's pill is not drawn (it read as a second menu beside the toggle; the owner's cut took the bar's running head
    away); Enter on the menu toggle opens the sheet with the reader's chapter marked (a[aria-current] is the chapter the
    bar names for where the reader is); Tab enters the sheet on a link with its visible ring (:focus-visible); Escape
    closes the sheet and returns focus to the toggle. Home 390 (touch), Platform 900, Trust 390 (touch), each read with
    the reader 45% down the page.
    hc30r (system; RETHINK-hc30 SYS-6, the director's HC30 item 11: "a visitor who opens the menu wants the site first"):
    the sheet leads with the site. In its own order (the order Tab walks): the six pages, then Request access, then "On
    this page" and the chapters (was: the chapters first, pinned here since the 1 Nov cut); the chapter rows carry no
    hairline at their right but the reader's own (its progress)."""
    said = []
    for path, w, h, touch in (("index.html", 390, 844, True), ("platform.html", 900, 900, False), ("trust.html", 390, 844, True)):
        ctx, pg = await open_page(b, path, w, h, dpr=2 if touch else 1, touch=touch)
        await pg.evaluate("window.scrollTo({top: document.body.scrollHeight * .45, behavior: 'instant'})")
        await expect(pg.locator(".nav-toggle")).to_be_visible()
        await pg.wait_for_timeout(600)
        pill = await pg.evaluate("(() => { const p = document.querySelector('.nav-ch-btn'); return !!p && p.checkVisibility({ visibilityProperty: true, opacityProperty: true }) && p.getBoundingClientRect().width > 0; })()")
        await pg.focus(".nav-toggle"); await pg.keyboard.press("Enter")
        st = await until(pg, """(() => { const sh = document.querySelector('#site-menu'); if (!sh || !sh.matches(':popover-open')) return null;
          const cur = sh.querySelector('.nav-ch-list a[aria-current]'), lab = (document.querySelector('.nav-ch-btn') || { getAttribute: () => '' }).getAttribute('aria-label') || '';
          const t = cur && (cur.querySelector('.t') || cur);
          const order = [...sh.querySelectorAll('a[href], button')].filter(e => e.getClientRects().length).map(e => e.closest('.nav-sheet-links') ? 'page' : e.matches('.btn') ? 'access' : e.closest('.nav-ch-list') ? 'chapter' : e.matches('.nav-ch-top') ? 'top' : 'other');
          const lines = [...sh.querySelectorAll('.nav-ch-list a')].filter(a => getComputedStyle(a.querySelector('.p')).visibility !== 'hidden').map(a => a.getAttribute('aria-current'));
          return { current: t ? t.textContent.trim() : null, label: lab.split(' · ')[0], order, lines }; })()""", 3000)
        await pg.keyboard.press("Tab"); await pg.wait_for_timeout(250)
        a1 = await pg.evaluate(PILL_ACTIVE)
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(500)
        a2 = await pg.evaluate("(() => ({ toggle: document.activeElement === document.querySelector('.nav-toggle'), open: document.querySelector('#site-menu').matches(':popover-open') }))()")
        await ctx.close()
        where = f"{path}@{w}"
        assert not pill, f"pill_focus {where}: the readout's pill is drawn beside the menu toggle under 961 px (two menus)"
        assert st and st["current"] and st["current"] in st["label"], f"pill_focus {where}: Enter on the toggle: the sheet {st} (want it open, the reader's chapter marked as the bar names it)"
        ch = len([k for k in st["order"] if k == "chapter"])
        assert st["order"] == ["page"] * 6 + ["access"] + ["chapter"] * ch + ["top"] and ch >= 2, f"pill_focus {where}: the sheet's order is {st['order']} (the six pages, Request access, then this page's chapters and Back to top)"
        assert st["lines"] == ["true"], f"pill_focus {where}: {len(st['lines'])} chapter rows draw their hairline ({st['lines']}); only the reader's chapter keeps its own"
        assert a1 and a1["inSheet"] and a1["tag"] == "A" and a1["ring"], f"pill_focus {where}: Tab after opening the sheet left focus on {a1} (want a link inside the sheet, with its visible ring)"
        assert a2["toggle"] and not a2["open"], f"pill_focus {where}: Escape in the sheet left {a2} (want the sheet closed and focus on the toggle)"
        said.append(f"{where}: no pill; Enter on the toggle -> sheet (six pages, Request access, {ch} chapters), '{st['current']}' marked current; Tab -> '{a1['text']}' (ring); Escape -> the toggle")
    print("pill_focus: " + "; ".join(said))


@check
async def tables_phone(b):
    """at 390, 360 and 320, every .table-scroll on /platform.html and /evidence.html has scrollWidth <= clientWidth + 1.
    v2x cut (1 Nov): Proof's only table is the session record for readers without JavaScript (<noscript>; with it the
    chart carries each session), so Proof is read with JavaScript off, where that table is drawn."""
    bad = []
    for w, h in ((390, 844), (360, 780), (320, 640)):
        for name in ("platform", "evidence"):
            ctx, pg = await open_page(b, f"{name}.html", w, h, reduced=True, js=name != "evidence")
            m = await pg.evaluate("[...document.querySelectorAll('.table-scroll')].map(t => [t.scrollWidth, t.clientWidth])")
            over = [x for x in m if x[0] > x[1] + 1]
            if not m or over: bad.append(f"{name}.html@{w}x{h}: .table-scroll [scrollWidth, clientWidth] {m}")
            await ctx.close()
    assert not bad, "tables_phone:\n  " + "\n  ".join(bad)
    print("tables_phone: every Platform table (with JavaScript) and Proof's no-JS record fit at 390, 360 and 320")


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
SPEC = """async () => { const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
  const doc = new DOMParser().parseFromString(await (await fetch(location.pathname, {cache: 'no-store'})).text(), 'text/html');
  // each layer of the markup: its name (the h3 without its verb) and its job line (v2x cut: data-job, the readout's text)
  return { layers: [...doc.querySelectorAll('#architecture .layers .layer')].map(l => { const h = l.querySelector('h3').cloneNode(true), v = h.querySelector('small'); if (v) v.remove();
    return [norm(h.textContent), norm(l.getAttribute('data-job'))]; }) }; }"""
SPEC_TAGS = """() => { const ir = document.querySelector('#architecture .arch').getBoundingClientRect();
  // the layer buttons a reader can hit (v2x cut: no spec mode, so the list's own buttons; the r4 tags were spec-only)
  const r = [...document.querySelectorAll('#architecture .arch-layer')].filter(x => x.checkVisibility()).map(x => x.getBoundingClientRect());
  let overlap = 0; for (let i = 0; i < r.length; i++) for (let j = i + 1; j < r.length; j++) { const a = r[i], c = r[j];
    if (a.left < c.right - .5 && c.left < a.right - .5 && a.top < c.bottom - .5 && c.top < a.bottom - .5) overlap++; }
  return { n: r.length, minH: r.length ? Math.min(...r.map(q => q.height)) : 0, overlap, outside: r.filter(q => q.left < ir.left - .5 || q.right > ir.right + .5).length,
           sizes: r.map(q => [Math.round(q.width), Math.round(q.height)]) }; }"""


@check
async def platform_spec(b):
    """Platform's explorer. v2x cut (1 Nov): the spec sheet under it (eight paragraphs, chip lists, In/Out pairs) left the
    page; each layer keeps its name, verb and one job line (data-job), which the readout shows, as on Home. At 1440 the
    markup lists the eight layers, each with its job, and pointing at each layer shows its name and that job in the
    readout; at 900 Tab from Pause reaches layer 01, ArrowDown 02, Enter opens its panel (aria-expanded, the panel shown)
    and Escape closes it with focus kept; on short windows (844x390, 320x256) the eight layer buttons stay targets: each
    at least 24 px tall, none overlapping another, none outside the instrument (WCAG 2.5.8, r4). hc5 (integrate): the
    keys Home's check held until Home §02 drew Platform's plate (HC5 item 1), here at 1440: the boundary after 04;
    ArrowDown x3 lands on 04 (lit), Enter opens its panel in the readout card, Escape closes it with focus kept, End /
    Home; pointing at a layer sets the instrument's has-hot. hc6 (integrate, platform's request; HC6 item 5): the readout
    is gone and a layer's job opens under its own row at every width, as on phones: at 1440 opening each layer shows its
    panel (#arch0-pN, the next sibling of the Nth h3.arch-h in the list, aria-expanded true) whose text is the markup's
    job line, under a row naming the markup's layer; pressing the open layer again closes it; the boundary (its line and
    hairline) stands after 04 with its hairline level with the drawing's plane (within 2 px); pointing at each layer sets
    has-hot and never changes the instrument's height; Enter opens 04's panel in the list.
    hc26r (integrate, standing in for tests; platform's request, PLAT-1): at 1440 x 900 the explorer is the end of a pinned
    scene, so the check reaches it as a visitor does, by the address (#architecture lands on the travel's end, the
    explorer whole), and points and clicks with the mouse at each layer's centre (Playwright's own scroll-into-view would
    move the page back into the scene, where the rows are still arriving); everything after that is as before"""
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    m = await pg.evaluate(SPEC)
    await pg.evaluate("location.hash = '#architecture'"); await pg.wait_for_timeout(1500)
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-wide.is-ready')", 10000), "platform explorer not ready at 1440"
    await pg.wait_for_timeout(600)
    arch_h = "Math.round(document.querySelector('#architecture .arch').getBoundingClientRect().height)"
    mid = lambda sel: pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }", sel)
    h0 = await pg.evaluate(arch_h)
    hov = []
    for k in range(1, 9):
        x, y = await mid(f"#arch0-b{k}"); await pg.mouse.move(x, y); await pg.wait_for_timeout(150)
        hov.append(await pg.evaluate(f"[document.querySelector('#architecture .arch').classList.contains('has-hot'), {arch_h}]"))
    await pg.mouse.move(5, 450)
    assert all(hh and abs(hgt - h0) <= 1 for hh, hgt in hov), f"platform_spec platform.html@1440x900: pointing at each layer gives [has-hot, height] {hov} (want has-hot, height {h0} throughout)"
    shown = []
    for k, (name, job) in enumerate(m["layers"]):
        x, y = await mid(f"#arch0-b{k + 1}"); await pg.mouse.click(x, y)
        got = await until(pg, f"""(() => {{ const norm = s => (s || '').replace(/\\s+/g, ' ').trim(), p = document.querySelector('#arch0-p{k + 1}'), h = document.querySelectorAll('#architecture h3.arch-h')[{k}];
          return p && h && !p.hidden && p.getClientRects().length > 0 && p.previousElementSibling === h && !!p.closest('.arch-list')
            && document.querySelector('#arch0-b{k + 1}').getAttribute('aria-expanded') === 'true' && norm(p.textContent) === {json.dumps(job)} ? norm(h.querySelector('.nm').textContent) : ''; }})()""", 3000)
        shown.append(got)
    x, y = await mid("#arch0-b8"); await pg.mouse.click(x, y)
    await expect(pg.locator("#arch0-b8")).to_have_attribute("aria-expanded", "false")
    await expect(pg.locator("#arch0-p8")).to_be_hidden()
    await pg.mouse.move(5, 450); await pg.wait_for_timeout(700)
    bd = await pg.evaluate("""(() => { const list = document.querySelector('#architecture .arch-list'), r = document.querySelector('#architecture .arch-bound .ab-rule'), ps = [...document.querySelectorAll('#architecture .arch-svg .ab polygon')];
      const rr = r && r.getBoundingClientRect(), pr = ps.length ? ps[ps.length - 1].getBoundingClientRect() : null, l = document.querySelector('#architecture .arch-bound .ab-line');
      return { bound: [...list.children].filter(e => !e.classList.contains('arch-panel')).findIndex(e => e.classList.contains('arch-bound')), line: l ? l.textContent.replace(/\\s+/g, ' ').trim() : '',
               off: rr && pr ? Math.round((rr.top + rr.height / 2 - (pr.top + pr.height / 2)) * 10) / 10 : null }; })()""")
    assert bd["bound"] == 4 and bd["line"].startswith("The boundary") and bd["off"] is not None and abs(bd["off"]) <= 2, f"platform_spec platform.html@1440x900: the boundary {bd} (want after 4 layers, its line, its hairline within 2 px of the plane)"
    await pg.locator("#arch0-b1").focus()
    for _ in range(3): await pg.keyboard.press("ArrowDown")
    assert await pg.evaluate("document.activeElement.id") == "arch0-b4"
    await expect(pg.locator("#arch0-b4")).to_have_class(re.compile(r"\bis-hot\b"))
    await pg.keyboard.press("Enter")
    await expect(pg.locator("#arch0-b4")).to_have_attribute("aria-expanded", "true")
    await expect(pg.locator("#architecture .arch-list #arch0-p4")).to_be_visible()
    await pg.keyboard.press("Escape")
    await expect(pg.locator("#arch0-b4")).to_have_attribute("aria-expanded", "false")
    assert await pg.evaluate("document.activeElement.id") == "arch0-b4"
    await pg.keyboard.press("End"); assert await pg.evaluate("document.activeElement.id") == "arch0-b8"
    await pg.keyboard.press("Home"); assert await pg.evaluate("document.activeElement.id") == "arch0-b1"
    x, y = await mid("#arch0-b5"); await pg.mouse.move(x, y)
    await expect(pg.locator("#architecture .arch")).to_have_class(re.compile(r"\bhas-hot\b"))
    await pg.mouse.move(5, 450)
    await ctx.close()
    assert len(m["layers"]) == 8 and all(j for _, j in m["layers"]) and shown == [n for n, _ in m["layers"]], f"platform_spec platform.html@1440x900: layers {[(n, j[:24]) for n, j in m['layers']]}; opening each layer showed its job under the row named {shown} (want each layer's name with its job line)"
    ctx, pg = await open_page(b, "platform.html", 900, 900)
    await pg.evaluate("document.querySelector('#architecture .arch-motion').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1500)
    await pg.focus("#architecture .arch-motion")
    keys = []
    for k in ("Tab", "ArrowDown", "Enter", "Escape"):
        await pg.keyboard.press(k); await pg.wait_for_timeout(500 if k == "Enter" else 250)
        keys.append(await pg.evaluate("[document.activeElement.id, document.activeElement.getAttribute('aria-expanded'), !!document.querySelector('#arch0-p2') && !document.querySelector('#arch0-p2').hidden]"))
    await ctx.close()
    assert keys == [["arch0-b1", "false", False], ["arch0-b2", "false", False], ["arch0-b2", "true", True], ["arch0-b2", "false", False]], f"platform_spec platform.html@900x900: Tab, ArrowDown, Enter, Escape from Pause give [focus, aria-expanded, panel 02 shown] {keys}"
    sizes = []
    for w, h, touch in ((844, 390, True), (320, 256, False)):
        ctx, pg = await open_page(b, "platform.html", w, h, dpr=2 if touch else 1, touch=touch)
        await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(1500)
        t = await pg.evaluate(SPEC_TAGS)
        await ctx.close()
        sizes.append(f"{w}x{h}: {t['n']} layer buttons, least {t['minH']:.1f} px tall, {t['overlap']} overlaps, {t['outside']} outside")
        assert t["n"] == 8 and t["minH"] >= 23.5 and not t["overlap"] and not t["outside"], f"platform_spec platform.html@{w}x{h}: {sizes[-1]} (want 8, >= 24 px, 0, 0); sizes {t['sizes']}"
    print(f"platform_spec: 8 layers in the markup with their jobs; opening each shows its job under its own named row, pressing it again closes it; at 1440 pointing sets has-hot at a steady height, the boundary after 04 (hairline {bd['off']} px from the plane), ArrowDown/Enter/Escape/End/Home; at 900 Tab/ArrowDown/Enter/Escape open and close layer 02's panel; "
          + "; ".join(sizes))


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


LAB_BOXES = """(() => { const l = document.querySelector('[data-swarm-live]'), h = e => e ? +e.getBoundingClientRect().height.toFixed(1) : null;
  return { on: l.classList.contains('sw-on'), lab: h(l), head: h(l.querySelector('.sw-head')), stage: h(l.querySelector('.sw-stage')),
    bar: h(l.querySelector('.swarm-bar')), btns: h(l.querySelector('.sw-btns')) }; })()"""


@check
async def lab_hold(b):
    """integrate hc1: the swarm lab's start moves nothing. With swarm.js blocked, the lab (Home §03, Platform §02) holds
    the boxes the running lab draws: the lab, its head, stage, bar and controls within 1 px at 1440 and on a 390 phone.
    hc1 moved Pause motion into the head; its place before the start moved with it (swarm.css), so a hold left in the
    controls, or none in the head where the phone's glyph shares the name's line, fails here."""
    bad, seen = [], []
    limit = int(15000 * max(1.0, MODE["throttle"]))
    for path, frag in (("index.html", "lc01"), ("platform.html", "swarm")):
        for w, h, touch in ((1440, 900, False), (390, 844, True)):
            got = []
            for block in (True, False):
                ctx = await b.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch, device_scale_factor=2 if touch else 1)
                pg = await ctx.new_page()
                if block: await pg.route("**/js/swarm.js*", lambda r: r.abort())  # path-agnostic: the deploy copy is versioned
                await pg.goto(f"{BASE}/{path}#{frag}", wait_until="load")
                await pg.evaluate("document.fonts.ready.then(() => 1)")
                if block: await pg.wait_for_timeout(int(2500 * max(1.0, MODE["throttle"])))
                elif not await until(pg, "!!document.querySelector('[data-swarm-live].sw-on')", limit, 200):
                    bad.append(f"{path}@{w}: the lab did not start within {limit} ms")
                else: await pg.wait_for_timeout(1000)
                got.append(await pg.evaluate(LAB_BOXES)); await ctx.close()
            st, lv = got
            if st["on"]: bad.append(f"{path}@{w}: the lab ran with swarm.js blocked")
            diff = {k: (st[k], lv[k]) for k in ("lab", "head", "stage", "bar", "btns") if st[k] is None or lv[k] is None or abs(st[k] - lv[k]) > 1}
            if diff: bad.append(f"{path}@{w}: static -> live boxes differ {diff}")
            seen.append(f"{path[:-5]}@{w} {lv['lab']}")
    assert not bad, "lab_hold:\n  " + "\n  ".join(bad)
    print(f"lab_hold: the lab's static boxes equal its live ones ({', '.join(seen)} px)")



# hc13r (home, HOME-2): every start of the lab's own act, from the document's start. hc22 (home, HC22 4.4): the act is the
# lab root's data-sw-act turning "on" (it was the follow button's pressed state); `ctl` counts every change of the Follow
# control (its pressed state, its text) while data-sw-act is set: the act must leave the control alone
ACT_WATCH = r"""(() => { const W = window, R = W.__act = { pressed: 0, t: [], ctl: 0 }; const go = () => { const r = document.querySelector('[data-swarm-live]'), f = document.querySelector('[data-sw-follow]'); if (!r || !f) return false;
    new MutationObserver(() => { if (r.dataset.swAct === 'on') { R.pressed++; R.t.push(Math.round(performance.now())); } }).observe(r, { attributes: true, attributeFilter: ['data-sw-act'] });
    new MutationObserver(() => { if (r.dataset.swAct) R.ctl++; }).observe(f, { attributes: true, attributeFilter: ['aria-pressed'], childList: true, characterData: true, subtree: true }); return true; };
  if (!go()) document.addEventListener('DOMContentLoaded', go, { once: true }); })();"""
LAB_SEEN = r"""(() => { const r = document.querySelector('[data-swarm-live]').getBoundingClientRect(); const v = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
  return Math.round(v / Math.max(1, Math.min(r.height, innerHeight)) * 1000) / 1000; })()"""
LAB_SIZE = "(() => [Math.round(document.querySelector('[data-swarm-live]').getBoundingClientRect().height * 10) / 10, document.documentElement.scrollHeight])()"


@check
async def lab_act(b):
    """hc13r (home, HOME-2, on system's SYS-3 OXA.actOnce; home's optional request 9): Home's lab acts by itself only as the
    rule allows. At 1440: once it is well in view it follows one proposal, quietly (its live region stays empty), across
    the six gates, and rests in its follow view; hc22 (HC22 4.4): through the act and at its rest the Follow control never
    changes (not pressed, "Follow a proposal"); it never acts again (no second follow at rest, nor
    after the lab leaves the screen and comes back). Under reduced motion it never acts (6 s in view). After a mouse press
    on one of its controls before it is 60% in view, it never acts. On a stacked lab (390 phone, 1024) the act leaves the
    lab's height and the page's unchanged (no layout shift without input)."""
    bad, notes = [], []
    lim = lambda ms: int(ms * max(1.0, MODE["throttle"]))
    center = "document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})"
    # 1. the act, once, quiet, to its rest
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=ACT_WATCH)
    await pg.mouse.move(5, 450)
    await pg.evaluate(center)
    if not await until(pg, "document.querySelector('[data-swarm-live]').dataset.swAct === 'on'", lim(6000), 100):
        bad.append("1440: the lab did not follow a proposal by itself within 6 s in view")
    else:
        if await pg.evaluate("document.querySelector('[data-sw-say]').textContent !== ''"): bad.append("1440: the act announced itself")
        if not await until(pg, LAB_ACT_REST + " && document.querySelectorAll('[data-sw-gates] li.is-hit').length === 6", lim(20000), 200):
            bad.append(f"1440: the act did not rest in its follow view across six gates: {await pg.evaluate(TRACE_STATE)!r}")
        say = await pg.evaluate("document.querySelector('[data-sw-say]').textContent")
        if say: bad.append(f"1440: the act announced {say!r}")
        if await pg.evaluate("window.__act.ctl"): bad.append("1440: the Follow control changed without input during the act")
        await pg.wait_for_timeout(4000)
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(1200)
        await pg.evaluate(center); await pg.wait_for_timeout(lim(4000))
        n = await pg.evaluate("window.__act.pressed")
        if n != 1: bad.append(f"1440: the follow was pressed {n} times without input (one act expected, also after leaving and coming back)")
        notes.append(f"1440 acted once ({n})")
    await ctx.close()
    # 2. never under reduced motion
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=ACT_WATCH, reduced=True)
    await pg.mouse.move(5, 450)
    await pg.evaluate(center); await pg.wait_for_timeout(lim(6000))
    n = await pg.evaluate("window.__act.pressed")
    if n: bad.append(f"reduced motion: the lab followed by itself ({n})")
    await ctx.close()
    # 3. never after a press on one of its controls before it is well in view (the loader gone first: until then its
    # overlay takes the press)
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=ACT_WATCH)
    await pg.locator(".loader").wait_for(state="detached", timeout=lim(15000))
    await pg.evaluate("(() => { const r = document.querySelector('[data-swarm-live]'); window.__pd = []; r.addEventListener('pointerdown', e => window.__pd.push(e.pointerType + ' ' + e.target.tagName), true); })()")
    await pg.evaluate("(() => { const r = document.querySelector('[data-swarm-live]').getBoundingClientRect(); window.scrollTo({top: r.bottom + scrollY - innerHeight * 0.32, behavior: 'instant'}); })()")
    await pg.wait_for_timeout(300)
    seen = await pg.evaluate(LAB_SEEN)
    box = await pg.locator("[data-sw-strict]").bounding_box()
    if seen >= 0.6 or not box or box["y"] < 0 or box["y"] + box["height"] > 900:
        bad.append(f"press: could not reach the Council slider with the lab under 60% in view (seen {seen}, slider {box})")
    else:
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.mouse.up()
        await pg.mouse.move(5, 450)
        pd = await pg.evaluate("window.__pd")
        if not any(x.startswith("mouse") for x in pd): bad.append(f"press: the mouse press did not reach the lab ({pd})")
        await pg.evaluate(center); await pg.wait_for_timeout(lim(5000))
        n = await pg.evaluate("window.__act.pressed")
        if n: bad.append(f"press: after a mouse press on the Council slider (lab {seen:.0%} in view) the lab followed by itself ({n})")
        notes.append(f"pressed at {seen:.0%} in view")
    await ctx.close()
    # 4. stacked labs: the act moves nothing
    for w, h, touch in ((390, 844, True), (1024, 768, False)):
        ctx, pg = await open_page(b, "index.html", w, h, touch=touch, init=ACT_WATCH)
        await pg.evaluate(center); await pg.wait_for_timeout(200)
        # The engine names the lab stacked in its first resize(), once it has started. Under CI's software GL that can be
        # later than 200 ms (run 42785737245 read 1024 too early), so wait for it, then measure.
        stacked = await until(pg, "document.querySelector('[data-swarm-live]').classList.contains('is-stacked')", lim(6000), 100)
        before = await pg.evaluate(LAB_SIZE)
        if not await until(pg, "document.querySelector('[data-swarm-live]').dataset.swAct === 'on'", lim(6000), 100):
            bad.append(f"{w}: the lab did not follow a proposal by itself within 6 s in view")
        else:
            during = await pg.evaluate(LAB_SIZE)
            await until(pg, LAB_ACT_REST, lim(20000), 200)
            after = await pg.evaluate(LAB_SIZE)
            trace = await pg.evaluate("(() => { const t = document.querySelector('#sw-trace, [data-sw-callout]'); return t ? t.hidden : null; })()")
            if not stacked: bad.append(f"{w}: the lab is not stacked")
            if any(abs(x[0] - before[0]) > 0.5 or x[1] != before[1] for x in (during, after)):
                bad.append(f"{w}: the act moved the page: lab height / page height {before} -> {during} (acting) -> {after} (rest)")
            if trace is False: bad.append(f"{w}: the act opened the trace on a stacked lab")
            notes.append(f"{w} held {before[0]} px")
        await ctx.close()
    assert not bad, "lab_act:\n  " + "\n  ".join(bad)
    print(f"lab_act: Home's lab acts once, quietly, to its rest at 1440; never under reduced motion; never after a press on a control before it is in view; the act moves nothing on a stacked lab ({'; '.join(notes)})")

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
        # hc13r (home, HOME-2): Home's lab follows one proposal by itself once it is well in view; the reader's follow waits
        # for the act's rest (hc22, HC22 4.4: data-sw-act="rest", the control unpressed, "Follow a proposal"; a press during
        # the act would start the reader's follow, no longer stop the act)
        if path == "index.html" and not await until(pg, LAB_ACT_REST, 40000, 250):
            bad.append(f"{tag}: the lab's own act never came to rest ({await pg.evaluate(TRACE_STATE)!r})"); await ctx.close(); continue
        for want in wants:
            await pg.evaluate(SET_RANGE, ["[data-sw-strict]", 0 if want == "settled" else 60])
            # integrate hc20: up to 10 follows for a rejection (was 6): at the range's top (60%) about 6 in 10 are rejected
            # (trace_probe.py: 10 of 16), so six settled in a row, ~0.4% by chance, failed one full run; ten, ~0.01%
            seen = await follow_once(pg, want, tries=1 if want == "settled" else 10)
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


# ---- the ledger: time only moves forward (LG-R2-2; the digests of LG-R2-3 left with Home's stream, 1 Nov)
def stamp_ms(t):
    m = re.fullmatch(r"(\d\d):(\d\d):(\d\d)(?:\.(\d{1,3}))?", t)
    return None if not m else ((int(m[1]) * 60 + int(m[2])) * 60 + int(m[3])) * 1000 + int((m[4] or "0").ljust(3, "0"))


@check
async def ledger_time(b):
    """time moves forward in the ledger (LG-R2-2): on Trust at 1440 the excerpt's nine records read their ids in sequence
    and timestamps that strictly increase, and a replay writes the same nine records again in the same order with the
    same stamps. v2x cut, owner's-eye fix (1 Nov): until then this read Home's live ledger fed by the swarm lab (40
    consecutive new records moving forward in time, and the foot's swarm totals equal to the digests seen, LG-R2-3); that
    stream left the site with Home's agent log, and no page carries swarm digests any more."""
    READ = r"""(() => [...document.querySelectorAll('[data-ledger=replay] .lt-rec')].map(li => { const t = s => ((li.querySelector(s) || {}).textContent || '').replace(/\s+/g, ' ').trim();
      return { id: t('.lt-id'), t: t('.lt-t'), ev: t('.lt-ev') }; }))()"""
    ctx, pg = await open_page(b, "trust.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-ledger=replay]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await until(pg, "(() => { const r = document.querySelector('[data-ledger=replay] [data-lt-replay]'); return !!r && !r.hidden; })()", 8000 if MODE["throttle"] <= 1 else 30000)
    before = await pg.evaluate(READ)
    await pg.locator("[data-ledger=replay] [data-lt-replay]").click()
    end = await until(pg, "/^Replayed/.test(document.querySelector('[data-ledger=replay] [data-lt-state]').textContent)", 20000, 100)
    after = await pg.evaluate(READ)
    await ctx.close()
    bad = []
    for tag, recs in (("before", before), ("after the replay", after)):
        if len(recs) != 9: bad.append(f"{tag}: {len(recs)} records (9 expected)")
        if any(stamp_ms(r["t"]) is None for r in recs): bad.append(f"{tag}: unreadable timestamps {[r['t'] for r in recs if stamp_ms(r['t']) is None][:3]}")
        back = [(a["id"], a["t"], c["id"], c["t"]) for a, c in zip(recs, recs[1:]) if (stamp_ms(c["t"]) or 0) <= (stamp_ms(a["t"]) or 0)]
        if back: bad.append(f"{tag}: {len(back)} of {len(recs) - 1} steps do not move forward in time, e.g. {back[:3]}")
        ids = [int(r["id"].lstrip("#"), 16) if re.fullmatch(r"#[0-9a-f]{4}", r["id"]) else None for r in recs]
        if None in ids or any(j != i + 1 for i, j in zip(ids, ids[1:])): bad.append(f"{tag}: the ids are not in sequence: {[r['id'] for r in recs]}")
    if not end: bad.append("the replay did not end within 20 s")
    elif after != before: bad.append(f"the replay changed the excerpt: {[(a['id'], a['t']) for a, c in zip(before, after) if a != c][:3]}")
    assert not bad, "ledger_time trust.html@1440x900:\n  " + "\n  ".join(bad)
    print(f"ledger_time: Trust's excerpt {before[0]['id']}...{before[-1]['id']} moves forward in time ({before[0]['t']} -> {before[-1]['t']}), and a replay writes the same nine records in the same order")


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
    text (at least 4.5:1) on white (no dark background colour or image behind it) (OV-R2-6). v2x cut (1 Nov): the scene
    kickers ('The work', 'The stack', 'The swarm', 'The proof') left the page, so every beat must print its headline and
    the first its kicker ('An AI agentic company'); every one of those that exists prints dark on white, as before"""
    ctx, pg = await open_page(b, "index.html", 1280, 900)
    await pg.emulate_media(media="print"); await pg.wait_for_timeout(800)
    els = await pg.evaluate(PRINT_BEATS)
    await ctx.close()
    bad = [e for e in els if e["o"] < 0.99 or e["hidden"] or not e["w"] or e["bg"] < 0.8 or e["img"] or e["cr"] < 4.5]
    beats = {e["beat"] for e in els if e["el"].startswith(("h1", "h2"))}
    kick0 = any(e["beat"] == 0 and re.search(r"eyebrow|kicker", e["el"]) for e in els)
    assert beats == set(range(5)) and kick0 and not bad, f"print_home index.html@1280 (print): beats with a headline {sorted(beats)}, scene 0's kicker {kick0}; {len(bad)} of {len(els)} overture text elements do not print as dark text on white (opacity 1, contrast >= 4.5, no dark background or image behind), e.g. {bad[:4]}"
    print(f"print_home: {len(els)} overture text elements print at opacity 1, dark on white")


# ---- 400% zoom: 320x256 reflows (PG-R2-5b, OV-R2-5c)
SHEET_FIT = """(() => { const s = document.querySelector('#site-menu');
  const over = [...s.querySelectorAll('a, button')].filter(a => a.getClientRects().length).map(a => [a.textContent.trim().slice(0, 18), Math.round(a.getBoundingClientRect().left), Math.round(a.getBoundingClientRect().right)])
    .filter(l => l[2] > innerWidth + 0.5 || l[1] < -0.5);
  return { sw: s.scrollWidth, cw: s.clientWidth, over }; })()"""
# v2x r2 (research's probe, work/research/r2/probe_r2.py "zoom"): the first screen's own text boxes in main (elements
# with a text node of their own, drawn, opacity > .05); figure labels (.fl) count only while their layer is on and they are
# not leaving. over: boxes past the right edge; hits: two boxes that cross (neither contains the other); lede: the first
# .lede's width; grid: the number of columns of the blog hero's grid (null elsewhere)
REFLOW_TEXT = """(() => {
  const vw = innerWidth, over = [], boxes = [];
  const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && +cs.opacity > 0.05 ? r : null; };
  document.querySelectorAll('main *').forEach(el => {
    if (![...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())) return;
    if (el.closest('.fl') && (el.closest('.fl.is-out') || !el.closest('.fig-labels.is-on'))) return;
    const r = vis(el); if (!r || r.bottom < 0 || r.top > innerHeight) return;
    if (r.right > vw + 0.5) over.push([String(el.className || el.tagName).slice(0, 30), Math.round(r.right), el.textContent.trim().slice(0, 40)]);
    // hc21: an inline element is measured line by line at its em box (its font-size, centred on each fragment), not by its
    // content area: a display serif's ascent + descent (1.3 em) reaches into the next line of the same heading although no
    // glyph does; a tighter leading than the em, a box moved over another, still cross
    const cs = getComputedStyle(el), fs = parseFloat(cs.fontSize);
    if (cs.display === 'inline') [...el.getClientRects()].forEach(f => { const h = Math.min(f.height, fs), c = (f.top + f.bottom) / 2;
      if (f.width > 0 && c + h / 2 >= 0 && c - h / 2 <= innerHeight) boxes.push([el, { left: f.left, right: f.right, top: c - h / 2, bottom: c + h / 2 }]); });
    else boxes.push([el, r]);
  });
  const hits = [];
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [c, rc] = boxes[j]; if (a.contains(c) || c.contains(a)) continue;
    if (ra.left < rc.right - 1 && rc.left < ra.right - 1 && ra.top < rc.bottom - 1 && rc.top < ra.bottom - 1) hits.push([a.textContent.trim().slice(0, 30), c.textContent.trim().slice(0, 30)]);
  }
  const lede = document.querySelector('main .lede'), g = document.querySelector('.blog-hero-grid');
  return { over, hits: hits.slice(0, 8), lede: lede ? Math.round(lede.getBoundingClientRect().width) : null,
           grid: g ? getComputedStyle(g).gridTemplateColumns.split(' ').filter(Boolean).length : null };
})()"""


@check
async def reflow_400(b):
    """at 320x256 (a 1280x1024 screen at 400%): no horizontal scroll on the seven hand-written pages
    (scrollWidth <= 320), and the overture either shows its static sequence (html.story-tiny) or, at each scene's rest,
    no visible callout crosses the copy; v2x r2: on Research, notes 06 and 09, the blog index and a post, no sideways
    scroll, no first-screen text past the edge or crossing other text, the lede >= 260 px, the blog hero one column"""
    bad = []
    for name in ("index", "platform", "lifecycles", "evidence", "trust", "company", "access"):
        ctx, pg = await open_page(b, f"{name}.html", 320, 256)
        await pg.wait_for_timeout(800)
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        if sw > 320: bad.append(f"{name}.html@320x256: scrollWidth {sw}")
        if name in ("index", "platform", "access"):  # v2x r1: the menu sheet reflows too (no sideways scroll, every link inside the width)
            await pg.locator(".nav-toggle").click()
            if not await until(pg, "document.querySelector('#site-menu').matches(':popover-open')", 3000): bad.append(f"{name}.html@320x256: the menu sheet did not open")
            else:
                await pg.wait_for_timeout(500)
                sh = await pg.evaluate(SHEET_FIT)
                if sh["sw"] > sh["cw"] or sh["over"]: bad.append(f"{name}.html@320x256: the menu sheet scrolls sideways (scrollWidth {sh['sw']} > clientWidth {sh['cw']}) or a link leaves the width: {sh['over'][:3]}")
                await pg.keyboard.press("Escape"); await until(pg, "!document.querySelector('#site-menu').matches(':popover-open')", 3000)
        if name == "index" and not await pg.evaluate("document.documentElement.classList.contains('story-tiny')"):
            for i in range(5):
                if not await scene_rest(pg, i): bad.append(f"index.html@320x256 scene 0{i}: no story-tiny and the scene did not come to rest"); continue
                m = await pg.evaluate(PHONE_LAB)
                hits = [x for x in m["issues"] if " x beat " in x]
                if hits: bad.append(f"index.html@320x256 scene 0{i} (no story-tiny): {hits[:3]}")
        await ctx.close()
    # v2x r2 (research, blog; r2-a11y serious): the generated pages too. A sideways-phone two-up hero also fired at 400 %
    # zoom (labels over titles, a hedge cut at the edge, ledes in a 151 px column) because this check opened only the
    # seven hand-written pages. At 320x256 (DPR 4): no horizontal scroll; no visible first-screen text in main past the
    # right edge; no two first-screen text boxes cross (a figure label counts only while its layer is on and it is not
    # leaving); the lede is at least 260 px wide; the blog's hero is one column.
    # hc21 (integrate): the research heroes lead with their titles on phones, so note 06's h1 is on this first screen: an
    # inline span in it (`.nw`, "Post-Training") is now measured at its em box per line (REFLOW_TEXT), not its 1.3 em content
    # area, which reached 4 px into the next line's box with no glyph crossing (TESTS.md section 43)
    for name in ("research", "research/06-post-training-on-a-rulebook", "research/09-lifecycle-01-ten-sessions", "blog/index", "blog/in-search-gen-ai-business-model"):
        ctx, pg = await open_page(b, f"{name}.html", 320, 256, dpr=4)
        await pg.wait_for_timeout(2600)  # the figure's labels come and go on their own clock
        sw = await pg.evaluate("document.documentElement.scrollWidth")
        if sw > 320: bad.append(f"{name}.html@320x256: scrollWidth {sw}")
        r = await pg.evaluate(REFLOW_TEXT)
        if r["over"]: bad.append(f"{name}.html@320x256: first-screen text past the right edge: {r['over'][:3]}")
        if r["hits"]: bad.append(f"{name}.html@320x256: first-screen text boxes cross: {r['hits'][:3]}")
        if r["lede"] is not None and r["lede"] < 260: bad.append(f"{name}.html@320x256: the lede is {r['lede']} px wide (at least 260)")
        if r["grid"] is not None and r["grid"] != 1: bad.append(f"{name}.html@320x256: the blog hero has {r['grid']} columns (one at 400 % zoom)")
        await ctx.close()
    assert not bad, "reflow_400:\n  " + "\n  ".join(bad)
    print("reflow_400: the seven pages reflow at 320x256 (the menu sheet too, on Home, Platform and Access); the overture is the static sequence or keeps its callouts off the copy; "
          "Research, notes 06 and 09, the blog index and a post: no sideways scroll, no text past the edge or over other text, ledes >= 260 px, the blog hero one column")


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
    and the trace's ledger link, the desk's threshold slider among them (NV-R2-5, SW-R2-3, LC-R2-3). v2x cut, owner's-eye
    fix (1 Nov): Home has no ledger, so a settled trace ends in a link 'Ledger' named 'The ledger on the Trust page'
    (it was a record button 'record #id · hash' answered by Home's ledger)"""
    bad, n = [], 0
    for name in ("index", "platform", "lifecycles", "evidence", "trust", "company", "access"):
        ctx, pg = await open_page(b, f"{name}.html", 1440, 900)
        cdp = await ctx.new_cdp_session(pg)
        if name == "index":  # the trace's ledger link exists once a followed proposal has settled; hc13r (HOME-2): the lab's
            # own act follows one the Council passes, once the lab is well in view, and rests on it without a click; hc22
            # (HC22 4.4): the act leaves the control at "Follow a proposal", read here like every control
            await pg.mouse.move(2, 2)
            await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
            await until(pg, "+((document.querySelector('[data-sw-inflight]') || {}).textContent || '0').replace(/\\D/g, '') > 0", 25000, 200)
            if not await until(pg, LAB_ACT_REST + " && !!document.querySelector('[data-sw-log] a.sw-led-a')", 60000, 250): bad.append("index.html: no ledger link in the trace of the lab's own act after 60 s (nothing to check)")
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
    """in forced colours (Windows High Contrast), a Tab onto the lab's strictness slider (home), Access's #name, the
    desk's threshold slider (Lifecycles) and, at 390, the menu toggle (v2x r1) changes at least 100 pixels by 3:1 or more
    around the control (the focus ring in the system colours; method of r2/a11y/focus_pix.py)"""
    from PIL import Image
    import io
    bad, got = [], []
    for path, sel, W, Hh in (("index.html", "[data-sw-strict]", 1440, 900), ("access.html", "#name", 1440, 900), ("lifecycles.html", "[data-gap-thr]", 1440, 900),
                             ("index.html", ".nav-toggle", 390, 844)):  # v2x r1: the phone's menu toggle
        ctx = await b.new_context(viewport={"width": W, "height": Hh}, forced_colors="active", reduced_motion="reduce")
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/{path}", wait_until="load"); await until(pg, LOADED, 15000); await pg.wait_for_timeout(1200)
        await pg.mouse.move(2, Hh - 2)
        if await pg.evaluate(FOCUS_PREP, sel) is None: bad.append(f"{path}: no {sel}"); await ctx.close(); continue
        await pg.wait_for_timeout(500); await pg.keyboard.press("Tab"); await pg.wait_for_timeout(600)
        on = await pg.evaluate("(s) => document.activeElement === document.querySelector(s)", sel)
        r = await pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }", sel)
        x0, y0 = max(0, r[0] - 10), max(0, r[1] - 10)
        clip = {"x": x0, "y": y0, "width": min(W, r[0] + r[2] + 10) - x0, "height": min(Hh, r[1] + r[3] + 10) - y0}
        fimg = Image.open(io.BytesIO(await pg.screenshot(clip=clip, animations="disabled"))).convert("RGB")
        await pg.evaluate("document.activeElement && document.activeElement.blur()"); await pg.wait_for_timeout(600)
        uimg = Image.open(io.BytesIO(await pg.screenshot(clip=clip, animations="disabled"))).convert("RGB")
        await ctx.close()
        fb, ub = fimg.tobytes(), uimg.tobytes()
        fp, up = [tuple(fb[i:i + 3]) for i in range(0, len(fb), 3)], [tuple(ub[i:i + 3]) for i in range(0, len(ub), 3)]
        changed = [(a, c) for a, c in zip(fp, up) if max(abs(a[0] - c[0]), abs(a[1] - c[1]), abs(a[2] - c[2])) > 10]
        good = sum(1 for a, c in changed if contrast(a, c) >= 3)
        got.append(f"{path} {sel}: {good}")
        if not on: bad.append(f"{path}@{W} (forced colours): Tab did not land on {sel}")
        elif good < 100: bad.append(f"{path}@{W} (forced colours): focusing {sel} changes {len(changed)} px, {good} of them by 3:1 or more (100 needed)")
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
    """no grey slab: on /blog/ at 1440 (incomplete last rows) and on Trust's control plane (#control; §02 until v2x) at t=0 of its reveal (animations held at
    their start; since hc26r the plate has no reveal, its scene is its entrance, so this is the plate as it stands), no area of rgba(14,21,18,.14) over the paper wider than a rule (a 3x3 block; images excluded) shows in
    a card grid (PG-R2-2: the rules are drawn on the cells, not as the container's background between them). hc13r
    (proof, PROOF-1): Trust's six boxed K-plates became one control-plane plate, an <ol> of six stations
    (#control .tr-st), read the same way in their place"""
    bad = []
    ctx, pg = await open_page(b, "blog/index.html", 1440, 900, reduced=True)
    out, n = await grid_slabs(pg, ".blog-grid", "blog/index.html@1440")
    bad += out
    if not n: bad.append("blog/index.html: no .blog-grid")
    await ctx.close()
    ctx, pg = await open_page(b, "trust.html", 1440, 900)
    cdp = await ctx.new_cdp_session(pg)
    await cdp.send("Animation.enable"); await cdp.send("Animation.setPlaybackRate", {"playbackRate": 0})
    await pg.evaluate("(() => { const g = document.querySelector('#control .tr-st'); if (g) g.setAttribute('data-oxa-grid', ''); })()")
    out, n = await grid_slabs(pg, "[data-oxa-grid]", "trust.html@1440 #control at t=0 of its reveal", hold=True)
    await cdp.send("Animation.setPlaybackRate", {"playbackRate": 1})
    bad += out
    if not n: bad.append("trust.html: no control plane (.tr-st) in #control")
    await ctx.close()
    assert not bad, "grid_slab:\n  " + "\n  ".join(bad[:10])
    print("grid_slab: no grey slab in the blog's grids or in Trust's control plane (its six stations) before they arrive")


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
# story.js: four scenes plus the pinned exit, spread over the story's scroll run. hc15 (home, the director's 4.1): the exit
# is 0.9 of a scene from 600 px (the standing chart holds longer: 4.9 scenes, home.css 343svh) and 0.6 under it (4.6:
# overture.css 322svh, home.css 230svh on portrait phones), so the scene count follows the stage's width. hc16 (home, the
# director's 4.1): on wide, non-short screens the story ends in a tail, the paper's slack, that the run leaves out
# (story.js run = storyH - stageH - tail); §01 is pulled up by as much (its negative margin-top), read from there
STORY_Y = """(s) => { const st = document.querySelector('.story'), stage = st.querySelector('.story-stage') || st.firstElementChild;
  const units = (stage ? stage.clientWidth : innerWidth) < 600 ? 4.6 : 4.9;
  const tail = st.nextElementSibling ? Math.max(0, -parseFloat(getComputedStyle(st.nextElementSibling).marginTop) || 0) : 0;
  return Math.round(st.getBoundingClientRect().top + scrollY + Math.max(1, st.offsetHeight - (stage ? stage.offsetHeight : innerHeight) - tail) * s / units); }"""
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
    above .1; from S0 to S1 .story-num never shows '00' (every frame) (OV-R2-2). v2x cut (1 Nov): scenes 3 and 4 have
    no paragraph any more (the headline is the scene's one line), so a beat without a .body-lg is complete when every
    headline word has risen; a beat that has one still needs it at >= .9. hc16: and the scene index lands scenes 1-4 where
    STORY_Y puts them (2 px): the stops are where the check means them"""
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
                whole = [x["i"] for x in st if x["n"] and x["up"] == x["n"] and (x["body"] is None or x["body"] >= 0.9)]
                eyes = [(x["i"], x["eye"]) for x in st if x["i"] not in whole and x["eye"] > 0.1]
                if len(whole) != 1 or eyes:
                    bad.append(f"{tag} S{i}->S{i + 1} stop at {int(f * 100)}% (s={s:.2f}, y={y}): complete beats {whole}, other eyebrows {eyes}; "
                               f"beats [words up/n, body, eyebrow] {[(x['up'], x['n'], x['body'], x['eye']) for x in st]}")
        # hc16 (integrate): the check's model of the run is the page's own: the scene index lands each scene where STORY_Y
        # puts it (2 px), so a change in the run's length (hc15's 4.9 scenes, hc16's paper slack) fails here, not by drift
        for i in range(1, 5):
            await pg.evaluate(f"document.querySelectorAll('.story-idx button')[{i}].click()"); await pg.wait_for_timeout(900)
            yi, ys = await pg.evaluate(f"[Math.round(scrollY), ({STORY_Y})({i})]")
            if abs(yi - ys) > 2: bad.append(f"{tag}: the scene index lands scene {i} at y={yi}, STORY_Y({i}) says {ys}: the check's run is not the page's")
        await ctx.close()
    assert not bad, f"overture_rest: {len(bad)} problems ({n} stops):\n  " + "\n  ".join(bad[:16])
    print(f"overture_rest: {n} stops mid-hand-over at 1440 (wheel) and 390 (touch) each settle on one complete headline; no '00'")



# ---- hc17 (integrate; the director's 4.1, hc16 wide + hc17 stacked): §01 opens one chapter opening under the paper's caption
# hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1): the strip (.story-paper-cap) is gone
# and §01 itself is the paper; `cap` reads the strip's rule if a page still has one (else null), `hit` says whether the
# point 2 px under §01's top, mid-width, is §01's (it covers the stage it has passed over)
PAPER_OPEN = """() => { const st = document.querySelector('.story'), sec = st && st.nextElementSibling;
  const paper = document.querySelector('.story-paper'), cap = document.querySelector('.story-paper-cap'), h = sec && sec.querySelector('h2');
  if (!paper || !h) return null;
  let p = document.getElementById('__vopen');
  if (!p) { p = document.createElement('i'); p.id = '__vopen'; p.setAttribute('aria-hidden', 'true'); const ps = p.style;
    ps.position = 'absolute'; ps.left = ps.top = '0'; ps.width = '0'; ps.height = 'var(--sec-open)'; ps.visibility = 'hidden'; ps.pointerEvents = 'none'; document.body.appendChild(p); }
  const pr = paper.getBoundingClientRect(), shown = getComputedStyle(paper).visibility !== 'hidden' && pr.height > .5;
  const sr = sec.getBoundingClientRect(), nav = document.querySelector('.nav'), navB = nav ? nav.getBoundingClientRect().bottom : 0;
  const at = sr.top + 2 < innerHeight ? document.elementFromPoint(innerWidth / 2, Math.max(0, sr.top) + 2) : null;
  return { y: Math.round(scrollY), open: parseFloat(getComputedStyle(p).height) || 0, paper: shown ? Math.round(pr.top) : null,
    cap: cap ? Math.round(cap.getBoundingClientRect().bottom) : null, sec: Math.round(sr.top), h2: Math.round(h.getBoundingClientRect().top),
    navB: Math.round(navB), hit: at ? sec.contains(at) : null,
    tail: Math.max(0, -parseFloat(getComputedStyle(sec).marginTop) || 0), end: Math.round(st.offsetTop + st.offsetHeight), H: innerHeight }; }"""


@check
async def paper_opening(b):
    """hc17 (integrate, new coverage for the director's hc16 / hc17 item 4.1): the overture hands over to §01 as a chapter
    opens. At 390 x 844 (touch), 768 x 1024, 1024 x 1366, 1440 x 900 and 3840 x 2160: at the release (story end - h, the
    stage starts to move) §01's heading stands one --sec-open under the paper caption's rule (4 px), where the frame once
    left 150-750 px of blank paper (stacked: 295 px at 390, 572 at 1024 x 1366); and on a wheel walk in 0.1 h steps from
    scene 4's rest to half a screen past the release, each step settled, §01's top never shows above the paper's top (over
    the dark stage) or over the caption
    hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1: "the paper wipes the chart",
    the ten-tick strip deleted): §01 itself is the paper now (lifted over the pinned stage, one screen of slack; the
    empty `.story-paper` tracks its top), so the same chapter opening reads: at the release (story end - h) §01's top
    is at the viewport's top (2 px) and its heading one --sec-open under it (4 px); on the walk, wherever §01's top
    shows between the bar's foot and the screen's foot, the paper is drawn with its top on §01's top (1 px: never §01
    over the dark stage) and §01 covers what it has passed over (the point 2 px under its top, mid-width, is §01's).
    The caption clause stays for a page that draws the strip again."""
    bad, n = [], 0
    for w, h, touch in ((390, 844, True), (768, 1024, False), (1024, 1366, False), (1440, 900, False), (3840, 2160, False)):
        tag = f"index.html@{w}x{h}"
        ctx, pg = await open_page(b, "index.html", w, h, touch=touch)
        await pg.wait_for_timeout(1500)
        g = await pg.evaluate(PAPER_OPEN)
        if not g: bad.append(f"{tag}: no .story-paper / §01 h2"); await ctx.close(); continue
        rel = g["end"] - h
        await pg.evaluate(f"window.scrollTo({{top: {rel}, behavior: 'instant'}})"); await pg.wait_for_timeout(1500)
        at = await pg.evaluate(PAPER_OPEN)
        gap = at["h2"] - (at["cap"] if at["cap"] is not None else at["sec"])
        if at["paper"] is None: bad.append(f"{tag} at the release (y={at['y']}): the paper is not drawn")
        elif at["cap"] is None and abs(at["sec"]) > 2: bad.append(f"{tag} at the release (y={at['y']}): §01's top at {at['sec']} (the viewport's top, 2 px)")
        if abs(gap - at["open"]) > 4: bad.append(f"{tag} at the release (y={at['y']}): §01's heading {gap} px under {'the caption' if at['cap'] is not None else '§01'}'s top, --sec-open is {at['open']:.1f} (tail {at['tail']})")
        y0 = await pg.evaluate(STORY_Y, 3.95)
        y1 = rel + round(0.45 * h)
        await pg.evaluate(f"window.scrollTo({{top: {y0}, behavior: 'instant'}})"); await pg.wait_for_timeout(1200)
        await pg.mouse.move(w // 2, h // 2)
        cur, step, steps = await pg.evaluate("scrollY"), max(1, round(0.1 * h)), 0
        for y in range(y0, y1 + step, step):
            while cur < y - 3:
                await pg.mouse.wheel(0, min(120, y - cur)); await pg.wait_for_timeout(30); cur = await pg.evaluate("scrollY")
            await pg.wait_for_timeout(750)
            s = await pg.evaluate(PAPER_OPEN); n += 1; steps += 1
            if s["cap"] is not None:
                if s["sec"] < h - 1:
                    if s["paper"] is None or s["sec"] < s["paper"] - 1: bad.append(f"{tag} y={s['y']}: §01's top at {s['sec']} over the dark stage (paper top {s['paper']})")
                    elif s["cap"] > 0 and s["sec"] < s["cap"] + 1: bad.append(f"{tag} y={s['y']}: §01's top at {s['sec']} covers the paper's caption (rule at {s['cap']})")
            elif s["navB"] < s["sec"] < h - 1:
                if s["paper"] is None or abs(s["sec"] - s["paper"]) > 1: bad.append(f"{tag} y={s['y']}: §01's top at {s['sec']}, the paper's top at {s['paper']} (§01 is the paper: 1 px)")
                if s["hit"] is False: bad.append(f"{tag} y={s['y']}: the point under §01's top ({s['sec']}) is not §01's: the stage shows over it")
        print(f"  {tag}: {'rule' if at['cap'] is not None else '§01 top'} -> heading {gap} px (--sec-open {at['open']:.1f}, tail {at['tail']}, top {at['sec']}); {steps} settled steps")
        await ctx.close()
    assert not bad, f"paper_opening: {len(bad)} problems ({n} steps):\n  " + "\n  ".join(bad[:16])
    print(f"paper_opening: §01 is the paper and opens one --sec-open under its top at the release at five sizes; {n} settled steps, its top on the paper's, never over the dark stage")


# ---- hc18 (integrate; the director's HC18 4.2-4.4, done by platform, proof and home): under text-wrap: balance (site.css,
# hc17) no lede, chapter line, beat sentence or hedge ends a line on an article, determiner or short preposition
LINE_ENDS_WEAK = ["a", "an", "the", "of", "to", "for", "and", "on", "in", "at", "any", "by", "or", "its", "your", "with", "from", "as", "every", "each"]
LINE_ENDS = r"""(weak) => { const W = new Set(weak), out = [];
  document.querySelectorAll('main :is(.lede, .ch-line, .body-lg, .pf-lc-hedge)').forEach(p => {
    const r0 = p.getBoundingClientRect(); if (r0.width < 2 || r0.height < 2) return;
    const tw = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let n; const words = [];
    while ((n = tw.nextNode())) { const re = /\S+/g; let m; while ((m = re.exec(n.textContent))) {
      const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length);
      const rr = rg.getClientRects()[0]; if (rr && rr.width > 0) words.push([m[0], rr.top]); } }
    const lines = []; let cur = [], top = null;
    for (const [t, y] of words) { if (top !== null && Math.abs(y - top) > 4) { lines.push(cur); cur = []; } top = y; cur.push(t); }
    if (cur.length) lines.push(cur);
    const bad = lines.slice(0, -1).map(l => l[l.length - 1]).filter(x => !/[.,;:!?’”)]$/.test(x) && W.has(x.toLowerCase()));
    if (bad.length) out.push({ sec: (p.closest('section') || {}).id || '', bad, lines: lines.map(l => l.join(' ')) });
  }); return out; }"""
LINE_ENDS_PAGES = ["index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "research.html", "company.html", "access.html", "blog/index.html", "404.html"]


@check
async def lede_line_ends(b):
    """hc18 (integrate, new coverage for the director's HC18 4.2-4.4): the balanced ledes (site.css's hc17 text-wrap:
    balance on .lede, .ch-line, .body-lg) let Chromium end a line on "a", "the", "its" or "for" (six ledes on HEAD 1435ec9,
    Home's scene 4 at 390 among them); the groups glued each weak word to its phrase (.nowrap spans, no-break spaces;
    same words). On Home, Platform, Lifecycles, Proof, Trust, Research, Access and the Blog index, reduced motion, at
    1920 x 1080, 1440 x 900, 768 x 1024, 390 x 844 and 320 x 568 (touch): no line but the last of a .lede, .ch-line,
    .body-lg or .pf-lc-hedge in <main> ends on an article, determiner or short preposition (LINE_ENDS_WEAK, the
    director's rag18 set + every / each; a word carrying punctuation closes its phrase and never counts: "in each,"). hc19
    (integrate): Company joins the list, its §03 line (build_team.py) now "led work at&nbsp;Google, ..." (company hc19, the
    director's HC19 4.6); it ended "led work at / Google, ..." at 1920, 1440 and 768 on hc18's tree; and the 404, whose lede
    (launch_meta_v9.py, system hc19) now glues "or&nbsp;never&nbsp;existed" (it ended "has moved, or / never existed" at 390)"""
    bad, n = [], 0
    for w, h, touch in ((1920, 1080, False), (1440, 900, False), (768, 1024, False), (390, 844, True), (320, 568, True)):
        for path in LINE_ENDS_PAGES:
            ctx, pg = await open_page(b, path, w, h, touch=touch, reduced=True)
            await pg.wait_for_timeout(600)
            for x in await pg.evaluate(LINE_ENDS, LINE_ENDS_WEAK):
                bad.append(f"{path}@{w}x{h} #{x['sec']}: ends a line on {x['bad']}: " + " / ".join(x["lines"]))
            n += 1
            await ctx.close()
    assert not bad, f"lede_line_ends: {len(bad)} lines ({n} page loads):\n  " + "\n  ".join(bad[:20])
    print(f"lede_line_ends: no lede, chapter line, beat sentence or hedge ends a line on a weak word ({len(LINE_ENDS_PAGES)} pages x 5 sizes, {n} loads)")

# ---- hc19 (integrate; real breakage found by verify_budget home_landing): Home's chapters after the overture are laid out
# near the screen only (content-visibility: auto); each stand-in is the chapter's drawn content height, so the page is as
# long at load as drawn, in short windows too
STANDINS = r"""async () => { const out = [];
  for (const s of document.querySelectorAll('main > *')) { const c = getComputedStyle(s); if (c.contentVisibility !== 'auto') continue;
    const est = parseFloat(c.containIntrinsicHeight.split(' ').pop()); s.scrollIntoView({ behavior: 'instant' });
    await new Promise(r => setTimeout(r, 400)); const d = getComputedStyle(s), h = s.getBoundingClientRect().height - parseFloat(d.paddingTop) - parseFloat(d.paddingBottom) - parseFloat(d.borderTopWidth) - parseFloat(d.borderBottomWidth);
    out.push([s.id || s.classList[0], Math.round((est - h) * 10) / 10]); } return out; }"""


@check
async def home_standins(b):
    """hc19 (integrate): system's hc19 let the lab's stage give way in a short window (swarm.css --sw-h: 100vh - 31rem),
    and Home §02's stand-in (home.css #lc01 --cis, one value per width band) kept the tall stage: 127 px too tall at
    1440 x 900, 150 at 1280 x 800, 68 at 1024 x 768, so a place read before §02 was drawn moved by that much once it was
    (verify_budget home_landing: §03 at -47 for 80). The stand-in now gives way with the stage. At 1024 x 768,
    1280 x 800, 1440 x 900, 1920 x 1080 and 3840 x 2160 (the band widths the stand-ins were measured at; laptop heights),
    reduced motion: every content-visibility: auto chapter of Home is within 5 px of its drawn content height (padding and
    border off) once drawn."""
    bad, n, worst = [], 0, 0.0
    for w, h in ((1024, 768), (1280, 800), (1440, 900), (1920, 1080), (3840, 2160)):
        ctx, pg = await open_page(b, "index.html", w, h, reduced=True)
        await pg.wait_for_timeout(600)
        rows = await pg.evaluate(STANDINS)
        n += len(rows)
        for sid, d in rows:
            worst = max(worst, abs(d))
            if abs(d) > 5: bad.append(f"index.html@{w}x{h} #{sid}: stand-in {d:+.1f} px against the drawn chapter")
        if not rows: bad.append(f"index.html@{w}x{h}: no content-visibility chapter found")
        await ctx.close()
    assert not bad, "home_standins:\n  " + "\n  ".join(bad)
    print(f"home_standins: Home's {n} chapter stand-ins at 5 laptop windows within {worst:.1f} px of the drawn chapters (budget 5)")

# ---- hc19 (integrate, standing in for tests; platform's optional request): Platform §03's pipeline acts once by the
# site's rule (plate.js: OXA.actOnce -> .is-run; platform.css), then rests as the still it is without the pass
PIPE = "#pipeline .pipe-fig"
PIPE_STATE = r"""(() => { const f = document.querySelector('#pipeline .pipe-fig'); if (!f) return null; const r = f.getBoundingClientRect();
  const an = f.getAnimations({ subtree: true }).filter(a => a.playState === 'running');
  return { run: f.classList.contains('is-run'), running: an.length, names: [...new Set(an.map(a => a.animationName || a.transitionProperty || '?'))].sort(),
    box: [Math.round(r.top), Math.round(r.height)], vh: innerHeight }; })()"""
PIPE_NAMES = {"pp-ride", "pp-lit", "pp-on", "pl-pop"}  # the ring's ride, a gate lit, its lines on, a record written


@check
async def pipeline_once(b):
    """hc19 (integrate, standing in for tests; platform's optional request; the director's HC19 4.2, done by platform):
    Platform §03's pipeline drawing (`#pipeline .pipe-fig`) acts by the site's one rule (OXA.actOnce, site.js), as Trust
    §02 and Proof §01 did until hc26r (they are scroll scenes now: plate_scenes). At 1440 x 900, scrolled to the middle of the screen, it gains .is-run within 4 s and plays its one
    pass (the ring's ride, the gates lit, the records written: pp-ride, pp-lit, pp-on, pl-pop among its running
    animations); within 4 s more nothing in it is running, and the drawing then equals, pixel for pixel (no more than 0.05%
    of its pixels off by more than 8 levels), the same page with the pass cancelled (a keydown inside the figure before it
    is in view, which must also keep .is-run away). It never plays twice: after leaving the screen and coming back, nothing
    in it runs. Under reduced motion (1440 x 900, 5 s in view) and on a 390 x 844 phone (the drawing is the list there,
    display: none) it never gains .is-run."""
    import io
    from PIL import Image, ImageChops
    bad, notes = [], []
    lim = lambda ms: int(ms * max(1.0, MODE["throttle"]))
    center = "(s) => document.querySelector(s).scrollIntoView({block: 'center', behavior: 'instant'})"

    async def still(pg):
        box = await pg.evaluate(BOX, PIPE)
        img = await pg.screenshot(clip={"x": box[0], "y": box[1], "width": box[2], "height": box[3]}, animations="disabled", timeout=60000)
        return Image.open(io.BytesIO(img)).convert("RGB")

    # 1. the pass, once, to its rest
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    await pg.mouse.move(5, 450)
    await pg.evaluate(center, PIPE)
    ran = None
    if not await until(pg, f"document.querySelector('{PIPE}').classList.contains('is-run')", lim(4000), 50):
        bad.append(f"1440: the pipeline did not act within 4 s in view: {await pg.evaluate(PIPE_STATE)!r}")
    else:
        st = await pg.evaluate(PIPE_STATE)
        seen = set(st["names"])
        for _ in range(12):  # the gates light and the records pop on their own delays: gather what runs over the first ~1.2 s
            await pg.wait_for_timeout(100)
            seen |= set((await pg.evaluate(PIPE_STATE))["names"])
        if not PIPE_NAMES <= seen: bad.append(f"1440: the pass did not play: running {sorted(seen)}, expected {sorted(PIPE_NAMES)} among them")
        if not await until(pg, "(() => document.querySelector('#pipeline .pipe-fig').getAnimations({ subtree: true }).every(a => a.playState !== 'running'))()", lim(4000), 100):
            bad.append(f"1440: still running 4 s after the pass began: {await pg.evaluate(PIPE_STATE)!r}")
        else:
            await pg.wait_for_timeout(300)
            ran = await still(pg)
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(1200)
        await pg.evaluate(center, PIPE); await pg.wait_for_timeout(lim(3000))
        again = await pg.evaluate(PIPE_STATE)
        if again["running"]: bad.append(f"1440: the pass played again after leaving the screen and coming back: {again!r}")
        notes.append(f"1440 acted once ({', '.join(sorted(seen & PIPE_NAMES))})")
    await ctx.close()
    # 2. the pass cancelled (a keydown inside the figure before it is in view): never runs; the still it rests as
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    await pg.mouse.move(5, 450)
    await pg.evaluate("(s) => document.querySelector(s).dispatchEvent(new KeyboardEvent('keydown', {bubbles: true}))", PIPE)
    await pg.evaluate(center, PIPE); await pg.wait_for_timeout(lim(4500))
    st = await pg.evaluate(PIPE_STATE)
    if st["run"]: bad.append(f"1440: a keydown inside the figure before it was in view did not cancel the pass: {st!r}")
    elif ran is not None:
        await pg.wait_for_timeout(300)
        rest = await still(pg)
        if rest.size != ran.size: bad.append(f"1440: the drawing after the pass is {ran.size}, without it {rest.size}")
        else:
            d = ImageChops.difference(ran, rest).convert("L").point(lambda v: 255 if v > 8 else 0)
            off, total = d.histogram()[255], rest.size[0] * rest.size[1]
            if off > total * 0.0005: bad.append(f"1440: after its pass the drawing is not the still: {off} of {total} pixels off by more than 8 levels")
            notes.append(f"rest = still ({off} of {total} px off)")
    await ctx.close()
    # 3. never under reduced motion; never on a phone (the drawing is not shown there)
    for w, h, touch, reduced, tag in ((1440, 900, False, True, "reduced motion"), (390, 844, True, False, "390")):
        ctx, pg = await open_page(b, "platform.html", w, h, touch=touch, reduced=reduced)
        await pg.evaluate(center, "#pipeline"); await pg.evaluate(center, PIPE)
        await pg.wait_for_timeout(lim(5000))
        st = await pg.evaluate(PIPE_STATE)
        if st["run"] or st["running"]: bad.append(f"{tag}: the pipeline acted: {st!r}")
        notes.append(f"{tag} still (drawing {st['box'][1]} px tall)")
        await ctx.close()
    assert not bad, "pipeline_once:\n  " + "\n  ".join(bad)
    print(f"pipeline_once: Platform §03 plays one pass when in view at 1440 and rests as its still; never twice, never after a keydown inside it, never under reduced motion or on a phone ({'; '.join(notes)})")

# ---- hc20 (integrate, standing in for tests; platform's optional pin): Platform §06's plate draws itself once on the
# site's reveal (platform.css, `#marketplace .will-reveal.is-in:not(.is-cut)`), then rests as its still; a roadmap never loops
MARKET = "#marketplace .sec-plate--market"
MARKET_STATE = r"""(() => { const f = document.querySelector('#marketplace .sec-plate--market'); if (!f) return null;
  const an = f.getAnimations({ subtree: true }).filter(a => a.animationName && a.playState === 'running');
  const by = {}; an.forEach(a => { by[a.animationName] = (by[a.animationName] || 0) + 1; });
  return { cls: f.className, running: an.length, by, recs: f.querySelectorAll('.hp-rec').length }; })()"""
# the moment the reveal lands: what the figure runs then (installed before the plate is reached)
MARKET_WATCH = r"""(() => { const f = document.querySelector('#marketplace .sec-plate--market'); window.__mk = null;
  const take = () => { const an = f.getAnimations({ subtree: true }).filter(a => a.animationName); const by = {};
    an.forEach(a => { by[a.animationName] = (by[a.animationName] || 0) + 1; });
    window.__mk = { cls: f.className, n: an.length, by, pops: new Set(an.filter(a => a.animationName === 'pl-pop').map(a => a.effect.target)).size,
      end: Math.round(Math.max(0, ...an.map(a => a.effect.getComputedTiming().endTime))) }; };
  if (f.classList.contains('is-in')) { take(); return; }
  const mo = new MutationObserver(() => { if (f.classList.contains('is-in')) { mo.disconnect(); take(); } });
  mo.observe(f, { attributes: true, attributeFilter: ['class'] }); })()"""
MARKET_NAMES = {"mk-wipe", "pl-in", "pl-fade", "pl-pop"}  # the streams wiped in, the layers closing, the fades, the records
MARKET_WHOLE_MS = 1400  # hc21 (HC21 4.2): the plate is whole within ~1.4 s of its reveal (a still that only arrives comes sooner than the plates that act)
MARKET_HALVES = r"""(() => [...document.querySelectorAll('#marketplace .sp-half svg')].map(s => s.getBoundingClientRect().height))()"""


def near_off(a, b, lv=8):
    """pixels of a that are more than lv levels (any channel) from every pixel of b within one pixel (a 3 x 3
    neighbourhood): the same drawing at another sub-pixel offset passes, a changed drawing does not"""
    from PIL import ImageChops, ImageFilter
    lo, hi = b.filter(ImageFilter.MinFilter(3)), b.filter(ImageFilter.MaxFilter(3))
    under = ImageChops.subtract(lo, a)   # how far a is under b's darkest neighbour (0 when not under)
    over = ImageChops.subtract(a, hi)    # how far a is over b's lightest neighbour
    d = ImageChops.lighter(under, over).convert("L").point(lambda v: 255 if v > lv else 0)
    return d.histogram()[255]


@check
async def market_draw_once(b):
    """hc20 (integrate, standing in for tests; platform's optional pin; the director's HC20 4.4, done by platform):
    Platform §06's plate (`#marketplace .sec-plate--market`, "Schematic · roadmap") draws itself once as it arrives, by the
    site's reveal, and never runs again. At 1440 x 900, scrolled to in half-screen steps as a visitor does, the moment the
    reveal lands it runs mk-wipe, pl-in, pl-fade and pl-pop (every one of its records pops; 40 animations in all at the
    time of writing); within 4 s nothing in it runs, and the plate then equals, pixel for pixel (no more than 0.05% of its
    pixels off by more than 8 levels), the same plate under reduced motion; after leaving the screen and coming back
    nothing runs. It never animates under reduced motion, on a deep link to #marketplace (the first screen) or after a
    jump to it (an in-page link: the reveal is .is-cut, nothing runs at the landing or 1.6 s after).
    hc21 (integrate, standing in for tests; the director's HC21 4.2 and platform's optional pin): the draw-in is whole within
    MARKET_WHOLE_MS of the reveal, read from its animations' own timing (the latest delay + duration, so a slow CPU cannot
    move it; .85 s at the time of writing, 2.15 s at hc20); and the plate's two halves are drawn in boxes of one height at
    1440 x 900 and 3840 x 2160 (the record line runs on across the join with no step: 0.57 px at 3840 at hc20).
    hc26r (integrate, standing in for tests; platform's request, PLAT-1): reduced motion now unpins Platform's hero scene,
    so §06 sits at another sub-pixel offset there (0.9% of the plate's pixels differ by anti-aliasing alone). The draw-in's
    rest is compared, pixel for pixel as before, with the still on the same layout: the motion page reached by a jump (the
    reveal cut, nothing runs); and that still with the reduced-motion plate, a pixel matching when it is within 8 levels
    of any pixel of the other within one device pixel (the same drawing, shifted by less than a pixel)."""
    import io
    from PIL import Image, ImageChops
    bad, notes = [], []
    lim = lambda ms: int(ms * max(1.0, MODE["throttle"]))
    center = "(s) => document.querySelector(s).scrollIntoView({block: 'center', behavior: 'instant'})"

    async def still(pg):
        await pg.evaluate(center, MARKET); await pg.wait_for_timeout(400)
        box = await pg.evaluate(BOX, MARKET)
        img = await pg.screenshot(clip={"x": box[0], "y": box[1], "width": box[2], "height": box[3]}, animations="disabled", timeout=60000)
        return Image.open(io.BytesIO(img)).convert("RGB")

    async def visit(pg):  # half-screen steps down to the plate, as platform hc20's film.py: the reveal fires, not a jump
        y = await pg.evaluate(f"document.querySelector('{MARKET}').getBoundingClientRect().top + scrollY - innerHeight * .25")
        cur = 0
        while cur < y:
            cur = min(y, cur + 450)
            await pg.evaluate(f"window.scrollTo({{top: {cur}, behavior: 'instant'}})"); await pg.wait_for_timeout(40)

    # 1. the still: the plate under reduced motion (nothing runs there)
    ctx, pg = await open_page(b, "platform.html", 1440, 900, reduced=True)
    ref = await still(pg)
    st = await pg.evaluate(MARKET_STATE)
    if st["running"]: bad.append(f"reduced motion: the plate runs {st['by']!r}")
    await ctx.close()
    # 2. the draw-in, once, to its rest
    rest = None
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    await pg.mouse.move(5, 450)
    await pg.evaluate(MARKET_WATCH)
    await visit(pg)
    if not await until(pg, "!!window.__mk", lim(4000), 50):
        bad.append(f"1440: the plate was not revealed within 4 s of reaching it: {await pg.evaluate(MARKET_STATE)!r}")
    else:
        mk = await pg.evaluate("window.__mk")
        if "is-cut" in mk["cls"]: bad.append(f"1440: scrolling to the plate cut its entrance: {mk!r}")
        if not MARKET_NAMES <= set(mk["by"]): bad.append(f"1440: the draw-in did not play: {mk['by']!r}, expected {sorted(MARKET_NAMES)} among them")
        recs = (await pg.evaluate(MARKET_STATE))["recs"]
        if not recs or mk["pops"] != recs: bad.append(f"1440: {mk['pops']} of the plate's {recs} records popped")
        if not 0 < mk["end"] <= MARKET_WHOLE_MS: bad.append(f"1440: the draw-in is whole {mk['end']} ms after the reveal (at most {MARKET_WHOLE_MS})")
        notes.append(f"whole {mk['end']} ms after the reveal")
        if not await until(pg, f"(() => document.querySelector('{MARKET}').getAnimations({{ subtree: true }}).every(a => a.playState !== 'running'))()", lim(4000), 100):
            bad.append(f"1440: still running 4 s after the reveal: {await pg.evaluate(MARKET_STATE)!r}")
        else:
            rest = await still(pg)
            notes.append(f"1440 drew once ({mk['n']} animations: {', '.join(f'{k} {v}' for k, v in sorted(mk['by'].items()))})")
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(1200)
        await pg.evaluate(center, MARKET); await pg.wait_for_timeout(lim(2500))
        again = await pg.evaluate(MARKET_STATE)
        if again["running"]: bad.append(f"1440: the plate ran again after leaving the screen and coming back: {again!r}")
    await ctx.close()
    # 3. a deep link (the plate in the first screen) and a jump (an in-page link, as the chapter menu's): the still at once
    ctx, pg = await open_page(b, "platform.html#marketplace", 1440, 900)
    await pg.wait_for_timeout(300)
    st = await pg.evaluate(MARKET_STATE)
    if st["running"]: bad.append(f"deep link: the plate runs {st['by']!r}")
    await ctx.close()
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    await pg.mouse.move(5, 450)
    await pg.evaluate(MARKET_WATCH)
    await pg.evaluate("(() => { const a = document.createElement('a'); a.href = '#marketplace'; a.textContent = 'x'; document.body.appendChild(a); a.click(); a.remove(); })()")
    if not await until(pg, "!!window.__mk", lim(3000), 50): bad.append(f"jump: the plate was not revealed by the jump: {await pg.evaluate(MARKET_STATE)!r}")
    else:
        mk = await pg.evaluate("window.__mk")
        if "is-cut" not in mk["cls"]: bad.append(f"jump: the reveal was not cut: {mk!r}")
        if mk["n"]: bad.append(f"jump: the plate ran {mk['by']!r} at the landing")
        await pg.wait_for_timeout(1600)
        st = await pg.evaluate(MARKET_STATE)
        if st["running"]: bad.append(f"jump: the plate runs {st['by']!r} 1.6 s after the landing")
        cut = await still(pg)
        if rest is not None:
            if rest.size != cut.size: bad.append(f"1440: the plate after its draw-in is {rest.size}, after a jump {cut.size}")
            else:
                d = ImageChops.difference(cut, rest).convert("L").point(lambda v: 255 if v > 8 else 0)
                off, total = d.histogram()[255], cut.size[0] * cut.size[1]
                if off > total * 0.0005: bad.append(f"1440: after its draw-in the plate is not the still: {off} of {total} pixels off by more than 8 levels")
                notes.append(f"rest = still, {off} of {total} px off")
        if cut.size != ref.size: bad.append(f"1440: the still after a jump is {cut.size}, under reduced motion {ref.size}")
        else:
            # Two layouts, so the plate sits at two sub-pixel offsets and text is rasterized twice. Chromium on Windows
            # leaves 88 of 399,848 pixels off (10 Nov); CI's Linux font rasterizer leaves 417 (run 42782516694). 0.2% still
            # means the same drawing: a missing mark or label is thousands of pixels.
            off, total = near_off(cut, ref), cut.size[0] * cut.size[1]
            if off > total * 0.002: bad.append(f"1440: the still after a jump is not the reduced-motion plate: {off} of {total} pixels off by more than 8 levels within a pixel")
            notes.append(f"still = reduced-motion still within a pixel, {off} px off")
    await ctx.close()
    notes.append("reduced motion, deep link and jump: the still")
    # 4. one record line across the join: the two halves' boxes have one height (the same viewBox height, the same snap)
    for w, h in ((1440, 900), (3840, 2160)):
        ctx, pg = await open_page(b, "platform.html", w, h, reduced=True)
        await pg.evaluate(center, MARKET); await pg.wait_for_timeout(200)
        hs = await pg.evaluate(MARKET_HALVES)
        if len(hs) != 2 or abs(hs[0] - hs[1]) > 0.25: bad.append(f"{w}: the plate's halves are {hs} px tall (one height expected)")
        else: notes.append(f"{w}: halves {hs[0]:.1f} / {hs[1]:.1f} px")
        await ctx.close()
    assert not bad, "market_draw_once:\n  " + "\n  ".join(bad)
    print(f"market_draw_once: Platform §06 draws itself once as a visitor reaches it and rests as its still; never again, never under reduced motion, on a deep link or after a jump ({'; '.join(notes)})")

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
    # v2x r3 (platform; r3-motion minor): with Follow centred, Pause lies under the bar and answers at its centre; the
    # desk's head keeps its height during a followed walk (the state no longer wraps Pause onto a third row)
    mo, head0 = await pg.evaluate(GAP_MOTION), await pg.evaluate(DESK_HEAD)
    if not (mo["inside"] and mo["hit"]): bad.append(f"lifecycles.html@390x844: with Follow centred, Pause is not under the bar inside the viewport or does not answer at its centre {mo}")
    await bounded(pg.locator("[data-gap-follow]").tap(), "a tap on Follow the next action", 60)
    walk, heads, t0 = [], set(), time.monotonic()
    while time.monotonic() - t0 < 40:
        d = await pg.evaluate(DESK)
        if d["on"]: walk.append(d); heads.add(await pg.evaluate(DESK_HEAD))
        if walk and d["state"] != "Following an action": break
        await pg.wait_for_timeout(150)
    if heads - {head0}: bad.append(f"lifecycles.html@390x844: the desk's head is {head0} px before the walk and {sorted(heads)} px during it (must not change)")
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
    readout (never the old and the new bar both drawn) (NV-R2-2). v2x cut (1 Nov): phones have no readout pill; the menu
    toggle opens the sheet that holds Back to top and the chapters, so the tap that opens it is on the toggle"""
    bad, summary = [], []
    for case in ("top", "06"):
        ctx, pg = await open_page(b, "index.html", 390, 844, touch=True)
        cdp = await ctx.new_cdp_session(pg)
        if case == "top": await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
        else: await pg.evaluate("(() => { const a = document.querySelectorAll('.nav-ch-list a')[0]; const el = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1))); window.scrollTo({top: el.getBoundingClientRect().top + scrollY, behavior: 'instant'}); })()")
        await pg.wait_for_timeout(1800)
        await bounded(pg.locator(".nav-toggle").tap(), "a tap on the menu toggle", 60); await pg.wait_for_timeout(700)
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


# ---- hc22 (integrate, standing in for tests): the type sizes on a first screen (EVOLVE "<= 4 type sizes on any screen",
# the director's HC22 4.1) and the footer that ends the page (HC22 4.2)
FIRST_SIZES = r"""(() => { const vh = innerHeight, vw = innerWidth, out = {};
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const t = n.textContent.trim(); if (!t) continue; const el = n.parentElement; if (!el) continue;
    const r = el.getBoundingClientRect(); if (r.width <= 1 || r.height <= 1) continue;
    if (r.bottom - r.height / 2 < 0 || r.top + r.height / 2 > vh || r.right - r.width / 2 < 0 || r.left + r.width / 2 > vw) continue;
    if (el.closest('.sr-only, .visually-hidden, .skip, .skip-link, .nav-logo, .brand, script, style, noscript, template')) continue;
    let a = el, hid = false; while (a && a !== document.documentElement) { const c = getComputedStyle(a); if (+c.opacity < 0.05 || c.visibility === 'hidden' || c.display === 'none') { hid = true; break; } a = a.parentElement; }
    if (hid) continue;
    const k = (Math.round(parseFloat(getComputedStyle(el).fontSize) * 2) / 2).toFixed(1);
    (out[k] = out[k] || []).push(t.slice(0, 28)); }
  return out; })()"""
FIRST_SIZES_AT = (("index.html", 1440, 900, 1, False), ("index.html", 3840, 2160, 1, False), ("index.html", 1920, 1080, 2, False),
                  ("index.html", 1024, 768, 1, False), ("index.html", 768, 1024, 2, True), ("index.html", 390, 844, 3, True),
                  ("index.html", 320, 568, 2, True))


@check
async def first_screen_sizes(b):
    """hc22 (integrate, standing in for tests; EVOLVE.md "at most 4 type sizes on any screen"; the director's HC22 4.1, done
    by home: the four figures in the site's stat grammar, a serif numeral over an Inter label at the small step, not 11 px
    mono caps): Home's first screen, at rest after its opening (the loader gone, every engine started, 4.5 s), shows text in
    at most four font sizes (the computed size of every visible text node whose box's centre is on the screen, to the half
    pixel; the logo and screen-reader-only text aside) at 1440 x 900, 3840 x 2160, 1920 x 1080 @2, 1024 x 768, and with
    touch at 768 x 1024, 390 x 844 and 320 x 568. At hc22's review it was five at 1440 and 3840 (89.3, 30.2, 17.8, 14, 11)."""
    bad, notes = [], []
    for path, w, h, dpr, touch in FIRST_SIZES_AT:
        ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch)
        if not touch: await pg.mouse.move(2, 2)
        await pg.wait_for_timeout(4500)
        sizes = await pg.evaluate(FIRST_SIZES)
        keys = sorted(sizes, key=lambda k: -float(k))
        if len(keys) > 4: bad.append(f"{path}@{w}x{h}: {len(keys)} type sizes on the first screen: " + "; ".join(f"{k} px {sizes[k][:3]}" for k in keys))
        notes.append(f"{w}x{h} {' / '.join(k.rstrip('0').rstrip('.') for k in keys)}")
        await ctx.close()
    assert not bad, "first_screen_sizes:\n  " + "\n  ".join(bad)
    print(f"first_screen_sizes: Home's first screen shows at most four type sizes ({'; '.join(notes)} px)")


# ---- hc28 (integrate, standing in for tests; platform's request, the director's HC28 4.1 "extend first_screen_sizes to every
# main page"): the council's own probe (hc/hc28-director/type_sizes2.js): text in <main> under the bar that a reader sees
# (not hidden, faded out, clipped away by an inset clip-path, visually hidden or in an SVG), its size times any scaled ancestor
SCREEN_SIZES = r"""(() => { const out = {}, vw = innerWidth, vh = innerHeight, nav = document.querySelector('.nav'), bar = nav ? nav.getBoundingClientRect().bottom : 0;
  const vis = el => { for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
      const cp = cs.clipPath; if (cp && cp.startsWith('inset(')) { const r = e.getBoundingClientRect(), v = cp.slice(6, -1).split(/\s+/), t = parseFloat(v[0]), ri = parseFloat(v[1] === undefined ? v[0] : v[1]);
        if (/%/.test(v[0]) ? t >= 99.5 : t >= r.height - 1) return false; if (/%/.test(v[1] || '') && ri >= 99.5) return false; } } return true; };
  const srOnly = el => { for (let e = el; e && e !== document.body; e = e.parentElement) { const c = getComputedStyle(e); if ((c.clip && c.clip !== 'auto') || (c.position === 'absolute' && parseFloat(c.width) <= 1.5 && c.overflow === 'hidden')) return true; } return false; };
  const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; const el = n.parentElement, r = el.getBoundingClientRect();
    if (el.closest('svg, .sr-only, .visually-hidden, noscript') || r.bottom < bar || r.top > vh || r.right < 0 || r.left > vw || r.width < 1 || !vis(el) || srOnly(el)) continue;
    let k = parseFloat(getComputedStyle(el).fontSize); for (let e = el; e; e = e.parentElement) { const sc = getComputedStyle(e).scale; if (sc && sc !== 'none') k *= parseFloat(sc); }
    k = (Math.round(k * 2) / 2).toFixed(1); (out[k] = out[k] || []).push(n.textContent.trim().slice(0, 18)); }
  return out; })()"""
MAIN_PAGES = ("index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "research.html", "company.html",
              "access.html", "blog/index.html")
LC_STAGE = r"""(() => { const h = document.querySelector('.page-hero'), s1 = document.querySelector('#test .ch-head'),
    labs = [...document.querySelectorAll('.hero-plate--rings .hp-labs .hp-lab')], fs = el => +parseFloat(getComputedStyle(el).fontSize).toFixed(2);
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return { vh: innerHeight, rem, heroTop: h.getBoundingClientRect().top + scrollY, heroB: h.getBoundingClientRect().bottom + scrollY, s1: s1 ? s1.getBoundingClientRect().top + scrollY : null,
    labs: labs.map(l => [l.textContent.trim().slice(0, 12), fs(l), ...[...l.querySelectorAll('*')].map(fs)]) }; })()"""
EDGE_LINE = r"""(() => { const a = document.querySelector('.stack-scene #architecture'); if (!a) return null;
  const c = a.querySelector('.container'), cs = getComputedStyle(c), cr = c.getBoundingClientRect(), ar = a.getBoundingClientRect(), b = getComputedStyle(a, '::before');
  const t = document.createElement('i'); t.style.cssText = 'position:absolute;width:var(--hair);height:0'; a.appendChild(t); const hair = t.getBoundingClientRect().width; t.remove();
  return { content: b.content, l: parseFloat(b.left), r: parseFloat(b.right), h: parseFloat(b.height),
    cl: cr.left + parseFloat(cs.paddingLeft) - ar.left, cr: ar.right - (cr.right - parseFloat(cs.paddingRight)), hair }; })()"""


@check
async def page_type_sizes(b):
    """hc28 (integrate, standing in for tests; platform's request under the director's HC28 4.1; EVOLVE.md "at most 4 type
    sizes on any screen"): every main page, not Home alone. (1) The first screen of Home, Platform, Lifecycles, Proof, Trust,
    Research, Company, Access and the Blog index, at rest (the loader gone, the scripts run, 3 s; Home 4.5 s), shows text in
    <main> in at most four sizes at 1440 x 900 and, with touch, at 390 x 844 (the council's probe: SCREEN_SIZES). (2) Every
    half screen of Platform (its pinned scene included) and Lifecycles, top to foot, at 1440 x 900 and 390 x 844: at most four.
    (3) Facts the platform group pinned: the Lifecycles hero is a whole stage again (its foot 2.5rem above the first screen's
    foot, +-2 px, at 1440 x 900 and 390 x 844; at 390 x 844 §01's head starts below the fold), and its ring carries one label
    register (every gate numeral and label at one size: "01"-"06" at the label step, not 11 px mono under 14 px labels);
    Platform's ink edge line (`#architecture::before`, pinned at 1440 x 900) runs the content's width (the container's
    content box, +-1 px each side) at two hairlines. At hc28's review Lifecycles' first screen showed six sizes at 1440 and
    390 and three half screens five; the bar's own readout (the chapter numerals) is chrome, outside <main>, as in the
    council's probe."""
    bad, notes = [], []
    srt = lambda s: sorted(s, key=lambda k: -float(k))
    for w, h, touch in ((1440, 900, False), (390, 844, True)):
        firsts = []
        for path in MAIN_PAGES:
            ctx, pg = await open_page(b, path, w, h, touch=touch)
            if not touch: await pg.mouse.move(2, 2)
            await pg.wait_for_timeout(4500 if path == "index.html" else 3000)
            sz = await pg.evaluate(SCREEN_SIZES)
            if len(sz) > 4: bad.append(f"{path}@{w}x{h}: {len(sz)} type sizes on the first screen: " + "; ".join(f"{k} px {sz[k][:3]}" for k in srt(sz)))
            firsts.append(f"{path.split('.')[0].split('/')[0]} {len(sz)}")
            if path == "lifecycles.html":
                st = await pg.evaluate(LC_STAGE)
                want = st["vh"] - 2.5 * st["rem"]
                if abs(st["heroB"] - want) > 2: bad.append(f"{path}@{w}x{h}: the hero ends at {st['heroB']:.1f}, not on its stage ({want:.1f}: the first screen less 2.5rem)")
                if touch and (st["s1"] is None or st["s1"] < st["vh"]): bad.append(f"{path}@{w}x{h}: §01's head starts at {st['s1']} (inside the first screen of {st['vh']})")
                sizes = {x for lab in st["labs"] for x in lab[1:]}
                if not st["labs"] or len(sizes) != 1: bad.append(f"{path}@{w}x{h}: the ring's gate numerals and labels in {len(sizes)} sizes, not one register: {st['labs']}")
                else: notes.append(f"Lifecycles {w}: hero foot {st['heroB']:.0f}, ring labels {sizes.pop()} px")
            if path == "platform.html" and not touch:
                e = await pg.evaluate(EDGE_LINE)
                if not e or e["content"] in ("none", "normal"): bad.append(f"{path}@{w}x{h}: no ink edge line (#architecture::before) in the pinned scene ({e})")
                else:
                    if abs(e["l"] - e["cl"]) > 1 or abs(e["r"] - e["cr"]) > 1: bad.append(f"{path}@{w}x{h}: the ink edge line is inset {e['l']:.1f} / {e['r']:.1f}, not the content's {e['cl']:.1f} / {e['cr']:.1f}")
                    if abs(e["h"] - 2 * e["hair"]) > 0.05: bad.append(f"{path}@{w}x{h}: the ink edge line is {e['h']} px, not two hairlines ({2 * e['hair']})")
                    notes.append(f"Platform's edge line {e['l']:.0f} / {e['r']:.0f} in, {e['h']:g} px")
            await ctx.close()
        notes.append(f"first screens {w}: " + ", ".join(firsts))
        for path in ("platform.html", "lifecycles.html"):
            ctx, pg = await open_page(b, path, w, h, touch=touch)
            if not touch: await pg.mouse.move(2, 2)
            await pg.wait_for_timeout(2000)
            H = await pg.evaluate("document.documentElement.scrollHeight")
            y, n, worst = 0, 0, 0
            while y < H - h // 4:
                await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
                sz = await pg.evaluate(SCREEN_SIZES); n += 1; worst = max(worst, len(sz))
                if len(sz) > 4: bad.append(f"{path}@{w}x{h} at {y / h:.1f} screens: {len(sz)} type sizes: " + "; ".join(f"{k} px {sz[k][:3]}" for k in srt(sz)))
                y += h // 2
            notes.append(f"{path.split('.')[0]} {w}: {n} half screens, at most {worst}")
            await ctx.close()
    assert not bad, "page_type_sizes:\n  " + "\n  ".join(bad[:24])
    print(f"page_type_sizes: every main page's first screen and every half screen of Platform and Lifecycles show at most four type sizes ({'; '.join(notes)})")


FOOT_END = r"""(() => { const f = document.querySelector('footer.footer'), bt = f && f.querySelector('.bottom'); if (!f || !bt) return null;
  const R = e => e.getBoundingClientRect(), fb = R(f), bb = R(bt), cs = getComputedStyle(bt), fs = getComputedStyle(f), sy = scrollY;
  const under = [...f.querySelectorAll('*')].filter(e => !bt.contains(e) && !e.contains(bt)).map(e => [e, R(e)])
    .filter(([e, r]) => r.width > 0 && r.height > 0 && r.top >= bb.top - 0.5 && e.checkVisibility({ visibilityProperty: true }))  // a closed fold's content (the phones' Legal & disclosures) is not drawn
    .map(([e, r]) => (e.className || e.tagName).toString().slice(0, 40) + ' @' + Math.round(r.top + sy));
  const pseudo = ['::before', '::after'].filter(p => { const c = getComputedStyle(f, p); return c.content !== 'none' && c.content !== 'normal' && c.display !== 'none'; });
  return { doc: document.documentElement.scrollHeight, footBottom: Math.round((fb.bottom + sy) * 10) / 10, botBottom: Math.round((bb.bottom + sy) * 10) / 10,
    padBottom: parseFloat(cs.paddingBottom), padTop: parseFloat(fs.paddingTop), under, pseudo, wordmark: document.querySelectorAll('footer .wordmark, footer [data-word]').length }; })()"""


@check
async def footer_end(b):
    """hc22 (integrate, standing in for tests; the director's HC22 4.2, done by system: "the footer ends the page"): on Home,
    Proof, a research note and a blog post, at 1440 x 900, 3840 x 2160 and with touch at 390 x 844, scrolled to the foot:
    the page ends on the footer's bottom row (the copyright and the clocks): nothing in the footer is drawn at or below
    that row's top but the row itself (no ghost masthead or other decorative field, and no `[data-word]` wordmark element),
    the footer's own box ends with that row and the document with the footer (within 1 px), and the paper under the row
    is no more than the footer's top padding (within 1 px). Its links and disclosures are check_static's `footer` and
    verify_v9's `disclosures`."""
    bad, notes = [], []
    for path in ("index.html", "evidence.html", "research/09-lifecycle-01-ten-sessions.html", "blog/in-search-gen-ai-business-model.html"):
        for w, h, touch in ((1440, 900, False), (3840, 2160, False), (390, 844, True)):
            tag = f"{path}@{w}"
            ctx, pg = await open_page(b, path, w, h, touch=touch)
            await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(900)
            r = await pg.evaluate(FOOT_END)
            await ctx.close()
            if not r: bad.append(f"{tag}: no footer with a bottom row"); continue
            if r["wordmark"]: bad.append(f"{tag}: a wordmark element in the footer ({r['wordmark']})")
            if r["under"]: bad.append(f"{tag}: drawn at or under the footer's bottom row: {r['under'][:4]}")
            if r["pseudo"]: bad.append(f"{tag}: the footer draws {r['pseudo']}")
            if abs(r["footBottom"] - r["botBottom"]) > 1: bad.append(f"{tag}: the footer ends {r['footBottom'] - r['botBottom']:.1f} px under its bottom row")
            if abs(r["doc"] - r["footBottom"]) > 1: bad.append(f"{tag}: the page runs {r['doc'] - r['footBottom']:.1f} px past the footer")
            if r["padBottom"] > r["padTop"] + 1: bad.append(f"{tag}: {r['padBottom']:.0f} px of paper under the bottom row, more than the footer's top padding {r['padTop']:.0f}")
            if path == "index.html": notes.append(f"{w}: {r['padBottom']:.0f} px under the row (top {r['padTop']:.0f})")
    assert not bad, "footer_end:\n  " + "\n  ".join(bad)
    print(f"footer_end: on Home, Proof, a note and a post the page ends on the footer's bottom row, nothing drawn under it ({'; '.join(notes)})")



# ---- hc23 (integrate, standing in for tests): Inter's UI weight follows its ground (HC23 4.4), Lifecycles' line under the
# gates never empties once it has spoken (HC23 4.6), the Research index's phone strip (HC23 4.8)
UI_WEIGHT = r"""(() => { const out = [], sel = '.nav-links a, .btn, .link-arrow, .chain-more, .lt-more, .lt-btn, .instr-primary, .sw-follow, .desk-follow, .chain-try, .chain-restore, .chip b';
  const lum = c => { const m = (c.match(/[\d.]+/g) || []).slice(0, 3).map(v => { v = +v / 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return m.length < 3 ? null : .2126 * m[0] + .7152 * m[1] + .0722 * m[2]; };
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect(); if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > innerHeight) continue;
    if (!el.checkVisibility({ visibilityProperty: true })) continue;
    const cs = getComputedStyle(el); if (!/Inter/.test(cs.fontFamily.split(',')[0])) continue;
    if (!(el.textContent || '').trim()) continue;
    const L = lum(cs.color); if (L === null || (L > .2 && L < .4)) continue;  // light text (paper) or dark text (ink); the accent between is neither
    out.push({ k: (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/)[0] : el.tagName.toLowerCase()) + ' "' + el.textContent.trim().slice(0, 22) + '"',
      light: L >= .4, w: +cs.fontWeight }); }
  return out; })()"""
UI_WEIGHT_AT = (("index.html", 1440, 900, False), ("lifecycles.html", 1440, 900, False), ("trust.html", 1440, 900, False),
                ("access.html", 1440, 900, False), ("index.html", 390, 844, True), ("trust.html", 390, 844, True))


@check
async def ui_weight(b):
    """hc23 (integrate, standing in for tests; the director's HC23 4.4, done by system: light on dark blooms, so Inter UI
    text is set lighter where it is light): on Home, Lifecycles, Trust and Access at 1440 x 900 and on Home and Trust with
    touch at 390 x 844, walked a screen at a time from the top to the foot, every visible Inter control in the viewport (the
    bar's links, buttons, arrow links, the instruments' primaries and Follow, the ledgers' buttons and the chains' paper
    buttons, Home's and Trust's "Show all ... records", the chips' values) is 450 where its text is light (paper on ink, or
    on a fill of ink) and 500 where it is dark (ink on paper, or on a fill of paper); text in the accent is neither and not
    read. Before hc23 every one was 500 (the bar read semibold over the overture and regular on paper); its first run
    caught Trust's "Change a record" (a paper fill on the replay's ink) at 450 beside Home's at 500 (ledger.css's
    `.lt-btn` overrode the primary's weight). Print sets both to 500 (print_home)."""
    bad, seen = [], {"light": set(), "dark": set()}
    for path, w, h, touch in UI_WEIGHT_AT:
        ctx, pg = await open_page(b, path, w, h, touch=touch)
        if not touch: await pg.mouse.move(w - 2, h - 2)
        total = await pg.evaluate("document.documentElement.scrollHeight")
        y, steps = 0, 0
        while y < total and steps < 40:
            await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})"); await pg.wait_for_timeout(450)
            for e in await pg.evaluate(UI_WEIGHT):
                want = 450 if e["light"] else 500
                seen["light" if e["light"] else "dark"].add(e["k"].split(' "')[0])
                if e["w"] != want: bad.append(f"{path}@{w}: {e['k']} is {e['w']:g} in {'light text' if e['light'] else 'dark text'}, {want} expected")
            y += int(h * 0.9); steps += 1
            total = await pg.evaluate("document.documentElement.scrollHeight")
        await ctx.close()
    if not seen["light"] or not seen["dark"]: bad.append(f"too little seen to judge: light {sorted(seen['light'])}, dark {sorted(seen['dark'])}")
    bad = list(dict.fromkeys(bad))
    assert not bad, "ui_weight:\n  " + "\n  ".join(bad[:24])
    print(f"ui_weight: Inter controls are 450 in light text ({', '.join(sorted(seen['light']))}) and 500 in dark ({', '.join(sorted(seen['dark']))})")


SAY = r"""(() => { const d = document.querySelector('[data-gap]'), s = d && d.querySelector('[data-gap-say]'), l = d && d.querySelector('.desk-ledger'); if (!s || !l) return null;
  const live = [...s.children].filter(k => !k.classList.contains('is-out'));
  return { fol: d.classList.contains('is-following'), txt: live.map(k => k.textContent).join(' | ').trim(), n: s.children.length,
    led: Math.round((l.getBoundingClientRect().top + scrollY) * 2) / 2, h: Math.round(s.getBoundingClientRect().height * 2) / 2 }; })()"""


@check
async def desk_say(b):
    """hc23 (integrate, standing in for tests; the director's HC23 4.6, done by platform in gap.js): Lifecycles §03, the line
    under the gates ([data-gap-say]) through the desk's own act, with touch at 390 x 844 and at 1440 x 900: the desk scrolled
    in with its ledger in view and left alone, sampled every 80 ms for 30 s: the act is seen following (`.is-following`)
    and the line speaks; once it has spoken it is never empty again (a new line crossfades over the last; when the followed
    record leaves the strip the receipt stays, spent); and the slot keeps one height, so the ledger under it never moves.
    Before hc23 the slot emptied between steps (an 80 px hole between the stepper and the ledger at 390)."""
    bad, notes = [], []
    for w, h, dpr, touch in ((390, 844, 3, True), (1440, 900, 1, False)):
        ctx, pg = await open_page(b, "lifecycles.html", w, h, dpr=dpr, touch=touch)
        await pg.evaluate("document.querySelector('#desk').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(600)
        await pg.evaluate("(() => { const l = document.querySelector('.desk-ledger').getBoundingClientRect(); if (l.bottom > innerHeight) scrollBy(0, l.bottom - innerHeight + 40); })()")
        rows, t0 = [], time.monotonic()
        while time.monotonic() - t0 < 30:
            r = await pg.evaluate(SAY)
            if r: rows.append(r)
            await pg.wait_for_timeout(80)
        await ctx.close()
        tag = f"lifecycles.html@{w}x{h}"
        if not rows: bad.append(f"{tag}: no [data-gap-say] in the desk"); continue
        spoke = next((i for i, x in enumerate(rows) if x["txt"]), None)
        if not any(x["fol"] for x in rows): bad.append(f"{tag}: the desk's own act was not seen following in 30 s")
        if spoke is None: bad.append(f"{tag}: the line under the gates never spoke in 30 s"); continue
        empty = [i for i, x in enumerate(rows) if i > spoke and not x["txt"]]
        if empty: bad.append(f"{tag}: the line is empty in {len(empty)} of {len(rows) - spoke} samples after it first spoke (first at sample {empty[0]})")
        leds, hs = sorted({x["led"] for x in rows[spoke:]}), sorted({x["h"] for x in rows[spoke:]})
        if leds[-1] - leds[0] > 1: bad.append(f"{tag}: the ledger under the line moves as the line changes (its top at {leds[:6]} px)")
        lines = len({x["txt"] for x in rows if x["txt"]})
        notes.append(f"{w}: {lines} lines, slot {'/'.join(f'{v:g}' for v in hs)} px")
    assert not bad, "desk_say:\n  " + "\n  ".join(bad)
    print(f"desk_say: the line under the gates never empties once it has spoken, the ledger never moves ({'; '.join(notes)})")


STRIP = r"""(() => { const rail = document.querySelector('.rs-rail'), plate = document.querySelector('.rs-plate'), cap = document.querySelector('.rs-cap');
  if (!rail || !cap) return null; const t = cap.querySelector('.figcap-t'), hd = cap.querySelector('.figcap-h');
  const cur = document.querySelector('.posts-list .post.is-current');
  const lines = el => { const rg = document.createRange(); rg.selectNodeContents(el); const ys = []; for (const r of rg.getClientRects()) if (r.width > 1 && !ys.some(y => Math.abs(y - r.bottom) < 4)) ys.push(r.bottom); return ys.length; };
  return { rail: Math.round(rail.getBoundingClientRect().height * 2) / 2, vh: innerHeight, lines: lines(cap), two: !!(plate && plate.classList.contains('is-two')),
    t: t ? t.textContent : '', h: hd ? hd.textContent : '', s: cur ? cur.dataset.capS || '' : null, full: cur ? cur.dataset.capT || '' : null, noplate: !!document.querySelector('.no-plate') }; })()"""
STRIP_ROWS = r"""[...document.querySelectorAll('.posts-list .post')].map(li => [li.dataset.capS || '', li.dataset.capT || '', (li.querySelector('a') || li).textContent.trim().replace(/\s+/g, ' ').slice(0, 30)])"""


@check
async def research_strip(b):
    """hc23 (integrate, standing in for tests; the director's HC23 4.8, done by research): under 760 px the Research index
    docks its plate as one 56 px running foot. With touch at 412 x 915, 390 x 844, 360 x 780 and 320 x 640, a row at the
    reading line (rows 1, 5 and 10): `.rs-rail` is 56 px (+-1), the caption shows that row's short phrase (data-cap-s) and
    its hedge, on one line from 390 px and on two under it, where every hedge takes the second line (`.rs-plate.is-two`, one
    form while the list scrolls); every row carries a data-cap-s whose every word is a word of its own caption or that
    word's stem (data-cap-t; the first six letters, as build_research.py's STRIP assert: the phrase is the caption's,
    nothing new); from 760 px (1024 x 768) the plate shows the full caption. Before hc23 the strip was 120-154 px (14% of
    a 390 x 844 screen) with the caption on two or three lines."""
    bad, notes = [], []
    word = lambda s: re.findall(r"[\w’'-]+", s.lower())
    ctx, pg = await open_page(b, "research.html", 390, 844, touch=True)
    rows = await pg.evaluate(STRIP_ROWS)
    await ctx.close()
    if len(rows) < 10: bad.append(f"research.html: {len(rows)} rows in the list (10 expected)")
    for s, t, name in rows:
        if not s: bad.append(f"research.html: the row {name!r} has no data-cap-s"); continue
        extra = [x for x in word(s) if not any(c.startswith(x[:6]) for c in word(t))]
        if extra: bad.append(f"research.html: the row {name!r}'s phone phrase {s!r} has words not in its caption {t!r}: {extra}")
    for w, h, dpr in ((412, 915, 2.625), (390, 844, 3), (360, 780, 3), (320, 640, 2)):
        ctx, pg = await open_page(b, "research.html", w, h, dpr=dpr, touch=True)
        await pg.wait_for_timeout(800)
        r = None
        for n in (1, 5, 10):
            await pg.evaluate(f"(() => {{ const li = document.querySelectorAll('.posts-list .post')[{n - 1}]; window.scrollTo(0, li.getBoundingClientRect().top + scrollY - innerHeight * 0.4 + 30); }})()")
            await pg.wait_for_timeout(1400)
            r = await pg.evaluate(STRIP); tag = f"research.html@{w}x{h} row {n}"
            if not r: bad.append(f"{tag}: no .rs-rail / .rs-cap"); continue
            if r["noplate"]: bad.append(f"{tag}: no plate (WebGL off?)"); continue
            if abs(r["rail"] - 56) > 1: bad.append(f"{tag}: the strip is {r['rail']:g} px tall (56 expected; {r['rail'] / r['vh'] * 100:.1f}% of the screen)")
            want = 2 if w < 390 else 1
            if r["lines"] != want: bad.append(f"{tag}: the caption runs on {r['lines']} line(s), {want} expected ({r['t']!r} · {r['h']!r})")
            if (w < 390) != r["two"]: bad.append(f"{tag}: .rs-plate.is-two is {r['two']} at {w} px")
            if r["s"] is not None and r["t"] != r["s"]: bad.append(f"{tag}: the caption reads {r['t']!r}, the row's phrase is {r['s']!r}")
            if not r["h"]: bad.append(f"{tag}: the caption has no hedge")
        if r: notes.append(f"{w}: {r['rail']:g} px, {r['lines']} line(s)")
        await ctx.close()
    ctx, pg = await open_page(b, "research.html", 1024, 768)
    await pg.evaluate("document.querySelectorAll('.posts-list .post')[2].scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(1400)
    r = await pg.evaluate(STRIP)
    await ctx.close()
    if r and r["full"] is not None and r["t"] != r["full"]: bad.append(f"research.html@1024x768: the caption reads {r['t']!r}, the full caption {r['full']!r} expected from 760 px")
    assert not bad, "research_strip:\n  " + "\n  ".join(bad)
    print(f"research_strip: the phone strip is one 56 px running foot with the row's own phrase and hedge ({'; '.join(notes)}); the full caption from 760 px")


# ---- hc24 (integrate, standing in for tests): the close on the H1 step, its globe on Home only (HC24 4.1, 4.2: system);
# the overture's record row lands whole on paper (HC24 8: home); Lifecycles' desk in source order (HC24 4.7: platform)
CLOSE_PAGES = ["index.html", "platform.html", "lifecycles.html", "evidence.html", "trust.html", "research.html", "company.html", "blog/index.html"]
CLOSE = r"""(() => { const band = document.querySelector('main .cta-band'), h = band && band.querySelector('h2'); if (!h) return null;
  let p = document.getElementById('__vhero');
  if (!p) { p = document.createElement('i'); p.id = '__vhero'; p.setAttribute('aria-hidden', 'true'); const ps = p.style;
    ps.position = 'absolute'; ps.left = ps.top = '0'; ps.fontSize = 'var(--fs-hero)'; ps.visibility = 'hidden'; ps.pointerEvents = 'none'; document.body.appendChild(p); }
  const c = h.closest('.container') || band, cs = getComputedStyle(c), cr = c.getBoundingClientRect();
  const l = cr.left + parseFloat(cs.paddingLeft), r = cr.right - parseFloat(cs.paddingRight);
  const rg = document.createRange(); rg.selectNodeContents(h);
  const over = [...rg.getClientRects()].filter(x => x.width > 1).reduce((m, x) => Math.max(m, l - x.left, x.right - r), -1e9);
  const heads = [...document.querySelectorAll('main h2')].filter(x => !band.contains(x) && !x.closest('.story') && x.getBoundingClientRect().width > 0 && x.checkVisibility({ visibilityProperty: true }))
    .map(x => parseFloat(getComputedStyle(x).fontSize));
  const bar = document.querySelector('.nav'), gb = getComputedStyle(band, '::before'), bs = getComputedStyle(band), br = band.getBoundingClientRect();
  const els = [...band.querySelectorAll('.globe')].filter(g => getComputedStyle(g).display !== 'none' && g.getBoundingClientRect().width > 0).length;
  const bx = { l: parseFloat(gb.left), t: parseFloat(gb.top), w: parseFloat(gb.width), h: parseFloat(gb.height) };
  return { fs: parseFloat(getComputedStyle(h).fontSize), hero: parseFloat(getComputedStyle(p).fontSize), over, head: Math.max(0, ...heads),
    els, img: (gb.backgroundImage.match(/url\([^)]*\)/g) || []).map(u => u.replace(/^url\(["']?|["']?\)$/g, '').split('/').pop()), op: +gb.opacity,
    content: gb.content, z: gb.zIndex, bx, bw: br.width, bh: br.height, ov: bs.overflowX + ' ' + bs.overflowY, iso: bs.isolation,
    inn: !!band.querySelector('[data-reveal].is-in'),
    top: h.getBoundingClientRect().top, bar: bar ? bar.getBoundingClientRect().bottom : 0 }; })()"""
CLOSE_GLOBE_OK = "(() => { const b = document.querySelector('main .cta-band'); return !!b && !!b.querySelector('[data-reveal].is-in') && +getComputedStyle(b, '::before').opacity > .99; })()"


def close_globe_issues(tag, r, w):
    """hc29 (integrate, standing in for tests; system's request, the HC29 director's item 5): the globe behind every close,
    drawn by the band's own ::before (site.css), not by an element in the page"""
    bad, bx = [], r["bx"]
    if r["els"]: bad.append(f"{tag}: {r['els']} .globe element(s) shown in the close (the band's ::before draws the globe)")
    if r["img"] != ["globe-fine.svg"] or r["content"] in ("none", "normal"): bad.append(f"{tag}: the close's ::before draws {r['img']} (content {r['content']}), not the fine globe alone")
    if r["op"] < 0.99: bad.append(f"{tag}: the revealed close's globe at opacity {r['op']:.2f} (1)")
    if r["z"] != "-1" or r["iso"] != "isolate": bad.append(f"{tag}: the globe is not behind the copy (z-index {r['z']}, band isolation {r['iso']})")
    if "visible" in r["ov"]: bad.append(f"{tag}: the band does not clip its globe (overflow {r['ov']})")
    if not all(v == v for v in bx.values()): bad.append(f"{tag}: the globe's box is not resolved ({bx})"); return bad
    vis_w = max(0.0, min(r["bw"], bx["l"] + bx["w"]) - max(0.0, bx["l"])); vis_h = max(0.0, min(r["bh"], bx["t"] + bx["h"]) - max(0.0, bx["t"]))
    if bx["l"] < r["bw"] / 2 - 1: bad.append(f"{tag}: the globe starts at {bx['l']:.0f} px, left of the band's middle ({r['bw'] / 2:.0f}): it composes the right half")
    if vis_w < 0.75 * bx["w"] or vis_h < 0.5 * bx["h"]: bad.append(f"{tag}: {vis_w:.0f} x {vis_h:.0f} px of the {bx['w']:.0f} px globe inside the band (3/4 of its width, half its height)")
    if w >= 1440 and bx["w"] < r["bw"] / 3 - 0.5: bad.append(f"{tag}: the globe is {bx['w']:.0f} px wide, under a third of the band ({r['bw']:.0f})")
    return bad


@check
async def close_step(b):
    """hc24 (integrate, standing in for tests; the director's HC24 4.1 and 4.2, done by system): every page ends on its
    close set at the H1 step, the page's last word, and only Home's close keeps the cropped globe. On the eight pages with
    a close, at 3840 x 2160, 1440 x 900, 1024 x 768, 768 x 1024 and with touch at 390 x 844 and 320 x 640: the close's
    head (`.cta-band h2`) is the system's H1 step (`--fs-hero`, 0.5 px) from 396 px up, and under it no larger than that
    and no smaller than 36 px (10.5vw keeps its phrases in the column); it is never smaller than any chapter head on its
    page; no line of it passes its column (1 px); Home's band draws its globe and no other band has one (check_static
    close_globe pins the markup); and at 1440 x 900 and 3840 x 2160 with the page at its end the head stands clear of the
    bar. Before hc24 the close was the chapter heads' 60 px step (at 1440) beside the same globe on all eight pages.
    hc29 (integrate, standing in for tests; system's request, the HC29 director's item 5: "give all seven closes one
    composition", the globe behind every close, reversing HC24 4.2): the globe clause now reads, on all eight pages at the
    six sizes: no `.globe` element in the band is shown; the band's own ::before draws `globe-fine.svg` and nothing else,
    behind the copy (z-index -1 in an isolated band that clips it), at opacity 1 once the close has revealed (its
    `[data-reveal]` .is-in), standing in the band's right half (its left edge at or right of the middle), at least 3/4 of
    its width and half its height inside the band, and from 1440 up at least a third of the band's width (it composes the
    right half at 4K: 1,440 px of 3,840); before the close reveals, with JavaScript, it asks for no image (the globe waits
    for the close: no request in the first paint's graph); without JavaScript it is drawn at once (1440, Home and
    Research). Everything else is unchanged."""
    bad, notes = [], []
    for w, h, dpr, touch in ((3840, 2160, 1, False), (1440, 900, 1, False), (1024, 768, 1, False), (768, 1024, 2, False), (390, 844, 3, True), (320, 640, 2, True)):
        for path in CLOSE_PAGES:
            tag = f"{path}@{w}x{h}"
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch)
            r0 = await pg.evaluate(CLOSE)
            if r0 and not r0["inn"] and r0["img"]: bad.append(f"{tag}: before the close reveals its ::before already asks for {r0['img']} (the globe waits for the close)")
            await pg.evaluate("(() => { const c = document.querySelector('main .cta-band'); if (c) c.scrollIntoView({block: 'center', behavior: 'instant'}); })()")
            await pg.wait_for_timeout(400)
            await until(pg, CLOSE_GLOBE_OK, 3000)
            r = await pg.evaluate(CLOSE)
            if not r: bad.append(f"{tag}: no close (.cta-band h2)"); await ctx.close(); continue
            if w >= 396 and abs(r["fs"] - r["hero"]) > 0.5: bad.append(f"{tag}: the close's head is {r['fs']:.1f} px, the H1 step (--fs-hero) {r['hero']:.1f}")
            if w < 396 and not (36 - 0.5 <= r["fs"] <= r["hero"] + 0.5): bad.append(f"{tag}: the close's head is {r['fs']:.1f} px, not between 36 and the H1 step {r['hero']:.1f}")
            if r["fs"] < r["head"] - 0.5: bad.append(f"{tag}: the close's head ({r['fs']:.1f} px) is smaller than a chapter head ({r['head']:.1f})")
            if r["over"] > 1: bad.append(f"{tag}: a line of the close's head passes its column by {r['over']:.1f} px")
            bad += close_globe_issues(tag, r, w)
            if (w, h) in ((1440, 900), (3840, 2160)):
                await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(700)
                e = await pg.evaluate(CLOSE)
                if e and e["top"] < e["bar"] - 0.5: bad.append(f"{tag}: at the page's end the close's head is {e['bar'] - e['top']:.1f} px under the bar")
            if path == "evidence.html": notes.append(f"{w}: {r['fs']:.1f} px (chapters {r['head']:.1f}), globe {r['bx']['w']:.0f} px from {r['bx']['l']:.0f}")
            await ctx.close()
    for path in ("index.html", "research.html"):
        ctx, pg = await open_page(b, path, 1440, 900, js=False)
        await pg.evaluate("(() => { const c = document.querySelector('main .cta-band'); if (c) c.scrollIntoView({block: 'center', behavior: 'instant'}); })()")
        await pg.wait_for_timeout(300)
        r = await pg.evaluate(CLOSE)
        await ctx.close()
        if not r: bad.append(f"{path}@1440x900 no JS: no close"); continue
        if r["img"] != ["globe-fine.svg"] or r["op"] < 0.99: bad.append(f"{path}@1440x900 no JS: the close's globe is {r['img']} at opacity {r['op']:.2f} (drawn at once)")
        if r["els"]: bad.append(f"{path}@1440x900 no JS: {r['els']} .globe element(s) shown in the close")
    assert not bad, "close_step:\n  " + "\n  ".join(bad[:24])
    print(f"close_step: eight closes on the H1 step, inside their columns, each with the fine globe behind it from the band's ::before, none before it reveals, at once without JS (Proof {'; '.join(notes)})")


# ---- hc30r (system; RETHINK-hc30 SYS-4, the director's HC30 item 9; EVOLVE "Owner, 8 Nov" motion conditions): the close
# closes the loop
CLOSE_LOOP = r"""(() => { const c = document.querySelector('main > .cta-band'); if (!c) return null; const r = c.getBoundingClientRect();
  const a = getComputedStyle(c, '::after'), b = getComputedStyle(c, '::before');
  const an = c.getAnimations({ subtree: true }).map(x => ({ n: x.animationName || '', pe: (x.effect && x.effect.pseudoElement) || '', st: x.playState, d: x.effect ? x.effect.getComputedTiming().duration : 0,
    it: x.effect ? String(x.effect.getComputedTiming().iterations) : '', tl: x.timeline === document.timeline ? 'time' : 'view' }));
  const m = /matrix\(([^)]+)\)/.exec(a.transform), gw = parseFloat(b.width), gy = parseFloat(b.bottom), br = { l: parseFloat(b.left), t: parseFloat(b.top) };
  return { top: r.top, h: r.height, H: innerHeight, p: +getComputedStyle(c).getPropertyValue('--scene-p'), whole: c.classList.contains('is-whole'), off: c.classList.contains('is-offscreen'),
    inn: !!c.querySelector('[data-reveal].is-in'), mask: b.maskImage || b.webkitMaskImage || 'none', comp: b.maskComposite || '', bead: a.content === 'none' || a.content === 'normal' ? null : { op: +a.opacity, w: parseFloat(a.width), bg: a.backgroundColor,
      at: m ? [+m[1].split(',')[4], +m[1].split(',')[5]] : [0, 0], c: [parseFloat(a.left) + parseFloat(a.marginLeft) + parseFloat(a.width) / 2 - br.l, parseFloat(a.top) + parseFloat(a.marginTop) + parseFloat(a.height) / 2 - br.t] }, gw, gy, an,
    end: Math.round(document.documentElement.scrollHeight - innerHeight - scrollY) }; })()"""


@check
async def close_loop(b):
    """hc30r (system; RETHINK-hc30 SYS-4, the director's HC30 item 9): every page ended on a still. On Proof and the blog
    index at 1440 x 900 and with touch at 390 x 844, with motion: before the close is on screen its ring is not drawn
    (--scene-p 0); as the band rises the ring is drawn round once with the scroll (--scene-p never falls while scrolling
    down), by a mask on the band's ::before (a conic gradient: the
    globe's own picture is untouched) with one green bead at its tip (the band's ::after: on the ring's ellipse, 104/240
    of the globe's width from its centre, within 3 px); when the ring is whole the band takes .is-whole, the scroll
    animation is gone, and the bead runs the ellipse on the clock (close-lap, 20 s, endless, a transform: nothing on the
    main thread); scrolling back up never un-draws it (drawn once); with the close off screen the lap is paused. Under
    reduced motion and without JavaScript: the whole ring, no mask, no bead, nothing animated.
    hc30r, third sitting (system): the ring is drawn while it stands on screen, not while it enters (on a phone the whole
    drawing happened in the last 55 px above the fold). The clause "whole by the time the whole band is in view" now
    reads: nothing is drawn before the ring's centre has crossed the foot of the screen (--scene-p under .02 there), and
    the ring is whole when its centre stands .45 of the globe's width above it (the band's foot `-bottom - .05 width` of
    the globe above the fold), which every page reaches before its end (at least 40 px of scroll left). The walk runs
    from the band's top at the fold to that point."""
    bad, notes = [], []
    for path in ("evidence.html", "blog/index.html"):
        for w, h, dpr, touch in ((1440, 900, 1, False), (390, 844, 3, True)):
            tag = f"{path}@{w}x{h}"
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch)
            top = await pg.evaluate("(() => { const c = document.querySelector('main > .cta-band'); return c ? c.getBoundingClientRect().top + scrollY : null; })()")
            if top is None: bad.append(f"{tag}: no close"); await ctx.close(); continue
            bh = await pg.evaluate("document.querySelector('main > .cta-band').offsetHeight")
            await pg.evaluate(f"window.scrollTo({{top: {max(0, top - h - 40)}, behavior: 'instant'}})"); await pg.wait_for_timeout(500)
            r0 = await pg.evaluate(CLOSE_LOOP)
            if r0["p"] > 0.001 or r0["whole"]: bad.append(f"{tag}: before the close is on screen its ring reads --scene-p {r0['p']} (whole: {r0['whole']})")
            if "conic-gradient" not in r0["mask"]: bad.append(f"{tag}: the ring is not drawn by a mask on the band's ::before ({r0['mask'][:60]!r})")
            if not r0["bead"]: bad.append(f"{tag}: no bead (the band's ::after)")
            ps, seen_mid = [], None
            done = bh + (-r0["gy"] - r0["gw"] * .05)   # the band's foot this far above the fold: the ring's centre .45 of the globe's width up
            for k in range(0, 41):
                y = top - h + (done + 6) * k / 40
                await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})"); await pg.wait_for_timeout(120)
                r = await pg.evaluate(CLOSE_LOOP); ps.append(r["p"])
                centre = r["H"] - (r["top"] + r["h"]) + r["gw"] / 2 + r["gy"]   # the ring's centre above the fold
                if centre < -2 and r["p"] > 0.02: bad.append(f"{tag}: the ring is part drawn (--scene-p {r['p']:.2f}) with its centre still {-centre:.0f} px under the fold")
                if k == 40 and r["end"] < 40: bad.append(f"{tag}: the ring is whole only {r['end']} px before the page's end")
                if r["bead"] and 0.15 < r["p"] < 0.85 and r["inn"] and not r["whole"]: seen_mid = r
            if any(q < p - 0.002 for p, q in zip(ps, ps[1:])): bad.append(f"{tag}: --scene-p falls while the band rises ({[round(p, 2) for p in ps]})")
            if ps[-1] < 0.999: bad.append(f"{tag}: with its centre .45 of the globe's width above the fold the ring is not whole (--scene-p {ps[-1]:.2f})")
            if not [p for p in ps if 0.02 < p < 0.98]: bad.append(f"{tag}: the ring is never part drawn on the way in ({[round(p, 2) for p in ps]}): it is not tied to the scroll")
            if seen_mid:
                bd, gw = seen_mid["bead"], seen_mid["gw"]
                dx, dy = bd["c"][0] + bd["at"][0] - gw / 2, bd["c"][1] + bd["at"][1] - gw / 2   # the bead from the globe's centre
                import math
                t = math.radians(4); u, v = dx * math.cos(t) - dy * math.sin(t), dx * math.sin(t) + dy * math.cos(t)   # into the ellipse's own axes (it is tilted -4 deg)
                off = abs(math.hypot(u / (gw * 104 / 240), v / (gw * 24 / 240)) - 1) * gw * 24 / 240
                if off > 3: bad.append(f"{tag}: at --scene-p {seen_mid['p']:.2f} the bead is {off:.1f} px off the ring's ellipse (at {dx:.0f}, {dy:.0f} from the globe's centre, globe {gw:.0f} px)")
                if bd["op"] < 0.99 or bd["bg"] != "rgb(79, 203, 147)": bad.append(f"{tag}: the bead at opacity {bd['op']:.2f}, {bd['bg']} (1, signal bright)")
            else: bad.append(f"{tag}: no step showed the bead on a part-drawn ring")
            await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(700)
            e = await pg.evaluate(CLOSE_LOOP)
            lap = [a for a in e["an"] if a["n"] == "close-lap"]
            if not e["whole"] or e["p"] < 0.999: bad.append(f"{tag}: at the page's end the ring is not whole (.is-whole {e['whole']}, --scene-p {e['p']})")
            if [a for a in e["an"] if a["n"] == "scene-p"]: bad.append(f"{tag}: once whole the band still runs its scroll animation")
            if not lap or lap[0]["pe"] != "::after" or lap[0]["st"] != "running" or abs(lap[0]["d"] - 20000) > 1 or lap[0]["it"] != "Infinity" or lap[0]["tl"] != "time":
                bad.append(f"{tag}: once whole the bead does not run its lap (close-lap on ::after, running, 20 s, endless): {lap or e['an']}")
            await pg.evaluate(f"window.scrollTo({{top: {top - h + bh * 0.5}, behavior: 'instant'}})"); await pg.wait_for_timeout(400)
            u = await pg.evaluate(CLOSE_LOOP)
            if not u["whole"] or u["p"] < 0.999: bad.append(f"{tag}: scrolling back up un-draws the ring (--scene-p {u['p']}): it is drawn once")
            await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(600)
            o = await pg.evaluate(CLOSE_LOOP)
            run = [a for a in o["an"] if a["n"] == "close-lap" and a["st"] == "running"]
            if run and o["off"]: bad.append(f"{tag}: with the close off screen its bead still runs")
            if path == "evidence.html": notes.append(f"{w}: drawn over {len([p for p in ps if 0 < p < 1])} of 41 steps")
            await ctx.close()
    for mode, kw in (("reduced motion", dict(reduced=True)), ("no JavaScript", dict(js=False))):
        ctx, pg = await open_page(b, "evidence.html", 1440, 900, **kw)
        await pg.evaluate("(() => { const c = document.querySelector('main > .cta-band'); c.scrollIntoView({block: 'center', behavior: 'instant'}); })()"); await pg.wait_for_timeout(900)
        r = await pg.evaluate(CLOSE_LOOP)
        await ctx.close()
        if r["bead"]: bad.append(f"evidence.html@1440x900, {mode}: a bead is drawn ({r['bead']})")
        if "conic-gradient" in r["mask"]: bad.append(f"evidence.html@1440x900, {mode}: the ring is masked")
        if r["an"]: bad.append(f"evidence.html@1440x900, {mode}: the close animates ({r['an'][:2]})")
        if abs(r["p"] - 1) > 0.001: bad.append(f"evidence.html@1440x900, {mode}: --scene-p {r['p']} (1: the whole ring)")
    assert not bad, "close_loop:\n  " + "\n  ".join(bad[:24])
    print(f"close_loop: the close's ring is drawn round once with the scroll, a bead at its tip, then the bead laps on the clock; drawn once, paused off screen, whole and still under reduced motion and without JavaScript (Proof {'; '.join(notes)})")


# hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1): the record row on paper left with
# the strip (§01 itself is the paper now); the probe reads S4's parts: the headline, the lede, its last line, the shown
# labels (each with its effective opacity, ancestors included) and the stage's canvas, against the paper's edge
PAPER_ROW = r"""(() => { const paper = document.querySelector('.story-paper'), st = document.querySelector('.story'), b4 = document.querySelector('.beat-4');
  if (!paper || !st || !b4) return null;
  const pr = paper.getBoundingClientRect(), shown = getComputedStyle(paper).visibility !== 'hidden' && pr.height > .5;
  const eff = el => { let o = 1; for (let x = el; x; x = x.parentElement) { const cs = getComputedStyle(x); if (cs.visibility === 'hidden' || cs.display === 'none') return 0; o *= +cs.opacity; } return o; };
  const R = (el, k) => { if (!el || !el.getClientRects().length) return null; const r = el.getBoundingClientRect(); return { k, t: r.top, b: r.bottom, o: eff(el) }; };
  const parts = [R(b4.querySelector('h2'), 'headline'), R(b4.querySelector('.body-lg'), 'lede'), R(b4.querySelector('.beat-more'), 'last line')]
    .concat([...document.querySelectorAll('.story-labels .story-lab')].map((l, i) => R(l, 'label ' + (l.className.replace(/\bstory-lab\b|\bis-\w+/g, '').trim() || 'x') + ' #' + i)))
    .concat([R(st.querySelector('canvas'), 'canvas')]).filter(Boolean);
  const nav = document.querySelector('.nav');
  return { edge: shown ? pr.top : null, parts, cov: st.classList.contains('is-covered'),
    beats: [...st.querySelectorAll('.beat')].map(x => getComputedStyle(x).visibility === 'hidden' || eff(x) < .01),
    navB: nav ? nav.getBoundingClientRect().bottom : 0, H: innerHeight, end: Math.round(st.offsetTop + st.offsetHeight) }; })()"""


@check
async def paper_row(b):
    """hc24 (integrate, standing in for tests; the director's HC24 8, done by home in story.js and home.css): the overture's
    last frame landed the record row whole on paper (the paper's edge over the printed ticks, no record across it); hc26r
    took that to the portrait exit. hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1:
    "the paper wipes the chart; nothing fades first", the ten-tick strip and the ink row deleted): §01 itself is the
    paper, and the principle is now the wipe. At 1440 x 900, 1920 x 1080, 3840 x 2160, 1024 x 768, 1280 x 600 (a short
    one), 768 x 1024 and with touch at 390 x 844, walking down in tenth-of-a-screen steps from S4's rest (STORY_Y(4)) to
    the release (story end - h), each step settled: S4's parts shown at rest (the headline, the lede, "The full proof
    file", every label at opacity 1 then, and the stage's canvas) are still at opacity 1 (effective, ancestors included)
    at every step wherever any of them stands above the paper's edge (or the paper is not up yet): nothing of S4 fades
    before the edge reaches it; the paper rises at least half a screen during the walk; and at the release the story is
    .is-covered and every beat hidden (visibility hidden or opacity 0: nothing of S4 rides under the bar or takes focus
    behind the paper)."""
    bad, notes = [], []
    for w, h, touch in ((1440, 900, False), (1920, 1080, False), (3840, 2160, False), (1024, 768, False),
                        (1280, 600, False), (390, 844, True), (768, 1024, False)):
        tag = f"index.html@{w}x{h}"
        ctx, pg = await open_page(b, "index.html", w, h, dpr=2 if touch else 1, touch=touch)
        await pg.wait_for_timeout(1500)
        y0 = await pg.evaluate(STORY_Y, 4.0)
        cur, y, steps, rest, rel, rose = 0, y0, 0, None, None, 0.0
        while True:
            while cur < y:
                cur = min(y, cur + h // 4); await pg.evaluate(f"window.scrollTo(0, {cur})"); await pg.wait_for_timeout(80)
            await pg.wait_for_timeout(800)
            r = await pg.evaluate(PAPER_ROW); steps += 1
            if not r: bad.append(f"{tag}: no .story-paper / .story / .beat-4"); break
            if rel is None: rel = r["end"] - h
            if rest is None:
                rest = {x["k"] for x in r["parts"] if x["o"] > 0.99}
                if not {"headline", "lede", "last line", "canvas"} <= rest: bad.append(f"{tag}: at S4's rest not every part is at opacity 1 ({sorted(k for k in ('headline', 'lede', 'last line', 'canvas') if k not in rest)})")
            e = r["edge"]
            if e is not None: rose = max(rose, h - e)
            if y < rel:
                for x in r["parts"]:
                    if x["k"] not in rest or x["b"] <= r["navB"] or x["t"] >= h: continue
                    if (e is None or x["t"] < e - 0.5) and x["o"] < 0.99:
                        bad.append(f"{tag} at {cur} ({(cur - y0) / h:.1f} screens into the exit, edge {'none' if e is None else round(e)}): {x['k']} at opacity {x['o']:.2f} above the paper's edge (it fades before the edge reaches it)")
            else:
                if not r["cov"]: bad.append(f"{tag} at the release ({cur}): the story is not .is-covered")
                if not all(r["beats"]): bad.append(f"{tag} at the release ({cur}): {r['beats'].count(False)} beat(s) still shown behind the paper")
                break
            y = min(rel, round(y + h * 0.1))
        if rose < 0.5 * h: bad.append(f"{tag}: the paper rose {rose:.0f} px on the walk (half a screen at least)")
        notes.append(f"{w}x{h} {steps} steps, {len(rest or ())} parts held")
        await ctx.close()
    assert not bad, "paper_row:\n  " + "\n  ".join(bad[:24])
    print(f"paper_row: the paper (§01) wipes S4 whole, nothing of it faded before the edge, the beats hidden once covered ({'; '.join(notes)})")


DESK_ORDER = r"""(() => { const d = document.querySelector('#desk .desk') || document.querySelector('.desk'); if (!d) return null;
  const R = s => { const e = d.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { t: r.top, b: r.bottom, l: r.left, r: r.right }; };
  return { chart: R('.desk-chart'), side: R('.desk-side'), lane: R('.desk-lane'), ledger: R('.desk-ledger') }; })()"""


@check
async def desk_order(b):
    """hc24 (integrate, standing in for tests; the director's HC24 4.7, done by platform): Lifecycles' desk reads in source
    order where it stacks, so the controls follow the picture they move and the focus order is the screen's: with touch at
    390 x 844 and 320 x 640, and at 768 x 1024 and 960 x 1000, the chart, then the counters and sliders (`.desk-side`),
    then the lane, then the ledger, each wholly under the one before (1 px); at 1440 x 900 and with a phone held sideways
    (844 x 390, touch) the side column stands beside the chart. Before hc24 the sliders came before the chart on phones
    and after the ledger on tablets."""
    bad = []
    for w, h, dpr, touch, stacked in ((390, 844, 3, True, True), (320, 640, 2, True, True), (768, 1024, 2, False, True), (960, 1000, 1, False, True),
                                      (1440, 900, 1, False, False), (844, 390, 3, True, False)):
        tag = f"lifecycles.html@{w}x{h}"
        ctx, pg = await open_page(b, "lifecycles.html", w, h, dpr=dpr, touch=touch)
        await pg.evaluate("document.querySelector('#desk').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(DESK_ORDER)
        await ctx.close()
        if not r or not all(r.values()): bad.append(f"{tag}: the desk's chart, side, lane or ledger is missing ({r})"); continue
        if stacked:
            seq = ["chart", "side", "lane", "ledger"]
            for a, z in zip(seq, seq[1:]):
                if r[z]["t"] < r[a]["b"] - 1: bad.append(f"{tag}: the {z} ({r[z]['t']:.0f}) is not under the {a} (ends {r[a]['b']:.0f})")
        else:
            c, s = r["chart"], r["side"]
            if not (s["l"] >= c["r"] - 1 and s["t"] < c["b"] and c["t"] < s["b"]): bad.append(f"{tag}: the side column is not beside the chart (chart {c}, side {s})")
    assert not bad, "desk_order:\n  " + "\n  ".join(bad)
    print("desk_order: the desk stacks chart, counters and sliders, lane, ledger on phones and tablets; the side beside the chart at 1440 and on a phone held sideways")



# ---- hc25 (integrate, standing in for tests): the lab's emergency halt at one width (HC25 5), the two scroll scenes
# (HC25 1, 2), the phone footer's Access row (HC25 8), the chapters' links under their heads and §04's one baseline (HC25 6, 7)
HALT_BAR = r"""(() => { const bar = document.querySelector('.swarm-bar'), b = document.querySelector('[data-sw-halt]'); if (!bar || !b) return null;
  const B = bar.getBoundingClientRect(), R = e => { const r = e.getBoundingClientRect(); return [r.left - B.left, r.top - B.top, r.width, r.height]; };
  const labs = [...bar.querySelectorAll('.swarm-controls label')].map(l => { const s = l.querySelector('span'), o = s && s.querySelector('output'), t = s && s.firstChild;
    if (!o || !t || t.nodeType !== 3) return null;
    const rg = document.createRange(); rg.selectNodeContents(t); const rs = [...rg.getClientRects()].filter(r => r.width > .5), last = rs[rs.length - 1], orr = o.getBoundingClientRect();
    const tops = [...o.getClientRects()].filter(r => r.width > .5).map(r => r.top).sort((x, y) => x - y);  // one rect per fragment ('· ' is its own): count lines
    return { name: t.textContent.trim(), boxes: tops.filter((v, i) => !i || v - tops[i - 1] > 2).length, under: !!last && orr.top >= last.bottom - 1,
             sep: getComputedStyle(o, '::before').content, input: R(l.querySelector('input')) }; });
  return { label: b.textContent.trim(), btn: R(b), labs }; })()"""


@check
async def halt_toggle(b):
    """hc25 (integrate, standing in for tests; the director's HC25 5, done by home and platform, the width in swarm.css):
    the lab's stop button names the product's emergency halt, as Platform §05's table and Trust's rail do, and toggling it
    moves nothing. On Home and Platform at 1440 x 900, 1280 x 800, 1101 x 800, 1024 x 768 and with touch at 390 x 844 and
    320 x 640: the button reads "Emergency halt"; pressed, it reads "Resume" and, pressed again, "Emergency halt"; its box
    and both sliders' boxes are the same in all three states (0.5 px). Each slider's value is one box (never split from its
    separator over two lines), and where it sits under its name it carries no "·" (no separator at a line's end). Before
    hc25 the button read "Halt", "Emergency halt" was 34 px wider than "Resume" (every toggle moved the sliders 17 px), and
    from 1101 to 1359 px "Agents in this model · 1.8k" broke after its "·"."""
    bad, notes = [], []
    for path in ("index.html", "platform.html"):
        for w, h, dpr, touch in ((1440, 900, 1, False), (1280, 800, 1, False), (1101, 800, 1, False), (1024, 768, 1, False), (390, 844, 3, True), (320, 640, 2, True)):
            tag = f"{path}@{w}x{h}"
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch, reduced=True)
            await pg.evaluate("document.querySelector('.swarm-bar').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(500)
            states = [await pg.evaluate(HALT_BAR)]
            for _ in range(2):
                if not states[-1]: break
                await pg.evaluate("document.querySelector('[data-sw-halt]').click()"); await pg.wait_for_timeout(350)
                states.append(await pg.evaluate(HALT_BAR))
            await ctx.close()
            if not all(states): bad.append(f"{tag}: no lab bar or halt button"); continue
            got = [s["label"] for s in states]
            if got != ["Emergency halt", "Resume", "Emergency halt"]: bad.append(f"{tag}: the button reads {got}, not Emergency halt / Resume / Emergency halt")
            a = states[0]
            for i, s in enumerate(states[1:], 1):
                d = max(abs(x - y) for x, y in zip(a["btn"], s["btn"]))
                if d > 0.5: bad.append(f"{tag}: toggle {i} moves or resizes the button by {d:.1f} px ({a['btn']} -> {s['btn']})")
                for la, ls in zip(a["labs"], s["labs"]):
                    if la and ls:
                        d = max(abs(x - y) for x, y in zip(la["input"], ls["input"]))
                        if d > 0.5: bad.append(f"{tag}: toggle {i} moves the slider '{la['name']}' by {d:.1f} px")
            for l in a["labs"]:
                if not l: bad.append(f"{tag}: a slider without its name and value"); continue
                if l["boxes"] != 1: bad.append(f"{tag}: '{l['name']}''s value (with its separator) is split over {l['boxes']} lines")
                if l["under"] and l["sep"] not in ("none", "normal"): bad.append(f"{tag}: '{l['name']}''s value sits under its name and still draws {l['sep']}")
            if w in (1440, 1101) and path == "index.html": notes.append(f"{w}: {a['btn'][2]:.0f} px, values {'under' if a['labs'][0]['under'] else 'beside'} their names")
    assert not bad, "halt_toggle:\n  " + "\n  ".join(bad[:24])
    print(f"halt_toggle: Emergency halt / Resume at one width on Home and Platform, nothing moves on a toggle, no '·' at a line's end ({'; '.join(notes)})")


STACK_SCENE = r"""(() => { const f = document.querySelector('[data-plate="stack"]'); if (!f) return null; const g = f.querySelector('.hp-s1');
  const C = e => { const r = e.getBoundingClientRect(); return (r.top + r.bottom) / 2; };
  const pl = [...f.querySelectorAll('.pl')].map(x => x.querySelector('.hp-h')), n = [...f.querySelectorAll('.hp-lab--n')];
  return { p: g ? +getComputedStyle(g).getPropertyValue('--st-p') : null, dy: n.map((e, i) => pl[i] ? Math.abs(C(e) - C(pl[i])) : 99),
           anims: f.getAnimations({subtree: true}).length, scroll: f.getAnimations({subtree: true}).filter(a => a.timeline && a.timeline !== document.timeline).length,
           lay: pl.length, y: scrollY, H: innerHeight }; })()"""
COST_SCENE = r"""(() => { const fig = document.querySelector('#economics figure.cost'); if (!fig) return null;
  const rows = [...fig.querySelectorAll('.pf-ck > div')];
  const shown = e => { const cs = getComputedStyle(e), m = (cs.clipPath || '').match(/^inset\(([^)]*)\)/); let cut = 0;
    if (m) { const p = m[1].trim().split(/\s+/), rgt = p.length > 1 ? p[1] : p[0]; cut = /%$/.test(rgt) ? parseFloat(rgt) / 100 : parseFloat(rgt) / (e.getBoundingClientRect().width || 1); }
    return +cs.opacity * Math.max(0, 1 - cut); };
  return { top: fig.getBoundingClientRect().top + scrollY, H: innerHeight, dec: fig.classList.contains('is-dec') && !!fig.querySelector('.pf-ck'),
    rows: rows.map(d => { const r = d.getBoundingClientRect(), g = [...d.querySelectorAll('.cost-blk .is-gone, .cost-blk .is-rest')];
      const cover = i => { const s = getComputedStyle(i, '::before'); return s.content === 'none' ? 0 : +s.opacity; };
      const op = g.map(cover), all = [...d.querySelectorAll('.cost-blk .is-gone, .cost-blk .is-rest, .cost-blk .is-part')].map(cover), em = d.querySelector('.cost-db em');
      return { t: r.top, h: r.height, prog: (innerHeight - r.top) / (innerHeight + r.height), cp: +getComputedStyle(d).getPropertyValue('--scene-p'), out: g.length, max: op.length ? Math.max(...op) : 0, min: op.length ? Math.min(...op) : 0,
               // hc30r (PROOF-1): the drain steps. mid: units whose cover is neither there nor gone; on: units still covered; em: "Eliminated"
               // (how much of the word shows: its opacity times the part its clip leaves, 0 while it is clipped away)
               mid: all.filter(v => v > .02 && v < .98).length, on: op.filter(v => v >= .98).length, em: em ? shown(em) : null,
               anims: d.getAnimations().length }; }) }; })()"""


@check
async def scroll_scenes(b):
    """hc25 (integrate, standing in for tests; the director's HC25 1 and 2, done by platform and proof, under EVOLVE's
    "Owner, 8 Nov" motion conditions): the two scroll-linked scenes follow the page's own scroll and reduced motion turns
    them off completely. Platform's hero (1440 x 900, and with touch at 390 x 844): with motion its stack is exactly still
    at the top (--st-p 0), parted at 30% of a screen down (--st-p 1) with every layer numeral still on its layer (1.5 px),
    and still again back at the top; under reduced motion the plate runs no animation and stays at 0. Proof §02 (1440 x 900,
    and with touch at 390 x 844): with motion each row of the decomposed index arrives filled (--cp 0, every block the
    agentic stack drops drawn at full) while it enters the screen, and ends on the still picture (--cp 1, those blocks
    empty to outlines) once it has risen past the middle; under reduced motion each row is the still picture at once (--cp 1,
    nothing filled, no animation). Native scrolling drives both (window.scrollTo); check_static offscreen_pause pins their
    off-screen pause.
    hc26r (integrate, standing in for tests; platform's and proof's requests): Platform's hero is the first act of a
    pinned scene on windows of 1000 x 700 and up (stack_scene checks it there), so its hc25 parting is checked where it
    still runs on the page's own scroll: 960 x 900 and 390 x 844 (touch), with reduced motion also at 1440 x 900. Proof
    §02's rows are bare data-scene on the scene primitive (SYS-1): their progress is --scene-p (it was --cp), same range
    (cover 10% cover 40%), same pictures.
    hc29 (integrate, standing in for tests; home's request, the HC29 director's item 3: "one dataset, one picture"): Home
    §03 is now the same rows component (`figure.cost[data-cost-view="rows"]`, proof.js rows(), the same data-scene rows
    and range), so the Proof half runs on Home's #economics too, with the same pictures and the same reduced-motion still;
    on both pages the figure must be in its rows view (.is-dec with its key rows).
    hc30r (PROOF-1; integrate, standing in for tests, on proof's request; TESTS.md section 53): the rows are drawn on one
    grid of units and the drain steps: a unit is ink or hollow at every scroll offset, never a blend, and "Eliminated"
    arrives when its row has emptied. The rows' ranges are their own now (cover 12%-52%, 12%-46%, 9%-30%), so "risen" is
    read past the longest (53%; it was 41%). New, on both pages with motion: at 16 offsets from the first row entering to
    the last row risen, no unit's cover is between 0 and 1, the count of covered units never rises as the page goes down,
    and "Eliminated" is shown only on a row whose every unit is hollow; at the end every row that has the word shows it."""
    bad, notes = [], []
    for w, h, dpr, touch, rms in ((960, 900, 1, False, (False, True)), (1440, 900, 1, False, (True,)), (390, 844, 3, True, (False, True))):
        for reduced in rms:
            tag = f"platform.html@{w}x{h}{' reduced' if reduced else ''}"
            ctx, pg = await open_page(b, "platform.html", w, h, dpr=dpr, touch=touch, reduced=reduced)
            await pg.wait_for_timeout(600)
            r0 = await pg.evaluate(STACK_SCENE)
            if not r0 or r0["p"] is None: bad.append(f"{tag}: no stack plate scene (.hp-s1)"); await ctx.close(); continue
            await pg.evaluate(f"window.scrollTo({{top: Math.ceil(innerHeight * .3) + 2, behavior: 'instant'}})"); await pg.wait_for_timeout(500)
            r1 = await pg.evaluate(STACK_SCENE)
            await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(500)
            r2 = await pg.evaluate(STACK_SCENE)
            await ctx.close()
            if reduced:
                if r0["anims"] or r1["anims"]: bad.append(f"{tag}: the plate runs {max(r0['anims'], r1['anims'])} animation(s) under reduced motion")
                if abs(r1["p"]) > 0.001: bad.append(f"{tag}: --st-p is {r1['p']:.3f} after scrolling under reduced motion (0)")
                continue
            if abs(r0["p"]) > 0.01: bad.append(f"{tag}: at the top --st-p is {r0['p']:.3f} (0: the plate as drawn)")
            if r1["p"] < 0.99: bad.append(f"{tag}: 30% of a screen down --st-p is {r1['p']:.3f} (1)")
            if abs(r2["p"]) > 0.01: bad.append(f"{tag}: back at the top --st-p is {r2['p']:.3f} (0)")
            if not r1["scroll"]: bad.append(f"{tag}: no animation on a scroll timeline in the plate")
            off = [i + 1 for i, d in enumerate(r1["dy"]) if d > 1.5]
            if r1["lay"] != 8 or off: bad.append(f"{tag}: parted, layer numeral(s) {off} off their layers ({[round(d, 1) for d in r1['dy']]}; {r1['lay']} layers)")
            notes.append(f"stack {w}: {r0['p']:.2f} -> {r1['p']:.2f} -> {r2['p']:.2f}, numerals <= {max(r1['dy']):.1f} px")
    for path, w, h, dpr, touch in (("evidence.html", 1440, 900, 1, False), ("evidence.html", 390, 844, 3, True), ("index.html", 1440, 900, 1, False), ("index.html", 390, 844, 3, True)):
        for reduced in (False, True):
            tag = f"{path}@{w}x{h}{' reduced' if reduced else ''}"
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch, reduced=reduced)
            await pg.evaluate("document.querySelector('#economics').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(1200)
            g = await pg.evaluate(COST_SCENE)
            if not g or not g["rows"]: bad.append(f"{tag}: no decomposed cost index (#economics .pf-ck > div)"); await ctx.close(); continue
            if not g["dec"]: bad.append(f"{tag}: the cost figure is not in its rows view (figure.cost.is-dec with .pf-ck)")
            # entering: the first row's top 2 px above the screen's foot; past the middle: the last row's top at 30% of the screen
            first = g["rows"][0]["t"] + (await pg.evaluate("scrollY"))
            last = g["rows"][-1]["t"] + (await pg.evaluate("scrollY"))
            y_in, y_out = first - h + 2, last - h * .3
            await pg.evaluate(f"window.scrollTo({{top: {y_in}, behavior: 'instant'}})"); await pg.wait_for_timeout(600)
            a = await pg.evaluate(COST_SCENE)
            steps = []
            if not reduced:
                # hc30r: the drain, offset by offset (the two ends are read below as before)
                for k in range(1, 16):
                    await pg.evaluate(f"window.scrollTo({{top: {y_in + (y_out - y_in) * k / 16}, behavior: 'instant'}})"); await pg.wait_for_timeout(250)
                    steps.append(await pg.evaluate(COST_SCENE))
            await pg.evaluate(f"window.scrollTo({{top: {y_out}, behavior: 'instant'}})"); await pg.wait_for_timeout(600)
            z = await pg.evaluate(COST_SCENE)
            await ctx.close()
            if not any(r["out"] for r in z["rows"]): bad.append(f"{tag}: no emptied blocks in the index"); continue
            if reduced:
                for k, s in (("entering", a), ("past the middle", z)):
                    if any(abs(r["cp"] - 1) > 0.001 or r["max"] > 0.001 or r["anims"] for r in s["rows"]): bad.append(f"{tag} {k}: under reduced motion a row is not the still picture ({[(round(r['cp'], 2), round(r['max'], 2), r['anims']) for r in s['rows']]})")
                    if any(r["em"] is not None and r["em"] < 0.98 for r in s["rows"]): bad.append(f"{tag} {k}: under reduced motion a row's 'Eliminated' is not shown ({[r['em'] for r in s['rows']]})")
                continue
            # a row's own view timeline starts at cover 9% or later and ends by cover 52%: entering (<= 9%) it is filled,
            # risen (>= 53%) it is still
            for i, r in enumerate(a["rows"]):
                if r["prog"] > 0.09: continue
                if r["cp"] > 0.02 or (r["out"] and r["min"] < 0.98): bad.append(f"{tag}: row {i + 1} entering is not filled (--scene-p {r['cp']:.2f}, blocks {r['min']:.2f}-{r['max']:.2f})")
            if a["rows"][0]["prog"] > 0.09: bad.append(f"{tag}: the first row did not stand at the screen's foot (cover {a['rows'][0]['prog']:.2f})")
            for i, r in enumerate(z["rows"]):
                if r["prog"] < 0.53: bad.append(f"{tag}: row {i + 1} did not rise past its range (cover {r['prog']:.2f})"); continue
                if r["cp"] < 0.98 or r["max"] > 0.02: bad.append(f"{tag}: row {i + 1} past the middle is not the still picture (--scene-p {r['cp']:.2f}, a block at {r['max']:.2f})")
                if r["em"] is not None and r["em"] < 0.98: bad.append(f"{tag}: row {i + 1} past the middle does not show 'Eliminated' (opacity {r['em']:.2f})")
            # hc30r: the steps
            walk = [a] + steps + [z]
            covered = [sum(r["on"] for r in s["rows"]) for s in walk]
            for k, s in enumerate(walk):
                for i, r in enumerate(s["rows"]):
                    if r["mid"]: bad.append(f"{tag} at offset {k} of 16: row {i + 1} has {r['mid']} unit(s) between ink and hollow (the drain steps, never a blend)")
                    if r["em"] is not None and r["em"] > 0.02 and r["on"]: bad.append(f"{tag} at offset {k} of 16: row {i + 1} shows 'Eliminated' (opacity {r['em']:.2f}) with {r['on']} unit(s) still covered")
            up = [k for k in range(1, len(covered)) if covered[k] > covered[k - 1]]
            if up: bad.append(f"{tag}: covered units rise as the page goes down ({covered})")
            if covered[0] <= covered[-1]: bad.append(f"{tag}: nothing drained between the first row entering and the last row risen ({covered})")
            notes.append(f"cost {path.split('.')[0]} {w}: {a['rows'][0]['cp']:.2f} -> {min(r['cp'] for r in z['rows']):.2f}, covered units {covered[0]} -> {covered[-1]} in {len(set(covered))} steps")
    assert not bad, "scroll_scenes:\n  " + "\n  ".join(bad[:24])
    print(f"scroll_scenes: Platform's stack parts on the page's scroll and the cost index (Proof §02, Home §03) empties as it rises, unit by unit, never blended; reduced motion keeps them still ({'; '.join(notes)})")


# ---- hc26r (system): SYS-1, one scroll-scene primitive (site.css v2:scenes, site.js); SYS-2, the drawing travels
# (site.css's page turn, site.js / afterpaint.js at pageswap and pagereveal). SYSTEM.md 13.
# A pinned test scene, put into Proof's <main> after its hero before site.js runs (readystatechange 'interactive' comes
# before the deferred scripts): a stage, an end with an id and a control, a dark tone sentinel at half the travel
SCENE_FIX = r"""(() => { document.addEventListener('readystatechange', () => {
  if (document.readyState !== 'interactive' || document.getElementById('scn-fix')) return;
  const main = document.querySelector('main'); if (!main || !main.firstElementChild) return;
  const lead = document.createElement('p'); lead.className = 'container';
  lead.innerHTML = '<a id="scn-link" href="#scn-end">To the scene end</a> <button type="button" id="scn-before">Before</button>';
  const w = document.createElement('div'); w.id = 'scn-fix'; w.setAttribute('data-scene', 'pin');
  w.innerHTML = '<div class="scene-stage"><div class="container"><p>Scene start</p><section id="scn-end" data-scene-end><h2>Scene end</h2><button type="button" id="scn-btn">A control</button></section></div></div><span data-scene-tone="dark"></span>';
  main.firstElementChild.after(lead, w); }); })()"""
SCENE_STATE = r"""(() => { const s = document.getElementById('scn-fix'); if (!s) return null; const st = s.firstElementChild, a = s.getBoundingClientRect().top + scrollY;
  return { y: scrollY, a, z: Math.ceil(a + s.offsetHeight - document.documentElement.clientHeight), pos: getComputedStyle(st).position,
    p: +getComputedStyle(s).getPropertyValue('--scene-p'), anims: s.getAnimations().length, dark: document.querySelector('.nav').classList.contains('nav--dark'),
    active: document.activeElement && document.activeElement.id, endTop: document.getElementById('scn-end').getBoundingClientRect().top,
    sp: parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0 }; })()"""
# every scene on a page ([data-scene] bare or "view", and "pin"; story.js's numbered data-scene on Home's overture is not one): its --scene-p, animations, box, and whether any HTML text inside is faded (opacity < 1
# from the text's element up to the scene: text arrives by translate or clip, only drawings change opacity)
REAL_SCENES = r"""(() => [...document.querySelectorAll('[data-scene=""], [data-scene="view"], [data-scene="pin"]')].map((s, i) => { const r = s.getBoundingClientRect();
  const faded = [...s.querySelectorAll('*')].filter(el => !el.closest('svg') && [...el.childNodes].some(n => n.nodeType === 3 && n.data.trim()) && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
    .filter(el => { let o = 1; for (let e = el; e && e !== s.parentElement; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o < .999; }).map(el => el.textContent.trim().slice(0, 30));
  const st = s.dataset.scene === 'pin' && s.firstElementChild;
  return { i, pin: s.dataset.scene === 'pin', top: r.top + scrollY, h: r.height, p: +getComputedStyle(s).getPropertyValue('--scene-p'), anims: s.getAnimations().length,
    pinned: !!st && getComputedStyle(st).position === 'sticky', faded }; }))()"""
FRAMES_ON = "(() => { window.__fr = []; let t0 = performance.now(); const f = t => { window.__fr.push(t - t0); t0 = t; if (window.__fr.length < 3000) requestAnimationFrame(f); }; requestAnimationFrame(f); })()"


def long_frames(fr, lim):
    """frames that break the 33 ms rule: any frame longer than three vsyncs (50 ms x the throttle), or more than one in a
    hundred at two (one stray missed vsync in a run passes: measured once in 121 frames after 77 checks, never alone)"""
    return any(x > lim * 1.5 for x in fr) or sum(1 for x in fr if x > lim) > max(1, len(fr) // 100)


async def scene_frames(pg, y0, y1):
    """wheel from y0 to y1 (60 px a notch, a notch a frame); the frame intervals after the first two"""
    await pg.evaluate(f"window.scrollTo({{top: {y0}, behavior: 'instant'}})"); await pg.wait_for_timeout(300)
    await pg.mouse.move(720, 450)
    await pg.evaluate(FRAMES_ON)
    for _ in range(max(1, int((y1 - y0) / 60))): await pg.mouse.wheel(0, 60); await pg.wait_for_timeout(16)
    await pg.wait_for_timeout(300)
    return (await pg.evaluate("window.__fr"))[2:]


@check
async def scenes(b):
    """hc26r (system; SYS-1, under EVOLVE's "Owner, 8 Nov" motion conditions): one scroll-scene primitive. A pinned test
    scene put into Proof (1440 x 900): its stage sticks for the whole travel, --scene-p is 0 at the travel's start, .5 half
    way and 1 at its end; the bar turns ink at the dark tone sentinel (half the travel) and not before; no frame over 33 ms
    (x the CPU throttle) while the wheel scrolls through; a link to the end's id, the address with that id and Tab into
    the end's control all land at the end (--scene-p 1). Under reduced motion and at 900 px wide nothing pins, --scene-p
    is 1 with no animation and the id lands as any anchor (under the bar). Then every real [data-scene] on the site's
    pages (1440 x 900): before its range --scene-p is 0, after it 1 (a pinned one: at its travel's start and end); no HTML
    text inside it is faded at any step; under reduced motion 1 with no animation; and no frame over the limit through a
    pinned one."""
    bad, notes = [], []
    lim = 33.4 * max(1.0, MODE["throttle"])
    ctx, pg = await open_page(b, "evidence.html", 1440, 900, init=SCENE_FIX)
    s = await pg.evaluate(SCENE_STATE)
    if not s: bad.append("evidence.html@1440: the test scene was not put in")
    else:
        a, z = s["a"], s["z"]
        rows = []
        for f, want, dark in ((0, 0, False), (.25, .25, False), (.5, .5, None), (.75, .75, True), (1, 1, True)):
            await pg.evaluate(f"window.scrollTo({{top: {a + f * (z - a)}, behavior: 'instant'}})"); await pg.wait_for_timeout(300)
            r = await pg.evaluate(SCENE_STATE); rows.append(round(r["p"], 3))
            if r["pos"] != "sticky": bad.append(f"evidence.html@1440 test scene at {f}: the stage is {r['pos']} (sticky)")
            if abs(r["p"] - want) > 0.02: bad.append(f"evidence.html@1440 test scene at {f} of the travel: --scene-p {r['p']:.3f} ({want})")
            if dark is not None and r["dark"] != dark: bad.append(f"evidence.html@1440 test scene at {f}: the bar is {'ink' if r['dark'] else 'paper'} ({'ink' if dark else 'paper'}: the sentinel is at .5)")
        fr = await scene_frames(pg, max(0, a - 450), z + 450)
        over = [round(x, 1) for x in fr if x > lim]
        if long_frames(fr, lim): bad.append(f"evidence.html@1440 test scene: {len(over)} of {len(fr)} frames over {lim:.0f} ms while scrolling through ({over[:6]})")
        notes.append(f"test scene --scene-p {rows}, frames <= {max(fr) if fr else 0:.1f} ms")
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(400)
        await pg.click("#scn-link"); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(SCENE_STATE)
        if abs(r["y"] - z) > 2 or r["p"] < 0.99: bad.append(f"evidence.html@1440: the link to #scn-end landed at {r['y']:.0f} (--scene-p {r['p']:.2f}); the end is {z}")
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(400)
        await pg.focus("#scn-before"); await pg.keyboard.press("Tab"); await pg.wait_for_timeout(1200)
        r = await pg.evaluate(SCENE_STATE)
        if r["active"] != "scn-btn" or not (z - 2 <= r["y"] <= z + 225) or r["p"] < 0.99: bad.append(f"evidence.html@1440: Tab into the scene's end: focus on {r['active']!r}, at {r['y']:.0f} (--scene-p {r['p']:.2f}); the end is {z}")
    await ctx.close()
    ctx, pg = await open_page(b, "evidence.html#scn-end", 1440, 900, init=SCENE_FIX); await pg.wait_for_timeout(1800)
    r = await pg.evaluate(SCENE_STATE)
    if r and (abs(r["y"] - r["z"]) > 2 or r["p"] < 0.99): bad.append(f"evidence.html#scn-end@1440: the address landed at {r['y']:.0f} (--scene-p {r['p']:.2f}); the end is {r['z']}")
    await ctx.close()
    for tag, w, h, reduced in (("reduced motion", 1440, 900, True), ("900 px wide", 900, 900, False)):
        ctx, pg = await open_page(b, "evidence.html", w, h, reduced=reduced, init=SCENE_FIX)
        r = await pg.evaluate(SCENE_STATE)
        if r["pos"] == "sticky" or abs(r["p"] - 1) > 0.001 or r["anims"]: bad.append(f"evidence.html@{w} {tag}: the test scene pins ({r['pos']}) or is not at its end (--scene-p {r['p']:.2f}, {r['anims']} animation(s))")
        await pg.click("#scn-link"); await pg.wait_for_timeout(1500)
        r = await pg.evaluate(SCENE_STATE)
        if abs(r["endTop"] - r["sp"]) > 2: bad.append(f"evidence.html@{w} {tag}: #scn-end landed {r['endTop']:.0f} px from the top (under the bar: {r['sp']:.0f})")
        await ctx.close()
    # every real scene
    seen = 0
    for name in PAGES:
        for reduced in (False, True):
            ctx, pg = await open_page(b, f"{name}.html", 1440, 900, reduced=reduced)
            sc = await pg.evaluate(REAL_SCENES)
            if not sc: await ctx.close(); break
            for k, s0 in enumerate(sc):
                tag = f"{name}.html@1440 scene {k + 1}{' (pinned)' if s0['pin'] else ''}{' reduced' if reduced else ''}"
                if reduced:
                    if abs(s0["p"] - 1) > 0.001 or s0["anims"] or s0["pinned"]: bad.append(f"{tag}: --scene-p {s0['p']:.2f}, {s0['anims']} animation(s), pinned {s0['pinned']} (1, none, no)")
                    continue
                seen += 1
                vh = 900
                if s0["pin"]:
                    steps = [(s0["top"], 0), (s0["top"] + (s0["h"] - vh) * .5, None), (s0["top"] + s0["h"] - vh, 1)]
                else:
                    steps = [(max(0, s0["top"] - 2 * vh), 0), (s0["top"] - vh * .5, None), (s0["top"] + s0["h"] + vh, 1)]
                for y, want in steps:
                    await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})"); await pg.wait_for_timeout(350)
                    r = (await pg.evaluate(REAL_SCENES))[k]
                    # A scroll timeline's time is sampled once a frame. Where the page draws a few frames a second (CI's
                    # software GL on Home) the value can still be the last position's after 350 ms (CI run 42782516694:
                    # Home's scene 3 read 1.000 from the step before), so give it frames to land before judging it.
                    waited = 350
                    while want is not None and y > 0 and abs(r["p"] - want) > 0.01 and waited < 4000 * max(1.0, MODE["throttle"]):
                        await pg.wait_for_timeout(150); waited += 150
                        r = (await pg.evaluate(REAL_SCENES))[k]
                    if r["faded"]: bad.append(f"{tag} at {y:.0f}: text faded on scroll ({r['faded'][:3]}): text arrives by translate or clip")
                    if want is not None and y > 0 and abs(r["p"] - want) > 0.01: bad.append(f"{tag} at {y:.0f}: --scene-p {r['p']:.3f} ({want})")
                if s0["pin"]:
                    fr = await scene_frames(pg, s0["top"] - 300, s0["top"] + s0["h"])
                    over = [round(x, 1) for x in fr if x > lim]
                    if MODE["gl"] == "gpu":
                        if long_frames(fr, lim): bad.append(f"{tag}: {len(over)} of {len(fr)} frames over {lim:.0f} ms through the scene ({over[:6]})")
                    else:
                        # The 33 ms rule is a real-GPU rule (run it with --gpu, as the integrator does). Under SwiftShader the
                        # CPU draws a scene's WebGL: Platform's explorer starts with one frame of about 1.3 s at the scene's end
                        # (measured 10 Nov: 1350 and 1283 ms; with a GPU 67 and 33 ms). Here the frames are reported, and only
                        # a hang fails.
                        hang = [round(x) for x in fr if x > 5000 * max(1.0, MODE["throttle"])]
                        if hang: bad.append(f"{tag}: a frame of {hang[0]} ms through the scene under software GL (a hang; 5 s at most)")
                        notes.append(f"{name} scene {k + 1} under software GL: {len(over)} of {len(fr)} frames over {lim:.0f} ms, longest {max(fr) if fr else 0:.0f} ms (judged with --gpu only)")
            await ctx.close()
    assert not bad, "scenes:\n  " + "\n  ".join(bad[:24])
    print(f"scenes: the primitive pins, runs 0 -> 1 over its travel, turns the bar at its sentinel, lands links, the address and Tab at its end; static under reduced motion and narrow; {seen} real scene(s) checked ({'; '.join(notes)})")


VT_FIG = r"""(() => { addEventListener('pagereveal', e => {
  const R = window.__vtfig = { vt: !!e.viewTransition, names: [], dest: null, end: 0 };
  const d = document.querySelector('[data-vt-dest]');
  const f = () => { const an = document.getAnimations().filter(a => a.effect && /::view-transition/.test(a.effect.pseudoElement || ''));
    an.forEach(a => { if (!R.names.includes(a.effect.pseudoElement)) R.names.push(a.effect.pseudoElement); R.end = Math.max(R.end, a.effect.getComputedTiming().endTime || 0); });
    if (d && R.dest === null && an.length) R.dest = getComputedStyle(d).viewTransitionName;
    if (an.length || (R.k = (R.k || 0) + 1) < 3) requestAnimationFrame(f); };
  requestAnimationFrame(f); }); })()"""


@check
async def vt_fig(b):
    """hc26r (system; SYS-2): the drawing travels with the page turn. At 1440 x 900 a click on Home §05's first note card
    (its mark carries .vt-src, home's marker) turns to note 01, whose hero (data-vt-dest, research's marker) carries the
    view-transition name `fig`: the turn has both halves of `fig` (a morph, not the plain rise), every part of it ends by
    550 ms, and one name per side (a duplicate would skip the turn: no animation at all). A click on the bar's Proof link
    during the turn is not lost (the turn ends at once and the click lands: site.js / afterpaint.js). Under reduced
    motion there is no turn."""
    bad, notes = [], []
    for reduced in (False, True):
        ctx, pg = await open_page(b, "index.html", 1440, 900, reduced=reduced, init=VT_FIG)
        src = await pg.evaluate("(() => { const a = document.querySelector('a.research-card[href*=\"01-compounding\"]'); return a ? { src: !!a.querySelector('.vt-src') || a.matches('.vt-src') } : null; })()")
        if not src: bad.append("index.html: no §05 card for note 01"); await ctx.close(); continue
        if not src["src"] and not reduced: bad.append("index.html §05 card 01: no .vt-src on its mark (home's marker, SYS-2)")
        await pg.evaluate("document.querySelector('a.research-card[href*=\"01-compounding\"]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1200)
        await pg.click("a.research-card[href*='01-compounding']"); await pg.wait_for_url("**/01-compounding-error*")
        await until(pg, "!!window.__vtfig", 5000, 10)
        await pg.wait_for_timeout(900)
        r = await pg.evaluate("window.__vtfig")
        has_dest = await pg.evaluate("!!document.querySelector('[data-vt-dest]')")
        if reduced:
            if r and (r["vt"] or r["names"]): bad.append(f"research/01 reduced motion: a page turn ran ({r['names'][:4]})")
            await ctx.close(); continue
        if not has_dest: bad.append("research/01-compounding-error.html: no [data-vt-dest] on its hero (research's marker, SYS-2)")
        if not r or not r["vt"] or not r["names"]: bad.append(f"research/01 at 1440: no page turn ran ({r}): a duplicate view-transition name skips it")
        else:
            if r["dest"] != "fig": bad.append(f"research/01 at 1440: the hero's view-transition name during the turn is {r['dest']!r} ('fig')")
            if not {"::view-transition-old(fig)", "::view-transition-new(fig)"} <= set(r["names"]): bad.append(f"research/01 at 1440: the turn has no morph of 'fig' ({[n for n in r['names'] if 'fig' in n]})")
            if r["end"] > 551: bad.append(f"research/01 at 1440: the turn runs to {r['end']:.0f} ms (550)")
            notes.append(f"morph {sorted(n.split('(')[0].split('-')[-1] for n in r['names'] if 'fig' in n)}, ends {r['end']:.0f} ms")
        # a click during a turn: back to Home, the card again, the bar's Proof link at once
        await pg.go_back(); await pg.wait_for_timeout(1500)
        await pg.evaluate("document.querySelector('a.research-card[href*=\"01-compounding\"]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(800)
        await pg.evaluate("window.__vtfig = null")
        await pg.click("a.research-card[href*='01-compounding']"); await pg.wait_for_url("**/01-compounding-error*")
        await until(pg, "!!window.__vtfig", 5000, 5)
        await pg.wait_for_timeout(60)
        box = await pg.evaluate("(() => { const a = [...document.querySelectorAll('.nav-links a')].find(x => /evidence/.test(x.href)); if (!a) return null; const r = a.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, !!document.activeViewTransition]; })()")
        if box:
            await pg.mouse.click(box[0], box[1])
            try: await pg.wait_for_url("**/evidence*", timeout=4000); notes.append(f"a click {'during' if box[2] else 'after'} the turn landed")
            except Exception: bad.append(f"research/01 at 1440: a click on the bar's Proof link {'during' if box[2] else 'after'} the turn was lost")
        await ctx.close()
    assert not bad, "vt_fig:\n  " + "\n  ".join(bad[:24])
    print(f"vt_fig: Home §05's first card turns into note 01's hero ({'; '.join(notes)}); no turn under reduced motion")


# ---- hc30r (system; RETHINK-hc30 SYS-2, under EVOLVE's "Owner, 8 Nov" motion conditions): the page turn is the boundary.
# The recorder runs in the page you reach (pagereveal) and reads, frame by frame, the transition's pseudo-elements and the
# first band's own animations; JUMP_REC does the same for an in-page jump (a same-document transition)
TURN_REC = r"""(() => { const ids = new WeakMap(); let nid = 0; const idOf = a => { if (!ids.has(a)) ids.set(a, ++nid); return ids.get(a); };
  const rec = (R, vt) => { const root = document.documentElement, cs = n => getComputedStyle(root, n);
  const f = () => { const an = document.getAnimations().filter(a => a.effect && /^::view-transition/.test(a.effect.pseudoElement || ''));
    if (an.length) { an.forEach(a => { const n = a.effect.pseudoElement.replace('::view-transition-', ''); if (!R.names.includes(n)) R.names.push(n); });
      const g = an.find(a => a.effect.pseudoElement === '::view-transition-image-pair(root)'), first = document.querySelector('main > :first-child');
      const bar = ['old', 'new'].map(k => R.names.includes(k + '(site-nav)') ? +cs('::view-transition-' + k + '(site-nav)').opacity : null);
      const live = first && !first.classList.contains('story') ? first.getAnimations({ subtree: true }).filter(a => a.timeline === document.timeline && a.effect.getComputedTiming().iterations !== Infinity && a.playState !== 'finished').map(a => (a.animationName || a.transitionProperty || '?') + '#' + idOf(a)) : [];
      try { if (vt) R.types = [...vt.types]; } catch (err) { }
      const m = /matrix\(([^)]+)\)/.exec(cs('::view-transition-image-pair(root)').transform);
      R.f.push({ t: Math.round(performance.now()), p: g ? +(g.effect.getComputedTiming().progress || 0).toFixed(3) : null, g: g ? g.animationName : null,
        end: Math.max(...an.map(a => a.effect.getComputedTiming().endTime || 0)),
        fade: an.filter(a => /-(old|new)\((root|leave)\)$/.test(a.effect.pseudoElement) && a.effect.getKeyframes().some(k => k.opacity !== undefined || k.scale !== undefined)).map(a => a.effect.pseudoElement),
        old: an.filter(a => /-old\((root|leave)\)$/.test(a.effect.pseudoElement)).map(a => a.animationName), oldOp: +cs('::view-transition-old(leave)').opacity,
        leave: cs('::view-transition-group(leave)').width, clip: cs('::view-transition-group(root)').overflow + ' ' + cs('::view-transition-image-pair(root)').overflow, z: [cs('::view-transition-group(leave)').zIndex, cs('::view-transition-group(root)').zIndex],
        top: parseFloat(cs('::view-transition-group(root)').top), navh: parseFloat(getComputedStyle(root).getPropertyValue('--nav-h')), bar,
        rule: cs('::view-transition-image-pair(root)').boxShadow, ty: m ? +(+m[1].split(',')[5]).toFixed(1) : 0, live, vtin: root.classList.contains('vt-in'), jump: root.dataset.jump || '' }); }
    if (an.length || (R.k = (R.k || 0) + 1) < 4) requestAnimationFrame(f); else R.done = true; };
  requestAnimationFrame(f); };
  window.__turnRec = () => { const R = window.__turn = { vt: true, f: [], types: [], names: [], H: innerHeight }; rec(R, null); };
  addEventListener('pagereveal', e => { const R = window.__turn = { vt: !!e.viewTransition, f: [], types: [], names: [], H: innerHeight }; if (e.viewTransition) rec(R, e.viewTransition); else R.done = true; }); })()"""
GREENS = ("rgb(79, 203, 147)", "rgb(30, 122, 90)")


def turn_issues(tag, r, *, back=False, jump=""):
    """one recorded turn against the principle: the page you leave is whole and still above the rule (its own name, no
    animation, opacity 1), the page you reach is revealed under it (a clipping window that only translates: no fade, no
    scale) on a stage that starts at the bar's foot (the rule stops there), the bar is held with the page you leave and
    switched at the turn's end (its two views are never both drawn and never part-faded), the rule is the two signal
    greens, the turn is over by 550 ms, and it runs the other way on Back / a jump up"""
    bad = []
    if not r or not r.get("vt") or not r.get("f"): return [f"{tag}: no page turn ran ({str(r)[:160]})"]
    f, H = r["f"], r["H"]
    if "image-pair(root)" not in r["names"] or "new(root)" not in r["names"]: bad.append(f"{tag}: the turn has no window on the page you reach ({r['names'][:8]})")
    if "old(root)" in r["names"] or any(x["leave"] == "auto" for x in f[:-1]): bad.append(f"{tag}: the page you leave did not take its own name ('leave'): old(root) {'old(root)' in r['names']}, group(leave) width {f[0]['leave']}")
    fade = sorted({n for x in f for n in x["fade"]}); moved = sorted({n for x in f for n in x["old"] if n and n != "none"})
    if fade: bad.append(f"{tag}: a page view fades or scales during the turn ({fade}): never a fade")
    if moved or any(x["oldOp"] < 0.999 for x in f): bad.append(f"{tag}: the page you leave is not still and opaque for the whole turn (animations {moved}, opacity {min(x['oldOp'] for x in f)})")
    if any(x["clip"] != "clip clip" for x in f): bad.append(f"{tag}: the stage and the window on the page you reach do not both clip it (overflow {f[0]['clip']})")
    if any(abs(x["top"] - x["navh"]) > 1.5 for x in f): bad.append(f"{tag}: the stage starts at {f[0]['top']} px, the bar's foot is at {f[0]['navh']} px (the rule stops at the bar's foot)")
    mixed = [x["bar"] for x in f if x["bar"][0] is not None and x["bar"][1] is not None and (0.02 < x["bar"][0] < 0.98 or 0.02 < x["bar"][1] < 0.98 or (x["bar"][0] > 0.5) == (x["bar"][1] > 0.5))]
    if mixed: bad.append(f"{tag}: the bar is cross-faded in {len(mixed)} frames (old, new opacity e.g. {mixed[:3]}): it is held with the page you leave and switched at the end")
    z = f[0]["z"]
    if not (z[0].lstrip("-").isdigit() and z[1].lstrip("-").isdigit() and int(z[0]) < int(z[1]) < 0): bad.append(f"{tag}: z-index leave {z[0]} / root {z[1]}: the page you leave lies under the window, both under the bar and the travelling drawing")
    if not all(g in f[0]["rule"] for g in GREENS): bad.append(f"{tag}: the rule is {f[0]['rule'][:80]!r}, not the two signal greens")
    end = max(x["end"] for x in f)
    if end > 551: bad.append(f"{tag}: the turn runs to {end:.0f} ms (550)")
    down = back or jump == "up"
    want = "vt-hold" if down else "vt-edge"
    if any(x["g"] != want for x in f if x["g"]): bad.append(f"{tag}: the window's animation is {sorted({x['g'] for x in f if x['g']})} ({want}: the rule runs {'down from the bar' if down else 'up from the foot'})")
    ty = [x["ty"] for x in f if x["p"] is not None and 0.02 < x["p"] < 0.98]
    if ty and not all((v < 0) if down else (v > 0) for v in ty): bad.append(f"{tag}: the window sits at {ty[:4]} px mid-turn ({'above' if down else 'below'} its place expected)")
    if ty and any(abs(v) > H + 2 for v in ty): bad.append(f"{tag}: the window is further than one screen from its place ({ty[:4]})")
    if jump and any(x["jump"] != jump for x in f): bad.append(f"{tag}: html[data-jump] reads {sorted({x['jump'] for x in f})} ({jump})")
    return bad


@check
async def page_turn(b):
    """hc30r (system; RETHINK-hc30 SYS-2): the page turn is the boundary. At 1440 x 900, from Proof (scrolled 500 px) the
    bar's link to Platform, Trust, Lifecycles, Company and Research turns the page under the rule: the page you leave takes
    the name `leave` and is whole, still and opaque for the whole turn; the page you reach is revealed in a clipping window
    that only translates (no fade, no scale) from the foot of the screen to the bar's foot (the stage it moves on starts
    at --nav-h); the bar is held with the page you leave and switched at the end, never cross-faded; the rule on the
    window's edge is the two signal greens; every part ends by 550 ms; and from the turn's midpoint on, no entrance in the first band is still running
    (html.vt-in: arriving by a turn the first screen is whole; an act that should still play goes through OXA.actOnce,
    which waits for the turn; third sitting: an entrance a script starts during the turn, as figure.js's swap of
    Company's still for its canvas, is finished in the frame it is first seen, so "still running" reads: the same
    animation live in two successive frames. The recorder's frame callback runs before the page's and saw such a swap
    once, in the run where the script booted after the midpoint). Back turns the other way (type `back`, the rule down from the bar). A hero drawing that
    nothing travels to keeps no name of its own (Platform -> Lifecycles: no `fig` in the turn). A click on the bar during
    a turn lands. An in-page jump (Platform, the chapter list's last row, then Back to top) takes the same rule, up for
    down and down for up. Leaving Home at the top, the hero keeps a globe for the snapshot though the WebGL canvas cannot
    be kept (hidden): the stage's own frame on its 2D canvas (story.js's OXA.stageStill, home's hc30r; the same box and
    bitmap, the globe drawn), or else the static mark on the globe's place (shown, centred within 2 px of
    html[data-globe]); never neither, never both. At 390 x 844
    with touch the menu's link turns the page the same way. Under reduced motion there is no turn and a jump lands at once."""
    bad, notes = [], []
    ctx, pg = await open_page(b, "evidence.html", 1440, 900, init=TURN_REC)
    for dest in ("platform", "trust", "lifecycles", "company", "research"):
        if "/evidence" not in pg.url: await pg.goto(f"{BASE}/evidence.html", wait_until="load"); await until(pg, LOADED, 15000)
        await pg.evaluate("window.scrollTo({top: 500, behavior: 'instant'})"); await pg.wait_for_timeout(500)
        await pg.click(f".nav-links a[href*='{dest}']"); await pg.wait_for_url(f"**/{dest}*")
        await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20)
        r = await pg.evaluate("window.__turn"); tag = f"evidence -> {dest} at 1440"
        bad += turn_issues(tag, r)
        if r and r.get("f"):
            late = [x for x in r["f"] if x["p"] is not None and x["p"] >= 0.5]
            live = sorted({n.split("#")[0] for x, y in zip(late, late[1:]) for n in x["live"] if n in y["live"]})
            if live: bad.append(f"{tag}: from the turn's midpoint the first band still runs {live[:6]} (arriving by a turn the first screen is whole)")
            if not all(x["vtin"] for x in late): bad.append(f"{tag}: html.vt-in is not set by the turn's midpoint")
            if dest == "platform": notes.append(f"{len(r['f'])} frames, ends {max(x['end'] for x in r['f']):.0f} ms")
    # Back turns the other way
    await pg.goto(f"{BASE}/evidence.html", wait_until="load"); await until(pg, LOADED, 15000)
    await pg.click(".nav-links a[href*='platform']"); await pg.wait_for_url("**/platform*"); await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20); await pg.wait_for_timeout(400)
    await pg.go_back(wait_until="commit"); await pg.wait_for_url("**/evidence*"); await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20)
    r = await pg.evaluate("window.__turn")
    bad += turn_issues("platform -> Back to evidence at 1440", r, back=True)
    if r and "back" not in (r.get("types") or []): bad.append(f"platform -> Back to evidence at 1440: the turn's types are {r.get('types')} ('back' expected)")
    # a hero drawing nothing travels to keeps no name; a click during the turn lands
    await pg.goto(f"{BASE}/platform.html", wait_until="load"); await until(pg, LOADED, 15000); await pg.wait_for_timeout(600)
    await pg.click(".nav-links a[href*='lifecycles']"); await pg.wait_for_url("**/lifecycles*"); await until(pg, "!!(window.__turn && window.__turn.f.length)", 6000, 5)
    box = await pg.evaluate("(() => { const a = [...document.querySelectorAll('.nav-links a')].find(x => /trust/.test(x.href)); const r = a.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, !!document.activeViewTransition]; })()")
    names = (await pg.evaluate("window.__turn"))["names"]
    await pg.mouse.click(box[0], box[1])
    try: await pg.wait_for_url("**/trust*", timeout=4000); notes.append(f"a click {'during' if box[2] else 'after'} the turn landed")
    except Exception: bad.append(f"platform -> lifecycles at 1440: a click on the bar's Trust link {'during' if box[2] else 'after'} the turn was lost")
    if any("fig" in n for n in names): bad.append(f"platform -> lifecycles at 1440: the hero drawing took the name fig though nothing travelled to it ({[n for n in names if 'fig' in n]})")
    # the in-page jump takes the same rule
    await pg.goto(f"{BASE}/platform.html", wait_until="load"); await until(pg, LOADED, 15000); await pg.wait_for_timeout(1200)
    for way, js in (("down", "document.querySelector('.nav-ch-list li:last-child a').click()"), ("up", "document.querySelector('.nav-ch-top').click()")):
        y0 = await pg.evaluate("scrollY")
        await pg.evaluate("window.__turnRec()"); await pg.evaluate(js)
        await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20)
        r = await pg.evaluate("window.__turn"); y1 = await pg.evaluate("scrollY")
        bad += turn_issues(f"platform, a jump {way} at 1440", r, jump=way)
        if abs(y1 - y0) < 900: bad.append(f"platform, a jump {way} at 1440: the page moved {y1 - y0} px")
        await pg.wait_for_timeout(300)
    await ctx.close()
    # leaving Home at the top: the hero keeps a globe for the snapshot though the WebGL canvas cannot be kept.
    # hc30r (HOME; integrate, standing in for tests; TESTS.md section 53): home took system's offer (SYSTEM.md 15,
    # OXA.stageStill): story.js copies the stage's current frame to the 2D canvas at pageswap, and site.js then leaves the
    # static mark alone. So the hero's picture for the snapshot is one of two, never neither and never both: the stage's
    # own frame (canvas.story-2d shown over the hidden WebGL canvas, the same box, the same bitmap size, and drawn: the
    # globe's limb lit inside the globe's place), or, where there is no frame to copy, the static mark on the globe's place
    # as before (shown, centred within 2 px of html[data-globe]).
    ctx, pg = await open_page(b, "index.html", 1440, 900, init=TURN_REC)
    await to_top_settled(pg)
    await pg.evaluate("""addEventListener('pageswap', () => { const m = document.querySelector('.story-static-mark'), r = m.getBoundingClientRect(), g = (document.documentElement.dataset.globe || '').split(' ').map(parseFloat);
      const gl = document.querySelector('.story-gl'), s2 = document.querySelector('canvas.story-2d'), a = gl.getBoundingClientRect(), z = s2.getBoundingClientRect();
      let lit = -1; const on = !s2.hidden && !!s2.getClientRects().length && getComputedStyle(s2).visibility !== 'hidden';
      if (on && g.length === 3 && g[2] > 0) { try { const k = s2.width / z.width, x0 = Math.max(0, Math.round((g[0] - g[2] - z.left) * k)), y0 = Math.max(0, Math.round((g[1] - g[2] - z.top) * k)), n = Math.round(2 * g[2] * k);
        const d = s2.getContext('2d').getImageData(x0, y0, Math.min(n, s2.width - x0), Math.min(n, s2.height - y0)).data; lit = 0;
        for (let i = 0; i < d.length; i += 4) if (d[i] * .2126 + d[i + 1] * .7152 + d[i + 2] * .0722 > 60) lit++; } catch (e) { lit = -2; } }
      sessionStorage.setItem('__mark', JSON.stringify({ shown: getComputedStyle(m).display !== 'none' && +getComputedStyle(m).opacity > .9, c: [r.left + r.width / 2, r.top + r.height / 2], w: r.width, g,
        still: on, box: [z.left - a.left, z.top - a.top, z.width - a.width, z.height - a.height], bmp: [s2.width - gl.width, s2.height - gl.height], lit,
        gl: getComputedStyle(gl).visibility, name: getComputedStyle(document.documentElement).viewTransitionName })); })""")
    await pg.click(".nav-links a[href*='platform']"); await pg.wait_for_url("**/platform*"); await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20)
    r = await pg.evaluate("window.__turn"); mk = await pg.evaluate("JSON.parse(sessionStorage.getItem('__mark') || 'null')")
    bad += turn_issues("home (the overture) -> platform at 1440", r)
    if not mk: bad.append("home -> platform at 1440: no pageswap on Home")
    else:
        if mk["name"] != "leave": bad.append(f"home -> platform at 1440: the root's name at the snapshot is {mk['name']!r} (leave)")
        if mk["gl"] != "hidden": bad.append(f"home -> platform at 1440: the WebGL canvas is {mk['gl']} for the snapshot (it cannot be kept: hidden)")
        g = mk["g"]
        if len(g) == 3 and g[2] > 0:
            if mk["still"] and mk["shown"]: bad.append("home -> platform at 1440: the stage's frame and the static mark are both shown for the snapshot (two globes)")
            elif mk["still"]:
                if any(abs(v) > 1 for v in mk["box"]) or any(mk["bmp"]): bad.append(f"home -> platform at 1440: the stage's frame is not the WebGL canvas's box and bitmap (box off by {[round(v, 1) for v in mk['box']]}, bitmap by {mk['bmp']})")
                elif mk["lit"] < 200: bad.append(f"home -> platform at 1440: the stage's frame is blank where the globe stands ({mk['lit']} lit pixels in the globe's place; the hero keeps a globe)")
                else: notes.append(f"Home leaves with its stage's own frame ({mk['lit']} lit pixels on the globe at {g[0]:.0f}, {g[1]:.0f}, r {g[2]:.0f})")
            elif not mk["shown"]: bad.append("home -> platform at 1440: neither the stage's frame nor the static mark is shown for the snapshot (the hero keeps a globe)")
            elif abs(mk["c"][0] - g[0]) > 2 or abs(mk["c"][1] - g[1]) > 2 or abs(mk["w"] * 92 / 240 - g[2]) > 2:
                bad.append(f"home -> platform at 1440: the static mark at {[round(v) for v in mk['c']]} / limb {mk['w'] * 92 / 240:.0f} px, the globe at {g}")
            else: notes.append(f"Home leaves with its mark on the globe ({g[0]:.0f}, {g[1]:.0f}, r {g[2]:.0f})")
    await ctx.close()
    # a phone: the menu's link
    ctx, pg = await open_page(b, "evidence.html", 390, 844, touch=True, init=TURN_REC)
    await bounded(pg.locator(".nav-toggle").tap(), "a tap on the menu toggle", 60); await pg.wait_for_timeout(700)
    await bounded(pg.locator(".nav-sheet-links a[href*='trust']").tap(), "a tap on the menu's Trust link", 60); await pg.wait_for_url("**/trust*")
    await until(pg, "!!(window.__turn && window.__turn.done)", 6000, 20)
    bad += turn_issues("evidence -> trust at 390 (the menu)", await pg.evaluate("window.__turn"))
    await ctx.close()
    # reduced motion: no turn, a jump lands at once
    ctx, pg = await open_page(b, "evidence.html", 1440, 900, reduced=True, init=TURN_REC)
    await pg.click(".nav-links a[href*='platform']"); await pg.wait_for_url("**/platform*"); await pg.wait_for_timeout(700)
    r = await pg.evaluate("window.__turn")
    if r and (r.get("vt") or r.get("f")): bad.append(f"evidence -> platform, reduced motion: a page turn ran ({(r.get('names') or [])[:4]})")
    if await pg.evaluate("document.documentElement.classList.contains('vt-in')"): bad.append("evidence -> platform, reduced motion: html.vt-in is set without a turn")
    await pg.evaluate("window.__turnRec()"); await pg.evaluate("document.querySelector('.nav-ch-list li:last-child a').click()"); await pg.wait_for_timeout(500)
    r = await pg.evaluate("window.__turn")
    if r["f"] or await pg.evaluate("scrollY") < 900: bad.append(f"platform, a jump under reduced motion: {len(r['f'])} transition frames, scrollY {await pg.evaluate('scrollY')}")
    await ctx.close()
    assert not bad, "page_turn:\n  " + "\n  ".join(bad[:28])
    print(f"page_turn: the page you leave stays whole above the rule and the page you reach is revealed under it, no fade, on five turns from Proof, on Back (the other way), on a jump down and up, from Home's overture and on a phone ({'; '.join(notes)}); no turn under reduced motion")


# ---- hc26r (integrate, standing in for tests): the rethink's scenes, checked to their principles (RETHINK-hc26 PLAT-1,
# PLAT-2, PROOF-1, PROOF-2, HOME-3, HOME-4; the groups' requests in CHANGE_REQUESTS.md, 9 Nov)
CLIP_SIDE = r"""const side = (e, k) => { if (!e) return null; const c = getComputedStyle(e).clipPath; const m = c && c.match(/inset\((.*?)(?:\s+round\b.*)?\)$/); if (!m) return c === 'none' ? '0px' : c;
    const v = m[1].trim().split(/\s+(?![^(]*\))/); const q = v.length === 1 ? [v[0], v[0], v[0], v[0]] : v.length === 2 ? [v[0], v[1], v[0], v[1]] : v.length === 3 ? [v[0], v[1], v[2], v[1]] : v; return q[k]; };"""
STACK_PIN = "(() => { " + CLIP_SIDE + r""" const s = document.querySelector('.stack-scene'); if (!s) return null; const st = s.firstElementChild;
  const a = s.getBoundingClientRect().top + scrollY, z = Math.ceil(a + s.offsetHeight - document.documentElement.clientHeight);
  const C = e => { const r = e.getBoundingClientRect(); return (r.top + r.bottom) / 2; }, q = x => document.querySelector(x);
  const svg = q('.hero-plate--stack .hp-art > svg').getBoundingClientRect(), h1 = q('.stack-scene h1').getBoundingClientRect(), cs = q('#architecture .arch') ? getComputedStyle(q('#architecture .arch')) : null;
  return { a, z, y: scrollY, p: +getComputedStyle(s).getPropertyValue('--scene-p'), pos: getComputedStyle(st).position, stTop: st.getBoundingClientRect().top,
    lay: [...document.querySelectorAll('.hero-plate--stack .pl')].map(C), rows: [...document.querySelectorAll('#architecture .arch-layer')].map(C),
    svg: [svg.left, svg.top, svg.right, svg.bottom], copyB: q('.stack-scene .hero-copy').getBoundingClientRect().bottom, navB: q('.nav').getBoundingClientRect().bottom,
    h1: [h1.top, h1.bottom], archTop: side(q('#architecture'), 0), dark: q('.nav').classList.contains('nav--dark'),
    rowR: [...document.querySelectorAll('#architecture .arch-h')].map(e => side(e, 1)), boundR: side(q('#architecture .arch-bound'), 1), headL: side(q('#architecture .arch-head'), 3),
    frame: cs ? [cs.borderTopWidth, cs.borderTopColor, cs.borderTopLeftRadius] : ['?', '?', '?'], heroB: q('.stack-scene .page-hero').getBoundingClientRect().bottom, archT: q('#architecture').getBoundingClientRect().top,
    bw: parseFloat(getComputedStyle(s).getPropertyValue('--st-bw')), tone: parseFloat(getComputedStyle(s).getPropertyValue('--scene-tone-at')),
    edge: (() => { const e = q('#architecture'), r = e.getBoundingClientRect(), v = side(e, 0); return typeof v !== 'string' ? null : v.endsWith('%') ? r.top + parseFloat(v) / 100 * r.height : v.endsWith('px') ? r.top + parseFloat(v) : null; })(),
    rule: q('#architecture .ab-rule') ? C(q('#architecture .ab-rule')) : null, hair: +getComputedStyle(q('#architecture'), '::before').opacity,
    h2t: q('#architecture .ch-title') ? getComputedStyle(q('#architecture .ch-title')).translate : null,
    act: document.activeElement ? [document.activeElement.className || document.activeElement.tagName, !!document.activeElement.closest('.page-hero'), !!document.activeElement.closest('#architecture')] : null,
    W: innerWidth, H: innerHeight }; })()"""
STAGE_FADED = r"""((sel) => { const s = document.querySelector(sel); if (!s) return null;
  return [...s.querySelectorAll('*')].filter(el => !el.closest('svg') && [...el.childNodes].some(n => n.nodeType === 3 && n.data.trim()) && el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
    .filter(el => { let o = 1; for (let e = el; e && e !== s.parentElement; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o < .999; }).map(el => el.textContent.trim().slice(0, 30)); })"""
# the type sizes a reader sees on the screen: text in <main>, on screen under the bar, not hidden, faded out or clipped away;
# a scaled ancestor scales its size (platform hc26r sizes.py)
TYPE_SIZES = r"""(() => { const out = {}, vw = innerWidth, vh = innerHeight, bar = document.querySelector('.nav').getBoundingClientRect().bottom;
  const vis = el => { for (let e = el; e && e !== document.body; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false;
      const cp = cs.clipPath; if (cp && cp.startsWith('inset(')) { const r = e.getBoundingClientRect(), v = cp.slice(6, -1).split(/\s+/), t = parseFloat(v[0]), ri = parseFloat(v[1] === undefined ? v[0] : v[1]);
        if (/%/.test(v[0]) ? t >= 99.5 : t >= r.height - 1) return false; if (/%/.test(v[1] || '') && ri >= 99.5) return false; } } return true; };
  const w = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; const el = n.parentElement, r = el.getBoundingClientRect();
    if (el.closest('svg') || r.bottom < bar || r.top > vh || r.right < 0 || r.left > vw || r.width < 1 || !vis(el)) continue;
    let k = parseFloat(getComputedStyle(el).fontSize); for (let e = el; e; e = e.parentElement) { const sc = getComputedStyle(e).scale; if (sc && sc !== 'none') k *= parseFloat(sc); }
    k = Math.round(k * 2) / 2; (out[k] = out[k] || []).push(n.textContent.trim().slice(0, 18)); }
  return out; })()"""
pct = lambda v: (float(v[:-1]) if isinstance(v, str) and v.endswith("%") else None)
num = lambda v: (float(v.rstrip("%px")) if isinstance(v, str) and v.rstrip("%px").lstrip("-").replace(".", "", 1).isdigit() else None)


@check
async def stack_scene(b):
    """hc26r (integrate, standing in for tests; platform's request, RETHINK-hc26 PLAT-1, under EVOLVE's "Owner, 8 Nov"
    motion conditions): Platform's "take the stack apart" is one pinned scene in which the hero plate becomes the explorer.
    At 1440 x 900 with motion, once arch.js has measured (--st-s): the stage is stuck at the top for the whole travel and
    --scene-p runs 0 -> 1 with it; at .45 the eight plate layers stand on the eight explorer rows (centres within 1.5 px),
    04 -> 05 at least 120 px apart (the boundary between), the plate inside the screen and the H1 column gone above the
    bar; at .2 the H1 is on screen and §01 clipped whole; the bar is paper at .5 and ink at .7 (the tone sentinel at .667,
    where the ink reaches the bar's foot). hc27 (integrate, standing in for tests; platform's request, the director's HC27
    4.1): the ink's edge holds level with the boundary plane and the explorer is written behind it, bottom up. At the
    hold (--scene-p .45 + .2 x --st-bw + .02, --st-bw read from the scene) #architecture's clip edge is within 1 px of
    the boundary row's rule (.ab-rule's centre), rows 05-08 have arrived and rows 01-04 not yet, and the edge's hairline
    (#architecture::before) shows (opacity 1); at .75 every row, the boundary and the head have arrived and the H2 stands
    at rest (translate 0); at 1 the hairline is gone (opacity 0), every row, the boundary and the head have arrived and
    the explorer has no card frame (no border, no radius). (hc26r's "at .9 rows 01-04 arrived, 08 not yet" asserted the
    old top-down order, and its "the bar is ink at .65" the old sentinel .61.) No HTML text fades (opacity under 1) at
    .2, .5, the hold or .9, and at .3, the hold and .9 the screen shows at most four type sizes. "Take the stack apart",
    the address #architecture and Tab into the explorer's
    Pause land on the travel's end (--scene-p 1); Shift+Tab from there back into the hero returns to its start (0). Under
    reduced motion and at 999 px wide nothing pins: the hero and §01 are two blocks in order, --scene-p 1."""
    bad, notes = [], []
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    if not await until(pg, "!!document.querySelector('.stack-scene[style*=\"--st-s\"]')", 8000): bad.append("platform.html@1440: arch.js never measured the scene (no --st-s)")
    s0 = await pg.evaluate(STACK_PIN)
    if not s0: await ctx.close(); assert False, "stack_scene: no .stack-scene on platform.html"
    a, z = s0["a"], s0["z"]
    bw = s0.get("bw")
    if not isinstance(bw, (int, float)) or bw != bw or not (0.2 <= bw <= 0.8): bad.append(f"platform.html@1440: --st-bw {bw!r} (the boundary plane's height in the section, .2-.8)"); bw = 0.46
    hold = round(0.45 + 0.2 * bw + 0.02, 4)
    seen = []
    for f in (0, .2, .3, .45, .5, hold, .7, .75, .9, 1):
        await pg.evaluate(f"window.scrollTo({{top: {round(a + f * (z - a))}, behavior: 'instant'}})"); await pg.wait_for_timeout(450)
        r = await pg.evaluate(STACK_PIN); tag = f"platform.html@1440 at {f} of the travel{' (the hold)' if f == hold else ''}"
        seen.append(round(r["p"], 2))
        if r["pos"] != "sticky" or abs(r["stTop"]) > 1: bad.append(f"{tag}: the stage is {r['pos']} at {r['stTop']:.0f} px (stuck at the top)")
        if abs(r["p"] - f) > 0.02: bad.append(f"{tag}: --scene-p {r['p']:.3f}")
        if f == .45:
            off = [i + 1 for i, (l, w) in enumerate(zip(r["lay"], r["rows"])) if abs(l - w) > 1.5]
            if len(r["lay"]) != 8 or len(r["rows"]) != 8 or off: bad.append(f"{tag}: layers {[round(l) for l in r['lay']]} on rows {[round(w) for w in r['rows']]} (off: {off})")
            elif r["rows"][4] - r["rows"][3] < 119.5: bad.append(f"{tag}: 04 -> 05 only {r['rows'][4] - r['rows'][3]:.1f} px apart (120 at least: the boundary)")
            v = r["svg"]
            if v[0] < -0.5 or v[1] < -0.5 or v[2] > r["W"] + 0.5 or v[3] > r["H"] + 0.5: bad.append(f"{tag}: the plate {[round(x) for x in v]} leaves the screen")
            if r["copyB"] >= r["navB"]: bad.append(f"{tag}: the H1 column ends at {r['copyB']:.0f}, under the bar's foot {r['navB']:.0f}")
            if len(r["rows"]) == 8: notes.append(f".45: layers on rows within {max(abs(l - w) for l, w in zip(r['lay'], r['rows'])):.1f} px, 04 -> 05 {r['rows'][4] - r['rows'][3]:.0f} px")
        if f == .2:
            if not (r["h1"][1] > r["navB"] and r["h1"][0] < r["H"]): bad.append(f"{tag}: the H1 {[round(x) for x in r['h1']]} is off the screen")
            if (pct(r["archTop"]) or 0) < 99.5: bad.append(f"{tag}: §01 is not clipped whole (clip-path top {r['archTop']})")
        if f == .5 and r["dark"]: bad.append(f"{tag}: the bar is ink before the tone sentinel ({r['tone']})")
        if f == .7 and not r["dark"]: bad.append(f"{tag}: the bar is still paper after the tone sentinel ({r['tone']})")
        if f == hold:
            if r["edge"] is None or r["rule"] is None or abs(r["edge"] - r["rule"]) > 1: bad.append(f"{tag}: the ink's edge at {r['edge']}, the boundary's rule at {r['rule']} (level within 1 px)")
            if len(r["rowR"]) < 8 or any(num(x) is None or num(x) > 0.5 for x in r["rowR"][4:8]): bad.append(f"{tag}: rows 05-08 not all arrived ({r['rowR'][4:8]})")
            if any((num(x) if num(x) is not None else 100) <= 0.5 for x in r["rowR"][:4]): bad.append(f"{tag}: rows 01-04 arrived before the edge reached them ({r['rowR'][:4]})")
            if r["hair"] < 0.99: bad.append(f"{tag}: the edge's hairline at opacity {r['hair']:.2f} (1)")
            if r["edge"] is not None and r["rule"] is not None: notes.append(f"hold {hold}: edge {r['edge'] - r['rule']:+.2f} px from the rule")
        if f == .75:
            if any(num(x) is None or num(x) > 0.5 for x in r["rowR"] + [r["boundR"], r["headL"]]): bad.append(f"{tag}: not every row, the boundary and the head arrived ({r['rowR']}, {r['boundR']}, {r['headL']})")
            if r["h2t"] not in ("none", None) and any(abs(float(v.rstrip("px%") or 0)) > 0.5 for v in r["h2t"].split()): bad.append(f"{tag}: the H2 still rising (translate {r['h2t']})")
        if f == 1:
            if r["hair"] > 0.01: bad.append(f"{tag}: the edge's hairline still shows (opacity {r['hair']:.2f})")
            if any(num(x) is None or num(x) > 0.5 for x in r["rowR"] + [r["boundR"], r["headL"]]): bad.append(f"{tag}: not every row, the boundary and the head arrived ({r['rowR']}, {r['boundR']}, {r['headL']})")
            bw, bc, br = r["frame"]
            if bw == "?": bad.append(f"{tag}: no explorer (#architecture .arch)")
            elif not (float(bw.rstrip("px") or 0) == 0 or bc.replace(" ", "") in ("transparent", "rgba(0,0,0,0)")) or float(br.rstrip("px") or 0) > 0: bad.append(f"{tag}: the explorer is framed (border {bw} {bc}, radius {br})")
        if f in (.2, .5, hold, .9):
            fd = await pg.evaluate(STAGE_FADED, ".stack-scene > .scene-stage")
            if fd: bad.append(f"{tag}: text faded on scroll ({fd[:3]}): text arrives by translate or clip")
        if f in (.3, hold, .9):
            sz = await pg.evaluate(TYPE_SIZES)
            if len(sz) > 4: bad.append(f"{tag}: {len(sz)} type sizes on the screen ({ {k: v[:2] for k, v in sz.items()} })")
            notes.append(f"{f}: sizes {sorted(float(k) for k in sz)}")
    notes.insert(0, f"--scene-p {seen}")
    # the ways in: the hero's link, Tab into the explorer, Shift+Tab back
    await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(600)
    await pg.click(".stack-scene .page-hero a[href='#architecture']", timeout=15000); await pg.wait_for_timeout(1600)
    r = await pg.evaluate(STACK_PIN)
    if r["p"] < 0.99 or abs(r["y"] - r["z"]) > 2: bad.append(f"platform.html@1440: 'Take the stack apart' landed at {r['y']:.0f} (--scene-p {r['p']:.2f}); the end is {r['z']}")
    await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(600)
    await pg.focus(".stack-scene .page-hero a[href='#architecture']")
    for _ in range(14):
        await pg.keyboard.press("Tab"); await pg.wait_for_timeout(150)
        if await pg.evaluate("!!document.activeElement && document.activeElement.matches('#architecture .arch-motion')"): break
    await pg.wait_for_timeout(1000)
    r = await pg.evaluate(STACK_PIN)
    if not (r["act"] and r["act"][2]) or r["p"] < 0.99: bad.append(f"platform.html@1440: Tab into the explorer: focus on {r['act']}, --scene-p {r['p']:.2f} (the end)")
    await pg.keyboard.press("Shift+Tab"); await pg.wait_for_timeout(1200)
    r = await pg.evaluate(STACK_PIN)
    if not (r["act"] and r["act"][1]) or r["p"] > 0.01: bad.append(f"platform.html@1440: Shift+Tab back into the hero: focus on {r['act']}, --scene-p {r['p']:.2f} (the start)")
    await ctx.close()
    ctx, pg = await open_page(b, "platform.html#architecture", 1440, 900); await pg.wait_for_timeout(1800)
    r = await pg.evaluate(STACK_PIN)
    if r["p"] < 0.99 or abs(r["y"] - r["z"]) > 2: bad.append(f"platform.html#architecture@1440: the address landed at {r['y']:.0f} (--scene-p {r['p']:.2f}); the end is {r['z']}")
    await ctx.close()
    for tag, w, h, reduced in (("reduced motion", 1440, 900, True), ("999 px wide", 999, 900, False)):
        ctx, pg = await open_page(b, "platform.html", w, h, reduced=reduced)
        r = await pg.evaluate(STACK_PIN)
        await ctx.close()
        if r["pos"] == "sticky" or abs(r["p"] - 1) > 0.001: bad.append(f"platform.html@{w}x{h} {tag}: the stage pins ({r['pos']}) or --scene-p is {r['p']:.2f} (1)")
        if r["heroB"] > r["archT"] + 1: bad.append(f"platform.html@{w}x{h} {tag}: the hero ends at {r['heroB']:.0f}, under §01's top {r['archT']:.0f} (two blocks in order)")
    assert not bad, "stack_scene:\n  " + "\n  ".join(bad[:24])
    print(f"stack_scene: Platform's hero becomes the explorer over one pinned travel; links, the address and Tab land at its end, Shift+Tab at its start; nothing pins under reduced motion or narrow ({'; '.join(notes)})")


TRUST_SCENE = r"""(() => { const s = document.querySelector('#control .tr-cpl'); if (!s) return null; const r = s.getBoundingClientRect();
  const pl = s.querySelector('.tr-pl'), rj = s.querySelector('.tr-h .tr-rj'), M = e => { const t = e && getComputedStyle(e).transform; return !t || t === 'none' ? [1, 0, 0, 1, 0, 0] : (m => [m.a, m.b, m.c, m.d, m.e, m.f])(new DOMMatrixReadOnly(t)); };
  return { top: r.top + scrollY, h: r.height, p: +getComputedStyle(s).getPropertyValue('--scene-p'), anims: s.getAnimations({ subtree: true }).length,
    pl: pl ? { x: M(pl)[4], a: parseFloat(getComputedStyle(pl).getPropertyValue('--a')), shown: getComputedStyle(pl).display !== 'none' && !!pl.getClientRects().length } : null,
    rj: rj && rj.getClientRects().length ? M(rj) : null, dots: [...s.querySelectorAll('.tr-sd')].filter(e => e.getClientRects().length).map(e => +getComputedStyle(e, '::after').opacity) }; })()"""
TRAIL_SCENE = "(() => { " + CLIP_SIDE + r""" const s = document.querySelector('#verification .pf-trail'); if (!s) return null; const r = s.getBoundingClientRect();
  return { top: r.top + scrollY, h: r.height, p: +getComputedStyle(s).getPropertyValue('--scene-p'), anims: s.getAnimations({ subtree: true }).length,
    oks: [...s.querySelectorAll('.pf-ok')].map(e => side(e, 1)), first: side(s.querySelector('.pf-ok[style*="--k:0"]'), 1) }; })()"""


@check
async def plate_scenes(b):
    """hc26r (integrate, standing in for tests; proof's request, RETHINK-hc26 PROOF-1 and PROOF-2, under EVOLVE's "Owner, 8
    Nov" motion conditions): Trust §02's control plane (#control .tr-cpl) and Proof §01's paper trail (#verification
    .pf-trail) play as the reader scrolls them in (bare data-scene on the primitive; they were played once by
    OXA.actOnce). At 1440 x 900 and 390 x 844 (touch, DPR 2): before its range (--scene-p 0) Trust's proposal stands at the
    layer's start (.tr-pl translated to its --a) and the off-list block sits on the layer (a transform), or on a phone the
    first station's mark is lit and the others not; Proof's first confirmation is clipped away (right inset 100%). Past
    its range (--scene-p 1), the scene top at 15% of the screen, each drawing equals, pixel for pixel, the same scroll
    under reduced motion (no more than 0.05% of its pixels off by more than 8 levels), and all ten confirmations are
    whole. Under reduced motion neither drawing runs an animation and both read --scene-p 1."""
    import io
    from PIL import Image, ImageChops
    bad, notes = [], []
    for w, h, dpr, touch in ((1440, 900, 1, False), (390, 844, 2, True)):
        shots = {}
        for reduced in (False, True):
            for path, probe, sel in (("trust.html", TRUST_SCENE, "#control .tr-cpl"), ("evidence.html", TRAIL_SCENE, "#verification .pf-trail")):
                tag = f"{path}@{w}x{h}{' reduced' if reduced else ''}"
                ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch, reduced=reduced)
                g = await pg.evaluate(probe)
                if not g: bad.append(f"{tag}: no {sel}"); await ctx.close(); continue
                if not reduced:
                    await pg.evaluate(f"window.scrollTo({{top: {max(0, round(g['top'] - h - 40))}, behavior: 'instant'}})"); await pg.wait_for_timeout(400)
                    r = await pg.evaluate(probe)
                    if g["top"] - h - 40 <= 0: notes.append(f"{tag}: on the first screen, no 'before'")
                    elif r["p"] > 0.001: bad.append(f"{tag}: before its range --scene-p is {r['p']:.3f} (0)")
                    if g["top"] - h - 40 <= 0: pass
                    elif path == "trust.html":
                        if w >= 1000:
                            if not r["pl"] or abs(r["pl"]["x"] - r["pl"]["a"]) > 0.5: bad.append(f"{tag}: before its range the proposal is not at the layer's start ({r['pl']})")
                            if not r["rj"] or r["rj"] == [1, 0, 0, 1, 0, 0]: bad.append(f"{tag}: before its range the off-list block is not on the layer ({r['rj']})")
                        elif not r["dots"] or r["dots"][0] < 0.99 or any(x > 0.01 for x in r["dots"][1:]): bad.append(f"{tag}: before its range the stations' marks read {r['dots']} (the first lit, the others not)")
                    elif (pct(r["first"]) or 0) < 99.5: bad.append(f"{tag}: before its range the first confirmation is not clipped away ({r['first']})")
                await pg.evaluate(f"window.scrollTo({{top: {round(g['top'] - h * .15)}, behavior: 'instant'}})"); await pg.wait_for_timeout(1200)
                r = await pg.evaluate(probe)
                if abs(r["p"] - 1) > 0.001: bad.append(f"{tag}: past its range --scene-p is {r['p']:.3f} (1)")
                if reduced and r["anims"]: bad.append(f"{tag}: {r['anims']} animation(s) run under reduced motion")
                if path == "evidence.html" and (len(r["oks"]) != 10 or any(num(x) is None or num(x) > 0.5 for x in r["oks"])): bad.append(f"{tag}: past its range not all ten confirmations are whole ({r['oks']})")
                box = await pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return [Math.max(0, r.left), Math.max(0, r.top), Math.min(r.right, innerWidth) - Math.max(0, r.left), Math.min(r.bottom, innerHeight) - Math.max(0, r.top)]; }", sel)
                img = await pg.screenshot(clip={"x": box[0], "y": box[1], "width": box[2], "height": box[3]}, animations="disabled", timeout=60000)
                shots[(path, reduced)] = Image.open(io.BytesIO(img)).convert("RGB")
                await ctx.close()
        for path in ("trust.html", "evidence.html"):
            a, z = shots.get((path, False)), shots.get((path, True))
            if not a or not z: continue
            if a.size != z.size: bad.append(f"{path}@{w}x{h}: the scene's end is {a.size}, under reduced motion {z.size}"); continue
            d = ImageChops.difference(a, z).convert("L").point(lambda v: 255 if v > 8 else 0)
            off, total = d.histogram()[255], a.size[0] * a.size[1]
            if off > total * 0.0005: bad.append(f"{path}@{w}x{h}: the scene's end is not the still: {off} of {total} pixels off by more than 8 levels")
            notes.append(f"{path.split('.')[0]} {w}: {off} of {total} px off")
    assert not bad, "plate_scenes:\n  " + "\n  ".join(bad[:24])
    print(f"plate_scenes: Trust's control plane and Proof's paper trail start at their first frame and end on their stills ({'; '.join(notes)})")


LC_WATCH = r"""(() => { const R = window.__lc = { lit: [], run: null, done: null };
  new MutationObserver(ms => { for (const m of ms) { const t = m.target; if (!t.classList) continue;
    if (t.classList.contains('lc-gate') && t.classList.contains('is-lit') && !R.lit.includes(t.dataset.g)) R.lit.push(t.dataset.g);
    if (t.classList.contains('hero-plate--rings')) { if (t.classList.contains('is-run') && R.run === null) R.run = performance.now(); if (t.classList.contains('is-done') && R.done === null) R.done = performance.now(); } } })
    .observe(document, { subtree: true, attributes: true, attributeFilter: ['class'] }); })()"""
LC_STATE = r"""(() => { const f = document.querySelector('.hero-plate--rings'), n = f && f.querySelector('.lc-new'); if (!f || !n) return null;
  const nav = performance.getEntriesByType('navigation')[0];
  return { R: window.__lc || null, load: nav ? nav.loadEventEnd : 0, now: performance.now(), cls: f.className.baseVal !== undefined ? f.className.baseVal : f.className,
    op: +getComputedStyle(n).opacity, lit: f.querySelectorAll('.is-lit').length, anims: f.getAnimations({ subtree: true }).filter(a => a.playState === 'running').length }; })()"""


@check
async def lc_hero_once(b):
    """hc26r (integrate, standing in for tests; platform's optional request, RETHINK-hc26 PLAT-2): Lifecycles' hero ring
    runs its one proposal once, quietly (OXA.actOnce). At 1440 x 900 with motion it gains .is-run within 4 s of load, its
    six gates light 01 -> 06 in order, it ends .is-done with the green block (.lc-new) whole (opacity 1) and, 1.2 s later,
    no gate still lit. Under reduced motion and without JavaScript the block is there at once and nothing runs; a click on
    the drawing before the run (the visitor's own hand) keeps it from running, and the fallback shows the block within
    3.5 s."""
    bad, notes = [], []
    lim = lambda ms: int(ms * max(1.0, MODE["throttle"]))
    ctx, pg = await open_page(b, "lifecycles.html", 1440, 900, init=LC_WATCH)
    if not await until(pg, "!!(window.__lc && window.__lc.done !== null)", lim(8000), 50): bad.append(f"1440: never .is-done ({await pg.evaluate(LC_STATE)})")
    else:
        s = await pg.evaluate(LC_STATE); R = s["R"]
        if R["run"] is None: bad.append("1440: the ring never ran (.is-run)")
        elif R["run"] - s["load"] > lim(4000): bad.append(f"1440: the run began {R['run'] - s['load']:.0f} ms after load (4 s at most)")
        if R["lit"] != ["1", "2", "3", "4", "5", "6"]: bad.append(f"1440: the gates lit in the order {R['lit']} (01 -> 06)")
        await pg.wait_for_timeout(500)
        s = await pg.evaluate(LC_STATE)
        if s["op"] < 0.99: bad.append(f"1440: at .is-done the green block is at opacity {s['op']}")
        await pg.wait_for_timeout(1200)
        s2 = await pg.evaluate(LC_STATE)
        if s2["lit"]: bad.append(f"1440: {s2['lit']} gate(s) still lit 1.2 s after the run")
        if R["run"] is not None: notes.append(f"ran {R['run'] - s['load']:.0f} ms after load, gates {''.join(R['lit'])}, done {R['done'] - R['run']:.0f} ms later")
    await ctx.close()
    for tag, kw in (("reduced motion", {"reduced": True}), ("no JavaScript", {"js": False})):
        ctx, pg = await open_page(b, "lifecycles.html", 1440, 900, init=LC_WATCH if "js" not in kw else None, **kw)
        await pg.wait_for_timeout(300)
        op = await pg.evaluate("+getComputedStyle(document.querySelector('.hero-plate--rings .lc-new')).opacity")
        if op < 0.99: bad.append(f"1440 {tag}: the green block is at opacity {op} (shown at once)")
        if "js" not in kw:
            await pg.wait_for_timeout(3000)
            s = await pg.evaluate(LC_STATE)
            if s["R"]["run"] is not None or s["R"]["lit"] or s["anims"]: bad.append(f"1440 {tag}: something ran ({s['R']}, {s['anims']} animation(s))")
        await ctx.close()
    ctx, pg = await open_page(b, "lifecycles.html", 1440, 900, init=LC_WATCH, loaded=False)
    await until(pg, HOME_ENGINES, lim(15000), 20)
    box = await pg.evaluate("(() => { const r = document.querySelector('.hero-plate--rings').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    early = await pg.evaluate("window.__lc.run === null")
    await pg.mouse.click(box[0], box[1])
    t0 = time.monotonic()
    got = await until(pg, "!!(window.__lc && window.__lc.done !== null)", lim(4000), 50)
    s = await pg.evaluate(LC_STATE)
    if not early: notes.append("the click came after the run began (not judged)")
    else:
        if s["R"]["run"] is not None: bad.append(f"1440: a click before the run did not keep it from running ({s['R']})")
        if not got or s["R"]["done"] - s["load"] > lim(3500) + 500: bad.append(f"1440: after a click before the run the block came {(s['R']['done'] or 0) - s['load']:.0f} ms after load (the 3 s fallback)")
        notes.append(f"a click before the run: block by the fallback {(s['R']['done'] or 0) - s['load']:.0f} ms after load")
    await ctx.close()
    assert not bad, "lc_hero_once:\n  " + "\n  ".join(bad)
    print(f"lc_hero_once: Lifecycles' ring runs once, 01 -> 06, and rests with its block; still under reduced motion and without JS ({'; '.join(notes)})")


LAB_COPY = r"""(() => { const l = document.querySelector('[data-swarm-live]'), st = l && l.querySelector('[data-sw-stage]'), cv = l && l.querySelector('[data-sw-stage] canvas, canvas'); if (!st) return null;
  const r = st.getBoundingClientRect(); let lit = null;
  if (cv && cv.width) { try { const g = cv.getContext('2d'), W = cv.width, H = cv.height, x1 = Math.floor(W * .5), d = g.getImageData(0, 0, x1, H).data; lit = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i] * .2126 + d[i + 1] * .7152 + d[i + 2] * .0722 > 70) lit++; } catch (e) { lit = -1; } }
  // hc30r (SYS-3, PLAT-1): the lab's one hedge is its foot caption: inside the root (Home) or the caption the root names
  // (aria-describedby; Platform's #sw-cap). None in the lab's head.
  const named = (l.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean).map(id => document.getElementById(id)).filter(Boolean);
  const il = [l, ...named].flatMap(root => [...root.querySelectorAll('*')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.includes('Illustrative'))));
  const onScreen = e => { const b = e.getBoundingClientRect(); return !!b.width && b.bottom > 0 && b.top < innerHeight; };
  const whole = e => { for (let x = e; x; x = x.parentElement) { const cs = getComputedStyle(x); if (+cs.opacity < .99 || cs.visibility === 'hidden') return false; } return true; };
  const shown = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) / Math.max(1, Math.min(r.height, innerHeight));
  return { c: (r.top + r.bottom) / 2, top: r.top + scrollY, h: r.height, H: innerHeight, copy: l.dataset.swCopy === undefined ? null : l.dataset.swCopy, lit, shown,
           il: il.length, ilOn: il.some(onScreen), ilOk: il.some(e => onScreen(e) && whole(e)), ilHead: il.filter(e => e.closest('.sw-head')).length,
           ilText: il.length ? il[0].textContent.replace(/\s+/g, ' ').trim() : '' }; })()"""


async def scroll_frames(pg, y0, y1, steps=40):
    """scrollTo from y0 to y1 in steps (a touch window ignores a wheel at the mouse's spot); the frame intervals after the first two"""
    await pg.evaluate(f"window.scrollTo({{top: {y0}, behavior: 'instant'}})"); await pg.wait_for_timeout(300)
    await pg.evaluate(FRAMES_ON)
    for k in range(1, steps + 1):
        await pg.evaluate(f"window.scrollTo({{top: {round(y0 + (y1 - y0) * k / steps)}, behavior: 'instant'}})"); await pg.wait_for_timeout(50)
    await pg.wait_for_timeout(600)
    return (await pg.evaluate("window.__fr"))[2:]


@check
async def lab_copy(b):
    """hc26r (integrate, standing in for tests; home's request, RETHINK-hc26 HOME-4, under EVOLVE's "Owner, 8 Nov" motion
    conditions): Platform §02 plays its own act of the swarm lab, the master agent copied out across the field. With
    reduced motion, and after Pause motion or Emergency halt, data-sw-copy reads "1.00" at once. Home's lab never carries
    data-sw-copy. hc27 (integrate, standing in for home and tests; the director's HC27 2: Platform's lab rests in its own
    pose): at 1440 x 900 with the act done Platform's lab names no gate and no boundary (the gate list and the "Boundary"
    tag at opacity 0) until "Follow a proposal" is pressed (both back at 1); Home's lab names them at rest. The resting
    drawing itself (the master's track, its origin, the fan) is judged on renders, not here.
    hc30r (HOME-2, PLAT-1, SYS-3; integrate, standing in for tests, on platform's and home's requests; TESTS.md section
    53). Three things the check read are staged another way, and each keeps its principle:
    - The act is on a clock, once, not tied to the scroll (RETHINK-hc30 rule 1: every frame of it is a whole picture; it
      was data-sw-copy = p at four scroll positions). On platform.html at 1440 x 900 and 390 x 844 (touch): with the lab
      started and a fifth of its stage on screen the act has not begun (data-sw-copy "0.00", and it stays there); brought
      to the middle of the screen it runs 0 -> 1 without ever falling, reads "1.00" within 1.5 s of arriving (x the
      throttle) and still reads "1.00" after the page has left and come back.
    - The field is never empty (it was: next to nothing lit at .1, four times as much at 1; the wide lab only, as before):
      waiting, before its act, the field's half of the canvas already holds at least 60% of the lit pixels it holds at
      rest, and at rest it holds no fewer than nine tenths of that.
    - The hedge is the lab's foot caption, not a word in its head (it was: "Illustrative" inside the lab's root, visible
      at every scroll position): the lab names its caption (aria-describedby), the caption opens "Illustrative", no hedge
      stands in the lab's head, and whenever the caption is on screen it is whole (never faded or hidden); it is read
      on screen at rest at both widths. check_static `hedges` holds the words.
    Through the act, no frame over 33 ms (x the throttle; judged with --gpu only, as before)."""
    bad, notes = [], []
    lim = 33.4 * max(1.0, MODE["throttle"])
    copy = "(() => { const l = document.querySelector('[data-swarm-live]'); return l.dataset.swCopy === undefined ? null : l.dataset.swCopy; })()"
    WATCH = "(() => { const l = document.querySelector('[data-swarm-live]'), R = window.__cp = []; const f = () => { R.push(l.dataset.swCopy === undefined ? -1 : +l.dataset.swCopy); if (R.length < 2400) requestAnimationFrame(f); }; requestAnimationFrame(f); })()"
    async def wait_at(pg, h):
        """come down to the lab from above and stop where a fifth of its stage shows: it starts, its act does not"""
        g = await pg.evaluate(LAB_COPY)
        if not g: return None, None
        y = 0
        for f in (1.6, 1.2):
            await pg.evaluate(f"window.scrollTo({{top: {round(g['top'] + g['h'] / 2 - f * h)}, behavior: 'instant'}})"); await pg.wait_for_timeout(500)
        for _ in range(3):  # three times: the page above the lab may still settle by a few pixels
            g = await pg.evaluate(LAB_COPY); y = round(g["top"] - h + 0.2 * min(g["h"], h))
            await pg.evaluate(f"window.scrollTo({{top: {y}, behavior: 'instant'}})"); await pg.wait_for_timeout(450)
        await until(pg, "!!document.querySelector('[data-swarm-live].sw-on')", 10000)
        await pg.wait_for_timeout(400)
        return await pg.evaluate(LAB_COPY), y
    for w, h, touch in ((1440, 900, False), (390, 844, True)):
        tag = f"platform.html@{w}x{h}"
        ctx, pg = await open_page(b, "platform.html", w, h, dpr=2 if touch else 1, touch=touch)
        r0, y_wait = await wait_at(pg, h)
        if not r0: bad.append(f"{tag}: no swarm lab"); await ctx.close(); continue
        if not await pg.evaluate("!!document.querySelector('[data-swarm-live].sw-on')"): bad.append(f"{tag}: the lab did not start with a fifth of its stage on screen")
        # waiting: the act has not begun, and does not begin on its own
        held = [await pg.evaluate(copy)]
        for _ in range(6): await pg.wait_for_timeout(100); held.append(await pg.evaluate(copy))
        if any(v != "0.00" for v in held): bad.append(f"{tag} waiting ({r0['shown']:.2f} of the stage on screen): data-sw-copy reads {sorted(set(map(str, held)))} (0.00 until the stage stands on screen)")
        lit0 = r0["lit"]
        # the act: the stage's centre brought to the middle of the screen
        await pg.evaluate(WATCH)
        y_mid = round(r0["top"] + r0["h"] / 2 - h / 2)
        fr = await scroll_frames(pg, y_wait, y_mid, steps=16)
        done = await until(pg, copy + " === '1.00'", int(900 * max(1.0, MODE["throttle"])), 50)
        seq = [v for v in await pg.evaluate("window.__cp") if v >= 0]
        if not done: bad.append(f"{tag}: data-sw-copy reads {await pg.evaluate(copy)!r} 1.5 s after the stage reached the middle of the screen (1.00)")
        falls = [(round(seq[i - 1], 2), round(seq[i], 2)) for i in range(1, len(seq)) if seq[i] < seq[i - 1] - 0.001]
        if falls: bad.append(f"{tag}: data-sw-copy falls back during the act ({falls[:4]})")
        if not seq or seq[0] > 0.001 or len(set(seq)) < 4: bad.append(f"{tag}: the act was not seen running from 0 ({len(set(seq))} values, first {seq[:1]})")
        over = [round(x, 1) for x in fr if x > lim]
        if MODE["gl"] == "gpu":
            if long_frames(fr, lim): bad.append(f"{tag}: {len(over)} of {len(fr)} frames over {lim:.0f} ms through the act ({over[:6]})")
        else:
            # as in scenes: the 33 ms rule is a real-GPU rule (--gpu). Under SwiftShader the CPU draws the lab's WebGL field
            # (CI run 42782516694: frames of 183 to 483 ms through the act; 283 ms here on 10 Nov), so only a hang fails.
            hang = [round(x) for x in fr if x > 5000 * max(1.0, MODE["throttle"])]
            if hang: bad.append(f"{tag}: a frame of {hang[0]} ms through the act under software GL (a hang; 5 s at most)")
        notes.append(f"{w}: 0 -> 1 in {len(set(seq))} steps, frames <= {max(fr) if fr else 0:.1f} ms" + ("" if MODE["gl"] == "gpu" else f" under software GL, {len(over)} of {len(fr)} over {lim:.0f} ms (judged with --gpu only)"))
        # at rest: the field, the hedge
        await pg.wait_for_timeout(600)
        r1 = await pg.evaluate(LAB_COPY)
        if not touch:  # on a phone the Council's ring fills the field's half: the census is the wide lab's
            if lit0 is None or r1["lit"] is None or lit0 < 0 or r1["lit"] < 0: bad.append(f"{tag}: the canvas could not be read ({lit0}, {r1['lit']})")
            else:
                if lit0 < max(200, 0.6 * r1["lit"]): bad.append(f"{tag}: waiting, the field's half of the canvas holds {lit0} lit pixels against {r1['lit']} at rest (never an empty field: 60% at least)")
                if r1["lit"] < 0.9 * lit0: bad.append(f"{tag}: at rest the field's half holds {r1['lit']} lit pixels, fewer than the {lit0} it opened on")
                notes.append(f"lit {lit0} waiting, {r1['lit']} at rest")
        if not r1["il"] or not r1["ilText"].startswith("Illustrative"): bad.append(f"{tag}: the lab names no caption that opens 'Illustrative' ({r1['il']} found: {r1['ilText'][:40]!r})")
        if r1["ilHead"]: bad.append(f"{tag}: a hedge stands in the lab's head ({r1['ilHead']}; one hedge, in the foot)")
        seen_cap = 0
        for where in ("the stage in the middle", "the caption at the screen's foot"):
            if where.startswith("the caption"):
                await pg.evaluate("(() => { const l = document.querySelector('[data-swarm-live]'), c = document.getElementById((l.getAttribute('aria-describedby') || '').split(/\\s+/)[0]) || l.querySelector('.figure-cap'); if (c) c.scrollIntoView({block: 'end', behavior: 'instant'}); })()")
                await pg.wait_for_timeout(900)
            q = await pg.evaluate(LAB_COPY)
            if q["ilOn"]:
                seen_cap += 1
                if not q["ilOk"]: bad.append(f"{tag} with {where}: the lab's 'Illustrative' is on screen but not whole (faded or hidden)")
        if not seen_cap: bad.append(f"{tag}: the lab's caption was never on screen (nothing was tested)")
        # it never falls back: away and back
        await pg.evaluate("window.scrollTo({top: 0, behavior: 'instant'})"); await pg.wait_for_timeout(500)
        await pg.evaluate(f"window.scrollTo({{top: {y_mid}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
        v = await pg.evaluate(copy)
        if v != "1.00": bad.append(f"{tag}: back at the lab after leaving, data-sw-copy reads {v!r} (1.00: the act runs once)")
        if not touch:
            for ctl in ("[data-sw-motion]", "[data-sw-halt]"):
                await pg.close(); pg = await ctx.new_page(); await pg.goto(f"{BASE}/platform.html", wait_until="load"); await until(pg, HOME_ENGINES, 15000)
                rw, _ = await wait_at(pg, h)
                before = await pg.evaluate(copy)
                if before != "0.00": bad.append(f"{tag}: before {ctl}, waiting, data-sw-copy reads {before!r} (0.00)")
                if await pg.evaluate(f"!!document.querySelector('{ctl}') && !document.querySelector('{ctl}').hidden"):
                    await pg.evaluate(f"document.querySelector('{ctl}').click()"); await pg.wait_for_timeout(150)
                    after = await pg.evaluate(copy)
                    if after != "1.00": bad.append(f"{tag}: after {ctl} data-sw-copy reads {after!r} (was {before!r}; 1.00 at once)")
                else: bad.append(f"{tag}: no {ctl} to press")
        await ctx.close()
    ctx, pg = await open_page(b, "platform.html", 1440, 900, reduced=True)
    await pg.evaluate("document.querySelector('[data-sw-stage]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1200)
    v = await pg.evaluate("document.querySelector('[data-swarm-live]').dataset.swCopy")
    if v != "1.00": bad.append(f"platform.html@1440 reduced motion: data-sw-copy {v!r} (1.00)")
    await ctx.close()
    ctx, pg = await open_page(b, "index.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-sw-stage]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1500)
    v = await pg.evaluate("document.querySelector('[data-swarm-live]').dataset.swCopy")
    if v is not None: bad.append(f"index.html@1440: Home's lab carries data-sw-copy {v!r} (Platform's act alone)")
    tags = "(() => { const r = document.querySelector('[data-swarm-live]'), o = s => { const e = r && r.querySelector(s); return e ? +getComputedStyle(e).opacity : null; }; return [o('[data-sw-gates]'), o('[data-sw-bound]')]; })()"
    t_home = await pg.evaluate(tags)
    if t_home != [1, 1]: bad.append(f"index.html@1440: Home's lab hides its gate list or Boundary tag at rest (opacity {t_home})")
    await ctx.close()
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    g = await pg.evaluate(LAB_COPY); ctr = g["top"] + g["h"] / 2
    for f in (1.6, 1.2, 1.0):
        await pg.evaluate(f"window.scrollTo({{top: {round(ctr - f * 900)}, behavior: 'instant'}})"); await pg.wait_for_timeout(500)
    await until(pg, "!!document.querySelector('[data-swarm-live].sw-on')", 10000)
    for _ in range(2):
        await pg.evaluate(f"window.scrollTo({{top: {round(ctr - 0.4 * 900)}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
        q = await pg.evaluate(LAB_COPY); ctr = q["top"] + q["h"] / 2
    await until(pg, copy + " === '1.00'", int(3000 * max(1.0, MODE["throttle"])), 100)
    await pg.wait_for_timeout(800)
    rest = await pg.evaluate(tags); cp = await pg.evaluate("document.querySelector('[data-swarm-live]').dataset.swCopy")
    if cp != "1.00" or rest != [0, 0]: bad.append(f"platform.html@1440 at rest (data-sw-copy {cp!r}): the gate list / Boundary tag at opacity {rest} (0 until a proposal is followed)")
    await pg.evaluate("document.querySelector('[data-sw-follow]').click()"); await pg.wait_for_timeout(900)
    fol = await pg.evaluate(tags)
    # The tags fade in over the follow's first frames. Where frames are slow (CI's software GL, run 42785737245) 900 ms
    # is mid-fade (0.81), so give the fade time to end before judging where it ended.
    waited = 900
    while fol != [1, 1] and waited < 6000 * max(1.0, MODE["throttle"]):
        await pg.wait_for_timeout(150); waited += 150
        fol = await pg.evaluate(tags)
    if fol != [1, 1]: bad.append(f"platform.html@1440 following a proposal: the gate list / Boundary tag at opacity {fol} (1)")
    notes.append(f"Platform at rest names {rest}, following {fol}; Home {t_home}")
    await ctx.close()
    assert not bad, "lab_copy:\n  " + "\n  ".join(bad[:24])
    print(f"lab_copy: Platform §02's act runs once on its clock, 0 -> 1, from a field that is never empty, under one hedge in the lab's foot; at once 1 under reduced motion, Pause and halt; never on Home ({'; '.join(notes)})")


# hc29 (integrate, standing in for tests; home's request): the chart is drawn in WebGL, so the band it fills counts as
# content: from the hedge label's top to the key label's bottom (the shown labels' span if either is missing); `runs`
# is the longest empty run of ink between the bar's foot and the screen's foot (read at S4's rest, before the paper)
HANDOFF_INK = r"""(() => { const H = innerHeight, nav = document.querySelector('.nav'), navB = nav ? nav.getBoundingClientRect().bottom : 0;
  const paper = document.querySelector('.story-paper'), pr = paper.getBoundingClientRect(), paperTop = pr.height > .5 && getComputedStyle(paper).visibility !== 'hidden' ? pr.top : H;
  const anc = el => { for (let e = el; e; e = e.parentElement) { const cs = getComputedStyle(e); if (+cs.opacity < .05 || cs.visibility === 'hidden') return false; } return true; };
  const boxes = [];
  document.querySelectorAll('.story .beat h2, .story .beat p, .story .beat a, .story-labels .story-lab, .story-ink > *').forEach(el => {
    const r = el.getBoundingClientRect(); if (r.height < 1 || !anc(el)) return; boxes.push([r.top, r.bottom]); });
  const labs = [...document.querySelectorAll('.story-labels .story-lab')].filter(l => l.getBoundingClientRect().height >= 1 && anc(l));
  const hd = labs.find(l => l.classList.contains('hedge')), ky = labs.find(l => l.classList.contains('key'));
  if (hd && ky) boxes.push([hd.getBoundingClientRect().top, ky.getBoundingClientRect().bottom]);
  else if (labs.length) boxes.push([Math.min(...labs.map(l => l.getBoundingClientRect().top)), Math.max(...labs.map(l => l.getBoundingClientRect().bottom))]);
  let low = navB;
  boxes.forEach(([t, bt]) => { if (bt <= navB || t >= paperTop) return; low = Math.max(low, Math.min(bt, paperTop)); });
  let runs = 0, at = navB; boxes.filter(([t, bt]) => bt > navB && t < H).sort((a, c) => a[0] - c[0]).forEach(([t, bt]) => { runs = Math.max(runs, t - at); at = Math.max(at, bt); });
  runs = Math.max(runs, H - at);
  const b4 = document.querySelector('.beat-4'), st = document.querySelector('.story'); let op = 1; for (let e = b4; e && e !== st; e = e.parentElement) op *= +getComputedStyle(e).opacity;
  const br = b4 ? b4.getBoundingClientRect() : null;
  return { y: scrollY, paperTop, up: st.classList.contains('is-paper-up'), gap: paperTop < H ? paperTop - low : null, runs, b4: br ? { shown: br.bottom > navB && br.top < paperTop, op } : null }; })()"""


@check
async def overture_handoff(b):
    """hc26r (integrate, standing in for tests; home's request, RETHINK-hc26 HOME-3): the overture hands over to the paper
    with no empty ink. At 390 x 844 (touch) and 768 x 1024, walking down in tenth-of-a-screen steps from the exit's start
    (STORY_Y(4)) to one screen past the release, each step settled: wherever the paper shows, the band between the bar's
    foot and the paper's edge never holds more than 48 px of ink without content (beat text, the day labels, the ink
    records), through the paper's rise as well as once it has taken the record row (.story.is-paper-up); and S4 leaves by
    being clipped at the bar, never faded: while any of it shows above the paper its opacity is 1. hc27 (integrate,
    standing in for tests; home's request): the rise is judged too, now that home closed it (story.js EXIT.tall: the paper
    rises under "The full proof file" as the exit starts and follows the lifting copy; hc26r's walk judged only the
    paper-up steps and reported the rise, 330 px of empty ink at 2.2 screens on a 390 phone then). The probe is
    HANDOFF_INK (it shadowed nav_handoff's HANDOFF until hc27).
    hc29 (integrate, standing in for tests; home's request, the HC29 director's item 1): S4 now holds whole while §01
    (the paper) rises over it at scroll speed, so the paper opens no band of its own; what lies between the content and
    the rising edge is S4's own layout (on a 390 phone the bar's foot to the hedge, the key line to the headline). The
    chart (WebGL) counts as content, from the hedge label's top to the key label's bottom; and the empty run above the
    paper may be as long as S4's longest empty run at rest (read before the paper shows) but no longer, nor longer than
    48 px where S4 has no such run: content that faded or lifted early would open a longer one. S4's "clipped, never
    faded" clause is unchanged."""
    bad, notes = [], []
    for w, h, touch in ((390, 844, True), (768, 1024, False)):
        tag = f"index.html@{w}x{h}"
        ctx, pg = await open_page(b, "index.html", w, h, dpr=2 if touch else 1, touch=touch)
        await pg.wait_for_timeout(1500)
        y0 = await pg.evaluate(STORY_Y, 4.0)
        end = await pg.evaluate("Math.round(document.querySelector('.story').offsetTop + document.querySelector('.story').offsetHeight)")
        cur, worst, n, rise, allow = 0, 0.0, 0, 0.0, None
        y = y0
        while y <= end + 1:
            while cur < y:
                cur = min(y, cur + h // 4); await pg.evaluate(f"window.scrollTo(0, {cur})"); await pg.wait_for_timeout(100)
            await pg.wait_for_timeout(900)
            r = await pg.evaluate(HANDOFF_INK); n += 1
            if allow is None: allow = max(48.0, r["runs"] + 2)  # S4 at rest, the paper not up yet
            if r["gap"] is not None:
                if r["up"]: worst = max(worst, r["gap"])
                else: rise = max(rise, r["gap"])
                if r["gap"] > allow: bad.append(f"{tag} at {r['y']:.0f} ({(r['y'] - y0) / h:.1f} screens into the exit{'' if r['up'] else ', the paper rising'}): {r['gap']:.1f} px of ink without content over the paper (S4's own longest run at rest {allow - 2:.1f})")
            if r["b4"] and r["b4"]["shown"] and r["b4"]["op"] < 0.99: bad.append(f"{tag} at {r['y']:.0f}: S4 shows at opacity {r['b4']['op']:.2f} (clipped, never faded)")
            y = round(y + h * 0.1)
        notes.append(f"{w}: {n} steps, ink without content <= {worst:.1f} px with the paper up, <= {rise:.1f} px while it rises (S4's own run at rest {allow - 2:.1f})")
        await ctx.close()
    assert not bad, "overture_handoff:\n  " + "\n  ".join(bad[:24])
    print(f"overture_handoff: the paper takes over with no empty ink band and S4 clipped, never faded ({'; '.join(notes)})")


FOOT_LINKS = r"""(() => { const top = document.querySelector('.footer .top'); if (!top) return null; const groups = [...top.children].slice(1);
  return groups.map(g => ({ head: (g.querySelector('h2') || {}).textContent, links: [...g.querySelectorAll('li a')].map(a => { const r = a.getBoundingClientRect(); return { t: a.textContent.trim(), x: r.left, y: r.top, b: r.bottom }; }) })); })()"""


@check
async def footer_phone(b):
    """hc25 (integrate, standing in for tests; the director's HC25 8, adapted by system): on phones the footer's links fill
    both columns, no empty column. With touch at 390 x 844, 360 x 780 and 320 x 640, on Home and the blog index: Product and
    Company stand side by side; Access spans both columns under them, "Request access" and "For managers" down the first
    column (Product's left edge) and "Bring a lifecycle" at the top of the second (Company's left edge, level with "Request
    access"). At 768 x 1024 the three groups stand in their own columns, each group's links stacked (unchanged). Links,
    order, row height and disclosures: check_static footer, verify_v9 phone, footer_end and disclosures."""
    bad, notes = [], []
    for path in ("index.html", "blog/index.html"):
        for w, h, dpr, touch in ((390, 844, 3, True), (360, 780, 3, True), (320, 640, 2, True), (768, 1024, 2, False)):
            tag = f"{path}@{w}x{h}"
            ctx, pg = await open_page(b, path, w, h, dpr=dpr, touch=touch)
            await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(600)
            g = await pg.evaluate(FOOT_LINKS)
            await ctx.close()
            if not g or len(g) != 3 or [x["head"] for x in g] != ["Product", "Company", "Access"]: bad.append(f"{tag}: the footer's groups are not Product, Company, Access ({g and [x['head'] for x in g]})"); continue
            prod, comp, acc = (x["links"] for x in g)
            if len(acc) != 3: bad.append(f"{tag}: Access has {len(acc)} links"); continue
            if w <= 600:
                if not abs(prod[0]["y"] - comp[0]["y"]) <= 1 or comp[0]["x"] <= prod[0]["x"] + 1: bad.append(f"{tag}: Product and Company are not side by side")
                if abs(acc[0]["x"] - prod[0]["x"]) > 1 or abs(acc[1]["x"] - prod[0]["x"]) > 1: bad.append(f"{tag}: Request access / For managers are not in the first column ({acc[0]['x']:.0f}, {acc[1]['x']:.0f} vs {prod[0]['x']:.0f})")
                if acc[1]["y"] < acc[0]["b"] - 1: bad.append(f"{tag}: For managers is not under Request access")
                if abs(acc[2]["x"] - comp[0]["x"]) > 1 or abs(acc[2]["y"] - acc[0]["y"]) > 1: bad.append(f"{tag}: Bring a lifecycle is not at the top of the second column ({acc[2]['x']:.0f},{acc[2]['y']:.0f} vs {comp[0]['x']:.0f},{acc[0]['y']:.0f})")
                if acc[0]["y"] < max(l["b"] for l in prod + comp) - 1: bad.append(f"{tag}: Access does not stand under Product and Company")
                if path == "index.html" and w == 390: notes.append(f"390: Access at x {acc[0]['x']:.0f} / {acc[2]['x']:.0f}")
            else:
                if len({round(l["x"]) for l in acc}) != 1 or any(z["y"] < a["b"] - 1 for a, z in zip(acc, acc[1:])): bad.append(f"{tag}: Access's links are not one stacked column")
                if acc[0]["x"] <= comp[0]["x"] + 1 and abs(acc[0]["y"] - comp[0]["y"]) > 1: bad.append(f"{tag}: Access is not its own column")
    assert not bad, "footer_phone:\n  " + "\n  ".join(bad[:24])
    print(f"footer_phone: on phones Access spans both columns under Product and Company, no empty column; tablets unchanged ({'; '.join(notes)})")


CH_LINKS = r"""(() => { const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
  // a line of text's baseline: the foot of its first glyph's box less the face's descent at that size
  const base = (e) => { const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let t; while ((t = w.nextNode())) if (t.textContent.trim()) break; if (!t) return null;
    const rg = document.createRange(), i = t.textContent.search(/\S/); rg.setStart(t, i); rg.setEnd(t, i + 1); const r = rg.getBoundingClientRect(), cs = getComputedStyle(t.parentElement);
    const g = document.createElement('canvas').getContext('2d'); g.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`; const m = g.measureText(t.textContent[i]);
    return r.bottom - (m.fontBoundingBoxDescent || 0); };
  return [...document.querySelectorAll('#lc01 .ch-head, #governance .ch-head, #research .ch-head')].map(h => { const t = h.querySelector('.ch-title'), a = h.querySelector('.ch-link'); if (!t || !a) return null;
    const u = a.previousElementSibling && a.previousElementSibling.matches('.ch-title, .ch-line') ? a.previousElementSibling : t;
    const tr = t.getBoundingClientRect(), ur = u.getBoundingClientRect(), ar = a.getBoundingClientRect();
    // hc30r: the head laid over the stage (Home §02's one-screen form): the link stands on its line's row
    const over = getComputedStyle(h).position === 'absolute';
    return { id: h.closest('section').id, under: u.classList.contains('ch-line') ? 'line' : 'head', gap: ar.top - ur.bottom, dx: ar.left - tr.left, rem,
             over, row: over ? { db: base(a) - base(u), dt: base(a) - base(t), dx: ar.left - ur.right } : null }; }); })()"""
DPL_ART = r"""(() => { const cols = [...document.querySelectorAll('#mcp .dpl-col')]; return cols.map(c => { const s = c.querySelector('.dpl-plate svg'), g = s && s.querySelector(':scope > g'), h = c.querySelector('h3');
  if (!g) return null; const sb = s.getBoundingClientRect(), k = sb.height / 112, gb = g.getBBox(), m = g.transform.baseVal.consolidate(), ty = m ? m.matrix.f : 0;
  return { base: (gb.y + gb.height + ty), h3: h ? h.getBoundingClientRect().top : null, k }; }); })()"""


@check
async def section_links(b):
    """hc25 (integrate, standing in for tests; the director's HC25 6 and 7, done by home and platform): a chapter's action
    sits under its head and a row of drawings stands on one line. Home §02, §04 and §05 at 3840 x 2160, 1440 x 900, 1024 x
    768, 768 x 1024 and with touch at 390 x 844 and 320 x 640: the link ("Lifecycle 01 in depth", "The governance model",
    "All ten notes") starts at its head's left edge (1 px) and 1.5rem (2 px) under what it follows (the title, or §02's
    line "Tighten the Council and it rejects more.": hc27, home's request, the director's HC27 7 moved §02's link from
    under the lab to under its lede), never on the head's baseline. Platform §04 at 3840 x 2160, 1440 x 900
    and 1024 x 768 (three columns): the three drawings' art ends on one baseline (0.5 of the drawing's 112 units) and the
    three titles start on one line (1 px). Before hc25 §05's link sat on its head's baseline at the row's right (x 953 at
    1440) and §04's three drawings ended at three different heights.
    hc30r (HOME-2; integrate, standing in for tests, on home's request; TESTS.md section 53): where Home's lab is one
    screen (home.css: from 1200 px wide in a window at least 800 px and 50rem tall, with scripting; here 3840 x 2160 and
    1440 x 900) the head lies over the stage and must stay short, so §02's link stands on its line's row: on the line's
    baseline (2 px), 1.75rem (2 px) right of the line's end, and still never on the title's baseline (it is a line's
    height or more under it). The form is read from the page (the head laid over the stage: position absolute), and must
    be the one-screen form at those two windows and the stacked form at the other four; in the stacked form, and for §04
    and §05 everywhere, the check holds as written."""
    bad, notes = [], []
    for w, h, dpr, touch in ((3840, 2160, 1, False), (1440, 900, 1, False), (1024, 768, 1, False), (768, 1024, 2, False), (390, 844, 3, True), (320, 640, 2, True)):
        tag = f"index.html@{w}x{h}"
        ctx, pg = await open_page(b, "index.html", w, h, dpr=dpr, touch=touch, reduced=True)
        await pg.evaluate("document.querySelector('#research').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(CH_LINKS)
        await ctx.close()
        if not r or len(r) != 3 or not all(r): bad.append(f"{tag}: §02 / §04 / §05 without a head and its link ({r})"); continue
        if r[0]["under"] != "line": bad.append(f"{tag} #lc01: the link follows the {r[0]['under']}, not the line under the title")
        if r[0]["over"] != (w >= 1200 and h >= 800): bad.append(f"{tag} #lc01: the head {'lies over the stage' if r[0]['over'] else 'stands above the stage'} (the one-screen form is for 1200 px by 800 px and up)")
        if r[1]["over"] or r[2]["over"]: bad.append(f"{tag}: §04's or §05's head is laid over its content")
        for x in r:
            if x["over"]:
                row = x["row"]
                if abs(row["db"]) > 2: bad.append(f"{tag} #{x['id']}: the link's baseline is {row['db']:.1f} px off its line's (one row)")
                if abs(row["dx"] - 1.75 * x["rem"]) > 2: bad.append(f"{tag} #{x['id']}: the link starts {row['dx']:.1f} px right of its line's end (1.75rem = {1.75 * x['rem']:.0f})")
                if row["dt"] < x["rem"]: bad.append(f"{tag} #{x['id']}: the link's baseline is {row['dt']:.1f} px under the title's (never on the head's baseline)")
                continue
            if abs(x["dx"]) > 1: bad.append(f"{tag} #{x['id']}: the link starts {x['dx']:.1f} px from its head's left edge")
            if abs(x["gap"] - 1.5 * x["rem"]) > 2: bad.append(f"{tag} #{x['id']}: the link is {x['gap']:.1f} px under its {x['under']} (1.5rem = {1.5 * x['rem']:.0f})")
        if w == 1440: notes.append("Home 1440: " + ", ".join(("#%s on its line's row, %.0f px right of it" % (x["id"], x["row"]["dx"])) if x["over"] else ("#%s %.0f px under its %s" % (x["id"], x["gap"], x["under"])) for x in r))
        if w == 1024: notes.append("Home 1024: " + ", ".join("#%s %.0f px under its %s" % (x["id"], x["gap"], x["under"]) for x in r if not x["over"]))
    for w, h in ((3840, 2160), (1440, 900), (1024, 768)):
        tag = f"platform.html@{w}x{h}"
        ctx, pg = await open_page(b, "platform.html", w, h, reduced=True)
        await pg.evaluate("document.querySelector('#mcp').scrollIntoView({block: 'start', behavior: 'instant'})"); await pg.wait_for_timeout(500)
        r = await pg.evaluate(DPL_ART)
        await ctx.close()
        if not r or len(r) != 3 or not all(r): bad.append(f"{tag}: §04 without three drawings ({r})"); continue
        bases = [x["base"] for x in r]
        if max(bases) - min(bases) > 0.5: bad.append(f"{tag}: the three drawings end at {[round(v, 1) for v in bases]} of 112 (one baseline)")
        tops = [x["h3"] for x in r]
        if None in tops or max(tops) - min(tops) > 1: bad.append(f"{tag}: the three titles start at {tops}")
        if w == 1440: notes.append(f"Platform §04 baseline {[round(v, 1) for v in bases]}")
    assert not bad, "section_links:\n  " + "\n  ".join(bad[:24])
    print(f"section_links: Home's chapter links under their heads (§02's under its line, or on its line's row where the lab is one screen); Platform §04's drawings on one baseline ({'; '.join(notes)})")


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
