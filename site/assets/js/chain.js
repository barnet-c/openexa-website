/* OpenEXA — the chain, for real (Home §06). Eight records from the page, each hashed with SHA-256 over its content and
   the hash before it. Edit a field: that record and every one after it turn red in a cascade (110 ms a record), the
   status names the record where the chain broke (Trust's words; hc2) and its last sentence is announced once. Restore
   heals from the top. */
(function () {
  'use strict';
  const root = document.querySelector('[data-chain]');
  if (!root) return;
  const list = root.querySelector('[data-chain-list]'), status = root.querySelector('[data-chain-status]');
  const restore = root.querySelector('[data-chain-restore]'), tryIt = root.querySelector('[data-chain-try]');
  const acts = root.querySelector('.chain-acts'), foot = root.querySelector('.chain-foot'), sayEl = root.querySelector('[data-chain-say]');
  const fallback = root.querySelector('[data-chain-fallback]');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!list || !status) return;
  // one Text node per element, its data rewritten in place
  function textOf(el) {
    let t = el.lastChild;
    if (t && t.nodeType === 3 && (t === el.firstChild || el === status)) return t;
    const s = el === status ? '' : el.textContent;
    if (el !== status) el.textContent = '';
    t = document.createTextNode(s); el.append(t);
    return t;
  }
  const statusText = textOf(status);
  const setStatus = s => { if (statusText.data !== s) statusText.data = s; };
  // the actions show only when they hold a button
  const syncActs = () => { if (acts) acts.hidden = (!tryIt || tryIt.hidden) && (!restore || restore.hidden); };
  if (!window.crypto || !crypto.subtle) {
    setStatus('Interactive verification is unavailable');
    if (fallback) fallback.textContent = 'This study needs a browser with WebCrypto on HTTPS or localhost. No records have been verified.';
    console.warn('OpenEXA chain study: WebCrypto is unavailable on this origin.');
    return;
  }
  const read = (li, s) => { const n = li.querySelector(s); return n ? n.textContent.trim() : ''; };
  let RECORDS = Array.from(list.children).map(li => [read(li, '.who'), read(li, '.ev'), read(li, '.what')]).filter(r => r[0] && r[1]);
  if (RECORDS.length < 2) RECORDS = [
    ['A-0412', 'PROPOSED', 'lifecycle L-01 · next step'], ['A-0412', 'VALIDATED', 'schema ok · inputs complete'],
    ['COUNCIL', 'APPROVED', 'policy v7 · scoped action'], ['A-0412', 'SUBMITTED', 'registry tool · key 9f3c'],
    ['A-0412', 'RECEIVED', 'source receipt attached'], ['A-0412', 'EXECUTED', 'action complete · result stored'],
    ['A-0891', 'RECONCILED', 'source receipt ↔ internal record'], ['A-0412', 'SETTLED', 'confirmed · appended · chained']];
  const ORIGINAL = RECORDS.map(r => r.slice());
  const enc = new TextEncoder();
  const hex = (buf) => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  async function sha(s) { return hex(await crypto.subtle.digest('SHA-256', enc.encode(s))); }
  const pad = n => String(n).padStart(2, '0');

  // a row per record: node, record, and the link carrying its hash to the next
  const rows = RECORDS.map((r, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<i class="chain-node" aria-hidden="true"></i><span class="i" role="button" tabindex="${i ? -1 : 0}" aria-label="Edit record ${pad(i + 1)}" aria-describedby="chain-how-i">${pad(i + 1)}</span><span class="who"></span>` +
      `<b class="ev" tabindex="-1" spellcheck="false" role="textbox" aria-label="Event for record ${i + 1}" aria-multiline="false"></b>` +
      `<span class="what" tabindex="-1" spellcheck="false" role="textbox" aria-label="Detail for record ${i + 1}" aria-multiline="false"></span>` +
      `<span class="chain-flag" hidden>edited</span><i class="chain-seg" aria-hidden="true"></i>` +
      `<span class="chain-link"><span class="sr-only">Hash of record ${i + 1}: </span><s><span class="sr-only">stored </span><span class="chain-was"></span><span class="sr-only">, now </span></s><b></b></span>`;
    li.querySelector('.who').textContent = r[0];
    li.querySelector('.ev').textContent = r[1];
    li.querySelector('.what').textContent = r[2];
    return li;
  });
  const links = rows.map(li => li.querySelector('.chain-link b'));
  list.replaceChildren(...rows);
  if (fallback) fallback.remove();
  if (foot) foot.classList.remove('is-static');
  root.classList.add('chain-ready');
  // its one loop (the broken status dot) runs only while the chain is on screen
  if ('IntersectionObserver' in window) new IntersectionObserver(([en]) => root.classList.toggle('is-away', !en.isIntersecting)).observe(root);
  const stored = []; // the chain as it was written: [prevHash, hash] per record
  const want = []; // the hash each link is showing, or rolling towards
  let busy = false, pending = false, revision = 0;

  async function compute() {
    const snapshot = rows.map(li => `${li.querySelector('.who').textContent}|${li.querySelector('.ev').textContent}|${li.querySelector('.what').textContent}`);
    let prev = '0'.repeat(64);
    const out = [];
    for (let i = 0; i < rows.length; i++) {
      const h = await sha(prev + '|' + snapshot[i]);
      out.push([prev, h]); prev = h;
    }
    return out;
  }
  async function write() {
    const c = await compute();
    c.forEach(p => stored.push(p));
    // the stored hash, struck beside the new one once a link snaps
    rows.forEach((li, i) => { li.querySelector('.chain-was').textContent = stored[i][1].slice(0, 8); });
    paint(c, -1, true);
    // the fields become editable as the chain nears the screen, or on a first touch or focus inside it: each set lays
    // out the chain, which on Home sits far below the overture (a4, home's request: the phone's second second)
    let editable = false;
    const arm = () => { if (editable) return; editable = true; rows.forEach(li => li.querySelectorAll('.ev, .what').forEach(field => field.setAttribute('contenteditable', 'plaintext-only'))); };
    if ('IntersectionObserver' in window) { const io = new IntersectionObserver(es => { if (es.some(en => en.isIntersecting)) { io.disconnect(); arm(); } }, { rootMargin: '100% 0px' }); io.observe(root); } else arm();
    root.addEventListener('pointerdown', arm, { once: true, capture: true }); root.addEventListener('focusin', arm, { once: true, capture: true });
    if (tryIt) tryIt.hidden = false;
    syncActs();
  }
  async function verify() {
    pending = true;
    if (busy) return;
    busy = true;
    try {
      do {
        pending = false;
        const version = revision;
        const c = await compute();
        if (version !== revision) { pending = true; continue; }
        paint(c, c.findIndex((record, i) => record[1] !== stored[i][1]));
      } while (pending);
    } finally {
      busy = false;
    }
  }
  function reportCryptoError(error) {
    setStatus('Verification failed. Reload the page to retry.');
    console.error('OpenEXA chain study could not compute the record hashes.', error);
  }

  // hex digits roll to their new value with the cascade (one frame loop)
  const HEX = '0123456789abcdef', rolls = new Map();
  let rollRaf = 0;
  function roll(el, to, delay) {
    const t = textOf(el);
    if (motion.matches || !t.data) { rolls.delete(t); t.data = to; return; }
    rolls.set(t, { to, start: performance.now() + delay, dur: 380 });
    if (!rollRaf) rollRaf = requestAnimationFrame(frame);
  }
  function frame(now) {
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
    if (rolls.size) rollRaf = requestAnimationFrame(frame);
  }

  // the status line reads what is red on screen right now
  const red = () => rows.reduce((n, li) => n + (li.classList.contains('is-broken') ? 1 : 0), 0);
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  function line(broken) {
    const n = red();
    if (!n) return 'Chain intact'; // a2 (UX juror, VOICE 5.10): the label only; the lede says what a chain is
    if (broken < 0) return `Restoring · ${plural(n, 'record still fails', 'records still fail')}`;
    // hc2: one vocabulary with Trust's replay: 'Chain intact' or 'Chain broken at <record> · every later link fails'
    const first = rows.findIndex(li => li.classList.contains('is-broken'));
    return `Chain broken at record ${pad(first + 1)}${first < rows.length - 1 ? ' · every later link fails' : ''}`;
  }
  let said = '';
  function settled(broken, quiet) { // the last record reached: the final sentence, announced once
    const s = line(broken);
    setStatus(s);
    root.classList.toggle('is-broken', red() > 0);
    if (!quiet && sayEl && s !== said) sayEl.textContent = said = s;
    if (quiet) said = s;
  }

  const STEP = 110; // ms from one record to the next, breaking or healing
  let cascade = [];
  function paint(c, broken, quiet) {
    cascade.forEach(clearTimeout); cascade = [];
    const steps = [];
    rows.forEach((li, i) => {
      // "edited": every record that differs from what was written
      const edited = li.querySelector('.ev').textContent !== ORIGINAL[i][1] || li.querySelector('.what').textContent !== ORIGINAL[i][2];
      li.classList.toggle('is-edited', edited);
      li.querySelector('.chain-flag').hidden = !edited;
      const bad = broken >= 0 && i >= broken, h = c[i][1].slice(0, 8);
      if (li.classList.contains('is-broken') !== bad || want[i] !== h) steps.push({ i, bad, h });
    });
    const now = quiet || motion.matches;
    steps.forEach((s, k) => {
      const run = () => {
        const li = rows[s.i];
        if (li.classList.contains('is-broken') !== s.bad) {
          // red as the break reaches it; green as it verifies again
          li.classList.toggle('is-broken', s.bad);
          li.classList.remove('is-heal');
          if (!s.bad && !now) {
            void li.offsetWidth; li.classList.add('is-heal');
            clearTimeout(li._heal); li._heal = setTimeout(() => li.classList.remove('is-heal'), 1100);
          }
        }
        if (want[s.i] !== s.h) { want[s.i] = s.h; roll(links[s.i], s.h, s.bad ? STEP / 2 : 0); }
        if (k === steps.length - 1) settled(broken, quiet);
        else { setStatus(line(broken)); root.classList.toggle('is-broken', red() > 0); }
      };
      if (now || !k) run(); else cascade.push(setTimeout(run, k * STEP));
    });
    if (!steps.length) settled(broken, quiet);
    const intact = broken < 0;
    if (restore) restore.hidden = intact;
    if (tryIt) tryIt.hidden = !intact || !stored.length;
    syncActs();
  }
  // r4 a11y: one Tab stop, the record's number (roving; Enter edits). A record's fields are Tab stops only while in use
  const idx = rows.map(li => li.querySelector('.i')), F = li => li.querySelectorAll('.ev, .what');
  [['i', 'Enter types over its detail; Up and Down choose another record.'], ['f', 'Type to change this record: it and every record after it stop verifying. Enter or Escape goes back to the record.']].forEach(([k, s]) => {
    const e = document.createElement('span'); e.id = 'chain-how-' + k; e.hidden = true; e.textContent = s; root.append(e);
  });
  let rove = 0, armed = -1;
  const point = j => { idx[rove].tabIndex = -1; idx[rove = j].tabIndex = 0; };
  function arm(j) {
    if (armed === j) return;
    if (armed >= 0) F(rows[armed]).forEach(f => { f.tabIndex = -1; f.removeAttribute('aria-describedby'); });
    if ((armed = j) < 0) return;
    point(j);
    const fresh = !rows[j].classList.contains('is-edited');
    F(rows[j]).forEach(f => { f.tabIndex = 0; if (fresh) f.setAttribute('aria-describedby', 'chain-how-f'); });
  }
  function edit(j) {
    const f = rows[j].querySelector('.what');
    if (!f.isContentEditable) return;
    arm(j); f.focus();
    try { const r = document.createRange(), s = getSelection(); r.selectNodeContents(f); s.removeAllRanges(); s.addRange(r); } catch (err) { /* the caret stays where focus put it */ }
  }
  // a1-dev: the whole record row is the press target (the number alone was 15 x 20 px on a phone); a press inside a
  // field still puts the caret where it lands
  list.addEventListener('click', e => { const j = rows.indexOf(e.target.closest('li')); if (j >= 0 && !e.target.closest('[contenteditable]')) edit(j); });
  list.addEventListener('focusin', e => { const f = e.target.closest('.ev, .what'); if (f && f.isContentEditable) arm(rows.indexOf(f.parentNode)); });
  list.addEventListener('focusout', e => { const to = e.relatedTarget; if (armed >= 0 && !(to && to.parentNode === rows[armed] && to.matches('.ev, .what'))) arm(-1); });
  let t = 0;
  list.addEventListener('input', () => { revision++; clearTimeout(t); t = setTimeout(() => verify().catch(reportCryptoError), 120); });
  list.addEventListener('keydown', e => {
    const j = rows.indexOf(e.target.closest('li')), k = e.key;
    if (j < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.target !== idx[j]) { if (k === 'Enter' || k === 'Escape') { e.preventDefault(); getSelection().removeAllRanges(); idx[j].focus(); } return; }
    if (k === 'Enter' || k === ' ') { e.preventDefault(); edit(j); return; }
    const vis = rows.map((li, n) => n).filter(n => rows[n].offsetParent), v = vis.indexOf(j); // Home folds 05-08 on phones
    const to = /^Arrow(Down|Right)$/.test(k) ? vis[v + 1] : /^Arrow(Up|Left)$/.test(k) ? vis[v - 1] : k === 'Home' ? vis[0] : k === 'End' ? vis[vis.length - 1] : -1;
    if (to === -1) return;
    e.preventDefault();
    if (to !== undefined) { point(to); idx[to].focus(); }
  });
  // the one-tap version: change the council's decision on record 03
  if (tryIt) tryIt.addEventListener('click', () => {
    const ev = rows[Math.min(2, rows.length - 1)].querySelector('.ev');
    ev.textContent = ev.textContent.trim() === 'REJECTED' ? 'REVOKED' : 'REJECTED';
    point(Math.min(2, rows.length - 1)); // Tab from Restore reaches record 03
    revision++; clearTimeout(t);
    verify().then(() => { if (restore && !restore.hidden) restore.focus(); }).catch(reportCryptoError);
  });
  if (restore) restore.addEventListener('click', () => {
    revision++;
    clearTimeout(t);
    rows.forEach((li, i) => { li.querySelector('.ev').textContent = ORIGINAL[i][1]; li.querySelector('.what').textContent = ORIGINAL[i][2]; });
    verify().then(() => { if (tryIt && !tryIt.hidden) tryIt.focus(); }).catch(reportCryptoError);
  });
  write().catch(reportCryptoError);
})();
