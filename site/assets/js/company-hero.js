/* OpenEXA: Company's hero figure (company.html only; loaded after site.js). Notes: .shots/v2x/notes/company.md, hc30r, hc31r.
   hc30r: the hero performs its sentence. "Intelligence," is one mass: every mark packed into a disc, nineteen rings
   round one mark. "put to work." is the same 1,141 marks as a sheet of 96 agents, each a 5 x 5 bitmap. The act runs
   once: the disc stands, then the marks travel to the sheet in 1.4 s (edge first).
   hc31r: then the sheet works, as the fifth camera on the run (window.OXA.run, started after the first paint; SYSTEM.md
   16). An agent is signal green for 300 ms when it proposes, from the moment it lands. The tagged proposal's agent
   carries the tag: a hairline box on the lattice, the agent in its first cell, the number and gate beside it. A click
   or tap on an agent follows its newest proposal, or its next (the box waits, dashed); again lets go; on the focused
   figure Enter follows the next one born and Escape lets go. It draws through OXA.run.subscribe: the header's pause
   holds the frame (and the act), a halt lights nothing, a page opened paused shows the sheet at once.
   Marks are hard squares on whole device pixels; nothing is blended. Reduced motion: the generator's sheet (twelve
   agents green; none while halted), nothing to operate. No JavaScript: the inline SVG still (tools/build_team.py draws
   it from AGENTS below). Phones in portrait deal the same 96 as 8 x 12. */
(function () {
  'use strict';
  const doc = document, root = doc.documentElement;
  const stage = doc.getElementById('company-figure');
  const cv = stage && stage.querySelector('canvas');
  const g = cv && cv.getContext ? cv.getContext('2d') : null;
  if (!g) return;
  // 96 agents, four hex digits each: bit 15 green in the still; bits 0-14 the left three columns of five rows (row-major), mirrored
  const AGENTS = '552b12e692a628d569542ca3cc5536d41ec912e478a4453ef49344ae228e2389ca91629d2555292e649c3694645446bc452a64e92255144f14d412b4246a371ac5d254961f6a65894eb61c8916e4548f251c1b8a489d2c53172e6259c5e42b4a1cabb98a4e8a4b6e4d17147b325e228f15121523471d2f31653747367454144e54e726552891c6943594126a3b3224aa44521b9528f1457424b1c7142b141e514d4a147c62a2c4da5ca6693114eacce61539728944e22d1157b1eab428ca254a';
  const N = AGENTS.length / 4, RINGS = 19, GAP = 2, CELL = 5 + GAP;
  const OUT = 900, STAGGER = 500, LIT = .3; // ms: one mark's travel, the spread of starts; s: how long a proposing agent is lit
  const LABEL = 'Ninety-six agents of the run, an illustrative model: each lights when it proposes. Enter follows the next proposal; Escape lets it go.';
  const HALTED = 'The model is halted: no new proposals.';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const css = getComputedStyle(root);
  const PAPER = css.getPropertyValue('--paper').trim() || '#F5F2EC', GREEN = css.getPropertyValue('--signal-bright').trim() || '#4FCB93';

  const green = new Uint8Array(N), first = new Uint16Array(N + 1), cell = [];
  for (let i = 0; i < N; i++) {
    const v = parseInt(AGENTS.substr(i * 4, 4), 16);
    green[i] = v >> 15 & 1; first[i] = cell.length / 2;
    for (let y = 0; y < 5; y++) for (let x = 0; x < 5; x++) if (v >> (y * 3 + (x < 3 ? x : 4 - x)) & 1) cell.push(x, y);
  }
  const M = first[N] = cell.length / 2;
  const owner = new Uint8Array(M);
  for (let i = 0; i < N; i++) owner.fill(i, first[i], first[i + 1]);

  // --ease-move, cubic-bezier(.62, 0, .2, 1), as a table
  const EASE = new Float32Array(129);
  (function () {
    const bz = (t, a, b) => 3 * (1 - t) * (1 - t) * t * a + 3 * (1 - t) * t * t * b + t * t * t;
    for (let i = 0; i <= 128; i++) {
      let lo = 0, hi = 1;
      for (let k = 0; k < 24; k++) { const t = (lo + hi) / 2; if (bz(t, .62, .2) < i / 128) lo = t; else hi = t; }
      EASE[i] = bz((lo + hi) / 2, 0, 1);
    }
  })();
  const ease = u => { if (u <= 0) return 0; if (u >= 1) return 1; const f = u * 128, i = f | 0; return EASE[i] + (EASE[i + 1] - EASE[i]) * (f - i); };

  // geometry, in device pixels: the sheet (bx, by), the disc (ax, ay), when each agent leaves (wait, 0-1), and the
  // lattice's own lines half way between two agents (EX, EY): the tag's box stands on them
  const ax = new Int16Array(M), ay = new Int16Array(M), bx = new Int16Array(M), by = new Int16Array(M);
  const wait = new Float32Array(N), X = new Int16Array(12), Y = new Int16Array(12), EX = new Float32Array(13), EY = new Float32Array(13);
  let cols = 12, rows = 8, p = 0, m = 0, sc = 1;
  function layout() {
    const W = cv.width, H = cv.height;
    cols = H > W ? 8 : 12; rows = N / cols;
    const uw = cols * CELL - GAP, uh = rows * CELL - GAP;
    p = Math.max(2, Math.floor(Math.min((W + 1) / uw, (H + 1) / uh)));
    m = Math.max(1, Math.round(p * .72));
    // where company.css cannot size the box to whole cells (under the head; a screen at 150 %; a zoomed page) the spare
    // pixels go between the agents, a few each: the sheet ends on the box's edges and every agent stays a whole lattice
    const sx = Math.max(0, W - uw * p), sy = Math.max(0, H - uh * p);
    for (let c = 0; c < cols; c++) X[c] = c * CELL * p + Math.round(c * sx / (cols - 1));
    for (let r = 0; r < rows; r++) Y[r] = r * CELL * p + Math.round(r * sy / (rows - 1));
    const edge = (A, n, E) => { for (let i = 0; i <= n; i++) E[i] = ((i ? A[i - 1] + 4 * p + m : A[0] - 2 * p - (p - m)) + (i < n ? A[i] : A[n - 1] + CELL * p)) / 2; };
    edge(X, cols, EX); edge(Y, rows, EY);
    for (let k = 0; k < M; k++) {
      const a = owner[k];
      bx[k] = X[a % cols] + cell[2 * k] * p;
      by[k] = Y[(a / cols) | 0] + cell[2 * k + 1] * p;
    }
    // the disc: ring r holds 6r marks at the sheet's own pitch, so "packed" is literal. It stands in the middle of the
    // sheet; on the tall sheet in its top square, so a phone shows it whole above the fold
    const cx = (W - (p - m)) / 2, cy = (Math.min(W, H) - (p - m)) / 2, disc = [];
    disc.push([Math.round(cx - m / 2), Math.round(cy - m / 2)]);
    for (let r = 1; r <= RINGS; r++) for (let j = 0; j < 6 * r; j++) {
      const t = Math.PI * 2 * j / (6 * r) - Math.PI / 2;
      disc.push([Math.round(cx + r * p * Math.cos(t) - m / 2), Math.round(cy + r * p * Math.sin(t) - m / 2)]);
    }
    // which mark goes where: the disc is cut into the sheet's columns, each column into its agents, each agent into its
    // rows, always in order, so no two marks cross and the disc opens out instead of bursting
    const byX = (u, v) => u[0] - v[0] || u[1] - v[1], byY = (u, v) => u[1] - v[1] || u[0] - v[0];
    disc.sort(byX);
    let at = 0;
    for (let c = 0; c < cols; c++) {
      let n = 0;
      for (let r = 0; r < rows; r++) { const a = r * cols + c; n += first[a + 1] - first[a]; }
      const col = disc.slice(at, at + n).sort(byY); at += n;
      let q = 0;
      for (let r = 0; r < rows; r++) {
        const a = r * cols + c, k0 = first[a], k1 = first[a + 1], part = col.slice(q, q + k1 - k0); q += k1 - k0;
        let k = k0;
        while (k < k1) {
          let e = k; while (e < k1 && cell[2 * e + 1] === cell[2 * k + 1]) e++;
          const row = part.slice(k - k0, e - k0).sort(byX);
          for (let i = 0; k < e; k++, i++) { ax[k] = row[i][0]; ay[k] = row[i][1]; }
        }
      }
    }
    // the agents with the longest way to go leave first, the ones under the disc last
    let far = 0;
    for (let a = 0; a < N; a++) {
      wait[a] = Math.hypot((a % cols) * CELL + 2.5 - uw / 2, ((a / cols) | 0) * CELL + 2.5 - Math.min(uh, uw) / 2);
      if (wait[a] > far) far = wait[a];
    }
    for (let a = 0; a < N; a++) wait[a] = 1 - wait[a] / far;
  }

  // 0 the disc at rest, 1 travelling out, 2 the sheet (lit as the run says). If the still is already on screen (reduced
  // motion; a script that came late: company.css shows it after 4 s) or the model is paused, there is no act
  const svg = stage.querySelector('.plate-still');
  let held = false;
  try { held = JSON.parse(sessionStorage.getItem('oxa:run')).paused != null; } catch (err) { }
  let mode = reduce.matches || held || (svg && getComputedStyle(svg).visibility === 'visible') ? 2 : 0, T = 0, last = 0, raf = 0, sized = false, run = null;
  const lit = new Uint8Array(N), on = new Uint8Array(N); // the colours on the canvas, and the ones the run asks for
  if (reduce.matches) lit.set(green);
  const fill = (a, k) => { g.fillStyle = lit[a] ? GREEN : PAPER; g.fillRect(bx[k], by[k], m, m); };
  const landed = a => mode === 2 || (mode === 1 && T >= wait[a] * STAGGER + OUT);
  function draw() {
    g.clearRect(0, 0, cv.width, cv.height);
    for (let c = 0; c < 2; c++) {
      g.fillStyle = c ? GREEN : PAPER;
      for (let k = 0; k < M; k++) {
        const a = owner[k];
        if (lit[a] !== c) continue;
        const e = mode === 2 ? 1 : mode ? ease((T - wait[a] * STAGGER) / OUT) : 0;
        if (e >= 1) g.fillRect(bx[k], by[k], m, m);
        else if (e <= 0) g.fillRect(ax[k], ay[k], m, m);
        else g.fillRect(Math.round(ax[k] + (bx[k] - ax[k]) * e), Math.round(ay[k] + (by[k] - ay[k]) * e), m, m);
      }
    }
  }
  const one = a => { g.clearRect(X[a % cols], Y[(a / cols) | 0], 5 * p, 5 * p); for (let k = first[a]; k < first[a + 1]; k++) fill(a, k); };
  // the act keeps its own clock (1.4 s, once); the header's pause holds it where it stands, and oxa:run starts it again
  const stopped = () => root.classList.contains('run-paused');
  function frame(now) {
    raf = 0;
    if (mode !== 1 || stopped()) return;
    T += Math.min(64, now - last); last = now;
    if (T >= OUT + STAGGER) mode = 2;
    draw();
    if (mode === 1) raf = requestAnimationFrame(frame);
  }
  const kick = () => { if (mode === 1 && !raf && !stopped()) { last = performance.now(); raf = requestAnimationFrame(frame); } };
  const deal = () => { if (mode === 0 && !reduce.matches) { mode = 1; kick(); } };

  // the tag, and the frame under a fine pointer: hairline boxes on the lattice's own lines, over the canvas
  const el = (t, c) => { const n = doc.createElement(t); n.className = c; return n; };
  const tag = el('div', 'co-tag'), lab = el('div', 'stage-tag'), tid = el('b', ''), tln = el('span', ''), ring = el('i', 'co-tag co-tag--hot'), say = el('span', 'sr-only');
  lab.append(tid, tln); tag.append(lab); tag.hidden = ring.hidden = true; say.setAttribute('role', 'status');
  [tag, ring].forEach(n => n.setAttribute('aria-hidden', 'true')); // as on the other cameras: the tag is not read out, the status line is
  stage.append(tag, ring, say);
  let ta = -1, tk = '', hot = -1, mine = -1, mineId = '', mineNo = false, ak = -1, aa = -1, told = false;
  const halt = () => { told = true; say.textContent = HALTED; };
  function place(node, a, w) { // over agent a's cell; w: the label's width in CSS pixels (0: the cell alone), taken in whole cells on the roomier side
    const c = a % cols, r = (a / cols) | 0, need = w ? Math.ceil(w * sc * cols / (EX[cols] - EX[0]) - .01) : 0;
    const right = need <= cols - 1 - c || (need > c && cols - 1 - c >= c), n = Math.min(need, right ? cols - 1 - c : c);
    // a lattice line can fall on half a device pixel: the box takes the whole pixels inside its lines (sharp hairlines)
    const up = Math.ceil, dn = Math.floor, x0 = up(EX[right ? c : c - n]), x1 = dn(EX[right ? c + 1 + n : c + 1]), y0 = up(EY[r]), s = node.style;
    s.transform = `translate(${x0 / sc}px, ${y0 / sc}px)`; s.width = (x1 - x0) / sc + 'px'; s.height = (dn(EY[r + 1]) - y0) / sc + 'px';
    s.setProperty('--cw', (dn(EX[c + 1]) - up(EX[c])) / sc + 'px');
    node.classList.toggle('is-left', !right);
    return n === need;
  }
  function setTag(a, id, line, no, again) {
    const key = a + id + line;
    if (key === tk && !again) return;
    tk = key; ta = a;
    tag.hidden = a < 0; lab.hidden = !id; tag.classList.toggle('is-wait', !id); // dashed while it waits for its agent to propose
    if (a < 0) return;
    if (tid.textContent !== id) tid.textContent = id;
    if (tln.textContent !== line) tln.textContent = line;
    lab.classList.toggle('is-no', no);
    tag.classList.toggle('is-flat', (EY[1] - EY[0]) / sc < 2 * parseFloat(getComputedStyle(lab).fontSize) + 9); // rows too short for two lines (a phone on its side): the number alone
    const wide =() => Math.max(tid.offsetWidth, tln.offsetWidth) + parseFloat(getComputedStyle(root).fontSize);
    // a narrow sheet (small phones): before a letter is cut the gate's number goes, then the line keeps one word ("checking", "Rejected")
    let fit = place(tag, a, id ? wide() : 0); const j = line.indexOf(' · ');
    if (!fit && /^\d\d /.test(line)) { tln.textContent = line.slice(3); fit = place(tag, a, wide()); }
    if (!fit && j > 0) { tln.textContent = no ? line.slice(0, j) : line.slice(j + 3); place(tag, a, wide()); }
    point();
  }
  function point() { // on the tagged agent the tag's own box answers the pointer (is-own)
    const own = hot >= 0 && hot === ta, h = hot >= 0 && !own && !root.classList.contains('run-halted');
    ring.hidden = !h; stage.classList.toggle('is-near', h || own); stage.classList.toggle('is-own', own); if (h) place(ring, hot, 0);
  }

  // the camera: which agents proposed in the last 300 ms, and whose proposal is tagged. It starts while the sheet is
  // still being dealt: an agent is at work from the moment it lands (the act's own frames draw it until the sheet rests)
  const KK = new Int32Array(64).fill(-1), TB = new Float64Array(64);
  function cam(S) {
    if (!mode || !sized) return;
    if (told && !S.halted) { told = false; say.textContent = ''; } // resumed
    let a = -1, id = '', line = '', no = false;
    if (reduce.matches) for (let i = 0; i < N; i++) on[i] = S.halted ? 0 : green[i];
    else {
      on.fill(0);
      for (let i = S.n - 1; i >= 0 && !S.ph[i]; i--) { // newest first; a proposal's birth is its agent proposing
        const k = S.k[i], j = k & 63;
        if (KK[j] !== k) { KK[j] = k; TB[j] = run.prop(k).tb; }
        if (S.t - TB[j] >= LIT) break;
        if (landed(S.agent[i])) on[S.agent[i]] = 1;
      }
      if (S.ti >= 0) { a = S.agent[S.ti]; id = S.tagId; line = S.tagLine; no = S.tagTone === 'no'; if (S.tag === mine) mineNo = no; }
      else if (S.n && S.tag > S.k[S.n - 1] && !S.halted) { if (ak !== S.tag) { ak = S.tag; aa = run.prop(ak).agent; } a = aa; } // followed, not yet born: the box waits on its agent
      if (mine >= 0 && S.tag !== mine) { say.textContent = mineId + (mineNo ? ' rejected, logged.' : ' settled.'); mine = -1; }
    }
    for (let i = 0; i < N; i++) if (on[i] !== lit[i]) { lit[i] = on[i]; if (mode === 2) one(i); }
    if (a >= 0 && !landed(a)) a = -1;
    setTag(a, id, line, no);
  }
  const live = () => !!run && mode === 2 && !reduce.matches;
  function arm() { // the figure is one stop for the keyboard only while there is something to operate
    if (run && !reduce.matches) { stage.tabIndex = 0; stage.setAttribute('role', 'group'); stage.setAttribute('aria-label', LABEL); }
    else { ['tabindex', 'role', 'aria-label'].forEach(n => stage.removeAttribute(n)); hot = -1; if (mode === 2) setTag(-1, '', '', false); point(); }
  }
  function hook() {
    kick();
    if (run || !window.OXA || !window.OXA.run) return;
    run = window.OXA.run; run.subscribe(cam, stage); arm();
  }
  doc.addEventListener('oxa:run', hook);

  function size(w, h) {
    w = Math.max(1, Math.round(w)); h = Math.max(1, Math.round(h));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    sc = w / (cv.getBoundingClientRect().width || w);
    layout();
    if (!sized) { sized = true; stage.classList.add('is-live'); }
    draw();
    if (ta >= 0) setTag(ta, lab.hidden ? '' : tid.textContent, tln.textContent, lab.classList.contains('is-no'), true);
    point();
  }
  // the backing store is the box in device pixels (at most 3 to the pixel): the observer's own count where it agrees
  // with the box (an emulated screen reports CSS pixels there), the rounded box otherwise
  const measure = box => {
    const r = cv.getBoundingClientRect(), d = Math.min(3, window.devicePixelRatio || 1), w = r.width * d, h = r.height * d;
    if (!w || !h) return;
    if (box && Math.abs(box.inlineSize - w) < 2 && Math.abs(box.blockSize - h) < 2) size(box.inlineSize, box.blockSize); else size(w, h);
  };
  measure();
  if ('ResizeObserver' in window) {
    const ro = new ResizeObserver(es => { const b = es[es.length - 1].devicePixelContentBoxSize; measure(b && b[0]); });
    try { ro.observe(cv, { box: 'device-pixel-content-box' }); } catch (err) { ro.observe(cv); }
  } else window.addEventListener('resize', () => measure());

  // the act, once: after the page has landed (a turn included) and the disc has stood on screen for under half a second
  if (mode === 0) {
    const O = window.OXA;
    if (O && O.actOnce && 'IntersectionObserver' in window) O.actOnce(stage, deal, { visible: .4, delay: 440 });
    else setTimeout(deal, 440);
  }
  reduce.addEventListener('change', () => {
    if (reduce.matches) { mode = 2; lit.set(green); if (sized) draw(); }
    arm();
    if (run) cam(run.sample());
  });
  hook();

  // the hand: the agent under the pointer (the nearest one: a gap belongs half to each neighbour)
  const pick = (v, A, n) => { let i = n - 1; while (i > 0 && v < (A[i - 1] + 5 * p + A[i]) / 2) i--; return i; };
  const at = e => { const r = cv.getBoundingClientRect(), k = cv.width / r.width; return pick((e.clientY - r.top) * k, Y, rows) * cols + pick((e.clientX - r.left) * k, X, cols); };
  function take(k) { // follow proposal k (none given: the next one born), and say so once
    mine = k == null ? -1 : k; // before the run is told: a paused run answers at once, and cam() reads `mine`
    if (k == null) { run.follow('next'); mine = k = run.sample().tag; } else run.follow(k);
    mineNo = false; mineId = run.prop(k).id; say.textContent = 'Following ' + mineId + '.';
  }
  function drop() { const was = mine; mine = -1; run.follow(null); if (was >= 0) say.textContent = 'Stopped following.'; }
  stage.addEventListener('pointermove', e => { const h = live() && e.pointerType === 'mouse' ? at(e) : -1; if (h !== hot) { hot = h; point(); } });
  stage.addEventListener('pointerleave', () => { if (hot >= 0) { hot = -1; point(); } });
  stage.addEventListener('click', e => {
    if (mode === 0) { deal(); return; }
    if (!live()) return;
    const a = at(e), S = run.sample();
    if (a === ta && mine >= 0) { drop(); return; }
    let k = -1;
    for (let i = S.n - 1; i >= 0 && k < 0; i--) if (S.agent[i] === a) k = S.k[i]; // its newest proposal in flight
    if (k < 0 && !S.halted && S.n) for (let j = S.k[S.n - 1] + 1, end = j + 2000; j < end && k < 0; j++) if (run.prop(j).agent === a) k = j; // or its next
    if (k >= 0) take(k); else if (S.halted) halt();
  });
  stage.addEventListener('keydown', e => {
    if (!live() || e.target !== stage) return;
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (root.classList.contains('run-halted')) halt(); else take(); }
    else if (e.key === 'Escape') drop();
  });
})();
