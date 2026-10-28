/* OpenEXA — shared behaviour
   nav (chapter readout, progress, menu sheet) · clocks · loader · kinetic type · manifesto · reveals · forms
   · 2D swarm fallback */
(function () {
  'use strict';

  const CONTACT = document.body.dataset.contact || 'access@openexa.com'; // inbox for the access form — set data-contact on <body> of access.html
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)'); // read live where motion is optional
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pad = (n) => String(n).padStart(2, '0');
  const clamp01 = (v) => v < 0 ? 0 : v > 1 ? 1 : v;
  const root = document.documentElement;

  /* ---------------- nav: the frame of every page ----------------
     The bar is transparent over a dark opening and otherwise glass that takes the ground of the section beneath it.
     Pages with chapters (homepage [data-chapter] sections; numbered sections elsewhere; an article's headings) get a
     readout beside the brand — number + title of the chapter being read, a list on click/Enter — and a progress hairline
     along the bar's lower edge, cut into those chapters. Geometry is measured on resize/content change, never per frame. */
  const nav = $('.nav');
  const darkStart = document.body.dataset.nav === 'dark-start';
  const themeMeta = $('meta[name="theme-color"]');
  const story = $('.story');
  const paper = story && $('.story-paper', story);
  let paperTop = null, paperWatch = 0;
  const toggle = $('.nav-toggle');
  const sheet = $('.nav-sheet');
  let navH = 72, vh = window.innerHeight, maxScroll = 1, clearUntil = -1, bands = [], navRaf = 0, menuOpen = false;

  const pageKey = path => path.replace(/\/+$/, '').split('/').pop().replace(/\.html$/, '') || 'index';
  const here = pageKey(location.pathname);
  const section = /\/research\/[^/]+$/.test(location.pathname) ? 'research' : here; // an article sits under Research
  // marks the link to where the reader is; never removes a mark the page itself states (a research article's markup
  // marks Research, and stripping it hid the current-page underline there)
  $$('.nav-links a, .nav-sheet a, .nav .btn').forEach(a => {
    const href = (a.getAttribute('href') || '').split(/[?#]/)[0];
    if (href && (pageKey(href) === here || pageKey(href) === section)) a.setAttribute('aria-current', 'page');
  });

  /* chapters: [data-chapter] sections, else numbered sections (.sec-head), else an article's table of contents.
     A chapter is named by its section's own label (.sec-head .lab), exactly as the page prints it; data-chapter-short
     may abbreviate it in the phone bar, and only where the full label does not fit (fitModes) */
  const tagline = ($('.nav .brand small') || {}).textContent || '';
  const headOf = el => { const head = $('.sec-head', el); return head && head.closest('section') === el ? head : null; };
  const labOf = el => { const lab = headOf(el) && $('.lab', headOf(el)); return lab ? lab.textContent.trim() : ''; };
  const shortOf = el => (el.dataset.chapterShort || '').trim();
  let chapters = $$('section[data-chapter]').map((el, i) => ({ el, n: el.dataset.n || pad(i + 1), title: labOf(el) || el.dataset.chapter, short: shortOf(el) }));
  if (chapters.length < 2) chapters = $$('main section').map(el => {
    const head = headOf(el), idx = head && $('.idx', head), lab = head && $('.lab', head);
    return idx && lab ? { el, n: idx.textContent.trim(), title: lab.textContent.trim(), short: shortOf(el) } : null;
  }).filter(Boolean);
  if (chapters.length < 2) chapters = $$('.toc a[href^="#"]').map((a, i) => {
    const el = document.getElementById(decodeURIComponent(a.hash.slice(1)));
    return el ? { el, n: pad(i + 1), title: a.textContent.trim(), short: '', toc: true, scope: el.closest('article, .article') } : null;
  }).filter(Boolean);
  if (chapters.length < 2) chapters = [];
  if (!nav || !$('.brand', nav)) chapters = [];
  chapters.forEach((c, k) => {
    c.k = k;
    if (!c.el.id) { let id = 'chapter-' + (c.n.replace(/[^\w-]/g, '') || k); while (document.getElementById(id)) id += '-'; c.el.id = id; }
  });
  // an address that names a section given its id just now (the browser looked for it before this script ran)
  if (chapters.length && location.hash && chapters.some(c => '#' + c.el.id === decodeURIComponent(location.hash)) && window.scrollY < 2) {
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    requestAnimationFrame(() => target.scrollIntoView({ block: 'start', behavior: 'instant' }));
  }

  let live = [], segs = [], current = -2, shownK = -3, chOpen = false;
  const ui = {};
  if (nav) {
    // the hairline: intro · chapters · outro, each as long as the scroll it covers
    ui.progress = document.createElement('div'); ui.progress.className = 'nav-progress'; ui.progress.setAttribute('aria-hidden', 'true');
    nav.appendChild(ui.progress);
  }
  if (nav && chapters.length) {
    const brand = $('.brand', nav);
    nav.classList.add('has-ch');
    const wrap = ui.wrap = document.createElement('div'); wrap.className = 'nav-ch';
    wrap.innerHTML =
      '<button class="nav-ch-btn" type="button" aria-expanded="false" aria-controls="nav-ch-panel"><span class="nav-ch-roll"></span>' +
      '<svg class="nav-ch-caret" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.6l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.3"/></svg></button>' +
      '<div class="nav-ch-panel" id="nav-ch-panel"><div class="nav-ch-head"><span>On this page</span><span></span></div><ol class="nav-ch-list"></ol>' +
      '<a class="nav-ch-top" href="#"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8.5V1.8M2 4.6l3-3 3 3" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>Back to top</a></div>';
    brand.after(wrap);
    ui.btn = $('.nav-ch-btn', wrap); ui.roll = $('.nav-ch-roll', wrap); ui.panel = $('.nav-ch-panel', wrap); ui.list = $('.nav-ch-list', wrap);
    $('.nav-ch-head span:last-child', wrap).textContent = pad(chapters.length) + ' chapters';
    chapters.forEach(c => {
      const li = document.createElement('li'), a = document.createElement('a');
      a.href = '#' + c.el.id; a.dataset.k = c.k;
      a.innerHTML = '<span class="n"></span><span class="t"></span><span class="p"><b></b></span>';
      $('.n', a).textContent = c.n; $('.t', a).textContent = c.title;
      li.appendChild(a); ui.list.appendChild(li); c.li = li; c.a = a; c.bar = $('.p b', a);
    });
  }

  /* the readout: the line rolls up to the next chapter (down when going back); its width follows. Each line carries the
     label, its short form (if the section gives one) and a compact '§NN / total'; a mode class shows one of them */
  const MODES = ['is-short', 'is-compact'];
  const total = () => pad(Math.max(0, ...chapters.map(c => /^\d+$/.test(c.n) ? +c.n : 0)) || chapters.length);
  function lineFor(k, mode) {
    const line = document.createElement('span');
    line.className = 'nav-ch-line';
    if (k < 0) {
      line.classList.add('is-intro');
      line.innerHTML = '<span class="t t-wide"></span><span class="t t-short">Index</span>';
      line.firstChild.textContent = tagline || 'Index';
    } else {
      const c = chapters[k], b = document.createElement('b'), t = document.createElement('span');
      b.textContent = c.n; if (/^\d+$/.test(c.n)) b.className = 'is-num';
      t.className = 't'; t.textContent = c.title;
      line.append(b, ' ', t);
      if (c.short && c.short !== c.title) { const s = document.createElement('span'); s.className = 't-sh'; s.textContent = c.short; line.append(s); }
      if (b.className) { const o = document.createElement('span'); o.className = 't-of'; o.textContent = '/ ' + total(); line.append(o); }
      const m = mode || c.mode || 'full';
      if (m !== 'full') line.classList.add('is-' + m);
    }
    return line;
  }
  /* phones: the full label wherever it fits; else the section's short form; else '§NN / total'. Decided per page (when one
     label needs the compact form, every chapter takes it, so the bar keeps one register), from the natural width of
     every form in the readout's own type against the room the bar gives the line. Articles' headings go compact
     under 600 px. Desktop keeps the label (961-1099 px shows the number only). */
  const narrowMQ = window.matchMedia('(max-width: 960px)'), phoneMQ = window.matchMedia('(max-width: 600px)');
  let fitKey = '';
  function fitModes() {
    if (!ui.roll || !live.length) return;
    const key = [window.innerWidth, live.map(c => c.k).join(), document.fonts ? document.fonts.status : ''].join('|');
    if (key === fitKey) return;
    fitKey = key;
    live.forEach(c => { c.mode = 'full'; });
    if (narrowMQ.matches) {
      const box = document.createElement('span'); box.className = 'nav-ch-measure'; box.setAttribute('aria-hidden', 'true');
      const forms = [];
      live.forEach(c => { forms.push([c, 'full', lineFor(c.k, 'full')]); if (c.short && c.short !== c.title) forms.push([c, 'short', lineFor(c.k, 'short')]); });
      forms.forEach(f => box.appendChild(f[2]));
      ui.btn.appendChild(box);
      const avail = ui.wrap.getBoundingClientRect().width - (ui.btn.getBoundingClientRect().width - ui.roll.getBoundingClientRect().width) - 1;
      const w = new Map(forms.map(([c, m, l]) => [c.k + m, l.getBoundingClientRect().width]));
      box.remove();
      let compact = false;
      live.forEach(c => {
        if (c.toc && phoneMQ.matches) { compact = true; c.fit = false; }
        else if (w.get(c.k + 'full') <= avail) c.mode = 'full';
        else if (w.has(c.k + 'short') && w.get(c.k + 'short') <= avail) c.mode = 'short';
        else { compact = true; c.fit = false; }
      });
      // the compact form is a number: a chapter without one (the blog's featured series) keeps its label if it fits
      if (compact) live.forEach(c => { if (/^\d+$/.test(c.n) || c.fit === false) c.mode = 'compact'; });
      live.forEach(c => { delete c.fit; });
    }
    const c = chapters[shownK];
    if (ui.line && c) { MODES.forEach(m => ui.line.classList.toggle(m, m === 'is-' + c.mode)); }
  }
  function showChapter(k) {
    if (!ui.roll || k === shownK) return;
    const dir = k > shownK ? 1 : -1, first = shownK === -3;
    shownK = k;
    const label = k < 0 ? `On this page: ${chapters.length} chapters` : `Chapter ${chapters[k].n}, ${chapters[k].title}. On this page: ${chapters.length} chapters`;
    ui.btn.setAttribute('aria-label', label);
    chapters.forEach(c => { if (c.k === k) c.a.setAttribute('aria-current', 'true'); else c.a.removeAttribute('aria-current'); });
    if (ui.roll.getAnimations) ui.roll.getAnimations({ subtree: true }).forEach(a => a.cancel());
    const w0 = first ? 0 : ui.roll.getBoundingClientRect().width; // the width on screen now, before anything leaves
    Array.from(ui.roll.children).forEach(ch => ch.remove());
    const old = ui.line, neu = lineFor(k);
    ui.line = neu;
    ui.roll.appendChild(neu);
    // a long jump (ours, or the swarm lab's record trip: html[data-jump]) lands with its readout: no roll
    if (first || !old || reducedMQ.matches || !neu.animate || document.hidden || jumping || root.dataset.jump) return;
    old.style.cssText = 'position:absolute;left:0;top:4px;width:max-content';
    ui.roll.appendChild(old);
    const w1 = neu.getBoundingClientRect().width;
    const timing = { duration: 560, easing: 'cubic-bezier(.2, .7, .2, 1)' };
    if (Math.abs(w1 - w0) > 1) ui.roll.animate([{ width: w0 + 'px' }, { width: w1 + 'px' }], timing);
    old.animate([{ transform: 'none', opacity: 1 }, { transform: `translateY(${-dir * 120}%)`, opacity: 0 }], { ...timing, duration: 420, fill: 'forwards' })
      .finished.then(() => old.remove(), () => old.remove());
    neu.animate([{ transform: `translateY(${dir * 120}%)`, opacity: 0 }, { transform: 'none', opacity: 1 }], timing);
  }

  function buildSegments() {
    ui.progress.textContent = '';
    const parts = live.length ? ['edge', ...live, 'edge'] : ['page'];
    segs = parts.map(part => {
      const i = document.createElement('i'), b = document.createElement('b');
      if (part === 'edge') i.className = 'is-edge';
      i.appendChild(b); ui.progress.appendChild(i);
      return { i, b, part, s: 0, e: 0, p: -1 };
    });
  }

  /* geometry, in document coordinates */
  function measure() {
    if (!nav) return;
    const y = window.scrollY;
    vh = window.innerHeight; navH = nav.offsetHeight || 72;
    maxScroll = Math.max(1, root.scrollHeight - vh);
    const pinned = story && root.classList.contains('story-ready') && !root.classList.contains('no-webgl');
    // over a pinned overture the bar stays clear until the stage starts to leave (its text then passes under glass, never
    // under bare links); a static dark opening is clear only at the very top
    clearUntil = !darkStart ? -1 : pinned ? story.getBoundingClientRect().bottom + y - vh : 16;
    bands = $$('main > *, body > .footer').map(el => {
      const r = el.getBoundingClientRect();
      return { el, top: r.top + y, bottom: r.bottom + y, dark: el.classList.contains('is-dark') };
    });
    const before = live.map(c => c.k).join();
    live = chapters.filter(c => c.el.getClientRects().length > 0);
    chapters.forEach(c => { c.li.hidden = !live.includes(c); });
    if (before !== live.map(c => c.k).join() || !segs.length) buildSegments();
    const probe = navH + (vh - navH) * 0.3; // the reading line: a third of the way down below the bar
    live.forEach(c => { const r = c.el.getBoundingClientRect(); c.top = r.top + y; c.bottom = r.bottom + y; });
    live.forEach((c, i) => {
      const next = live[i + 1];
      const end = next ? next.top : c.scope ? c.scope.getBoundingClientRect().bottom + y : c.bottom;
      c.s = Math.min(maxScroll, Math.max(0, c.top - probe));
      c.e = Math.min(maxScroll, Math.max(c.s, end - probe));
    });
    if (live.length) {
      const first = live[0], last = live[live.length - 1];
      segs.forEach((g, j) => {
        if (g.part === 'edge') { g.s = j === 0 ? 0 : last.e; g.e = j === 0 ? first.s : maxScroll; }
        else { g.s = g.part.s; g.e = g.part.e; }
      });
    } else if (segs.length) { segs[0].s = 0; segs[0].e = maxScroll; }
    segs.forEach(g => {
      const len = g.e - g.s;
      g.i.style.flexGrow = Math.max(0, len).toFixed(1);
      g.i.style.display = len < 2 ? 'none' : '';
      g.p = -1;
    });
    fitModes();
    update();
  }
  const queue = () => { if (!navRaf) navRaf = requestAnimationFrame(() => { navRaf = 0; update(); }); };

  function update() {
    if (!nav) return;
    const y = window.scrollY;
    // the bar's surface: the ground of the section that meets its lower edge, so bar and section read as one
    let dark = false, band = null;
    const edge = y + navH + 1;
    for (const b of bands) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    // the overture's exit: its rising paper (.story-paper; hidden unless it rises) is paper under the bar as soon as its
    // edge reaches the bar's lower edge, though the band beneath is the dark stage. The rise follows the scroll with the
    // stage's inertia, so while the edge moves this looks again on the next frames.
    let overPaper = false;
    if (band && band.el === story && paper) {
      const r = getComputedStyle(paper).visibility !== 'hidden' ? paper.getBoundingClientRect() : null;
      overPaper = !!r && r.height > 0 && r.top <= navH + 1 && r.bottom > navH;
      const top = r && r.height > 0 ? Math.round(r.top) : null;
      if (top !== paperTop) { paperTop = top; paperWatch = 8; }
      if (paperWatch > 0) { paperWatch--; queue(); }
    } else { paperTop = null; paperWatch = 0; }
    if (overPaper) dark = false;
    const clear = y <= clearUntil && !menuOpen && !overPaper;
    nav.classList.toggle('nav--solid', !clear);
    nav.classList.toggle('nav--dark', dark);
    if (themeMeta) {
      const ink = clear ? darkStart : dark || menuOpen;
      const want = ink ? '#0E1512' : '#F5F2EC';
      if (themeMeta.content !== want) themeMeta.content = want;
    }
    // the hairline
    let on = -1;
    segs.forEach((g, j) => {
      const len = g.e - g.s;
      const p = len > 0 ? clamp01((y - g.s) / len) : (y >= g.e ? 1 : 0);
      if (Math.abs(p - g.p) > 0.001) { g.p = p; g.b.style.transform = `scaleX(${p.toFixed(4)})`; }
      if (y >= g.s && (y < g.e || j === segs.length - 1)) on = j;
    });
    segs.forEach((g, j) => g.i.classList.toggle('is-on', j === on && g.p > 0 && live.length > 0)); // green marks a chapter
    // the readout
    if (!live.length) return;
    let k = -1;
    for (const c of live) if (y >= c.s) k = c.k;
    live.forEach(c => {
      const p = c.e > c.s ? clamp01((y - c.s) / (c.e - c.s)) : (y >= c.e ? 1 : 0);
      if (Math.abs(p - (c.p || 0)) > 0.004 || c.p === undefined) { c.p = p; c.bar.style.setProperty('--p', p.toFixed(3)); }
    });
    if (k !== current) { current = k; showChapter(k); }
  }

  /* the chapter list */
  function setPanel(open, refocus) {
    if (!ui.wrap || open === chOpen) return;
    chOpen = open;
    ui.wrap.classList.toggle('is-open', open);
    ui.btn.setAttribute('aria-expanded', String(open));
    if (open && menuOpen) setMenu(false);
    if (!open && refocus) ui.btn.focus();
  }
  const rows = () => live.map(c => c.a);
  const focusRow = (i) => { const r = rows(); if (r.length) r[(i + r.length) % r.length].focus(); };
  if (ui.wrap) {
    ui.btn.addEventListener('click', () => setPanel(!chOpen));
    ui.btn.addEventListener('keydown', e => {
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
      e.preventDefault(); setPanel(true);
      const i = live.findIndex(c => c.k === current);
      focusRow(e.key === 'ArrowUp' ? live.length - 1 : Math.max(0, i));
    });
    ui.panel.addEventListener('keydown', e => {
      const r = rows(), i = r.indexOf(document.activeElement);
      if (e.key === 'Escape') { e.preventDefault(); setPanel(false, true); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); focusRow(i + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); focusRow(i < 0 ? r.length - 1 : i - 1); }
      else if (e.key === 'Home') { e.preventDefault(); focusRow(0); }
      else if (e.key === 'End') { e.preventDefault(); focusRow(r.length - 1); }
    });
    ui.btn.addEventListener('keydown', e => { if (e.key === 'Escape' && chOpen) { e.preventDefault(); setPanel(false); } });
    ui.list.addEventListener('click', e => {
      const a = e.target.closest('a');
      if (!a) return;
      const c = chapters[+a.dataset.k];
      setPanel(false);
      // focus follows the reader to the chapter (the next Tab continues inside it). A long jump cuts to it (jumpTo);
      // a short hop is the browser's own anchor scroll, smooth where motion is welcome
      c.el.setAttribute('tabindex', '-1'); c.el.classList.add('nav-ch-target');
      const focus = () => c.el.focus({ preventScroll: true });
      if (!jumpTo(c.el, a.hash, e, focus)) setTimeout(focus, 0);
    });
    $('.nav-ch-top', ui.wrap).addEventListener('click', e => {
      e.preventDefault(); setPanel(false, true);
      if (!jumpTo(null)) window.scrollTo({ top: 0, behavior: reducedMQ.matches ? 'instant' : 'smooth' });
    });
    document.addEventListener('pointerdown', e => { if (chOpen && !ui.wrap.contains(e.target)) setPanel(false); });
    ui.wrap.addEventListener('focusout', e => { if (chOpen && e.relatedTarget && !ui.wrap.contains(e.relatedTarget)) setPanel(false); });
  }

  /* the menu sheet (phones, tablets): a popover — it opens without JavaScript; this adds focus care, the bar's state,
     a fallback for browsers without the popover API, and keeps the page behind it inert */
  const popover = !!(sheet && sheet.hasAttribute('popover') && typeof sheet.showPopover === 'function');
  function syncMenu(open) {
    if (open === menuOpen) return;
    menuOpen = open;
    document.body.classList.toggle('nav-open', open);
    if (nav) nav.classList.toggle('nav--menu', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    $$('body > main, body > .footer').forEach(el => { el.inert = open; });
    if (open) setPanel(false);
    update();
  }
  function setMenu(open) {
    if (!sheet) return;
    if (popover) { try { open ? sheet.showPopover() : sheet.hidePopover(); } catch (e) { /* already in that state */ } }
    else syncMenu(open);
  }
  if (toggle && sheet) {
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-controls', sheet.id);
    if (popover) sheet.addEventListener('beforetoggle', e => syncMenu(e.newState === 'open'));
    else {
      toggle.removeAttribute('popovertarget');
      toggle.addEventListener('click', () => setMenu(!menuOpen));
    }
    // a link to another page leaves the sheet open, marked, so the page transition carries it away
    $$('a', sheet).forEach(a => a.addEventListener('click', () => {
      const href = a.getAttribute('href') || '';
      if (href.startsWith('#') || pageKey(href.split(/[?#]/)[0]) === here) setMenu(false);
      else a.classList.add('is-going');
    }));
    document.addEventListener('keydown', e => {
      if (!menuOpen) return;
      if (e.key === 'Escape' && !popover) { setMenu(false); toggle.focus(); }
      else if (e.key === 'Tab') {
        const items = $$('a[href], button', sheet).filter(el => el.getClientRects().length);
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === toggle && last) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); toggle.focus(); }
      }
    });
    window.matchMedia('(min-width: 961px)').addEventListener('change', e => { if (e.matches) setMenu(false); });
    window.addEventListener('pageshow', e => { if (e.persisted) { setMenu(false); $$('.is-going', sheet).forEach(a => a.classList.remove('is-going')); } });
  }
  window.addEventListener('keydown', e => { if (e.key === 'Escape' && chOpen) setPanel(false, true); });

  /* ---------------- long jumps: never through blank paper ----------------
     A jump of more than 1.5 screens (a chapter from the list, Back to top, any link to a place on this page) used to
     scroll smoothly through every section in between, whose reveals had not run: about a second of near-empty paper,
     then a landing mid-reveal. It now cuts: everything it passes over and the destination are revealed without
     transition, the page lands at once (at the bar's edge, as an anchor jump does), and a same-document view transition
     brings the live destination in as a sheet over the still of where the reader was: rising from the bottom edge going
     down the page, coming down from the top going up (v2:nav CSS; the bar holds; no blend, never a blank frame).
     Without view transitions, or with reduced motion, it is a plain instant cut. Short hops keep the native scroll.
     The browser's still of the outgoing view holds nothing below about 16,384 CSS px of the document at any pixel ratio
     (the sheet would slide over flat ink there; the incoming view is live and is not affected): a jump that leaves a
     view reaching past VT_LIMIT is a plain cut, and what lands settles in from a dim start in .16 s (.is-landing). The
     swarm's record trip applies the same limit. */
  const VT_LIMIT = 16000;
  let jumping = false;
  function settle() {
    const bands = $$('main > *, body > .footer').filter(el => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; });
    bands.forEach(el => {
      el.classList.remove('is-offscreen', 'is-landing'); // on screen now (the observer agrees a frame later)
      void el.offsetWidth; // a second landing restarts the settle
      el.classList.add('is-landing');
      setTimeout(() => el.classList.remove('is-landing'), 400);
    });
  }
  function cut(to, land) {
    const from = window.scrollY;
    // the chapter list is already closing: it goes at once (it would hang over the landing)
    if (ui.wrap) { ui.wrap.classList.add('is-snap'); setTimeout(() => ui.wrap.classList.remove('is-snap'), 60); }
    const go = () => {
      jumping = true;
      revealRange(Math.min(from, to), Math.max(from, to) + window.innerHeight); // first: an entrance offset would skew the landing
      land();
      if (nav) measure(); // the bar takes the destination's ground (and its readout) in the same frame
      jumping = false;
      document.dispatchEvent(new CustomEvent('oxa:jump', { detail: { from, to: window.scrollY } }));
    };
    if (reducedMQ.matches || typeof document.startViewTransition !== 'function' || document.hidden) { go(); return; }
    if (from + window.innerHeight > VT_LIMIT) { go(); settle(); return; }
    root.dataset.jump = to > from ? 'down' : 'up';
    let vt;
    try { vt = document.startViewTransition(go); } catch (err) { delete root.dataset.jump; go(); return; }
    vt.ready.catch(() => {}); vt.updateCallbackDone.catch(() => {});
    vt.finished.catch(() => {}).then(() => { delete root.dataset.jump; });
  }
  // a jump to an element (null: the top) longer than 1.5 screens is handled here (returns true); a shorter one is not
  function jumpTo(el, hash, e, after) {
    const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
    const y0 = window.scrollY, max = Math.max(0, root.scrollHeight - window.innerHeight);
    const to = el ? Math.max(0, Math.min(max, el.getBoundingClientRect().top + y0 - sp)) : 0;
    if (Math.abs(to - y0) <= 1.5 * window.innerHeight) return false;
    if (e) e.preventDefault();
    cut(to, () => {
      // the address changes as an anchor jump's would, and so does everything that listens for it (the blog's filter)
      if (hash && hash !== location.hash) {
        const oldURL = location.href;
        history.pushState(null, '', hash);
        window.dispatchEvent(new HashChangeEvent('hashchange', { oldURL, newURL: location.href }));
      }
      if (el) el.scrollIntoView({ block: 'start', behavior: 'instant' });
      else window.scrollTo({ top: 0, behavior: 'instant' });
      if (after) after();
    });
    return true;
  }
  // any other link to a place on this page (the overture's "See the stack", Company's "Our thinking", ...)
  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest('a[href*="#"]');
    if (!a || (a.target && a.target !== '_self') || a.closest('.nav-ch, .nav-sheet')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname || url.search !== location.search || url.hash.length < 2) return;
    const el = document.getElementById(decodeURIComponent(url.hash.slice(1)));
    if (!el || el.closest('details:not([open])')) return; // the browser opens a closed <details> for its target
    jumpTo(el, url.hash, e, () => {
      // as after an anchor jump, the next Tab continues from the destination
      if (!el.matches('a[href], button, input, select, textarea, [tabindex]')) { el.setAttribute('tabindex', '-1'); el.classList.add('nav-ch-target'); }
      el.focus({ preventScroll: true });
    });
  });

  if (nav) {
    measure();
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', measure);
    window.addEventListener('load', measure);
    ['story:gl-ready', 'story:no-webgl', 'oxa:loaded'].forEach(t => document.addEventListener(t, measure));
    // content that changes height (fonts, lazy images, opened details, filtered collections) moves every chapter
    if ('ResizeObserver' in window) { let ro = 0; new ResizeObserver(() => { cancelAnimationFrame(ro); ro = requestAnimationFrame(measure); }).observe(document.body); }
    if (document.fonts) document.fonts.ready.then(measure);
  }
  /* ---------------- the reader's place: kept through resizes, and a deep link's landing kept after late layout ----------------
     The fluid gutters change computed paddings on every resize, which switches the browser's own scroll anchoring off:
     a reader at Home 06 was moved by -868 to +3,006 px between widths. When scrolling settles this keeps a reading
     anchor (the element at the bar's lower edge and its offset from the edge); after a resize that changed the width,
     or the height while the reader was not scrolling, it scrolls back by the difference, and again as late layout
     settles. Not inside the overture, which keeps its own scene. */
  let anchor = null, settleUntil = 0, lastInput = 0, lastW = window.innerWidth;
  const inFlow = el => { const p = getComputedStyle(el).position; return p !== 'fixed' && p !== 'sticky' && p !== 'absolute'; };
  // where layout puts an element (viewport y), ignoring transforms: a reveal's entrance offset is not the place
  const layoutTop = el => { let y = 0; for (let e = el; e; e = e.offsetParent) y += e.offsetTop; return y - window.scrollY; };
  function pickAnchor() {
    anchor = null;
    if (!nav || !bands.length) return;
    const line = navH + 8; // viewport y, just under the bar
    const yDoc = window.scrollY + line;
    const band = bands.find(b => yDoc >= b.top && yDoc < b.bottom);
    if (!band || band.el === story) return;
    let el = band.el;
    for (let depth = 0; depth < 14; depth++) {
      if (Math.abs(layoutTop(el) - navH) <= 24) break; // it starts at the bar's edge: it is the place
      let straddle = null, next = null;
      for (const ch of el.children) {
        if (!(ch instanceof HTMLElement) || !ch.offsetHeight || !inFlow(ch)) continue;
        const t = layoutTop(ch);
        if (t <= line && t + ch.offsetHeight > line) { straddle = ch; break; }
        if (t > line) { next = ch; break; }
      }
      if (straddle) { el = straddle; continue; }
      // the line falls in a gap: inside a band or a section, the band/section itself is the place (its top is the
      // chapter's start); inside content, the next block if it is near
      if (next && el !== band.el && el.tagName !== 'SECTION' && layoutTop(next) - line < window.innerHeight * 0.25) el = next;
      break;
    }
    anchor = { el, off: layoutTop(el) - navH };
  }
  function restoreAnchor() {
    if (!anchor || !anchor.el.isConnected || performance.now() > settleUntil) return;
    const d = layoutTop(anchor.el) - (navH + anchor.off);
    if (Math.abs(d) > 0.5) window.scrollBy({ top: d, behavior: 'instant' });
  }
  if (nav) {
    ['wheel', 'touchstart', 'touchmove', 'keydown', 'pointerdown'].forEach(t => window.addEventListener(t, () => { lastInput = performance.now(); settleUntil = 0; }, { passive: true, capture: true }));
    let pickT = 0;
    window.addEventListener('scroll', () => {
      if (performance.now() < settleUntil) return; // our own correction, or the page settling after a resize
      clearTimeout(pickT); pickT = setTimeout(pickAnchor, 160);
    }, { passive: true });
    window.addEventListener('resize', () => {
      const w = window.innerWidth, widthChanged = w !== lastW;
      lastW = w;
      // a height-only change while the reader scrolls is a phone's toolbar: nothing moved under the reader
      if (!anchor || (!widthChanged && performance.now() - lastInput < 800)) return;
      settleUntil = performance.now() + 900;
      navH = nav.offsetHeight || navH;
      restoreAnchor();
      requestAnimationFrame(() => { restoreAnchor(); requestAnimationFrame(restoreAnchor); });
      [120, 300, 600, 880].forEach(ms => setTimeout(restoreAnchor, ms));
    });
    setTimeout(pickAnchor, 0);
    document.addEventListener('oxa:jump', () => setTimeout(pickAnchor, 0));
  }
  // a deep link (#id) lands at the bar's edge once the layout has settled after load (components that build late,
  // fonts, the overture's stage), unless the reader has already moved: two quiet frames with the same page height,
  // then once more if the page still changes within 2.5 s
  const deep = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (deep && nav) {
    let quietFrom = 0, deepDone = false, alignedY = 0;
    const realign = (h0, n) => requestAnimationFrame(() => requestAnimationFrame(() => {
      if (lastInput || deepDone) return;
      const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0, off = () => deep.getBoundingClientRect().top - sp;
      // late layout moves the target while the page stays where it was; a page that has moved away from the target since
      // (a script scrolled elsewhere) is someone else's: stop watching (moved and still on target: the browser's own anchoring)
      if (Math.abs(window.scrollY - alignedY) > 2) { if (Math.abs(off()) > 2) { deepDone = true; return; } alignedY = window.scrollY; }
      const h = root.scrollHeight;
      if (h !== h0 && n < 60) { realign(h, n + 1); return; }
      if (Math.abs(off()) > 1) deep.scrollIntoView({ block: 'start', behavior: 'instant' });
      alignedY = window.scrollY;
    }));
    const start = () => {
      quietFrom = performance.now();
      alignedY = window.scrollY;
      realign(root.scrollHeight, 0);
      if ('ResizeObserver' in window) {
        const ro = new ResizeObserver(() => { if (performance.now() - quietFrom < 2500 && !lastInput && !deepDone) realign(root.scrollHeight, 0); else ro.disconnect(); });
        ro.observe(document.body);
      }
    };
    if (document.readyState === 'complete') start(); else window.addEventListener('load', start, { once: true });
  }

  const openLinkedDetails = () => {
    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;
    let details = target.closest('details'), changed = false;
    while (details) {
      if (!details.open) { details.open = true; changed = true; }
      details = details.parentElement && details.parentElement.closest('details');
    }
    if (changed) requestAnimationFrame(() => target.scrollIntoView({ block: 'start', behavior: 'instant' }));
  };
  openLinkedDetails();
  window.addEventListener('hashchange', openLinkedDetails);

  /* ---------------- footer: legal detail remains available without JavaScript ---------------- */
  const disclosures = $('.footer .disc');
  if (disclosures && !disclosures.closest('details')) {
    const details = document.createElement('details');
    details.className = 'footer-legal';
    const summary = document.createElement('summary');
    summary.textContent = 'Legal & disclosures';
    disclosures.before(details);
    details.append(summary, disclosures);
  }

  /* ---------------- clocks (footer) ---------------- */
  const clockFmt = (tz) => new Intl.DateTimeFormat('en-US', { timeZone: tz, hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const clocks = [];
  const bottom = $('.footer .bottom');
  if (bottom) {
    const span = document.createElement('span'); span.className = 'clocks';
    span.innerHTML = '<span><b>Seattle</b> <time data-tz="America/Los_Angeles"></time></span><span><b>New York</b> <time data-tz="America/New_York"></time></span>';
    bottom.appendChild(span);
    const fmts = $$('time[data-tz]', span).map(t => ({ t, f: clockFmt(t.dataset.tz) }));
    clocks.push(() => { const now = new Date(); fmts.forEach(({ t, f }) => { t.textContent = f.format(now).replace(/^24/, '00'); t.dateTime = now.toISOString(); }); });
  }
  if (clocks.length) { const tick = () => clocks.forEach(fn => fn()); tick(); setInterval(tick, 1000); }

  /* ---------------- manifesto — words light up as the paragraph passes through the viewport ---------------- */
  $$('[data-manifesto]').forEach(el => {
    const words = [];
    const walk = (node) => {
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(' ')); return; }
            const w = document.createElement('span'); w.className = 'mw'; w.textContent = p; words.push(w); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) walk(child);
      });
    };
    walk(el);
    if (prefersReduced) { words.forEach(w => w.classList.add('is-lit')); return; }
    let lit = -1, raf = 0;
    const update = () => {
      raf = 0;
      const r = el.getBoundingClientRect(), vh = window.innerHeight;
      // progress 0 → 1 as the block travels from 85% of the viewport up to 30%
      const p = Math.min(1, Math.max(0, (vh * 0.85 - r.top) / (r.height + vh * 0.55)));
      const n = Math.round(p * words.length);
      if (n === lit) return; lit = n;
      words.forEach((w, i) => w.classList.toggle('is-lit', i < n));
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    window.addEventListener('scroll', onScroll, { passive: true }); window.addEventListener('resize', onScroll); update();
  });

  /* ---------------- kinetic split text ---------------- */
  function splitWords(el) {
    let i = 0;
    const walk = (node) => {
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const parts = child.textContent.split(/(\s+)/);
          const frag = document.createDocumentFragment();
          parts.forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(' ')); return; }
            const w = document.createElement('span'); w.className = 'w';
            const wi = document.createElement('span'); wi.className = 'wi'; wi.style.setProperty('--i', i++); wi.textContent = p;
            w.appendChild(wi); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1 && !child.classList.contains('w')) walk(child);
      });
    };
    walk(el);
  }
  if (!prefersReduced) $$('[data-split]').forEach(splitWords);

  /* ---------------- reveal on scroll ---------------- */
  $$('[data-stagger]').forEach(el => { Array.from(el.children).forEach((c, i) => c.style.setProperty('--i', i)); if (!el.hasAttribute('data-reveal')) el.setAttribute('data-reveal', ''); });
  const revealEls = $$('[data-reveal]');
  let rio = null, tio = null;
  if ('IntersectionObserver' in window && !prefersReduced) {
    const show = el => { el.classList.add('is-in'); rio.unobserve(el); tio.unobserve(el); };
    rio = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) show(e.target); });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    // a block taller than the screen would wait for 8% of its own height and show blank paper until then (Platform's
    // full spec: half a phone screen; past ~11 screens, at a large text size, never): it comes in once its top is in
    tio = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting && e.boundingClientRect.height > (e.rootBounds ? e.rootBounds.height : window.innerHeight)) show(e.target); });
    }, { rootMargin: '0px 0px -16% 0px', threshold: 0 });
    revealEls.forEach(el => { el.classList.add('will-reveal'); rio.observe(el); tio.observe(el); });
  } else revealEls.forEach(el => el.classList.add('is-in'));
  // at once, with no transition: what a long jump passes over or lands on, and anything the keyboard focuses (focus
  // never lands on something still invisible). .is-instant lasts two frames; .is-cut stays (a skipped entrance never
  // plays later)
  const instant = el => { el.classList.add('is-instant'); requestAnimationFrame(() => requestAnimationFrame(() => el.classList.remove('is-instant'))); };
  function revealNow(el) {
    if (!el.classList.contains('will-reveal') || el.classList.contains('is-in')) return;
    el.classList.add('is-cut', 'is-in');
    instant(el);
    if (rio) { rio.unobserve(el); tio.unobserve(el); }
  }
  function revealRange(a, b) {
    const y = window.scrollY;
    revealEls.forEach(el => {
      if (!el.classList.contains('will-reveal') || el.classList.contains('is-in')) return;
      const r = el.getBoundingClientRect();
      if ((r.width || r.height) && r.top + y < b && r.bottom + y > a) revealNow(el);
    });
  }
  document.addEventListener('focusin', e => {
    // every reveal around the focused control: not started yet, or still fading in (the scroll that brought it near
    // started it a moment ago): both are finished now
    let el = e.target.closest && e.target.closest('.will-reveal');
    while (el) {
      if (!el.classList.contains('is-in')) revealNow(el);
      else if (el.getAnimations && el.getAnimations({ subtree: true }).some(a => a.playState === 'running' && a.transitionProperty)) instant(el);
      el = el.parentElement && el.parentElement.closest('.will-reveal');
    }
  });

  /* ---------------- off-screen bands: their CSS loops stop ----------------
     Every top-level band of the page carries .is-offscreen while no part of it is on screen; v2:nav pauses every CSS
     animation inside it (owners keep their loops on transform/opacity). Nothing runs where nobody can see it. */
  if ('IntersectionObserver' in window) {
    const oio = new IntersectionObserver(entries => entries.forEach(e => e.target.classList.toggle('is-offscreen', !e.isIntersecting)));
    $$('main > section, main > div, body > .footer').forEach(el => oio.observe(el));
  }

  /* ---------------- preloader: loader.js (the homepage loads it first among its scripts) ----------------
     It runs the loader and marks the page loaded (html.is-loaded, 'oxa:loaded') when the curtain lifts. Every other
     page is ready now; and should loader.js not have run (blocked, failed), its loader goes at once */
  const loaded = () => {
    $$('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
    root.classList.add('is-loaded');
    document.dispatchEvent(new CustomEvent('oxa:loaded'));
  };
  if (!root.classList.contains('is-loaded') && !document.body.classList.contains('is-loading')) {
    const stray = $('.loader');
    if (stray) stray.remove();
    loaded();
  }
  /* ---------------- figures: never counted, never rewritten ----------------
     A number on this site is only ever shown at its true value: the HTML holds it and nothing here writes another one
     into the DOM ([data-count] is inert; the count-up from zero is gone). A stat row's arrival is presentation only: its
     numerals rise out of a mask as the row reveals (v2:nav CSS), the text untouched. */
  // printing: the legal disclosures (folded into a <details> above) must reach the paper, whatever the reader has opened
  window.addEventListener('beforeprint', () => $$('details.footer-legal').forEach(d => { d.dataset.wasOpen = d.open ? '1' : ''; d.open = true; }));
  window.addEventListener('afterprint', () => $$('details.footer-legal').forEach(d => { d.open = d.dataset.wasOpen === '1'; }));

  /* ---------------- forms (no backend: mailto handoff or configured endpoint) ---------------- */
  $$('form[data-access]').forEach(form => {
    const result = $('.form-ok', form.parentElement);
    const endpoint = form.dataset.endpoint;
    const submit = $('button[type="submit"]', form);
    const submitLabel = $('[data-submit-label]', form);
    const errorBox = $('[data-form-error]', form);
    const note = $('[data-form-note]', form);
    const name = $('input[name="name"]', form);
    if (!result || !submit || !errorBox) {
      console.error('OpenEXA introduction form is missing its result, submit or error element.');
      return;
    }
    if (endpoint) {
      if (submitLabel) submitLabel.textContent = 'Send introduction';
      if (note) note.textContent = 'Your introduction will be submitted to OpenEXA when you send it.';
    }
    const choosePath = () => {
      const choice = document.getElementById(location.hash.slice(1));
      if (!choice) return;
      // the target may be a form option, or a description elsewhere on the page that names its option via data-interest
      const radio = form.contains(choice) ? $('input[type="radio"]', choice) : (choice.dataset.interest ? $(`input[type="radio"][value="${choice.dataset.interest}"]`, form) : null);
      if (radio) radio.checked = true;
    };
    choosePath();
    window.addEventListener('hashchange', choosePath);
    if (name) name.addEventListener('input', () => name.setCustomValidity(''));
    const showError = message => {
      errorBox.textContent = message;
      errorBox.hidden = false;
    };
    const showResult = sent => {
      const heading = $('[data-result-title]', result);
      const body = $('[data-result-body]', result);
      const mail = $('[data-mailto]', result);
      if (heading) heading.textContent = sent ? 'Introduction submitted.' : 'Your draft is ready.';
      if (body) body.textContent = sent
        ? 'Your introduction was accepted. You can return to the platform or edit your details to prepare another request.'
        : 'Open it in your email app, review it and press send. Preparing the draft has not submitted your details to OpenEXA.';
      if (mail) mail.hidden = sent;
      form.hidden = true;
      result.classList.add('show');
      result.focus();
    };
    const edit = $('[data-form-edit]', result);
    if (edit) edit.addEventListener('click', () => {
      result.classList.remove('show');
      form.hidden = false;
      if (name) name.focus();
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (name) name.setCustomValidity(name.value.trim() ? '' : 'Please enter your name.');
      if (!form.reportValidity() || submit.disabled) return;
      errorBox.hidden = true;
      const data = Object.fromEntries(Array.from(new FormData(form), ([key, value]) => [key, typeof value === 'string' ? value.trim() : value]));
      if (!endpoint) {
        const mail = $('[data-mailto]', result);
        if (!mail) {
          console.error('OpenEXA introduction form has no email-draft link.');
          showError('The email draft could not be prepared. Please reload and try again.');
          return;
        }
        // Windows mail handlers cut mailto URLs past ~2,000 characters, even mid-escape: shorten the message (then, if need be, the body) to fit
        const head = `mailto:${CONTACT}?subject=${encodeURIComponent('OpenEXA introduction - ' + data.interest)}&body=`;
        const fits = s => (head + encodeURIComponent(s)).length <= 1900;
        const bodyWith = msg => Object.entries(data).map(([key, value]) => `${key}: ${key === 'message' ? msg : value}`).join('\r\n');
        const cut = (text, wrap, mark) => { // longest whole-character prefix that fits, then the mark
          const ch = Array.from(text); let lo = 0, hi = ch.length;
          while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (fits(wrap(ch.slice(0, mid).join('') + mark))) lo = mid; else hi = mid - 1; }
          return wrap(ch.slice(0, lo).join('') + mark);
        };
        let body = bodyWith(data.message || '');
        if (!fits(body)) body = cut(data.message || '', bodyWith, '… [shortened to fit an email link: paste the rest here]');
        if (!fits(body)) body = cut(body, s => s, '…');
        mail.href = head + encodeURIComponent(body);
        showResult(false);
        return;
      }
      submit.disabled = true;
      form.setAttribute('aria-busy', 'true');
      if (submitLabel) submitLabel.textContent = 'Sending...';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      let response;
      try {
        response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal: controller.signal });
      } catch (error) {
        if (error instanceof TypeError || (error instanceof DOMException && error.name === 'AbortError')) {
          showError(controller.signal.aborted ? 'The request timed out. Your details are still here; please try again.' : 'The request could not reach OpenEXA. Check your connection and try again.');
          return;
        }
        throw error;
      } finally {
        clearTimeout(timeout);
        submit.disabled = false;
        form.removeAttribute('aria-busy');
        if (submitLabel) submitLabel.textContent = 'Send introduction';
      }
      if (!response.ok) {
        showError(`Your introduction was not accepted (HTTP ${response.status}). Your details are still here; please try again.`);
        return;
      }
      showResult(true);
    });
  });

  /* ---------------- 2D swarm (interior heroes & no-WebGL fallback) ---------------- */
  const canvas = $('canvas[data-swarm]');
  const inStory = canvas && canvas.closest('.story');
  // story.js decides on WebGL after first paint, so its fallback can arrive after this script has run
  if (canvas && (!inStory || document.documentElement.classList.contains('no-webgl'))) initSwarm(canvas);
  else if (inStory) document.addEventListener('story:no-webgl', () => initSwarm(canvas), { once: true });

  function initSwarm(cv) {
    const ctx = cv.getContext('2d', { alpha: true });
    cv.hidden = false;
    let W = 0, H = 0, dpr = 1, visible = true, frameId = 0, t = 0, last = performance.now();
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    const IVORY = [245, 242, 236], GREEN = [79, 203, 147], TAU = Math.PI * 2;
    const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
    // the overture's globe, drawn flat: the brand mark's latitude rows as fine beads (the back hemisphere is never drawn), two thin
    // orbits and one green proposal travelling the first of them
    const sphere = [], ROWS = 34;
    for (let r = 0; r < ROWS; r++) { const la = (78 - 156 * r / (ROWS - 1)) * Math.PI / 180, n = Math.max(8, Math.round(92 * Math.cos(la))); for (let k = 0; k < n; k++) sphere.push({ la, lo: (k + (r % 2) * 0.5) / n * TAU }); }
    const orbits = [{ r: 1.34, tiltX: 1.16, rotZ: -0.36 }, { r: 1.6, tiltX: 1.42, rotZ: 0.52 }];
    // up to 3x within a UHD budget, no side past 4096 px: a tall fallback stage stays under iOS Safari's ~16 MP canvas limit
    const PIXEL_BUDGET = 3840 * 2160;
    function resize() { const r = cv.getBoundingClientRect(); W = Math.max(1, Math.floor(r.width)); H = Math.max(1, Math.floor(r.height)); dpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(PIXEL_BUDGET / (W * H)), 4096 / W, 4096 / H); cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); if (prefersReduced) draw(0); }
    function rot(p, ax, ay, az) { let [x, y, z] = p; let c = Math.cos(ax), s = Math.sin(ax); let y1 = y * c - z * s, z1 = y * s + z * c; y = y1; z = z1; c = Math.cos(ay); s = Math.sin(ay); let x1 = x * c + z * s; z1 = -x * s + z * c; x = x1; z = z1; c = Math.cos(az); s = Math.sin(az); x1 = x * c - y * s; y1 = x * s + y * c; return [x1, y1, z]; }
    function draw() {
      ctx.clearRect(0, 0, W, H);
      const narrow = W < 960;
      const R = narrow ? W * 0.40 : Math.min(W * 0.20, H * 0.30), cx = narrow ? W * 0.62 : W * 0.735, cy = narrow ? H * 0.22 : H * 0.42;
      ctx.globalAlpha = narrow ? 0.55 : 1;
      mouse.x += (mouse.tx - mouse.x) * 0.04; mouse.y += (mouse.ty - mouse.y) * 0.04;
      const spin = t * 0.10 + mouse.x * 0.25, tilt = 0.32 + mouse.y * 0.12;
      const onOrbit = (o, a) => { const q = rot(rot([Math.cos(a) * o.r, Math.sin(a) * o.r, 0], o.tiltX, 0, o.rotZ), tilt, spin * 0.3, 0); return [cx + q[0] * R, cy + q[1] * R, q[2]]; };
      const hidden = (x, y, z) => z < 0 && Math.hypot((x - cx) / R, (y - cy) / R) < 0.99; // behind the globe
      // two thin orbits, one stroke each (their arcs behind the globe are left out)
      ctx.lineWidth = 1;
      orbits.forEach((o, oi) => {
        ctx.beginPath(); let pen = false;
        for (let i = 0; i <= 160; i++) { const [x, y, z] = onOrbit(o, i / 160 * TAU); if (hidden(x, y, z)) { pen = false; continue; } if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } }
        ctx.strokeStyle = rgba(oi ? IVORY : GREEN, oi ? 0.09 : 0.16); ctx.stroke();
      });
      // the globe: ~1.4 px beads, 12% ivory at the limb rising to ~32% facing the eye (fainter vanishes at 1x); beads of one alpha share one path
      const eb = new Map();
      sphere.forEach(pt => {
        const lo = pt.lo + spin, q = rot([Math.cos(pt.la) * Math.sin(lo), Math.sin(pt.la), Math.cos(pt.la) * Math.cos(lo)], tilt, 0, 0);
        if (q[2] <= 0.04) return;
        const k = Math.round((0.12 + 0.2 * Math.pow(q[2], 1.2)) * 100);
        let f = eb.get(k); if (!f) eb.set(k, f = []); f.push(cx + q[0] * R, cy + q[1] * R);
      });
      eb.forEach((f, k) => { ctx.beginPath(); for (let i = 0; i < f.length; i += 2) { ctx.moveTo(f[i] + 0.7, f[i + 1]); ctx.arc(f[i], f[i + 1], 0.7, 0, TAU); } ctx.fillStyle = rgba(IVORY, k / 100); ctx.fill(); });
      // one proposal: a green ring travelling the first orbit (it passes behind the globe)
      const [px, py, pz] = onOrbit(orbits[0], t * 0.32 + 1.1);
      if (!hidden(px, py, pz)) { ctx.beginPath(); ctx.arc(px, py, 3.4, 0, TAU); ctx.strokeStyle = rgba(GREEN, 0.9); ctx.lineWidth = 1.2; ctx.stroke(); }
      const g = ctx.createRadialGradient(cx, cy, R * 0.94, cx, cy, R * 1.1); g.addColorStop(0, rgba(IVORY, 0.035)); g.addColorStop(1, rgba(IVORY, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.1, 0, TAU); ctx.fill();
      ctx.globalAlpha = 1;
    }
    // the loop runs only while the canvas is on screen in a visible tab
    function frame(now) { frameId = 0; if (!visible || document.hidden) return; const dt = Math.min(0.05, (now - last) / 1000); last = now; t += dt; draw(); request(); }
    function request() { if (!frameId && visible && !document.hidden) frameId = requestAnimationFrame(frame); }
    function stop() { cancelAnimationFrame(frameId); frameId = 0; last = performance.now(); }
    resize(); window.addEventListener('resize', resize);
    // a move to a display with another pixel ratio changes no CSS size: watch the ratio itself, re-arming each time
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    if (!prefersReduced) {
      window.addEventListener('pointermove', (e) => { mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2; mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2; }, { passive: true });
      if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) request(); else stop(); }, { threshold: 0 }).observe(cv);
      document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else request(); });
      request();
    } else draw(0);
  }
})();
