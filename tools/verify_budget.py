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
  style_ledger         a 2 s trace while Trust's ledger replays (centred, 1440): median UpdateLayoutTree elementCount < 60
                       (Home's live ledger until it left the page on 1 Nov)   [LG1, NV2; round 2 tightened from 200]
  style_clock          reduced motion, at the footer: one footer-clock text change restyles < 50 elements, on / and /platform.html   [NV2]
  cls_latency          / at 390 with 700 ms of network latency: layout shift (no recent input) sums to < 0.1   [OV9]
  offscreen_work       at the footer of /, /lifecycles.html, /platform.html: no running animation with an off-screen target,
                       and 0 requestAnimationFrame callbacks in 3 s; round 2: landing on /#lifecycles, story.js runs 0 rAF in
                       3 s (1440 and 390@3); /evidence.html with the chart's band on screen and the chart off it: no running
                       off-screen animation; the explorer (arch.js, on /platform.html since hc5) runs 0 rAF after 8 s idle   [NV6, SW4, LG1, LC6; OV-R2-3b, PF-R2-3, AR-R2-4]
  desk_reduced_raf     reduced motion, the desk in view: gap.js runs 0 requestAnimationFrame callbacks in 3 s   [LC2b, LC6]
  headline_after_step* 400 ms after each overture index step (1440, 390): every headline word is up (translateY <= 4% of its height)   [OV4]
  desk_warm_time*      within 1.2 s of the desk scrolling into view: its clock reads >= 11:00 ET and its strip holds a record   [LC2b]
  inspect_time*        a click on a record of Trust's ledger selects it and the inspector names it within 800 ms (until
                       1 Nov: the swarm trace's record button and Home's ledger, which left the page)   [SW2, LG4; round 2 tightened from 1.5 s]
  proof_entrance_time* the proof chart's entrance (Proof's hero at load since hc13r; Home §03's, arrived at from above,
                       until then): its entrance transitions finish within 1.3 s of .is-in   [PF2]
  swarm_pacing*        the swarm lab centred at 1440x900@2: frame interval median <= 18 ms, p95 <= 33 ms   [SW4]
  swarm_phone_fps*     the lab at 390x844@3, touch, 4x CPU, agents at the slider's maximum: >= 30 fps once the governor has
                       settled (up to 30 s; the cap it reached is printed)   [SW4]
  page_transition+     home at S0 to Company and to Proof, 5 runs each: every screencast frame's mean luminance under the bar
                       < 60 (no white flash between dark pages); Platform to Lifecycles, 5 runs: no frame draws both pages'
                       views at opacity >= .25 (two headlines legible)   [NV-R2-3]
  home_landing+        v2x r3: Home opened mid-way. Reload and Back with a chapter 80 px under the top (1440; 390@2 touch;
                       §04 #proof until hc13r, §03 #economics since, the chapter after the lab whose cost index builds on
                       screen): it lands within 2 px of 80 and the largest layout-shift window (no recent input; 1 s gap,
                       5 s cap) is < 0.01; /#economics (/#proof until hc13r), /#lc01, /#governance fresh, five loads each
                       at both widths: the target's top at the bar's bottom (2 px) and that window < 0.1 in every load
                       [r3-motion M1, r3-perf moderate]
  loader_curtain+      v2x r3: 20 first visits to / at 390x844@2, touch, 4x CPU: every visit ends with the loader's exit (the
                       curtain until a1, the hand-off since: .is-done comes, and before the loader is removed; none ends at
                       .is-complete alone) and the beat (the exit's transition start + delay - the '100' pulse) is 85-110 ms
                       in every visit (designed 90)   [r3-perf moderate, r3-motion minor; award a1]
  trust_landing+       v2x r5: Trust opened mid-way. Reload and Back with §03 80 px under the top (390@2 and 320@2 touch,
                       1024) and §02/§04 at 20/80/500 (390): the section's top within 2 px of where it was, the largest
                       layout-shift window < 0.01   [r5-perf issues 2, 4]
  offscreen_reveals+   v2x r5: /evidence.html, / and /platform.html at 412x823@2, touch, 4x CPU, sampled every 50 ms until
                       1.5 s after site.js sets its reveals up: no CSS transition on an off-screen [data-reveal]   [r5-perf issue 3]
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
    ctx, pg = await V.open_page(b, "trust.html", 1440, 900)
    cdp = await ctx.new_cdp_session(pg)
    await pg.evaluate("document.querySelector('[data-ledger=replay]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await V.until(pg, "(() => { const r = document.querySelector('[data-ledger=replay] [data-lt-replay]'); return !!r && !r.hidden; })()", 8000)
    await pg.wait_for_timeout(1500)
    await pg.locator("[data-ledger=replay] [data-lt-replay]").click()
    await pg.mouse.move(5, 450)
    await pg.wait_for_timeout(500)  # the click's own restyle is not the ledger's
    n = recalcs(await trace(pg, cdp, 2.0))
    await ctx.close()
    med = statistics.median(n) if n else 0
    return med < 60 and len(n) > 0, f"trust.html@1440x900, ledger centred and replaying, 2 s: {len(n)} recalcs, median {med:.0f} elements (max {max(n or [0])}); budget < 60 (round 2; was < 200)"


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


# hc26r (system): an animation on a scroll or view timeline (the scene primitive, Proof's drain) only moves with the scroll:
# off screen it does no work, so it is not counted (check_static offscreen_pause skips it the same way)
OFFSCREEN = """(() => { const out = []; for (const a of document.getAnimations()) { if (a.playState !== 'running' || (a.timeline && !(a.timeline instanceof DocumentTimeline))) continue;
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
    # round 2 (AR-R2-4): the explorer stops after 8 s with no pointer or focus in it. hc5 (integrate): on Platform §01, its
    # one page now (Home §02 draws Platform's plate, still, and no longer loads arch.js)
    ctx, pg = await V.open_page(b, "platform.html", 1440, 900, init=RAF_COUNTER)
    await pg.evaluate("document.querySelector('#architecture .arch').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.mouse.move(2, 898)
    await V.until(pg, "!!document.querySelector('#architecture .arch.is-ready')", 10000)
    await pg.wait_for_timeout(8500)
    await pg.evaluate(RAF_ZERO); await pg.wait_for_timeout(3000)
    raf = await pg.evaluate("window.__raf")
    await ctx.close()
    arch = raf["by"].get("arch.js", 0)
    ok = ok and arch == 0
    out.append(f"Platform's explorer after 8.5 s idle: arch.js {arch} rAF in 3 s")
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
    ctx, pg = await V.open_page(b, "trust.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-ledger=replay]').scrollIntoView({block: 'center', behavior: 'instant'})")
    ok = await V.until(pg, "document.querySelectorAll('[data-ledger=replay] .lt-rec').length === 9 && document.querySelector('[data-ledger=replay]').classList.contains('lt-ready')", 8000)
    if not ok:
        await ctx.close(); return False, "trust.html@1440x900: the ledger did not mount with its nine records", float("inf")
    await pg.wait_for_timeout(800)
    await pg.evaluate("""(() => { const l = document.querySelector('[data-ledger=replay]'), li = l.querySelectorAll('.lt-rec')[4], id = li.querySelector('.lt-id').textContent.trim();
      const R = window.__ins = { click: 0, sel: 0 }; document.addEventListener('click', e => { if (e.target.closest('.lt-rec')) R.click = performance.now(); }, true);
      const watch = () => { const f = l.querySelector('[data-f="rec"]'); if (li.classList.contains('is-sel') && f && f.textContent.includes(id) && R.click && !R.sel) R.sel = performance.now(); };
      new MutationObserver(watch).observe(l, { subtree: true, attributes: true, childList: true, characterData: true }); })()""")
    await pg.locator("[data-ledger=replay] .lt-rec").nth(4).click()
    await V.until(pg, "window.__ins.sel > 0", 8000)
    r = await pg.evaluate("window.__ins")
    await ctx.close()
    ms = r["sel"] - r["click"] if r["sel"] else None
    return ms is not None and ms <= 800, f"trust.html@1440x900: the fifth record was selected and named in the inspector {'%.0f ms' % ms if ms is not None else 'never (8 s)'} after the click; budget 800 ms (round 2; was 1.5 s)", ms if ms is not None else float("inf")


# hc13r (home, HOME-1): the chart left Home §03 (arrived at from above there); it draws only as Proof's hero, whose entrance
# is the page's opening at load. The watch starts from the document's start, once proof.js has built the ten lanes (before
# the IntersectionObserver's first report can set .is-in), so the whole entrance is timed
PT_HOOK = r"""(() => { const R = window.__pt = { inAt: 0, end: 0, ran: false, pre: null };
  const go = host => { const f = () => { const now = performance.now(); if (!R.inAt && host.classList.contains('is-in')) R.inAt = now;
      if (R.inAt) { const run = host.getAnimations({ subtree: true }).filter(a => a instanceof CSSTransition && a.playState === 'running').length;
        if (run) R.ran = true; else if (R.ran && !R.end) R.end = now; }
      if (!R.end && now - (R.inAt || now) < 6000) requestAnimationFrame(f); }; requestAnimationFrame(f); };
  const mo = new MutationObserver(() => { const h = document.querySelector('#performance [data-proof-chart]');
    if (h && h.querySelectorAll('.pf-lane').length >= 10) { mo.disconnect(); R.pre = h.classList.contains('is-in'); go(h); } });
  mo.observe(document, { subtree: true, childList: true }); })();"""


@check
@timing
async def proof_entrance_time(b):
    ctx = await b.new_context(viewport={"width": 1440, "height": 900})
    await ctx.add_init_script(PT_HOOK)
    pg = await ctx.new_page()
    await pg.goto(f"{V.BASE}/evidence.html", wait_until="load")
    await V.until(pg, "window.__pt && window.__pt.end > 0", 8000)
    r = await pg.evaluate("window.__pt")
    await ctx.close()
    ms = r["end"] - r["inAt"] if r["end"] and r["inAt"] and r["pre"] is False else None
    return ms is not None and ms <= 1300, f"evidence.html@1440x900, the hero at load: the entrance's transitions ran {'%.0f ms' % ms if ms is not None else '(never finished / never ran / revealed before: ' + str(r) + ')'} after .is-in; budget 1.3 s", ms if ms is not None else float("inf")


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


def shift_window(ls):
    """the largest session window of layout shifts without recent input (1 s gap, 5 s cap), as CLS counts them"""
    best = cur = 0.0; s0 = last = -1e9
    for e in sorted(ls, key=lambda e: e["t"]):
        if e["t"] - last > 1000 or e["t"] - s0 > 5000: cur, s0 = 0.0, e["t"]
        cur += e["v"]; last = e["t"]; best = max(best, cur)
    return best


LAND_AT = """(id) => { const p = document.getElementById(id), n = document.querySelector('header.nav') || document.querySelector('.nav');
  return { top: p ? Math.round(p.getBoundingClientRect().top) : null, bar: n ? Math.round(n.getBoundingClientRect().bottom) : null, y: Math.round(scrollY) }; }"""
LAND_SIZES = ((1440, 900, False), (390, 844, True))
# v2x r4: the deeper places (chapter, px into it) and the two desktop widths system measured them at
LAND_DEEP = (("reload", "lc01", 900), ("back", "lc01", 900), ("reload", "governance", 600), ("back", "governance", 600),
             ("reload", "governance", 1200), ("back", "governance", 1200))
LAND_DEEP_SIZES = ((1440, 900), (1280, 800))
LAND_GOTO = """([id, off]) => { const t = document.getElementById(id); scrollTo({ top: t.getBoundingClientRect().top + scrollY + off, behavior: 'instant' }); }"""
LAND_PLACE = """() => { const s = [...document.querySelectorAll('main > section[id]')].filter(c => c.getBoundingClientRect().top < innerHeight / 3).pop();
  return s ? [s.id, Math.round(s.getBoundingClientRect().top)] : [null, null]; }"""


async def land_ctx(b, w, h, touch):
    ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if touch else 1, has_touch=touch, is_mobile=touch)
    await ctx.add_init_script(CLS)
    pg = await ctx.new_page(); pg.set_default_navigation_timeout(60000)
    return ctx, pg


@check
@frames
async def home_landing(b):
    """v2x r3 (home; r3-motion M1, r3-perf moderate): reload and Back land where the reader was, and a deep link lands at
    the bar, without the page jumping (home.js keeps the place; based on home's .shots/v2x/work/home-r3/clsnav.py).
    v2x r4 (system; r4-motion M1): §04's window tightened to 0.01 (the chart's live height is held now), and reload/Back
    at #lc01+900 and #governance+600/+1200 at 1440 and 1280 (window < 0.05). hc13r (home, HOME-1): §04 #proof left Home;
    the reload/Back place and the first deep link are §03 #economics, the same kind of chapter (a drawing that builds on
    screen: proof.js's cost index), the chapter after the lab."""
    ok, out, worst = True, [], 0.0
    for w, h, touch in LAND_SIZES:
        for case in ("reload", "back"):
            ctx, pg = await land_ctx(b, w, h, touch)
            await pg.goto(f"{V.BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(5000)
            # html scrolls smoothly: a scrollTo takes ~1.5 s to arrive, so the place is read 2.5 s after it
            await pg.evaluate("(() => { const p = document.getElementById('economics'); scrollTo(0, p.getBoundingClientRect().top + scrollY - 80); })()")
            await pg.wait_for_timeout(2500)
            before = (await pg.evaluate(LAND_AT, "economics"))["top"]
            if case == "reload": await pg.reload(wait_until="load")
            else:
                await pg.goto(f"{V.BASE}/evidence.html", wait_until="load"); await pg.wait_for_timeout(1500)
                await pg.go_back(wait_until="load")
            await pg.wait_for_timeout(6000)
            at = await pg.evaluate(LAND_AT, "economics"); cls = shift_window(await pg.evaluate("window.__ls || []"))
            await ctx.close()
            worst = max(worst, cls)
            good = at["top"] is not None and abs(at["top"] - 80) <= 2 and cls < 0.01
            ok = ok and good
            out.append(f"{case}@{w}: §03 at {at['top']} (was {before}), CLS {cls:.4f}" + ("" if good else " FAIL"))
    # v2x r4 (system; r4-motion M1): deeper places, past the instruments that build on screen (the swarm lab, the chart,
    # the stream, the chain), whose live boxes the instrument sheets now hold before their engines run. The reader's
    # place is the chapter in the upper third of the screen (as home.js keeps it); after the reload or Back its top is
    # where it was (2 px). Based on system's .shots/v2x/work/system-r4/land.py (32 of 32 exact, CLS <= 0.0035).
    for w, h in LAND_DEEP_SIZES:
        for case, sec, off in LAND_DEEP:
            ctx, pg = await land_ctx(b, w, h, False)
            await pg.goto(f"{V.BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(3500)
            await pg.evaluate(LAND_GOTO, [sec, off]); await pg.wait_for_timeout(1400); await pg.mouse.move(3, 300)
            pid, before = await pg.evaluate(LAND_PLACE)
            if case == "reload": await pg.reload(wait_until="load")
            else:
                await pg.goto(f"{V.BASE}/evidence.html", wait_until="load"); await pg.wait_for_timeout(1200)
                await pg.go_back(wait_until="load")
            await pg.wait_for_timeout(5000)
            after = (await pg.evaluate(LAND_AT, pid))["top"] if pid else None
            cls = shift_window(await pg.evaluate("window.__ls || []"))
            await ctx.close()
            worst = max(worst, cls)
            good = pid is not None and after is not None and abs(after - before) <= 2 and cls < 0.05
            ok = ok and good
            out.append(f"{case} #{sec}{off:+d}@{w}: #{pid} at {after} (was {before}), CLS {cls:.4f}" + ("" if good else " FAIL"))
    for w, h, touch in LAND_SIZES:
        for tid in ("economics", "lc01", "governance"):
            tops, clss = [], []
            for _ in range(5):
                ctx, pg = await land_ctx(b, w, h, touch)
                await pg.goto(f"{V.BASE}/index.html#{tid}", wait_until="load"); await pg.wait_for_timeout(6000)
                at = await pg.evaluate(LAND_AT, tid); cls = shift_window(await pg.evaluate("window.__ls || []"))
                await ctx.close()
                tops.append(None if at["top"] is None or at["bar"] is None else at["top"] - at["bar"]); clss.append(cls)
            worst = max(worst, max(clss))
            good = all(t is not None and abs(t) <= 2 for t in tops) and max(clss) < 0.1
            ok = ok and good
            out.append(f"#{tid}@{w}: target - bar {tops}, CLS max {max(clss):.3f}" + ("" if good else " FAIL"))
    return ok, "; ".join(out) + ("; budget: reload/Back §03 within 2 px of 80 and CLS < 0.01; the deeper places within 2 px of where they"
                                 " were and CLS < 0.05; deep links at the bar (2 px), CLS < 0.1"), worst


CURTAIN = r"""(() => { const E = window.__ev = {}, A = window.__an = {}; const mark = k => { if (!(k in E)) E[k] = Math.round(performance.now()); };
  // v2x r4 (system): when .is-done appears, find the exit's transition and the dial's 'loader-pulse' (it starts in the
  // '100' frame) and read their start times once the compositor has set them (rAF until both are set).
  // award a1 (system): the curtain became the hand-off: the exit is the ground's opacity transition on .loader::before
  // (the dial travels to the globe meanwhile); it exists one frame after .is-done, so it is read in the next frame
  const grab = l => { try {
    const tr = l.getAnimations({ subtree: true }).find(a => a.transitionProperty === 'opacity' && a.effect && a.effect.pseudoElement === '::before');
    const dial = l.querySelector('.loader-dial'), pu = dial && dial.getAnimations().find(a => a.animationName === 'loader-pulse');
    A.found = [!!tr, !!pu];
    const rd = () => { if (tr) { A.tr_start = tr.startTime == null ? null : tr.startTime; A.tr_delay = tr.effect.getTiming().delay; }
      if (pu) A.pulse_start = pu.startTime == null ? null : pu.startTime;
      if ((tr && tr.startTime == null) || (pu && pu.startTime == null)) requestAnimationFrame(rd); };
    rd(); } catch (e) { A.err = String(e); } };
  new MutationObserver(ms => { for (const m of ms) {
    if (m.type === 'attributes') { const el = m.target, c = el.classList; if (c && c.contains('loader')) { for (const k of ['is-complete', 'is-done']) if (c.contains(k)) mark('loader.' + k);
      if (c.contains('is-done') && !A.found) requestAnimationFrame(() => grab(el)); } }
    else for (const n of m.removedNodes) if (n.classList && n.classList.contains('loader')) mark('loader.removed'); } })
    .observe(document, { attributes: true, attributeFilter: ['class'], subtree: true, childList: true }); })();"""


@check
@frames
async def loader_curtain(b):
    """v2x r3 (home, system; r3-perf moderate, r3-motion minor): on a slow phone the loader still ends with its curtain:
    the count reaches 100 (.is-complete), then the curtain lifts (.is-done), before the loader is removed.
    v2x r4 (system; r4-perf moderate): loader.js now adds .is-done in the same task as .is-complete and site.css holds the
    curtain with a 90 ms transition delay that the compositor runs, so the class times are equal by design and measured
    nothing. The beat is read as the visitor sees it: the curtain's transform transition starts (startTime + its delay)
    85-110 ms after the dial's 'loader-pulse' animation, which starts in the frame that shows '100' (both start times are
    the compositor's frame time). Based on system's .shots/v2x/work/system-r4/beat.py (20/20 at 90 ms; a 150 ms long
    task after '100' leaves it at 90; v2 under the same task 183-200).
    award a1 (system, AWARD_BAR L4): the curtain is gone; at '100' the ground (.loader::before) fades by an opacity
    transition delayed by the beat while the dial travels to the overture's globe. Same principle, read on that
    transition (system's .shots/v2x/work/system-a1/beat_handoff.py: 20/20 hand off, beat 90 ms in all 20)."""
    runs = []
    for _ in range(20):
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, has_touch=True, is_mobile=True)
        await ctx.add_init_script(CURTAIN)
        pg = await ctx.new_page(); pg.set_default_navigation_timeout(60000)
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        await pg.goto(f"{V.BASE}/index.html", wait_until="load"); await pg.wait_for_timeout(4500)
        ev = await pg.evaluate("Object.assign({}, window.__ev || {})")
        an = await pg.evaluate("Object.assign({}, window.__an || {})")
        await ctx.close()
        c, d, r = ev.get("loader.is-complete"), ev.get("loader.is-done"), ev.get("loader.removed")
        ts, td, ps = an.get("tr_start"), an.get("tr_delay"), an.get("pulse_start")
        beat = round(ts + td - ps) if None not in (ts, td, ps) else None
        runs.append({"curtain": bool(d and (not r or d <= r)), "beat": beat, "complete_only": bool(c and not d), "found": an.get("found"), "err": an.get("err")})
    beats = [x["beat"] for x in runs if x["beat"] is not None]
    curt, alone = sum(x["curtain"] for x in runs), sum(x["complete_only"] for x in runs)
    off = [x for x in beats if not 85 <= x <= 110]
    unread = [(x["found"], x["err"]) for x in runs if x["beat"] is None]
    ok = curt == len(runs) and not alone and len(beats) == len(runs) and not off
    med = statistics.median(beats) if beats else None
    return ok, (f"20 first visits at 390x844@2, 4x CPU: {curt}/20 hand off before the loader goes, {alone} end at .is-complete alone; "
                f"beat (the ground's fade start + delay - '100' pulse start) median {med} ms, range {min(beats) if beats else None}-{max(beats) if beats else None} ms "
                f"({len(off)} outside 85-110; {len(unread)} unread{': ' + str(unread[:3]) if unread else ''}); "
                "budget: 20/20, none alone, every beat 85-110 ms"), (max(beats) if beats else float("inf"))


# v2x r5 (system; r5-perf issues 2/4): Trust starts its engines after the first paint and ledger.css holds its replay's
# live size, so a reload or Back lands where the reader was. (width, the <main> section's place, px under the top)
TRUST_LAND = ((390, 3, 80), (320, 3, 80), (1024, 3, 80),
              (390, 2, 20), (390, 2, 80), (390, 2, 500), (390, 4, 20), (390, 4, 80), (390, 4, 500))
TRUST_TOP = "(k) => { const el = document.querySelector('main > section:nth-of-type(' + k + ')'); return el ? Math.round(el.getBoundingClientRect().top) : null; }"


@check
@frames
async def trust_landing(b):
    """v2x r5 (system; r5-perf issues 2 and 4): Trust opened mid-way. With §03's top 80 px under the top at 390 and 320
    (touch, DPR 2) and 1024, and §02/§04 at 20, 80 and 500 px at 390, a reload and a Back (via /access.html) each put the
    section's top within 2 px of where it was, and the largest layout-shift window (no recent input) is < 0.01. r4's
    Trust (engines before the paint, the inspector unheld) landed 73 / 109 / 27 px off for §03+80 at 390 / 320 / 1024.
    Based on system's .shots/v2x/work/system-r5/land.py (36/36 exact, CLS <= 0.0001)."""
    ok, out, worst = True, [], 0.0
    for w, k, off in TRUST_LAND:
        touch = w < 600
        for case in ("reload", "back"):
            ctx, pg = await land_ctx(b, w, 844 if touch else 900, touch)
            await pg.goto(f"{V.BASE}/trust.html", wait_until="load"); await pg.wait_for_timeout(2500)
            await pg.evaluate("([k, off]) => { const el = document.querySelector('main > section:nth-of-type(' + k + ')'); if (el) window.scrollTo({top: el.getBoundingClientRect().top + scrollY - off, behavior: 'instant'}); }", [k, off])
            await pg.wait_for_timeout(1200)
            before = await pg.evaluate(TRUST_TOP, k)
            if case == "reload": await pg.reload(wait_until="load")
            else:
                await pg.goto(f"{V.BASE}/access.html", wait_until="load"); await pg.wait_for_timeout(600)
                await pg.go_back(wait_until="load")
            await pg.wait_for_timeout(4000)
            after = await pg.evaluate(TRUST_TOP, k); cls = shift_window(await pg.evaluate("window.__ls || []"))
            await ctx.close()
            worst = max(worst, cls)
            good = None not in (before, after) and abs(after - before) <= 2 and cls < 0.01
            ok = ok and good
            if not good or case == "reload" and (w, k, off) in ((390, 3, 80), (320, 3, 80), (1024, 3, 80)):
                out.append(f"{case} §{k:02d}+{off}@{w}: at {after} (was {before}), CLS {cls:.4f}" + ("" if good else " FAIL"))
    n = len(TRUST_LAND) * 2
    return ok, (f"{n} landings ({', '.join(out)}); worst CLS window {worst:.4f}; "
                "budget: within 2 px of where the section was, CLS < 0.01 in every landing"), worst


# v2x r5 (system; r5-perf issue 3): from DOMContentLoaded, every 50 ms, the CSS transitions running on a [data-reveal]
# target (or inside one) that lies wholly off the screen, on the properties a reveal moves (opacity, transform, a stroke's
# dash, a clip; not colour: Home's swarm lab turns its gate list's colour as it mounts, 300 ms, not a reveal); and when
# site.js first set a reveal up (.will-reveal)
REVEAL_SAMPLER = r"""(() => { const REVEAL_PROPS = /^(opacity|transform|translate|scale|rotate|stroke-dashoffset|clip-path|visibility|filter)$/; const R = window.__rv = { setup: null, worst: 0, at: null, what: [], samples: 0 }; const t0 = performance.now();
  addEventListener('DOMContentLoaded', () => { const iv = setInterval(() => { const t = Math.round(performance.now() - t0); R.samples++;
    if (R.setup === null && document.querySelector('.will-reveal')) R.setup = t;
    const vh = innerHeight; let n = 0; const what = new Set();
    for (const a of document.getAnimations()) { if (a.playState !== 'running' || !REVEAL_PROPS.test(a.transitionProperty || '')) continue; const el = a.effect && a.effect.target;
      const host = el && el.closest && el.closest('[data-reveal]'); if (!host) continue; const r = el.getBoundingClientRect(); if (r.bottom > 0 && r.top < vh) continue;
      n++; what.add((host.closest('section[id]') ? '#' + host.closest('section[id]').id + ' ' : '') + host.tagName.toLowerCase() + ':' + a.transitionProperty); }
    if (n > R.worst) { R.worst = n; R.at = t; R.what = [...what].slice(0, 4); }
    if ((R.setup !== null && t > R.setup + 1500) || t > 8000) clearInterval(iv); }, 50); }); })();"""


@check
@frames
async def offscreen_reveals(b):
    """v2x r5 (system; r5-perf issue 3): a reveal set up below the first screen hides at once, with no fade-out the
    reader cannot see. On /evidence.html, /index.html and /platform.html at 412x823@2 (touch, 4x CPU), sampled every 50 ms
    from DOMContentLoaded until 1.5 s after site.js first sets a reveal up: no CSS transition of a property a reveal moves
    (opacity, transform, a stroke's dash, a clip) runs on an off-screen [data-reveal] target (or inside one) in any sample. r4's site.js ran ~430 such transitions on Proof at 0.6-0.8 s
    (Home ~110, Platform 60+), each a 0.5-0.6 s fade-out off screen. Based on the r5-perf critic's anims5.py."""
    ok, out = True, []
    for path in ("evidence.html", "index.html", "platform.html"):
        ctx = await b.new_context(viewport={"width": 412, "height": 823}, device_scale_factor=2, has_touch=True, is_mobile=True)
        await ctx.add_init_script(REVEAL_SAMPLER)
        pg = await ctx.new_page(); pg.set_default_navigation_timeout(60000)
        cdp = await ctx.new_cdp_session(pg); await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        await pg.goto(f"{V.BASE}/{path}", wait_until="load")
        await V.until(pg, "(() => { const R = window.__rv; return !!R && R.setup !== null && performance.now() > R.setup + 1700; })()", 15000)
        r = await pg.evaluate("Object.assign({}, window.__rv || {})")
        await ctx.close()
        good = r.get("setup") is not None and r.get("worst", 1) == 0
        ok = ok and good
        out.append(f"{path}: reveals set up at {r.get('setup')} ms, {r.get('samples')} samples, at most {r.get('worst')} off-screen reveal transitions"
                   + (f" (at {r.get('at')} ms: {r.get('what')})" if r.get("worst") else "") + ("" if good else " FAIL"))
    return ok, "; ".join(out) + "; budget: 0 in every sample, and the set-up seen", 0


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
