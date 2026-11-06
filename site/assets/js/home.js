/* OpenEXA: Home's start-up (home group). The page paints first; data-after-paint's scripts follow in order: loader, story
   and site at the first paint (5 s net), the instruments as the curtain goes (2.5 s net), all at once on a page opened
   mid-way. A reload or Back lands the reader in the chapter they left in the first frame (the browser's restore would
   land on the static figures, shorter than the live ones). .story-wait / .story-failed mark story.js. */
(function () {
  'use strict';
  // §06 on phones: the chain shows records #4f23-#4f26; the control, an edit or 'Change a record' opens all eight
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
  // an engine whose instrument the page does not draw is not fetched (a safety net: Home's list dropped ledger.js and
  // lane.js on 1 Nov, when its lane and running log left the page; hc5: §02 draws Platform's plate, the explorer is Platform's)
  const draws = { 'ledger.js': '[data-ledger]', 'lane.js': '[data-lane]', 'arch.js': '[data-arch]' };
  const list = ((me && me.getAttribute('data-after-paint')) || '').split(/\s+/).filter(src => {
    const k = src && draws[src.split('/').pop()];
    return !!src && (!k || !!document.querySelector(k));
  });
  if (!list.length) return;
  if (list.some(src => /story\.js$/.test(src))) root.classList.add('story-wait');
  const FIRST = /(?:^|\/)(?:loader|story|site)\.js$/;
  // (award a2) the instruments at the curtain run one per frame, in the list's order: fetched at once (preload), each a
  // frame after the one before it has run (together they made one 100+ ms frame in the hand-off on a 4x-throttled phone).
  // The first batch (loader, story, site) still runs at once: the loader's hand-off, and so the headline, waits for the
  // overture's first frame and the window's load, and spacing that batch put both ~75 ms later in Lighthouse.
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
  const add = (srcs, done) => { // at once, in order
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
  // while the instruments grow, the chapters above the place are no scroll anchors: the place holds
  const hold = (on) => { for (const c of secs()) { if (c.id === at[0]) break; c.style.overflowAnchor = on ? 'none' : ''; } };
  const land = () => { const e = document.getElementById(at[0]); if (e && !moved) scrollTo({ top: e.getBoundingClientRect().top + scrollY + at[1], behavior: 'instant' }); };
  try {
    at = back && JSON.parse(sessionStorage.getItem(K));
    // the place, read as scrolling settles (by pagehide the page has already reacted to being hidden)
    let place = null, pt = 0;
    addEventListener('scroll', () => { clearTimeout(pt); pt = setTimeout(() => { const e = secs().filter(c => c.getBoundingClientRect().top < innerHeight / 3).pop(); place = e ? [e.id, -Math.round(e.getBoundingClientRect().top)] : null; }, 300); }, { passive: true });
    addEventListener('pagehide', () => {
      sessionStorage.setItem(K, JSON.stringify(place));
      if (place) H.scrollRestoration = 'manual'; // (in the overture the browser's is right)
    });
    addEventListener('pageshow', e => { if (e.persisted) H.scrollRestoration = 'auto'; });
  } catch (e) { /* no storage */ }
  if (at) { ['wheel', 'touchstart', 'keydown'].forEach(t => addEventListener(t, () => { moved = 1; }, { once: true, passive: true })); hold(1); requestAnimationFrame(land); }
  const rest = () => { if (later) return; later = true; spread(list.filter(src => !FIRST.test(src))); };
  // '100' sets the curtain going (.is-done; its beat is a CSS delay the compositor runs): the instruments start then
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
