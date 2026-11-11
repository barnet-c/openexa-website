/* OpenEXA: the 404 (system; 404.html only). The plate's rejected proposal carries the address that was asked for, and the rejection
   is sealed as a record in the visitor's own ledger (run.js: kept in this tab, sent nowhere). Without script it reads "this address". */
(function () {
  'use strict';
  // the walk's dash is the drawing's scale on screen (notfound.css; a2): read once, before the walk starts at .4 s
  document.querySelectorAll('.nf-plate svg').forEach(svg => {
    const m = svg.getScreenCTM();
    if (m && m.a) svg.style.setProperty('--k', Math.max(1, Math.hypot(m.a, m.b) * 1.02 + .02).toFixed(3));
  });
  const outs = document.querySelectorAll('[data-nf-path]');
  if (!outs.length) return;
  let path = location.pathname.replace(/\/{2,}/g, '/');
  try { path = decodeURI(path); } catch (err) { /* a malformed escape: show it as typed */ }
  if (!path || path === '/' || /^\/404(\.html)?$/.test(path)) return; // the page itself, opened directly
  const chars = Array.from(path); // by code point: an ellipsis never splits a character
  if (chars.length > 34) path = chars.slice(0, 16).join('') + '…' + chars.slice(-16).join('');
  outs.forEach(el => { el.textContent = path; });
  // the run starts after the first paint (site.js's tag lists run.js): the rejection is sealed when it is up, once per address
  const seal = () => {
    const run = window.OXA && window.OXA.run;
    if (!run) return false;
    const d = path + ' · gate 04 · unknown route', last = run.records().pop(), foot = document.querySelector('.nf-foot');
    if ((last && last.ev === 'Rejected route' && last.d === d) || run.record('Rejected route', d, 'the 404')) { if (foot) foot.classList.add('is-recorded'); }
    return true;
  };
  if (!seal()) document.addEventListener('oxa:run', seal, { once: true });
})();
