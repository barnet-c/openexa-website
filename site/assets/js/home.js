/* OpenEXA: Home's start-up (home group; index.html only). The page paints from its HTML and CSS first. The scripts in
   this tag's data-after-paint (in order, async = false) are added once the first-contentful-paint entry arrives (its
   time is when the frame was presented); 5 s is a net, a hidden tab starts at once, no paint timing starts on 'load'.
   Two phases: loader, story and site at the paint; the instruments below the fold on 'oxa:loaded' (2.5 s net), so the
   overture's set-up does not share the main thread with six engines that draw nothing above the fold. .story-wait while
   story.js is due, .story-failed if it fails. check_static's script budget reads data-after-paint too. */
(function () {
  'use strict';
  // §06 on phones: the chain shows records 01-04 and a control for all eight; an edit or 'Alter record 03' opens it
  const chain = document.querySelector('[data-chain]'), more = chain && chain.querySelector('[data-chain-more]');
  if (more) {
    const set = (open) => {
      chain.classList.toggle('is-folded', !open);
      more.setAttribute('aria-expanded', String(open));
      more.textContent = open ? 'Show the first four records' : 'Show all eight records';
    };
    set(false); more.hidden = false;
    more.addEventListener('click', () => set(chain.classList.contains('is-folded')));
    chain.addEventListener('input', () => set(true));
    chain.addEventListener('click', e => { if (e.target.closest('[data-chain-try]')) set(true); });
  }
  // §06 the stream on phones: the inspector's hash links fold under 'Hash links' (open from 601 px)
  const hx = document.querySelector('[data-lt-hx]');
  if (hx && window.matchMedia) {
    const mq = matchMedia('(max-width: 600px)'), fold = () => { hx.open = !mq.matches; };
    fold(); mq.addEventListener('change', fold);
  }
})();
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
