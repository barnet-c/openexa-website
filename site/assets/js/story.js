/* OpenEXA — the overture (homepage): one instrument, five scenes, signal → record.
   S0 a globe of agents with six faint orbits; signals drift in and are absorbed · S1 the globe unwraps band by band into six
   lifecycle rings · S2 the rings flatten and stack into eight layers around one glowing boundary (jitter above, grid below)
   · S3 seen from the side, the layers become six gates: proposals pass them, the council aperture decides, rejections fall
   away, settled actions become hash-linked records · S4 the ledger's records regroup into ten session columns above the
   10 bps floor; on the way out the ledger line becomes the rule the paper chapters continue.
   - every particle keeps its identity: morphs are staggered by structure (band, ring, layer, column), travel on curved paths
     and settle with a light spring, so the instrument never dissolves into noise;
   - one vocabulary of role-coded sprites: signal mote, agent bead, proposal ring, council aperture, settled square,
     rejected red (falls with gravity), record block, hash link;
   - callouts are DOM (crisp, selectable), projected from 3D anchors with leader lines, kept clear of the beat text;
   - contracts other code and the checks rely on: html.story-ready / .no-webgl / .gl-ready, story:no-webgl / story:gl-ready,
     [data-story-motion], .story-idx buttons (aria-current="step"), .beat-N, .story-2d (site.js draws the 2D fallback).
   Reduced motion: no autonomous motion and the scenes snap. No WebGL: the static beats. The context, shaders and buffers
   are built under the loader and rebuilt in place if the GPU drops the context. */
(function () {
  'use strict';
  const story = document.querySelector('.story');
  if (!story) return;
  const root = document.documentElement;

  /* ================= data: the sessions record (the proof chart reads the same block) ================= */
  const pad2 = (n) => String(n).padStart(2, '0');
  const NUMW = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(' ');
  const words = (n) => NUMW[n] || String(n), capw = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  // without the page's <script type="application/json" id="oxa-sessions">: the per-session table as published, the same record
  const TABLE = { lifecycle: 'Lifecycle 01', unit: 'bps', floor: 10, sessions: 'DDPPPPDPDD'.split('').map((c, i) => ({ day: 'Day ' + pad2(i + 1), regime: c === 'P' ? 'Premium' : 'Discount', value: '>10', confirmation: 'Broker confirmation', status: 'Settled' })) };
  const REC = (() => {
    const str = (v) => (v == null ? '' : String(v)).trim();
    const read = (j) => {
      const list = j && Array.isArray(j.sessions) ? j.sessions : null, floor = Number(j && j.floor);
      if (!list || !list.length || list.length > 24 || !(floor > 0)) return null;
      const sessions = list.map((s, i) => {
        const r = str(s && s.regime).toLowerCase(), value = str(s && s.value).replace(/\s+/g, '');
        const m = /^(>=|≥|>)?(\d+(?:\.\d+)?)$/.exec(value), amount = m ? Number(m[2]) : NaN, conf = str(s && s.confirmation);
        return {
          day: pad2(parseInt((str(s && s.day).match(/\d+/) || [String(i + 1)])[0], 10)),
          regime: r.startsWith('prem') ? 'premium' : r.startsWith('disc') ? 'discount' : '',
          value, above: !!m && (m[1] === '>' ? amount >= floor : amount > floor), // ">10" on a 10 floor: above it, by how much is not published
          confirmed: /confirm/i.test(conf) && !/pending|awaiting|unconfirm|^not\b/i.test(conf),
        };
      });
      if (!sessions.every(s => s.regime)) return null;
      return { lifecycle: str(j.lifecycle) || TABLE.lifecycle, unit: str(j.unit) || 'bps', floor, sessions };
    };
    try { const el = document.getElementById('oxa-sessions'); const r = el && read(JSON.parse(el.textContent)); if (r) return r; } catch (e) { /* unreadable: the table */ }
    return read(TABLE);
  })();
  const SESSIONS = REC.sessions, NCOL = SESSIONS.length, FLOOR = REC.floor, UNIT = REC.unit, FLOOR_T = `${FLOOR} ${UNIT}`;
  const count = (f) => SESSIONS.filter(f).length;
  const N_PREM = count(s => s.regime === 'premium'), N_DISC = NCOL - N_PREM, N_ABOVE = count(s => s.above), N_CONF = count(s => s.confirmed);
  const valueT = (s) => s.value ? `${s.value} ${UNIT}` : 'value not stated'; // only what the record states: ">10 bps"
  // every count in the overture's copy is derived from the record: [data-story-n="total|above|premium|discount|floor|confirmed|every|tally|lifecycle"]
  const derive = (k, as) => {
    if (k === 'every') return N_ABOVE === NCOL ? 'every one of ' + words(NCOL) : words(N_ABOVE) + ' of ' + words(NCOL);
    if (k === 'lifecycle') return REC.lifecycle;
    if (k === 'tally') return `${capw(words(N_ABOVE))} for ${words(NCOL)}.`; // 'Ten for ten.'
    const n = { total: NCOL, above: N_ABOVE, premium: N_PREM, discount: N_DISC, floor: FLOOR, confirmed: N_CONF }[k];
    return n == null ? null : as === 'words' ? words(n) : as === 'Words' ? capw(words(n)) : String(n);
  };
  story.querySelectorAll('[data-story-n]').forEach(el => { const t = derive(el.dataset.storyN, el.dataset.storyAs); if (t != null && el.textContent !== t) el.textContent = t; });

  const stage = story.querySelector('.story-stage');
  const cv = story.querySelector('canvas.story-gl');
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  // static beats; site.js runs the 2D swarm behind them (it listens for this event when WebGL fails after it has run)
  const fallback = () => { root.classList.remove('story-ready', 'gl-ready'); root.classList.add('no-webgl'); document.dispatchEvent(new Event('story:no-webgl')); };
  if (!cv || !stage || !window.WebGLRenderingContext) { fallback(); return; }
  root.classList.add('story-ready');
  // portrait and small screens stack the visual above the copy (the same query lives in the stylesheet)
  const stackedMQ = window.matchMedia('(max-width: 639.98px), (max-aspect-ratio: 23/20)');
  const LITE = stackedMQ.matches || Math.min(window.innerWidth, window.innerHeight) < 640;

  const SCENES = ['Infrastructure', 'The work', 'The stack', 'The swarm', 'The proof'];
  const LC = [ // code, short name (callout), status, full name and job (inspector)
    ['LC-01', 'Financial markets', 'Live', 'Financial markets & insurance', 'ETF creation and redemption, in production on live capital'],
    ['LC-02', 'Trade finance', 'Next', 'International trade · letters of credit', 'Issuance, document checks, discrepancies and payment'],
    ['LC-03', 'Securitization', 'Next', 'Asset securitization · MBS / ABS', 'Pool assembly, tranche compliance, investor distributions'],
    ['LC-04', 'Energy settlement', 'Roadmap', 'Wholesale energy settlement', 'Metering, scheduling, imbalance, multi-party settlement'],
    ['LC-05', 'Semiconductors', 'Roadmap', 'Semiconductor manufacturing', 'Order to wafer across foundries, packaging and logistics'],
    ['LC-06', 'Pharma & aerospace', 'Roadmap', 'Pharmaceutical & aerospace', 'Qualification, batch release, full traceability'],
  ];
  const LAYERS = [
    ['Signal intelligence', 'Perceive', 'Risk, price and regime models'], ['Model layer', 'Reason', 'A post-trained LLM on the domain'],
    ['Domain-specific agents', 'Act', 'One narrow job each'], ['Execution council', 'Govern', 'Approve or reject, by policy'],
    ['Routing layer', 'Optimize', 'The cheapest, fastest, safest path'], ['Execution layer', 'Orchestrate', 'Deterministic order state'],
    ['MCP server', 'Connect', 'Authenticated tools and adapters'], ['Authentication layer', 'Permit', 'Scoped, revocable permissions'],
  ];
  const GATES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];

  /* ================= geometry (local units; each scene is fitted into its frame at run time) ================= */
  const TAU = Math.PI * 2, PI = Math.PI;
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const lerp = (a, b, t) => a + (b - a) * t;
  const sstep = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  // the morph's easing, mirrored in the vertex shader: smooth in, a light spring over the target, settled at 1
  const C1 = 0.8, C3 = C1 + 1;
  const ease = (t) => { const s = t * t * (3 - 2 * t), u = s - 1; return 1 + C3 * u * u * u + C1 * u * u; };
  const stag = (m, key) => { const sp = SPREADS[seg] || 0.42; return clamp((m - key * sp) / (1 - sp), 0, 1); };
  // how far apart the structure's parts set off: the globe unwraps band by band (wide), the columns fill one by one
  const HOLD = 0.1, SPREADS = [0.6, 0.46, 0.42, 0.5], EXIT_U = 0.6, TOTAL_U = 4 + EXIT_U;

  // orbits (S0) and lifecycle rings (S1) share their tilt azimuths so each orbit opens into its ring
  const ORBITS = [[1.24, 0.40, 0.35, 0.15], [1.31, -0.30, 1.40, -0.11], [1.38, 0.60, 2.20, 0.09], [1.46, -0.52, 3.05, -0.13], [1.54, 0.24, 4.10, 0.08], [1.62, -0.70, 5.20, -0.07]];
  const RINGS = [[0.52, 0.03, 0.35, 0.30], [0.735, -0.025, 1.40, 0.22], [0.95, 0.03, 2.20, 0.18], [1.165, -0.02, 3.05, 0.15], [1.38, 0.025, 4.10, 0.12], [1.595, -0.03, 5.20, 0.10]];
  function basis(tilt, az) {
    const sa = Math.sin(tilt), ca = Math.cos(tilt), sb = Math.sin(az), cb = Math.cos(az);
    return { U: [cb, 0, sb], V: [ca * sb, sa, -ca * cb], N: [-sb * sa, ca, cb * sa] };
  }
  const OB = ORBITS.map(o => basis(o[1], o[2])), RB = RINGS.map(o => basis(o[1], o[2]));
  const onLoop = (b, r, th, lift) => [(b.U[0] * Math.cos(th) + b.V[0] * Math.sin(th)) * r + b.N[0] * lift, (b.U[1] * Math.cos(th) + b.V[1] * Math.sin(th)) * r + b.N[1] * lift, (b.U[2] * Math.cos(th) + b.V[2] * Math.sin(th)) * r + b.N[2] * lift];
  // the globe band that opens into each ring: equatorial bands carry the most agents and go to the live ring
  const RING_OF_BAND = [4, 2, 0, 1, 3, 5];
  // S2: eight plates, the boundary between 04 and 05 at y = 0
  const PL_Y = (p) => 0.84 - 0.24 * p, PL_HX = 0.86, PL_HZ = 0.54, PL_RC = 0.07;
  function rrHit(phi, hx, hz, rc) { // where the ray from the centre at angle phi leaves a rounded rectangle (x, z)
    const dx = Math.cos(phi), dz = Math.sin(phi);
    let t = Math.min(hx / Math.max(1e-6, Math.abs(dx)), hz / Math.max(1e-6, Math.abs(dz)));
    const x = dx * t, z = dz * t;
    if (Math.abs(x) > hx - rc && Math.abs(z) > hz - rc) {
      const cx = Math.sign(dx) * (hx - rc), cz = Math.sign(dz) * (hz - rc), dc = dx * cx + dz * cz;
      t = dc + Math.sqrt(Math.max(0, dc * dc - (cx * cx + cz * cz) + rc * rc));
    }
    return [dx * t, dz * t];
  }
  // S3: the lane (side view of the same layers), six gates, the council at gate 04, the ledger along the bottom
  const LX = -0.62, Y_TOP = 1.14, Y_BOT = -0.9, GATE_Y = [0.86, 0.56, 0.26, -0.04, -0.34, -0.64], COUNCIL = 3, Y_LEDGER = -1.0;
  const GATE_HX = 0.5, GATE_HZ = 0.27, AP_R = 0.3, LEDGER_X0 = LX + 0.36, LEDGER_DX = 0.17, LEDGER_N = 10;
  const GATE_OF_PLATE = [0, 1, 2, 3, 4, 4, 5, 5];
  // S4: the floor line (10 bps) and one column per session; heights carry no magnitude (">10 bps" only)
  const Y_FLOOR = -0.5, H_COL = 1.0, COL_SPAN = Math.min(2.9, 0.29 * NCOL);
  const COL_X = (c) => -COL_SPAN / 2 + COL_SPAN * (c + 0.5) / NCOL;

  /* ================= particles: identity, five scene targets, stagger keys ================= */
  const N_SURF = LITE ? 5400 : 10800, N_ORB = LITE ? 760 : 1500, N_SIG = LITE ? 520 : 960, N_DUST = LITE ? 520 : 1000;
  const N = N_SURF + N_ORB + N_SIG + N_DUST;
  const I_ORB = N_SURF, I_SIG = I_ORB + N_ORB, I_DUST = I_SIG + N_SIG;
  // per-scene attribute: xyz + code (mode * 1000 + kind * 100 + group); modes and kinds are decoded in the vertex shader
  const M = { STATIC: 0, GLOBE: 1, ORBIT: 2, RING: 3, JITTER: 4, SIGIN: 5, FLOW: 6, FLOWREJ: 7, FALL: 8, DRIFT: 9, COLUMN: 10 };
  const K = { IVORY: 0, KHAKI: 1, GREEN: 2, RED: 3, DUST: 4, MOTE: 5, DIM: 6, GDIM: 7, BRIGHT: 8 };
  const code = (mode, kind, grp) => mode * 1000 + kind * 100 + (grp || 0);
  const F = Array.from({ length: 5 }, () => new Float32Array(N * 4));
  const RAND = new Float32Array(N * 4), KEY = new Float32Array(N * 4);
  let seed = 11;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const gauss = () => (rnd() + rnd() + rnd() - 1.5) * 0.82;
  for (let i = 0; i < N * 4; i++) RAND[i] = rnd();
  const set = (s, i, x, y, z, c) => { const o = i * 4; F[s][o] = x; F[s][o + 1] = y; F[s][o + 2] = z; F[s][o + 3] = c; };
  const R = (i, k) => RAND[i * 4 + k];

  (function build() {
    /* ---- S0: the globe (the brand mark's latitude rows), six orbits, signals, dust ---- */
    const rows = LITE ? 44 : 64, lat = [], cnt = [];
    let cs = 0;
    for (let r = 0; r < rows; r++) { const la = (78 - 156 * r / (rows - 1)) * PI / 180; lat.push(la); cs += Math.cos(la); }
    let tot = 0;
    for (let r = 0; r < rows; r++) { cnt.push(Math.max(8, Math.round(N_SURF * Math.cos(lat[r]) / cs))); tot += cnt[r]; }
    for (let r = Math.floor(rows / 2); tot !== N_SURF; r = (r + 1) % rows) { const d = tot < N_SURF ? 1 : -1; cnt[r] += d; tot += d; }
    const band = new Uint8Array(N_SURF), lam = new Float32Array(N_SURF);
    let i = 0;
    for (let r = 0; r < rows; r++) {
      const b = Math.min(5, Math.floor(r * 6 / rows));
      for (let j = 0; j < cnt[r]; j++, i++) {
        const l = (j + (r % 2) * 0.5) / cnt[r] * TAU, c = Math.cos(lat[r]);
        band[i] = b; lam[i] = l;
        set(0, i, c * Math.cos(l), Math.sin(lat[r]), c * Math.sin(l), code(M.GLOBE, R(i, 0) < 0.022 ? K.GREEN : K.IVORY, 0));
        KEY[i * 4] = (b + 0.45 * (j / cnt[r])) / 6.45; // band by band, each band peeling round from one meridian
      }
    }
    for (let q = 0; q < N_ORB; q++) {
      const ii = I_ORB + q, k = q % 6;
      set(0, ii, R(ii, 0) * TAU, ORBITS[k][0] + gauss() * 0.01, gauss() * 0.006, code(M.ORBIT, K.DIM, k));
      KEY[ii * 4] = 0.12 + 0.5 * k / 6;
    }
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU;
      set(0, ii, Math.cos(la) * Math.cos(lo), Math.sin(la), Math.cos(la) * Math.sin(lo), code(M.SIGIN, K.MOTE, 0));
      KEY[ii * 4] = rnd();
    }
    for (let q = 0; q < N_DUST; q++) { // a sparse field all round the instrument: the same in every scene (depth and parallax)
      const ii = I_DUST + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = 2.6 + rnd() * 3.2;
      const x = Math.cos(la) * Math.cos(lo) * rr * 1.5, y = Math.sin(la) * rr * 0.8, z = Math.cos(la) * Math.sin(lo) * rr - 1.0;
      for (let s = 0; s < 5; s++) set(s, ii, x, y, z, code(M.DRIFT, K.DUST, 0));
    }

    /* ---- S1: six lifecycle rings (LC-01 green, solid; next: dashed ivory; roadmap: sparse khaki) ---- */
    const ringAng = new Float32Array(N_SURF), ringOf = new Uint8Array(N_SURF);
    const dash = (k, th) => { // snap an angle into the ring's dash pattern, keeping the order of the agents
      if (k === 0) return th;
      const n = k < 3 ? 72 : 44, duty = k < 3 ? 0.66 : 0.3, per = TAU / n, x = ((th % TAU) + TAU) % TAU;
      const di = Math.floor(x / per); return di * per + (x - di * per) * duty;
    };
    for (let q = 0; q < N_SURF; q++) {
      const k = RING_OF_BAND[band[q]], [rr, , az] = RINGS[k];
      const th = dash(k, az - lam[q]); // the ring point that sits at the agent's longitude
      ringAng[q] = th; ringOf[q] = k;
      const kind = k === 0 ? (R(q, 1) < 0.72 ? K.GREEN : K.BRIGHT) : k < 3 ? K.IVORY : K.KHAKI;
      set(1, q, th, rr + gauss() * (k === 0 ? 0.022 : 0.014), gauss() * 0.006, code(M.RING, kind, k));
    }
    for (let q = 0; q < N_ORB; q++) {
      const ii = I_ORB + q, k = q % 6;
      set(1, ii, dash(k, F[0][ii * 4]), RINGS[k][0] + gauss() * 0.006, gauss() * 0.004, code(M.RING, k === 0 ? K.GREEN : K.DIM, k));
    }
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = 0.03 + rnd() * 0.07;
      set(1, ii, Math.cos(la) * Math.cos(lo) * rr, Math.sin(la) * rr, Math.cos(la) * Math.sin(lo) * rr, code(M.SIGIN, K.MOTE, 1));
      KEY[ii * 4 + 1] = rnd();
    }
    // world angle of every agent in S1 (what the layers' fills preserve)
    const phi1 = new Float32Array(N_SURF);
    for (let q = 0; q < N_SURF; q++) { const p = onLoop(RB[ringOf[q]], RINGS[ringOf[q]][0], ringAng[q], 0); phi1[q] = Math.atan2(p[2], p[0]); }

    /* ---- S2: eight layers; agents jitter above the boundary, sit on an exact grid below it ---- */
    const order = Array.from({ length: N_SURF }, (_, q) => q).sort((a, b) => (ringOf[a] - ringOf[b]) || (R(a, 2) - R(b, 2)));
    const per = Math.floor(N_SURF / 8), plateOf = new Uint8Array(N_SURF), rankIn = new Float32Array(N_SURF);
    for (let p = 0; p < 8; p++) {
      const chunk = order.slice(p * per, p === 7 ? N_SURF : (p + 1) * per), y = PL_Y(p);
      chunk.forEach((q, j) => { plateOf[q] = p; rankIn[q] = j / chunk.length; });
      if (p < 4) {
        chunk.forEach(q => {
          const [ex, ez] = rrHit(phi1[q], PL_HX, PL_HZ, PL_RC), u = Math.sqrt(0.04 + 0.96 * R(q, 3));
          const kind = p === 2 ? (R(q, 1) < 0.45 ? K.GREEN : K.IVORY) : K.IVORY;
          set(2, q, ex * u, y, ez * u, code(M.JITTER, kind, p));
        });
      } else { // the deterministic side: an exact lattice, matched to the agents by angle so they slide straight in
        const gx = Math.max(4, Math.round(Math.sqrt(chunk.length * PL_HX / PL_HZ))), gz = Math.ceil(chunk.length / gx);
        const pts = [];
        for (let a = 0; a < gx; a++) for (let b = 0; b < gz; b++) { const x = (-1 + 2 * (a + 0.5) / gx) * (PL_HX - 0.05), z = (-1 + 2 * (b + 0.5) / gz) * (PL_HZ - 0.05); pts.push([x, z, Math.atan2(z, x)]); }
        pts.sort((a, b) => a[2] - b[2]);
        const byAng = chunk.slice().sort((a, b) => phi1[a] - phi1[b]);
        byAng.forEach((q, j) => { const g = pts[Math.floor(j * pts.length / byAng.length)]; set(2, q, g[0], y, g[1], code(M.STATIC, K.IVORY, p)); });
      }
      chunk.forEach(q => { KEY[q * 4 + 1] = (p + 0.35 * R(q, 0)) / 8.35; });
    }
    // orbit riders: the layers' rims (crisp edges) and, the ninth share, the boundary's green rim
    const orbOrder = Array.from({ length: N_ORB }, (_, q) => I_ORB + q).sort((a, b) => ((a - I_ORB) % 6 - (b - I_ORB) % 6) || (R(a, 2) - R(b, 2)));
    const operN = Math.floor(N_ORB / 9), orbPlate = new Uint8Array(N + 1);
    orbOrder.forEach((ii, j) => {
      const p = Math.min(8, Math.floor(j / operN)), k = (ii - I_ORB) % 6;
      const pw = onLoop(RB[k], RINGS[k][0], F[1][ii * 4], 0), ph = Math.atan2(pw[2], pw[0]);
      orbPlate[ii] = p;
      if (p < 8) { const [x, z] = rrHit(ph, PL_HX, PL_HZ, PL_RC); set(2, ii, x, PL_Y(p), z, code(M.STATIC, K.DIM, p)); }
      else { const [x, z] = rrHit(ph, PL_HX * 1.1, PL_HZ * 1.12, PL_RC * 1.6); set(2, ii, x, 0, z, code(M.STATIC, K.GDIM, 9)); }
      KEY[ii * 4 + 1] = (Math.min(p, 7.5) + 0.3 * R(ii, 0)) / 8.3;
    });
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q, [ex, ez] = rrHit(R(ii, 3) * TAU, PL_HX, PL_HZ, PL_RC), u = Math.sqrt(R(ii, 2));
      if (q % 2) set(2, ii, (rnd() - 0.5) * 3.2, (rnd() - 0.5) * 2.4, -0.8 - rnd() * 1.2, code(M.DRIFT, K.DUST, 0));
      else set(2, ii, ex * u * 0.92, PL_Y(0), ez * u * 0.92, code(M.FALL, K.MOTE, 0));
      KEY[ii * 4 + 2] = rnd();
    }

    /* ---- S3: the side view — layers become gates, agents become the stream, the boundary becomes the council aperture ---- */
    const gateLists = [[], [], [], [], [], []];
    const stream = [];
    for (let q = 0; q < N_SURF; q++) {
      const p = plateOf[q];
      if (rankIn[q] < 0.4) gateLists[GATE_OF_PLATE[p]].push(q); else stream.push(q);
      KEY[q * 4 + 2] = (p + 0.4 * R(q, 1)) / 8.4;
    }
    gateLists.forEach((list, g) => { // a fine lattice on each gate plate
      const gx = Math.max(3, Math.round(Math.sqrt(list.length * GATE_HX / GATE_HZ))), gz = Math.ceil(list.length / gx), y = GATE_Y[g];
      list.forEach((q, j) => {
        const a = j % gx, b = Math.floor(j / gx);
        set(3, q, LX + (-1 + 2 * (a + 0.5) / gx) * GATE_HX, y + gauss() * 0.002, (-1 + 2 * (b + 0.5) / gz) * GATE_HZ, code(M.STATIC, K.DIM, g));
      });
    });
    stream.forEach((q, j) => {
      const p = plateOf[q], ph = (p + rankIn[q]) / 8 + j * 0.61803 % 1 * 0.02;
      const rej = R(q, 3) < 0.07;
      set(3, q, gauss() * 1.05, ph % 1, gauss() * 1.0, code(rej ? M.FLOWREJ : M.FLOW, R(q, 1) < 0.08 ? K.GREEN : K.DIM, 0));
    });
    orbOrder.forEach((ii) => {
      const p = orbPlate[ii];
      if (p < 8) { // gate rims
        const g = GATE_OF_PLATE[p], [x, z] = rrHit(R(ii, 2) * TAU, GATE_HX, GATE_HZ, 0.04);
        set(3, ii, LX + x, GATE_Y[g], z, code(M.STATIC, K.DIM, g));
      } else { // the council aperture: the boundary, seen from the side, is the gate every proposal passes
        const a = R(ii, 2) * TAU;
        set(3, ii, LX + Math.cos(a) * AP_R, GATE_Y[COUNCIL], Math.sin(a) * AP_R, code(M.STATIC, K.GDIM, 9));
      }
      KEY[ii * 4 + 2] = (Math.min(p, 7.5) + 0.3 * R(ii, 1)) / 8.3;
    });
    for (let q = 0; q < N_SIG; q++) { // signals funnel into the top of the lane (every other one stays as faint dust)
      const ii = I_SIG + q;
      if (q % 2) set(3, ii, (rnd() - 0.5) * 3.2, (rnd() - 0.5) * 2.4, -0.6 - rnd() * 1.2, code(M.DRIFT, K.DUST, 0));
      else set(3, ii, LX + gauss() * 0.03, Y_TOP + 0.02, gauss() * 0.03, code(M.SIGIN, K.MOTE, 2));
      KEY[ii * 4 + 3] = rnd();
    }

    /* ---- S4: ten columns of agents standing on the floor; the orbit riders become the floor line ---- */
    const s3y = (q) => { const c = F[3][q * 4 + 3], mode = Math.floor(c / 1000); return mode === M.FLOW || mode === M.FLOWREJ ? Y_TOP - F[3][q * 4 + 1] * (Y_TOP - Y_BOT) : F[3][q * 4 + 1]; };
    const byY = Array.from({ length: N_SURF }, (_, q) => q).sort((a, b) => s3y(b) - s3y(a));
    const perC = Math.floor(N_SURF / NCOL);
    for (let c = 0; c < NCOL; c++) {
      const list = byY.slice(c * perC, c === NCOL - 1 ? N_SURF : (c + 1) * perC);
      const nx = 4, nz = 3, ny = Math.ceil(list.length / (nx * nz)), x0 = COL_X(c), ss = SESSIONS[c];
      const kind = !ss.above ? K.DIM : ss.regime === 'premium' ? K.GREEN : K.BRIGHT; // a session the record does not put above the floor stays dim
      list.sort((a, b) => R(a, 2) - R(b, 2)).forEach((q, j) => {
        const a = j % nx, b = Math.floor(j / nx) % nz, h = Math.floor(j / (nx * nz));
        const x = x0 + (a - (nx - 1) / 2) * 0.026, z = (b - (nz - 1) / 2) * 0.026, y = Y_FLOOR + 0.04 + (h + 0.5) / ny * H_COL;
        set(4, q, x, y, z, code(M.COLUMN, kind, c));
        KEY[q * 4 + 3] = (c + 0.55 * (h / ny)) / (NCOL + 0.55);
      });
    }
    orbOrder.forEach((ii, j) => {
      const u = j / N_ORB, x = -COL_SPAN / 2 - 0.16 + u * (COL_SPAN + 0.32);
      set(4, ii, x, Y_FLOOR + gauss() * 0.002, gauss() * 0.004, code(M.STATIC, K.DIM, 9));
      KEY[ii * 4 + 3] = u * 0.9;
    });
    for (let q = 0; q < N_SIG; q++) { // a few signals settle as slow dust over the columns
      const ii = I_SIG + q;
      set(4, ii, (rnd() - 0.5) * (COL_SPAN + 0.8), Y_FLOOR + 0.1 + rnd() * 1.2, (rnd() - 0.5) * 1.2 - 0.2, code(M.DRIFT, K.DUST, 0));
    }
    // S0 → S1 keys for the rest; dust never moves between scenes
    for (let q = 0; q < N_SIG; q++) { const ii = I_SIG + q; KEY[ii * 4 + 1] = KEY[ii * 4 + 1] || rnd(); }
  })();

  /* ================= shaders ================= */
  const GATE_GLSL = GATE_Y.map(v => v.toFixed(4));
  const VS_BULK = `
  precision highp float;
  attribute vec4 a_from, a_to, a_rand, a_key;
  uniform mat4 u_view, u_proj;
  uniform float u_time, u_m, u_spread, u_swirl, u_lift, u_keyIdx, u_sA, u_sB, u_spin, u_pr, u_dist, u_fogR, u_halo, u_maxpt, u_intro, u_shade;
  uniform vec3 u_liftDir, u_light;
  uniform vec3 u_rU[12]; uniform vec3 u_rV[12]; uniform float u_rW[12];
  uniform float u_hov[24]; uniform float u_hovOn, u_hovScene, u_sceneA, u_sceneB, u_hovLift;
  uniform vec4 u_occ;
  varying vec3 v_col; varying float v_a, v_size, v_soft, v_halo;
  const float PI = 3.14159265, TAU = 6.2831853;
  mat3 rotY(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
  float pinch(float y, float g, float w, float k) { float x = (y - g) / w; return 1.0 - k * exp(-x * x); }
  float laneW(float y) { // the stream narrows through every gate, hardest at the council
    float w = 0.13 + max(0.0, y - ${GATE_GLSL[0]}) * 0.7;
    w *= pinch(y, ${GATE_GLSL[0]}, 0.05, 0.3) * pinch(y, ${GATE_GLSL[1]}, 0.05, 0.3) * pinch(y, ${GATE_GLSL[2]}, 0.05, 0.3);
    w *= pinch(y, ${GATE_GLSL[3]}, 0.06, 0.6) * pinch(y, ${GATE_GLSL[4]}, 0.05, 0.3) * pinch(y, ${GATE_GLSL[5]}, 0.05, 0.3);
    return w;
  }
  vec3 resolve(vec4 s, out float kind, out float grp, out float al) {
    float mode = floor(s.w / 1000.0 + 0.001);
    float rem = s.w - mode * 1000.0;
    kind = floor(rem / 100.0 + 0.001);
    grp = rem - kind * 100.0;
    al = 1.0;
    vec4 r = a_rand;
    if (mode < 0.5) return s.xyz;
    if (mode < 1.5) return rotY(u_spin) * s.xyz;
    if (mode < 3.5) { // orbit (S0, rings 0-5) or lifecycle ring (S1, rings 6-11): x angle, y radius, z lift
      int k = int(grp + 0.5) + (mode > 2.5 ? 6 : 0);
      float a = s.x + u_time * u_rW[k];
      vec3 U = u_rU[k], V = u_rV[k];
      return (cos(a) * U + sin(a) * V) * s.y + normalize(cross(U, V)) * s.z;
    }
    if (mode < 4.5) { // estimation: agents above the boundary never sit still
      float t = u_time;
      return s.xyz + 0.011 * vec3(sin(t * 2.1 + r.x * 40.0), 0.35 * sin(t * 1.6 + r.y * 40.0), sin(t * 1.9 + r.z * 40.0)) * (0.55 + 0.45 * sin(t * 0.7 + r.w * 6.28));
    }
    if (mode < 5.5) { // a signal drifts in on a curved path and is absorbed at its target
      vec3 T = grp < 0.5 ? rotY(u_spin) * s.xyz : s.xyz;
      float ph = fract(r.y + u_time * (0.05 + 0.035 * r.x));
      vec3 S;
      if (grp < 1.5) {
        vec3 d = normalize(s.xyz + vec3(0.0001));
        if (grp > 0.5) d = normalize(vec3(cos(r.z * TAU), (r.w - 0.5) * 0.7, sin(r.z * TAU)));
        S = rotY((r.w - 0.5) * 1.4) * (d * (2.3 + 1.3 * r.z)) + vec3(0.0, (r.x - 0.5) * 0.8, 0.0);
      } else S = T + vec3((r.z - 0.5) * 0.7, 0.16 + 0.24 * r.x, (r.w - 0.5) * 0.35); // a tight funnel just above the lane
      float e = ph * ph;
      al = smoothstep(0.0, 0.14, ph) * (1.0 - smoothstep(0.9, 1.0, ph)) * (1.0 + 1.4 * smoothstep(0.72, 0.92, ph));
      vec3 P = mix(S, T, e);
      return rotY((1.0 - e) * (r.w - 0.5) * 1.1) * (P - T) + T;
    }
    if (mode < 7.5) { // the stream down the lane; a few proposals leave it at the council and fall away
      float ph = fract(s.y + u_time * 0.05);
      float y = ${Y_TOP.toFixed(3)} - ph * ${(Y_TOP - Y_BOT).toFixed(3)};
      al = smoothstep(0.0, 0.05, ph) * (1.0 - smoothstep(0.9, 1.0, ph));
      float yc = ${GATE_GLSL[COUNCIL]};
      if (mode > 6.5 && y < yc) {
        float tau = (yc - y) / ${(GATE_Y[COUNCIL] - Y_BOT).toFixed(3)};
        kind = 3.0;
        al = pow(1.0 - tau, 1.4);
        float tf = tau * 1.35;
        return vec3(${LX.toFixed(3)} + 0.04 + (0.62 + 0.25 * r.x) * (1.0 - exp(-tf * 2.4)), yc + 0.05 * tf - 0.52 * tf * tf, (r.z - 0.5) * 0.4 * tau);
      }
      float w = laneW(y);
      return vec3(${LX.toFixed(3)} + s.x * w, y, s.z * w * 0.6);
    }
    if (mode < 8.5) { // signals fall onto the top layer and are absorbed
      float ph = fract(r.y + u_time * (0.07 + 0.05 * r.x));
      al = smoothstep(0.0, 0.15, ph) * (1.0 - smoothstep(0.82, 1.0, ph));
      return s.xyz + vec3(0.0, (1.0 - ph * ph) * (0.28 + 0.3 * r.z), 0.0);
    }
    if (mode < 9.5) { // dust: a slow wander
      float t = u_time;
      return s.xyz + 0.05 * vec3(sin(t * 0.13 + r.x * 6.28), sin(t * 0.11 + r.y * 6.28), cos(t * 0.09 + r.z * 6.28));
    }
    // a session column: solid low, open at the top (no magnitude above the floor)
    al = 1.0 - smoothstep(0.62, 1.0, (s.y - ${Y_FLOOR.toFixed(3)}) / ${H_COL.toFixed(3)}) * 0.78;
    return s.xyz;
  }
  vec3 kcol(float k) {
    if (k < 0.5) return vec3(0.94, 0.93, 0.90);
    if (k < 1.5) return vec3(0.70, 0.67, 0.57);
    if (k < 2.5) return vec3(0.33, 0.82, 0.60);
    if (k < 3.5) return vec3(0.86, 0.42, 0.37);
    if (k < 4.5) return vec3(0.78, 0.79, 0.75);
    if (k < 5.5) return vec3(0.93, 0.92, 0.88);
    if (k < 6.5) return vec3(0.86, 0.85, 0.81);
    if (k < 7.5) return vec3(0.33, 0.82, 0.60);
    return vec3(0.99, 0.98, 0.95);
  }
  // size, alpha, softness, halo weight per kind
  vec4 kprop(float k) {
    if (k < 0.5) return vec4(1.0, 0.80, 0.0, 0.0);
    if (k < 1.5) return vec4(0.95, 0.72, 0.0, 0.0);
    if (k < 2.5) return vec4(1.08, 0.95, 0.0, 1.0);
    if (k < 3.5) return vec4(1.08, 0.95, 0.0, 1.0);
    if (k < 4.5) return vec4(0.62, 0.20, 1.0, 0.0);
    if (k < 5.5) return vec4(0.72, 0.55, 1.0, 0.25);
    if (k < 6.5) return vec4(0.82, 0.46, 0.0, 0.0);
    if (k < 7.5) return vec4(0.9, 0.62, 0.0, 0.6);
    return vec4(1.15, 1.0, 0.0, 0.5);
  }
  float easeSpring(float t) { float s = t * t * (3.0 - 2.0 * t); float u = s - 1.0; return 1.0 + ${C3.toFixed(3)} * u * u * u + ${C1.toFixed(3)} * u * u; }
  void main() {
    float kA, gA, aA, kB, gB, aB;
    vec3 A = resolve(a_from, kA, gA, aA) * u_sA;
    vec3 B = resolve(a_to, kB, gB, aB) * u_sB;
    float key = u_keyIdx < 0.5 ? a_key.x : (u_keyIdx < 1.5 ? a_key.y : (u_keyIdx < 2.5 ? a_key.z : a_key.w));
    float t = clamp((u_m - key * u_spread) / (1.0 - u_spread), 0.0, 1.0);
    float te = easeSpring(t), tc = clamp(te, 0.0, 1.0), arc = sin(PI * tc);
    vec3 D = B - A;
    float L = min(length(D), 1.8);
    vec3 lift = u_liftDir * arc * L * u_lift * (0.7 + 0.6 * a_rand.z);
    vec3 Pl = A + D * te;
    // the swirl: interpolate round the vertical axis, so rings open and close instead of cutting across
    float ra = length(A.xz), rb = length(B.xz);
    float pa = atan(A.z, A.x + 1e-6), pb = atan(B.z, B.x + 1e-6);
    if (ra < 1e-3) pa = pb;
    if (rb < 1e-3) pb = pa;
    float dp = mod(pb - pa + PI, TAU) - PI;
    float rr = mix(ra, rb, te), pp = pa + dp * te;
    vec3 Pc = vec3(cos(pp) * rr, mix(A.y, B.y, te), sin(pp) * rr);
    vec3 P = mix(Pl, Pc, u_swirl) + lift;
    float k = te < 0.5 ? kA : kB;
    float g = te < 0.5 ? gA : gB;
    float sc = te < 0.5 ? u_sceneA : u_sceneB;
    float h = 0.0;
    if (u_hovOn > 0.001 && abs(sc - u_hovScene) < 0.5) h = u_hov[int(clamp(g, 0.0, 23.0) + 0.5)];
    P.y += h * u_hovLift;
    vec4 mv = u_view * vec4(P, 1.0);
    gl_Position = u_proj * mv;
    vec4 pr = kprop(k), prB = kprop(kB), prA = kprop(kA);
    vec3 col = mix(kcol(kA), kcol(kB), tc);
    float al = mix(prA.y * aA, prB.y * aB, tc);
    float soft = mix(prA.z, prB.z, tc);
    float glow = mix(prA.w, prB.w, tc);
    // light: a green key from the upper left, an ivory rim, depth fog
    vec3 Nw = normalize(P + vec3(0.0, 0.0001, 0.0));
    vec3 Nv = (u_view * vec4(Nw, 0.0)).xyz;
    float diff = clamp(dot(Nv, u_light), 0.0, 1.0);
    float rim = pow(1.0 - abs(Nv.z), 3.0);
    // the globe is modelled (key, terminator, rim); flat structures only take a hint of it
    col = col * mix(0.62 + 0.5 * diff, 0.26 + 1.02 * diff, u_shade) + vec3(0.07, 0.20, 0.13) * diff * (1.0 - soft) * (1.0 + u_shade) + col * rim * (0.22 + 0.3 * u_shade);
    float fz = clamp((-mv.z - u_dist + u_fogR) / (2.0 * u_fogR), 0.0, 1.0);
    al *= mix(1.12, 0.26, fz);
    // the globe hides what is behind it
    if (u_occ.w > 0.0) {
      vec4 oc = u_view * vec4(u_occ.xyz, 1.0);
      vec2 d2 = mv.xy / -mv.z - oc.xy / -oc.z;
      float inside = 1.0 - smoothstep(0.88, 1.02, length(d2) / (u_occ.w / -oc.z));
      float behind = smoothstep(0.0, 0.25 * u_occ.w, oc.z - mv.z);
      al *= 1.0 - 0.8 * inside * behind;
    }
    float green = step(1.5, k) * step(k, 2.5);
    al *= 1.0 - 0.16 * green * (0.5 + 0.5 * sin(u_time * 2.2 + a_rand.w * 6.283));
    float dim = u_hovOn * (1.0 - h);
    al *= (1.0 + 0.55 * h) * (1.0 - 0.5 * dim);
    // the intro: the globe draws in band by band, from the top
    float ia = clamp(u_intro * 1.7 - a_key.x * 0.7, 0.0, 1.0);
    al *= ia;
    float persp = u_dist / max(0.2, -mv.z);
    float size = pr.x * (1.55 + 1.15 * a_rand.x) * mix(0.82, 1.18, persp - 0.5) * (1.0 + 0.3 * h) * mix(1.1, 0.8, fz) * (0.55 + 0.45 * ia) * u_pr;
    v_soft = soft; v_halo = 0.0;
    if (u_halo > 0.5) {
      float hw = max(glow, h * 0.6);
      if (hw < 0.01 || al < 0.01) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0; v_a = 0.0; v_col = col; v_size = 1.0; return; }
      size *= 4.2;
      al *= 0.085 * hw;
      v_halo = 1.0;
    }
    size = clamp(size, 1.0, u_maxpt);
    gl_PointSize = size;
    v_size = size; v_a = al; v_col = col;
  }`;
  const FS_BULK = `
  precision mediump float;
  varying vec3 v_col; varying float v_a, v_size, v_soft, v_halo;
  void main() {
    vec2 q = gl_PointCoord - 0.5;
    float d = length(q), a;
    if (v_halo > 0.5) a = exp(-d * d * 15.0) * (1.0 - smoothstep(0.42, 0.5, d));
    else {
      float aa = 1.0 / max(v_size, 1.0);
      float disc = 1.0 - smoothstep(0.5 - aa * 1.6, 0.5, d);
      float bead = 0.74 + 0.36 * (1.0 - smoothstep(0.0, 0.42, length(q - vec2(-0.13, -0.13))));
      a = mix(disc * bead, exp(-d * d * 11.0), v_soft);
    }
    a *= v_a;
    gl_FragColor = vec4(v_col * a, a);
  }`;
  // hairlines: screen-space quads, anti-aliased, one CSS pixel wide whatever the DPR
  const VS_LINE = `
  precision highp float;
  attribute vec2 a_corner; attribute vec3 a_p0, a_p1; attribute vec4 a_col; attribute float a_w;
  uniform mat4 u_view, u_proj; uniform vec2 u_res; uniform float u_pr, u_dist, u_fogR; uniform vec4 u_occ;
  varying vec4 v_col; varying float v_side, v_hw;
  void main() {
    vec4 v0 = u_view * vec4(a_p0, 1.0), v1 = u_view * vec4(a_p1, 1.0);
    vec4 c0 = u_proj * v0, c1 = u_proj * v1;
    vec2 s0 = c0.xy / c0.w, s1 = c1.xy / c1.w;
    vec2 d = (s1 - s0) * u_res * 0.5;
    float len = length(d);
    vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
    vec2 n = vec2(-dir.y, dir.x);
    float hw = 0.5 * a_w * u_pr;
    vec4 c = mix(c0, c1, a_corner.x);
    vec4 vv = mix(v0, v1, a_corner.x);
    vec2 off = n * a_corner.y * (hw + 1.0) + dir * (a_corner.x * 2.0 - 1.0) * 0.5;
    c.xy += off / (u_res * 0.5) * c.w;
    gl_Position = c;
    v_side = a_corner.y * (hw + 1.0); v_hw = hw;
    float fz = clamp((-vv.z - u_dist + u_fogR) / (2.0 * u_fogR), 0.0, 1.0);
    float al = a_col.a * mix(1.1, 0.38, fz);
    if (u_occ.w > 0.0) {
      vec4 oc = u_view * vec4(u_occ.xyz, 1.0);
      vec2 d2 = vv.xy / -vv.z - oc.xy / -oc.z;
      float inside = 1.0 - smoothstep(0.9, 1.02, length(d2) / (u_occ.w / -oc.z));
      al *= 1.0 - 0.85 * inside * smoothstep(0.0, 0.2 * u_occ.w, oc.z - vv.z);
    }
    v_col = vec4(a_col.rgb, al);
  }`;
  const FS_LINE = `
  precision mediump float;
  varying vec4 v_col; varying float v_side, v_hw;
  void main() {
    float cov = clamp(v_hw + 0.5 - abs(v_side), 0.0, 1.0);
    float a = v_col.a * cov;
    gl_FragColor = vec4(v_col.rgb * a, a);
  }`;
  // the actors: proposal ring (morphs into the settled square), record block, tick, bead, soft flash
  const VS_ACT = `
  precision highp float;
  attribute vec3 a_pos; attribute vec4 a_col; attribute vec4 a_shp;
  uniform mat4 u_view, u_proj; uniform float u_pr, u_dist, u_fogR, u_halo, u_maxpt;
  varying vec4 v_col; varying vec4 v_shp; varying float v_size;
  void main() {
    vec4 mv = u_view * vec4(a_pos, 1.0);
    gl_Position = u_proj * mv;
    float persp = u_dist / max(0.2, -mv.z);
    float sz = a_shp.y * u_pr * mix(1.0, persp, 0.5);
    float fz = clamp((-mv.z - u_dist + u_fogR) / (2.0 * u_fogR), 0.0, 1.0);
    float al = a_col.a * mix(1.05, 0.45, fz);
    float size = sz + 2.0;
    if (u_halo > 0.5) {
      if (a_shp.z < 0.01 || al < 0.01) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0; v_col = vec4(0.0); v_shp = vec4(0.0); v_size = 1.0; return; }
      size = sz * 3.4; al *= 0.16 * a_shp.z;
    }
    size = clamp(size, 1.0, u_maxpt);
    gl_PointSize = size;
    v_size = size; v_col = vec4(a_col.rgb, al); v_shp = vec4(a_shp.x, a_shp.w, u_halo, min(sz, size - 2.0));
  }`;
  const FS_ACT = `
  precision mediump float;
  varying vec4 v_col; varying vec4 v_shp; varying float v_size;
  float box(vec2 p, vec2 b, float r) { vec2 q = abs(p) - b + r; return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r; }
  float seg(vec2 p, vec2 a, vec2 b) { vec2 pa = p - a, ba = b - a; float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0); return length(pa - ba * h); }
  void main() {
    vec2 q = (gl_PointCoord - 0.5) * v_size; // device px, y down
    float s = v_shp.w, shape = v_shp.x, aux = v_shp.y, a;
    if (v_shp.z > 0.5) { float d = length(gl_PointCoord - 0.5); a = exp(-d * d * 14.0) * (1.0 - smoothstep(0.42, 0.5, d)); }
    else if (shape < 0.5) { a = clamp(s * 0.5 - length(q) + 0.5, 0.0, 1.0); }
    else if (shape < 1.5) { // proposal ring → settled square (aux 0 → 1)
      float sw = max(1.15, s * 0.12);
      float ring = abs(length(q) - (s * 0.5 - sw * 0.5)) - sw * 0.5;
      float sq = box(q, vec2(s * 0.36), s * 0.06);
      a = clamp(0.5 - mix(ring, sq, aux), 0.0, 1.0);
    }
    else if (shape < 2.5) { // record block: a 2:1 bar with its hash slot
      float b = box(q, vec2(s * 0.5, s * 0.22), 1.0);
      float slot = box(q - vec2(s * 0.28, 0.0), vec2(s * 0.09, s * 0.07), 0.5);
      a = clamp(0.5 - b, 0.0, 1.0) * (1.0 - 0.55 * clamp(0.5 - slot, 0.0, 1.0));
    }
    else if (shape < 3.5) { // broker-confirmed tick
      float d = min(seg(q, vec2(-0.34, 0.02) * s, vec2(-0.1, 0.26) * s), seg(q, vec2(-0.1, 0.26) * s, vec2(0.36, -0.24) * s));
      a = clamp(max(1.0, s * 0.09) - d + 0.5, 0.0, 1.0);
    }
    else { float d = length(q) / (s * 0.5); a = exp(-d * d * 3.0) * (1.0 - smoothstep(0.85, 1.0, d)); }
    a *= v_col.a;
    gl_FragColor = vec4(v_col.rgb * a, a);
  }`;

  /* ================= GL resources (built under the loader, rebuilt on restore) ================= */
  let gl = null, lost = false, ext = null, ready = false;
  const P = {}; // programs: {prog, u: {}, a: {}}
  const BUF = {};
  let N_LINE_MAX = 6000, N_ACT_MAX = 160;
  const lineData = new Float32Array(N_LINE_MAX * 11), actData = new Float32Array(N_ACT_MAX * 11);
  const guard = (fn) => { try { fn(); } catch (e) { if (gl && !gl.isContextLost()) fail(e); } };
  let setupGen = 0;
  function program(vs, fs) {
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const v = sh(gl.VERTEX_SHADER, vs), f = sh(gl.FRAGMENT_SHADER, fs), p = gl.createProgram();
    gl.attachShader(p, v); gl.attachShader(p, f); gl.linkProgram(p);
    return { prog: p, v, f, u: {}, a: {} };
  }
  function bindProgram(pr, unis, attrs) {
    unis.forEach(n => { pr.u[n] = gl.getUniformLocation(pr.prog, n); });
    attrs.forEach(n => { pr.a[n] = gl.getAttribLocation(pr.prog, n); });
  }
  function setupGL(done) { guard(() => {
    ext = gl.getExtension('ANGLE_instanced_arrays');
    const progs = { bulk: program(VS_BULK, FS_BULK), line: program(VS_LINE, FS_LINE), act: program(VS_ACT, FS_ACT) };
    const par = gl.getExtension('KHR_parallel_shader_compile'); // poll the links instead of stalling the main thread on them
    const gen = ++setupGen;
    (function linked() { guard(() => {
      if (gen !== setupGen || gl.isContextLost()) return;
      if (par && !Object.values(progs).every(p => gl.getProgramParameter(p.prog, par.COMPLETION_STATUS_KHR))) { requestAnimationFrame(linked); return; }
      Object.values(progs).forEach(p => {
        if (!gl.getProgramParameter(p.prog, gl.LINK_STATUS)) throw new Error('story shader: ' + (gl.getShaderInfoLog(p.v) || gl.getShaderInfoLog(p.f) || gl.getProgramInfoLog(p.prog)));
      });
      Object.assign(P, progs);
      bindProgram(P.bulk, ['u_view', 'u_proj', 'u_time', 'u_m', 'u_spread', 'u_swirl', 'u_lift', 'u_keyIdx', 'u_sA', 'u_sB', 'u_spin', 'u_pr', 'u_dist', 'u_fogR', 'u_halo', 'u_maxpt', 'u_intro', 'u_shade', 'u_liftDir', 'u_light', 'u_rU', 'u_rV', 'u_rW', 'u_hov', 'u_hovOn', 'u_hovScene', 'u_sceneA', 'u_sceneB', 'u_hovLift', 'u_occ'], ['a_from', 'a_to', 'a_rand', 'a_key']);
      bindProgram(P.line, ['u_view', 'u_proj', 'u_res', 'u_pr', 'u_dist', 'u_fogR', 'u_occ'], ['a_corner', 'a_p0', 'a_p1', 'a_col', 'a_w']);
      bindProgram(P.act, ['u_view', 'u_proj', 'u_pr', 'u_dist', 'u_fogR', 'u_halo', 'u_maxpt'], ['a_pos', 'a_col', 'a_shp']);
      const buf = (data, usage) => { const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, data, usage || gl.STATIC_DRAW); return b; };
      BUF.scene = F.map(f => buf(f));
      BUF.rand = buf(RAND); BUF.key = buf(KEY);
      BUF.corner = buf(new Float32Array([0, -1, 1, -1, 0, 1, 1, 1]));
      BUF.line = buf(lineData, gl.DYNAMIC_DRAW);
      BUF.act = buf(actData, gl.DYNAMIC_DRAW);
      maxPt = (gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE) || [1, 64])[1];
      gl.useProgram(P.bulk.prog);
      const rU = [], rV = [], rW = [];
      OB.forEach((b, k) => { rU.push(...b.U); rV.push(...b.V); rW.push(ORBITS[k][3]); });
      RB.forEach((b, k) => { rU.push(...b.U); rV.push(...b.V); rW.push(RINGS[k][3]); });
      gl.uniform3fv(P.bulk.u.u_rU, new Float32Array(rU)); gl.uniform3fv(P.bulk.u.u_rV, new Float32Array(rV)); gl.uniform1fv(P.bulk.u.u_rW, new Float32Array(rW));
      const L = [-0.52, 0.62, 0.58], l = Math.hypot(...L);
      gl.uniform3f(P.bulk.u.u_light, L[0] / l, L[1] / l, L[2] / l);
      gl.disable(gl.DEPTH_TEST); gl.enable(gl.BLEND);
      ready = true;
      done();
    }); })();
  }); }
  let maxPt = 64;

  /* ================= matrices & projection ================= */
  const proj = new Float32Array(16), view = new Float32Array(16), vp = new Float32Array(16);
  const FOV = 0.56, CAM_D = 6.2;
  function perspective(out, fovy, aspect, near, far, sx, sy) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
    out.fill(0); out[0] = f / aspect; out[5] = f; out[10] = (far + near) * nf; out[11] = -1; out[14] = 2 * far * near * nf;
    out[8] = -sx; out[9] = -sy; // an off-centre frustum: the scene's centre lands on its frame, not the screen's
  }
  function lookAt(out, e, t) {
    let zx = e[0] - t[0], zy = e[1] - t[1], zz = e[2] - t[2], l = Math.hypot(zx, zy, zz); zx /= l; zy /= l; zz /= l;
    let xx = zz, xy = 0, xz = -zx; l = Math.hypot(xx, xy, xz) || 1; xx /= l; xz /= l;
    const yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
    out[0] = xx; out[1] = yx; out[2] = zx; out[3] = 0; out[4] = xy; out[5] = yy; out[6] = zy; out[7] = 0; out[8] = xz; out[9] = yz; out[10] = zz; out[11] = 0;
    out[12] = -(xx * e[0] + xy * e[1] + xz * e[2]); out[13] = -(yx * e[0] + yy * e[1] + yz * e[2]); out[14] = -(zx * e[0] + zy * e[1] + zz * e[2]); out[15] = 1;
  }
  function mul(out, a, b) { for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k]; out[i * 4 + j] = s; } }
  const PO = { x: 0, y: 0, z: 0, w: 1 };
  function project(x, y, z) { // world → CSS px (+ view depth)
    const cx = vp[0] * x + vp[4] * y + vp[8] * z + vp[12], cy = vp[1] * x + vp[5] * y + vp[9] * z + vp[13], cw = vp[3] * x + vp[7] * y + vp[11] * z + vp[15];
    PO.x = (cx / cw * 0.5 + 0.5) * W; PO.y = (0.5 - cy / cw * 0.5) * H; PO.w = cw; return PO;
  }

  /* ================= layout: each scene fitted into the frame the copy leaves free ================= */
  let W = 1, H = 1, dpr = 1, ratio = 0, stacked = false, navH = 72, barH = 64, gutter = 24;
  const EXT = [[2.9, 2.5], [3.45, 2.2], [2.75, 2.75], [2.55, 2.5], [3.8, 2.0]]; // local extent seen from each scene's camera (w, h)
  const CENTER = [[0, 0, 0], [0, 0.04, 0], [0, -0.02, 0], [0.12, 0.08, 0], [0, Y_FLOOR + 0.6, 0]]; // S4 sits low: the floor line is where the paper will rise to
  const CAM = [[0.13, 0.0], [0.6, -0.08], [0.5, -0.56], [0.17, -0.07], [0.12, 0.0]]; // elevation, azimuth
  const ROOM_W = [0, 250, 236, 214, 0]; // room kept on the right of the structure for its callouts (wide layouts)
  const ZONE = ['right', 'upper', 'right', 'right', 'right'];
  const layouts = Array.from({ length: 5 }, () => ({ cx: 0, cy: 0, s: 1, rect: [0, 0, 0, 0] }));
  const beatRects = [], numFit = [0, 0, 0, 0];
  let storyTop = 0, run = 1, scrollY = 0;
  function measure() {
    scrollY = window.scrollY;
    storyTop = story.getBoundingClientRect().top + scrollY;
    run = Math.max(1, story.offsetHeight - window.innerHeight);
    const cs = getComputedStyle(stage);
    navH = parseFloat(cs.getPropertyValue('--nav-h')) || 72;
    const bar = stage.querySelector('.story-bar');
    barH = bar ? bar.offsetHeight : 64;
    const cont = stage.querySelector('.story-ui .container');
    gutter = (cont && parseFloat(getComputedStyle(cont).paddingLeft)) || 24; // --gutter is a clamp(): read it resolved
    beats.forEach((b, i) => { // where each beat's copy sits, untransformed (offsets ignore the scroll-driven translate)
      let l = 1e9, r = -1e9, t = 1e9;
      b.querySelectorAll('.beat-text, .hero-stats').forEach(el => {
        const x = el.offsetLeft + b.offsetLeft + b.offsetParent.offsetLeft, y = el.offsetTop + b.offsetTop;
        l = Math.min(l, x); r = Math.max(r, x + el.offsetWidth); t = Math.min(t, y);
      });
      const h2 = b.querySelector('h2, h1');
      beatRects[i] = { l, r, t, ht: h2 ? b.offsetTop + h2.offsetTop : t, hb: h2 ? b.offsetTop + h2.offsetTop + h2.offsetHeight : t };
    });
    // the chapter mark sits above the copy column: per hand-over, the scale that keeps it clear of both scenes' copy (0: no room)
    const nm = story.querySelector('.story-num');
    if (nm) {
      const nh = nm.offsetHeight, nt = nm.offsetTop;
      for (let a = 0; a < 4; a++) { const k = nh ? Math.min(1, (Math.min(beatRects[a].t, beatRects[a + 1].t) - nt - 18) / nh) : 0; numFit[a] = k < 0.42 ? 0 : k; }
    }
  }
  function fitScenes() {
    stacked = stackedMQ.matches;
    const pxu = (H / 2) / (CAM_D * Math.tan(FOV / 2));
    for (let i = 0; i < 5; i++) {
      const br = beatRects[i] && beatRects[i].r > 0 && beatRects[i].r < W ? beatRects[i] : { r: W * 0.46, t: H * 0.55 };
      let x0, x1, y0, y1;
      if (!stacked) { // right of this scene's copy (or, for the wide rings, above it), clear of the nav, the index and the callouts
        const room = Math.min(ROOM_W[i], W * 0.18);
        x1 = W - gutter - room; y0 = navH + 22;
        if (ZONE[i] === 'upper' && br.t - y0 > H * 0.36) { x0 = gutter + (W - 2 * gutter) * 0.3; y1 = br.t - 26; }
        else { x0 = Math.min(br.r + 36, W * 0.56); y1 = H - barH - 18; }
        if (x1 - x0 < 240) x0 = x1 - 240;
      } else { // above this scene's copy, under the index
        const room = [0, 0.13, 0.15, 0.1, 0][i] * W;
        x0 = gutter * 0.5; x1 = W - gutter * 0.5 - room; y0 = navH + barH + 6; y1 = Math.max(y0 + 120, Math.min(H * 0.8, br.t) - 14);
      }
      const rw = x1 - x0, rh = y1 - y0;
      let s = Math.min(rw / (EXT[i][0] * pxu), rh / (EXT[i][1] * pxu));
      s = Math.min(s, (H * 0.74) / (EXT[i][1] * pxu));
      layouts[i] = { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, s, rect: [x0, y0, x1, y1] };
    }
  }

  /* ================= scene state ================= */
  // the clocks start mid-flow: the ledger already holds records, proposals are already in the lane (and a still frame — reduced motion — reads)
  let sNow = 0, sTarget = 0, xNow = 0, xTarget = 0, time = 14.3, intro = 0, introStart = -1;
  let seg = 0, mRaw = 0, mE = 0, scale = [1, 1];
  let eye = [0, 0, CAM_D], target = [0, 0, 0], camD = CAM_D;
  const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
  function sceneScroll() {
    const p = clamp((scrollY - storyTop) / run, 0, 1), u = p * TOTAL_U;
    sTarget = Math.min(4, u); xTarget = clamp((u - 4) / EXIT_U, 0, 1);
  }
  // the morph state for the current pair of scenes: a hold at each end, the stagger in between
  function morphState() {
    let s = sNow;
    if (reducedMQ.matches) s = Math.round(s); // reduced motion: the scenes snap
    seg = Math.min(3, Math.floor(s));
    const f = s - seg;
    mRaw = clamp((f - HOLD) / (1 - 2 * HOLD), 0, 1);
    mE = mRaw * mRaw * (3 - 2 * mRaw);
  }
  const SWIRL = [0.85, 0.7, 0.25, 0.0], LIFT = [0.18, 0.22, 0.3, 0.32], SHADE = [1, 0.3, 0.25, 0.15, 0.2];
  const LIFT_DIR = [[0, 1, 0], [0, 1, 0], [0, 0, 1], [0, 1, 0.35]];

  // where a scene's local point lands in the world, given the scene and the current fit
  function camera() {
    const a = layouts[seg], b = layouts[seg + 1];
    const L = { cx: lerp(a.cx, b.cx, mE), cy: lerp(a.cy, b.cy, mE) };
    scale = [a.s, b.s];
    const el = lerp(CAM[seg][0], CAM[seg + 1][0], mE) + (reducedMQ.matches ? 0 : mouse.y * 0.06);
    const az = lerp(CAM[seg][1], CAM[seg + 1][1], mE) + (reducedMQ.matches ? 0 : mouse.x * 0.11);
    const tc = [lerp(CENTER[seg][0] * a.s, CENTER[seg + 1][0] * b.s, mE), lerp(CENTER[seg][1] * a.s, CENTER[seg + 1][1] * b.s, mE), 0];
    target = tc;
    eye = [tc[0] + Math.sin(az) * Math.cos(el) * CAM_D, tc[1] + Math.sin(el) * CAM_D, tc[2] + Math.cos(az) * Math.cos(el) * CAM_D];
    lookAt(view, eye, target);
    const frust = (cy) => { perspective(proj, FOV, W / H, 0.1, 40, (L.cx / W) * 2 - 1, 1 - (cy / H) * 2); mul(vp, proj, view); };
    frust(L.cy);
    if (seg === 3 && xNow > 0) { // the hand-off: the proof settles lower as the paper rises to meet it, so the paper is a page edge, not a wall
      const f = project(0, Y_FLOOR * layouts[4].s, 0).y, xe = reducedMQ.matches ? (xNow > 0.5 ? 1 : 0) : xNow;
      frust(L.cy + Math.max(0, H * (stacked ? 0.7 : 0.76) - f) * sstep(0, 0.7, xe));
    }
  }

  /* ================= actors: proposals, decisions, settled squares, records, ticks ================= */
  const hash = (n) => { let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b); x ^= x >>> 13; x = Math.imul(x, 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296; };
  const EMIT = 0.92, T_IN = 0.55, T_SEG = 0.46, T_DWELL = 0.15, T_COUNCIL = 0.34, T_SNAP = 0.22, T_DROP = 0.42, T_FALL = 1.6;
  const ARR = []; { let t = T_IN; for (let g = 0; g < 6; g++) { ARR.push(t); t += (g === COUNCIL ? T_COUNCIL : T_DWELL) + T_SEG; } }
  const T_DEC = ARR[COUNCIL] + T_COUNCIL, T_REC = ARR[5] + T_DWELL + T_SNAP + T_DROP;
  const rejected = (n) => hash(n * 7 + 3) < 0.2;
  const C = { ivory: [0.96, 0.95, 0.92], green: [0.31, 0.80, 0.58], red: [0.85, 0.40, 0.36], khaki: [0.68, 0.65, 0.56] };
  function councilPulse(T) { // the most recent decision: when, and which way
    const nNow = Math.floor((T - T_DEC) / EMIT);
    if (nNow < 0) return { k: 0, rej: false };
    const dt = T - (nNow * EMIT + T_DEC);
    return { k: Math.exp(-dt / 0.3), rej: rejected(nNow), dt };
  }
  function ledger(T) { // the ten most recent records (newest first) and when the newest arrived
    const out = [];
    for (let n = Math.floor((T - T_REC) / EMIT); n >= 0 && out.length < LEDGER_N + 1; n--) if (!rejected(n)) out.push(n);
    return out;
  }
  // every actor: id → {p:[x,y,z] local, col, a, shape, size, glow, aux}
  function actorsFor(sc, T, out) {
    const put = (id, x, y, z, col, a, shape, size, glow, aux) => { out.set(id, { p: [x, y, z], col, a, shape, size, glow: glow || 0, aux: aux || 0 }); };
    if (sc === 0) {
      [0, 2, 4].forEach((k, j) => { const th = 1.1 + j * 2.1 + T * ORBITS[k][3] * 1.6; const p = onLoop(OB[k], ORBITS[k][0], th, 0); put('p' + j, p[0], p[1], p[2], C.green, 0.95, 1, 9, 0.8, 0); });
    } else if (sc === 1) {
      for (let j = 0; j < 3; j++) { const th = 0.6 + j * TAU / 3 + T * RINGS[0][3]; const p = onLoop(RB[0], RINGS[0][0], th, 0); put('p' + j, p[0], p[1], p[2], C.green, 1, 1, 9, 0.8, 0); }
    } else if (sc === 2) { // one proposal at a time crosses the boundary: it wanders above it, steps on the grid below it
      for (let j = 0; j < 3; j++) {
        const per = 6.0, ph = ((T / per + j / 3) % 1 + 1) % 1, cyc = Math.floor(T / per + j / 3);
        const x0 = (hash(cyc * 3 + j) - 0.5) * 1.0, z0 = (hash(cyc * 5 + j) - 0.5) * 0.6;
        let x, y, z, aux = 0, a = 1;
        if (ph < 0.5) { const u = ph / 0.5; y = lerp(PL_Y(0) + 0.08, 0.02, u); x = x0 + Math.sin(T * 2.3 + j) * 0.05; z = z0 + Math.cos(T * 1.9 + j) * 0.04; a = sstep(0, 0.08, u); }
        else { const u = (ph - 0.5) / 0.5, st = Math.min(3, Math.floor(u * 4)), f = sstep(0.62, 1, u * 4 - st); y = lerp(PL_Y(4 + st) + 0.02, PL_Y(Math.min(7, 5 + st)) + 0.02, st < 3 ? f : 0); x = Math.round(x0 * 8) / 8; z = Math.round(z0 * 6) / 6; aux = sstep(0, 0.06, u); a = 1 - sstep(0.9, 1, u); }
        put('p' + j, x, y, z, C.green, a, 1, 9, 0.7, aux);
      }
    } else if (sc === 3) {
      const nNow = Math.floor(T / EMIT);
      for (let n = Math.max(0, nNow - 8); n <= nNow; n++) {
        const age = T - n * EMIT; if (age < 0) continue;
        const id = 'p' + (n % 8), rej = rejected(n), wob = (hash(n) - 0.5) * 0.06;
        let x = LX + wob, y, z = 0, col = C.green, a = 1, aux = 0, shape = 1, size = 11, glow = 0.8;
        if (age < ARR[0]) { const u = sstep(0, 1, age / ARR[0]); y = lerp(Y_TOP + 0.16, GATE_Y[0], u); a = sstep(0, 0.25, age / ARR[0]); }
        else {
          let g = 0; while (g < 5 && age >= ARR[g + 1]) g++;
          const dwell = g === COUNCIL ? T_COUNCIL : T_DWELL, inG = age - ARR[g];
          y = GATE_Y[g];
          if (inG > dwell && g < 5) y = lerp(GATE_Y[g], GATE_Y[g + 1], sstep(0, 1, (inG - dwell) / T_SEG));
          if (inG < 0.12) size = 11 + 4 * (1 - inG / 0.12); // a small flare as it meets each gate
          if (rej && age >= T_DEC) { // rejected: red, falls away with gravity and fades
            const tf = age - T_DEC; if (tf > T_FALL) continue;
            x = LX + 0.04 + 0.78 * (1 - Math.exp(-tf * 2.4)); y = GATE_Y[COUNCIL] + tf * 0.05 - 0.52 * tf * tf; z = tf * 0.08;
            col = C.red; a = 1 - sstep(0.5, T_FALL, tf); shape = 0; size = 7; glow = 0.9;
          } else if (age >= ARR[5]) { // settled: snaps into a square, drops to the ledger, becomes a record there
            const ts = age - ARR[5];
            if (ts > T_DWELL + T_SNAP + T_DROP) continue;
            aux = sstep(0, T_SNAP, ts - T_DWELL * 0.5);
            if (ts > T_DWELL + T_SNAP) { const u = sstep(0, 1, (ts - T_DWELL - T_SNAP) / T_DROP); x = lerp(LX, LEDGER_X0, u); y = lerp(GATE_Y[5], Y_LEDGER + 0.045, u) + Math.sin(u * PI) * 0.06; }
            size = 8.5;
          }
        }
        put(id, x, y, z, col, a, shape, size, glow, aux);
      }
      const recs = ledger(T);
      if (recs.length) {
        const tNew = recs[0] * EMIT + T_REC, sh = sstep(0, 1, (T - tNew) / 0.45);
        recs.forEach((n, j) => {
          const slot = j === 0 ? 0 : j - 1 + sh;
          const a = j === LEDGER_N ? 1 - sh : (j === 0 ? sstep(0, 0.12, T - tNew) : 1);
          if (j > LEDGER_N) return;
          put('r' + j, LEDGER_X0 + slot * LEDGER_DX, Y_LEDGER + 0.045, 0, C.ivory, a * 0.92, 2, 15, 0, 0);
        });
      }
    } else { // S4: each session's record on the floor (the ledger, hash-linked) and its broker-confirmed tick on top
      for (let c = 0; c < NCOL; c++) {
        const x = COL_X(c), prem = SESSIONS[c].regime === 'premium';
        put('r' + c, x, Y_FLOOR + 0.035, 0.04, prem ? C.green : C.ivory, 0.95, 2, 15, prem ? 0.5 : 0, 0);
        if (SESSIONS[c].confirmed) put('t' + c, x, Y_FLOOR + H_COL + 0.1, 0, C.green, 0.95, 3, 12, 0.5, 0);
      }
    }
    return out;
  }
  const actA = new Map(), actB = new Map();
  let nAct = 0;
  function buildActors() {
    actA.clear(); actB.clear();
    actorsFor(seg, simTime, actA); actorsFor(seg + 1, simTime, actB);
    const sA = scale[0], sB = scale[1];
    let o = 0;
    const emit = (p, col, a, shape, size, glow, aux) => {
      a *= intro;
      if (nAct >= N_ACT_MAX || a < 0.004) return;
      actData.set([p[0], p[1], p[2], col[0], col[1], col[2], a, shape, size, glow, aux], o); o += 11; nAct++;
    };
    nAct = 0;
    const keyOf = (id) => id[0] === 'r' ? 0.25 + 0.5 * (parseInt(id.slice(1), 10) / 11) : id[0] === 't' ? 0.7 : 0.35;
    actA.forEach((A, id) => {
      const B = actB.get(id), t = ease(stag(mRaw, keyOf(id)));
      if (B) {
        const p = [lerp(A.p[0] * sA, B.p[0] * sB, t), lerp(A.p[1] * sA, B.p[1] * sB, t) + Math.sin(PI * clamp(t, 0, 1)) * 0.12 * sB, lerp(A.p[2] * sA, B.p[2] * sB, t)];
        const tc = clamp(t, 0, 1);
        emit(p, [lerp(A.col[0], B.col[0], tc), lerp(A.col[1], B.col[1], tc), lerp(A.col[2], B.col[2], tc)], lerp(A.a, B.a, tc), tc < 0.5 ? A.shape : B.shape, lerp(A.size, B.size, tc), lerp(A.glow, B.glow, tc), lerp(A.aux, B.aux, tc));
      } else emit([A.p[0] * sA, A.p[1] * sA, A.p[2] * sA], A.col, A.a * (1 - clamp(t * 1.6, 0, 1)), A.shape, A.size, A.glow, A.aux);
    });
    actB.forEach((B, id) => {
      if (actA.has(id)) return;
      const t = clamp(ease(stag(mRaw, keyOf(id))), 0, 1);
      const rise = id[0] === 'r' || id[0] === 't' ? (1 - t) * -0.25 : 0;
      emit([B.p[0] * sB, (B.p[1] + rise) * sB, B.p[2] * sB], B.col, B.a * clamp(t * 1.4 - 0.2, 0, 1), B.shape, B.size, B.glow, B.aux);
    });
  }

  /* ================= hairlines: orbits, rings, layer rims, the boundary, gates, the aperture, the ledger, hash links ================= */
  const LOOP_N = LITE ? 72 : 112;
  const loopAngles = (az) => Array.from({ length: LOOP_N }, (_, j) => az - j / LOOP_N * TAU); // world angles shared by every loop shape
  const GEO = new Map(), geo = (k, fn) => { let g = GEO.get(k); if (!g) GEO.set(k, g = fn()); return g; }; // static shapes, built once
  function linesFor(sc, T, out) {
    const put = (id, pts, closed, col, a, w, key, dy) => out.set(id, { pts, closed, col, a, w: w || 1, key: key == null ? 0.5 : key, dy: dy || 0 });
    if (sc === 0) {
      ORBITS.forEach((o, k) => { const pts = geo('o0' + k, () => Array.from({ length: LOOP_N }, (_, j) => onLoop(OB[k], o[0], j / LOOP_N * TAU, 0))); put('o' + k, pts, true, k === 0 ? C.green : C.ivory, k === 0 ? 0.2 : 0.1, 1, 0.12 + 0.5 * k / 6); });
      put('hz', [[-1.35, -1.3, 0], [1.35, -1.3, 0]], false, C.ivory, 0.07, 1, 0.9);
    } else if (sc === 1) {
      RINGS.forEach((o, k) => {
        const pts = geo('o1' + k, () => Array.from({ length: LOOP_N }, (_, j) => onLoop(RB[k], o[0], j / LOOP_N * TAU, 0)));
        put('o' + k, pts, true, k === 0 ? C.green : k < 3 ? C.ivory : C.khaki, (k === 0 ? 0.42 : k < 3 ? 0.16 : 0.12) * (1 + 1.6 * hovFor(1, k)), 1 + 0.6 * hovFor(1, k), 0.15 + 0.6 * k / 6);
      });
      const tk = geo('tk1', () => { const t = []; for (let j = 0; j < 48; j++) { const a = j / 48 * TAU, l = j % 4 ? 0.03 : 0.07; t.push(onLoop(RB[0], RINGS[0][0] - 0.06, a, 0), onLoop(RB[0], RINGS[0][0] - 0.06 - l, a, 0)); } return t; });
      put('tk', tk, 'pairs', C.green, 0.32, 1, 0.3);
      put('hub', [[-0.07, 0, 0], [0.07, 0, 0], [0, 0, -0.07], [0, 0, 0.07], [0, -0.07, 0], [0, 0.07, 0]], 'pairs', C.ivory, 0.32, 1, 0.5);
      put('hz', [[-1.6, -0.92, 0], [1.6, -0.92, 0]], false, C.ivory, 0.0, 1, 0.9);
    } else if (sc === 2) {
      for (let p = 0; p < 8; p++) {
        const hp = hovFor(2, p), az = p < 6 ? RINGS[p][2] : 0, y = PL_Y(p);
        const pts = geo('o2' + p, () => loopAngles(az).map(ph => { const [x, z] = rrHit(ph, PL_HX, PL_HZ, PL_RC); return [x, y, z]; }));
        put('o' + p, pts, true, p === 3 ? C.green : C.ivory, (p < 4 ? 0.2 : 0.26) * (1 + 1.5 * hp) * (p === 3 ? 1.4 : 1), 1 + 0.5 * hp, (p + 0.2) / 8.4, reducedMQ.matches ? 0 : hp * 0.07);
      }
      const bd = geo('bd2', () => loopAngles(0).map(ph => { const [x, z] = rrHit(ph, PL_HX * 1.1, PL_HZ * 1.12, PL_RC * 1.6); return [x, 0, z]; }));
      put('bd', bd, true, C.green, 0.75, 1.25, 0.5);
      put('bdg', bd, true, C.green, 0.07, 7, 0.5);
      [[1, 1], [1, -1], [-1, 1], [-1, -1]].forEach(([sx, sz], j) => put('v' + j, [[sx * (PL_HX - 0.02), PL_Y(0), sz * (PL_HZ - 0.02)], [sx * (PL_HX - 0.02), PL_Y(7), sz * (PL_HZ - 0.02)]], false, C.ivory, 0.06, 1, 0.5));
      put('hz', [[-PL_HX - 0.2, PL_Y(7) - 0.26, PL_HZ + 0.2], [PL_HX + 0.2, PL_Y(7) - 0.26, PL_HZ + 0.2]], false, C.ivory, 0.0, 1, 0.9);
    } else if (sc === 3) {
      const pulse = councilPulse(T);
      for (let p = 0; p < 8; p++) {
        const g = GATE_OF_PLATE[p], az = p < 6 ? RINGS[p][2] : 0, y = GATE_Y[g];
        const pts = geo('o3' + p, () => loopAngles(az).map(ph => { const [x, z] = rrHit(ph, GATE_HX, GATE_HZ, 0.04); return [LX + x, y, z]; }));
        put('o' + p, pts, true, C.ivory, (p === 5 || p === 7) ? 0.0 : 0.3, 1, (p + 0.2) / 8.4);
      }
      const apc = pulse.rej ? C.red : C.green, k = pulse.k;
      const ap = geo('ap3', () => loopAngles(0).map(ph => [LX + Math.cos(ph) * AP_R, GATE_Y[COUNCIL], Math.sin(ph) * AP_R]));
      put('bd', ap, true, C.green, 0.55 + 0.4 * k, 1 + 0.6 * k, 0.5);
      put('bdg', ap, true, apc, 0.05 + 0.18 * k, 7, 0.5);
      const ticks = []; for (let j = 0; j < 60; j++) { const a = j / 60 * TAU, r0 = AP_R + 0.03, r1 = AP_R + 0.03 + (j % 5 ? 0.035 : 0.07) * (1 + 0.6 * k); ticks.push([LX + Math.cos(a) * r0, GATE_Y[COUNCIL], Math.sin(a) * r0], [LX + Math.cos(a) * r1, GATE_Y[COUNCIL], Math.sin(a) * r1]); }
      put('apt', ticks, 'pairs', k > 0.02 && pulse.rej ? C.red : C.green, 0.4 + 0.5 * k, 1, 0.5);
      put('hz', [[LX - 0.3, Y_LEDGER, 0], [LEDGER_X0 + LEDGER_DX * (LEDGER_N - 0.2), Y_LEDGER, 0]], false, C.ivory, 0.3, 1, 0.9);
      // hash links: each record points at the one before it
      const recs = ledger(T);
      if (recs.length > 1) {
        const tNew = recs[0] * EMIT + T_REC, sh = sstep(0, 1, (T - tNew) / 0.45), pts = [];
        for (let j = 0; j < Math.min(recs.length, LEDGER_N) - 1; j++) {
          const xa = LEDGER_X0 + (j === 0 ? 0 : j - 1 + sh) * LEDGER_DX, xb = LEDGER_X0 + (j + sh) * LEDGER_DX;
          pts.push([xa + 0.05, Y_LEDGER + 0.045, 0], [xb - 0.05, Y_LEDGER + 0.045, 0]);
        }
        put('hl', pts, 'pairs', C.ivory, 0.5, 1, 0.4);
      }
      put('lane', [[LX, Y_TOP + 0.2, 0], [LX, Y_BOT, 0]], false, C.ivory, 0.05, 1, 0.5);
    } else {
      put('hz', [[-COL_SPAN / 2 - 0.5, Y_FLOOR, 0], [COL_SPAN / 2 + 0.3, Y_FLOOR, 0]], false, C.ivory, 0.42 * (1 - 0.5 * sstep(0.5, 0.8, xNow)), 1, 0.9);
      const hl = []; for (let c = 0; c < NCOL - 1; c++) hl.push([COL_X(c) + 0.06, Y_FLOOR + 0.035, 0.04], [COL_X(c + 1) - 0.06, Y_FLOOR + 0.035, 0.04]);
      put('hl', hl, 'pairs', C.ivory, 0.45, 1, 0.4);
      const tk = []; for (let c = 0; c < NCOL; c++) tk.push([COL_X(c), Y_FLOOR - 0.025, 0], [COL_X(c), Y_FLOOR - 0.06, 0]);
      put('ft', tk, 'pairs', C.ivory, 0.4, 1, 0.6);
    }
    return out;
  }
  const linA = new Map(), linB = new Map();
  let nLine = 0;
  function buildLines() {
    linA.clear(); linB.clear();
    linesFor(seg, simTime, linA); linesFor(seg + 1, simTime, linB);
    const sA = scale[0], sB = scale[1];
    let o = 0; nLine = 0;
    // one hairline set (A alone, B alone, or A morphing into B with t) written segment by segment into the buffer
    const emit = (A, B, t, cr, cg, cb, a, w) => {
      a *= intro;
      if (a < 0.003) return;
      const P = A.pts, Q = B ? B.pts : null, n = P.length, pairs = A.closed === 'pairs';
      const segs = pairs ? n >> 1 : (A.closed ? n : n - 1);
      const dA = A.dy, dB = B ? B.dy : 0;
      for (let j = 0; j < segs && nLine < N_LINE_MAX; j++) {
        const i0 = pairs ? 2 * j : j, i1 = pairs ? 2 * j + 1 : (j + 1) % n;
        for (let e = 0; e < 2; e++) {
          const i = e ? i1 : i0, p = P[i], d = o + e * 3;
          if (Q) { const q = Q[i]; lineData[d] = lerp(p[0] * sA, q[0] * sB, t); lineData[d + 1] = lerp((p[1] + dA) * sA, (q[1] + dB) * sB, t); lineData[d + 2] = lerp(p[2] * sA, q[2] * sB, t); }
          else { const s = A.s; lineData[d] = p[0] * s; lineData[d + 1] = (p[1] + dA) * s; lineData[d + 2] = p[2] * s; }
        }
        lineData[o + 6] = cr; lineData[o + 7] = cg; lineData[o + 8] = cb; lineData[o + 9] = a; lineData[o + 10] = w; o += 11; nLine++;
      }
    };
    linA.forEach((A, id) => {
      const B = linB.get(id), t = ease(stag(mRaw, B ? B.key : A.key)), tc = clamp(t, 0, 1);
      A.s = sA;
      if (B && B.pts.length === A.pts.length && B.closed === A.closed) {
        emit(A, B, t, lerp(A.col[0], B.col[0], tc), lerp(A.col[1], B.col[1], tc), lerp(A.col[2], B.col[2], tc), lerp(A.a, B.a, tc), lerp(A.w, B.w, tc));
      } else {
        emit(A, null, 0, A.col[0], A.col[1], A.col[2], A.a * (1 - tc), A.w);
        if (B) { B.s = sB; emit(B, null, 0, B.col[0], B.col[1], B.col[2], B.a * tc, B.w); }
      }
    });
    linB.forEach((B, id) => { if (!linA.has(id)) { const t = clamp(ease(stag(mRaw, B.key)), 0, 1); B.s = sB; emit(B, null, 0, B.col[0], B.col[1], B.col[2], B.a * t, B.w); } });
  }

  /* ================= callouts: DOM labels projected from 3D anchors, leader lines, hover and focus ================= */
  const labelHost = story.querySelector('.story-labels');
  const SVGNS = 'http://www.w3.org/2000/svg';
  const leaders = document.createElementNS(SVGNS, 'svg');
  leaders.setAttribute('class', 'story-leaders'); leaders.setAttribute('aria-hidden', 'true'); leaders.setAttribute('focusable', 'false');
  if (labelHost) labelHost.appendChild(leaders);
  const labels = [];
  // kind: 'list' (a right-hand column with leaders), 'tag' (at its anchor), 'cap' (the scene's figure caption)
  function label(scene, html, opts) {
    const interactive = !!opts.group || opts.group === 0;
    const el = document.createElement(interactive ? 'button' : 'div');
    if (interactive) { el.type = 'button'; el.tabIndex = -1; el.setAttribute('aria-hidden', 'true'); }
    else el.setAttribute('aria-hidden', 'true');
    el.className = 'story-lab ' + (opts.cls || '');
    el.innerHTML = html;
    if (labelHost) labelHost.appendChild(el);
    let path = null;
    if (opts.leader) { path = document.createElementNS(SVGNS, 'path'); path.setAttribute('class', 'story-leader ' + (opts.cls || '')); leaders.appendChild(path); }
    const l = Object.assign({ el, path, scene, on: false, tr: '', d: '', w: 0, h: 0, y: 0 }, opts);
    labels.push(l);
    return l;
  }
  const lab = {};
  if (labelHost) {
    label(0, '<b>Fig. 00</b> The work, worldwide · every point is an agent', { cls: 'cap', kind: 'cap' });
    label(1, '<b>Fig. 01</b> Six lifecycle classes · one infrastructure', { cls: 'cap', kind: 'cap' });
    label(2, '<b>Fig. 02</b> Eight layers, read top to bottom · one boundary', { cls: 'cap', kind: 'cap' });
    label(3, '<b>Fig. 03</b> Six gates · one council · one ledger · illustrative', { cls: 'cap', kind: 'cap' });
    label(4, `<b>Fig. 04</b> ${REC.lifecycle} · ${NCOL} sessions · heights not to scale`, { cls: 'cap', kind: 'cap' });
    // S1: a column of callouts, one per ring, each anchored on the ring's front-right arc
    lab.rings = LC.map((c, k) => label(1, `<span class="k">${c[0]}</span><span class="n">${c[1]}</span><span class="st st-${c[2].toLowerCase()}">${c[2]}</span><span class="dt">${c[3]}: ${c[4]}</span>`,
      { cls: 'ring' + (k === 0 ? ' is-live' : ''), kind: 'list', group: k, leader: true, info: [`${c[0]} · ${c[3]}`, c[2], c[4]], anchor: () => onLoop(RB[k], RINGS[k][0], RINGS[k][2] - 0.95, 0) }));
    label(1, '<span class="n">One infrastructure</span>', { cls: 'note', kind: 'list', leader: true, anchor: () => [0.05, 0, 0], wide: true });
    // S2: the layers, top to bottom, and the boundary between 04 and 05
    lab.layers = LAYERS.map((l, p) => label(2, `<span class="k">${pad2(p + 1)}</span><span class="n">${l[0]}</span><span class="dt">${l[1]} · ${l[2]}</span>`,
      { cls: 'layer' + (p === 3 ? ' is-council' : ''), kind: 'list', group: p, leader: true, info: [`${pad2(p + 1)} · ${l[0]}`, l[1], `${l[2]} · ${p < 4 ? 'above' : 'below'} the boundary`], anchor: () => [PL_HX - 0.03, PL_Y(p) + hovFor(2, p) * 0.07, PL_HZ - 0.03] }));
    label(2, '<span class="n">Boundary</span><span class="dt">Intelligence decides above · execution is deterministic below</span>', { cls: 'bound', kind: 'list', leader: true, anchor: () => [PL_HX * 1.1 - 0.03, 0, PL_HZ * 1.12 - 0.03] });
    // S3: the six gates, then what leaves the lane and what it writes
    GATES.forEach((g, i) => label(3, `<span class="k">${pad2(i + 1)}</span><span class="n">${g}${i === COUNCIL ? ' · council' : ''}</span>`, { cls: 'gate' + (i === COUNCIL ? ' is-council' : ''), kind: 'list', leader: true, anchor: () => [LX + GATE_HX, GATE_Y[i], 0] }));
    label(3, '<i class="lg-r"></i><span class="n">Rejected · falls away</span>', { cls: 'note', kind: 'list', leader: true, wide: true, anchor: () => [LX + 0.74, GATE_Y[COUNCIL] - 0.36, 0] });
    label(3, '<i class="lg-b"></i><span class="n">Records · hash-linked</span>', { cls: 'note', kind: 'list', leader: true, wide: true, anchor: () => [LEDGER_X0 + LEDGER_DX * 3.5, Y_LEDGER + 0.05, 0] });
    // S4: the sessions under their columns (from the data), the floor, the derived summary
    const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    lab.days = SESSIONS.map((s, c) => label(4, `<span class="k">${s.day}</span><span class="rg">${s.regime === 'premium' ? 'P' : 'D'}</span><span class="dt">Day ${s.day} · ${s.regime} · ${esc(valueT(s))} · ${s.confirmed ? 'broker-confirmed' : 'confirmation not stated'}</span>`,
      { cls: 'day' + (s.regime === 'premium' ? ' is-prem' : ''), kind: 'tag', group: c, side: 's', keep: true, info: [`Day ${s.day}`, capw(s.regime), `${s.above ? 'Above' : 'Not above'} the ${FLOOR_T} floor (${esc(valueT(s))}) · ${s.confirmed ? 'confirmed against the broker’s records' : 'confirmation not stated'}`], anchor: () => [COL_X(c), Y_FLOOR - 0.07, 0] }));
    label(4, `${FLOOR_T} floor`, { cls: 'floor', kind: 'tag', wide: true, anchor: () => [-COL_SPAN / 2 - 0.5, Y_FLOOR + 0.02, 0], side: 'ne' });
    label(4, `<b>${N_ABOVE} of ${NCOL}</b> sessions above the ${FLOOR_T} floor<span class="sep"></span><span class="lg-p">${N_PREM} premium</span> · <span class="lg-d">${N_DISC} discount</span><span class="sep"></span><span class="lg-t">${N_CONF === NCOL ? 'every session' : N_CONF + ' of ' + NCOL} broker-confirmed</span>`, { cls: 'sum', kind: 'tag', anchor: () => [COL_SPAN / 2 + 0.06, Y_FLOOR + H_COL + 0.26, 0], side: 'nw' });
  }
  // the inspector: one quiet box that shows the hovered or focused ring, layer or session
  const insp = document.createElement('div');
  insp.className = 'story-insp'; insp.setAttribute('aria-hidden', 'true');
  if (labelHost) labelHost.appendChild(insp);
  let inspFor = null, inspW = 0, inspH = 0;
  const hov = new Float32Array(24), hovT = new Float32Array(24);
  const hovFor = (sc, i) => (hoverScene === sc ? hov[i] : 0);
  let hoverPtr = null, hoverFocus = null, hoverOn = 0, hoverScene = -1;
  function setHover() {
    const h = hoverPtr || hoverFocus;
    hovT.fill(0);
    if (h) hovT[h.idx] = 1;
    hoverScene = h ? h.scene : hoverScene;
    let hot = null;
    labels.forEach(l => {
      if (l.group == null) return;
      const on = !!h && h.scene === l.scene && h.idx === l.group;
      l.el.classList.toggle('is-hot', on); if (l.path) l.path.classList.toggle('is-hot', on);
      if (on) hot = l;
    });
    if (hot && hot.info && hot !== inspFor) {
      const [t, s, d] = hot.info;
      insp.innerHTML = `<b>${t}</b><em>${s}</em> · ${d}`;
      inspW = insp.offsetWidth; inspH = insp.offsetHeight;
    }
    inspFor = hot;
    insp.classList.toggle('is-on', !!hot);
    stage.classList.toggle('is-pointing', !!hoverPtr);
    requestFrame();
  }
  labels.forEach(l => {
    if (l.group == null) return;
    const on = () => { hoverFocus = { scene: l.scene, idx: l.group }; setHover(); };
    const off = () => { hoverFocus = null; setHover(); };
    l.el.addEventListener('focus', on); l.el.addEventListener('blur', off);
    l.el.addEventListener('pointerenter', () => { hoverPtr = { scene: l.scene, idx: l.group }; setHover(); });
    l.el.addEventListener('pointerleave', e => { if (e.pointerType === 'touch') return; hoverPtr = null; setHover(); });
  });
  // a callout shows while its scene is near; on the way out the proof's day tags stay, so the rising paper turns them to ink
  const vis = (sc, keep) => 1 - sstep(0.22, 0.4, Math.abs(sNow - sc)) - (sc === 4 && !keep ? sstep(0.15, 0.55, xNow) : 0);
  let tabScene = -1;
  function placeLabels() {
    if (!labelHost) return;
    const cur = Math.round(sNow), settledScene = Math.abs(sNow - cur) < 0.3 && xNow < 0.4 ? cur : -1;
    if (settledScene !== tabScene) { // only the current scene's callouts are reachable (and announced)
      tabScene = settledScene;
      labels.forEach(l => { if (l.group == null) return; const on = l.scene === tabScene; l.el.tabIndex = on ? 0 : -1; if (on) l.el.removeAttribute('aria-hidden'); else l.el.setAttribute('aria-hidden', 'true'); });
      if (document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('story-lab') && document.activeElement.tabIndex < 0) stage.focus({ preventScroll: true });
    }
    const listCol = [];
    labels.forEach(l => {
      const v = vis(l.scene, l.keep), on = v > 0.5 && !(stacked && l.wide); // portrait screens leave out the secondary notes
      if (on !== l.on) { l.on = on; l.el.classList.toggle('is-on', on); if (l.path) l.path.classList.toggle('is-on', on); }
      if (!on) return;
      if (!l.w) { l.w = l.el.offsetWidth; l.h = l.el.offsetHeight; }
      if (l.kind === 'cap') {
        const L = layouts[l.scene], tr = stacked ? `translate(${(gutter).toFixed(1)}px, ${(L.rect[1] - 2).toFixed(1)}px)` : `translate(${(L.rect[2] + (l.scene === 0 || l.scene === 4 ? 0 : Math.min(ROOM_W[l.scene], W * 0.18)) - l.w).toFixed(1)}px, ${(H - barH - l.h - 6).toFixed(1)}px)`;
        if (tr !== l.tr) l.el.style.transform = l.tr = tr;
        return;
      }
      const sc = layouts[l.scene].s, a = l.anchor();
      const pp = project(a[0] * sc, a[1] * sc, a[2] * sc);
      l.ax = pp.x; l.ay = pp.y;
      if (l.kind === 'list') listCol.push(l);
      else {
        let x = pp.x, y = pp.y;
        const sd = l.side || 'c';
        if (sd.includes('w')) x -= l.w + 8; else if (sd.includes('e')) x += 8; else x -= l.w / 2;
        if (sd.includes('n')) y -= l.h + 6; else if (sd.includes('s')) y += 6; else y -= l.h / 2;
        x = clamp(x, 6, W - l.w - 6);
        l.y = y;
        const tr = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
        if (tr !== l.tr) { l.el.style.transform = l.tr = tr; if (l.ink) l.ink.style.transform = tr; } // its ink copy on the paper sits exactly under it
      }
    });
    if (listCol.length) { // a column of callouts on the right of the structure; spread so they never touch
      listCol.sort((a, b) => a.ay - b.ay);
      const sc = listCol[0].scene, L = layouts[sc];
      const maxW = Math.max(...listCol.map(l => l.w)), colX = stacked ? W - gutter * 0.5 - maxW : Math.min(L.rect[2] + 22, W - gutter * 0.5 - maxW);
      const gap = Math.max(...listCol.map(l => l.h)) + (stacked ? 2 : 6), top = navH + (stacked ? barH : 0) + 14, bottom = (stacked ? beatRects[sc].t - 10 : H - barH - 26);
      let y = -1e9;
      listCol.forEach(l => { l.y = Math.max(l.ay - l.h / 2, y + gap); y = l.y; });
      const over = y + listCol[listCol.length - 1].h - bottom;
      if (over > 0) { listCol.forEach(l => { l.y -= over; }); }
      for (let j = 1; j < listCol.length; j++) if (listCol[j].y < listCol[j - 1].y + gap) listCol[j].y = listCol[j - 1].y + gap;
      if (listCol[0].y < top) { const d = top - listCol[0].y; listCol.forEach(l => { l.y += d; }); }
      listCol.forEach(l => {
        const tr = `translate(${colX.toFixed(1)}px, ${l.y.toFixed(1)}px)`;
        if (tr !== l.tr) l.el.style.transform = l.tr = tr;
        if (l.path) {
          const ly = l.y + l.h / 2, ex = colX - 6;
          const d = `M${l.ax.toFixed(1)} ${l.ay.toFixed(1)} L${(ex - 14).toFixed(1)} ${ly.toFixed(1)} L${ex.toFixed(1)} ${ly.toFixed(1)}`;
          if (d !== l.d) l.path.setAttribute('d', l.d = d);
        }
      });
      listX = colX; listBottom = listCol[listCol.length - 1].y + listCol[listCol.length - 1].h;
    }
    const io = !!inspFor && inspFor.on;
    insp.classList.toggle('is-on', io);
    if (io) {
      let x, y;
      if (stacked) { x = gutter * 0.5; y = navH + barH + 8; }
      else if (inspFor.kind === 'list') { x = listX; y = listBottom + 18; }
      else { const sc = layouts[inspFor.scene].s, p = project(COL_X(inspFor.group) * sc, (Y_FLOOR + H_COL + 0.24) * sc, 0); x = p.x - inspW / 2; y = p.y - inspH - 12; }
      x = clamp(x, 8, W - inspW - 8); y = clamp(y, navH + 8, H - inspH - 8);
      const tr = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      if (tr !== inspTr) insp.style.transform = inspTr = tr;
    }
  }
  let listX = 0, listBottom = 0, inspTr = '';
  function hitTest(px, py) { // which ring, layer or session the pointer is over (current scene only, settled)
    const cur = Math.round(sNow);
    if (Math.abs(sNow - cur) > 0.25 || xNow > 0.3) return null;
    const sc = layouts[cur].s;
    if (cur === 1) {
      let best = null, bd = 16;
      for (let k = 0; k < 6; k++) {
        let prev = null;
        for (let j = 0; j <= 48; j++) {
          const q = onLoop(RB[k], RINGS[k][0], j / 48 * TAU, 0), p = project(q[0] * sc, q[1] * sc, q[2] * sc), cur2 = [p.x, p.y];
          if (prev) { const d = segDist(px, py, prev[0], prev[1], cur2[0], cur2[1]); if (d < bd) { bd = d; best = k; } }
          prev = cur2;
        }
      }
      return best == null ? null : { scene: 1, idx: best };
    }
    if (cur === 2) {
      for (let p = 0; p < 8; p++) {
        const y = PL_Y(p) + hov[p] * 0.07, q = [[PL_HX, PL_HZ], [PL_HX, -PL_HZ], [-PL_HX, -PL_HZ], [-PL_HX, PL_HZ]].map(([x, z]) => { const r = project(x * sc, y * sc, z * sc); return [r.x, r.y]; });
        if (inQuad(px, py, q)) return { scene: 2, idx: p };
      }
      return null;
    }
    if (cur === 4) {
      for (let c = 0; c < NCOL; c++) {
        const a = project((COL_X(c) - 0.1) * sc, Y_FLOOR * sc, 0), ax = a.x, ay = a.y; // project() reuses one object: copy before the next call
        const b = project((COL_X(c) + 0.1) * sc, (Y_FLOOR + H_COL + 0.15) * sc, 0);
        if (px > ax && px < b.x && py < ay + 24 && py > b.y) return { scene: 4, idx: c };
      }
    }
    return null;
  }
  const segDist = (px, py, ax, ay, bx, by) => { const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1, t = clamp(((px - ax) * dx + (py - ay) * dy) / l2, 0, 1); return Math.hypot(px - ax - dx * t, py - ay - dy * t); };
  const inQuad = (px, py, q) => { let s = 0; for (let i = 0; i < 4; i++) { const [ax, ay] = q[i], [bx, by] = q[(i + 1) % 4], c = (bx - ax) * (py - ay) - (by - ay) * (px - ax); if (c !== 0) { if (s && Math.sign(c) !== s) return false; s = Math.sign(c); } } return true; };

  /* ================= the copy, the index, the motion control ================= */
  const beats = Array.from(story.querySelectorAll('.beat'));
  const idx = Array.from(story.querySelectorAll('.story-idx button'));
  const motionButton = story.querySelector('[data-story-motion]');
  const live = story.querySelector('[data-story-live]');
  const bar = story.querySelector('.story-bar');
  // the chapter mark: two stacked lines (this scene, the next) for the numeral and for the name, rolled like a counter
  const num = story.querySelector('.story-num');
  const numRows = num ? ['b', 'span'].map(t => { const el = num.querySelector(t); el.textContent = ''; return [0, 1].map(() => el.appendChild(document.createElement('i'))); }) : null;
  let shownNum = -1, shownNumOp = '', shownNumTr = '', shownRoll = '';
  const paper = story.querySelector('.story-paper');
  const paperIn = paper && paper.querySelector('.story-paper-in'), paperCap = paperIn && paperIn.querySelector('.container');
  // the paper's copy of the proof's day tags, in ink: the rising edge uncovers each one exactly where its tag stood
  if (paperIn && lab.days) {
    const ink = document.createElement('div');
    ink.className = 'story-ink';
    lab.days.forEach(l => { const e = document.createElement('div'); e.className = l.el.className; e.innerHTML = l.el.innerHTML; ink.appendChild(e); l.ink = e; });
    paperIn.insertBefore(ink, paperIn.firstChild);
  }
  let shownCap = '', shownLeaving = null;
  const paperSum = story.querySelector('[data-story-sum]');
  if (paperSum) paperSum.textContent = `${N_ABOVE} of ${NCOL} above the ${FLOOR_T} floor · ${N_PREM} premium · ${N_DISC} discount · ${N_CONF === NCOL ? 'every session' : N_CONF + ' of ' + NCOL} broker-confirmed`;
  const shown = beats.map(() => ({ op: '', tr: '', on: null }));
  const beatLinks = beats.map(b => Array.from(b.querySelectorAll('a[href], button')));
  let shownIdx = -1, shownScrolled = null, shownBar = '', shownPaper = '', shownXo = '', shownFill = [];
  let paperH = 0;
  // the index follows the scroll position itself: immediate, and right even when frames are slow or throttled
  function syncIndex() {
    const ci = clamp(Math.round(sTarget), 0, 4);
    if (shownIdx === ci) return;
    shownIdx = ci;
    idx.forEach((button, i) => { const a = ci === i; button.classList.toggle('is-on', a); if (a) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current'); });
    beatLinks.forEach((list, i) => list.forEach(el => { if (i === ci) el.removeAttribute('tabindex'); else el.setAttribute('tabindex', '-1'); }));
    story.dataset.scene = String(ci);
  }
  function updateUI() {
    const red = reducedMQ.matches, xe = red ? (xNow > 0.5 ? 1 : 0) : xNow;
    const ov = Math.max(0, scrollY - storyTop - run); // past the pin the stage leaves with the page
    // the hand-off: the paper rises from the bottom edge to the ledger's floor line, which becomes its edge
    paperH = 0;
    if (xe > 0 && seg === 3) paperH = Math.max(0, H - project(0, Y_FLOOR * layouts[4].s, 0).y - 1) * sstep(0.16, 0.8, xe);
    if (paper) { const v = paperH.toFixed(1); if (v !== shownPaper) { shownPaper = v; paper.style.height = v + 'px'; paper.style.visibility = paperH > 0.5 ? 'visible' : 'hidden'; } }
    beats.forEach((b, i) => {
      const d = Math.abs(sNow - i);
      let op = red ? (Math.round(sNow) === i ? 1 : 0) : 1 - sstep(stacked ? 0.42 : 0.38, 0.5, d); // each scene's copy holds for 76-84% of the scroll (reduced motion: it snaps with the scene)
      let dy = red ? 0 : (sNow - i) * -24;
      if (i === 4 && xe > 0) { // the headline stays above the paper when it fits; the rest gives way to it
        const br = beatRects[4] || { ht: 0, hb: 0 }, edge = H - paperH - 26, shift = Math.min(0, edge - br.hb);
        if (!stacked && br.ht + shift >= navH + 14) dy += shift; else op *= 1 - sstep(0.03, 0.3, xe);
        const xo = (1 - sstep(0.04, 0.3, xe)).toFixed(3);
        if (xo !== shownXo) b.style.setProperty('--xo', shownXo = xo);
      }
      if (i === 4 && ov > 0) { // as the stage scrolls away the copy finishes leaving before it reaches the nav's lower edge
        const room0 = (beatRects[4] ? beatRects[4].t : 0) + dy - navH; // the room left above it when the stage starts to move
        const k = room0 <= 6 ? 0 : 1 - sstep(Math.max(0, room0 - 6 - Math.min(150, H * 0.2)), room0 - 6, ov);
        op *= k; if (!red) dy -= (1 - k) * 14;
      }
      const s = shown[i], o = op.toFixed(3), tr = `translate3d(0, ${dy.toFixed(1)}px, 0)`;
      if (s.op !== o) b.style.opacity = s.op = o;
      if (s.tr !== tr) b.style.transform = s.tr = tr;
      if (s.on !== op > 0.5) b.classList.toggle('is-active', s.on = op > 0.5);
    });
    syncIndex();
    idx.forEach((button, i) => { const f = clamp(sNow - i + 0.5, 0, 1).toFixed(2); if (shownFill[i] !== f) button.style.setProperty('--fill', shownFill[i] = f); });
    if (shownScrolled !== sNow > 0.3) story.classList.toggle('is-scrolled', shownScrolled = sNow > 0.3);
    // between two scenes, while the copy hands over, the scene numeral holds the column and rolls from this scene to the next
    // (a chapter mark, never an empty frame; reduced motion: the copy snaps, nothing to bridge)
    if (num) {
      const a = Math.min(3, Math.floor(sNow)), f = sNow - a;
      const fit = numFit[a], op = red || stacked || !fit || sNow >= 4 || xNow > 0 ? 0 : 1 - sstep(0.06, 0.15, Math.abs(f - 0.5));
      if (a !== shownNum) { shownNum = a; numRows[0][0].textContent = pad2(a); numRows[0][1].textContent = pad2(a + 1); numRows[1][0].textContent = SCENES[a]; numRows[1][1].textContent = SCENES[a + 1]; }
      const v = op.toFixed(3), tr = red ? 'none' : `translate3d(0, ${((0.5 - f) * 24).toFixed(1)}px, 0) scale(${fit.toFixed(3)})`, roll = sstep(0.43, 0.57, f).toFixed(3);
      if (v !== shownNumOp) { num.style.opacity = shownNumOp = v; }
      if (tr !== shownNumTr) { num.style.transform = shownNumTr = tr; }
      if (roll !== shownRoll) num.style.setProperty('--roll', shownRoll = roll);
    }
    const bo = (1 - sstep(0.08, 0.3, xe)).toFixed(3);
    if (bar && bo !== shownBar) { bar.style.opacity = shownBar = bo; bar.style.visibility = bo < 0.01 ? 'hidden' : ''; }
    if (shownLeaving !== xe > 0.05) story.classList.toggle('is-leaving', shownLeaving = xe > 0.05); // the covered tags take no pointer
    placeLabels();
    // the paper's caption sits under the ink tags (stage coordinates: the paper uncovers it, it does not carry it)
    if (paperCap && paperH > 0.5) {
      let yb = 0;
      if (lab.days) lab.days.forEach(l => { if (l.on && l.h) yb = Math.max(yb, l.y + l.h); });
      if (!yb) yb = H - paperH + 30;
      const cap = `translate3d(0, ${Math.round(yb + 16)}px, 0)`;
      if (cap !== shownCap) paperCap.style.transform = shownCap = cap;
    }
  }

  /* ================= the frame ================= */
  let running = true, visible = true, paused = false, frameId = 0, t0 = performance.now(), simTime = 14.3, settledOnce = false, pointerDirty = false, ptr = null, firstFrame = -1;
  const PIXEL_BUDGET = 3840 * 2160;
  function resize(force) {
    if (lost || !ready) return;
    measure();
    const w = stage.clientWidth, h = stage.clientHeight, r = window.devicePixelRatio || 1;
    if (force === true || w !== W || h !== H || r !== ratio || stackedMQ.matches !== stacked) {
      W = w; H = h; ratio = r;
      dpr = Math.min(3, r, Math.sqrt(PIXEL_BUDGET / Math.max(1, W * H)));
      cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr);
      gl.viewport(0, 0, cv.width, cv.height);
      if (paperIn) paperIn.style.height = H + 'px'; // the paper's contents live in the stage's frame
      leaders.setAttribute('viewBox', `0 0 ${W} ${H}`);
      labels.forEach(l => { l.w = 0; l.tr = ''; });
    }
    fitScenes();
    sceneScroll();
    requestFrame();
  }
  function drawBulk(halo) {
    const pr = P.bulk, u = pr.u;
    gl.useProgram(pr.prog);
    const from = seg, to = seg + 1;
    const attr = (name, b) => { const loc = pr.a[name]; if (loc < 0) return; gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 0, 0); if (ext) ext.vertexAttribDivisorANGLE(loc, 0); };
    attr('a_from', BUF.scene[from]); attr('a_to', BUF.scene[to]); attr('a_rand', BUF.rand); attr('a_key', BUF.key);
    gl.uniformMatrix4fv(u.u_view, false, view); gl.uniformMatrix4fv(u.u_proj, false, proj);
    gl.uniform1f(u.u_time, time); gl.uniform1f(u.u_m, mRaw); gl.uniform1f(u.u_keyIdx, seg); gl.uniform1f(u.u_spread, SPREADS[seg]);
    gl.uniform1f(u.u_swirl, SWIRL[seg]); gl.uniform1f(u.u_lift, LIFT[seg]); gl.uniform3fv(u.u_liftDir, LIFT_DIR[seg]);
    gl.uniform1f(u.u_sA, scale[0]); gl.uniform1f(u.u_sB, scale[1]);
    gl.uniform1f(u.u_spin, time * 0.07 + 0.6);
    gl.uniform1f(u.u_pr, dpr); gl.uniform1f(u.u_dist, CAM_D); gl.uniform1f(u.u_fogR, 1.7 * Math.max(scale[0], scale[1]));
    gl.uniform1f(u.u_maxpt, maxPt); gl.uniform1f(u.u_intro, intro); gl.uniform1f(u.u_halo, halo ? 1 : 0);
    gl.uniform1f(u.u_shade, lerp(SHADE[seg], SHADE[seg + 1], mE));
    gl.uniform1fv(u.u_hov, hov); gl.uniform1f(u.u_hovOn, hoverOn); gl.uniform1f(u.u_hovScene, hoverScene);
    gl.uniform1f(u.u_sceneA, seg); gl.uniform1f(u.u_sceneB, seg + 1);
    gl.uniform1f(u.u_hovLift, reducedMQ.matches ? 0 : 0.07 * scale[hoverScene === seg ? 0 : 1] * (hoverScene === 2 ? 1 : 0));
    const occ = seg === 0 ? (1 - sstep(0, 0.55, mRaw)) : 0;
    gl.uniform4f(u.u_occ, 0, 0, 0, occ * scale[0] * 0.995);
    gl.blendFunc(gl.ONE, gl.ONE);
    gl.drawArrays(gl.POINTS, 0, N);
  }
  function drawLines() {
    if (!nLine) return;
    const pr = P.line, u = pr.u;
    gl.useProgram(pr.prog);
    gl.uniformMatrix4fv(u.u_view, false, view); gl.uniformMatrix4fv(u.u_proj, false, proj);
    gl.uniform2f(u.u_res, cv.width, cv.height); gl.uniform1f(u.u_pr, dpr); gl.uniform1f(u.u_dist, CAM_D); gl.uniform1f(u.u_fogR, 1.7 * Math.max(scale[0], scale[1]));
    const occ = seg === 0 ? (1 - sstep(0, 0.55, mRaw)) : 0;
    gl.uniform4f(u.u_occ, 0, 0, 0, occ * scale[0] * 0.995);
    gl.bindBuffer(gl.ARRAY_BUFFER, BUF.line); gl.bufferSubData(gl.ARRAY_BUFFER, 0, lineData.subarray(0, nLine * 11));
    const st = 44;
    const inst = (name, size, off) => { const loc = pr.a[name]; if (loc < 0) return; gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, st, off); ext.vertexAttribDivisorANGLE(loc, 1); };
    inst('a_p0', 3, 0); inst('a_p1', 3, 12); inst('a_col', 4, 24); inst('a_w', 1, 40);
    gl.bindBuffer(gl.ARRAY_BUFFER, BUF.corner);
    const lc = pr.a.a_corner; gl.enableVertexAttribArray(lc); gl.vertexAttribPointer(lc, 2, gl.FLOAT, false, 0, 0); ext.vertexAttribDivisorANGLE(lc, 0);
    gl.blendFunc(gl.ONE, gl.ONE);
    ext.drawArraysInstancedANGLE(gl.TRIANGLE_STRIP, 0, 4, nLine);
    ['a_p0', 'a_p1', 'a_col', 'a_w'].forEach(n => { const loc = pr.a[n]; if (loc >= 0) { ext.vertexAttribDivisorANGLE(loc, 0); gl.disableVertexAttribArray(loc); } });
  }
  function drawActors(halo) {
    if (!nAct) return;
    const pr = P.act, u = pr.u;
    gl.useProgram(pr.prog);
    gl.uniformMatrix4fv(u.u_view, false, view); gl.uniformMatrix4fv(u.u_proj, false, proj);
    gl.uniform1f(u.u_pr, dpr); gl.uniform1f(u.u_dist, CAM_D); gl.uniform1f(u.u_fogR, 1.7 * Math.max(scale[0], scale[1])); gl.uniform1f(u.u_maxpt, maxPt); gl.uniform1f(u.u_halo, halo ? 1 : 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, BUF.act);
    if (!halo) gl.bufferSubData(gl.ARRAY_BUFFER, 0, actData.subarray(0, nAct * 11));
    const st = 44;
    const at = (name, size, off) => { const loc = pr.a[name]; if (loc < 0) return; gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, st, off); if (ext) ext.vertexAttribDivisorANGLE(loc, 0); };
    at('a_pos', 3, 0); at('a_col', 4, 12); at('a_shp', 4, 28);
    if (halo) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.POINTS, 0, nAct);
  }
  // attributes are shared state: switching programs must not leave another program's arrays enabled past their buffers
  let nAttribs = 0;
  function resetAttribs() { if (!nAttribs) nAttribs = Math.min(16, gl.getParameter(gl.MAX_VERTEX_ATTRIBS)); for (let i = 0; i < nAttribs; i++) gl.disableVertexAttribArray(i); }

  function frame(now, initial) {
    frameId = 0;
    if (!running || lost || !ready) return;
    const raw = Math.max(0, (now - t0) / 1000), dt = Math.min(0.05, raw); t0 = now;
    const dtS = Math.min(0.25, raw); // the scroll's weight runs on real time, so throttled frames never leave the scenes lagging
    if (!((visible && !document.hidden) || initial)) return;
    const red = reducedMQ.matches, moving = !red && !paused;
    if (moving) { time += dt; simTime += dt; mouse.x += (mouse.tx - mouse.x) * (1 - Math.exp(-dt * 3)); mouse.y += (mouse.ty - mouse.y) * (1 - Math.exp(-dt * 3)); }
    // the intro: when the loader lifts, the globe draws in from the top band down
    if (firstFrame < 0) firstFrame = now;
    if (introStart < 0 && (!document.body.classList.contains('is-loading') || now - firstFrame > 2400)) introStart = now; // never wait on a slow loader
    intro = red || introStart < 0 ? (introStart < 0 ? 0 : 1) : clamp((now - introStart) / 1100, 0, 1);
    if (red && introStart >= 0) intro = 1;
    // scroll with a little weight: the instrument follows, it does not snap (reduced motion: it does)
    if (red || !settledOnce) { sNow = sTarget; xNow = xTarget; settledOnce = true; }
    else { const k = 1 - Math.exp(-dtS * 6.5); sNow += (sTarget - sNow) * k; xNow += (xTarget - xNow) * k; if (Math.abs(sTarget - sNow) < 0.0004) sNow = sTarget; if (Math.abs(xTarget - xNow) < 0.0004) xNow = xTarget; }
    morphState();
    camera();
    if (pointerDirty) {
      pointerDirty = false;
      const h = ptr ? hitTest(ptr.x, ptr.y) : null;
      const same = (a, b) => (!a && !b) || (a && b && a.scene === b.scene && a.idx === b.idx);
      if (!same(h, hoverPtr) && !(ptr && ptr.onLabel)) { hoverPtr = h; setHover(); }
    }
    const kh = 1 - Math.exp(-dtS * (red ? 60 : 12));
    let hmax = 0;
    for (let i = 0; i < hov.length; i++) { hov[i] += (hovT[i] - hov[i]) * kh; if (Math.abs(hovT[i] - hov[i]) < 0.002) hov[i] = hovT[i]; hmax = Math.max(hmax, hov[i]); }
    hoverOn = hmax;
    buildLines(); buildActors();
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    resetAttribs();
    if (ext) drawLines();
    resetAttribs();
    drawBulk(true); drawBulk(false);
    resetAttribs();
    drawActors(false); drawActors(true);
    updateUI();
    const busy = moving || Math.abs(sTarget - sNow) > 0.0004 || Math.abs(xTarget - xNow) > 0.0004 || hov.some((v, i) => Math.abs(v - hovT[i]) > 0.002) || (intro < 1 && introStart >= 0) || introStart < 0;
    if (busy) requestFrame();
  }
  function requestFrame() { if (!frameId && running && !lost && ready && visible && !document.hidden) frameId = requestAnimationFrame(frame); }
  function stopFrames() { cancelAnimationFrame(frameId); frameId = 0; t0 = performance.now(); }
  function updateMotion() {
    if (!motionButton) return;
    motionButton.hidden = reducedMQ.matches;
    motionButton.textContent = paused ? 'Resume motion' : 'Pause motion'; // the label itself toggles (no aria-pressed)
  }

  /* ================= navigation: index, keys, focus ================= */
  const sceneTop = (i) => storyTop + run * (i / TOTAL_U);
  let lastGo = { i: -1, t: 0 };
  function goTo(i, announce) {
    i = clamp(i, 0, 4);
    measure();
    lastGo = { i, t: performance.now() };
    window.scrollTo({ top: Math.round(sceneTop(i)), behavior: reducedMQ.matches ? 'instant' : 'smooth' });
    if (announce && live) live.textContent = `Scene ${i + 1} of 5: ${SCENES[i]}`;
  }
  function onKey(e) {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    const d = e.key === 'ArrowRight' || e.key === 'PageDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'PageUp' ? -1 : 0;
    if (!d) return;
    measure();
    if (window.scrollY < storyTop - 4 || window.scrollY > storyTop + run + 4) return; // past the overture the keys scroll the page as usual
    const base = performance.now() - lastGo.t < 1200 ? lastGo.i : clamp(Math.round(sTarget + (xTarget > 0 ? 0.5 : 0)), 0, 4);
    if (d > 0 && base >= 4) { // past the last scene: through the hand-off to the first paper chapter
      e.preventDefault();
      const next = document.querySelector('.story ~ section[id], .story ~ * section[id]');
      const top = next ? next.getBoundingClientRect().top + window.scrollY : storyTop + story.offsetHeight;
      window.scrollTo({ top: Math.round(top), behavior: reducedMQ.matches ? 'instant' : 'smooth' });
      lastGo = { i: 5, t: performance.now() };
      return;
    }
    if (d < 0 && base <= 0) return;
    e.preventDefault();
    goTo(base + d, true);
  }

  // WebGL failed to start (or to come back): stop, clear what the loop wrote, hand over to the static beats
  function fail(err) {
    if (err) console.error(err);
    running = false; stopFrames();
    beats.forEach(b => { b.style.opacity = b.style.transform = b.style.visibility = ''; b.classList.remove('is-active'); });
    beatLinks.forEach(list => list.forEach(el => el.removeAttribute('tabindex')));
    labels.forEach(l => l.el.remove()); leaders.remove();
    if (bar) bar.style.opacity = bar.style.visibility = '';
    if (paper) paper.style.height = paper.style.visibility = '';
    if (motionButton) motionButton.hidden = true;
    insp.remove();
    stage.removeAttribute('tabindex'); stage.removeAttribute('aria-describedby');
    fallback();
  }
  let wired = false;
  function begin() {
    if (!wired) {
      wired = true;
      stage.tabIndex = 0; // the stage takes focus: arrow keys and Page Up / Page Down step the scenes
      if (document.getElementById('story-keys')) stage.setAttribute('aria-describedby', 'story-keys');
      idx.forEach((button, i) => button.addEventListener('click', () => goTo(i, true)));
      stage.addEventListener('keydown', onKey);
      // every beat stays in the accessibility tree; keyboard focus entering one brings the story to it
      beats.forEach((b, i) => b.addEventListener('focusin', () => { if (running && Math.abs(sTarget - i) > 0.45) goTo(i); }));
      if (motionButton) motionButton.addEventListener('click', () => { paused = !paused; updateMotion(); requestFrame(); });
      reducedMQ.addEventListener('change', () => { mouse.x = mouse.y = mouse.tx = mouse.ty = 0; updateMotion(); requestFrame(); });
      window.addEventListener('resize', () => resize());
      stackedMQ.addEventListener('change', () => resize(true));
      (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
      window.addEventListener('scroll', () => { scrollY = window.scrollY; sceneScroll(); syncIndex(); requestFrame(); }, { passive: true });
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => resize(true));
      window.addEventListener('load', () => resize(true), { once: true });
      stage.addEventListener('pointermove', e => {
        const r = stage.getBoundingClientRect();
        const onCopy = !!(e.target.closest && e.target.closest('.beat-text, .hero-stats, .story-bar'));
        ptr = onCopy ? null : { x: e.clientX - r.left, y: e.clientY - r.top, onLabel: !!(e.target.closest && e.target.closest('.story-lab')) };
        pointerDirty = true;
        if (!reducedMQ.matches && !paused && e.pointerType !== 'touch') { mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2; mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2; }
        requestFrame();
      }, { passive: true });
      stage.addEventListener('pointerleave', e => { if (e.pointerType === 'touch') return; ptr = null; pointerDirty = true; mouse.tx = mouse.ty = 0; requestFrame(); }); // a tap's highlight stays until the next tap
      stage.addEventListener('pointerdown', e => { // touch: a tap shows what is under the finger
        if (e.pointerType !== 'touch') return;
        const r = stage.getBoundingClientRect();
        ptr = { x: e.clientX - r.left, y: e.clientY - r.top }; pointerDirty = true; requestFrame();
      }, { passive: true });
      if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) requestFrame(); else stopFrames(); }, { threshold: 0 }).observe(story);
      document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
    }
    resize(true);
    updateMotion();
    stopFrames();
    frame(performance.now(), true);
    root.classList.add('gl-ready'); document.dispatchEvent(new Event('story:gl-ready')); // the loader waits for this (capped)
  }
  function start() {
    try { gl = cv.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: true, powerPreference: 'high-performance' }); } catch (e) { gl = null; }
    if (!gl) { fail(); return; }
    cv.addEventListener('webglcontextlost', e => { e.preventDefault(); lost = true; ready = false; stopFrames(); });
    cv.addEventListener('webglcontextrestored', () => { lost = false; if (running) setupGL(begin); });
    setupGL(begin);
  }
  start();
})();
