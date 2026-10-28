/* OpenEXA — the desk: an illustrative model of one trading session of Lifecycle 01 (Lifecycles §03).
   The gap (price minus NAV, in basis points) wanders as an Ornstein–Uhlenbeck process with occasional flow shocks.
   Whenever it runs past the threshold a strategy agent proposes: create above NAV, redeem below. The proposal is a ring
   at the crossing; a few session minutes later it fills, the ring squares up, the gap is pulled back, and the action is
   sealed as a record on the ledger strip (one block per record; each link carries the first 8 hex of the SHA-256 of the
   record it leaves, computed here, or no hex at all where the browser has no crypto.subtle).
   The panel opens with the morning already run (to about 11:15 ET) and then runs on. Every counter is read from the
   model's state. "Follow the next action" walks the next proposal down the six gates, one line per gate, and lands its
   record in the strip. Off screen, in a hidden tab or paused, nothing runs. Under reduced motion the panel is a still of
   the whole session; the sliders redraw it. Nothing here is market data. */
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
    log: $('[data-gap-log]'), thr: $('[data-gap-thr]'), thrOut: $('[data-gap-thr-out]'), n: $('[data-gap-n]'), nOut: $('[data-gap-n-out]'),
    state: $('[data-gap-state]'), follow: $('[data-gap-follow]'), lane: $('[data-gap-lane]'), say: $('[data-gap-say]'),
    dot: $('.desk-head .live i'),
  };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const IVORY = '245, 242, 236', KHAKI = '172, 166, 142', GREEN = '79, 203, 147', GROUND = '27, 34, 31';

  /* ---------------- model ---------------- */
  const SESSION = 390;            // minutes, 09:30 → 16:00 ET
  const SPEED = 8.5;              // session minutes per real second
  const STEP = 0.25;              // integration step, minutes
  const KAPPA = 0.02, SIGMA = 2.1; // OU mean reversion / volatility (bps per √minute)
  const WARM = 105;               // the panel opens at 11:15 ET with the morning drawn ...
  const WARM_MAX = 170;           // ... and on an open proposal when one comes before 12:20
  const FILL = 12;                // session minutes from proposal to fill
  let seed = 11;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const randn = () => { let u = 0, v = 0; while (u === 0) u = rnd(); while (v === 0) v = rnd(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.283185 * v); };

  let thr = 6, agents = 2000, live = false;
  const S = { t: 0, g: 0, samples: [], acts: [], cooldown: 0, creates: 0, redeems: 0, sumGap: 0, done: 0, nextJump: 0 };
  const cooldownFor = () => { const f = Math.log10(agents / 500) / 2; return 42 - 38 * Math.min(1, Math.max(0, f)); }; // 500 agents: every ~40 min · 50,000: every ~4 min
  const pullFor = () => 0.45 + 0.4 * Math.min(1, Math.max(0, Math.log10(agents / 500) / 2));

  function reset() {
    S.t = 0; S.g = (rnd() - 0.5) * 6; S.samples = [[0, S.g]]; S.acts = []; S.cooldown = 0;
    S.creates = 0; S.redeems = 0; S.sumGap = 0; S.done = 0; S.nextJump = 20 + rnd() * 60;
    if (el.log) el.log.replaceChildren();
  }
  // integrate the session by `mins` minutes (stops early once a followed proposal exists)
  function advance(mins) {
    let left = mins;
    while (left > 0 && S.t < SESSION) {
      const h = Math.min(STEP, left); left -= h;
      S.g += -KAPPA * S.g * h + SIGMA * Math.sqrt(h) * randn();
      if (S.t >= S.nextJump) { S.g += (rnd() < 0.5 ? -1 : 1) * (6 + rnd() * 9); S.nextJump = S.t + 30 + rnd() * 70; }
      S.t += h; S.cooldown -= h;
      for (const a of S.acts) if (!a.filled && !a.held && S.t >= a.tf) fill(a);
      if (Math.abs(S.g) > thr && S.cooldown <= 0) propose();
      if (S.samples[S.samples.length - 1][0] < S.t - 0.5) S.samples.push([S.t, S.g]);
      if (follow.state === 'waiting' && follow.act) break;
    }
    if (S.t >= SESSION && !S.done) {
      S.acts.forEach(a => { if (!a.filled && !a.held) fill(a); }); // the close fills what is still open
      S.done = performance.now(); S.samples.push([SESSION, S.g]);
    }
  }
  function propose() {
    const a = { t: S.t, g: S.g, create: S.g > 0, tf: S.t + FILL, filled: false, at: 0, held: false, followed: false, rec: null };
    S.acts.push(a);
    S.cooldown = cooldownFor() * (0.6 + rnd() * 0.8);
    if (follow.state === 'waiting' && !follow.act) { a.held = true; follow.act = a; }
    if (live) ping();
  }
  function fill(a) {
    a.filled = true; a.at = live ? performance.now() : 0;
    S.g -= S.g * pullFor();
    if (a.create) S.creates++; else S.redeems++;
    S.sumGap += Math.abs(a.g);
    a.rec = record(a);
  }
  // a session opens with its morning run: to 11:15 ET, then on to the next proposal (if one comes before 12:20)
  function warm() {
    live = false;
    reset();
    advance(WARM);
    let guard = 0;
    while (!S.acts.some(a => !a.filled) && S.t < WARM_MAX && guard++ < 1000) advance(STEP);
    live = true;
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
      const b = document.createElement('b'); b.textContent = rec.kind;
      ev.append(b, ` · ${rec.clock}`);
      const line = document.createElement('span'); line.className = 'dk-line'; line.setAttribute('aria-hidden', 'true');
      const blk = document.createElement('i'); blk.className = 'dk-blk';
      const link = document.createElement('span'); link.className = 'dk-link';
      const h = document.createElement('span'); h.className = 'dk-h';
      link.append(h); line.append(blk, link);
      li.append(ev, line);
      el.log.append(li);
      while (el.log.children.length > 40) el.log.firstElementChild.remove();
      rec.li = li; rec.h = h;
    }
    if (subtle) {
      const body = `OXA-DESK|${rec.seq}|${rec.kind}|${rec.clock}|${rec.gap}`;
      chain = chain.then(prev => subtle.digest('SHA-256', new TextEncoder().encode(`${body}|${prev}`)).then(buf => {
        rec.hash = hexOf(buf);
        if (rec.h) rec.h.textContent = rec.hash.slice(0, 8);
        return rec.hash;
      })).catch(() => GENESIS);
    }
    return rec;
  }

  /* ---------------- ui ---------------- */
  const fmtAgents = (n) => n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, '')}k` : String(n);
  let paused = false;
  function stats() {
    if (el.creates) el.creates.textContent = S.creates;
    if (el.redeems) el.redeems.textContent = S.redeems;
    const n = S.creates + S.redeems;
    if (el.avg) el.avg.textContent = n ? (S.sumGap / n).toFixed(1) : '0.0';
    if (el.time) el.time.textContent = `${clock(Math.min(SESSION, S.t))} ET`;
    if (el.state) el.state.textContent = reduced.matches ? 'Static session' : follow.state !== 'idle' ? 'Following an action' : paused ? 'Model paused' : S.done ? 'Session complete' : 'Model running';
    root.classList.toggle('is-closed', !!S.done && follow.state === 'idle');
    // open proposals (rings on the chart), for tests and assistive tools: written only when it changes
    const open = String(S.acts.filter(a => !a.filled).length);
    if (root.dataset.gapOpen !== open) root.dataset.gapOpen = open;
  }
  // the agent slider is log-scaled: screen readers announce what the outputs show, not the raw position
  const showThr = () => { if (el.thrOut) el.thrOut.textContent = thr; if (el.thr) el.thr.setAttribute('aria-valuetext', `${thr} bps`); };
  const showN = () => { if (el.nOut) el.nOut.textContent = fmtAgents(agents); if (el.n) el.n.setAttribute('aria-valuetext', `${fmtAgents(agents)} agents`); };
  if (el.thr) { thr = +el.thr.value; el.thr.addEventListener('input', () => { thr = +el.thr.value; showThr(); if (reduced.matches) still(); else draw(); }); }
  if (el.n) {
    const read = () => Math.round(500 * Math.pow(100, el.n.value / 100) / 100) * 100;
    agents = read();
    el.n.addEventListener('input', () => { agents = read(); showN(); if (reduced.matches) still(); });
  }
  showThr(); showN();
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
    ctx.font = '500 10px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
    // grid + axes
    for (const g of [-20, -10, 10, 20]) { ctx.strokeStyle = `rgba(${IVORY}, .07)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(PADL, yOf(g)); ctx.lineTo(W - PADR, yOf(g)); ctx.stroke(); ctx.fillStyle = `rgba(${IVORY}, .45)`; ctx.textAlign = 'left'; ctx.fillText(`${g > 0 ? '+' : '−'}${Math.abs(g)}`, W - PADR + 10, yOf(g)); }
    ctx.textAlign = 'center'; ctx.fillStyle = `rgba(${IVORY}, .45)`;
    const every = W < 600 ? 2 : 1;
    for (let h = 10; h <= 16; h++) { const t = (h - 9.5) * 60; if ((h - 10) % every === 0) ctx.fillText(`${pad2(h)}:00`, xOf(t), H - 12); ctx.fillRect(xOf(t) - .5, H - PADB + 2, 1, 4); }
    // the threshold: two boundary hairlines, each with a soft glow band on the side the agents work
    const yT = yOf(thr), yB = yOf(-thr), x0 = PADL, x1 = W - PADR;
    for (const [y, dir] of [[yT, -1], [yB, 1]]) {
      const gr = ctx.createLinearGradient(0, y, 0, y + dir * 16);
      gr.addColorStop(0, `rgba(${GREEN}, .16)`); gr.addColorStop(1, `rgba(${GREEN}, 0)`);
      ctx.fillStyle = gr; ctx.fillRect(x0, Math.min(y, y + dir * 16), x1 - x0, 16);
      ctx.strokeStyle = `rgba(${GREEN}, .75)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, y + .5 * -dir); ctx.lineTo(x1, y + .5 * -dir); ctx.stroke();
    }
    ctx.fillStyle = `rgba(${GREEN}, .9)`; ctx.textAlign = 'left'; ctx.fillText(`+${thr} create`, W - PADR + 10, yT); ctx.fillText(`−${thr} redeem`, W - PADR + 10, yB);
    // NAV: a dashed hairline
    ctx.setLineDash([3, 4]); ctx.strokeStyle = `rgba(${KHAKI}, .9)`; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x0, Math.round(yOf(0)) + .5); ctx.lineTo(x1, Math.round(yOf(0)) + .5); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = `rgba(${KHAKI}, 1)`; ctx.fillText('NAV', W - PADR + 10, yOf(0));
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
        ctx.font = '500 10px "IBM Plex Mono", monospace'; const tw = ctx.measureText(label).width + 16;
        const bx = Math.min(W - PADR - tw, Math.max(PADL, x - tw / 2)), by = PADT - 4;
        ctx.fillStyle = 'rgba(14, 21, 18, .92)'; ctx.fillRect(bx, by, tw, 20); ctx.strokeStyle = `rgba(${IVORY}, .2)`; ctx.strokeRect(bx + .5, by + .5, tw - 1, 19);
        ctx.fillStyle = `rgba(${IVORY}, .95)`; ctx.textAlign = 'left'; ctx.fillText(label, bx + 8, by + 10);
      }
    }
  }

  /* ---------------- follow the next action: one proposal, walked down the six gates ---------------- */
  const follow = { state: 'idle', act: null, k: 0, wt: 0, waitT: 0, timers: [] };
  const STEP_MS = 1000;
  const GATES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];
  function lineFor(k, a) {
    const side = a.create ? 'above' : 'below', what = a.create ? 'a create' : 'a redeem';
    return [
      `${clock(a.t)} ET: price runs ${Math.abs(a.g).toFixed(1)} bps ${side} NAV, past the ${thr} bps threshold.`,
      'Models score the persistence of the gap and the risk of moving against it.',
      `A strategy agent proposes ${what}: price is ${side} NAV.`,
      'The execution council approves it, against policy.',
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
  function say(text, gate) {
    if (!el.say) return;
    el.say.replaceChildren();
    if (gate) { const b = document.createElement('b'); b.textContent = `${pad2(gate)} ${GATES[gate - 1]}`; el.say.append(b, ' '); }
    el.say.append(text);
  }
  function setFollowButton(on) {
    if (!el.follow) return;
    el.follow.setAttribute('aria-pressed', String(on));
    el.follow.textContent = on ? 'Stop following' : 'Follow the next action';
    root.classList.toggle('is-following', on);
  }
  function startFollow() {
    if (reduced.matches) { stillFollow(); return; }
    follow.state = 'waiting'; follow.act = null; follow.k = 0; follow.wt = 0; follow.waitT = 0;
    setFollowButton(true); setLane(0);
    say('Following the next action the model produces. Esc stops.');
    if (paused) togglePause();
    if (S.done) S.done = performance.now() - 3400; // a closed session hands over quickly
    stats(); requestFrame();
  }
  function stopFollow(msg) {
    follow.timers.forEach(clearTimeout); follow.timers = [];
    if (follow.act && !follow.act.filled) { follow.act.held = false; follow.act.followed = false; }
    follow.state = 'idle'; follow.act = null; follow.k = 0;
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
    follow.state = 'idle'; follow.act = null;
    setFollowButton(false);
    follow.timers.push(setTimeout(() => { if (follow.state === 'idle') setLane(0); }, 1600));
    stats();
  }
  // under reduced motion the panel is a still: the follow walks its last action through the gates without motion
  function stillFollow() {
    const a = [...S.acts].reverse().find(x => x.filled);
    follow.timers.forEach(clearTimeout); follow.timers = [];
    if (!a) { say('This session has no action to follow.'); return; }
    follow.state = 'walking'; follow.act = a; setFollowButton(true); stats();
    for (let k = 1; k <= 6; k++) follow.timers.push(setTimeout(() => { if (follow.act === a) walk(k); }, (k - 1) * STEP_MS));
    follow.timers.push(setTimeout(() => {
      if (follow.act !== a) return;
      root.querySelectorAll('.dk-rec.is-followed').forEach(li => li.classList.remove('is-followed'));
      if (a.rec && a.rec.li) a.rec.li.classList.add('is-followed');
      follow.state = 'idle'; follow.act = null; setFollowButton(false); stats();
    }, 6 * STEP_MS));
  }
  if (el.follow) {
    el.follow.hidden = false;
    el.follow.addEventListener('click', () => { if (follow.state === 'idle') startFollow(); else stopFollow('Stopped following.'); });
  }
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && follow.state !== 'idle') stopFollow('Stopped following.'); });

  /* ---------------- loop ---------------- */
  let visible = false, last = performance.now(), uiTick = 0, frameId = 0;
  const motion = document.createElement('button');
  motion.type = 'button';
  motion.className = 'model-motion';
  motion.dataset.gapMotion = '';
  motion.textContent = 'Pause model'; // the label itself toggles: no aria-pressed
  const head = root.querySelector('.desk-head');
  if (head) head.appendChild(motion);
  function still() {
    seed = 11; seq = 0; chain = Promise.resolve(GENESIS);
    live = false;
    reset();
    while (!S.done) advance(SESSION);
    draw(); stats();
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
      follow.waitT += dt;
      if (!S.done) advance(dt * SPEED * (follow.waitT > 1.2 ? 24 : 6));
      else if (now - S.done > 4000) warm();
      if (follow.act) { follow.state = 'walking'; follow.wt = 0; walk(1); }
    } else if (follow.state === 'walking') {
      follow.wt += raw * 1000;
      const k = Math.min(6, 1 + Math.floor(follow.wt / STEP_MS));
      if (k > follow.k) walk(k);
      if (follow.wt >= 6 * STEP_MS) land();
    } else if (!S.done) advance(dt * SPEED);
    else if (now - S.done > 4000) warm();
    draw();
    if ((uiTick += dt) > 0.12) { uiTick = 0; stats(); }
    requestFrame();
  }
  function togglePause() {
    paused = !paused;
    motion.textContent = paused ? 'Resume model' : 'Pause model';
    if (paused) stopFrames(); else requestFrame();
    draw(); stats();
  }
  motion.addEventListener('click', togglePause);
  cv.addEventListener('pointermove', e => { const r = cv.getBoundingClientRect(); hover = e.clientX - r.left; if (reduced.matches || paused) draw(); }, { passive: true });
  cv.addEventListener('pointerleave', () => { hover = null; if (reduced.matches || paused) draw(); });

  resize();
  motion.hidden = reduced.matches;
  if (reduced.matches) still(); else { warm(); draw(); stats(); }
  window.addEventListener('resize', resize);
  // a move to a display with another pixel ratio changes no CSS size: watch the ratio itself, re-arming each time
  (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => {
    visible = e.isIntersecting; last = performance.now();
    if (visible) requestFrame(); else stopFrames();
  }, { threshold: 0.05 }).observe(root);
  else visible = true;
  reduced.addEventListener('change', () => {
    stopFrames();
    if (follow.state !== 'idle') stopFollow();
    motion.hidden = reduced.matches;
    if (reduced.matches) still(); else { warm(); requestFrame(); }
    draw(); stats();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
  requestFrame();
})();
