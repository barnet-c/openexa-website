/* OpenEXA — figures
   One compact WebGL point-cloud renderer for the research and company pages. Each [data-figure] stage shows a named
   formation (a sculpture of the idea in the article) and can morph to another — the research index morphs to the
   formation of whichever post you point at. Rotates slowly, tilts with the pointer, glows in two passes, pauses
   off-screen, honours prefers-reduced-motion, and falls back to the inline SVG when WebGL is missing.
   v2x: a stage with data-rest="N" (the research index's plate) moves only while it has something to show: it eases to
   a stop N seconds after its last change or pointer move, holds that frame, and wakes on the next (WCAG 2.2.2 without a
   Pause control). Under reduced motion a change of formation is drawn at once, without the morph.
   v2x lab (research moment): a stage with data-plate is read as a figure, not a sculpture. It faces the reader and sways a
   little instead of spinning (so it comes to rest face-on); its first draw is written left to right, each point where it
   belongs (no frame shows a part where it is not); a new formation arrives left to right; once it lands, one pulse walks the idea's own
   path (the record in order, proposals through the Council, the decision down through the boundary) and the labels in
   its .fig-labels group pin to their points (data-at="x,y,z" in the formation's own space). As the pulse passes the part
   a label names (data-ph, that part's span of the path) the label is lit, so the plate reads itself out in the note's
   order. Words stand only inside the page's content edge and below the bar; beside-the-point words without room swap
   sides; words never cross words or another label's point (the table's order is the priority); a label that cannot
   stand whole is not shown. Everything rests with the stage; under reduced motion the labelled figure is drawn still,
   at once, nothing lit. */
(function () {
  'use strict';
  const stages = Array.from(document.querySelectorAll('[data-figure]'));
  if (!stages.length) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  // a media query, not innerWidth: reading innerWidth forces a layout, and figure.js reads it while the page is still
  // being laid out (r1 perf: 106-161 ms of the research pages' first long task on a slowed phone)
  const narrowMQ = window.matchMedia('(max-width: 759.98px)'), narrow = () => narrowMQ.matches;
  // a 'Pause motion' control on every stage that moves (WCAG 2.2.2), except on the research pages, which stay as they
  // are until the owner decides (D9)
  const pausable = !/^\/research(\.html|\/|$)/.test(location.pathname);

  /* ---------------- geometry helpers (deterministic) ---------------- */
  function makeRng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
  const TAU = Math.PI * 2;

  /* Each generator fills an array of N points as [x, y, z, kind]. kinds: 0 ivory · 1 khaki · 2 green · 3 red · 7 dust */
  const FORMS = {
    // 01 · Compounding error: a monolithic run decays as p^n; a decomposed run is caught at every gate and stays high.
    // v2x r1: the decaying run is ivory, not reject red (red is for rejections only; nothing here is rejected)
    horizon(N, rnd, g) {
      const P = [], floorN = Math.floor(N * 0.18), curveN = Math.floor(N * 0.30), stairN = Math.floor(N * 0.34);
      for (let i = 0; i < floorN; i++) P.push([(rnd() * 2 - 1) * 1.25, -0.72 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 7]);
      for (let i = 0; i < curveN; i++) { const t = rnd(); const y = -0.72 + 1.3 * Math.pow(0.986, t * 160); P.push([-1.15 + t * 2.3, y + g() * 0.02, (rnd() - 0.5) * 0.08 - 0.12, 0, t]); }
      for (let i = 0; i < stairN; i++) { const t = rnd(); const step = Math.floor(t * 10); const y = 0.52 - (step % 2) * 0.05 + g() * 0.012; P.push([-1.15 + t * 2.3, y, (rnd() - 0.5) * 0.08 + 0.14, 2, t]); }
      const gateN = Math.floor(N * 0.011);
      for (let s = 0; s <= 10; s++) { const x = -1.15 + s * 0.23; for (let i = 0; i < gateN; i++) P.push([x + g() * 0.004, -0.72 + rnd() * 1.26, 0.14 + g() * 0.01, 1, s / 10]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 02 · One base model, many adapters, an audit chain beneath
    weights(N, rnd, g) {
      const P = []; const sph = Math.floor(N * 0.42);
      for (let i = 0; i < sph; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, r = 0.46 * Math.pow(rnd(), 0.25); P.push([r * Math.cos(la) * Math.sin(lo), 0.22 + r * Math.sin(la), r * Math.cos(la) * Math.cos(lo), rnd() < 0.08 ? 2 : 0]); }
      const tilts = [[0.35, 0.2], [1.25, 0.9], [2.1, -0.6]];
      tilts.forEach(([tx, tz], k) => { for (let i = 0; i < N * 0.09; i++) { const a = rnd() * TAU; let x = Math.cos(a) * 0.72, y = g() * 0.01, z = Math.sin(a) * 0.72; let y1 = y * Math.cos(tx) - z * Math.sin(tx), z1 = y * Math.sin(tx) + z * Math.cos(tx); const x1 = x * Math.cos(tz) - y1 * Math.sin(tz); y1 = x * Math.sin(tz) + y1 * Math.cos(tz); P.push([x1, 0.22 + y1, z1, k === 1 ? 2 : 1, a / TAU * 0.5]); } });
      for (let b = 0; b < 5; b++) { const y = -0.42 - b * 0.16; for (let i = 0; i < N * 0.04; i++) { const e = rnd(); const w = 0.13, h = 0.05; const side = Math.floor(e * 4); const t = rnd() * 2 - 1; const pt = side === 0 ? [t * w, h] : side === 1 ? [t * w, -h] : side === 2 ? [-w, t * h] : [w, t * h]; P.push([pt[0] + g() * 0.003, y + pt[1] + g() * 0.003, (rnd() - 0.5) * 0.02, 2, 0.55 + b * 0.1]); } for (let i = 0; i < N * 0.006; i++) P.push([0, y + 0.05 + rnd() * 0.06, 0, 7, 0.52 + b * 0.1]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 1.0, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 03 · Not tasks, lifecycles: a loop of six gates, agents flowing round it, the sixth gate lit
    lifecycle(N, rnd, g) {
      const P = []; const ringN = Math.floor(N * 0.34), nodeN = Math.floor(N * 0.05);
      const tilt = 0.9;
      const on = (a, r, lift) => { const x = Math.cos(a) * r, z = Math.sin(a) * r; return [x, lift + z * Math.sin(tilt) * 0.5, z * Math.cos(tilt)]; };
      for (let i = 0; i < ringN; i++) { const a = rnd() * TAU; const p = on(a, 0.95 + g() * 0.02, g() * 0.015); P.push([p[0], p[1], p[2], rnd() < 0.15 ? 2 : 0, ((a - 0.5 + TAU) % TAU) / TAU * 6 / 5.4]); }
      for (let n = 0; n < 6; n++) { const p = on(n / 6 * TAU + 0.5, 0.95, 0); for (let i = 0; i < nodeN; i++) P.push([p[0] + g() * 0.045, p[1] + g() * 0.045, p[2] + g() * 0.045, n === 5 ? 2 : 0, n / 5.4]); }
      for (let i = 0; i < N * 0.18; i++) { const p = on(rnd() * TAU, 0.2 + rnd() * 0.7, 0); P.push([p[0] + g() * 0.01, p[1] + g() * 0.01, p[2] + g() * 0.01, 7]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 04 · One large agent versus thousands of small ones
    swarm(N, rnd, g) {
      const P = []; const mono = Math.floor(N * 0.30);
      for (let i = 0; i < mono; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, r = 0.42 * Math.pow(rnd(), 0.4); P.push([-0.72 + r * Math.cos(la) * Math.sin(lo), r * Math.sin(la), r * Math.cos(la) * Math.cos(lo), 1]); }
      for (let i = 0; i < N * 0.56; i++) { const gx = Math.floor(rnd() * 7), gy = Math.floor(rnd() * 7), gz = Math.floor(rnd() * 3); P.push([0.28 + gx * 0.12 + g() * 0.014, -0.42 + gy * 0.14 + g() * 0.014, -0.16 + gz * 0.16 + g() * 0.014, rnd() < 0.55 ? 2 : 0, ((gx * 37 + gy * 11 + gz * 23) % 49) / 49]); }
      for (let i = 0; i < N * 0.06; i++) P.push([-0.2 + g() * 0.01, (rnd() * 2 - 1) * 0.7, (rnd() - 0.5) * 0.3, 7]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 05 · Eight layers, one boundary: agents decide above the bright plane, code executes below
    boundary(N, rnd, g) {
      const P = []; const per = Math.floor(N * 0.085);
      for (let l = 0; l < 8; l++) { const y = 0.7 - l * 0.2; for (let i = 0; i < per; i++) { const rim = rnd() < 0.3; let x = (rnd() * 2 - 1) * 0.8, z = (rnd() * 2 - 1) * 0.36; if (rim) { if (rnd() < 0.5) z = (rnd() < 0.5 ? -1 : 1) * 0.36; else x = (rnd() < 0.5 ? -1 : 1) * 0.8; } P.push([x + g() * 0.004, y + g() * 0.006, z + g() * 0.004, l === 2 ? (rnd() < 0.7 ? 2 : 0) : l < 4 ? 0 : 1, (l + (l > 3 ? 1 : 0)) / 9]); } }
      for (let i = 0; i < N * 0.14; i++) P.push([(rnd() * 2 - 1) * 0.92, 0.0 + g() * 0.004, (rnd() * 2 - 1) * 0.46, 2, 4 / 9]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 06 · The rulebook moves into the weights: a dense cube with a lit core, documents drifting in
    rulebook(N, rnd, g) {
      const P = []; const cube = Math.floor(N * 0.62);
      for (let i = 0; i < cube; i++) { const x = (rnd() * 2 - 1) * 0.5, y = (rnd() * 2 - 1) * 0.5, z = (rnd() * 2 - 1) * 0.5; const core = Math.hypot(x, y, z) < 0.22; P.push(core ? [x, y, z, 2, 0.96] : [x, y, z, rnd() < 0.5 ? 0 : 1]); }
      for (let d = 0; d < 6; d++) { const a = d / 6 * TAU, cx = Math.cos(a) * 1.05, cz = Math.sin(a) * 1.05, cy = (d % 3 - 1) * 0.35; for (let i = 0; i < N * 0.03; i++) P.push([cx + (rnd() - 0.5) * 0.02, cy + (rnd() - 0.5) * 0.22, cz + (rnd() - 0.5) * 0.16, 0]); for (let i = 0; i < N * 0.015; i++) { const t = rnd(); P.push([cx * (1 - t) + g() * 0.01, cy * (1 - t) + g() * 0.01, cz * (1 - t) + g() * 0.01, 7, 0.08 + t * 0.84]); } }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 07 · The council: proposals stream in from above, approved continue down, rejected leave to the side
    council(N, rnd, g) {
      const P = [];
      for (let i = 0; i < N * 0.18; i++) { const t = rnd(); const a = rnd() * TAU, r = 0.36 + 0.24 * Math.sqrt(rnd()); P.push([Math.cos(a) * r * 0.55 + g() * 0.004, 0.1 + 0.02 * Math.sin(a), Math.sin(a) * r * 0.55 + g() * 0.004, 0, 0.42]); }
      for (let i = 0; i < N * 0.28; i++) { const t = rnd(); P.push([g() * 0.09 * (1 - t) + g() * 0.02, 1.05 - t * 0.9, g() * 0.09 * (1 - t), 1, t * 0.4]); }
      for (let i = 0; i < N * 0.24; i++) { const t = rnd(); P.push([g() * 0.05, 0.05 - t * 1.05, g() * 0.05, 2, 0.46 + t * 0.44]); }
      for (let i = 0; i < N * 0.09; i++) { const t = rnd(); P.push([0.05 + t * 1.1, 0.06 - t * 0.55, g() * 0.03, 3, 0.46 + t * 0.44]); }
      for (let i = 0; i < N * 0.06; i++) P.push([(rnd() * 2 - 1) * 0.6, -1.02 + g() * 0.004, (rnd() * 2 - 1) * 0.3, 2, 0.92]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 1.0, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 08 · A ledger nobody can edit: blocks linked in a chain, each pointing at the one before
    ledger(N, rnd, g) {
      const P = []; const blocks = 8;
      for (let b = 0; b < blocks; b++) {
        const t = b / (blocks - 1), cx = -1.0 + t * 2.0, cy = 0.55 - t * 1.1, cz = Math.sin(t * Math.PI) * 0.25;
        for (let i = 0; i < N * 0.075; i++) { const f = Math.floor(rnd() * 6); const u = rnd() * 2 - 1, v = rnd() * 2 - 1; const w = 0.11, h = 0.07, d = 0.07; const pt = f === 0 ? [u * w, v * h, d] : f === 1 ? [u * w, v * h, -d] : f === 2 ? [u * w, h, v * d] : f === 3 ? [u * w, -h, v * d] : f === 4 ? [w, u * h, v * d] : [-w, u * h, v * d]; P.push([cx + pt[0], cy + pt[1], cz + pt[2], b === blocks - 1 ? 2 : 0, b / blocks]); }
        if (b) { const px = -1.0 + (b - 1) / (blocks - 1) * 2.0, py = 0.55 - (b - 1) / (blocks - 1) * 1.1, pz = Math.sin((b - 1) / (blocks - 1) * Math.PI) * 0.25; for (let i = 0; i < N * 0.03; i++) { const s = rnd(); P.push([px + (cx - px) * s + g() * 0.004, py + (cy - py) * s + g() * 0.004, pz + (cz - pz) * s + g() * 0.004, 2, (b - 1 + s) / blocks]); } }
      }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 09 · Ten sessions above the floor
    // v2x cut (1 Nov; the site's rule: a chart never draws more above the 10 bps floor than one open unit per session):
    // each column fills to the floor (the khaki line) and carries ONE open unit above it, an outline, not a scatter. How
    // far above the floor a session went is not published, and the drawing no longer suggests it. The stack is centred
    // (build_research.py LABELS["sessions"] pins its labels to these points: B, F and U move together with them)
    sessions(N, rnd, g) {
      // each column's NAV regime comes from the session record: data-regimes on the stage (p = premium, d = discount),
      // written by build_research.py from #oxa-sessions. The literal is only the fallback (the research index's morph).
      const rec = (document.querySelector('[data-figure][data-regimes]') || { dataset: {} }).dataset.regimes;
      const P = []; const regime = /^[pd]{10}$/.test(rec || '') ? rec : 'ddppppdpdd'; const per = Math.floor(N * 0.082);
      const B = -0.72, F = 0.48, U = (F - B) / 10, w = 0.07, o0 = F + 0.025, o1 = o0 + U; // ten units to the floor; one open unit above
      for (let c = 0; c < 10; c++) {
        const x = -1.08 + c * 0.24, k = regime[c] === 'p' ? 2 : 0;
        for (let i = 0; i < per; i++) {
          if (rnd() < 0.86) { P.push([x + (rnd() - 0.5) * 2 * w, B + rnd() * (F - B), (rnd() - 0.5) * 0.1, k]); continue; }
          // the open unit: its outline only (the perimeter, sides weighted by length)
          const e = rnd() * (4 * w + 2 * U); let px, py;
          if (e < 2 * w) { px = x - w + e; py = o0; } else if (e < 4 * w) { px = x - w + (e - 2 * w); py = o1; }
          else if (e < 4 * w + U) { px = x - w; py = o0 + (e - 4 * w); } else { px = x + w; py = o0 + (e - 4 * w - U); }
          P.push([px + g() * 0.004, py + g() * 0.004, (rnd() - 0.5) * 0.03, k]);
        }
      }
      for (let i = 0; i < N * 0.08; i++) P.push([(rnd() * 2 - 1) * 1.25, F + g() * 0.005, 0.07, 1]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 10 · Master and copy: one proven agent, replicated onto new assets under one control plane
    mastercopy(N, rnd, g) {
      const P = [];
      const sphere = (cx, cy, cz, r, n, k, ph) => { for (let i = 0; i < n; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = r * Math.pow(rnd(), 0.3); P.push([cx + rr * Math.cos(la) * Math.sin(lo), cy + rr * Math.sin(la), cz + rr * Math.cos(la) * Math.cos(lo), k, ph]); } };
      sphere(0, 0.6, 0, 0.3, Math.floor(N * 0.28), 2, 0.04);
      for (let c = 0; c < 5; c++) { const a = (c / 4 - 0.5) * 2.4; const cx = Math.sin(a) * 1.0, cy = -0.35, cz = Math.cos(a) * 0.35 - 0.2; sphere(cx, cy, cz, 0.17, Math.floor(N * 0.07), c === 0 ? 0 : 1, 0.74); for (let i = 0; i < N * 0.035; i++) { const s = rnd(); P.push([cx * s + g() * 0.006, 0.6 + (cy - 0.6) * s + g() * 0.006, cz * s + g() * 0.006, 7, 0.1 + s * 0.6]); } }
      for (let i = 0; i < N * 0.1; i++) P.push([(rnd() * 2 - 1) * 1.3, -0.75 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 1, 0.9]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // Index · the library: ten leaves fanned round one spine like the pages of an open book, the two research notes lit
    // (v2x: v2 set the leaves edge to edge on one arc, which read as a single slab)
    library(N, rnd, g) {
      const P = []; const per = Math.floor(N * 0.088);
      for (let l = 0; l < 10; l++) { const a = (l / 9 - 0.5) * 2.2; const ux = Math.sin(a), uz = Math.cos(a); for (let i = 0; i < per; i++) { const rim = rnd() < 0.3; let u = 0.12 + rnd() * 0.86, v = rnd() * 2 - 1; if (rim) { if (rnd() < 0.5) v = rnd() < 0.5 ? -1 : 1; else u = rnd() < 0.5 ? 0.12 : 0.98; } P.push([ux * u + g() * 0.003, v * 0.46 + g() * 0.003, uz * u - 0.35 + g() * 0.003, l < 2 ? 2 : (rim ? 0 : 1), (l + u * 0.7) / 10.7]); } }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -1.2 - rnd() * 0.6, 7]);
      return P;
    },
    // Company · the swarm as one body: a sphere of agents with three orbits of work around it
    company(N, rnd, g) {
      const P = []; const sph = Math.floor(N * 0.5);
      for (let i = 0; i < sph; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU; P.push([0.62 * Math.cos(la) * Math.sin(lo), 0.62 * Math.sin(la), 0.62 * Math.cos(la) * Math.cos(lo), rnd() < 0.1 ? 2 : 0]); }
      [[1.1, -0.4], [1.5, 0.6], [0.4, 0.1]].forEach(([tx, tz], k) => { for (let i = 0; i < N * 0.12; i++) { const a = rnd() * TAU; let x = Math.cos(a) * (0.92 + k * 0.12), y = g() * 0.012, z = Math.sin(a) * (0.92 + k * 0.12); let y1 = y * Math.cos(tx) - z * Math.sin(tx), z1 = y * Math.sin(tx) + z * Math.cos(tx); const x1 = x * Math.cos(tz) - y1 * Math.sin(tz); y1 = x * Math.sin(tz) + y1 * Math.cos(tz); P.push([x1, y1, z1, k === 1 ? 2 : k === 0 ? 0 : 1]); } });
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
  };

  const VS = `
  precision highp float;
  attribute vec4 a_a; attribute vec4 a_b; attribute vec4 a_rand;
  uniform mat4 u_proj, u_view; uniform float u_time, u_mix, u_pr, u_spin, u_scale, u_halo, u_maxpt, u_flow, u_pulse, u_sweep, u_reveal;
  varying float v_alpha; varying float v_size; varying vec3 v_col;
  mat3 rotY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0., -s, 0., 1., 0., s, 0., c); }
  vec3 kcol(float k) {
    if (k < 0.5) return vec3(0.961, 0.949, 0.925);
    if (k < 1.5) return vec3(0.675, 0.651, 0.557);
    if (k < 2.5) return vec3(0.310, 0.796, 0.576);
    if (k < 3.5) return vec3(0.839, 0.376, 0.337);
    return vec3(0.35, 0.36, 0.34);
  }
  void main() {
    float kA = floor(a_a.w + 0.001), kB = floor(a_b.w + 0.001);
    float lag = u_sweep * (0.05 + 0.35 * clamp((a_b.x + 1.3) / 2.6, 0.0, 1.0));
    float t = clamp((u_mix - a_rand.y * mix(0.3, 0.08, u_sweep) - lag) / mix(0.7, 0.52, u_sweep), 0.0, 1.0); t = t * t * (3.0 - 2.0 * t);
    vec3 P = mix(a_a.xyz, a_b.xyz, t);
    vec3 dir = a_b.xyz - a_a.xyz; float L = length(dir);
    P += (L > 0.001 ? cross(normalize(dir), vec3(0.0, 0.0, 1.0)) : vec3(0.0)) * sin(t * 3.14159) * (0.1 + 0.2 * a_rand.z) * min(L, 1.0) * (1.0 - 0.7 * u_sweep);
    P += 0.008 * vec3(sin(u_time * 0.9 + a_rand.x * 6.283), cos(u_time * 0.7 + a_rand.y * 6.283), sin(u_time * 1.1 + a_rand.z * 6.283));
    P = rotY(u_spin) * P * u_scale;
    vec4 mv = u_view * vec4(P, 1.0); gl_Position = u_proj * mv;
    float depth = clamp((mv.z + 5.6) / 2.6, 0.0, 1.0);
    float k = mix(kA, kB, step(0.5, t));
    float fr = mix(a_a.w - kA, a_b.w - kB, step(0.5, t)), d = u_flow - (fr - 0.1) / 0.8;
    float glow = fr > 0.05 ? u_pulse * (d < 0.0 ? exp(-d * d * 2500.0) : exp(-d * 15.0)) : 0.0;
    float vis = clamp((u_reveal - clamp((a_b.x + 1.45) / 2.9, 0.0, 1.0)) / 0.05, 0.0, 1.0); // the first draw, left to right
    float dust = (k > 6.5) ? 0.16 : 1.0;
    float accent = (k > 1.5 && k < 2.5) ? 1.3 : 1.0;
    float pulse = accent > 1.0 ? (0.86 + 0.14 * sin(u_time * 2.2 + a_rand.w * 6.283)) : 1.0;
    float sz = (1.65 + a_rand.x * 2.0) * (0.6 + depth * 0.8) * accent * (dust < 0.5 ? 0.7 : 1.0) * pulse * (1.0 + 0.4 * glow) * mix(0.3, 1.0, vis);
    float al = (0.26 + 0.6 * depth) * dust * (accent > 1.0 ? 1.15 : 1.0) * (1.0 + 1.15 * glow) * vis;
    float px = min(sz * u_pr * (u_halo > 0.5 ? 3.6 : 1.0), u_maxpt);
    gl_PointSize = px; v_size = px;
    v_alpha = u_halo > 0.5 ? al * (accent > 1.0 ? 0.17 : 0.038) : al;
    v_col = mix(mix(kcol(kA), kcol(kB), t), vec3(1.0), 0.14 * glow);
  }`;
  /* Sprites are resolution-aware: the disc edge is one device pixel wide whatever the size, so points stay round
     and crisp at 3x without shimmering; the halo is a true gaussian so the bloom has no visible edge. */
  const FS = `
  #ifdef GL_FRAGMENT_PRECISION_HIGH
  precision highp float;
  #else
  precision mediump float;
  #endif
  uniform float u_halo; varying float v_alpha; varying float v_size; varying vec3 v_col;
  void main() {
    vec2 q = gl_PointCoord - 0.5; float d = length(q);
    float a;
    if (u_halo > 0.5) { a = exp(-d * d * 14.0) * (1.0 - smoothstep(0.42, 0.5, d)) * v_alpha; }
    else {
      float edge = 1.0 / max(v_size, 1.5);
      float disc = 1.0 - smoothstep(0.5 - edge * 1.4, 0.5, d);
      float bead = 0.78 + 0.22 * (1.0 - smoothstep(0.0, 0.5, d));
      a = disc * bead * v_alpha;
    }
    gl_FragColor = vec4(v_col * a, a);
  }`;

  function perspective(out, fovy, aspect, near, far) { const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far); out.fill(0); out[0] = f / aspect; out[5] = f; out[10] = (far + near) * nf; out[11] = -1; out[14] = 2 * far * near * nf; }
  function lookAt(out, eye) {
    let zx = eye[0], zy = eye[1], zz = eye[2]; let l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
    let xx = zz, xz = -zx; l = Math.hypot(xx, xz) || 1; xx /= l; xz /= l;
    const yx = zy * xz, yy = zz * xx - zx * xz, yz = -zy * xx;
    out[0] = xx; out[1] = yx; out[2] = zx; out[3] = 0; out[4] = 0; out[5] = yy; out[6] = zy; out[7] = 0; out[8] = xz; out[9] = yz; out[10] = zz; out[11] = 0;
    out[12] = -(xx * eye[0] + xz * eye[2]); out[13] = -(yx * eye[0] + yy * eye[1] + yz * eye[2]); out[14] = -(zx * eye[0] + zy * eye[1] + zz * eye[2]); out[15] = 1;
  }

  // a stage that cannot draw at all (no canvas, no WebGL, a program that fails) says so to its page: a caption must not
  // describe a figure that is not there (research.js hides the captions and the index plate)
  const none = stage => { stage.classList.add('no-figure'); stage.dispatchEvent(new CustomEvent('figure:none', { bubbles: true })); };
  function init(stage) {
    // v2x cut (1 Nov): a plate's labels arrive as <template data-labels> (instrument text, not page text: nothing shows them
    // until the figure draws); they join the stage here, before the groups below are read
    stage.querySelectorAll(':scope > template[data-labels]').forEach(t => t.replaceWith(t.content));
    const cv = stage.querySelector('canvas');
    const initial = stage.dataset.figure;
    if (!cv || !FORMS[initial]) { none(stage); return; }
    let gl = null;
    try { gl = cv.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: true, powerPreference: 'low-power' }); } catch (e) { gl = null; }
    if (!gl) { none(stage); return; }
    const N = narrow() ? 7000 : 15000;
    const rnd = makeRng(41), g = () => (rnd() + rnd() + rnd() - 1.5) * 0.82;
    const RAND = new Float32Array(N * 4); for (let i = 0; i < N * 4; i++) RAND[i] = rnd();
    const built = {};
    const build = (name) => { if (!built[name]) { const r = makeRng(name.length * 977 + 13), gg = () => (r() + r() + r() - 1.5) * 0.82; const pts = FORMS[name](N, r, gg); const f = new Float32Array(N * 4); for (let i = 0; i < N; i++) { const p = pts[i] || [0, 0, -2, 7]; f[i * 4] = p[0]; f[i * 4 + 1] = p[1]; f[i * 4 + 2] = p[2]; f[i * 4 + 3] = p[3] + (p[4] >= 0 ? 0.1 + 0.8 * Math.min(1, p[4]) : 0); } built[name] = f; } return built[name]; };
    let prog = null, bufA = null, bufB = null;
    const U = {};
    const buf = (name, data) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW); const loc = gl.getAttribLocation(prog, name); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 0, 0); return b; };
    const fail = (msg, log) => { if (!gl.isContextLost()) { console.warn(msg, log); none(stage); } };
    // program, buffers and constant state — built once, and again in place when a lost context is restored
    let setupGen = 0; // a quick lose/restore starts a new setup: the old link poll must stop, not spin on a dead program
    function setup(done) {
      try {
        const shader = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
        const vs = shader(gl.VERTEX_SHADER, VS), fs = shader(gl.FRAGMENT_SHADER, FS), p = gl.createProgram();
        gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
        const par = gl.getExtension('KHR_parallel_shader_compile'); // poll the link instead of stalling the main thread on it
        const gen = ++setupGen;
        (function linked() {
          try {
            if (gen !== setupGen || gl.isContextLost()) return; // the restore starts over
            if (par && !gl.getProgramParameter(p, par.COMPLETION_STATUS_KHR)) { requestAnimationFrame(linked); return; }
            if (!gl.getProgramParameter(p, gl.LINK_STATUS)) { fail('figure program:', gl.getShaderInfoLog(vs) || gl.getShaderInfoLog(fs) || gl.getProgramInfoLog(p)); return; }
            prog = p; gl.useProgram(prog);
            const target = build(current); mix = 1; // a restore lands on the current formation
            if (plate && gen === 1 && !reduced.matches) reveal = -0.06; // a plate's first draw is written left to right
            bufA = buf('a_a', target); bufB = buf('a_b', target); buf('a_rand', RAND);
            ['u_proj', 'u_view', 'u_time', 'u_mix', 'u_pr', 'u_spin', 'u_scale', 'u_halo', 'u_maxpt', 'u_flow', 'u_pulse', 'u_sweep', 'u_reveal'].forEach(n => U[n] = gl.getUniformLocation(prog, n));
            gl.uniform1f(U.u_maxpt, (gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE) || [1, 64])[1]);
            gl.enable(gl.BLEND); gl.disable(gl.DEPTH_TEST);
            done();
          } catch (e) { fail('figure:', e); }
        })();
      } catch (e) { fail('figure:', e); }
    }
    const proj = new Float32Array(16), view = new Float32Array(16);
    let W = 1, H = 1, dpr = 1, time = 0, mix = 1, current = initial, spinBase = parseFloat(stage.dataset.spin || '0.12');
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    let frameId = 0, visible = true, lost = false, last = performance.now(), paused = false, motionBtn = null;
    const rest = parseFloat(stage.dataset.rest || '0') * 1000; let woke = performance.now(), vel = 1; // data-rest (v2x)
    let homing = false; // a resting stage turns a new formation to face the reader while it morphs, then drifts on
    // data-plate (lab): face the reader and sway, draw a new formation left to right, one pulse along its path, labels
    const plate = 'plate' in stage.dataset; let sweep = 0, flow = 0, reveal = 2;
    const landed = () => mix >= 1 && reveal >= 1.1;
    // a plate fills its stage alike whatever the formation's own size (the flat ring and the small cube are drawn larger);
    // the size changes with the morph
    const FIT = { lifecycle: 1.16, rulebook: 1.12 }; let fitA = plate ? FIT[initial] || 1 : 1, fitB = fitA;
    const fitNow = () => fitA + (fitB - fitA) * mix * mix * (3 - 2 * mix);
    const SWAY = 0.2, FLOW_S = 1.5; // radians either side of face-on; seconds per pass of the pulse
    const groups = {}; let grp = null, grpOn = false;
    stage.querySelectorAll('.fig-labels').forEach(el => { groups[el.dataset.for] = { el, items: Array.from(el.querySelectorAll('.fl')).map(l => ({ el: l, at: l.dataset.at.split(',').map(Number), side: l.dataset.side || 'r', ph: l.dataset.ph ? l.dataset.ph.split(',').map(Number) : null, to: l.dataset.to ? l.dataset.to.split(',').map(Number) : null, keep: l.hasAttribute('data-keep'), sides: (l.dataset.keep || '').split(' ').filter(Boolean), lead: 19, w: 0, h: 0, w1: 0, h1: 0, drop: 0, one: false, dropSet: 0, oneSet: false, x: NaN, y: NaN, dx: 0, out: false, lit: false })) }; });
    grp = groups[initial] || null;
    // where the words may stand (stage px): inside the page's content edge, never under the bar (a hero stage starts at
    // the top of the page); a label that cannot stand there whole is not shown
    const safe = { l: 0, r: 1, t: 0 };
    function measureSafe() {
      const r = stage.getBoundingClientRect(), box = stage.parentElement && stage.parentElement.querySelector(':scope > .container'), bar = document.querySelector('header.nav');
      safe.l = 0; safe.r = r.width;
      if (box) { const b = box.getBoundingClientRect(), cs = getComputedStyle(box); safe.l = Math.max(0, b.left + parseFloat(cs.paddingLeft) - r.left); safe.r = Math.min(r.width, b.right - parseFloat(cs.paddingRight) - r.left); }
      safe.t = bar ? Math.max(0, bar.offsetHeight - (r.top + window.scrollY)) : 0;
    }
    const wake = home => { woke = performance.now(); if (rest && home) homing = true; };
    // the formation's size: data-scale, or the stage's --figure-scale (a stylesheet may size it per layout; read on resize)
    const baseScale = parseFloat(stage.dataset.scale || '1'); let scale = baseScale;
    const cssScale = () => { const v = parseFloat(getComputedStyle(stage).getPropertyValue('--figure-scale')); scale = v > 0 ? v : baseScale; };
    // render at the device's full resolution (up to 3x), within a UHD pixel budget so a large stage on a 3x display stays fluid
    const PIXEL_BUDGET = 3840 * 2160;
    function resize() { if (!prog || lost) return; cssScale(); if (plate) { measureSafe(); if (grpOn) labelsOn(); } const r = cv.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height); dpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(PIXEL_BUDGET / (W * H))); cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); gl.viewport(0, 0, cv.width, cv.height); perspective(proj, 0.62, W / H, 0.1, 30); gl.uniform1f(U.u_pr, dpr); draw(true); }
    function draw(force) {
      const now = performance.now(); const dt = Math.min(0.05, (now - last) / 1000); last = now;
      const moving = !reduced.matches && !paused;
      const awake = !rest || now - woke < rest; // a resting stage eases its spin to a stop, then stops asking for frames
      if (moving) { if (rest) { vel += ((awake ? 1 : 0) - vel) * Math.min(1, dt * 2.4); if (!awake && vel < 0.004) { vel = 0; planned = false; } } time += dt * vel; if (plate && landed()) flow += dt * vel; if (homing && !plate) { const a = time * spinBase, to = Math.round(a / TAU) * TAU; time += (to - a) / spinBase * Math.min(1, dt * 3); if (Math.abs(to - a) < 0.004) homing = false; } mouse.x += (mouse.tx - mouse.x) * 0.05; mouse.y += (mouse.ty - mouse.y) * 0.05; }
      if (mix < 1) mix = Math.min(1, mix + dt * (plate ? 1.25 : 0.9));
      if (reveal < 1.1) reveal = moving ? reveal + dt * 1.15 : 1.1;
      const ang = mouse.x * 0.35, elev = 0.35 + mouse.y * 0.25;
      lookAt(view, [Math.sin(ang) * 4.4, elev, Math.cos(ang) * 4.4]);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniformMatrix4fv(U.u_proj, false, proj); gl.uniformMatrix4fv(U.u_view, false, view);
      const spin = plate ? SWAY * Math.sin(time * 0.5) * (rest ? vel : 1) : time * spinBase, sc = scale * (narrow() ? 0.86 : 1) * fitNow();
      gl.uniform1f(U.u_time, time); gl.uniform1f(U.u_mix, mix); gl.uniform1f(U.u_spin, spin); gl.uniform1f(U.u_scale, sc);
      const at = (flow / FLOW_S % 1) * 1.32 - 0.12, amp = plate && moving && landed() ? (rest ? vel : 1) * Math.min(1, flow * 2.5) : 0;
      gl.uniform1f(U.u_sweep, sweep); gl.uniform1f(U.u_flow, at);
      gl.uniform1f(U.u_pulse, amp); gl.uniform1f(U.u_reveal, reveal);
      gl.blendFunc(gl.ONE, gl.ONE); gl.uniform1f(U.u_halo, 1); gl.drawArrays(gl.POINTS, 0, N);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.uniform1f(U.u_halo, 0); gl.drawArrays(gl.POINTS, 0, N);
      stage.classList.add('figure-ready');
      if (grp) { if (!grpOn && landed()) labelsOn(); if (grpOn) { if (!planned) plan(sc); place(spin, sc); light(amp > 0.3 ? at : NaN); } }
      if (!force && ((moving && (awake || vel > 0)) || mix < 1 || reveal < 1.1)) request();
    }
    function labelsOn() {
      grpOn = true; planned = false; grp.items.forEach(it => {
        if (it.oneSet) { it.el.classList.remove('is-one'); it.oneSet = false; }
        const t = it.el.firstElementChild; it.w = t ? t.offsetWidth : 0; it.h = t ? t.offsetHeight : 0; it.x = NaN; it.sd = it.side; it.blocked = false; it.drop = 0; it.one = false;
        // a hedge label's words on one line, measured for the slot search (r3)
        it.w1 = it.h1 = 0;
        if (it.keep && t && t.querySelector('small')) { it.el.classList.add('is-one'); it.w1 = t.offsetWidth; it.h1 = t.offsetHeight; it.el.classList.remove('is-one'); }
      });
      grp.el.classList.add('is-on');
    }
    // the formation's point (x, y, z), turned by the sway and sized, onto the stage (px); false behind the eye
    const scr = [0, 0];
    function project(x, y, z, s, c, sc) {
      const X = (c * x + s * z) * sc, Y = y * sc, Z = (-s * x + c * z) * sc;
      const v0 = view[0] * X + view[4] * Y + view[8] * Z + view[12], v1 = view[1] * X + view[5] * Y + view[9] * Z + view[13], v2 = view[2] * X + view[6] * Y + view[10] * Z + view[14], v3 = view[3] * X + view[7] * Y + view[11] * Z + view[15];
      const w = proj[3] * v0 + proj[7] * v1 + proj[11] * v2 + proj[15] * v3; if (w <= 0) return false;
      scr[0] = Math.round(((proj[0] * v0 + proj[4] * v1 + proj[8] * v2 + proj[12] * v3) / w * 0.5 + 0.5) * W);
      scr[1] = Math.round((0.5 - (proj[1] * v0 + proj[5] * v1 + proj[9] * v2 + proj[13] * v3) / w * 0.5) * H);
      return true;
    }
    /* words never stand on their own drawing (v2x, jury A1 condition 4). Once a formation lands, on a resize and again
       when the plate comes to rest, a sample of its points (no dust) is projected in the pose it rests in (face-on) onto
       a grid of 8 px cells. A label whose words would cover more than three occupied cells takes the other side of its
       point (left/right, above/below); if that is covered too, or off the stage, it is not shown: the caption says the
       same words. The side chosen holds until the next plan, so a swaying plate never flips its labels. */
    const CELL = 8; let occ = null, oc = 0, orow = 0, occN = 0, planned = false;
    const hits = (x0, y0, x1, y1) => {
      let n = 0; const c0 = Math.max(0, Math.floor(x0 / CELL)), c1 = Math.min(oc - 1, Math.floor(x1 / CELL)), r0 = Math.max(0, Math.floor(y0 / CELL)), r1 = Math.min(orow - 1, Math.floor(y1 / CELL));
      for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) n += occ[r * oc + c];
      return n;
    };
    function plan(sc) {
      planned = true;
      const pts = built[current]; if (!pts) return;
      oc = Math.ceil(W / CELL); orow = Math.ceil(H / CELL);
      if (!occ || occ.length < oc * orow) occ = new Uint16Array(oc * orow); else occ.fill(0);
      let S = 0;
      for (let i = 0, step = Math.max(1, Math.floor(N / 3000)); i < N; i += step) {
        if (pts[i * 4 + 3] >= 6.5 || !project(pts[i * 4], pts[i * 4 + 1], pts[i * 4 + 2], 0, 1, sc)) continue;
        if (scr[0] >= 0 && scr[1] >= 0 && scr[0] < W && scr[1] < H) { occ[Math.floor(scr[1] / CELL) * oc + Math.floor(scr[0] / CELL)]++; S++; }
      }
      occN = S; place(0, sc, true);
    }
    function labelsOff() { if (grp) { grp.el.classList.remove('is-on'); grp.items.forEach(it => { if (it.lit) { it.el.classList.remove('is-lit'); it.lit = false; } }); } grpOn = false; }
    // the pulse names each part as it passes: a label whose part (data-ph, the span of the formation's own path it
    // labels) holds the pulse is lit; it stays lit while the trail goes by
    function light(f) {
      grp.items.forEach(it => { const on = !!it.ph && f >= it.ph[0] - 0.02 && f <= it.ph[it.ph.length - 1] + 0.08; if (on !== it.lit) { it.el.classList.toggle('is-lit', on); it.lit = on; } });
    }
    const mirror = d => d === 'l' ? 'r' : d === 'r' ? 'l' : (d[0] === 't' ? 'b' : 't') + d.slice(1);
    /* r3 (a11y): a label that carries a hedge (data-keep: note 09 "how far is not published", note 10 "phase two, on the
       roadmap") is listed first, so the claim-side labels yield to it where words would cross. Where its own side and
       the other have no room (a phone's stage), it tries the sides its data-keep allows (all if empty), a rule 8 px
       shorter or up to 96 px longer, and its two lines set as one; the first slot inside the stage, clear of the drawing
       (at most three of its sampled points) and of its own point wins. If none does, no label of the group is shown: a
       part is never named without its hedge (the caption says it all) */
    const SIDES = ['t', 'b', 'r', 'l', 'tr', 'tl', 'br', 'bl'], DROPS = [0, -8, 12, 24, 36, 48, 60, 72, 84, 96];
    const setOut = (it, out) => { if (out !== it.out) { it.el.classList.toggle('is-out', out); it.out = out; } };
    function place(spin, sc, planning) {
      const s = Math.sin(spin), c = Math.cos(spin), M = 6, L = safe.l + M, R = safe.r - M, T = safe.t + 4, B = H - 4, taken = [];
      let bare = false; // the hedge label is not shown, so no other label is
      grp.items.forEach(it => {
        if (!project(it.at[0], it.at[1], it.at[2], s, c, sc)) { if (it.keep) { bare = true; setOut(it, true); } return; }
        const px = scr[0], py = scr[1];
        // a label whose point lies inside the drawing (data-to: where its words begin, in the formation's space) reaches
        // out on a longer rule, so its words stand clear of what surrounds the point
        if (it.to && project(it.to[0], it.to[1], it.to[2], s, c, sc)) { const lead = Math.max(19, Math.round(Math.abs(scr[0] - px))); if (lead !== it.lead) { it.lead = lead; it.el.style.setProperty('--lead', `${lead}px`); } }
        // keep the words inside the safe box: the text slides along its rule, the point stays where it is; a label whose
        // point or words would stand outside it (beyond the content edge, under the bar), or wider than it, is not shown
        const off = (d, w) => d === 'l' ? -it.lead - w : d === 'r' ? it.lead : d.length > 1 ? (d[1] === 'l' ? 6 - w : -6) : -w / 2;
        const over = q => Math.max(L - q.left, q.left + q.w - R, 0);
        const at = (sd, drop, one) => {
          const w = one ? it.w1 : it.w, h = one ? it.h1 : it.h, left = px + off(sd, w), top = sd[0] === 't' ? py - 18 - drop - h : sd[0] === 'b' ? py + 18 + drop : py - 7;
          const dx = left < L ? L - left : left + w > R ? R - left - w : 0;
          return { sd, drop, one, w, h, left, top, dx, bad: top < T || top + h > B || Math.abs(dx) > w * 0.5 + 12 || w > R - L };
        };
        if (planning) {
          // words beside a point that lack room on their side (more than a short slide) stand on the other, if they fit
          // there; words that would lie on the drawing do the same, or are not shown
          let g = at(it.side, 0, false);
          if ((g.sd === 'l' || g.sd === 'r') && over(g) > 16) { const o = at(mirror(g.sd), 0, false); if (!over(o)) g = o; }
          const covered = q => hits(q.left + q.dx, q.top, q.left + q.dx + q.w, q.top + q.h) > Math.max(6, 0.35 * occN * q.w * q.h / (W * H));
          it.blocked = false;
          if (it.w && covered(g)) { const o = at(mirror(g.sd), 0, false); if (!o.bad && !covered(o)) g = o; else it.blocked = true; }
          if (it.keep && it.w && (it.blocked || g.bad)) {
            it.blocked = true;
            const clear = q => hits(q.left + q.dx, q.top, q.left + q.dx + q.w, q.top + q.h) <= 3 && !(px > q.left + q.dx - 4 && px < q.left + q.dx + q.w + 4 && py > q.top - 3 && py < q.top + q.h + 3);
            const sides = [it.side, mirror(it.side), ...SIDES].filter(sd => !it.sides.length || it.sides.includes(sd));
            search: for (const drop of DROPS) for (const one of it.w1 ? [false, true] : [false]) for (const sd of sides) {
              if (drop && (sd === 'l' || sd === 'r')) continue;
              const q = at(sd, drop, one); if (!q.bad && clear(q)) { g = q; it.blocked = false; break search; }
            }
          }
          it.sd = g.sd; it.drop = g.drop; it.one = g.one; return;
        }
        const { sd, left, top, dx, bad, w, h } = at(it.sd || it.side, it.drop, it.one);
        if (sd !== it.el.dataset.side) it.el.dataset.side = sd;
        if (it.drop !== it.dropSet) { it.el.style.setProperty('--drop', `${it.drop}px`); it.dropSet = it.drop; }
        if (it.one !== it.oneSet) { it.el.classList.toggle('is-one', it.one); it.oneSet = it.one; }
        let out = bare || it.blocked || px < safe.l || px > safe.r || py < T || py > B || bad;
        // words never cross words: a label that would touch one shown before it (the table's order is the priority) waits
        if (!out && w) { const x0 = left + dx - 4, x1 = left + dx + w + 4; if (taken.some(b => x0 < b[2] && x1 > b[0] && top - 3 < b[3] && top + h + 3 > b[1])) out = true; else taken.push([x0, top, x1, top + h], [px - 5, py - 5, px + 5, py + 5]); }
        if (it.keep && out) bare = true;
        if (px !== it.x || py !== it.y) { it.el.style.transform = `translate(${px}px, ${py}px)`; it.x = px; it.y = py; }
        if (dx !== it.dx) { it.el.style.setProperty('--dx', `${Math.round(dx)}px`); it.dx = dx; }
        setOut(it, out);
      });
    }
    function frame() { frameId = 0; if (!visible || document.hidden || lost || paused) return; draw(false); }
    function request() { if (!frameId && prog && visible && !document.hidden && !lost && !paused) frameId = requestAnimationFrame(frame); }
    function stop() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
    /* Pause motion: the stage's loop stops at once (no frame is requested until Resume) and the figure holds its last
       frame; a mode chosen meanwhile is drawn once, in place. The control is offered while the stage moves: not under
       reduced motion, not for the static fallback, not while the stage is not laid out (Company §04 on phones). Its
       label says what it will do (as the overture's), so it carries no pressed state. */
    function syncMotion() { if (motionBtn) motionBtn.hidden = reduced.matches || lost || !stage.getClientRects().length; }
    function setPaused(p) {
      paused = p;
      if (motionBtn) motionBtn.textContent = p ? 'Resume motion' : 'Pause motion';
      if (p) stop(); else { last = performance.now(); request(); }
    }
    function addMotion() {
      if (!pausable || motionBtn || !stage.parentElement) return;
      motionBtn = document.createElement('button');
      motionBtn.type = 'button'; motionBtn.className = 'figure-motion'; motionBtn.textContent = 'Pause motion';
      motionBtn.addEventListener('click', () => setPaused(!paused));
      stage.parentElement.appendChild(motionBtn); // after the stage's own content: the page's text comes first in the Tab order
      syncMotion();
    }
    stage.__figure = {
      show(name) {
        if (!FORMS[name] || name === current) return;
        stage.dataset.figureCurrent = name;
        if (!prog || lost) { current = name; if (plate) { labelsOff(); grp = groups[name] || null; fitA = fitB = FIT[name] || 1; } return; } // not drawing yet: setup or the restore starts on this formation
        if (plate) { fitA = fitNow(); fitB = FIT[name] || 1; }
        // the current target becomes the origin; snapping mid-morph is invisible at these speeds
        gl.bindBuffer(gl.ARRAY_BUFFER, bufA); gl.bufferData(gl.ARRAY_BUFFER, build(current), gl.DYNAMIC_DRAW);
        gl.bindBuffer(gl.ARRAY_BUFFER, bufB); gl.bufferData(gl.ARRAY_BUFFER, build(name), gl.DYNAMIC_DRAW);
        current = name; wake(true);
        if (plate) { sweep = name === 'sessions' ? 0 : 1; flow = 0; labelsOff(); grp = groups[name] || null; }
        // paused or reduced motion: the new formation, in place, in one frame
        if (paused || reduced.matches) { mix = 1; reveal = 2; if (visible && !document.hidden) draw(true); }
        else { mix = 0; request(); }
      },
    };
    stage.dataset.figureCurrent = initial;
    // a lost context shows the static mark; a restored one is rebuilt in place and carries on
    cv.addEventListener('webglcontextlost', e => { e.preventDefault(); lost = true; prog = null; stop(); stage.classList.add('no-figure'); syncMotion(); });
    cv.addEventListener('webglcontextrestored', () => { lost = false; setup(() => { stage.classList.remove('no-figure'); resize(); request(); syncMotion(); }); });
    if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { const was = visible; visible = e.isIntersecting; if (visible) { if (plate && rest && !was) wake(); request(); } else stop(); }, { threshold: 0 }).observe(stage);
    if (plate && document.fonts) document.fonts.ready.then(() => { if (grpOn) { grpOn = false; if (prog && !lost) draw(true); } }); // labels measured in their own face
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else request(); });
    reduced.addEventListener('change', () => { mouse.tx = mouse.ty = 0; request(); syncMotion(); });
    if ('ResizeObserver' in window) new ResizeObserver(() => { resize(); syncMotion(); }).observe(stage); else window.addEventListener('resize', () => { resize(); syncMotion(); });
    // a move to a display with another pixel ratio changes no CSS size: watch the ratio itself, re-arming each time
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    stage.addEventListener('pointermove', e => { if (reduced.matches || e.pointerType === 'touch') return; const r = stage.getBoundingClientRect(); mouse.tx = (e.clientX - r.left) / r.width - 0.5; mouse.ty = (e.clientY - r.top) / r.height - 0.5; if (rest) { wake(); request(); } }, { passive: true });
    stage.addEventListener('pointerleave', () => { mouse.tx = mouse.ty = 0; });
    // the context in this task, the program in the next: two shorter tasks, not one long one (r1 perf)
    setTimeout(() => { if (!lost) setup(() => { resize(); request(); addMotion(); }); }, 0);
  }
  // after the first paint, one stage per task: context creation and shader compilation never hold up a frame
  requestAnimationFrame(() => stages.forEach(s => setTimeout(() => init(s), 0)));

  // the research index: point at a post, the sculpture becomes that post's figure
  document.querySelectorAll('[data-figure-target]').forEach(el => {
    const stage = document.querySelector(el.dataset.figureStage ? `#${el.dataset.figureStage}` : '[data-figure]');
    // before its stage has started, the choice becomes the formation it starts on
    const go = () => { if (!stage) return; if (stage.__figure) stage.__figure.show(el.dataset.figureTarget); else stage.dataset.figure = el.dataset.figureTarget; };
    if (el.tagName === 'BUTTON') {
      // mode buttons: click switches the figure, marks the pressed state among siblings and swaps the caption
      el.addEventListener('click', () => {
        go();
        const group = el.parentElement;
        group.querySelectorAll('[data-figure-target]').forEach(b => b.setAttribute('aria-pressed', String(b === el)));
        const copy = document.querySelector(group.dataset.figureCopy ? `#${group.dataset.figureCopy}` : '[data-figure-copy]');
        if (copy && el.dataset.copy) copy.textContent = el.dataset.copy;
      });
    } else { el.addEventListener('pointerenter', go); el.addEventListener('focusin', go); }
  });
})();
