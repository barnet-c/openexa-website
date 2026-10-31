/* OpenEXA — the Company page (company.html; loaded after site.js and figure.js).
   1. The manifesto: its words are written in reading order, once, as the paragraph arrives (under half a second), and then
      stay. v2 tied each word to the scroll position, which left the paragraph half grey for as long as it was on
      screen; v2x: nothing stays half-lit after it arrives. In view at load, under reduced motion or without
      IntersectionObserver: all lit at once (first paint is final, SYSTEM 5.1).
   2. The hero plate's caption follows the mode (figure.js switches the formation and the mode caption; the plate
      label was the same for all three).
   3. §04, the constants plate (lab, 31 Oct): "The lifecycles vary. Four constants don't.", drawn. A proposal walks the
      loop of gates: above the boundary (agents decide), across it (C-01), below it (code executes), and is written to
      the ledger when the counterparty confirms (C-04); one pass in four is rejected at the Council and written too.
      Every second pass the loop takes another shape (another lifecycle); the boundary, the agents scoped to their
      gates (C-02), the stop short of custody (C-03) and the ledger do not move. The still in the markup is shape 0
      with the proposal on the boundary: what readers see without JavaScript and under reduced motion. It runs only on
      screen, with Pause motion; the constant being read (from 961 px) or pointed at is marked on the plate.
      The still SVG in company.html is maintained by hand: it is draw(lay(SHAPES[0])) with the proposal on the boundary,
      so a change to SHAPES[0], CX/CY or the label positions means redrawing it to match (r1, 31 Oct). */
(function () {
  'use strict';
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------- manifesto ---------------- */
  $$('[data-manifesto]').forEach(el => {
    const vh = window.innerHeight;
    const r = el.getBoundingClientRect();
    const inView = r.top < vh && r.bottom > 0;
    const words = [];
    const walk = (node) => {
      Array.from(node.childNodes).forEach(child => {
        if (child.nodeType === 3) {
          const frag = document.createDocumentFragment();
          child.textContent.split(/(\s+)/).forEach(p => {
            if (!p) return;
            if (/^\s+$/.test(p)) { frag.appendChild(document.createTextNode(p.replace(/[^ ]+/g, ' ') || ' ')); return; }
            const w = document.createElement('span'); w.className = 'mw'; w.textContent = p; words.push(w); frag.appendChild(w);
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) walk(child);
      });
    };
    walk(el);
    const all = () => words.forEach(w => w.classList.add('is-lit'));
    if (prefersReduced || inView || !('IntersectionObserver' in window)) { el.classList.add('is-written'); all(); return; }
    const step = Math.min(10, 450 / Math.max(1, words.length)); // the whole paragraph in at most ~0.45 s, settled by ~0.7 s
    const io = new IntersectionObserver(entries => {
      if (!entries.some(e => e.isIntersecting)) return;
      io.disconnect();
      el.classList.add('is-writing');
      words.forEach((w, i) => { w.style.transitionDelay = `${Math.round(i * step)}ms`; });
      requestAnimationFrame(() => { all(); setTimeout(() => { el.classList.replace('is-writing', 'is-written'); words.forEach(w => { w.style.transitionDelay = ''; }); }, words.length * step + 400); });
    }, { rootMargin: '0px 0px 8% 0px' }); // starts just before it scrolls in
    io.observe(el);
  });

  /* ---------------- the hero plate's caption follows the mode ---------------- */
  const label = document.querySelector('[data-plate-label]');
  $$('.company-modes [data-plate]').forEach(b => b.addEventListener('click', () => { if (label) label.textContent = b.dataset.plate; }));

  /* ---------------- §04: the constants plate ---------------- */
  const kfig = document.querySelector('[data-kplate]');
  if (kfig && kfig.querySelector('.k-recs')) plate(kfig);

  function plate(fig) {
    const NS = 'http://www.w3.org/2000/svg';
    const svg = fig.querySelector('svg');
    const one = s => svg.querySelector(s), all = s => Array.from(svg.querySelectorAll(s));
    const CX = 405, CY = 198, LX = 590, LY = 414, PITCH = 24, KEEP = 18, TAU = Math.PI * 2;
    // four loops, none of them a real lifecycle's (the caption says Schematic): u gates above the boundary, l below
    const SHAPES = [{ a: 170, b: 128, n: 2.0, u: 4, l: 2 }, { a: 185, b: 105, n: 2.8, u: 5, l: 3 },
      { a: 150, b: 140, n: 2.2, u: 3, l: 2 }, { a: 178, b: 118, n: 3.4, u: 4, l: 3 }];
    const f = v => Math.round(v * 10) / 10;
    const lerp = (x, y, t) => x + (y - x) * t;
    // a superellipse walked clockwise from its right-hand crossing: s 0-.5 above the boundary, .5-1 below
    const pt = (L, s) => {
      const t = TAU - TAU * s, c = Math.cos(t), si = Math.sin(t), e = 2 / L.n;
      return [CX + L.a * Math.sign(c) * Math.pow(Math.abs(c), e), CY + L.b * Math.sign(si) * Math.pow(Math.abs(si), e)];
    };
    // five gate slots above and three below; a slot a shape does not use sits on its last gate, hidden
    const lay = g => ({ a: g.a, b: g.b, n: g.n,
      up: [0, 1, 2, 3, 4].map(i => (Math.min(i, g.u - 1) + 1) / (g.u + 1) * .5), uo: [0, 1, 2, 3, 4].map(i => +(i < g.u)),
      dn: [0, 1, 2].map(j => .5 + (Math.min(j, g.l - 1) + 1) / (g.l + 1) * .5), do: [0, 1, 2].map(j => +(j < g.l)),
      top: (Math.floor(g.u / 2) + 1) / (g.u + 1) * .5 });
    const mix = (A, B, t) => { const o = {}; for (const k in A) o[k] = Array.isArray(A[k]) ? A[k].map((v, i) => lerp(v, B[k][i], t)) : lerp(A[k], B[k], t); return o; };
    const loopUp = one('.k-loop--up'), loopDn = one('.k-loop--dn'), gUp = all('.k-gate--up'), gDn = all('.k-gate--dn');
    const council = one('.k-council'), tag2 = one('.k-tag2'), stop = one('.k-stop'), bar = one('.k-bar'), lead = one('.k-lead');
    const tok = one('.k-tok'), recs = one('.k-recs'), bnd = all('.k-bnd'), state = one('.k-state');
    const say = t => { if (state && state.textContent !== t) state.textContent = t; };
    const spur = document.createElementNS(NS, 'path');
    spur.setAttribute('class', 'k-spur'); spur.setAttribute('opacity', '0'); council.parentNode.insertBefore(spur, council);
    const ledger = Array.from(recs.children).map(r => (r.classList.contains('k-rec--rej') ? 'rej' : 'ok'));
    const arc = (L, s0, s1) => { let d = ''; for (let i = 0; i <= 40; i++) { const [x, y] = pt(L, s0 + (s1 - s0) * i / 40); d += (i ? 'L' : 'M') + f(x) + ' ' + f(y); } return d; };
    const at = (el, x, y) => el.setAttribute('transform', `translate(${f(x)} ${f(y)})`);
    // the last gate on each side (the Council above, the settling gate below), eased while a gate appears or leaves
    const lastOf = (ss, os) => { let v = ss[0]; for (let i = 1; i < ss.length; i++) v = lerp(v, ss[i], os[i]); return v; };
    function draw(L) {
      loopUp.setAttribute('d', arc(L, 0, .5)); loopDn.setAttribute('d', arc(L, .5, 1));
      gUp.forEach((g, i) => {
        const [x, y] = pt(L, L.up[i]); at(g, x, y); g.setAttribute('opacity', f(L.uo[i]));
        let nx = (x - CX) / (L.a * L.a), ny = (y - CY) / (L.b * L.b); const m = Math.hypot(nx, ny) || 1; nx /= m; ny /= m;
        // the gate's agents: a short row beside it, parallel to the loop (each scoped to this gate alone)
        g.querySelectorAll('.k-agent').forEach((c, k) => { c.setAttribute('cx', f(nx * 14 - ny * (k - 1) * 6)); c.setAttribute('cy', f(ny * 14 + nx * (k - 1) * 6)); });
      });
      gDn.forEach((g, j) => { const [x, y] = pt(L, L.dn[j]); at(g, x, y); g.setAttribute('opacity', f(L.do[j])); });
      const [cx, cy] = pt(L, lastOf(L.up, L.uo)); at(council, cx, cy);
      const [tx, ty] = pt(L, L.top); tag2.setAttribute('x', f(tx + 22)); tag2.setAttribute('y', f(ty - 22));
      const [ex, ey] = pt(L, L.dn[0]); stop.setAttribute('d', `M${f(ex - 9)} ${f(ey)}H160`); bar.setAttribute('d', `M156 ${f(ey - 8)}V${f(ey + 8)}`);
      const [sx, sy] = pt(L, lastOf(L.dn, L.do)); lead.setAttribute('d', `M${f(sx)} ${f(sy + 8)}V372H${LX}V${LY - 6}`);
    }
    // the ledger: newest at the right; a new record slides in and the oldest fades off the left
    let shift = 0;
    function placeRecs() {
      const n = ledger.length; let el = recs.firstElementChild;
      ledger.forEach((k, i) => {
        if (!el) { el = document.createElementNS(NS, 'rect'); el.setAttribute('width', '12'); el.setAttribute('height', '8'); el.setAttribute('y', String(LY - 4)); recs.appendChild(el); }
        const age = n - 1 - i;
        el.setAttribute('class', 'k-rec' + (k === 'rej' ? ' k-rec--rej' : '') + (age === 0 && k === 'ok' ? ' k-rec--new' : ''));
        el.setAttribute('x', f(LX - 6 - (age - shift) * PITCH));
        el.setAttribute('opacity', f(Math.max(0, Math.min(1, KEEP - 1 - age + shift))));
        el = el.nextElementSibling;
      });
      while (el) { const nx = el.nextElementSibling; el.remove(); el = nx; }
    }
    function write(kind) { ledger.push(kind); if (ledger.length > KEEP) ledger.shift(); shift = 1; placeRecs(); }

    let shape = 0, L = lay(SHAPES[0]), pass = 0, phase = 'walk', next = 'walk', s = .5, hold = 0, gap = 0, morph = null;
    let stops = [], si = 0, rejecting = false, onStop = null;
    const SPEED = .23; // laps per second, before the holds at the gates
    function plan() {
      const g = SHAPES[shape], st = [];
      for (let i = 0; i < g.u; i++) st.push({ s: L.up[i], el: gUp[i], kind: i === g.u - 1 ? 'council' : 'gate' });
      st.push({ s: .5, kind: 'cross' });
      for (let j = 0; j < g.l; j++) st.push({ s: L.dn[j], el: gDn[j], kind: j === g.l - 1 ? 'settle' : 'gate' });
      return st;
    }
    function walk(from) {
      phase = 'walk'; s = from; stops = plan(); si = stops.findIndex(x => x.s > s + 1e-6); if (si < 0) si = stops.length;
      rejecting = pass % 4 === 3;
      if (s < .5) say('Agents decide · a proposal, gate by gate');
      tok.setAttribute('opacity', '1'); tok.setAttribute('class', 'k-tok' + (s >= .5 ? ' is-ok' : ''));
    }
    function arrive(x) {
      const el = x.el;
      if (x.kind === 'cross') { // the typed schema: only now is the proposal more than a data structure
        say('Crossing the boundary · typed schema'); tok.setAttribute('class', 'k-tok is-ok'); bnd.forEach(b => b.classList.add('is-hit'));
        hold = 260; onStop = () => bnd.forEach(b => b.classList.remove('is-hit')); return;
      }
      if (x.kind === 'council' && rejecting) { // refused before anything executes, and written all the same
        el.classList.add('is-no'); tok.setAttribute('class', 'k-tok is-rej'); say('Rejected at the Council · recorded too');
        const [gx, gy] = pt(L, x.s); let nx = (gx - CX) / (L.a * L.a), ny = (gy - CY) / (L.b * L.b); const m = Math.hypot(nx, ny) || 1; nx /= m; ny /= m;
        spur.setAttribute('d', `M${f(gx + nx * 13)} ${f(gy + ny * 13)}L${f(gx + nx * 40)} ${f(gy + ny * 40)}`); spur.setAttribute('opacity', '1');
        hold = 1100; onStop = () => { el.classList.remove('is-no'); spur.setAttribute('opacity', '0'); write('rej'); end(); }; return;
      }
      el.classList.add('is-hit');
      if (x.kind === 'settle') { // the counterparty confirms; then, and only then, the record
        lead.classList.add('is-hit'); say('The counterparty confirms · written to the ledger');
        hold = 620; onStop = () => { el.classList.remove('is-hit'); lead.classList.remove('is-hit'); write('ok'); }; return;
      }
      say(x.s < .5 ? 'Agents decide · a proposal, gate by gate' : 'Code executes · below the boundary');
      hold = 300; onStop = () => el.classList.remove('is-hit');
    }
    function end() { tok.setAttribute('opacity', '0'); pass++; next = pass % 2 === 0 ? 'morph' : 'walk'; phase = 'gap'; gap = 700; si = stops.length; }
    function tick(dt) {
      if (shift > 0) { shift = Math.max(0, shift - dt / 520); placeRecs(); }
      if (phase === 'walk') {
        if (hold > 0) { hold -= dt; if (hold <= 0) { const k = onStop; onStop = null; si++; if (k) k(); } }
        else {
          const x = stops[si], ns = s + SPEED * dt / 1000;
          if (x && ns >= x.s) { s = x.s; arrive(x); }
          else { s = Math.min(1, ns); if (s >= 1) { end(); return; } }
        }
        if (phase === 'walk') { const [x, y] = pt(L, s); tok.setAttribute('cx', f(x)); tok.setAttribute('cy', f(y)); }
      } else if (phase === 'gap') {
        gap -= dt;
        if (gap <= 0) {
          if (next === 'morph') { const A = L; shape = (shape + 1) % SHAPES.length; morph = { A, B: lay(SHAPES[shape]), t: 0 }; phase = 'morph'; next = 'walk'; say('Another lifecycle · the same four constants'); }
          else walk(0);
        }
      } else if (phase === 'morph') { // another lifecycle: only the loop and its gates move
        morph.t = Math.min(1, morph.t + dt / 1500);
        const t = morph.t, e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
        L = mix(morph.A, morph.B, e); draw(L);
        if (t >= 1) { L = morph.B; morph = null; phase = 'gap'; gap = 450; }
      }
    }
    // it runs only on screen, with the page visible, not paused and not under reduced motion (the still stays)
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    let raf = 0, last = 0, visible = false, paused = false;
    const btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'figure-motion'; btn.textContent = 'Pause motion';
    btn.addEventListener('click', () => { paused = !paused; btn.textContent = paused ? 'Resume motion' : 'Pause motion'; kick(); });
    fig.appendChild(btn);
    function frame(now) { raf = 0; tick(Math.min(64, now - last)); last = now; kick(); }
    function kick() {
      const go = visible && !paused && !reduce.matches && !document.hidden;
      if (go && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
      else if (!go && raf) { cancelAnimationFrame(raf); raf = 0; }
    }
    const sync = () => { btn.hidden = reduce.matches; kick(); };
    walk(.5);
    if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; kick(); }).observe(svg);
    document.addEventListener('visibilitychange', kick);
    reduce.addEventListener('change', sync); sync();

    // the constant being read (from 961 px, where the plate stays beside the list) or pointed at
    const cons = Array.from(document.querySelectorAll('#constants [data-k]'));
    const wide = window.matchMedia('(min-width: 961px)');
    let pointed = null, read = null;
    const mark = () => {
      const k = pointed || (wide.matches ? read : null);
      if (k) fig.dataset.on = k; else delete fig.dataset.on;
      cons.forEach(c => c.classList.toggle('is-on', c.dataset.k === k));
    };
    cons.forEach(c => {
      c.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse') { pointed = c.dataset.k; mark(); } });
      c.addEventListener('pointerleave', () => { pointed = null; mark(); });
    });
    if ('IntersectionObserver' in window) {
      const seen = new Map();
      const io = new IntersectionObserver(es => {
        es.forEach(e => seen.set(e.target, e.isIntersecting));
        const hit = cons.find(c => seen.get(c)); read = hit ? hit.dataset.k : null; mark();
      }, { rootMargin: '-40% 0px -48% 0px' });
      cons.forEach(c => io.observe(c));
    }
    wide.addEventListener('change', mark);
  }
})();
