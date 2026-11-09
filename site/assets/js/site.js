/* OpenEXA: shared behaviour (nav, chapter readout, menu sheet, jumps, page turns, scenes, footer, clocks, loader hand-off, kinetic type, reveals, 2D swarm) */
(function () {
  'use strict';

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pad = (n) => String(n).padStart(2, '0');
  const clamp01 = (v) => v < 0 ? 0 : v > 1 ? 1 : v;
  const root = document.documentElement;
  const unhash = h => { try { return decodeURIComponent(h); } catch (e) { return h; } };

  const ZOOMS = [0.25, 1 / 3, 0.5, 2 / 3, 0.75, 0.8, 0.85, 0.9, 1.1, 1.15, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, 5];
  function readZoom() {
    const ow = window.outerWidth;
    if (!(ow >= 1200) && !root.classList.contains('uz')) return;
    const zr = ow / window.innerWidth, dpr = window.devicePixelRatio || 1;
    let uz = 1;
    const z = zr > 0 && isFinite(zr) ? ZOOMS.find(p => Math.abs(zr / p - 1) < 0.015) : 0;
    if (z) {
      const base = dpr / z, s = Math.round(base * 4) / 4;
      if (s >= 1 && Math.abs(base - s) < 0.02) uz = Math.round(z * 1000) / 1000;
    }
    if (uz === 1) { if (root.classList.contains('uz')) { root.classList.remove('uz'); root.style.removeProperty('--uz'); } return; }
    root.style.setProperty('--uz', String(uz));
    root.classList.add('uz');
  }
  readZoom();
  window.addEventListener('resize', readZoom);

  const nav = $('.nav');
  const darkStart = document.body.dataset.nav === 'dark-start';
  const themeMeta = $('meta[name="theme-color"]');
  const story = $('.story');
  const paper = story && $('.story-paper', story);
  if (story && !root.classList.contains('story-ready') && !root.classList.contains('no-webgl')) root.classList.add('story-failed');
  const toggle = $('.nav-toggle');
  const sheet = $('.nav-sheet');
  let navH = 72, vh = 0, maxScroll = 1, clearUntil = -1, bands = [], tones = [], navRaf = 0, menuOpen = false, lastY = 0;

  const pins = $$('[data-scene="pin"]');
  const pinOf = el => {
    const s = pins.length && el && el.closest ? el.closest('[data-scene="pin"]') : null, st = s && s.firstElementChild;
    return st && st.classList.contains('scene-stage') && getComputedStyle(st).position === 'sticky' ? s : null;
  };
  const sceneSpan = s => { const a = s.getBoundingClientRect().top + window.scrollY; return [a, Math.ceil(a + s.offsetHeight - root.clientHeight)]; };
  const sceneAt = el => { const f = parseFloat((el.closest('[data-scene-at]') || el).dataset.sceneAt); return isNaN(f) ? (el.closest('[data-scene-end], [data-scene-anchor]') ? 1 : 0) : Math.min(1, Math.max(0, f)); };
  function sceneY(el) {
    const s = pinOf(el);
    if (!s || s === el) return null;
    const [a, z] = sceneSpan(s);
    return el.closest('[data-scene-end], [data-scene-anchor]') ? z : Math.round(a + sceneAt(el) * (z - a));
  }

  const pageKey = path => path.replace(/(\/index)?(\.html)?\/*$/, '').split('/').pop() || 'index';
  const here = pageKey(location.pathname);
  const section = /\/research\/[^/]+$/.test(location.pathname) ? 'research' : here;
  const blog = /^\/blog(\/|$)/.test(location.pathname);
  $$('.nav-links a, .nav-sheet a, .nav .btn, .footer ul a').forEach(a => {
    const k = pageKey(a.pathname);
    if (a.host !== location.host || a.hasAttribute('aria-current')) return;
    if (a.closest('.footer') ? k === here && !a.hash : k === here || k === section) a.setAttribute('aria-current', 'page');
    else if (blog && k === 'research' && !a.closest('.footer')) a.setAttribute('aria-current', 'true');
  });

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
  if (chapters.length && location.hash && chapters.some(c => '#' + c.el.id === unhash(location.hash)) && window.scrollY < 2) {
    const target = document.getElementById(unhash(location.hash.slice(1)));
    requestAnimationFrame(() => target.scrollIntoView({ block: 'start', behavior: 'instant' }));
  }

  let live = [], segs = [], current = -2, shownK = -3, chOpen = false;
  const ui = {};
  if (nav) {
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
      '<div class="nav-ch-panel" id="nav-ch-panel"><p class="nav-ch-head" id="nav-ch-head">On this page</p><ol class="nav-ch-list" aria-labelledby="nav-ch-head"></ol>' +
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
  const narrowMQ = window.matchMedia('(max-width: 960px)'), phoneMQ = window.matchMedia('(max-width: 600px)');
  const midMQ = window.matchMedia('(min-width: 961px) and (max-width: 1279.98px)');
  let fitKey = '';
  function fitModes() {
    if (!ui.roll || !live.length) return;
    const zoomed = root.classList.contains('uz'), rootPx = zoomed ? parseFloat(getComputedStyle(root).fontSize) || 16 : 16;
    const key = [window.innerWidth, rootPx, live.map(c => c.k).join(), document.fonts ? document.fonts.status : ''].join('|');
    if (key === fitKey) return;
    fitKey = key;
    live.forEach(c => { c.mode = 'full'; });
    const links = (midMQ.matches || (zoomed && !narrowMQ.matches && window.innerWidth / rootPx < 80)) && $('.nav-links', nav);
    if (narrowMQ.matches || links) {
      const box = document.createElement('span'); box.className = 'nav-ch-measure'; box.setAttribute('aria-hidden', 'true');
      const forms = [];
      live.forEach(c => { forms.push([c, 'full', lineFor(c.k, 'full')]); if (c.short && c.short !== c.title) forms.push([c, 'short', lineFor(c.k, 'short')]); });
      forms.forEach(f => box.appendChild(f[2]));
      ui.btn.appendChild(box);
      const r0 = ui.roll.getBoundingClientRect();
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
      if (compact) live.forEach(c => { if ((!links && /^\d+$/.test(c.n)) || c.fit === false) c.mode = 'compact'; });
      live.forEach(c => { delete c.fit; });
    }
    const c = chapters[shownK];
    if (ui.line && c) { MODES.forEach(m => ui.line.classList.toggle(m, m === 'is-' + c.mode)); }
    nameReadout();
  }
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
    const w0 = first ? 0 : ui.roll.getBoundingClientRect().width;
    Array.from(ui.roll.children).forEach(ch => ch.remove());
    const old = ui.line, neu = lineFor(k);
    ui.line = neu;
    ui.btn.classList.toggle('is-intro', k < 0);
    ui.progress.classList.toggle('is-ch', k >= 0);
    ui.roll.appendChild(neu);
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

  function measure() {
    if (!nav) return;
    const y = window.scrollY;
    vh = window.innerHeight; navH = nav.offsetHeight || 72;
    maxScroll = Math.max(1, root.scrollHeight - vh);
    const pinned = story && root.classList.contains('story-ready') && !root.classList.contains('no-webgl');
    clearUntil = !darkStart ? -1 : pinned ? story.getBoundingClientRect().bottom + y - vh : 16;
    bands = $$('main > *, body > .footer').map(el => {
      const r = el.getBoundingClientRect();
      return { el, top: r.top + y, bottom: r.bottom + y, dark: el.classList.contains('is-dark') };
    });
    tones = [];
    pins.forEach(s => {
      if (!pinOf(s)) return;
      const end = s.getBoundingClientRect().bottom + y;
      const m = $$(':scope > [data-scene-tone]', s).filter(t => t.getClientRects().length)
        .map(t => ({ el: s, top: t.getBoundingClientRect().top + y, dark: t.dataset.sceneTone === 'dark' })).sort((p, q) => p.top - q.top);
      m.forEach((t, i) => { t.bottom = i + 1 < m.length ? m[i + 1].top : end; tones.push(t); });
    });
    const before = live.map(c => c.k).join();
    live = chapters.filter(c => c.el.getClientRects().length > 0);
    chapters.forEach(c => { c.li.hidden = !live.includes(c); });
    if (before !== live.map(c => c.k).join() || !segs.length) buildSegments();
    const probe = navH + (vh - navH) * 0.3;
    live.forEach(c => {
      const s = pinOf(c.el), r = (s || c.el).getBoundingClientRect();
      c.top = r.top + y; c.bottom = r.bottom + y;
      if (s && s !== c.el && sceneAt(c.el) > 0) { const [a, z] = sceneSpan(s); c.top = a + sceneAt(c.el) * (z - a) + probe; }
    });
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
    const y = lastY = window.scrollY;
    let dark = false, band = null;
    const edge = y + navH * 1.1;
    for (const b of tones) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    if (!band) for (const b of bands) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    let overPaper = false;
    if (band && band.el === story && paper) {
      const r = getComputedStyle(paper).visibility !== 'hidden' ? paper.getBoundingClientRect() : null;
      overPaper = !!r && r.height > 0 && r.top <= edge - y && r.bottom > edge - y;
    }
    if (overPaper) dark = false;
    if (darkStart) { const opening = bands[0] && bands[0].dark ? bands[0] : null; root.classList.toggle('is-paper-root', !!opening && y >= opening.bottom); }
    const clear = y <= (root.classList.contains('story-tiny') ? 16 : clearUntil) && !menuOpen && !overPaper;
    nav.classList.toggle('nav--solid', !clear);
    nav.classList.toggle('nav--dark', dark);
    if (themeMeta) {
      const ink = clear ? darkStart : dark || menuOpen;
      const want = ink ? '#0E1512' : '#F5F2EC';
      if (themeMeta.content !== want) themeMeta.content = want;
    }
    let on = -1;
    segs.forEach((g, j) => {
      const len = g.e - g.s;
      const p = len > 0 ? clamp01((y - g.s) / len) : (y >= g.e ? 1 : 0);
      if (Math.abs(p - g.p) > 0.001) { g.p = p; g.b.style.transform = `scaleX(${p.toFixed(4)})`; }
      if (y >= g.s && (y < g.e || j === segs.length - 1)) on = j;
    });
    segs.forEach((g, j) => g.i.classList.toggle('is-on', j === on && g.p > 0 && live.length > 0 && g.part !== 'edge'));
    if (!live.length) return;
    let k = -1;
    for (const c of live) if (y >= c.s) k = c.k;
    const last = live[live.length - 1];
    if (k === last.k && y >= last.e && last.e < maxScroll - 1) k = -1;
    live.forEach(c => {
      const p = c.e > c.s ? clamp01((y - c.s) / (c.e - c.s)) : (y >= c.e ? 1 : 0);
      if (Math.abs(p - (c.p || 0)) > 0.004 || c.p === undefined) { c.p = p; c.bar.style.setProperty('--p', p.toFixed(3)); }
    });
    if (k !== current) { current = k; showChapter(k); }
  }

  function setPanel(open, refocus) {
    if (open && narrowMQ.matches) {
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
      if (e.key === 'Escape') { e.preventDefault(); if (menuOpen) { const o = opener; setMenu(false); if (!o) toggle.focus(); } else setPanel(false, true); }
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

  const popover = !!(sheet && sheet.hasAttribute('popover') && typeof sheet.showPopover === 'function');
  let opener = null;
  function syncMenu(open) {
    if (open === menuOpen) return;
    menuOpen = open;
    root.classList.toggle('sb-lock', open && window.innerWidth > root.clientWidth);
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
    if (popover) { try { open ? sheet.showPopover() : sheet.hidePopover(); } catch (e) { } }
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
  function closeSheetForJump() {
    if (!menuOpen || !sheet) return;
    sheet.classList.add('is-snap');
    setMenu(false);
    setTimeout(() => sheet.classList.remove('is-snap'), 80);
  }
  function placePanel() {
    if (!ui.panel || !sheet) return;
    const inSheet = narrowMQ.matches;
    if (inSheet && ui.panel.parentElement !== sheet) { setPanel(false); sheet.prepend(ui.panel); }
    else if (!inSheet && ui.panel.parentElement !== ui.wrap) { setMenu(false); ui.wrap.appendChild(ui.panel); }
    sheet.classList.toggle('has-ch', inSheet);
    ui.btn.setAttribute('aria-controls', inSheet ? sheet.id : ui.panel.id);
    ui.btn.setAttribute('aria-expanded', String(inSheet ? menuOpen : chOpen));
  }
  placePanel();
  narrowMQ.addEventListener('change', placePanel);

  const VT_LIMIT = 16000;
  let jumping = false;
  function settle() {
    const bands = $$('main > *, body > .footer').filter(el => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < window.innerHeight; });
    bands.forEach(el => {
      el.classList.remove('is-offscreen', 'is-landing');
      void el.offsetWidth;
      el.classList.add('is-landing');
      setTimeout(() => el.classList.remove('is-landing'), 400);
    });
  }
  function cut(to, land) {
    const from = window.scrollY;
    if (ui.wrap) { ui.wrap.classList.add('is-snap'); setTimeout(() => ui.wrap.classList.remove('is-snap'), 60); }
    const go = () => {
      jumping = true;
      revealRange(Math.min(from, to), Math.max(from, to) + window.innerHeight);
      land();
      if (nav) measure();
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
  let sceneJumpAt = -1e4;
  const setHash = hash => {
    if (!hash || hash === location.hash) return;
    const oldURL = location.href;
    history.pushState(null, '', hash);
    window.dispatchEvent(new HashChangeEvent('hashchange', { oldURL, newURL: location.href }));
  };
  function jumpTo(el, hash, e, after) {
    const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0;
    const y0 = window.scrollY, max = Math.max(0, root.scrollHeight - window.innerHeight);
    const sy = el ? sceneY(el) : null;
    const to = el ? Math.max(0, Math.min(max, sy !== null ? sy : el.getBoundingClientRect().top + y0 - sp)) : 0;
    if (sy !== null) sceneJumpAt = performance.now();
    if (Math.abs(to - y0) <= 1.5 * window.innerHeight) {
      if (sy === null) return false;
      if (e) e.preventDefault();
      setHash(hash);
      window.scrollTo({ top: to, behavior: reducedMQ.matches ? 'instant' : 'smooth' });
      if (after) after();
      return true;
    }
    if (e) e.preventDefault();
    cut(to, () => {
      setHash(hash);
      if (sy !== null) window.scrollTo({ top: to, behavior: 'instant' });
      else if (el) el.scrollIntoView({ block: 'start', behavior: 'instant' });
      else window.scrollTo({ top: 0, behavior: 'instant' });
      if (after) after();
    });
    return true;
  }
  if (pins.length) {
    document.addEventListener('focusin', e => {
      const t = e.target, s = t && t.closest && t.closest('[data-scene-end]') && pinOf(t);
      if (!s || performance.now() - sceneJumpAt < 1500) return;
      requestAnimationFrame(() => {
        if (!t.closest('[data-scene-end]').contains(document.activeElement)) return;
        const z = sceneSpan(s)[1];
        if (window.scrollY >= z - 1) return;
        sceneJumpAt = performance.now();
        if (z - window.scrollY > 1.5 * window.innerHeight) cut(z, () => window.scrollTo({ top: z, behavior: 'instant' }));
        else window.scrollTo({ top: z, behavior: 'instant' });
      });
    });
    window.addEventListener('hashchange', () => {
      const el = location.hash.length > 1 && document.getElementById(unhash(location.hash.slice(1))), sy = el ? sceneY(el) : null;
      if (sy === null || performance.now() - sceneJumpAt < 1500) return;
      sceneJumpAt = performance.now();
      window.scrollTo({ top: sy, behavior: 'instant' });
    });
  }
  document.addEventListener('click', e => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest && e.target.closest('a[href*="#"]');
    if (!a || (a.target && a.target !== '_self') || a.closest('.nav-ch, .nav-sheet')) return;
    const url = new URL(a.href, location.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname || url.search !== location.search || url.hash.length < 2) return;
    const el = document.getElementById(unhash(url.hash.slice(1)));
    if (!el || el.closest('details:not([open])')) return;
    jumpTo(el, url.hash, e, () => focusInto(el));
  });
  function focusInto(el) {
    let t = el;
    if (el.tagName === 'SECTION') {
      const h = $$('h2', el).find(x => x.getClientRects().length && x.closest('section') === el);
      if (h) t = h;
    }
    if (!t.matches('a[href], button, input, select, textarea, summary, [tabindex]')) { t.setAttribute('tabindex', '-1'); t.classList.add('nav-ch-target'); }
    t.focus({ preventScroll: true });
  }

  const OXA = window.OXA = window.OXA || {};
  let landed = Promise.resolve();
  const seen = new WeakSet();
  function turned(vt) {
    if (!vt) return;
    const a = window.navigation && navigation.activation;
    const moving = () => document.getAnimations().some(x => x.effect && /^::view-transition/.test(x.effect.pseudoElement || '') && x.currentTime > 0);
    if (a && a.navigationType === 'traverse' && a.from && a.entry && a.entry.index < a.from.index && !moving()) { try { vt.types.add('back'); } catch (err) { } }
    if (!seen.has(vt)) { seen.add(vt); landed = vt.finished.catch(() => {}).then(() => {}); }
  }
  window.addEventListener('pagereveal', e => turned(e.viewTransition));
  if (document.activeViewTransition && !root.dataset.jump) turned(document.activeViewTransition);
  OXA.landed = () => landed;
  if (!OXA.tapThrough) {
    OXA.tapThrough = true;
    let tap = null;
    document.addEventListener('pointerdown', e => {
      const vt = document.activeViewTransition;
      tap = null;
      if (!vt || e.target !== root || e.button !== 0) return;
      tap = { x: e.clientX, y: e.clientY };
      try { vt.skipTransition(); } catch (err) { }
    }, true);
    document.addEventListener('click', e => {
      if (!tap || e.target !== root) return;
      const { x, y } = tap;
      tap = null;
      requestAnimationFrame(() => {
        const el = document.elementFromPoint(x, y), t = el && el.closest('a[href], button, summary, label, input, select, textarea, [role="button"], [tabindex]');
        if (!t || t === root) return;
        if (t.matches('input, select, textarea, [tabindex]:not(a, button, summary, label, [role="button"])')) t.focus(); else t.click();
      });
    }, true);
  }

  const CONTROL = 'a[href], button, input, select, textarea, label, summary, [role="button"], [role="slider"], [role="tab"], [tabindex]';
  function actOnce(el, start, opts) {
    if (!el || typeof start !== 'function' || !('IntersectionObserver' in window)) return () => {};
    const o = Object.assign({ visible: 0.6, delay: 700, paused: null }, opts);
    let done = false, timer = 0, inView = false;
    const stop = () => { clearTimeout(timer); timer = 0; };
    const off = () => {
      if (done) return;
      done = true; stop(); io.disconnect();
      el.removeEventListener('pointerdown', press, true); el.removeEventListener('keydown', off, true); el.removeEventListener('click', off, true);
      document.removeEventListener('visibilitychange', vis);
    };
    const press = e => { if (e.pointerType !== 'touch' || (e.target.closest && e.target.closest(CONTROL))) off(); };
    const blocked = () => done || !inView || document.hidden || reducedMQ.matches || !!(o.paused && o.paused());
    const fire = () => { timer = 0; if (!blocked()) landed.then(() => { if (!blocked()) { off(); start({ quiet: true }); } }); };
    const vis = () => { if (document.hidden) stop(); else if (inView && !timer) timer = setTimeout(fire, o.delay); };
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      const vh = e.rootBounds ? e.rootBounds.height : window.innerHeight;
      const r = e.isIntersecting ? Math.max(e.intersectionRatio, e.intersectionRect.height / Math.max(1, Math.min(e.boundingClientRect.height, vh))) : 0;
      inView = r >= o.visible - 0.001;
      if (!inView) stop(); else if (!timer && !document.hidden) timer = setTimeout(fire, o.delay);
    }), { threshold: Array.from({ length: 21 }, (v, k) => k / 20) });
    el.addEventListener('pointerdown', press, true);
    el.addEventListener('keydown', off, true);
    el.addEventListener('click', off, true);
    document.addEventListener('visibilitychange', vis);
    io.observe(el);
    return off;
  }
  OXA.actOnce = actOnce;
  (OXA.q || []).splice(0).forEach(a => actOnce(...a));

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

  if (!OXA.figs) {
    const figs = OXA.figs = [], all = s => Array.from(document.querySelectorAll(s));
    const figSet = (el, v) => { el.style.setProperty('view-transition-name', v); figs.push(el); };
    const figClear = () => figs.splice(0).forEach(el => el.style.removeProperty('view-transition-name'));
    const docOf = u => { try { const x = new URL(u, location.href); return x.origin + x.pathname.replace(/(\/index)?(\.html)?\/*$/, ''); } catch (err) { return ''; } };
    const inView = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; };
    const srcOf = a => a && (a.matches('.vt-src') ? a : a.querySelector('.vt-src') || (a.dataset.vtSrc ? document.getElementById(a.dataset.vtSrc) : null));
    const pair = v => { try { if (v === undefined) return JSON.parse(sessionStorage.getItem('oxa-vt') || 'null'); sessionStorage.setItem('oxa-vt', JSON.stringify(v)); } catch (err) { } return null; };
    let lastLink = null;
    document.addEventListener('click', e => { lastLink = (e.target.closest && e.target.closest('a[href]')) || null; }, true);
    addEventListener('pageswap', e => {
      figClear();
      const a = e.activation;
      if (!e.viewTransition || !a || !a.entry) return;
      const to = docOf(a.entry.url), me = docOf(location.href), back = a.navigationType === 'traverse', p = pair();
      const home = back && p && p.to === me && p.from === to;
      all('[data-vt-dest]').forEach(d => { if (!home || !inView(d)) figSet(d, 'none'); });
      if (back) return;
      const src = lastLink && docOf(lastLink.href) === to ? srcOf(lastLink) : null;
      if (!src || !inView(src)) return;
      figSet(src, 'fig');
      pair({ from: me, to });
    });
    addEventListener('pagereveal', e => {
      figClear();
      const a = window.navigation && navigation.activation;
      if (!e.viewTransition || !a) return;
      all('[data-vt-dest]').forEach(d => { if (!inView(d)) figSet(d, 'none'); });
      e.viewTransition.ready.then(() => { if (document.getAnimations().some(x => x.effect && x.effect.pseudoElement === '::view-transition-old(fig)')) all('[data-vt-dest]').forEach(d => d.getAnimations({ subtree: true }).forEach(x => x.cancel())); }, () => { });
      if (a.navigationType !== 'traverse' || !a.from) return;
      const from = docOf(a.from.url), p = pair();
      if (!p || p.from !== docOf(location.href) || p.to !== from) return;
      const src = all('a[href]').filter(l => docOf(l.href) === from).map(srcOf).find(x => x && inView(x));
      if (!src) return;
      all('[data-vt-dest]').forEach(d => figSet(d, 'none'));
      figSet(src, 'fig');
    });
    addEventListener('pageshow', e => { if (e.persisted) figClear(); });
  }

  if (nav) {
    let mRaf = 0;
    const measureSoon = () => { if (!mRaf) mRaf = requestAnimationFrame(() => { mRaf = 0; measure(); }); };
    measureSoon();
    window.addEventListener('scroll', queue, { passive: true });
    if (paper) new MutationObserver(queue).observe(paper, { attributes: true, attributeFilter: ['style'] });
    window.addEventListener('resize', measure);
    window.addEventListener('load', measureSoon);
    const handoff = () => {
      const sb = story && bands.find(b => b.el === story);
      if (!sb || mRaf) { measureSoon(); return; }
      const pinned = root.classList.contains('story-ready') && !root.classList.contains('no-webgl');
      clearUntil = !darkStart ? -1 : pinned ? sb.bottom - vh : 16;
      if (lastY > 16 || menuOpen) queue();
    };
    ['story:gl-ready', 'story:no-webgl', 'oxa:loaded'].forEach(t => document.addEventListener(t, story ? handoff : measureSoon));
    if ('ResizeObserver' in window) new ResizeObserver(measureSoon).observe(document.body);
    if (document.fonts) requestAnimationFrame(() => document.fonts.ready.then(measureSoon));
  }
  let anchor = null, settleUntil = 0, lastInput = 0, lastW = 0;
  const inFlow = el => { const p = getComputedStyle(el).position; return p !== 'fixed' && p !== 'sticky' && p !== 'absolute'; };
  const layoutTop = el => { let y = 0; for (let e = el; e; e = e.offsetParent) y += e.offsetTop; return y - window.scrollY; };
  function pickAnchor() {
    anchor = null;
    if (!nav || !bands.length) return;
    const line = navH + 8;
    const yDoc = window.scrollY + line;
    const band = bands.find(b => yDoc >= b.top && yDoc < b.bottom);
    if (!band || band.el === story) return;
    let el = band.el;
    for (let depth = 0; depth < 14; depth++) {
      if (Math.abs(layoutTop(el) - navH) <= 24) break;
      let straddle = null, next = null;
      for (const ch of el.children) {
        if (!(ch instanceof HTMLElement) || !ch.offsetHeight || !inFlow(ch)) continue;
        const t = layoutTop(ch);
        if (t <= line && t + ch.offsetHeight > line) { straddle = ch; break; }
        if (t > line) { next = ch; break; }
      }
      if (straddle) { el = straddle; continue; }
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
      if (performance.now() < settleUntil) return;
      clearTimeout(pickT); pickT = setTimeout(pickAnchor, 160);
    }, { passive: true });
    window.addEventListener('resize', () => {
      const w = window.innerWidth, widthChanged = w !== lastW;
      lastW = w;
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
  const hashId = () => unhash(location.hash.slice(1));
  const deep = location.hash.length > 1 && document.getElementById(hashId());
  if (deep && nav) {
    let quietTo = 0, busy = false, ro = null;
    const realign = (h0, n) => requestAnimationFrame(() => requestAnimationFrame(() => {
      if (lastInput) { busy = false; return; }
      const h = root.scrollHeight;
      if (h !== h0 && n < 60) { realign(h, n + 1); return; }
      busy = false;
      const sp = parseFloat(getComputedStyle(root).scrollPaddingTop) || 0, sy = sceneY(deep);
      if (sy !== null) { if (Math.abs(window.scrollY - sy) > 1) window.scrollTo({ top: sy, behavior: 'instant' }); }
      else if (Math.abs(deep.getBoundingClientRect().top - sp) > 1) deep.scrollIntoView({ block: 'start', behavior: 'instant' });
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
    if (inFold) requestAnimationFrame(() => { if (changed) target.scrollIntoView({ block: 'start', behavior: 'instant' }); if (target.tabIndex < 0) target.tabIndex = -1; target.focus({ preventScroll: true }); });
  };
  window.addEventListener('hashchange', openLinkedDetails);

  const disclosures = $('.footer .disc');
  if (disclosures && !disclosures.closest('details')) {
    const details = document.createElement('details');
    details.className = 'footer-legal';
    const summary = document.createElement('summary');
    summary.textContent = 'Legal & disclosures';
    disclosures.before(details);
    details.append(summary, disclosures);
  }
  openLinkedDetails();

  const bottom = $('.footer .bottom');
  if (bottom) {
    const span = document.createElement('span'); span.className = 'clocks';
    span.innerHTML = '<span><b>Seattle</b> <time data-tz="America/Los_Angeles"></time></span> <span><b>New York <small>· market time</small></b> <time data-tz="America/New_York"></time></span>';
    bottom.appendChild(span);
    const fmts = $$('time[data-tz]', span).map(t => ({ t, f: new Intl.DateTimeFormat('en-US', { timeZone: t.dataset.tz, hourCycle: 'h23', hour: '2-digit', minute: '2-digit' }) }));
    const tick = () => { const now = new Date(); fmts.forEach(({ t, f }) => { t.textContent = f.format(now); t.dateTime = now.toISOString(); }); setTimeout(tick, 60050 - now % 60000); };
    tick();
  }

  const SERIF_TEXT = 'h1, h2, h3, .display-1, .display-2, .display-3, .footer .tag';
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

  function splitWords(el) {
    if (el.dataset.split === 'done') return;
    el.dataset.split = 'done';
    let i = 0;
    const walk = (node) => {
      let wi = null;
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const parts = child.textContent.split(/([ \t\n\r\f]+)/);
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

  $$('[data-stagger]').forEach(el => { Array.from(el.children).forEach((c, i) => c.style.setProperty('--i', i)); if (!el.hasAttribute('data-reveal')) el.setAttribute('data-reveal', ''); });
  const storySplit = $$('.story [data-split]');
  if (!prefersReduced) storySplit.forEach(splitWords);
  const watched = $$('[data-reveal], [data-split], [data-draw]').filter(el => !el.closest('.story'));
  let rio = null, sio = null;
  const drawScale = (el, now) => $$('.dr, .dm--line', el).forEach(d => {
    const svg = d.ownerSVGElement, k = svg && svg.style.getPropertyValue('--dr-k'), m = svg && (now || !k) && svg.getScreenCTM();
    const v = m && Math.max(1, Math.hypot(m.a, m.b) * 1.02 + .02).toFixed(3);
    if (v && v !== k) svg.style.setProperty('--dr-k', v);
  });
  if (!prefersReduced && $('a[data-draw], a [data-draw]')) {
    const again = e => { const a = e.target.closest && e.target.closest('a'); const p = a && (a.matches('[data-draw]') ? a : $('[data-draw]', a)); if (p) drawScale(p, true); };
    document.addEventListener('pointerover', again, { passive: true });
    document.addEventListener('focusin', again);
  }
  if ('IntersectionObserver' in window && !prefersReduced) requestAnimationFrame(() => {
    const fold = window.innerHeight;
    const tops = new Map(), secTop = s => { if (!tops.has(s)) tops.set(s, s.getBoundingClientRect().top); return tops.get(s); };
    const rects = watched.map(el => { const s = el.closest('main > section'); return s && secTop(s) >= fold - 1 ? { top: secTop(s), width: 1, height: 1 } : el.getBoundingClientRect(); });
    const later = watched.filter((el, k) => { const r = rects[k]; return (r.width || r.height) && r.top >= fold - 1; });
    watched.forEach(el => { if (!later.includes(el)) el.classList.add('is-in'); });
    const show = (el, k) => {
      drawScale(el);
      if (el.classList.contains('will-draw')) { el.style.setProperty('--draw-i', k); setTimeout(() => el.classList.remove('will-draw'), 1200 + k * 80); }
      el.classList.add('is-in'); rio.unobserve(el);
    };
    rio = new IntersectionObserver((entries) => {
      let k = 0;
      entries.forEach(e => { if (e.isIntersecting) show(e.target, e.target.hasAttribute('data-draw') ? k++ : 0); });
    }, { rootMargin: '0px 0px -4% 0px', threshold: 0 });
    sio = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { sio.unobserve(e.target); if (!e.target.classList.contains('is-in')) splitWords(e.target); } });
    }, { rootMargin: '0px 0px 150% 0px', threshold: 0 });
    later.forEach(el => {
      if (el.hasAttribute('data-split')) sio.observe(el);
      if (el.hasAttribute('data-reveal')) { el.classList.add('will-reveal'); instant(el); }
      if (el.hasAttribute('data-draw') && $('.dm', el)) el.classList.add('will-draw');
      rio.observe(el);
    });
  }); else watched.forEach(el => el.classList.add('is-in'));
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
    let el = e.target.closest && e.target.closest('.will-reveal');
    while (el) {
      if (!el.classList.contains('is-in')) revealNow(el);
      else if (el.getAnimations && el.getAnimations({ subtree: true }).some(a => a.playState === 'running' && a.transitionProperty)) instant(el);
      el = el.parentElement && el.parentElement.closest('.will-reveal');
    }
  });

  if ('IntersectionObserver' in window) {
    const oio = new IntersectionObserver(entries => entries.forEach(e => e.target.classList.toggle('is-offscreen', !e.isIntersecting)));
    $$('main > section, main > div, body > .footer').forEach(el => oio.observe(el));
  }

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
  window.addEventListener('beforeprint', () => $$('details.footer-legal').forEach(d => { d.dataset.wasOpen = d.open ? '1' : ''; d.open = true; }));
  window.addEventListener('afterprint', () => $$('details.footer-legal').forEach(d => { d.open = d.dataset.wasOpen === '1'; }));

  const canvas = $('canvas[data-swarm]');
  const inStory = canvas && canvas.closest('.story');
  if (canvas && (!inStory || document.documentElement.classList.contains('no-webgl'))) initSwarm(canvas);
  else if (inStory) document.addEventListener('story:no-webgl', () => initSwarm(canvas), { once: true });

  function initSwarm(cv) {
    const ctx = cv.getContext('2d', { alpha: true });
    if (!ctx) return;
    cv.hidden = false;
    const story = cv.closest('.story');
    const copy = story ? $$('.beat-0 .beat-text > *, .beat-0 .hero-stats', story) : $$('.container > *', cv.parentElement);
    const strict = story ? [] : copy.filter(el => el.matches('h1, .lede'));
    const IVORY = [245, 242, 236], GREEN = [79, 203, 147], RED = [217, 103, 93], TAU = Math.PI * 2;
    const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
    const orbits = [{ r: 1.34, tiltX: 1.16, rotZ: -0.36 }, { r: 1.6, tiltX: 1.42, rotZ: 0.52 }];
    const PIXEL_BUDGET = 3840 * 2160;
    const WAKE = 5000, RAMP = 0.6, EASE = 1.5, P = 4, FALL = 2.6, PHASE = 0.3;
    let W = 0, H = 0, dpr = 1, G = null, sphere = [], visible = true, frameId = 0, tau = 0, plan = null, last = 0;
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    const rot = (p, ax, ay, az) => { let [x, y, z] = p; let c = Math.cos(ax), s = Math.sin(ax); let y1 = y * c - z * s, z1 = y * s + z * c; y = y1; z = z1; c = Math.cos(ay); s = Math.sin(ay); let x1 = x * c + z * s; z1 = -x * s + z * c; x = x1; z = z1; c = Math.cos(az); s = Math.sin(az); x1 = x * c - y * s; y1 = x * s + y * c; return [x1, y1, z]; };
    const view = (tt) => ({ spin: tt * 0.10 + mouse.x * 0.25, tilt: 0.32 + mouse.y * 0.12 });
    const onOrbit = (o, a, v) => { const q = rot(rot([Math.cos(a) * o.r, Math.sin(a) * o.r, 0], o.tiltX, 0, o.rotZ), v.tilt, v.spin * 0.3, 0); return [G.cx + q[0] * G.R, G.cy + q[1] * G.R, q[2]]; };
    const hidden = (x, y, z) => z < 0 && Math.hypot((x - G.cx) / G.R, (y - G.cy) / G.R) < 0.99;
    const ringAt = (tt) => onOrbit(orbits[0], tt * 0.32 + 1.1, view(tt));
    function reject(te) {
      const [x0, y0, z0] = ringAt(te);
      if (hidden(x0, y0, z0) || x0 < 12 || x0 > W - 12) return null;
      const drop = Math.min(G.R * 0.5, G.floor - y0 - 10);
      return drop < G.R * 0.22 ? null : { x0, y0, dx: (x0 >= G.cx ? 1 : -1) * G.R * 0.14, drop };
    }
    function good(tt) {
      const te = Math.floor((tt - PHASE) / P) * P + PHASE, u = (tt - te) / FALL;
      if (u < 0.55 || u > 0.68 || !reject(te)) return false;
      const [x, y, z] = ringAt(tt);
      return !hidden(x, y, z) && x > 16 && x < W - 16 && y > G.top && y < G.floor;
    }
    const goodFrom = (t0) => { for (let tt = t0; tt < t0 + 3 * P; tt += 0.02) if (good(tt)) return tt; return t0; };
    function extent(els, cr) {
      let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
      els.forEach(el => {
        const box = el.getBoundingClientRect(); if (box.width < 1 || box.height < 1) return;
        let ty = 0; try { ty = new DOMMatrixReadOnly(getComputedStyle(el).transform).m42; } catch (e) { }
        const rg = document.createRange(); rg.selectNodeContents(el);
        for (const q of rg.getClientRects()) if (q.width >= 1) { l = Math.min(l, q.left - cr.left); r = Math.max(r, q.right - cr.left); }
        t = Math.min(t, box.top - ty - cr.top); b = Math.max(b, box.bottom - ty - cr.top);
      });
      return l < Infinity ? { l, t, r, b } : null;
    }
    function holes(els, cr) {
      const out = [];
      els.forEach(el => {
        let ty = 0; try { ty = new DOMMatrixReadOnly(getComputedStyle(el).transform).m42; } catch (e) { }
        const rg = document.createRange(); rg.selectNodeContents(el);
        for (const q of rg.getClientRects()) if (q.width >= 1 && q.height >= 1) out.push([q.left - cr.left - 9, q.top - ty - cr.top - 7, q.right - cr.left + 9, q.bottom - ty - cr.top + 7]);
      });
      return out;
    }
    function place() {
      const cr = cv.getBoundingClientRect(), bar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 64;
      const top = Math.max(0, bar - cr.top) + 14, C = extent(copy, cr), S = extent(strict, cr), gap = 18;
      const wide = cr.left > 1;
      const beside = (cap) => {
        const x0 = C ? Math.max(0, C.r + gap) : 0, R = Math.min(cap, (W - 8 - x0) / 2.6, (H - top - 12) / 2), mid = C ? (C.t + C.b) / 2 : H * 0.48;
        return { mode: 'beside', R, cx: Math.min(W - R - 8, Math.max(W * 0.6, x0 + 1.6 * R)), cy: Math.max(top + R, Math.min(H - R - 12, mid)), floor: H - 12, alpha: 1 };
      };
      let g;
      if (story && wide) g = { mode: 'beside', R: Math.min(W * 0.20, H * 0.30), cx: W * 0.735, cy: H * 0.42, floor: H - 12, alpha: 1 };
      else if (wide || !C) g = beside(Math.min(W * 0.30, H * 0.36));
      else {
        const cap = story ? W * 0.40 : Math.min(W * 0.30, H * 0.36);
        const room = (y0, y1, mode) => ({ mode, R: Math.min(cap, (y1 - y0) / 2), cy: (y0 + y1) / 2, floor: y1, alpha: 1 });
        const side = beside(cap), pick = [side, room(C.b + gap, H - 12, 'below'), room(top, C.t - gap, 'above')].reduce((a, b) => (b.R > a.R ? b : a));
        if (pick.R >= Math.min(cap, 54)) g = pick;
        else if (S) g = { ...room(S.b + gap, H - 12, 'under'), mode: 'under', alpha: 0.7 };
        else { const R = W * 0.40; g = { mode: 'behind', R, cy: Math.max(H * 0.3, top + R * 0.6), floor: H - 12, alpha: 0.55 }; }
        g.R = Math.max(24, g.R);
        if (g.mode !== 'beside') g.cx = Math.max(g.R + 8, Math.min(W - g.R - 8, story ? W * 0.62 : W * 0.6));
        if (g.mode === 'under' || g.mode === 'behind') g.holes = holes(copy, cr);
      }
      g.top = top; g.bead = W < 600 ? 1.6 : 1.25;
      G = g; cv.dataset.globe = g.mode;
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
      const body = ctx.createRadialGradient(cx - R * 0.38, cy - R * 0.42, R * 0.05, cx, cy, R);
      body.addColorStop(0, rgba(GREEN, 0.075)); body.addColorStop(0.55, rgba(IVORY, 0.03)); body.addColorStop(1, rgba(IVORY, 0.012));
      ctx.fillStyle = body; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
      ctx.lineWidth = 1;
      orbits.forEach((o, oi) => {
        ctx.beginPath(); let pen = false;
        for (let i = 0; i <= 180; i++) { const [x, y, z] = onOrbit(o, i / 180 * TAU, v); if (hidden(x, y, z) || out(x, y)) { pen = false; continue; } if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } }
        ctx.strokeStyle = rgba(oi ? IVORY : GREEN, oi ? 0.16 : 0.26); ctx.stroke();
      });
      const eb = new Map();
      sphere.forEach(pt => {
        const lo = pt.lo + v.spin, q = rot([Math.cos(pt.la) * Math.sin(lo), Math.sin(pt.la), Math.cos(pt.la) * Math.cos(lo)], v.tilt, 0, 0);
        if (q[2] <= 0.04 || out(cx + q[0] * R, cy + q[1] * R)) return;
        const k = Math.round((0.22 + 0.38 * Math.pow(q[2], 1.2)) * 50);
        let f = eb.get(k); if (!f) eb.set(k, f = []); f.push(cx + q[0] * R, cy + q[1] * R, bead * (0.75 + 0.6 * q[2]));
      });
      eb.forEach((f, k) => { ctx.beginPath(); for (let i = 0; i < f.length; i += 3) { ctx.moveTo(f[i] + f[i + 2], f[i + 1]); ctx.arc(f[i], f[i + 1], f[i + 2], 0, TAU); } ctx.fillStyle = rgba(IVORY, k / 50); ctx.fill(); });
      const te = Math.floor((tau - PHASE) / P) * P + PHASE, u = (tau - te) / FALL, rj = u >= 0 && u <= 1 ? reject(te) : null;
      if (rj) {
        const fade = u < 0.7 ? 1 : Math.max(0, 1 - (u - 0.7) / 0.3), at = (s) => [rj.x0 + rj.dx * s, rj.y0 + rj.drop * Math.pow(s, 1.6)];
        ctx.beginPath(); let pen = false; for (let i = 0; i <= 14; i++) { const [x, y] = at(u * i / 14); if (out(x, y)) { pen = false; continue; } if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; } }
        ctx.setLineDash([2, 3.5]); ctx.strokeStyle = rgba(RED, 0.55 * fade); ctx.lineWidth = 1; ctx.stroke(); ctx.setLineDash([]);
        if (u < 0.18) { const k = u / 0.18; ctx.beginPath(); ctx.arc(rj.x0, rj.y0, 4 + 7 * k, 0, TAU); ctx.strokeStyle = rgba(RED, 0.5 * (1 - k)); ctx.stroke(); }
        const [mx, my] = at(u); if (!out(mx, my)) { ctx.beginPath(); ctx.arc(mx, my, small ? 2.6 : 2.2, 0, TAU); ctx.fillStyle = rgba(RED, 0.95 * fade); ctx.fill(); }
      }
      const [px, py, pz] = ringAt(tau);
      if (!hidden(px, py, pz) && !out(px, py)) { ctx.beginPath(); ctx.arc(px, py, small ? 4.2 : 3.6, 0, TAU); ctx.strokeStyle = rgba(GREEN, 0.95); ctx.lineWidth = 1.3; ctx.stroke(); }
      ctx.globalAlpha = 1;
    }
    const speedAt = (p, t) => { const d = (t - p.t0) / 1000; if (d < RAMP) return p.s0 + (1 - p.s0) * d / RAMP; const x = (p.tEnd - t) / 1000 / EASE; return x >= 1 ? 1 : Math.max(0, x * x); };
    function tauAt(p, t) {
      if (t >= p.tEnd) return p.tauEnd;
      const d = Math.max(0, (t - p.t0) / 1000), x = (p.tEnd - t) / 1000 / EASE;
      if (x < 1) return p.tauEnd - EASE / 3 * x * x * x;
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
    function request() {
      if (frameId || !visible || document.hidden || !plan) return;
      if (!rests()) { last = performance.now(); frameId = requestAnimationFrame(frame); return; }
      if (tau !== plan.tauEnd) { tau = plan.tauEnd; draw(); }
      cv.dataset.still = '';
    }
    function stop() { cancelAnimationFrame(frameId); frameId = 0; }
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
    tau = 2.4; resize();
    window.addEventListener('resize', resize);
    if (document.fonts) document.fonts.ready.then(relayout);
    setTimeout(relayout, 1800);
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    if (prefersReduced) { cv.dataset.still = ''; return; }
    const t0 = performance.now(), still = tau;
    plan = { t0, s0: 0, tau0: still - (RAMP / 2 + (WAKE / 1000 - RAMP - EASE) + EASE / 3), tauEnd: still, tEnd: t0 + WAKE };
    tau = plan.tau0; draw();
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
