/* OpenEXA: Trust (trust.html only): the ledger replay's own controls (Replay, Verify, Change a record, Restore). Why: .shots/v2x/notes/proof.md */
(function () {
  'use strict';
  const root = document.querySelector('[data-ledger="replay"]');
  const T = root && root.oxaTrace;
  if (!T) return;
  const { X, recs, els, track, view, ui, F } = T;
  const canEdit = !!ui.edit && !!F.ev && !!F.d, cue = root.querySelector('[data-lt-enter]');

  const ORIG = new Map();
  const orig = () => { if (!ORIG.size && recs.length) recs.forEach(r => ORIG.set(r.seq, { ev: r.ev, sub: r.sub, d: r.d, lc: r.lc })); return ORIG; };
  let brokenAt = -1, auditKey = '', auditRes = [];
  X.v = 0; X.dirty = false;
  const isEdited = r => { const o = orig().get(r.seq); return !!o && (o.ev !== r.ev || o.d !== r.d || o.sub !== r.sub); };
  const anyEdited = () => recs.some(isEdited);
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
  const brokeAt = i => `Chain broken at ${recs[i].id}${i < recs.length - 1 ? ' · every later link fails' : ''}`;
  function setIdle() {
    const n = recs.length, ok = verified();
    T.idle = brokenAt >= 0 && recs[brokenAt] ? brokeAt(brokenAt) : ok === n ? 'Chain intact' : `${n - ok} of ${n} records fail verification`;
  }
  let said = '';
  const say = t => { if (ui.say && t && t !== said) ui.say.textContent = said = t; };

  function nowTag(li, a) {
    const line = li.querySelector('.lt-line');
    if (!line) return;
    let el = line.querySelector('.lt-now');
    if (!a) { if (el) el.remove(); return; }
    if (!el) { el = T.node('span', 'lt-now'); line.append(el); }
    T.put(el, a.now.slice(0, 8));
  }
  function nows() {
    Array.from(track.children).forEach(li => {
      const r = T.bySeq(+li.dataset.seq);
      nowTag(li, r && X.v && (li.classList.contains('is-edited') || li.classList.contains('is-broken')) ? at(r) : null);
    });
  }
  function unbreak() {
    Array.from(track.querySelectorAll('.is-broken')).forEach(li => li.classList.remove('is-broken'));
    T.flag('is-broken', false);
    nows();
  }

  const secs = t => { const m = /(\d+):(\d+):(\d+)(?:\.(\d+))?/.exec(t || ''); return m ? +m[1] * 3600 + +m[2] * 60 + +m[3] + +('0.' + (m[4] || '0')) : 0; };
  function gapMark(li, a, b) {
    const s = secs(b.t) - secs(a.t);
    if (!li || s < 3600) return;
    const line = li.querySelector('.lt-line');
    if (line && !line.querySelector('.lt-gap')) line.append(T.node('span', 'lt-gap', `+${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m`));
  }
  function whole() {
    hold(false); T.rebuild();
    Array.from(track.children).forEach((li, i, all) => { if (i) gapMark(all[i - 1], T.bySeq(+all[i - 1].dataset.seq), T.bySeq(+li.dataset.seq)); });
  }
  let replaying = 0, glideRaf = 0, sweep = [];
  function hold(on) { track.style.minHeight = on ? track.offsetHeight + 'px' : ''; }
  function replay() {
    unfold(true);
    clearTimeout(replaying);
    sweep.forEach(clearTimeout); sweep = []; cancelAnimationFrame(glideRaf);
    armed = null; pending = false;
    if (canEdit) { brokenAt = -1; X.dirty = anyEdited(); unbreak(); setIdle(); }
    const all = recs.slice();
    if (!all.length) return;
    if (T.sel !== null) T.follow(false);
    T.following = true;
    hold(true); els.clear(); track.replaceChildren(); T.rendered = 0; T.forget();
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
        const gap = secs(all[i].t) - secs(r.t);
        replaying = setTimeout(next, Math.min(1500, Math.max(380, gap * 600)));
      } else { replaying = 0; hold(false); }
    };
    next();
  }
  function glide(from, to, ms) {
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

  function verify() {
    unfold(true);
    if (T.sel !== null) { T.sel = null; T.markSel(); }
    T.following = false; T.inspect();
    armed = null; pending = false; tabs();
    sweep.forEach(clearTimeout); sweep = [];
    if (replaying) { clearTimeout(replaying); replaying = 0; whole(); T.inspect(); }
    const reduced = T.reduced, res = audit(), ok = verified(), n = recs.length, lis = Array.from(track.children), STEP = 110;
    const first = res.findIndex(a => !a.ok), links = Math.max(0, n - 1);
    const done = ok === n ? `Verified here · ${links} of ${links} links hold`
      : canEdit && first >= 0 ? brokeAt(first) : `${n - ok} of ${n} records fail verification`;
    X.dirty = false; brokenAt = -1; unbreak();
    const cause = canEdit && first >= 0 ? els.get(recs[first].seq) : null, k = cause ? lis.indexOf(cause) : -1;
    const m = T.maxScroll(), lead = !reduced && m > 4 && view.scrollLeft > 4 ? 280 : 0;
    const to = k >= 0 ? Math.max(0, Math.min(m, Math.round(xOf(lis[Math.max(0, k - 1)])))) : m;
    if (m > 4) { glide(view.scrollLeft, 0, lead); sweep.push(setTimeout(() => glide(0, to, (k >= 0 ? k + 1 : lis.length) * STEP + 240), lead)); }
    lis.forEach((li, i) => {
      const a = res[+li.dataset.seq - recs[0].seq], bad = !!a && !a.ok;
      li.classList.remove('is-verified'); void li.offsetWidth;
      const t = reduced ? 0 : lead + i * STEP;
      sweep.push(setTimeout(() => {
        li.classList.add(bad ? 'is-broken' : 'is-verified');
        if (bad) { T.flag('is-broken', true); nowTag(li, a); }
        if (!reduced) T.state(`Verifying · ${i + 1} of ${lis.length}`);
      }, t));
      if (!bad) sweep.push(setTimeout(() => li.classList.remove('is-verified'), t + 1300));
    });
    sweep.push(setTimeout(() => {
      brokenAt = first >= 0 && canEdit ? first : -1; setIdle();
      if (cause && cause.isConnected && performance.now() > T.intent) T.select(cause, false);
      T.state(done); say(done);
    }, reduced ? 0 : lead + lis.length * STEP + 120));
  }
  const xOf = li => li.getBoundingClientRect().left - view.getBoundingClientRect().left + view.scrollLeft - (parseFloat(getComputedStyle(track).paddingLeft) || 0);

  function refresh(r) {
    const li = els.get(r.seq); if (!li) return;
    const ed = isEdited(r), t = T.tone(r.ev), o = orig().get(r.seq);
    r.lc = ed ? 'edited' : (o ? o.lc : r.lc);
    li.classList.toggle('is-settled', t === ' is-settled'); li.classList.toggle('is-rejected', t === ' is-rejected'); li.classList.toggle('is-edited', ed);
    T.put(li.querySelector('.lt-ev'), r.ev); T.put(li.querySelector('.lt-sub'), r.sub); T.put(li.querySelector('.lt-lc'), r.lc || '');
    li.setAttribute('aria-label', `${r.id}, ${r.ev}, ${r.d}, ${r.t}${ed ? ', edited' : ''}`);
  }
  function changed() {
    X.v++; X.dirty = anyEdited(); brokenAt = -1; unbreak(); setIdle();
    T.reshow(); T.inspect(); T.state(); ctrls();
  }
  function ctrls() {
    const ed = anyEdited();
    if (ui.restore) ui.restore.hidden = !ed;
    ui.edit.hidden = ed;
    T.flag('is-changed', ed);
  }
  function typed(e) {
    const el = e.currentTarget, r = T.sel !== null ? T.bySeq(T.sel) : null, o = r && orig().get(r.seq);
    if (!r || !el.isContentEditable) return;
    pending = true;
    const v = el.textContent.replace(/[\r\n]+/g, ' ');
    if (el === F.ev) r.ev = v;
    else { r.d = v; r.sub = o && v === o.d ? o.sub : v; }
    refresh(r); changed();
  }
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

  function place(field) {
    const bar = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0, pad = 12, vh = window.innerHeight;
    const c = (ui.ctrl || root).getBoundingClientRect(), f = field ? (cue && !cue.hidden ? cue : F.d).getBoundingClientRect() : c;
    if (c.top >= bar + pad && f.bottom <= vh - pad) return;
    let dy = c.top - bar - pad;
    if (field && f.bottom - dy > vh - pad) dy = f.bottom - (vh - pad);
    if (Math.abs(dy) > 1) window.scrollBy({ top: dy, behavior: T.reduced ? 'auto' : 'smooth' });
  }
  const toVerify = () => { ui.verify.focus({ preventScroll: true }); place(false); };

  const more = root.querySelector('[data-lt-more]'), shut = more ? more.textContent : '';
  function unfold(open) {
    if (!more || root.classList.contains('is-open') === open) return;
    root.classList.toggle('is-open', open);
    more.setAttribute('aria-expanded', String(open));
    more.textContent = open ? 'Show the first four records' : shut;
    if (!open) {
      if (replaying) { clearTimeout(replaying); replaying = 0; whole(); }
      const li = T.sel !== null ? els.get(T.sel) : null;
      if (li && !li.getClientRects().length) { T.sel = null; T.markSel(); }
      T.stop(T.sel !== null ? els.get(T.sel) : track.lastElementChild);
    }
    T.inspect(); T.state();
  }
  if (more) more.addEventListener('click', () => unfold(!root.classList.contains('is-open')));

  X.whole = whole;
  X.check = r => {
    const a = X.v ? at(r) || { linked: true, now: r.hash, ok: true } : null;
    if (a && !a.ok && F.ev) F.ev.classList.remove('is-settled');
    return a;
  };
  X.built = (r, li) => { if (X.v && li.classList.contains('is-edited')) nowTag(li, at(r)); };
  if (canEdit) { X.edited = isEdited; X.editable = editable; }
  if (root.classList.contains('lt-ready')) whole();
  if (ui.replay) { ui.replay.hidden = false; ui.replay.addEventListener('click', replay); }
  if (ui.verify) { ui.verify.hidden = false; ui.verify.addEventListener('click', verify); }
  if (canEdit) {
    const typing = on => { if (cue && cue.hidden === on) { cue.hidden = !on; if (ui.insp) ui.insp.classList.toggle('is-typing', on); } };
    [F.ev, F.d].forEach(el => {
      el.addEventListener('focus', () => { if (el.isContentEditable && T.sel !== null && armed !== T.sel) arm(T.sel); typing(el.isContentEditable); });
      el.addEventListener('blur', e => { typing(false); if (e.relatedTarget !== F.ev && e.relatedTarget !== F.d) pending = false; });
      el.addEventListener('input', typed);
      el.addEventListener('keydown', e => {
        if (!el.isContentEditable) return;
        if (e.key === 'Enter') { e.preventDefault(); pending = false; if (ui.verify) { toVerify(); ui.verify.click(); } }
        else if (e.key === 'Escape') { e.preventDefault(); const b = !ui.edit.hidden ? ui.edit : ui.restore; if (b) b.focus(); }
        else if (e.key === 'Tab' && pending && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey && el === F.d && ui.verify && !ui.verify.hidden) { e.preventDefault(); pending = false; toVerify(); }
      });
    });
    ui.edit.addEventListener('click', () => {
      T.mount(); unfold(true);
      let li = T.sel !== null ? els.get(T.sel) : null;
      if (!li) { const r = recs.find(x => /^REJECTED/.test(x.ev)) || recs[0]; li = r ? els.get(r.seq) : null; }
      if (!li) return;
      orig();
      armed = +li.dataset.seq;
      T.select(li, false, true); tabs();
      F.d.focus({ preventScroll: true });
      place(true);
      try { const range = document.createRange(), s = window.getSelection(); range.selectNodeContents(F.d); s.removeAllRanges(); s.addRange(range); } catch (err) { }
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

    document.querySelectorAll('a[data-lt-go]').forEach(a => a.addEventListener('click', e => {
      if (ui.edit.hidden || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (location.hash !== a.hash) history.pushState(null, '', a.hash);
      ui.edit.focus({ preventScroll: true });
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

/* hc30r (PROOF-2, on system's SYS-2): reached by a page turn the hero plate arrives whole, so its act (a proposal passes
   the Council and settles) runs once when the turn has landed (OXA.actOnce: in view, never under reduced motion);
   proof.css .is-act. A direct load plays the act in the plate's entrance, as before */
(function () {
  'use strict';
  const plate = document.querySelector('.hero-plate--council'), O = window.OXA;
  if (plate && O && O.byTurn && O.actOnce) O.actOnce(plate, () => plate.classList.add('is-act'), { delay: 900 });
})();
