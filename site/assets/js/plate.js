/* OpenEXA: Platform's plates (page-only): the hero plate, the console (§02), the dial (§05), the pipeline (§03).
   The hero plate (hc31r PLAT-1) is a camera on the run: runplate.js moves the run's marks along the plate's authored paths, and this
   file writes the tag's second line, which reads the layer the tagged proposal is on (the model's own words while the Council
   checks it and when it is refused). When the page scrolls and the plate hands over to the explorer the marks step aside
   (.is-away; platform.css fades them in 120 ms). The long straight rules (the floor, the rails, the brackets) move by under a
   device pixel onto whole rows or columns (award a3, 4K). As authored the plate is the finished still. */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {};
  const fig = document.querySelector('[data-plate="stack"]');
  const svg = fig && fig.querySelector('.hp-art svg');
  if (!svg || !svg.getScreenCTM) return;
  const rules = [...svg.querySelectorAll('.pm-floor path, .pm-down, .pl-br path')];
  let queued = 0;
  function fit() {
    queued = 0;
    const m = svg.getScreenCTM();
    if (!m) return;
    const k = Math.hypot(m.a, m.b), d = window.devicePixelRatio || 1;
    if (!k) return;
    rules.forEach((p) => { p.style.translate = ''; });
    // the browser paints the <svg> box from a whole device pixel: its drawing moves with that snap
    const s = svg.getBoundingClientRect(), sx = (s.left + window.scrollX) * d, sy = (s.top + window.scrollY) * d;
    const at = rules.map((p) => {
      const r = p.getBoundingClientRect(), v = r.height > r.width, w = Math.round(parseFloat(getComputedStyle(p).strokeWidth) * d);
      const c = v ? (r.right + window.scrollX) * d - sx + Math.round(sx) : (r.top + window.scrollY) * d - sy + Math.round(sy);
      const want = w % 2 ? Math.floor(c) + 0.5 : Math.round(c);
      return [v, (want - c) / d / k];
    });
    rules.forEach((p, i) => { const [v, u] = at[i]; if (Math.abs(u) > 1e-4) p.style.translate = v ? `${u.toFixed(4)}px 0` : `0 ${u.toFixed(4)}px`; });
  }
  const later = () => { if (!queued && window.scrollY < 8) queued = requestAnimationFrame(fit); };
  later();
  if ('ResizeObserver' in window) new ResizeObserver(later).observe(svg);
  else window.addEventListener('resize', later);
  const away = () => fig.classList.toggle('is-away', window.scrollY > 8);
  window.addEventListener('scroll', away, { passive: true });
  away();
  // the tag reads the layer: 01 to 03 on the way down, the Council's check and a refusal in the model's words, 05 to 08 on a rail
  const LAYER = ['Signal intelligence', 'Model layer', 'Domain agents', 'Execution Council', 'Routing layer', 'Execution layer', 'MCP server', 'Authentication'];
  const tag = fig.querySelector('[data-run="tag"]'), line = tag && tag.querySelector('[data-pl-line]');
  let on = false, seen = '';
  function live() {
    const run = OXA.run;
    if (on || !run || !line) return;
    on = true;
    run.subscribe((S) => {
      const i = S.ti, pl = svg.__plate;
      if (i < 0) return;
      const ph = S.ph[i];
      let t = S.tagLine;
      if (pl && ph !== 1 && ph !== 4) {
        const list = ph ? pl.paths.rail : pl.paths.approach, l = list[(ph ? S.lane[i] : S.k[i]) % list.length];
        const f = ph === 0 ? S.u[i] : ph === 2 ? S.u[i] * 0.8 : 0.8 + 0.2 * S.u[i], y = l.a[Math.min(48, Math.max(0, Math.round(f * 48))) * 2 + 1];
        const n = ph === 0 ? (y < 46 ? 0 : y < 78 ? 1 : 2) : y < 170 ? -1 : y < 208 ? 4 : y < 240 ? 5 : y < 272 ? 6 : y < 318 ? 7 : 8;
        t = n < 0 ? '04 Approved' : n > 7 ? 'Settled' : `0${n + 1} ${LAYER[n]}`;
      }
      if (t !== seen) { line.textContent = seen = t; tag.classList.toggle('is-no', S.tagTone === 'no'); }
    }, fig); // (the figure: run.js keeps one subscriber an element, and the svg is the plate engine's)
  }
  if (OXA.run) live(); else document.addEventListener('oxa:run', live);
})();

/* Platform §02 (hc31r PLAT-2): the run's console. The picture is stage.js on OXA.run (mounted by markup; the hand on the
   Council is the stage's own). This file keeps the three counts (in flight, settled, rejected: the run's own sums since
   arrival), the hand's read-out, Follow, and the emergency halt. The halt is the run's: pressed here it stops births on
   every page (no new proposal is born, those in flight finish, the ledger stands), the header says Halted everywhere,
   and one record is sealed; "Resume" here or the header's play glyph on any page brings the run back. One gesture, one
   record; reading is never recorded. Without JavaScript the stage is its still and the bar is not shown. */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {}, doc = document;
  const root = doc.querySelector('#swarm .swarm-live');
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const fig = $('figure'), input = $('[data-sw-strict]'), ro = $('[data-stage-ro]'), fb = $('[data-sw-follow]'), hb = $('[data-sw-halt]'), ban = $('[data-sw-banner]'), sayEl = $('[data-sw-say]');
  const outs = [$('[data-sw-inflight]'), $('[data-sw-recorded]'), $('[data-sw-rejected]')];
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)');
  const fmt = (n) => n.toLocaleString('en-US'), put = (n, t) => { if (n && n.textContent !== t) n.textContent = t; };
  const say = (t) => { if (sayEl) sayEl.textContent = t; };
  let on = false;
  function start() {
    const run = OXA.run;
    if (on || !run || !fig || !fb || !hb) return;
    on = true;
    /* the hand's read-out, beside the scale the stage draws */
    const read = () => {
      if (!input) return;
      const pct = +input.value, l = (1 - pct / 100).toFixed(2);
      input.setAttribute('aria-valuetext', `${pct}% rejected, risk limit ${l}`);
      if (!ro) return;
      put(ro.children[0], pct > 0 ? `approves ${100 - pct}%` : 'approves every proposal');
      put(ro.children[1], pct > 0 ? `rejects risk > ${l}` : '');
    };
    if (input) {
      input.addEventListener('input', () => { read(); if (ro) ro.classList.add('is-moved'); });
      if (ro && run.records().some((r) => r.ev === 'Council strictness')) ro.classList.add('is-moved');
    }
    /* follow: the next proposal born takes the tag, on every camera; a proposal picked on the stage does the same */
    let fk = null, spoke = 0;
    const follow = (k) => {
      fk = k; spoke = 0;
      fb.setAttribute('aria-pressed', String(k != null));
      if (k == null) { put(fb, 'Follow a proposal'); return; }
      put(fb, 'Stop following'); spoke = 1; say(`Following ${run.prop(k).id}.`);
    };
    fb.addEventListener('click', () => { if (fk != null) { run.follow(null); follow(null); } else { run.follow('next'); follow(run.sample().tag); } });
    fig.addEventListener('stage:follow', (e) => follow(e.detail));
    const track = (S) => {
      if (fk == null) return;
      const p = run.prop(fk), e = S.t - p.tb;
      if (e >= p.ta + 0.5 && spoke < 2) { spoke = 2; say(`${p.id}: ${p.rej ? 'rejected' : 'approved'} by the council.`); }
      if (S.t > p.te) { if (spoke < 3) say(`${p.id}: ${p.rej ? 'its rejection is recorded' : 'settled'}.`); fk = null; fb.setAttribute('aria-pressed', 'false'); put(fb, S.halted ? 'Halted · no new proposals' : 'Follow another'); }
    };
    /* the halt */
    let halted = null, timer = 0;
    const render = (S) => {
      const c = S.counts;
      put(outs[0], fmt(c.f)); put(outs[1], fmt(c.s)); put(outs[2], fmt(c.r));
      put(ban, S.halted ? `Halted · no new proposals · ${c.f ? fmt(c.f) + ' in flight, draining' : 'nothing in flight'}` : '');
      track(S);
    };
    const state = () => {
      const S = run.sample(), h = S.halted;
      if (input && !fig.dataset.stage) input.value = String(Math.round(run.strict() * 100)); // until the camera is mounted (its hand keeps the two in step from then on)
      read();
      if (h !== halted) {
        const first = halted === null;
        halted = h;
        hb.setAttribute('aria-pressed', String(h)); put(hb, h ? 'Resume' : 'Emergency halt');
        root.classList.toggle('is-halted', h);
        if (fk == null) { fb.disabled = h; put(fb, h ? 'Halted · no new proposals' : 'Follow a proposal'); }
        if (!first) say(h ? `Halted. No new proposals. ${fmt(S.counts.f)} in flight, draining.` : 'Resumed. New proposals.');
        // with nothing moving (reduced motion, a paused run) the drained picture is drawn once the last proposal has landed
        clearTimeout(timer);
        if (h) timer = setTimeout(() => { if (!rm.matches && !run.sample().paused) return; if (OXA.stage && OXA.stage.get(fig)) { OXA.stage.hold(fig, true); OXA.stage.hold(fig, false); } render(run.sample()); }, 9200);
      }
      render(S);
    };
    hb.addEventListener('click', () => {
      const S = run.sample();
      if (S.halted) { run.resume(); run.record('Emergency halt', 'off · resumed'); } else { run.halt(); run.record('Emergency halt', `on · ${fmt(S.counts.f)} in flight`); }
    });
    doc.addEventListener('oxa:run', state);
    state();
    run.subscribe(render, root);
    // the camera is mounted when the section comes within a screen (stage.js's mount for a figure added later): a load spends
    // nothing on a canvas two screens down
    // 3 s without the engine (a failed request): the console shows its still (swarm.css .no-stage) and keeps asking, slowly
    let tries = 0;
    const mount = () => { if (fig.dataset.stage) return; if (!OXA.stage) { if (++tries === 50) root.classList.add('no-stage'); setTimeout(mount, tries < 50 ? 60 : 1000); return; } root.classList.remove('no-stage'); fig.dataset.stage = fig.dataset.stageLater || 'wide'; OXA.stage.mount(fig); };
    if ('IntersectionObserver' in window) { const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); mount(); } }, { rootMargin: '100% 0px' }); io.observe(root); } else mount();
    try { const s = JSON.parse(sessionStorage.getItem('oxa:run')); if (s && s.follow != null && run.sample().tag === s.follow) follow(s.follow); } catch (e) { }
  }
  if (OXA.run) start(); else doc.addEventListener('oxa:run', start);
})();

/* Platform §05 (hc13r PLAT-1): the dial is the control. Its four labels are one radio group (arrow keys, Home, End; the
   site's focus ring): a mode swings the pointer to its detent (.32 s on --ease-move; at once under reduced motion), lights
   that detent and marks the mode's row in the table (aria-current); "Emergency halt" drops the pointer onto the halt
   shutter, the shorter way round, and any mode can be chosen again. The pointer starts where the drawing has it (Fully
   automatic). Without JavaScript the dial is the still drawing and the table says the rest.
   hc31r (PLAT-2): one halt. The dial's "Emergency halt" and the console's button show and set the same state, the run's:
   choosing it here halts the run (one record), choosing another mode while halted resumes it (one record), and a halt
   or a resume made anywhere else (the console, the header on any page) moves the pointer. The other three modes stay
   illustrative. */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {};
  const fig = document.querySelector('#modes .sec-plate--dial');
  const labs = fig && fig.querySelector('.hp-labs');
  const ptr = fig && fig.querySelector('.sp-ptr');
  if (!labs || !ptr) return;
  const opts = [...labs.querySelectorAll('.hp-lab[data-m]')].sort((a, b) => a.dataset.m - b.dataset.m);
  const marks = [...fig.querySelectorAll('svg [data-m]')];
  const rows = [...document.querySelectorAll('#modes .ledger > tbody > tr')];
  if (opts.length !== 4) return;
  const ANG = [0, 60, 120, 240]; // clockwise from the drawn pointer: Auto-with-approval, Manual, the halt shutter
  let cur = 0, mode = 0, last = 0; // last: the mode the dial stood on before a halt (a resume made elsewhere returns to it)
  function show(m) {
    mode = m;
    if (m !== 3) last = m;
    opts.forEach((o, i) => { o.setAttribute('aria-checked', String(i === m)); o.tabIndex = i === m ? 0 : -1; });
    marks.forEach((p) => p.classList.toggle('is-on', +p.dataset.m === m));
    rows.forEach((r, i) => { if (i === m) r.setAttribute('aria-current', 'true'); else r.removeAttribute('aria-current'); });
  }
  function pick(m) {
    const t = ANG[m] + 360 * Math.round((cur - ANG[m]) / 360); // the shorter way round from where the pointer is
    if (t !== cur) { cur = t; ptr.style.transform = `rotate(${t}deg)`; }
    show(m);
  }
  // a mode chosen by the visitor: the pointer at once, and the run's halt where the choice rests on it or leaves it. Arrow
  // keys pass over modes on their way, so a choice made by arrows is taken 700 ms after the last one, or when focus leaves
  // (the hand's rule: one gesture, one record); a click, Space or Enter is taken at once
  let pend = 0;
  const apply = () => {
    clearTimeout(pend); pend = 0;
    const run = OXA.run;
    if (!run) return;
    const S = run.sample();
    if (mode === 3 && !S.halted) { run.halt(); run.record('Emergency halt', `on · ${S.counts.f.toLocaleString('en-US')} in flight`); }
    else if (mode !== 3 && S.halted) { run.resume(); run.record('Emergency halt', 'off · resumed'); }
  };
  function choose(m, keys) {
    pick(m);
    clearTimeout(pend); pend = 0;
    if (keys) pend = setTimeout(apply, 700); else apply();
  }
  labs.addEventListener('focusout', () => { if (pend) apply(); });
  labs.removeAttribute('aria-hidden');
  labs.setAttribute('role', 'radiogroup');
  labs.setAttribute('aria-label', 'Operating mode');
  opts.forEach((o, i) => {
    o.setAttribute('role', 'radio');
    o.addEventListener('click', () => { choose(i); o.focus({ preventScroll: true }); });
  });
  labs.addEventListener('keydown', (e) => {
    const i = opts.indexOf(e.target);
    if (i < 0) return;
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); choose(i); return; }
    const n = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: opts.length - 1 }[e.key];
    if (n === undefined) return;
    e.preventDefault();
    const k = (n + opts.length) % opts.length;
    choose(k, true); opts[k].focus();
  });
  fig.classList.add('is-live');
  show(0);
  // the run's state, from wherever it was changed
  const sync = () => { const run = OXA.run; if (!run || pend) return; const h = run.sample().halted; if (h && mode !== 3) pick(3); else if (!h && mode === 3) pick(last); };
  document.addEventListener('oxa:run', sync);
  sync();
})();

/* Platform §03 (hc19, the director's 4.2): the pipeline acts once by the site's rule (site.js OXA.actOnce), as Trust §02 and
   Proof §01: well in view, .is-run plays one pass in CSS (platform.css). Whole at rest without JavaScript, under reduced
   motion and on phones (the drawing is the list there, never in view). */
(function () {
  'use strict';
  const pipe = document.querySelector('#pipeline .pipe-fig'), OXA = window.OXA = window.OXA || {};
  if (!pipe) return;
  const run = () => pipe.classList.add('is-run');
  if (OXA.actOnce) OXA.actOnce(pipe, run); else (OXA.q = OXA.q || []).push([pipe, run]);
})();
