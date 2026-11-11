/* OpenEXA — the desk: an illustrative model of one trading session of Lifecycle 01 (Lifecycles §03).
   The gap (price minus NAV, in basis points) wanders as an Ornstein–Uhlenbeck process with occasional flow shocks: one path a
   session, drawn before the session runs. Wherever it runs past the threshold a strategy agent proposes: create above NAV,
   redeem below. The proposal is a ring at the crossing; a few session minutes later it fills, the ring squares up, and the
   action is sealed as a record on the ledger strip (one block per record; each link carries the first 8 hex of the SHA-256
   of the record it leaves, computed here, or no hex at all where the browser has no crypto.subtle).
   hc31r (PLAT-4): the session's actions are a pure function of the threshold and the clock (the path no longer bends to
   the fills), so the threshold is the hand: a pip on the chart's own axis at the end of the upper threshold line (flat
   under the plot under a thumb). Pulling it closes both lines on NAV and recomputes every crossing, the three counts and
   the strip in the same frame; a gesture is one record in the visitor's own ledger (OXA.run.hand). The desk obeys the
   run: the header's pause and a halt hold it, so it has no Pause of its own.
   The panel opens with the day already run to about 13:30 ET and runs on through the afternoon. Every counter is read
   from the model's state; the strip keeps the records it can show and counts the rest in a leading '+N earlier records'
   line, so its records plus N always equal creates plus redeems. "Follow the next action" runs the session quickly (but
   drawn) to the next proposal, holds the model and walks that proposal down the six gates, then lands its record in the
   strip. Off screen, in a hidden tab or paused, nothing runs. Under reduced motion the panel is a still of the whole
   session; the hand recomputes it. Nothing here is market data. */
(function () {
  'use strict';
  const root = document.querySelector('[data-gap]');
  if (!root) return;
  const cv = root.querySelector('[data-gap-canvas]');
  const ctx = cv && cv.getContext('2d');
  if (!ctx) return;
  const $ = (s) => root.querySelector(s);
  const el = {
    time: $('[data-gap-time]'), creates: $('[data-gap-creates]'), redeems: $('[data-gap-redeems]'), avg: $('[data-gap-avg]'),
    log: $('[data-gap-log]'), thr: $('[data-gap-thr]'), thrOut: $('[data-gap-thr-out]'), thrBox: $('.desk-thr'),
    state: $('[data-gap-state]'), follow: $('[data-gap-follow]'), lane: $('[data-gap-lane]'), say: $('[data-gap-say]'),
    dot: $('.desk-head .live i'),
  };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const IVORY = '245, 242, 236', KHAKI = '172, 166, 142', GREEN = '79, 203, 147', GROUND = '27, 34, 31';

  /* ---------------- model ---------------- */
  const SESSION = 390;            // minutes, 09:30 → 16:00 ET
  const SPEED = 8.5;              // session minutes per real second
  const STEP = 0.25;              // integration step, minutes
  const KAPPA = 0.03, SIGMA = 2.1; // OU mean reversion / volatility (bps per √minute)
  const WARM = 240;               // the panel opens at 13:30 ET with the day so far drawn ...
  const WARM_MAX = 275;           // ... and on an open proposal when one comes before 14:05
  const FILL = 12;                // session minutes from proposal to fill
  const COOL = 9;                 // session minutes an agent waits after a proposal, about (x 0.6 to 1.4)
  const NS = SESSION / STEP;      // steps a session
  const SEED = 22;                // the first session's path (and the still's): both sides of NAV worked before 13:30
  let seed = SEED;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const randn = () => { let u = 0, v = 0; while (u === 0) u = rnd(); while (v === 0) v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.283185 * v); };
  const wait = (i) => { let x = Math.imul(i + 1, 0x9E3779B1) >>> 0; x = Math.imul(x ^ (x >>> 15), 0x85EBCA77) >>> 0; return COOL * (0.6 + 0.8 * ((x ^ (x >>> 13)) >>> 0) / 4294967296); };

  let thr = 6, live = false;
  // G: the session's path, one value a step, drawn when the session opens; S.i: the step the clock has reached; S.at: the
  // step the scan for crossings has reached, and S.cool the minute before which no agent proposes again
  const G = new Float32Array(NS + 1);
  const S = { t: 0, g: 0, i: 0, at: 0, cool: 0, samples: [], acts: [], creates: 0, redeems: 0, sumGap: 0, done: 0 };
  function path() {
    let g = (rnd() - 0.5) * 6, jump = 20 + rnd() * 60;
    G[0] = g;
    for (let i = 1; i <= NS; i++) {
      g += -KAPPA * g * STEP + SIGMA * Math.sqrt(STEP) * randn();
      if (i * STEP >= jump) { g += (rnd() < 0.5 ? -1 : 1) * (6 + rnd() * 9); jump = i * STEP + 30 + rnd() * 70; }
      G[i] = Math.max(-28.5, Math.min(28.5, g));
    }
  }

  function clearLog() {
    dropped = 0; more = null; clearReceipt();
    if (el.log) { el.log.replaceChildren(); el.log.classList.remove('has-more'); }
  }
  function reset() {
    path();
    S.t = 0; S.i = 0; S.g = G[0]; S.samples = [[0, S.g]]; S.at = 0; S.cool = 0; S.acts = [];
    S.creates = 0; S.redeems = 0; S.sumGap = 0; S.done = 0;
    clearLog();
  }
  // the crossings up to step `to`: wherever the path is past the threshold and no agent is waiting, one proposes
  function scan(to) {
    while (S.at < to) {
      const i = ++S.at, t = i * STEP;
      if (Math.abs(G[i]) > thr && t >= S.cool) { S.cool = t + wait(i); propose(t, G[i]); if (follow.state === 'waiting' && follow.act) return true; }
    }
    return false;
  }
  // integrate the session by `mins` minutes (stops early once a followed proposal exists)
  function advance(mins) {
    let left = mins;
    while (left > 0 && S.i < NS) {
      left -= STEP;
      S.i++; S.t = S.i * STEP; S.g = G[S.i];
      for (const a of S.acts) if (!a.filled && !a.held && S.t >= a.tf) fill(a);
      const got = scan(S.i);
      if (S.samples[S.samples.length - 1][0] < S.t - 0.5) S.samples.push([S.t, S.g]);
      if (got) break;
    }
    if (S.i >= NS && !S.done) {
      S.acts.forEach(a => { if (!a.filled && !a.held) fill(a); }); // the close fills what is still open
      S.done = performance.now(); S.samples.push([SESSION, S.g]);
    }
  }
  // the hand moved: the same path and the same clock under the new threshold. Every crossing so far is found again, what
  // has had its twelve minutes is filled, the counts and the strip are written again, all before the next frame
  function recount() {
    if (follow.state !== 'idle') stopFollow(follow.quiet ? '' : 'Stopped following: the threshold moved.');
    const was = live;
    live = false;
    S.at = 0; S.cool = 0; S.acts = []; S.creates = 0; S.redeems = 0; S.sumGap = 0;
    seq = 0; chain = Promise.resolve(GENESIS);
    clearLog();
    scan(S.i);
    for (const a of S.acts) if (S.done || S.t >= a.tf) fill(a);
    live = was;
    trim();
  }
  function propose(t, g) {
    const a = { t, g, create: g > 0, tf: t + FILL, filled: false, at: 0, held: false, followed: false, rec: null };
    S.acts.push(a);
    if (follow.state === 'waiting' && !follow.act) { a.held = true; follow.act = a; }
    if (live) ping();
  }
  function fill(a) {
    a.filled = true; a.at = live ? performance.now() : 0;
    if (a.create) S.creates++; else S.redeems++;
    S.sumGap += Math.abs(a.g);
    a.rec = record(a);
    fresh = true; // the counters are rewritten in the same frame as the strip, never a tick later
  }
  // a session opens with the day so far run: to 13:30 ET, then on to the next proposal (if one comes before 14:05).
  // A follow asked for while a session closed waits through it: following is suspended during the warm advance (so the
  // new session is not cut short at its first proposal) and then picks up the open proposal, if the warm start left one.
  function warm() {
    const keep = follow.state;
    follow.state = 'idle';
    live = false;
    reset();
    advance(WARM);
    // a waiting follow wants the next action: the warm start runs on to the next proposal (up to 15:00), not just 14:05
    const upTo = keep === 'waiting' ? SESSION - 60 : WARM_MAX;
    let guard = 0;
    while (!S.acts.some(a => !a.filled) && S.t < upTo && guard++ < 2000) advance(STEP);
    live = true;
    follow.state = keep;
    if (keep === 'waiting' && !follow.act) {
      const open = S.acts.find(a => !a.filled);
      if (open) { open.held = true; follow.act = open; }
    }
    trim();
  }

  /* ---------------- the ledger strip: records, chained by real SHA-256 where the browser has it ---------------- */
  const subtle = window.crypto && window.crypto.subtle && window.isSecureContext ? window.crypto.subtle : null;
  const GENESIS = '0'.repeat(64);
  let chain = Promise.resolve(GENESIS), seq = 0;
  const pad2 = (n) => String(n).padStart(2, '0');
  const clock = (m) => { const total = 9 * 60 + 30 + m; return `${pad2(Math.floor(total / 60))}:${pad2(Math.floor(total % 60))}`; };
  const hexOf = (buf) => Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('');
  function record(a) {
    const rec = { seq: ++seq, kind: a.create ? 'CREATE' : 'REDEEM', clock: clock(a.t), gap: `${a.create ? '+' : '-'}${Math.abs(a.g).toFixed(1)}`, hash: null, li: null, h: null };
    if (el.log) {
      const li = document.createElement('li');
      li.className = 'dk-rec ' + (a.create ? 'is-c' : 'is-r') + (live ? ' is-new' : '');
      const ev = document.createElement('span'); ev.className = 'dk-ev';
      // one ink for both sides; the side is a glyph: ▲ price above NAV (create), ▼ below (redeem)
      const side = document.createElement('i'); side.className = 'dk-side'; side.setAttribute('aria-hidden', 'true');
      const b = document.createElement('b'); b.textContent = rec.kind;
      const dot = document.createElement('span'); dot.className = 'dk-dot'; dot.textContent = ' · '; // a phone shows a space here (platform.css)
      ev.append(side, b, dot, rec.clock);
      const line = document.createElement('span'); line.className = 'dk-line'; line.setAttribute('aria-hidden', 'true');
      const blk = document.createElement('i'); blk.className = 'dk-blk';
      const link = document.createElement('span'); link.className = 'dk-link';
      const h = document.createElement('span'); h.className = 'dk-h';
      link.append(h); line.append(blk, link);
      li.append(ev, line);
      el.log.append(li);
      if (live) trim();
      rec.li = li; rec.h = h;
    }
    if (subtle) {
      const body = `OXA-DESK|${rec.seq}|${rec.kind}|${rec.clock}|${rec.gap}`;
      chain = chain.then(prev => subtle.digest('SHA-256', new TextEncoder().encode(`${body}|${prev}`)).then(buf => {
        rec.hash = hexOf(buf); rec.prev = prev;
        if (rec.h) rec.h.textContent = rec.hash.slice(0, 8);
        return rec.hash;
      })).catch(() => GENESIS);
    }
    return rec;
  }
  // the strip keeps as many records as it can show whole (v2x: none is cut by the edge) and counts
  // the rest in a leading line, '+N earlier records': records kept + N = creates + redeems, always
  let dropped = 0, more = null, rcptLi = null; // rcptLi: the record the walk's last line names (receipt)
  function capacity() {
    const recs = el.log.querySelectorAll(':scope > .dk-rec');
    const W = el.log.clientWidth - (parseFloat(getComputedStyle(el.log).paddingRight) || 0);
    if (W <= 0 || !recs.length) return 40; // not laid out (hidden): keep a generous number until it is
    const w = recs[0].offsetWidth || 124, wl = recs[recs.length - 1].offsetWidth || w;
    return Math.max(2, 1 + Math.floor(Math.max(0, W - wl) / w));
  }
  function trim() {
    if (!el.log) return;
    const recs = el.log.querySelectorAll(':scope > .dk-rec');
    const n = recs.length - capacity();
    for (let i = 0; i < n; i++) { if (recs[i] === rcptLi) clearReceipt(); recs[i].remove(); dropped++; }
    if (!dropped) return;
    if (!more) { more = document.createElement('li'); more.className = 'dk-more'; }
    if (el.log.firstElementChild !== more) el.log.prepend(more);
    more.dataset.n = dropped;
    more.textContent = `+${dropped} earlier record${dropped === 1 ? '' : 's'}`;
    el.log.classList.add('has-more');
  }

  /* ---------------- ui ---------------- */
  let shownClock = '';
  function showClock() {
    const c = `${clock(Math.min(SESSION, S.t))} ET`;
    if (c !== shownClock && el.time) { el.time.textContent = c; shownClock = c; }
  }
  const fmtAgents = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n);
  let paused = false, halted = false; // the run's own state (the header's pause, a halt): the desk has no Pause of its own
  function stats() {
    if (el.creates) el.creates.textContent = S.creates;
    if (el.redeems) el.redeems.textContent = S.redeems;
    const n = S.creates + S.redeems;
    if (el.avg) el.avg.textContent = n ? (S.sumGap / n).toFixed(1) : '0.0';
    showClock();
    if (el.state) el.state.textContent = reduced.matches ? 'Static session' : follow.state !== 'idle' ? 'Following an action' : halted ? 'Halted' : paused ? 'Model paused' : S.done ? 'Session complete' : 'Model running';
    root.classList.toggle('is-closed', !!S.done && follow.state === 'idle');
    // open proposals (rings on the chart), for tests and assistive tools: written only when it changes
    const open = String(S.acts.filter(a => !a.filled).length);
    if (root.dataset.gapOpen !== open) root.dataset.gapOpen = open;
  }
  const showThr = () => { if (el.thrOut) el.thrOut.textContent = `${thr} bps`; if (el.thr) el.thr.setAttribute('aria-valuetext', `${thr} basis points`); };
  // the hand: every move recomputes the session under the new threshold and redraws it at once; a gesture is one record
  const move = (v) => { if (v === thr) return; thr = v; showThr(); if (!started) return; recount(); draw(); stats(); };
  if (el.thr) {
    thr = +el.thr.value;
    const fmt = (a, b) => `${a} → ${b} bps · ${S.creates} create${S.creates === 1 ? '' : 's'}, ${S.redeems} redeem${S.redeems === 1 ? '' : 's'}`;
    const hand = () => { const run = window.OXA && window.OXA.run; if (!run || el.thr.__hand) return; el.thr.__hand = run.hand(el.thr, { detent: 6, ev: 'Threshold', fmt, input: move, page: 4 }); };
    el.thr.addEventListener('input', () => move(+el.thr.value));
    if (window.OXA && window.OXA.run) hand(); else document.addEventListener('oxa:run', hand);
  }
  showThr();
  // the state dot pings once when an agent proposes (an event, not a loop)
  let pingT = 0;
  function ping() {
    if (!el.dot) return;
    el.dot.classList.remove('is-ping');
    clearTimeout(pingT);
    void el.dot.offsetWidth;
    el.dot.classList.add('is-ping');
    pingT = setTimeout(() => el.dot.classList.remove('is-ping'), 700);
  }

  /* ---------------- drawing ---------------- */
  let W = 0, H = 0, CW = 0, CH = 0, dpr = 1, K = 1, hover = null;
  const RANGE = 30; // ±bps shown
  const PADL = 14, PADT = 18, PADB = 30;
  let PADR = 92;
  const xOf = (t) => PADL + (t / SESSION) * (W - PADL - PADR);
  const yOf = (g) => PADT + (0.5 - g / (2 * RANGE)) * (H - PADT - PADB);
  function resize() {
    dpr = Math.min(3, window.devicePixelRatio || 1);
    // above 1920 the page grows with the window (root = 100vw / 120): the chart is the 1920 chart, scaled (a2, 4K)
    K = Math.max(1, (parseFloat(getComputedStyle(document.documentElement).fontSize) || 16) / 16);
    const r = cv.getBoundingClientRect(); CW = Math.max(1, Math.floor(r.width)); CH = Math.max(1, Math.floor(r.height));
    W = CW / K; H = CH / K;
    PADR = W < 600 ? 74 : 124;
    cv.width = Math.floor(CW * dpr); cv.height = Math.floor(CH * dpr); ctx.setTransform(dpr * K, 0, 0, dpr * K, 0, 0);
    place();
    draw();
    // a narrower strip shows fewer records: the rest join the count, once the size has settled (a passing resize, such
    // as a page capture's, never drops records)
    clearTimeout(trimT); trimT = setTimeout(trim, 300);
  }
  let trimT = 0;
  // the hand's place: where the pip is laid over the axis (a fine pointer on a wide plot; platform.css says when) the range
  // input stands on end at the plot's right edge, its 2 on the 2 bps line and its 20 on the 20 bps line, so its thumb is the
  // end of the upper threshold line; anywhere else it lies flat under the plot, in the page's flow
  function place() {
    const box = el.thrBox, inp = el.thr;
    if (!box || !inp) return;
    const on = getComputedStyle(box).position === 'absolute';
    if (!on) { inp.style.width = ''; box.style.left = box.style.top = ''; return; }
    const fs = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16, len = (yOf(2) - yOf(20)) * K + 2.75 * fs;
    inp.style.width = len.toFixed(1) + 'px';
    box.style.left = (cv.offsetLeft + (W - PADR) * K).toFixed(1) + 'px';
    box.style.top = (cv.offsetTop + (yOf(2) + yOf(20)) / 2 * K).toFixed(1) + 'px';
  }
  const ease = (p) => 1 - Math.pow(1 - p, 3);
  function mark(a, now) {
    // a proposal is a ring at its crossing; filled, it squares up over 220 ms and stays a settled square
    const x = xOf(a.t), y = yOf(a.g);
    const p = a.filled ? (a.at ? Math.min(1, (now - a.at) / 220) : 1) : 0, e = ease(p);
    const s = 11 - 3.4 * e, r = (s / 2) * (1 - e) + 1 * e;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x - s / 2, y - s / 2, s, s, r);
    else if (e < 0.5) ctx.arc(x, y, s / 2, 0, 6.283);
    else ctx.rect(x - s / 2, y - s / 2, s, s);
    ctx.fillStyle = `rgba(${GROUND}, 1)`; ctx.fill();
    if (e > 0) { ctx.fillStyle = `rgba(${GREEN}, ${0.92 * e})`; ctx.fill(); }
    ctx.lineWidth = 1.5; ctx.strokeStyle = `rgba(${GREEN}, ${1 - 0.6 * e})`; ctx.stroke();
    if (a.followed || a === follow.act) {
      ctx.lineWidth = 1; ctx.strokeStyle = `rgba(${GREEN}, .55)`;
      ctx.beginPath(); ctx.arc(x, y, 13, 0, 6.283); ctx.stroke();
      ctx.strokeStyle = `rgba(${GREEN}, .2)`; ctx.beginPath(); ctx.arc(x, y, 19, 0, 6.283); ctx.stroke();
    }
  }
  function draw() {
    const now = performance.now();
    ctx.clearRect(0, 0, W, H);
    ctx.font = '500 11px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
    // the labels on the right: the threshold's two keep a label's height clear of NAV's, and a grid value that would
    // print under either of them is left out (its hairline stays)
    const yT = yOf(thr), yB = yOf(-thr), x0 = PADL, x1 = W - PADR, LH = 13, yN = yOf(0);
    const yTl = Math.min(yT, yN - LH), yBl = Math.max(yB, yN + LH);
    // grid + axes
    for (const g of [-20, -10, 10, 20]) {
      const y = yOf(g);
      ctx.strokeStyle = `rgba(${IVORY}, .07)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(PADL, y); ctx.lineTo(W - PADR, y); ctx.stroke();
      if (Math.abs(y - yTl) >= LH && Math.abs(y - yBl) >= LH) { ctx.fillStyle = `rgba(${IVORY}, .45)`; ctx.textAlign = 'left'; ctx.fillText(`${g > 0 ? '+' : '−'}${Math.abs(g)}`, W - PADR + 10, y); }
    }
    ctx.textAlign = 'center'; ctx.fillStyle = `rgba(${IVORY}, .45)`;
    const every = W < 600 ? 2 : 1;
    for (let h = 10; h <= 16; h++) { const t = (h - 9.5) * 60; if ((h - 10) % every === 0) ctx.fillText(`${pad2(h)}:00`, xOf(t), H - 12); ctx.fillRect(xOf(t) - .5, H - PADB + 2, 1, 4); }
    // the threshold: two boundary hairlines, each with a soft glow band on the side the agents work
    for (const [y, dir] of [[yT, -1], [yB, 1]]) {
      const gr = ctx.createLinearGradient(0, y, 0, y + dir * 16);
      gr.addColorStop(0, `rgba(${GREEN}, .16)`); gr.addColorStop(1, `rgba(${GREEN}, 0)`);
      ctx.fillStyle = gr; ctx.fillRect(x0, Math.min(y, y + dir * 16), x1 - x0, 16);
      ctx.strokeStyle = `rgba(${GREEN}, .75)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y + .5 * -dir); ctx.lineTo(x1, y + .5 * -dir); ctx.stroke();
    }
    const wideLab = PADR > 100; // beside the pip: '+6 bps · create'
    if (wideLab) { ctx.strokeStyle = `rgba(${IVORY}, .22)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x1 + .5, yOf(20)); ctx.lineTo(x1 + .5, yOf(2)); for (const d of [6, 10]) { ctx.moveTo(x1 - 3, Math.round(yOf(d)) + .5); ctx.lineTo(x1 + 4, Math.round(yOf(d)) + .5); } ctx.stroke(); }
    ctx.fillStyle = `rgba(${GREEN}, .9)`; ctx.textAlign = 'left'; ctx.fillText(wideLab ? `+${thr} bps · create` : `+${thr} create`, W - PADR + (wideLab ? 18 : 10), yTl); ctx.fillText(wideLab ? `−${thr} bps · redeem` : `−${thr} redeem`, W - PADR + (wideLab ? 18 : 10), yBl);
    // NAV: a dashed hairline
    ctx.setLineDash([3, 4]); ctx.strokeStyle = `rgba(${KHAKI}, .9)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, Math.round(yN) + .5); ctx.lineTo(x1, Math.round(yN) + .5); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = `rgba(${KHAKI}, 1)`; ctx.fillText('NAV', W - PADR + 10, yN);
    const s = S.samples;
    if (s.length > 1) {
      // worked gap: where price runs past the threshold, the swarm is at work
      ctx.fillStyle = `rgba(${GREEN}, .13)`;
      for (let i = 1; i < s.length; i++) {
        const [t0, g0] = s[i - 1], [t1, g1] = s[i];
        if (Math.abs(g0) > thr && Math.abs(g1) > thr && Math.sign(g0) === Math.sign(g1)) {
          const base = g0 > 0 ? yT : yB;
          ctx.beginPath(); ctx.moveTo(xOf(t0), base); ctx.lineTo(xOf(t0), yOf(g0)); ctx.lineTo(xOf(t1), yOf(g1)); ctx.lineTo(xOf(t1), base); ctx.closePath(); ctx.fill();
        }
      }
      // price
      ctx.strokeStyle = `rgba(${IVORY}, .92)`; ctx.lineWidth = 1.4; ctx.lineJoin = 'round'; ctx.beginPath();
      s.forEach(([t, g], i) => { i ? ctx.lineTo(xOf(t), yOf(g)) : ctx.moveTo(xOf(t), yOf(g)); });
      ctx.stroke();
      // the head of the session
      const [lt, lg] = s[s.length - 1];
      if (!S.done) { ctx.fillStyle = `rgba(${IVORY}, .16)`; ctx.beginPath(); ctx.arc(xOf(lt), yOf(lg), 8, 0, 6.283); ctx.fill(); }
      ctx.fillStyle = `rgba(${IVORY}, 1)`; ctx.beginPath(); ctx.arc(xOf(lt), yOf(lg), 2.6, 0, 6.283); ctx.fill();
    }
    // proposals and settled actions, at their crossings
    S.acts.forEach(a => mark(a, now));
    // hover readout
    if (hover !== null && s.length > 1) {
      const t = Math.min(SESSION, Math.max(0, (hover - PADL) / (W - PADL - PADR) * SESSION));
      if (t <= s[s.length - 1][0]) {
        let lo = 0, hi = s.length - 1; while (lo < hi) { const mid = (lo + hi) >> 1; if (s[mid][0] < t) lo = mid + 1; else hi = mid; }
        const [st, sg] = s[lo], x = xOf(st), y = yOf(sg);
        ctx.strokeStyle = `rgba(${IVORY}, .25)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, PADT); ctx.lineTo(x, H - PADB); ctx.stroke();
        ctx.fillStyle = `rgba(${IVORY}, 1)`; ctx.beginPath(); ctx.arc(x, y, 3, 0, 6.283); ctx.fill();
        const label = `${clock(st)} · ${sg > 0 ? '+' : '−'}${Math.abs(sg).toFixed(1)} bps ${Math.abs(sg) > thr ? (sg > 0 ? '· create' : '· redeem') : '· hold'}`;
        ctx.font = '500 11px "IBM Plex Mono", monospace'; const tw = ctx.measureText(label).width + 16;
        const bx = Math.min(W - PADR - tw, Math.max(PADL, x - tw / 2)), by = PADT - 4;
        ctx.fillStyle = 'rgba(14, 21, 18, .92)'; ctx.fillRect(bx, by, tw, 20); ctx.strokeStyle = `rgba(${IVORY}, .2)`; ctx.strokeRect(bx + .5, by + .5, tw - 1, 19);
        ctx.fillStyle = `rgba(${IVORY}, .95)`; ctx.textAlign = 'left'; ctx.fillText(label, bx + 8, by + 10);
      }
    }
  }

  /* ---------------- follow the next action: one proposal, walked down the six gates ---------------- */
  const follow = { state: 'idle', act: null, k: 0, wt: 0, waitT: 0, timers: [], quiet: false };
  const STEP_MS = 1000;
  const GATES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];
  function lineFor(k, a) {
    const side = a.create ? 'above' : 'below', what = a.create ? 'a create' : 'a redeem';
    return [
      `${clock(a.t)} ET: price runs ${Math.abs(a.g).toFixed(1)} bps ${side} NAV, past the ${thr} bps threshold.`,
      'Models score the persistence of the gap and the risk of moving against it.',
      `A strategy agent proposes ${what}: price is ${side} NAV.`,
      'The Council approves it, against policy.',
      'Past the boundary, execution agents route it across the rails.',
      'Settled, matched to broker truth and hash-chained into the ledger.',
    ][k - 1];
  }
  let ring = null;
  if (el.lane) { ring = document.createElement('i'); ring.className = 'dl-ring'; ring.setAttribute('aria-hidden', 'true'); el.lane.append(ring); }
  function setLane(k) {
    if (!el.lane) return;
    if (k) { el.lane.dataset.on = k; el.lane.style.setProperty('--k', k); } else delete el.lane.dataset.on;
    el.lane.querySelectorAll('li').forEach(li => { const g = +li.dataset.g; li.classList.toggle('is-past', !!k && g < k); li.classList.toggle('is-on', g === k); });
  }
  // hc23: once it has spoken the line is never empty: each new line crossfades over the last one in the line's one cell
  // (platform.css), so nothing below moves; the old one leaves the accessibility tree at once. The first line opens with
  // its room, and the same words come back without a fade
  function put(line) {
    if (!el.say) return;
    rcptLi = null;
    const cur = el.say.querySelector(':scope > :not(.is-out)'), same = !!cur && cur.textContent === line.textContent;
    for (const c of [...el.say.children]) {
      if (same || reduced.matches || c.classList.contains('is-out')) { c.remove(); continue; }
      c.classList.add('is-out'); c.setAttribute('aria-hidden', 'true'); c.style.transition = ''; // (a first line had none)
      setTimeout(() => c.remove(), 250);
    }
    if (same || !cur) line.style.transition = 'none';
    el.say.append(line);
  }
  function say(text, gate) {
    const line = document.createElement('span');
    if (gate) { const b = document.createElement('b'); b.textContent = `${pad2(gate)} ${GATES[gate - 1]}`; line.append(b, ' '); }
    line.append(text);
    put(line);
  }
  // Esc is named only where there is a keyboard to press it (a phone stops with the button itself)
  const WAIT = 'Following the next action the model produces.' + (window.matchMedia('(any-pointer: fine)').matches ? ' Esc stops.' : '');
  function setFollowButton(on) {
    if (!el.follow) return;
    el.follow.setAttribute('aria-pressed', String(on)); // a toggle keeps its label; the pressed state says it is on
    root.classList.toggle('is-following', on);
  }
  // the walk happens on the lane and lands in the ledger strip: when either is off screen as a follow starts (a phone, a
  // short window, the desk scrolled half away), scroll the least that brings both in under the bar
  function walkIntoView() {
    const a = el.lane && (el.lane.closest('.desk-lane') || el.lane), z = (el.log && el.log.closest('.desk-ledger')) || a;
    if (!a) return;
    const top = Math.min(a.getBoundingClientRect().top, z.getBoundingClientRect().top);
    const bottom = Math.max(a.getBoundingClientRect().bottom, z.getBoundingClientRect().bottom);
    // under the bar and, where it sticks, under the desk's own head (r5: it sticks on a phone held sideways too)
    const head = $('.desk-head'), stuck = head && getComputedStyle(head).position === 'sticky' ? head.getBoundingClientRect().height : 0;
    const lo = (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 0) + stuck + 12, hi = window.innerHeight - 12;
    let dy = 0;
    if (bottom - top > hi - lo || top < lo) dy = top - lo; // taller than the room: the lane first
    else if (bottom > hi) dy = bottom - hi;
    if (Math.abs(dy) > 1) window.scrollBy({ top: dy, behavior: reduced.matches ? 'instant' : 'smooth' });
  }
  // quiet (hc13r, the desk's one act by itself): no announcement and no scroll; what a visitor starts speaks as before
  const voice = (on) => { if (el.say) el.say.setAttribute('aria-live', on ? 'polite' : 'off'); };
  function startFollow(quiet) {
    if (reduced.matches) { stillFollow(); return; }
    if (halted) { voice(!quiet); say('The run is halted: no new actions. Resume it from the header.'); return; }
    voice(!quiet); follow.quiet = !!quiet;
    follow.state = 'waiting'; follow.act = null; follow.k = 0; follow.wt = 0; follow.waitT = 0;
    setFollowButton(true); setLane(0);
    if (paused && !halted && window.OXA && window.OXA.run) window.OXA.run.pause(false);
    // a proposal already on the chart (a ring not yet settled) is the next action: walk it at once; otherwise the line
    // says what runs (hc23: the desk's own act too, unannounced, so the line under the gates is never an empty hole)
    const open = !S.done && S.acts.find(a => !a.filled && !a.held);
    if (open) { open.held = true; follow.act = open; follow.state = 'walking'; follow.wt = 0; walk(1); } else say(WAIT);
    stats();
    // measured once the head reads 'Following an action' (on some widths the longer state wraps the head onto a new row)
    if (!quiet) walkIntoView();
    requestFrame(); // otherwise the model runs fast to the next one; a closed session hands over at the next frame
  }
  function stopFollow(msg) {
    follow.timers.forEach(clearTimeout); follow.timers = [];
    if (follow.act && !follow.act.filled) { follow.act.held = false; follow.act.followed = false; }
    follow.state = 'idle'; follow.act = null; follow.k = 0; follow.quiet = false;
    setFollowButton(false); setLane(0);
    if (msg) say(msg);
    stats(); draw(); requestFrame();
  }
  function walk(k) {
    follow.k = k; setLane(k); say(lineFor(k, follow.act), k);
  }
  function land() {
    const a = follow.act;
    a.held = false; a.followed = true;
    fill(a);
    if (a.rec && a.rec.li) a.rec.li.classList.add('is-followed');
    follow.state = 'idle'; follow.act = null; follow.quiet = false;
    setFollowButton(false);
    follow.timers.push(setTimeout(() => { if (follow.state === 'idle' && !rcptLi) setLane(0); }, 1600));
    receipt(a, 1200);
    stats();
  }
  // the walk ends on the record itself (v2x lab): after the Settle line, the action as the ledger holds it, its SHA-256
  // and the record it is chained to (the same line's room: nothing below moves); both hashes are the ones the strip
  // prints, and both light on the strip
  // hc23: when that record leaves the strip (or the session restarts) the line stays, back in the line's own colour
  function clearReceipt() {
    if (!rcptLi) return;
    rcptLi = null;
    const done = el.say && el.say.querySelector(':scope > .dl-rcpt:not(.is-out)');
    if (done) done.classList.add('is-spent');
    root.querySelectorAll('.dk-rec.is-linked').forEach(li => li.classList.remove('is-linked'));
    if (follow.state === 'idle') setLane(0);
  }
  function receipt(a, ms) {
    const r = a.rec;
    if (!r || !el.say) return;
    chain.then(() => follow.timers.push(setTimeout(() => {
      if (follow.state !== 'idle' || !r.li || !r.li.isConnected || !r.li.classList.contains('is-followed')) return;
      const line = document.createElement('span'); line.className = 'dl-rcpt';
      const b = document.createElement('b'); b.textContent = 'Recorded';
      const hx = (h) => { const c = document.createElement('span'); c.className = 'dl-hx'; c.textContent = h.slice(0, 8); return c; };
      line.append(b, ` A ${r.kind === 'CREATE' ? 'create' : 'redeem'} at ${r.clock} ET`);
      if (r.hash && r.prev) line.append(', hashed ', hx(r.hash), ' and chained to the record before it, ', hx(r.prev), r.prev === GENESIS ? ', the start of the chain.' : '.');
      else line.append(', recorded in this session’s ledger.');
      put(line);
      rcptLi = r.li;
      // the lane keeps the route it walked, every gate passed, for as long as the line names a record on the strip
      setLane(0);
      if (el.lane) el.lane.querySelectorAll('li').forEach(li => li.classList.add('is-past'));
      root.querySelectorAll('.dk-rec.is-linked').forEach(li => li.classList.remove('is-linked'));
      const before = r.li.previousElementSibling;
      if (before && before.classList.contains('dk-rec')) before.classList.add('is-linked');
    }, ms)));
  }
  // under reduced motion the panel is a still: the follow walks its last action through the gates without motion
  function stillFollow() {
    const a = [...S.acts].reverse().find(x => x.filled);
    follow.timers.forEach(clearTimeout); follow.timers = [];
    if (!a) { say('This session has no action to follow.'); return; }
    follow.state = 'walking'; follow.act = a; setFollowButton(true); stats(); walkIntoView();
    for (let k = 1; k <= 6; k++) follow.timers.push(setTimeout(() => { if (follow.act === a) walk(k); }, (k - 1) * STEP_MS));
    follow.timers.push(setTimeout(() => {
      if (follow.act !== a) return;
      root.querySelectorAll('.dk-rec.is-followed').forEach(li => li.classList.remove('is-followed'));
      if (a.rec && a.rec.li) a.rec.li.classList.add('is-followed');
      follow.state = 'idle'; follow.act = null; setFollowButton(false); stats();
      receipt(a, 0);
    }, 6 * STEP_MS));
  }
  if (el.follow) {
    el.follow.hidden = false;
    el.follow.addEventListener('click', () => {
      voice(true);
      // a press during the desk's own act takes that walk over (and speaks it), rather than stopping what it came to see
      if (follow.state !== 'idle' && follow.quiet) { follow.quiet = false; if (follow.act && follow.k) say(lineFor(follow.k, follow.act), follow.k); else say(WAIT); return; }
      if (follow.state === 'idle') startFollow(); else stopFollow('Stopped following.');
    });
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && follow.state !== 'idle') { voice(true); stopFollow('Stopped following.'); } });
  // award a3 (a3-dev): the hero's "Run one simulated session" (a[data-gap-go]) lands on the instrument, not on its
  // chapter's head: the desk under the bar with Follow in view, and focus on Follow, so the act is the next key press (as
  // Trust's jump). site.js makes the jump (a cut when it is long) and lands #desk; this moves the landing in the same
  // frame (oxa:jump), or after the browser's own short jump (hashchange). The chapter menu's #desk keeps the head.
  let goAt = 0;
  document.addEventListener('click', (e) => {
    if (!e.button && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey && e.target.closest && e.target.closest('a[data-gap-go]')) goAt = performance.now();
  }, true);
  const arrive = () => {
    if (!goAt || performance.now() - goAt > 2500 || !el.follow || el.follow.hidden) return;
    goAt = 0;
    quietAct(); // the visitor came to run it: the desk does not act first
    root.scrollIntoView({ block: 'start', behavior: 'instant' });
    const over = el.follow.getBoundingClientRect().bottom - (window.innerHeight - 16);
    if (over > 0) window.scrollBy({ top: over, behavior: 'instant' });
    el.follow.focus({ preventScroll: true });
  };
  document.addEventListener('oxa:jump', arrive);
  window.addEventListener('hashchange', () => setTimeout(arrive, 0));

  /* ---------------- loop ---------------- */
  let visible = false, last = performance.now(), uiTick = 0, frameId = 0, fresh = false;
  function still() {
    seed = SEED; seq = 0; chain = Promise.resolve(GENESIS);
    live = false;
    reset();
    while (!S.done) advance(SESSION);
    trim(); draw(); stats();
  }
  function requestFrame() {
    if (!frameId && !reduced.matches && !paused && visible && !document.hidden) frameId = requestAnimationFrame(frame);
  }
  function stopFrames() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
  function frame(now) {
    frameId = 0;
    if (reduced.matches || paused || !visible || document.hidden) return;
    const raw = Math.min(0.25, Math.max(0, (now - last) / 1000)); last = now;
    const dt = Math.min(0.05, raw); // the model's step; the walk below keeps real time
    if (follow.state === 'waiting') {
      // run to the next proposal quickly but drawn: from 3x to 25x the model's speed over 300 ms, and never more than one
      // session minute a frame, so the trace and the clock run on instead of jumping; a closed session restarts at once
      follow.waitT += raw;
      if (!S.done) advance(Math.min(1, dt * SPEED * (3 + 22 * Math.min(1, follow.waitT / 0.3))));
      else warm();
      if (follow.act) { follow.state = 'walking'; follow.wt = 0; walk(1); }
      uiTick = 1; // the clock is redrawn every frame while it runs fast
    } else if (follow.state === 'walking') {
      follow.wt += raw * 1000;
      const k = Math.min(6, 1 + Math.floor(follow.wt / STEP_MS));
      if (k > follow.k) walk(k);
      if (follow.wt >= 6 * STEP_MS) land();
    } else if (!S.done) advance(dt * SPEED);
    else if (now - S.done > 4000) warm();
    draw();
    if (fresh || (uiTick += dt) > 0.12) { uiTick = 0; fresh = false; stats(); }
    else showClock(); // the clock moves a minute at a time, never two between frames
    requestFrame();
  }
  // the run's pause and halt hold the desk (OXA.run fires oxa:run once when it is ready and after every change)
  function obey() {
    const run = window.OXA && window.OXA.run;
    if (!run) return;
    const R = run.sample(), was = paused;
    halted = R.halted; paused = R.paused || R.halted;
    if (paused === was) { if (started) stats(); return; }
    if (paused) { stopFrames(); if (follow.state !== 'idle') stopFollow(); } else requestFrame();
    if (started) { draw(); stats(); }
  }
  document.addEventListener('oxa:run', obey);
  cv.addEventListener('pointermove', e => { const r = cv.getBoundingClientRect(); hover = (e.clientX - r.left) / K; if (reduced.matches || paused) draw(); }, { passive: true });
  cv.addEventListener('pointerleave', () => { hover = null; if (reduced.matches || paused) draw(); });

  // The desk sits screens below the fold: it sizes, runs its morning and draws only when it comes within one and a half
  // screens (as the ledger strip does), so a load spends nothing on it. It re-measures whenever the canvas's box changes,
  // which also covers a browser that runs this before the stylesheets apply (WebKit: a 300 x 150 canvas until then).
  let started = false;
  obey();
  function start() {
    if (started) return;
    started = true;
    resize();
    if (reduced.matches) still(); else { warm(); draw(); stats(); }
    if ('ResizeObserver' in window) new ResizeObserver(([e]) => {
      const r = e.contentRect;
      if (Math.floor(r.width) !== CW || Math.floor(r.height) !== CH) resize();
    }).observe(cv);
    else window.addEventListener('resize', resize);
    // a move to a display with another pixel ratio changes no CSS size: watch the ratio itself, re-arming each time
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    requestFrame();
  }
  if ('IntersectionObserver' in window) {
    const near = new IntersectionObserver(([e]) => { if (e.isIntersecting) { near.disconnect(); start(); } }, { rootMargin: '150% 0px' });
    near.observe(root);
    new IntersectionObserver(([e]) => {
      visible = e.isIntersecting; last = performance.now();
      if (visible) { start(); requestFrame(); } else stopFrames();
    }, { threshold: 0.05 }).observe(root);
  } else { visible = true; start(); }
  /* hc13r (PLAT-3; SYSTEM.md 12, act once): the first time the desk is well in view it follows one action by itself,
     quietly (no announcement, no scroll): the session runs on to the next proposal, the gates light from Signal to
     Settle and the record is written into the strip. Then it is still and the button is the visitor's. Never under
     reduced motion, never once the visitor has touched the desk or come to it with "Run one simulated session", never
     while it is paused or already following. */
  // A desk taller than the screen (phones) waits for its foot, the ledger strip, so the walk down the lane above it and
  // the record it writes are both on screen; a touch anywhere on the desk still cancels it, as actOnce does for its own el
  const OXA = window.OXA = window.OXA || {};
  const deskH = root.getBoundingClientRect().height; // (0 if not laid out yet: then a phone's width decides)
  const foot = (deskH ? deskH > window.innerHeight * 0.9 : window.matchMedia('(max-width: 600px)').matches) && root.querySelector('.desk-ledger');
  const actArgs = [foot || root, () => { if (follow.state === 'idle' && !paused && started) startFollow(true); },
    { paused: () => paused || follow.state !== 'idle' || !started }];
  let quietAct = () => {};
  if (OXA.actOnce) quietAct = OXA.actOnce(...actArgs) || quietAct;
  else (OXA.q = OXA.q || []).push(actArgs);
  if (foot) {
    const touch = (e) => { if (e.type !== 'pointerdown' || e.pointerType !== 'touch' || (e.target.closest && e.target.closest('a[href], button, input, label, [tabindex]'))) quietAct(); };
    ['pointerdown', 'keydown', 'click'].forEach((t) => root.addEventListener(t, touch, true));
  }

  reduced.addEventListener('change', () => {
    stopFrames();
    if (follow.state !== 'idle') stopFollow();
    if (!started) return;
    if (reduced.matches) still(); else { warm(); requestFrame(); }
    draw(); stats();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
})();

/* The hero (hc31r PLAT-3): the ring is a camera on the run. runplate.js moves the run's marks along the plate's authored paths
   (the swarm to gate 01, over the top to gate 04, the lower arc to the record) on the run's own clock: it obeys the header's
   pause and the halt, and stands still under reduced motion. Here: the gate the tagged proposal is at is lit, so the tag's
   words and the drawing say the same thing ("04 Approve · checking" lights gate 04 for the half second of its check). */
(function () {
  'use strict';
  const fig = document.querySelector('.hero-plate--rings'), OXA = window.OXA = window.OXA || {};
  const gates = fig ? [...fig.querySelectorAll('.lc-gate')].sort((a, b) => a.dataset.g - b.dataset.g) : [];
  if (gates.length !== 6) return;
  let lit = -1, on = false;
  const start = () => {
    const run = OXA.run;
    if (on || !run) return;
    on = true;
    run.subscribe((S) => {
      const g = S.ti >= 0 && S.ph[S.ti] !== 4 ? S.gate[S.ti] || 1 : 0;
      if (g === lit) return;
      lit = g;
      gates.forEach((n, k) => n.classList.toggle('is-lit', k === g - 1));
    }, fig);
  };
  if (OXA.run) start(); else document.addEventListener('oxa:run', start);
})();

/* §01 (hc30r PLAT-2): the stack and its register are one index. A trait's row and the place it lands in the stack light
   together (.is-on; platform.css): under a fine pointer, from either side (a row lights its landing; a plate or a mark
   lights its rows), and once, when the plate is well in view, in one pass of signal ink down the stack (OXA.actOnce).
   The plate is whole without any of it: nothing under reduced motion (the pass) or without JavaScript. */
(function () {
  'use strict';
  const fig = document.querySelector('#test .lc-traits'), OXA = window.OXA = window.OXA || {};
  const rows = fig ? [...document.querySelectorAll('#test .traits > li')] : [];
  if (!rows.length) return;
  // one trait: its row, its mark and its plate (data-t names the traits a part answers, 1-6)
  const parts = rows.map((li, k) => [li, ...fig.querySelectorAll(`[data-t~="${k + 1}"]`)]);
  let lit = [], timers = [];
  const light = (ks, pick) => {
    const keep = new Set(ks.flatMap((k) => parts[k]));
    lit.forEach((k) => parts[k].forEach((el) => { if (!keep.has(el)) el.classList.remove('is-on'); }));
    keep.forEach((el) => el.classList.add('is-on'));
    lit = ks; fig.classList.toggle('is-pick', !!pick && ks.length > 0);
  };
  const quiet = () => { timers.splice(0).forEach(clearTimeout); };
  if (window.matchMedia('(hover: hover)').matches) {
    rows.forEach((li, k) => {
      li.addEventListener('pointerenter', () => { quiet(); light([k], true); });
      li.addEventListener('pointerleave', () => light([]));
    });
    const svg = fig.querySelector('svg');
    svg.addEventListener('pointerover', (e) => {
      const el = e.target.closest('[data-t]');
      if (el) { quiet(); light(el.dataset.t.split(' ').map((n) => n - 1), true); }
    });
    svg.addEventListener('pointerout', (e) => { if (e.target.closest('[data-t]') && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-t]'))) light([]); });
  } else {
    // under a thumb: a tap on a row lights its landing and holds it; the same row again lets it go
    rows.forEach((li, k) => li.addEventListener('click', () => { quiet(); light(lit.length === 1 && lit[0] === k ? [] : [k], true); }));
  }
  // the pass: each landing in the stack's order, 03 twice, 04, 06, 07 and the newest record; a pointer takes over at once
  const STEP = 190, HOLD = 300;
  const run = () => {
    if (lit.length) return;
    rows.forEach((li, k) => {
      timers.push(setTimeout(() => light([...lit, k]), k * STEP), setTimeout(() => light(lit.filter((n) => n !== k)), k * STEP + HOLD));
    });
  };
  const args = [fig, run];
  if (OXA.actOnce) OXA.actOnce(...args); else (OXA.q = OXA.q || []).push(args);
})();

/* The orbit (Lifecycles §04; award a1, a1-dev): each list of twelve callouts is one Tab stop, and the arrow keys (Home,
   End) move between its items, so a keyboard reaches the call to action without twelve stops that do nothing. Without
   JavaScript every callout stays a stop. */
(function () {
  'use strict';
  [['.orbit-cs', '.orb-c'], ['.orbit-list', 'li']].forEach(([ls, is]) => {
    const list = document.querySelector(ls);
    const items = list ? [...list.querySelectorAll(is)].filter((el) => el.hasAttribute('tabindex')) : [];
    if (items.length < 2) return;
    const live = items.findIndex((el) => el.classList.contains('is-live') || !!el.querySelector('.is-live'));
    const take = (k) => items.forEach((el, i) => el.setAttribute('tabindex', i === k ? '0' : '-1'));
    take(Math.max(0, live));
    list.addEventListener('focusin', (e) => { const k = items.indexOf(e.target.closest(is)); if (k >= 0) take(k); });
    list.addEventListener('keydown', (e) => {
      const i = items.indexOf(e.target.closest(is));
      if (i < 0) return;
      const n = { ArrowDown: i + 1, ArrowRight: i + 1, ArrowUp: i - 1, ArrowLeft: i - 1, Home: 0, End: items.length - 1 }[e.key];
      if (n === undefined) return;
      e.preventDefault();
      const k = (n + items.length) % items.length;
      take(k);
      items[k].focus();
    });
  });
})();
