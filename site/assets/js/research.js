/* OpenEXA: the research pages (research.html and the ten notes; group "research", v2x).
   Index: one plate beside the list (#research-figure, a figure.js stage) shows the figure of the note pointed at or
   focused, and while the list scrolls (pointer elsewhere, or a touch screen), of the note at the reading line. Its
   caption comes from the row (data-cap-t, what is drawn, shown on phones only; data-cap-h, the hedge; written by
   tools/build_research.py) and changes with it (cut, 1 Nov: the caption paragraphs and "Fig. NN" are gone). The row whose figure is
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
    const write = li => ['t', 'h'].forEach(k => {
      const el = part(k); if (el) el.textContent = li.dataset['cap' + k.toUpperCase()] || '';
    });
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
    // the plate starts on the first note (its figure and hedge are in the markup); mark that row, write its caption
    current = rows[0]; current.classList.add('is-current'); write(current);
    rows.forEach(li => {
      li.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') choose(li); });
      li.addEventListener('focusin', () => choose(li));
    });
    // while the list scrolls, the note at the reading line (about two-fifths down the screen) is the plate's: always on
    // touch screens; with a mouse, unless the pointer is on the list (then the row pointed at decides). r1: read from the
    // rows' positions on each scrolled frame (the last row whose top has passed the line), not from a thin band the rows
    // cross: a jump (Page Down, End, a link, a hard flick) carried rows past the band in one frame and left the plate on
    // an earlier note's figure, even after the last note
    const touch = window.matchMedia('(hover: none)');
    let onList = false;
    $$('.rs-col .posts-list').forEach(l => {
      l.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') onList = true; });
      l.addEventListener('pointerleave', () => { onList = false; });
    });
    const atLine = () => {
      if (onList && !touch.matches) return;
      // a row reached with the keyboard keeps the plate while the page scrolls it into view (else two rows were marked)
      const f = document.activeElement; if (f && f.closest && f.closest('.posts-list .post')) return;
      const line = window.innerHeight * 0.4; let li = rows[0];
      for (const r of rows) { if (r.getBoundingClientRect().top <= line) li = r; else break; }
      choose(li);
    };
    // phones: the plate is a strip at the foot of the screen; it comes up once the list is being read (research.css)
    const shelf = plate.closest('.rs-shelf');
    let queued = false;
    const reading = () => {
      queued = false;
      // cut (1 Nov): the hero is shorter, so the first row now starts on a phone's first screen; the strip still waits
      // for the reader's first scroll, so it never covers the first screen
      if (shelf) shelf.classList.toggle('is-reading', window.scrollY > 24 && rows[0].getBoundingClientRect().top < window.innerHeight * 0.78);
      atLine();
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(reading); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue, { passive: true });
    requestAnimationFrame(reading); // first read in the frame, not while the page is still being parsed and laid out

    /* r2 (r2-motion): on phones the strip is in the page's flow (it settles under the list), and the notes' captions
       differ in length (Fig. 09's three-part hedge), so a swap moved the page below it, and the lines inside the strip.
       The caption's title and hedge are each held at the height of the longest at this width (--rs-t-h, --rs-h-h;
       research.css), so the strip, and every line in it, keeps its place: each caption is written, measured and the
       current one put back in one task, so nothing is painted in between. Again when the width changes and once the
       fonts are in */
    const box = $('.rs-caption', plate), strip = window.matchMedia('(max-width: 759.98px)');
    const slots = [['t', '--rs-t-h'], ['h', '--rs-h-h']];
    let measuredW = -1;
    const reserve = () => {
      if (!box || !cap) return;
      if (!strip.matches || plate.closest('.no-plate')) { slots.forEach(([, v]) => plate.style.removeProperty(v)); measuredW = -1; return; }
      const w = box.clientWidth; if (w === measuredW) return; measuredW = w;
      slots.forEach(([, v]) => plate.style.setProperty(v, '0px'));
      const max = { t: 0, h: 0 };
      rows.forEach(li => { write(li); slots.forEach(([k]) => { const el = part(k); if (el) max[k] = Math.max(max[k], el.offsetHeight); }); });
      write(current);
      slots.forEach(([k, v]) => plate.style.setProperty(v, `${Math.ceil(max[k])}px`));
    };
    // r4 (r4-a11y m2): the strip's height, so a row focused from the keyboard scrolls clear of it (research.css
    // scroll-margin-bottom). Read after the slots are held; the strip's height also follows the screen's height
    const rail = plate.closest('.rs-rail');
    const stripH = () => {
      if (!shelf || !rail) return;
      if (strip.matches && !plate.closest('.no-plate')) shelf.style.setProperty('--rs-strip-h', `${Math.ceil(rail.offsetHeight)}px`);
      else shelf.style.removeProperty('--rs-strip-h');
    };
    let rq = false;
    const queueReserve = () => { if (!rq) { rq = true; requestAnimationFrame(() => { rq = false; reserve(); stripH(); }); } };
    window.addEventListener('resize', queueReserve, { passive: true });
    strip.addEventListener('change', queueReserve);
    queueReserve();
    if (document.fonts) requestAnimationFrame(() => document.fonts.ready.then(() => { measuredW = -1; queueReserve(); }));
  }

  /* ---------- a stage that cannot draw (figure.js 'figure:none'): no caption for a figure that is not there ---------- */
  const noFigure = st => {
    if (st.id === 'research-figure') { // the list takes the width, and no row is marked as on a plate that is not drawn
      const shelf = st.closest('.rs-shelf'); if (shelf) shelf.classList.add('no-plate');
      $$('.posts-list .post.is-current').forEach(li => li.classList.remove('is-current'));
    }
    else { const host = st.closest('section'); if (host) host.classList.add(st.classList.contains('has-still') ? 'still-cap' : 'no-figure-cap'); } // (r2: the index hero keeps its still; a1: so does every note, and its hedge shows beside it)
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
    requestAnimationFrame(mark);
  }
})();
