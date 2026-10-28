/* OpenEXA — the ledger trace.
   Records sit on one hairline. The link out of each record carries that record's SHA-256, and the next record stores
   the same hash as its "previous hash": that is the whole idea of a hash-chained ledger, drawn literally.
   [data-ledger="live"]   (home §06) runs an illustrative lifecycle and records what the swarm lab on the page decides.
                          It listens on document for
                            'oxa:settled'  {id, lane, ts, gate:'settle', count, followed}
                            'oxa:rejected' {id, ts, count, followed, gate:'approve'}
                            'oxa:inspect'  {record, seq}   (the swarm's trace asks to see a record: scroll, select, pulse)
                          and answers every announcement with 'oxa:recorded' {id, record, hash, seq, followed}.
                          In view, announcements are sealed into at most one record every 2 s; out of view, every 8 s.
                          A followed proposal is answered at once, in a record of its own, which is selected and pulses
                          the next time the ledger is in view.
   [data-ledger="replay"] (Trust §03) holds a fixed excerpt that can be replayed and verified.
   Select any record (click, tap, or arrow keys once the list has focus) to inspect its id, event and both hash links.
   The records are illustrative; every hash is real SHA-256, computed here in the browser. Every count on the panel is
   read from the records themselves. */
(function () {
  'use strict';
  const roots = Array.from(document.querySelectorAll('[data-ledger]'));
  if (!roots.length) return;
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

  /* ---------------- SHA-256 (FIPS 180-4) over UTF-8, synchronous: records are hashed the moment they exist ---------------- */
  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
  const utf8 = new TextEncoder(), W = new Uint32Array(64);
  function sha256(text) {
    const m = utf8.encode(text), len = m.length, words = ((len + 8) >> 6) + 1 << 4, x = new Uint32Array(words);
    for (let i = 0; i < len; i++) x[i >> 2] |= m[i] << (24 - (i & 3) * 8);
    x[len >> 2] |= 0x80 << (24 - (len & 3) * 8);
    x[words - 2] = Math.floor(len / 0x20000000); x[words - 1] = len << 3;
    const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
    for (let o = 0; o < words; o += 16) {
      for (let t = 0; t < 64; t++) {
        if (t < 16) W[t] = x[o + t];
        else {
          const a = W[t - 15], b = W[t - 2];
          W[t] = W[t - 16] + ((a >>> 7 | a << 25) ^ (a >>> 18 | a << 14) ^ a >>> 3) + W[t - 7] + ((b >>> 17 | b << 15) ^ (b >>> 19 | b << 13) ^ b >>> 10);
        }
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

  /* ---------------- shared helpers ---------------- */
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const agentNo = () => String(Math.floor(Math.random() * 900) + 100).padStart(4, '0');
  const clock = (d = new Date()) => d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0');
  const node = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const grouped = hex => hex.match(/.{8}/g).join(' ');
  const HEX = '0123456789abcdef';
  const clean = v => String(v).replace(/[^\w:.#-]/g, '').slice(0, 16);
  const fmt = n => n.toLocaleString('en-US');
  const TOOLS = ['source-01', 'registry-02', 'workflow-01', 'records-03'];
  const REASONS = ['permission missing', 'approval required', 'input outside policy'];
  const tone = ev => (/^(SETTLED|RECONCILED)$/.test(ev) ? ' is-settled' : ev === 'REJECTED' ? ' is-rejected' : '');
  // the swarm's timestamp may be epoch ms or a performance.now() reading; anything else is stamped on arrival
  const stamp = ts => { const n = Number(ts); if (!Number.isFinite(n) || n < 0) return clock(); return clock(new Date(n > 1e12 ? n : (performance.timeOrigin || Date.now() - performance.now()) + n)); };
  // DOM writes only when something changed: a text that is already right is never written again
  const put = (el, text) => { if (el && el.textContent !== text) el.textContent = text; };

  /* ---------------- hex digits that roll to their value ----------------
     One Text node per element (its data is rewritten, nothing is re-created) and one shared frame loop for every roll on
     the page; a roll that should not animate is written at its final value at once. */
  const rolls = new Map(); let rollRaf = 0, rollWake = 0;
  function textOf(el) {
    let t = el.firstChild;
    if (t && t.nodeType === 3 && t === el.lastChild) return t;
    const s = el.textContent; el.textContent = ''; t = document.createTextNode(s); el.append(t);
    return t;
  }
  function rollTo(el, to, delay, dur) {
    const t = textOf(el);
    rolls.set(t, { to, start: performance.now() + delay, dur });
    rollNext(performance.now());
  }
  // frames run only while a roll is actually moving; until the next one is due the loop sleeps on a timer
  function rollNext(now) {
    if (rollRaf || !rolls.size) return;
    let due = Infinity; rolls.forEach(r => { due = Math.min(due, r.start); });
    clearTimeout(rollWake); rollWake = 0;
    if (due - now > 24) rollWake = setTimeout(() => { rollWake = 0; rollNext(performance.now()); }, due - now - 16);
    else rollRaf = requestAnimationFrame(rollFrame);
  }
  function rollFrame(now) {
    rollRaf = 0;
    rolls.forEach((r, t) => {
      if (now < r.start) return;
      const p = Math.min(1, (now - r.start) / r.dur);
      if (p >= 1) { t.data = r.to; rolls.delete(t); return; }
      const n = Math.floor(p * r.to.length);
      let s = r.to.slice(0, n);
      for (let k = n; k < r.to.length; k++) s += HEX[Math.random() * 16 | 0];
      t.data = s;
    });
    rollNext(now);
  }
  function finishRolls(scope) { rolls.forEach((r, t) => { if (scope.contains(t)) { t.data = r.to; rolls.delete(t); } }); }

  roots.forEach(root => { try { trace(root); } catch (error) { console.error('OpenEXA ledger trace could not start.', error); } });

  function trace(root) {
    const stream = root.dataset.ledger !== 'replay';
    const view = root.querySelector('.lt-view'), track = root.querySelector('.lt-track');
    if (!view || !track) return;
    const q = s => root.querySelector(s);
    const ui = { state: q('[data-lt-state]'), ctrl: q('.lt-ctrl'), play: q('[data-lt-play]'), latest: q('[data-lt-latest]'), fresh: q('[data-lt-new]'),
      replay: q('[data-lt-replay]'), verify: q('[data-lt-verify]'), count: q('[data-stream-count]'), swarm: q('[data-lt-swarm]'),
      insp: q('[data-lt-insp]'), leader: q('.lt-leader') };
    ui.playText = ui.play && ui.play.querySelector('span');
    const field = name => root.querySelector(`[data-f="${name}"]`);
    const F = { k: field('k'), rec: field('rec'), ev: field('ev'), d: field('d'), src: field('src'), prev: field('prev'), prevok: field('prevok'), hash: field('hash'), next: field('next') };
    let reduced = motionQuery.matches;

    /* ---- the chain, in memory: newest last; the DOM shows a contiguous window onto it ---- */
    const CAP = 400, DOM_CAP = 36;
    const recs = [], els = new Map();
    let seq = 0, total = 0, nextId = 0x4f21;
    const sw = { recs: 0, settled: 0, rejected: 0 }; // records from the swarm, and the proposals they carry
    const excerpt = Array.from(track.querySelectorAll('.lt-rec')).map(li => {
      const t = s => { const n = li.querySelector(s); return n ? n.textContent.trim() : ''; };
      return { id: t('.lt-id'), lc: t('.lt-lc'), ev: t('.lt-ev').toUpperCase(), sub: t('.lt-sub'), d: li.dataset.d || t('.lt-sub'), t: t('.lt-t'), src: 'excerpt' };
    }).filter(r => r.id && r.ev);
    if (excerpt.length) nextId = (parseInt(excerpt[excerpt.length - 1].id.replace(/[^0-9a-f]/gi, ''), 16) || 0x4f20) + 1;
    const genesis = sha256('genesis|' + (excerpt[0] ? excerpt[0].id : '#4f20'));
    let head = genesis;
    const body = r => [r.id, r.t, r.ev, r.sub, r.d].join('|');
    function write(r) {
      r.seq = ++seq; r.prev = head; r.prevId = recs.length ? recs[recs.length - 1].id : null;
      r.hash = sha256(r.prev + '|' + body(r));
      head = r.hash; recs.push(r); total++;
      if (recs.length > CAP) recs.shift();
      return r;
    }
    const bySeq = s => { if (!recs.length) return null; const i = s - recs[0].seq; return i >= 0 && i < recs.length ? recs[i] : null; };
    const newest = () => (recs.length ? recs[recs.length - 1].seq : 0);
    if (stream) { // the excerpt in the page is the start of today's stream: stamp it as just written
      const now = Date.now();
      excerpt.forEach((r, i) => { r.t = clock(new Date(now - (excerpt.length - i) * 1150 - 600)); });
    }
    excerpt.forEach(write);

    /* ---- one record = one column on the line ---- */
    function build(r) {
      const li = node('li', 'ln lt-rec' + tone(r.ev) + (r.src === 'swarm' ? ' is-swarm' : '') + (r.followed ? ' is-followed' : ''));
      li.setAttribute('role', 'option'); li.setAttribute('aria-selected', 'false'); li.tabIndex = -1;
      li.dataset.seq = r.seq;
      li.setAttribute('aria-label', `${r.id}, ${r.ev}, ${r.d}, ${r.t}`);
      const meta = node('span', 'lt-meta'); meta.append(node('span', 'lt-id', r.id), node('span', 'lt-lc', r.lc || ''));
      const line = node('span', 'lt-line'); line.setAttribute('aria-hidden', 'true');
      line.append(node('i', 'lt-node'), node('i', 'lt-seg'), node('span', 'lt-tag', r.hash.slice(0, 8)));
      li.append(meta, node('b', 'lt-ev', r.ev), node('span', 'lt-sub', r.sub), node('time', 'lt-t', r.t), line);
      els.set(r.seq, li);
      return li;
    }
    track.setAttribute('role', 'listbox');
    track.setAttribute('aria-orientation', 'horizontal');
    let rendered = 0; // the newest record in the DOM
    const firstSeq = () => (track.firstElementChild ? +track.firstElementChild.dataset.seq : 0);
    // the window: the newest DOM_CAP records, reaching back far enough to keep a selection (or a given record) in it
    function rebuild(from) {
      els.clear();
      const lo = Math.min(from || Infinity, sel !== null ? sel - 1 : Infinity, newest() - DOM_CAP + 1);
      const keep = recs.filter(r => r.seq >= lo);
      track.replaceChildren(...keep.map(build));
      rendered = keep.length ? keep[keep.length - 1].seq : 0;
      selLi = beforeLi = null;
      markHead();
      if (sel !== null && !els.has(sel)) sel = null;
      markSel();
      stop(sel !== null ? els.get(sel) : track.lastElementChild);
    }
    // a new record's hash resolves on its link, digit by digit, as the link forms (the chain below does the same). Only
    // the newest record rolls, and only while it is on screen and the stream is running
    function landed(li) {
      li.classList.add('is-new'); setTimeout(() => li.classList.remove('is-new'), 1300);
      const tag = li.querySelector('.lt-tag');
      if (tag && onScreen() && (playing || !stream)) rollTo(tag, tag.textContent, 380, 420);
    }
    // columns are sized so a whole number of records fills the view: no record is ever cut in half at rest. Every
    // horizontal position is then arithmetic on these numbers: the scroll path never measures the DOM
    const MIN_COL = stream ? 136 : 122;
    const G = { col: 148, padL: 28, padR: 28, w: 0 };
    function fit() {
      const cs = getComputedStyle(track);
      G.padL = parseFloat(cs.paddingLeft) || 0; G.padR = parseFloat(cs.paddingRight) || 0; G.w = view.clientWidth;
      const avail = G.w - G.padL - G.padR;
      if (avail <= 0) return;
      // a phone still shows three live records and two whole links; an excerpt keeps two wider columns, read in full
      const min = window.innerWidth < 600 ? (stream ? 100 : 136) : MIN_COL;
      let n = Math.max(2, Math.floor(avail / min));
      if (!stream) n = Math.min(n, Math.max(2, recs.length));
      G.col = Math.floor(avail / n * 10) / 10;
      root.style.setProperty('--lt-col', G.col + 'px');
    }
    const maxScroll = () => Math.max(0, Math.round(G.padL + G.padR + track.childElementCount * G.col - G.w));
    const leftOf = li => G.padL + (+li.dataset.seq - firstSeq()) * G.col;
    let headLi = null;
    function markHead() {
      const li = track.lastElementChild;
      if (headLi && headLi !== li) headLi.classList.remove('is-head');
      if (li) li.classList.add('is-head');
      headLi = li;
    }
    let tabStop = null;
    function stop(li) { // roving tabindex: the list is one tab stop
      if (tabStop && tabStop !== li) tabStop.tabIndex = -1;
      tabStop = li || null; if (tabStop) tabStop.tabIndex = 0;
    }
    // the selected record, and the record before it, whose outgoing link is the selected record's previous hash
    let sel = null, selLi = null, beforeLi = null;
    function markSel() {
      const li = sel !== null ? els.get(sel) || null : null, before = li ? li.previousElementSibling : null;
      if (selLi && selLi !== li) { selLi.classList.remove('is-sel'); selLi.setAttribute('aria-selected', 'false'); }
      if (beforeLi && beforeLi !== before) beforeLi.classList.remove('is-before-sel');
      if (li && li !== selLi) { li.classList.add('is-sel'); li.setAttribute('aria-selected', 'true'); }
      if (before && before !== beforeLi) before.classList.add('is-before-sel');
      selLi = li; beforeLi = before;
    }

    /* ---- following the newest record, browsing, inspecting ---- */
    let following = true, intentUntil = 0, playing = stream && !reduced, visible = false;
    const onScreen = () => visible && !document.hidden;
    const atEnd = () => view.scrollLeft >= maxScroll() - 6;
    function toEnd(smooth) { view.scrollTo({ left: maxScroll(), behavior: smooth && !reduced ? 'smooth' : 'auto' }); }
    function reveal(li, smooth, centre) { // horizontal only: never scroll the page under the reader
      const pad = 36, x = leftOf(li), l = x - pad, r = x + G.col + pad, sl = view.scrollLeft;
      let to = null;
      if (centre) to = Math.min(maxScroll(), x + G.col / 2 - G.w / 2); // a record asked for by name sits mid-strip
      else if (l < sl) to = l; else if (r > sl + G.w) to = r - G.w;
      if (to !== null && Math.abs(to - sl) > 1) view.scrollTo({ left: Math.max(0, to), behavior: smooth && !reduced ? 'smooth' : 'auto' });
    }
    function follow(smooth = true) {
      sel = null; following = true;
      intentUntil = 0; // an explicit return to the head outranks the tail of an earlier swipe: the glide is the view's own
      markSel();
      if (stream && rendered !== newest()) flush(false, true); // what was held back while paused joins the line
      stop(track.lastElementChild);
      toEnd(smooth); inspect(); state();
    }
    function select(li, focus, centre) {
      if (!li || !els.has(+li.dataset.seq)) return;
      sel = +li.dataset.seq; following = false;
      markSel(); stop(li);
      if (focus && document.activeElement !== li) li.focus({ preventScroll: true });
      reveal(li, true, centre); inspect(); state();
    }
    track.addEventListener('click', e => { const li = e.target.closest('.lt-rec'); if (li) select(li, true); });
    track.addEventListener('focusin', e => { const li = e.target.closest('.lt-rec'); if (li && +li.dataset.seq !== sel) select(li, false); });
    track.addEventListener('keydown', e => {
      const cur = e.target.closest('.lt-rec'); if (!cur) return;
      const go = { ArrowLeft: cur.previousElementSibling, ArrowRight: cur.nextElementSibling, Home: track.firstElementChild, End: track.lastElementChild }[e.key];
      if (go !== undefined) { e.preventDefault(); if (go) select(go, true); return; }
      if (e.key === 'Escape') { e.preventDefault(); follow(); const b = [ui.play, ui.replay, ui.latest].find(x => x && !x.hidden); if (b) b.focus(); }
    });
    // only a person's own sideways gesture decides that the view stops following the head: a horizontal wheel or trackpad
    // swipe (or shift + wheel), a horizontal touch drag, or a press on the strip's own scrollbar. A vertical page scroll
    // that happens to pass over the strip never does, so the strip's own glide to a new record stays the strip's
    const intent = () => { intentUntil = performance.now() + 900; };
    view.addEventListener('wheel', e => { if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) intent(); }, { passive: true });
    let tx = 0, ty = 0;
    view.addEventListener('touchstart', e => { const t = e.touches[0]; if (t) { tx = t.clientX; ty = t.clientY; } }, { passive: true });
    view.addEventListener('touchmove', e => { const t = e.touches[0]; if (t && Math.abs(t.clientX - tx) > Math.abs(t.clientY - ty)) intent(); }, { passive: true });
    view.addEventListener('pointerdown', e => { if (e.target === view) intent(); }, { passive: true });
    let edgeRaf = 0;
    view.addEventListener('scroll', () => {
      if (!edgeRaf) edgeRaf = requestAnimationFrame(scrolled);
      if (performance.now() > intentUntil) return;
      if (atEnd()) { if (sel === null && !following) follow(false); }
      else if (following) { following = false; state(); }
    }, { passive: true });
    function scrolled() {
      edgeRaf = 0;
      const sl = view.scrollLeft; // read first, then write
      edges(sl);
      if (sel === null) inspect(); else leader();
      pill(); // only the pill's count: a replay's or an audit's own status line stays as it is
    }
    let edgeL = null, edgeR = null;
    function edges(sl = view.scrollLeft) {
      const m = maxScroll(), l = sl > 4, r = sl < m - 4;
      if (l !== edgeL) root.classList.toggle('has-left', (edgeL = l));
      if (r !== edgeR) root.classList.toggle('has-right', (edgeR = r));
    }

    /* ---- the inspector: id, event, detail, source, and both hash links of one record ---- */
    function hexInto(el, hex) {
      // the first eight hex are the ones written on the links
      el.replaceChildren(node('b', null, hex.slice(0, 8)), document.createTextNode(grouped(hex).slice(8)));
    }
    // the newest record wholly inside the view (the head while the view rests on it); never one that is not drawn
    function inView() {
      const n = track.childElementCount; if (!n || G.col <= 0) return null;
      const sl = view.scrollLeft;
      const i = Math.min(n - 1, Math.floor((sl + G.w + 1 - G.padL) / G.col) - 1);
      if (i < 0 || G.padL + i * G.col < sl - 1) return null;
      return bySeq(firstSeq() + i);
    }
    function sourceOf(r) {
      if (r.src === 'swarm') {
        const who = r.pid ? `proposal ${r.pid}${r.n > 1 ? ` + ${fmt(r.n - 1)} more` : ''}` : `${fmt(r.n)} proposal${r.n > 1 ? 's' : ''}`;
        return `The swarm above · ${who}${r.lane ? ' · ' + r.lane : ''}${r.rej ? ' · rejected at 04 Approve' : ''}${r.followed ? ' · the proposal you followed' : ''}`;
      }
      return `Illustrative ${r.src === 'gen' ? 'generator' : 'excerpt'}${r.lc ? ' · ' + r.lc : ''}`;
    }
    let shown = '';
    function inspect() {
      if (!F.rec || !recs.length) return;
      const r = (sel !== null && bySeq(sel)) || inView() || bySeq(rendered);
      if (!r) return;
      const after = bySeq(r.seq + 1), drawnAfter = after && after.seq <= rendered;
      const title = sel !== null ? (r.followed ? 'The proposal you followed' : 'Selected record') : 'Newest record in view';
      const key = `${r.seq}|${title}|${after ? (drawnAfter ? 'd' : 'b') : 'n'}`;
      if (key === shown) { leader(); return; }
      shown = key;
      if (F.k) { put(F.k, title); F.k.classList.toggle('is-followed', sel !== null && !!r.followed); }
      put(F.rec, `${r.id} · ${r.t}`);
      put(F.ev, r.ev); F.ev.className = 'lt-insp-ev' + tone(r.ev);
      put(F.d, r.d);
      if (F.src) put(F.src, sourceOf(r));
      hexInto(F.prev, r.prev); hexInto(F.hash, r.hash);
      // real checks, not labels: the stored link equals the previous record's hash; this hash recomputes from the content
      const before = bySeq(r.seq - 1);
      const linkOk = before ? before.hash === r.prev : r.seq === 1 ? r.prev === genesis : true;
      const selfOk = sha256(r.prev + '|' + body(r)) === r.hash;
      put(F.prevok, !linkOk ? '✗ does not match the record before' : before ? `✓ the hash of ${before.id}` : r.seq === 1 ? '✓ genesis of this ledger' : '✓ the hash of the record before');
      F.prevok.classList.toggle('is-bad', !linkOk);
      put(F.next, !selfOk ? '✗ does not recompute from this record' : drawnAfter ? `✓ recomputes · stored as previous hash by ${after.id}` : after ? '✓ recomputes · stored by the next record' : stream ? '✓ recomputes · awaiting the next record' : '✓ recomputes · last record of this excerpt');
      F.next.classList.toggle('is-bad', !selfOk);
      leader();
    }
    let leaderOn = false;
    function leader() {
      if (!ui.leader) return;
      const li = sel !== null ? els.get(sel) : null;
      if (!li || !ui.insp || ui.insp.hidden) { if (leaderOn) { ui.leader.classList.remove('is-on'); leaderOn = false; } return; }
      const n = li.querySelector('.lt-node').getBoundingClientRect(), v = view.getBoundingClientRect(), r = root.getBoundingClientRect(), i = ui.insp.getBoundingClientRect();
      const on = n.left >= v.left + 8 && n.right <= v.right - 8;
      ui.leader.style.setProperty('--x', (n.left + n.width / 2 - r.left - 0.5).toFixed(1) + 'px');
      ui.leader.style.setProperty('--y', (n.bottom - r.top + 3).toFixed(1) + 'px');
      ui.leader.style.setProperty('--h', Math.max(0, i.top - n.bottom - 3).toFixed(1) + 'px');
      if (on !== leaderOn) { ui.leader.classList.toggle('is-on', on); leaderOn = on; }
    }

    /* ---- status line, controls, counters: all derived from state ---- */
    const flags = {};
    function flag(name, on) { if (flags[name] !== on) { flags[name] = on; root.classList.toggle(name, on); } }
    function state(text) {
      flag('is-inspecting', sel !== null);
      flag('is-following', following);
      flag('is-running', stream && playing && following && onScreen()); // its breathing loops run only while it is seen
      flag('is-paused', stream && !playing);
      const r = sel !== null ? bySeq(sel) : null;
      put(ui.state, text || (r ? `Inspecting ${r.id}` : stream ? (playing ? (following ? 'Running · illustrative stream' : 'Illustrative stream · browsing') : 'Paused · illustrative stream') : stateIdle));
      if (ui.play) {
        put(ui.playText, playing ? 'Pause' : 'Play');
        const label = playing ? 'Pause the stream' : 'Play the stream';
        if (ui.play.getAttribute('aria-label') !== label) ui.play.setAttribute('aria-label', label);
        ui.play.classList.toggle('is-paused', !playing);
      }
      pill();
    }
    function pill() {
      if (!ui.latest) return;
      // the way back: shown whenever the view is not resting on the newest record, with how many records are newer
      // than the last one wholly in view (records held back while paused included)
      const held = newest() - rendered, show = stream && (!following || held > 0);
      if (ui.latest.hidden === show) ui.latest.hidden = !show;
      if (show && ui.fresh) { const lv = following ? null : inView(), n = newest() - (lv ? lv.seq : rendered); put(ui.fresh, n > 0 ? `+${n > 99 ? '99+' : n}` : ''); }
    }
    function counts() {
      put(ui.count, fmt(total));
      if (ui.swarm) {
        if (ui.swarm.hidden !== !sw.recs) ui.swarm.hidden = !sw.recs;
        if (sw.recs) put(ui.swarm, ` · ${fmt(sw.recs)} from the swarm above, carrying ${fmt(sw.settled)} settled${sw.rejected ? ` and ${fmt(sw.rejected)} rejected` : ''} proposals`);
      }
    }

    /* ---- appending: new columns land on the line, the link to them forms, the view glides to the head ---- */
    let lastFlush = 0, flushTimer = 0;
    function flush(animate, force) {
      lastFlush = performance.now();
      if (!recs.length || newest() === rendered) return;
      // paused: the records are written, hashed and counted, but nothing is drawn until the reader asks for them
      if (stream && !playing && !force) { counts(); state(); return; }
      const fresh = recs.filter(r => r.seq > rendered);
      if (!rendered || fresh.length > 8 || !track.lastElementChild) { rebuild(); if (following) toEnd(false); }
      else {
        const was = track.lastElementChild, play = animate && !reduced && onScreen();
        fresh.forEach((r, i) => { const li = build(r); track.append(li); if (play && i === fresh.length - 1) landed(li); });
        if (play) { was.classList.add('is-linking'); setTimeout(() => was.classList.remove('is-linking'), 1400); }
        rendered = fresh[fresh.length - 1].seq;
        markHead(); trim();
        if (following) { stop(track.lastElementChild); toEnd(play); }
      }
      edges(); counts(); inspect(); state();
    }
    function trim() { // keep the DOM small; compensate the scroll so nothing on screen moves
      let removed = 0;
      while (track.childElementCount > DOM_CAP) {
        const first = track.firstElementChild;
        if (first === document.activeElement || first === selLi || first === beforeLi) break;
        els.delete(+first.dataset.seq); first.remove(); removed += G.col;
      }
      if (removed) view.scrollLeft = Math.max(0, view.scrollLeft - removed);
    }
    function soon() { // the line takes records in at a readable pace
      if (flushTimer) return;
      flushTimer = setTimeout(() => { flushTimer = 0; if (onScreen()) flush(true); }, Math.max(0, 420 - (performance.now() - lastFlush)));
    }

    /* ---- live: the illustrative lifecycle generator ---- */
    let timer = 0, queue = [], cycles = 0;
    function lifecycle(lc = 'L-' + (Math.floor(Math.random() * 9000) + 1000)) {
      const a = agentNo(), e = agentNo(), r = agentNo();
      const steps = [
        { ev: 'PROPOSED', lc, sub: `domain agent a-${a}`, d: `agent=domain:a-${a} · lifecycle=${lc} · next step` },
        { ev: 'VALIDATED', lc, sub: 'schema · inputs · scope', d: `${lc} · schema checked · inputs complete · scope checked` },
      ];
      cycles++;
      if (cycles === 2 || (cycles > 2 && Math.random() < 0.12)) { // rejects are recorded too: the second lifecycle shows one
        const why = pick(REASONS);
        steps.push({ ev: 'REJECTED', lc, sub: `council · ${why}`, d: `council · ${why} · recorded` });
        return steps;
      }
      steps.push(
        { ev: 'APPROVED', lc, sub: 'council · policy v7', d: 'council · policy v7 · bounded action' },
        { ev: 'SUBMITTED', lc, sub: `exec agent e-${e}`, d: `agent=exec:e-${e} · tool=${pick(TOOLS)} · idempotent` },
        { ev: 'COMPLETED', lc, sub: 'action confirmed', d: `${lc} · action confirmed · receipt attached` },
        { ev: 'SETTLED', lc, sub: `records agent r-${r}`, d: `agent=records:r-${r} · previous hash linked` });
      return steps;
    }
    if (stream && excerpt.length) { // the page's excerpt may end mid-lifecycle: the stream picks that lifecycle up where it stopped
      const last = excerpt[excerpt.length - 1], done = recs.filter(r => r.lc === last.lc).map(r => r.ev);
      cycles = recs.some(r => r.lc !== last.lc) ? 1 : 0;
      if (last.lc && !/^(SETTLED|REJECTED)$/.test(last.ev)) queue = lifecycle(last.lc).filter(s => !done.includes(s.ev));
    }
    const newId = () => '#' + (nextId++ & 0xffff).toString(16).padStart(4, '0');
    function tick() {
      timer = 0;
      if (!playing || !onScreen()) return;
      if (!queue.length) queue = lifecycle();
      write(Object.assign({ id: newId(), t: clock(), src: 'gen' }, queue.shift()));
      flush(true);
      timer = setTimeout(tick, queue.length ? 950 + Math.random() * 500 : 1900 + Math.random() * 900);
    }
    function wake() {
      if (onScreen()) {
        if (stream) { // what the swarm decided while the line was out of view arrives now, sealed
          clearTimeout(sealTimer); sealTimer = 0;
          if (inbox.settled.length || inbox.rejected.length) { sealOne(); lastSeal = performance.now(); }
          schedule();
        }
        flush(false);
        if (pendingFollow) showFollowed();
        if (stream && playing && !timer) timer = setTimeout(tick, 1100);
      } else {
        clearTimeout(timer); timer = 0;
        finishRolls(root);
        if (stream) { clearTimeout(sealTimer); sealTimer = 0; schedule(); }
      }
      if (stream) state();
    }
    if (ui.play) ui.play.addEventListener('click', () => {
      playing = !playing;
      clearTimeout(timer); timer = 0;
      if (playing) { follow(); timer = setTimeout(tick, 350); }
      state();
    });
    if (ui.latest) ui.latest.addEventListener('click', () => follow());

    /* ---- live: what the swarm decides becomes records ----
       Announcements are sealed into blocks: in view at most one record every 2 s (so the lifecycle's own records stay
       readable), out of view one every 8 s (nothing is drawn there). A block names the proposal it carries and how many
       more; no id is ever invented. Settled and rejected proposals are sealed apart: a block is one or the other. The
       proposal the visitor followed never waits: what was announced before it is sealed first, then it is written in a
       record of its own and answered at once. */
    const SEAL_MS = 8000, SEAL_MS_IN_VIEW = 2000;
    const inbox = { settled: [], rejected: [] };
    let sealTimer = 0, lastSeal = -Infinity, followedSeq = 0, pendingFollow = false;
    const laneOf = v => v == null || v === '' ? null : typeof v === 'number' ? (Number.isInteger(v) ? v : +v.toFixed(2)) : clean(v);
    const countOf = d => Math.min(99999, Math.max(1, Math.floor(Number(d.count)) || 1)); // detail.count: proposals in one announcement
    const pidOf = id => typeof id === 'number' ? 'P-' + id : clean(id || '');
    function intake(kind, e) {
      const d = e && e.detail;
      if (!d || typeof d !== 'object') return;
      const a = { id: d.id, lane: kind === 'settled' ? d.lane : null, ts: d.ts, count: countOf(d), followed: d.followed === true, at: performance.now() };
      if (a.followed) { queueMicrotask(() => followedIn(a, kind)); return; } // never inside the swarm's frame, but at once
      inbox[kind].push(a);
      schedule();
    }
    function schedule() {
      if (sealTimer || (!inbox.settled.length && !inbox.rejected.length)) return;
      // even a zero wait goes through a timer: announcements dispatched together are sealed together
      const wait = onScreen() ? Math.max(0, SEAL_MS_IN_VIEW - (performance.now() - lastSeal)) : SEAL_MS;
      sealTimer = setTimeout(sealDue, wait);
    }
    function sealDue() {
      sealTimer = 0;
      if (onScreen()) { sealOne(); counts(); soon(); }
      else { ['settled', 'rejected'].forEach(k => { if (inbox[k].length) record(take(k), k); }); }
      lastSeal = performance.now();
      schedule();
    }
    const take = k => { const g = inbox[k]; inbox[k] = []; return g; };
    function sealOne() { // the kind that has waited longest
      const s = inbox.settled, j = inbox.rejected;
      const k = !s.length ? 'rejected' : !j.length ? 'settled' : s[0].at <= j[0].at ? 'settled' : 'rejected';
      if (inbox[k].length) record(take(k), k);
    }
    function record(group, kind) { // one record for one or more announcements of one kind
      const rej = kind === 'rejected';
      const named = group.filter(a => a.id != null && a.id !== '');
      const key = named.find(a => a.followed) || named[named.length - 1] || null;
      const pid = key ? pidOf(key.id) : '', followed = !!(key && key.followed);
      const n = group.reduce((s, a) => s + a.count, 0);
      const lanes = Array.from(new Set(group.map(a => laneOf(a.lane)).filter(v => v !== null)));
      const nums = lanes.every(v => typeof v === 'number') ? lanes.slice().sort((a, b) => a - b) : null;
      const lane = !lanes.length ? '' : lanes.length === 1 ? `lane ${lanes[0]}` : nums ? `lanes ${nums[0]}–${nums[nums.length - 1]}` : `${lanes.length} lanes`;
      const tail = rej ? 'rejected at 04' : lane;
      const what = pid ? (n > 1 ? `${pid} +${fmt(n - 1)} more` : `proposal ${pid}`) : `${fmt(n)} proposal${n > 1 ? 's' : ''}`;
      const verb = rej ? 'rejected by the council at 04 Approve in the swarm above' : 'settled in the swarm above';
      const d = (pid ? (n > 1 ? `${pid}${followed ? ' (followed)' : ''} and ${fmt(n - 1)} more ${verb}` : `proposal ${pid} ${verb}`)
        : `${fmt(n)} proposal${n > 1 ? 's' : ''} ${verb}, in the batch of the one you followed`)
        + (group.length > 1 ? ' · sealed as one block' : '') + (rej ? ' · not executed · recorded' : ' · chained here');
      const r = write({ id: newId(), t: stamp(group[group.length - 1].ts), ev: rej ? 'REJECTED' : 'SETTLED', lc: followed ? 'Followed' : 'Swarm',
        sub: what + (tail ? ' · ' + tail : ''), d, src: 'swarm', pid, lane, n, followed, rej });
      sw.recs++; if (rej) sw.rejected += n; else sw.settled += n;
      named.forEach(a => document.dispatchEvent(new CustomEvent('oxa:recorded', { detail: { id: a.id, record: r.id, hash: r.hash, seq: r.seq, followed: a.followed } })));
      return r;
    }
    function followedIn(a, kind) {
      clearTimeout(sealTimer); sealTimer = 0;
      // the rest of its batch (settled or rejected in the same announcement) rides with the block sealed just before it,
      // or, when nothing is waiting, with the next one
      const rest = a.count > 1 ? { id: null, lane: null, ts: a.ts, count: a.count - 1, followed: false, at: a.at } : null;
      const restNow = !!rest && inbox[kind].length > 0;
      if (restNow) inbox[kind].push(rest);
      ['settled', 'rejected'].forEach(k => { if (inbox[k].length) record(take(k), k); });
      const r = record([Object.assign({}, a, { count: 1 })], kind);
      if (rest && !restNow) inbox[kind].push(rest);
      lastSeal = performance.now();
      followedSeq = r.seq; pendingFollow = true;
      counts();
      if (onScreen()) { flush(playing && !reduced, true); showFollowed(); }
      schedule();
    }
    // the followed record is selected the next time the ledger is in view (exempt from trimming while it is), and its
    // block pulses once the strip is actually on screen; Escape or Latest returns to the running line
    function showFollowed() {
      pendingFollow = false;
      const li = ensure(followedSeq);
      if (!li) return;
      select(li, false, true);
      pulseSoon(li);
    }
    function ensure(s) { // the record's column, drawing it first if it is held back or was trimmed from the window
      if (els.has(s)) return els.get(s);
      if (!bySeq(s)) return null;
      if (s > rendered) flush(false, true);
      if (!els.has(s)) rebuild(s - 2);
      return els.get(s) || null;
    }
    let pulseLi = null, pulseTimer = 0, pulseWant = 0, stripSeen = false;
    function pulseSoon(li) { pulseWant = +li.dataset.seq; if (stripSeen) pulseNow(); }
    function pulseNow() {
      const li = els.get(pulseWant); pulseWant = 0;
      if (!li || reduced) return;
      clearTimeout(pulseTimer);
      if (pulseLi) pulseLi.classList.remove('is-pulse');
      void li.offsetWidth; // the same record may pulse again: restart its animation
      li.classList.add('is-pulse'); pulseLi = li;
      pulseTimer = setTimeout(() => { li.classList.remove('is-pulse'); if (pulseLi === li) pulseLi = null; }, 1600);
    }
    // the swarm's trace asks to see a record: bring the ledger to the middle of the screen below the bar, select, pulse
    function bringIntoView() {
      const navH = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 72;
      let b = root.getBoundingClientRect(), shift = 0;
      try { shift = new DOMMatrixReadOnly(getComputedStyle(root).transform).m42 || 0; } catch (e) { shift = 0; } // a reveal still rising
      const top = b.top - shift, avail = window.innerHeight - navH;
      const y = b.height <= avail - 24 ? top - navH - (avail - b.height) / 2 : top - navH - 12;
      if (Math.abs(y) > 2) window.scrollTo({ top: Math.max(0, Math.round(window.scrollY + y)), behavior: reduced ? 'instant' : 'smooth' });
    }
    function inspectEvent(e) {
      const d = (e && e.detail) || {};
      const s = Math.floor(Number(d.seq)), id = typeof d.record === 'string' ? d.record.trim().toLowerCase() : '';
      let r = Number.isFinite(s) ? bySeq(s) : null;
      if (id && (!r || r.id !== id)) { for (let i = recs.length - 1; i >= 0; i--) if (recs[i].id === id) { r = recs[i]; break; } }
      bringIntoView();
      if (!r) { state(`${id || 'That record'} is no longer held here`); return; }
      if (r.seq === followedSeq) pendingFollow = false;
      const li = ensure(r.seq);
      if (!li) return;
      select(li, true, true); // the reader asked for this record: keyboard focus lands on it too (the page glides, not jumps)
      pulseSoon(li);
    }
    if (stream) {
      document.addEventListener('oxa:settled', e => intake('settled', e));
      document.addEventListener('oxa:rejected', e => intake('rejected', e));
      document.addEventListener('oxa:inspect', inspectEvent);
      // Escape anywhere on the page also returns a selected line to the running stream, unless a control that is on
      // screen holds focus (it keeps its own Escape). After following a proposal, focus is usually still on the swarm's
      // button, screens above: the reader's Escape is for the ledger they are looking at
      document.addEventListener('keydown', e => {
        if (e.key !== 'Escape' || e.defaultPrevented || sel === null || !onScreen()) return;
        const t = e.target;
        if (track.contains(t)) return; // the list handles its own Escape
        if (t && t !== document.body && t !== document.documentElement && !root.contains(t)) {
          const b = t.getBoundingClientRect();
          if (b.bottom > 0 && b.top < window.innerHeight) return;
        }
        follow();
      });
    }

    /* ---- replay: the excerpt writes itself again, at its own rhythm ---- */
    const secs = t => { const m = /(\d+):(\d+):(\d+)(?:\.(\d+))?/.exec(t || ''); return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] + +('0.' + (m[4] || '0')) : 0; };
    function gapMark(li, a, b) { // a long wait between two records is drawn on the link that spans it
      const s = secs(b.t) - secs(a.t);
      if (!li || s < 3600) return;
      const line = li.querySelector('.lt-line');
      if (line && !line.querySelector('.lt-gap')) line.append(node('span', 'lt-gap', `+${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m`));
    }
    function verified() { // recompute every hash from its record and the hash before it; compare with what was stored
      let ok = 0, prev = recs.length ? recs[0].prev : genesis;
      recs.forEach(r => { if (r.prev === prev && sha256(r.prev + '|' + body(r)) === r.hash) ok++; prev = r.hash; });
      return ok;
    }
    const n0 = recs.length, ok0 = verified();
    const stateIdle = stream ? '' : ok0 === n0 ? `Chain ✓ · ${n0} records verify` : `${n0 - ok0} of ${n0} records fail verification`;
    let replaying = 0;
    function replay() {
      clearTimeout(replaying);
      sweep.forEach(clearTimeout); sweep = []; cancelAnimationFrame(glideRaf);
      const all = recs.slice();
      if (!all.length) return;
      if (sel !== null) follow(false);
      following = true; // the view and the inspector follow the record being written
      els.clear(); track.replaceChildren(); rendered = 0; selLi = beforeLi = headLi = null;
      let i = 0;
      const next = () => {
        const r = all[i++];
        const was = track.lastElementChild, li = build(r);
        if (!reduced) landed(li);
        track.append(li); rendered = r.seq; markHead();
        if (was) { gapMark(was, all[i - 2], r); if (!reduced) { was.classList.add('is-linking'); setTimeout(() => was.classList.remove('is-linking'), 1400); } }
        stop(li); toEnd(true); edges(); inspect();
        state(i < all.length ? `Replaying · ${i} of ${all.length}` : `Replayed · ${all.length} records`);
        if (i < all.length) {
          // real gaps between records, compressed: milliseconds stay quick, a long wait shows as a pause
          const gap = secs(all[i].t) - secs(r.t);
          replaying = setTimeout(next, Math.min(1500, Math.max(380, gap * 600)));
        } else replaying = 0;
      };
      next();
    }
    let glideRaf = 0, sweep = [];
    function glide(from, to, ms) { // a scripted pan of the strip, eased; the reader's own scrolling is never fought
      cancelAnimationFrame(glideRaf);
      if (reduced || ms <= 0 || Math.abs(to - from) < 2) { view.scrollLeft = to; return; }
      const t0 = performance.now();
      const step = now => {
        const p = Math.min(1, (now - t0) / ms), e = p < .5 ? 2 * p * p : 1 - Math.pow(2 - 2 * p, 2) / 2;
        view.scrollLeft = from + (to - from) * e;
        if (p < 1 && performance.now() > intentUntil) glideRaf = requestAnimationFrame(step);
      };
      glideRaf = requestAnimationFrame(step);
    }
    function verify() {
      // an audit walks every link from the first record to the last, so the selection steps aside and the strip pans along
      if (sel !== null) { sel = null; markSel(); }
      following = false; inspect(); // the inspector rides along with the sweep
      sweep.forEach(clearTimeout); sweep = [];
      if (replaying) { clearTimeout(replaying); replaying = 0; whole(); inspect(); } // a replay in progress completes at once
      const ok = verified(), n = recs.length, lis = Array.from(track.children), STEP = 110;
      const links = Math.max(0, n - 1), done = ok === n ? `Verified here · ${links} of ${links} links hold` : `${n - ok} of ${n} records fail verification`;
      const m = maxScroll(), lead = !reduced && m > 4 && view.scrollLeft > 4 ? 280 : 0;
      if (m > 4) { glide(view.scrollLeft, 0, lead); sweep.push(setTimeout(() => glide(0, m, lis.length * STEP + 240), lead)); }
      lis.forEach((li, i) => {
        li.classList.remove('is-verified'); void li.offsetWidth;
        const at = reduced ? 0 : lead + i * STEP;
        sweep.push(setTimeout(() => { li.classList.add('is-verified'); if (!reduced) state(`Verifying · ${i + 1} of ${lis.length}`); }, at));
        sweep.push(setTimeout(() => li.classList.remove('is-verified'), at + 1300));
      });
      sweep.push(setTimeout(() => state(done), reduced ? 0 : lead + lis.length * STEP + 120));
    }
    if (ui.replay) { ui.replay.hidden = false; ui.replay.addEventListener('click', replay); }
    if (ui.verify) { ui.verify.hidden = false; ui.verify.addEventListener('click', verify); }
    if (ui.play) ui.play.hidden = !stream;
    // the controls' container shows only when it holds a control (no selector has to ask the document)
    if (ui.ctrl) ui.ctrl.hidden = ![ui.play, ui.replay, ui.verify].some(b => b && !b.hidden && ui.ctrl.contains(b));

    function whole() { // the excerpt, all of it, with its long waits marked on the links
      rebuild();
      Array.from(track.children).forEach((li, i, all) => { if (i) gapMark(all[i - 1], bySeq(+all[i - 1].dataset.seq), bySeq(+li.dataset.seq)); });
    }

    /* ---- start ---- */
    fit();
    if (stream) rebuild(); else { following = false; whole(); }
    if (ui.insp) ui.insp.hidden = false;
    root.classList.add('lt-ready');
    if (stream) {
      root.classList.add('is-stream');
      requestAnimationFrame(() => { toEnd(false); edges(); });
    }
    edges(); counts(); inspect(); state();
    if ('IntersectionObserver' in window) {
      // the stream runs only while some of it is on screen (no margin: nothing is drawn for a reader who cannot see it)
      new IntersectionObserver(([en]) => { visible = en.isIntersecting; wake(); }).observe(root);
      // a pulse waits until the strip itself is on screen
      new IntersectionObserver(([en]) => { stripSeen = en.isIntersecting && en.intersectionRatio >= 0.55; if (stripSeen && pulseWant) pulseNow(); }, { threshold: [0, 0.6, 1] }).observe(view);
    } else { visible = true; stripSeen = true; wake(); }
    document.addEventListener('visibilitychange', wake);
    let fitRaf = 0;
    window.addEventListener('resize', () => {
      if (fitRaf) return;
      fitRaf = requestAnimationFrame(() => {
        fitRaf = 0; fit();
        if (following) toEnd(false); else if (sel !== null && els.has(sel)) reveal(els.get(sel), false);
        edges(); inspect(); leader();
      });
    });
    motionQuery.addEventListener('change', e => { reduced = e.matches; if (reduced && playing) { playing = false; clearTimeout(timer); timer = 0; state(); } });
  }
})();
