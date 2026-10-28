"""Budget and timing checks for the v2 site: what the browser has to do, and how soon things happen. These depend on the
machine (GPU, load), so they run locally on the real GPU and are NOT wired into CI this round (.github/workflows/checks.yml
runs check_static, linkcheck_tree, verify_v9 and verify_editorial only; every deterministic invariant lives in verify_v9).

    python tools/serve.py 8125            (in another terminal; any port)
    python tools/verify_budget.py [http://127.0.0.1:8125] [--only name1,name2] [--swiftshader] [--list]

Chromium runs with --use-angle=d3d11 --enable-gpu --ignore-gpu-blocklist (the real GPU); --swiftshader uses CI's software
GL instead, to see what a runner would measure. Run it on an idle machine, once per change: one PASS/FAIL line per check,
exit status 1 if any check failed. Start the PowerShell command with (Get-Process -Id $PID).PriorityClass = 'BelowNormal'.

The checks (the item each one guards in brackets):
  style_ledger         a 2 s trace with the live ledger centred: median UpdateLayoutTree elementCount < 200   [LG1, NV2]
  style_clock          reduced motion, at the footer: one footer-clock text change restyles < 50 elements, on / and /platform.html   [NV2]
  cls_latency          / at 390 with 700 ms of network latency: layout shift (no recent input) sums to < 0.1   [OV9]
  offscreen_work       at the footer of /, /lifecycles.html, /platform.html: no running animation with an off-screen target,
                       and 0 requestAnimationFrame callbacks in 3 s   [NV6, SW4, LG1, LC6, cross: off-screen loops]
  desk_reduced_raf     reduced motion, the desk in view: gap.js runs 0 requestAnimationFrame callbacks in 3 s   [LC2b, LC6]
  headline_after_step  400 ms after each overture index step (1440, 390): every headline word is up (translateY <= 4% of its height)   [OV4]
  desk_warm_time       within 1.2 s of the desk scrolling into view: its clock reads >= 11:00 ET and its strip holds a record   [LC2b]
  inspect_time         the trace's record button: the followed record is selected in the ledger within 1.5 s of the click   [SW2, LG4]
  proof_entrance_time  home 4.1's chart, arrived at from above: its entrance transitions finish within 1.3 s of .is-in   [PF2]
  swarm_pacing         the swarm lab centred at 1440x900@2: frame interval median <= 18 ms, p95 <= 33 ms (idle machine)   [SW4]
  swarm_phone_fps      the lab at 390x844@3, touch, 4x CPU, agents at the slider's maximum: >= 30 fps after 15 s (the
                       governor sheds trails, then population, and says so)   [SW4; needs nav's :has() removal too]
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import asyncio, collections, json, re, statistics, sys, time, traceback
from playwright.async_api import async_playwright
import verify_v9 as V  # shared helpers: open_page, until, scene_rest, the record and events scripts

GPU = ["--use-angle=d3d11", "--enable-gpu", "--ignore-gpu-blocklist"]
SWIFTSHADER = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
CATS = "devtools.timeline,disabled-by-default-devtools.timeline"
# counts requestAnimationFrame callbacks per calling script (assets/js/<file>), before any page script runs
RAF_COUNTER = r"""(() => { const W = window; if (W.__raf) return; const R = W.__raf = { n: 0, by: {} };
  const who = () => { const m = ((new Error()).stack || '').match(/assets\/js\/([\w.-]+\.js)/); return m ? m[1] : 'other'; };
  const o = W.requestAnimationFrame.bind(W);
  W.requestAnimationFrame = function (cb) { const k = who(); return o(function (t) { R.n++; R.by[k] = (R.by[k] || 0) + 1; return cb(t); }); }; })();"""
CLS = r"""(() => { const S = window.__ls = []; try { new PerformanceObserver(l => l.getEntries().forEach(e => { if (!e.hadRecentInput) S.push({ t: Math.round(e.startTime), v: e.value,
  src: (e.sources || []).slice(0, 2).map(s => s.node && s.node.nodeType === 1 ? s.node.tagName + '.' + String(s.node.className || '').split(' ')[0] : '?') }); })).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} })();"""
CHECKS = []
def check(fn): CHECKS.append(fn); return fn


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
    return med < 200 and len(n) > 0, f"index.html@1440x900, ledger centred, 2 s: {len(n)} recalcs, median {med:.0f} elements (max {max(n or [0])}); budget < 200"


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


@check
async def offscreen_work(b):
    out, ok = [], True
    for path in ("index.html", "lifecycles.html", "platform.html"):
        ctx, pg = await V.open_page(b, path, 1440, 900, init=RAF_COUNTER)
        await pg.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})"); await pg.wait_for_timeout(1500)
        anims = await pg.evaluate(OFFSCREEN)
        await pg.evaluate("(() => { window.__raf.n = 0; window.__raf.by = {}; })()"); await pg.wait_for_timeout(3000)
        raf = await pg.evaluate("window.__raf")
        await ctx.close()
        ok = ok and not anims and raf["n"] == 0
        out.append(f"{path}: {len(anims)} off-screen animations {sorted(set(anims))[:4]}, {raf['n']} rAF callbacks {raf['by']}")
    return ok, "at the footer (1440x900): " + "; ".join(out) + "; budget 0 and 0"


@check
async def desk_reduced_raf(b):
    ctx, pg = await V.open_page(b, "lifecycles.html", 1440, 900, reduced=True, init=RAF_COUNTER)
    await pg.evaluate("document.querySelector('[data-gap]').scrollIntoView({block: 'center', behavior: 'instant'})"); await pg.wait_for_timeout(1500)
    await pg.evaluate("(() => { window.__raf.n = 0; window.__raf.by = {}; })()"); await pg.wait_for_timeout(3000)
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
async def headline_after_step(b):
    out, ok = [], True
    for w, h in ((1440, 900), (390, 844)):
        ctx, pg = await V.open_page(b, "index.html", w, h)
        await pg.wait_for_timeout(800)
        for i in range(1, 5):
            r = await pg.evaluate(HEADLINE, i)
            if not r["n"] or r["low"]: ok = False; out.append(f"{w}x{h} step 0{i}: {len(r['low'])} of {r['n']} words still low {r['low'][:3]}")
            await V.scene_rest(pg, i)
        await ctx.close()
    return ok, "400 ms after each index step at 1440 and 390: " + ("every headline word is up" if ok else "; ".join(out))


@check
async def desk_warm_time(b):
    ctx, pg = await V.open_page(b, "lifecycles.html", 1440, 900)
    r = await pg.evaluate("""async () => { document.querySelector('[data-gap]').scrollIntoView({block: 'center', behavior: 'instant'}); const t0 = performance.now();
      const ok = () => { const m = (document.querySelector('[data-gap-time]').textContent || '').match(/(\\d\\d):(\\d\\d)/); return !!m && (+m[1] * 60 + +m[2]) >= 660 && document.querySelectorAll('.desk-log li').length >= 1; };
      while (!ok() && performance.now() - t0 < 1200) await new Promise(r => setTimeout(r, 50));
      return { ok: ok(), ms: Math.round(performance.now() - t0), time: document.querySelector('[data-gap-time]').textContent, log: document.querySelectorAll('.desk-log li').length }; }""")
    await ctx.close()
    return r["ok"], f"lifecycles.html@1440x900: {r['ms']} ms after the reveal the desk reads {r['time']} with {r['log']} record(s); budget >= 11:00 ET and >= 1 record within 1.2 s"


@check
async def inspect_time(b):
    ctx, pg = await V.open_page(b, "index.html", 1440, 900)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await V.until(pg, "+document.querySelector('[data-sw-inflight]').textContent.replace(/\\D/g, '') > 0", 25000, 200)
    await pg.evaluate("(() => { const s = document.querySelector('[data-sw-strict]'); s.value = '0'; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    await pg.locator("[data-sw-follow]").click()
    has = await V.until(pg, """(() => { if (document.querySelector('[data-sw-log] [data-sw-rec]')) return 'button';
        return /record #[0-9a-f]{4}/.test((document.querySelector('[data-sw-log]') || {}).textContent || '') ? 'text' : ''; })()""", 60000, 250)
    if has != "button":
        await ctx.close(); return False, f"index.html@1440x900: the trace's ledger row is no record button ({has or 'nothing after 60 s'}; needs SW2 + LG4)"
    await pg.evaluate("""(() => { const R = window.__ins = { click: 0, sel: 0 }; document.addEventListener('click', e => { if (e.target.closest('[data-sw-rec]')) R.click = performance.now(); }, true);
      const watch = () => { const li = document.querySelector('[data-ledger=live] .lt-rec.is-followed'); if (li && li.classList.contains('is-sel') && R.click && !R.sel) R.sel = performance.now(); };
      new MutationObserver(watch).observe(document.querySelector('[data-ledger=live]'), { subtree: true, attributes: true, attributeFilter: ['class'] }); })()""")
    await pg.locator("[data-sw-log] [data-sw-rec]").click()
    await V.until(pg, "window.__ins.sel > 0", 8000)
    r = await pg.evaluate("window.__ins")
    await ctx.close()
    ms = r["sel"] - r["click"] if r["sel"] else None
    return ms is not None and ms <= 1500, f"index.html@1440x900: the followed record was selected {'%.0f ms' % ms if ms is not None else 'never (8 s)'} after the click; budget 1.5 s"


@check
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
    return ms is not None and ms <= 1300, f"index.html@1440x900, from above: the entrance's transitions ran {'%.0f ms' % ms if ms is not None else '(never finished / never ran)'} after .is-in; budget 1.3 s"


@check
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
    return med <= 18 and p95 <= 33, f"index.html@1440x900@2, lab centred, 4 s: {len(iv)} frames, median {med:.1f} ms, p95 {p95:.1f} ms (quality {q}); budget <= 18 / <= 33 ms (idle machine)"


@check
async def swarm_phone_fps(b):
    ctx, pg = await V.open_page(b, "index.html", 390, 844, dpr=3, touch=True)
    cdp = await ctx.new_cdp_session(pg)
    await pg.evaluate("document.querySelector('[data-swarm-live]').scrollIntoView({block: 'center', behavior: 'instant'})")
    await pg.wait_for_timeout(1500)
    await pg.evaluate("(() => { const s = document.querySelector('[data-sw-n]'); s.value = s.max; s.dispatchEvent(new Event('input', {bubbles: true})); s.dispatchEvent(new Event('change', {bubbles: true})); })()")
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
    await pg.wait_for_timeout(15000)  # the governor sheds trails, then population, in steps
    r = await pg.evaluate("""() => new Promise(res => { let n = 0; const t0 = performance.now(); const f = t => { n++; if (t - t0 < 4000) requestAnimationFrame(f); else res({ n, ms: t - t0 }); }; requestAnimationFrame(f); })""")
    out = await pg.evaluate("(document.querySelector('[data-sw-n-out]') || {}).textContent || ''")
    await cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    await ctx.close()
    fps = r["n"] * 1000 / max(1, r["ms"])
    return fps >= 30, f"index.html@390x844@3, touch, 4x CPU, agents at the slider's maximum, after 15 s: {fps:.1f} fps (agents output {out!r}); budget >= 30 fps"


async def main():
    base, only, listing = V.parse_args(sys.argv[1:])
    if base: V.BASE = base
    names = [c.__name__ for c in CHECKS]
    if listing:
        for n in names: print(n)
        return 0
    unknown = [n for n in (only or []) if n not in names]
    if unknown: print("unknown check(s):", unknown, "- known:", ", ".join(names)); return 2
    args = SWIFTSHADER if "--swiftshader" in sys.argv else GPU
    failed = []
    async with async_playwright() as p:
        b = await p.chromium.launch(args=args)
        print(f"verify_budget against {V.BASE} ({'SwiftShader' if args is SWIFTSHADER else 'GPU: ' + ' '.join(GPU)})", flush=True)
        for c in [c for c in CHECKS if only is None or c.__name__ in only]:
            t0 = time.monotonic()
            try:
                ok, msg = await c(b)
            except Exception as e:
                ok, msg = False, "error: " + "".join(traceback.format_exception_only(type(e), e)).strip()
            print(f"{'PASS' if ok else 'FAIL'} {c.__name__}: {msg} ({time.monotonic() - t0:.0f}s)", flush=True)
            if not ok: failed.append(c.__name__)
        await b.close()
    print(f"BUDGET CHECKS {'FAILED: ' + ', '.join(failed) if failed else 'PASSED'}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
