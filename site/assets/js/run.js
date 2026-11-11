/* OpenEXA: the run (system). One clock a visit, one closed-form model, the visitor's inputs, their sealed records and the header's transport: window.OXA.run. */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {};
  if (OXA.run) return;
  const doc = document, root = doc.documentElement;
  const { floor, max, min, sin, cos, sqrt, round, abs, imul } = Math, TAU = Math.PI * 2;
  const KEY = 'oxa:run', V = 1, PRE = 40, DT = 0.075, TB = 0.5, TC = 2.7, TD = 0.8, TR = 1.5, BT = 1.6, CARRY = 9, DRAIN = 8.6, STRICT = 0.12, TICK = 0.25, N = 256, AWAY = 1800;
  const GX = [-0.92, -0.58, -0.24, 0.12, 0.5, 0.84], LX = 1.05, RING = 0.19, RAIL = [-0.15, -0.075, 0, 0.075, 0.15];
  const GATE = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];
  const ROOT = '5f90194828e85cf431a18e2b15fc575ff6fb9d6fc91b9e103c7fcce42d1d2286';
  const PAGES = { home: 'Home', platform: 'Platform', lifecycles: 'Lifecycles', proof: 'Proof', trust: 'Trust', company: 'Company', 404: 'the 404' };
  const page = (doc.body && doc.body.dataset.page) || '', PAGE = PAGES[page] || page || 'this page', CAM = /^(home|platform|lifecycles|trust|company)$/.test(page);
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const pad = (n, w) => String(n).padStart(w, '0');

  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  const utf8 = new TextEncoder(), W = new Uint32Array(64);
  function sha256(text) {
    const m = utf8.encode(text), len = m.length, words = ((len + 8) >> 6) + 1 << 4, x = new Uint32Array(words);
    for (let i = 0; i < len; i++) x[i >> 2] |= m[i] << (24 - (i & 3) * 8);
    x[len >> 2] |= 0x80 << (24 - (len & 3) * 8);
    x[words - 2] = floor(len / 0x20000000); x[words - 1] = len << 3;
    const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    for (let o = 0; o < words; o += 16) {
      for (let t = 0; t < 64; t++) {
        if (t < 16) W[t] = x[o + t];
        else { const a = W[t - 15], b = W[t - 2]; W[t] = W[t - 16] + ((a >>> 7 | a << 25) ^ (a >>> 18 | a << 14) ^ a >>> 3) + W[t - 7] + ((b >>> 17 | b << 15) ^ (b >>> 19 | b << 13) ^ b >>> 10); }
      }
      let a = H[0], b = H[1], c = H[2], d = H[3], e = H[4], f = H[5], g = H[6], h = H[7];
      for (let t = 0; t < 64; t++) {
        const t1 = (h + ((e >>> 6 | e << 26) ^ (e >>> 11 | e << 21) ^ (e >>> 25 | e << 7)) + ((e & f) ^ (~e & g)) + K[t] + W[t]) | 0;
        const t2 = (((a >>> 2 | a << 30) ^ (a >>> 13 | a << 19) ^ (a >>> 22 | a << 10)) + ((a & b) ^ (a & c) ^ (b & c))) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
    }
    return Array.from(H, v => v.toString(16).padStart(8, '0')).join('');
  }

  const fresh = () => ({ v: V, t0: Date.now(), seed: (Math.random() * 4294967296) >>> 0, paused: null, follow: null, ev: [], rec: [], head: null });
  const sound = s => !!s && s.v === V && isFinite(s.t0) && isFinite(s.seed) && Array.isArray(s.ev) && Array.isArray(s.rec);
  const read = () => { try { const s = JSON.parse(sessionStorage.getItem(KEY)); return sound(s) ? s : null; } catch (e) { return null; } };
  const save = () => { if (doc.prerendering) return; try { sessionStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { } };
  let st = null, lastT = 0, H = [], SV = [], hb0 = 0, hl0 = 0, s0 = STRICT, K0 = 0, CH = null, Q = '', QI = -1;
  const P = new Map(), HS = new Map();

  function derive() {
    H = []; SV = []; hb0 = hl0 = 0; s0 = STRICT;
    for (const [t, k, v] of st.ev) {
      if (k === 'b') { s0 = v[0]; hb0 = v[1]; hl0 = v[2]; }
      else if (k === 's') SV.push(t, v);
      else if (k === 'h') { if (!H.length || H[H.length - 1][1] < Infinity) H.push([t, Infinity]); }
      else if (k === 'r') { const h = H[H.length - 1]; if (h && h[1] === Infinity) h[1] = t; }
    }
    P.clear();
  }
  function load() {
    const s = read();
    st = s || st || fresh();
    if (!s) save();
    derive(); CH = null; HS.clear();
    const h = st.head;
    Q = (h && h.h && h.q) || ''; QI = h && h.h ? h.i : -1; lastT = (h && h.t) || 0;
    K0 = bornCount(PRE);
  }

  const hash = (k, s) => { let x = (imul(k + 1, 0x9E3779B1) ^ imul(s + 7, 0x85EBCA77) ^ st.seed) >>> 0; x = imul(x ^ (x >>> 16), 0x7FEB352D); x = imul(x ^ (x >>> 15), 0x846CA68B); return (x ^ (x >>> 16)) >>> 0; };
  const u01 = (k, s) => hash(k, s) / 4294967296;
  const beta = t => { let b = t - hb0; for (const [h, r] of H) if (t > h) b -= min(t, r) - h; return b; };
  const bornAt = b => { let t = b + hb0; for (const [h, r] of H) if (t >= h) t += r - h; return t; };
  const lam = t => { let l = t - hl0; for (const [h, r] of H) { const d = h + DRAIN; if (t > d && r > d) l -= min(t, r) - d; } return l; };
  const lamInv = l => { let t = l + hl0; for (const [h, r] of H) { const d = h + DRAIN; if (r > d && t > d) t += r - d; } return t; };
  const strictAt = t => { let s = s0; for (let i = 0; i < SV.length && SV[i] <= t; i += 2) s = SV[i + 1]; return s; };
  const strictNow = () => (SV.length ? SV[SV.length - 1] : s0);
  const haltedAt = t => { const h = H[H.length - 1]; return !!h && t >= h[0] && t < h[1]; };
  const bornCount = b => { const k = floor(b / DT); return k < 0 ? 0 : k + (b - k * DT >= DT * 0.8 * u01(k, 1) ? 1 : 0); };
  const clockOf = t => { const e = max(0, floor(t - PRE)); return pad(floor(e / 60), 2) + ':' + pad(e % 60, 2); };
  const pid = k => 'P-' + pad(46000 + (k % 53000), 5);

  function now() {
    if (st.paused != null) return st.paused;
    let t = PRE + (Date.now() - st.t0) / 1000;
    if (t < lastT || (lastT && t - lastT > AWAY)) { st.t0 += (t - lastT) * 1000; t = lastT; save(); }
    return (lastT = t);
  }
  function prop(k) {
    let p = P.get(k);
    if (p) return p;
    const tb = bornAt(k * DT + DT * 0.8 * u01(k, 1)), ta = 3.1 + 1.3 * u01(k, 2), risk = u01(k, 3), tv = tb + ta + TB, rej = risk > 1 - strictAt(tv);
    p = { k, tb, ta, tv, risk, rej, te: rej ? tv + TR : tv + TC + TD, lane: hash(k, 4) % 5, agent: hash(k, 5) % 96, xs: -1.3 + 0.42 * u01(k, 6), a: TAU * u01(k, 7), rho: sqrt(u01(k, 8)) };
    if (P.size > 4000) P.clear();
    P.set(k, p);
    return p;
  }
  const tube = x => (x < GX[0] ? 0.3 + (GX[0] - x) * 0.3 : x <= GX[2] ? 0.3 - 0.03 * ((x - GX[0]) / (GX[2] - GX[0])) : 0.27 + (RING * 0.84 - 0.27) * smooth(GX[2], GX[3], x));
  function place(p, t, S, i) {
    const e = t - p.tb, rr = RING * 0.96 * p.risk;
    let ph, u, x, y, z, g;
    if (e < p.ta) {
      u = e / p.ta; x = p.xs + (GX[3] - p.xs) * (u * (0.55 + 0.45 * u));
      const a = p.a + 0.45 * sin(e * 0.8 + p.k), m = smooth(GX[2], GX[3], x), r = tube(x) * p.rho * (1 - m) + rr * m;
      ph = 0; y = r * sin(a); z = r * cos(a); g = x < GX[0] ? 0 : x < GX[1] ? 1 : x < GX[2] ? 2 : 3;
    } else {
      const a1 = p.a + 0.45 * sin(p.ta * 0.8 + p.k), y1 = rr * sin(a1), z1 = rr * cos(a1), e2 = e - p.ta, e3 = e2 - TB;
      if (e2 < TB) { ph = 1; u = e2 / TB; x = GX[3]; y = y1; z = z1; g = 4; }
      else if (p.rej) { ph = 4; u = e3 / TR; x = GX[3] + 0.09 * u; y = y1 - 0.5 * u * u - 0.03 * u; z = z1 + 0.08 * u; g = 4; }
      else if (e3 < TC) { ph = 2; u = e3 / TC; const s = smooth(0, 0.14, u); x = GX[3] + (GX[5] - GX[3]) * u; y = y1 + (RAIL[p.lane] - y1) * s; z = z1 * (1 - s); g = x < GX[4] ? 5 : 6; }
      else { ph = 3; u = (e3 - TC) / TD; x = GX[5] + (LX - GX[5]) * u; y = RAIL[p.lane] * (1 - smooth(0, 1, u)); z = 0; g = 6; }
    }
    S.k[i] = p.k; S.ph[i] = ph; S.u[i] = u; S.x[i] = x; S.y[i] = y; S.z[i] = z; S.gate[i] = g; S.lane[i] = p.lane; S.agent[i] = p.agent; S.risk[i] = p.risk;
  }

  let TS = 0, TJ = 0;
  function tally(a, b) {
    TS = TJ = 0;
    const lo = max(K0, floor(beta(a - 8.5) / DT) - 1), hi = floor(beta(b - 3.5) / DT) + 1;
    for (let k = lo; k <= hi; k++) { const p = prop(k); if (p.rej) { if (p.tv >= a && p.tv < b) TJ++; } else if (p.te >= a && p.te < b) TS++; }
  }
  const gen = () => ({ i: -1, h: sha256('genesis|' + st.seed), s: 0, r: 0 });
  function step(c, keep) {
    const i = c.i + 1, a = lamInv(i * BT), b = lamInv((i + 1) * BT);
    if (b > PRE) { tally(a, b); c.s += TS; c.r += TJ; }
    c.i = i; c.h = sha256(c.h + '|' + i + '|' + c.s + '|' + c.r);
    if (keep) { HS.set(i, c.h); if (HS.size > 128) for (const k of HS.keys()) { if (HS.size <= 64) break; HS.delete(k); } }
  }
  function seal(t, live) {
    const n = floor(lam(t) / BT) - 1;
    if (!CH) { const h = st.head; CH = h && h.h ? { i: h.i, h: h.h, s: h.s, r: h.r } : gen(); }
    if (n >= CH.i && (live || t <= lastT)) { while (CH.i < n) step(CH, true); return CH; }
    const c = n >= CH.i ? { i: CH.i, h: CH.h, s: CH.s, r: CH.r } : gen();
    while (c.i < n) step(c, false);
    return c;
  }
  function block(i) {
    const h = HS.get(i) || (CH && CH.i === i ? CH.h : '');
    if (h) return h;
    const o = (i - (QI - Q.length / 8 + 1)) * 8;
    return i <= QI && o >= 0 ? Q.slice(o, o + 8) : '';
  }
  function checkpoint() {
    if (!CH) { st.head = Object.assign(st.head || {}, { t: lastT }); save(); return; }
    let q = '';
    for (let i = max(0, CH.i - 39); i <= CH.i; i++) { const h = block(i); if (!h) { q = ''; continue; } q += h.slice(0, 8); }
    st.head = { i: CH.i, h: CH.h, s: CH.s, r: CH.r, q, t: lastT };
    save();
  }

  const mk = () => ({ t: 0, clock: '', strict: STRICT, halted: false, paused: false, n: 0, k: new Int32Array(N), ph: new Uint8Array(N), u: new Float32Array(N), x: new Float32Array(N), y: new Float32Array(N), z: new Float32Array(N),
    gate: new Uint8Array(N), lane: new Uint8Array(N), agent: new Uint8Array(N), risk: new Float32Array(N), tag: -1, ti: -1, tagId: '', tagLine: '', tagTone: '', bl: 0, bi: -1, counts: { n: 0, s: 0, r: 0, f: 0 } });
  function sample(t, S) {
    const live = t == null;
    if (live) t = now();
    S = S || mk();
    const b = beta(t), c = seal(t, live);
    S.t = t; S.clock = clockOf(t); S.strict = live ? strictNow() : strictAt(t + TICK); S.halted = haltedAt(t); S.paused = st.paused != null;
    let tag = floor((b - 0.6) / CARRY) * round(CARRY / DT) + 2;
    if (st.follow != null) { if (t <= prop(st.follow).te) tag = st.follow; else if (live) { st.follow = null; save(); } }
    let n = 0;
    S.tag = tag; S.ti = -1;
    for (let k = max(0, floor(beta(t - 8.5) / DT) - 1), hi = floor(b / DT); k <= hi && n < N; k++) {
      const p = prop(k);
      if (t < p.tb || t > p.te) continue;
      place(p, t, S, n);
      if (k === tag) S.ti = n;
      n++;
    }
    S.n = n;
    if (S.ti >= 0) {
      const ph = S.ph[S.ti], g = S.gate[S.ti] || 1;
      S.tagId = pid(tag); S.tagTone = ph === 4 ? 'no' : 'ok';
      S.tagLine = ph === 4 ? 'Rejected · logged' : ph === 1 ? '04 Approve · checking' : pad(g, 2) + ' ' + GATE[g - 1];
    } else S.tagId = S.tagLine = S.tagTone = '';
    S.bl = lam(t) / BT; S.bi = c.i;
    tally(lamInv((c.i + 1) * BT), t + 1e-9);
    const cn = S.counts;
    cn.s = c.s + TS; cn.r = c.r + TJ; cn.n = max(0, bornCount(b) - K0); cn.f = cn.n - cn.s - cn.r;
    return S;
  }

  function push(t, k, v) {
    const e = st.ev, last = e[e.length - 1];
    if (k === 's' && last && last[1] === 's' && last[0] === t) last[2] = v; else e.push([t, k, v]);
    let folded = false;
    if (e.length > 40) { derive(); seal(now(), true); }
    while (e.length > 40) {
      const b = e[0][1] === 'b' ? e.shift() : [0, 'b', [STRICT, 0, 0]], x = e[0], lim = min(t, lastT) - 12;
      let done = false;
      if (x && x[0] < lim) {
        if (x[1] === 'h') {
          const j = e.findIndex(y => y[1] === 'r');
          if (j > 0 && e[j][0] < lim) { const d = e[j][0] - x[0]; b[2][1] += d; b[2][2] += max(0, d - DRAIN); e.splice(j, 1); e.shift(); done = true; }
        } else { if (x[1] === 's') b[2][0] = x[2]; e.shift(); done = true; }
      }
      e.unshift(b);
      if (!done) break;
      folded = true;
    }
    derive();
    if (folded) checkpoint(); else save();
  }
  function set(k, v) {
    if (k !== 'strict') return;
    v = round(clamp(+v || 0, 0, 0.6) * 100) / 100;
    if (v === strictNow()) return;
    push((floor(now() / TICK) + 1) * TICK, 's', v);
    changed();
  }
  function halt() { const t = now(); if (haltedAt(t)) return; push(t, 'h', 0); changed(); }
  function resume() {
    const t = now(), was = haltedAt(t);
    if (was) push(t, 'r', 0);
    if (st.paused != null) pause(false); else if (was) changed();
  }
  function pause(on) {
    on = on !== false;
    if (on === (st.paused != null)) return;
    if (on) st.paused = now(); else { const t = st.paused; st.paused = null; st.t0 = Date.now() - (t - PRE) * 1000; lastT = t; }
    save(); changed();
  }
  function follow(k) {
    k = k === 'next' ? bornCount(beta(now())) : k == null ? null : +k;
    if (k === st.follow) return;
    st.follow = k; save(); changed();
  }

  const el = (tag, cls, text) => { const n = doc.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const body = r => [r.id, r.t, r.ev, r.sub, r.d].join('|');
  function record(ev, d, where) {
    const L = st.rec;
    if (L.length >= 500 || !ev) return null;
    const at = now(), r = { id: '#' + pad(L.length + 1, 4), t: clockOf(at), at, ev: String(ev), sub: 'you · ' + (where || PAGE), d: String(d == null ? '' : d), where: where || PAGE, prev: L.length ? L[L.length - 1].hash : ROOT };
    r.hash = sha256(r.prev + '|' + body(r));
    L.push(r); save(); receipts(true);
    doc.dispatchEvent(new CustomEvent('oxa:record', { detail: r }));
    return r;
  }
  function verify() {
    let prev = ROOT, at = -1;
    st.rec.forEach((r, i) => { if (at < 0 && (r.prev !== prev || sha256(r.prev + '|' + body(r)) !== r.hash)) at = i; prev = r.hash; });
    return { ok: at < 0, n: st.rec.length, at };
  }
  function clear() { st.rec = []; save(); receipts(false); doc.dispatchEvent(new CustomEvent('oxa:record', { detail: null })); }
  function receipts(isNew) {
    const L = st.rec, r = L[L.length - 1], link = doc.querySelector('.nav-links a[href*="trust"]');
    doc.querySelectorAll('[data-run-receipt]').forEach(box => {
      if (!r) { box.replaceChildren(); return; }
      const line = el('span', 'receipt-rec'), say = el('span', 'sr-only', isNew ? `Recorded. ${r.ev} ${r.d}. Record ${L.length}.` : ''), go = el('a', 'link-arrow receipt-go', `${L.length} record${L.length > 1 ? 's' : ''} · Your ledger`);
      line.setAttribute('aria-hidden', 'true');
      line.append(el('i', 'pip'), el('b', '', r.id), el('span', 'receipt-who', ' · you'), el('span', 'receipt-what', ` · ${r.ev} ${r.d}`), ' · ', el('u', '', r.hash.slice(0, 8)));
      go.href = page === 'trust' ? '#ledger' : ((link && link.getAttribute('href')) || 'trust.html') + '#ledger';
      go.insertAdjacentHTML('beforeend', '<svg class="arr" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" focusable="false"><path d="M2 8h11M9 4l4 4-4 4"/></svg>');
      box.replaceChildren(line, say, go);
      if (isNew && !rm.matches) { box.classList.remove('is-new'); void box.offsetWidth; box.classList.add('is-new'); }
    });
  }

  function hand(input, o) {
    o = o || {};
    const fig = input.closest('figure') || input.parentNode, lo = +input.min || 0, hi = input.max === '' ? 100 : +input.max, k = o.scale || 1, det = o.detent;
    let v0 = +input.value, vd = v0, timer = 0, held = false, lock = false, tapAt = 0, tapX = 0, fs = 16;
    const say = v => { if (o.key) set(o.key, v * k); if (o.input) o.input(v); };
    const commit = () => {
      clearTimeout(timer); timer = 0;
      const v = +input.value, a = v0;
      if (v === a) return;
      v0 = v;
      if (o.ev) record(o.ev, o.fmt ? o.fmt(a, v) : `${a} → ${v}${o.unit || ''}`, o.where);
      if (o.commit) o.commit(a, v);
    };
    const put = v => { v = clamp(v, lo, hi); if (v === +input.value) return; input.value = v; say(+input.value); };
    // a press that did not move waits 320 ms before it is sealed, so a double click or a double tap (back to the detent) is one record
    // a gesture the browser takes back (a touch that turned into a scroll) puts the scale where the press found it and seals nothing
    const up = e => { lock = false; if (!held) return; held = false; fig.classList.remove('is-held'); if (e && e.type === 'pointercancel') { if (+input.value !== vd) { input.value = vd; input.dispatchEvent(new Event('input', { bubbles: true })); } else if (vd !== v0) timer = setTimeout(commit, 700); return; } if (det != null && e && e.type === 'pointerup' && abs(e.clientX - tapX) < 4) { clearTimeout(timer); timer = setTimeout(commit, 320); } else commit(); };
    input.addEventListener('input', () => {
      if (lock) input.value = det;
      else if (held && det != null && +input.value !== det && abs(+input.value - det) / (hi - lo) * (input.offsetWidth - 2.75 * fs) < 5 * fs / 16) input.value = det;
      say(+input.value);
      if (!held) { clearTimeout(timer); timer = setTimeout(commit, 700); }
    });
    input.addEventListener('pointerdown', e => {
      if (e.button) return;
      const t = performance.now();
      fs = parseFloat(getComputedStyle(root).fontSize) || 16;
      ['pointerup', 'pointercancel'].forEach(n => window.addEventListener(n, up, { once: true, capture: true }));
      if (det != null && e.pointerType !== 'mouse' && t - tapAt < 320 && abs(e.clientX - tapX) < 24) { tapAt = 0; lock = true; put(det); commit(); return; }
      tapAt = t; tapX = e.clientX;
      vd = +input.value; held = true; clearTimeout(timer); timer = 0; fig.classList.add('is-held');
    });
    input.addEventListener('dblclick', () => { if (det != null) { put(det); commit(); } });
    input.addEventListener('keydown', e => {
      const d = e.key === 'PageUp' ? 1 : e.key === 'PageDown' ? -1 : 0;
      if (!d) return;
      e.preventDefault(); put(+input.value + d * (o.page || 10));
      clearTimeout(timer); timer = setTimeout(commit, 700);
    });
    input.addEventListener('blur', () => { if (!held && timer) commit(); });
    const sync = first => { const v = round(strictNow() / k); if (o.key === 'strict' && !held && !timer && (first === true || v !== +input.value)) { input.value = v; v0 = +input.value; if (o.input) o.input(v0); } };
    sync(true);
    doc.addEventListener('oxa:run', sync);
    return { commit, sync };
  }

  const subs = [];
  let raf = 0, tmr = 0, dtm = 0, ckAt = 0, bar = null, rec = null, barW = null, barT = null, mode = 'model', shown = '';
  const S = mk();
  const running = () => st.paused == null && !doc.hidden && !rm.matches && !doc.prerendering;
  const anyOn = () => subs.some(s => s.on);
  // every subscriber of an element is switched with it (two may draw on one node: a plate's marks and a page's tag)
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => subs.forEach(s => {
    if (s.el !== e.target) return;
    const was = s.on;
    s.on = e.isIntersecting;
    if (s.on && !was) { if (running()) kick(); else s.fn(sample(null, S), 'still'); }
  // the root starts under the bar: what only shows under it (a page's first chapter at the bar, the take's foot) is not on screen
  })), { rootMargin: `-${(n => (n ? Math.ceil(n.getBoundingClientRect().height) + 2 : 0))(doc.querySelector('.nav'))}px 0px 10% 0px` }) : null;
  function subscribe(fn, node) {
    const s = { fn, el: node || null, on: !node || !io }, peer = node && io && subs.find(x => x.el === node);
    subs.push(s);
    if (peer) { s.on = peer.on; if (s.on) { if (running()) kick(); else fn(sample(null, S), 'still'); } }
    else if (node && io) io.observe(node); else { fn(sample(null, S), 'still'); kick(); }
    return () => { const i = subs.indexOf(s); if (i >= 0) subs.splice(i, 1); if (node && io && !subs.some(x => x.el === node)) io.unobserve(node); };
  }
  function frame() {
    raf = 0;
    if (!running()) return;
    sample(null, S);
    let any = false;
    for (let i = 0; i < subs.length; i++) if (subs[i].on) { any = true; subs[i].fn(S, 'frame'); }
    paint(S.t);
    if (S.t - ckAt > 8) { ckAt = S.t; checkpoint(); }
    if (any) raf = requestAnimationFrame(frame); else idle();
  }
  function idle() {
    clearTimeout(tmr);
    if (running()) tmr = setTimeout(() => { if (anyOn()) kick(); else { const t = now(); paint(t); if (t - ckAt > 8) { ckAt = t; checkpoint(); } idle(); } }, 1020 - (now() % 1) * 1000);
  }
  function kick() { clearTimeout(tmr); if (running()) { if (!raf) raf = requestAnimationFrame(frame); } }
  function changed() {
    const t = now(), h = H[H.length - 1], left = h && h[1] === Infinity && st.paused == null ? h[0] + DRAIN + 0.4 - t : 0;
    // a halt's last proposal lands up to DRAIN seconds after the press: one more still then, so nothing is left drawn in flight where no frame runs
    clearTimeout(dtm);
    if (left > 0) dtm = setTimeout(changed, left * 1000 + 20);
    root.classList.toggle('run-paused', st.paused != null);
    root.classList.toggle('run-halted', haltedAt(t));
    if (OXA.run) doc.dispatchEvent(new CustomEvent('oxa:run'));
    if (running()) { paint(now()); kick(); return; }
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    clearTimeout(tmr);
    sample(null, S);
    for (let i = 0; i < subs.length; i++) if (subs[i].on) subs[i].fn(S, 'still');
    paint(S.t);
  }

  function build() {
    const row = doc.querySelector('.nav .container');
    if (!row || bar) return;
    bar = el('button', 'nav-run'); bar.type = 'button';
    const s = el('span', 'nav-run-s');
    s.setAttribute('aria-hidden', 'true');
    barW = el('b', '', 'Model'); barT = el('span', '', '00:00');
    s.append(el('i'), barW, barT);
    const g = el('i', 'nav-run-g');
    g.setAttribute('aria-hidden', 'true');
    bar.append(s, g);
    rec = el('span', 'nav-run nav-run--rec'); rec.hidden = true;
    rec.append(el('span', 'nav-run-s', 'Record'), g.cloneNode());
    const before = row.querySelector('.nav-links') || row.querySelector('.nav-toggle');
    row.insertBefore(bar, before); row.insertBefore(rec, before);
    bar.addEventListener('click', () => { if (haltedAt(now())) resume(); else pause(st.paused == null); });
    bar.addEventListener('blur', () => paint(now()));
  }
  function paint(t) {
    if (!bar) return;
    const halted = haltedAt(t), state = halted ? 'halt' : st.paused != null ? 'pause' : 'run', want = mode === 'record' && doc.activeElement !== bar ? 'record' : 'model';
    if (want !== shown) { shown = want; bar.hidden = want === 'record'; rec.hidden = want !== 'record'; }
    if (bar.dataset.state !== state) {
      bar.dataset.state = state;
      bar.setAttribute('aria-label', halted ? 'Resume the model (halted)' : state === 'pause' ? 'Resume the model' : 'Pause the model');
      barW.textContent = halted ? 'Halted' : 'Model';
    }
    const c = clockOf(t);
    if (barT.textContent !== c) barT.textContent = c;
  }
  function transport(m) { mode = m === 'record' ? 'record' : 'model'; paint(now()); }

  function endcard() {
    const band = doc.querySelector('main > .cta-band');
    if (!band) return;
    band.classList.add('cta-band--run');
    const box = el('div', 'ledger-line'), sum = el('p', 'll-sum'), track = el('div', 'll-track'), line = el('div', 'll-run'), since = el('b'), eq = el('span', 'll-eq'), lead = el('span'), nums = [];
    const part = w => { const x = el('span'), b = el('b'); nums.push(b); x.append(b, w); return x; };
    lead.append('Since you arrived ', since);
    eq.append(part(' proposed'), ' = ', part(' settled'), ' + ', part(' rejected'), ' + ', part(' in flight'));
    sum.append(lead, el('span', 'sr-only', ': '), eq, el('span', 'sr-only', '. '), el('small', '', 'Illustrative model'));
    const B = Array.from({ length: 30 }, (v, j) => { const b = el('i', 'll-b'); b.style.setProperty('--j', j); b.dataset.h = ''; return b; });
    line.append(...B); track.append(line); track.setAttribute('aria-hidden', 'true');
    const fmt = n => n.toLocaleString('en-US'), put = (n, t) => { if (n.textContent !== t) n.textContent = t; };
    // the sum arrives whole (its words never move after they are first shown), in the room the band kept for it (run.css --ll-h)
    const first = sample(null, S), c0 = first.counts;
    put(since, first.clock); [c0.n, c0.s, c0.r, c0.f].forEach((v, i) => put(nums[i], fmt(v)));
    box.append(sum, track); band.append(box);
    let top = -2, recs = -1, G = 0, said = -1, pips = [];
    const size = () => { G = 5.75 * (parseFloat(getComputedStyle(root).fontSize) || 16); };
    size();
    window.addEventListener('resize', size);
    subscribe(S => {
      const c = S.counts, n = floor(S.bl) - 1;
      if (floor(S.t * 4) !== said || S.paused) { said = floor(S.t * 4); put(since, S.clock); put(nums[0], fmt(c.n)); put(nums[1], fmt(c.s)); put(nums[2], fmt(c.r)); put(nums[3], fmt(c.f)); }
      if (n !== top || recs !== st.rec.length) {
        top = n; recs = st.rec.length;
        B.forEach((b, j) => { const h = n - j >= 0 ? block(n - j).slice(0, 8) : ''; if (b.dataset.h !== h) b.dataset.h = h; b.classList.toggle('is-new', !j && !S.halted); });
        pips.splice(0).forEach(x => x.remove());
        st.rec.forEach(r => { const d = r.at == null ? -1 : n + 1 - lam(r.at) / BT; if (d < 0 || d > 30) return; const x = el('i', 'pip'); x.style.right = (d * 5.75).toFixed(3) + 'rem'; pips.push(x); line.append(x); });
      }
      line.style.transform = `translate3d(${(-(S.bl - floor(S.bl)) * G).toFixed(1)}px, 0, 0)`;
    }, band);
  }

  load();
  if (CAM) { build(); endcard(); }
  changed();
  receipts(false);
  rm.addEventListener('change', changed);
  doc.addEventListener('visibilitychange', () => { if (doc.hidden) checkpoint(); else changed(); });
  window.addEventListener('pagehide', checkpoint);
  window.addEventListener('pageshow', e => { if (e.persisted) { load(); changed(); receipts(false); } });
  doc.addEventListener('prerenderingchange', () => { load(); changed(); receipts(false); });

  OXA.run = {
    now, sample: t => sample(t), set, halt, resume, pause, follow, subscribe, record, records: () => st.rec.map(r => Object.assign({}, r)), verify, clear, hand, transport,
    block, prop: k => Object.assign({ id: pid(k) }, prop(k)), strict: strictNow, sha256, u: u01, body, world: { GX, LX, RING, RAIL, GATE, PRE, DT, BT, tube }, ROOT,
  };
  doc.dispatchEvent(new CustomEvent('oxa:run'));
})();
