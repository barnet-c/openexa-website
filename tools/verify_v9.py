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
    assert st["days"] == rc["total"] and st["prem"] == rc["premium"] and st["ink"] == rc["total"] and not wrong, (st, "record", rc, "differ", wrong)
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
    # the last beat has faded before the stage's exit could carry it under the bar
    await pg.evaluate("(() => { const s = document.querySelector('.story'); window.scrollTo({top: s.offsetTop + s.offsetHeight - innerHeight * 0.5, behavior: 'instant'}); })()")
    op = await until(pg, "(() => { const o = +getComputedStyle(document.querySelector('.beat-4')).opacity; return o < 0.05 ? String(o) : ''; })()", 4000)
    assert op, ("beat 4 still visible past the stage's end", await pg.evaluate("getComputedStyle(document.querySelector('.beat-4')).opacity"))
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
    # hc13r (home, HOME-2): the lab follows one proposal by itself, quietly (its live region stays empty), then rests
    assert await until(pg, "document.querySelector('[data-sw-follow]').getAttribute('aria-pressed') === 'true'", 4000), "the lab did not follow a proposal by itself"
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
    # hc13r (HOME-2): the act rests in its follow view: not pressed, "Follow another", the six gates hit, the trace shown (1440)
    rest = await until(pg, "(() => { const f = document.querySelector('[data-sw-follow]'); return f.getAttribute('aria-pressed') === 'false' && f.textContent === 'Follow another' && document.querySelectorAll('[data-sw-gates] li.is-hit').length === 6 && !document.querySelector('[data-sw-callout]').hidden; })()", 15000, 200)
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


LAB_ACT_REST = "(() => { const f = document.querySelector('[data-sw-follow]'); return !!f && f.getAttribute('aria-pressed') === 'false' && f.textContent.trim() === 'Follow another'; })()"
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
    ends on the same link without a click. A click on Follow while the act runs stops it (a toggle), so the reader's own
    follow is "Follow another" at the act's rest; that trace too must end at the link, which is followed to Trust."""
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
            else: print(f"swarm_trace_to_ledger: the lab's own act rested on the ledger link after {t_act:.1f} s; the reader's follow ('Follow another') links to Trust's ledger after {time.monotonic() - t0:.1f} s; it lands in view (top {land[0]} px) with nine records")
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
    away); Enter on the menu toggle opens the sheet with this page's chapters first and the reader's chapter marked
    (a[aria-current] is the chapter the bar names for where the reader is); Tab enters the sheet on a chapter link with
    its visible ring (:focus-visible); Escape closes the sheet and returns focus to the toggle. Home 390 (touch),
    Platform 900, Trust 390 (touch), each read with the reader 45% down the page."""
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
          const first = sh.querySelector('a[href], button'), t = cur && (cur.querySelector('.t') || cur);
          return { current: t ? t.textContent.trim() : null, label: lab.split(' · ')[0], firstIsChapter: !!first && !!first.closest('.nav-ch-list') }; })()""", 3000)
        await pg.keyboard.press("Tab"); await pg.wait_for_timeout(250)
        a1 = await pg.evaluate(PILL_ACTIVE)
        await pg.keyboard.press("Escape"); await pg.wait_for_timeout(500)
        a2 = await pg.evaluate("(() => ({ toggle: document.activeElement === document.querySelector('.nav-toggle'), open: document.querySelector('#site-menu').matches(':popover-open') }))()")
        await ctx.close()
        where = f"{path}@{w}"
        assert not pill, f"pill_focus {where}: the readout's pill is drawn beside the menu toggle under 961 px (two menus)"
        assert st and st["firstIsChapter"] and st["current"] and st["current"] in st["label"], f"pill_focus {where}: Enter on the toggle: the sheet {st} (want it open, this page's chapters first, the reader's chapter marked as the bar names it)"
        assert a1 and a1["inSheet"] and a1["tag"] == "A" and a1["ring"], f"pill_focus {where}: Tab after opening the sheet left focus on {a1} (want a link inside the sheet, with its visible ring)"
        assert a2["toggle"] and not a2["open"], f"pill_focus {where}: Escape in the sheet left {a2} (want the sheet closed and focus on the toggle)"
        said.append(f"{where}: no pill; Enter on the toggle -> sheet, '{st['current']}' marked current; Tab -> '{a1['text']}' (ring); Escape -> the toggle")
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
    has-hot and never changes the instrument's height; Enter opens 04's panel in the list"""
    ctx, pg = await open_page(b, "platform.html", 1440, 900)
    m = await pg.evaluate(SPEC)
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})")
    assert await until(pg, "!!document.querySelector('#architecture .arch.is-wide.is-ready')", 10000), "platform explorer not ready at 1440"
    await pg.wait_for_timeout(600)
    arch_h = "Math.round(document.querySelector('#architecture .arch').getBoundingClientRect().height)"
    h0 = await pg.evaluate(arch_h)
    hov = []
    for k in range(1, 9):
        await pg.locator(f"#arch0-b{k}").hover(); await pg.wait_for_timeout(150)
        hov.append(await pg.evaluate(f"[document.querySelector('#architecture .arch').classList.contains('has-hot'), {arch_h}]"))
    await pg.mouse.move(5, 450)
    assert all(hh and abs(hgt - h0) <= 1 for hh, hgt in hov), f"platform_spec platform.html@1440x900: pointing at each layer gives [has-hot, height] {hov} (want has-hot, height {h0} throughout)"
    shown = []
    for k, (name, job) in enumerate(m["layers"]):
        await pg.locator(f"#arch0-b{k + 1}").click()
        got = await until(pg, f"""(() => {{ const norm = s => (s || '').replace(/\\s+/g, ' ').trim(), p = document.querySelector('#arch0-p{k + 1}'), h = document.querySelectorAll('#architecture h3.arch-h')[{k}];
          return p && h && !p.hidden && p.getClientRects().length > 0 && p.previousElementSibling === h && !!p.closest('.arch-list')
            && document.querySelector('#arch0-b{k + 1}').getAttribute('aria-expanded') === 'true' && norm(p.textContent) === {json.dumps(job)} ? norm(h.querySelector('.nm').textContent) : ''; }})()""", 3000)
        shown.append(got)
    await pg.locator("#arch0-b8").click()
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
    await pg.locator("#arch0-b5").hover()
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



# hc13r (home, HOME-2): every change of the follow button's pressed state, from the document's start
ACT_WATCH = r"""(() => { const W = window, R = W.__act = { pressed: 0, t: [] }; const go = () => { const f = document.querySelector('[data-sw-follow]'); if (!f) return false;
    new MutationObserver(() => { if (f.getAttribute('aria-pressed') === 'true') { R.pressed++; R.t.push(Math.round(performance.now())); } }).observe(f, { attributes: true, attributeFilter: ['aria-pressed'] }); return true; };
  if (!go()) document.addEventListener('DOMContentLoaded', go, { once: true }); })();"""
LAB_SEEN = r"""(() => { const r = document.querySelector('[data-swarm-live]').getBoundingClientRect(); const v = Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0));
  return Math.round(v / Math.max(1, Math.min(r.height, innerHeight)) * 1000) / 1000; })()"""
LAB_SIZE = "(() => [Math.round(document.querySelector('[data-swarm-live]').getBoundingClientRect().height * 10) / 10, document.documentElement.scrollHeight])()"


@check
async def lab_act(b):
    """hc13r (home, HOME-2, on system's SYS-3 OXA.actOnce; home's optional request 9): Home's lab acts by itself only as the
    rule allows. At 1440: once it is well in view it follows one proposal, quietly (its live region stays empty), across
    the six gates, and rests in its follow view ("Follow another"); it never acts again (no second follow at rest, nor
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
    if not await until(pg, "document.querySelector('[data-sw-follow]').getAttribute('aria-pressed') === 'true'", lim(6000), 100):
        bad.append("1440: the lab did not follow a proposal by itself within 6 s in view")
    else:
        if await pg.evaluate("document.querySelector('[data-sw-say]').textContent !== ''"): bad.append("1440: the act announced itself")
        if not await until(pg, LAB_ACT_REST + " && document.querySelectorAll('[data-sw-gates] li.is-hit').length === 6", lim(20000), 200):
            bad.append(f"1440: the act did not rest in its follow view across six gates: {await pg.evaluate(TRACE_STATE)!r}")
        say = await pg.evaluate("document.querySelector('[data-sw-say]').textContent")
        if say: bad.append(f"1440: the act announced {say!r}")
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
        before = await pg.evaluate(LAB_SIZE)
        stacked = await pg.evaluate("document.querySelector('[data-swarm-live]').classList.contains('is-stacked')")
        if not await until(pg, "document.querySelector('[data-sw-follow]').getAttribute('aria-pressed') === 'true'", lim(6000), 100):
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
        # hc13r (home, HOME-2): Home's lab follows one proposal by itself once it is well in view; a press on Follow during
        # that act stops it (a toggle), so the reader's follow waits for the act's rest ("Follow another")
        if path == "index.html" and not await until(pg, LAB_ACT_REST, 40000, 250):
            bad.append(f"{tag}: the lab's own act never came to rest ({await pg.evaluate(TRACE_STATE)!r})"); await ctx.close(); continue
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
    boxes.push([el, r]);
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
            # own act follows one the Council passes, once the lab is well in view, and rests on it without a click (a
            # click during the act would stop it); its rest also shows "Follow another", read here like every control
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
    their start), no area of rgba(14,21,18,.14) over the paper wider than a rule (a 3x3 block; images excluded) shows in
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
# overture.css 322svh, home.css 230svh on portrait phones), so the scene count follows the stage's width
STORY_Y = """(s) => { const st = document.querySelector('.story'), stage = st.querySelector('.story-stage') || st.firstElementChild;
  const units = (stage ? stage.clientWidth : innerWidth) < 600 ? 4.6 : 4.9;
  return Math.round(st.getBoundingClientRect().top + scrollY + Math.max(1, st.offsetHeight - (stage ? stage.offsetHeight : innerHeight)) * s / units); }"""
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
    headline word has risen; a beat that has one still needs it at >= .9"""
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
