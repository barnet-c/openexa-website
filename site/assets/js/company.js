/* OpenEXA — the Company page's manifesto (company.html; loaded after site.js). */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------- manifesto — words light up as the paragraph passes through the viewport ---------------- */
  $$('[data-manifesto]').forEach(el => {
    const words = [];
    const walk = (node) => {
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(' ')); return; }
            const w = document.createElement('span'); w.className = 'mw'; w.textContent = p; words.push(w); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) walk(child);
      });
    };
    walk(el);
    if (prefersReduced) { words.forEach(w => w.classList.add('is-lit')); return; }
    let lit = -1, raf = 0;
    const update = () => {
      raf = 0;
      const r = el.getBoundingClientRect(), vh = window.innerHeight;
      // progress 0 → 1 as the block travels from 85% of the viewport up to 30%
      const p = Math.min(1, Math.max(0, (vh * 0.85 - r.top) / (r.height + vh * 0.55)));
      const n = Math.round(p * words.length);
      if (n === lit) return; lit = n;
      words.forEach((w, i) => w.classList.toggle('is-lit', i < n));
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    window.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('resize', onScroll); update();
  });
})();
