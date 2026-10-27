/* OpenEXA — the ledger trace.
   Records sit on one hairline. The link out of each record carries that record's SHA-256, and the next record stores
   the same hash as its "previous hash": that is the whole idea of a hash-chained ledger, drawn literally.
   [data-ledger="live"]   (home §06) streams an illustrative lifecycle and appends every proposal the swarm on the
                          page settles (document event 'oxa:settled', detail {id, lane, ts}); it answers each one with
                          'oxa:recorded' (detail {id, record, hash, seq}).
   [data-ledger="replay"] (Trust §03) holds a fixed excerpt that can be replayed and verified.
   Select any record (click, tap, or arrow keys once the list has focus) to inspect its id, event and both hash links.
   The records are illustrative; every hash is real SHA-256, computed here in the browser. */
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
  const TOOLS = ['source-01', 'registry-02', 'workflow-01', 'records-03'];
  const REASONS = ['permission missing', 'approval required', 'input outside policy'];
  const tone = ev => (/^(SETTLED|RECONCILED)$/.test(ev) ? ' is-settled' : ev === 'REJECTED' ? ' is-rejected' : '');
  // the swarm's timestamp may be epoch ms or a performance.now() reading; anything else is stamped on arrival
  const stamp = ts => { const n = Number(ts); if (!Number.isFinite(n) || n < 0) return clock(); return clock(new Date(n > 1e12 ? n : (performance.timeOrigin || Date.now() - performance.now()) + n)); };

  roots.forEach(root => { try { trace(root); } catch (error) { console.error('OpenEXA ledger trace could not start.', error); } });

  function trace(root) {
    const live = root.dataset.ledger !== 'replay';
    const view = root.querySelector('.lt-view'), track = root.querySelector('.lt-track');
    if (!view || !track) return;
    const q = s => root.querySelector(s);
    const ui = { state: q('[data-lt-state]'), play: q('[data-lt-play]'), latest: q('[data-lt-latest]'), fresh: q('[data-lt-new]'),
      replay: q('[data-lt-replay]'), verify: q('[data-lt-verify]'), count: q('[data-stream-count]'), swarm: q('[data-lt-swarm]'),
      insp: q('[data-lt-insp]'), leader: q('.lt-leader') };
    const field = name => root.querySelector(`[data-f="${name}"]`);
    const F = { rec: field('rec'), ev: field('ev'), d: field('d'), src: field('src'), prev: field('prev'), prevok: field('prevok'), hash: field('hash'), next: field('next') };
    const srcRow = root.querySelector('[data-f-row="src"]');
    let reduced = motionQuery.matches;

    /* ---- the chain, in memory: newest last; the DOM shows a window onto it ---- */
    const CAP = 240, DOM_CAP = 36;
    const recs = [], els = new Map();
    let seq = 0, total = 0, fromSwarm = 0, nextId = 0x4f21;
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
    const bySeq = s => { const i = s - recs[0].seq; return i >= 0 && i < recs.length ? recs[i] : null; };
    if (live) { // the excerpt in the page is the start of today's stream: stamp it as just written
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
    let rendered = 0;
    function rebuild() {
      els.clear();
      const keep = recs.slice(-DOM_CAP);
      track.replaceChildren(...keep.map(build));
      rendered = keep.length ? keep[keep.length - 1].seq : 0;
      markHead();
      if (sel !== null && !els.has(sel)) sel = null;
      if (sel !== null) els.get(sel).classList.add('is-sel'), els.get(sel).setAttribute('aria-selected', 'true');
      stop(sel !== null ? els.get(sel) : track.lastElementChild);
    }
    // a new record's hash resolves on its link, digit by digit, as the link forms (the chain below does the same)
    function roll(el, to, delay, dur = 420) {
      cancelAnimationFrame(el._roll);
      if (reduced) { el.textContent = to; return; }
      const start = performance.now() + delay;
      const step = now => {
        if (now >= start) {
          const p = Math.min(1, (now - start) / dur), n = Math.floor(p * to.length);
          el.textContent = to.slice(0, n) + Array.from({ length: to.length - n }, () => HEX[Math.random() * 16 | 0]).join('');
          if (p >= 1) { el.textContent = to; return; }
        }
        el._roll = requestAnimationFrame(step);
      };
      el._roll = requestAnimationFrame(step);
    }
    function landed(li) {
      li.classList.add('is-new'); setTimeout(() => li.classList.remove('is-new'), 1300);
      const tag = li.querySelector('.lt-tag'); if (tag) roll(tag, tag.textContent, 380);
    }
    // columns are sized so a whole number of records fills the view: no record is ever cut in half at rest
    const MIN_COL = live ? 136 : 122;
    function fit() {
      const cs = getComputedStyle(track), avail = view.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      if (avail <= 0) return;
      // a phone still shows three live records and two whole links; an excerpt keeps two wider columns, read in full
      const min = window.innerWidth < 600 ? (live ? 100 : 136) : MIN_COL;
      let n = Math.max(2, Math.floor(avail / min));
      if (!live) n = Math.min(n, Math.max(2, recs.length));
      root.style.setProperty('--lt-col', (Math.floor(avail / n * 10) / 10) + 'px');
    }
    function markHead() {
      track.querySelectorAll('.is-head').forEach(li => li.classList.remove('is-head'));
      if (track.lastElementChild) track.lastElementChild.classList.add('is-head');
    }
    let tabStop = null;
    function stop(li) { // roving tabindex: the list is one tab stop
      if (tabStop && tabStop !== li) tabStop.tabIndex = -1;
      tabStop = li || null; if (tabStop) tabStop.tabIndex = 0;
    }

    /* ---- following the newest record, browsing, inspecting ---- */
    let following = true, sel = null, unseen = 0, intentUntil = 0, playing = live && !reduced, visible = false;
    const maxScroll = () => view.scrollWidth - view.clientWidth;
    const atEnd = () => view.scrollLeft >= maxScroll() - 6;
    function toEnd(smooth) { view.scrollTo({ left: maxScroll(), behavior: smooth && !reduced ? 'smooth' : 'auto' }); }
    function reveal(li, smooth) { // horizontal only: never scroll the page under the reader
      const pad = 36, l = li.offsetLeft - pad, r = li.offsetLeft + li.offsetWidth + pad;
      let to = null;
      if (l < view.scrollLeft) to = l; else if (r > view.scrollLeft + view.clientWidth) to = r - view.clientWidth;
      if (to !== null) view.scrollTo({ left: to, behavior: smooth && !reduced ? 'smooth' : 'auto' });
    }
    function follow(smooth = true) {
      if (sel !== null && els.has(sel)) { const o = els.get(sel); o.classList.remove('is-sel'); o.setAttribute('aria-selected', 'false'); }
      sel = null; following = true; unseen = 0;
      stop(track.lastElementChild);
      toEnd(smooth); inspect(); state();
    }
    function select(li, focus) {
      if (!li || !els.has(+li.dataset.seq)) return;
      if (sel !== null && els.has(sel)) { const o = els.get(sel); o.classList.remove('is-sel'); o.setAttribute('aria-selected', 'false'); }
      sel = +li.dataset.seq; following = false;
      li.classList.add('is-sel'); li.setAttribute('aria-selected', 'true');
      stop(li);
      if (focus && document.activeElement !== li) li.focus({ preventScroll: true });
      reveal(li, true); inspect(); state();
    }
    track.addEventListener('click', e => { const li = e.target.closest('.lt-rec'); if (li) select(li, true); });
    track.addEventListener('focusin', e => { const li = e.target.closest('.lt-rec'); if (li && +li.dataset.seq !== sel) select(li, false); });
    track.addEventListener('keydown', e => {
      const cur = e.target.closest('.lt-rec'); if (!cur) return;
      const go = { ArrowLeft: cur.previousElementSibling, ArrowRight: cur.nextElementSibling, Home: track.firstElementChild, End: track.lastElementChild }[e.key];
      if (go !== undefined) { e.preventDefault(); if (go) select(go, true); return; }
      if (e.key === 'Escape') { e.preventDefault(); follow(); const b = [ui.play, ui.replay, ui.latest].find(x => x && !x.hidden); if (b) b.focus(); }
    });
    // only a person's own swipe, wheel or drag decides whether the view stops following the head
    const intent = () => { intentUntil = performance.now() + 900; };
    ['wheel', 'touchstart', 'pointerdown'].forEach(t => view.addEventListener(t, intent, { passive: true }));
    let edgeRaf = 0;
    view.addEventListener('scroll', () => {
      if (!edgeRaf) edgeRaf = requestAnimationFrame(() => { edgeRaf = 0; edges(); if (sel === null && !following) inspect(); else leader(); });
      if (performance.now() > intentUntil) return;
      if (atEnd()) { if (sel === null && !following) follow(false); }
      else if (following) { following = false; unseen = 0; state(); }
    }, { passive: true });
    function edges() {
      const m = maxScroll();
      root.classList.toggle('has-left', view.scrollLeft > 4);
      root.classList.toggle('has-right', view.scrollLeft < m - 4);
    }

    /* ---- the inspector: id, event, detail, and both hash links of one record ---- */
    function hexInto(el, hex) {
      // the first eight hex are the ones written on the links
      el.replaceChildren(node('b', null, hex.slice(0, 8)), document.createTextNode(grouped(hex).slice(8)));
    }
    // with nothing selected the inspector describes what the reader is looking at: the head while the view follows it,
    // otherwise the newest record wholly in view (on a phone the excerpt opens at its start, and so does the inspector)
    function inView() {
      const left = view.scrollLeft - 2, right = view.scrollLeft + view.clientWidth + 2;
      for (let li = track.lastElementChild; li; li = li.previousElementSibling) {
        if (li.offsetLeft >= left && li.offsetLeft + li.offsetWidth - 18 <= right) return bySeq(+li.dataset.seq);
      }
      return null;
    }
    let shown = '';
    function inspect() {
      if (!ui.insp || !recs.length) return;
      const r = (sel !== null && bySeq(sel)) || (!following && inView()) || bySeq(rendered) || recs[recs.length - 1];
      const key = `${r.seq}/${recs[recs.length - 1].seq}`;
      if (key === shown) { leader(); return; }
      shown = key;
      F.rec.textContent = `${r.id} · ${r.t}`;
      F.ev.textContent = r.ev; F.ev.className = 'lt-insp-ev' + tone(r.ev);
      F.d.textContent = r.d;
      if (srcRow) srcRow.hidden = r.src !== 'swarm';
      if (F.src && r.src === 'swarm') F.src.textContent = `The swarm above · proposal ${r.pid}${r.n > 1 ? ` + ${r.n - 1} more` : ''}${r.lane ? ' · ' + r.lane : ''}${r.followed ? ' · the proposal you followed' : ''}`;
      hexInto(F.prev, r.prev); hexInto(F.hash, r.hash);
      // real checks, not labels: the stored link equals the previous record's hash; this hash recomputes from the content
      const before = bySeq(r.seq - 1), after = bySeq(r.seq + 1);
      const linkOk = before ? before.hash === r.prev : r.prev === genesis || r.seq > 1;
      const selfOk = sha256(r.prev + '|' + body(r)) === r.hash;
      F.prevok.textContent = !linkOk ? '✗ does not match the record before' : before ? `✓ the hash of ${before.id}` : r.seq === 1 ? '✓ genesis of this ledger' : '✓ the hash of the record before';
      F.prevok.classList.toggle('is-bad', !linkOk);
      F.next.textContent = !selfOk ? '✗ does not recompute from this record' : after ? `✓ recomputes · stored as previous hash by ${after.id}` : live ? '✓ recomputes · awaiting the next record' : '✓ recomputes · last record of this excerpt';
      F.next.classList.toggle('is-bad', !selfOk);
      ui.insp.classList.toggle('is-swarm', r.src === 'swarm');
      leader();
    }
    function leader() {
      if (!ui.leader) return;
      const li = sel !== null ? els.get(sel) : null;
      if (!li || !ui.insp || ui.insp.hidden) { ui.leader.classList.remove('is-on'); return; }
      const n = li.querySelector('.lt-node').getBoundingClientRect(), v = view.getBoundingClientRect(), r = root.getBoundingClientRect(), i = ui.insp.getBoundingClientRect();
      const on = n.left >= v.left + 8 && n.right <= v.right - 8;
      ui.leader.style.setProperty('--x', (n.left + n.width / 2 - r.left - 0.5).toFixed(1) + 'px');
      ui.leader.style.setProperty('--y', (n.bottom - r.top + 3).toFixed(1) + 'px');
      ui.leader.style.setProperty('--h', Math.max(0, i.top - n.bottom - 3).toFixed(1) + 'px');
      ui.leader.classList.toggle('is-on', on);
    }

    /* ---- status line, controls, counters: all derived from state ---- */
    function state(text) {
      root.classList.toggle('is-inspecting', sel !== null);
      root.classList.toggle('is-following', following);
      root.classList.toggle('is-live', live && playing && following);
      root.classList.toggle('is-paused', live && !playing);
      if (ui.state) {
        const r = sel !== null ? bySeq(sel) : null;
        ui.state.textContent = text || (r ? `Inspecting ${r.id}` : live ? (playing ? (following ? 'Live · illustrative stream' : 'Illustrative stream · browsing') : 'Paused · illustrative stream') : stateIdle);
      }
      if (ui.play) { ui.play.hidden = !live; ui.play.textContent = playing ? 'Pause' : 'Play'; ui.play.setAttribute('aria-label', playing ? 'Pause the stream' : 'Play the stream'); }
      if (ui.latest) {
        ui.latest.hidden = following;
        if (ui.fresh) ui.fresh.textContent = unseen ? `+${unseen > 99 ? '99+' : unseen}` : '';
      }
      leader();
    }
    function counts() {
      if (ui.count) ui.count.textContent = total.toLocaleString('en-US');
      if (ui.swarm) { ui.swarm.hidden = !fromSwarm; ui.swarm.textContent = ` · ${fromSwarm.toLocaleString('en-US')} from the swarm above`; }
    }

    /* ---- appending: new columns land on the line, the link to them forms, the view glides to the head ---- */
    let lastFlush = 0, flushTimer = 0;
    function flush(animate) {
      lastFlush = performance.now();
      if (!recs.length || recs[recs.length - 1].seq === rendered) return;
      const fresh = recs.filter(r => r.seq > rendered);
      if (!rendered || fresh.length > 8 || !track.lastElementChild) { rebuild(); if (following) toEnd(false); }
      else {
        const was = track.lastElementChild;
        fresh.forEach((r, i) => { const li = build(r); if (animate && !reduced && i >= fresh.length - 2) landed(li); track.append(li); });
        if (animate && !reduced) { was.classList.add('is-linking'); setTimeout(() => was.classList.remove('is-linking'), 1400); }
        rendered = fresh[fresh.length - 1].seq;
        markHead(); trim();
        // a paused stream holds still: records still append (the ledger never drops one), the view stays where it is
        // and the Latest pill counts what arrived
        if (following && playing) { stop(track.lastElementChild); toEnd(animate); }
        else { following = false; unseen += fresh.length; }
      }
      edges(); counts(); if (following) inspect(); state();
    }
    function trim() { // keep the DOM small; compensate the scroll so nothing on screen moves
      let removed = 0;
      while (track.children.length > DOM_CAP) {
        const first = track.firstElementChild;
        if (first === document.activeElement || +first.dataset.seq === sel) break;
        removed += first.offsetWidth; els.delete(+first.dataset.seq); first.remove();
      }
      if (removed) view.scrollLeft = Math.max(0, view.scrollLeft - removed);
    }
    function soon() { // the swarm can settle many proposals a second: the line takes them in at a readable pace
      if (flushTimer) return;
      flushTimer = setTimeout(() => { flushTimer = 0; if (visible && !document.hidden) flush(true); }, Math.max(0, 420 - (performance.now() - lastFlush)));
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
    if (live && excerpt.length) { // the page's excerpt may end mid-lifecycle: the stream picks that lifecycle up where it stopped
      const last = excerpt[excerpt.length - 1], done = recs.filter(r => r.lc === last.lc).map(r => r.ev);
      cycles = recs.some(r => r.lc !== last.lc) ? 1 : 0;
      if (last.lc && !/^(SETTLED|REJECTED)$/.test(last.ev)) queue = lifecycle(last.lc).filter(s => !done.includes(s.ev));
    }
    const newId = () => '#' + (nextId++ & 0xffff).toString(16).padStart(4, '0');
    function tick() {
      timer = 0;
      if (!playing || !visible || document.hidden) return;
      if (!queue.length) queue = lifecycle();
      write(Object.assign({ id: newId(), t: clock(), src: 'gen' }, queue.shift()));
      flush(true);
      timer = setTimeout(tick, queue.length ? 950 + Math.random() * 500 : 1900 + Math.random() * 900);
    }
    function wake() {
      if (visible && !document.hidden) {
        flush(false);
        if (live && playing && !timer) timer = setTimeout(tick, 1100);
      } else { clearTimeout(timer); timer = 0; }
    }
    if (ui.play) ui.play.addEventListener('click', () => {
      playing = !playing;
      if (playing) { follow(); clearTimeout(timer); timer = setTimeout(tick, 350); } else { clearTimeout(timer); timer = 0; }
      state();
    });
    if (ui.latest) ui.latest.addEventListener('click', () => follow());

    /* ---- live: proposals settled by the swarm become records ---- */
    let inbox = [], draining = false;
    if (live) document.addEventListener('oxa:settled', e => {
      if (!e || !e.detail) return;
      inbox.push(e.detail);
      if (!draining) { draining = true; queueMicrotask(drain); } // never inside the swarm's own frame
    });
    function drain() {
      draining = false;
      const batch = inbox; inbox = [];
      batch.forEach(d => {
        const pid = typeof d.id === 'number' ? 'P-' + d.id : clean(d.id || '') || '—';
        const lane = d.lane == null || d.lane === '' ? '' : 'lane ' + (typeof d.lane === 'number' ? (Number.isInteger(d.lane) ? d.lane : d.lane.toFixed(2)) : clean(d.lane));
        // the swarm may announce several settlements at once (detail.count): one record says so, ids are never invented
        const n = Math.min(9999, Math.max(1, Math.floor(Number(d.count)) || 1)), followed = d.followed === true;
        const r = write({ id: newId(), t: stamp(d.ts), ev: 'SETTLED', lc: followed ? 'Followed' : 'Swarm',
          sub: n > 1 ? `${pid} +${n - 1} more${lane ? ' · ' + lane : ''}` : `proposal ${pid}${lane ? ' · ' + lane : ''}`,
          d: n > 1 ? `${pid} and ${n - 1} more settled in the swarm above · chained here` : `proposal ${pid} settled in the swarm above · chained here`,
          src: 'swarm', pid, lane, n, followed });
        fromSwarm++;
        document.dispatchEvent(new CustomEvent('oxa:recorded', { detail: { id: d.id, record: r.id, hash: r.hash, seq: r.seq } }));
      });
      counts();
      if (visible && !document.hidden) soon();
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
    const stateIdle = live ? '' : ok0 === n0 ? `Chain ✓ · ${n0} records verify` : `${n0 - ok0} of ${n0} records fail verification`;
    let replaying = 0;
    function replay() {
      clearTimeout(replaying);
      sweep.forEach(clearTimeout); sweep = []; cancelAnimationFrame(glideRaf);
      const all = recs.slice();
      if (!all.length) return;
      if (sel !== null) follow(false);
      following = true; // the view and the inspector follow the record being written
      els.clear(); track.replaceChildren(); rendered = 0;
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
      if (sel !== null) { const o = els.get(sel); if (o) { o.classList.remove('is-sel'); o.setAttribute('aria-selected', 'false'); } sel = null; }
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

    function whole() { // the excerpt, all of it, with its long waits marked on the links
      rebuild();
      Array.from(track.children).forEach((li, i, all) => { if (i) gapMark(all[i - 1], bySeq(+all[i - 1].dataset.seq), bySeq(+li.dataset.seq)); });
    }

    /* ---- start ---- */
    fit();
    if (live) rebuild(); else { following = false; whole(); }
    if (ui.insp) ui.insp.hidden = false;
    root.classList.add('lt-ready');
    if (live) {
      root.classList.add('is-stream');
      requestAnimationFrame(() => toEnd(false));
    }
    edges(); counts(); inspect(); state();
    if ('IntersectionObserver' in window) new IntersectionObserver(([en]) => { visible = en.isIntersecting; wake(); }, { rootMargin: '80px 0px' }).observe(root);
    else { visible = true; wake(); }
    document.addEventListener('visibilitychange', wake);
    let fitRaf = 0;
    window.addEventListener('resize', () => {
      if (fitRaf) return;
      fitRaf = requestAnimationFrame(() => { fitRaf = 0; fit(); if (following) toEnd(false); else if (sel !== null && els.has(sel)) reveal(els.get(sel), false); edges(); leader(); });
    });
    motionQuery.addEventListener('change', e => { reduced = e.matches; if (reduced && playing) { playing = false; clearTimeout(timer); timer = 0; state(); } });
  }
})();
