/* OpenEXA — the 404 (system; 404.html only). The plate's rejected proposal carries the address that was asked for.
   Text only, from this tab's own location: nothing is sent or kept. Without script it reads "this address". */
(function () {
  'use strict';
  const outs = document.querySelectorAll('[data-nf-path]');
  if (!outs.length) return;
  let path = location.pathname.replace(/\/{2,}/g, '/');
  try { path = decodeURI(path); } catch (err) { /* a malformed escape: show it as typed */ }
  if (!path || path === '/' || /^\/404(\.html)?$/.test(path)) return; // the page itself, opened directly
  const chars = Array.from(path); // by code point: an ellipsis never splits a character
  if (chars.length > 34) path = chars.slice(0, 16).join('') + '…' + chars.slice(-16).join('');
  outs.forEach(el => { el.textContent = path; });
})();
