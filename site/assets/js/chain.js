/* OpenEXA — the chain, for real.
   Eight records on one vertical hairline. Each is hashed with SHA-256 over (its content + the previous hash), and the
   link below it carries that hash down to the next record, which stores it. Edit any field and the link out of that
   record snaps: it and every record after it turn red, one after another, because each stored previous-hash no longer
   matches. "Restore" heals the chain from the top. The records come from the page (readable without JavaScript).
   The cascade is walked here, one record every 110 ms, and the status line counts exactly the records that are red on
   screen; the sentence it ends on is announced once, to a separate live region.
   The point: nothing on the ledger can be changed quietly. */
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
  // the actions' container shows only when it holds a button (no selector has to ask the document)
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

  // one row per record: node on the line, the record, and below it the link that carries its hash to the next one
  const rows = RECORDS.map((r, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<i class="chain-node" aria-hidden="true"></i><span class="i">${pad(i + 1)}</span><span class="who"></span>` +
      `<b class="ev" spellcheck="false" role="textbox" aria-label="Event for record ${i + 1}" aria-multiline="false"></b>` +
      `<span class="what" spellcheck="false" role="textbox" aria-label="Detail for record ${i + 1}" aria-multiline="false"></span>` +
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
    // what each link stored when the chain was written: shown struck through beside the new hash once that link snaps
    rows.forEach((li, i) => { li.querySelector('.chain-was').textContent = stored[i][1].slice(0, 8); });
    paint(c, -1, true);
    rows.forEach(li => li.querySelectorAll('.ev, .what').forEach(field => field.setAttribute('contenteditable', 'plaintext-only')));
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

  // hex digits roll to their new value, in step with the cascade: one shared frame loop for every rolling link
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
    if (!n) return 'Chain intact · every record points at the one before it';
    if (broken < 0) return `Restoring · ${plural(n, 'record still fails', 'records still fail')}`;
    const first = rows.findIndex(li => li.classList.contains('is-broken'));
    return `Chain broken at record ${pad(first + 1)} · ${plural(n, 'record no longer verifies', 'records no longer verify')}`;
  }
  let said = '';
  function settled(broken, quiet) { // the cascade has reached the last record: the final sentence, announced once
    const s = line(broken);
    setStatus(s);
    root.classList.toggle('is-broken', red() > 0);
    if (!quiet && sayEl && s !== said) sayEl.textContent = said = s;
    if (quiet) said = s;
  }

  const STEP = 110; // ms between one record turning and the next: the cascade (and the healing) travel down the line
  let cascade = [];
  function paint(c, broken, quiet) {
    cascade.forEach(clearTimeout); cascade = [];
    const steps = [];
    rows.forEach((li, i) => {
      // "edited" marks every record whose content differs from what was written, not only the first one
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
          // a record that stops verifying flares red as the break reaches it; one that verifies again flares green
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
  let t = 0;
  list.addEventListener('input', () => { revision++; clearTimeout(t); t = setTimeout(() => verify().catch(reportCryptoError), 120); });
  list.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } });
  // the one-tap version for anyone who would rather not type: change the council's decision on record 03
  if (tryIt) tryIt.addEventListener('click', () => {
    const ev = rows[Math.min(2, rows.length - 1)].querySelector('.ev');
    ev.textContent = ev.textContent.trim() === 'REJECTED' ? 'REVOKED' : 'REJECTED';
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
