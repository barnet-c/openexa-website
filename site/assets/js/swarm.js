/* OpenEXA — the swarm, live.
   Thousands of agents flow left to right through six gates. Each agent carries a proposal; at gate 04 the council
   approves or rejects against a policy you can tighten. Rejected agents leave downward and fade. Recorded agents land
   in the ledger on the right. One halt switch stops every new proposal while open ones drain. Illustrative. */
(function () {
  'use strict';
  const root = document.querySelector('[data-swarm-live]');
  if (!root) return;
  const cv = root.querySelector('canvas'), ctx = cv.getContext('2d');
  const $ = (s) => root.querySelector(s);
  const el = { n: $('[data-sw-n]'), nOut: $('[data-sw-n-out]'), strict: $('[data-sw-strict]'), strictOut: $('[data-sw-strict-out]'), halt: $('[data-sw-halt]'), state: $('[data-sw-state]'),
    inflight: $('[data-sw-inflight]'), recorded: $('[data-sw-recorded]'), rejected: $('[data-sw-rejected]'), rate: $('[data-sw-rate]') };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const IVORY = '245, 242, 236', KHAKI = '172, 166, 142', GREEN = '79, 203, 147', RED = '214, 96, 86';
  const GATES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];

  let seed = 3;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };

  let target = window.innerWidth < 600 ? 700 : 1800, strict = 0.12, halted = false;
  const agents = [];
  const S = { recorded: 0, rejected: 0, recent: [], flash: 0 };
  function spawn() {
    const lane = rnd();
    agents.push({ x: -0.02 - rnd() * 0.08, y: 0.18 + lane * 0.64, vy: 0, sp: 0.09 + rnd() * 0.07, gate: 0, state: 'flow', t: 0, size: 0.8 + rnd() * 1.2, ph: rnd() * 6.283, risk: rnd() });
  }
  for (let i = 0; i < target; i++) { spawn(); const a = agents[agents.length - 1]; a.x = rnd(); a.gate = Math.floor(a.x * 6); }

  let W = 0, H = 0, dpr = 1, narrow = false;
  const PADX = 26, PADT = 46, PADB = 34;
  let LEDGER_W = 92;
  const gateX = (g) => PADX + (g + 0.5) / 6 * (W - PADX * 2 - LEDGER_W);
  const laneW = () => (W - PADX * 2 - LEDGER_W);
  function resize() {
    dpr = Math.min(3, window.devicePixelRatio || 1);
    const r = cv.getBoundingClientRect(); W = Math.max(1, Math.floor(r.width)); H = Math.max(1, Math.floor(r.height));
    narrow = W < 600; LEDGER_W = narrow ? 48 : 92;
    cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function step(dt) {
    // population follows the slider
    const deficit = target - agents.filter(a => a.state === 'flow').length;
    if (!halted && deficit > 0) for (let i = 0; i < Math.min(deficit, 40); i++) spawn();
    let recentNow = 0;
    for (let i = agents.length - 1; i >= 0; i--) {
      const a = agents[i]; a.t += dt;
      if (a.state === 'flow') {
        a.x += a.sp * dt * (0.85 + 0.3 * Math.sin(a.t * 2 + a.ph));
        a.y += Math.sin(a.t * 1.6 + a.ph) * 0.0006;
        const g = Math.min(5, Math.floor(Math.max(0, a.x) * 6));
        if (g > a.gate) {
          a.gate = g;
          if (g === 3 && a.risk < strict) { a.state = 'reject'; a.vy = 0.05 + rnd() * 0.05; S.rejected++; S.flash = 1; continue; }
        }
        if (a.x >= 0.985) { a.state = 'record'; a.t = 0; a.rx = PADX + a.x * laneW(); a.ry = a.y; S.recorded++; recentNow++; }
      } else if (a.state === 'reject') {
        a.x += a.sp * 0.25 * dt; a.vy += 0.16 * dt; a.y += a.vy * dt;
        if (a.y > 1.15) agents.splice(i, 1);
      } else if (a.state === 'record') {
        if (a.t > 1.2) agents.splice(i, 1);
      }
    }
    if (recentNow) S.recent.push({ t: performance.now(), n: recentNow });
    const cutoff = performance.now() - 5000; while (S.recent.length && S.recent[0].t < cutoff) S.recent.shift();
    S.flash = Math.max(0, S.flash - dt * 2);
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.font = '500 10px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
    const top = PADT, bot = H - PADB, lw = laneW();
    // gates
    for (let g = 0; g < 6; g++) {
      const x = gateX(g), council = g === 3, last = g === 5;
      ctx.strokeStyle = council ? `rgba(${RED}, ${0.35 + 0.4 * S.flash})` : last ? `rgba(${GREEN}, .5)` : `rgba(${IVORY}, .16)`;
      ctx.setLineDash(council || last ? [] : [2, 6]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bot); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = council ? `rgba(${RED}, .9)` : last ? `rgba(${GREEN}, .95)` : `rgba(${IVORY}, .5)`;
      ctx.fillText(narrow ? `0${g + 1}` : `0${g + 1}  ${GATES[g].toUpperCase()}`, x, top - 22);
      if (council) { ctx.fillStyle = `rgba(${RED}, .7)`; ctx.fillText(narrow ? `${Math.round(strict * 100)}% REJECTED` : `COUNCIL · ${Math.round(strict * 100)}% REJECTED`, x, bot + 18); }
    }
    // ledger column
    const lx = W - PADX - LEDGER_W + 18;
    ctx.fillStyle = `rgba(${GREEN}, .06)`; ctx.fillRect(lx, top, LEDGER_W - 18, bot - top);
    ctx.strokeStyle = `rgba(${GREEN}, .35)`; ctx.strokeRect(lx + .5, top + .5, LEDGER_W - 19, bot - top - 1);
    ctx.fillStyle = `rgba(${GREEN}, .9)`; ctx.fillText(narrow ? 'LOG' : 'LEDGER', lx + (LEDGER_W - 18) / 2, top - 22);
    const rows = Math.min(S.recorded, Math.floor((bot - top - 16) / 6));
    for (let r = 0; r < rows; r++) { const y = bot - 8 - r * 6; const w = 18 + ((S.recorded - r) * 7919 % 41); ctx.fillStyle = `rgba(${GREEN}, ${r < 3 ? .9 : .45})`; ctx.fillRect(lx + 8, y, Math.max(6, Math.min(w, LEDGER_W - 34)), 2); }
    // agents
    for (const a of agents) {
      const x = PADX + a.x * lw, y = top + a.y * (bot - top);
      if (a.state === 'flow') {
        const past = a.gate >= 4;
        ctx.fillStyle = past ? `rgba(${GREEN}, .85)` : a.gate >= 3 ? `rgba(${IVORY}, .9)` : `rgba(${KHAKI}, .7)`;
        ctx.beginPath(); ctx.arc(x, y, a.size, 0, 6.283); ctx.fill();
      } else if (a.state === 'reject') {
        ctx.fillStyle = `rgba(${RED}, ${Math.max(0, 1 - (a.y - 0.85) * 3)})`;
        ctx.beginPath(); ctx.arc(x, y, a.size, 0, 6.283); ctx.fill();
      } else {
        // recorded: arc from where it crossed the last gate into the ledger column
        const p = Math.min(1, a.t / 1.2), e = 1 - Math.pow(1 - p, 3);
        const sx = a.rx, sy = top + a.ry * (bot - top), tx = lx + 8 + ((S.recorded * 13 + a.size * 97) % Math.max(4, LEDGER_W - 42)), ty = bot - 10;
        const ex = sx + (tx - sx) * e, ey = sy + (ty - sy) * e * e;
        ctx.fillStyle = `rgba(${GREEN}, ${1 - p * 0.85})`; ctx.beginPath(); ctx.arc(ex, ey, a.size * (1 - p * 0.5), 0, 6.283); ctx.fill();
      }
    }
    if (halted) {
      ctx.fillStyle = 'rgba(14, 21, 18, .55)'; ctx.fillRect(PADX, top, lw, bot - top);
      ctx.fillStyle = `rgba(${IVORY}, .9)`; ctx.font = '500 11px "IBM Plex Mono", monospace';
      ctx.fillText(narrow ? 'HALTED' : 'HALTED · NO NEW PROPOSALS · OPEN WORK DRAINING', PADX + lw / 2, (top + bot) / 2);
    }
  }

  function stats() {
    const inflight = agents.filter(a => a.state === 'flow').length;
    if (el.inflight) el.inflight.textContent = inflight.toLocaleString('en-US');
    if (el.recorded) el.recorded.textContent = S.recorded.toLocaleString('en-US');
    if (el.rejected) el.rejected.textContent = S.rejected.toLocaleString('en-US');
    if (el.rate) el.rate.textContent = Math.round(S.recent.reduce((s, r) => s + r.n, 0) / 5).toLocaleString('en-US');
    if (el.state) el.state.textContent = halted ? 'Halted' : reduced.matches ? 'Static study' : 'Running';
    root.classList.toggle('is-halted', halted);
  }
  const fmtN = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n);
  if (el.n) { el.n.value = Math.round(Math.log(target / 500) / Math.log(12) * 100); el.n.addEventListener('input', () => { target = Math.round(500 * Math.pow(12, el.n.value / 100) / 100) * 100; if (el.nOut) el.nOut.textContent = fmtN(target); if (reduced.matches) staticStudy(); }); }
  if (el.strict) el.strict.addEventListener('input', () => { strict = el.strict.value / 100; if (el.strictOut) el.strictOut.textContent = `${el.strict.value}%`; if (reduced.matches) staticStudy(); });
  if (el.halt) el.halt.addEventListener('click', () => { halted = !halted; el.halt.setAttribute('aria-pressed', String(halted)); el.halt.textContent = halted ? 'Resume' : 'Halt'; stats(); draw(); });
  if (el.nOut) el.nOut.textContent = fmtN(target);
  if (el.strictOut) el.strictOut.textContent = `${Math.round(strict * 100)}%`;

  let visible = false, last = performance.now(), ui = 0, frameId = 0;
  function staticStudy() {
    seed = 3;
    agents.length = 0;
    S.recorded = S.rejected = S.flash = 0;
    S.recent.length = 0;
    for (let i = 0; i < target; i++) { spawn(); const agent = agents[agents.length - 1]; agent.x = rnd(); agent.gate = Math.floor(agent.x * 6); }
    for (let i = 0; i < 60; i++) step(.05);
    draw(); stats();
  }
  function requestFrame() {
    if (!frameId && !reduced.matches && visible && !document.hidden) frameId = requestAnimationFrame(frame);
  }
  function stopFrames() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
  function frame(now) {
    frameId = 0;
    if (reduced.matches || !visible || document.hidden) return;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (visible && !document.hidden) { step(dt); draw(); if ((ui += dt) > 0.15) { ui = 0; stats(); } }
    requestFrame();
  }
  resize(); window.addEventListener('resize', resize);
  if (reduced.matches) staticStudy();
  else stats();
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => {
    visible = e.isIntersecting; last = performance.now();
    if (visible) requestFrame(); else stopFrames();
  }, { threshold: 0.05 }).observe(root);
  else visible = true;
  reduced.addEventListener('change', () => {
    stopFrames();
    if (reduced.matches) staticStudy(); else requestFrame();
    stats();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
  requestFrame();
})();
