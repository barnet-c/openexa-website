/* OpenEXA — the desk: an illustrative model of one trading session.
   The gap (price minus NAV, in basis points) wanders as an Ornstein–Uhlenbeck process with occasional flow shocks.
   Whenever it runs past the threshold, an agent acts: create above NAV, redeem below, pulling the gap back toward zero.
   Nothing here is market data. */
(function () {
  'use strict';
  const root = document.querySelector('[data-gap]');
  if (!root) return;
  const cv = root.querySelector('[data-gap-canvas]');
  const ctx = cv.getContext('2d');
  const $ = (s) => root.querySelector(s);
  const el = {
    time: $('[data-gap-time]'), creates: $('[data-gap-creates]'), redeems: $('[data-gap-redeems]'), avg: $('[data-gap-avg]'),
    log: $('[data-gap-log]'), thr: $('[data-gap-thr]'), thrOut: $('[data-gap-thr-out]'), n: $('[data-gap-n]'), nOut: $('[data-gap-n-out]'),
    state: $('[data-gap-state]'),
  };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const IVORY = '245, 242, 236', KHAKI = '172, 166, 142', GREEN = '79, 203, 147';

  /* ---------------- model ---------------- */
  const SESSION = 390;            // minutes, 09:30 → 16:00 ET
  const SPEED = 8.5;              // session minutes per real second → one session ≈ 45 s
  const STEP = 0.25;              // integration step, minutes
  const KAPPA = 0.02, SIGMA = 2.1; // OU mean reversion / volatility (bps per √minute)
  let seed = 11;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const randn = () => { let u = 0, v = 0; while (u === 0) u = rnd(); while (v === 0) v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.283185 * v); };

  let thr = 6, agents = 2000;
  const S = { t: 0, g: 0, samples: [], actions: [], marks: [], cooldown: 0, creates: 0, redeems: 0, sumGap: 0, done: 0, nextJump: 0 };
  function reset() {
    S.t = 0; S.g = (rnd() - 0.5) * 6; S.samples = [[0, S.g]]; S.actions = []; S.marks = []; S.cooldown = 0;
    S.creates = 0; S.redeems = 0; S.sumGap = 0; S.done = 0; S.nextJump = 20 + rnd() * 60;
  }
  const cooldownFor = () => { const f = Math.log10(agents / 500) / 2; return 42 - 38 * Math.min(1, Math.max(0, f)); }; // 500 agents: every ~40 min · 50,000: every ~4 min
  const pullFor = () => 0.45 + 0.4 * Math.min(1, Math.max(0, Math.log10(agents / 500) / 2));

  function step(dt) {
    let left = dt * SPEED;
    while (left > 0 && S.t < SESSION) {
      const h = Math.min(STEP, left); left -= h;
      S.g += -KAPPA * S.g * h + SIGMA * Math.sqrt(h) * randn();
      if (S.t >= S.nextJump) { S.g += (rnd() < 0.5 ? -1 : 1) * (6 + rnd() * 9); S.nextJump = S.t + 30 + rnd() * 70; }
      S.t += h; S.cooldown -= h;
      if (Math.abs(S.g) > thr && S.cooldown <= 0) act();
      if (S.samples[S.samples.length - 1][0] < S.t - 0.5) S.samples.push([S.t, S.g]);
    }
    if (S.t >= SESSION && !S.done) { S.done = performance.now(); S.samples.push([SESSION, S.g]); }
  }
  function act() {
    const create = S.g > 0, gap = Math.abs(S.g);
    const shares = Math.round((25 + rnd() * 175) / 5) * 5000;
    S.actions.push({ t: S.t, g: S.g, create, shares, at: performance.now() });
    S.marks.push({ t: S.t, create });
    if (create) S.creates++; else S.redeems++;
    S.sumGap += gap;
    S.g -= S.g * pullFor();
    S.cooldown = cooldownFor() * (0.6 + rnd() * 0.8);
    log(S.t, create, shares, gap);
  }

  /* ---------------- ui ---------------- */
  const pad2 = (n) => String(n).padStart(2, '0');
  const clock = (m) => { const total = 9 * 60 + 30 + m; return `${pad2(Math.floor(total / 60))}:${pad2(Math.floor(total % 60))}`; };
  function log(t, create, shares, gap) {
    if (!el.log) return;
    const li = document.createElement('li');
    li.innerHTML = `<span class="t">${clock(t)}</span><b class="${create ? 'c' : 'r'}">${create ? 'CREATE' : 'REDEEM'}</b><span>${shares.toLocaleString('en-US')} sh</span><span class="g">${create ? '+' : '−'}${gap.toFixed(1)} bps</span>`;
    el.log.prepend(li);
    while (el.log.children.length > 7) el.log.lastElementChild.remove();
  }
  function stats() {
    if (el.creates) el.creates.textContent = S.creates;
    if (el.redeems) el.redeems.textContent = S.redeems;
    const n = S.creates + S.redeems;
    if (el.avg) el.avg.textContent = n ? (S.sumGap / n).toFixed(1) : '0.0';
    if (el.time) el.time.textContent = `${clock(Math.min(SESSION, S.t))} ET`;
    if (el.state) el.state.textContent = reduced.matches ? 'Static session' : paused ? 'Model paused' : S.done ? 'Session complete' : 'Model running';
    root.classList.toggle('is-closed', !!S.done);
  }
  const fmtAgents = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n);
  if (el.thr) el.thr.addEventListener('input', () => { thr = +el.thr.value; if (el.thrOut) el.thrOut.textContent = thr; if (reduced.matches) staticStudy(); else draw(); });
  if (el.n) el.n.addEventListener('input', () => { agents = Math.round(500 * Math.pow(100, el.n.value / 100) / 100) * 100; if (el.nOut) el.nOut.textContent = fmtAgents(agents); if (reduced.matches) staticStudy(); });
  if (el.thrOut) el.thrOut.textContent = thr;
  if (el.nOut) el.nOut.textContent = fmtAgents(agents);

  /* ---------------- drawing ---------------- */
  let W = 0, H = 0, dpr = 1, hover = null;
  const RANGE = 30; // ±bps shown
  const PADL = 14, PADT = 18, PADB = 30;
  let PADR = 92;
  const xOf = (t) => PADL + (t / SESSION) * (W - PADL - PADR);
  const yOf = (g) => PADT + (0.5 - g / (2 * RANGE)) * (H - PADT - PADB);
  function resize() {
    dpr = Math.min(3, window.devicePixelRatio || 1);
    const r = cv.getBoundingClientRect(); W = Math.max(1, Math.floor(r.width)); H = Math.max(1, Math.floor(r.height));
    PADR = W < 600 ? 74 : 92;
    cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }
  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.font = '500 10px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
    // grid + axes
    for (const g of [-20, -10, 10, 20]) { ctx.strokeStyle = `rgba(${IVORY}, .07)`; ctx.beginPath(); ctx.moveTo(PADL, yOf(g)); ctx.lineTo(W - PADR, yOf(g)); ctx.stroke(); ctx.fillStyle = `rgba(${IVORY}, .4)`; ctx.textAlign = 'left'; ctx.fillText(`${g > 0 ? '+' : '−'}${Math.abs(g)}`, W - PADR + 10, yOf(g)); }
    ctx.textAlign = 'center'; ctx.fillStyle = `rgba(${IVORY}, .4)`;
    const every = W < 600 ? 2 : 1;
    for (let h = 10; h <= 16; h++) { const t = (h - 9.5) * 60; if ((h - 10) % every === 0) ctx.fillText(`${pad2(h)}:00`, xOf(t), H - 12); ctx.fillRect(xOf(t) - .5, H - PADB + 2, 1, 4); }
    // threshold band
    const yT = yOf(thr), yB = yOf(-thr);
    ctx.fillStyle = `rgba(${GREEN}, .035)`; ctx.fillRect(PADL, yT, W - PADL - PADR, yB - yT);
    ctx.setLineDash([3, 5]); ctx.strokeStyle = `rgba(${GREEN}, .35)`;
    for (const y of [yT, yB]) { ctx.beginPath(); ctx.moveTo(PADL, y); ctx.lineTo(W - PADR, y); ctx.stroke(); }
    ctx.setLineDash([]);
    ctx.fillStyle = `rgba(${GREEN}, .8)`; ctx.textAlign = 'left'; ctx.fillText(`+${thr} create`, W - PADR + 10, yT); ctx.fillText(`−${thr} redeem`, W - PADR + 10, yB);
    // NAV
    ctx.strokeStyle = `rgba(${KHAKI}, .9)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(PADL, yOf(0)); ctx.lineTo(W - PADR, yOf(0)); ctx.stroke();
    ctx.fillStyle = `rgba(${KHAKI}, 1)`; ctx.fillText('NAV', W - PADR + 10, yOf(0));
    // worked gap: shade between threshold and price where the swarm is active
    const s = S.samples;
    if (s.length > 1) {
      ctx.fillStyle = `rgba(${GREEN}, .16)`;
      for (let i = 1; i < s.length; i++) {
        const [t0, g0] = s[i - 1], [t1, g1] = s[i];
        if (Math.abs(g0) > thr && Math.abs(g1) > thr && Math.sign(g0) === Math.sign(g1)) {
          const base = g0 > 0 ? yT : yB;
          ctx.beginPath(); ctx.moveTo(xOf(t0), base); ctx.lineTo(xOf(t0), yOf(g0)); ctx.lineTo(xOf(t1), yOf(g1)); ctx.lineTo(xOf(t1), base); ctx.closePath(); ctx.fill();
        }
      }
      // price path
      ctx.strokeStyle = `rgba(${IVORY}, .92)`; ctx.lineWidth = 1.4; ctx.lineJoin = 'round'; ctx.beginPath();
      s.forEach(([t, g], i) => { i ? ctx.lineTo(xOf(t), yOf(g)) : ctx.moveTo(xOf(t), yOf(g)); });
      ctx.stroke();
      // settled marks on NAV
      S.marks.forEach(m => { ctx.fillStyle = `rgba(${GREEN}, .9)`; ctx.fillRect(xOf(m.t) - 1, yOf(0) - (m.create ? 5 : 0), 2, 5); });
      // live head
      const [lt, lg] = s[s.length - 1];
      if (!S.done) { const pulse = 0.5 + 0.5 * Math.sin(performance.now() / 300); ctx.fillStyle = `rgba(${IVORY}, ${0.25 * pulse})`; ctx.beginPath(); ctx.arc(xOf(lt), yOf(lg), 7 + 3 * pulse, 0, 6.283); ctx.fill(); }
      ctx.fillStyle = `rgba(${IVORY}, 1)`; ctx.beginPath(); ctx.arc(xOf(lt), yOf(lg), 2.6, 0, 6.283); ctx.fill();
    }
    // agents in flight: fall from the price to NAV, then a ripple on the line
    const now = performance.now();
    S.actions.forEach(a => {
      const age = (now - a.at) / 1000; if (age > 1.6) return;
      const x = xOf(a.t), y0 = yOf(a.g), y1 = yOf(0);
      if (age < 0.7) {
        const p = age / 0.7, e = 1 - Math.pow(1 - p, 3);
        const y = y0 + (y1 - y0) * e;
        ctx.strokeStyle = `rgba(${GREEN}, ${0.5 * (1 - p)})`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x, y); ctx.stroke();
        ctx.fillStyle = `rgba(${GREEN}, 1)`; ctx.beginPath(); ctx.arc(x, y, 3.2, 0, 6.283); ctx.fill();
        ctx.fillStyle = `rgba(${GREEN}, .35)`; ctx.beginPath(); ctx.arc(x, y, 7, 0, 6.283); ctx.fill();
      } else {
        const p = (age - 0.7) / 0.9;
        ctx.strokeStyle = `rgba(${GREEN}, ${0.7 * (1 - p)})`; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y1, 4 + 16 * p, 0, 6.283); ctx.stroke();
      }
      if (age < 1.2) { ctx.fillStyle = `rgba(${GREEN}, ${Math.min(1, 2 - age * 1.6)})`; ctx.textAlign = 'center'; ctx.fillText(a.create ? 'CREATE' : 'REDEEM', x, (a.create ? y0 - 12 : y0 + 12)); }
    });
    // hover readout
    if (hover && s.length > 1) {
      const t = Math.min(SESSION, Math.max(0, (hover - PADL) / (W - PADL - PADR) * SESSION));
      if (t <= s[s.length - 1][0]) {
        let lo = 0, hi = s.length - 1; while (lo < hi) { const mid = (lo + hi) >> 1; if (s[mid][0] < t) lo = mid + 1; else hi = mid; }
        const [st, sg] = s[lo], x = xOf(st), y = yOf(sg);
        ctx.strokeStyle = `rgba(${IVORY}, .25)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, PADT); ctx.lineTo(x, H - PADB); ctx.stroke();
        ctx.fillStyle = `rgba(${IVORY}, 1)`; ctx.beginPath(); ctx.arc(x, y, 3, 0, 6.283); ctx.fill();
        const label = `${clock(st)} · ${sg > 0 ? '+' : '−'}${Math.abs(sg).toFixed(1)} bps ${Math.abs(sg) > thr ? (sg > 0 ? '· create' : '· redeem') : '· hold'}`;
        ctx.font = '500 10px "IBM Plex Mono", monospace'; const tw = ctx.measureText(label).width + 16;
        const bx = Math.min(W - PADR - tw, Math.max(PADL, x - tw / 2)), by = PADT - 4;
        ctx.fillStyle = 'rgba(14, 21, 18, .92)'; ctx.fillRect(bx, by, tw, 20); ctx.strokeStyle = `rgba(${IVORY}, .2)`; ctx.strokeRect(bx + .5, by + .5, tw - 1, 19);
        ctx.fillStyle = `rgba(${IVORY}, .95)`; ctx.textAlign = 'left'; ctx.fillText(label, bx + 8, by + 10);
      }
    }
  }

  /* ---------------- loop ---------------- */
  let visible = false, last = performance.now(), uiTick = 0, frameId = 0, paused = false;
  const motion = document.createElement('button');
  motion.type = 'button';
  motion.className = 'model-motion';
  motion.dataset.gapMotion = '';
  motion.setAttribute('aria-pressed', 'false');
  motion.textContent = 'Pause model';
  const head = root.querySelector('.desk-head');
  if (head) head.appendChild(motion);
  function staticStudy() {
    seed = 11;
    reset();
    if (el.log) el.log.replaceChildren();
    while (!S.done) step(1);
    draw(); stats();
  }
  function requestFrame() {
    if (!frameId && !reduced.matches && !paused && visible && !document.hidden) frameId = requestAnimationFrame(frame);
  }
  function stopFrames() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
  function frame(now) {
    frameId = 0;
    if (reduced.matches || paused || !visible || document.hidden) return;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (visible && !document.hidden) {
      if (!S.done) step(dt);
      else if (now - S.done > 4000) { reset(); if (el.log) el.log.innerHTML = ''; }
      draw();
      if ((uiTick += dt) > 0.12) { uiTick = 0; stats(); }
    }
    requestFrame();
  }
  motion.addEventListener('click', () => {
    paused = !paused;
    motion.textContent = paused ? 'Resume model' : 'Pause model';
    motion.setAttribute('aria-pressed', String(paused));
    if (paused) stopFrames(); else requestFrame();
    draw(); stats();
  });
  cv.addEventListener('pointermove', e => { const r = cv.getBoundingClientRect(); hover = e.clientX - r.left; if (reduced.matches || paused) draw(); }, { passive: true });
  cv.addEventListener('pointerleave', () => { hover = null; if (reduced.matches || paused) draw(); });
  reset();
  resize();
  motion.hidden = reduced.matches;
  if (reduced.matches) staticStudy(); else stats();
  window.addEventListener('resize', resize);
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => {
    visible = e.isIntersecting; last = performance.now();
    if (visible) requestFrame(); else stopFrames();
  }, { threshold: 0.05 }).observe(root);
  else visible = true;
  reduced.addEventListener('change', () => {
    stopFrames();
    motion.hidden = reduced.matches;
    if (reduced.matches) staticStudy(); else { reset(); if (el.log) el.log.replaceChildren(); requestFrame(); }
    stats();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
  requestFrame();
})();
