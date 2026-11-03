/* OpenEXA — the homepage loader
   The first of the page's scripts (index.html, started by home.js once the first paint is on screen), so nothing
   evaluated after it (the overture's WebGL set-up, the instruments, site.js) can hold it up: its cap is armed as soon
   as the first paint is on screen (its clocks run from navigation start either way).
   It finishes on elapsed time and readiness, never on a count of frames: a throttled or starved requestAnimationFrame
   (background tab, battery saver) only skips repaints of the count; timers lift the loader. performance.now() runs from
   the start of navigation, so the count is the real time the visitor has waited. A later visit (in the same session, or
   arriving from another page of the site) gets the short version: the mark, no count, for as long as the stage needs and
   no longer.
   The failsafe: 1.9-2.2 s after navigation the loader is gone (v2x; it was 2.3-2.6 s). A fade on the document timeline (the compositor runs it, so
   scripts that hold the main thread cannot delay it) takes it away at that moment unless the hand-off has run; a
   count that has not reached 100 by then is never shown again (the loader is removed at once: no count, no hand-off),
   and a timer removes it then whatever else is running. A count that reached 100 before it always hands off:
   .is-done comes with '100', and site.css holds a first visit's hand-off for a 90 ms beat in its own transition delay, on
   the compositor, so no long task can stretch the beat or skip it (r4; it was a 90 ms timer). Without this script a CSS
   animation (v2:nav) still fades it out 1.9-2.2 s after its first frame. While the loader is up, Tab stays on the skip link:
   nothing hidden beneath the loader takes keyboard focus. (The page is not made inert, which would restyle all of it
   twice on the loader's path; reading the loader's own animations needs only the styles its first frame computes.)
   award a1 (1 Nov): the curtain is gone; at '100' the loader hands off to the overture (AWARD_BAR L4, below).
   v2x (30 Oct): shorter (a first visit holds 600 ms to 1.2 s, the hand-off takes .7 s) and cheaper: the count and the
   dial are written only when the count's number changes (at most 100 small writes, not one per frame), the idle sweep
   is read from the clock instead of from computed style, and the page is told it is ready in a task of its own, so what
   answers 'oxa:loaded' does not run inside the loader's frame. */
(function () {
  'use strict';
  const loader = document.querySelector('.loader');
  if (!loader) return;
  const root = document.documentElement, body = document.body;
  // the overture reads this and then publishes its globe's place only as html[data-globe] (award a4: an inline style
  // write on <html> restyles the whole drawn page; the attribute restyles nothing, no selector reads it)
  root.dataset.globeRead = '';
  const LATE = 1900; // ms from navigation start: the failsafe's moment (v2:nav's .loader fade starts 1.9 s into its clock)
  const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;
  const pad = n => String(n).padStart(2, '0');

  // the page beneath the loader takes no keyboard focus until it lifts
  const skip = document.querySelector('.skip');
  const trap = e => { if (e.key === 'Tab' && skip) { e.preventDefault(); skip.focus(); } };
  const hold = on => { if (on) document.addEventListener('keydown', trap, true); else document.removeEventListener('keydown', trap, true); };
  // the overture's first headline rises as the loader hands off; the page is told it is ready
  const loaded = () => {
    document.querySelectorAll('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
    root.classList.add('is-loaded');
    // the page's answers (the bar measures, the overture relays) run in their own task, not inside the loader's frame
    setTimeout(() => document.dispatchEvent(new CustomEvent('oxa:loaded')), 0);
  };
  let gone = false;
  const drop = () => { // at once: no count, no hand-off (the page is told it is ready in the next task, so the loader's
    // removal is not held up by everything that answers 'oxa:loaded' on a busy device)
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
  const MIN = seen ? 0 : 600, CAP = seen ? 800 : 1200, OUT = seen ? 0 : 300; // ms from navigation start; OUT = the count's run to 100
  const count = loader.querySelector('.loader-count'), dial = loader.querySelector('.loader-dial');
  // the overture draws its first frame (or falls back) after this script
  const glReady = !document.querySelector('.story-gl') || ['gl-ready', 'no-webgl'].some(c => root.classList.contains(c)) ? Promise.resolve()
    : new Promise(r => ['story:gl-ready', 'story:no-webgl'].forEach(t => document.addEventListener(t, r, { once: true })));
  // the fonts are asked for after load: asking earlier makes the browser lay out the whole page inside this script
  const ready = Promise.all([glReady,
    (document.readyState === 'complete' ? Promise.resolve() : new Promise(r => window.addEventListener('load', r, { once: true })))
      .then(() => document.fonts ? document.fonts.ready : null)]);
  const easeOut = t => 1 - Math.pow(1 - t, 3);
  // the dial has swept on its own (CSS) since the first paint: about where loader-idle has got to, read from the clock
  const t0 = performance.now(); // MIN and CAP count from navigation start
  const idle = Math.min(0.26, 0.26 * (1 - Math.exp(-t0 / 700)));
  const TAU = 420; // ms: the count's approach to 90 before readiness
  if (!seen) loader.classList.add('is-counting');
  const early = t => idle + (0.9 - idle) * (1 - Math.exp(-Math.max(0, t - t0) / TAU)); // before readiness the count eases towards 90
  let runFrom = 0, pFrom = 0, finishAt = 0, completed = false;
  const progressAt = (now) => finishAt && now >= runFrom ? pFrom + (1 - pFrom) * easeOut(clamp01((now - runFrom) / Math.max(1, OUT))) : early(now);
  let shown = '';
  const paint = (p) => {
    if (gone || !count) return;
    const n = Math.min(100, Math.round(p * 100)), t = pad(n);
    if (t === shown) return; // nothing visible changed: no write
    shown = t; count.textContent = t;
    if (dial && !seen) dial.style.setProperty('--lp', (n / 100).toFixed(2));
  };
  /* the hand-off (award a1, AWARD_BAR L4): where the dial goes. The overture publishes its globe's place on <html> as
     html[data-globe] "x y r" (px in the window; story.js, home; a4; the a1 inline custom properties --globe-x, --globe-y,
     --globe-r stay a fallback, written only while html[data-globe-read] is absent); until it does, the
     place is estimated as the overture lays it out: right of the opening copy (wide), or above it (stacked: phones,
     tablets); a window too short for either dissolves where it is. Read once, after load. */
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
        loader.style.setProperty('--hm', (r / half).toFixed(3)); // the mark grows with the ring (a third of the globe) as it gives way to the globe's points
      }
    } catch (e) { /* the CSS defaults: a dissolve in place */ }
  };
  const complete = () => {
    if (completed || gone) return;
    completed = true;
    if (performance.now() >= LATE) { drop(); return; }
    paint(1);
    loader.classList.add('is-complete');
    body.classList.remove('is-loading');
    hold(false);
    loaded();
    // the hand-off, in the frame that shows '100' (.is-done also stops the CSS failsafe); a first visit's decision reads
    // for a beat (the aperture pulses green) while its transitions wait out their 90 ms delay (site.css)
    handoff();
    loader.classList.add('is-done');
    setTimeout(() => { if (!gone) { gone = true; loader.remove(); } }, seen ? 760 : 990);
  };
  const schedule = () => {
    if (finishAt) return;
    const now = performance.now();
    runFrom = Math.max(now, MIN - OUT);
    pFrom = early(runFrom);
    finishAt = runFrom + OUT;
    setTimeout(complete, Math.max(0, finishAt - now));
  };
  ready.then(schedule);
  setTimeout(schedule, Math.max(0, CAP - performance.now())); // never hold the page hostage
  setTimeout(() => { if (!completed) complete(); }, Math.max(0, LATE - performance.now())); // the failsafe's moment: whatever the timers above are doing
  const frame = () => { if (completed || gone) return; paint(progressAt(performance.now())); requestAnimationFrame(frame); };
  paint(progressAt(performance.now()));
  requestAnimationFrame(frame);
})();
