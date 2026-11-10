/* OpenEXA — the homepage loader
   The first of the page's scripts (index.html, started by home.js once the first paint is on screen). The mark's ring
   draws itself in CSS from the loader's first frame (site.css loader-draw, .31 s); this script hands off to the
   overture when it has drawn, so the loader gives way 400 ms after the first paint at the latest (hc29: no count, no
   wait for the stage; the overture's globe draws in from the ring whenever its first frame is ready). A later visit (in
   the same session, or arriving from another page of the site) shows the mark only, until the stage is ready and never
   longer than those 400 ms.
   It finishes on elapsed time, never on a count of frames. The failsafe: 1.9-2.2 s after navigation the loader is gone.
   A fade on the document timeline (the compositor runs it) takes it away at that moment unless the hand-off has run,
   and a timer removes it then (no hand-off). .is-complete and .is-done come in the same task; site.css holds a first
   visit's hand-off for a 90 ms beat in its own transition delay, on the compositor. While the loader is up, Tab stays
   on the skip link. */
(function () {
  'use strict';
  const loader = document.querySelector('.loader');
  if (!loader) return;
  const root = document.documentElement, body = document.body;
  // the overture reads this and then publishes its globe's place only as html[data-globe] (award a4)
  root.dataset.globeRead = '';
  const LATE = 1900; // ms from navigation start: the failsafe's moment (v2:nav's .loader fade starts 1.9 s into its clock)
  const DRAW = 310; // ms after the first paint: the ring has drawn (loader-draw); the 90 ms beat follows
  const CAP = 400; // ms after the first paint: a later visit's mark, at most

  // the page beneath the loader takes no keyboard focus until it lifts
  const skip = document.querySelector('.skip');
  const trap = e => { if (e.key === 'Tab' && skip) { e.preventDefault(); skip.focus(); } };
  const hold = on => { if (on) document.addEventListener('keydown', trap, true); else document.removeEventListener('keydown', trap, true); };
  // the overture's first headline rises as the loader hands off; the page is told it is ready (in a task of its own)
  const loaded = () => {
    document.querySelectorAll('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
    root.classList.add('is-loaded');
    setTimeout(() => document.dispatchEvent(new CustomEvent('oxa:loaded')), 0);
  };
  let gone = false;
  const drop = () => { // at once: no hand-off
    if (gone) return;
    gone = true;
    loader.remove();
    body.classList.remove('is-loading');
    hold(false);
    if (!root.classList.contains('is-loaded')) setTimeout(() => { if (!root.classList.contains('is-loaded')) loaded(); }, 0);
  };
  if (performance.now() >= LATE) { drop(); return; }
  // the failsafe on the navigation's clock: the CSS fade (v2:nav) runs from the loader's first frame
  try {
    const fs = loader.getAnimations().find(a => a.animationName === 'loader-failsafe');
    if (fs && (fs.startTime === null || fs.startTime > 0)) fs.startTime = 0;
  } catch (e) { /* no Web Animations: the CSS clock stands */ }

  let seen = false;
  try { seen = sessionStorage.getItem('oxa:intro') === '1'; sessionStorage.setItem('oxa:intro', '1'); } catch (e) { /* storage off: full intro */ }
  // a click from another page of the site is a visit in progress, not an arrival: the mark only
  try { if (document.referrer && new URL(document.referrer).origin === location.origin) seen = true; } catch (e) { /* no referrer */ }
  if (seen) loader.classList.add('is-quick');
  body.classList.add('is-loading');
  hold(true);
  // the first paint: the moment the loader (and its ring's draw) appeared
  let fp = performance.now();
  try {
    const p = performance.getEntriesByType('paint');
    const e = p.find(x => x.name === 'first-paint') || p[0];
    if (e && e.startTime > 0) fp = e.startTime;
  } catch (e) { /* no paint timing: from now */ }
  const dial = loader.querySelector('.loader-dial');

  /* the hand-off (award a1, AWARD_BAR L4): where the dial goes. The overture publishes its globe's place on <html> as
     html[data-globe] "x y r" (px in the window; story.js, home; the inline custom properties --globe-x, --globe-y,
     --globe-r stay a fallback, written only while html[data-globe-read] is absent); until it does, the place is
     estimated as the overture lays it out: right of the opening copy (wide), or above it (stacked: phones, tablets); a
     window too short for either dissolves where it is. Read once, at the hand-off. */
  const RM = window.matchMedia('(prefers-reduced-motion: reduce)');
  const handoff = () => {
    if (RM.matches || !dial) return;
    try {
      const st = root.style, W = window.innerWidth, H = window.innerHeight;
      const g = (root.dataset.globe || '').split(' ').map(parseFloat);
      let x = g[0], y = g[1], r = g[2];
      if (!(r > 0)) { x = parseFloat(st.getPropertyValue('--globe-x')); y = parseFloat(st.getPropertyValue('--globe-y')); r = parseFloat(st.getPropertyValue('--globe-r')); }
      if (!(r > 0)) {
        const copy = document.querySelector('.beat-0 .beat-text'), b = copy && H >= 420 ? copy.getBoundingClientRect() : null;
        const g = Math.max(20, Math.min(56, W * 0.04)) * Math.max(1, W / 1920), nav = (W < 961 ? 64 : 72) * Math.max(1, W / 1920);
        if (b && b.right > 0 && W >= 961) { // beside the copy, between the bar and the scene index
          const x0 = Math.min(b.right + 36, W * 0.56), x1 = W - g, y0 = nav + 22, y1 = H - nav;
          x = (x0 + x1) / 2; y = (y0 + y1) / 2; r = Math.min(x1 - x0, y1 - y0) / 2 * 0.7;
        } else if (b && b.top > H * 0.3) { // stacked (phones, tablets): above the copy, under the scene index
          const x0 = g / 2, x1 = W - g / 2, y0 = nav + 56, y1 = b.top - 14;
          if (y1 - y0 > 120) { x = (x0 + x1) / 2; y = (y0 + y1) / 2; r = Math.min(x1 - x0, y1 - y0) / 2 * 0.85; }
        }
      }
      const d = dial.getBoundingClientRect(), half = d.width / 2;
      if (!(half > 0)) return;
      if (r > 0) {
        loader.style.setProperty('--hx', (x - (d.left + half)).toFixed(1) + 'px');
        loader.style.setProperty('--hy', (y - (d.top + half)).toFixed(1) + 'px');
        loader.style.setProperty('--hr', (r / half).toFixed(3)); // the tick ring opens to the globe's limb
        loader.style.setProperty('--hm', (r / half).toFixed(3)); // the mark grows with the ring as it gives way to the globe's points
      }
    } catch (e) { /* the CSS defaults: a dissolve in place */ }
  };
  let completed = false;
  const complete = () => {
    if (completed || gone) return;
    completed = true;
    if (performance.now() >= LATE) { drop(); return; }
    loader.classList.add('is-complete');
    body.classList.remove('is-loading');
    hold(false);
    loaded();
    // the hand-off, in the frame that completes the ring (.is-done also stops the CSS failsafe); a first visit's ring
    // reads for a beat (it pulses green) while its transitions wait out their 90 ms delay (site.css)
    handoff();
    loader.classList.add('is-done');
    setTimeout(() => { if (!gone) { gone = true; loader.remove(); } }, seen ? 760 : 990);
  };
  const at = t => setTimeout(complete, Math.max(0, fp + t - performance.now()));
  if (seen) {
    // a later visit: the mark until the overture has its first frame (or has fallen back) and the fonts are in
    const glReady = !document.querySelector('.story-gl') || ['gl-ready', 'no-webgl'].some(c => root.classList.contains(c)) ? Promise.resolve()
      : new Promise(r => ['story:gl-ready', 'story:no-webgl'].forEach(t => document.addEventListener(t, r, { once: true })));
    // the fonts are asked for after load: asking earlier makes the browser lay out the whole page inside this script
    const fonts = (document.readyState === 'complete' ? Promise.resolve() : new Promise(r => window.addEventListener('load', r, { once: true })))
      .then(() => document.fonts ? document.fonts.ready : null);
    Promise.all([glReady, fonts]).then(complete);
    at(CAP);
  } else at(DRAW);
  setTimeout(() => { if (!completed) complete(); }, Math.max(0, LATE - performance.now())); // the failsafe's moment
})();
