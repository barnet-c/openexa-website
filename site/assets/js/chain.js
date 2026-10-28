/* OpenEXA — the chain, for real.
   Eight records on one vertical hairline. Each is hashed with SHA-256 over (its content + the previous hash), and the
   link below it carries that hash down to the next record, which stores it. Edit any field and the link out of that
   record snaps: it and every record after it turn red, one after another, because each stored previous-hash no longer
   matches. "Restore" heals the chain from the top. The records come from the page (readable without JavaScript).
   The point: nothing on the ledger can be changed quietly. */
(function () {
  'use strict';
  const root = document.querySelector('[data-chain]');
  if (!root) return;
  const list = root.querySelector('[data-chain-list]'), status = root.querySelector('[data-chain-status]');
  const restore = root.querySelector('[data-chain-restore]'), tryIt = root.querySelector('[data-chain-try]');
  const fallback = root.querySelector('[data-chain-fallback]');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (!list || !status) return;
  if (!window.crypto || !crypto.subtle) {
    status.textContent = 'Interactive verification is unavailable';
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
  list.replaceChildren(...rows);
  if (fallback) fallback.remove();
  root.classList.add('chain-ready');
  const stored = []; // the chain as it was written: [prevHash, hash] per record
  let busy = false, pending = false, revision = 0, lastBroken = -1;

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
    paint(c, -1);
    rows.forEach(li => li.querySelectorAll('.ev, .what').forEach(field => field.setAttribute('contenteditable', 'plaintext-only')));
    if (tryIt) tryIt.hidden = false;
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
    status.textContent = 'Verification failed. Reload the page to retry.';
    console.error('OpenEXA chain study could not compute the record hashes.', error);
  }

  // hex digits roll to their new value, in step with the cascade
  const HEX = '0123456789abcdef';
  function roll(el, to, delay) {
    cancelAnimationFrame(el._roll);
    if (el.textContent === to) return;
    if (motion.matches || !el.textContent) { el.textContent = to; return; }
    const from = el.textContent, start = performance.now() + delay, dur = 380;
    const step = now => {
      if (now < start) { el.textContent = from; el._roll = requestAnimationFrame(step); return; }
      const p = Math.min(1, (now - start) / dur), n = Math.floor(p * to.length);
      el.textContent = to.slice(0, n) + Array.from({ length: to.length - n }, () => HEX[Math.random() * 16 | 0]).join('');
      if (p < 1) el._roll = requestAnimationFrame(step); else el.textContent = to;
    };
    el._roll = requestAnimationFrame(step);
  }

  const STEP = 110; // ms between one record turning and the next: the cascade (and the healing) travel down the line
  function paint(c, broken) {
    const was = lastBroken;
    rows.forEach((li, i) => {
      const bad = broken >= 0 && i >= broken;
      const k = bad ? i - broken : was >= 0 && i >= was ? i - was : 0;
      // "edited" marks every record whose content differs from what was written, not only the first one
      const edited = li.querySelector('.ev').textContent !== ORIGINAL[i][1] || li.querySelector('.what').textContent !== ORIGINAL[i][2];
      li.style.setProperty('--k', k);
      // a record that stops verifying flares red as the break reaches it; one that verifies again flares green
      const heals = !bad && li.classList.contains('is-broken');
      li.classList.toggle('is-broken', bad);
      if (heals) {
        li.classList.remove('is-heal'); void li.offsetWidth; li.classList.add('is-heal');
        clearTimeout(li._heal); li._heal = setTimeout(() => li.classList.remove('is-heal'), k * STEP + 1100);
      } else if (bad) li.classList.remove('is-heal');
      li.classList.toggle('is-edited', edited);
      li.querySelector('.chain-flag').hidden = !edited;
      roll(li.querySelector('.chain-link b'), c[i][1].slice(0, 8), k * STEP + (bad ? STEP / 2 : 0));
    });
    lastBroken = broken;
    const intact = broken < 0;
    root.classList.toggle('is-broken', !intact);
    status.innerHTML = intact ? '<i></i>Chain intact · every record points at the one before it' : `<i></i>Chain broken at record ${pad(broken + 1)} · ${rows.length - broken} record${rows.length - broken > 1 ? 's' : ''} no longer verify`;
    if (restore) restore.hidden = intact;
    if (tryIt) tryIt.hidden = !intact || !stored.length;
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
