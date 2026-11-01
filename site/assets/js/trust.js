/* OpenEXA: Trust (trust.html only). The ledger replay's own controls, kept out of ledger.js so Home's stream never
   downloads them (v2x r1, perf). ledger.js draws the chain and the inspector; on a [data-ledger="replay"] root it exposes
   root.oxaTrace (the engine's parts) and X (hooks it calls). This file, loaded after ledger.js:
   - Replay: the excerpt writes itself again at its own rhythm; a long wait between two records is marked on the link.
   - Verify the chain: every hash is recomputed from its record and the hash recomputed before it, and compared with the
     hash it was sealed with. The walk lights each link that holds; from the first record that does not, every record
     turns red and stays red ('Chain broken at #4f1b · 8 of 9 records no longer verify').
   - Change a record: the selected record's event and detail can be typed over in the inspector (the rejection when
     nothing is selected); Restore puts the excerpt back.
   - Sealed vs now: a record being typed over shows, beside the hash it was sealed with, the hash it produces now
     (khaki); once Verify fails it, the sealed hash is struck and the new one is red. Same SHA-256 (ledger.js's), same
     recipe (genesis = sha256('genesis|' + first id); hash = sha256(previous hash + '|' + id|time|event|sub|detail)).
   - "Try to change the past" (a[data-lt-go] in the hero) starts the edit; without JS it is a plain link to #ledger.
   The records are illustrative; every hash is real, computed here in the browser. */
(function () {
  'use strict';
  const root = document.querySelector('[data-ledger="replay"]');
  const T = root && root.oxaTrace;
  if (!T) return;
  const { X, recs, els, track, view, ui, F } = T;
  const canEdit = !!ui.edit && !!F.ev && !!F.d, cue = root.querySelector('[data-lt-enter]');

  /* ---- the records as written, and what the visitor has done to them since ---- */
  const ORIG = new Map();
  const orig = () => { if (!ORIG.size && recs.length) recs.forEach(r => ORIG.set(r.seq, { ev: r.ev, sub: r.sub, d: r.d, lc: r.lc })); return ORIG; };
  let brokenAt = -1, auditKey = '', auditRes = [];
  X.v = 0; X.dirty = false;
  const isEdited = r => { const o = orig().get(r.seq); return !!o && (o.ev !== r.ev || o.d !== r.d || o.sub !== r.sub); };
  const anyEdited = () => recs.some(isEdited);
  // the chain as it reads now: every hash recomputed from its record and the hash recomputed before it. A record
  // verifies while that equals the hash it was sealed with, which the next record stores as its previous hash.
  function audit() {
    const key = X.v + ':' + recs.length;
    if (key === auditKey) return auditRes;
    let p = recs.length ? recs[0].prev : '';
    auditRes = recs.map(r => { const now = T.sha256(p + '|' + T.body(r)), linked = r.prev === p; p = now; return { linked, now, ok: linked && now === r.hash }; });
    auditKey = key;
    return auditRes;
  }
  const at = r => audit()[r.seq - recs[0].seq];
  const verified = () => audit().reduce((n, a) => n + (a.ok ? 1 : 0), 0);
  function setIdle() {
    const n = recs.length, ok = verified();
    T.idle = brokenAt >= 0 && recs[brokenAt] ? `Chain broken at ${recs[brokenAt].id} · ${n - ok} of ${n} records no longer verify`
      : ok === n ? `Chain ✓ · ${n} records verify` : `${n - ok} of ${n} records fail verification`;
  }
  let said = '';
  const say = t => { if (ui.say && t && t !== said) ui.say.textContent = said = t; };

  /* ---- sealed vs now: the hash a record produces now, on its link beside the one it was sealed with ---- */
  function nowTag(li, a) {
    const line = li.querySelector('.lt-line');
    if (!line) return;
    let el = line.querySelector('.lt-now');
    if (!a) { if (el) el.remove(); return; }
    if (!el) { el = T.node('span', 'lt-now'); line.append(el); }
    T.put(el, a.now.slice(0, 8));
  }
  function nows() { // every column that is edited or broken shows what it produces now; any other shows only its seal
    Array.from(track.children).forEach(li => {
      const r = T.bySeq(+li.dataset.seq);
      nowTag(li, r && X.v && (li.classList.contains('is-edited') || li.classList.contains('is-broken')) ? at(r) : null);
    });
  }
  function unbreak() { // a verdict holds only for the records it was given on
    Array.from(track.querySelectorAll('.is-broken')).forEach(li => li.classList.remove('is-broken'));
    T.flag('is-broken', false);
    nows();
  }

  /* ---- replay: the excerpt writes itself again, at its own rhythm ---- */
  const secs = t => { const m = /(\d+):(\d+):(\d+)(?:\.(\d+))?/.exec(t || ''); return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] + +('0.' + (m[4] || '0')) : 0; };
  function gapMark(li, a, b) { // a long wait between two records is drawn on the link that spans it
    const s = secs(b.t) - secs(a.t);
    if (!li || s < 3600) return;
    const line = li.querySelector('.lt-line');
    if (line && !line.querySelector('.lt-gap')) line.append(T.node('span', 'lt-gap', `+${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m`));
  }
  function whole() { // the excerpt, all of it, with its long waits marked on the links
    T.rebuild();
    Array.from(track.children).forEach((li, i, all) => { if (i) gapMark(all[i - 1], T.bySeq(+all[i - 1].dataset.seq), T.bySeq(+li.dataset.seq)); });
  }
  let replaying = 0, glideRaf = 0, sweep = [];
  function replay() {
    clearTimeout(replaying);
    sweep.forEach(clearTimeout); sweep = []; cancelAnimationFrame(glideRaf);
    armed = null; pending = false;
    if (canEdit) { brokenAt = -1; X.dirty = anyEdited(); unbreak(); setIdle(); }
    const all = recs.slice();
    if (!all.length) return;
    if (T.sel !== null) T.follow(false);
    T.following = true; // the view and the inspector follow the record being written
    els.clear(); track.replaceChildren(); T.rendered = 0; T.forget();
    let i = 0;
    const next = () => {
      const r = all[i++];
      const was = track.lastElementChild, li = T.build(r);
      if (!T.reduced) T.landed(li);
      track.append(li); T.rendered = r.seq; T.markHead();
      if (was) { gapMark(was, all[i - 2], r); if (!T.reduced) { was.classList.add('is-linking'); setTimeout(() => was.classList.remove('is-linking'), 1400); } }
      T.stop(li); T.toEnd(true); T.edges(); T.inspect();
      T.state(i < all.length ? `Replaying · ${i} of ${all.length}` : `Replayed · ${all.length} records`);
      if (i < all.length) {
        // real gaps between records, compressed: milliseconds stay quick, a long wait shows as a pause
        const gap = secs(all[i].t) - secs(r.t);
        replaying = setTimeout(next, Math.min(1500, Math.max(380, gap * 600)));
      } else replaying = 0;
    };
    next();
  }
  function glide(from, to, ms) { // a scripted pan of the strip, eased; the reader's own scrolling is never fought
    cancelAnimationFrame(glideRaf);
    if (T.reduced || ms <= 0 || Math.abs(to - from) < 2) { view.scrollLeft = to; return; }
    const t0 = performance.now();
    const step = now => {
      const p = Math.min(1, (now - t0) / ms), e = p < .5 ? 2 * p * p : 1 - Math.pow(2 - 2 * p, 2) / 2;
      view.scrollLeft = from + (to - from) * e;
      if (p < 1 && performance.now() > T.intent) glideRaf = requestAnimationFrame(step);
    };
    glideRaf = requestAnimationFrame(step);
  }

  /* ---- verify: an audit walks every link from the first record to the last ---- */
  function verify() {
    if (T.sel !== null) { T.sel = null; T.markSel(); }
    T.following = false; T.inspect(); // the inspector rides along with the sweep
    armed = null; pending = false; tabs(); // a verdict ends the edit: the fields leave the Tab order (r3)
    sweep.forEach(clearTimeout); sweep = [];
    if (replaying) { clearTimeout(replaying); replaying = 0; whole(); T.inspect(); } // a replay in progress completes at once
    const reduced = T.reduced, res = audit(), ok = verified(), n = recs.length, lis = Array.from(track.children), STEP = 110;
    const first = res.findIndex(a => !a.ok), links = Math.max(0, n - 1);
    const done = ok === n ? `Verified here · ${links} of ${links} links hold`
      : canEdit && first >= 0 ? `Chain broken at ${recs[first].id} · ${n - ok} of ${n} records no longer verify` : `${n - ok} of ${n} records fail verification`;
    X.dirty = false; brokenAt = -1; unbreak();
    // the sweep pans with the walk; a broken chain stops one record before the break, which is then selected (r2)
    const cause = canEdit && first >= 0 ? els.get(recs[first].seq) : null, k = cause ? lis.indexOf(cause) : -1;
    const m = T.maxScroll(), lead = !reduced && m > 4 && view.scrollLeft > 4 ? 280 : 0;
    const to = k >= 0 ? Math.max(0, Math.min(m, Math.round(xOf(lis[Math.max(0, k - 1)])))) : m;
    if (m > 4) { glide(view.scrollLeft, 0, lead); sweep.push(setTimeout(() => glide(0, to, (k >= 0 ? k + 1 : lis.length) * STEP + 240), lead)); }
    lis.forEach((li, i) => {
      const a = res[+li.dataset.seq - recs[0].seq], bad = !!a && !a.ok;
      li.classList.remove('is-verified'); void li.offsetWidth;
      const t = reduced ? 0 : lead + i * STEP;
      // the walk lights each link that holds; from the first that does not, every record turns red and stays red,
      // its sealed hash struck and the hash it produces now written beside it
      sweep.push(setTimeout(() => {
        li.classList.add(bad ? 'is-broken' : 'is-verified');
        if (bad) { T.flag('is-broken', true); nowTag(li, a); }
        if (!reduced) T.state(`Verifying · ${i + 1} of ${lis.length}`);
      }, t));
      if (!bad) sweep.push(setTimeout(() => li.classList.remove('is-verified'), t + 1300));
    });
    sweep.push(setTimeout(() => {
      brokenAt = first >= 0 && canEdit ? first : -1; setIdle();
      if (cause && cause.isConnected && performance.now() > T.intent) T.select(cause, false); // not while the reader is swiping the strip
      T.state(done); say(done);
    }, reduced ? 0 : lead + lis.length * STEP + 120));
  }
  // a record's left edge in the strip's scroll coordinates
  const xOf = li => li.getBoundingClientRect().left - view.getBoundingClientRect().left + view.scrollLeft - (parseFloat(getComputedStyle(track).paddingLeft) || 0);

  /* ---- change a record: type over the selected record, verify, watch the chain fail; restore ---- */
  function refresh(r) { // a record's column, rewritten in place to what it now says
    const li = els.get(r.seq); if (!li) return;
    const ed = isEdited(r), t = T.tone(r.ev), o = orig().get(r.seq);
    r.lc = ed ? 'edited' : (o ? o.lc : r.lc);
    li.classList.toggle('is-settled', t === ' is-settled'); li.classList.toggle('is-rejected', t === ' is-rejected'); li.classList.toggle('is-edited', ed);
    T.put(li.querySelector('.lt-ev'), r.ev); T.put(li.querySelector('.lt-sub'), r.sub); T.put(li.querySelector('.lt-lc'), r.lc || '');
    li.setAttribute('aria-label', `${r.id}, ${r.ev}, ${r.d}, ${r.t}${ed ? ', edited' : ''}`);
  }
  function changed() { // any edit (or a restore) voids the last verdict
    X.v++; X.dirty = anyEdited(); brokenAt = -1; unbreak(); setIdle();
    T.reshow(); T.inspect(); T.state(); ctrls();
  }
  function ctrls() {
    const ed = anyEdited();
    if (ui.restore) ui.restore.hidden = !ed;
    ui.edit.hidden = ed;
  }
  function typed(e) {
    const el = e.currentTarget, r = T.sel !== null ? T.bySeq(T.sel) : null, o = r && orig().get(r.seq);
    if (!r || !el.isContentEditable) return;
    pending = true; // the next Tab out of Detail goes to Verify, once
    const v = el.textContent.replace(/[\r\n]+/g, ' ');
    if (el === F.ev) r.ev = v;
    else { r.d = v; r.sub = o && v === o.d ? o.sub : v; } // the column shows what was typed; the original text restores the original column
    refresh(r); changed();
  }
  // the selected record's event and detail can be typed over; with nothing selected they are read only.
  // r3 (a11y S1, motion): they are Tab stops only once an edit was started on purpose for that record ('Change a record',
  // 'Try to change the past', a click or tap in a field): a record selected by Tab focus never puts an editor in the
  // Tab path. An editable field nobody has typed in yet says what it is (aria-describedby).
  let armed = null, pending = false;
  const touch = () => matchMedia('(hover: none) and (pointer: coarse)').matches;
  const how = document.getElementById('lt-how');
  function arm(seq) { armed = seq; tabs(); }
  function tabs() {
    if (!canEdit) return;
    const r = T.sel !== null ? T.bySeq(T.sel) : null, on = !!r && armed === r.seq, fresh = !!r && !isEdited(r);
    if (how) how.textContent = `Start typing to change this record, then ${touch() ? 'tap your keyboard’s Go or Enter key' : 'press Enter'} to verify the chain.`;
    [F.ev, F.d].forEach(el => {
      if (!el.isContentEditable) { el.removeAttribute('tabindex'); el.removeAttribute('aria-describedby'); return; }
      el.tabIndex = on ? 0 : -1;
      if (how && fresh) el.setAttribute('aria-describedby', how.id); else el.removeAttribute('aria-describedby');
    });
  }
  function editable(r) {
    if (!r || r.seq !== armed) armed = null;
    [[F.ev, 'Event'], [F.d, 'Detail']].forEach(([el, k]) => {
      if (r) {
        if (!el.hasAttribute('contenteditable')) {
          el.setAttribute('contenteditable', 'plaintext-only');
          if (!el.isContentEditable) el.setAttribute('contenteditable', 'true');
          el.setAttribute('role', 'textbox'); el.setAttribute('aria-multiline', 'false'); el.setAttribute('enterkeyhint', 'go'); el.spellcheck = false;
        }
        const label = `${k} of record ${r.id}`;
        if (el.getAttribute('aria-label') !== label) el.setAttribute('aria-label', label);
      } else if (el.hasAttribute('contenteditable')) {
        if (document.activeElement === el) el.blur();
        ['contenteditable', 'role', 'aria-multiline', 'aria-label', 'enterkeyhint'].forEach(a => el.removeAttribute(a));
      }
    });
    tabs();
  }

  // the controls come under the bar when off screen (a browser centres a focused button); with a field being typed in,
  // the field and its cue stay on screen first, so on a short screen the controls show only as far as they fit (r2)
  function place(field) {
    const bar = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0, pad = 12, vh = window.innerHeight;
    const c = (ui.ctrl || root).getBoundingClientRect(), f = field ? (cue && !cue.hidden ? cue : F.d).getBoundingClientRect() : c;
    if (c.top >= bar + pad && f.bottom <= vh - pad) return;
    let dy = c.top - bar - pad;
    if (field && f.bottom - dy > vh - pad) dy = f.bottom - (vh - pad);
    if (Math.abs(dy) > 1) window.scrollBy({ top: dy, behavior: T.reduced ? 'auto' : 'smooth' });
  }
  const toVerify = () => { ui.verify.focus({ preventScroll: true }); place(false); };

  /* ---- wiring: the hooks ledger.js calls, then the controls ---- */
  X.whole = whole;
  X.check = r => { // the inspector's checks; a record that no longer verifies loses its green 'settled' tone there too
    const a = X.v ? at(r) || { linked: true, now: r.hash, ok: true } : null;
    if (a && !a.ok && F.ev) F.ev.classList.remove('is-settled');
    return a;
  };
  X.built = (r, li) => { if (X.v && li.classList.contains('is-edited')) nowTag(li, at(r)); };
  if (canEdit) { X.edited = isEdited; X.editable = editable; }
  if (root.classList.contains('lt-ready')) whole(); // drawn before this file arrived (no IntersectionObserver): mark the waits now
  if (ui.replay) { ui.replay.hidden = false; ui.replay.addEventListener('click', replay); }
  if (ui.verify) { ui.verify.hidden = false; ui.verify.addEventListener('click', verify); }
  if (canEdit) {
    // while a field is typed in, the next step shows under it (r2)
    const typing = on => { if (cue && cue.hidden === on) { cue.hidden = !on; if (ui.insp) ui.insp.classList.toggle('is-typing', on); } };
    [F.ev, F.d].forEach(el => {
      // a field can take focus only by a click or tap, a screen reader or this file (it is out of the Tab order until
      // then): that starts the edit on purpose
      el.addEventListener('focus', () => { if (el.isContentEditable && T.sel !== null && armed !== T.sel) arm(T.sel); typing(el.isContentEditable); });
      el.addEventListener('blur', e => { typing(false); if (e.relatedTarget !== F.ev && e.relatedTarget !== F.d) pending = false; });
      el.addEventListener('input', typed);
      el.addEventListener('keydown', e => {
        if (!el.isContentEditable) return;
        if (e.key === 'Enter') { e.preventDefault(); pending = false; if (ui.verify) { toVerify(); ui.verify.click(); } } // one line: Enter verifies
        else if (e.key === 'Escape') { e.preventDefault(); const b = !ui.edit.hidden ? ui.edit : ui.restore; if (b) b.focus(); }
        // Tab out of Detail after typing goes to Verify, once; any other Tab keeps the page's order (r2; r3: never a loop)
        else if (e.key === 'Tab' && pending && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey && el === F.d && ui.verify && !ui.verify.hidden) { e.preventDefault(); pending = false; toVerify(); }
      });
    });
    ui.edit.addEventListener('click', () => {
      T.mount();
      // the selected record, or the rejection: the record a visitor would most want to rewrite
      let li = T.sel !== null ? els.get(T.sel) : null;
      if (!li) { const r = recs.find(x => /^REJECTED/.test(x.ev)) || recs[0]; li = r ? els.get(r.seq) : null; }
      if (!li) return;
      orig();
      armed = +li.dataset.seq;
      T.select(li, false, true); tabs();
      F.d.focus({ preventScroll: true });
      place(true);
      try { const range = document.createRange(), s = window.getSelection(); range.selectNodeContents(F.d); s.removeAllRanges(); s.addRange(range); } catch (err) { /* the caret stays where focus put it */ }
      say(`Editing ${T.bySeq(T.sel).id}: type over its detail, then ${touch() ? 'tap your keyboard’s Go or Enter key' : 'press Enter'} to verify the chain`);
    });
    if (ui.restore) ui.restore.addEventListener('click', () => {
      armed = null;
      if (T.sel !== null) { T.sel = null; T.markSel(); }
      recs.forEach(r => { const o = orig().get(r.seq); if (o) { r.ev = o.ev; r.sub = o.sub; r.d = o.d; } refresh(r); });
      changed();
      say(`Original records restored · ${T.idle}`);
      ui.edit.focus();
    });
    ui.edit.hidden = false;
    if (ui.hint) ui.hint.hidden = false;

    // the hero's way in: the panel comes up under the bar and "Change a record" puts the caret in the rejection's detail.
    // A modified click, or a record already changed (the button is then Restore), keeps it a plain link to #ledger.
    document.querySelectorAll('a[data-lt-go]').forEach(a => a.addEventListener('click', e => {
      if (ui.edit.hidden || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (location.hash !== a.hash) history.pushState(null, '', a.hash);
      ui.edit.focus({ preventScroll: true }); // site.js settles the panel's entrance at once (focusin), so the scroll lands true
      const still = T.reduced;
      root.scrollIntoView({ block: 'start', behavior: still ? 'auto' : 'smooth' });
      let done = false;
      const go = () => { if (done) return; done = true; window.removeEventListener('scrollend', go); ui.edit.click(); };
      if (still || !('onscrollend' in window)) setTimeout(go, still ? 0 : 700);
      else { window.addEventListener('scrollend', go); setTimeout(go, 1200); }
    }));
  }
  if (ui.ctrl) ui.ctrl.hidden = false;
})();
