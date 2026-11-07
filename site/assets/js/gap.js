/* OpenEXA — the desk: an illustrative model of one trading session of Lifecycle 01 (Lifecycles §03).
   The gap (price minus NAV, in basis points) wanders as an Ornstein–Uhlenbeck process with occasional flow shocks.
   Whenever it runs past the threshold a strategy agent proposes: create above NAV, redeem below. The proposal is a ring
   at the crossing; a few session minutes later it fills, the ring squares up, the gap is pulled back, and the action is
   sealed as a record on the ledger strip (one block per record; each link carries the first 8 hex of the SHA-256 of the
   record it leaves, computed here, or no hex at all where the browser has no crypto.subtle).
   The panel opens with the day already run to about 13:30 ET (the trace covers most of the plot at first sight) and runs
   on through the afternoon. Every counter is read from the model's state; the strip keeps the records it can show and
   counts the rest in a leading '+N earlier records' line, so its records plus N always equal creates plus redeems.
   "Follow the next action" runs the session quickly (but drawn, at most a session minute a frame) to the next proposal,
   holds the model and walks that proposal down the six gates, one line per gate, then lands its record in the strip.
   Off screen, in a hidden tab or paused, nothing runs. Under reduced motion the panel is a still of the whole session;
   the sliders redraw it. Nothing here is market data. */
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
  const WARM = 240;               // the panel opens at 13:30 ET with the day so far drawn ...
  const WARM_MAX = 275;           // ... and on an open proposal when one comes before 14:05
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
    dropped = 0; more = null; clearReceipt();
    if (el.log) { el.log.replaceChildren(); el.log.classList.remove('has-more'); }
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
  let paused = false;
  function stats() {
    if (el.creates) el.creates.textContent = S.creates;
    if (el.redeems) el.redeems.textContent = S.redeems;
    const n = S.creates + S.redeems;
    if (el.avg) el.avg.textContent = n ? (S.sumGap / n).toFixed(1) : '0.0';
    showClock();
    if (el.state) el.state.textContent = reduced.matches ? 'Static session' : follow.state !== 'idle' ? 'Following an action' : paused ? 'Model paused' : S.done ? 'Session complete' : 'Model running';
    root.classList.toggle('is-closed', !!S.done && follow.state === 'idle');
    // open proposals (rings on the chart), for tests and assistive tools: written only when it changes
    const open = String(S.acts.filter(a => !a.filled).length);
    if (root.dataset.gapOpen !== open) root.dataset.gapOpen = open;
  }
  // the agent slider is log-scaled: screen readers announce what the outputs show, not the raw position
  const showThr = () => { if (el.thrOut) el.thrOut.textContent = `${thr} bps`; if (el.thr) el.thr.setAttribute('aria-valuetext', `${thr} bps`); };
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
    PADR = W < 600 ? 74 : 92;
    cv.width = Math.floor(CW * dpr); cv.height = Math.floor(CH * dpr); ctx.setTransform(dpr * K, 0, 0, dpr * K, 0, 0);
    draw();
    // a narrower strip shows fewer records: the rest join the count, once the size has settled (a passing resize, such
    // as a page capture's, never drops records)
    clearTimeout(trimT); trimT = setTimeout(trim, 300);
  }
  let trimT = 0;
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
    ctx.fillStyle = `rgba(${GREEN}, .9)`; ctx.textAlign = 'left'; ctx.fillText(`+${thr} create`, W - PADR + 10, yTl); ctx.fillText(`−${thr} redeem`, W - PADR + 10, yBl);
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
  function say(text, gate) {
    if (!el.say) return;
    rcptLi = null;
    el.say.replaceChildren();
    if (gate) { const b = document.createElement('b'); b.textContent = `${pad2(gate)} ${GATES[gate - 1]}`; el.say.append(b, ' '); }
    el.say.append(text);
  }
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
    voice(!quiet); follow.quiet = !!quiet;
    follow.state = 'waiting'; follow.act = null; follow.k = 0; follow.wt = 0; follow.waitT = 0;
    setFollowButton(true); setLane(0);
    if (quiet) { rcptLi = null; if (el.say) el.say.replaceChildren(); } else say('Following the next action the model produces. Esc stops.');
    if (paused) togglePause();
    // a proposal already on the chart (a ring not yet settled) is the next action: walk it at once
    const open = !S.done && S.acts.find(a => !a.filled && !a.held);
    if (open) { open.held = true; follow.act = open; follow.state = 'walking'; follow.wt = 0; walk(1); }
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
  function clearReceipt() {
    if (!rcptLi) return;
    rcptLi = null;
    if (el.say && el.say.querySelector('.dl-rcpt')) el.say.replaceChildren();
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
      el.say.replaceChildren(line);
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
      if (follow.state !== 'idle' && follow.quiet) { follow.quiet = false; if (follow.act && follow.k) say(lineFor(follow.k, follow.act), follow.k); else say('Following the next action the model produces. Esc stops.'); return; }
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
  const motion = document.createElement('button');
  motion.type = 'button';
  motion.className = 'model-motion';
  motion.dataset.gapMotion = '';
  motion.textContent = 'Pause motion'; // the label itself toggles: no aria-pressed (the site's one name for it)
  const head = root.querySelector('.desk-head');
  if (head) head.appendChild(motion);
  function still() {
    seed = 11; seq = 0; chain = Promise.resolve(GENESIS);
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
  function togglePause() {
    paused = !paused;
    motion.textContent = paused ? 'Resume motion' : 'Pause motion';
    if (paused) stopFrames(); else requestFrame();
    draw(); stats();
  }
  motion.addEventListener('click', togglePause);
  cv.addEventListener('pointermove', e => { const r = cv.getBoundingClientRect(); hover = (e.clientX - r.left) / K; if (reduced.matches || paused) draw(); }, { passive: true });
  cv.addEventListener('pointerleave', () => { hover = null; if (reduced.matches || paused) draw(); });

  // The desk sits screens below the fold: it sizes, runs its morning and draws only when it comes within one and a half
  // screens (as the ledger strip does), so a load spends nothing on it. It re-measures whenever the canvas's box changes,
  // which also covers a browser that runs this before the stylesheets apply (WebKit: a 300 x 150 canvas until then).
  let started = false;
  motion.hidden = reduced.matches;
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
    motion.hidden = reduced.matches;
    if (!started) return;
    if (reduced.matches) still(); else { warm(); requestFrame(); }
    draw(); stats();
  });
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopFrames(); else requestFrame(); });
})();

/* The hero rings (award a3, 4K): once their one draw is over, the plate's animations let go (each ends on the plate's
   own style), so the browser paints the plate straight onto the page again: while an animation holds its end state the
   plate sits on a layer at a fractional offset, and every hairline spreads over three device rows. */
(function () {
  'use strict';
  const fig = document.querySelector('.hero-plate--rings');
  if (!fig || typeof fig.getAnimations !== 'function') return;
  requestAnimationFrame(() => {
    const all = fig.getAnimations({ subtree: true });
    if (all.length) Promise.all(all.map((a) => a.finished)).then(() => all.forEach((a) => a.cancel()), () => {});
  });
})();

/* The hero draws its headline (hc13r PLAT-2; SYSTEM.md 12, act once): the first time the plate is well in view, a proposal
   ring leaves Signal (the live bead, gate 01), runs LC-01's ring once clockwise, lights each of gates 02-06 as it passes
   and squares up on Record (2.4 s); then the gates fade back and the plate is the still drawing. Never under reduced
   motion (actOnce); nothing is announced (the plate is a drawing, aria-hidden). */
(function () {
  'use strict';
  const fig = document.querySelector('.hero-plate--rings');
  const dot = fig && fig.querySelector('.lr-dot'), rec = fig && fig.querySelector('.lr-rec');
  if (!dot || !rec) return;
  const gates = [...fig.querySelectorAll('.lr-g')];
  const CX = 260, CY = 150, RX = 94.9, RY = 55, T0 = 165, LAP = 330, MS = 2400; // the plate's units (hero.py)
  const ease = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(2 - 2 * p, 3) / 2);
  function run() {
    let t0 = 0;
    fig.classList.add('is-run');
    const step = (now) => {
      if (!t0) t0 = now;
      const p = Math.min(1, (now - t0) / MS), e = ease(p), a = (T0 + LAP * e) * Math.PI / 180;
      dot.setAttribute('cx', (CX + RX * Math.cos(a)).toFixed(2));
      dot.setAttribute('cy', (CY + RY * Math.sin(a)).toFixed(2));
      gates.forEach((g) => { if (!g.classList.contains('is-lit') && e >= (g.dataset.g - 1) / 6) g.classList.add('is-lit'); });
      if (p < 1) { requestAnimationFrame(step); return; }
      rec.classList.add('is-in');
      setTimeout(() => {
        gates.forEach((g) => g.classList.remove('is-lit'));
        fig.classList.remove('is-run'); rec.classList.remove('is-in');
      }, 900);
    };
    requestAnimationFrame(step);
  }
  const OXA = window.OXA = window.OXA || {};
  const args = [fig, run, { visible: 0.6 }];
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
