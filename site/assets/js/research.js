/* OpenEXA: the research pages (research.html and the ten notes): the index plate follows the note, a note marks the part being read, the margin plate */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  const plate = $('.rs-plate'), stage = $('#research-figure');
  const rows = $$('.posts-list .post[data-figure-target]');
  if (plate && stage && rows.length) {
    const cap = $('.rs-cap', plate);
    const part = k => $('.figcap-' + k, cap);
    let current = null, swap = 0, since = 0;
    const strip = window.matchMedia('(max-width: 759.98px)');
    let short = false;
    const write = li => { short = strip.matches; ['t', 'h'].forEach(k => {
      const d = li.dataset, el = part(k);
      if (el) el.textContent = (k === 't' && short && d.capS) || d['cap' + k.toUpperCase()] || '';
    }); };
    const docOf = u => { try { const x = new URL(u, location.href); return x.origin + x.pathname.replace(/(\/index)?(\.html)?\/*$/, ''); } catch (err) { return ''; } };
    const act = window.navigation && navigation.activation;
    let hold = (act && act.navigationType === 'traverse' && act.from && rows.find(li => docOf(li.querySelector('a').href) === docOf(act.from.url))) || null;
    function choose(li) {
      hold = null;
      if (!li || li === current || plate.closest('.no-plate')) return;
      if (current) current.classList.remove('is-current');
      current = li; li.classList.add('is-current');
      const fig = li.dataset.figureTarget;
      if (stage.__figure) stage.__figure.show(fig); else stage.dataset.figure = fig;
      since = performance.now();
      clearTimeout(swap);
      if (reduced.matches || !cap) { write(li); return; }
      cap.classList.add('is-swapping');
      swap = setTimeout(() => { write(li); cap.classList.remove('is-swapping'); }, 140);
    }
    current = hold || rows[0]; current.classList.add('is-current'); write(current);
    if (hold) {
      if (stage.__figure) stage.__figure.show(hold.dataset.figureTarget); else stage.dataset.figure = hold.dataset.figureTarget;
      since = performance.now();
      ['wheel', 'touchmove', 'keydown'].forEach(t => window.addEventListener(t, () => { hold = null; }, { passive: true, once: true }));
    }
    rows.forEach(li => {
      li.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') choose(li); });
      li.addEventListener('focusin', () => choose(li));
      li.addEventListener('click', () => {
        const a = li.querySelector('a[data-vt-src]');
        if (a && (li !== current || performance.now() - since < 450)) { a.removeAttribute('data-vt-src'); setTimeout(() => a.setAttribute('data-vt-src', stage.id), 500); }
        choose(li);
      });
    });
    const touch = window.matchMedia('(hover: none)');
    let onList = false;
    $$('.rs-col .posts-list').forEach(l => {
      l.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') onList = true; });
      l.addEventListener('pointerleave', () => { onList = false; });
    });
    const atLine = () => {
      if (hold || (onList && !touch.matches)) return;
      const f = document.activeElement; if (f && f.closest && f.closest('.posts-list .post')) return;
      const line = window.innerHeight * 0.4; let li = rows[0];
      for (const r of rows) { if (r.getBoundingClientRect().top <= line) li = r; else break; }
      choose(li);
    };
    const shelf = plate.closest('.rs-shelf');
    let queued = false, held = () => {};
    const reading = () => {
      queued = false;
      const on = window.scrollY > 24 && rows[0].getBoundingClientRect().top < window.innerHeight * 0.78;
      if (on) held();
      if (shelf) shelf.classList.toggle('is-reading', on);
      atLine();
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(reading); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue, { passive: true });
    requestAnimationFrame(reading);

    const box = $('.rs-caption', plate);
    let measuredW = -1;
    const reserve = () => {
      if (!box || !cap) return;
      if (!strip.matches || plate.closest('.no-plate')) { plate.style.removeProperty('--rs-c-h'); plate.classList.remove('is-two'); if (short) write(current); measuredW = -1; return; }
      const w = box.clientWidth; if (w === measuredW) return; measuredW = w;
      plate.style.setProperty('--rs-c-h', '0px'); plate.classList.remove('is-two');
      let max = 0, min = Infinity;
      rows.forEach(li => { write(li); const h = cap.offsetHeight; max = Math.max(max, h); min = Math.min(min, h); });
      if (max > min * 1.4) plate.classList.add('is-two');
      write(current);
      plate.style.setProperty('--rs-c-h', `${Math.ceil(max)}px`);
    };
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
    const idle = window.requestIdleCallback ? f => window.requestIdleCallback(f, { timeout: 1200 }) : f => setTimeout(f, 300);
    held = () => { if (strip.matches && measuredW < 0) { reserve(); stripH(); } };
    idle(queueReserve);
    if (document.fonts) document.fonts.ready.then(() => idle(() => { measuredW = -1; queueReserve(); }));
  }

  const noFigure = st => {
    if (st.id === 'research-figure') {
      const shelf = st.closest('.rs-shelf'); if (shelf) shelf.classList.add('no-plate');
      $$('.posts-list .post.is-current').forEach(li => li.classList.remove('is-current'));
    }
  };
  document.addEventListener('figure:none', e => noFigure(e.target));
  $$('.figure-stage.no-figure').forEach(noFigure);

  const toc = $$('.toc a[href^="#"]');
  if (toc.length) {
    const heads = toc.map(a => document.getElementById(decodeURIComponent(a.hash.slice(1))));
    const npStage = $('.np-stage'), lits = npStage ? $$('[data-parts]', npStage.closest('.np-plate')) : [];
    const light = id => {
      let any = false;
      lits.forEach(el => { const on = !!id && el.dataset.parts.split(' ').indexOf(id) > -1; el.classList.toggle('is-lit', on); any = any || on; });
      npStage.classList.toggle('has-lit', any);
    };
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
      if (lits.length) light(k > -1 && heads[k] ? heads[k].id : '');
    }
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(mark); } };
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', queue, { passive: true });
    requestAnimationFrame(mark);
  }

  const npRail = $('.np-rail'), art = $('.article-body-section .article');
  if (npRail && art) {
    const first = $('h2', art), end = $('.article-end', art), wide = window.matchMedia('(min-width: 1440px)');
    let placing = false;
    const place = () => {
      placing = false;
      if (!wide.matches || !npRail.getClientRects().length) return;
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
