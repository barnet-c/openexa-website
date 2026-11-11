/* OpenEXA: the take (home). Five beats on one stage: the scroll says which shot, the clock plays the change; the follow log, the hand's read-out, the record. window.OXA.take */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {}, run = OXA.run, stage = OXA.stage, doc = document, root = doc.documentElement;
  const story = doc.querySelector('.story'), fig = story && story.querySelector('.take-stage');
  if (!run || !stage || !fig || OXA.take) return;
  const $ = (s, n) => (n || story).querySelector(s), $$ = (s, n) => Array.from((n || story).querySelectorAll(s));
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)');
  const beats = $$('.beat'), marks = $$('.take-at i'), idx = $$('.story-idx button'), sayEl = $('[data-take-say]');
  const shots = beats.map(b => $('.beat-shot', b)), SHOT = ['wide', 'wide', 'section', 'close', ''];
  const { GX } = run.world, pad2 = n => String(n).padStart(2, '0');
  const say = t => { if (sayEl) sayEl.textContent = t; };
  let beat = -1, pinned = root.classList.contains('story-ready');

  /* ---------- the shot ---------- */
  const upright = () => window.innerWidth < 640 || window.innerWidth * 20 < window.innerHeight * 23;
  const nameOf = i => (i === 1 && upright() ? 'down' : SHOT[i]);
  function go(i) {
    if (i === beat || !pinned) return;
    const was = beat, rec = i === 4;
    beat = i;
    // the record is a hard cut; one set-up in two frames (0 and 1 on a desk) is a move of the camera; the rest are cuts
    story.dataset.via = rec || was === 4 ? 'hard' : was >= 0 && nameOf(was) === nameOf(i) ? 'move' : 'cut';
    story.dataset.beat = i;
    idx.forEach((b, j) => { if (j === i) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); b.parentNode.classList.toggle('is-past', j < i); });
    stage.hold(fig, rec);
    if (!rec) stage.cut(fig, nameOf(i), shots[i]);
    box();
    fill();
  }
  // the tick of the beat on screen fills as it is scrolled through: a hold still answers the hand
  let fillRaf = 0;
  function fill() {
    fillRaf = 0;
    if (!pinned || beat < 0 || rm.matches) return;
    const q = marks[beat].getBoundingClientRect();
    idx[beat].style.setProperty('--fill', Math.max(0, Math.min(1, (window.innerHeight / 2 - q.top) / (q.height || 1))).toFixed(3));
  }
  window.addEventListener('scroll', () => { if (!fillRaf && pinned && !story.classList.contains('is-offscreen')) fillRaf = requestAnimationFrame(fill); }, { passive: true });
  // the beat for where the page is: the mark on the screen's middle; past the last mark's foot (a jump beyond the take:
  // End, a chapter link, a reload lower down) the last beat, so the way back up meets the record, never a stale shot
  const here = () => {
    const i = marks.findIndex(m => m.__on);
    if (i >= 0 || !marks.length) return i;
    const mid = window.innerHeight / 2;
    return marks[marks.length - 1].getBoundingClientRect().bottom <= mid ? marks.length - 1 : marks[0].getBoundingClientRect().top >= mid ? 0 : -1;
  };
  // the header says Record while the record has the screen, and Model again once the take is left
  let seen = true;
  const box = () => run.transport(pinned && beat === 4 && seen ? 'record' : 'model');
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(es => { seen = es[es.length - 1].intersectionRatio >= 0.5; box(); }, { threshold: 0.5 }).observe(story.querySelector('.take'));
    const io = new IntersectionObserver(es => {
      es.forEach(e => { e.target.__on = e.isIntersecting; });
      const i = here();
      if (i >= 0) go(i);
    }, { rootMargin: '-50% 0px -50% 0px' });
    marks.forEach(m => io.observe(m));
  }
  const mode = () => {
    const on = root.classList.contains('story-ready');
    if (on === pinned) return;
    pinned = on;
    if (!on) { beat = -1; delete story.dataset.beat; delete story.dataset.via; stage.hold(fig, false); box(); }
    else { const i = here(); go(i < 0 ? 0 : i); }
  };
  doc.addEventListener('story:gl-ready', mode);
  window.addEventListener('resize', () => { if (pinned && beat >= 0 && beat < 4) stage.cut(fig, nameOf(beat), shots[beat]); });

  // where a beat holds: its mark's middle on the screen's middle
  const at = i => { const q = marks[i].getBoundingClientRect(); return Math.max(0, q.top + window.scrollY + q.height / 2 - window.innerHeight / 2); };
  function to(i) {
    const how = rm.matches ? 'auto' : 'smooth';
    if (i < beats.length) { window.scrollTo({ top: i <= 0 ? 0 : at(i), behavior: how }); return; }
    const next = story.nextElementSibling;
    if (!next) return;
    next.setAttribute('tabindex', '-1'); next.classList.add('story-next-target');
    next.focus({ preventScroll: true }); next.scrollIntoView({ behavior: how, block: 'start' });
  }
  idx.forEach((b, i) => b.addEventListener('click', () => to(i)));
  fig.addEventListener('keydown', e => {
    if (e.target !== fig || !pinned || e.altKey || e.ctrlKey || e.metaKey) return;
    const d = /^(ArrowDown|ArrowRight|PageDown)$/.test(e.key) ? 1 : /^(ArrowUp|ArrowLeft|PageUp)$/.test(e.key) ? -1 : 0;
    if (!d || beat + d < 0) return;
    e.preventDefault(); to(beat + d);
  });
  // every beat stays in the reading and the tab order; focus that lands in a beat off screen brings that beat on, at once
  story.addEventListener('focusin', e => { const b = e.target.closest && e.target.closest('.beat'), i = beats.indexOf(b); if (pinned && i >= 0 && i !== beat) window.scrollTo({ top: i ? at(i) : 0, behavior: 'instant' }); });
  if (!pinned && location.hash === '#lc01' && beats[3]) beats[3].scrollIntoView();

  /* ---------- beat 1: follow a proposal; its tag opens into the gate log ---------- */
  const fb = $('[data-take-follow]'), tr = $('[data-take-trace]'), trId = $('[data-trace-id]'), trState = $('[data-trace-state]'), trLog = $('[data-trace-log]');
  let fk = null, shown = -1, spoke = 0, done = false, lim = 0.88;
  const label = t => { if (fb && fb.textContent !== t) fb.textContent = t; };
  function rowsOf(p) {
    const f = x => { const v = (x - p.xs) / (GX[3] - p.xs); return v <= 0 ? 0 : p.ta * (-0.55 + Math.sqrt(0.3025 + 1.8 * v)) / 0.9; }, v = p.ta + 0.5;
    const rows = [['01 Signal', f(GX[0]), `picked up · ${2 + (p.k % 4)} signals`, ''], ['02 Predict', f(GX[1]), 'estimate formed', ''], ['03 Decide', f(GX[2]), 'proposal formed', ''],
      ['04 Approve', v, p.rej ? `rejected · risk ${p.risk.toFixed(2)} > ${lim.toFixed(2)}` : `approved · risk ${p.risk.toFixed(2)} ≤ ${lim.toFixed(2)}`, p.rej ? 'bad' : 'ok']];
    if (p.rej) rows.push(['Ledger', v + 1.5, 'rejection logged', 'bad']);
    else rows.push(['05 Execute', v + 2.7 * (GX[4] - GX[3]) / (GX[5] - GX[3]), `executed · rail ${p.lane + 1}`, ''], ['06 Settle', v + 2.7, 'settled', 'ok'], ['Ledger', v + 3.5, 'sealed', 'ok']);
    return rows;
  }
  function trace(S) {
    if (fk == null || !tr) return;
    const p = run.prop(fk), e = S.t - p.tb;
    if (e < p.ta + 0.5) lim = 1 - S.strict;
    const rows = rowsOf(p), n = rows.filter(r => e >= r[1]).length, over = S.t > p.te;
    if (n !== shown || over !== done) {
      shown = n; done = over;
      trLog.replaceChildren(...rows.map((r, i) => { const li = doc.createElement('li'), a = doc.createElement('b'), b = doc.createElement('i'), c = doc.createElement('span'); a.textContent = r[0]; a.style.fontWeight = '400'; if (i < n) { li.className = 'is-hit' + (r[3] ? ' is-' + r[3] : ''); b.textContent = r[1].toFixed(2) + ' s'; c.textContent = r[2]; } li.append(a, b, c); return li; }));
      trId.textContent = p.id; tr.classList.toggle('is-no', p.rej && e >= p.ta + 0.5);
      trState.textContent = over ? (p.rej ? 'Rejected at 04' : 'Settled') : e < 0 ? 'entering 01' : S.tagLine || '';
      if (e >= p.ta + 0.5 && spoke < 2) { spoke = 2; say(`${p.id}: ${p.rej ? 'rejected' : 'approved'} by the council.`); }
      if (over && spoke < 3) { spoke = 3; say(`${p.id}: ${p.rej ? 'its rejection is recorded' : 'settled'}.`); }
    } else if (!over && S.tagLine && trState.textContent !== S.tagLine && e >= 0) trState.textContent = S.tagLine;
    if (over) { fk = null; fb.setAttribute('aria-pressed', 'false'); label('Follow another'); }
  }
  function follow(k) {
    fk = k; shown = -1; done = false; spoke = 0;
    if (!fb) return;
    fb.setAttribute('aria-pressed', String(k != null));
    if (k == null) { tr.hidden = true; label('Follow a proposal'); return; }
    tr.hidden = false; label('Stop following'); spoke = 1; say(`Following ${run.prop(k).id}.`);
    trace(run.sample());
  }
  if (fb) {
    fb.addEventListener('click', () => { if (fk != null) { run.follow(null); follow(null); } else { run.follow('next'); follow(run.sample().tag); } });
    $('[data-trace-close]').addEventListener('click', () => { if (fk != null) run.follow(null); follow(null); fb.focus(); });
    fig.addEventListener('stage:follow', e => follow(e.detail));
    // a halted run has no next proposal to follow: the button says so until the run resumes
    const halt = () => { const h = fk == null && run.sample().halted; if (fb.disabled !== h) { fb.disabled = h; label(h ? 'Halted · no new proposals' : 'Follow a proposal'); } };
    doc.addEventListener('oxa:run', halt); halt();
    try { const s = JSON.parse(sessionStorage.getItem('oxa:run')); if (s && s.follow != null && run.sample().tag === s.follow) follow(s.follow); } catch (e) { }
  }

  /* ---------- beat 3: the hand's read-out ---------- */
  const input = $('[data-sw-strict]'), ro = $('[data-stage-ro]');
  function read() {
    if (!input) return;
    const pct = +input.value, l = (1 - pct / 100).toFixed(2);
    input.setAttribute('aria-valuetext', `${pct}% rejected, risk limit ${l}`);
    if (!ro) return;
    const a = ro.children[0], b = ro.children[1], ta = pct > 0 ? `approves ${100 - pct}%` : 'approves every proposal', tb = pct > 0 ? `rejects risk > ${l}` : '';
    if (a.textContent !== ta) a.textContent = ta;
    if (b.textContent !== tb) b.textContent = tb;
  }
  if (input) {
    input.addEventListener('input', () => { read(); if (ro) ro.classList.add('is-moved'); });
    doc.addEventListener('oxa:run', read);
    if (ro && run.records().some(r => r.ev === 'Council strictness')) ro.classList.add('is-moved');
    read();
  }

  run.subscribe(S => { if (!story.classList.contains('is-live') && fig.classList.contains('is-live')) story.classList.add('is-live'); trace(S); }, story);
  OXA.take = { to, beat: () => beat };
})();
