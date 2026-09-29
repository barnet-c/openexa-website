/* OpenEXA — the chain, for real.
   Eight records, each hashed with SHA-256 over (its content + the previous hash). Edit any field and every record after
   it turns red, because its stored previous-hash no longer matches. Press "restore" and the chain heals.
   The point: nothing on the ledger can be changed quietly. */
(function () {
  'use strict';
  const root = document.querySelector('[data-chain]');
  if (!root) return;
  const list = root.querySelector('[data-chain-list]'), status = root.querySelector('[data-chain-status]'), restore = root.querySelector('[data-chain-restore]');
  if (!window.crypto || !crypto.subtle) {
    status.textContent = 'Interactive verification is unavailable';
    list.textContent = 'This study needs a browser with WebCrypto on HTTPS or localhost. No records have been verified.';
    console.warn('OpenEXA chain study: WebCrypto is unavailable on this origin.');
    return;
  }
  const RECORDS = [
    ['A-0412', 'PROPOSED', 'lifecycle L-01 · next step'],
    ['A-0412', 'VALIDATED', 'schema ok · inputs complete'],
    ['COUNCIL', 'APPROVED', 'policy v7 · scoped action'],
    ['A-0412', 'SUBMITTED', 'registry tool · key 9f3c'],
    ['A-0412', 'RECEIVED', 'source receipt attached'],
    ['A-0412', 'EXECUTED', 'action complete · result stored'],
    ['A-0891', 'RECONCILED', 'source receipt ↔ internal record'],
    ['A-0412', 'SETTLED', 'confirmed · appended · chained'],
  ];
  const ORIGINAL = RECORDS.map(r => r.slice());
  const enc = new TextEncoder();
  const hex = (buf) => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  async function sha(s) { return hex(await crypto.subtle.digest('SHA-256', enc.encode(s))); }

  list.replaceChildren();
  const rows = RECORDS.map((r, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<span class="i">${String(i + 1).padStart(2, '0')}</span><span class="who">${r[0]}</span><b class="ev" spellcheck="false" role="textbox" aria-label="Event for record ${i + 1}" aria-multiline="false">${r[1]}</b><span class="what" spellcheck="false" role="textbox" aria-label="Detail for record ${i + 1}" aria-multiline="false">${r[2]}</span><span class="prev" title="previous hash"></span><span class="hash" title="this record's hash"></span>`;
    list.appendChild(li);
    return li;
  });
  const stored = []; // the chain as it was written: [prevHash, hash] per record
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
    paint(c, true);
    rows.forEach(li => li.querySelectorAll('.ev, .what').forEach(field => field.setAttribute('contenteditable', 'plaintext-only')));
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
        const broken = c.findIndex((record, i) => record[1] !== stored[i][1]);
        paint(c, broken < 0, broken);
      } while (pending);
    } finally {
      busy = false;
    }
  }
  function reportCryptoError(error) {
    status.textContent = 'Verification failed. Reload the page to retry.';
    console.error('OpenEXA chain study could not compute the record hashes.', error);
  }
  function paint(c, intact, broken = -1) {
    rows.forEach((li, i) => {
      li.querySelector('.prev').textContent = stored[i] ? stored[i][0].slice(0, 8) : '';
      const h = li.querySelector('.hash'), bad = broken >= 0 && i >= broken;
      h.innerHTML = bad ? `<s>${stored[i][1].slice(0, 8)}</s> ${c[i][1].slice(0, 8)}` : c[i][1].slice(0, 8);
      li.classList.toggle('is-broken', bad);
      li.classList.toggle('is-edited', broken === i);
    });
    root.classList.toggle('is-broken', !intact);
    if (status) status.innerHTML = intact ? '<i></i>Chain intact · every record points at the one before it' : `<i></i>Chain broken at record ${String(broken + 1).padStart(2, '0')} · ${rows.length - broken} record${rows.length - broken > 1 ? 's' : ''} no longer verify`;
    if (restore) restore.hidden = intact;
  }
  let t = 0;
  list.addEventListener('input', () => { revision++; clearTimeout(t); t = setTimeout(() => verify().catch(reportCryptoError), 120); });
  list.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } });
  if (restore) restore.addEventListener('click', () => {
    revision++;
    clearTimeout(t);
    rows.forEach((li, i) => { li.querySelector('.ev').textContent = ORIGINAL[i][1]; li.querySelector('.what').textContent = ORIGINAL[i][2]; });
    verify().catch(reportCryptoError);
  });
  write().catch(reportCryptoError);
})();
