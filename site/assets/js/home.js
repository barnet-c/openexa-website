/* OpenEXA: Home's start-up (home group; index.html only)
   The page paints from its HTML and CSS first; the instruments start once that first paint is on screen.
   The scripts named in this tag's data-after-paint attribute (space-separated, in order) are added after the browser
   reports its first contentful paint (the paint entry carries the moment the frame was presented, which can be well
   after the main thread finished it), so none of their downloading, parsing or start-up stands between the visitor and
   the first screen. They keep their order (async = false). A hidden tab paints nothing: it starts at once. A late
   first paint is waited for, not overtaken (a 0.7 s timer used to win the race on slow runs and put every script back
   in front of the paint); 5 s is only a safety net. A browser without paint timing starts on 'load'.
   While story.js is on its way <html> carries .story-wait, so site.css's safety net does not turn the overture static
   on a slow connection; a failed download sets .story-failed at once. Without JavaScript nothing here runs and the
   page is already whole. check_static's per-page script budget reads this attribute as well as the script tags. */
(function () {
  'use strict';
  // §06 on phones (home.css folds it under 601 px): the chain shows records 01-04 and a control for all eight. An edit
  // or "Alter record 03" opens it, so the break is seen running to the last record. Without JavaScript all eight show.
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
  // §06 the running log on phones: the inspector's two hash blocks fold under "Hash links" (one tap opens them; the
  // checks inside are the same). From 601 px they stand open and the fold's summary is not drawn (home.css).
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
  let started = false;
  const start = () => {
    if (started) return;
    started = true;
    for (const src of list) {
      const s = document.createElement('script');
      s.src = src;
      s.async = false; // in order, as the tags were
      if (/story\.js$/.test(src)) s.onerror = () => root.classList.add('story-failed');
      document.body.appendChild(s);
    }
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
