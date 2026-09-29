/* OpenEXA — shared behaviour
   nav · clocks · chapters · loader · kinetic type · manifesto · reveals · counters · forms · ledger stream · 2D swarm fallback */
(function () {
  'use strict';

  const CONTACT = document.body.dataset.contact || 'access@openexa.com'; // inbox for the access form — set data-contact on <body> of access.html
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  /* ---------------- nav ---------------- */
  const nav = $('.nav');
  const darkStart = document.body.dataset.nav === 'dark-start';
  const progress = document.createElement('i'); progress.className = 'nav-progress'; if (nav) nav.appendChild(progress);
  let lastY = window.scrollY;
  function updateNav() {
    if (!nav) return;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const y = window.scrollY;
    progress.style.transform = `scaleX(${max > 0 ? Math.min(1, y / max) : 0})`;
    // hide on the way down, return on the way up
    const open = document.body.classList.contains('nav-open');
    if (!open && y > 140 && y > lastY + 6) nav.classList.add('nav--hidden');
    else if (open || y < lastY - 6 || y < 140) nav.classList.remove('nav--hidden');
    lastY = y;
    if (!darkStart) { nav.classList.add('nav--solid'); return; }
    const hero = $('.story, .hero, .page-hero--dark');
    const staticStory = document.documentElement.classList.contains('no-webgl'); // beats stack and scroll under the nav
    const threshold = hero && !staticStory ? hero.offsetHeight + hero.offsetTop - nav.offsetHeight - 8 : 40;
    nav.classList.toggle('nav--solid', y > threshold || open);
  }
  updateNav();
  window.addEventListener('scroll', updateNav, { passive: true });
  window.addEventListener('resize', updateNav);

  const toggle = $('.nav-toggle');
  const menu = $('.nav-menu');
  if (toggle) {
    if (menu) {
      menu.id = 'site-menu';
      menu.setAttribute('role', 'navigation');
      menu.setAttribute('aria-label', 'Mobile');
      toggle.setAttribute('aria-controls', menu.id);
    }
    const setMenu = (open) => {
      document.body.classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      updateNav();
    };
    toggle.addEventListener('click', () => setMenu(!document.body.classList.contains('nav-open')));
    $$('.nav-menu a').forEach(a => a.addEventListener('click', () => setMenu(false)));
    document.addEventListener('keydown', e => {
      if (!document.body.classList.contains('nav-open')) return;
      if (e.key === 'Escape') {
        setMenu(false);
        toggle.focus();
      } else if (e.key === 'Tab' && menu) {
        const links = $$('a[href]', menu);
        const last = links[links.length - 1];
        if (e.shiftKey && document.activeElement === toggle && last) {
          e.preventDefault(); last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault(); toggle.focus();
        }
      }
    });
    window.matchMedia('(min-width: 961px)').addEventListener('change', e => {
      if (e.matches) setMenu(false);
    });
  }
  const pageKey = path => path.replace(/\/+$/, '').split('/').pop().replace(/\.html$/, '') || 'index';
  const here = pageKey(location.pathname);
  $$('.nav-links a, .nav-menu a').forEach(a => {
    const href = (a.getAttribute('href') || '').split(/[?#]/)[0];
    if (href && pageKey(href) === here) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  });
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
  const pad = (n) => String(n).padStart(2, '0');
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

  /* ---------------- chapters — a fixed index of the page, lit as you scroll ---------------- */
  const chapterSecs = $$('section[data-chapter]');
  if (chapterSecs.length > 2 && 'IntersectionObserver' in window) {
    const rail = document.createElement('nav'); rail.className = 'chapters'; rail.setAttribute('aria-label', 'Chapters');
    rail.innerHTML = chapterSecs.map((s, i) => `<a href="#${s.id}"><span>${s.dataset.chapter}</span><b>${pad(i + 1)}</b></a>`).join('');
    document.body.appendChild(rail);
    const links = $$('a', rail);
    const cio = new IntersectionObserver(entries => {
      entries.forEach(e => { if (e.isIntersecting) { const i = chapterSecs.indexOf(e.target); links.forEach((a, j) => a.classList.toggle('is-on', j === i)); } });
    }, { rootMargin: '-45% 0px -45% 0px', threshold: 0 });
    chapterSecs.forEach(s => cio.observe(s));
    const first = chapterSecs[0];
    const showRail = () => rail.classList.toggle('is-on', window.scrollY > first.offsetTop - window.innerHeight * 0.6 && window.scrollY < document.documentElement.scrollHeight - window.innerHeight * 1.8);
    showRail(); window.addEventListener('scroll', showRail, { passive: true });
  }

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

  /* ---------------- ticker ---------------- */
  $$('.ticker-track').forEach(t => { const ul = $('ul', t); if (ul && t.children.length === 1) t.appendChild(ul.cloneNode(true)); });

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
  if ('IntersectionObserver' in window && !prefersReduced) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    revealEls.forEach(el => { el.classList.add('will-reveal'); io.observe(el); });
  } else revealEls.forEach(el => el.classList.add('is-in'));

  /* ---------------- preloader (homepage) ---------------- */
  const loader = $('.loader');
  if (loader) {
    document.body.classList.add('is-loading');
    const count = $('.loader-count', loader), bar = $('.loader-bar i', loader);
    let p = 0, done = false;
    const t0 = performance.now();
    // time-based, so a slow GPU never stretches the count: 0 → 92 in 1.1 s, then straight to 100 once the page is ready
    const ready = Promise.all([document.fonts ? document.fonts.ready : Promise.resolve(), document.readyState === 'complete' ? Promise.resolve() : new Promise(r => window.addEventListener('load', r, { once: true }))]);
    const tick = (now) => {
      const target = done ? 100 : Math.min(92, (now - t0) / 1100 * 92);
      p += (target - p) * 0.18;
      if (count) count.textContent = Math.round(p).toString().padStart(2, '0');
      if (bar) bar.style.setProperty('--p', (p / 100).toFixed(3));
      if (p > 99.4 && done) { finish(); return; }
      requestAnimationFrame(tick);
    };
    const finish = () => {
      if (count) count.textContent = '100';
      loader.classList.add('is-done');
      document.body.classList.remove('is-loading');
      $$('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
      setTimeout(() => loader.remove(), 1200);
    };
    ready.then(() => { done = true; });
    setTimeout(() => { done = true; }, 1800); // never hold the page hostage
    if (prefersReduced) { finish(); } else requestAnimationFrame(tick);
  } else {
    $$('.beat-0 [data-split]').forEach(el => el.classList.add('is-in'));
  }
  /* ---------------- count-up ---------------- */
  const fmt = (n, dec) => n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
  function countUp(el) {
    const target = parseFloat(el.dataset.count), dec = parseInt(el.dataset.decimals || '0', 10);
    const prefix = el.dataset.prefix || '', suffix = el.dataset.suffix || '';
    if (prefersReduced) { el.textContent = prefix + fmt(target, dec) + suffix; return; }
    const dur = 1400, t0 = performance.now(), ease = t => 1 - Math.pow(1 - t, 4);
    (function step(now) { const p = Math.min(1, (now - t0) / dur); el.textContent = prefix + fmt(target * ease(p), dec) + suffix; if (p < 1) requestAnimationFrame(step); })(t0);
  }
  const counters = $$('[data-count]');
  if (counters.length) {
    if ('IntersectionObserver' in window) {
      const cio = new IntersectionObserver((entries) => { entries.forEach(e => { if (e.isIntersecting) { countUp(e.target); cio.unobserve(e.target); } }); }, { threshold: 0.4 });
      counters.forEach(c => cio.observe(c));
    } else counters.forEach(countUp);
  }

  /* ---------------- economics calculator ---------------- */
  $$('[data-calc]').forEach(calc => {
    const range = $('input[type=range]', calc);
    const tiers = [100e6, 250e6, 500e6, 1e9, 2.5e9, 5e9, 10e9];
    const money = v => v >= 1e9 ? '$' + (v / 1e9).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'B' : '$' + Math.round(v / 1e6).toLocaleString('en-US') + 'M';
    const update = () => {
      const aum = tiers[parseInt(range.value, 10)];
      const ret = aum * 0.0004 * 250;   // 4 bps/day × 250 trading days
      const arr = ret * 0.10;           // OpenEXA keeps 10% of yield generated
      $('[data-out=aum]', calc).textContent = money(aum);
      $('[data-out=ret]', calc).textContent = money(ret);
      $('[data-out=arr]', calc).textContent = money(arr);
    };
    range.addEventListener('input', update); update();
  });

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
        const body = Object.entries(data).map(([key, value]) => `${key}: ${value}`).join('\r\n');
        mail.href = `mailto:${CONTACT}?subject=${encodeURIComponent('OpenEXA introduction - ' + data.interest)}&body=${encodeURIComponent(body)}`;
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

  /* ---------------- illustrative ledger stream ---------------- */
  $$('[data-ledger-stream]').forEach(box => {
    const body = $('.body', box), counter = $('[data-stream-count]', box);
    const TOOLS = ['source-01', 'registry-02', 'workflow-01', 'records-03'];
    let n = 0x4f21, active = [], running = true;
    const hex = v => '#' + v.toString(16).padStart(4, '0');
    const now = () => { const d = new Date(); return d.toTimeString().slice(0, 8) + '.' + String(d.getMilliseconds()).padStart(3, '0'); };
    const push = (cls, st, detail) => {
      const prev = hex(n - 1); const id = hex(n++);
      const ln = document.createElement('div'); ln.className = 'ln ' + cls;
      ln.innerHTML = `<span class="h">${id}</span><span class="t">${now()}</span><span class="s">${st}</span><span class="d">${detail}</span><span class="p">prev ${prev}</span>`;
      body.appendChild(ln);
      while (body.children.length > 12) body.removeChild(body.firstChild);
      if (counter) counter.textContent = (n - 0x4f21).toLocaleString('en-US');
    };
    const rnd = a => a[Math.floor(Math.random() * a.length)];
    const agent = (p) => `${p}-${String(Math.floor(Math.random() * 900) + 100).padStart(4, '0')}`;
    const order = () => {
      const job = 'L-' + String(Math.floor(Math.random() * 9000) + 1000), tool = rnd(TOOLS);
      const steps = [
        ['dim', 'PROPOSED', `agent=domain:${agent('a')} · lifecycle=${job} · next step`],
        ['', 'VALIDATED', `${job} · schema checked · inputs complete · scope checked`],
      ];
      if (Math.random() < 0.09) { steps.push(['bad', 'REJECTED', `council · ${rnd(['permission missing', 'approval required', 'input outside policy'])} · recorded`]); return steps; }
      steps.push(['', 'APPROVED', 'council · policy v7 · bounded action']);
      steps.push(['', 'SUBMITTED', `agent=exec:${agent('e')} · tool=${tool} · idempotent`]);
      steps.push(['', 'COMPLETED', `${job} · action confirmed · receipt attached`]);
      steps.push(['ok', 'SETTLED', `agent=records:${agent('r')} · previous hash linked`]);
      return steps;
    };
    let queue = [], timer = 0;
    const loop = () => {
      if (!running) return;
      if (!queue.length) queue = order();
      const [cls, st, detail] = queue.shift(); push(cls, st, detail);
      timer = setTimeout(loop, 520 + Math.random() * 900);
    };
    const start = () => { if (running) return; running = true; loop(); };
    const stop = () => { running = false; clearTimeout(timer); };
    running = false;
    for (let i = 0; i < 6; i++) { if (!queue.length) queue = order(); const [c, s, d] = queue.shift(); push(c, s, d); }
    if (!prefersReduced) {
      if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { e.isIntersecting && !document.hidden ? start() : stop(); }, { threshold: 0.1 }).observe(box);
      else start();
      document.addEventListener('visibilitychange', () => {
        const rect = box.getBoundingClientRect();
        if (!document.hidden && rect.bottom > 0 && rect.top < window.innerHeight) start();
        else stop();
      });
    }
  });

  /* ---------------- 2D swarm (interior heroes & no-WebGL fallback) ---------------- */
  const canvas = $('canvas[data-swarm]');
  const inStory = canvas && canvas.closest('.story');
  if (canvas && (!inStory || document.documentElement.classList.contains('no-webgl'))) initSwarm(canvas);

  function initSwarm(cv) {
    const ctx = cv.getContext('2d', { alpha: true });
    let W = 0, H = 0, dpr = 1, running = true, visible = true, t = 0, last = performance.now();
    const mouse = { x: 0, y: 0, tx: 0, ty: 0 };
    const IVORY = [245, 242, 236], KHAKI = [172, 166, 142], GREEN = [79, 203, 147], RED = [214, 96, 86];
    const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
    const sphere = [];
    for (let lat = -80; lat <= 80; lat += 10) { const la = lat * Math.PI / 180; const n = Math.max(6, Math.round(40 * Math.cos(la))); for (let k = 0; k < n; k++) sphere.push({ la, lo: (k + 0.5) / n * Math.PI * 2 }); }
    const NODES = ['Signal', 'Predict', 'Decide', 'Approve', 'Execute', 'Settle'];
    const rings = [{ r: 1.38, tiltX: 1.12, rotZ: -0.38, speed: 0.11, count: 150, labelled: true }, { r: 1.62, tiltX: 1.42, rotZ: 0.55, speed: -0.07, count: 110, labelled: false }];
    rings.forEach(ring => { ring.agents = []; for (let i = 0; i < ring.count; i++) ring.agents.push({ a: Math.random() * Math.PI * 2, v: 0.75 + Math.random() * 0.6, off: (Math.random() - 0.5) * 0.06, flash: 0, kind: 0, size: 0.8 + Math.random() * 1.2, lastNode: -1 }); });
    function resize() { dpr = Math.min(3, window.devicePixelRatio || 1); const r = cv.getBoundingClientRect(); W = Math.max(1, Math.floor(r.width)); H = Math.max(1, Math.floor(r.height)); cv.width = Math.floor(W * dpr); cv.height = Math.floor(H * dpr); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); if (prefersReduced) draw(0); }
    function rot(p, ax, ay, az) { let [x, y, z] = p; let c = Math.cos(ax), s = Math.sin(ax); let y1 = y * c - z * s, z1 = y * s + z * c; y = y1; z = z1; c = Math.cos(ay); s = Math.sin(ay); let x1 = x * c + z * s; z1 = -x * s + z * c; x = x1; z = z1; c = Math.cos(az); s = Math.sin(az); x1 = x * c - y * s; y1 = x * s + y * c; return [x1, y1, z]; }
    function draw(dt) {
      ctx.clearRect(0, 0, W, H);
      const narrow = W < 960;
      const R = narrow ? W * 0.40 : Math.min(W * 0.20, H * 0.30), cx = narrow ? W * 0.62 : W * 0.735, cy = narrow ? H * 0.22 : H * 0.42;
      ctx.globalAlpha = narrow ? 0.55 : 1;
      mouse.x += (mouse.tx - mouse.x) * 0.04; mouse.y += (mouse.ty - mouse.y) * 0.04;
      const spin = t * 0.10 + mouse.x * 0.25, tilt = 0.32 + mouse.y * 0.12;
      ctx.lineWidth = 1;
      for (let i = 1; i <= 3; i++) { ctx.beginPath(); ctx.arc(cx, cy, R * (1 + i * 0.42), 0, Math.PI * 2); ctx.strokeStyle = rgba(IVORY, 0.035); ctx.stroke(); }
      const behind = [], front = [];
      rings.forEach((ring, ri) => {
        ring.agents.forEach(ag => {
          ag.a += ring.speed * ag.v * dt; if (ag.a > Math.PI * 2) ag.a -= Math.PI * 2; if (ag.a < 0) ag.a += Math.PI * 2;
          ag.flash = Math.max(0, ag.flash - dt * 1.4);
          if (ring.labelled) { const seg = Math.floor(ag.a / (Math.PI * 2) * NODES.length); if (seg !== ag.lastNode) { ag.lastNode = seg; if (seg === 3 && Math.random() < 0.10) { ag.kind = 2; ag.flash = 1; } else if (seg === 5 && ag.kind !== 2) { ag.kind = 1; ag.flash = 1; } else if (seg === 0) ag.kind = 0; } }
          const rr = ring.r * (1 + ag.off);
          const q = rot(rot([Math.cos(ag.a) * rr, Math.sin(ag.a) * rr, 0], ring.tiltX, 0, ring.rotZ), tilt, spin * (ri ? -0.15 : 0.35), 0);
          (q[2] < 0 ? behind : front).push({ x: cx + q[0] * R, y: cy + q[1] * R, z: q[2], ag, ring });
        });
        ctx.beginPath();
        for (let i = 0; i <= 120; i++) { const a = i / 120 * Math.PI * 2; const q = rot(rot([Math.cos(a) * ring.r, Math.sin(a) * ring.r, 0], ring.tiltX, 0, ring.rotZ), tilt, spin * (ri ? -0.15 : 0.35), 0); const x = cx + q[0] * R, y = cy + q[1] * R; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
        ctx.strokeStyle = rgba(IVORY, 0.10); ctx.stroke();
        if (ring.labelled && !narrow) {
          ctx.font = '500 10px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
          NODES.forEach((n, i) => { const a = i / NODES.length * Math.PI * 2; const q = rot(rot([Math.cos(a) * ring.r, Math.sin(a) * ring.r, 0], ring.tiltX, 0, ring.rotZ), tilt, spin * 0.35, 0); const x = cx + q[0] * R, y = cy + q[1] * R; if (q[2] < 0 && Math.hypot(q[0], q[1]) < 1) return; const al = 0.35 + 0.45 * (q[2] + 1) / 2; ctx.fillStyle = rgba(IVORY, al * 0.9); ctx.fillRect(x - 0.5, y - 5, 1, 10); ctx.fillStyle = rgba(i === 5 ? GREEN : IVORY, al); ctx.textAlign = q[0] > 0 ? 'left' : 'right'; ctx.fillText(n.toUpperCase(), x + (q[0] > 0 ? 9 : -9), y); });
        }
      });
      const drawAgent = (it) => { const { ag, z } = it; if (z < 0 && Math.hypot((it.x - cx) / R, (it.y - cy) / R) < 0.985) return; const depth = (z + 1) / 2; const base = ag.kind === 1 ? GREEN : ag.kind === 2 ? RED : (it.ring.labelled ? IVORY : KHAKI); const alpha = (0.22 + depth * 0.7) * (ag.kind === 2 ? 0.7 : 1); const sz = ag.size * (0.8 + depth * 0.9); if (ag.flash > 0) { ctx.beginPath(); ctx.arc(it.x, it.y, sz + 8 * ag.flash, 0, Math.PI * 2); ctx.strokeStyle = rgba(base, 0.55 * ag.flash); ctx.lineWidth = 1; ctx.stroke(); } ctx.beginPath(); ctx.arc(it.x, it.y, sz, 0, Math.PI * 2); ctx.fillStyle = rgba(base, alpha); ctx.fill(); };
      behind.forEach(drawAgent);
      const dotR = R * 0.021;
      sphere.forEach(pt => { const lo = pt.lo + spin; const q = rot([Math.cos(pt.la) * Math.sin(lo), Math.sin(pt.la), Math.cos(pt.la) * Math.cos(lo)], tilt, 0, 0); if (q[2] <= 0.02) return; const px = cx + q[0] * R, py = cy + q[1] * R; const a = 0.07 + 0.40 * Math.pow(q[2], 1.6); ctx.save(); ctx.translate(px, py); ctx.rotate(Math.atan2(q[1], q[0])); ctx.beginPath(); ctx.ellipse(0, 0, Math.max(0.4, dotR * q[2]), dotR, 0, 0, Math.PI * 2); ctx.fillStyle = rgba(IVORY, a); ctx.fill(); ctx.restore(); });
      front.forEach(drawAgent);
      const g = ctx.createRadialGradient(cx, cy, R * 0.92, cx, cy, R * 1.12); g.addColorStop(0, rgba(IVORY, 0.05)); g.addColorStop(1, rgba(IVORY, 0)); ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.12, 0, Math.PI * 2); ctx.fill();
      ctx.globalAlpha = 1;
    }
    function frame(now) { if (!running) return; const dt = Math.min(0.05, (now - last) / 1000); last = now; if (visible && !document.hidden) { t += dt; draw(dt); } requestAnimationFrame(frame); }
    resize(); window.addEventListener('resize', resize);
    if (!prefersReduced) {
      window.addEventListener('pointermove', (e) => { mouse.tx = (e.clientX / window.innerWidth - 0.5) * 2; mouse.ty = (e.clientY / window.innerHeight - 0.5) * 2; }, { passive: true });
      if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; }, { threshold: 0 }).observe(cv);
      requestAnimationFrame(frame);
    } else draw(0);
  }
})();
