"""Budget and timing checks for the v2 site: what the browser has to do, and how soon things happen. These depend on the
machine (GPU, load), so they run locally on the real GPU and are NOT wired into CI (.github/workflows/checks.yml runs
check_static, linkcheck_tree, verify_v9 in shards and verify_editorial; every deterministic invariant lives in verify_v9).

    python tools/serve.py 8125            (in another terminal; any port)
    python tools/verify_budget.py [http://127.0.0.1:8125] [--only name1,name2] [--swiftshader] [--cal-ref MS] [--list]

Chromium runs with --use-angle=d3d11 --enable-gpu --ignore-gpu-blocklist (the real GPU); --swiftshader uses CI's software
GL instead, to see what a runner would measure. Run it on an idle machine, once per change: one line per check, exit
status 1 if any check failed, 2 if none failed but some were inconclusive. Start the PowerShell command with
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'.

Load awareness (round 2). Before each check the run prints the host's CPU load and a calibration: a fixed JavaScript loop
(2e7 square roots, about 50 ms idle; the median of three after a warm-up run) timed in the browser, as a ratio to this
machine's idle time for it. The idle reference is the fastest calibration this machine has recorded
(.shots/budget-calibration.json, per machine and workload; --cal-ref MS sets it); until this workload has a record, an
older workload's record scaled to it stands in (the 1e7 loop's x2), so a first run on a loaded machine cannot become the
idle reference unchallenged; with no record at all the run says so. The timing
checks (marked * below) run three times and judge the median; when such a check, or page_transition (+, judged frame by
frame over its own repeated runs), fails while the calibration is above 2x idle it prints INCONCLUSIVE instead of FAIL
(rerun on a quiet machine). Counting checks (recalcs, rAF callbacks, animations, layout shift) judge one run: load does
not change what they count.

The checks (the item each one guards in brackets):
  style_ledger         a 2 s trace with the live ledger centred: median UpdateLayoutTree elementCount < 60   [LG1, NV2; round 2 tightened from 200]
  style_clock          reduced motion, at the footer: one footer-clock text change restyles < 50 elements, on / and /platform.html   [NV2]
  cls_latency          / at 390 with 700 ms of network latency: layout shift (no recent input) sums to < 0.1   [OV9]
  offscreen_work       at the footer of /, /lifecycles.html, /platform.html: no running animation with an off-screen target,
                       and 0 requestAnimationFrame callbacks in 3 s; round 2: landing on /#lifecycles, story.js runs 0 rAF in
                       3 s (1440 and 390@3); /evidence.html with the chart's band on screen and the chart off it: no running
                       off-screen animation; the explorer (arch.js) runs 0 rAF after 8 s idle   [NV6, SW4, LG1, LC6; OV-R2-3b, PF-R2-3, AR-R2-4]
  desk_reduced_raf     reduced motion, the desk in view: gap.js runs 0 requestAnimationFrame callbacks in 3 s   [LC2b, LC6]
  headline_after_step* 400 ms after each overture index step (1440, 390): every headline word is up (translateY <= 4% of its height)   [OV4]
  desk_warm_time*      within 1.2 s of the desk scrolling into view: its clock reads >= 11:00 ET and its strip holds a record   [LC2b]
  inspect_time*        the trace's record button: the followed record is selected in the ledger within 800 ms of the click   [SW2, LG4; round 2 tightened from 1.5 s]
  proof_entrance_time* home 4.1's chart, arrived at from above: its entrance transitions finish within 1.3 s of .is-in   [PF2]
  swarm_pacing*        the swarm lab centred at 1440x900@2: frame interval median <= 18 ms, p95 <= 33 ms   [SW4]
  swarm_phone_fps*     the lab at 390x844@3, touch, 4x CPU, agents at the slider's maximum: >= 30 fps once the governor has
                       settled (up to 30 s; the cap it reached is printed)   [SW4]
  page_transition+     home at S0 to Company and to Proof, 5 runs each: every screencast frame's mean luminance under the bar
                       < 60 (no white flash between dark pages); Platform to Lifecycles, 5 runs: no frame draws both pages'
                       views at opacity >= .25 (two headlines legible)   [NV-R2-3]
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import asyncio, base64, collections, io, json, platform, re, statistics, sys, time, traceback
from pathlib import Path
from playwright.async_api import async_playwright
import verify_v9 as V  # shared helpers: open_page, until, scene_rest, the record and events scripts, host_load

GPU = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
SWIFTSHADER = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
CATS = "devtools.timeline,disabled-by-default-devtools.timeline"
CAL_FILE = Path(str(V.SHOTS)) / "budget-calibration.json"
CAL_ID = "sqrt-2e7"  # the calibration workload; its idle time is recorded per machine and per workload
# about 50 ms on an idle laptop (director's test list: 'a 50 ms JS calibration': this PC's fastest 1e7 loop took 25 ms);
# the median of three runs is used
CAL_LOOP = "(() => { const t = performance.now(); let x = 0; for (let i = 0; i < 2e7; i++) x += Math.sqrt(i); window.__calx = x; return performance.now() - t; })()"
CAL_SCALE = {"sqrt-1e7": 2.0}  # an older workload's idle record, scaled to this one, stands in until this one has its own
# counts requestAnimationFrame callbacks per calling script (assets/js/<file>), before any page script runs
RAF_COUNTER = r"""(() => { const W = window; if (W.__raf) return; const R = W.__raf = { n: 0, by: {} };
  const who = () => { const m = ((new Error()).stack || '').match(/assets\/js\/([\w.-]+\.js)/); return m ? m[1] : 'other'; };
  const o = W.requestAnimationFrame.bind(W);
  W.requestAnimationFrame = function (cb) { const k = who(); return o(function (t) { R.n++; R.by[k] = (R.by[k] || 0) + 1; return cb(t); }); }; })();"""
CLS = r"""(() => { const S = window.__ls = []; try { new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput) S.push({ t: Math.round(e.startTime), v: e.value,
  src: (e.sources || []).slice(0, 2).map(s => s.node && s.node.nodeType === 1 ? s.node.tagName + '.' + String(s.node.className || '').split(' ')[0] : '?') }); })).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} })();"""
CHECKS, TIMING, LOADED_OUT = [], set(), set()
def check(fn): CHECKS.append(fn); return fn
def timing(fn): TIMING.add(fn.__name__); LOADED_OUT.add(fn.__name__); return fn  # the median of three runs; INCONCLUSIVE under load
def frames(fn): LOADED_OUT.add(fn.__name__); return fn  # one pass of repeated runs, judged frame by frame; INCONCLUSIVE under load


async def calibrate(b):
    """the calibration loop's median time over three runs in a fresh page, after one warm-up run (ms)"""
    ctx = await b.new_context(viewport={"width": 400, "height": 300})
    pg = await ctx.new_page()
    await pg.goto("about:blank")
    await pg.evaluate(CAL_LOOP)  # the first run includes compiling the loop
    ms = statistics.median([await pg.evaluate(CAL_LOOP) for _ in range(3)])
    await ctx.close()
    return ms


def cal_ref(now_ms, override=None):
    """this machine's idle reference: --cal-ref, else the fastest calibration recorded here (updated with this one)"""
    if override: return float(override), "set by --cal-ref"
    rec = {}
    try: rec = json.loads(CAL_FILE.read_text(encoding="utf-8"))
    except Exception: pass
    node = platform.node() or "this machine"
    key = f"{node} | {CAL_ID}"
    best, note = rec.get(key), "the fastest recorded on this machine"
    if not best:  # a first run on a loaded machine must not become the idle reference unchallenged
        old = [(rec[f"{node} | {w}"] * f, w) for w, f in CAL_SCALE.items() if rec.get(f"{node} | {w}")]
        if old:
            best, w = min(old)
            note = f"this machine's fastest {w} run x{CAL_SCALE[w]:g}, until a faster run of this workload replaces it"
        else:
            note = "no idle reference yet: this run's calibration becomes it (run the first time on an idle machine, or pass --cal-ref)"
    if not best or now_ms < best:  # only a measured run of this workload is recorded, and only when it is the fastest
        rec[key] = round(now_ms, 1)
        try: CAL_FILE.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        except Exception: pass
        best = now_ms
    return best, note


async def trace(pg, cdp, secs, during=None):
    """a CDP timeline trace of `secs` seconds; `during` (a coroutine factory) runs 0.3 s into it"""
    events, done = [], asyncio.get_running_loop().create_future()
    cdp.on("Tracing.dataCollected", lambda e: events.extend(e["value"]))
    cdp.on("Tracing.tracingComplete", lambda e: (not done.done()) and done.set_result(1))
    await cdp.send("Tracing.start", {"categories": CATS, "transferMode": "ReportEvents"})
    if during: await pg.wait_for_timeout(300); await during(); await pg.wait_for_timeout(int(secs * 1000) - 300)
    else: await pg.wait_for_timeout(int(secs * 1000))
    await cdp.send("Tracing.end"); await asyncio.wait_for(done, 60)
    return events


def recalcs(events):
    """elementCount of every style recalc (UpdateLayoutTree) on the renderer's main thread"""
    ult = [e for e in events if e.get("name") == "UpdateLayoutTree" and e.get("ph") == "X"]
    main = collections.Counter(e.get("tid") for e in ult).most_common(1)
    return [e.get("args", {}).get("elementCount", 0) for e in ult if main and e.get("tid") == main[0][0]]


@check
async def style_ledger(b):
    ctx, pg = await V.open_page(b, "index.html", 1440, 900)
    cdp = await ctx.new_cdp_session(pg)
    await pg.evaluate("document.querySelector('[data-ledger=live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(2500)
    n = recalcs(await trace(pg, cdp, 2.0))
    await ctx.close()
    med = statistics.median(n) if n else 0
    return med < 60 and len(n) > 0, f"index.html@1440x900, ledger centred, 2 s: {len(n)} recalcs, median {med:.0f} elements (max {max(n or [0])}); budget < 60 (round 2; was < 200)"


@check
async def style_clock(b):
    out, ok = [], True
    for path in ("index.html", "platform.html"):
        ctx, pg = await V.open_page(b, path, 1440, 900, reduced=True)
        cdp = await ctx.new_cdp_session(pg)
        await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(1500)
        # the clock's own interval keeps writing to the nodes it holds; a clone takes their place, so only our one change counts
        await pg.evaluate("(() => { const s = document.querySelector('.footer .clocks'); if (s) s.replaceWith(s.cloneNode(true)); })()")
        await pg.wait_for_timeout(1200)
        async def change(): await pg.evaluate("(() => { const t = document.querySelector('.footer time') || document.querySelector('.footer .clocks span'); t.textContent = '12:' + String(Math.random()).slice(2, 4) + ':00'; })()")
        n = recalcs(await trace(pg, cdp, 1.2, change))
        await ctx.close()
        top = max(n or [0])
        ok = ok and top < 50
        out.append(f"{path}: {len(n)} recalcs, largest {top} elements")
    return ok, "reduced motion, at the footer, one clock text change: " + "; ".join(out) + "; budget < 50"


@check
async def cls_latency(b):
    ctx = await b.new_context(viewport={"width": 390, "height": 844})
    await ctx.add_init_script(CLS)
    pg = await ctx.new_page(); pg.set_default_navigation_timeout(120000)
    cdp = await ctx.new_cdp_session(pg)
    await cdp.send("Network.enable")
    await cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 700, "downloadThroughput": 10 * 1024 * 1024 / 8, "uploadThroughput": 5 * 1024 * 1024 / 8})
    await pg.goto(f"{V.BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(5000)
    ls = await pg.evaluate("window.__ls")
    await ctx.close()
    total = sum(e["v"] for e in ls)
    big = sorted(ls, key=lambda e: -e["v"])[:3]
    return total < 0.1, f"index.html@390x844, latency 700 ms: CLS {total:.4f} over {len(ls)} shifts (largest {[(e['t'], round(e['v'], 4), e['src']) for e in big]}); budget < 0.1"


OFFSCREEN = """(() => { const out = []; for (const a of document.getAnimations()) { if (a.playState !== 'running') continue;
    const t = a.effect && a.effect.target; if (!t || !t.getBoundingClientRect) continue; const r = t.getBoundingClientRect();
    if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth)
      out.push((a.animationName || a.transitionProperty || a.constructor.name) + ' on ' + t.tagName.toLowerCase() + '.' + String(t.className && t.className.baseVal !== undefined ? t.className.baseVal : t.className).trim().split(/\\s+/).slice(0, 2).join('.') + (a.effect.pseudoElement || '')); }
  return out; })()"""
RAF_ZERO = "(() => { window.__raf.n = 0; window.__raf.by = {}; })()"


@check
async def offscreen_work(b):
    out, ok = [], True
    for path in ("index.html", "lifecycles.html", "platform.html"):
        ctx, pg = await V.open_page(b, path, 1440, 900, init=RAF_COUNTER)
        await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(1500)
        anims = await pg.evaluate(OFFSCREEN)
        await pg.evaluate(RAF_ZERO); await pg.wait_for_timeout(3000)
        raf = await pg.evaluate("window.__raf")
        await ctx.close()
        ok = ok and not anims and raf["n"] == 0
        out.append(f"{path} at the footer: {len(anims)} off-screen animations {sorted(set(anims))[:4]}, {raf['n']} rAF callbacks {raf['by']}")
    # round 2 (OV-R2-3b): landing on the home page's first chapter, the overture (under the opaque bar) draws nothing
    for w, h, dpr in ((1440, 900, 1), (390, 844, 3)):
        ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr)
        await ctx.add_init_script(RAF_COUNTER)
        pg = await ctx.new_page(); pg.set_default_timeout(45000)
        await pg.goto(f"{V.BASE}/index.html#lifecycles", wait_until="load"); await V.until(pg, V.LOADED, 15000); await pg.wait_for_timeout(1500)
        await pg.evaluate(RAF_ZERO); await pg.wait_for_timeout(3000)
        raf = await pg.evaluate("window.__raf"); y = await pg.evaluate("scrollY")
        await ctx.close()
        story = raf["by"].get("story.js", 0)
        ok = ok and story == 0
        out.append(f"/#lifecycles at {w}x{h}@{dpr} (scrollY {y}): story.js {story} rAF in 3 s")
    # round 2 (PF-R2-3c): Proof's chart seen (its entrance and idle loops start), then scrolled just above the view while
    # its band stays on screen: no animation runs on it
    ctx, pg = await V.open_page(b, "evidence.html", 1440, 900)
    await pg.evaluate("document.querySelector('#performance [data-proof-chart]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(3500)
    await pg.evaluate("(() => { const c = document.querySelector('#performance [data-proof-chart]'); const r = c.getBoundingClientRect(); window.scrollTo({top: r.bottom + scrollY + 40, behavior: 'instant'}); })()")
    await pg.wait_for_timeout(2000)
    band = await pg.evaluate("(() => { const r = document.querySelector('#performance').getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; })()")
    anims = await pg.evaluate(OFFSCREEN)
    await ctx.close()
    ok = ok and band and not anims
    out.append(f"evidence.html, chart seen then just above the view, its band on screen ({band}): {len(anims)} off-screen animations {sorted(set(anims))[:4]}")
    # round 2 (AR-R2-4): the explorer stops after 8 s with no pointer or focus in it
    ctx, pg = await V.open_page(b, "index.html", 1440, 900, init=RAF_COUNTER)
    await pg.evaluate("document.querySelector('#stack .arch').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.mouse.move(2, 898)
    await V.until(pg, "!!document.querySelector('#stack .arch.is-ready')", 10000)
    await pg.wait_for_timeout(8500)
    await pg.evaluate(RAF_ZERO); await pg.wait_for_timeout(3000)
    raf = await pg.evaluate("window.__raf")
    await ctx.close()
    arch = raf["by"].get("arch.js", 0)
    ok = ok and arch == 0
    out.append(f"home's explorer after 8.5 s idle: arch.js {arch} rAF in 3 s")
    return ok, "; ".join(out) + "; budget 0 everywhere"


@check
async def desk_reduced_raf(b):
    ctx, pg = await V.open_page(b, "lifecycles.html", 1440, 900, reduced=True, init=RAF_COUNTER)
    await pg.evaluate("document.querySelector('[data-gap]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1500)
    await pg.evaluate(RAF_ZERO); await pg.wait_for_timeout(3000)
    raf = await pg.evaluate("window.__raf")
    await ctx.close()
    gap = raf["by"].get("gap.js", 0)
    return gap == 0, f"lifecycles.html@1440x900, reduced motion, desk centred, 3 s: gap.js {gap} rAF callbacks (all scripts: {raf['by']}); budget 0"


HEADLINE = """async (i) => { document.querySelector('.story-idx [data-n="0' + i + '"]').click(); await new Promise(r => setTimeout(r, 400));
  const ws = [...document.querySelectorAll('.beat-' + i + ' h1 .wi, .beat-' + i + ' h2 .wi')];
  const ty = w => { const t = getComputedStyle(w).transform; return !t || t === 'none' ? 0 : new DOMMatrixReadOnly(t).m42; };
  const low = ws.filter(w => ty(w) > 0.04 * (w.offsetHeight || 1)).map(w => w.textContent + ' ' + Math.round(ty(w)) + '/' + w.offsetHeight);
  return { n: ws.length, low }; }"""


@check
@timing
async def headline_after_step(b):
    out, low = [], 0
    for w, h in ((1440, 900), (390, 844)):
        ctx, pg = await V.open_page(b, "index.html", w, h)
        await pg.wait_for_timeout(800)
        for i in range(1, 5):
            r = await pg.evaluate(HEADLINE, i)
            if not r["n"] or r["low"]: low += max(1, len(r["low"])); out.append(f"{w}x{h} step 0{i}: {len(r['low'])} of {r['n']} words still low {r['low'][:3]}")
            await V.scene_rest(pg, i)
        await ctx.close()
    return not low, "400 ms after each index step at 1440 and 390: " + ("every headline word is up" if not low else "; ".join(out)), low


@check
@timing
async def desk_warm_time(b):
    ctx, pg = await V.open_page(b, "lifecycles.html", 1440, 900)
    r = await pg.evaluate("""async () => { document.querySelector('[data-gap]').scrollIntoView({block: 'center', behavior: 'instant'}); const t0 = performance.now();
      const recs = () => document.querySelectorAll('.desk-log li:not(.dk-more)').length;  // LC-R2-6a's '+N earlier records' row is no record
      const ok = () => { const m = (document.querySelector('[data-gap-time]').textContent || '').match(/(\\d\\d):(\\d\\d)/); return !!m && (+m[1] * 60 + +m[2]) >= 660 && recs() >= 1; };
      while (!ok() && performance.now() - t0 < 1200) await new Promise(r => setTimeout(r, 50));
      return { ok: ok(), ms: Math.round(performance.now() - t0), time: document.querySelector('[data-gap-time]').textContent, log: recs() }; }""")
    await ctx.close()
    return r["ok"], f"lifecycles.html@1440x900: {r['ms']} ms after the reveal the desk reads {r['time']} with {r['log']} record(s); budget >= 11:00 ET and >= 1 record within 1.2 s", r["ms"] if r["ok"] else float("inf")


@check
@timing
async def inspect_time(b):
    ctx, pg = await V.open_page(b, "index.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await V.until(pg, "+document.querySelector('[data-sw-inflight]').textContent.replace(/\\D/g, '') > 0", 25000, 200)
    await pg.evaluate("(() => { const s = document.querySelector('[data-sw-strict]'); s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    await pg.locator("[data-sw-follow]").click()
    has = await V.until(pg, """(() => { if (document.querySelector('[data-sw-log] [data-sw-rec]')) return 'button';
        return /record #[0-9a-f]{4}/.test((document.querySelector('[data-sw-log]') || {}).textContent || '') ? 'text' : ''; })()""", 60000, 250)
    if has != "button":
        await ctx.close(); return False, f"index.html@1440x900: the trace's ledger row is no record button ({has or 'nothing after 60 s'}; needs SW2 + LG4)", float("inf")
    await pg.evaluate("""(() => { const R = window.__ins = { click: 0, sel: 0 }; document.addEventListener('click', e => { if (e.target.closest('[data-sw-rec]')) R.click = performance.now(); }, true);
      const watch = () => { const li = document.querySelector('[data-ledger=live] .lt-rec.is-followed'); if (li && li.classList.contains('is-sel') && R.click && !R.sel) R.sel = performance.now(); };
      new MutationObserver(watch).observe(document.querySelector('[data-ledger=live]'), { subtree: true, attributes: true, attributeFilter: ['class'] }); })()""")
    await pg.locator("[data-sw-log] [data-sw-rec]").click()
    await V.until(pg, "window.__ins.sel > 0", 8000)
    r = await pg.evaluate("window.__ins")
    await ctx.close()
    ms = r["sel"] - r["click"] if r["sel"] else None
    return ms is not None and ms <= 800, f"index.html@1440x900: the followed record was selected {'%.0f ms' % ms if ms is not None else 'never (8 s)'} after the click; budget 800 ms (round 2; was 1.5 s)", ms if ms is not None else float("inf")


@check
@timing
async def proof_entrance_time(b):
    ctx, pg = await V.open_page(b, "index.html", 1440, 900)
    g = await pg.evaluate("(() => { const r = document.querySelector('#proof [data-proof-chart]').getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; })()")
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 - 60}, behavior: 'instant'}})"); await pg.wait_for_timeout(700)
    await pg.evaluate("""(() => { const host = document.querySelector('#proof [data-proof-chart]'); const R = window.__pt = { inAt: 0, end: 0, ran: false };
      const f = () => { const now = performance.now(); if (!R.inAt && host.classList.contains('is-in')) R.inAt = now;
        if (R.inAt) { const run = host.getAnimations({ subtree: true }).filter(a => a instanceof CSSTransition && a.playState === 'running').length;
          if (run) R.ran = true; else if (R.ran && !R.end) R.end = now; }
        if (!R.end && now - (R.inAt || now) < 6000) requestAnimationFrame(f); }; requestAnimationFrame(f); })()""")
    await pg.evaluate(f"window.scrollTo({{top: {g['top'] - 900 + g['h'] * 0.38:.0f}, behavior: 'instant'}})")
    await V.until(pg, "window.__pt.end > 0", 8000)
    r = await pg.evaluate("window.__pt")
    await ctx.close()
    ms = r["end"] - r["inAt"] if r["end"] and r["inAt"] else None
    return ms is not None and ms <= 1300, f"index.html@1440x900, from above: the entrance's transitions ran {'%.0f ms' % ms if ms is not None else '(never finished / never ran)'} after .is-in; budget 1.3 s", ms if ms is not None else float("inf")


@check
@timing
async def swarm_pacing(b):
    ctx, pg = await V.open_page(b, "index.html", 1440, 900, dpr=2)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(3000)
    iv = await pg.evaluate("""() => new Promise(res => { const out = []; let last = 0; const t0 = performance.now();
      const f = t => { if (last) out.push(t - last); last = t; if (t - t0 < 4000) requestAnimationFrame(f); else res(out); }; requestAnimationFrame(f); })""")
    q = await pg.evaluate("(document.querySelector('[data-swarm-live]').dataset.swQuality || '?')")
    await ctx.close()
    iv = sorted(iv)
    med = statistics.median(iv) if iv else 999
    p95 = iv[min(len(iv) - 1, int(len(iv) * 0.95))] if iv else 999
    return med <= 18 and p95 <= 33, f"index.html@1440x900@2, lab centred, 4 s: {len(iv)} frames, median {med:.1f} ms, p95 {p95:.1f} ms (quality {q}); budget <= 18 / <= 33 ms", p95


@check
@timing
async def swarm_phone_fps(b):
    ctx, pg = await V.open_page(b, "index.html", 390, 844, dpr=3, touch=True)
    cdp = await ctx.new_cdp_session(pg)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(1500)
    await pg.evaluate("(() => { const s = document.querySelector('[data-sw-n]'); s.value = s.max; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    # round 2: the governor sheds trails, then population, in steps; wait (up to 30 s) until its cap holds for 5 s.
    # The hold counts only while the lane carries the population it is held to (in flight within 15 % of the cap, or of
    # the slider's target while uncapped): the governor judges a step once the lane is down to it, so before the lane has
    # filled (about 5 s after the slider moves) an unchanged output means it has not acted yet, not that it settled
    LAB = r"""(() => { const t = s => (document.querySelector(s) || {}).textContent || '', out = t('[data-sw-n-out]');
      const m = [...out.matchAll(/([\d.,]+)\s*(k?)\b/g)].pop(), pop = m ? parseFloat(m[1].replace(/,/g, '')) * (m[2] ? 1000 : 1) : 0;
      return { out, pop, fl: +(t('[data-sw-inflight]').replace(/\D/g, '') || 0) }; })()"""
    t0, last, since = time.monotonic(), None, None
    while time.monotonic() - t0 < 30:
        s = await pg.evaluate(LAB)
        full = s["pop"] > 0 and abs(s["fl"] - s["pop"]) <= 0.15 * s["pop"]
        if s["out"] != last or not full: last, since = s["out"], (time.monotonic() if full else None)
        elif since is None: since = time.monotonic()
        if since is not None and time.monotonic() - since >= 5: break
        await pg.wait_for_timeout(500)
    settled = f"settled after {time.monotonic() - t0:.0f} s" if since is not None and time.monotonic() - since >= 5 else "still moving after 30 s"
    r = await pg.evaluate("""() => new Promise(res => { let n = 0; const t0 = performance.now(); const f = t => { n++; if (t - t0 < 4000) requestAnimationFrame(f); else res({ n, ms: t - t0 }); }; requestAnimationFrame(f); })""")
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    await ctx.close()
    fps = r["n"] * 1000 / max(1, r["ms"])
    return fps >= 30, f"index.html@390x844@3, touch, 4x CPU, agents at the slider's maximum, governor {settled} at {last!r}: {fps:.1f} fps; budget >= 30 fps", fps


# ---- round 2 (NV-R2-3): page transitions never flash white between dark pages, never show two headlines
VT_ROOTS = r"""(() => { if (window.__vtr) return; const R = window.__vtr = [];
  const bez = (x1, y1, x2, y2) => t => { let lo = 0, hi = 1, s = t; for (let i = 0; i < 24; i++) { s = (lo + hi) / 2; const x = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s * s * x2 + s ** 3; if (x < t) lo = s; else hi = s; }
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s * s * y2 + s ** 3; };
  const EASE = { linear: t => t, ease: bez(.25, .1, .25, 1), 'ease-in': bez(.42, 0, 1, 1), 'ease-out': bez(0, 0, .58, 1), 'ease-in-out': bez(.42, 0, .58, 1) };
  const easing = e => { const m = /cubic-bezier\(([^)]+)\)/.exec(e || ''); return m ? bez(...m[1].split(',').map(Number)) : EASE[e] || EASE.linear; };
  // the opacity an animation gives its pseudo-element now: its keyframes, eased per interval, at its current progress
  const opac = a => { const p = a.effect.getComputedTiming().progress; if (p == null) return null; const k = a.effect.getKeyframes().filter(f => f.opacity !== undefined);
    if (!k.length) return null; const pts = [...k]; if (pts[0].computedOffset > 0) pts.unshift({ computedOffset: 0, opacity: '1', easing: 'linear' }); if (pts[pts.length - 1].computedOffset < 1) pts.push({ computedOffset: 1, opacity: '1' });
    for (let i = 0; i < pts.length - 1; i++) { const a0 = pts[i], a1 = pts[i + 1]; if (p >= a0.computedOffset && p <= a1.computedOffset) { const u = a1.computedOffset > a0.computedOffset ? (p - a0.computedOffset) / (a1.computedOffset - a0.computedOffset) : 1;
      return +a0.opacity + (+a1.opacity - +a0.opacity) * easing(a0.easing)(u); } } return +pts[pts.length - 1].opacity; };
  const f = () => { const an = document.getAnimations().filter(a => a.effect && a.effect.pseudoElement && /^::view-transition-(old|new)\(root\)$/.test(a.effect.pseudoElement));
    const o = { t: Math.round(performance.now()) }; an.forEach(a => { const v = opac(a); if (v !== null) o[/old/.test(a.effect.pseudoElement) ? 'old' : 'neu'] = +v.toFixed(2); });
    if (an.length) R.push(o); if (R.length < 400 && performance.now() < 8000) requestAnimationFrame(f); }; requestAnimationFrame(f); })();"""


async def screencast(cdp, frames):
    def on(ev):
        frames.append((ev["metadata"].get("timestamp", 0) * 1000.0, ev["data"]))
        asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))
    cdp.on("Page.screencastFrame", on)
    await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 80, "maxWidth": 1440, "maxHeight": 900, "everyNthFrame": 1})
    return on


@check
@frames
async def page_transition(b):
    from PIL import Image
    worst, msgs, ok = 0.0, [], True
    for dest, sel in (("company.html", ".nav-links a[href*='company']"), ("evidence.html", ".nav-links a[href*='evidence']")):
        hi = []
        for run in range(5):
            ctx, pg = await V.open_page(b, "index.html", 1440, 900)
            await V.to_top_settled(pg)
            cdp = await ctx.new_cdp_session(pg)
            frames = []
            on = await screencast(cdp, frames)
            await pg.wait_for_timeout(300)
            t0 = time.time() * 1000.0
            await pg.click(sel)
            await pg.wait_for_timeout(1800)
            try: await cdp.send("Page.stopScreencast")
            except Exception: pass
            await ctx.close()
            lums = []
            for ts, data in frames:
                if ts < t0 - 60 or ts > t0 + 1600: continue
                im = Image.open(io.BytesIO(base64.b64decode(data))).convert("L")
                body = im.crop((0, int(im.size[1] * 64 / 900), im.size[0], im.size[1]))
                lums.append((int(ts - t0), sum(i * c for i, c in enumerate(body.histogram())) / max(1, body.size[0] * body.size[1])))
            peak = max(lums, key=lambda x: x[1]) if lums else (0, 999)
            hi.append(peak)
            worst = max(worst, peak[1])
        bad = [p for p in hi if p[1] >= 60]
        ok = ok and not bad
        msgs.append(f"/ (S0) -> {dest}: brightest frame per run (ms, mean luminance) {[(p[0], round(p[1])) for p in hi]}")
    both = []
    for run in range(5):
        ctx = await b.new_context(viewport={"width": 1440, "height": 900})
        await ctx.add_init_script(VT_ROOTS)
        pg = await ctx.new_page(); pg.set_default_timeout(45000)
        await pg.goto(f"{V.BASE}/platform.html", wait_until="load"); await pg.wait_for_timeout(1500)
        await pg.click(".nav-links a[href*='lifecycles']")
        await pg.wait_for_timeout(1500)
        r = await pg.evaluate("window.__vtr || []")
        await ctx.close()
        two = [x for x in r if (x.get("old") or 0) >= 0.25 and (x.get("neu") or 0) >= 0.25]
        both.append((len(r), len(two), two[:2]))
    ok = ok and not any(x[1] for x in both)
    msgs.append(f"platform -> lifecycles: (frames, frames with both views at >= .25, e.g.) per run {both}")
    return ok, "; ".join(msgs) + "; budget: luminance < 60 in every frame, never both views at .25", worst


def parse_cal(argv):
    for i, a in enumerate(argv):
        if a.startswith("--cal-ref="): return a.split("=", 1)[1]
        if a == "--cal-ref" and i + 1 < len(argv): return argv[i + 1]
    return None


async def main():
    base, only, listing = V.parse_args(sys.argv[1:])
    if base: V.BASE = base
    names = [c.__name__ for c in CHECKS]
    if listing:
        for n in names: print(n + (" (timing: median of 3)" if n in TIMING else ""))
        return 0
    unknown = [n for n in (only or []) if n not in names]
    if unknown: print("unknown check(s):", unknown, "- known:", ", ".join(names)); return 2
    args = SWIFTSHADER if "--swiftshader" in sys.argv else GPU
    override = parse_cal(sys.argv[1:])
    failed, vague = [], []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=args)
        print(f"verify_budget against {V.BASE} ({'SwiftShader' if args is SWIFTSHADER else 'GPU: ' + ' '.join(GPU)}) · Chromium {b.version}", flush=True)
        for c in [c for c in CHECKS if only is None or c.__name__ in only]:
            t0 = time.monotonic()
            cal = await calibrate(b)
            ref, note = cal_ref(cal, override)
            ratio = cal / ref if ref else 1.0
            print(f"  {c.__name__}: host {V.host_load()} · calibration {cal:.0f} ms = {ratio:.2f}x idle ({ref:.0f} ms, {note})", flush=True)
            runs = 3 if c.__name__ in TIMING else 1
            res = []
            for k in range(runs):
                try:
                    r = await asyncio.wait_for(c(b), 600)
                    res.append(r if len(r) == 3 else (r[0], r[1], 0))
                except Exception as e:
                    res.append((False, "error: " + "".join(traceback.format_exception_only(type(e), e)).strip(), float("inf")))
            if runs > 1:
                order = sorted(res, key=lambda r: (r[2] is None, r[2] if r[2] is not None else 0))
                ok, msg, _ = order[len(order) // 2]
                msg = f"median of 3 ({', '.join(f'{r[2]:.4g}' if isinstance(r[2], (int, float)) else str(r[2]) for r in res)}): {msg}"
            else:
                ok, msg, _ = res[0]
            verdict = "PASS" if ok else ("INCONCLUSIVE" if c.__name__ in LOADED_OUT and ratio > 2 else "FAIL")
            print(f"{verdict} {c.__name__}: {msg} ({time.monotonic() - t0:.0f}s)" + (f" [calibration {ratio:.1f}x idle: rerun on a quiet machine]" if verdict == "INCONCLUSIVE" else ""), flush=True)
            if verdict == "FAIL": failed.append(c.__name__)
            elif verdict == "INCONCLUSIVE": vague.append(c.__name__)
        await b.close()
    if failed: print(f"BUDGET CHECKS FAILED: {', '.join(failed)}" + (f" (inconclusive under load: {', '.join(vague)})" if vague else "")); return 1
    if vague: print(f"BUDGET CHECKS INCONCLUSIVE under load: {', '.join(vague)} (the rest passed)"); return 2
    print("BUDGET CHECKS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
