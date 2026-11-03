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
    // award a2: 'k', a figure's colour key (note 09: green premium, white discount), between the two; empty for the others
    const write = li => ['t', 'k', 'h'].forEach(k => {
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
    let queued = false, held = () => {};
    const reading = () => {
      queued = false;
      // cut (1 Nov): the hero is shorter, so the first row now starts on a phone's first screen; the strip still waits
      // for the reader's first scroll, so it never covers the first screen
      const on = window.scrollY > 24 && rows[0].getBoundingClientRect().top < window.innerHeight * 0.78;
      if (on) held(); // the strip's slots are measured before it first comes up (a3)
      if (shelf) shelf.classList.toggle('is-reading', on);
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
    /* award a2: a colour key (note 09) stands on the strip where the strip has the room: it shares the title's held
       slot, at its foot (.rs-k-fits, research.css), and only if that leaves the strip's height as it was (2 px of
       rounding allowed), so a swap still moves nothing and the strip is no taller for the other nine notes */
    const slots = [['t', '--rs-t-h'], ['h', '--rs-h-h']];
    let measuredW = -1;
    const reserve = () => {
      if (!box || !cap) return;
      if (!strip.matches || plate.closest('.no-plate')) { slots.forEach(([, v]) => plate.style.removeProperty(v)); plate.classList.remove('rs-k-fits'); measuredW = -1; return; }
      const w = box.clientWidth; if (w === measuredW) return; measuredW = w;
      slots.forEach(([, v]) => plate.style.setProperty(v, '0px'));
      plate.classList.add('rs-k-fits'); // measured as it would stand
      const max = { t: 0, h: 0 }; let tk = 0;
      rows.forEach(li => {
        write(li); slots.forEach(([k]) => { const el = part(k); if (el) max[k] = Math.max(max[k], el.offsetHeight); });
        const t = part('t'), k = part('k'); if (t && k && k.textContent) tk = Math.max(tk, t.offsetHeight + k.offsetHeight); // as the title's next line
      });
      write(current);
      const hold = th => slots.forEach(([k, v]) => plate.style.setProperty(v, `${Math.ceil(k === 't' ? th : max[k])}px`));
      plate.classList.remove('rs-k-fits'); hold(max.t);
      if (tk) { const h0 = plate.offsetHeight; plate.classList.add('rs-k-fits'); hold(Math.max(max.t, tk)); if (plate.offsetHeight > h0 + 2) { plate.classList.remove('rs-k-fits'); hold(max.t); } }
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
    /* award a3 (a3-dev): the ten captions are written and measured once the page is idle, not in its first frames (a
       phone's start: ~20 ms of forced layout at 4x); the strip is off the screen until the list is read, and the first
       scroll that brings it up measures first if idle has not come (reading(), above), so it never grows on screen */
    const idle = window.requestIdleCallback ? f => window.requestIdleCallback(f, { timeout: 1200 }) : f => setTimeout(f, 300);
    held = () => { if (strip.matches && measuredW < 0) { reserve(); stripH(); } };
    idle(queueReserve);
    if (document.fonts) document.fonts.ready.then(() => idle(() => { measuredW = -1; queueReserve(); }));
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

  /* ---------- a note: the margin plate (award a3) stands from the first part head to the end mark ----------
     research.css shows it from 1440 px; here its rail is cut to that span (--np-t, --np-b, from the text's own box), again
     whenever the text's box changes (fonts in, a new width). It is hidden until placed, so it never moves on screen, and
     it fades in (.is-in) once half the hero has left the screen, so no screen shows the drawing twice */
  const npRail = $('.np-rail'), art = $('.article-body-section .article');
  if (npRail && art) {
    const first = $('h2', art), end = $('.article-end', art), wide = window.matchMedia('(min-width: 1440px)');
    let placing = false;
    const place = () => {
      placing = false;
      if (!wide.matches || !npRail.getClientRects().length) return; // below 1440 (no layout read) or not shown
      const a = art.getBoundingClientRect();
      npRail.style.setProperty('--np-t', `${Math.max(0, Math.round(first ? first.getBoundingClientRect().top - a.top : 0))}px`);
      npRail.style.setProperty('--np-b', `${Math.max(0, Math.round(end ? a.bottom - end.getBoundingClientRect().top : 0))}px`);
      npRail.classList.add('is-set');
    };
    const queuePlace = () => { if (!placing) { placing = true; requestAnimationFrame(place); } };
    if ('ResizeObserver' in window) new ResizeObserver(queuePlace).observe(art); else window.addEventListener('resize', queuePlace, { passive: true });
    wide.addEventListener('change', queuePlace);
    queuePlace();
    const hero = $('.article-hero');
    if (hero && 'IntersectionObserver' in window) {
      new IntersectionObserver(([e]) => npRail.classList.toggle('is-in', e.intersectionRatio < 0.5), { threshold: [0, 0.5, 1] }).observe(hero);
    } else npRail.classList.add('is-in');
  }
})();
