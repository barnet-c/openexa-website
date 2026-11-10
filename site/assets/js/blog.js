/* OpenEXA: the Blog's script (the index's plates beside its lists, the bundles under the H1; a long read's margin plate) */
(function () {
  'use strict';
  const idx = document.querySelector('.blog-idx'), lib = document.querySelector('.lib-plate');
  if (idx && lib) {
    const name = a => (a && idx.contains(a)) ? a.getAttribute('href').slice(1) : '';
    const lit = k => { if (k) lib.setAttribute('data-lit', k); else lib.removeAttribute('data-lit'); };
    idx.addEventListener('pointerover', e => { if (e.pointerType !== 'touch') lit(name(e.target.closest && e.target.closest('a'))); });
    idx.addEventListener('pointerleave', () => lit(idx.contains(document.activeElement) ? name(document.activeElement) : ''));
    idx.addEventListener('focusin', e => lit(name(e.target.closest && e.target.closest('a'))));
    idx.addEventListener('focusout', e => { if (!idx.contains(e.relatedTarget)) lit(''); });
  }
  if (document.body.classList.contains('blog-page')) window.addEventListener('pageswap', e => { if (e.viewTransition) try { e.viewTransition.types.add('lift'); } catch (err) { } });
  const mp = document.querySelector('.post-mp-in');
  const figs = mp ? document.querySelectorAll('.blog-article figure') : [];
  if (figs.length && 'IntersectionObserver' in window) {
    const seen = new Set();
    const rest = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) seen.add(e.target); else seen.delete(e.target); });
      mp.classList.toggle('is-rest', seen.size > 0);
    }, { rootMargin: '-10% 0px -12% 0px' });
    figs.forEach(f => rest.observe(f));
  }
  const boxes = Array.from(document.querySelectorAll('[data-blog-follow], [data-blog-turn]'));
  if (!boxes.length || !('IntersectionObserver' in window)) return;
  let wide, touch;
  const USER = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  const doc = u => u.replace(/(\/index)?(\.html)?\/*$/, '');
  const from = (() => { try { const a = window.navigation && navigation.activation; return a && a.navigationType === 'traverse' && a.from && a.from.url ? doc(new URL(a.from.url).pathname) : ''; } catch (err) { return ''; } })();

  function follow(box, choose) {
    const list = box.querySelector('.blog-register');
    const rows = list ? Array.from(list.children) : [];
    if (!rows.length) return null;
    let current = -1, onList = false, near = false, queued = false, keyed = false, hold = false;
    const set = i => { if (i !== current) { current = i; choose(i, rows); } };
    const keyFocus = () => { const f = document.activeElement; return !!f && list.contains(f) && f.matches(':focus-visible'); };
    rows.forEach((li, i) => {
      li.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch' && wide.matches && !keyed) set(i); });
      li.addEventListener('focusin', () => { if (!wide.matches) return; keyed = keyFocus(); set(i); });
      li.addEventListener('click', () => { if (!wide.matches) return; keyed = false; box.classList.add('is-go'); set(i); void box.offsetWidth; box.classList.remove('is-go'); });
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
      if (hold || !near || !wide.matches || (onList && !touch.matches) || keyFocus()) return;
      const line = window.innerHeight * 0.4; let k = 0;
      for (let i = 0; i < rows.length; i++) { if (rows[i].getBoundingClientRect().top <= line) k = i; else break; }
      set(k);
    };
    const queue = () => { if (!queued) { queued = true; requestAnimationFrame(atLine); } };
    new IntersectionObserver(es => { near = es[0].isIntersecting; if (near) queue(); }).observe(list);
    window.addEventListener('scroll', queue, { passive: true });
    const k = from ? rows.findIndex(li => { const a = li.querySelector('a'); return !!a && doc(a.pathname) === from; }) : -1;
    if (k >= 0 && wide.matches) {
      set(k); hold = true;
      const free = () => { hold = false; USER.forEach(t => window.removeEventListener(t, free, true)); };
      USER.forEach(t => window.addEventListener(t, free, { capture: true, passive: true }));
    }
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
        panel.classList.add('is-live');
      });
      if (set && wide.matches && !box.querySelector('.blog-register > li.is-current')) box.querySelector('.blog-register > li').classList.add('is-current');
    } else if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      box.classList.add('js-turn');
      follow(box, i => box.style.setProperty('--turn', (-6 * i) + 'deg'));
    }
  }

  const io = new IntersectionObserver(es => es.forEach(e => {
    if (e.isIntersecting) { io.unobserve(e.target); start(e.target); }
  }), { rootMargin: '50% 0px' });
  boxes.forEach(b => io.observe(b));
})();
