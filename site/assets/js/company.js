/* OpenEXA — the Company page (company.html; loaded after site.js and figure.js).
   1. The manifesto: its words are written in reading order, once, as the paragraph arrives (under half a second), and then
      stay. v2 tied each word to the scroll position, which left the paragraph half grey for as long as it was on
      screen; v2x: nothing stays half-lit after it arrives. In view at load, under reduced motion or without
      IntersectionObserver: all lit at once (first paint is final, SYSTEM 5.1).
   2. The hero plate's caption follows the mode (figure.js switches the formation and the mode caption; the plate
      label was the same for all three). */
(function () {
  'use strict';
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------- manifesto ---------------- */
  $$('[data-manifesto]').forEach(el => {
    const vh = window.innerHeight;
    const r = el.getBoundingClientRect();
    const inView = r.top < vh && r.bottom > 0;
    const words = [];
    const walk = (node) => {
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p.replace(/[^ ]+/g, ' ') || ' ')); return; }
            const w = document.createElement('span'); w.className = 'mw'; w.textContent = p; words.push(w); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) walk(child);
      });
    };
    walk(el);
    const all = () => words.forEach(w => w.classList.add('is-lit'));
    if (prefersReduced || inView || !('IntersectionObserver' in window)) { el.classList.add('is-written'); all(); return; }
    const step = Math.min(10, 450 / Math.max(1, words.length)); // the whole paragraph in at most ~0.45 s, settled by ~0.7 s
    const io = new IntersectionObserver(entries => {
      if (!entries.some(e => e.isIntersecting)) return;
      io.disconnect();
      el.classList.add('is-writing');
      words.forEach((w, i) => { w.style.transitionDelay = `${Math.round(i * step)}ms`; });
      requestAnimationFrame(() => { all(); setTimeout(() => { el.classList.replace('is-writing', 'is-written'); words.forEach(w => { w.style.transitionDelay = ''; }); }, words.length * step + 400); });
    }, { rootMargin: '0px 0px 8% 0px' }); // starts just before it scrolls in
    io.observe(el);
  });

  /* ---------------- the hero plate's caption follows the mode ---------------- */
  const label = document.querySelector('[data-plate-label]');
  $$('.company-modes [data-plate]').forEach(b => b.addEventListener('click', () => { if (label) label.textContent = b.dataset.plate; }));
})();
