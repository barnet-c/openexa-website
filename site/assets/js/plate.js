/* OpenEXA: Platform's plates (page-only): the hero plate, and §05's dial (hc13r, below).
   The hero plate draws one decision at first paint in CSS (platform.css), once:
   three proposals reach the Execution Council, one is refused, two cross the boundary and settle. "Replay" restarts
   those CSS animations; it stays hidden without JavaScript and under reduced motion, where the plate is a still.
   award a3 (4K): the lines that draw in (the boundary, the two rails, the refusal's spur) are non-scaling hairlines like
   every other stroke on the plate; a non-scaling dash is measured on screen, so their dash is the drawing's scale
   (--dr-k, as site.js gives the reveal draw-ins; without it they draw in the drawing's own units). The long straight
   rules (the counterparties rule, the rails, the brackets) move by under a device pixel onto whole rows or columns. */
(function () {
  'use strict';
  const fig = document.querySelector('[data-plate="stack"]');
  const svg = fig && fig.querySelector('.hp-art svg');
  if (!svg || !svg.getScreenCTM) return;
  const rules = [...svg.querySelectorAll('.pm-floor path, .pm-down, .pl-br path')];
  let queued = 0, anims = null;
  function fit() {
    queued = 0;
    const m = svg.getScreenCTM();
    if (!m) return;
    const k = Math.hypot(m.a, m.b), d = window.devicePixelRatio || 1;
    if (!k) return;
    svg.style.setProperty('--dr-k', Math.max(1, k * 1.02 + 0.02).toFixed(3));
    fig.classList.add('is-k');
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
    if (!anims && typeof fig.getAnimations === 'function') { anims = played(); release(); }
  }
  // the plate's played animations; hc25's scroll scene (platform.css: the stack comes apart on scroll) runs on the page's
  // scroll timeline, so it is never let go or replayed
  const played = () => fig.getAnimations({ subtree: true }).filter((a) => a.timeline === document.timeline);
  const later = () => { if (!queued) queued = requestAnimationFrame(fit); };
  later();
  // each element's animations let go once all of that element's own have finished (each ends on the plate's own style):
  // while any finished one holds its end state the browser keeps the plate on a layer at a fractional offset, and every
  // hairline spreads over three device rows. a3 let them go at the sequence's end (~3.8 s); a4: as each part lands, so the
  // rules drawn first are whole while the proposals still run (a grab at 2.5 s read 216/166/166/216; now two full rows)
  const release = () => {
    const all = anims;
    if (!all || !all.length) return;
    const by = new Map();
    all.forEach((a) => { const el = a.effect && a.effect.target; if (!by.has(el)) by.set(el, []); by.get(el).push(a); });
    by.forEach((own) => Promise.all(own.map((a) => a.finished)).then(() => own.forEach((a) => a.cancel()), () => {}));
    Promise.all(all.map((a) => a.finished)).then(later, () => {});
  };
  if ('ResizeObserver' in window) new ResizeObserver(later).observe(svg);
  else window.addEventListener('resize', later);
  if (document.fonts && document.fonts.status !== 'loaded') document.fonts.ready.then(later);
  const btn = fig.querySelector('[data-plate-replay]');
  if (!btn || typeof fig.getAnimations !== 'function') return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const sync = () => { btn.hidden = reduce.matches; };
  sync();
  if (reduce.addEventListener) reduce.addEventListener('change', sync);
  // again(): the whole drawing from its first line (Replay), or, with a test, only the parts that pass it, begun .12 s
  // before the first of them moves (their delays were timed to follow the plate's own entrance)
  const again = (part) => {
    fit(); if (!anims || !anims.length) anims = played();
    const run = part ? anims.filter((a) => part(a.effect && a.effect.target)) : anims;
    const lead = part ? Math.max(0, Math.min(...run.map((a) => a.effect.getComputedTiming().delay)) - 120) : 0;
    run.forEach((a) => { a.cancel(); a.play(); if (lead) a.currentTime = lead; });
    release();
  };
  btn.addEventListener('click', () => again());
  // hc30r (system's SYS-2): arriving by a page turn the first screen lands whole (site.js ends the entrances that began with
  // the page), so the plate's one decision was never seen by a visitor who came from another page. After a turn the three
  // proposals run once more over the standing plate (the layers, the boundary and the labels do not redraw), by the site's
  // rule for an act (OXA.actOnce: well in view, after the turn has landed, never under reduced motion, never after a touch)
  const OXA = window.OXA = window.OXA || {};
  let armed = false;
  const decision = () => requestAnimationFrame(() => requestAnimationFrame(() => again((el) => el && el.closest && el.closest('.pm-rail'))));
  const arm = () => { if (armed) return; armed = true; const args = [fig, decision, { paused: () => window.scrollY > 8 }]; if (OXA.actOnce) OXA.actOnce(...args); else (OXA.q = OXA.q || []).push(args); };
  if (OXA.byTurn || document.documentElement.classList.contains('vt-in')) arm();
  else window.addEventListener('pagereveal', (e) => { if (e.viewTransition) arm(); });
})();

/* Platform §05 (hc13r PLAT-1): the dial is the control. Its four labels are one radio group (arrow keys, Home, End; the
   site's focus ring): a mode swings the pointer to its detent (.32 s on --ease-move; at once under reduced motion), lights
   that detent and marks the mode's row in the table (aria-current); "Emergency halt" drops the pointer onto the halt
   shutter, the shorter way round, and any mode can be chosen again. The pointer starts where the drawing has it (Fully
   automatic). Without JavaScript the dial is the still drawing and the table says the rest. */
(function () {
  'use strict';
  const fig = document.querySelector('#modes .sec-plate--dial');
  const labs = fig && fig.querySelector('.hp-labs');
  const ptr = fig && fig.querySelector('.sp-ptr');
  if (!labs || !ptr) return;
  const opts = [...labs.querySelectorAll('.hp-lab[data-m]')].sort((a, b) => a.dataset.m - b.dataset.m);
  const marks = [...fig.querySelectorAll('svg [data-m]')];
  const rows = [...document.querySelectorAll('#modes .ledger > tbody > tr')];
  if (opts.length !== 4) return;
  const ANG = [0, 60, 120, 240]; // clockwise from the drawn pointer: Auto-with-approval, Manual, the halt shutter
  let cur = 0;
  function show(m) {
    opts.forEach((o, i) => { o.setAttribute('aria-checked', String(i === m)); o.tabIndex = i === m ? 0 : -1; });
    marks.forEach((p) => p.classList.toggle('is-on', +p.dataset.m === m));
    rows.forEach((r, i) => { if (i === m) r.setAttribute('aria-current', 'true'); else r.removeAttribute('aria-current'); });
  }
  function pick(m) {
    const t = ANG[m] + 360 * Math.round((cur - ANG[m]) / 360); // the shorter way round from where the pointer is
    if (t !== cur) { cur = t; ptr.style.transform = `rotate(${t}deg)`; }
    show(m);
  }
  labs.removeAttribute('aria-hidden');
  labs.setAttribute('role', 'radiogroup');
  labs.setAttribute('aria-label', 'Operating mode');
  opts.forEach((o, i) => {
    o.setAttribute('role', 'radio');
    o.addEventListener('click', () => { pick(i); o.focus({ preventScroll: true }); });
  });
  labs.addEventListener('keydown', (e) => {
    const i = opts.indexOf(e.target);
    if (i < 0) return;
    if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); pick(i); return; }
    const n = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: opts.length - 1 }[e.key];
    if (n === undefined) return;
    e.preventDefault();
    const k = (n + opts.length) % opts.length;
    pick(k); opts[k].focus();
  });
  fig.classList.add('is-live');
  show(0);
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
