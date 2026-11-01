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
