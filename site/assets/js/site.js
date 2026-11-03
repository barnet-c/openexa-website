/* OpenEXA — shared behaviour
   nav (chapter readout, progress, menu sheet) · footer · clocks · loader hand-off · kinetic type · reveals
   · 2D swarm fallback. Page-only behaviour lives beside its page: access.js (the request form), company.js (the
   manifesto); the instruments have their own engines. */
(function () {
  'use strict';

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)'); // read live where motion is optional
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pad = (n) => String(n).padStart(2, '0');
  const clamp01 = (v) => v < 0 ? 0 : v > 1 ? 1 : v;
  const root = document.documentElement;
  const unhash = h => { try { return decodeURIComponent(h); } catch (e) { return h; } }; // (#% must not stop the script)

  /* ---------------- nav: the frame of every page ---------------- */
  const nav = $('.nav');
  const darkStart = document.body.dataset.nav === 'dark-start';
  const themeMeta = $('meta[name="theme-color"]');
  const story = $('.story');
  const paper = story && $('.story-paper', story);
  // on Home this runs after story.js: an overture not started by now never will (site.css's net)
  if (story && !root.classList.contains('story-ready') && !root.classList.contains('no-webgl')) root.classList.add('story-failed');
  let paperTop = null, paperWatch = 0;
  const toggle = $('.nav-toggle');
  const sheet = $('.nav-sheet');
  let navH = 72, vh = 0, maxScroll = 1, clearUntil = -1, bands = [], navRaf = 0, menuOpen = false;

  const pageKey = path => path.replace(/(\/index)?(\.html)?\/*$/, '').split('/').pop() || 'index';
  const here = pageKey(location.pathname);
  const section = /\/research\/[^/]+$/.test(location.pathname) ? 'research' : here; // an article sits under Research
  // marks where the reader is (the footer: that page only); never removes a mark the page states
  // the blog has no link of its own in the bar: it reads under Research, its front door (a2), marked as the section
  const blog = /^\/blog(\/|$)/.test(location.pathname);
  $$('.nav-links a, .nav-sheet a, .nav .btn, .footer ul a').forEach(a => {
    const k = pageKey(a.pathname);
    if (a.host !== location.host || a.hasAttribute('aria-current')) return;
    if (a.closest('.footer') ? k === here && !a.hash : k === here || k === section) a.setAttribute('aria-current', 'page');
    else if (blog && k === 'research' && !a.closest('.footer')) a.setAttribute('aria-current', 'true');
  });

  /* chapters: [data-chapter] sections, else numbered sections (.sec-head), else an article's table of contents. */
  const headOf = el => { const head = $('.sec-head', el); return head && head.closest('section') === el ? head : null; };
  const labOf = el => { const lab = headOf(el) && $('.lab', headOf(el)); return lab ? lab.textContent.trim() : ''; };
  const shortOf = el => (el.dataset.chapterShort || '').trim();
  let chapters = $$('section[data-chapter]').map((el, i) => ({ el, n: el.dataset.n || pad(i + 1), title: labOf(el) || el.dataset.chapter, short: shortOf(el) }));
  if (chapters.length < 2) chapters = $$('main section').map(el => {
    const head = headOf(el), idx = head && $('.idx', head), lab = head && $('.lab', head);
    return idx && lab ? { el, n: idx.textContent.trim(), title: lab.textContent.trim(), short: shortOf(el) } : null;
  }).filter(Boolean);
  if (chapters.length < 2) chapters = $$('.toc a[href^="#"]').map((a, i) => {
    const el = document.getElementById(unhash(a.hash.slice(1)));
    return el ? { el, n: pad(i + 1), title: a.textContent.trim(), short: '', toc: true, scope: el.closest('article, .article') } : null;
  }).filter(Boolean);
  if (chapters.length < 2) chapters = [];
  if (!nav || !$('.brand', nav)) chapters = [];
  chapters.forEach((c, k) => {
    c.k = k;
    if (!c.el.id) { let id = 'chapter-' + (c.n.replace(/[^\w-]/g, '') || k); while (document.getElementById(id)) id += '-'; c.el.id = id; }
  });
  // an address that names a section given its id just now
  if (chapters.length && location.hash && chapters.some(c => '#' + c.el.id === unhash(location.hash)) && window.scrollY < 2) {
    const target = document.getElementById(unhash(location.hash.slice(1)));
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
      '<button class="nav-ch-btn is-intro" type="button" aria-expanded="false" aria-controls="nav-ch-panel"><span class="nav-ch-roll"></span>' +
      '<svg class="nav-ch-caret" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.6l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.3"/></svg></button>' +
      '<div class="nav-ch-panel" id="nav-ch-panel"><ol class="nav-ch-list"></ol>' +
      '<a class="nav-ch-top" href="#"><svg viewBox="0 0 10 10" aria-hidden="true"><path d="M5 8.5V1.8M2 4.6l3-3 3 3" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>Back to top</a></div>';
    brand.after(wrap);
    ui.btn = $('.nav-ch-btn', wrap); ui.roll = $('.nav-ch-roll', wrap); ui.panel = $('.nav-ch-panel', wrap); ui.list = $('.nav-ch-list', wrap);
    chapters.forEach(c => {
      const li = document.createElement('li'), a = document.createElement('a');
      a.href = '#' + c.el.id; a.dataset.k = c.k;
      a.innerHTML = '<span class="n"></span><span class="t"></span><span class="p"><b></b></span>';
      $('.n', a).textContent = c.n; $('.t', a).textContent = c.title;
      li.appendChild(a); ui.list.appendChild(li); c.li = li; c.a = a; c.bar = $('.p b', a);
    });
  }

  /* the readout: the line rolls up to the next chapter (down when going back); its width follows. It shows the chapter's
     number only (1 Nov: no running head; the title is in the list); at the top of the page it is empty (site.css shows
     it there only to a keyboard). */
  const MODES = ['is-short', 'is-compact'];
  const total = () => pad(Math.max(0, ...chapters.map(c => /^\d+$/.test(c.n) ? +c.n : 0)) || chapters.length);
  function lineFor(k, mode) {
    const line = document.createElement('span');
    line.className = 'nav-ch-line';
    if (k < 0) {
      line.classList.add('is-intro');
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
  /* phones: the full label wherever it fits; else the section's short form; else '§NN / total'. The bar from 961 to 1279
     px (a2): the name, else the short form, else the number, in the room the links leave. */
  const narrowMQ = window.matchMedia('(max-width: 960px)'), phoneMQ = window.matchMedia('(max-width: 600px)');
  const midMQ = window.matchMedia('(min-width: 961px) and (max-width: 1279.98px)');
  let fitKey = '';
  function fitModes() {
    if (!ui.roll || !live.length) return;
    const key = [window.innerWidth, live.map(c => c.k).join(), document.fonts ? document.fonts.status : ''].join('|');
    if (key === fitKey) return;
    fitKey = key;
    live.forEach(c => { c.mode = 'full'; });
    const links = midMQ.matches && $('.nav-links', nav);
    if (narrowMQ.matches || links) {
      const box = document.createElement('span'); box.className = 'nav-ch-measure'; box.setAttribute('aria-hidden', 'true');
      const forms = [];
      live.forEach(c => { forms.push([c, 'full', lineFor(c.k, 'full')]); if (c.short && c.short !== c.title) forms.push([c, 'short', lineFor(c.k, 'short')]); });
      forms.forEach(f => box.appendChild(f[2]));
      ui.btn.appendChild(box);
      const r0 = ui.roll.getBoundingClientRect();
      // the bar: up to the links, less the bar's gap and the button's caret (the roll shrinks before anything moves)
      const avail = links ? Math.min(parseFloat(getComputedStyle(ui.roll).maxWidth) || 1e4, links.getBoundingClientRect().left
          - (parseFloat(getComputedStyle(links.parentNode).columnGap) || 24) - (ui.btn.getBoundingClientRect().right - r0.right) - r0.left - 2)
        : ui.wrap.getBoundingClientRect().width - (ui.btn.getBoundingClientRect().width - r0.width) - 1;
      const w = new Map(forms.map(([c, m, l]) => [c.k + m, l.getBoundingClientRect().width]));
      box.remove();
      let compact = false;
      live.forEach(c => {
        if (c.toc && phoneMQ.matches) { compact = true; c.fit = false; }
        else if (w.get(c.k + 'full') <= avail) c.mode = 'full';
        else if (w.has(c.k + 'short') && w.get(c.k + 'short') <= avail) c.mode = 'short';
        else { compact = true; c.fit = false; }
      });
      // the compact form is a number: a chapter without one
      if (compact) live.forEach(c => { if ((!links && /^\d+$/.test(c.n)) || c.fit === false) c.mode = 'compact'; });
      live.forEach(c => { delete c.fit; });
    }
    const c = chapters[shownK];
    if (ui.line && c) { MODES.forEach(m => ui.line.classList.toggle(m, m === 'is-' + c.mode)); }
    nameReadout();
  }
  /* the readout's accessible name starts with exactly what it shows */
  function nameReadout() {
    if (!ui.btn || shownK < -1) return;
    const c = chapters[shownK];
    ui.btn.setAttribute('aria-label', `${c ? `${c.n} ${c.title} · ` : ''}On this page: ${chapters.length} chapters`);
  }
  function showChapter(k) {
    if (!ui.roll || k === shownK) return;
    const dir = k > shownK ? 1 : -1, first = shownK === -3;
    shownK = k;
    nameReadout();
    chapters.forEach(c => { if (c.k === k) c.a.setAttribute('aria-current', 'true'); else c.a.removeAttribute('aria-current'); });
    if (ui.roll.getAnimations) ui.roll.getAnimations({ subtree: true }).forEach(a => a.cancel());
    const w0 = first ? 0 : ui.roll.getBoundingClientRect().width; // the width on screen now, before anything leaves
    Array.from(ui.roll.children).forEach(ch => ch.remove());
    const old = ui.line, neu = lineFor(k);
    ui.line = neu;
    ui.btn.classList.toggle('is-intro', k < 0); // nothing to show above the first chapter (site.css)
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
    // over a pinned overture the bar stays clear until the stage starts to leave
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
    // the bar's surface: the ground of the section that meets its lower edge
    let dark = false, band = null;
    const edge = y + navH + 1;
    for (const b of bands) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    // the overture's exit: its rising paper
    let overPaper = false;
    if (band && band.el === story && paper) {
      const r = getComputedStyle(paper).visibility !== 'hidden' ? paper.getBoundingClientRect() : null;
      overPaper = !!r && r.height > 0 && r.top <= navH + 1 && r.bottom > navH;
      const top = r && r.height > 0 ? Math.round(r.top) : null;
      if (top !== paperTop) { paperTop = top; paperWatch = 8; }
      if (paperWatch > 0) { paperWatch--; queue(); }
    } else { paperTop = null; paperWatch = 0; }
    if (overPaper) dark = false;
    // a dark-start page whose dark opening has scrolled away has a paper ground
    if (darkStart) { const opening = bands[0] && bands[0].dark ? bands[0] : null; root.classList.toggle('is-paper-root', !!opening && y >= opening.bottom); }
    // the overture as a static sequence (story-tiny, under 300 px tall) scrolls its text under the bar: glass once moved
    const clear = y <= (root.classList.contains('story-tiny') ? 16 : clearUntil) && !menuOpen && !overPaper;
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
    if (open && narrowMQ.matches) { // phones and tablets: the chapters are in the menu sheet, and focus goes in with them
      opener = ui.btn; setMenu(true);
      requestAnimationFrame(() => { if (menuOpen && !sheet.contains(document.activeElement)) ($('.nav-ch-list a[aria-current]', sheet) || $('.nav-ch-list a', sheet) || toggle).focus(); });
      return;
    }
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
      if (e.key === 'Escape') { e.preventDefault(); if (menuOpen) { const o = opener; setMenu(false); if (!o) toggle.focus(); } else setPanel(false, true); } // in the sheet: the sheet closes
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
      closeSheetForJump();
      // focus follows the reader to the chapter, onto its heading
      const focus = () => focusInto(c.el);
      if (!jumpTo(c.el, a.hash, e, focus)) setTimeout(focus, 0);
    });
    $('.nav-ch-top', ui.wrap).addEventListener('click', e => {
      e.preventDefault(); setPanel(false, true); closeSheetForJump();
      if (!jumpTo(null)) window.scrollTo({ top: 0, behavior: reducedMQ.matches ? 'instant' : 'smooth' });
    });
    document.addEventListener('pointerdown', e => { if (chOpen && !ui.wrap.contains(e.target)) setPanel(false); });
    ui.wrap.addEventListener('focusout', e => { if (chOpen && e.relatedTarget && !ui.wrap.contains(e.relatedTarget)) setPanel(false); });
  }

  /* the menu sheet (phones, tablets): a popover — it opens without JavaScript */
  const popover = !!(sheet && sheet.hasAttribute('popover') && typeof sheet.showPopover === 'function');
  let opener = null; // the readout's pill, when it opened the sheet: focus returns to it (r5)
  function syncMenu(open) {
    if (open === menuOpen) return;
    menuOpen = open;
    document.body.classList.toggle('nav-open', open);
    if (nav) nav.classList.toggle('nav--menu', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));
    if (ui.btn && sheet && ui.panel && ui.panel.parentElement === sheet) ui.btn.setAttribute('aria-expanded', String(open));
    $$('body > main, body > .footer').forEach(el => { el.inert = open; });
    if (open) setPanel(false);
    update();
    if (!open && opener) {
      const o = opener, a = document.activeElement; opener = null;
      if (!a || a === document.body || sheet.contains(a)) (o.checkVisibility && !o.checkVisibility({ visibilityProperty: true }) ? toggle : o).focus();
    }
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
      if (e.key === 'Escape' && !popover) { const o = opener; setMenu(false); if (!o) toggle.focus(); }
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
  // (v2x) phones and tablets have one menu: the readout is its label, and the sheet holds this page's chapters above
  // the site's pages (the chapter list moves into the sheet under 961 px and back above it)
  function closeSheetForJump() {
    if (!menuOpen || !sheet) return;
    sheet.classList.add('is-snap'); // gone before a jump takes its still
    setMenu(false);
    setTimeout(() => sheet.classList.remove('is-snap'), 80);
  }
  function placePanel() {
    if (!ui.panel || !sheet) return;
    const inSheet = narrowMQ.matches;
    if (inSheet && ui.panel.parentElement !== sheet) { setPanel(false); sheet.prepend(ui.panel); }
    else if (!inSheet && ui.panel.parentElement !== ui.wrap) { setMenu(false); ui.wrap.appendChild(ui.panel); }
    sheet.classList.toggle('has-ch', inSheet); // this page's chapters (body step), then the site's pages (larger): no head rows (1 Nov)
    ui.btn.setAttribute('aria-controls', inSheet ? sheet.id : ui.panel.id);
    ui.btn.setAttribute('aria-expanded', String(inSheet ? menuOpen : chOpen));
  }
  placePanel();
  narrowMQ.addEventListener('change', placePanel);

  /* ---------------- long jumps: never through blank paper ---------------- */
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
  // a jump to an element (null: the top) longer than 1.5 screens is handled here (returns true)
  function jumpTo(el, hash, e, after) {
    const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
    const y0 = window.scrollY, max = Math.max(0, root.scrollHeight - window.innerHeight);
    const to = el ? Math.max(0, Math.min(max, el.getBoundingClientRect().top + y0 - sp)) : 0;
    if (Math.abs(to - y0) <= 1.5 * window.innerHeight) return false;
    if (e) e.preventDefault();
    cut(to, () => {
      // the address changes as an anchor jump's would, and so does everything that listens for it
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
  // any other link to a place on this page
  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest('a[href*="#"]');
    if (!a || (a.target && a.target !== '_self') || a.closest('.nav-ch, .nav-sheet')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname || url.search !== location.search || url.hash.length < 2) return;
    const el = document.getElementById(unhash(url.hash.slice(1)));
    if (!el || el.closest('details:not([open])')) return; // the browser opens a closed <details> for its target
    jumpTo(el, url.hash, e, () => focusInto(el)); // as after an anchor jump, the next Tab continues from the destination
  });
  // where focus lands after a jump: a control or an element that takes focus itself
  function focusInto(el) {
    let t = el;
    if (el.tagName === 'SECTION') {
      const h = $$('h2', el).find(x => x.getClientRects().length && x.closest('section') === el);
      if (h) t = h;
    }
    if (!t.matches('a[href], button, input, select, textarea, summary, [tabindex]')) { t.setAttribute('tabindex', '-1'); t.classList.add('nav-ch-target'); }
    t.focus({ preventScroll: true });
  }

  /* ---------------- page transitions: leaving the overture fades like every other page ----------------
     (award a1) A WebGL canvas is not kept for the outgoing snapshot, so leaving the stage used to skip the transition (a
     hard cut). Now the stage's canvases are hidden for the snapshot (html.vt-out, site.css): the dark stage and its copy
     fade out as any page does. Back from the bfcache, the class is gone before the page shows. */
  const stageEl = $('.story-stage');
  if (stageEl) {
    window.addEventListener('pageswap', e => {
      if (!e.viewTransition) return;
      const r = stageEl.getBoundingClientRect();
      if (r.height > 0 && r.bottom > 0 && r.top < window.innerHeight) root.classList.add('vt-out');
    });
    window.addEventListener('pageshow', () => root.classList.remove('vt-out'));
    window.addEventListener('pagereveal', () => root.classList.remove('vt-out'));
  }

  if (nav) {
    // (v2x) no layout read in a script task: every measure waits for the frame, which lays out anyway. (r2: fonts.ready
    // resolves as a microtask right after this script when the faces are in, and oxa:loaded fires inside it on pages
    // without a loader; both forced the page's first full layout inside site.js's task: 340 ms at 4x on Lifecycles.)
    let mRaf = 0;
    const measureSoon = () => { if (!mRaf) mRaf = requestAnimationFrame(() => { mRaf = 0; measure(); }); };
    // (a2: deferring this to idle after the first paint was measured worse, LoAF at 4x: the reveal's first-frame writes
    // invalidate the layout, so a later read forces a second one; here it shares the page's one first layout)
    measureSoon();
    window.addEventListener('scroll', queue, { passive: true });
    window.addEventListener('resize', measure);
    window.addEventListener('load', measureSoon);
    ['story:gl-ready', 'story:no-webgl', 'oxa:loaded'].forEach(t => document.addEventListener(t, measureSoon));
    // content that changes height
    if ('ResizeObserver' in window) new ResizeObserver(measureSoon).observe(document.body);
    // (reading document.fonts.ready updates style and layout in Chromium: it too waits for the frame)
    if (document.fonts) requestAnimationFrame(() => document.fonts.ready.then(measureSoon));
  }
  /* ---------------- the reader's place: kept through resizes, and a deep link's landing kept after late layout ---------------- */
  let anchor = null, settleUntil = 0, lastInput = 0, lastW = 0;
  const inFlow = el => { const p = getComputedStyle(el).position; return p !== 'fixed' && p !== 'sticky' && p !== 'absolute'; };
  // where layout puts an element (viewport y), ignoring transforms
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
      // the line falls in a gap: inside a band or a section, the band/section itself is the place
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
    requestAnimationFrame(() => { lastW = window.innerWidth; setTimeout(pickAnchor, 0); });
    document.addEventListener('oxa:jump', () => setTimeout(pickAnchor, 0));
  }
  // a deep link lands at the bar after load and again as the overture settles; only the reader's input stops it
  const hashId = () => unhash(location.hash.slice(1));
  const deep = location.hash.length > 1 && document.getElementById(hashId());
  if (deep && nav) {
    let quietTo = 0, busy = false, ro = null;
    const realign = (h0, n) => requestAnimationFrame(() => requestAnimationFrame(() => {
      if (lastInput) { busy = false; return; }
      const h = root.scrollHeight;
      if (h !== h0 && n < 60) { realign(h, n + 1); return; }
      busy = false;
      const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
      if (Math.abs(deep.getBoundingClientRect().top - sp) > 1) deep.scrollIntoView({ block: 'start', behavior: 'instant' });
    }));
    const land = () => { if (!busy && !lastInput) { busy = true; realign(root.scrollHeight, 0); } };
    const watch = () => {
      if (lastInput) return;
      quietTo = performance.now() + 2500;
      land();
      if (!ro && 'ResizeObserver' in window) {
        ro = new ResizeObserver(() => { if (performance.now() < quietTo && !lastInput) land(); else { ro.disconnect(); ro = null; } });
        ro.observe(document.body);
      }
    };
    if (document.readyState === 'complete') watch(); else window.addEventListener('load', watch, { once: true });
    ['story:gl-ready', 'story:no-webgl', 'oxa:loaded'].forEach(t => document.addEventListener(t, watch));
  }

  const openLinkedDetails = () => {
    const id = hashId();
    const target = id && document.getElementById(id);
    if (!target) return;
    let details = target.closest('details'), changed = false;
    const inFold = !!details;
    while (details) {
      if (!details.open) { details.open = true; changed = true; }
      details = details.parentElement && details.parentElement.closest('details');
    }
    // a link into a fold also takes focus there (G-11); a followed link finds the fold already opened by the browser
    if (inFold) requestAnimationFrame(() => { if (changed) target.scrollIntoView({ block: 'start', behavior: 'instant' }); if (target.tabIndex < 0) target.tabIndex = -1; target.focus({ preventScroll: true }); });
  };
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
  openLinkedDetails(); // after the fold exists

  /* ---------------- clocks (footer): hours and minutes, set on the minute; New York is market time ---------------- */
  const bottom = $('.footer .bottom');
  if (bottom) {
    const span = document.createElement('span'); span.className = 'clocks';
    span.innerHTML = '<span><b>Seattle</b> <time data-tz="America/Los_Angeles"></time></span> <span><b>New York <small>· market time</small></b> <time data-tz="America/New_York"></time></span>';
    bottom.appendChild(span);
    const fmts = $$('time[data-tz]', span).map(t => ({ t, f: new Intl.DateTimeFormat('en-US', { timeZone: t.dataset.tz, hourCycle: 'h23', hour: '2-digit', minute: '2-digit' }) }));
    const tick = () => { const now = new Date(); fmts.forEach(({ t, f }) => { t.textContent = f.format(now); t.dateTime = now.toISOString(); }); setTimeout(tick, 60050 - now % 60000); };
    tick();
  }

  /* ---------------- type: the serif's hyphen ----------------
     Instrument Serif's U+002D has wide side bearings ("Domain - Specific") and its file has no U+2010 (a U+2010 is drawn
     by whatever serif the system has). In display text the hyphen stays U+002D, so find-in-page and copy match a typed
     '-', inside a .hy span whose margins take the bearings in (site.css); a static U+2010 becomes U+002D again. No style is
     read now: in the first frame a heading that is not in the serif gets its plain hyphen back. */
  const SERIF_TEXT = 'h1, h2, h3, .display-1, .display-2, .display-3, .manifesto, .footer .tag';
  const HY = /(\p{L})[-\u2010](?=\p{L})/u;
  function serifHyphens(root) {
    const hosts = [];
    $$(SERIF_TEXT, root).forEach(el => {
      if (el.closest('pre, code, kbd, samp, .mono, [data-keep-hyphens], .hy')) return;
      const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), hits = [];
      for (let n = tw.nextNode(); n; n = tw.nextNode()) if (HY.test(n.data)) hits.push(n);
      if (!hits.length) return;
      hosts.push(el);
      hits.forEach(n => {
        for (let m = HY.exec(n.data); m; m = HY.exec(n.data)) {
          const rest = n.splitText(m.index + m[1].length), hy = document.createElement('span');
          rest.data = rest.data.slice(1); hy.className = 'hy'; hy.textContent = '-'; rest.before(hy); n = rest;
        }
      });
    });
    if (hosts.length) requestAnimationFrame(() => hosts.filter(el => !/Instrument Serif/.test(getComputedStyle(el).fontFamily.split(',')[0]))
      .forEach(el => el.querySelectorAll('.hy').forEach(hy => hy.replaceWith('-'))));
  }
  serifHyphens(document);

  /* ---------------- kinetic split text ---------------- */
  function splitWords(el) {
    if (el.dataset.split === 'done') return;
    el.dataset.split = 'done';
    let i = 0;
    const walk = (node) => {
      let wi = null; // the word being built: a .hy hyphen and the text after it stay in it (one word, no new break)
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const parts = child.textContent.split(/([ \t\n\r\f]+)/); // U+00A0 stays in its word
          const frag = document.createDocumentFragment();
          parts.forEach(p => {
            if (!p) return;
            if (/^[ \t\n\r\f]+$/.test(p)) { frag.appendChild(document.createTextNode(' ')); wi = null; return; }
            if (wi) { wi.append(p); return; }
            const w = document.createElement('span'); w.className = 'w';
            wi = document.createElement('span'); wi.className = 'wi'; wi.style.setProperty('--i', i++); wi.textContent = p;
            w.appendChild(wi); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1 && child.classList.contains('hy') && wi) wi.append(child);
        else { wi = null; if (child.nodeType === 1 && !child.classList.contains('w')) walk(child); }
      });
    };
    walk(el);
  }

  /* ---------------- reveal on scroll ----------------
     (v2x) The first screen is never hidden, faded or split (the overture's beats excepted); sorted in the first frame.
     Below it a block fades in as its top crosses 96% of the screen; a headline is split 1.5 screens ahead. Without
     JavaScript, and under reduced motion, nothing is hidden and nothing is split. */
  $$('[data-stagger]').forEach(el => { Array.from(el.children).forEach((c, i) => c.style.setProperty('--i', i)); if (!el.hasAttribute('data-reveal')) el.setAttribute('data-reveal', ''); });
  const storySplit = $$('.story [data-split]');
  if (!prefersReduced) storySplit.forEach(splitWords);
  const watched = $$('[data-reveal], [data-split]').filter(el => !el.closest('.story'));
  let rio = null, sio = null;
  if ('IntersectionObserver' in window && !prefersReduced) requestAnimationFrame(() => {
    const fold = window.innerHeight;
    // every read first, then every write. A chapter that starts below the fold makes all its elements "later" from its own
    // top: reading each element's rect inside a content-visibility chapter would force that chapter's layout (a2, home)
    const tops = new Map(), secTop = s => { if (!tops.has(s)) tops.set(s, s.getBoundingClientRect().top); return tops.get(s); };
    const rects = watched.map(el => { const s = el.closest('main > section'); return s && secTop(s) >= fold - 1 ? { top: secTop(s), width: 1, height: 1 } : el.getBoundingClientRect(); });
    const later = watched.filter((el, k) => { const r = rects[k]; return (r.width || r.height) && r.top >= fold - 1; });
    watched.forEach(el => { if (!later.includes(el)) el.classList.add('is-in'); });
    // a drawn line's dash is its drawing's scale on screen while it draws (site.css .dr; a2: whole at any size)
    const drawScale = el => $$('.dr', el).forEach(d => {
      const svg = d.ownerSVGElement, m = svg && !svg.style.getPropertyValue('--dr-k') && svg.getScreenCTM();
      if (m) svg.style.setProperty('--dr-k', Math.max(1, Math.hypot(m.a, m.b) * 1.02 + .02).toFixed(3));
    });
    const show = el => { drawScale(el); el.classList.add('is-in'); rio.unobserve(el); };
    rio = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) show(e.target); });
    }, { rootMargin: '0px 0px -4% 0px', threshold: 0 });
    sio = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { sio.unobserve(e.target); if (!e.target.classList.contains('is-in')) splitWords(e.target); } });
    }, { rootMargin: '0px 0px 150% 0px', threshold: 0 });
    later.forEach(el => {
      if (el.hasAttribute('data-split')) sio.observe(el);
      if (el.hasAttribute('data-reveal')) { el.classList.add('will-reveal'); instant(el); } // hidden at once: no fade-out off screen (r5)
      rio.observe(el);
    });
  }); else watched.forEach(el => el.classList.add('is-in'));
  // at once, with no transition: what a long jump passes over or lands on
  const instant = el => { el.classList.add('is-instant'); requestAnimationFrame(() => requestAnimationFrame(() => el.classList.remove('is-instant'))); };
  function revealNow(el) {
    if (el.classList.contains('is-in')) return;
    el.classList.add('is-cut', 'is-in');
    instant(el);
    if (rio) rio.unobserve(el);
    if (sio) sio.unobserve(el);
  }
  function revealRange(a, b) {
    const y = window.scrollY;
    watched.forEach(el => {
      if (el.classList.contains('is-in')) return;
      const r = el.getBoundingClientRect();
      if ((r.width || r.height) && r.top + y < b && r.bottom + y > a) revealNow(el);
    });
  }
  document.addEventListener('focusin', e => {
    // every reveal around the focused control: not started yet, or still fading in
    let el = e.target.closest && e.target.closest('.will-reveal');
    while (el) {
      if (!el.classList.contains('is-in')) revealNow(el);
      else if (el.getAnimations && el.getAnimations({ subtree: true }).some(a => a.playState === 'running' && a.transitionProperty)) instant(el);
      el = el.parentElement && el.parentElement.closest('.will-reveal');
    }
  });

  /* ---------------- off-screen bands: their CSS loops stop ---------------- */
  if ('IntersectionObserver' in window) {
    const oio = new IntersectionObserver(entries => entries.forEach(e => e.target.classList.toggle('is-offscreen', !e.isIntersecting)));
    $$('main > section, main > div, body > .footer').forEach(el => oio.observe(el));
  }

  /* ---------------- preloader: loader.js (the homepage loads it first among its scripts) ---------------- */
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
  /* ---------------- figures: never counted, never rewritten ---------------- */
  // printing: the legal disclosures (folded into a <details> above) must reach the paper
  window.addEventListener('beforeprint', () => $$('details.footer-legal').forEach(d => { d.dataset.wasOpen = d.open ? '1' : ''; d.open = true; }));
  window.addEventListener('afterprint', () => $$('details.footer-legal').forEach(d => { d.open = d.dataset.wasOpen === '1'; }));

  /* ---------------- 2D swarm (interior heroes & no-WebGL fallback) ---------------- */
  // The overture's globe drawn flat: the 404 and, when WebGL is missing, S0.
  const canvas = $('canvas[data-swarm]');
  const inStory = canvas && canvas.closest('.story');
  // story.js decides on WebGL after first paint, so its fallback can arrive after this script has run
  if (canvas && (!inStory || document.documentElement.classList.contains('no-webgl'))) initSwarm(canvas);
  else if (inStory) document.addEventListener('story:no-webgl', () => initSwarm(canvas), { once: true });

  function initSwarm(cv) {
    const ctx = cv.getContext('2d', { alpha: true });
    if (!ctx) return;
    cv.hidden = false;
    const story = cv.closest('.story');
    // the copy it keeps clear of: S0's beat text and figures, or the 404's eyebrow, h1, lede
    const copy = story ? $$('.beat-0 .beat-text > *, .beat-0 .hero-stats', story) : $$('.container > *', cv.parentElement);
    const strict = story ? [] : copy.filter(el => el.matches('h1, .lede')); // never under these, whatever the room
    const IVORY = [245, 242, 236], GREEN = [79, 203, 147], RED = [217, 103, 93], TAU = Math.PI * 2;
    const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
    const orbits = [{ r: 1.34, tiltX: 1.16, rotZ: -0.36 }, { r: 1.6, tiltX: 1.42, rotZ: 0.52 }];
    // up to 3x within a UHD budget, no side past 4096 px
    const PIXEL_BUDGET = 3840 * 2160;
    // the drift: a clock (tau, in seconds of motion) that runs only while awake.
    const WAKE = 5000, RAMP = 0.6, EASE = 1.5, P = 4, FALL = 2.6, PHASE = 0.3;
    let W = 0, H = 0, dpr = 1, G = null, sphere = [], visible = true, frameId = 0, tau = 0, plan = null, last = 0;
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    const rot = (p, ax, ay, az) => { let [x, y, z] = p; let c = Math.cos(ax), s = Math.sin(ax); let y1 = y * c - z * s, z1 = y * s + z * c; y = y1; z = z1; c = Math.cos(ay); s = Math.sin(ay); let x1 = x * c + z * s; z1 = -x * s + z * c; x = x1; z = z1; c = Math.cos(az); s = Math.sin(az); x1 = x * c - y * s; y1 = x * s + y * c; return [x1, y1, z]; };
    const view = (tt) => ({ spin: tt * 0.10 + mouse.x * 0.25, tilt: 0.32 + mouse.y * 0.12 });
    const onOrbit = (o, a, v) => { const q = rot(rot([Math.cos(a) * o.r, Math.sin(a) * o.r, 0], o.tiltX, 0, o.rotZ), v.tilt, v.spin * 0.3, 0); return [G.cx + q[0] * G.R, G.cy + q[1] * G.R, q[2]]; };
    const hidden = (x, y, z) => z < 0 && Math.hypot((x - G.cx) / G.R, (y - G.cy) / G.R) < 0.99; // behind the globe
    const ringAt = (tt) => onOrbit(orbits[0], tt * 0.32 + 1.1, view(tt));
    // the reject that leaves the ring at clock te: where it starts, its sideways drift and its drop
    function reject(te) {
      const [x0, y0, z0] = ringAt(te);
      if (hidden(x0, y0, z0) || x0 < 12 || x0 > W - 12) return null;
      const drop = Math.min(G.R * 0.5, G.floor - y0 - 10);
      return drop < G.R * 0.22 ? null : { x0, y0, dx: (x0 >= G.cx ? 1 : -1) * G.R * 0.14, drop };
    }
    // a composed still: the ring in front and on the canvas, the latest reject well clear of it
    function good(tt) {
      const te = Math.floor((tt - PHASE) / P) * P + PHASE, u = (tt - te) / FALL;
      if (u < 0.55 || u > 0.68 || !reject(te)) return false;
      const [x, y, z] = ringAt(tt);
      return !hidden(x, y, z) && x > 16 && x < W - 16 && y > G.top && y < G.floor;
    }
    const goodFrom = (t0) => { for (let tt = t0; tt < t0 + 3 * P; tt += 0.02) if (good(tt)) return tt; return t0; };
    // the copy in the canvas's coordinates: across, its lines (an h1's box is wider than its words)
    function extent(els, cr) {
      let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
      els.forEach(el => {
        const box = el.getBoundingClientRect(); if (box.width < 1 || box.height < 1) return;
        let ty = 0; try { ty = new DOMMatrixReadOnly(getComputedStyle(el).transform).m42; } catch (e) { /* none */ }
        const rg = document.createRange(); rg.selectNodeContents(el);
        for (const q of rg.getClientRects()) if (q.width >= 1) { l = Math.min(l, q.left - cr.left); r = Math.max(r, q.right - cr.left); }
        t = Math.min(t, box.top - ty - cr.top); b = Math.max(b, box.bottom - ty - cr.top);
      });
      return l < Infinity ? { l, t, r, b } : null;
    }
    // the copy's lines, padded: where a globe set behind the copy leaves a gap
    function holes(els, cr) {
      const out = [];
      els.forEach(el => {
        let ty = 0; try { ty = new DOMMatrixReadOnly(getComputedStyle(el).transform).m42; } catch (e) { /* none */ }
        const rg = document.createRange(); rg.selectNodeContents(el);
        for (const q of rg.getClientRects()) if (q.width >= 1 && q.height >= 1) out.push([q.left - cr.left - 9, q.top - ty - cr.top - 7, q.right - cr.left + 9, q.bottom - ty - cr.top + 7]);
      });
      return out;
    }
    function place() {
      const cr = cv.getBoundingClientRect(), bar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 64;
      const top = Math.max(0, bar - cr.top) + 14, C = extent(copy, cr), S = extent(strict, cr), gap = 18;
      const wide = cr.left > 1; // the canvas keeps to the right of the copy (the 404 from 961 px, S0 on wide screens)
      // beside the copy, in the brief's proportions, level with it; its orbits never reach back into it
      const beside = (cap) => {
        const x0 = C ? Math.max(0, C.r + gap) : 0, R = Math.min(cap, (W - 8 - x0) / 2.6, (H - top - 12) / 2), mid = C ? (C.t + C.b) / 2 : H * 0.48;
        return { mode: 'beside', R, cx: Math.min(W - R - 8, Math.max(W * 0.6, x0 + 1.6 * R)), cy: Math.max(top + R, Math.min(H - R - 12, mid)), floor: H - 12, alpha: 1 };
      };
      let g;
      if (story && wide) g = { mode: 'beside', R: Math.min(W * 0.20, H * 0.30), cx: W * 0.735, cy: H * 0.42, floor: H - 12, alpha: 1 };
      else if (wide || !C) g = beside(Math.min(W * 0.30, H * 0.36));
      else {
        // full width: the largest of the rooms beside, below and above the copy
        const cap = story ? W * 0.40 : Math.min(W * 0.30, H * 0.36);
        const room = (y0, y1, mode) => ({ mode, R: Math.min(cap, (y1 - y0) / 2), cy: (y0 + y1) / 2, floor: y1, alpha: 1 });
        const side = beside(cap), pick = [side, room(C.b + gap, H - 12, 'below'), room(top, C.t - gap, 'above')].reduce((a, b) => (b.R > a.R ? b : a));
        if (pick.R >= Math.min(cap, 54)) g = pick;
        else if (S) g = { ...room(S.b + gap, H - 12, 'under'), mode: 'under', alpha: 0.7 }; // a short screen: under the lede, behind the buttons and the log
        else { const R = W * 0.40; g = { mode: 'behind', R, cy: Math.max(H * 0.3, top + R * 0.6), floor: H - 12, alpha: 0.55 }; } // S0 on a tall tablet
        g.R = Math.max(24, g.R);
        if (g.mode !== 'beside') g.cx = Math.max(g.R + 8, Math.min(W - g.R - 8, story ? W * 0.62 : W * 0.6));
        if (g.mode === 'under' || g.mode === 'behind') g.holes = holes(copy, cr);
      }
      g.top = top; g.bead = W < 600 ? 1.6 : 1.25; // a bead's radius at mid depth (it grows toward the eye)
      G = g; cv.dataset.globe = g.mode;
      // the beads: about 12 px apart whatever the globe's size
      const sp = W < 600 ? 12.5 : 11.5, rows = Math.max(14, Math.min(64, Math.round(2.93 * g.R / sp) + 1)), eq = Math.round(TAU * g.R / sp);
      sphere = [];
      for (let r = 0; r < rows; r++) { const la = (84 - 168 * r / (rows - 1)) * Math.PI / 180, n = Math.max(8, Math.round(eq * Math.cos(la))); for (let k = 0; k < n; k++) sphere.push({ la, lo: (k + (r % 2) * 0.5) / n * TAU }); }
    }
    function draw() {
      if (!G) return;
      const { R, cx, cy, bead } = G, v = view(tau), small = W < 600, hs = G.holes;
      const out = hs ? (x, y) => { for (const h of hs) if (x > h[0] && x < h[2] && y > h[1] && y < h[3]) return true; return false; } : () => false;
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = G.alpha;
      // the body: a green key light from the upper left, fading to the limb
      const body = ctx.createRadialGradient(cx - R * 0.38, cy - R * 0.42, R * 0.05, cx, cy, R);
      body.addColorStop(0, rgba(GREEN, 0.075)); body.addColorStop(0.55, rgba(IVORY, 0.03)); body.addColorStop(1, rgba(IVORY, 0.012));
      ctx.fillStyle = body; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
      // two thin orbits, one stroke each (their arcs behind the globe are left out)
      ctx.lineWidth = 1;
      orbits.forEach((o, oi) => {
        ctx.beginPath(); let pen = false;
        for (let i = 0; i <= 180; i++) { const [x, y, z] = onOrbit(o, i / 180 * TAU, v); if (hidden(x, y, z) || out(x, y)) { pen = false; continue; } if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } }
        ctx.strokeStyle = rgba(oi ? IVORY : GREEN, oi ? 0.16 : 0.26); ctx.stroke();
      });
      // the globe: beads at .22 alpha at the limb rising to .6 facing the eye
      const eb = new Map();
      sphere.forEach(pt => {
        const lo = pt.lo + v.spin, q = rot([Math.cos(pt.la) * Math.sin(lo), Math.sin(pt.la), Math.cos(pt.la) * Math.cos(lo)], v.tilt, 0, 0);
        if (q[2] <= 0.04 || out(cx + q[0] * R, cy + q[1] * R)) return;
        const k = Math.round((0.22 + 0.38 * Math.pow(q[2], 1.2)) * 50);
        let f = eb.get(k); if (!f) eb.set(k, f = []); f.push(cx + q[0] * R, cy + q[1] * R, bead * (0.75 + 0.6 * q[2]));
      });
      eb.forEach((f, k) => { ctx.beginPath(); for (let i = 0; i < f.length; i += 3) { ctx.moveTo(f[i] + f[i + 2], f[i + 1]); ctx.arc(f[i], f[i + 1], f[i + 2], 0, TAU); } ctx.fillStyle = rgba(IVORY, k / 50); ctx.fill(); });
      // the latest reject: a dashed fall from where it left the ring, the mote on it
      const te = Math.floor((tau - PHASE) / P) * P + PHASE, u = (tau - te) / FALL, rj = u >= 0 && u <= 1 ? reject(te) : null;
      if (rj) {
        const fade = u < 0.7 ? 1 : Math.max(0, 1 - (u - 0.7) / 0.3), at = (s) => [rj.x0 + rj.dx * s, rj.y0 + rj.drop * Math.pow(s, 1.6)];
        ctx.beginPath(); let pen = false; for (let i = 0; i <= 14; i++) { const [x, y] = at(u * i / 14); if (out(x, y)) { pen = false; continue; } if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } }
        ctx.setLineDash([2, 3.5]); ctx.strokeStyle = rgba(RED, 0.55 * fade); ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
        if (u < 0.18) { const k = u / 0.18; ctx.beginPath(); ctx.arc(rj.x0, rj.y0, 4 + 7 * k, 0, TAU); ctx.strokeStyle = rgba(RED, 0.5 * (1 - k)); ctx.stroke(); }
        const [mx, my] = at(u); if (!out(mx, my)) { ctx.beginPath(); ctx.arc(mx, my, small ? 2.6 : 2.2, 0, TAU); ctx.fillStyle = rgba(RED, 0.95 * fade); ctx.fill(); }
      }
      // the proposal: a green ring travelling the first orbit (it passes behind the globe)
      const [px, py, pz] = ringAt(tau);
      if (!hidden(px, py, pz) && !out(px, py)) { ctx.beginPath(); ctx.arc(px, py, small ? 4.2 : 3.6, 0, TAU); ctx.strokeStyle = rgba(GREEN, 0.95); ctx.lineWidth = 1.3; ctx.stroke(); }
      ctx.globalAlpha = 1;
    }
    // a wake, from now: ease in from the current speed, cruise
    const speedAt = (p, t) => { const d = (t - p.t0) / 1000; if (d < RAMP) return p.s0 + (1 - p.s0) * d / RAMP; const x = (p.tEnd - t) / 1000 / EASE; return x >= 1 ? 1 : Math.max(0, x * x); };
    function tauAt(p, t) {
      if (t >= p.tEnd) return p.tauEnd;
      const d = Math.max(0, (t - p.t0) / 1000), x = (p.tEnd - t) / 1000 / EASE;
      if (x < 1) return p.tauEnd - EASE / 3 * x * x * x; // easing out: speed x^2
      const ramp = Math.min(d, RAMP);
      return p.tau0 + p.s0 * ramp + (1 - p.s0) * ramp * ramp / (2 * RAMP) + Math.max(0, d - RAMP);
    }
    function wake(t, s0, tau0) {
      const nominal = tau0 + RAMP * (1 + s0) / 2 + (WAKE / 1000 - RAMP - EASE) + EASE / 3, tauEnd = goodFrom(nominal);
      plan = { t0: t, s0, tau0, tauEnd, tEnd: t + WAKE + (tauEnd - nominal) * 1000 };
      delete cv.dataset.still; request();
    }
    const rests = () => !plan || performance.now() >= plan.tEnd;
    function frame(now) {
      frameId = 0;
      if (!visible || document.hidden || !plan) return;
      const k = 1 - Math.exp(-Math.min(0.1, (now - last) / 1000) * 3); last = now;
      mouse.x += (mouse.tx - mouse.x) * k; mouse.y += (mouse.ty - mouse.y) * k;
      tau = tauAt(plan, now); draw();
      if (now < plan.tEnd) frameId = requestAnimationFrame(frame); else cv.dataset.still = '';
    }
    // run while awake and in sight; at rest (or a wake that ended out of sight)
    function request() {
      if (frameId || !visible || document.hidden || !plan) return;
      if (!rests()) { last = performance.now(); frameId = requestAnimationFrame(frame); return; }
      if (tau !== plan.tauEnd) { tau = plan.tauEnd; draw(); }
      cv.dataset.still = '';
    }
    function stop() { cancelAnimationFrame(frameId); frameId = 0; }
    // placed again (a resize, a new pixel ratio, the copy's face arriving)
    function relayout() {
      place();
      if (rests()) { tau = goodFrom(plan ? plan.tauEnd : tau); if (plan) plan.tauEnd = tau; } else tau = tauAt(plan, performance.now());
      draw();
    }
    function resize() {
      const r = cv.getBoundingClientRect(); W = Math.max(1, Math.floor(r.width)); H = Math.max(1, Math.floor(r.height));
      dpr = Math.min(3, window.devicePixelRatio || 1, Math.sqrt(PIXEL_BUDGET / (W * H)), 4096 / W, 4096 / H);
      cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      relayout();
    }
    tau = 2.4; resize(); // the first still, composed in advance: reduced motion shows it, and the first wake lands on it
    window.addEventListener('resize', resize);
    if (document.fonts) document.fonts.ready.then(relayout); // the copy's lines move when its face arrives
    setTimeout(relayout, 1800); // and once the copy's entrance is over (the split h1's words rise a line)
    // a move to a display with another pixel ratio changes no CSS size
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    if (prefersReduced) { cv.dataset.still = ''; return; }
    // the first wake starts at once, from rest, and lands on that still 5 s later
    const t0 = performance.now(), still = tau;
    plan = { t0, s0: 0, tau0: still - (RAMP / 2 + (WAKE / 1000 - RAMP - EASE) + EASE / 3), tauEnd: still, tEnd: t0 + WAKE };
    tau = plan.tau0; draw();
    // a pointer moving over the globe tilts it toward itself and keeps it awake for another 5 s
    window.addEventListener('pointermove', (e) => {
      if (!G) return; const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      if (x < 0 || y < 0 || x > r.width || y > r.height || Math.hypot(x - G.cx, y - G.cy) > G.R * 1.7) return;
      mouse.tx = Math.max(-1, Math.min(1, (x - G.cx) / (G.R * 1.7))); mouse.ty = Math.max(-1, Math.min(1, (y - G.cy) / (G.R * 1.7)));
      const now = performance.now();
      if (!rests() && now < plan.t0 + 250) return;
      wake(now, rests() ? 0 : speedAt(plan, now), rests() ? tau : tauAt(plan, now));
    }, { passive: true });
    if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible) request(); else stop(); }, { threshold: 0 }).observe(cv);
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); else request(); });
    request();
  }
})();
