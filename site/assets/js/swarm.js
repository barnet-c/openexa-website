/* OpenEXA — the swarm lab (home §03, Platform §03). An illustrative model, drawn in 3D on a 2D canvas (no WebGL needed).
   Agents carry proposals left to right through six gates. Signals drift in and are picked up at 01 Signal; through
   02 Predict and 03 Decide agents estimate (they jitter), and at 03 each forms a proposal (a green ring). At 04 Approve the
   execution council, an aperture of fine ticks, approves or rejects against a risk limit you can tighten: the aperture
   closes, proposals queue at it, rejected ones fall away and fade. Past the council execution is deterministic: approved
   proposals snap onto five rails that advance in lockstep, settle at 06 as solid squares and are sealed into blocks on a
   hash-chained ledger line. Halt stops new proposals while open work drains. "Follow a proposal" (or click/tap an agent)
   traces one proposal gate by gate until it settles or is rejected. Every counter is derived from the model's state;
   'Settled / s' is an exponentially weighted rate of the model's own settlements (tau 0.8 s of model time).
   The page hears the model through document events, both batched on one clock (at most four flushes a second):
     'oxa:settled'  {id, lane, ts, gate: 'settle', count, followed}   proposals settled since the previous flush
     'oxa:rejected' {id, ts, count, followed, gate: 'approve'}        proposals the council rejected since then
   A ledger on the page ([data-ledger="live"], home §06) answers with 'oxa:recorded' {id, record, hash, seq, followed}; the
   trace of a followed proposal then names that record, and its button scrolls the ledger into view and dispatches
   'oxa:inspect' {record, seq, focus}. Without a ledger (Platform) the trace names the lab's own ledger line, where the
   followed proposal's block was drawn (a followed rejection is logged there too, in red).
   The model runs while the lab is on screen. Off screen it writes nothing to the DOM and steps (a 4 Hz pulse, nothing
   drawn) only while the page's ledger is within a viewport or a followed proposal is still in flight; otherwise model
   time stops: nothing is extrapolated. 'Pause motion' freezes it all; hidden tabs too.
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
    halt: $('[data-sw-halt]'), state: $('[data-sw-state]'), follow: $('[data-sw-follow]'), motion: $('[data-sw-motion]'),
    inflight: $('[data-sw-inflight]'), recorded: $('[data-sw-recorded]'), rejected: $('[data-sw-rejected]'), rate: $('[data-sw-rate]'),
    gates: Array.from(root.querySelectorAll('[data-sw-gates] > li')), limit: $('[data-sw-limit]'), ledger: $('[data-sw-ledger]'),
    banner: $('[data-sw-banner]'), tag: $('[data-sw-agent]'), trace: $('[data-sw-callout]'), traceId: $('[data-sw-trace-id]'),
    traceState: $('[data-sw-trace-state]'), log: $('[data-sw-log]'), close: $('[data-sw-trace-close]'), say: $('[data-sw-say]'),
    hov: $('[data-sw-hover]'), bound: $('[data-sw-bound]'),
  };
  const LEDGER = document.querySelector('[data-ledger="live"]'); // the page's own ledger (home §06); Platform has none
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
  const TAU_R = 0.8;                                            // 'Settled / s': exponential weighting of settlements, model seconds
  const st = new Uint8Array(CAP), gate = new Uint8Array(CAP), lane = new Uint8Array(CAP), flag = new Uint8Array(CAP), hc = new Uint8Array(CAP);
  const annR = new Uint8Array(CAP);                             // a followed rejection is announced when it lands, not at the decision
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

  let target = window.innerWidth < 600 ? 700 : 1800, strict = 0.12, halted = false, paused = false;
  let popCap = 0;                                               // a device that cannot carry the population lowers it (0: no cap)
  const pop = () => (popCap && popCap < target ? popCap : target);
  let sim = 0, seq = 41000 + Math.floor(Math.random() * 9000), inflight = 0, spawnAcc = 0, railPh = 0, histT = 0, hHead = 0, pulse = 0, rejGlow = 0;
  const S = { settled: 0, rejected: 0, rate: 0 };               // derived counters read these, nothing else
  const ledger = []; let openPulse = 0;
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
    st[i] = FLOW; gate[i] = 0; hc[i] = 0; flag[i] = 0; annR[i] = 0;
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
    const keepRail = clamp(0.2075 / V_RAIL * limit, 0, 1), n = pop();
    for (let k = 0; k < n; k++) {
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
    st.fill(0); annR.fill(0); hi = 0; nFree = 0; sim = 0; inflight = 0; spawnAcc = 0; railPh = 0; histT = 0; hHead = 0; pulse = 0; rejGlow = 0;
    S.settled = S.rejected = 0; S.rate = 0; ledger.length = 0; TF.fill(0); GF.fill(0); evPending = null; rjPending = null;
  }

  /* ---------------- following one proposal ---------------- */
  const follow = { active: false, show: false, i: -1, uid: 0, id: '', n: 0, px: new Float32Array(900 * 3), ps: new Uint8Array(900), pt: 0,
    marks: [], verdict: '', endAt: 0, dim: 0, x: 0, y: 0, z: 0 };
  const isFollowed = (i) => follow.active && follow.i === i && follow.uid === UID[i];

  /* ---------------- settled → ledger blocks; settled and rejected → the page's events (one clock, at most 4 flushes/s) ---------------- */
  let evPending = null, rjPending = null, evLast = -1e9, evTimer = 0;
  function sealed(i) {
    const f = isFollowed(i);
    if (!evPending) evPending = { id: '', lane: 0, count: 0, followed: false };
    evPending.count++;
    if (f || !evPending.followed) { evPending.id = pid(UID[i]); evPending.lane = lane[i] + 1; evPending.followed = f; }
    openPulse = 1;
  }
  function refused(i) { // a rejection joins the next flush; the followed one names it
    const f = isFollowed(i);
    if (!rjPending) rjPending = { id: '', count: 0, followed: false };
    rjPending.count++;
    if (f || !rjPending.followed) { rjPending.id = pid(UID[i]); rjPending.followed = f; }
  }
  // the clock is read at dispatch, not the frame's timestamp, so listeners never see two flushes closer than 250 ms;
  // a forced flush (a followed proposal in a still study) waits for its turn instead of breaking the limit. The trace
  // learns of its proposal's flush before the event goes out, so a ledger that answers inside the event is heard.
  function flush(force) {
    if (!evPending && !rjPending) return;
    const nowMs = performance.now(), wait = 250 - (nowMs - evLast);
    if (wait > 0) { if (force && !evTimer) evTimer = setTimeout(() => { evTimer = 0; flush(true); }, wait + 1); return; }
    evLast = nowMs;
    const p = evPending, q = rjPending, ts = Date.now(); evPending = rjPending = null;
    if (p) {
      ledger.push({ x: LX, n: p.count, t: sim, f: p.followed });
      if (ledger.length > 64) ledger.shift();
      if (p.followed) traceFlushed(p.id, 'settled');
      document.dispatchEvent(new CustomEvent('oxa:settled', { detail: { id: p.id, lane: p.lane, ts, gate: 'settle', count: p.count, followed: p.followed } }));
    }
    if (q) {
      if (q.followed) {
        // the rejection you followed is logged on the lab's own ledger line, as a record of its own (red): the newest
        // block, so a settled digest sealed in the same flush steps one place along the line (it is not drawn yet)
        const b = ledger[ledger.length - 1];
        if (p && b && b.t === sim) b.x += 0.03;
        ledger.push({ x: LX, n: 1, t: sim, f: true, r: true });
        if (ledger.length > 64) ledger.shift();
        openPulse = 1;
        traceFlushed(q.id, 'rejected');
      }
      document.dispatchEvent(new CustomEvent('oxa:rejected', { detail: { id: q.id, ts, count: q.count, followed: q.followed, gate: 'approve' } }));
    }
  }

  /* ---------------- one step of the model ---------------- */
  function step(dt, project) {
    sim += dt;
    apR += (apT - apR) * (1 - Math.exp(-dt * 5));
    shutK += ((halted ? 1 : 0) - shutK) * (1 - Math.exp(-dt * 8));
    S.rate *= Math.exp(-dt / TAU_R);                             // each settlement below adds 1/tau: settlements per second, weighted
    const limit = 1 - strict, cong = 0.1 + 1.05 * strict, n = pop();
    if (!halted) { // inflow keeps the lane near the population you chose
      const tEst = (GX[3] - GX[0]) / 0.2 * (1 + cong * 0.3) + (1 - strict) * (GX[5] - GX[3]) / V_RAIL;
      spawnAcc += clamp(n / tEst + (n - inflight) * 0.9, 0, 1.6 * n / tEst) * dt; // a refill arrives as a wave
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
        // the proposal you follow estimates at twice the pace, so its council decision comes a few seconds after the click
        X[i] += SPD[i] * dt * slow * (1 + 0.16 * Math.sin(sim * 1.3 + PH[i])) * (isFollowed(i) ? 2 : 1);
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
          S.settled++; S.rate += 1 / TAU_R;
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
          if (Y[i] <= FLOOR) {
            Y[i] = FLOOR; flag[i] = 1; T0[i] = 0; rejGlow = Math.min(1, rejGlow + 0.05);
            if (annR[i]) { annR[i] = 0; refused(i); } // the followed rejection is announced once its fall is over
            if (isFollowed(i)) endFollow('rejected', i);
          }
        } else if (T0[i] > 1.5) { kill(i); continue; }
      }
    }
    inflight = fl;
    if (halted && fl === 0) S.rate = 0; // drained: nothing can settle, so the weighted rate keeps no tail into a Resume
    // signals drifting in: data the agents pick up at 01 (nobody picks it up while halted: it fades at the closed gate)
    for (let m = 0; m < MOTES; m++) { MS[m] += MV[m] * dt / 1.05; if (MS[m] >= 1) mote(m, false); }
    for (let k = 0; k < NT; k++) if (TF[k] > 0) TF[k] = Math.max(0, TF[k] - dt / 0.32);
    for (let g = 0; g < 6; g++) if (GF[g] > 0) GF[g] = Math.max(0, GF[g] - dt / 0.9);
    pulse = Math.max(0, pulse - dt / 0.3); openPulse = Math.max(0, openPulse - dt / 0.25); rejGlow = Math.max(0, rejGlow - dt * 0.35);
    for (const b of ledger) b.x += V_LED * dt;
    while (ledger.length && ledger[0].x > 2.4) ledger.shift();
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
      if (f) annR[i] = 1; else refused(i);
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
  let par = 0, parT = 0, P_X = 0, P_Y = 0, P_D = 1, breath = 1;
  function camera() {
    par += (parT - par) * 0.04;
    // the camera's slow breathing is decoration: a device that had to drop every trail (quality 0) lets it ease out, so
    // the projected labels come to rest and their transforms stop being rewritten every frame
    breath += ((quality === 0 ? 0 : 1) - breath) * 0.03; if (breath < 0.002) breath = 0;
    const still = reduced.matches, b = still ? 0 : breath;
    const yaw = YAW + b * 0.03 * Math.sin(sim * 0.11) + (still ? 0 : par * 0.05), pitch = PITCH + b * 0.012 * Math.sin(sim * 0.083);
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
  let tcv = null, tctx = null, tdpr = 1; // the trails' own layer (see trailLayer), or none at DPR 1.25 and under
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
      const C = B.r ? RD : GR; // a followed rejection's record is red, every settlement's green
      ctx.fillStyle = B.f ? `rgba(${C},1)` : fresh > 0 ? `rgba(${GR},${(0.35 + 0.65 * fresh).toFixed(3)})` : `rgba(${IV},.86)`;
      if (!B.f && fresh > 0) { ctx.fillStyle = `rgba(${IV},.86)`; ctx.fillRect(P_X - s / 2, P_Y - s / 2, s, s); ctx.fillStyle = `rgba(${GR},${fresh.toFixed(3)})`; }
      ctx.fillRect(P_X - s / 2, P_Y - s / 2, s, s);
      if (B.f) { ctx.strokeStyle = `rgba(${C},.9)`; ctx.strokeRect(P_X - s / 2 - 3.5, P_Y - s / 2 - 3.5, s + 7, s + 7); }
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
    // dense screens draw them on their own layer at 1.25 device px per CSS px, composited in one drawImage
    const g = tctx || ctx, kd = tctx ? tdpr : dpr;
    if (tctx) { tctx.setTransform(1, 0, 0, 1, 0, 0); tctx.globalAlpha = 1; tctx.clearRect(0, 0, tcv.width, tcv.height); tctx.setTransform(tdpr, 0, 0, tdpr, 0, 0); }
    const hair = Math.min(1, 1 / kd), boost = kd > 1.4 ? 1.35 : 1;
    const cols = [IV, GR, RD], base = [0.24 * boost, 0.34 * boost, 0.55 * boost], dim = 1 - 0.72 * follow.dim;
    const at = (i, k) => (i * TRAIL + ((hHead - k + TRAIL * 2) % TRAIL)) * 2; // k-th sample back from the newest
    g.lineWidth = hair; g.lineCap = 'butt'; g.lineJoin = 'bevel';
    let drew = false;
    for (let c = 0; c < 3; c++) {
      const list = cls[c], n = clsN[c];
      for (let band = 0; band < 2; band++) {
        for (let part = 0; part < (quality === 2 ? 2 : 1); part++) {
          g.beginPath(); let any = false;
          for (let j = 0; j < n; j++) {
            const i = list[j]; if ((PF[i] < 0.5 ? 1 : 0) !== band) continue;
            const h = hc[i];
            if (part === 0) { // head: now → 1 → 2 samples back
              g.moveTo(PX[i], PY[i]); let o = at(i, 0); g.lineTo(HIST[o], HIST[o + 1]);
              if (h > 1) { o = at(i, 1); g.lineTo(HIST[o], HIST[o + 1]); }
            } else if (h > 2) { // tail: 1 → 3 samples back
              let o = at(i, 1); g.moveTo(HIST[o], HIST[o + 1]); o = at(i, 2); g.lineTo(HIST[o], HIST[o + 1]);
              if (h > 3) { o = at(i, 3); g.lineTo(HIST[o], HIST[o + 1]); }
            } else continue;
            any = true;
          }
          if (!any) continue;
          g.globalAlpha = Math.min(1, base[c] * (part ? 0.38 : 1) * (band ? 1 : 0.55) * dim);
          g.strokeStyle = `rgb(${cols[c]})`; g.stroke(); drew = true;
        }
      }
    }
    g.globalAlpha = 1; g.lineWidth = 1;
    if (tctx && drew) ctx.drawImage(tcv, 0, 0, W, H);
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
    row.sort((p, q) => p.ax - q.ax); // gate order (by anchor): a wide label (04 with its policy line) must not jump a neighbour
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
    if (el.ledger && lw[6]) {
      // the ledger line runs on to the right at a slope the camera sets (parallax, breathing): the label hangs 12 px under
      // the line's lowest point across its own width, so the right-hand blocks never sit on its text
      proj(LX + 1, 0, 0); const ex = P_X, ey = P_Y;
      proj(LX + 0.04, 0, 0);
      const x = clamp(P_X, 4, W - lw[6][0] - 4), k = Math.abs(ex - P_X) > 1 ? (ey - P_Y) / (ex - P_X) : 0;
      setPos(el.ledger, x, P_Y + Math.max(0, k * (x + lw[6][0] - P_X)) + 12);
    }
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
  // the followed proposal's tag on the stage: its text is model state (TG), written to the DOM only while it is drawn
  let tagBox = null;
  const TG = { b: '', s: '', cls: '', on: false, ver: 0, shown: -1, w: 120, h: 34 };
  function tagSet(s, cls) { if (TG.s !== s || TG.cls !== cls) { TG.s = s; TG.cls = cls; TG.ver++; } }
  function placeTag() {
    if (!el.tag) return;
    if (!TG.on || !follow.show) { if (!el.tag.hidden) el.tag.hidden = true; tagBox = null; return; }
    if (TG.shown !== TG.ver || el.tag.hidden) { // a new verdict: write it, then measure it once (not every frame)
      el.tag.hidden = false;
      const b = el.tag.firstElementChild, s = el.tag.lastElementChild;
      if (b && b.textContent !== TG.b) b.textContent = TG.b;
      if (s && s.textContent !== TG.s) s.textContent = TG.s;
      el.tag.classList.toggle('is-ok', TG.cls === 'ok'); el.tag.classList.toggle('is-bad', TG.cls === 'bad');
      TG.w = el.tag.offsetWidth || 120; TG.h = el.tag.offsetHeight || 34; TG.shown = TG.ver;
    }
    proj(follow.x, follow.y, follow.z);
    const w = TG.w, h = TG.h, gap = narrow ? 16 : 26;
    // the side with room; when neither side holds the whole tag (a long verdict on a phone) it is clamped into the
    // stage above the agent, and the leader rises straight to it
    const roomR = W - 6 - (P_X + gap), roomL = P_X - gap - 6;
    const side = roomR >= w ? 1 : roomL >= w ? -1 : roomR >= roomL ? 1 : -1;
    const x = clamp(side > 0 ? P_X + gap : P_X - gap - w, 6, Math.max(6, W - w - 6)), y = clamp(P_Y - h - 22, rowTop + rowH + 8, H - h - 6);
    setPos(el.tag, x, y); tagBox = { x, y, w, h, side };
  }
  function hideTag() { TG.on = false; if (el.tag && !el.tag.hidden) el.tag.hidden = true; tagBox = null; }

  /* ---------------- the trace (callout) ----------------
     The trace is a small model (T): one row per gate from the start (the ones still ahead are pending), then the
     ledger. It is written to the DOM only while the lab is on screen; off screen a followed proposal can still finish
     its journey (the model pulses) and the trace shows it when the lab is back. */
  const VERDICT = (i, g, limit) => {
    if (g === 1) return [`picked up · ${2 + (UID[i] % 4)} signals`, ''];
    if (g === 2) return ['estimate formed', ''];
    if (g === 3) return ['proposal formed', ''];
    if (g === 4) { const r = RISK[i].toFixed(2), l = limit.toFixed(2); return st[i] === REJECT ? [`rejected · risk ${r} > ${l}`, 'bad'] : [`approved · risk ${r} ≤ ${l}`, 'ok']; }
    if (g === 5) return [`executed · rail ${lane[i] + 1}`, ''];
    return ['settled', 'ok'];
  };
  const fmtT = (s) => `${Math.max(0, s).toFixed(2)} s`;
  function t0Of(i) { const t = GT[i * 7 + 1]; return t > UNSET ? t : sim; } // back-dated crossings are negative: only UNSET means "not yet"
  const T = { open: false, id: '', head: '', state: '', cls: '', rows: [], hit: 0, outcome: '', wait: false, waitT: 0 };
  const rowOf = (k) => T.rows.find(r => r.k === k);
  function setRow(k, t, v, cls, rec) { const r = rowOf(k); if (!r) return; r.t = t; r.v = v; r.cls = cls; r.rec = rec || null; r.ver++; }
  function journeyRows() { // 01 … 06 and the ledger, all pending: they fill in as the proposal advances
    const rows = [];
    for (let g = 1; g <= 6; g++) rows.push({ k: 'g' + g, name: `0${g} ${GATE[g - 1]}`, t: null, v: '', cls: 'pend', rec: null, ver: 0 });
    rows.push({ k: 'led', name: 'Ledger', t: null, v: '', cls: 'pend', rec: null, ver: 0 });
    return rows;
  }
  function traceGate(i, g) {
    const [v, kind] = VERDICT(i, g, 1 - strict);
    setRow('g' + g, GT[i * 7 + g] - t0Of(i), v, kind);
    if (g === 4 && kind === 'bad') { // a rejected proposal never reaches 05 or 06: its last rows are the floor and the record
      const at = T.rows.findIndex(r => r.k === 'g5');
      if (at >= 0) T.rows.splice(at, 2, { k: 'floor', name: 'Floor', t: null, v: '', cls: 'pend', rec: null, ver: 0 });
    }
    follow.marks.push({ x: X[i], y: Y[i], z: Z[i], g, bad: kind === 'bad' });
    GF[g - 1] = 1; T.hit |= 1 << (g - 1);
    tagText(i, g);
    if (g === 4) say(`${follow.id}: ${kind === 'bad' ? 'rejected' : 'approved'} by the council.`);
    if (g === 6) say(`${follow.id}: settled.`);
    touch();
  }
  // the followed proposal's announcement is going out: with a ledger on the page the trace waits for its record;
  // without one (Platform) the trace names what the lab itself drew: the block on its own ledger line (green for a
  // settlement, red for the rejection), and the screen reader hears where the inspectable ledger is
  function traceFlushed(id, outcome) {
    if (!T.open || id !== T.id) return;
    const t = sim - follow.t1;
    if (LEDGER) {
      setRow('led', t, outcome === 'settled' ? 'sealing into the ledger…' : 'recording the rejection…', 'wait');
      T.wait = true; clearTimeout(T.waitT);
      T.waitT = setTimeout(() => { // no answer: say so, but keep listening (a late answer still fills it in)
        T.waitT = 0; const r = rowOf('led');
        if (T.wait && r && r.cls === 'wait') { setRow('led', r.t, outcome === 'settled' ? 'sealed · the ledger did not answer' : 'rejected · the ledger did not answer', 'ok'); touch(); }
      }, 10000);
      if (outcome === 'settled') tagSet('settled · sealing…', 'ok');
    } else {
      const what = outcome === 'settled' ? "sealed into the lab's ledger line" : "rejection logged on the lab's ledger line";
      setRow('led', t, what, outcome === 'settled' ? 'ok' : 'bad');
      const r = rowOf('led'); if (r) r.link = 'index.html#governance'; // its name links to the inspectable ledger
      if (outcome === 'settled') tagSet('settled · sealed', 'ok');
      say(`${id}: ${what}; the inspectable ledger is on the home page.`);
    }
    touch();
  }
  function tagText(i, g) {
    TG.b = follow.id; TG.on = true;
    tagSet(st[i] === REJECT ? `rejected · risk ${RISK[i].toFixed(2)}` : g >= 6 ? 'settled' : g > 0 ? `${String(g).padStart(2, '0')} ${GATE[g - 1]}` : 'entering 01',
      st[i] === REJECT ? 'bad' : g >= 6 ? 'ok' : '');
  }
  let sayText = null;
  function say(t) { sayText = t; touch(); }
  // the ledger further down the page answers every announcement with 'oxa:recorded' {id, record, hash, seq, followed};
  // when the answer is for the proposal in the trace, its ledger row becomes a button naming that record and the first
  // 8 hex of its hash. The answer can come after the drawn path has faded: the open trace is what decides.
  document.addEventListener('oxa:recorded', (e) => {
    const d = e.detail;
    if (!d || !d.record || !T.open || !T.wait || d.id !== T.id) return;
    T.wait = false; clearTimeout(T.waitT); T.waitT = 0;
    const r = rowOf('led'), rec = String(d.record).slice(0, 12);
    const hash = /^[0-9a-f]{8}/i.test(d.hash || '') ? d.hash.slice(0, 8).toLowerCase() : '';
    setRow('led', r ? r.t : sim - follow.t1, '', 'rec', { record: rec, hash, seq: Number.isFinite(+d.seq) && d.seq !== null && d.seq !== '' ? +d.seq : null });
    if (T.outcome !== 'rejected') tagSet(`settled · record ${rec}`, 'ok');
    say(`${d.id}: ${T.outcome === 'rejected' ? 'its rejection is recorded' : 'sealed'} in the ledger below as record ${rec}.`);
    touch();
  });
  // the record button: brings the ledger into view (centred under the nav), then, once the page has landed (the
  // ledger renders what it holds when it is in view), asks it to show that record. The ledger is screens below the lab,
  // so the trip is taken the way the site takes every long jump (site.js, nav): what it passes over and lands on is
  // revealed at once (no half-revealed paper streams past, and the landing is measured without an entrance offset), the
  // page lands at once, and where same-document view transitions exist the ledger comes in as a sheet over a still of
  // the lab (html[data-jump], styled by the nav's CSS); reduced motion or no view transitions: a plain cut. Then
  // 'oxa:jump' {from, to}, as after any long jump. A hop of 1.5 screens or less glides.
  let inspectRaf = 0;
  function ledgerY() { // the scroll position that centres the ledger in the room under the bar (top-aligned when taller)
    const navH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 0;
    const r = LEDGER.getBoundingClientRect(), room = window.innerHeight - navH;
    return Math.max(0, Math.min(document.documentElement.scrollHeight - window.innerHeight, Math.round(window.scrollY + r.top - navH - Math.max(0, (room - r.height) / 2))));
  }
  function revealPassed(a, b) { // site.js's reveal classes: .is-in shows, .is-cut marks a skipped entrance, .is-instant drops transitions for two frames
    const y = window.scrollY;
    document.querySelectorAll('.will-reveal:not(.is-in)').forEach((n) => {
      const r = n.getBoundingClientRect();
      if (!(r.width || r.height) || r.top + y >= b || r.bottom + y <= a) return;
      n.classList.add('is-cut', 'is-in', 'is-instant');
      requestAnimationFrame(() => requestAnimationFrame(() => n.classList.remove('is-instant')));
    });
  }
  // the landing holds while the page settles: a smooth scroll still under way when the trip began (the focus that
  // brought the button into view, with Enter pressed at once) carries on after the cut and would leave the ledger up to
  // a few dozen px off centre. For at most 0.7 s the ledger is kept where it landed; the reader's own wheel, touch, key
  // or pointer ends the hold at once.
  let holdRaf = 0;
  const HOLD_END = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
  function unhold() { cancelAnimationFrame(holdRaf); holdRaf = 0; HOLD_END.forEach((k) => window.removeEventListener(k, unhold, true)); }
  function hold() {
    unhold();
    HOLD_END.forEach((k) => window.addEventListener(k, unhold, { capture: true, passive: true }));
    const t0 = performance.now(); let calm = 0;
    const f = () => {
      const y = ledgerY(), dt = performance.now() - t0;
      if (Math.abs(window.scrollY - y) > 1) { window.scrollTo({ top: y, behavior: 'instant' }); calm = 0; } else calm++;
      if (dt < 700 && (calm < 8 || dt < 300)) holdRaf = requestAnimationFrame(f); else unhold();
    };
    holdRaf = requestAnimationFrame(f);
  }
  function toLedger(rec, kbd) {
    if (!LEDGER) return;
    cancelAnimationFrame(inspectRaf); inspectRaf = 0; unhold();
    // a scroll still under way (the focus that brought the button into view, a wheel's glide) finishes first: a cut
    // taken mid-glide is undone by the glide's remaining frames. Two still frames, and 0.12 s after the button took
    // keyboard focus (its scroll into view starts a frame or two late); half a second at most.
    let sy = window.scrollY, still = 0; const t0 = performance.now();
    const settle = () => {
      const y = window.scrollY, now = performance.now(); still = Math.abs(y - sy) < 0.5 ? still + 1 : 0; sy = y;
      if ((still < 2 || (kbd && now - recFocusT < 120)) && now - t0 < 500) { inspectRaf = requestAnimationFrame(settle); return; }
      inspectRaf = 0; trip(rec, kbd);
    };
    inspectRaf = requestAnimationFrame(settle);
  }
  let recFocusT = -1e9;
  if (el.log) el.log.addEventListener('focusin', (e) => { if (e.target.closest('[data-sw-rec]')) recFocusT = performance.now(); });
  function trip(rec, kbd) {
    // the ledger is asked for the record once it has been told it is in view: two frames, and, for a ledger that draws
    // what it held only when it comes into view, until its record is on the line (half a second at most)
    const ask = () => {
      let n = 0;
      const drawn = () => rec.seq === null || !!LEDGER.querySelector(`.lt-rec[data-seq="${rec.seq}"]`);
      const f = () => {
        if (++n < 2 || (!drawn() && n < 30)) { inspectRaf = requestAnimationFrame(f); return; }
        inspectRaf = 0;
        document.dispatchEvent(new CustomEvent('oxa:inspect', { detail: { record: rec.record, seq: rec.seq, focus: !!kbd } }));
      };
      inspectRaf = requestAnimationFrame(f);
    };
    const from = window.scrollY, y = ledgerY();
    if (Math.abs(y - from) > 1.5 * window.innerHeight) {
      const de = document.documentElement;
      const go = () => {
        revealPassed(Math.min(from, y), Math.max(from, y) + window.innerHeight);
        window.scrollTo({ top: ledgerY(), behavior: 'instant' }); // measured again: nothing on the way is mid-entrance now
        document.dispatchEvent(new CustomEvent('oxa:jump', { detail: { from, to: window.scrollY } }));
        hold();
        ask();
      };
      if (reduced.matches || typeof document.startViewTransition !== 'function' || document.hidden) { go(); return; }
      de.dataset.jump = y > from ? 'down' : 'up';
      let vt;
      try { vt = document.startViewTransition(go); } catch (err) { delete de.dataset.jump; go(); return; }
      vt.ready.catch(() => {}); vt.updateCallbackDone.catch(() => {});
      vt.finished.catch(() => {}).then(() => { delete de.dataset.jump; });
      return;
    }
    window.scrollTo({ top: y, behavior: reduced.matches ? 'auto' : 'smooth' });
    const t0 = performance.now(), y0 = window.scrollY; let lastY = y0, still = 0, moved = false;
    const land = () => { // landed: at the target, or stopped for four frames once it moved, or 1.6 s at most
      const sy = window.scrollY, dt = performance.now() - t0;
      if (Math.abs(sy - y0) > 1) moved = true;
      still = Math.abs(sy - lastY) < 0.5 ? still + 1 : 0; lastY = sy;
      if (Math.abs(sy - y) > 1.5 && (moved ? still < 4 : dt < 400) && dt < 1600) { inspectRaf = requestAnimationFrame(land); return; }
      inspectRaf = 0;
      ask();
    };
    inspectRaf = requestAnimationFrame(land);
  }
  if (el.log) el.log.addEventListener('click', (e) => {
    const b = e.target.closest('[data-sw-rec]'); if (!b) return;
    const r = rowOf('led'); if (r && r.rec) toLedger(r.rec, e.detail === 0);
  });

  /* ---------------- writing the trace to the DOM (on screen only) ---------------- */
  let inLoop = false, uiDirty = false;
  function touch() { uiDirty = true; if (!inLoop && onScreen) syncUI(); }
  function syncUI() {
    uiDirty = false;
    if (sayText !== null && el.say) { el.say.textContent = sayText; sayText = null; }
    if (el.follow) {
      const pressed = follow.active ? 'true' : 'false', label = follow.active ? 'Stop following' : T.outcome ? 'Follow another' : 'Follow a proposal';
      if (el.follow.getAttribute('aria-pressed') !== pressed) el.follow.setAttribute('aria-pressed', pressed);
      if (el.follow.textContent !== label) el.follow.textContent = label;
    }
    el.gates.forEach((li, g) => li.classList.toggle('is-hit', T.open && !!(T.hit & (1 << g))));
    if (!el.trace) return;
    if (el.trace.hidden === T.open) { el.trace.hidden = !T.open; root.classList.toggle('is-tracing', T.open); }
    if (!T.open) return;
    if (el.traceId && el.traceId.textContent !== T.head) el.traceId.textContent = T.head;
    if (el.traceState) {
      if (el.traceState.textContent !== T.state) el.traceState.textContent = T.state;
      const c = 'sw-trace-state' + (T.cls ? ' ' + T.cls : ''); if (el.traceState.className !== c) el.traceState.className = c;
    }
    if (!el.log) return;
    const keep = new Set(T.rows.map(r => r.k));
    Array.from(el.log.children).forEach(li => { if (!keep.has(li.dataset.k)) li.remove(); });
    T.rows.forEach((r, n) => {
      let li = null;
      for (const c of el.log.children) if (c.dataset.k === r.k) { li = c; break; }
      if (!li) {
        li = document.createElement('li'); li.dataset.k = r.k; li.__ver = -1;
        const a = document.createElement('span'); a.className = 'sw-t';
        const b = document.createElement('b'); b.textContent = r.name;
        const c = document.createElement('span'); c.className = 'sw-v';
        li.append(a, b, c);
      }
      if (el.log.children[n] !== li) el.log.insertBefore(li, el.log.children[n] || null);
      if (li.__ver === r.ver) return;
      const was = li.__cls; li.__ver = r.ver; li.__cls = r.cls;
      li.className = (r.cls ? 'is-' + r.cls : '') + (was === 'pend' && r.cls !== 'pend' ? ' is-filled' : '');
      li.children[0].textContent = r.t === null ? '—' : fmtT(r.t);
      if (r.link && !li.children[1].firstElementChild) { // a page without a ledger: the row's name leads to the home page's
        const a = document.createElement('a'); a.href = r.link; a.className = 'sw-led-a';
        a.setAttribute('aria-label', 'The ledger on the home page');
        const ar = document.createElement('i'); ar.setAttribute('aria-hidden', 'true'); ar.textContent = ' →';
        a.append(r.name, ar); li.children[1].replaceChildren(a);
      }
      const v = li.children[2];
      if (r.rec) { // the ledger's answer: a button that takes the reader to that record
        const btn = document.createElement('button');
        btn.type = 'button'; btn.className = 'sw-rec'; btn.dataset.swRec = r.rec.record; if (r.rec.seq !== null) btn.dataset.swSeq = r.rec.seq;
        btn.setAttribute('aria-label', `Record ${r.rec.record}${r.rec.hash ? ', hash ' + r.rec.hash : ''}: show it in the ledger below`);
        btn.append(`record ${r.rec.record}${r.rec.hash ? ' · ' + r.rec.hash : ''} `);
        const ar = document.createElement('i'); ar.setAttribute('aria-hidden', 'true'); ar.textContent = '↓'; btn.append(ar);
        v.replaceChildren(btn);
      } else v.textContent = r.v;
    });
  }

  /* ---------------- following ---------------- */
  function startFollow(i) {
    if (i < 0) {
      clearTimeout(T.waitT);
      Object.assign(T, { open: true, id: '', head: 'Nothing in flight', state: halted ? 'Halted' : 'Waiting', cls: '', hit: 0, outcome: '', wait: false, waitT: 0 });
      T.rows = [{ k: 'none', name: '—', t: null, v: halted ? 'resume to send new proposals' : 'no proposal in the lane yet', cls: '', rec: null, ver: 1 }];
      say(halted ? 'Nothing in flight. Resume to send new proposals.' : 'No proposal in the lane yet.');
      return;
    }
    clearTimeout(T.waitT);
    Object.assign(follow, { active: true, show: true, i, uid: UID[i], id: pid(UID[i]), n: 0, pt: -1, marks: [], verdict: '', endAt: 0, x: X[i], y: Y[i], z: Z[i], t1: t0Of(i) });
    Object.assign(T, { open: true, id: follow.id, head: `Proposal ${follow.id}`, state: 'In flight', cls: 'is-live', rows: journeyRows(), hit: 0, outcome: '', wait: false, waitT: 0 });
    // the gates it already passed, from its own record (back-dated: its 01 line is when it really crossed 01)
    for (let g = 1; g <= gate[i]; g++) { const [v, kind] = VERDICT(i, g, 1 - strict); setRow('g' + g, GT[i * 7 + g] - t0Of(i), v, kind); T.hit |= 1 << (g - 1); }
    tagText(i, gate[i]);
    recordPath();
    say(`Following proposal ${follow.id}${gate[i] ? `, now past gate 0${gate[i]} ${GATE[gate[i] - 1]}` : ', entering gate 01 Signal'}.`);
    if (reduced.matches) settleStill();
  }
  function endFollow(verdict, i) {
    if (!follow.active) return;
    follow.active = false; follow.verdict = verdict; follow.endAt = sim;
    follow.x = X[i]; follow.y = Y[i]; follow.z = Z[i];
    T.outcome = verdict; T.state = verdict === 'settled' ? 'Settled' : 'Rejected at 04'; T.cls = verdict === 'settled' ? 'is-ok' : 'is-bad';
    if (verdict === 'rejected') {
      tagSet(`rejected at 04 · risk ${RISK[i].toFixed(2)}`, 'bad');
      setRow('floor', sim - follow.t1, 'fell away · not executed', 'bad');
      say(`${follow.id}: rejected at gate 04, never executed.`);
    } else { const r = rowOf('led'); if (r && r.cls === 'pend') tagSet('settled · sealing…', 'ok'); }
    touch();
  }
  function clearFollow() { // the trace and the stage forget the followed proposal (nothing is announced)
    follow.active = false; follow.show = false; follow.verdict = '';
    clearTimeout(T.waitT); Object.assign(T, { open: false, id: '', rows: [], hit: 0, outcome: '', wait: false, waitT: 0 });
    hideTag(); touch();
  }
  function stopFollow() {
    clearFollow();
    say('Stopped following.');
    if (reduced.matches) still();
  }
  // a fresh proposal about 0.4 s (at the follow's own pace) before gate 02, so its decision comes soon after the click
  function pickFresh() {
    let best = -1, bs = -1e9;
    for (let i = 0; i < hi; i++) {
      if (st[i] !== FLOW || gate[i] !== 1) continue;
      const lead = (GX[1] - X[i]) / (2 * SPD[i]);
      if (lead < 0.12 || lead > 1.2) continue;
      const s = -Math.abs(lead - 0.4) * 2.5 + Z[i] * 0.9 - Math.abs(Y[i]) * 0.9 + rnd() * 0.04;
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

  /* ---------------- counters, all read from the model (written only while the lab is on screen) ---------------- */
  const fmt = (n) => n.toLocaleString('en-US');
  const fmtN = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n));
  const put = (node, s) => { // a lone text node is rewritten in place (no node swapped into the tree, no restyle)
    if (!node) return;
    const t = node.firstChild;
    if (t && t.nodeType === 3 && !t.nextSibling) { if (t.data !== s) t.data = s; } else if (node.textContent !== s) node.textContent = s;
  };
  function stats() {
    put(el.inflight, fmt(inflight));
    put(el.recorded, fmt(S.settled));
    put(el.rejected, fmt(S.rejected));
    // halted and drained, nothing is settling: the weighted rate's tail is not shown as settlements
    put(el.rate, fmt(halted && inflight === 0 ? 0 : Math.round(S.rate)));
    put(el.state, reduced.matches ? (halted ? 'Halted' : 'Static study') : paused ? (halted ? 'Halted · paused' : 'Paused') : halted ? 'Halted' : 'Running');
    root.classList.toggle('is-halted', halted);
    if (el.banner) {
      const txt = !halted ? '' : inflight ? `Halted · no new proposals · ${fmt(inflight)} in flight, draining` : 'Halted · drained · nothing in flight';
      if (el.banner.textContent !== txt) { el.banner.textContent = txt; el.banner.hidden = !txt; if (txt) lw[7] = [el.banner.offsetWidth, el.banner.offsetHeight]; }
    }
  }
  const showN = () => {
    const capped = popCap && popCap < target, txt = capped ? `${fmtN(target)} · capped to ${fmtN(popCap)} on this device` : fmtN(target);
    put(el.nOut, txt);
    if (el.n) el.n.setAttribute('aria-valuetext', capped ? `${fmtN(target)} agents, capped to ${fmtN(popCap)} on this device` : `${fmtN(target)} agents`);
  };
  // the council's live state at 04: the share it approves and the risk it rejects (in this model risk is uniform on
  // 0..1, so a limit of 0.88 approves 88% of proposals)
  const showStrict = () => {
    const pct = Math.round(strict * 100), lim = (1 - strict).toFixed(2);
    put(el.strictOut, `${pct}%`);
    if (el.strict) el.strict.setAttribute('aria-valuetext', `${pct}% rejected, risk limit ${lim}`);
    if (el.limit) {
      const a = el.limit.children[0], r = el.limit.children[2];
      if (a && r) { put(a, strict > 0 ? `approves ${100 - pct}%` : 'approves every proposal'); put(r, strict > 0 ? `rejects risk > ${lim}` : ''); el.limit.classList.toggle('is-all', !(strict > 0)); }
      else put(el.limit, strict > 0 ? `approves ${100 - pct}% · rejects risk > ${lim}` : 'approves every proposal');
    }
  };
  let flashA = null;
  function flashRejected() { // a policy change shows first where its effect is counted
    const n = el.rejected;
    if (!n || reduced.matches || !n.animate) return;
    if (flashA) flashA.cancel();
    flashA = n.animate([{ color: '#D9675D' }, { color: '#D9675D', offset: 0.35 }], { duration: 900, easing: 'ease-out' });
  }

  /* ---------------- controls ---------------- */
  if (el.n) {
    el.n.value = Math.round(Math.log(target / 500) / Math.log(12) * 100);
    // a deliberate choice of population is measured afresh: the device cap (if any) is lifted until frames say otherwise
    el.n.addEventListener('input', () => { target = Math.round(500 * Math.pow(12, el.n.value / 100) / 100) * 100; if (popCap) { popCap = 0; delete root.dataset.swCap; } showN(); if (reduced.matches) still(); });
  }
  let tuneT = 0;
  if (el.strict) {
    el.strict.value = Math.round(strict * 100);
    el.strict.addEventListener('input', () => {
      setStrict(el.strict.value / 100); showStrict(); flashRejected();
      const li = el.gates[3]; // the council's label lights while its policy is being changed
      if (li) { li.classList.add('is-tuned'); clearTimeout(tuneT); tuneT = setTimeout(() => li.classList.remove('is-tuned'), 900); }
      if (reduced.matches) still(); else measureSoon();
    });
  }
  if (el.halt) {
    el.halt.removeAttribute('aria-pressed'); // the label itself toggles
    el.halt.addEventListener('click', () => { halted = !halted; el.halt.textContent = halted ? 'Resume' : 'Halt'; stats(); if (reduced.matches) still(); else measureSoon(); });
  }
  // Pause motion (WCAG 2.2.2): model time, drawing and the off-screen pulse all stop; the counters hold
  if (el.motion) {
    el.motion.hidden = reduced.matches;
    el.motion.addEventListener('click', () => {
      paused = !paused;
      el.motion.textContent = paused ? 'Resume motion' : 'Pause motion'; // the label itself toggles (as the overture's)
      root.classList.toggle('is-paused', paused);
      stats(); schedule();
    });
  }
  if (el.follow) el.follow.addEventListener('click', () => { if (follow.active) stopFollow(); else startFollow(pickFresh()); });
  if (el.close) el.close.addEventListener('click', () => { stopFollow(); if (el.follow) el.follow.focus(); });
  // Escape stops following from inside the lab, and also after a click or tap on an agent (focus is then on the page
  // itself); it is left alone while another widget (the nav's chapter list, the menu) holds focus, and while no part of
  // the lab is on screen (after the record button's trip focus may still sit on that button: Escape is then the ledger's)
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || e.defaultPrevented || !(follow.active || follow.show || T.open)) return;
    const box = root.getBoundingClientRect(); if (box.bottom <= 0 || box.top >= window.innerHeight) return;
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
    if (booted && (reduced.matches || !running())) { updateHover(); paint(); }
  });
  cv.addEventListener('pointerleave', () => { mouse = null; hover = -1; parT = 0; cv.style.cursor = ''; placeHover(); if (booted && !running()) paint(); });
  cv.addEventListener('click', (e) => {
    if (!booted) return;
    const p = local(e);
    // a mouse click takes the agent the hover tag names (if it is still under the pointer); a tap searches a
    // finger-sized radius
    const named = !pointerTouch && live(hover) && UID[hover] === hoverUid && (PX[hover] - p.x) ** 2 + (PY[hover] - p.y) ** 2 < 484;
    const i = named ? hover : hitTest(p.x, p.y, pointerTouch ? 30 : 16);
    if (i >= 0 && !isFollowed(i)) { hoverHold = p; startFollow(i); if (!running()) paint(); }
  });

  /* ---------------- still studies (prefers-reduced-motion) ---------------- */
  function still() {
    clearFollow();
    seed = 11; reset(); apR = apT; shutK = halted ? 1 : 0; camera(); warmStart();
    const steps = halted ? 100 : 40; // halted: the lane has had five seconds to drain
    inLoop = true;
    for (let k = 0; k < steps; k++) {
      step(0.05, k >= steps - TRAIL - 1);
      // the ledger line fills as it would have, block by block, but a still study announces nothing to the page
      if (k % 5 === 4 && evPending) { ledger.push({ x: LX, n: evPending.count, t: sim - 9, f: false }); evPending = null; } // blocks then drift right with the model
      rjPending = null;
    }
    evPending = null; rjPending = null;
    inLoop = false;
    projectAll(); paint();
    if (onScreen) { stats(); syncUI(); }
  }
  // reduced motion: following computes the whole journey at once and shows it as a still; only its outcome is announced
  function settleStill() {
    let guard = 0;
    inLoop = true;
    while (follow.active && guard++ < 600) step(0.05, false);
    const fe = evPending && evPending.followed ? evPending : null, fr = rjPending && rjPending.followed ? rjPending : null;
    evPending = rjPending = null;
    for (let k = 0; k < TRAIL + 1; k++) step(0.03, true);
    evPending = fe && Object.assign(fe, { count: 1 }); rjPending = fr && Object.assign(fr, { count: 1 });
    flush(true);
    inLoop = false;
    follow.endAt = sim; projectAll(); paint(); stats(); syncUI();
  }

  /* ---------------- sizing, loops, visibility ---------------- */
  let measureQueued = false;
  function measureSoon() { if (measureQueued) return; measureQueued = true; requestAnimationFrame(() => { measureQueued = false; measure(); if (booted && !running()) paint(); }); }
  // the trails' own layer: at most 1.25 device pixels per CSS pixel, composited onto the stage in one drawImage
  // (thin, soft strokes lose nothing at that density, and they are most of the drawing cost at DPR 2-3)
  function trailLayer() {
    tdpr = Math.min(dpr, 1.25);
    if (tdpr > dpr - 0.01) { tcv = null; tctx = null; return; }
    if (!tcv) { tcv = document.createElement('canvas'); tctx = tcv.getContext('2d'); }
    if (!tctx) { tcv = null; return; }
    tcv.width = Math.round(W * tdpr); tcv.height = Math.round(H * tdpr);
  }
  let stale = false;
  function paint() { if (onScreen && !lost) { stale = false; draw(); } else stale = true; } // nothing is drawn off screen
  function resize() {
    const r = cv.getBoundingClientRect(); // the canvas band, not the stage (on phones the trace flows below it)
    W = Math.max(1, Math.round(r.width)); H = Math.max(1, Math.round(r.height));
    const ndpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(3840 * 2160 / (W * H)));
    const rebuild = ndpr !== dpr || !SPR.bead; dpr = ndpr;
    narrow = W < 560;
    root.classList.toggle('is-narrow', narrow);
    root.classList.toggle('is-stacked', W < 820); // the trace flows under the canvas instead of over it
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    // a dense backing store (DPR 2+ or over 2 MP) starts without the estimation field's trails
    const qStart = dpr >= 2 || cv.width * cv.height > 2e6 ? 1 : 2;
    if (quality > qStart) { quality = qStart; root.dataset.swQuality = quality; }
    trailLayer();
    if (rebuild) buildSprites();
    measure(); fit();
    hc.fill(0); // trails live in screen space
    camera(); projectAll(); paint();
  }
  let onScreen = false, near = false, ledgerNear = false, frameId = 0, bgId = 0, last = performance.now(), ui = 0, booted = false;
  // quality governor, driven by a frame-time EMA: above 20 ms a device sheds trail work (2 all trails · 1 proposals and
  // rejections only · 0 none); it tries the level above again only after cheap frames for a while, and waits twice as
  // long after each drop (a stall passes, a slow device is not made to stutter every few seconds); at level 0, a device
  // still under 30 fps carries fewer agents, a step at a time, and the Agents output says so
  let quality = 2, frameDt = 1 / 60, ema = 1 / 60, workEma = 0, slowFor = 0, fastFor = 0, capFor = 0, coolFor = 0, retry = 6;
  function govern(raw, work) {
    ema += (raw - ema) * 0.1; workEma += (work - workEma) * 0.1; coolFor += raw;
    if (ema > 0.020) { slowFor += raw; fastFor = 0; } else { slowFor = 0; fastFor = ema < 0.0185 && workEma < 0.006 ? fastFor + raw : 0; }
    if (slowFor > 1 && quality > 0 && coolFor > 1.5) { quality--; retry = Math.min(96, retry * 2); slowFor = 0; coolFor = 0; root.dataset.swQuality = quality; }
    else if (fastFor > retry && quality < 2) { quality++; fastFor = 0; coolFor = 0; root.dataset.swQuality = quality; }
    capFor = quality === 0 && ema > 1 / 30 ? capFor + raw : 0;
    const floor = narrow ? 1200 : 1800, cur = pop();
    if (capFor > 2 && cur > floor && inflight <= cur * 1.15) { // the last step has taken effect: the lane is down to it
      popCap = Math.max(floor, Math.round(cur * 0.8 / 100) * 100); capFor = 0;
      root.dataset.swCap = popCap; showN();
    }
  }
  const running = () => !reduced.matches && !document.hidden && !paused;
  // off screen the model steps only while the page's ledger is near, or a followed proposal has not finished
  const followPending = () => !!((evPending && evPending.followed) || (rjPending && rjPending.followed));
  const pulseOK = () => booted && running() && !onScreen && (ledgerNear || follow.active || followPending());
  function frame(now) {
    frameId = 0;
    if (!running() || !onScreen) return;
    const raw = Math.max(0, (now - last) / 1000), dt = Math.min(0.05, raw); last = now; frameDt = dt;
    const t0 = performance.now();
    inLoop = true;
    step(dt, true);
    if (mouse) updateHover();
    draw(); flush(false);
    inLoop = false;
    if (uiDirty) syncUI();
    if ((ui += dt) > 0.15) { ui = 0; stats(); }
    if (raw < 0.5) govern(raw, (performance.now() - t0) / 1000);
    frameId = requestAnimationFrame(frame);
  }
  // the off-screen pulse: four model steps a second, nothing drawn, nothing written to the DOM
  function bg() {
    bgId = 0;
    if (!pulseOK()) return;
    const now = performance.now(), dt = Math.min(0.5, (now - last) / 1000); last = now;
    inLoop = true;
    for (let k = 0; k < 5; k++) step(dt / 5, false);
    flush(false);
    inLoop = false;
    bgId = setTimeout(bg, 250);
  }
  function schedule() {
    cancelAnimationFrame(frameId); frameId = 0; clearTimeout(bgId); bgId = 0; last = performance.now();
    if (!booted || !running()) return;
    if (onScreen) { hc.fill(0); frameId = requestAnimationFrame(frame); } else if (pulseOK()) bgId = setTimeout(bg, 250);
  }
  // the model starts when the lab comes within a viewport, or when the ledger it feeds does
  function boot() {
    if (booted) return; booted = true;
    resize(); root.dataset.swQuality = quality;
    if (reduced.matches) still(); else { reset(); camera(); warmStart(); inLoop = true; for (let k = 0; k < 30; k++) step(0.05, k > 22); inLoop = false; projectAll(); paint(); }
    stats(); // once, at the model's birth (a viewport away at most): the counters never hold a zero the model does not
    schedule();
  }
  let bootQueued = false;
  function wantBoot() { if (!booted && !bootQueued && (near || ledgerNear)) { bootQueued = true; requestAnimationFrame(() => { bootQueued = false; boot(); }); } }
  showN(); showStrict();
  // a still study is re-run on resize (its trails live in screen space), except while it shows a followed proposal:
  // then the same moment is re-projected, so a rotated phone keeps the journey and its trace
  if ('ResizeObserver' in window) new ResizeObserver(([e]) => {
    if (!booted) return;
    const r = e && e.contentRect; if (r && Math.round(r.width) === W && Math.round(r.height) === H) return; // its first report repeats boot's size
    resize(); if (reduced.matches && !follow.show) still();
  }).observe(cv);
  else window.addEventListener('resize', () => { if (booted) resize(); });
  (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { if (booted) resize(); watchRatio(); }, { once: true }); })();
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { if (booted) { measure(); fit(); paint(); } });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(([e]) => {
      onScreen = e.isIntersecting; root.classList.toggle('is-off', !onScreen);
      if (onScreen && booted) { if (stale) { projectAll(); paint(); } stats(); if (uiDirty) syncUI(); }
      schedule();
    }, { rootMargin: '80px 0px' }).observe(stage);
    new IntersectionObserver(([e]) => { near = e.isIntersecting; wantBoot(); }, { rootMargin: '100% 0px' }).observe(stage);
    if (LEDGER) new IntersectionObserver(([e]) => { ledgerNear = e.isIntersecting; wantBoot(); if (!onScreen) schedule(); }, { rootMargin: '100% 0px' }).observe(LEDGER);
  } else { onScreen = near = true; wantBoot(); }
  document.addEventListener('visibilitychange', schedule);
  reduced.addEventListener('change', () => { if (el.motion) el.motion.hidden = reduced.matches; if (!booted) return; if (reduced.matches) still(); schedule(); if (onScreen) stats(); });
  cv.addEventListener('contextlost', () => { lost = true; });
  cv.addEventListener('contextrestored', () => { lost = false; buildSprites(); paint(); });
})();
