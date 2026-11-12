/* OpenEXA — the overture (Home): five scenes, signal → record, on one WebGL canvas (home group). */
(function () {
  'use strict';
  const story = document.querySelector('.story');
  if (!story) return;
  const root = document.documentElement;

  const pad2 = (n) => String(n).padStart(2, '0');
  const NUMW = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(' ');
  const words = (n) => NUMW[n] || String(n), capw = (s) => s.charAt(0).toUpperCase() + s.slice(1);
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
          value, above: !!m && (m[1] === '>' ? amount >= floor : amount > floor),
          confirmed: /confirm/i.test(conf) && !/pending|awaiting|unconfirm|^not\b/i.test(conf),
        };
      });
      if (!sessions.every(s => s.regime)) return null;
      return { lifecycle: str(j.lifecycle) || TABLE.lifecycle, unit: str(j.unit) || 'bps', floor, sessions };
    };
    try { const el = document.getElementById('oxa-sessions'); const r = el && read(JSON.parse(el.textContent)); if (r) return r; } catch (e) { }
    return read(TABLE);
  })();
  const SESSIONS = REC.sessions, NCOL = SESSIONS.length, FLOOR = REC.floor, UNIT = REC.unit, FLOOR_T = `${FLOOR} ${UNIT}`;
  const count = (f) => SESSIONS.filter(f).length;
  const N_PREM = count(s => s.regime === 'premium'), N_DISC = NCOL - N_PREM, N_ABOVE = count(s => s.above), N_CONF = count(s => s.confirmed);
  const valueT = (s) => s.value ? `${s.value} ${UNIT}` : 'value not stated';
  const derive = (k, as) => {
    if (k === 'every') return N_ABOVE === NCOL ? 'every one of ' + words(NCOL) : words(N_ABOVE) + ' of ' + words(NCOL);
    if (k === 'lifecycle') return REC.lifecycle;
    if (k === 'tally') return `${capw(words(N_ABOVE))} for ${words(NCOL)}.`;
    const n = { total: NCOL, above: N_ABOVE, premium: N_PREM, discount: N_DISC, floor: FLOOR, confirmed: N_CONF }[k];
    return n == null ? null : as === 'words' ? words(n) : as === 'Words' ? capw(words(n)) : String(n);
  };
  story.querySelectorAll('[data-story-n]').forEach(el => { const t = derive(el.dataset.storyN, el.dataset.storyAs); if (t != null && el.textContent !== t) el.textContent = t; });

  const stage = story.querySelector('.story-stage');
  const cv = story.querySelector('canvas.story-gl');
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  const coarseMQ = window.matchMedia('(pointer: coarse)');
  const fallback = () => { root.classList.remove('story-ready', 'gl-ready'); root.classList.add('no-webgl'); story.setAttribute('data-settled', ''); document.dispatchEvent(new Event('story:no-webgl')); };
  if (!cv || !stage || !window.WebGLRenderingContext) { fallback(); return; }
  root.classList.add('story-ready');
  const stackedMQ = window.matchMedia('(max-width: 639.98px), (max-aspect-ratio: 23/20)');
  const LITE = stackedMQ.matches || Math.min(window.innerWidth, window.innerHeight) < 640;

  const SCENES = ['Infrastructure', 'The work', 'The stack', 'The swarm', 'The proof'];
  const LC = [
    ['LC-01', 'Financial markets', 'Live', 'Financial markets & insurance', 'ETF creation and redemption, in production on live capital'],
    ['LC-02', 'Trade finance', 'Next', 'International trade · letters of credit', 'Issuance, document checks, discrepancies and payment'],
    ['LC-03', 'Securitization', 'Next', 'Asset securitization · MBS / ABS', 'Pool assembly, tranche compliance, investor distributions'],
    ['LC-04', 'Energy settlement', 'Roadmap', 'Wholesale energy settlement', 'Metering, scheduling, imbalance, multi-party settlement'],
    ['LC-05', 'Semiconductors', 'Roadmap', 'Semiconductor manufacturing', 'Order to wafer across foundries, packaging and logistics'],
    ['LC-06', 'Pharma & aerospace', 'Roadmap', 'Pharmaceutical & aerospace', 'Qualification, batch release, full traceability'],
  ];
  const LAYERS = [
    ['Signal intelligence', 'Perceive', 'Risk, price and regime models'], ['Model layer', 'Reason', 'A post-trained LLM on the domain'],
    ['Domain-specific agents', 'Act', 'One narrow job each'], ['Execution Council', 'Govern', 'Approve or reject, by policy'],
    ['Routing layer', 'Optimize', 'The cheapest, fastest, safest path'], ['Execution layer', 'Orchestrate', 'Deterministic order state'],
    ['MCP server', 'Connect', 'Authenticated tools and adapters'], ['Authentication layer', 'Permit', 'Scoped, revocable permissions'],
  ];
  const GATES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];

  const TAU = Math.PI * 2, PI = Math.PI;
  const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
  const lerp = (a, b, t) => a + (b - a) * t;
  const sstep = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const C1 = 0.8, C3 = C1 + 1;
  const ease = (t) => { const s = t * t * (3 - 2 * t), u = s - 1; return 1 + C3 * u * u * u + C1 * u * u; };
  const stag = (m, key) => { const sp = SPREADS[seg] || 0.42; return clamp((m - key * sp) / (1 - sp), 0, 1); };
  const HOLD = 0.3, LEAN = 0.03, SPREADS = [0.6, 0.46, 0.42, 0.5];
  const nearScene = (s) => clamp(Math.floor(s + 0.5 + LEAN), 0, 4);
  const easeMove = (t) => { let u = t; for (let k = 0; k < 6; k++) { const w = 1 - u, f = 1.86 * u * w * w + 0.6 * u * u * w + u * u * u - t, d = 1.86 * w * w - 2.52 * u * w + 2.4 * u * u; if (Math.abs(d) < 1e-6) break; u = clamp(u - f / d, 0, 1); } return 3 * u * u * (1 - u) + u * u * u; };
  let EXIT_U = window.innerWidth < 600 ? 0.6 : 0.9, TOTAL_U = 4 + EXIT_U;

  const ORBITS = [[1.24, 0.40, 0.35, 0.15], [1.31, -0.30, 1.40, -0.11], [1.38, 0.60, 2.20, 0.09], [1.46, -0.52, 3.05, -0.13], [1.54, 0.24, 4.10, 0.08], [1.62, -0.70, 5.20, -0.07]];
  const RINGS = [[0.52, 0.155, 0.35, 0.30], [0.735, -0.133, 1.40, 0.12], [0.95, 0.196, 2.20, 0.09], [1.165, -0.179, 3.05, 0], [1.38, 0.12, 4.10, 0], [1.595, -0.22, 5.20, 0]];
  function basis(tilt, az) {
    const sa = Math.sin(tilt), ca = Math.cos(tilt), sb = Math.sin(az), cb = Math.cos(az);
    return { U: [cb, 0, sb], V: [ca * sb, sa, -ca * cb], N: [-sb * sa, ca, cb * sa] };
  }
  const OB = ORBITS.map(o => basis(o[1], o[2])), RB = RINGS.map(o => basis(o[1], o[2]));
  const KH_ORB = 3;
  const onLoop = (b, r, th, lift) => [(b.U[0] * Math.cos(th) + b.V[0] * Math.sin(th)) * r + b.N[0] * lift, (b.U[1] * Math.cos(th) + b.V[1] * Math.sin(th)) * r + b.N[1] * lift, (b.U[2] * Math.cos(th) + b.V[2] * Math.sin(th)) * r + b.N[2] * lift];
  const RING_OF_BAND = [4, 2, 0, 1, 3, 5];
  const PL_Y = (p) => 0.84 - 0.24 * p, PL_HX = 0.86, PL_HZ = 0.54, PL_RC = 0.07;
  function rrHit(phi, hx, hz, rc) {
    const dx = Math.cos(phi), dz = Math.sin(phi);
    let t = Math.min(hx / Math.max(1e-6, Math.abs(dx)), hz / Math.max(1e-6, Math.abs(dz)));
    const x = dx * t, z = dz * t;
    if (Math.abs(x) > hx - rc && Math.abs(z) > hz - rc) {
      const cx = Math.sign(dx) * (hx - rc), cz = Math.sign(dz) * (hz - rc), dc = dx * cx + dz * cz;
      t = dc + Math.sqrt(Math.max(0, dc * dc - (cx * cx + cz * cz) + rc * rc));
    }
    return [dx * t, dz * t];
  }
  const LX = -0.62, Y_TOP = 1.14, Y_BOT = -0.9, GATE_Y = [0.86, 0.56, 0.26, -0.04, -0.34, -0.64], COUNCIL = 3, Y_LEDGER = -1.0;
  const GATE_HX = 0.5, GATE_HZ = 0.27, AP_R = 0.3, LEDGER_X0 = LX + 0.36, LEDGER_DX = 0.17, LEDGER_N = 10;
  const GATE_OF_PLATE = [0, 1, 2, 3, 4, 4, 5, 5];
  const Y_FLOOR = -0.5, H_COL = 1.0, COL_SPAN = Math.min(2.9, 0.29 * NCOL);
  const F_SOLID = 0.62, Y_FL = Y_FLOOR + F_SOLID * H_COL;
  const Y_CTOP = Y_FL + (Y_FL - Y_FLOOR - 0.04) / (FLOOR > 0 && FLOOR < 30 ? Math.round(FLOOR) : 10);
  const COL_X = (c) => -COL_SPAN / 2 + COL_SPAN * (c + 0.5) / NCOL;
  const NB = FLOOR > 0 && FLOOR < 30 ? Math.round(FLOOR) : 10, BP = (Y_FL - Y_FLOOR) / NB;
  const K4_MAX = 2.6;
  let colK = 1;
  const yK = (y) => Y_FLOOR + (y - Y_FLOOR) * colK;

  const N_SURF = LITE ? 5400 : 10800, N_ORB = LITE ? 760 : 1500, N_SIG = LITE ? 520 : 960, N_DUST = LITE ? 520 : 1000;
  const N = N_SURF + N_ORB + N_SIG + N_DUST;
  const I_ORB = N_SURF, I_SIG = I_ORB + N_ORB, I_DUST = I_SIG + N_SIG;
  const M = { STATIC: 0, GLOBE: 1, ORBIT: 2, RING: 3, JITTER: 4, SIGIN: 5, FLOW: 6, FLOWREJ: 7, FALL: 8, DRIFT: 9, COLUMN: 10 };
  const K = { IVORY: 0, KHAKI: 1, GREEN: 2, RED: 3, DUST: 4, MOTE: 5, DIM: 6, GDIM: 7, BRIGHT: 8, KDIM: 9 };
  const code = (mode, kind, grp) => mode * 1000 + kind * 100 + (grp || 0);
  const F = Array.from({ length: 5 }, () => new Float32Array(N * 4));
  const RAND = new Float32Array(N * 4), KEY = new Float32Array(N * 4);
  let seed = 11;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const gauss = () => (rnd() + rnd() + rnd() - 1.5) * 0.82;
  for (let i = 0; i < N * 4; i++) RAND[i] = rnd();
  const set = (s, i, x, y, z, c) => { const o = i * 4; F[s][o] = x; F[s][o + 1] = y; F[s][o + 2] = z; F[s][o + 3] = c; };
  const R = (i, k) => RAND[i * 4 + k];

  function* build() {
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
        set(0, i, c * Math.cos(l), Math.sin(lat[r]), c * Math.sin(l), code(M.GLOBE, R(i, 0) < 0.022 ? K.GREEN : R(i, 0) < 0.055 ? K.BRIGHT : K.IVORY, 0));
        KEY[i * 4] = (b + 0.45 * (j / cnt[r])) / 6.45;
      }
    }
    yield;
    for (let q = 0; q < N_ORB; q++) {
      const ii = I_ORB + q, k = q % 6;
      set(0, ii, R(ii, 0) * TAU, ORBITS[k][0] + gauss() * 0.01, gauss() * 0.006, code(M.ORBIT, k === KH_ORB ? K.KHAKI : K.DIM, k));
      KEY[ii * 4] = 0.12 + 0.5 * k / 6;
    }
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU;
      set(0, ii, Math.cos(la) * Math.cos(lo), Math.sin(la), Math.cos(la) * Math.sin(lo), code(M.SIGIN, K.MOTE, 0));
      KEY[ii * 4] = rnd();
    }
    for (let q = 0; q < N_DUST; q++) {
      const ii = I_DUST + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = 2.6 + rnd() * 3.2;
      const x = Math.cos(la) * Math.cos(lo) * rr * 1.5, y = Math.sin(la) * rr * 0.8, z = Math.cos(la) * Math.sin(lo) * rr - 1.0;
      for (let s = 0; s < 5; s++) set(s, ii, x, y, z, code(M.DRIFT, K.DUST, 0));
    }

    yield;
    const ringAng = new Float32Array(N_SURF), ringOf = new Uint8Array(N_SURF);
    const dash = (k, th) => {
      if (k === 0) return th;
      const n = k < 3 ? 64 : 84, duty = k < 3 ? 0.55 : 0.1, per = TAU / n, x = ((th % TAU) + TAU) % TAU;
      const di = Math.floor(x / per); return di * per + (x - di * per) * duty;
    };
    for (let q = 0; q < N_SURF; q++) {
      const k = RING_OF_BAND[band[q]], [rr, , az] = RINGS[k];
      const th = dash(k, az - lam[q]);
      ringAng[q] = th; ringOf[q] = k;
      const kind = k === 0 ? (R(q, 1) < 0.88 ? K.GREEN : K.BRIGHT) : k < 3 ? (R(q, 1) < 0.3 ? K.IVORY : K.DUST) : (R(q, 1) < 0.3 ? K.KHAKI : K.KDIM);
      set(1, q, th, rr + gauss() * (k === 0 ? 0.022 : 0.014), gauss() * 0.006, code(M.RING, kind, k));
    }
    for (let q = 0; q < N_ORB; q++) {
      const ii = I_ORB + q, k = q % 6;
      set(1, ii, dash(k, F[0][ii * 4]), RINGS[k][0] + gauss() * 0.006, gauss() * 0.004, code(M.RING, k === 0 ? K.GREEN : k < 3 ? K.DUST : K.KDIM, k));
    }
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q, la = Math.asin(rnd() * 2 - 1), lo = rnd() * TAU, rr = 0.03 + rnd() * 0.07;
      set(1, ii, Math.cos(la) * Math.cos(lo) * rr, Math.sin(la) * rr, Math.cos(la) * Math.sin(lo) * rr, code(M.SIGIN, K.MOTE, 1));
      KEY[ii * 4 + 1] = rnd();
    }
    yield;
    const phi1 = new Float32Array(N_SURF);
    for (let q = 0; q < N_SURF; q++) { const p = onLoop(RB[ringOf[q]], RINGS[ringOf[q]][0], ringAng[q], 0); phi1[q] = Math.atan2(p[2], p[0]); }

    yield;
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
      } else {
        const gx = Math.max(4, Math.round(Math.sqrt(chunk.length * PL_HX / PL_HZ))), gz = Math.ceil(chunk.length / gx);
        const pts = [];
        for (let a = 0; a < gx; a++) for (let b = 0; b < gz; b++) { const x = (-1 + 2 * (a + 0.5) / gx) * (PL_HX - 0.05), z = (-1 + 2 * (b + 0.5) / gz) * (PL_HZ - 0.05); pts.push([x, z, Math.atan2(z, x)]); }
        pts.sort((a, b) => a[2] - b[2]);
        const byAng = chunk.slice().sort((a, b) => phi1[a] - phi1[b]);
        byAng.forEach((q, j) => { const g = pts[Math.floor(j * pts.length / byAng.length)]; set(2, q, g[0], y, g[1], code(M.STATIC, K.IVORY, p)); });
      }
      chunk.forEach(q => { KEY[q * 4 + 1] = (p + 0.35 * R(q, 0)) / 8.35; });
    }
    yield;
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

    yield;
    const gateLists = [[], [], [], [], [], []];
    const stream = [];
    for (let q = 0; q < N_SURF; q++) {
      const p = plateOf[q];
      if (rankIn[q] < 0.4) gateLists[GATE_OF_PLATE[p]].push(q); else stream.push(q);
      KEY[q * 4 + 2] = (p + 0.4 * R(q, 1)) / 8.4;
    }
    yield;
    gateLists.forEach((list, g) => {
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
      if (p < 8) {
        const g = GATE_OF_PLATE[p], [x, z] = rrHit(R(ii, 2) * TAU, GATE_HX, GATE_HZ, 0.04);
        set(3, ii, LX + x, GATE_Y[g], z, code(M.STATIC, K.DIM, g));
      } else {
        const a = R(ii, 2) * TAU;
        set(3, ii, LX + Math.cos(a) * AP_R, GATE_Y[COUNCIL], Math.sin(a) * AP_R, code(M.STATIC, K.GDIM, 9));
      }
      KEY[ii * 4 + 2] = (Math.min(p, 7.5) + 0.3 * R(ii, 1)) / 8.3;
    });
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q;
      if (q % 2) set(3, ii, (rnd() - 0.5) * 3.2, (rnd() - 0.5) * 2.4, -0.6 - rnd() * 1.2, code(M.DRIFT, K.DUST, 0));
      else set(3, ii, LX + gauss() * 0.03, Y_TOP + 0.02, gauss() * 0.03, code(M.SIGIN, K.MOTE, 2));
      KEY[ii * 4 + 3] = rnd();
    }

    yield;
    const s3y = (q) => { const c = F[3][q * 4 + 3], mode = Math.floor(c / 1000); return mode === M.FLOW || mode === M.FLOWREJ ? Y_TOP - F[3][q * 4 + 1] * (Y_TOP - Y_BOT) : F[3][q * 4 + 1]; };
    const byY = Array.from({ length: N_SURF }, (_, q) => q).sort((a, b) => s3y(b) - s3y(a));
    yield;
    const perC = Math.floor(N_SURF / NCOL), nx = 5, nz = 3, sN = nx * nz, oN = 2 * nz, yS = Y_FL - Y_FLOOR - 0.04;
    const UO = yS / NB;
    for (let c = 0; c < NCOL; c++) {
      const list = byY.slice(c * perC, c === NCOL - 1 ? N_SURF : (c + 1) * perC);
      const pit = (sN * yS + oN * UO) / list.length, cut = sN * Math.round(yS / pit), x0 = COL_X(c);
      const above = SESSIONS[c].above;
      list.sort((a, b) => R(a, 2) - R(b, 2)).forEach((q, j) => {
        const o = j >= cut, k = o ? j - cut : j, w = o ? 2 : nx, a = o ? (k % 2) * (nx - 1) : k % nx, b = Math.floor(k / w) % nz;
        const g = (Math.floor(k / sN) + 0.5) * pit * NB / yS, f = o ? yS + UO * 0.14 + 0.72 * Math.min(UO, (Math.floor(k / oN) + 0.5) * pit) : (Math.floor(g) + 0.06 + 0.72 * (g % 1)) * BP - 0.04;
        set(4, q, x0 + (a - (nx - 1) / 2) * 0.024, Y_FLOOR + 0.04 + f, (b - (nz - 1) / 2) * 0.024, code(M.COLUMN, !above ? K.DIM : !o && R(q, 1) < 0.34 ? K.BRIGHT : K.IVORY, c));
        KEY[q * 4 + 3] = (c + 0.55 * (R(q, 3) * 7.31 % 1)) / (NCOL + 0.55);
      });
    }
    orbOrder.forEach((ii, j) => {
      const u = j / N_ORB, x = -COL_SPAN / 2 - 0.16 + u * (COL_SPAN / 2 + 0.16 + COL_X(NCOL - 1) + 0.08);
      set(4, ii, x, Y_FLOOR + gauss() * 0.002, gauss() * 0.004, code(M.STATIC, K.DIM, 9));
      KEY[ii * 4 + 3] = u * 0.9;
    });
    for (let q = 0; q < N_SIG; q++) {
      const ii = I_SIG + q;
      set(4, ii, (rnd() - 0.5) * (COL_SPAN + 0.8), Y_FLOOR + 0.1 + rnd() * 1.2, (rnd() - 0.5) * 1.2 - 0.2, code(M.DRIFT, K.DUST, 0));
    }
    for (let q = 0; q < N_SIG; q++) { const ii = I_SIG + q; KEY[ii * 4 + 1] = KEY[ii * 4 + 1] || rnd(); }
  }

  const GATE_GLSL = GATE_Y.map(v => v.toFixed(4));
  const VS_BULK = `
  precision highp float;
  attribute vec4 a_from, a_to, a_rand, a_key;
  uniform mat4 u_view, u_proj;
  uniform float u_time, u_m, u_spread, u_swirl, u_lift, u_keyIdx, u_sA, u_sB, u_spin, u_pr, u_dist, u_fogR, u_halo, u_maxpt, u_intro, u_shade, u_gather;
  uniform vec3 u_liftDir, u_light;
  uniform vec3 u_rU[12]; uniform vec3 u_rV[12]; uniform float u_rW[12];
  uniform float u_hov[24]; uniform float u_hovOn, u_hovScene, u_sceneA, u_sceneB, u_hovLift;
  uniform float u_cg[24]; uniform float u_fold, u_railA, u_colK; // (hc8) u_cg: each session column's green (0..1); u_fold: the columns' fold (one for all ten, was u_dc[24])
  uniform vec4 u_occ;
  uniform vec2 u_band;
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
  vec3 resolve(vec4 s, out float kind, out float grp, out float al, out float mode, out float cg) {
    cg = 0.0;
    mode = floor(s.w / 1000.0 + 0.001);
    float rem = s.w - mode * 1000.0;
    kind = floor(rem / 100.0 + 0.001);
    grp = rem - kind * 100.0;
    al = 1.0;
    vec4 r = a_rand;
    if (mode < 0.5) { // (hc6) S4's rail in agents (dim, group 9) gives way to its drawn hairline on wide screens as the row spreads
      if (abs(grp - 9.0) < 0.5 && abs(kind - ${K.DIM.toFixed(1)}) < 0.5) al = u_railA;
      return s.xyz;
    }
    if (mode < 1.5) return rotY(u_spin) * s.xyz;
    if (mode < 3.5) { // orbit (S0, rings 0-5) or lifecycle ring (S1, rings 6-11): x angle, y radius, z lift
      int k = int(grp + 0.5) + (mode > 2.5 ? 6 : 0);
      // LC-01's close beads at under half strength: overlaps stay green, not cyan white
      if (mode > 2.5 && grp < 0.5) al = kind > 1.5 && kind < 2.5 ? 0.44 : kind > 7.5 && kind < 8.5 ? 0.5 : 1.0;
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
    // a session column: solid up to the floor, open above it; on the way out all ten fold onto the foot together
    float hN = (s.y - ${Y_FLOOR.toFixed(3)}) / ${H_COL.toFixed(3)};
    al = 1.0 - step(${F_SOLID.toFixed(3)}, hN) * (1.0 - 0.62 * pow(1.0 - smoothstep(${F_SOLID.toFixed(3)}, 1.04, hN), 1.6));
    float dc = u_fold;
    cg = u_cg[int(clamp(grp, 0.0, 23.0) + 0.5)]; // (hc8) settled: signal green as its broker tick lands
    float yc = ${Y_FLOOR.toFixed(3)} + (s.y - ${Y_FLOOR.toFixed(3)}) * u_colK; // (hc7) wide: drawn taller, the same encoding
    if (dc > 0.0) {
      al *= 1.0 - smoothstep(0.6, 1.0, dc);
      return vec3(s.x, mix(yc, ${(Y_FLOOR + 0.02).toFixed(3)}, dc), s.z);
    }
    return vec3(s.x, yc, s.z);
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
    if (k < 8.5) return vec3(0.99, 0.98, 0.95);
    return vec3(0.70, 0.67, 0.57);
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
    if (k < 8.5) return vec4(1.15, 1.0, 0.0, 0.25);
    return vec4(0.7, 0.2, 1.0, 0.0);
  }
  float easeSpring(float t) { float s = t * t * (3.0 - 2.0 * t); float u = s - 1.0; return 1.0 + ${C3.toFixed(3)} * u * u * u + ${C1.toFixed(3)} * u * u; }
  void main() {
    float kA, gA, aA, kB, gB, aB, mA, mB, cA, cB;
    vec3 A = resolve(a_from, kA, gA, aA, mA, cA) * u_sA;
    vec3 B = resolve(a_to, kB, gB, aB, mB, cB) * u_sB;
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
    // the hand-off: on a first visit the loader's ring opens onto the globe's limb, and each globe point arrives from
    // that ring as it draws in (band by band, from the top), so the ring's dots become the globe
    float iaG = clamp(u_intro * 1.7 - a_key.x * 0.7, 0.0, 1.0);
    float gw = u_gather * step(u_sceneA, 0.5) * step(0.5, mA) * step(mA, 1.5) * (1.0 - tc) * (1.0 - iaG) * (1.0 - iaG);
    if (gw > 0.0) {
      vec4 o0 = u_view * vec4(0.0, 0.0, 0.0, 1.0);
      vec2 dq = mv.xy - o0.xy;
      float lq = length(dq);
      vec2 dir = lq > 1e-4 ? dq / lq : vec2(cos(a_rand.x * TAU), sin(a_rand.x * TAU));
      mv.xyz = mix(mv.xyz, vec3(o0.xy + dir * u_sA, o0.z), gw);
    }
    gl_Position = u_proj * mv;
    vec4 pr = kprop(k), prB = kprop(kB), prA = kprop(kA);
    vec3 col = mix(mix(kcol(kA), kcol(2.0), cA), mix(kcol(kB), kcol(2.0), cB), tc); // (hc8) a settled column in the signal green
    float al = mix(prA.y * aA, prB.y * aB, tc) * (1.0 - cB * tc);
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
    // at the globe's limb its foreshortened rows would stack into bright coils: smaller, fainter beads there
    float onGlobe = step(0.5, mA) * step(mA, 1.5) * (1.0 - tc), ndv = smoothstep(0.04, 0.5, abs(Nv.z));
    float limb = mix(1.0, mix(0.5, 1.0, ndv), onGlobe);
    al *= mix(1.0, mix(0.3, 1.0, ndv), onGlobe);
    // (hc5) the first frame's globe at Company's particle weight: a step brighter, most where its points are smallest (1x screens)
    al *= 1.0 + onGlobe * mix(1.0, 0.5, clamp((u_pr - 1.0) / 1.4, 0.0, 1.0));
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
    // (award a2) nothing drawn among the nav's words (or, portrait, the scene index's): points fade out under the bars
    al *= 1.0 - smoothstep(u_band.x, u_band.y, gl_Position.y / max(gl_Position.w, 1e-4));
    float persp = u_dist / max(0.2, -mv.z);
    float size = pr.x * (1.55 + 1.15 * a_rand.x) * mix(0.82, 1.18, persp - 0.5) * (1.0 + 0.3 * h) * mix(1.1, 0.8, fz) * (0.55 + 0.45 * ia) * limb * u_pr;
    size *= 1.0 + ${LITE ? '0.3' : '0.15'} * (u_colK - 1.0) * step(9.5, mB) * tc; // (hc7) the taller columns' blocks keep their weight (their points stand further apart; hc8: a tablet's half-count columns, twice the gain)
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
  const VS_LINE = `
  precision highp float;
  attribute vec2 a_corner; attribute vec3 a_p0, a_p1; attribute vec4 a_col; attribute float a_w;
  uniform mat4 u_view, u_proj; uniform vec2 u_res; uniform float u_pr, u_dist, u_fogR; uniform vec4 u_occ;
  varying vec4 v_col; varying float v_side, v_hw, v_glow;
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
    v_side = a_corner.y * (hw + 1.0); v_hw = hw; v_glow = a_w > 3.0 ? 1.0 : 0.0;
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
  varying vec4 v_col; varying float v_side, v_hw, v_glow;
  void main() {
    float cov = clamp(v_hw + 0.5 - abs(v_side), 0.0, 1.0), g = abs(v_side) / max(v_hw, 1.0);
    float a = v_col.a * mix(cov, exp(-g * g * 3.0) * 1.5, v_glow);
    gl_FragColor = vec4(v_col.rgb * a, a);
  }`;
  const VS_ACT = `
  precision highp float;
  attribute vec3 a_pos; attribute vec4 a_col; attribute vec4 a_shp;
  uniform mat4 u_view, u_proj; uniform float u_pr, u_dist, u_fogR, u_halo, u_maxpt; uniform vec2 u_res;
  varying vec4 v_col; varying vec4 v_shp; varying float v_size;
  void main() {
    vec4 mv = u_view * vec4(a_pos, 1.0);
    gl_Position = u_proj * mv;
    float blk = step(4.5, a_shp.x);
    if (blk > 0.5) { vec2 px = floor((gl_Position.xy / gl_Position.w * 0.5 + 0.5) * u_res + 0.5); gl_Position.xy = (px / u_res * 2.0 - 1.0) * gl_Position.w; }
    float persp = u_dist / max(0.2, -mv.z);
    float sz = a_shp.y * u_pr * mix(mix(1.0, persp, 0.5), 1.0, blk);
    float fz = clamp((-mv.z - u_dist + u_fogR) / (2.0 * u_fogR), 0.0, 1.0);
    float al = a_col.a * mix(mix(1.05, 0.45, fz), 1.0, blk);
    float size = sz * mix(1.0, max(1.0, a_shp.w), blk) + 2.0;
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
  uniform float u_sw;
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
    else if (shape < 4.5) { float d = length(q) / (s * 0.5); a = exp(-d * d * 3.0) * (1.0 - smoothstep(0.85, 1.0, d)); }
    else { // a basis-point block (5) or the open block above the floor (6), as on Proof
      float d = box(q, vec2(s * 0.5, s * 0.5 * aux), min(1.5, s * 0.08));
      a = clamp(0.5 - d, 0.0, 1.0);
      if (shape > 5.5) a *= clamp(d + u_sw + 0.5, 0.0, 1.0);
    }
    a *= v_col.a;
    gl_FragColor = vec4(v_col.rgb * a, a);
  }`;

  let gl = null, lost = false, ext = null, ready = false;
  const P = {};
  const BUF = {};
  let N_LINE_MAX = 6000, N_ACT_MAX = 200;
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
    const par = gl.getExtension('KHR_parallel_shader_compile');
    const gen = ++setupGen;
    (function linked() { guard(() => {
      if (gen !== setupGen || gl.isContextLost()) return;
      if (!built || (par && !Object.values(progs).every(p => gl.getProgramParameter(p.prog, par.COMPLETION_STATUS_KHR)))) { requestAnimationFrame(linked); return; }
      Object.values(progs).forEach(p => {
        if (!gl.getProgramParameter(p.prog, gl.LINK_STATUS)) throw new Error('story shader: ' + (gl.getShaderInfoLog(p.v) || gl.getShaderInfoLog(p.f) || gl.getProgramInfoLog(p.prog)));
      });
      Object.assign(P, progs);
      bindProgram(P.bulk, ['u_view', 'u_proj', 'u_time', 'u_m', 'u_spread', 'u_swirl', 'u_lift', 'u_keyIdx', 'u_sA', 'u_sB', 'u_spin', 'u_pr', 'u_dist', 'u_fogR', 'u_halo', 'u_maxpt', 'u_intro', 'u_shade', 'u_gather', 'u_liftDir', 'u_light', 'u_rU', 'u_rV', 'u_rW', 'u_hov', 'u_hovOn', 'u_hovScene', 'u_sceneA', 'u_sceneB', 'u_hovLift', 'u_occ', 'u_cg', 'u_fold', 'u_railA', 'u_colK', 'u_band'], ['a_from', 'a_to', 'a_rand', 'a_key']);
      bindProgram(P.line, ['u_view', 'u_proj', 'u_res', 'u_pr', 'u_dist', 'u_fogR', 'u_occ'], ['a_corner', 'a_p0', 'a_p1', 'a_col', 'a_w']);
      bindProgram(P.act, ['u_view', 'u_proj', 'u_pr', 'u_dist', 'u_fogR', 'u_halo', 'u_maxpt', 'u_res', 'u_sw'], ['a_pos', 'a_col', 'a_shp']);
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
      setTimeout(() => guard(done), 0);
    }); })();
  }); }
  let maxPt = 64;

  const proj = new Float32Array(16), view = new Float32Array(16), vp = new Float32Array(16);
  const FOV = 0.56, CAM_D = 6.2;
  function perspective(out, fovy, aspect, near, far, sx, sy) {
    const f = 1 / Math.tan(fovy / 2), nf = 1 / (near - far);
    out.fill(0); out[0] = f / aspect; out[5] = f; out[10] = (far + near) * nf; out[11] = -1; out[14] = 2 * far * near * nf;
    out[8] = -sx; out[9] = -sy;
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
  function project(x, y, z) {
    const cx = vp[0] * x + vp[4] * y + vp[8] * z + vp[12], cy = vp[1] * x + vp[5] * y + vp[9] * z + vp[13], cw = vp[3] * x + vp[7] * y + vp[11] * z + vp[15];
    PO.x = (cx / cw * 0.5 + 0.5) * W; PO.y = (0.5 - cy / cw * 0.5) * H; PO.w = cw; return PO;
  }

  let W = 1, H = 1, dpr = 1, ptK = 1, remK = 1, ratio = 0, stacked = false, compact = false, short = false, tiny = false, navH = 72, barH = 64, barTop = 0, gutter = 24, contR, safeL = 0, safeR = 0, safeProbe = null;
  const EXT = [[2.9, 2.5], [3.3, 2.2], [2.75, 2.75], [2.55, 2.5], [3.8, 2.0]];
  const EXT_ST = [[2.45, 2.12], [3.3, 2.7], null, null, null];
  const CENTER = [[0, 0, 0], [0, 0.04, 0], [0, -0.02, 0], [0.12, 0.08, 0], [0, Y_FLOOR + 0.6, 0]];
  const CAM_W = [[0.13, 0.0], [0.6, -0.08], [0.5, -0.56], [0.3, -0.3], [0.12, 0.0]];
  const CAM_ST = [[0.13, 0.0], [0.86, -0.08], [0.5, -0.56], [0.3, -0.3], [0.12, 0.0]];
  let CAM = CAM_W;
  const ROOM_W = [0, 250, 236, 214, 0];
  const ZONE = ['right', 'right', 'right', 'right', 'right'];
  const U_REC = 6.5, U_NAV = 22, U_TICK = 10, U_DAY = 35, DAY_BAND = 70, U_CHK = 9;
  const MIN_FRAME = [0, 120, 110, 120, DAY_BAND + 90];
  const frameTiny = [false, false, false, false, false];
  const band4 = () => (frameTiny[4] ? 8 : Math.max(DAY_BAND * remK, (U_DAY + 14) * remK + dayH + keyH));
  let dayPitch = 99, b4 = null;
  const layouts = Array.from({ length: 5 }, () => ({ cx: 0, cy: 0, s: 1, rect: [0, 0, 0, 0] }));
  const beatRects = [], capH = [0, 0, 0, 0, 0], labelMaxW = [0, 0, 0, 0, 0], roomOf = [0, 0, 0, 0, 0];
  let storyTop = 0, run = 1, scrollY = 0, stageH = 1, storyH = 1, lastP = NaN, floorW = 0, floorH = 0, hedgeW = 0, hedgeH = 0, hedgeBeside = false, floorL = -COL_SPAN / 2 - 0.5, dayH = 0, keyH = 0, keyOff = false;
  const hedgeGap = () => 6 * remK;
  const tagsUp = () => 6 + floorH + hedgeGap() + hedgeH + 6;
  let belowBar = true, shownCov = false;
  const pxuOf = (h) => (h / 2) / (CAM_D * Math.tan(FOV / 2));
  const probes = {};
  const tokenPx = (v) => {
    let p = probes[v];
    if (!p) { p = probes[v] = document.createElement('i'); p.setAttribute('aria-hidden', 'true'); const ps = p.style; ps.position = 'absolute'; ps.left = ps.top = '0'; ps.width = '0'; ps.height = `var(${v})`; ps.visibility = 'hidden'; ps.pointerEvents = 'none'; stage.appendChild(p); }
    return parseFloat(getComputedStyle(p).height) || 0;
  };
  const navPx = () => tokenPx('--nav-h');
  const l4 = (px) => px * remK / Math.max(1e-4, layouts[4].s * pxuOf(H));
  function measureScroll() {
    scrollY = window.scrollY;
    storyTop = story.getBoundingClientRect().top + scrollY;
    stageH = stage.offsetHeight || window.innerHeight;
    storyH = story.offsetHeight;
    run = Math.max(1, storyH - stageH - tail);
    sec1H = sec1 ? sec1.offsetHeight : 0;
  }
  const sec1 = story.nextElementSibling;
  let tail = 0, sec1H = 0;
  function setTail(px) {
    px = Math.max(0, Math.round(px));
    if (px === tail) return;
    tail = px;
    [story, sec1].forEach(el => { if (!el) return; if (px) el.style.setProperty('--paper-slack', px + 'px'); else el.style.removeProperty('--paper-slack'); });
  }
  const beatParts = () => beats.map(b => Array.from(b.querySelectorAll('.beat-text, .hero-stats')));
  let partsOf = null, ledeOf = null, ledeLR = null;
  function measureBeat(i) {
    const b = beats[i];
    if (!b || !b.offsetParent) return;
    let l = 1e9, r = -1e9, t = 1e9;
    (partsOf || (partsOf = beatParts()))[i].forEach(el => {
      if (!el.offsetHeight) return;
      const x = el.offsetLeft + b.offsetLeft + b.offsetParent.offsetLeft, y = el.offsetTop + b.offsetTop;
      l = Math.min(l, x); r = Math.max(r, x + el.offsetWidth); t = Math.min(t, y);
    });
    const h2 = b.querySelector('h2, h1');
    beatRects[i] = { l, r, t, bt: b.offsetTop, ht: h2 ? b.offsetTop + h2.offsetTop : t, hb: h2 ? b.offsetTop + h2.offsetTop + h2.offsetHeight : t };
    if (i === 4) {
      let lt = 1e9, lb = 0;
      const els = (ledeOf || (ledeOf = Array.from(b.querySelectorAll('.body-lg, .beat-more')))).filter(el => el.offsetHeight > 1);
      els.forEach(el => { const y = b.offsetTop + el.offsetTop; lt = Math.min(lt, y); lb = Math.max(lb, y + el.offsetHeight); });
      if (ledeLR == null) {
        ledeLR = -1e9;
        els.forEach(el => { const rg = document.createRange(); rg.selectNodeContents(el); Array.from(rg.getClientRects()).forEach(q => { if (q.width > 0) ledeLR = Math.max(ledeLR, q.right); }); });
      }
      Object.assign(beatRects[i], { lt, lb, lr: ledeLR });
    }
  }
  function measureBeats() { beats.forEach((b, i) => measureBeat(i)); }
  function measureLayout() {
    ledeLR = null;
    navH = navPx() || 72;
    const bar = stage.querySelector('.story-bar');
    barH = bar ? bar.offsetHeight : 64; barTop = bar ? bar.offsetTop : H - barH;
    const cont = stage.querySelector('.story-ui .container');
    const ccs = cont && getComputedStyle(cont);
    gutter = (ccs && parseFloat(ccs.paddingLeft)) || 24;
    contR = cont ? cont.getBoundingClientRect().right - ((ccs && parseFloat(ccs.paddingRight)) || gutter) : W - gutter;
    if (!safeProbe) { safeProbe = document.createElement('i'); safeProbe.setAttribute('aria-hidden', 'true'); const ps = safeProbe.style; ps.position = 'absolute'; ps.visibility = 'hidden'; ps.pointerEvents = 'none'; ps.paddingLeft = 'env(safe-area-inset-left)'; ps.paddingRight = 'env(safe-area-inset-right)'; stage.appendChild(safeProbe); }
    { const pc = getComputedStyle(safeProbe); safeL = parseFloat(pc.paddingLeft) || 0; safeR = parseFloat(pc.paddingRight) || 0; }
    measureBeats();
    labelMaxW.fill(0); capH.fill(0);
    const sizeLabel = (l) => {
      l.w = l.el.offsetWidth; l.h = l.el.offsetHeight; l.tr = '';
      if (l.kind === 'cap') capH[l.scene] = l.h;
      else if (l.kind === 'list' && !((stacked || short) && l.wide)) labelMaxW[l.scene] = Math.max(labelMaxW[l.scene], l.w);
      if (l.floor) { floorW = l.w; floorH = l.h; }
      if (l.hedge) { hedgeW = l.w; hedgeH = l.h; }
      if (l.key) keyH = short || keyOff ? 0 : l.h;
      if (l.col === 0) dayH = l.h;
    };
    labels.forEach(l => {
      if (l.terse) { l.terse = false; l.el.classList.remove('is-terse'); }
      if (l.row) { l.row = false; l.el.classList.remove('is-row'); }
      if (l.kind === 'cap') { const br = beatRects[l.scene]; l.el.style.maxWidth = !stacked && br && br.r > 0 ? Math.max(180, contR - (br.r + 28)) + 'px' : ''; }
      sizeLabel(l);
    });
    if (stacked && W >= 600 && hedgeH) capH[4] = hedgeH + 10;
    if (!stacked && short) [1, 2].forEach(i => {
      const br = beatRects[i] && beatRects[i].r > 0 ? beatRects[i] : { r: W * 0.46 }, ext = EXT[i];
      const needW = Math.min(H - barH - Math.max(18, capH[i] + 12) - (navH + 22), H * 0.74) * ext[0] / ext[1];
      const size = () => Math.max(0, Math.min(W - gutter - (labelMaxW[i] + 28) - Math.min(br.r + 36, W * 0.56), needW));
      const setTerse = (on) => { labelMaxW[i] = 0; labels.forEach(l => { if (l.scene !== i || l.kind !== 'list') return; if (l.group != null) { l.terse = on; l.el.classList.toggle('is-terse', on); } sizeLabel(l); }); };
      const named = size();
      setTerse(true);
      if (named >= 0.8 * size()) setTerse(false);
    });
    if (stacked && lab.rings && beatRects[1]) {
      const avail = beatRects[1].t - 18 - (navH + barH + capH[1] + 22), hMax = Math.max(...lab.rings.map(l => l.h));
      if (lab.rings.length * (hMax + 2) > avail) { labelMaxW[1] = 0; labels.forEach(l => { if (l.scene !== 1 || l.kind !== 'list') return; if (l.group != null) { l.row = true; l.el.classList.add('is-row'); } sizeLabel(l); }); }
    }
  }
  function setModes() {
    stacked = stackedMQ.matches; CAM = stacked ? CAM_ST : CAM_W;
    EXIT_U = stacked && W < 600 ? 0.6 : 0.9; TOTAL_U = 4 + EXIT_U;
    clearLift();
    root.classList.remove('story-compact', 'story-short');
    beats.forEach(b => b.classList.remove('is-tight', 'is-snug'));
    compact = stacked && (H < 780 || W < 600); short = !stacked && H < 600;
    if (stacked && !compact) {
      measureLayout();
      const top = navH + barH + Math.max(...capH) + 8;
      compact = beatRects.some(br => br.t - 14 - top < 0.4 * H);
    }
    root.classList.toggle('story-compact', compact); root.classList.toggle('story-short', short);
    measureLayout();
    const lim = navH + (stacked ? barH : 0) + 6;
    let tight = false;
    if (beatRects[0] && beatRects[0].t < lim) { beats[0].classList.add('is-snug'); measureLayout(); }
    beats.forEach((b, i) => { if (beatRects[i] && beatRects[i].t < lim) { b.classList.add('is-tight'); tight = true; } });
    if (stacked) beats.forEach((b, i) => {
      const br = beatRects[i];
      if (!br || !MIN_FRAME[i] || b.classList.contains('is-tight')) return;
      if (br.t - 14 - (navH + barH + capH[i] + 8) < MIN_FRAME[i]) { b.classList.add('is-tight'); tight = true; }
    });
    if (tight) measureLayout();
    if (liftBeats()) measureBeats();
    beats.forEach((b, i) => { const br = beatRects[i]; frameTiny[i] = !!(stacked && br && (MIN_FRAME[i] || !i) && br.t - 14 - (navH + barH + capH[i] + 8) < (i === 4 ? 40 + DAY_BAND : 40)); });
    shownIdx = -1;
  }
  function tailNow() { return tiny || !sec1 ? 0 : H; }
  const LIFT_AIR = 18, LIFT_K = 0.42;
  let lifted = false;
  function clearLift() { if (!lifted) return; lifted = false; beats.forEach(b => { b.style.top = b.style.bottom = ''; }); }
  function needOf(i) {
    const room = Math.max([0, 0.13, 0.15, 0.1, 0][i] * W, labelMaxW[i] ? labelMaxW[i] + 28 : 0), x0 = gutter * 0.5, x1 = W - gutter * 0.5 - room;
    if (i === 4) return (H_COL + 0.34) * (x1 - (x0 + floorW + 14)) / (COL_SPAN + 0.24) + band4();
    const ext = EXT_ST[i] || EXT[i], list = labels.filter(l => l.scene === i && l.kind === 'list' && !l.wide);
    const listH = list.length ? 14 + list.length * (Math.max(...list.map(l => l.h)) + 2) - 2 : 0;
    return Math.max(Math.min((x1 - x0) * ext[1] / ext[0], H * 0.74), listH);
  }
  function liftBeats() {
    if (!stacked || tiny) return false;
    let T = -1e9, foot = 1e9, fit = 0;
    for (let i = 1; i < 5; i++) {
      const b = beats[i];
      if (!b || !b.offsetParent || b.classList.contains('is-tight')) return false;
      const y0 = navH + barH + capH[i] + 8, need = needOf(i), top = b.offsetTop;
      const base = y0 + need + 14 + LIFT_AIR;
      T = Math.max(T, base + LIFT_K * (top - base));
      foot = Math.min(foot, top); fit = Math.max(fit, y0 + need + 14);
    }
    T = Math.round(Math.max(fit, Math.min(T, foot)));
    if (T > foot - 8) return false;
    beats.forEach((b, i) => { if (i) { b.style.top = T + 'px'; b.style.bottom = 'auto'; } });
    return (lifted = true);
  }
  const tmpV = new Float32Array(16), tmpP = new Float32Array(16), tmpVP = new Float32Array(16);
  function ringOutline(s) {
    const el = CAM[1][0], az = CAM[1][1], tc = [0, CENTER[1][1] * s, 0];
    lookAt(tmpV, [tc[0] + Math.sin(az) * Math.cos(el) * CAM_D, tc[1] + Math.sin(el) * CAM_D, tc[2] + Math.cos(az) * Math.cos(el) * CAM_D], tc);
    perspective(tmpP, FOV, W / H, 0.1, 40, 0, 0); mul(tmpVP, tmpP, tmpV);
    const out = [];
    for (let k = 0; k < 6; k++) for (let j = 0; j < 40; j++) {
      const q = onLoop(RB[k], RINGS[k][0], j / 40 * TAU, 0), x = q[0] * s, y = q[1] * s, z = q[2] * s, v = tmpVP;
      const cw = v[3] * x + v[7] * y + v[11] * z + v[15];
      out.push(((v[0] * x + v[4] * y + v[8] * z + v[12]) / cw) * 0.5 * W, -((v[1] * x + v[5] * y + v[9] * z + v[13]) / cw) * 0.5 * H);
    }
    return out;
  }
  function fitRings(s0, x1, cy, br, pxu) {
    const ok = (s) => {
      const o = ringOutline(s);
      let maxX = -1e9; for (let j = 0; j < o.length; j += 2) maxX = Math.max(maxX, o[j]);
      const cx = x1 - 8 - maxX;
      for (let j = 0; j < o.length; j += 2) {
        const x = cx + o[j], y = cy + o[j + 1];
        if (x < gutter || y < navH + 24 || y > H - barH - Math.max(18, capH[1] + 12)) return null;
        if (x < br.r + 22 && y > br.t - 14) return null;
      }
      return { cx, minX: Math.min(...o.filter((_, j) => j % 2 === 0)) };
    };
    let lo = s0 * 0.25, hi = Math.max(s0, Math.min(s0 * 2.4, (W * 0.62) / (3.25 * pxu)));
    if (!ok(lo)) return null;
    for (let it = 0; it < 16; it++) { const m = (lo + hi) / 2; if (ok(m)) lo = m; else hi = m; }
    const r = ok(lo);
    return { s: lo, cx: r.cx, cy, x0: r.cx + r.minX };
  }
  function fitScenes() {
    const pxu = pxuOf(H);
    for (let i = 0; i < 5; i++) {
      const br = beatRects[i] && beatRects[i].r > 0 && beatRects[i].r < W ? beatRects[i] : { r: W * 0.46, t: H * 0.55 };
      const ext = (stacked && EXT_ST[i]) || EXT[i];
      let x0, x1, y0, y1, s, cx, cy, yTop = 0;
      if (!stacked) {
        let room = Math.min(ROOM_W[i], W * 0.18);
        if (short && i >= 1 && i <= 3 && labelMaxW[i]) room = Math.max(room, labelMaxW[i] + 28);
        roomOf[i] = room;
        x1 = W - gutter - room; y0 = navH + 22;
        if (ZONE[i] === 'upper' && br.t - y0 > H * 0.36) { x0 = gutter + (W - 2 * gutter) * 0.3; y1 = br.t - 26; }
        else { x0 = Math.min(br.r + 36, W * 0.56); y1 = H - barH - Math.max(18, capH[i] + 12); }
        if (x1 - x0 < 240) x0 = Math.max(x1 - 240, short && br.t < y1 ? br.r + 16 : -1e9);
      } else {
        const room = roomOf[i] = Math.max([0, 0.13, 0.15, 0.1, 0][i] * W, labelMaxW[i] ? labelMaxW[i] + 28 : 0);
        x0 = gutter * 0.5; x1 = W - gutter * 0.5 - room;
        y0 = yTop = navH + barH + capH[i] + 8;
        y1 = Math.min(Math.max(y0 + 120, Math.min(H * 0.8, br.t) - 14), br.t - 14);
        if (lifted && i) y0 = Math.max(y0, y1 - needOf(i) - LIFT_AIR);
      }
      if (i === 4) {
        if (!stacked && contR > x0) x1 = Math.min(x1, contR);
        const xa = x0 + floorW + 14, sw = (x1 - xa) / ((COL_SPAN + 0.24) * pxu);
        const free = (stacked ? y1 - yTop : y1 - y0) - band4() - 12 * remK;
        let kw = stacked && W < 600 ? 0 : (free / Math.max(1e-4, sw * pxu) - 0.12) / (Y_CTOP - Y_FLOOR);
        const resv = !stacked && !short;
        if (resv) kw = Math.min(kw, (y1 - y0 - band4() - tagsUp()) / Math.max(1e-4, sw * pxu) / (Y_FL - Y_FLOOR));
        colK = kw > 1 ? Math.min(kw, K4_MAX) : 1;
        s = Math.max(0.05, kw > 1 ? sw : Math.min(sw, (y1 - y0 - band4()) / ((H_COL + 0.34) * pxu)));
        if (!stacked) s = Math.min(s, (H * 0.74) / (EXT[4][1] * pxu));
        dayPitch = COL_SPAN / NCOL * s * pxu;
        if (lab.days) lab.days.forEach((l, c) => {
          l.el.classList.toggle('is-thin', dayPitch < 18 && c % 2 === 1);
          const mw = W < 600 ? clamp(Math.floor(dayPitch - 3), 14, 24) + 'px' : '';
          if (l.el.style.minWidth !== mw) { l.el.style.minWidth = mw; l.w = l.el.offsetWidth; }
        });
        cx = (xa + x1) / 2;
        if (!stacked) { const tw = Math.max(15, ...(lab.days || []).map(l => l.w || 0)); cx = Math.max(cx, x1 - COL_X(NCOL - 1) * s * pxu - tw / 2); }
        let fy = stacked ? y1 - band4() : Math.min(y1 - band4(), Math.max((y0 + y1) / 2 + 0.6 * s * pxu, resv ? y0 + (Y_FL - Y_FLOOR) * s * pxu + tagsUp() : 0));
        const up = ((Y_CTOP - Y_FLOOR) * colK + 0.12) * s * pxu + 12 * remK, dn = band4(), tagUp = (Y_FL - Y_FLOOR) * colK * s * pxu + tagsUp();
        if (!stacked && colK > 1) {
          const top = Math.max(up, resv ? tagUp : 0);
          fy = clamp(y0 + (y1 - y0) * 0.44 + (top - dn) / 2, y0 + top, y1 - dn);
        } else if (stacked && W < 600 && !frameTiny[4]) {
          const top = Math.max(up, tagUp, cx - COL_SPAN / 2 * s * pxu - hedgeW - 8 < 6 + safeL ? ((Y_CTOP - Y_FLOOR) * colK + 0.1) * s * pxu + 7 * remK + 12 + hedgeH : 0);
          fy = Math.min(y1 - dn, Math.max(yTop + top, (yTop + y1 + top - dn) / 2));
        }
        cy = fy - 0.6 * s * pxu;
        floorL = -COL_SPAN / 2 - 0.04 - (floorW + 10) / (s * pxu);
        {
          const ax = cx - COL_SPAN / 2 * s * pxu, fly = fy - (Y_FL - Y_FLOOR) * colK * s * pxu;
          let top = fly - 6 - floorH - hedgeGap() - hedgeH;
          if (ax - hedgeW - 8 < 6 + safeL) top = Math.min(top, fy - ((Y_CTOP - Y_FLOOR) * colK + 0.1) * s * pxu - 7 * remK - 6 - hedgeH);
          hedgeBeside = top < navH + (stacked ? barH : 0) + 5.5 && ax - floorW - 8 - 12 - hedgeW >= 6 + safeL;
          if (lab.hedge) lab.hedge.out = hedgeBeside ? [0.04, 0.2] : [0.2, 0.3];
        }
      } else {
        s = Math.min((x1 - x0) / (ext[0] * pxu), (y1 - y0) / (ext[1] * pxu), (H * 0.74) / (ext[1] * pxu));
        cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
        if (i === 1 && !stacked) {
          const f = [cy, cy - H * 0.06, H * 0.36, H * 0.42].map(c => fitRings(s, x1, c, br, pxu)).filter(Boolean).sort((p, q) => q.s - p.s)[0];
          if (f) { s = f.s; cx = f.cx; x0 = f.x0; cy = f.cy; }
        }
      }
      if (!i && frameTiny[0]) cy = -H;
      layouts[i] = { cx, cy, s, rect: [x0, y0, x1, y1] };
    }
    const L4 = layouts[4], ml = beatRects[4] ? beatRects[4].l : gutter, tw = 15;
    b4 = { s: L4.s, cx: L4.cx, z: Math.max(1, (stacked ? 1.008 : 1.02) * (W - 2 * ml - tw) / (COL_SPAN * (NCOL - 1) / NCOL * L4.s * pxu)) };
  }

  let sNow = 0, sTarget = 0, xNow = 0, xTarget = 0, xeNow = 0, time = 14.3, intro = 0, introStart = -1, gather = 0;
  let seg = 0, mRaw = 0, mE = 0, scale = [1, 1];
  let copyS = 0, copyMode = 'follow', copyFrom = 0, copyTo = 0, copyT0 = 0, lastInput = -1e9, touchDown = false, idleTimer = 0, sPrev = 0;
  const COPY_IDLE = 300, COPY_EASE = 420, CATCH_G = 3;
  const inMorph = (c) => { const f = c - Math.floor(c); return c > 0 && c < 4 && f > HOLD + 0.004 && f < 1 - HOLD - 0.004; };
  const relayAt = (d) => { let bo = 1 - sstep(0.32, 0.42, d); if (bo < 0.08) bo = 0; return { eo: 1 - sstep(0.48, 0.54, d), w: 1 - sstep(0.38, 0.48, d), bo, op: d < 0.56 ? 1 : 0 }; };
  const part = (v) => v > 0.002 && v < 0.998;
  function relayMid(c) {
    let up = 0;
    for (let i = 0; i < 5; i++) { const r = relayAt(Math.abs(c - i)); if (!r.op) continue; up++; if (part(r.eo) || part(r.w) || part(r.bo)) return true; }
    return up > 1;
  }
  function handBack() {
    lastInput = performance.now();
    if (copyMode === 'resolve' || copyMode === 'rest') copyMode = 'catch';
    clearTimeout(idleTimer); idleTimer = setTimeout(requestFrame, COPY_IDLE + 20);
    if (shownSettled) { shownSettled = false; story.removeAttribute('data-settled'); }
  }
  function stepCopy(now, landed) {
    const v = sNow - sPrev; sPrev = sNow;
    if (reducedMQ.matches) { copyS = sNow; copyMode = 'follow'; return; }
    if (copyMode === 'follow') copyS = sNow;
    else if (copyMode === 'catch') {
      const i = Math.round(copyS);
      if (Math.abs(copyS - i) <= HOLD && Math.abs(sNow - i) > HOLD) copyS = i + (sNow > i ? HOLD - 1e-4 : 1e-4 - HOLD);
      const d = sNow - copyS;
      if (Math.abs(d) < 0.0015 || (Math.abs(copyS - i) <= HOLD && Math.abs(sNow - i) <= HOLD)) { copyS = sNow; copyMode = 'follow'; }
      else if (d * v > 0) copyS += Math.sign(d) * Math.min(Math.abs(d), Math.abs(v) * CATCH_G);
    }
    else if (copyMode === 'resolve') { const u = clamp((now - copyT0) / COPY_EASE, 0, 1); copyS = lerp(copyFrom, copyTo, easeMove(u)); if (u >= 1) { copyS = copyTo; copyMode = 'rest'; } }
    if ((copyMode === 'follow' || copyMode === 'catch') && now - lastInput > COPY_IDLE && !touchDown && xTarget <= 0 && inMorph(copyS)) {
      copyFrom = copyS; copyTo = nearScene(sTarget); copyT0 = now; copyMode = 'resolve';
      if (landed) { copyS = copyTo; copyMode = 'rest'; }
    }
  }
  const copyResting = () => copyMode === 'rest' || (copyMode !== 'resolve' && !inMorph(copyS));
  let eye = [0, 0, CAM_D], target = [0, 0, 0], camD = CAM_D;
  const mouse = { x: 0, y: 0, tx: 0, ty: 0, vx: 0, vy: 0 };
  const hand = { hold: false, id: -1, x: 0, a: 0, t: 0, to: 0, off: 0, v: 0, lx: 0, lt: 0, vm: 0 };
  const fineMQ = window.matchMedia('(hover: hover) and (pointer: fine)');
  function sceneScroll() {
    lastP = (scrollY - storyTop) / run;
    const p = clamp(lastP, 0, 1), u = p * TOTAL_U;
    sTarget = Math.min(4, u); xTarget = clamp((u - 4) / EXIT_U, 0, 1);
    belowBar = storyTop + storyH - tail - scrollY > navH + 1;
    const cov = !belowBar && tail > 0;
    if (cov !== shownCov) { story.classList.toggle('is-covered', shownCov = cov); if (cov && sec1) sec1H = sec1.offsetHeight; }
  }
  function morphState() {
    const s = reducedMQ.matches ? Math.round(sNow) : copyS;
    seg = Math.min(3, Math.floor(s));
    const f = s - seg;
    mRaw = clamp((f - HOLD) / (1 - 2 * HOLD), 0, 1);
    mE = mRaw * mRaw * (3 - 2 * mRaw);
  }
  const SWIRL = [0.85, 0.7, 0.25, 0.0], LIFT = [0.18, 0.22, 0.3, 0.32], SHADE = [1, 0.3, 0.25, 0.15, 0.2];
  const LIFT_DIR = [[0, 1, 0], [0, 1, 0], [0, 0, 1], [0, 1, 0.35]];

  let exitMove = 0, floorRest = 0;
  function camera() {
    if (b4) { const k = seg === 3 ? (stacked ? sstep(0.3, 0.6, xeNow) : sstep(WX.spread[0], WX.spread[1], xeNow)) : 0; layouts[4].s = b4.s * lerp(1, b4.z, k); layouts[4].cx = lerp(b4.cx, W / 2, k); }
    const a = layouts[seg], b = layouts[seg + 1];
    const L = { cx: lerp(a.cx, b.cx, mE), cy: lerp(a.cy, b.cy, mE) };
    scale = [a.s, b.s];
    const el = lerp(CAM[seg][0], CAM[seg + 1][0], mE) + (reducedMQ.matches ? 0 : mouse.y * 0.07);
    const az = lerp(CAM[seg][1], CAM[seg + 1][1], mE) + (reducedMQ.matches ? 0 : mouse.x * 0.122);
    const tc = [lerp(CENTER[seg][0] * a.s, CENTER[seg + 1][0] * b.s, mE), lerp(CENTER[seg][1] * a.s, CENTER[seg + 1][1] * b.s, mE), 0];
    target = tc;
    eye = [tc[0] + Math.sin(az) * Math.cos(el) * CAM_D, tc[1] + Math.sin(el) * CAM_D, tc[2] + Math.cos(az) * Math.cos(el) * CAM_D];
    lookAt(view, eye, target);
    const frust = (cy) => { perspective(proj, FOV, W / H, 0.1, 40, (L.cx / W) * 2 - 1, 1 - (cy / H) * 2); mul(vp, proj, view); };
    frust(L.cy);
    exitMove = 0;
    if (seg === 3 && xNow > 0) {
      const f = project(0, Y_FLOOR * layouts[4].s, 0).y;
      floorRest = b4 ? L.cy + (f - L.cy) * b4.s / layouts[4].s : f;
      const shift = stacked ? tallMove() : (H * FLOOR_END() - f) * sstep(WX.cam[0], WX.cam[1], xeNow);
      frust(L.cy + shift);
      exitMove = f + shift - floorRest;
    }
  }
  const HEAD_GAP = () => 44 * Math.max(1, W / 1920);
  const SEAM = () => stacked ? 0 : (U_CHK + 6 + (short ? 24 : 48)) * remK;
  const PAPER_GAP = () => 32 * remK;
  const tallTop = () => navH + 24 * remK;
  const tallFoot = (br) => br.lb > 0 ? br.lb : br.hb;
  const tallMove = () => { const br = beatRects[4]; return br ? (tallTop() - br.t) * sstep(EXIT.tall.cam[0], EXIT.tall.cam[1], xeNow) : 0; };
  const paperRow = (top) => { const tk = top + 28 * remK, rec = tk + 15 * remK, day = rec + 12 * remK; return { tk, rec, day, cap: Math.round(Math.min(day + dayH + 16 * remK, H - paperCapH - 2)) }; };
  const headH = () => { const br = beatRects[4]; return br ? Math.max(0, br.hb - br.ht) : 0; };
  const FLOOR_END = (fr = floorRest) => {
    if (stacked) {
      const br = beatRects[4], above = 22 * remK;
      const below = (br ? Math.max(0, br.hb - fr) : band4() + 10 + headH()) + PAPER_GAP() + 20 * remK + paperCapH;
      return clamp((navH + Math.max(22, (H - navH - above - below) * 0.46) + above) / H, 0.25, 0.8);
    }
    const above = HEAD_GAP() + SEAM() + headH(), below = capRoom();
    if (short) return Math.max((navH + 22 + above) / H, Math.min(0.76, 1 - below / H));
    return Math.min(1 - below / H, (navH + Math.max(22, (H - navH - above - below) * 0.46) + above) / H);
  };
  const capRoom = () => (U_DAY + 16) * remK + Math.max(14, ...(lab.days || []).map(l => l.h || 0)) + paperCapH + 12;
  const XHOLD = 0.6, xPostOf = (x) => stacked && W < 600 ? x : clamp((x - XHOLD) / (1 - XHOLD), 0, 1), xPost = () => xPostOf(xNow);
  const EXIT = { wide: { copy: [0.1, 0.22], paper: [0.12, 0.5] }, tall: { cam: [0.3, 0.56], paper: [0.1, 0.3], row: [0.26, 0.42], ink: [0.42, 0.52] } };
  const WX = { cam: [0, 0.5], fold: [0.05, 0.32], spread: [0.2, 0.48] };
  const foldE = () => stacked ? sstep(0.02, 0.3, xeNow) : sstep(WX.fold[0], WX.fold[1], xeNow), flY = () => lerp(yK(Y_FL), Y_FLOOR + 0.02, foldE());
  const sealOf = (c) => clamp((xeNow - 0.03 - 0.12 * c / Math.max(1, NCOL - 1)) / 0.1, 0, 1);
  const CG_T = 0.3, cgLin = new Float32Array(24), cgArr = new Float32Array(24);
  const cgTarget = (c) => seg === 3 && SESSIONS[c].above && SESSIONS[c].confirmed && colMorph(c) >= 0.78 ? 1 : 0;
  function stepGreen(dt, snap) {
    let busy = false;
    for (let c = 0; c < NCOL && c < 24; c++) {
      const t = cgTarget(c), v = cgLin[c];
      cgLin[c] = snap ? t : t > v ? Math.min(t, v + dt / CG_T) : Math.max(t, v - dt / CG_T);
      cgArr[c] = sstep(0, 1, cgLin[c]);
      if (cgLin[c] !== t) busy = true;
    }
    return busy;
  }
  let greenBusy = false;

  const hash = (n) => { let x = Math.imul(n ^ 0x9e3779b9, 0x85ebca6b); x ^= x >>> 13; x = Math.imul(x, 0xc2b2ae35); x ^= x >>> 16; return (x >>> 0) / 4294967296; };
  const EMIT = 0.92, T_IN = 0.55, T_SEG = 0.46, T_DWELL = 0.15, T_COUNCIL = 0.34, T_SNAP = 0.22, T_DROP = 0.42, T_FALL = 1.6;
  const ARR = []; { let t = T_IN; for (let g = 0; g < 6; g++) { ARR.push(t); t += (g === COUNCIL ? T_COUNCIL : T_DWELL) + T_SEG; } }
  const T_DEC = ARR[COUNCIL] + T_COUNCIL, T_REC = ARR[5] + T_DWELL + T_SNAP + T_DROP;
  const rejected = (n) => hash(n * 7 + 3) < 0.2;
  const C = { ivory: [0.96, 0.95, 0.92], green: [0.31, 0.80, 0.58], red: [0.85, 0.40, 0.36], khaki: [0.68, 0.65, 0.56] };
  function councilPulse(T) {
    const nNow = Math.floor((T - T_DEC) / EMIT);
    if (nNow < 0) return { k: 0, rej: false };
    const dt = T - (nNow * EMIT + T_DEC);
    return { k: Math.exp(-dt / 0.3), rej: rejected(nNow), dt };
  }
  function ledger(T) {
    const out = [];
    for (let n = Math.floor((T - T_REC) / EMIT); n >= 0 && out.length < LEDGER_N + 1; n--) if (!rejected(n)) out.push(n);
    return out;
  }
  function actorsFor(sc, T, out) {
    const put = (id, x, y, z, col, a, shape, size, glow, aux) => { out.set(id, { p: [x, y, z], col, a, shape, size, glow: glow || 0, aux: aux || 0 }); };
    if (sc === 0) {
      [0, 2, 4].forEach((k, j) => { const th = 1.1 + j * 2.1 + T * ORBITS[k][3] * 1.6; const p = onLoop(OB[k], ORBITS[k][0], th, 0); put('p' + j, p[0], p[1], p[2], C.green, 0.95, 1, 9, 0.8, 0); });
    } else if (sc === 1) {
      for (let j = 0; j < 3; j++) { const th = 0.6 + j * TAU / 3 + T * RINGS[0][3]; const p = onLoop(RB[0], RINGS[0][0], th, 0); put('p' + j, p[0], p[1], p[2], C.green, 1, 1, 9, 0.8, 0); }
    } else if (sc === 2) {
      for (let j = 0; j < 3; j++) {
        const per = 6.0, ph = ((T / per + j / 3) % 1 + 1) % 1, cyc = Math.floor(T / per + j / 3);
        const x0 = (hash(cyc * 3 + j) - 0.5) * 1.0, z0 = (hash(cyc * 5 + j) - 0.5) * 0.6;
        let x, y, z, aux = 0, a = 1;
        if (ph < 0.5) { const u = ph / 0.5; y = lerp(PL_Y(0) + 0.08, 0.02, u); x = x0 + Math.sin(T * 2.3 + j) * 0.05; z = z0 + Math.cos(T * 1.9 + j) * 0.04; a = sstep(0, 0.08, u); }
        else {
          const u = (ph - 0.5) / 0.5, st = Math.min(3, Math.floor(u * 4)), f = sstep(0.62, 1, u * 4 - st);
          y = lerp(PL_Y(4 + st) + 0.02, PL_Y(Math.min(7, 5 + st)) + 0.02, st < 3 ? f : 0); x = Math.round(x0 * 8) / 8; z = Math.round(z0 * 6) / 6;
          aux = st < 3 ? 0 : sstep(0.15, 0.55, u * 4 - 3); a = 1 - sstep(0.9, 1, u);
        }
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
          if (inG < 0.12) size = 11 + 4 * (1 - inG / 0.12);
          if (rej && age >= T_DEC) {
            const tf = age - T_DEC; if (tf > T_FALL) continue;
            x = LX + 0.04 + 0.78 * (1 - Math.exp(-tf * 2.4)); y = GATE_Y[COUNCIL] + tf * 0.05 - 0.52 * tf * tf; z = tf * 0.08;
            col = C.red; a = 1 - sstep(0.5, T_FALL, tf); shape = 0; size = 7; glow = 0.9;
          } else if (age >= ARR[5]) {
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
    } else {
      const rY = Y_FLOOR - l4(U_REC), k4 = remK / ptK, s4 = layouts[4].s, P = BP * colK, bh = 0.84 * P;
      const dev = (v) => Math.max(2, 2 * Math.round(v * dpr / 2)), dimH = hoverScene === 4 ? hoverOn : 0;
      const hPx = Math.abs(project(0, Y_FLOOR * s4, 0).y - project(0, (Y_FLOOR + bh) * s4, 0).y);
      const bwW = clamp(bh, 0.075, 0.12), wPx = Math.abs(project((COL_X(0) + bwW / 2) * s4, Y_FLOOR * s4, 0).x - project((COL_X(0) - bwW / 2) * s4, Y_FLOOR * s4, 0).x);
      const wD = dev(wPx), hD = dev(hPx), bs = wD / (dpr * ptK), ba = hD / wD;
      const up = (x, y) => { const a = project(x * s4, y * s4, 0).x, b = project((x + 0.01) * s4, y * s4, 0).x, t = project(x * s4, Y_FLOOR * s4, 0).x; return x + (t - a) * 0.01 / (b - a || 1); };
      for (let c = 0; c < NCOL; c++) {
        const x = COL_X(c), ss = SESSIONS[c];
        put('r' + c, x, rY, 0, C.ivory, 0.95, 2, 15 * k4, 0, 0);
        if (ss.confirmed) { const y = yK(Y_CTOP) + 0.1; put('t' + c, up(x, y), y, 0, C.green, 0.95, 3, 12 * k4, 0.5, 0); }
        const g = cgArr[c] * (1 + 0.3 * hovFor(4, c)) * (1 - 0.45 * dimH * (1 - hovFor(4, c)));
        if (!ss.above || g < 0.004) continue;
        for (let j = 0; j < NB; j++) { const y = Y_FLOOR + (j + 0.42) * P; put('b' + (c * NB + j), up(x, y), y, 0, C.green, g * (0.62 + 0.38 * j / Math.max(1, NB - 1)), 5, bs, 0, ba); }
        const yu = Y_FLOOR + (NB + 0.58) * P; put('u' + c, up(x, yu), yu, 0, C.green, g * 0.66, 6, bs, 0, ba);
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
    const keyOf = (id) => {
      const n = parseInt(id.slice(1), 10);
      if (seg === 3 && (id[0] === 'r' || id[0] === 's' || id[0] === 't')) return (n + (id[0] === 't' ? 0.55 : id[0] === 's' ? 0.4 : 0.3)) / (NCOL + 0.55);
      return id[0] === 'r' ? 0.25 + 0.5 * (n / 11) : id[0] === 't' ? 0.7 : 0.35;
    };
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
      const k = seg === 3 && (id[0] === 's' || id[0] === 't') ? sstep(0.6, 0.95, colMorph(parseInt(id.slice(1), 10))) : 1;
      emit([B.p[0] * sB, (B.p[1] + rise) * sB, B.p[2] * sB], B.col, B.a * clamp(t * 1.4 - 0.2, 0, 1) * k, B.shape, B.size, B.glow, B.aux);
    });
  }
  const colMorph = (c) => seg === 3 ? stag(mRaw, (c + 0.22) / (NCOL + 0.55)) : 1;

  const LOOP_N = LITE ? 72 : 112;
  const loopAngles = (az) => Array.from({ length: LOOP_N }, (_, j) => az - j / LOOP_N * TAU);
  const LIMB_N = 128, limbPts = Array.from({ length: LIMB_N }, () => [0, 0, 0]);
  const GEO = new Map(), geo = (k, fn) => { let g = GEO.get(k); if (!g) GEO.set(k, g = fn()); return g; };
  function linesFor(sc, T, out) {
    const put = (id, pts, closed, col, a, w, key, dy, dash) => out.set(id, { pts, closed, col, a, w: w || 1, key: key == null ? 0.5 : key, dy: dy || 0, dash: dash || 0 });
    if (sc === 0) {
      ORBITS.forEach((o, k) => { const pts = geo('o0' + k, () => Array.from({ length: LOOP_N }, (_, j) => onLoop(OB[k], o[0], j / LOOP_N * TAU, 0))); put('o' + k, pts, true, k === 0 ? C.green : k === KH_ORB ? C.khaki : C.ivory, k === 0 ? 0.34 : k === KH_ORB ? 0.55 : 0.16, 1 / dpr, 0.12 + 0.5 * k / 6); if (k === KH_ORB) put('kg', pts, true, C.khaki, 0.07, 6, 0.12 + 0.5 * k / 6); });
      const k = clamp(scale[0] / CAM_D, 0, 0.9), rl = Math.sqrt(1 - k * k), e = [eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]], el = Math.hypot(e[0], e[1], e[2]) || 1;
      const Rv = [view[0], view[4], view[8]], Uv = [view[1], view[5], view[9]], c = [e[0] / el * k, e[1] / el * k, e[2] / el * k];
      const limb = limbPts;
      for (let j = 0; j < LIMB_N; j++) { const a = j / LIMB_N * TAU, ca = Math.cos(a) * rl, sa = Math.sin(a) * rl, q = limb[j]; q[0] = c[0] + Rv[0] * ca + Uv[0] * sa; q[1] = c[1] + Rv[1] * ca + Uv[1] * sa; q[2] = c[2] + Rv[2] * ca + Uv[2] * sa; }
      put('lg', limb, true, C.green, 0.075, 26, 0.02);
      put('lr', limb, true, C.ivory, 0.045, 1, 0.02);
    } else if (sc === 1) {
      RINGS.forEach((o, k) => {
        const pts = geo('o1' + k, () => Array.from({ length: LOOP_N }, (_, j) => onLoop(RB[k], o[0], j / LOOP_N * TAU, 0)));
        put('o' + k, pts, true, k === 0 ? C.green : k < 3 ? C.ivory : C.khaki, (k === 0 ? 0.42 : k < 3 ? 0.24 : 0.34) * (1 + 1.6 * hovFor(1, k)), 1 + 0.6 * hovFor(1, k), 0.15 + 0.6 * k / 6, 0, k === 0 ? 0 : k < 3 ? 1 : 2);
      });
      const a0 = 2.1 + T * RINGS[0][3] * 1.7, arc = [];
      for (let j = 0; j <= 22; j++) arc.push(onLoop(RB[0], RINGS[0][0], a0 + j / 22 * 1.05, 0));
      put('kl', arc, false, C.green, 0.13, 7, 0.2);
      put('kc', arc, false, C.green, 0.55, 1.3, 0.2);
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
      put('hz', [[LEDGER_X0 - 0.14, Y_LEDGER, 0], [LEDGER_X0 + LEDGER_DX * (LEDGER_N - 0.2), Y_LEDGER, 0]], false, C.ivory, 0.3, 1, 0.9);
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
      const step = COL_SPAN / NCOL, rY = Y_FLOOR - l4(U_REC), yN = Y_FLOOR - l4(U_NAV), tk = l4(U_TICK), gap = l4(2), nav = 1 - sstep(0.06, 0.3, xeNow);
      const xR = COL_X(NCOL - 1) + l4(12);
      put('hz', [[COL_X(0) - step / 2, Y_FLOOR, 0], [xR, Y_FLOOR, 0]], false, C.ivory, 0.42, 1, 0.9);
      const fy = flY(); put('fl', [[floorL, fy, 0], [xR, fy, 0]], false, C.green, 0.85 * (1 - sstep(0.8, 1, foldE())), 1, 0.9);
      const dash = l4(4), per = l4(9);
      SESSIONS.forEach((ss, c) => {
        const x = COL_X(c), k = (c + 0.1) / (NCOL + 0.55);
        if (c < NCOL - 1) put('hl' + c, [[x + l4(8.5), rY, 0], [x + step - l4(8.5), rY, 0]], false, C.ivory, 0.45, 1, k);
        const ne = Math.min(x + step / 2, xR), nv = []; for (let u = x - step / 2; u < ne - dash * 0.5; u += per) nv.push([u, yN, 0], [Math.min(u + dash, ne), yN, 0]);
        put('nv' + c, nv, 'pairs', C.ivory, 0.3 * nav, 1, k);
        const d = ss.regime === 'premium' ? 1 : -1;
        put('rt' + c, [[x, yN + d * gap, 0], [x, yN + d * tk, 0]], false, C.ivory, 0.9 * nav, 1.6, k);
      });
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
    const emit = (A, B, t, cr, cg, cb, a, w) => {
      a *= intro;
      if (a < 0.003) return;
      const P = A.pts, Q = B ? B.pts : null, n = P.length, pairs = A.closed === 'pairs';
      const segs = pairs ? n >> 1 : (A.closed ? n : n - 1);
      const dA = A.dy, dB = B ? B.dy : 0;
      const dash = (B && t >= 0.5) ? B.dash : A.dash;
      for (let j = 0; j < segs && nLine < N_LINE_MAX; j++) {
        if (dash === 1 && j % 3 === 2) continue;
        if (dash === 2 && j % 2) continue;
        const i0 = pairs ? 2 * j : j, i1 = pairs ? 2 * j + 1 : (j + 1) % n;
        for (let e = 0; e < 2; e++) {
          const i = e ? i1 : i0, p = P[i], d = o + e * 3;
          if (Q) { const q = Q[i]; lineData[d] = lerp(p[0] * sA, q[0] * sB, t); lineData[d + 1] = lerp((p[1] + dA) * sA, (q[1] + dB) * sB, t); lineData[d + 2] = lerp(p[2] * sA, q[2] * sB, t); }
          else { const s = A.s; lineData[d] = p[0] * s; lineData[d + 1] = (p[1] + dA) * s; lineData[d + 2] = p[2] * s; }
        }
        if (dash === 2) { const k = 0.28; for (let c = 0; c < 3; c++) lineData[o + 3 + c] = lineData[o + c] + (lineData[o + 3 + c] - lineData[o + c]) * k; }
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
    linB.forEach((B, id) => {
      if (linA.has(id)) return;
      const t = clamp(ease(stag(mRaw, B.key)), 0, 1);
      const k = seg === 3 && /^(rt|nv|hl)\d/.test(id) ? sstep(0.6, 0.95, colMorph(parseInt(id.slice(2), 10))) : 1;
      B.s = sB; emit(B, null, 0, B.col[0], B.col[1], B.col[2], B.a * t * k, B.w);
    });
  }

  const labelHost = story.querySelector('.story-labels');
  const SVGNS = 'http://www.w3.org/2000/svg';
  const leaders = document.createElementNS(SVGNS, 'svg');
  leaders.setAttribute('class', 'story-leaders'); leaders.setAttribute('aria-hidden', 'true'); leaders.setAttribute('focusable', 'false');
  if (labelHost) labelHost.appendChild(leaders);
  const labels = [], capOf = [];
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
    let node = null;
    if (opts.node) { node = document.createElementNS(SVGNS, 'circle'); node.setAttribute('r', '1.5'); node.setAttribute('class', 'story-node ' + (opts.cls || '')); leaders.appendChild(node); }
    const l = Object.assign({ el, path, scene, on: false, tr: '', d: '', w: 0, h: 0, y: 0 }, opts);
    l.node = node;
    if (opts.kind === 'cap') capOf[scene] = l;
    labels.push(l);
    return l;
  }
  const lab = {};
  if (labelHost) {
    const cap = (i, h) => label(i, `<span class="fc-h">${h}</span>`, { cls: 'cap', kind: 'cap' });
    cap(3, 'Illustrative');
    lab.rings = LC.slice(0, 1).map((c, k) => label(1, `<span class="k">${c[0]}</span><span class="n">${c[1]}</span><span class="st st-${c[2].toLowerCase()}">${c[2]}</span><span class="dt">${c[3]}: ${c[4]}</span>`,
      { cls: 'ring' + (k === 0 ? ' is-live' : ''), kind: 'list', group: k, leader: true, node: true, info: [`${c[0]} · ${c[3]}`, c[2], c[4]], anchorPx: (sc) => ringFlank(k, sc) }));
    lab.layers = LAYERS.map((l, p) => label(2, `<span class="k">${pad2(p + 1)}</span><span class="n">${l[0]}</span><span class="dt">${l[1]} · ${l[2]}</span>`,
      { cls: 'layer' + (p === 3 ? ' is-council' : ''), kind: 'list', group: p, leader: true, info: [`${pad2(p + 1)} · ${l[0]}`, l[1], `${l[2]} · ${p < 4 ? 'above' : 'below'} the boundary`], anchor: () => [PL_HX - 0.03, PL_Y(p) + hovFor(2, p) * 0.07, PL_HZ - 0.03] }));
    label(2, '<span class="n">Boundary</span><span class="dt">Intelligence decides above · execution is deterministic below</span>', { cls: 'bound', kind: 'list', leader: true, anchor: () => [PL_HX * 1.1 - 0.03, 0, PL_HZ * 1.12 - 0.03] });
    GATES.forEach((g, i) => label(3, `<span class="k">${pad2(i + 1)}</span><span class="n">${g}${i === COUNCIL ? ' · Council' : ''}</span>`, { cls: 'gate' + (i === COUNCIL ? ' is-council' : ''), kind: 'list', leader: true, anchor: () => [LX + GATE_HX, GATE_Y[i], 0] }));
    label(3, '<i class="lg-r"></i><span class="n">Rejected · falls away</span>', { cls: 'note', kind: 'list', leader: true, wide: true, anchor: () => [LX + 0.74, GATE_Y[COUNCIL] - 0.36, 0] });
    label(3, '<i class="lg-b"></i><span class="n">Records · hash-linked</span>', { cls: 'note', kind: 'list', leader: true, wide: true, anchor: () => [LEDGER_X0 + LEDGER_DX * 3.5, Y_LEDGER + 0.05, 0] });
    const esc = (t) => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    lab.days = SESSIONS.map((s, c) => label(4, `<span class="k">${s.day}</span><span class="dt">Day ${s.day} · ${s.regime} · ${esc(valueT(s))} · ${s.confirmed ? 'broker-confirmed' : 'confirmation not stated'}</span>`,
      { cls: 'day' + (s.regime === 'premium' ? ' is-prem' : ''), kind: 'tag', group: c, side: 's', keep: true, col: c, dy: U_DAY - 6, info: [`Day ${s.day}`, capw(s.regime), `${s.above ? 'Above' : 'Not above'} the ${FLOOR_T} floor (${esc(valueT(s))}) · ${s.confirmed ? 'confirmed against the broker’s records' : 'confirmation not stated'}`], anchor: () => [COL_X(c), Y_FLOOR, 0] }));
    lab.floor = label(4, `<span>Floor</span> <span class="u">${FLOOR_T}</span>`, { cls: 'floor', kind: 'tag', floor: true, out: [0.2, 0.3], anchor: () => [COL_X(0) - COL_SPAN / NCOL * 0.5, flY(), 0], side: 'nw' });
    lab.hedge = label(4, '<span>Above the floor</span> <span class="h">Exact value not published</span>', { cls: 'hedge', kind: 'tag', hedge: true, out: [0.2, 0.3], anchor: () => [COL_X(0) - COL_SPAN / NCOL * 0.5, flY(), 0], side: 'nw' });
    lab.zero = label(4, '<span class="u">0</span>', { cls: 'floor zero', kind: 'tag', anchor: () => [COL_X(0) - COL_SPAN / NCOL * 0.5, Y_FLOOR, 0], side: 'nw' });
    lab.nav = label(4, 'NAV', { cls: 'navtag', kind: 'tag', out: [0.05, 0.22], anchor: () => [COL_X(0) - COL_SPAN / NCOL * 0.5, Y_FLOOR - l4(U_NAV), 0], side: 'w' });
    lab.key = label(4, `<span>${capw(words(N_PREM))} premium, ${words(N_DISC)} discount.</span> <span>One block per basis point.</span>`, { cls: 'key', kind: 'tag', key: true, out: [0.05, 0.22], anchor: () => [COL_X(0), Y_FLOOR, 0], side: 's' });
  }
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
      const brS = beatRects[hot.scene];
      insp.style.maxWidth = hot.kind !== 'list' || !(listX > 0) ? '' : stacked ? Math.max(160, Math.min(260, listX - 10 - gutter * 0.5)) + 'px'
        : short && brS && brS.r > 0 ? Math.max(160, Math.min(260, listX - 16 - (brS.r + 12))) + 'px' : '';
      inspW = insp.offsetWidth; inspH = insp.offsetHeight;
    }
    inspFor = hot;
    stage.classList.toggle('is-pointing', !!hoverPtr);
    requestFrame();
  }
  const lastPtr = { x: NaN, y: NaN };
  const moved = (e) => e.clientX !== lastPtr.x || e.clientY !== lastPtr.y;
  labels.forEach(l => {
    if (l.group == null) return;
    const on = () => { hoverFocus = { scene: l.scene, idx: l.group }; setHover(); };
    const off = () => { hoverFocus = null; setHover(); };
    l.el.addEventListener('focus', on); l.el.addEventListener('blur', off);
    l.el.addEventListener('pointerenter', e => { if (e.pointerType === 'touch' || !moved(e)) return; hoverPtr = { scene: l.scene, idx: l.group }; setHover(); });
    l.el.addEventListener('pointerleave', e => { if (e.pointerType === 'touch' || !moved(e)) return; hoverPtr = null; setHover(); });
  });
  let labelScene = -1, labA = 0, labOnT = 0, outScene = -1, outA = 0, outA0 = 0, outT = 0;
  const LAB_IN = 160, LAB_OUT = 110;
  function sceneOfLabels() {
    if (lost || !ready || tiny) return -1;
    const red = reducedMQ.matches, ci = clamp(Math.round(red ? sNow : copyS), 0, 4);
    if (!red && Math.abs(copyS - ci) > HOLD + 0.01) return -1;
    const sm = seg + mRaw;
    return Math.abs(sm - ci) < 0.02 ? ci : -1;
  }
  const plainLab = (l) => (l.scene === 2 || l.scene === 4) && W < 600 && coarseMQ.matches;
  const vis = (l) => {
    if (l.scene !== labelScene) return 0;
    if (l.scene !== 4 || l.keep) return labA;
    const o = l.out || OUT4, w = xeNow >= (o[0] + o[1]) / 2 ? 1 : 0, x = l.xo = (l.xo || 0) + clamp(w - (l.xo || 0), -kF, kF);
    if (x !== w) fading = true;
    return labA * (1 - x);
  };
  const OUT4 = [0.04, 0.2];
  const colIn = (c) => (reducedMQ.matches ? sNow : copyS) >= 4 ? 1 : seg === 3 ? clamp(ease(stag(mRaw, (c + 0.55) / (NCOL + 0.55))), 0, 1) : 0;
  let tabScene = -1, shownHasInsp = null;
  const FLANK = { x: 0, y: 0 };
  function ringFlank(k, sc) {
    const c = project(0, 0, 0), cx = c.x, cy = c.y, want = -0.95 + 1.9 * k / 5;
    let best = 1e9, bx = cx, by = cy;
    for (let j = 0; j < 96; j++) {
      const q = onLoop(RB[k], RINGS[k][0], j / 96 * TAU, 0), p = project(q[0] * sc, q[1] * sc, q[2] * sc);
      if (p.x <= cx) continue;
      const d = Math.abs(Math.atan2(p.y - cy, p.x - cx) - want);
      if (d < best) { best = d; bx = p.x; by = p.y; }
    }
    FLANK.x = bx; FLANK.y = by; return FLANK;
  }
  function flankAlts(k, sc, x0, y0) {
    const c = project(0, 0, 0), cx = c.x, out = [];
    for (let j = 0; j < 96; j++) {
      const q = onLoop(RB[k], RINGS[k][0], j / 96 * TAU, 0), p = project(q[0] * sc, q[1] * sc, q[2] * sc);
      if (p.x > cx) out.push([p.x, p.y, Math.hypot(p.x - x0, p.y - y0)]);
    }
    return out.sort((u, v) => u[2] - v[2]);
  }
  function placeLabels() {
    if (!labelHost) return;
    const settledScene = labelScene >= 0 && (reducedMQ.matches ? xNow : xPost()) < 0.4 ? labelScene : -1;
    if (settledScene !== tabScene) {
      const was = tabScene; tabScene = settledScene;
      labels.forEach(l => { if (l.group == null || (l.scene !== was && l.scene !== tabScene)) return; const on = l.scene === tabScene && !plainLab(l); l.el.tabIndex = on ? 0 : -1; if (on) l.el.removeAttribute('aria-hidden'); else l.el.setAttribute('aria-hidden', 'true'); });
      if (document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('story-lab') && document.activeElement.tabIndex < 0) stage.focus({ preventScroll: true });
      if (hoverPtr && hoverPtr.scene !== tabScene) { hoverPtr = null; setHover(); }
    }
    const tagTop = navH + barH + 6;
    const listCol = [];
    labels.forEach(l => {
      if (l.scene === outScene) { l.a = l.on ? outA : 0; return; }
      const a = vis(l);
      let on = a > 0.01 && !((stacked || short) && l.wide) && !(frameTiny[l.scene] && (l.kind !== 'cap' || !l.scene) && !l.hedge);
      if (l.key && !keyH) on = false;
      if (on && l.col != null) on = colIn(l.col) > 0.5;
      let x = 0, y = 0, tr = '';
      if (on && l.kind === 'cap') {
        const L = layouts[l.scene];
        if (stacked) { x = gutter; y = navH + barH + 4; }
        else { x = Math.min(L.rect[2] + roomOf[l.scene], contR) - l.w; y = H - barH - l.h - 6; }
        x = clamp(x, 6 + safeL, W - l.w - 6 - safeR);
        tr = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      } else if (on) {
        const sc = layouts[l.scene].s, pp = l.anchorPx ? l.anchorPx(sc) : (a => project(a[0] * sc, a[1] * sc, a[2] * sc))(l.anchor());
        l.ax = pp.x; l.ay = pp.y;
        if (l.kind === 'list') listCol.push(l);
        else {
          x = pp.x; y = pp.y;
          const sd = l.side || 'c';
          if (sd.includes('w')) x -= l.w + 8; else if (sd.includes('e')) x += 8; else x -= l.w / 2;
          if (sd.includes('n')) y -= l.h + 6; else if (sd.includes('s')) y += 6; else y -= l.h / 2;
          y += l.dy || 0;
          if (l.key) { const d = lab.days && lab.days[0]; x = l.ax - (d ? d.w : 0) / 2; y = l.ay + U_DAY * remK + (d ? d.h : 0) + 8 * remK; }
          if (l.hedge) {
            y -= floorH + hedgeGap();
            const fl = l.ax - floorW - 8;
            const beside = hedgeBeside, flush = !beside && x < 6 + safeL;
            if (flush !== !!l.flush) { l.flush = flush; l.el.classList.toggle('is-flush', flush); lab.floor.el.classList.toggle('is-flush', flush); }
            if (beside) { x = fl - 12 - l.w; y = Math.max(l.ay - floorH - 6, stacked ? tagTop + capH[4] : navH + 6); }
            else if (flush) {
              x = Math.max(6 + safeL, fl);
              const t = project(COL_X(0) * sc, (flY() + yK(Y_CTOP) + 0.1 - yK(Y_FL)) * sc, 0);
              if (x + l.w > t.x - 10 * remK) y = Math.min(y, t.y - 7 * remK - 6 - l.h);
            }
          }
          x = clamp(x, 6 + safeL, W - l.w - 6 - safeR);
          y = Math.max(y, stacked ? tagTop + (l.hedge ? 0 : capH[l.scene]) : navH + 6);
          if (l.sum && y + l.h > project(0, (Y_FLOOR + H_COL + 0.2) * layouts[4].s, 0).y - 4) on = false;
          l.y = y;
          tr = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
        }
      }
      l.a = on ? a : 0;
      if (on && tr && tr !== l.tr) l.el.style.transform = l.tr = tr;
    });
    if (listCol.length) {
      listCol.sort((a, b) => a.ay - b.ay);
      const sc = listCol[0].scene, L = layouts[sc];
      const maxW = Math.max(...listCol.map(l => l.w)), colX = stacked ? W - Math.max(gutter * 0.5, safeR + 6) - maxW : Math.min(L.rect[2] + 22, Math.min(contR, W - safeR - 6) - maxW);
      const gap = Math.max(...listCol.map(l => l.h)) + (stacked || short ? 2 : 6), top = navH + (stacked ? barH + capH[sc] + 22 : short ? 8 : 14);
      let bottom = stacked ? beatRects[sc].t - 10 - (lifted ? LIFT_AIR : 0) : H - barH - capH[sc] - (short ? 12 : 16);
      if (!stacked && capH[sc] && capOf[sc] && (listCol.length - 1) * gap + listCol[listCol.length - 1].h > bottom - top) { bottom = H - barH - 12; capOf[sc].a = 0; }
      let y = -1e9;
      listCol.forEach(l => { l.y = Math.max(l.ay - l.h / 2, y + gap); y = l.y; });
      const over = y + listCol[listCol.length - 1].h - bottom;
      if (over > 0) { listCol.forEach(l => { l.y -= over; }); }
      for (let j = 1; j < listCol.length; j++) if (listCol[j].y < listCol[j - 1].y + gap) listCol[j].y = listCol[j - 1].y + gap;
      if (listCol[0].y < top) { const d = top - listCol[0].y; listCol.forEach(l => { l.y += d; }); }
      if (stacked) listCol.forEach(l => { if (l.y + l.h > beatRects[sc].t - 8) l.a = 0; });
      if (sc === 1) for (let pass = 0; pass < 2; pass++) listCol.forEach(l => {
        if (!l.a) return;
        const ly = l.y + l.h / 2, ex = colX - 20;
        const clear = (x, y) => listCol.every(o => o === l || !o.a || segDist(o.ax, o.ay, x, y, ex, ly) >= 6);
        if (clear(l.ax, l.ay)) return;
        const alt = flankAlts(l.group, L.s, l.ax, l.ay).find(q => q[2] < 60 && clear(q[0], q[1]));
        if (alt) { l.ax = alt[0]; l.ay = alt[1]; }
      });
      listCol.forEach(l => {
        if (!l.a) return;
        const tr = `translate(${colX.toFixed(1)}px, ${l.y.toFixed(1)}px)`;
        if (tr !== l.tr) l.el.style.transform = l.tr = tr;
        if (l.path) {
          const ly = l.y + l.h / 2, ex = colX - 6;
          const d = `M${l.ax.toFixed(1)} ${l.ay.toFixed(1)} L${(ex - 14).toFixed(1)} ${ly.toFixed(1)} L${ex.toFixed(1)} ${ly.toFixed(1)}`;
          if (d !== l.d) l.path.setAttribute('d', l.d = d);
          if (l.node) { const c = `${l.ax.toFixed(1)},${l.ay.toFixed(1)}`; if (c !== l.nc) { l.nc = c; l.node.setAttribute('cx', l.ax.toFixed(1)); l.node.setAttribute('cy', l.ay.toFixed(1)); } }
        }
      });
      listX = colX; listBottom = Math.max(...listCol.map(l => l.a ? l.y + l.h : 0));
    }
    labels.forEach(l => {
      const on = l.a > 0;
      if (on !== l.on) { l.on = on; l.el.classList.toggle('is-on', on); if (l.path) l.path.classList.toggle('is-on', on); if (l.node) l.node.classList.toggle('is-on', on); }
      const ov = l.a.toFixed(2);
      if (ov !== l.ov) { l.ov = ov; l.el.style.opacity = ov; if (l.path) l.path.style.opacity = ov; if (l.node) l.node.style.opacity = ov; }
    });
    const io = !!inspFor && inspFor.on && Math.abs(sTarget - sNow) <= 0.02;
    if (io !== shownHasInsp) { shownHasInsp = io; labelHost.classList.toggle('has-insp', io); insp.classList.toggle('is-on', io); }
    if (io) {
      let x, y;
      if (stacked) {
        x = gutter * 0.5;
        y = inspFor.kind === 'list' ? (beatRects[inspFor.scene] || { t: H }).t - inspH - 12 : navH + barH + 8;
        y = clamp(y, navH + barH + (inspFor.kind === 'list' ? capH[inspFor.scene] : 0) + 8, H - inspH - 8);
      }
      else if (inspFor.kind === 'list') {
        const lim = H - barH - inspH - 8, br = beatRects[inspFor.scene] || { r: 0, t: H };
        x = listX; y = listBottom + 18;
        if (y > lim || x + inspW > W - 8) {
          x = listX - 16 - inspW; y = clamp(inspFor.y + inspFor.h / 2 - inspH / 2, navH + 8, lim);
          if (x < br.r + 12 && y + inspH > br.t - 8 && navH + 8 + inspH <= br.t - 8) { x = gutter; y = navH + 8; }
        }
      }
      else { const sc = layouts[inspFor.scene].s, p = project(COL_X(inspFor.group) * sc, (Y_FLOOR + H_COL + 0.24) * sc, 0); x = p.x - inspW / 2; y = p.y - inspH - 12; }
      x = clamp(x, 8, W - inspW - 8); y = clamp(y, navH + 8, H - (stacked ? 0 : barH) - inspH - 8);
      const tr = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
      if (tr !== inspTr) insp.style.transform = inspTr = tr;
    }
  }
  let listX = 0, listBottom = 0, inspTr = '';
  function hitTest(px, py) {
    const cur = labelScene;
    if (cur < 0 || (reducedMQ.matches ? xNow : xPost()) > 0.3) return null;
    const sc = layouts[cur].s;
    if (cur === 1) {
      let best = null, bd = 16;
      for (let k = 0; k < (lab.rings ? lab.rings.length : 0); k++) {
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
      const hw = W < 600 ? 0.13 : 0.1, under = W < 600 ? (U_DAY + 14) * remK : 24;
      for (let c = 0; c < NCOL; c++) {
        const a = project((COL_X(c) - hw) * sc, Y_FLOOR * sc, 0), ax = a.x, ay = a.y;
        const b = project((COL_X(c) + hw) * sc, (Y_FLOOR + H_COL * colK + 0.15) * sc, 0);
        if (px > ax && px < b.x && py < ay + under && py > b.y) return { scene: 4, idx: c };
      }
    }
    return null;
  }
  const segDist = (px, py, ax, ay, bx, by) => { const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy || 1, t = clamp(((px - ax) * dx + (py - ay) * dy) / l2, 0, 1); return Math.hypot(px - ax - dx * t, py - ay - dy * t); };
  const inQuad = (px, py, q) => { let s = 0; for (let i = 0; i < 4; i++) { const [ax, ay] = q[i], [bx, by] = q[(i + 1) % 4], c = (bx - ax) * (py - ay) - (by - ay) * (px - ax); if (c !== 0) { if (s && Math.sign(c) !== s) return false; s = Math.sign(c); } } return true; };

  const beats = Array.from(story.querySelectorAll('.beat'));
  const idx = Array.from(story.querySelectorAll('.story-idx button'));
  const motionButton = story.querySelector('[data-story-motion]');
  const live = story.querySelector('[data-story-live]');
  idx.forEach((button, i) => button.addEventListener('click', () => goTo(i, true)));
  const bar = story.querySelector('.story-bar');
  const paper = story.querySelector('.story-paper');
  let shownLeaving = null, paperCapH = 0;
  const shown = beats.map(() => ({ op: '', tr: '', on: null, eo: '', w: '', bo: '' }));
  const beatLinks = beats.map(b => Array.from(b.querySelectorAll('a[href], button')));
  const unseen = (el) => !tiny && !!el.closest('.beat .body-lg') && (short || el.closest('.beat').classList.contains('is-tight'));
  let shownIdx = -1, shownAt = -2, shownScrolled = null, shownBar = '', shownPaper = '', shownFill = [];
  let paperH = 0, relay0 = false, relayReady = false, shownBarOff = null;
  let fadeT = 0, copyX = 0, fading = false, kF = 1;
  let leave4 = 1, barA = 1;
  let shownBl = '', shownClip = '';
  function syncIndex() {
    const ci = nearScene(sTarget);
    if (shownIdx === ci) return;
    shownIdx = ci;
    idx.forEach((button, i) => { const a = ci === i; button.classList.toggle('is-on', a); if (a) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current'); });
    beatLinks.forEach((list, i) => list.forEach(el => { if (i === ci && !unseen(el)) el.removeAttribute('tabindex'); else el.setAttribute('tabindex', '-1'); }));
    story.dataset.scene = String(ci);
  }
  function updateUI(now) {
    const red = reducedMQ.matches, xe = xeNow;
    const cs = red ? Math.round(sNow) : copyS;
    const ls = sceneOfLabels();
    if (ls !== labelScene) {
      const t = now || performance.now(), back = ls >= 0 && ls === outScene ? outA : 0;
      if (labelScene >= 0 && labA > 0 && !red) { outScene = labelScene; outA0 = labA; outT = t; } else if (back) outScene = -1;
      labelScene = ls; labOnT = t - back * LAB_IN; labA = back;
    }
    if (outScene >= 0) { outA = red || outScene === labelScene ? 0 : outA0 * (1 - clamp(((now || performance.now()) - outT) / LAB_OUT, 0, 1)); if (outA <= 0) outScene = -1; }
    if (labelScene >= 0) { labA = red ? 1 : clamp(((now || performance.now()) - labOnT) / LAB_IN, 0, 1); measureBeat(labelScene); } else labA = 0;
    const ov = Math.max(0, scrollY - storyTop - run - tail);
    const lean = stacked, X = stacked ? EXIT.tall : EXIT.wide;
    const tN = now || performance.now(), k = red || lost ? 1 : Math.min(1, (tN - fadeT) / 250), mid = (w) => xe >= (w[0] + w[1]) / 2 ? 1 : 0;
    fadeT = tN; kF = k;
    const br4 = beatRects[4] || { ht: 0, hb: 0 };
    const wideLift = lean ? 0 : (H * FLOOR_END() - HEAD_GAP() - SEAM() - br4.hb) * sstep(WX.cam[0], WX.cam[1], xe);
    const headFits = lean || br4.ht + wideLift >= navH + 14;
    const cw = headFits ? 0 : mid(X.copy);
    copyX += clamp(cw - copyX, -k, k);
    fading = copyX !== cw;
    const tMove = lean && xe > 0 ? tallMove() : 0;
    const s1 = storyTop + storyH - tail - scrollY;
    paperH = tail ? clamp(H - s1, 0, H) : 0;
    /* hc30r: the marker is §01's box and no more. §01 is shorter than the stage it covers, so the ink chapter after it
       (the lab) rises over the stage's foot too: the marker's top is §01's top, as it was, and it stops at §01's foot,
       where the bar turns to ink (site.js). Covered, the stage draws no more frames: the marker takes the foot's last place */
    if (paper) { const gap = Math.max(0, (shownCov ? tail : paperH) - sec1H), ph = Math.max(0, paperH - gap), v = ph.toFixed(1) + '/' + gap.toFixed(1); if (v !== shownPaper) { shownPaper = v; paper.style.height = ph.toFixed(1) + 'px'; paper.style.bottom = gap.toFixed(1) + 'px'; paper.style.visibility = ph > 0.5 ? 'visible' : 'hidden'; } }
    if (!relay0 && (relayReady || sNow > 0.3)) { relay0 = true; beats[0].classList.add('is-relay'); }
    beats.forEach((b, i) => {
      const d = Math.abs(cs - i), s = shown[i];
      let op, eo, w, bo;
      if (red) { op = cs === i ? 1 : 0; eo = w = bo = 1; }
      else ({ eo, w, bo, op } = relayAt(d));
      let dy = red ? 0 : Math.sign(i - cs) * 38 * Math.max(0, d - HOLD);
      if (i === 4 && xe > 0) {
        if (lean) dy += tMove;
        else if (headFits) dy += wideLift;
        else op *= 1 - copyX;
      }
      if (i === 4) {
        const room0 = (beatRects[4] ? beatRects[4].t : 0) + dy - navH;
        const t4 = !headFits && ov > 0 && (room0 <= 6 || ov >= room0 - 6 - Math.min(150, H * 0.2) / 2) ? 0 : 1;
        const clip = ov > 0 ? Math.max(0, Math.ceil(navH - ((br4.bt || 0) + dy - ov))) : 0, cl = clip ? `inset(${clip}px 0 0 0)` : '';
        if (cl !== shownClip) b.style.clipPath = shownClip = cl;
        leave4 += clamp(t4 - leave4, -k, k); if (leave4 !== t4) fading = true;
        op *= leave4; if (!red) dy -= (1 - leave4) * 14;
        if (shownBl !== '0') b.style.setProperty('--bl', shownBl = '0');
      }
      if (bo < 0.08) bo = 0;
      const o = op.toFixed(3), tr = `translate3d(0, ${dy.toFixed(1)}px, 0)`, e = eo.toFixed(3), ww = w.toFixed(3), bb = bo.toFixed(3);
      if (s.op !== o) b.style.opacity = s.op = o;
      const seen = o !== '0.000', rest = v => v === '0.000' || v === '1.000';
      if (seen && s.tr !== tr) b.style.transform = s.tr = tr;
      if (s.eo !== e && (seen || rest(e))) b.style.setProperty('--eo', s.eo = e);
      if (s.w !== ww && (seen || rest(ww))) b.style.setProperty('--w', s.w = ww);
      if (s.bo !== bb && (seen || rest(bb))) b.style.setProperty('--bo', s.bo = bb);
      const act = op * bo > 0.5;
      if (s.on !== act) b.classList.toggle('is-active', s.on = act);
      const gone = bo === 0;
      if (s.gone !== gone) b.classList.toggle('is-bo0', s.gone = gone);
    });
    syncIndex();
    const at = mRaw <= 0 ? seg : mRaw >= 1 ? seg + 1 : -1;
    if (at !== shownAt) { shownAt = at; if (at < 0) story.removeAttribute('data-at'); else story.dataset.at = at; }
    idx.forEach((button, i) => { const f = clamp(sNow - i + 0.5, 0, 1).toFixed(2); if (shownFill[i] !== f) button.style.setProperty('--fill', shownFill[i] = f); });
    if (shownScrolled !== sNow > 0.3) story.classList.toggle('is-scrolled', shownScrolled = sNow > 0.3);
    barA = tail && s1 <= barTop ? 0 : 1;
    const bo = barA.toFixed(3);
    if (bar && bo !== shownBar) { bar.style.opacity = shownBar = bo; bar.style.visibility = bo < 0.01 ? 'hidden' : ''; }
    const barOff = +bo < 0.01;
    if (barOff !== shownBarOff) { shownBarOff = barOff; idx.concat(motionButton || []).forEach(el => { if (barOff) el.setAttribute('tabindex', '-1'); else el.removeAttribute('tabindex'); }); }
    if (shownLeaving !== xe > 0.05) story.classList.toggle('is-leaving', shownLeaving = xe > 0.05);
    placeLabels();
  }

  let running = true, visible = true, paused = false, frameId = 0, t0 = performance.now(), simTime = 14.3, settledOnce = false, pointerDirty = false, ptr = null, firstFrame = -1;
  const PIXEL_BUDGET = 3840 * 2160, LITE_BUDGET = 3.0e6;
  function readingPoint() {
    if (!(lastP >= 0)) return null;
    if (lastP <= 1) { const u = lastP * TOTAL_U; return { u: Math.min(4, u), x: clamp((u - 4) / EXIT_U, 0, 1) }; }
    const ov = (lastP - 1) * run / Math.max(1, stageH);
    return ov < 1 ? { ov } : null;
  }
  function restore(k) {
    if (!k) return;
    const y = Math.round(storyTop + (k.u != null ? (k.u + k.x * EXIT_U) / TOTAL_U * run : run + k.ov * stageH));
    if (Math.abs(y - window.scrollY) > 1) window.scrollTo({ top: y, behavior: 'instant' });
    scrollY = y;
  }
  let tinyBack = null, tinyPlace = null;
  function pinnedPlace() {
    if (!(lastP === lastP)) { measureScroll(); scrollY = window.scrollY; sceneScroll(); }
    if (lastP <= 1) return { at: clamp(Math.round(Math.min(4, Math.max(0, lastP) * TOTAL_U)), 0, 4) };
    const ov = (lastP - 1) * run;
    return ov < stageH ? { at: 4 } : { below: ov - stageH };
  }
  const navNow = () => navPx() || navH;
  function staticPlace() {
    const y = window.scrollY, bottom = story.getBoundingClientRect().top + y + story.offsetHeight, nh = navNow();
    if (y + nh >= bottom) return { below: y - bottom };
    let at = 0;
    beats.forEach((b, i) => { if (b.getBoundingClientRect().top <= nh + 40) at = i; });
    return { at };
  }
  function placeTo(k) {
    const top0 = story.getBoundingClientRect().top + window.scrollY;
    let y;
    if (k.below != null) y = top0 + story.offsetHeight - tail + k.below;
    else if (tiny) y = k.at ? beats[k.at].getBoundingClientRect().top + window.scrollY - navNow() : top0;
    else { measureScroll(); y = sceneTop(k.at); }
    window.scrollTo({ top: Math.max(0, Math.round(y)), behavior: 'instant' });
  }
  function invalidate() {
    shown.forEach(s => { s.op = s.tr = s.eo = s.w = s.bo = ''; s.on = s.gone = null; });
    shownIdx = labelScene = tabScene = outScene = -1; shownAt = -2; shownBarOff = shownLeaving = shownScrolled = shownHasInsp = null;
    shownBar = shownPaper = inspTr = '';
    clearTall();
    labels.forEach(l => { l.tr = l.ov = l.d = l.nc = ''; l.on = null; });
  }
  function clearTall() { shownClip = ''; cv.style.opacity = ''; if (labelHost) labelHost.style.opacity = ''; if (beats[4]) beats[4].style.clipPath = ''; }
  function setTiny(on) {
    tiny = on;
    if (on) {
      stopFrames(); clearTimeout(idleTimer);
      root.classList.remove('story-compact', 'story-short'); root.classList.add('story-tiny'); clearLift(); setTail(0);
      beats.forEach(b => { b.style.opacity = b.style.transform = ''; ['--eo', '--w', '--bo'].forEach(v => b.style.removeProperty(v)); b.classList.remove('is-active', 'is-tight', 'is-snug', 'is-bo0'); });
      if (bar) bar.style.opacity = bar.style.visibility = '';
      if (paper) paper.style.height = paper.style.bottom = paper.style.visibility = '';
      clearTall();
      beatLinks.forEach(list => list.forEach(el => el.removeAttribute('tabindex')));
      hoverPtr = hoverFocus = null; setHover();
      stage.removeAttribute('tabindex');
      shownSettled = true; story.setAttribute('data-settled', '');
    } else {
      root.classList.remove('story-tiny');
      stage.tabIndex = 0;
      invalidate();
      shownSettled = false; story.removeAttribute('data-settled');
      settledOnce = false;
    }
  }
  function resize(force) {
    if (lost || !ready) return;
    const tn = window.innerHeight < 300;
    if (tn !== tiny) {
      const k = tiny ? (tinyPlace || staticPlace()) : pinnedPlace();
      setTiny(tn);
      if (tn) { placeTo(k); tinyPlace = k; return; }
      force = true; tinyBack = k;
    } else if (tiny) return;
    const w = stage.clientWidth, h = stage.clientHeight, r = window.devicePixelRatio || 1;
    const sized = force === true || w !== W || h !== H || r !== ratio || stackedMQ.matches !== stacked;
    const keep = tinyBack ? null : readingPoint();
    if (sized) {
      W = w; H = h; ratio = r;
      dpr = Math.min(3, r, Math.sqrt((LITE ? LITE_BUDGET : PIXEL_BUDGET) / Math.max(1, W * H)));
      ptK = Math.max(1, W / 1600);
      remK = Math.max(1, (parseFloat(getComputedStyle(root).fontSize) || 16) / 16);
      if (lab.days) lab.days.forEach(l => { l.dy = U_DAY * remK - 6; });
      cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr);
      gl.viewport(0, 0, cv.width, cv.height);
      leaders.setAttribute('viewBox', `0 0 ${W} ${H}`);
      keyOff = false;
      setModes();
    }
    measureScroll();
    if (sized) {
      fitScenes();
      if (keyH && dayPitch < 18) { keyOff = true; setModes(); measureScroll(); fitScenes(); }
      const t0 = tail; setTail(tailNow()); if (tail !== t0) measureScroll();
      publishGlobe();
    }
    if (tinyBack) { placeTo(tinyBack); tinyBack = null; scrollY = window.scrollY; }
    else restore(keep);
    sceneScroll();
    requestFrame();
  }
  let shownGlobe = null;
  function publishGlobe() {
    const L0 = layouts[0];
    const v = !(L0.cy > 0) || frameTiny[0] ? '' : `${L0.cx.toFixed(1)} ${(L0.cy + Math.max(0, storyTop - scrollY)).toFixed(1)} ${(L0.s * pxuOf(H)).toFixed(1)}`;
    if (v === shownGlobe) return;
    shownGlobe = v;
    if (v) root.dataset.globe = v; else delete root.dataset.globe;
    if (root.hasAttribute('data-globe-read') || !document.querySelector('.loader:not(.is-done)')) return;
    const st = root.style, [x, y, r] = v.split(' ');
    if (!v) { ['--globe-x', '--globe-y', '--globe-r'].forEach(k => st.removeProperty(k)); return; }
    st.setProperty('--globe-x', x + 'px'); st.setProperty('--globe-y', y + 'px'); st.setProperty('--globe-r', r + 'px');
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
    gl.uniform1f(u.u_spin, time * 0.07 + 0.6 + hand.off);
    gl.uniform1f(u.u_pr, dpr * ptK); gl.uniform1f(u.u_dist, CAM_D); gl.uniform1f(u.u_fogR, 1.7 * Math.max(scale[0], scale[1]));
    gl.uniform1f(u.u_maxpt, maxPt); gl.uniform1f(u.u_intro, intro); gl.uniform1f(u.u_gather, gather); gl.uniform1f(u.u_halo, halo ? 1 : 0);
    { const t = navH + (stacked ? barH : 0), z = stacked ? navH + barH * 0.3 : navH * 0.5; gl.uniform2f(u.u_band, 1 - 2 * (t + 12) / H, 1 - 2 * z / H); }
    gl.uniform1f(u.u_shade, lerp(SHADE[seg], SHADE[seg + 1], mE));
    gl.uniform1fv(u.u_hov, hov); gl.uniform1f(u.u_hovOn, hoverOn); gl.uniform1f(u.u_hovScene, hoverScene);
    gl.uniform1f(u.u_sceneA, seg); gl.uniform1f(u.u_sceneB, seg + 1);
    gl.uniform1f(u.u_fold, seg === 3 ? foldE() : 0); gl.uniform1fv(u.u_cg, cgArr);
    gl.uniform1f(u.u_railA, seg === 3 ? 1 - cgArr.reduce((t, v, c) => t + (c < NCOL ? v : 0), 0) / NCOL : 1);
    gl.uniform1f(u.u_colK, colK);
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
    gl.uniform1f(u.u_pr, dpr * ptK); gl.uniform1f(u.u_dist, CAM_D); gl.uniform1f(u.u_fogR, 1.7 * Math.max(scale[0], scale[1])); gl.uniform1f(u.u_maxpt, maxPt); gl.uniform1f(u.u_halo, halo ? 1 : 0); gl.uniform2f(u.u_res, cv.width, cv.height); gl.uniform1f(u.u_sw, Math.max(1, Math.round(dpr * remK)));
    gl.bindBuffer(gl.ARRAY_BUFFER, BUF.act);
    if (!halo) gl.bufferSubData(gl.ARRAY_BUFFER, 0, actData.subarray(0, nAct * 11));
    const st = 44;
    const at = (name, size, off) => { const loc = pr.a[name]; if (loc < 0) return; gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, size, gl.FLOAT, false, st, off); if (ext) ext.vertexAttribDivisorANGLE(loc, 0); };
    at('a_pos', 3, 0); at('a_col', 4, 12); at('a_shp', 4, 28);
    if (halo) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.drawArrays(gl.POINTS, 0, nAct);
  }
  let nAttribs = 0;
  function resetAttribs() { if (!nAttribs) nAttribs = Math.min(16, gl.getParameter(gl.MAX_VERTEX_ATTRIBS)); for (let i = 0; i < nAttribs; i++) gl.disableVertexAttribArray(i); }

  function frame(now, initial) {
    frameId = 0;
    if (!running || lost || !ready || tiny) return;
    const raw = Math.max(0, (now - t0) / 1000), dt = Math.min(0.05, raw); t0 = now;
    const dtS = Math.min(1, raw);
    if (!((visible && belowBar && !document.hidden) || initial)) return;
    const red = reducedMQ.matches, moving = !red && !paused;
    if (moving) {
      time += dt; simTime += dt;
      const w = 7;
      mouse.vx += (w * w * (mouse.tx - mouse.x) - 2 * w * mouse.vx) * dt; mouse.x += mouse.vx * dt;
      mouse.vy += (w * w * (mouse.ty - mouse.y) - 2 * w * mouse.vy) * dt; mouse.y += mouse.vy * dt;
      if (hand.hold) hand.off = hand.to - (time - hand.t) * 0.07;
      else if (hand.v) { hand.off += hand.v * dt; hand.v *= Math.exp(-dt / 0.27); if (Math.abs(hand.v) < 0.002) hand.v = 0; }
    }
    if (firstFrame < 0) firstFrame = now;
    if (introStart < 0 && (!document.body.classList.contains('is-loading') || now - firstFrame > 2400)) {
      const ld = document.querySelector('.loader');
      gather = !red && ld && !ld.classList.contains('is-quick') && ld.style.getPropertyValue('--hr') ? 1 : 0;
      introStart = now + gather * 200;
    }
    intro = red || introStart < 0 ? (introStart < 0 ? 0 : 1) : clamp((now - introStart) / 1100, 0, 1);
    if (red && introStart >= 0) intro = 1;
    const jump = red || !settledOnce;
    if (jump) { sNow = sTarget; xNow = xTarget; settledOnce = true; }
    else { const k = 1 - Math.exp(-dtS * (performance.now() - lastGo.t < 1500 ? 10 : 6.5)), kx = scrollY > storyTop + run ? 1 - Math.exp(-dtS * 24) : k; sNow += (sTarget - sNow) * k; xNow += (xTarget - xNow) * kx; if (Math.abs(sTarget - sNow) < 0.0004) sNow = sTarget; if (Math.abs(xTarget - xNow) < 0.0004) xNow = xTarget; }
    xeNow = 0;
    stepCopy(now, jump);
    morphState();
    greenBusy = stepGreen(dtS, jump || paused);
    camera();
    if (pointerDirty) {
      pointerDirty = false;
      const h = ptr ? hitTest(ptr.x, ptr.y) : null;
      const same = (a, b) => (!a && !b) || (a && b && a.scene === b.scene && a.idx === b.idx);
      if (ptr && ptr.tap) { if (!same(h, hoverPtr) || !h) { hoverPtr = h; setHover(); } ptr = null; }
      else if (!same(h, hoverPtr) && !(ptr && ptr.onLabel)) { hoverPtr = h; setHover(); }
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
    if (!SOFT && !(LITE && Math.abs(sTarget - sNow) > 0.02)) drawBulk(true);
    drawBulk(false);
    resetAttribs();
    drawActors(false); if (!SOFT) drawActors(true);
    updateUI(now);
    const settled = Math.abs(sTarget - sNow) < 0.002 && Math.abs(xTarget - xNow) < 0.002 && copyResting() && labA >= 1 && intro >= 1 && !greenBusy;
    if (settled !== shownSettled) { shownSettled = settled; if (settled) story.setAttribute('data-settled', ''); else story.removeAttribute('data-settled'); }
    const changing = Math.abs(sTarget - sNow) > 0.0004 || Math.abs(xTarget - xNow) > 0.0004 || hov.some((v, i) => Math.abs(v - hovT[i]) > 0.002) || (intro < 1 && introStart >= 0) || introStart < 0
      || copyMode === 'resolve' || outScene >= 0 || (labelScene >= 0 && labA < 1) || fading || greenBusy || (moving && (hand.hold || hand.v !== 0 || Math.abs(mouse.vx) + Math.abs(mouse.vy) > 0.002));
    if (changing) requestFrame();
    else if (moving) { if (SOFT) { clearTimeout(softTimer); softTimer = setTimeout(requestFrame, 45); } else requestFrame(); }
  }
  let shownSettled = false, SOFT = false, softTimer = 0;
  function requestFrame() { if (!frameId && running && !lost && ready && !tiny && visible && belowBar && !document.hidden) frameId = requestAnimationFrame(frame); }
  function stopFrames() { cancelAnimationFrame(frameId); frameId = 0; clearTimeout(softTimer); t0 = performance.now(); }
  /* hc30r (system's hook, SYSTEM.md 15): leaving Home with the stage on screen, the WebGL canvas cannot stand in the turn's
     snapshot, so this frame is copied to the 2D canvas for the length of the turn: the page you leave stays whole */
  const still2d = story.querySelector('canvas.story-2d');
  let stillOn = false;
  window.addEventListener('pageswap', (e) => {
    stillOn = false;
    if (!e.viewTransition || !still2d || !gl || lost || !ready || tiny || !running || !visible) return;
    try {
      cancelAnimationFrame(frameId); frame(performance.now(), true);
      still2d.width = cv.width; still2d.height = cv.height;
      const g = still2d.getContext('2d'); if (!g) return;
      g.drawImage(cv, 0, 0); still2d.hidden = false; stillOn = true;
    } catch (err) { stillOn = false; }
  });
  window.addEventListener('pageshow', () => { if (stillOn) { stillOn = false; still2d.hidden = true; requestFrame(); } });
  (window.OXA = window.OXA || {}).stageStill = () => stillOn;
  function updateMotion() {
    if (!motionButton) return;
    motionButton.hidden = reducedMQ.matches;
    motionButton.textContent = paused ? 'Resume motion' : 'Pause motion';
  }

  const sceneTop = (i) => storyTop + run * (i / TOTAL_U);
  let lastGo = { i: -1, t: 0 };
  function goTo(i, announce) {
    if (tiny) return;
    i = clamp(i, 0, 4);
    measureScroll();
    handBack();
    lastGo = { i, t: performance.now() };
    window.scrollTo({ top: Math.round(sceneTop(i)), behavior: reducedMQ.matches ? 'instant' : 'smooth' });
    if (announce && live) {
      const h = beats[i] && beats[i].querySelector('h1, h2');
      live.textContent = `${SCENES[i]}${h ? ': ' + h.textContent.replace(/\s+/g, ' ').trim() : ''}`;
    }
  }
  function onKey(e) {
    if (tiny || e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    const d = e.key === 'ArrowRight' || e.key === 'PageDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'PageUp' ? -1 : 0;
    if (!d) return;
    measureScroll();
    if (window.scrollY < storyTop - 4 || window.scrollY > storyTop + run + 4) return;
    const base = performance.now() - lastGo.t < 1200 ? lastGo.i : clamp(Math.round(sTarget + (xTarget > 0 ? 0.5 : 0)), 0, 4);
    if (d > 0 && base >= 4) {
      e.preventDefault();
      const next = document.querySelector('.story ~ section[id], .story ~ * section[id]');
      const top = next ? next.getBoundingClientRect().top + window.scrollY - navH : storyTop + story.offsetHeight;
      window.scrollTo({ top: Math.round(top), behavior: reducedMQ.matches ? 'instant' : 'smooth' });
      lastGo = { i: 5, t: performance.now() };
      const head = next && (next.querySelector('h2') || next);
      if (head) {
        if (!head.hasAttribute('tabindex')) head.setAttribute('tabindex', '-1');
        head.classList.add('story-next-target');
        head.focus({ preventScroll: true });
      }
      return;
    }
    if (d < 0 && base <= 0) return;
    e.preventDefault();
    goTo(base + d, true);
  }

  function fail(err) {
    if (err) console.error(err);
    let at = null, below = null;
    if (wired && lastP === lastP && !tiny) {
      measureScroll();
      if (scrollY > storyTop + 4 && scrollY < storyTop + run + 4) at = clamp(Math.round(sTarget), 0, 4);
      else if (scrollY >= storyTop + run + 4) below = scrollY - (storyTop + storyH - tail);
    }
    running = false; stopFrames(); clearTimeout(lostTimer); clearTimeout(idleTimer);
    beats.forEach(b => { b.style.opacity = b.style.transform = b.style.visibility = ''; ['--eo', '--w', '--bo'].forEach(v => b.style.removeProperty(v)); b.classList.remove('is-active', 'is-relay', 'is-tight', 'is-snug', 'is-bo0'); });
    root.classList.remove('story-compact', 'story-short', 'story-tiny');
    beatLinks.forEach(list => list.forEach(el => el.removeAttribute('tabindex')));
    labels.forEach(l => l.el.remove()); leaders.remove();
    if (bar) bar.style.opacity = bar.style.visibility = '';
    if (paper) paper.style.height = paper.style.bottom = paper.style.visibility = '';
    clearTall();
    if (motionButton) motionButton.hidden = true;
    insp.remove();
    stage.removeAttribute('tabindex'); stage.removeAttribute('aria-describedby');
    setTail(0);
    fallback();
    if (at != null || below != null) {
      const top = at != null ? (at === 0 ? storyTop : beats[at].getBoundingClientRect().top + window.scrollY - navH) : story.getBoundingClientRect().top + window.scrollY + story.offsetHeight + below;
      window.scrollTo({ top: Math.max(0, Math.round(top)), behavior: 'instant' });
    }
  }
  let wired = false;
  function begin() {
    if (!wired) {
      wired = true;
      stage.tabIndex = 0;
      if (document.getElementById('story-keys')) stage.setAttribute('aria-describedby', 'story-keys');
      stage.addEventListener('keydown', onKey);
      document.addEventListener('keydown', e => { if (e.key === 'Escape' && (hoverPtr || hoverFocus)) { hoverPtr = hoverFocus = null; setHover(); } });
      if (bar) bar.addEventListener('focusin', () => { if (running && xTarget > 0.02) goTo(4); });
      stage.addEventListener('focusin', e => { if (e.target === stage && running && !tiny && xTarget > 0.02) goTo(4); });
      beats.forEach((b, i) => b.addEventListener('focusin', () => { if (running && !tiny && (Math.abs(sTarget - i) > 0.45 || xTarget > 0.02)) goTo(i); }));
      if (motionButton) motionButton.addEventListener('click', () => { paused = !paused; story.classList.toggle('is-paused', paused); hand.v = 0; updateMotion(); requestFrame(); });
      reducedMQ.addEventListener('change', () => { mouse.x = mouse.y = mouse.tx = mouse.ty = mouse.vx = mouse.vy = 0; hand.v = 0; letGo(); updateMotion(); requestFrame(); });
      window.addEventListener('resize', () => resize());
      stackedMQ.addEventListener('change', () => resize(true));
      if (window.ResizeObserver) { let bh = 0; new ResizeObserver(() => { const h = beats[0].offsetHeight; if (bh && h !== bh) requestAnimationFrame(() => { resize(true); bh = beats[0].offsetHeight; }); else bh = h; }).observe(beats[0]); }
      (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
      window.addEventListener('scroll', () => {
        const wasBelow = belowBar;
        if (tiny) { tinyPlace = staticPlace(); return; }
        const dS = window.scrollY - scrollY;
        scrollY = window.scrollY; sceneScroll(); syncIndex(); handBack();
        if (seg === 0 && fineMQ.matches && !hand.hold && !reducedMQ.matches && !paused && Math.abs(dS) < H) hand.v = clamp(hand.v + dS * 0.0022, -2.4, 2.4);
        if (!visible) { sNow = sTarget; xNow = xTarget; copyS = sNow; copyMode = 'follow'; settledOnce = false; }
        if (lost) { uiNoGL(); return; }
        if (wasBelow && !belowBar && running && ready) { sNow = sTarget; xNow = xTarget; copyS = sNow; copyMode = 'follow'; stopFrames(); frame(performance.now(), true); }
        requestFrame();
      }, { passive: true });
      window.addEventListener('wheel', handBack, { passive: true });
      window.addEventListener('touchstart', () => { touchDown = true; handBack(); }, { passive: true, capture: true });
      window.addEventListener('touchmove', handBack, { passive: true, capture: true });
      const lift = (e) => { touchDown = e.touches && e.touches.length > 0; handBack(); };
      window.addEventListener('touchend', lift, { passive: true, capture: true });
      window.addEventListener('touchcancel', lift, { passive: true, capture: true });
      document.addEventListener('oxa:loaded', () => setTimeout(() => { relayReady = true; requestFrame(); }, 1500), { once: true });
      document.addEventListener('oxa:jump', () => {
        if (!running || lost || !ready || tiny) return;
        measureScroll(); sceneScroll(); syncIndex();
        if (scrollY + window.innerHeight <= storyTop || scrollY >= storyTop + storyH - tail) return;
        sNow = sTarget; xNow = xTarget; copyS = sNow; copyMode = 'follow'; settledOnce = true;
        stopFrames(); frame(performance.now(), true);
      });
      if (root.classList.contains('is-loaded')) setTimeout(() => { relayReady = true; requestFrame(); }, 1500);
      const refit = () => { scrollY = window.scrollY; sceneScroll(); resize(true); };
      if (document.fonts && document.fonts.ready) requestAnimationFrame(() => requestAnimationFrame(() => document.fonts.ready.then(refit)));
      window.addEventListener('load', refit, { once: true });
      const discAt = (e) => {
        if (e.pointerType === 'touch' || !fineMQ.matches || reducedMQ.matches || paused || seg !== 0 || sNow > 0.08 || xNow > 0 || frameTiny[0] || intro < 1) return false;
        if (e.target.closest && e.target.closest('.beat-text, .hero-stats, .story-bar, .story-lab, .story-insp, a, button')) return false;
        const r = stage.getBoundingClientRect(), L = layouts[0];
        return Math.hypot(e.clientX - r.left - L.cx, e.clientY - r.top - L.cy) <= L.s * pxuOf(H) * 1.02;
      };
      let grabOn = false;
      const grabCue = (on) => { if (on !== grabOn) stage.classList.toggle('is-grab', grabOn = on); };
      function letGo(e) {
        if (!hand.hold || (e && e.pointerId !== hand.id)) return;
        hand.hold = false; stage.classList.remove('is-grabbing');
        hand.v = e && e.timeStamp - hand.lt < 90 ? clamp(hand.vm, -6, 6) : 0;
        if (e && stage.hasPointerCapture && stage.hasPointerCapture(e.pointerId)) stage.releasePointerCapture(e.pointerId);
        requestFrame();
      }
      stage.addEventListener('pointerdown', e => {
        if (e.button !== 0 || !discAt(e)) return;
        e.preventDefault();
        const R = Math.max(40, layouts[0].s * pxuOf(H));
        Object.assign(hand, { hold: true, id: e.pointerId, x: e.clientX, a: hand.off, t: time, to: hand.off, v: 0, lx: e.clientX, lt: e.timeStamp, vm: 0, R });
        try { stage.setPointerCapture(e.pointerId); } catch (err) { }
        stage.classList.add('is-grabbing');
        requestFrame();
      });
      ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(t => stage.addEventListener(t, letGo));
      stage.addEventListener('pointermove', e => {
        if (hand.hold && e.pointerId === hand.id) {
          const dtt = (e.timeStamp - hand.lt) / 1000;
          if (dtt > 0.004) { hand.vm = lerp(hand.vm, (e.clientX - hand.lx) / hand.R / dtt, 0.6); hand.lx = e.clientX; hand.lt = e.timeStamp; }
          hand.to = hand.a + (e.clientX - hand.x) / hand.R;
          requestFrame();
          return;
        }
        if (e.pointerType !== 'touch') grabCue(discAt(e));
        if (e.pointerType === 'touch' || !moved(e)) return;
        lastPtr.x = e.clientX; lastPtr.y = e.clientY;
        const r = stage.getBoundingClientRect();
        const onCopy = !!(e.target.closest && e.target.closest('.beat-text, .hero-stats, .story-bar'));
        ptr = onCopy ? null : { x: e.clientX - r.left, y: e.clientY - r.top, onLabel: !!(e.target.closest && e.target.closest('.story-lab')) };
        pointerDirty = true;
        if (!reducedMQ.matches && !paused) { mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2; mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2; }
        requestFrame();
      }, { passive: true });
      stage.addEventListener('pointerleave', e => { if (e.pointerType === 'touch') return; grabCue(false); ptr = null; pointerDirty = true; mouse.tx = mouse.ty = 0; requestFrame(); });
      let tap = null;
      stage.addEventListener('pointerdown', e => { tap = e.pointerType === 'touch' ? { x: e.clientX, y: e.clientY, t: performance.now(), id: e.pointerId } : null; }, { passive: true });
      stage.addEventListener('pointercancel', () => { tap = null; }, { passive: true });
      stage.addEventListener('pointerup', e => {
        const t = tap; tap = null;
        if (!t || e.pointerType !== 'touch' || e.pointerId !== t.id) return;
        if (Math.abs(e.clientX - t.x) >= 10 || Math.abs(e.clientY - t.y) >= 10 || performance.now() - t.t >= 450) return;
        const hitLab = e.target.closest && e.target.closest('.story-lab'), l = hitLab && labels.find(x => x.el === hitLab);
        if (l && l.group != null) { hoverPtr = { scene: l.scene, idx: l.group }; setHover(); return; }
        if (e.target.closest && e.target.closest('.beat-text, .hero-stats, .story-bar, .story-insp')) return;
        const r = stage.getBoundingClientRect();
        ptr = { x: e.clientX - r.left, y: e.clientY - r.top, tap: true }; pointerDirty = true; requestFrame();
      }, { passive: true });
      if ('IntersectionObserver' in window) {
        new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) requestFrame(); else stopFrames(); }, { threshold: 0 }).observe(story);
        new IntersectionObserver(([e]) => { if (e.isIntersecting && running && ready && !lost && !tiny) { scrollY = window.scrollY; sceneScroll(); sNow = sTarget; xNow = xTarget; settledOnce = false; stopFrames(); frame(performance.now(), true); } }, { rootMargin: '40% 0px 40% 0px', threshold: 0 }).observe(story);
      }
      document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
    }
    resize(true);
    updateMotion();
    stopFrames();
    frame(performance.now(), true);
    root.classList.add('gl-ready'); document.dispatchEvent(new Event('story:gl-ready'));
  }
  let lostTimer = 0;
  function uiNoGL() {
    if (!running || !wired || tiny) return;
    sNow = sTarget; xNow = xTarget; xeNow = 0; copyS = sNow; copyMode = 'follow';
    morphState(); camera(); updateUI(performance.now());
  }
  function start() {
    try { gl = cv.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: true, powerPreference: 'high-performance' }); } catch (e) { gl = null; }
    if (!gl) { fail(); return; }
    try { let r = String(gl.getParameter(gl.RENDERER)); if (r === 'WebKit WebGL') { const dbg = gl.getExtension('WEBGL_debug_renderer_info'); if (dbg) r = String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)); } SOFT = /swiftshader|llvmpipe|softpipe|software|basic render/i.test(r); } catch (e) { SOFT = false; }
    if (SOFT) stage.classList.remove('grain');
    cv.addEventListener('webglcontextlost', e => {
      e.preventDefault(); lost = true; ready = false; stopFrames();
      if (shownSettled) { shownSettled = false; story.removeAttribute('data-settled'); }
      uiNoGL();
      clearTimeout(lostTimer); lostTimer = setTimeout(() => { if (lost && running) fail(); }, 2500);
    });
    cv.addEventListener('webglcontextrestored', () => { clearTimeout(lostTimer); lost = false; if (running) setupGL(begin); });
    setupGL(begin);
  }
  let built = false;
  function buildInSlices() {
    const it = build();
    (function slice() {
      const t = performance.now();
      let r;
      do r = it.next(); while (!r.done && performance.now() - t < 6);
      if (r.done) built = true; else setTimeout(slice, 0);
    })();
  }
  let started = false;
  const go = () => { if (started) return; started = true; start(); if (gl) setTimeout(buildInSlices, 0); };
  if (document.hidden) setTimeout(go, 0); else requestAnimationFrame(() => setTimeout(go, 0));
})();
