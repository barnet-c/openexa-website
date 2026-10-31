/* OpenEXA: Home's start-up (home group; index.html only)
   The page paints from its HTML and CSS first; the instruments start once that first paint is on screen.
   The scripts named in this tag's data-after-paint attribute (space-separated, in order) are added after the browser
   reports its first contentful paint (the paint entry carries the moment the frame was presented, which can be well
   after the main thread finished it), so none of their downloading, parsing or start-up stands between the visitor and
   the first screen. They keep their order (async = false). A hidden tab paints nothing: it starts at once; and no
   browser waits more than 0.7 s for the paint entry. Without JavaScript nothing here runs and the page is already whole.
   check_static's per-page script budget reads this attribute as well as the page's script tags. */
(function () {
  'use strict';
  const me = document.currentScript;
  const list = ((me && me.getAttribute('data-after-paint')) || '').split(/\s+/).filter(Boolean);
  if (!list.length) return;
  let started = false;
  const start = () => {
    if (started) return;
    started = true;
    for (const src of list) {
      const s = document.createElement('script');
      s.src = src;
      s.async = false; // in order, as the tags were
      document.body.appendChild(s);
    }
  };
  if (document.visibilityState === 'hidden') { start(); return; }
  try {
    const po = new PerformanceObserver(entries => {
      if (entries.getEntriesByName('first-contentful-paint').length) { po.disconnect(); setTimeout(start, 0); }
    });
    po.observe({ type: 'paint', buffered: true });
  } catch (e) { /* no paint timing: the timer below */ }
  setTimeout(start, 700);
})();
