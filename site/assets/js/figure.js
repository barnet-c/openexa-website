/* OpenEXA — figures
   One compact WebGL point-cloud renderer for the research and company pages. Each [data-figure] stage shows a named
   formation (a sculpture of the idea in the article) and can morph to another — the research index morphs to the
   formation of whichever post you point at. Rotates slowly, tilts with the pointer, glows in two passes, pauses
   off-screen, honours prefers-reduced-motion, and falls back to the inline SVG when WebGL is missing. */
(function () {
  'use strict';
  const stages = Array.from(document.querySelectorAll('[data-figure]'));
  if (!stages.length) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const narrow = () => window.innerWidth < 760;

  /* ---------------- geometry helpers (deterministic) ---------------- */
  function makeRng(seed) { let s = seed >>> 0; return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; }
  const TAU = Math.PI * 2;

  /* Each generator fills an array of N points as [x, y, z, kind]. kinds: 0 ivory · 1 khaki · 2 green · 3 red · 7 dust */
  const FORMS = {
    // 01 · Compounding error: a monolithic run decays as p^n; a decomposed run is caught at every gate and stays high
    horizon(N, rnd, g) {
      const P = [], floorN = Math.floor(N * 0.18), curveN = Math.floor(N * 0.30), stairN = Math.floor(N * 0.34);
      for (let i = 0; i < floorN; i++) P.push([(rnd() * 2 - 1) * 1.25, -0.72 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 7]);
      for (let i = 0; i < curveN; i++) { const t = rnd(); const y = -0.72 + 1.3 * Math.pow(0.986, t * 160); P.push([-1.15 + t * 2.3, y + g() * 0.02, (rnd() - 0.5) * 0.08 - 0.12, t < 0.08 ? 0 : 3]); }
      for (let i = 0; i < stairN; i++) { const t = rnd(); const step = Math.floor(t * 10); const y = 0.52 - (step % 2) * 0.05 + g() * 0.012; P.push([-1.15 + t * 2.3, y, (rnd() - 0.5) * 0.08 + 0.14, 2]); }
      const gateN = Math.floor(N * 0.011);
      for (let s = 0; s <= 10; s++) { const x = -1.15 + s * 0.23; for (let i = 0; i < gateN; i++) P.push([x + g() * 0.004, -0.72 + rnd() * 1.26, 0.14 + g() * 0.01, 1]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 02 · One base model, many adapters, an audit chain beneath
    weights(N, rnd, g) {
      const P = []; const sph = Math.floor(N * 0.42);
      for (let i = 0; i < sph; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, r = 0.46 * Math.pow(rnd(), 0.25); P.push([r * Math.cos(la) * Math.sin(lo), 0.22 + r * Math.sin(la), r * Math.cos(la) * Math.cos(lo), rnd() < 0.08 ? 2 : 0]); }
      const tilts = [[0.35, 0.2], [1.25, 0.9], [2.1, -0.6]];
      tilts.forEach(([tx, tz], k) => { for (let i = 0; i < N * 0.09; i++) { const a = rnd() * TAU; let x = Math.cos(a) * 0.72, y = g() * 0.01, z = Math.sin(a) * 0.72; let y1 = y * Math.cos(tx) - z * Math.sin(tx), z1 = y * Math.sin(tx) + z * Math.cos(tx); const x1 = x * Math.cos(tz) - y1 * Math.sin(tz); y1 = x * Math.sin(tz) + y1 * Math.cos(tz); P.push([x1, 0.22 + y1, z1, k === 1 ? 2 : 1]); } });
      for (let b = 0; b < 5; b++) { const y = -0.42 - b * 0.16; for (let i = 0; i < N * 0.04; i++) { const e = rnd(); const w = 0.13, h = 0.05; const side = Math.floor(e * 4); const t = rnd() * 2 - 1; const pt = side === 0 ? [t * w, h] : side === 1 ? [t * w, -h] : side === 2 ? [-w, t * h] : [w, t * h]; P.push([pt[0] + g() * 0.003, y + pt[1] + g() * 0.003, (rnd() - 0.5) * 0.02, 2]); } for (let i = 0; i < N * 0.006; i++) P.push([0, y + 0.05 + rnd() * 0.06, 0, 7]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 1.0, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 03 · Not tasks, lifecycles: a loop of six gates, agents flowing round it, the sixth gate lit
    lifecycle(N, rnd, g) {
      const P = []; const ringN = Math.floor(N * 0.34), nodeN = Math.floor(N * 0.05);
      const tilt = 0.9;
      const on = (a, r, lift) => { const x = Math.cos(a) * r, z = Math.sin(a) * r; return [x, lift + z * Math.sin(tilt) * 0.5, z * Math.cos(tilt)]; };
      for (let i = 0; i < ringN; i++) { const p = on(rnd() * TAU, 0.95 + g() * 0.02, g() * 0.015); P.push([p[0], p[1], p[2], rnd() < 0.15 ? 2 : 0]); }
      for (let n = 0; n < 6; n++) { const p = on(n / 6 * TAU + 0.5, 0.95, 0); for (let i = 0; i < nodeN; i++) P.push([p[0] + g() * 0.045, p[1] + g() * 0.045, p[2] + g() * 0.045, n === 5 ? 2 : 0]); }
      for (let i = 0; i < N * 0.18; i++) { const p = on(rnd() * TAU, 0.2 + rnd() * 0.7, 0); P.push([p[0] + g() * 0.01, p[1] + g() * 0.01, p[2] + g() * 0.01, 7]); }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 04 · One large agent versus thousands of small ones
    swarm(N, rnd, g) {
      const P = []; const mono = Math.floor(N * 0.30);
      for (let i = 0; i < mono; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, r = 0.42 * Math.pow(rnd(), 0.4); P.push([-0.72 + r * Math.cos(la) * Math.sin(lo), r * Math.sin(la), r * Math.cos(la) * Math.cos(lo), 1]); }
      for (let i = 0; i < N * 0.56; i++) { const gx = Math.floor(rnd() * 7), gy = Math.floor(rnd() * 7), gz = Math.floor(rnd() * 3); P.push([0.28 + gx * 0.12 + g() * 0.014, -0.42 + gy * 0.14 + g() * 0.014, -0.16 + gz * 0.16 + g() * 0.014, rnd() < 0.55 ? 2 : 0]); }
      for (let i = 0; i < N * 0.06; i++) P.push([-0.2 + g() * 0.01, (rnd() * 2 - 1) * 0.7, (rnd() - 0.5) * 0.3, 7]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 05 · Eight layers, one boundary: agents decide above the bright plane, code executes below
    boundary(N, rnd, g) {
      const P = []; const per = Math.floor(N * 0.085);
      for (let l = 0; l < 8; l++) { const y = 0.7 - l * 0.2; for (let i = 0; i < per; i++) { const rim = rnd() < 0.3; let x = (rnd() * 2 - 1) * 0.8, z = (rnd() * 2 - 1) * 0.36; if (rim) { if (rnd() < 0.5) z = (rnd() < 0.5 ? -1 : 1) * 0.36; else x = (rnd() < 0.5 ? -1 : 1) * 0.8; } P.push([x + g() * 0.004, y + g() * 0.006, z + g() * 0.004, l === 2 ? (rnd() < 0.7 ? 2 : 0) : l < 4 ? 0 : 1]); } }
      for (let i = 0; i < N * 0.14; i++) P.push([(rnd() * 2 - 1) * 0.92, 0.0 + g() * 0.004, (rnd() * 2 - 1) * 0.46, 2]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 06 · The rulebook moves into the weights: a dense cube with a lit core, documents drifting in
    rulebook(N, rnd, g) {
      const P = []; const cube = Math.floor(N * 0.62);
      for (let i = 0; i < cube; i++) { const x = (rnd() * 2 - 1) * 0.5, y = (rnd() * 2 - 1) * 0.5, z = (rnd() * 2 - 1) * 0.5; const core = Math.hypot(x, y, z) < 0.22; P.push([x, y, z, core ? 2 : (rnd() < 0.5 ? 0 : 1)]); }
      for (let d = 0; d < 6; d++) { const a = d / 6 * TAU, cx = Math.cos(a) * 1.05, cz = Math.sin(a) * 1.05, cy = (d % 3 - 1) * 0.35; for (let i = 0; i < N * 0.03; i++) P.push([cx + (rnd() - 0.5) * 0.02, cy + (rnd() - 0.5) * 0.22, cz + (rnd() - 0.5) * 0.16, 0]); for (let i = 0; i < N * 0.015; i++) { const t = rnd(); P.push([cx * (1 - t) + g() * 0.01, cy * (1 - t) + g() * 0.01, cz * (1 - t) + g() * 0.01, 7]); } }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 07 · The council: proposals stream in from above, approved continue down, rejected leave to the side
    council(N, rnd, g) {
      const P = [];
      for (let i = 0; i < N * 0.18; i++) { const t = rnd(); const a = rnd() * TAU, r = 0.36 + 0.24 * Math.sqrt(rnd()); P.push([Math.cos(a) * r * 0.55 + g() * 0.004, 0.1 + 0.02 * Math.sin(a), Math.sin(a) * r * 0.55 + g() * 0.004, 0]); }
      for (let i = 0; i < N * 0.28; i++) { const t = rnd(); P.push([g() * 0.09 * (1 - t) + g() * 0.02, 1.05 - t * 0.9, g() * 0.09 * (1 - t), 1]); }
      for (let i = 0; i < N * 0.24; i++) { const t = rnd(); P.push([g() * 0.05, 0.05 - t * 1.05, g() * 0.05, 2]); }
      for (let i = 0; i < N * 0.09; i++) { const t = rnd(); P.push([0.05 + t * 1.1, 0.06 - t * 0.55, g() * 0.03, 3]); }
      for (let i = 0; i < N * 0.06; i++) P.push([(rnd() * 2 - 1) * 0.6, -1.02 + g() * 0.004, (rnd() * 2 - 1) * 0.3, 2]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 1.0, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 08 · A ledger nobody can edit: blocks linked in a chain, each pointing at the one before
    ledger(N, rnd, g) {
      const P = []; const blocks = 8;
      for (let b = 0; b < blocks; b++) {
        const t = b / (blocks - 1), cx = -1.0 + t * 2.0, cy = 0.55 - t * 1.1, cz = Math.sin(t * Math.PI) * 0.25;
        for (let i = 0; i < N * 0.075; i++) { const f = Math.floor(rnd() * 6); const u = rnd() * 2 - 1, v = rnd() * 2 - 1; const w = 0.11, h = 0.07, d = 0.07; const pt = f === 0 ? [u * w, v * h, d] : f === 1 ? [u * w, v * h, -d] : f === 2 ? [u * w, h, v * d] : f === 3 ? [u * w, -h, v * d] : f === 4 ? [w, u * h, v * d] : [-w, u * h, v * d]; P.push([cx + pt[0], cy + pt[1], cz + pt[2], b === blocks - 1 ? 2 : 0]); }
        if (b) { const px = -1.0 + (b - 1) / (blocks - 1) * 2.0, py = 0.55 - (b - 1) / (blocks - 1) * 1.1, pz = Math.sin((b - 1) / (blocks - 1) * Math.PI) * 0.25; for (let i = 0; i < N * 0.03; i++) { const s = rnd(); P.push([px + (cx - px) * s + g() * 0.004, py + (cy - py) * s + g() * 0.004, pz + (cz - pz) * s + g() * 0.004, 2]); } }
      }
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 09 · Ten sessions above the floor
    sessions(N, rnd, g) {
      const P = []; const regime = 'ddppppdpdd'; const per = Math.floor(N * 0.082);
      for (let c = 0; c < 10; c++) { const x = -1.08 + c * 0.24; for (let i = 0; i < per; i++) { const u = rnd(); const y = u < 0.78 ? -0.7 + rnd() * 1.1 : -0.7 + 1.1 + Math.min(-Math.log(1 - rnd()) * 0.16, 0.5); P.push([x + (rnd() - 0.5) * 0.14, y, (rnd() - 0.5) * 0.1, regime[c] === 'p' ? 2 : 0]); } }
      for (let i = 0; i < N * 0.08; i++) P.push([(rnd() * 2 - 1) * 1.25, 0.4 + g() * 0.005, 0.07, 1]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // 10 · Master and copy: one proven agent, replicated onto new assets under one control plane
    mastercopy(N, rnd, g) {
      const P = [];
      const sphere = (cx, cy, cz, r, n, k) => { for (let i = 0; i < n; i++) { const la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = r * Math.pow(rnd(), 0.3); P.push([cx + rr * Math.cos(la) * Math.sin(lo), cy + rr * Math.sin(la), cz + rr * Math.cos(la) * Math.cos(lo), k]); } };
      sphere(0, 0.6, 0, 0.3, Math.floor(N * 0.28), 2);
      for (let c = 0; c < 5; c++) { const a = (c / 4 - 0.5) * 2.4; const cx = Math.sin(a) * 1.0, cy = -0.35, cz = Math.cos(a) * 0.35 - 0.2; sphere(cx, cy, cz, 0.17, Math.floor(N * 0.07), c === 0 ? 0 : 1); for (let i = 0; i < N * 0.035; i++) { const s = rnd(); P.push([cx * s + g() * 0.006, 0.6 + (cy - 0.6) * s + g() * 0.006, cz * s + g() * 0.006, 7]); } }
      for (let i = 0; i < N * 0.1; i++) P.push([(rnd() * 2 - 1) * 1.3, -0.75 + g() * 0.004, (rnd() * 2 - 1) * 0.5, 1]);
      while (P.length < N) P.push([(rnd() * 2 - 1) * 1.4, (rnd() * 2 - 1) * 0.9, -0.9 - rnd() * 0.6, 7]);
      return P;
    },
    // Index · the library: ten leaves fanned in space, the two research notes lit
    library(N, rnd, g) {
      const P = []; const per = Math.floor(N * 0.088);
      for (let l = 0; l < 10; l++) { const a = (l / 9 - 0.5) * 1.5; const cx = Math.sin(a) * 0.9, cz = Math.cos(a) * 0.9 - 0.6; const ux = Math.cos(a), uz = -Math.sin(a); for (let i = 0; i < per; i++) { const u = rnd() * 2 - 1, v = rnd() * 2 - 1; const rim = rnd() < 0.28; const uu = rim && rnd() < 0.5 ? (rnd() < 0.5 ? -1 : 1) : u, vv = rim && !(rnd() < 0.5) ? (rnd() < 0.5 ? -1 : 1) : v; P.push([cx + ux * uu * 0.28 + g() * 0.003, vv * 0.42 + g() * 0.003, cz + uz * uu * 0.28 + g() * 0.003, l < 2 ? 2 : (rim ? 0 : 1)]); } }
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
  uniform mat4 u_proj, u_view; uniform float u_time, u_mix, u_pr, u_spin, u_scale, u_halo, u_maxpt;
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
    float t = clamp((u_mix - a_rand.y * 0.3) / 0.7, 0.0, 1.0); t = t * t * (3.0 - 2.0 * t);
    vec3 P = mix(a_a.xyz, a_b.xyz, t);
    vec3 dir = a_b.xyz - a_a.xyz; float L = length(dir);
    P += (L > 0.001 ? cross(normalize(dir), vec3(0.0, 0.0, 1.0)) : vec3(0.0)) * sin(t * 3.14159) * (0.1 + 0.2 * a_rand.z) * min(L, 1.0);
    P += 0.008 * vec3(sin(u_time * 0.9 + a_rand.x * 6.283), cos(u_time * 0.7 + a_rand.y * 6.283), sin(u_time * 1.1 + a_rand.z * 6.283));
    P = rotY(u_spin) * P * u_scale;
    vec4 mv = u_view * vec4(P, 1.0); gl_Position = u_proj * mv;
    float depth = clamp((mv.z + 5.6) / 2.6, 0.0, 1.0);
    float k = mix(a_a.w, a_b.w, step(0.5, t));
    float dust = (k > 6.5) ? 0.16 : 1.0;
    float accent = (k > 1.5 && k < 2.5) ? 1.3 : 1.0;
    float pulse = accent > 1.0 ? (0.86 + 0.14 * sin(u_time * 2.2 + a_rand.w * 6.283)) : 1.0;
    float sz = (1.65 + a_rand.x * 2.0) * (0.6 + depth * 0.8) * accent * (dust < 0.5 ? 0.7 : 1.0) * pulse;
    float al = (0.26 + 0.6 * depth) * dust * (accent > 1.0 ? 1.15 : 1.0);
    float px = min(sz * u_pr * (u_halo > 0.5 ? 3.6 : 1.0), u_maxpt);
    gl_PointSize = px; v_size = px;
    v_alpha = u_halo > 0.5 ? al * (accent > 1.0 ? 0.17 : 0.038) : al;
    v_col = mix(kcol(a_a.w), kcol(a_b.w), t);
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

  function init(stage) {
    const cv = stage.querySelector('canvas');
    const initial = stage.dataset.figure;
    if (!cv || !FORMS[initial]) { stage.classList.add('no-figure'); return; }
    const gl = cv.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: true, powerPreference: 'low-power' });
    if (!gl) { stage.classList.add('no-figure'); return; }
    const compile = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { console.warn('figure shader:', gl.getShaderInfoLog(s)); return null; } return s; };
    const vs = compile(gl.VERTEX_SHADER, VS), fs = compile(gl.FRAGMENT_SHADER, FS);
    if (!vs || !fs) { stage.classList.add('no-figure'); return; }
    const prog = gl.createProgram(); gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { console.warn('figure program:', gl.getProgramInfoLog(prog)); stage.classList.add('no-figure'); return; }
    gl.useProgram(prog);
    const N = narrow() ? 7000 : 15000;
    const rnd = makeRng(41), g = () => (rnd() + rnd() + rnd() - 1.5) * 0.82;
    const RAND = new Float32Array(N * 4); for (let i = 0; i < N * 4; i++) RAND[i] = rnd();
    const built = {};
    const build = (name) => { if (!built[name]) { const r = makeRng(name.length * 977 + 13), gg = () => (r() + r() + r() - 1.5) * 0.82; const pts = FORMS[name](N, r, gg); const f = new Float32Array(N * 4); for (let i = 0; i < N; i++) { const p = pts[i] || [0, 0, -2, 7]; f[i * 4] = p[0]; f[i * 4 + 1] = p[1]; f[i * 4 + 2] = p[2]; f[i * 4 + 3] = p[3]; } built[name] = f; } return built[name]; };
    const buf = (name, data) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW); const loc = gl.getAttribLocation(prog, name); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 0, 0); return b; };
    const first = build(initial);
    const bufA = buf('a_a', first), bufB = buf('a_b', first); buf('a_rand', RAND);
    const U = {}; ['u_proj', 'u_view', 'u_time', 'u_mix', 'u_pr', 'u_spin', 'u_scale', 'u_halo', 'u_maxpt'].forEach(n => U[n] = gl.getUniformLocation(prog, n));
    gl.uniform1f(U.u_maxpt, (gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE) || [1, 64])[1]);
    gl.enable(gl.BLEND); gl.disable(gl.DEPTH_TEST);
    const proj = new Float32Array(16), view = new Float32Array(16);
    let W = 1, H = 1, dpr = 1, time = 0, mix = 1, current = initial, spinBase = parseFloat(stage.dataset.spin || '0.12');
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    let frameId = 0, visible = true, lost = false, last = performance.now();
    const scale = parseFloat(stage.dataset.scale || '1');
    // render at the device's full resolution (up to 3x), within a UHD pixel budget so a large stage on a 3x display stays fluid
    const PIXEL_BUDGET = 3840 * 2160;
    function resize() { const r = cv.getBoundingClientRect(); W = Math.max(1, r.width); H = Math.max(1, r.height); dpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(PIXEL_BUDGET / (W * H))); cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); gl.viewport(0, 0, cv.width, cv.height); perspective(proj, 0.62, W / H, 0.1, 30); gl.uniform1f(U.u_pr, dpr); draw(true); }
    function draw(force) {
      const now = performance.now(); const dt = Math.min(0.05, (now - last) / 1000); last = now;
      const moving = !reduced.matches;
      if (moving) { time += dt; mouse.x += (mouse.tx - mouse.x) * 0.05; mouse.y += (mouse.ty - mouse.y) * 0.05; }
      if (mix < 1) mix = Math.min(1, mix + dt * 0.9);
      const ang = mouse.x * 0.35, elev = 0.35 + mouse.y * 0.25;
      lookAt(view, [Math.sin(ang) * 4.4, elev, Math.cos(ang) * 4.4]);
      gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniformMatrix4fv(U.u_proj, false, proj); gl.uniformMatrix4fv(U.u_view, false, view);
      gl.uniform1f(U.u_time, time); gl.uniform1f(U.u_mix, mix); gl.uniform1f(U.u_spin, time * spinBase); gl.uniform1f(U.u_scale, scale * (narrow() ? 0.86 : 1));
      gl.blendFunc(gl.ONE, gl.ONE); gl.uniform1f(U.u_halo, 1); gl.drawArrays(gl.POINTS, 0, N);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.uniform1f(U.u_halo, 0); gl.drawArrays(gl.POINTS, 0, N);
      stage.classList.add('figure-ready');
      if (!force && (moving || mix < 1)) request();
    }
    function frame() { frameId = 0; if (!visible || document.hidden || lost) return; draw(false); }
    function request() { if (!frameId && visible && !document.hidden && !lost) frameId = requestAnimationFrame(frame); }
    function stop() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
    stage.__figure = {
      show(name) {
        if (!FORMS[name] || name === current || lost) return;
        // the current target becomes the origin; snapping mid-morph is invisible at these speeds
        gl.bindBuffer(gl.ARRAY_BUFFER, bufA); gl.bufferData(gl.ARRAY_BUFFER, build(current), gl.DYNAMIC_DRAW);
        gl.bindBuffer(gl.ARRAY_BUFFER, bufB); gl.bufferData(gl.ARRAY_BUFFER, build(name), gl.DYNAMIC_DRAW);
        current = name; mix = 0; stage.dataset.figureCurrent = name; request();
      },
    };
    stage.dataset.figureCurrent = initial;
    cv.addEventListener('webglcontextlost', e => { e.preventDefault(); lost = true; stop(); stage.classList.add('no-figure'); });
    cv.addEventListener('webglcontextrestored', () => { location.reload(); });
    if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) request(); else stop(); }, { threshold: 0 }).observe(stage);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else request(); });
    reduced.addEventListener('change', () => { mouse.tx = mouse.ty = 0; request(); });
    if ('ResizeObserver' in window) new ResizeObserver(() => resize()).observe(stage); else window.addEventListener('resize', resize);
    stage.addEventListener('pointermove', e => { if (reduced.matches || e.pointerType === 'touch') return; const r = stage.getBoundingClientRect(); mouse.tx = (e.clientX - r.left) / r.width - 0.5; mouse.ty = (e.clientY - r.top) / r.height - 0.5; }, { passive: true });
    stage.addEventListener('pointerleave', () => { mouse.tx = mouse.ty = 0; });
    resize(); request();
  }
  stages.forEach(init);

  // the research index: point at a post, the sculpture becomes that post's figure
  document.querySelectorAll('[data-figure-target]').forEach(el => {
    const stage = document.querySelector(el.dataset.figureStage ? `#${el.dataset.figureStage}` : '[data-figure]');
    const go = () => stage && stage.__figure && stage.__figure.show(el.dataset.figureTarget);
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
