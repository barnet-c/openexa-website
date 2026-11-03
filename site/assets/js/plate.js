/* OpenEXA: Platform's hero plate (page-only). The plate draws one decision at first paint in CSS (platform.css), once:
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
    if (!anims && typeof fig.getAnimations === 'function') { anims = fig.getAnimations({ subtree: true }); release(); }
  }
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
  btn.addEventListener('click', () => { fit(); if (!anims || !anims.length) anims = fig.getAnimations({ subtree: true }); anims.forEach((a) => { a.cancel(); a.play(); }); release(); });
})();
