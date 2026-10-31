/* OpenEXA: the research pages (research.html and the ten notes; group "research", v2x).
   Index: one plate beside the list (#research-figure, a figure.js stage) shows the figure of the note pointed at or
   focused, and while the list scrolls (pointer elsewhere, or a touch screen), of the note at the reading line. Its
   caption, written from that note's own words, comes from the row (data-cap-n/-t/-d/-h, written by
   tools/build_research.py) and changes with it. The row whose figure is
   on the plate is marked (.is-current). Without JavaScript the plate is not drawn (research.css) and the list is v2's.
   Notes: "In this note" marks the part being read (.is-on, aria-current), which v2 had styled but no longer set.
   No inline script or style (CSP); nothing here is needed to read a page. */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  /* ---------- the index: the plate follows the note ---------- */
  const plate = $('.rs-plate'), stage = $('#research-figure');
  const rows = $$('.posts-list .post[data-figure-target]');
  if (plate && stage && rows.length) {
    const cap = $('.rs-cap', plate);
    const part = k => $('.figcap-' + k, cap);
    let current = null, swap = 0;
    const write = li => ['n', 't', 'd', 'h'].forEach(k => { const el = part(k); if (el) el.textContent = li.dataset['cap' + k.toUpperCase()] || ''; });
    function choose(li) {
      if (!li || li === current || plate.closest('.no-plate')) return; // no plate (no WebGL): no row is marked
      if (current) current.classList.remove('is-current');
      current = li; li.classList.add('is-current');
      const fig = li.dataset.figureTarget;
      if (stage.__figure) stage.__figure.show(fig); else stage.dataset.figure = fig; // before the stage starts: its first formation
      // the caption changes with the figure: a short cross-fade (none under reduced motion)
      clearTimeout(swap);
      if (reduced.matches || !cap) { write(li); return; }
      cap.classList.add('is-swapping');
      swap = setTimeout(() => { write(li); cap.classList.remove('is-swapping'); }, 140);
    }
    // the plate starts on the first note (its figure and caption are in the markup); mark that row
    current = rows[0]; current.classList.add('is-current');
    rows.forEach(li => {
      li.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') choose(li); });
      li.addEventListener('focusin', () => choose(li));
    });
    // while the list scrolls, the note at the reading line (about two-fifths down the screen) is the plate's: always on
    // touch screens; with a mouse, unless the pointer is on the list (then the row pointed at decides)
    const touch = window.matchMedia('(hover: none)');
    let onList = false;
    $$('.rs-col .posts-list').forEach(l => {
      l.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') onList = true; });
      l.addEventListener('pointerleave', () => { onList = false; });
    });
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(es => {
        if (onList && !touch.matches) return;
        es.forEach(e => { if (e.isIntersecting) choose(e.target); });
      }, { rootMargin: '-40% 0px -59% 0px' });
      rows.forEach(li => io.observe(li));
    }
    // phones: the plate is a strip at the foot of the screen; it comes up once the list is being read (research.css)
    const shelf = plate.closest('.rs-shelf');
    if (shelf) {
      let queued = false;
      const reading = () => { queued = false; shelf.classList.toggle('is-reading', rows[0].getBoundingClientRect().top < window.innerHeight * 0.78); };
      window.addEventListener('scroll', () => { if (!queued) { queued = true; requestAnimationFrame(reading); } }, { passive: true });
      reading();
    }
  }

  /* ---------- a stage that cannot draw (figure.js 'figure:none'): no caption for a figure that is not there ---------- */
  const noFigure = st => {
    if (st.id === 'research-figure') { // the list takes the width, and no row is marked as on a plate that is not drawn
      const shelf = st.closest('.rs-shelf'); if (shelf) shelf.classList.add('no-plate');
      $$('.posts-list .post.is-current').forEach(li => li.classList.remove('is-current'));
    }
    else { const host = st.closest('section'); if (host) host.classList.add('no-figure-cap'); }
  };
  document.addEventListener('figure:none', e => noFigure(e.target));
  $$('.figure-stage.no-figure').forEach(noFigure);

  /* ---------- a note: "In this note" marks the part being read ---------- */
  const toc = $$('.toc a[href^="#"]');
  if (toc.length) {
    const heads = toc.map(a => document.getElementById(decodeURIComponent(a.hash.slice(1))));
    let on = -2, queued = false;
    function mark() {
      queued = false;
      const line = window.innerHeight * 0.34;
      let k = -1;
      heads.forEach((h, i) => { if (h && h.getBoundingClientRect().top < line) k = i; });
      if (k === on) return;
      on = k;
      toc.forEach((a, i) => {
        a.parentElement.classList.toggle('is-on', i === k);
        if (i === k) a.setAttribute('aria-current', 'location'); else a.removeAttribute('aria-current');
      });
    }
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(mark); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue, { passive: true });
    mark();
  }
})();
