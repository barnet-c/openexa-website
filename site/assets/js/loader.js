/* OpenEXA — the homepage loader
   The first of the page's scripts (index.html), so nothing evaluated after it (the overture's WebGL set-up, the
   instruments, site.js) can hold it up: its cap is armed as soon as the document is parsed.
   It finishes on elapsed time and readiness, never on a count of frames: a throttled or starved requestAnimationFrame
   (background tab, battery saver) only skips repaints of the count; timers lift the loader. performance.now() runs from
   the start of navigation, so the count is the real time the visitor has waited. A later visit (in the same session, or
   arriving from another page of the site) gets the short version: the mark, no count, for as long as the stage needs and
   no longer.
   The failsafe: 3 s after navigation the loader is gone. Any step of this script that would run later than that, on a
   device too busy to lift the loader in time, removes the loader at once instead (no count, no curtain), so a late
   script never shows it again; a timer removes it at that moment whatever else is running. Without this script a CSS
   animation (v2:nav) still fades it out 3 s after its first frame. While the loader is up, Tab stays on the skip link:
   nothing hidden beneath the loader takes keyboard focus. (Nothing here forces a style or layout pass: the page is not
   made inert and no animation is read back, either of which restyles or lays out the whole page inside this script.) */
(function () {
  'use strict';
  const loader = document.querySelector('.loader');
  if (!loader) return;
  const root = document.documentElement, body = document.body;
  const LATE = 3000; // ms from navigation start: the failsafe (v2:nav's .loader animation has the same delay)
  const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;
  const pad = n => String(n).padStart(2, '0');

  // the page beneath the loader takes no keyboard focus until it lifts: Tab stays on the skip link (it shows above it)
  const skip = document.querySelector('.skip');
  const trap = e => { if (e.key === 'Tab' && skip) { e.preventDefault(); skip.focus(); } };
  const hold = on => { if (on) document.addEventListener('keydown', trap, true); else document.removeEventListener('keydown', trap, true); };
  // the overture's first headline rises as the curtain lifts; the page is told it is ready
  const loaded = () => {
    document.querySelectorAll('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
    root.classList.add('is-loaded');
    document.dispatchEvent(new CustomEvent('oxa:loaded'));
  };
  let gone = false;
  const drop = () => { // at once: no count, no curtain
    if (gone) return;
    gone = true;
    loader.remove();
    body.classList.remove('is-loading');
    hold(false);
    if (!root.classList.contains('is-loaded')) loaded();
  };
  if (performance.now() >= LATE) { drop(); return; }

  let seen = false;
  try { seen = sessionStorage.getItem('oxa:intro') === '1'; sessionStorage.setItem('oxa:intro', '1'); } catch (e) { /* storage off: full intro */ }
  // a click from another page of the site is a visit in progress, not an arrival: the mark only
  try { if (document.referrer && new URL(document.referrer).origin === location.origin) seen = true; } catch (e) { /* no referrer */ }
  if (seen) loader.classList.add('is-quick');
  body.classList.add('is-loading');
  hold(true);
  const MIN = seen ? 0 : 950, CAP = seen ? 1100 : 2000, OUT = seen ? 0 : 380; // ms from navigation start; OUT = the count's run to 100
  const count = loader.querySelector('.loader-count'), dial = loader.querySelector('.loader-dial');
  // the overture draws its first frame (or falls back) after this script: lift once it has, never later than the cap
  const glReady = !document.querySelector('.story-gl') || ['gl-ready', 'no-webgl'].some(c => root.classList.contains(c)) ? Promise.resolve()
    : new Promise(r => ['story:gl-ready', 'story:no-webgl'].forEach(t => document.addEventListener(t, r, { once: true })));
  // the fonts are asked for after load: asking earlier makes the browser lay out the whole page inside this script
  const ready = Promise.all([glReady,
    (document.readyState === 'complete' ? Promise.resolve() : new Promise(r => window.addEventListener('load', r, { once: true })))
      .then(() => document.fonts ? document.fonts.ready : null)]);
  const easeOut = t => 1 - Math.pow(1 - t, 3);
  // the dial has swept on its own (CSS) since the first paint: the count takes over from where it stands, and only now
  // appears (never a frozen "00" while the script is on its way); the short version never shows a count
  const idle = dial ? Math.min(0.6, parseFloat(getComputedStyle(dial).getPropertyValue('--lp')) || 0) : 0;
  if (!seen) loader.classList.add('is-counting');
  const t0 = performance.now(); // MIN and CAP count from navigation start
  const early = t => idle + (0.9 - idle) * (1 - Math.exp(-Math.max(0, t - t0) / 520)); // before readiness the count eases towards 90
  let runFrom = 0, pFrom = 0, finishAt = 0, completed = false;
  const progressAt = (now) => finishAt && now >= runFrom ? pFrom + (1 - pFrom) * easeOut(clamp01((now - runFrom) / Math.max(1, OUT))) : early(now);
  const paint = (p) => {
    if (gone) return;
    if (count) count.textContent = pad(Math.min(100, Math.round(p * 100)));
    if (dial && !seen) dial.style.setProperty('--lp', p.toFixed(4));
  };
  // the curtain: it starts moving at once and takes over from the CSS failsafe (.is-done stops it); hidden .95 s later,
  // removed at 1.15 s. Only ever before the failsafe's moment: no curtain after it
  const lift = () => {
    if (gone) return;
    if (performance.now() >= LATE) { drop(); return; }
    loader.classList.add('is-done');
    setTimeout(() => { if (!gone) { gone = true; loader.remove(); } }, seen ? 600 : 1150);
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
    // the decision reads for a beat (100, the aperture pulses green), then the curtain lifts
    if (seen) lift(); else setTimeout(lift, 120);
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
