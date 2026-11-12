/* OpenEXA: Company's hero figure (company.html only; loaded after site.js). hc30r COMP-1: the hero performs its sentence.
   "Intelligence," is one mass: every mark packed into a disc, nineteen rings round one mark. "put to work." is the same
   1,141 marks as a sheet of 96 agents, each a 5 x 5 bitmap of its own, one in eight signal green. The act runs once:
   the disc stands, the marks travel to the sheet in 1.4 s (edge first), each green agent lights as it lands, and the
   figure is still. "Replay" gathers the sheet back into the disc and deals it out again. Pointing at an agent lights it.
   Marks are hard squares on whole device pixels at every frame; nothing is blended. Reduced motion: the sheet, at once,
   no Replay. Without JavaScript: the inline SVG still (tools/build_team.py draws it from AGENTS below, so the two agree).
   Phones in portrait deal the same 96 as 8 x 12. Notes: .shots/v2x/notes/company.md, hc30r. */
(function () {
  'use strict';
  const stage = document.getElementById('company-figure');
  const cv = stage && stage.querySelector('canvas');
  const g = cv && cv.getContext ? cv.getContext('2d') : null;
  if (!g) return;
  // 96 agents, four hex digits each: bit 15 green; bits 0-14 the left three columns of five rows (row-major), mirrored
  const AGENTS = '552b12e692a628d569542ca3cc5536d41ec912e478a4453ef49344ae228e2389ca91629d2555292e649c3694645446bc452a64e92255144f14d412b4246a371ac5d254961f6a65894eb61c8916e4548f251c1b8a489d2c53172e6259c5e42b4a1cabb98a4e8a4b6e4d17147b325e228f15121523471d2f31653747367454144e54e726552891c6943594126a3b3224aa44521b9528f1457424b1c7142b141e514d4a147c62a2c4da5ca6693114eacce61539728944e22d1157b1eab428ca254a';
  const N = AGENTS.length / 4, RINGS = 19, GAP = 2, CELL = 5 + GAP;
  const OUT = 900, STAGGER = 500, BACK = 620, HOLD = 380; // ms: one mark's travel, the spread of starts, the gather, the disc's rest
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const css = getComputedStyle(document.documentElement);
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

  // geometry, in device pixels: the sheet (bx, by), the disc (ax, ay), and when each agent leaves (wait, 0-1)
  const ax = new Int16Array(M), ay = new Int16Array(M), bx = new Int16Array(M), by = new Int16Array(M);
  const wait = new Float32Array(N), prog = new Float32Array(N), lit = new Uint8Array(N), X = new Int16Array(12), Y = new Int16Array(12);
  let cols = 12, rows = 8, p = 0, m = 0;
  function layout() {
    const W = cv.width, H = cv.height;
    cols = H > W ? 8 : 12; rows = N / cols;
    const uw = cols * CELL - GAP, uh = rows * CELL - GAP;
    p = Math.max(2, Math.floor(Math.min((W + 1) / uw, (H + 1) / uh)));
    m = Math.max(1, Math.round(p * .72));
    // beside the head, company.css sizes the box to a whole number of cells where the screen has 1, 2 or 3 device pixels
    // to the pixel; under the head (phones, tablets upright) the box is the column, and at any other ratio (a 4K screen
    // at 150 %, a zoomed page) too: the pixels left over go between the agents, a few each, so the sheet ends on the
    // box's four edges, on both margins and under its caption, and every agent stays a whole lattice
    const sx = Math.max(0, W - uw * p), sy = Math.max(0, H - uh * p);
    for (let c = 0; c < cols; c++) X[c] = c * CELL * p + Math.round(c * sx / (cols - 1));
    for (let r = 0; r < rows; r++) Y[r] = r * CELL * p + Math.round(r * sy / (rows - 1));
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

  // 0 the disc at rest, 1 travelling out, 2 the sheet at rest, 3 gathering, 4 the disc held before it is dealt again
  // the page shows the still until this script is live; if the still is already on screen (reduced motion, or a script
  // that came late: company.css shows it after 4 s), the canvas takes over as the sheet and there is no act
  const svg = stage.querySelector('.plate-still');
  let mode = reduce.matches || (svg && getComputedStyle(svg).visibility === 'visible') ? 2 : 0, t0 = 0, raf = 0, hot = -1, sized = false;
  function draw(now) {
    const t = now - t0;
    for (let a = 0; a < N; a++) {
      let e = mode === 2 ? 1 : 0;
      if (mode === 1) e = ease((t - wait[a] * STAGGER) / OUT);
      else if (mode === 3) e = 1 - ease((t - (1 - wait[a]) * (BACK - 420)) / 420);
      prog[a] = e;
      lit[a] = a === hot || (green[a] && e >= 1) ? 1 : 0;
    }
    g.clearRect(0, 0, cv.width, cv.height);
    for (let pass = 0; pass < 2; pass++) {
      g.fillStyle = pass ? GREEN : PAPER;
      for (let k = 0; k < M; k++) {
        const a = owner[k];
        if (lit[a] !== pass) continue;
        const e = prog[a];
        if (e >= 1) g.fillRect(bx[k], by[k], m, m);
        else if (e <= 0) g.fillRect(ax[k], ay[k], m, m);
        else g.fillRect(Math.round(ax[k] + (bx[k] - ax[k]) * e), Math.round(ay[k] + (by[k] - ay[k]) * e), m, m);
      }
    }
  }
  function frame(now) {
    raf = 0;
    const t = now - t0;
    if (mode === 1 && t >= OUT + STAGGER) mode = 2;
    else if (mode === 3 && t >= BACK) { mode = 4; t0 = now; }
    else if (mode === 4 && t >= HOLD) { mode = 1; t0 = now; }
    draw(now);
    if (mode === 1 || mode === 3 || mode === 4) raf = requestAnimationFrame(frame);
  }
  const still = () => { if (sized && !raf) draw(performance.now()); };
  function go(to) {
    if (reduce.matches || (to === 1 ? mode !== 0 : mode !== 2)) return;
    mode = to; hot = -1; t0 = performance.now();
    if (!raf) raf = requestAnimationFrame(frame);
  }
  const deal = () => go(1);

  function size(w, h) {
    w = Math.max(1, Math.round(w)); h = Math.max(1, Math.round(h));
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    layout();
    if (!sized) { sized = true; stage.classList.add('is-live'); }
    draw(performance.now());
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
    stage.addEventListener('pointerdown', e => { if (e.pointerType !== 'touch') deal(); });
  }
  const btn = document.querySelector('[data-co-replay]');
  const sync = () => {
    if (btn) btn.hidden = reduce.matches;
    if (reduce.matches && mode !== 2) { mode = 2; if (raf) { cancelAnimationFrame(raf); raf = 0; } still(); }
  };
  if (btn) btn.addEventListener('click', () => { if (mode === 0) deal(); else go(3); });
  if (reduce.addEventListener) reduce.addEventListener('change', sync);
  sync();

  // a fine pointer lights the agent under it (the nearest one: a gap belongs half to each neighbour)
  const pick = (v, A, n) => { let i = n - 1; while (i > 0 && v < (A[i - 1] + 5 * p + A[i]) / 2) i--; return i; };
  const point = e => {
    let h = -1;
    if (mode === 2 && e.type !== 'pointerleave' && e.pointerType !== 'touch') {
      const r = cv.getBoundingClientRect(), k = cv.width / r.width;
      h = pick((e.clientY - r.top) * k, Y, rows) * cols + pick((e.clientX - r.left) * k, X, cols);
    }
    if (h !== hot) { hot = h; still(); }
  };
  stage.addEventListener('pointermove', point);
  stage.addEventListener('pointerleave', point);
})();
