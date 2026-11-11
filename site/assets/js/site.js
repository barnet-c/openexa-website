/* OpenEXA: shared behaviour (nav, chapter readout, menu sheet, jumps, page turns, scenes, footer, clocks, ready signal, kinetic type, reveals) */
(function () {
  'use strict';

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const reducedMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const pad = (n) => String(n).padStart(2, '0');
  const clamp01 = (v) => v < 0 ? 0 : v > 1 ? 1 : v;
  const root = document.documentElement;
  const runList = ((document.currentScript && document.currentScript.getAttribute('data-after-paint')) || '').split(/\s+/).filter(Boolean);
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
  const toggle = $('.nav-toggle');
  const sheet = $('.nav-sheet');
  const close = $('main > .cta-band');
  let navH = 72, vh = 0, maxScroll = 1, clearUntil = -1, bands = [], tones = [], navRaf = 0, menuOpen = false, lastY = 0, closeTop = Infinity;

  const pins = $$('[data-scene="pin"]');
  if (pins.length) root.classList.add('tone-parts'); // the bar reads a tone named inside an unpinned scene (measure(), below)
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

  let live = [], fillP = -1, current = -2, shownK = -3, chOpen = false;
  const ui = {};
  if (nav) {
    ui.progress = document.createElement('div'); ui.progress.className = 'nav-progress'; ui.progress.setAttribute('aria-hidden', 'true');
    ui.fill = ui.progress.appendChild(document.createElement('b'));
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
    const run = !narrowMQ.matches && $('.nav-run:not([hidden])', nav); // hc31r: the transport stands between the readout and the links
    const key = [window.innerWidth, rootPx, live.map(c => c.k).join(), document.fonts ? document.fonts.status : '', run ? Math.round(run.getBoundingClientRect().left) : 0].join('|');
    if (key === fitKey) return;
    fitKey = key;
    live.forEach(c => { c.mode = 'full'; });
    const links = (midMQ.matches || run || (zoomed && !narrowMQ.matches && window.innerWidth / rootPx < 80)) && $('.nav-links', nav);
    if (narrowMQ.matches || links) {
      const box = document.createElement('span'); box.className = 'nav-ch-measure'; box.setAttribute('aria-hidden', 'true');
      const forms = [];
      live.forEach(c => { forms.push([c, 'full', lineFor(c.k, 'full')]); if (c.short && c.short !== c.title) forms.push([c, 'short', lineFor(c.k, 'short')]); });
      forms.forEach(f => box.appendChild(f[2]));
      ui.btn.appendChild(box);
      const r0 = ui.roll.getBoundingClientRect();
      const avail = links ? Math.min(parseFloat(getComputedStyle(ui.roll).maxWidth) || 1e4, (run || links).getBoundingClientRect().left
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
    const cb = close && !close.classList.contains('is-whole') && bands.find(b => b.el === close);
    closeTop = cb ? cb.top : Infinity;
    tones = [];
    pins.forEach(s => {
      if (!pinOf(s)) {
        // unpinned (phones, reduced motion): a part of the stage that names its tone (data-tone) is a band of its own
        $$(':scope > .scene-stage > [data-tone]', s).forEach(t => { const r = t.getBoundingClientRect(); tones.push({ el: s, top: r.top + y, bottom: r.bottom + y, dark: t.dataset.tone === 'dark' }); });
        return;
      }
      const end = s.getBoundingClientRect().bottom + y;
      const m = $$(':scope > [data-scene-tone]', s).filter(t => t.getClientRects().length)
        .map(t => ({ el: s, top: t.getBoundingClientRect().top + y, dark: t.dataset.sceneTone === 'dark' })).sort((p, q) => p.top - q.top);
      m.forEach((t, i) => { t.bottom = i + 1 < m.length ? m[i + 1].top : end; tones.push(t); });
    });
    live = chapters.filter(c => c.el.getClientRects().length > 0);
    chapters.forEach(c => { c.li.hidden = !live.includes(c); });
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
    fillP = -1;
    fitModes();
    update();
  }
  const queue = () => { if (!navRaf) navRaf = requestAnimationFrame(() => { navRaf = 0; update(); }); };
  // hc31r: the transport takes its place between the readout and the links (or changes its width) after the readout was fitted
  let runFit = 0;
  document.addEventListener('oxa:run', () => { clearTimeout(runFit); runFit = setTimeout(fitModes, 150); });

  function update() {
    if (!nav) return;
    const y = lastY = window.scrollY;
    let dark = false, band = null;
    const edge = y + navH * 1.1;
    for (const b of tones) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    if (!band) for (const b of bands) if (edge >= b.top && edge < b.bottom) { dark = b.dark; band = b; break; }
    if (darkStart) { const opening = bands[0] && bands[0].dark ? bands[0] : null; root.classList.toggle('is-paper-root', !!opening && y >= opening.bottom); }
    const clear = y <= (root.classList.contains('story-tiny') ? 16 : clearUntil) && !menuOpen;
    nav.classList.toggle('nav--solid', !clear);
    nav.classList.toggle('nav--dark', dark);
    if (themeMeta) {
      const ink = clear ? darkStart : dark || menuOpen;
      const want = ink ? '#0E1512' : '#F5F2EC';
      if (themeMeta.content !== want) themeMeta.content = want;
    }
    const p = clamp01(y / maxScroll);
    if (Math.abs(p - fillP) > 0.001) { fillP = p; ui.fill.style.transform = `scaleX(${p.toFixed(4)})`; }
    if (y + vh > closeTop && (y >= maxScroll - 1 || +getComputedStyle(close).getPropertyValue('--scene-p') >= 1)) { closeTop = Infinity; if (!close.classList.contains('cta-band--run')) close.classList.add('is-whole'); }
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
    if (inSheet && ui.panel.parentElement !== sheet) { setPanel(false); sheet.append(ui.panel); }
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
    root.classList.add('vt-leave');
    let vt;
    try { vt = document.startViewTransition(() => { root.classList.remove('vt-leave'); go(); }); } catch (err) { delete root.dataset.jump; root.classList.remove('vt-leave'); go(); return; }
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
    let ptrAt = -1e9;
    ['pointerdown', 'pointerup'].forEach(n => document.addEventListener(n, () => { ptrAt = performance.now(); }, { capture: true, passive: true }));
    document.addEventListener('focusin', e => {
      const t = e.target, s = t && t.closest && t.closest('[data-scene-end]') && pinOf(t);
      if (!s || performance.now() - sceneJumpAt < 1500 || performance.now() - ptrAt < 600) return;
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
  if (document.body.dataset.page === 'proof' && nav && !$('.nav-run', nav)) {
    const rec = document.createElement('span'), word = document.createElement('span'), read = document.createElement('i'), row = $('.container', nav);
    rec.className = 'nav-run nav-run--rec'; word.className = 'nav-run-s'; word.textContent = 'Record'; read.className = 'nav-run-g'; read.setAttribute('aria-hidden', 'true');
    rec.append(word, read);
    row.insertBefore(rec, $('.nav-links', row) || toggle);
  }
  let landed = Promise.resolve();
  const seen = new WeakSet();
  function turned(vt) {
    if (!vt) return;
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
  if (!OXA.turn) {
    OXA.turn = true;
    const docOf = u => { try { const x = new URL(u, location.href); return x.origin + x.pathname.replace(/(\/index)?(\.html)?\/*$/, ''); } catch (err) { return ''; } };
    const sent = v => { try { if (v === undefined) return JSON.parse(sessionStorage.getItem('oxa-turn') || 'null'); sessionStorage.setItem('oxa-turn', JSON.stringify(v)); } catch (err) { } return null; };
    const named = () => Array.from(document.querySelectorAll('[data-vt-dest], [style*="view-transition-name: fig"]'));
    const edge = () => { const b = document.querySelector('[data-run-boundary]'), r = b && b.getBoundingClientRect(); return r && r.width > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth ? b : null; };
    const look = b => { const c = getComputedStyle(b); return [c.borderTopLeftRadius, c.borderTopColor, c.borderBottomWidth]; };
    const arrive = (vt, early) => {
      root.classList.add('vt-in'); OXA.byTurn = true;
      const f = sent(), a = window.navigation && navigation.activation;
      const moving = () => document.getAnimations().some(x => x.effect && /^::view-transition/.test(x.effect.pseudoElement || '') && x.currentTime > 0);
      if (a && a.navigationType === 'traverse' && a.from && a.entry && a.entry.index < a.from.index && (early || !moving())) { try { vt.types.add('back'); } catch (err) { } }
      if (early && !(f && f.fig && docOf(f.to) === docOf(location.href) && Date.now() - f.at < 4000)) {
        const un = named(); un.forEach(d => d.style.setProperty('view-transition-name', 'none'));
        vt.finished.catch(() => {}).then(() => un.forEach(d => d.style.removeProperty('view-transition-name')));
      }
      // the match cut needs both ends: only at pagereveal can this page's boundary still take its name
      const b = early && f && f.b && docOf(f.to) === docOf(location.href) && Date.now() - f.at < 4000 ? edge() : null;
      if (b) {
        b.style.setProperty('view-transition-name', 'boundary');
        look(b).forEach((v, i) => { root.style.setProperty('--b-' + 'rcw'[i] + '0', f.b[i]); root.style.setProperty('--b-' + 'rcw'[i] + '1', v); });
        try { vt.types.add('match'); } catch (err) { }
        vt.finished.catch(() => {}).then(() => b.style.removeProperty('view-transition-name'));
      }
      const first = document.querySelector('main > :first-child'), band = first && !first.classList.contains('story') && first.getAnimations ? first : null;
      const whole = () => band && band.getAnimations({ subtree: true }).forEach(x => {
        const t = x.effect && x.effect.getComputedTiming && x.effect.getComputedTiming();
        if (t && t.iterations !== Infinity && x.timeline === document.timeline && x.playState !== 'finished') { try { x.finish(); } catch (err) { } }
      });
      let on = true;
      const tick = () => { whole(); if (on) requestAnimationFrame(tick); };
      tick();
      vt.finished.catch(() => {}).then(() => { on = false; });
      vt.ready.then(() => {
        if (!document.getAnimations().some(x => x.effect && x.effect.pseudoElement === '::view-transition-old(fig)')) return;
        const g = getComputedStyle(root, '::view-transition-group(fig)'), m = /matrix\(([^)]+)\)/.exec(g.transform), t = m ? parseFloat(m[1].split(',')[5]) : 0;
        root.style.setProperty('--vt-t', t + 'px'); root.style.setProperty('--vt-b', t + (parseFloat(g.height) || 0) + 'px');
      }, () => { });
    };
    addEventListener('pageswap', e => {
      if (!e.viewTransition) return;
      // a boundary under the open menu sheet (the page is inert then) is not on screen: no match cut from the menu
      const a = e.activation, m = document.querySelector('main'), b = scrollY < innerHeight / 2 && !(m && m.inert) ? edge() : null;
      if (b) b.style.setProperty('view-transition-name', 'boundary');
      sent({ to: a && a.entry ? a.entry.url : '', at: Date.now(), fig: named().some(d => getComputedStyle(d).viewTransitionName === 'fig'), b: b ? look(b) : null });
      root.classList.add('vt-leave');
    });
    addEventListener('pageshow', () => { root.classList.remove('vt-leave'); document.querySelectorAll('[data-run-boundary]').forEach(b => b.style.removeProperty('view-transition-name')); });
    addEventListener('pagereveal', e => { root.classList.remove('vt-leave'); if (e.viewTransition) arrive(e.viewTransition, true); });
    if (document.activeViewTransition && !root.dataset.jump && !root.classList.contains('vt-in')) arrive(document.activeViewTransition, false);
  }

  if (nav) {
    let mRaf = 0;
    const measureSoon = () => { if (!mRaf) mRaf = requestAnimationFrame(() => { mRaf = 0; measure(); }); };
    measureSoon();
    window.addEventListener('scroll', queue, { passive: true });
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
  // a jump lands whole (hc31r; proof's hc30r request): when one scroll event moves the page by nearly a screen or more (End, Home, a click in
  // the scrollbar, find-in-page, a script) what it lands on is shown at once; Page Down and the space bar move 87.5% of a screen and keep their entrances
  if (!prefersReduced) {
    let jumpY = window.scrollY;
    window.addEventListener('scroll', () => {
      const y = window.scrollY, d = Math.abs(y - jumpY);
      jumpY = y;
      if (d > window.innerHeight * 0.95) revealRange(y, y + window.innerHeight);
    }, { passive: true });
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

  if (!root.classList.contains('is-loaded')) {
    $$('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
    root.classList.add('is-loaded');
    document.dispatchEvent(new CustomEvent('oxa:loaded'));
  }
  // hc31r: a page whose scripts are plain tags lists the run's engines on this tag (data-after-paint, as afterpaint.js and home.js read it):
  // they start once the first paint is on screen, in order, so they are no request before it
  if (runList.length) {
    let went = false;
    const go = () => { if (went) return; went = true; runList.forEach(src => { const sc = document.createElement('script'); sc.src = src; sc.async = false; document.body.appendChild(sc); }); };
    if (document.visibilityState !== 'hidden' && window.PerformanceObserver && (PerformanceObserver.supportedEntryTypes || []).includes('paint')) {
      new PerformanceObserver((list, po) => { if (list.getEntriesByName('first-contentful-paint').length) { po.disconnect(); setTimeout(go, 0); } }).observe({ type: 'paint', buffered: true });
      setTimeout(go, 5000);
    } else if (document.visibilityState === 'hidden' || document.readyState === 'complete') go();
    else window.addEventListener('load', go, { once: true });
  }
  window.addEventListener('beforeprint', () => $$('details.footer-legal').forEach(d => { d.dataset.wasOpen = d.open ? '1' : ''; d.open = true; }));
  window.addEventListener('afterprint', () => $$('details.footer-legal').forEach(d => { d.open = d.dataset.wasOpen === '1'; }));
})();
