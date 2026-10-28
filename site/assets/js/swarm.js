/* OpenEXA — the swarm lab (home §03). An illustrative model, drawn in 3D on a 2D canvas (no WebGL needed).
   Agents carry proposals left to right through six gates. Signals drift in and are picked up at 01 Signal; through
   02 Predict and 03 Decide agents estimate (they jitter), and at 03 each forms a proposal (a green ring). At 04 Approve the
   execution council, an aperture of fine ticks, approves or rejects against a risk limit you can tighten: the aperture
   closes, proposals queue at it, rejected ones fall away and fade. Past the council execution is deterministic: approved
   proposals snap onto five rails that advance in lockstep, settle at 06 as solid squares and are sealed into blocks on a
   hash-chained ledger line. Halt stops new proposals while open work drains. "Follow a proposal" (or click/tap an agent)
   traces one proposal gate by gate until it settles or is rejected. Every counter is derived from the model's state.
   Settled proposals are announced to the page: document 'oxa:settled' events, at most four a second, detail
   {id, lane, ts, gate: 'settle', count, followed} (count = proposals settled since the previous event).
   Paused off-screen (the model keeps a slow pulse so the ledger below still hears it) and in hidden tabs;
   prefers-reduced-motion: no autonomous motion, every control re-renders a still study. */
(function () {
  'use strict';
  const root = document.querySelector('[data-swarm-live]');
  if (!root) return;
  const $ = (s) => root.querySelector(s);
  const stage = $('[data-sw-stage]'), cv = stage && stage.querySelector('canvas');
  const ctx = cv && cv.getContext('2d');
  if (!ctx) return; // the static figure in the markup stays as it is
  root.classList.add('sw-on');

  const el = {
    n: $('[data-sw-n]'), nOut: $('[data-sw-n-out]'), strict: $('[data-sw-strict]'), strictOut: $('[data-sw-strict-out]'),
    halt: $('[data-sw-halt]'), state: $('[data-sw-state]'), follow: $('[data-sw-follow]'),
    inflight: $('[data-sw-inflight]'), recorded: $('[data-sw-recorded]'), rejected: $('[data-sw-rejected]'), rate: $('[data-sw-rate]'),
    gates: Array.from(root.querySelectorAll('[data-sw-gates] > li')), limit: $('[data-sw-limit]'), ledger: $('[data-sw-ledger]'),
    banner: $('[data-sw-banner]'), tag: $('[data-sw-agent]'), trace: $('[data-sw-callout]'), traceId: $('[data-sw-trace-id]'),
    traceState: $('[data-sw-trace-state]'), log: $('[data-sw-log]'), close: $('[data-sw-trace-close]'), say: $('[data-sw-say]'),
    hov: $('[data-sw-hover]'), bound: $('[data-sw-bound]'),
  };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const TAU = Math.PI * 2;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const easeOut = (t) => 1 - (1 - t) * (1 - t) * (1 - t);
  const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const easeBack = (t) => { const c = 1.9, u = t - 1; return 1 + (c + 1) * u * u * u + c * u * u; }; // a light spring: the snap onto a rail
  const tickEase = (p) => (p < 0.18 ? 0 : 0.5 - 0.5 * Math.cos(Math.PI * (p - 0.18) / 0.82)); // rails: dwell, then one smooth step

  /* ---------------- the model ---------------- */
  let seed = 7;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const GX = [-1.02, -0.64, -0.27, 0.1, 0.5, 0.86];          // gates 01..06 along the flow (world x)
  const GATE = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];
  const RY = 0.26, RZ = 0.18, FLOOR = -0.47;                  // the stream's half-height and half-depth; the floor
  const RAIL_Y = [-0.18, -0.09, 0, 0.09, 0.18], RAIL_Z = 0;    // five deterministic rails, a flat ladder after the boundary
  const X_SNAP = 0.14, LX = GX[5] + 0.24, XR = GX[3] - 0.05;   // snap distance past the council; the ledger's open block; where rejections land
  const V_RAIL = 0.34, TICK = 0.4, V_LED = 0.16;               // rails advance in lockstep ticks; the ledger line drifts right
  const TRAIL = 5, TRAIL_DT = 0.042;                           // per-agent trail: five samples, 42 ms apart
  const CAP = 8200, MOTES = 220, NT = 96;                      // agent slots; incoming signals; ticks on the council aperture
  const DEAD = 0, FLOW = 1, PROP = 2, RAIL = 3, SETTLE = 4, REJECT = 5;
  const st = new Uint8Array(CAP), gate = new Uint8Array(CAP), lane = new Uint8Array(CAP), flag = new Uint8Array(CAP), hc = new Uint8Array(CAP);
  const X = new Float32Array(CAP), Y = new Float32Array(CAP), Z = new Float32Array(CAP);
  const VX = new Float32Array(CAP), VY = new Float32Array(CAP), VZ = new Float32Array(CAP);
  const SX = new Float32Array(CAP), SY = new Float32Array(CAP), SZ = new Float32Array(CAP);
  const SPD = new Float32Array(CAP), RHO = new Float32Array(CAP), PHI = new Float32Array(CAP), PH = new Float32Array(CAP);
  const RISK = new Float32Array(CAP), T0 = new Float32Array(CAP), BORN = new Float32Array(CAP), UID = new Int32Array(CAP);
  const GT = new Float32Array(CAP * 7), UNSET = -1e9;          // when each agent crossed each gate (model seconds; UNSET: not yet)
  const PX = new Float32Array(CAP), PY = new Float32Array(CAP), PF = new Float32Array(CAP), PS = new Float32Array(CAP); // projected x, y, fog 0..1, scale
  const HIST = new Float32Array(CAP * TRAIL * 2);              // trails, in screen space (re-sampled on resize)
  const freeList = new Int32Array(CAP); let nFree = 0, hi = 0;
  const MX = new Float32Array(MOTES * 6), MS = new Float32Array(MOTES), MV = new Float32Array(MOTES), MA = new Float32Array(MOTES);
  const TF = new Float32Array(NT), TC = new Uint8Array(NT);    // aperture ticks: flash level and colour (0 approve, 1 reject)
  const GF = new Float32Array(6);                               // gate flash when the followed proposal passes

  let target = window.innerWidth < 600 ? 700 : 1800, strict = 0.12, halted = false;
  let sim = 0, seq = 41000 + Math.floor(Math.random() * 9000), inflight = 0, spawnAcc = 0, railPh = 0, histT = 0, hHead = 0, pulse = 0, rejGlow = 0;
  const S = { settled: 0, rejected: 0, win: [] };               // derived counters read these, nothing else
  const ledger = []; let blockSeq = 1040 + Math.floor(Math.random() * 400), openPulse = 0;
  // tightening the council closes its aperture: an iris that eases to its new opening (a click on the slider's track
  // must not snap the funnel and every agent in it); the entry gate's shutter eases closed on Halt the same way
  const AP_MAX = 0.19;
  let apR = 0.18, apT = 0.18, shutK = 0;
  const setStrict = (v, snap) => { strict = v; apT = AP_MAX - 0.12 * (v / 0.6); if (snap) apR = apT; };
  setStrict(strict, true);
  const pid = (u) => `P-${String(u).padStart(5, '0')}`;

  function alloc() { if (nFree) return freeList[--nFree]; return hi < CAP ? hi++ : -1; }
  function kill(i) { st[i] = DEAD; freeList[nFree++] = i; }
  function tube(x) { // half-height of the stream at x
    if (x < GX[0]) return RY + (GX[0] - x) * 0.9;
    if (x <= GX[2]) return RY;
    return RY + (apR * 0.86 - RY) * smooth(GX[2], GX[3], x);
  }
  function flowPos(i) {
    const x = X[i], t = smooth(GX[2], GX[3], x), r = tube(x) * RHO[i];
    const zs = RZ / RY + (1 - RZ / RY) * t;                     // flat in depth upstream, round at the aperture
    const a = PHI[i] + 0.32 * Math.sin(sim * 0.37 + PH[i]);
    const j = 0.011 * (1 - 0.8 * t), f = 0.7 + 0.6 * ((PH[i] * 7.13) % 1); // estimation: jitter, calming toward the council
    Y[i] = r * Math.sin(a) + j * (0.55 * Math.sin(sim * 10.3 * f + PH[i] * 7) + 0.3 * Math.sin(sim * 17.9 * f + PH[i] * 13) + 0.15 * Math.sin(sim * 27.1 + PH[i] * 3))
      + 0.008 * Math.sin(sim * 2.1 * f + PH[i] * 3);
    Z[i] = r * Math.cos(a) * zs + j * (0.6 * Math.cos(sim * 8.9 * f + PH[i] * 5) + 0.4 * Math.sin(sim * 15.7 * f + PH[i] * 11));
  }
  function spawnAt(x) {
    const i = alloc(); if (i < 0) return -1;
    st[i] = FLOW; gate[i] = 0; hc[i] = 0; flag[i] = 0;
    X[i] = x; RHO[i] = Math.sqrt(rnd()); PHI[i] = rnd() * TAU; PH[i] = rnd() * TAU;
    SPD[i] = 0.165 + rnd() * 0.085; RISK[i] = rnd(); T0[i] = 0; BORN[i] = sim; UID[i] = ++seq;
    for (let g = 0; g < 7; g++) GT[i * 7 + g] = UNSET;
    flowPos(i);
    return i;
  }
  function pickLane(i) { return clamp(Math.round(Y[i] / (apR + 1e-3) * 2.2 + 2 + (rnd() - 0.5) * 1.2), 0, 4); }
  // a lane already in steady state: agents placed along it with the history they would have had
  function warmStart() {
    const limit = 1 - strict;
    // steady-state density: the rails run faster than the estimation field and carry only the approved share, so they
    // hold fewer agents per unit length; a uniform fill would flush a burst of settlements in the first seconds
    const keepRail = clamp(0.2075 / V_RAIL * limit, 0, 1);
    for (let k = 0; k < target; k++) {
      let x = GX[0] - 0.08 + rnd() * (GX[5] - GX[0] + 0.06);
      if (x > GX[3] && rnd() > keepRail) x = GX[0] - 0.08 + rnd() * (GX[3] - GX[0] + 0.07);
      const i = spawnAt(x); if (i < 0) break;
      BORN[i] = sim - 5;
      // the gates it passed before the model began, back-dated at its own pace upstream and the rails' pace past the council
      while (gate[i] < 6 && X[i] >= GX[gate[i]]) {
        const x0 = GX[gate[i]]; gate[i]++;
        GT[i * 7 + gate[i]] = sim - Math.max(0, Math.min(X[i], GX[3]) - x0) / SPD[i] - Math.max(0, X[i] - Math.max(x0, GX[3])) / V_RAIL;
      }
      if (gate[i] >= 3) st[i] = PROP;
      if (gate[i] >= 4) {
        RISK[i] = rnd() * limit; st[i] = RAIL; lane[i] = clamp(Math.floor(rnd() * 5), 0, 4);
        SY[i] = Y[i]; SZ[i] = Z[i]; T0[i] = (X[i] - GX[3]) / V_RAIL;
        if (gate[i] >= 6) { gate[i] = 5; X[i] = GX[5] - 0.01; }
      }
    }
    for (let m = 0; m < MOTES; m++) mote(m, true);
  }
  function mote(m, fresh) {
    const o = m * 6;
    MX[o] = -1.75 - rnd() * 0.55; MX[o + 1] = (rnd() - 0.5) * 0.95 + 0.04; MX[o + 2] = (rnd() - 0.5) * 0.7;
    MX[o + 3] = GX[0] - 0.02; MX[o + 4] = MX[o + 1] * 0.28; MX[o + 5] = MX[o + 2] * 0.28;
    MS[m] = fresh ? rnd() : 0; MV[m] = 0.3 + rnd() * 0.32; MA[m] = 0.35 + rnd() * 0.45;
  }
  function reset() {
    st.fill(0); hi = 0; nFree = 0; sim = 0; inflight = 0; spawnAcc = 0; railPh = 0; histT = 0; hHead = 0; pulse = 0; rejGlow = 0;
    S.settled = S.rejected = 0; S.win.length = 0; ledger.length = 0; TF.fill(0); GF.fill(0); evPending = null;
  }

  /* ---------------- following one proposal ---------------- */
  const follow = { active: false, show: false, i: -1, uid: 0, id: '', n: 0, px: new Float32Array(900 * 3), ps: new Uint8Array(900), pt: 0,
    marks: [], verdict: '', endAt: 0, dim: 0, x: 0, y: 0, z: 0 };
  const isFollowed = (i) => follow.active && follow.i === i && follow.uid === UID[i];

  /* ---------------- settled → ledger blocks + the page event (at most 4/s) ---------------- */
  let evPending = null, evLast = -1e9, evTimer = 0;
  function sealed(i) {
    const f = isFollowed(i);
    if (!evPending) evPending = { id: '', lane: 0, count: 0, followed: false };
    evPending.count++;
    if (f || !evPending.followed) { evPending.id = pid(UID[i]); evPending.lane = lane[i] + 1; evPending.followed = f; }
    openPulse = 1;
  }
  // the clock is read at dispatch, not the frame's timestamp, so listeners never see two events closer than 250 ms;
  // a forced flush (a followed proposal in a still study) waits for its turn instead of breaking the limit
  function flush(force) {
    if (!evPending) return;
    const nowMs = performance.now(), wait = 250 - (nowMs - evLast);
    if (wait > 0) { if (force && !evTimer) evTimer = setTimeout(() => { evTimer = 0; flush(true); }, wait + 1); return; }
    evLast = nowMs;
    const p = evPending; evPending = null;
    const block = ++blockSeq;
    ledger.push({ x: LX, n: p.count, t: sim, f: p.followed });
    if (ledger.length > 64) ledger.shift();
    if (p.followed) traceLedger(p.id, block);
    document.dispatchEvent(new CustomEvent('oxa:settled', { detail: { id: p.id, lane: p.lane, ts: Date.now(), gate: 'settle', count: p.count, followed: p.followed } }));
  }

  /* ---------------- one step of the model ---------------- */
  function step(dt, project) {
    sim += dt;
    apR += (apT - apR) * (1 - Math.exp(-dt * 5));
    shutK += ((halted ? 1 : 0) - shutK) * (1 - Math.exp(-dt * 8));
    const limit = 1 - strict, cong = 0.1 + 1.05 * strict;
    if (!halted) { // inflow keeps the lane near the population you chose
      const tEst = (GX[3] - GX[0]) / 0.2 * (1 + cong * 0.3) + (1 - strict) * (GX[5] - GX[3]) / V_RAIL;
      spawnAcc += clamp(target / tEst + (target - inflight) * 0.9, 0, 1.6 * target / tEst) * dt; // a refill arrives as a wave
      let k = Math.min(Math.floor(spawnAcc), 90); spawnAcc -= k; if (spawnAcc > 90) spawnAcc = 90;
      while (k-- > 0) { const i = spawnAt(GX[0] - 0.025 - rnd() * 0.08); if (i < 0) break; }
    } else spawnAcc = 0;
    const p0 = railPh; railPh += dt / TICK;
    const railDx = V_RAIL * TICK * ((Math.floor(railPh) - Math.floor(p0)) + tickEase(railPh % 1) - tickEase(p0 % 1));
    let fl = 0;
    for (let i = 0; i < hi; i++) {
      const s = st[i];
      if (s === DEAD) continue;
      if (s === FLOW || s === PROP) {
        const slow = 1 - cong * smooth(GX[3] - 0.22, GX[3], X[i]);   // the stricter the council, the longer each decision
        X[i] += SPD[i] * dt * slow * (1 + 0.16 * Math.sin(sim * 1.3 + PH[i]));
        flowPos(i);
        while (gate[i] < 4 && X[i] >= GX[gate[i]]) {
          const g = ++gate[i]; GT[i * 7 + g] = sim;
          if (g === 3) st[i] = PROP;
          else if (g === 4) decide(i, limit);
          if (isFollowed(i)) traceGate(i, g);
          if (g === 4) break;
        }
        if (st[i] !== REJECT) fl++; // counted after its decision: in flight means not yet settled or rejected
      } else if (s === RAIL) {
        X[i] += railDx; T0[i] += dt;
        const e = easeBack(Math.min(1, T0[i] / 0.42));
        Y[i] = SY[i] + (RAIL_Y[lane[i]] - SY[i]) * e; Z[i] = SZ[i] + (RAIL_Z - SZ[i]) * e;
        if (gate[i] < 5 && X[i] >= GX[4]) { gate[i] = 5; GT[i * 7 + 5] = sim; if (isFollowed(i)) traceGate(i, 5); }
        if (X[i] >= GX[5]) {
          gate[i] = 6; GT[i * 7 + 6] = sim; st[i] = SETTLE; T0[i] = 0; SX[i] = X[i]; SY[i] = Y[i]; SZ[i] = Z[i];
          S.settled++; S.win.push(sim);
          if (isFollowed(i)) traceGate(i, 6);
        } else fl++;
      } else if (s === SETTLE) {
        T0[i] += dt;
        if (T0[i] < 0.22) X[i] = SX[i] + V_RAIL * T0[i];          // the snap: it turns solid, gliding off the clocked rail
        else {
          // five rails merge into one line: a smooth bend along its manifold guide into the open block
          const u = easeInOut(Math.min(1, (T0[i] - 0.22) / 0.46)), v = 1 - u, x0 = SX[i] + V_RAIL * 0.22;
          const cx = x0 + (LX - x0) * 0.62, cy = SY[i], cz = SZ[i];
          X[i] = v * v * x0 + 2 * v * u * cx + u * u * LX; Y[i] = v * v * SY[i] + 2 * v * u * cy; Z[i] = v * v * SZ[i] + 2 * v * u * cz;
          if (T0[i] >= 0.68) {
            sealed(i);
            if (isFollowed(i)) endFollow('settled', i);
            kill(i); continue;
          }
        }
      } else { // REJECT: falls away with gravity, lies on the floor, fades
        T0[i] += dt;
        if (!flag[i]) {
          VY[i] -= 1.35 * dt; X[i] += VX[i] * dt; Y[i] += VY[i] * dt; Z[i] += VZ[i] * dt;
          if (Y[i] <= FLOOR) { Y[i] = FLOOR; flag[i] = 1; T0[i] = 0; rejGlow = Math.min(1, rejGlow + 0.05); if (isFollowed(i)) endFollow('rejected', i); }
        } else if (T0[i] > 1.5) { kill(i); continue; }
      }
    }
    inflight = fl;
    // signals drifting in: data the agents pick up at 01 (nobody picks it up while halted: it fades at the closed gate)
    for (let m = 0; m < MOTES; m++) { MS[m] += MV[m] * dt / 1.05; if (MS[m] >= 1) mote(m, false); }
    for (let k = 0; k < NT; k++) if (TF[k] > 0) TF[k] = Math.max(0, TF[k] - dt / 0.32);
    for (let g = 0; g < 6; g++) if (GF[g] > 0) GF[g] = Math.max(0, GF[g] - dt / 0.9);
    pulse = Math.max(0, pulse - dt / 0.3); openPulse = Math.max(0, openPulse - dt / 0.25); rejGlow = Math.max(0, rejGlow - dt * 0.35);
    for (const b of ledger) b.x += V_LED * dt;
    while (ledger.length && ledger[0].x > 2.4) ledger.shift();
    const cut = sim - 5; while (S.win.length && S.win[0] < cut) S.win.shift();
    if (follow.active) recordPath();
    if (project) {
      camera(); projectAll();
      if (sim - histT >= TRAIL_DT) { histT = sim; sample(); }
    }
  }
  function decide(i, limit) {
    const ang = Math.atan2(Y[i], Z[i]), k = Math.floor(((ang / TAU) + 1) % 1 * NT);
    const f = isFollowed(i);
    if (RISK[i] >= limit) {
      st[i] = REJECT; T0[i] = 0; flag[i] = 0; S.rejected++;
      // it falls away on the near side of the boundary (a rejected proposal never reaches the deterministic rails),
      // fanning outward in depth so the fall reads as a curtain in front of the council, not a bundle through it
      VX[i] = -0.02 - rnd() * 0.06; VY[i] = rnd() * 0.06; VZ[i] = Z[i] * 0.6 + (rnd() - 0.5) * 0.1;
      TF[k] = 1; TC[k] = 1;
    } else {
      st[i] = RAIL; lane[i] = pickLane(i); SY[i] = Y[i]; SZ[i] = Z[i]; T0[i] = 0;
      if (TF[k] < 0.6) { TF[k] = 0.6; TC[k] = 0; }
    }
    if (f) pulse = 1;
  }

  /* ---------------- camera + projection (CPU, perspective) ---------------- */
  const cam = { yaw: -0.4, pitch: 0.2, D: 3.4, F: 500, cx: 0, cy: 0, cyw: 1, syw: 0, cp: 1, sp: 0, tx: 0.04, ty: -0.1, tz: 0, dmin: 3, dmax: 4, k0: 150 };
  const YAW = -0.4, PITCH = 0.2;
  let par = 0, parT = 0, P_X = 0, P_Y = 0, P_D = 1;
  function camera() {
    par += (parT - par) * 0.04;
    const still = reduced.matches;
    const yaw = YAW + (still ? 0 : 0.03 * Math.sin(sim * 0.11) + par * 0.05), pitch = PITCH + (still ? 0 : 0.012 * Math.sin(sim * 0.083));
    cam.cyw = Math.cos(yaw); cam.syw = Math.sin(yaw); cam.cp = Math.cos(pitch); cam.sp = Math.sin(pitch);
  }
  function proj(x, y, z) {
    const dx = x - cam.tx, dy = y - cam.ty, dz = z - cam.tz;
    const x1 = dx * cam.cyw + dz * cam.syw, z1 = -dx * cam.syw + dz * cam.cyw;
    const y2 = dy * cam.cp - z1 * cam.sp, z2 = dy * cam.sp + z1 * cam.cp;
    const d = cam.D - z2;
    P_X = cam.cx + x1 * cam.F / d; P_Y = cam.cy - y2 * cam.F / d; P_D = d;
  }
  const fog = (d) => clamp((d - cam.dmin) / (cam.dmax - cam.dmin), 0, 1);
  function projectAll() {
    for (let i = 0; i < hi; i++) {
      if (!st[i]) continue;
      proj(X[i], Y[i], Z[i]); PX[i] = P_X; PY[i] = P_Y; PF[i] = fog(P_D); PS[i] = cam.D / P_D;
    }
  }
  function sample() {
    hHead = (hHead + 1) % TRAIL;
    for (let i = 0; i < hi; i++) {
      if (!st[i]) continue;
      const o = (i * TRAIL + hHead) * 2; HIST[o] = PX[i]; HIST[o + 1] = PY[i];
      if (hc[i] < TRAIL) hc[i]++;
    }
  }
  // fit the scene into the stage: labels above, a little air below
  let W = 1, H = 1, dpr = 1, narrow = false, rowTop = 14, rowH = 30;
  function fit() {
    camera();
    const keep = { cx: cam.cx, cy: cam.cy, F: cam.F };
    cam.cx = 0; cam.cy = 0; cam.F = 1;
    let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, d0 = 1e9, d1 = -1e9;
    const pts = [];
    for (let g = 0; g < 6; g++) { const [hy, hz] = frameDims(g, true); for (const sy of [-1, 1]) for (const sz of [-1, 1]) pts.push([GX[g], sy * hy, sz * hz]); }
    // phones crop the runway and the ledger's tail so the gates get the width
    pts.push([GX[0] - (narrow ? 0.06 : 0.3), 0, 0], [LX + (narrow ? 0.1 : 0.3), 0, 0], [XR, FLOOR, 0.2], [XR, FLOOR, -0.2]);
    for (const p of pts) { proj(p[0], p[1], p[2]); x0 = Math.min(x0, P_X); x1 = Math.max(x1, P_X); y0 = Math.min(y0, P_Y); y1 = Math.max(y1, P_Y); d0 = Math.min(d0, P_D); d1 = Math.max(d1, P_D); }
    const padT = narrow ? rowTop + rowH + 18 : rowTop + rowH + 26, padB = narrow ? rowH + 22 : 16, padX = narrow ? 4 : 10;
    const aw = W - padX * 2, ah = H - padT - padB;
    cam.F = Math.min(aw / (x1 - x0), ah / (y1 - y0));
    cam.cx = padX + (aw - (x1 - x0) * cam.F) / 2 - x0 * cam.F; cam.cy = padT + (ah - (y1 - y0) * cam.F) / 2 - y0 * cam.F;
    cam.dmin = d0; cam.dmax = d1; cam.k0 = cam.F / cam.D;
    if (!isFinite(cam.F) || cam.F <= 0) Object.assign(cam, keep);
  }
  function frameDims(g, fitting) { const a = (fitting ? AP_MAX : apR) + 0.11; return g <= 2 ? [RY + 0.07, RZ + 0.07] : g === 3 ? [a, a] : [0.245, 0.075]; } // the camera fits the open aperture, so strictness never re-frames the shot

  /* ---------------- sprites: bead shading, green key light upper-left, ivory rim ---------------- */
  const SPR = {};
  const SPR_SIZES = [8, 16, 32, 64];
  function makeSprite(kind, P) {
    const c = document.createElement('canvas'); c.width = c.height = P;
    const g = c.getContext('2d'), r = P / 2;
    if (kind === 'bead' || kind === 'red') {
      const red = kind === 'red';
      const gr = g.createRadialGradient(r * 0.7, r * 0.66, 0, r, r, r);
      gr.addColorStop(0, red ? 'rgba(255,214,206,1)' : 'rgba(236,255,244,1)');
      gr.addColorStop(0.3, red ? 'rgba(229,118,106,1)' : 'rgba(245,242,236,1)');
      gr.addColorStop(0.68, red ? 'rgba(196,84,74,.92)' : 'rgba(208,214,204,.9)');
      gr.addColorStop(0.9, red ? 'rgba(160,60,52,.3)' : 'rgba(150,170,160,.28)');
      gr.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gr; g.fillRect(0, 0, P, P);
      if (P >= 32) { g.beginPath(); g.arc(r, r, r * 0.66, 0.15 * Math.PI, 0.85 * Math.PI); g.strokeStyle = red ? 'rgba(255,190,180,.35)' : 'rgba(245,242,236,.45)'; g.lineWidth = P * 0.05; g.stroke(); }
    } else if (kind === 'ring') {
      g.beginPath(); g.arc(r, r, r * 0.58, 0, TAU);
      g.fillStyle = 'rgba(79,203,147,.16)'; g.fill();
      g.lineWidth = Math.max(1, P * 0.15); g.strokeStyle = 'rgba(79,203,147,1)'; g.stroke();
      g.beginPath(); g.arc(r, r, r * 0.58, 1.05 * Math.PI, 1.55 * Math.PI); g.lineWidth = Math.max(1, P * 0.07); g.strokeStyle = 'rgba(214,255,234,.8)'; g.stroke();
    } else if (kind === 'square') {
      const s = P * 0.62, o = (P - s) / 2;
      g.fillStyle = '#4FCB93'; g.fillRect(o, o, s, s);
      g.fillStyle = 'rgba(220,255,236,.55)'; g.fillRect(o, o, s, Math.max(1, P * 0.08)); g.fillRect(o, o, Math.max(1, P * 0.08), s);
    } else if (kind === 'mote') {
      const gr = g.createRadialGradient(r, r, 0, r, r, r); gr.addColorStop(0, 'rgba(245,242,236,1)'); gr.addColorStop(0.35, 'rgba(245,242,236,.5)'); gr.addColorStop(1, 'rgba(245,242,236,0)');
      g.fillStyle = gr; g.fillRect(0, 0, P, P);
    } else if (kind === 'halo' || kind === 'halor' || kind === 'haloi') {
      const gr = g.createRadialGradient(r, r, 0, r, r, r);
      const c0 = kind === 'halo' ? '79,203,147' : kind === 'haloi' ? '245,242,236' : '217,103,93';
      gr.addColorStop(0, `rgba(${c0},.55)`); gr.addColorStop(0.4, `rgba(${c0},.16)`); gr.addColorStop(1, `rgba(${c0},0)`);
      g.fillStyle = gr; g.fillRect(0, 0, P, P);
    }
    return c;
  }
  function buildSprites() { for (const k of ['bead', 'red', 'ring', 'square', 'mote', 'halo', 'halor', 'haloi']) SPR[k] = SPR_SIZES.map(P => makeSprite(k, P)); }
  function spr(kind, devPx) { const a = SPR[kind]; for (let j = 0; j < a.length; j++) if (SPR_SIZES[j] >= devPx) return a[j]; return a[a.length - 1]; }
  function blit(kind, x, y, size, alpha) {
    if (alpha <= 0.004 || size <= 0) return;
    ctx.globalAlpha = alpha > 1 ? 1 : alpha;
    ctx.drawImage(spr(kind, size * dpr * 1.25), x - size / 2, y - size / 2, size, size);
  }

  /* ---------------- drawing ---------------- */
  const IV = '245,242,236', GR = '79,203,147', RD = '217,103,93', KH = '172,166,142';
  const bands = [new Int32Array(CAP), new Int32Array(CAP), new Int32Array(CAP)], bandN = [0, 0, 0];
  const cls = [new Int32Array(CAP), new Int32Array(CAP), new Int32Array(CAP)], clsN = [0, 0, 0];
  let lost = false, hover = -1, hoverUid = 0, mouse = null, pointerTouch = false;
  const lbl = []; // gate label boxes this frame: {x, y, w, h, ax, ay, bottom}

  function seg(x0, y0, z0, x1, y1, z1) { proj(x0, y0, z0); ctx.moveTo(P_X, P_Y); proj(x1, y1, z1); ctx.lineTo(P_X, P_Y); }
  // a soft light pool on the floor between x0 and x1: one stretched gradient sprite, turned to lie along the lane
  function pool(x0, x1, kind, alpha) {
    if (alpha <= 0.004) return;
    proj(x0, FLOOR, 0); const ax = P_X, ay = P_Y; proj(x1, FLOOR, 0); const bx = P_X, by = P_Y;
    proj((x0 + x1) / 2, FLOOR, 0.3); const dz = Math.hypot(P_X - (ax + bx) / 2, P_Y - (ay + by) / 2);
    const w = Math.hypot(bx - ax, by - ay) * 1.25, h = Math.max(8, dz * 1.7);
    ctx.save(); ctx.translate((ax + bx) / 2, (ay + by) / 2); ctx.rotate(Math.atan2(by - ay, bx - ax));
    ctx.globalAlpha = alpha; ctx.drawImage(spr(kind, 64), -w / 2, -h / 2, w, h); ctx.restore();
  }
  function draw() {
    if (lost) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = 'butt'; ctx.lineJoin = 'bevel'; // round caps tessellate per segment: only the followed path gets them
    follow.dim += ((follow.active || (follow.show && sim < follow.endAt + 1.2) ? 1 : 0) - follow.dim) * (reduced.matches ? 1 : 1 - Math.exp(-frameDt * 6));
    placeLabels();
    drawFloor(); drawLedger(); drawFrames(); drawBoundary(); drawRails(); drawAperture(false); drawMotes(); drawTrails(); drawAgents(); drawAperture(true);
    drawFollow(); drawLeaders();
    ctx.globalAlpha = 1;
  }
  function drawFloor() {
    ctx.lineWidth = 1;
    for (let k = -3; k <= 3; k++) {
      const z = k * 0.13;
      ctx.beginPath(); seg(-1.7, FLOOR, z, 1.9, FLOOR, z);
      ctx.strokeStyle = `rgba(${IV},${(0.03 + 0.03 * (k + 3) / 6).toFixed(3)})`; ctx.stroke();
    }
    ctx.beginPath();
    for (let g = 0; g < 6; g++) seg(GX[g], FLOOR, -0.39, GX[g], FLOOR, 0.39);
    ctx.strokeStyle = `rgba(${IV},.075)`; ctx.stroke();
    // the lane lights the floor under it: a soft ivory pool under the estimation field, a green one under the rails
    ctx.globalCompositeOperation = 'lighter';
    pool(GX[0] - 0.1, GX[3], 'haloi', 0.05 * clamp(inflight / Math.max(1, target), 0.15, 1)); // a drained lane leaves the floor dark
    pool(GX[3] + 0.1, LX, 'halo', 0.06);
    ctx.globalCompositeOperation = 'source-over';
    // where rejected proposals land: a faint red bloom under the council, as strong as recent rejections
    if (rejGlow > 0.01) {
      proj(XR, FLOOR, 0); const x = P_X, y = P_Y; proj(XR + 0.32, FLOOR, 0); const rx = Math.abs(P_X - x) + 8;
      ctx.save(); ctx.translate(x, y); ctx.scale(1, 0.32);
      const gr = ctx.createRadialGradient(0, 0, 0, 0, 0, rx); gr.addColorStop(0, `rgba(${RD},${(0.16 * rejGlow).toFixed(3)})`); gr.addColorStop(1, `rgba(${RD},0)`);
      ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(0, 0, rx, 0, TAU); ctx.fill(); ctx.restore();
    }
  }
  function drawLedger() {
    // the ledger line: hairline from the open block out of frame; blocks sealed at most four a second, linked by hairlines
    ctx.lineWidth = 1;
    ctx.beginPath(); seg(LX, 0, 0, 2.6, 0, 0); ctx.strokeStyle = `rgba(${IV},.2)`; ctx.stroke();
    const k = cam.k0;
    let prevX = null, prevY = 0, prevS = 0;
    for (let b = ledger.length - 1; b >= 0; b--) {
      const B = ledger[b]; proj(B.x, 0, 0);
      const s = clamp((0.011 + 0.008 * Math.log10(1 + B.n)) * k * (cam.D / P_D), 3, 10);
      const age = sim - B.t, fresh = reduced.matches ? 0 : clamp(1 - age / 0.6, 0, 1);
      if (prevX !== null) { ctx.globalAlpha = 0.55; ctx.strokeStyle = `rgba(${IV},.6)`; ctx.beginPath(); ctx.moveTo(prevX - prevS / 2 - 1, prevY); ctx.lineTo(P_X + s / 2 + 1, P_Y); ctx.stroke(); }
      ctx.globalAlpha = 1;
      ctx.fillStyle = B.f ? `rgba(${GR},1)` : fresh > 0 ? `rgba(${GR},${(0.35 + 0.65 * fresh).toFixed(3)})` : `rgba(${IV},.86)`;
      if (!B.f && fresh > 0) { ctx.fillStyle = `rgba(${IV},.86)`; ctx.fillRect(P_X - s / 2, P_Y - s / 2, s, s); ctx.fillStyle = `rgba(${GR},${fresh.toFixed(3)})`; }
      ctx.fillRect(P_X - s / 2, P_Y - s / 2, s, s);
      if (B.f) { ctx.strokeStyle = `rgba(${GR},.9)`; ctx.strokeRect(P_X - s / 2 - 3.5, P_Y - s / 2 - 3.5, s + 7, s + 7); }
      prevX = P_X; prevY = P_Y; prevS = s;
    }
    // the open block: proposals land here and are sealed into the next block
    proj(LX, 0, 0);
    const s0 = clamp(0.026 * k * (cam.D / P_D), 7, 14) * (1 + 0.22 * openPulse);
    ctx.globalAlpha = 1; ctx.strokeStyle = `rgba(${GR},${(0.55 + 0.45 * openPulse).toFixed(3)})`; ctx.lineWidth = 1;
    ctx.strokeRect(P_X - s0 / 2, P_Y - s0 / 2, s0, s0);
    if (prevX !== null) { ctx.strokeStyle = `rgba(${IV},.35)`; ctx.beginPath(); ctx.moveTo(P_X + s0 / 2, P_Y); ctx.lineTo(prevX - prevS / 2 - 1, prevY); ctx.stroke(); }
  }
  function frameQuad(x, hy, hz) { proj(x, hy, hz); ctx.moveTo(P_X, P_Y); proj(x, hy, -hz); ctx.lineTo(P_X, P_Y); proj(x, -hy, -hz); ctx.lineTo(P_X, P_Y); proj(x, -hy, hz); ctx.lineTo(P_X, P_Y); ctx.closePath(); }
  function drawFrames() {
    ctx.lineWidth = 1;
    for (let g = 0; g < 6; g++) {
      if (g === 3) continue; // the council is the aperture
      const [hy, hz] = frameDims(g), x = GX[g], L = 0.055;
      const k = g === 0 ? shutK : 0, col = g === 5 ? GR : k > 0.5 ? KH : IV, f = GF[g];
      ctx.beginPath(); frameQuad(x, hy, hz);
      ctx.strokeStyle = `rgba(${col},${(0.07 + 0.1 * f).toFixed(3)})`; ctx.stroke();
      if (k > 0.01) { // halted: the entry gate's shutter drops, slat by slat (and lifts again on Resume)
        ctx.fillStyle = `rgba(${KH},${(0.08 * k).toFixed(3)})`; ctx.beginPath(); frameQuad(x, hy, hz); ctx.fill();
        ctx.beginPath();
        for (let b = 0; b < 5; b++) {
          const e = easeOut(clamp(k * 1.5 - b * 0.12, 0, 1)), y = hy + ((2 - b) * hy / 3 - hy) * e;
          if (e > 0.002) seg(x, y, -hz, x, y, hz);
        }
        ctx.strokeStyle = `rgba(${KH},${(0.42 * k).toFixed(3)})`; ctx.stroke();
      }
      ctx.beginPath();
      for (const sy of [-1, 1]) for (const sz of [-1, 1]) {
        seg(x, sy * hy, sz * hz, x, sy * (hy - L), sz * hz); seg(x, sy * hy, sz * hz, x, sy * hy, sz * (hz - L * 1.4));
      }
      ctx.strokeStyle = `rgba(${col},${((g === 5 ? 0.62 : 0.36 + 0.39 * k) + 0.4 * f).toFixed(3)})`; ctx.lineWidth = 1 + 0.4 * f; ctx.stroke(); ctx.lineWidth = 1;
    }
  }
  // the boundary: a glowing hairline plane just past the council. Upstream agents jitter (estimation); downstream they
  // run on a grid (deterministic code). Intelligence decides, execution is deterministic.
  const XB = GX[3] + 0.075, BHY = 0.34, BHZ = 0.3;
  function drawBoundary() {
    const hy = BHY, hz = BHZ;
    ctx.beginPath(); frameQuad(XB, hy, hz);
    ctx.fillStyle = `rgba(${GR},.028)`; ctx.fill();
    ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${GR},.13)`; ctx.stroke();
    ctx.beginPath(); seg(XB, hy, -hz, XB, hy, hz); ctx.strokeStyle = `rgba(${GR},.42)`; ctx.stroke(); // its lit top edge
    ctx.globalCompositeOperation = 'lighter'; ctx.lineWidth = 3;
    ctx.beginPath(); seg(XB, hy, -hz, XB, hy, hz); ctx.strokeStyle = `rgba(${GR},.08)`; ctx.stroke();
    ctx.globalCompositeOperation = 'source-over'; ctx.lineWidth = 1;
  }
  const XM = GX[5] + V_RAIL * 0.22; // where a settled square leaves its rail for the ledger
  function drawRails() {
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let k = 0; k < 5; k++) seg(GX[3] + X_SNAP * 0.7, RAIL_Y[k], RAIL_Z, XM, RAIL_Y[k], RAIL_Z);
    ctx.strokeStyle = `rgba(${IV},.11)`; ctx.stroke();
    // the manifold: five rails merge into one ledger line
    ctx.beginPath();
    for (let k = 0; k < 5; k++) {
      const y0 = RAIL_Y[k], cx = XM + (LX - XM) * 0.62;
      for (let n = 0; n <= 14; n++) {
        const u = n / 14, v = 1 - u; proj(v * v * XM + 2 * v * u * cx + u * u * LX, v * v * y0 + 2 * v * u * y0, 0);
        if (n) ctx.lineTo(P_X, P_Y); else ctx.moveTo(P_X, P_Y);
      }
    }
    ctx.strokeStyle = `rgba(${GR},.2)`; ctx.stroke();
    // the grid the deterministic side snaps to: fixed stations along each rail
    ctx.beginPath();
    for (let k = 0; k < 5; k++) for (let x = GX[3] + X_SNAP; x < GX[5]; x += V_RAIL * TICK / 2) seg(x, RAIL_Y[k] - 0.009, RAIL_Z, x, RAIL_Y[k] + 0.009, RAIL_Z);
    ctx.strokeStyle = `rgba(${IV},.16)`; ctx.stroke();
  }
  function drawAperture(front) {
    const x = GX[3], R1 = apR + 0.045, R2 = R1 + 0.032;
    proj(x, 0, 0); const cxp = P_X, cyp = P_Y, cd = P_D;
    if (!front) { // the lens: a soft green light inside the aperture, brightest on a decision
      proj(x, R1, 0); const ry = Math.abs(P_Y - cyp); proj(x, 0, R1); const rx = Math.max(6, Math.abs(P_X - cxp));
      const breathe = reduced.matches ? 0 : 0.04 * Math.sin(sim * 1.1);
      ctx.save(); ctx.translate(cxp, cyp); ctx.scale(rx / ry, 1);
      const gr = ctx.createRadialGradient(0, 0, 0, 0, 0, ry * 1.5);
      gr.addColorStop(0, `rgba(${GR},${(0.13 + breathe + 0.22 * pulse).toFixed(3)})`); gr.addColorStop(0.6, `rgba(${GR},${(0.05 + 0.08 * pulse).toFixed(3)})`); gr.addColorStop(1, `rgba(${GR},0)`);
      ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(0, 0, ry * 1.5, 0, TAU); ctx.fill(); ctx.restore();
    }
    // fine ticks round the ring; each lights where a proposal is decided (green approve, red reject)
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let k = 0; k < NT; k++) {
      const a = (k + 0.5) / NT * TAU, sy = Math.sin(a), sz = Math.cos(a);
      proj(x, sy * R1, sz * R1); const isFront = P_D < cd; if (isFront !== front) continue;
      const len = k % 8 === 0 ? 1.6 : 1;
      ctx.moveTo(P_X, P_Y); proj(x, sy * (R1 + (R2 - R1) * len), sz * (R1 + (R2 - R1) * len)); ctx.lineTo(P_X, P_Y);
    }
    ctx.strokeStyle = `rgba(${IV},${(0.34 + 0.3 * pulse).toFixed(3)})`; ctx.stroke();
    ctx.lineWidth = 1.6;
    for (let k = 0; k < NT; k++) {
      const f = TF[k]; if (f < 0.03) continue;
      const a = (k + 0.5) / NT * TAU, sy = Math.sin(a), sz = Math.cos(a);
      proj(x, sy * R1, sz * R1); if ((P_D < cd) !== front) continue;
      ctx.beginPath(); ctx.moveTo(P_X, P_Y); proj(x, sy * (R2 + 0.012 * f), sz * (R2 + 0.012 * f)); ctx.lineTo(P_X, P_Y);
      ctx.strokeStyle = TC[k] ? `rgba(${RD},${f.toFixed(3)})` : `rgba(${GR},${(f * 0.75).toFixed(3)})`; ctx.stroke();
    }
    // the inner edge of the aperture, a hairline circle
    ctx.lineWidth = 1; ctx.beginPath();
    let pen = false;
    for (let k = 0; k <= 64; k++) {
      const a = k / 64 * TAU; proj(x, Math.sin(a) * apR, Math.cos(a) * apR);
      if ((P_D < cd) !== front) { pen = false; continue; }
      if (pen) ctx.lineTo(P_X, P_Y); else { ctx.moveTo(P_X, P_Y); pen = true; }
    }
    // two-pass glow: a wide faint stroke and a narrower one under the hairline make the aperture's rim luminous
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineWidth = 9; ctx.strokeStyle = `rgba(${GR},${(0.035 + 0.05 * pulse).toFixed(3)})`; ctx.stroke();
    ctx.lineWidth = 3.5; ctx.strokeStyle = `rgba(${GR},${(0.08 + 0.12 * pulse).toFixed(3)})`; ctx.stroke();
    ctx.globalCompositeOperation = 'source-over'; ctx.lineWidth = 1;
    ctx.strokeStyle = `rgba(${GR},${(0.5 + 0.4 * pulse).toFixed(3)})`; ctx.stroke();
  }
  function drawMotes() {
    const shut = 1 - 0.75 * shutK, dim = 1 - 0.7 * follow.dim;
    for (let m = 0; m < MOTES; m++) {
      const o = m * 6, t = MS[m], e = t * t * (3 - 2 * t);
      const x = MX[o] + (MX[o + 3] - MX[o]) * t, y = MX[o + 1] + (MX[o + 4] - MX[o + 1]) * e, z = MX[o + 2] + (MX[o + 5] - MX[o + 2]) * e;
      proj(x, y, z);
      const a = MA[m] * Math.sin(Math.PI * t) * shut * dim * (1 - 0.45 * fog(P_D));
      blit('mote', P_X, P_Y, 1.2 + 1.6 * cam.k0 / 420 * (cam.D / P_D), a);
    }
    ctx.globalAlpha = 1;
  }
  function drawTrails() {
    // two polylines per agent (a bright head, a dim tail), batched by colour and depth band: 12 strokes for every trail.
    // Butt caps and bevel joins: round ones tessellate a cap per segment and cost more than everything else drawn.
    if (quality === 0) return;
    clsN[0] = clsN[1] = clsN[2] = 0;
    for (let i = 0; i < hi; i++) {
      const s = st[i]; if (!s || hc[i] < 2 || s === SETTLE) continue;
      if (quality === 1 && s === FLOW) continue;
      if (s === REJECT && flag[i]) continue;
      if (isFollowed(i)) continue;
      const c = s === FLOW ? 0 : s === REJECT ? 2 : 1; cls[c][clsN[c]++] = i;
    }
    const hair = Math.min(1, 1 / dpr), boost = dpr > 1.4 ? 1.35 : 1;
    const cols = [IV, GR, RD], base = [0.24 * boost, 0.34 * boost, 0.55 * boost], dim = 1 - 0.72 * follow.dim;
    const at = (i, k) => (i * TRAIL + ((hHead - k + TRAIL * 2) % TRAIL)) * 2; // k-th sample back from the newest
    ctx.lineWidth = hair; ctx.lineCap = 'butt'; ctx.lineJoin = 'bevel';
    for (let c = 0; c < 3; c++) {
      const list = cls[c], n = clsN[c];
      for (let band = 0; band < 2; band++) {
        for (let part = 0; part < (quality === 2 ? 2 : 1); part++) {
          ctx.beginPath(); let any = false;
          for (let j = 0; j < n; j++) {
            const i = list[j]; if ((PF[i] < 0.5 ? 1 : 0) !== band) continue;
            const h = hc[i];
            if (part === 0) { // head: now → 1 → 2 samples back
              ctx.moveTo(PX[i], PY[i]); let o = at(i, 0); ctx.lineTo(HIST[o], HIST[o + 1]);
              if (h > 1) { o = at(i, 1); ctx.lineTo(HIST[o], HIST[o + 1]); }
            } else if (h > 2) { // tail: 1 → 3 samples back
              let o = at(i, 1); ctx.moveTo(HIST[o], HIST[o + 1]); o = at(i, 2); ctx.lineTo(HIST[o], HIST[o + 1]);
              if (h > 3) { o = at(i, 3); ctx.lineTo(HIST[o], HIST[o + 1]); }
            } else continue;
            any = true;
          }
          if (!any) continue;
          ctx.globalAlpha = Math.min(1, base[c] * (part ? 0.38 : 1) * (band ? 1 : 0.55) * dim);
          ctx.strokeStyle = `rgb(${cols[c]})`; ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1; ctx.lineWidth = 1;
  }
  let LK = 'bead', LS = 1, LA = 1; // the look of one agent: sprite, size multiplier, alpha (module scope: no allocation per agent)
  function agentLook(i) {
    const s = st[i];
    if (s === FLOW) { LK = 'bead'; LS = 1; LA = 0.86; }
    else if (s === PROP) { LK = 'ring'; LS = 1.7; LA = 0.95; }
    else if (s === RAIL) { LK = 'ring'; LS = 1.45; LA = 0.97; }
    else if (s === SETTLE) { const q = Math.min(1, Math.max(0, T0[i] - 0.22) / 0.46); LK = 'square'; LS = 1.5 * (T0[i] < 0.22 ? 1 + 0.9 * (1 - easeOut(T0[i] / 0.22)) : 0.8 - 0.45 * q); LA = T0[i] < 0.22 ? 1 : 0.85 - 0.55 * q; }
    else { LK = 'red'; LS = 1.15; LA = flag[i] ? 0.9 * (1 - T0[i] / 1.5) : 0.95; }
  }
  function drawAgents() {
    bandN[0] = bandN[1] = bandN[2] = 0;
    for (let i = 0; i < hi; i++) { if (!st[i] || isFollowed(i)) continue; const b = PF[i] > 0.66 ? 0 : PF[i] > 0.33 ? 1 : 2; bands[b][bandN[b]++] = i; }
    const r0 = clamp(0.0036 * cam.k0, 0.8, 2.1) * 2.3, dim = 1 - 0.72 * follow.dim, fade = reduced.matches;
    for (let b = 0; b < 3; b++) {
      const list = bands[b], n = bandN[b];
      for (let j = 0; j < n; j++) {
        const i = list[j]; agentLook(i);
        const born = fade ? 1 : smooth(0, 0.5, sim - BORN[i]);
        blit(LK, PX[i], PY[i], r0 * LS * PS[i], LA * (1 - 0.5 * PF[i]) * born * dim);
      }
    }
    // settled squares glow as they snap
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < hi; i++) if (st[i] === SETTLE && T0[i] < 0.2 && !isFollowed(i)) blit('halo', PX[i], PY[i], r0 * 4.5 * PS[i], 0.32 * (1 - T0[i] / 0.2) * dim);
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    if (!hoverHold && live(hover) && UID[hover] === hoverUid && !isFollowed(hover)) {
      ctx.strokeStyle = `rgba(${IV},.85)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(PX[hover], PY[hover], r0 * 1.7 + 5, 0, TAU); ctx.stroke();
    }
  }
  // the followed proposal: its whole path so far, gate marks, a halo, and a leader line to its tag
  function recordPath() {
    const i = follow.i;
    if (!isFollowed(i)) return;
    follow.x = X[i]; follow.y = Y[i]; follow.z = Z[i];
    if (sim - follow.pt < 0.04 || follow.n >= 900) return;
    follow.pt = sim; const o = follow.n * 3;
    follow.px[o] = X[i]; follow.px[o + 1] = Y[i]; follow.px[o + 2] = Z[i]; follow.ps[follow.n] = st[i]; follow.n++;
  }
  function drawFollow() {
    if (!follow.show || !follow.n) return;
    const a = follow.active ? 1 : clamp(1 - (sim - follow.endAt - 2.2) / 1.4, 0, 1);
    if (a <= 0) { if (!follow.active) { follow.show = false; hideTag(); } return; }
    const colOf = (s) => (s === FLOW ? IV : s === REJECT ? RD : GR);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    for (const pass of [0, 1]) {
      ctx.lineWidth = pass ? 1.3 : 5; ctx.globalAlpha = (pass ? 0.92 : 0.12) * a;
      let prev = -1;
      for (let k = 0; k < follow.n; k++) {
        const o = k * 3; proj(follow.px[o], follow.px[o + 1], follow.px[o + 2]);
        const s = follow.ps[k];
        if (prev !== s) { if (prev >= 0) { ctx.lineTo(P_X, P_Y); ctx.stroke(); } ctx.beginPath(); ctx.moveTo(P_X, P_Y); ctx.strokeStyle = `rgb(${colOf(s)})`; prev = s; }
        else ctx.lineTo(P_X, P_Y);
      }
      if (follow.active) { proj(follow.x, follow.y, follow.z); ctx.lineTo(P_X, P_Y); }
      ctx.stroke();
    }
    ctx.globalAlpha = a; ctx.lineCap = 'butt'; ctx.lineJoin = 'bevel';
    for (const m of follow.marks) { // a small square at every gate it crossed
      proj(m.x, m.y, m.z);
      ctx.fillStyle = m.bad ? `rgb(${RD})` : m.g >= 3 ? `rgb(${GR})` : `rgb(${IV})`;
      ctx.fillRect(P_X - 2.5, P_Y - 2.5, 5, 5); ctx.strokeStyle = 'rgba(11,17,15,.9)'; ctx.lineWidth = 1; ctx.strokeRect(P_X - 3, P_Y - 3, 6, 6);
    }
    ctx.globalAlpha = 1;
    const i = follow.i, live = isFollowed(i);
    proj(follow.x, follow.y, follow.z);
    const x = P_X, y = P_Y, r0 = clamp(0.0036 * cam.k0, 0.8, 2.1) * 2.3;
    if (live) {
      ctx.globalCompositeOperation = 'lighter';
      blit(st[i] === REJECT ? 'halor' : 'halo', x, y, 46 + 20 * pulse, 0.75 * a);
      ctx.globalCompositeOperation = 'source-over';
      agentLook(i); blit(LK, x, y, r0 * LS * 2.1, 1);
      ctx.globalAlpha = 1; ctx.strokeStyle = `rgba(${IV},.95)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y, r0 * 2 + 6, 0, TAU); ctx.stroke();
    }
    // leader: an elbow from the agent to its tag
    if (tagBox && a > 0.05) {
      ctx.globalAlpha = a; ctx.strokeStyle = `rgba(${IV},.7)`; ctx.lineWidth = 1; ctx.beginPath();
      const R = r0 * 2 + 7;
      if (x > tagBox.x - 4 && x < tagBox.x + tagBox.w + 4) { ctx.moveTo(x, y - R); ctx.lineTo(x, Math.min(y - R, tagBox.y + tagBox.h)); } // tag clamped above: straight up
      else {
        const ex = tagBox.side > 0 ? tagBox.x : tagBox.x + tagBox.w, ey = tagBox.y + tagBox.h / 2;
        ctx.moveTo(x + tagBox.side * R * 0.7, y - R * 0.7); ctx.lineTo(ex - tagBox.side * 10, ey); ctx.lineTo(ex, ey);
      }
      ctx.stroke(); ctx.globalAlpha = 1;
    }
  }
  function drawLeaders() {
    ctx.lineWidth = 1; ctx.setLineDash([2, 3]);
    for (const b of lbl) {
      if (!b) continue;
      ctx.strokeStyle = `rgba(${b.c},${b.a})`; ctx.beginPath();
      if (b.bottom) { ctx.moveTo(b.ax, b.ay + 5); ctx.lineTo(b.lx, b.y - 4); } else { ctx.moveTo(b.lx, b.y + b.h + 4); ctx.lineTo(b.ax, b.ay - 5); }
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  /* ---------------- DOM labels, projected from 3D anchors ---------------- */
  const lw = [];
  function measure() {
    el.gates.forEach((li, g) => { lw[g] = [li.offsetWidth, li.offsetHeight]; });
    if (el.ledger) lw[6] = [el.ledger.offsetWidth, el.ledger.offsetHeight];
    if (el.banner) lw[7] = [el.banner.offsetWidth, el.banner.offsetHeight];
    if (el.bound) lw[8] = [el.bound.offsetWidth, el.bound.offsetHeight];
    rowH = Math.max(24, ...el.gates.map((li, g) => (lw[g] ? lw[g][1] : 24)));
  }
  const setPos = (node, x, y) => { const v = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0)`; if (node.__t !== v) { node.style.transform = v; node.__t = v; } };
  function spread(row) { // 1-D: keep each label over its gate, push neighbours apart when they would touch
    if (!row.length) return;
    row.sort((p, q) => p.x - q.x);
    const gap = narrow ? 8 : 14, lo = 4, hiX = W - 4;
    for (let k = 0; k < row.length; k++) { const b = row[k]; b.x = Math.max(b.x, lo); if (k) b.x = Math.max(b.x, row[k - 1].x + row[k - 1].w + gap); }
    for (let k = row.length - 1; k >= 0; k--) { const b = row[k]; b.x = Math.min(b.x, (k === row.length - 1 ? hiX : row[k + 1].x - gap) - b.w); }
    row[0].x = Math.max(row[0].x, lo);
  }
  function placeLabels() {
    lbl.length = 0;
    const top = [], bot = [];
    el.gates.forEach((li, g) => {
      const [hy] = frameDims(g), w = (lw[g] || [80])[0], h = (lw[g] || [0, 24])[1];
      const bottom = narrow && g % 2 === 0;                      // phones: 01 03 05 below the lane, 02 04 06 above
      if (g === 3) proj(GX[3], apR + 0.09, 0); else proj(GX[g], bottom ? -hy : hy, 0);
      const b = { li, g, x: P_X - w / 2, y: bottom ? H - h - 10 : rowTop, w, h, ax: P_X, ay: P_Y, bottom,
        c: g === 5 || g === 3 ? GR : halted && g === 0 ? KH : IV, a: li.classList.contains('is-hit') ? 0.7 : g === 3 ? 0.42 : 0.26 };
      (bottom ? bot : top).push(b); lbl.push(b);
    });
    spread(top); spread(bot);
    for (const b of lbl) { setPos(b.li, b.x, b.y); b.lx = clamp(b.ax, b.x + 6, b.x + b.w - 6); }
    if (el.ledger && lw[6]) { proj(LX + 0.04, 0, 0); setPos(el.ledger, clamp(P_X, 4, W - lw[6][0] - 4), P_Y + 12); }
    // the halt banner: bottom right on wide stages (the trace owns the bottom left), above the lower label row on phones
    if (el.banner && lw[7]) setPos(el.banner, narrow ? 8 : W - lw[7][0] - 14, narrow ? H - rowH - 18 - lw[7][1] : H - lw[7][1] - 14);
    // the boundary's name sits off the far end of its lit top edge, when it clears every gate label and leader
    if (el.bound && lw[8]) {
      proj(XB, BHY, -BHZ);
      const w = lw[8][0], h = lw[8][1], x = P_X + 8, y = P_Y - h + 2;
      let ok = !narrow && x + w < W - 6 && y > rowTop + rowH + 6;
      for (const b of lbl) {
        if (!ok) break;
        if (x < b.x + b.w + 8 && x + w > b.x - 8 && y < b.y + b.h + 6 && y + h > b.y - 6) ok = false; // the label box
        else if (!b.bottom && b.lx > x - 8 && b.lx < x + w + 8 && y < b.ay && y + h > b.y + b.h) ok = false; // its leader
      }
      el.bound.classList.toggle('is-off', !ok);
      if (ok) setPos(el.bound, x, y);
    }
    placeTag(); placeHover();
  }
  let tagBox = null;
  function placeTag() {
    if (!el.tag || el.tag.hidden || !follow.show) { tagBox = null; return; }
    proj(follow.x, follow.y, follow.z);
    const w = el.tag.offsetWidth || 120, h = el.tag.offsetHeight || 34, gap = narrow ? 16 : 26;
    // the side with room; when neither side holds the whole tag (a long verdict on a phone) it is clamped into the
    // stage above the agent, and the leader rises straight to it
    const roomR = W - 6 - (P_X + gap), roomL = P_X - gap - 6;
    const side = roomR >= w ? 1 : roomL >= w ? -1 : roomR >= roomL ? 1 : -1;
    const x = clamp(side > 0 ? P_X + gap : P_X - gap - w, 6, Math.max(6, W - w - 6)), y = clamp(P_Y - h - 22, rowTop + rowH + 8, H - h - 6);
    setPos(el.tag, x, y); tagBox = { x, y, w, h, side };
  }
  function hideTag() { if (el.tag) el.tag.hidden = true; tagBox = null; }

  /* ---------------- the trace (callout) ---------------- */
  const VERDICT = (i, g, limit) => {
    if (g === 1) return [`picked up · ${2 + (UID[i] % 4)} signals`, ''];
    if (g === 2) return ['estimate formed', ''];
    if (g === 3) return ['proposal formed', ''];
    if (g === 4) { const r = RISK[i].toFixed(2), l = limit.toFixed(2); return st[i] === REJECT ? [`rejected · risk ${r} > ${l}`, 'bad'] : [`approved · risk ${r} ≤ ${l}`, 'ok']; }
    if (g === 5) return [`executed · rail ${lane[i] + 1}`, ''];
    return ['settled', 'ok'];
  };
  function row(t, gname, verdict, kind) {
    if (!el.log) return;
    const li = document.createElement('li'); if (kind) li.className = 'is-' + kind;
    const a = document.createElement('span'); a.className = 'sw-t'; a.textContent = t;
    const b = document.createElement('b'); b.textContent = gname;
    const c = document.createElement('span'); c.className = 'sw-v'; c.textContent = verdict;
    li.append(a, b, c); el.log.appendChild(li);
    return li;
  }
  const fmtT = (s) => `${Math.max(0, s).toFixed(2)} s`;
  function t0Of(i) { const t = GT[i * 7 + 1]; return t > UNSET ? t : sim; } // back-dated crossings are negative: only UNSET means "not yet"
  function traceGate(i, g) {
    const [v, kind] = VERDICT(i, g, 1 - strict);
    row(fmtT(GT[i * 7 + g] - t0Of(i)), `0${g} ${GATE[g - 1]}`, v, kind);
    follow.marks.push({ x: X[i], y: Y[i], z: Z[i], g, bad: kind === 'bad' });
    GF[g - 1] = 1;
    const li = el.gates[g - 1]; if (li) li.classList.add('is-hit');
    tagText(i, g);
    if (g === 4) say(`${follow.id}: ${kind === 'bad' ? 'rejected' : 'approved'} by the council.`);
    if (g === 6) say(`${follow.id}: settled.`);
  }
  function traceLedger(id, block) {
    if (id !== follow.id) return;
    const li = row(fmtT(sim - follow.t1), 'Ledger', follow.rec || `sealed in block ${block}`, 'ok');
    if (li) li.dataset.swLedger = '';
    say(`${id}: written to the ledger, block ${block}.`);
    const s = el.tag && el.tag.querySelector('span'); if (s) s.textContent = `settled · block ${block}`;
    if (reduced.matches) draw(); // a still study: re-place the tag (and its leader) for the longer text
  }
  function tagText(i, g) {
    if (!el.tag) return;
    const b = el.tag.querySelector('b'), s = el.tag.querySelector('span');
    if (b) b.textContent = follow.id;
    if (s) s.textContent = st[i] === REJECT ? `rejected · risk ${RISK[i].toFixed(2)}` : g >= 6 ? 'settled' : g > 0 ? `${String(g).padStart(2, '0')} ${GATE[g - 1]}` : 'entering 01';
    el.tag.classList.toggle('is-bad', st[i] === REJECT);
    el.tag.classList.toggle('is-ok', g >= 6);
  }
  function say(t) { if (el.say) el.say.textContent = t; }
  // the ledger trace further down the page answers every announcement with 'oxa:recorded' {id, record, hash, seq}; when
  // the answer is for the proposal in the trace, its last line becomes the record it was chained into and the first 8 hex
  // of that record's hash. Off screen the ledger seals announcements every few seconds, so the answer can come after the
  // drawn path has faded (follow.show is false by then): the open trace is what decides
  document.addEventListener('oxa:recorded', (e) => {
    const d = e.detail;
    if (!d || !d.record || !follow.id || d.id !== follow.id || !el.trace || el.trace.hidden) return;
    const h = /^[0-9a-f]{8}/i.test(d.hash || '') ? d.hash.slice(0, 8).toLowerCase() : '';
    follow.rec = `record ${d.record}${h ? ' · ' + h : ''}`;
    const v = el.log && el.log.querySelector('[data-sw-ledger] .sw-v');
    if (!v) return;
    v.textContent = follow.rec;
    const s = el.tag && !el.tag.hidden && el.tag.querySelector('span'); // its tag on the stage names the same record
    if (s && /^settled/.test(s.textContent)) { s.textContent = `settled · record ${d.record}`; if (reduced.matches) draw(); }
    say(`${d.id}: chained into the ledger below as record ${d.record}.`);
  });
  function setFollowButton() {
    if (!el.follow) return;
    el.follow.setAttribute('aria-pressed', follow.active ? 'true' : 'false');
    el.follow.textContent = follow.active ? 'Stop following' : follow.verdict ? 'Follow another' : 'Follow a proposal';
  }
  function startFollow(i) {
    if (i < 0) {
      if (el.trace) { el.trace.hidden = false; root.classList.add('is-tracing'); }
      if (el.log) el.log.replaceChildren();
      if (el.traceId) el.traceId.textContent = 'Nothing in flight';
      if (el.traceState) { el.traceState.textContent = halted ? 'Halted' : 'Waiting'; el.traceState.className = 'sw-trace-state'; }
      row('—', '—', halted ? 'resume to send new proposals' : 'no proposal in the lane yet', '');
      say(halted ? 'Nothing in flight. Resume to send new proposals.' : 'No proposal in the lane yet.');
      return;
    }
    el.gates.forEach(li => li.classList.remove('is-hit'));
    Object.assign(follow, { active: true, show: true, i, uid: UID[i], id: pid(UID[i]), n: 0, pt: -1, marks: [], verdict: '', endAt: 0, x: X[i], y: Y[i], z: Z[i], t1: t0Of(i), rec: '' });
    if (el.log) el.log.replaceChildren();
    if (el.traceId) el.traceId.textContent = `Proposal ${follow.id}`;
    if (el.traceState) { el.traceState.textContent = 'Live'; el.traceState.className = 'sw-trace-state is-live'; }
    if (el.trace) { el.trace.hidden = false; root.classList.add('is-tracing'); }
    // the gates it already passed, from its own record
    for (let g = 1; g <= gate[i]; g++) {
      const [v, kind] = VERDICT(i, g, 1 - strict);
      row(fmtT(GT[i * 7 + g] - t0Of(i)), `0${g} ${GATE[g - 1]}`, v, kind);
      const li = el.gates[g - 1]; if (li) li.classList.add('is-hit');
    }
    if (el.tag) { el.tag.hidden = false; tagText(i, gate[i]); }
    recordPath();
    setFollowButton();
    say(`Following proposal ${follow.id}${gate[i] ? `, now past gate 0${gate[i]} ${GATE[gate[i] - 1]}` : ', entering gate 01 Signal'}.`);
    if (reduced.matches) settleStill();
  }
  function endFollow(verdict, i) {
    if (!follow.active) return;
    follow.active = false; follow.verdict = verdict; follow.endAt = sim;
    follow.x = X[i]; follow.y = Y[i]; follow.z = Z[i];
    if (el.traceState) { el.traceState.textContent = verdict === 'settled' ? 'Settled' : 'Rejected at 04'; el.traceState.className = 'sw-trace-state ' + (verdict === 'settled' ? 'is-ok' : 'is-bad'); }
    if (el.tag) { const s = el.tag.querySelector('span'); if (s) s.textContent = verdict === 'settled' ? 'settled · sealing' : `rejected at 04 · risk ${RISK[i].toFixed(2)}`; el.tag.classList.toggle('is-ok', verdict === 'settled'); el.tag.classList.toggle('is-bad', verdict !== 'settled'); }
    if (verdict === 'rejected') { row(fmtT(sim - follow.t1), 'Floor', 'fell away · not executed', 'bad'); say(`${follow.id}: rejected at gate 04, never executed.`); }
    setFollowButton();
  }
  function stopFollow() {
    follow.active = false; follow.show = false; follow.verdict = '';
    hideTag(); el.gates.forEach(li => li.classList.remove('is-hit'));
    if (el.trace) el.trace.hidden = true;
    root.classList.remove('is-tracing');
    setFollowButton();
    say('Stopped following.');
    if (reduced.matches) still();
  }
  // a fresh proposal near the front of the lane, so its whole journey is ahead of it
  function pickFresh() {
    let best = -1, bs = -1e9;
    for (let i = 0; i < hi; i++) {
      if (st[i] !== FLOW || gate[i] > 1) continue;
      const s = -Math.abs(X[i] - (GX[0] - 0.01)) * 4 + Z[i] + rnd() * 0.12 - Math.abs(Y[i]) * 0.8;
      if (s > bs) { bs = s; best = i; }
    }
    if (best < 0) for (let i = 0; i < hi; i++) if ((st[i] === FLOW || st[i] === PROP || st[i] === RAIL) && (best < 0 || X[i] < X[best])) best = i;
    return best;
  }
  const live = (i) => i >= 0 && (st[i] === FLOW || st[i] === PROP || st[i] === RAIL);
  function hitTest(mx, my, radius) {
    let best = -1, bd = radius * radius;
    for (let i = 0; i < hi; i++) {
      if (!live(i)) continue;
      const dx = PX[i] - mx, dy = PY[i] - my, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }
  // the agent under the mouse, with hysteresis: it stays the hovered one while it is within 22 px of the pointer, so
  // the hover tag does not flicker between neighbours as the lane flows under a resting cursor
  function updateHover() {
    if (!mouse) { hover = -1; return; }
    const keep = live(hover) && UID[hover] === hoverUid && (PX[hover] - mouse.x) ** 2 + (PY[hover] - mouse.y) ** 2 < 484;
    if (!keep) { hover = hitTest(mouse.x, mouse.y, 14); hoverUid = hover >= 0 ? UID[hover] : 0; }
    cv.style.cursor = hover >= 0 ? 'pointer' : '';
  }
  // the hover tag never covers the followed proposal's tag: it takes the other side, or steps aside; right after a click
  // it waits for the pointer to move, so the new follow is not crowded by a tag for its neighbour
  let hoverHold = null;
  const hits = (x, y, w, h, b) => b && x < b.x + b.w + 6 && x + w > b.x - 6 && y < b.y + b.h + 6 && y + h > b.y - 6;
  function placeHover() {
    const t = el.hov; if (!t) return;
    const on = !hoverHold && hover >= 0 && live(hover) && UID[hover] === hoverUid && !isFollowed(hover);
    if (!on) { if (!t.hidden) t.hidden = true; return; }
    const id = pid(UID[hover]), b = t.firstElementChild;
    if (t.hidden) t.hidden = false;
    if (b && b.textContent !== id) { b.textContent = id; t.__w = t.offsetWidth; t.__h = t.offsetHeight; }
    const w = t.__w || 120, h = t.__h || 32, x = PX[hover], y = clamp(PY[hover] - (t.__h || 32) - 12, 4, H - h - 4);
    let px = x + 16 + w < W - 6 ? x + 16 : x - 16 - w;
    if (hits(px, y, w, h, tagBox)) px = px > x ? x - 16 - w : x + 16;
    if (hits(px, y, w, h, tagBox) || px < 2 || px + w > W - 2) { t.hidden = true; return; }
    setPos(t, px, y);
  }

  /* ---------------- counters, all read from the model ---------------- */
  const fmt = (n) => n.toLocaleString('en-US');
  const fmtN = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n));
  function stats() {
    if (el.inflight) el.inflight.textContent = fmt(inflight);
    if (el.recorded) el.recorded.textContent = fmt(S.settled);
    if (el.rejected) el.rejected.textContent = fmt(S.rejected);
    const span = Math.min(5, Math.max(0.5, sim));
    if (el.rate) el.rate.textContent = fmt(Math.round(S.win.length / span));
    if (el.state) el.state.textContent = halted ? 'Halted' : reduced.matches ? 'Static study' : 'Running';
    root.classList.toggle('is-halted', halted);
    if (el.banner) {
      const txt = !halted ? '' : inflight ? `Halted · no new proposals · ${fmt(inflight)} in flight, draining` : 'Halted · drained · nothing in flight';
      if (el.banner.textContent !== txt) { el.banner.textContent = txt; el.banner.hidden = !txt; if (txt) lw[7] = [el.banner.offsetWidth, el.banner.offsetHeight]; }
    }
  }
  const showN = () => { if (el.nOut) el.nOut.textContent = fmtN(target); if (el.n) el.n.setAttribute('aria-valuetext', `${fmtN(target)} agents`); };
  const showStrict = () => {
    const pct = Math.round(strict * 100), lim = (1 - strict).toFixed(2);
    if (el.strictOut) el.strictOut.textContent = `${pct}%`;
    if (el.strict) el.strict.setAttribute('aria-valuetext', `${pct}% rejected, risk limit ${lim}`);
    if (el.limit) el.limit.textContent = strict > 0 ? `rejects risk > ${lim}` : 'approves every proposal';
  };

  /* ---------------- controls ---------------- */
  if (el.n) {
    el.n.value = Math.round(Math.log(target / 500) / Math.log(12) * 100);
    el.n.addEventListener('input', () => { target = Math.round(500 * Math.pow(12, el.n.value / 100) / 100) * 100; showN(); if (reduced.matches) still(); });
  }
  let tuneT = 0;
  if (el.strict) {
    el.strict.value = Math.round(strict * 100);
    el.strict.addEventListener('input', () => {
      setStrict(el.strict.value / 100); showStrict();
      const li = el.gates[3]; // the council's label lights while its policy is being changed
      if (li) { li.classList.add('is-tuned'); clearTimeout(tuneT); tuneT = setTimeout(() => li.classList.remove('is-tuned'), 900); }
      if (reduced.matches) still(); else measureSoon();
    });
  }
  if (el.halt) {
    el.halt.removeAttribute('aria-pressed'); // the label itself toggles
    el.halt.addEventListener('click', () => { halted = !halted; el.halt.textContent = halted ? 'Resume' : 'Halt'; stats(); if (reduced.matches) still(); else measureSoon(); });
  }
  if (el.follow) el.follow.addEventListener('click', () => { if (follow.active) stopFollow(); else startFollow(pickFresh()); });
  if (el.close) el.close.addEventListener('click', () => { stopFollow(); if (el.follow) el.follow.focus(); });
  // Escape stops following from inside the lab, and also after a click or tap on an agent (focus is then on the page
  // itself); it is left alone while another widget (the nav's chapter list, the menu) holds focus
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || e.defaultPrevented || !(follow.active || follow.show || (el.trace && !el.trace.hidden))) return;
    const t = e.target;
    if (!(root.contains(t) || !t || t === document.body || t === document.documentElement)) return;
    stopFollow(); if (el.follow) el.follow.focus({ preventScroll: true });
  });
  const local = (e) => { const r = cv.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  cv.addEventListener('pointerdown', (e) => { pointerTouch = e.pointerType !== 'mouse'; });
  cv.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse') return;
    mouse = local(e); parT = clamp(mouse.x / W - 0.5, -0.5, 0.5);
    if (hoverHold && Math.hypot(mouse.x - hoverHold.x, mouse.y - hoverHold.y) > 8) hoverHold = null;
    if (reduced.matches || !running()) { updateHover(); draw(); }
  });
  cv.addEventListener('pointerleave', () => { mouse = null; hover = -1; parT = 0; cv.style.cursor = ''; placeHover(); if (reduced.matches) draw(); });
  cv.addEventListener('click', (e) => {
    const p = local(e);
    // a mouse click takes the agent the hover tag names (if it is still under the pointer); a tap searches a
    // finger-sized radius
    const named = !pointerTouch && live(hover) && UID[hover] === hoverUid && (PX[hover] - p.x) ** 2 + (PY[hover] - p.y) ** 2 < 484;
    const i = named ? hover : hitTest(p.x, p.y, pointerTouch ? 30 : 16);
    if (i >= 0 && !isFollowed(i)) { hoverHold = p; startFollow(i); }
  });

  /* ---------------- still studies (prefers-reduced-motion) ---------------- */
  function still() {
    if (follow.show || follow.active) { follow.active = false; follow.show = false; hideTag(); el.gates.forEach(li => li.classList.remove('is-hit')); if (el.trace) el.trace.hidden = true; root.classList.remove('is-tracing'); setFollowButton(); }
    seed = 11; reset(); apR = apT; shutK = halted ? 1 : 0; camera(); warmStart();
    const steps = halted ? 100 : 40; // halted: the lane has had five seconds to drain
    for (let k = 0; k < steps; k++) {
      step(0.05, k >= steps - TRAIL - 1);
      // the ledger line fills as it would have, block by block, but a still study announces nothing to the page
      if (k % 5 === 4 && evPending) { ledger.push({ x: LX, n: evPending.count, t: sim - 9, f: false }); evPending = null; } // blocks then drift right with the model
    }
    evPending = null;
    projectAll(); draw(); stats();
  }
  // reduced motion: following computes the whole journey at once and shows it as a still
  function settleStill() {
    let guard = 0;
    while (follow.active && guard++ < 600) step(0.05, false);
    if (evPending && evPending.followed) flush(true); else evPending = null;
    for (let k = 0; k < TRAIL + 1; k++) step(0.03, true);
    follow.endAt = sim; projectAll(); draw(); stats();
  }

  /* ---------------- sizing, loops, visibility ---------------- */
  let measureQueued = false;
  function measureSoon() { if (measureQueued) return; measureQueued = true; requestAnimationFrame(() => { measureQueued = false; measure(); }); }
  function resize() {
    const r = cv.getBoundingClientRect(); // the canvas band, not the stage (on phones the trace flows below it)
    W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
    const ndpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(3840 * 2160 / (W * H)));
    const rebuild = ndpr !== dpr || !SPR.bead; dpr = ndpr;
    narrow = W < 560;
    root.classList.toggle('is-narrow', narrow);
    root.classList.toggle('is-stacked', W < 820); // the trace flows under the canvas instead of over it
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    if (rebuild) buildSprites();
    measure(); fit();
    hc.fill(0); // trails live in screen space
    camera(); projectAll(); draw();
  }
  let onScreen = false, frameId = 0, bgId = 0, last = performance.now(), ui = 0, booted = false;
  // quality governor: a device that cannot hold the frame rate sheds trail work first (2 all trails · 1 proposals and
  // rejections only · 0 none); it climbs back when frames are cheap again
  let quality = 2, frameDt = 1 / 60, ema = 1 / 60, slowFor = 0, fastFor = 0;
  function govern(rawDt) {
    ema += (rawDt - ema) * 0.08;
    if (ema > 0.038) { slowFor += rawDt; fastFor = 0; } else if (ema < 0.024) { fastFor += rawDt; slowFor = 0; } else { slowFor = 0; fastFor = 0; }
    if (slowFor > 1.5 && quality > 0) { quality--; slowFor = 0; root.dataset.swQuality = quality; }
    if (fastFor > 6 && quality < 2) { quality++; fastFor = 0; root.dataset.swQuality = quality; }
  }
  const running = () => !reduced.matches && !document.hidden;
  function frame(now) {
    frameId = 0;
    if (!running() || !onScreen) return;
    const raw = Math.max(0, (now - last) / 1000), dt = Math.min(0.05, raw); last = now; frameDt = dt;
    if (raw < 0.5) govern(raw);
    step(dt, true);
    if (mouse) updateHover();
    draw(); flush(false);
    if ((ui += dt) > 0.15) { ui = 0; stats(); }
    frameId = requestAnimationFrame(frame);
  }
  // off-screen the model keeps a slow pulse (four steps a second, nothing drawn) so the page still hears it settle
  function bg() {
    bgId = 0;
    if (!running() || onScreen) return;
    const now = performance.now(), dt = Math.min(0.5, (now - last) / 1000); last = now;
    for (let k = 0; k < 5; k++) step(dt / 5, false);
    flush(false); stats();
    bgId = setTimeout(bg, 250);
  }
  function schedule() {
    cancelAnimationFrame(frameId); frameId = 0; clearTimeout(bgId); bgId = 0; last = performance.now();
    if (!running() || !booted) return;
    if (onScreen) { hc.fill(0); frameId = requestAnimationFrame(frame); } else bgId = setTimeout(bg, 250);
  }
  function boot() {
    if (booted) return; booted = true;
    resize();
    if (reduced.matches) still(); else { reset(); camera(); warmStart(); for (let k = 0; k < 30; k++) step(0.05, k > 22); projectAll(); draw(); stats(); }
    schedule();
  }
  showN(); showStrict(); setFollowButton();
  // first measure in a frame, not at script time: reading layout mid-load forced an extra full layout of the page
  requestAnimationFrame(boot);
  // a still study is re-run on resize (its trails live in screen space), except while it shows a followed proposal:
  // then the same moment is re-projected, so a rotated phone keeps the journey and its trace
  if ('ResizeObserver' in window) new ResizeObserver(([e]) => {
    if (!booted) return;
    const r = e && e.contentRect; if (r && Math.round(r.width) === W && Math.round(r.height) === H) return; // its first report repeats boot's size
    resize(); if (reduced.matches && !follow.show) still();
  }).observe(cv);
  else window.addEventListener('resize', () => { if (booted) resize(); });
  (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { if (booted) resize(); watchRatio(); }, { once: true }); })();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (booted) { measure(); fit(); draw(); } });
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; schedule(); }, { rootMargin: '80px 0px' }).observe(stage);
  else onScreen = true;
  document.addEventListener('visibilitychange', schedule);
  reduced.addEventListener('change', () => { if (!booted) return; if (reduced.matches) still(); schedule(); stats(); });
  cv.addEventListener('contextlost', () => { lost = true; });
  cv.addEventListener('contextrestored', () => { lost = false; buildSprites(); draw(); });
})();
