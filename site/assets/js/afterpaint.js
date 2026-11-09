/* OpenEXA: start a page's scripts after its first paint (system; r3, Lifecycles). The page paints from its HTML and
   CSS first; this tag's data-after-paint lists the scripts it would otherwise defer, in their order. They are added
   (async = false: in order, as the tags were) once the first-contentful-paint entry arrives; 5 s is a net, a hidden tab
   (or a prerender) starts at once, and a browser without paint timing starts on 'load'. Two phases, as on Home (home.js,
   the same code): loader.js, story.js and site.js at the paint; the rest on 'oxa:loaded' (site.js sends it at once on a
   page without a loader), with 2.5 s as a net. So a page's first full layout and style pass run in the frame the
   browser lays out anyway, not in a script task after the paint (Lifecycles, mobile Lighthouse: TBT 107-118 ms -> 14-22).
   check_static's script budget reads data-after-paint. Without JavaScript nothing changes: the page is complete. */
(function () {
  'use strict';
  const me = document.currentScript, root = document.documentElement;
  // (hc14, integrate) the footer's legal fold before the first paint, as on the pages that load site.js at once: made
  // after the paint, it took ~190 px out of the footer, so a page reloaded at its foot jumped (CLS .04-.06). site.js
  // keeps the same code (and skips a fold that exists); without JavaScript the disclosures stay open
  const disc = document.querySelector('.footer .disc');
  if (disc && !disc.closest('details')) {
    const d = document.createElement('details'), s = document.createElement('summary');
    d.className = 'footer-legal'; s.textContent = 'Legal & disclosures';
    disc.before(d); d.append(s, disc);
  }
  // (hc26r) a tap during a page turn: the turn ends and the tap reaches what is under it (site.js keeps the same code)
  const OXA = window.OXA = window.OXA || {};
  if (!OXA.tapThrough) {
    OXA.tapThrough = true;
    let tap = null;
    document.addEventListener('pointerdown', e => {
      const vt = document.activeViewTransition;
      tap = null;
      if (!vt || e.target !== root || e.button !== 0) return;
      tap = { x: e.clientX, y: e.clientY };
      try { vt.skipTransition(); } catch (err) { }
    }, true);
    document.addEventListener('click', e => {
      if (!tap || e.target !== root) return;
      const { x, y } = tap;
      tap = null;
      requestAnimationFrame(() => {
        const el = document.elementFromPoint(x, y), t = el && el.closest('a[href], button, summary, label, input, select, textarea, [role="button"], [tabindex]');
        if (!t || t === root) return;
        if (t.matches('input, select, textarea, [tabindex]:not(a, button, summary, label, [role="button"])')) t.focus(); else t.click();
      });
    }, true);
  }
  // (hc26r) the drawing that travels with a page turn (site.js keeps the same code; whichever runs first serves)
  if (!OXA.figs) {
    const figs = OXA.figs = [], all = s => Array.from(document.querySelectorAll(s));
    const figSet = (el, v) => { el.style.setProperty('view-transition-name', v); figs.push(el); };
    const figClear = () => figs.splice(0).forEach(el => el.style.removeProperty('view-transition-name'));
    const docOf = u => { try { const x = new URL(u, location.href); return x.origin + x.pathname.replace(/(\/index)?(\.html)?\/*$/, ''); } catch (err) { return ''; } };
    const inView = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; };
    const srcOf = a => a && (a.matches('.vt-src') ? a : a.querySelector('.vt-src') || (a.dataset.vtSrc ? document.getElementById(a.dataset.vtSrc) : null));
    const pair = v => { try { if (v === undefined) return JSON.parse(sessionStorage.getItem('oxa-vt') || 'null'); sessionStorage.setItem('oxa-vt', JSON.stringify(v)); } catch (err) { } return null; };
    let lastLink = null;
    document.addEventListener('click', e => { lastLink = (e.target.closest && e.target.closest('a[href]')) || null; }, true);
    addEventListener('pageswap', e => {
      figClear();
      const a = e.activation;
      if (!e.viewTransition || !a || !a.entry) return;
      const to = docOf(a.entry.url), me = docOf(location.href), back = a.navigationType === 'traverse', p = pair();
      const home = back && p && p.to === me && p.from === to;
      all('[data-vt-dest]').forEach(d => { if (!home || !inView(d)) figSet(d, 'none'); });
      if (back) return;
      const src = lastLink && docOf(lastLink.href) === to ? srcOf(lastLink) : null;
      if (!src || !inView(src)) return;
      figSet(src, 'fig');
      pair({ from: me, to });
    });
    addEventListener('pagereveal', e => {
      figClear();
      const a = window.navigation && navigation.activation;
      if (!e.viewTransition || !a) return;
      all('[data-vt-dest]').forEach(d => { if (!inView(d)) figSet(d, 'none'); });
      // a drawing that travelled in lands as itself: the dest's own entrance does not play again (blog's hc26r ask)
      e.viewTransition.ready.then(() => { if (document.getAnimations().some(x => x.effect && x.effect.pseudoElement === '::view-transition-old(fig)')) all('[data-vt-dest]').forEach(d => d.getAnimations({ subtree: true }).forEach(x => x.cancel())); }, () => { });
      if (a.navigationType !== 'traverse' || !a.from) return;
      const from = docOf(a.from.url), p = pair();
      if (!p || p.from !== docOf(location.href) || p.to !== from) return;
      const src = all('a[href]').filter(l => docOf(l.href) === from).map(srcOf).find(x => x && inView(x));
      if (!src) return;
      all('[data-vt-dest]').forEach(d => figSet(d, 'none'));
      figSet(src, 'fig');
    });
    addEventListener('pageshow', e => { if (e.persisted) figClear(); });
  }
  const list = ((me && me.getAttribute('data-after-paint')) || '').split(/\s+/).filter(Boolean);
  if (!list.length) return;
  if (list.some(src => /story\.js$/.test(src))) root.classList.add('story-wait');
  const FIRST = /(?:^|\/)(?:loader|story|site)\.js$/;
  const add = (src) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = false; // in order, as the tags were
    if (/story\.js$/.test(src)) s.onerror = () => root.classList.add('story-failed');
    document.body.appendChild(s);
  };
  let started = false, later = false;
  const rest = () => { if (later) return; later = true; list.filter(src => !FIRST.test(src)).forEach(add); };
  const start = () => {
    if (started) return;
    started = true;
    list.filter(src => FIRST.test(src)).forEach(add);
    if (root.classList.contains('is-loaded')) setTimeout(rest, 0);
    else document.addEventListener('oxa:loaded', () => setTimeout(rest, 0), { once: true });
    setTimeout(rest, 2500);
  };
  if (document.visibilityState === 'hidden') { start(); return; }
  if (window.PerformanceObserver && (PerformanceObserver.supportedEntryTypes || []).includes('paint')) {
    const po = new PerformanceObserver(entries => {
      if (entries.getEntriesByName('first-contentful-paint').length) { po.disconnect(); setTimeout(start, 0); }
    });
    po.observe({ type: 'paint', buffered: true });
    setTimeout(start, 5000);
  } else if (document.readyState === 'complete') start();
  else addEventListener('load', start, { once: true });
})();
