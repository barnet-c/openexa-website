/* OpenEXA: Home's start-up (home group): paint first, then data-after-paint's scripts in order. */
(function () {
  'use strict';
  const chain = document.querySelector('[data-chain]'), more = chain && chain.querySelector('[data-chain-more]');
  if (more) {
    const set = (open) => {
      chain.classList.toggle('is-folded', !open);
      more.setAttribute('aria-expanded', String(open));
      more.textContent = open ? 'Show the first four records' : 'Show all eight records';
    };
    set(false); more.hidden = false;
    more.addEventListener('click', () => set(chain.classList.contains('is-folded')));
    chain.addEventListener('input', () => set(true));
    chain.addEventListener('click', e => { if (e.target.closest('[data-chain-try]')) set(true); });
  }
})();
(function () {
  'use strict';
  const me = document.currentScript, root = document.documentElement;
  const disc = document.querySelector('.footer .disc');
  if (disc && !disc.closest('details')) {
    const d = document.createElement('details'), s = document.createElement('summary');
    d.className = 'footer-legal'; s.textContent = 'Legal & disclosures';
    disc.before(d); d.append(s, disc);
  }
  const OXA = window.OXA = window.OXA || {};
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
    const arrive = (vt, early) => {
      root.classList.add('vt-in'); OXA.byTurn = true;
      const f = sent(), a = window.navigation && navigation.activation;
      const moving = () => document.getAnimations().some(x => x.effect && /^::view-transition/.test(x.effect.pseudoElement || '') && x.currentTime > 0);
      if (a && a.navigationType === 'traverse' && a.from && a.entry && a.entry.index < a.from.index && (early || !moving())) { try { vt.types.add('back'); } catch (err) { } }
      if (early && !(f && f.fig && docOf(f.to) === docOf(location.href) && Date.now() - f.at < 4000)) {
        const un = named(); un.forEach(d => d.style.setProperty('view-transition-name', 'none'));
        vt.finished.catch(() => {}).then(() => un.forEach(d => d.style.removeProperty('view-transition-name')));
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
      const a = e.activation;
      sent({ to: a && a.entry ? a.entry.url : '', at: Date.now(), fig: named().some(d => getComputedStyle(d).viewTransitionName === 'fig') });
      root.classList.add('vt-leave');
    });
    addEventListener('pageshow', () => root.classList.remove('vt-leave'));
    addEventListener('pagereveal', e => { root.classList.remove('vt-leave'); if (e.viewTransition) arrive(e.viewTransition, true); });
    if (document.activeViewTransition && !root.dataset.jump && !root.classList.contains('vt-in')) arrive(document.activeViewTransition, false);
  }
  if (window.innerWidth > root.clientWidth) root.classList.add('sb-keep');
  const draws = { 'ledger.js': '[data-ledger]', 'lane.js': '[data-lane]', 'arch.js': '[data-arch]' };
  const list = ((me && me.getAttribute('data-after-paint')) || '').split(/\s+/).filter(src => {
    const k = src && draws[src.split('/').pop()];
    return !!src && (!k || !!document.querySelector(k));
  });
  if (!list.length) return;
  if (list.some(src => /story\.js$/.test(src))) root.classList.add('story-wait');
  const FIRST = /(?:^|\/)(?:loader|story|site)\.js$/;
  const queue = [];
  let pumping = false;
  const script = (src) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = false;
    if (/story\.js$/.test(src)) s.addEventListener('error', () => root.classList.add('story-failed'));
    return s;
  };
  const pump = () => {
    const src = queue.shift();
    if (!src) { pumping = false; return; }
    pumping = true;
    const s = script(src), on = () => { if (document.hidden) setTimeout(pump, 0); else requestAnimationFrame(() => setTimeout(pump, 0)); };
    s.addEventListener('load', on); s.addEventListener('error', on);
    document.body.appendChild(s);
  };
  const add = (srcs, done) => {
    let last = null;
    srcs.forEach(src => document.body.appendChild(last = script(src)));
    if (done && last) { last.addEventListener('load', done); last.addEventListener('error', done); }
  };
  const spread = (srcs) => {
    srcs.forEach(src => { const l = document.createElement('link'); l.rel = 'preload'; l.as = 'script'; l.href = src; document.head.appendChild(l); queue.push(src); });
    if (!pumping) pump();
  };
  const nav = (performance.getEntriesByType && performance.getEntriesByType('navigation')[0]) || {}, H = history, K = 'oxa:at';
  const back = /^(reload|back)/.test(nav.type);
  let started = false, later = back || location.hash.length > 1, at = null, moved = 0;
  const secs = () => [...document.querySelectorAll('main > section[id]')];
  const hold = (on) => { for (const c of secs()) { if (c.id === at[0]) break; c.style.overflowAnchor = on ? 'none' : ''; } };
  const land = () => { const e = document.getElementById(at[0]); if (e && !moved) scrollTo({ top: e.getBoundingClientRect().top + scrollY + at[1], behavior: 'instant' }); };
  try {
    at = back && JSON.parse(sessionStorage.getItem(K));
    let place = null, pt = 0;
    addEventListener('scroll', () => { clearTimeout(pt); pt = setTimeout(() => { const e = secs().filter(c => c.getBoundingClientRect().top < innerHeight / 3).pop(); place = e ? [e.id, -Math.round(e.getBoundingClientRect().top)] : null; }, 300); }, { passive: true });
    addEventListener('pagehide', () => {
      sessionStorage.setItem(K, JSON.stringify(place));
      if (place) H.scrollRestoration = 'manual';
    });
    addEventListener('pageshow', e => { if (e.persisted) H.scrollRestoration = 'auto'; });
  } catch (e) { }
  if (at) { ['wheel', 'touchstart', 'keydown'].forEach(t => addEventListener(t, () => { moved = 1; }, { once: true, passive: true })); hold(1); requestAnimationFrame(land); }
  const rest = () => { if (later) return; later = true; spread(list.filter(src => !FIRST.test(src))); };
  const lifted = () => {
    const l = document.querySelector('.loader'), up = () => !l.isConnected || l.classList.contains('is-done');
    if (!l || up()) return rest();
    const mo = new MutationObserver(() => { if (up()) { mo.disconnect(); rest(); } });
    mo.observe(l, { attributes: true }); mo.observe(document.body, { childList: true });
  };
  const start = () => {
    if (started) return;
    started = true;
    add(list.filter(src => later || FIRST.test(src)), at ? () => requestAnimationFrame(() => { land(); hold(0); H.scrollRestoration = 'auto'; }) : null);
    if (root.classList.contains('is-loaded')) lifted();
    else document.addEventListener('oxa:loaded', lifted, { once: true });
    setTimeout(rest, 2500);
  };
  if (document.visibilityState === 'hidden') { start(); return; }
  if (window.PerformanceObserver && (PerformanceObserver.supportedEntryTypes || []).includes('paint')) {
    const po = new PerformanceObserver(entries => {
      if (entries.getEntriesByName('first-contentful-paint').length) { po.disconnect(); setTimeout(start, 0); }
    });
    po.observe({ type: 'paint', buffered: true });
    setTimeout(start, 5000);
  } else if (document.readyState === 'complete') start();
  else addEventListener('load', start, { once: true });
})();
