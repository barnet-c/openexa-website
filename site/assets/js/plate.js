/* OpenEXA: Platform's hero plate (page-only). The plate draws one decision at first paint in CSS (platform.css), once:
   three proposals reach the Execution Council, one is refused, two cross the boundary and settle. "Replay" restarts
   those CSS animations; it stays hidden without JavaScript and under reduced motion, where the plate is a still. */
(function () {
  'use strict';
  const fig = document.querySelector('[data-plate="stack"]');
  const btn = fig && fig.querySelector('[data-plate-replay]');
  if (!btn || typeof fig.getAnimations !== 'function') return;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const sync = () => { btn.hidden = reduce.matches; };
  sync();
  if (reduce.addEventListener) reduce.addEventListener('change', sync);
  btn.addEventListener('click', () => { fig.getAnimations({ subtree: true }).forEach((a) => { a.cancel(); a.play(); }); });
})();
