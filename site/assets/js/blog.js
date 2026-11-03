/* OpenEXA: the blog index (group "blog"; award a2). The collections' chips filter this file drove went with the cut
   (1 Nov); this is what the index does now.
   - Financial markets research: one plate beside the register shows the drawing of the post pointed at or focused,
     and while the list scrolls (pointer elsewhere, or a touch screen), of the post at the reading line, as Research's
     plate follows its notes (research.js). The row whose drawing is on the plate is marked (.is-current).
   - Market structure & economics: the rings turn a step for each paper pointed at, focused or read (v2 turned them
     under the pointer). Not under reduced motion.
   Only where the plate stands beside the list (641 px and up: tablets and desks). Without JavaScript the plate shows
   the first row's drawing and the rings turn on hover (blog.css). No inline script or style (CSP); nothing here is
   needed to read.
   Nothing runs while the page is first laid out (a2 Lighthouse: a media query read at load forced the page's first
   style pass inside this file's task, ahead of the first paint): a list is set up when it comes within half a screen. */
(function () {
  'use strict';
  const boxes = Array.from(document.querySelectorAll('[data-blog-follow], [data-blog-turn]'));
  if (!boxes.length || !('IntersectionObserver' in window)) return;
  let wide, touch;

  // rows: the list's links' items; choose(i): show row i. Pointer and focus choose at once; otherwise the row whose
  // top has passed the reading line (two-fifths down the screen) is chosen on each scrolled frame while the list is
  // on screen (research.js r1: read positions, not a band the rows cross, so a jump cannot skip a row)
  function follow(box, choose) {
    const list = box.querySelector('.blog-register');
    const rows = list ? Array.from(list.children) : [];
    if (!rows.length) return null;
    let current = -1, onList = false, near = false, queued = false, keyed = false;
    const set = i => { if (i !== current) { current = i; choose(i, rows); } };
    // a row the keyboard reached keeps the plate until the pointer really moves: the page scrolling a focused row into
    // view slides other rows under a resting pointer, and that is not a choice (a2 probe: focus on row 4, plate on 7)
    const keyFocus = () => { const f = document.activeElement; return !!f && list.contains(f) && f.matches(':focus-visible'); };
    rows.forEach((li, i) => {
      li.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch' && wide.matches && !keyed) set(i); });
      li.addEventListener('focusin', () => { if (!wide.matches) return; keyed = keyFocus(); set(i); });
    });
    list.addEventListener('pointermove', e => {
      if (!keyed || e.pointerType === 'touch' || !(e.movementX || e.movementY)) return;
      keyed = false; const li = e.target.closest && e.target.closest('li'); const i = rows.indexOf(li);
      if (i >= 0 && wide.matches) set(i);
    });
    list.addEventListener('focusout', e => { if (!list.contains(e.relatedTarget)) keyed = false; });
    list.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') onList = true; });
    list.addEventListener('pointerleave', () => { onList = false; });
    const atLine = () => {
      queued = false;
      if (!near || !wide.matches || (onList && !touch.matches) || keyFocus()) return;
      const line = window.innerHeight * 0.4; let k = 0;
      for (let i = 0; i < rows.length; i++) { if (rows[i].getBoundingClientRect().top <= line) k = i; else break; }
      set(k);
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(atLine); } };
    new IntersectionObserver(es => { near = es[0].isIntersecting; if (near) queue(); }).observe(list);
    window.addEventListener('scroll', queue, { passive: true });
    return set;
  }

  function start(box) {
    if (!wide) {
      wide = window.matchMedia('(min-width: 641px)');
      touch = window.matchMedia('(hover: none)');
    }
    if (box.hasAttribute('data-blog-follow')) {
      const panel = box.querySelector('.blog-panel');
      const plates = panel ? Array.from(panel.querySelectorAll('.bpn')) : [];
      if (!plates.length) return;
      const set = follow(box, (i, rows) => {
        rows.forEach((li, j) => li.classList.toggle('is-current', j === i));
        plates.forEach((p, j) => p.classList.toggle('is-on', j === i));
        panel.classList.add('is-live'); // from the first change on, a plate that arrives engraves its green line again
      });
      // the plate starts on the first row (its drawing is in the markup); mark that row where the plate is beside it
      if (set && wide.matches) box.querySelector('.blog-register > li').classList.add('is-current');
    } else if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      box.classList.add('js-turn');
      // six degrees a paper, v2's own turn under the pointer
      follow(box, i => box.style.setProperty('--turn', (-6 * i) + 'deg'));
    }
  }

  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { io.unobserve(e.target); start(e.target); }
  }), { rootMargin: '50% 0px' });
  boxes.forEach(b => io.observe(b));
})();
