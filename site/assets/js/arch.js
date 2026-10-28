/* OpenEXA — the architecture explorer: eight layers, exploded, one boundary, on the floor of the rails.
   Enhances a `.layers[data-arch]` list (readable as it is without JavaScript) into an instrument: a readout on the left,
   the stack drawn in SVG in the centre (an axonometric projection, so it stays crisp at any pixel ratio) and the layers
   as buttons on the right, each one the label of its plate. Pointing at a layer, or focusing it, lifts its plate and shows
   its job and In -> Out; Up/Down (or Left/Right), Home and End move between layers, Enter or Space opens one, Escape closes it.
   With `data-arch-spec` (Platform) the list stays on the page as the full spec, under the instrument: Enter, a click or a
   tap on a layer or its plate brings that layer's entry into view and lights it, instead of opening a panel.
   Above the boundary (between 04 and 05) agents jitter, estimating; below it every mark snaps to the plane's grid, and the
   ground itself changes at the seam: scattered motes above, a lattice below. Dashed explosion lines join the plates' corners.
   Under 08 lies the floor (`.layer-floor`: the rails the stack connects to).
   An illustrative proposal travels the stack: the Council decides; approved, it crosses the boundary as a ring and snaps
   to each plate's grid below it, still a ring, until the last plate settles it as a square that drops to the floor;
   rejected, it falls away. The readout card follows the plate you point at and keeps itself on screen; it swaps one layer
   for the next out, then in, never both at once. Motion runs only on screen in a visible tab, stops on request, never
   starts under reduced motion.
   The wide instrument's height is set in CSS (--arch-minh), before and after this script builds it, so the page under it
   never moves when it does. */
(function () {
  'use strict';
  const roots = Array.from(document.querySelectorAll('.layers[data-arch]'));
  // no instrument here: the list stays a list (.is-plain lifts the room CSS holds for the instrument)
  if (!roots.length || !('ResizeObserver' in window) || !('IntersectionObserver' in window)) { roots.forEach((r) => r.classList.add('is-plain')); return; }

  const NS = 'http://www.w3.org/2000/svg';
  const reduceMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  const wideMQ = window.matchMedia('(min-width: 1000px)');
  const fineMQ = window.matchMedia('(hover: hover) and (pointer: fine)');
  const IVORY = '#F5F2EC', GREEN = '#4FCB93', KHAKI = '#ACA68E', RED = '#D9675D';
  const DEG = Math.PI / 180;
  const pad2 = (n) => String(n).padStart(2, '0');
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ease3 = (t) => 1 - Math.pow(1 - t, 3);
  const inout = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const f1 = (v) => (Math.round(v * 10) / 10).toString();
  const f3 = (v) => (Math.round(v * 1000) / 1000).toString();
  function S(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function H(tag, cls, parent, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function setA(e, k, v) { const c = e.__a || (e.__a = {}); if (c[k] !== v) { c[k] = v; e.setAttribute(k, v); } } // write only what changed
  // a critically damped spring (implicit Euler): stable at any frame time, no overshoot
  function spring(o, target, dt, w) {
    const f = 1 + 2 * dt * w, hoo = dt * w * w, hhoo = dt * hoo, det = 1 / (f + hhoo);
    const x = (f * o.x + dt * o.v + hhoo * target) * det;
    o.v = (o.v + hoo * (target - o.x)) * det; o.x = x;
  }
  const still = (o, target) => Math.abs(o.x - target) < 0.02 && Math.abs(o.v) < 0.02;
  const NSS = 'non-scaling-stroke';
  const navH = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 72; // the bar's height

  let uid = 0;
  roots.forEach((root) => explorer(root, uid++));

  function explorer(root, id) {
    const pre = `arch${id}`;
    const spec = root.hasAttribute('data-arch-spec'); // Platform: the list stays, as the spec under the instrument
    /* ---------------- 1 · read the list (also what readers without JavaScript get) ---------------- */
    const items = [];
    let bIndex = -1, bEl = null, fEl = null;
    const txt = (n) => (n ? n.textContent : '').replace(/\s+/g, ' ').trim();
    Array.from(root.children).forEach((el) => {
      if (el.classList.contains('layer')) {
        const k = el.querySelector('.k'), h3 = el.querySelector('h3'), small = h3 && h3.querySelector('small'), body = el.lastElementChild;
        const name = h3 ? Array.from(h3.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join(' ').replace(/\s+/g, ' ').trim() : '';
        const dd = body ? body.querySelectorAll('dl.io dd') : [];
        items.push({ el, body, num: txt(k) || pad2(items.length + 1), name, verb: txt(small), job: el.dataset.job || '', inp: txt(dd[0]), out: txt(dd[1]) });
      } else if (el.classList.contains('layer-boundary')) { bIndex = items.length; bEl = el; }
      else if (el.classList.contains('layer-floor')) fEl = el;
    });
    const N = items.length;
    if (N < 2 || items.some((it) => !it.body || it.body.tagName !== 'DIV' || !it.name)) { root.classList.add('is-plain'); return; } // not the markup this expects: leave the list
    if (bIndex < 1 || bIndex >= N) bIndex = Math.ceil(N / 2);
    const floorTxt = fEl ? txt(fEl.querySelector('p') || fEl).replace(/^[—–-]\s*/, '') : ''; // what the stack stands on: the rails
    const sideOf = (sel) => {
      const p = bEl && bEl.querySelector(sel);
      if (!p) return null;
      const b = p.querySelector('b'), s = p.querySelector('strong');
      return { k: txt(b), t: txt(s), d: Array.from(p.childNodes).filter((n) => n !== b && n !== s).map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim() };
    };
    const UP = sideOf('[data-side="above"]') || { k: 'Above', t: 'Intelligence decides.', d: '' };
    const DN = sideOf('[data-side="below"]') || { k: 'Below', t: 'Execution is deterministic.', d: '' };
    const lbt = bEl && bEl.querySelector('.lb-t');
    const bTitle = (lbt && lbt.firstChild && lbt.firstChild.textContent.trim()) || 'The boundary';
    const bNote = lbt && lbt.querySelector('small') ? txt(lbt.querySelector('small')) : '';
    const noDot = (s) => s.replace(/[.\s]+$/, '');

    /* ---------------- 2 · the instrument ---------------- */
    // inst is the instrument: the list itself (it becomes the explorer), or, in spec mode, a stage above the list (which stays)
    const inst = spec ? document.createElement('div') : root;
    if (!spec) root.classList.remove('layers');
    inst.classList.add('arch', 'is-building');
    if (spec) inst.classList.add('arch--spec');
    const head = H('div', 'arch-head');
    H('span', 'arch-lab', head, root.dataset.archLabel || 'The agentic stack');
    const legend = H('span', 'arch-legend', head);
    legend.setAttribute('aria-hidden', 'true');
    H('span', '', legend, 'Illustrative');
    [['lg-bead', 'Agent'], ['lg-ring', 'Proposal'], ['lg-sq', 'Settled']].forEach(([c, t]) => { const s = H('span', '', legend); H('i', c, s); s.appendChild(document.createTextNode(t)); });
    const hint = H('span', 'arch-hint', head);
    const motionBtn = H('button', 'arch-motion', head, 'Pause motion');
    motionBtn.type = 'button';
    const bodyEl = H('div', 'arch-body');
    const fig = H('div', 'arch-fig', bodyEl);
    fig.setAttribute('aria-hidden', 'true');
    // the ground on either side of the boundary: scattered motes above it (estimation), a lattice below it (determinism)
    const field = H('div', 'arch-field', fig);
    H('i', 'af-up', field); H('i', 'af-dn', field);
    const svg = S('svg', { class: 'arch-svg', focusable: 'false' }, fig);
    const list = H('div', 'arch-list', bodyEl);
    const read = H('div', 'arch-read', bodyEl);

    const btns = [], panels = [], heads = [];
    let bRow = null, fRow = null;
    // a glyph of the stack: eight bars, the boundary between them, the layer in question lit
    const glyph = (i) => {
      const g = S('svg', { class: 'arch-glyph', viewBox: `0 0 16 ${N * 3 + 3}`, width: 16, height: N * 3 + 3, 'aria-hidden': 'true', focusable: 'false' });
      for (let k = 0; k < N; k++) S('rect', { x: 1, y: k * 3 + (k >= bIndex ? 3 : 0), width: 14, height: 1.6, fill: k === i ? GREEN : IVORY, 'fill-opacity': k === i ? 1 : 0.3 }, g);
      S('rect', { x: 0, y: bIndex * 3 + 0.6, width: 16, height: 0.9, fill: GREEN, 'fill-opacity': 0.9 }, g);
      return g;
    };
    items.forEach((it, i) => {
      // spec mode: the entries below carry the headings, so the stage's layers are plain buttons that lead to them
      const hd = H(spec ? 'div' : 'h3', 'arch-h', list);
      const b = H('button', 'arch-layer', hd);
      b.type = 'button'; b.id = `${pre}-b${i + 1}`;
      H('span', 'n', b, it.num); H('span', 'nm', b, it.name); H('span', 'vb', b, it.verb);
      const p = it.body;
      p.id = `${pre}-p${i + 1}`;
      if (spec) {
        // the entry stays where it is, every word on the page; the button brings it into view and lights it
        it.el.id = `${pre}-e${i + 1}`; it.el.tabIndex = -1;
        p.classList.add('arch-panel');
        b.setAttribute('aria-controls', it.el.id);
      } else {
        b.setAttribute('aria-expanded', 'false'); b.setAttribute('aria-controls', p.id);
        p.className = 'arch-panel'; p.hidden = true;
        p.setAttribute('role', 'region'); p.setAttribute('aria-labelledby', b.id);
        const above = i < bIndex;
        const sd = document.createElement('p');
        sd.className = 'arch-side' + (above ? '' : ' is-below');
        sd.appendChild(glyph(i));
        H('span', '', sd, above ? `Above the boundary · ${noDot(UP.t).toLowerCase()}` : `Below the boundary · ${noDot(DN.t).toLowerCase()}`);
        p.insertBefore(sd, p.firstChild);
        list.appendChild(p);
      }
      btns.push(b); panels.push(p); heads.push(hd);
      if (i === bIndex - 1) {
        bRow = H('div', 'arch-bound', list);
        H('span', 'chip', bRow, bTitle);
        const sides = H('span', 'sides', bRow);
        [['Above it: ', '↑ ', UP.t], ['Below it: ', '↓ ', DN.t]].forEach(([sr, arrow, t]) => {
          const s = H('span', '', sides);
          H('span', 'sr-only', s, sr);
          H('span', '', s, arrow).setAttribute('aria-hidden', 'true');
          s.appendChild(document.createTextNode(noDot(t)));
        });
      }
    });
    // the floor under 08: the rails the stack connects to (wide: a row in the list, level with the floor line it labels);
    // when it needs two lines, they break at the middle dot nearest the middle, never leaving a dot at a line's end
    const fParts = floorTxt.split(' · ');
    let fMid = 1;
    for (let j = 1, bd = Infinity; j < fParts.length; j++) { const d = Math.abs(fParts.slice(0, j).join(' · ').length - floorTxt.length / 2); if (d < bd) { bd = d; fMid = j; } }
    if (floorTxt) {
      fRow = H('div', 'arch-floor', list); H('span', 'gl', fRow).setAttribute('aria-hidden', 'true');
      const ft = H('span', 'ft', fRow);
      if (fParts.length > 1) { H('span', 'fa', ft, fParts.slice(0, fMid).join(' · ')); H('span', 'fs', ft, ' · '); H('span', 'fb', ft, fParts.slice(fMid).join(' · ')); }
      else ft.textContent = floorTxt;
    }
    // the readout: an overview that straddles the boundary, and a card that follows the layer you point at
    const ov = H('div', 'arch-ov', read);
    ov.setAttribute('aria-hidden', 'true');
    const ovUp = H('div', 'ov-up', ov); H('b', '', ovUp, UP.k); H('strong', '', ovUp, UP.t); H('p', '', ovUp, UP.d);
    const ovDn = H('div', 'ov-dn', ov); H('b', '', ovDn, DN.k); H('strong', '', ovDn, DN.t); H('p', '', ovDn, DN.d);
    if (bNote) H('small', '', ovDn, bNote);
    const card = H('div', 'arch-card', read);
    const sum = H('div', 'arch-sum', card);
    sum.setAttribute('aria-hidden', 'true');
    const sk = H('div', 'sum-k', sum), skL = H('span', '', sk), skR = H('b', '', sk);
    const snm = H('div', 'sum-nm', sum), sjob = H('p', 'sum-job', sum);
    const sio = H('dl', 'io', sum);
    const ioRow = (k) => { const d = H('div', '', sio); H('dt', '', d, k); return H('dd', '', d); };
    const sIn = ioRow('In'), sOut = ioRow('Out');
    const sside = H('p', 'sum-side', sum), scue = H('p', 'sum-cue', sum);

    inst.append(head, bodyEl);
    if (spec) { root.insertBefore(inst, root.firstChild); root.classList.add('is-built'); } // takes the room CSS held for it
    else { items.forEach((it) => it.el.remove()); if (bEl) bEl.remove(); if (fEl) fEl.remove(); }

    /* ---------------- 3 · the drawing ---------------- */
    const defs = S('defs', null, svg);
    const grad = (tag, gid, attrs, stops) => { const g = S(tag, Object.assign({ id: `${pre}-${gid}` }, attrs), defs); stops.forEach(([o, c, a]) => S('stop', { offset: o, 'stop-color': c, 'stop-opacity': a }, g)); return `url(#${pre}-${gid})`; };
    const gTop = grad('linearGradient', 'top', { x1: 0, y1: 0, x2: 1, y2: 1 }, [[0, '#2A3530', 1], [0.5, '#18211D', 1], [1, '#111815', 1]]);
    const gSide = grad('linearGradient', 'side', { x1: 0, y1: 0, x2: 0, y2: 1 }, [[0, '#0D1311', 1], [1, '#070B09', 1]]);
    const gBead = grad('radialGradient', 'bead', { cx: 0.36, cy: 0.34, r: 0.72 }, [[0, IVORY, 1], [0.55, IVORY, 0.78], [1, IVORY, 0.28]]);
    const gPlane = grad('radialGradient', 'plane', { cx: 0.5, cy: 0.5, r: 0.5 }, [[0, GREEN, 0.2], [0.7, GREEN, 0.06], [1, GREEN, 0]]);
    const gAtt = grad('radialGradient', 'att', { cx: 0.5, cy: 0.5, r: 0.5 }, [[0, GREEN, 0.42], [1, GREEN, 0]]);
    // the floor under the stack: a ground line with the hatching of a technical drawing, labelled with what lies there
    const floor = floorTxt ? (() => {
      const g = S('g', { class: 'af' }, svg);
      const fl = { g, land: 0, lx: 0 };
      fl.hatch = S('path', { fill: 'none', stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1 }, g);
      fl.line = S('line', { stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1 }, g);
      fl.lead = S('line', { stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1, 'stroke-dasharray': '1 3' }, g);
      fl.node = S('circle', { r: 1.8, fill: KHAKI, 'fill-opacity': 0 }, g);
      fl.mark = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1.6 }, g); // where a settled action lands
      fl.t1 = S('text', { class: 'af-t', 'text-anchor': 'middle' }, g);
      fl.t2 = S('text', { class: 'af-t', 'text-anchor': 'middle' }, g);
      return fl;
    })() : null;
    const gBot = S('g', { class: 'lv-bottom' }, svg);   // what falls out under the stack
    let seed = 11 + id * 7;
    const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };

    // plates, drawn lowest first so the upper ones cover them; each level has an "above" group for travelling work
    const plates = items.map((it, i) => ({ i, above: i < bIndex, off: { x: 0, v: 0 }, heat: { x: 0, v: 0 }, fade: { x: 0, v: 0 }, beads: [] }));
    const levels = {};
    const order = [];
    for (let i = N - 1; i >= bIndex; i--) order.push(i);
    order.push('B');
    for (let i = bIndex - 1; i >= 0; i--) order.push(i);
    const gLead = S('g', { class: 'leaders' });   // drawn over every plate: attached after them
    let bound = null;
    order.forEach((key) => {
      const lv = S('g', { class: 'lv' }, svg);
      if (key === 'B') bound = buildBoundary(lv);
      else buildPlate(plates[key], lv);
      levels[key] = S('g', { class: 'lv-above' }, svg);
    });
    // the explosion lines of a technical drawing: dashed, from each plate's visible corners down to the next plate's
    // (the left, front and right corners are never covered by another plate, so one path drawn over the stack is right)
    const guides = S('path', { class: 'guides', fill: 'none', stroke: IVORY, 'stroke-opacity': 0, 'stroke-width': 1, 'stroke-dasharray': '2 3' }, svg);
    svg.appendChild(gLead);
    const gFront = S('g', { class: 'lv-front' }, svg);
    // pointer targets, one per plate, held at the plates' resting places: a plate that lifts under the pointer never
    // slides out from under it (no hover flicker); the upper plates' targets sit on top, as their plates do
    const gHit = S('g', { class: 'hits' }, svg);
    for (let i = N - 1; i >= 0; i--) plates[i].hit = S('polygon', { class: 'ap-hit', fill: 'transparent' }, gHit);

    function buildPlate(p, lv) {
      const g = S('g', { class: 'ap' }, lv);
      p.g = g;
      p.sideL = S('polygon', { fill: gSide }, g);
      p.sideR = S('polygon', { fill: gSide }, g);
      p.edgeB = S('polyline', { fill: 'none', stroke: IVORY, 'stroke-opacity': 0.1 }, g);
      p.top = S('polygon', { fill: gTop }, g);
      p.glow = S('polygon', { fill: IVORY, 'fill-opacity': 0 }, g);
      p.pat = S('g', { class: 'ap-pat' }, g);
      p.far = S('polyline', { fill: 'none', stroke: IVORY, 'stroke-width': 1 }, g);
      p.key = S('line', { stroke: GREEN, 'stroke-width': 1.2, 'stroke-opacity': 0 }, g);
      p.rim = S('polyline', { fill: 'none', stroke: IVORY, 'stroke-width': 1, 'stroke-linejoin': 'round' }, g);
      p.bead = S('g', { class: 'ap-beads' }, g);
      p.num = S('text', { class: 'ap-num', 'dominant-baseline': 'middle' }, lv);
      p.num.textContent = items[p.i].num + (items[p.i].verb ? ' · ' + items[p.i].verb : '');
      p.numShort = items[p.i].num;
      p.numLong = p.num.textContent;
      pattern(p);
    }
    function buildBoundary(lv) {
      const g = S('g', { class: 'ab' }, lv);
      const b = { g };
      b.fill = S('polygon', { fill: gPlane }, g);
      b.pat = S('g', null, g);
      S('path', { d: Array.from({ length: 9 }, (_, k) => `M-1.16 ${f3(-0.92 + k * 0.23)}H1.16`).join(''), stroke: GREEN, 'stroke-opacity': 0.07, 'vector-effect': NSS, fill: 'none' }, b.pat);
      b.ripple = S('circle', { r: 0.1, fill: 'none', stroke: GREEN, 'stroke-opacity': 0, 'vector-effect': NSS }, b.pat);
      b.glow2 = S('polygon', { fill: 'none', stroke: GREEN, 'stroke-width': 9, 'stroke-opacity': 0.045, 'stroke-linejoin': 'round' }, g);
      b.glow1 = S('polygon', { fill: 'none', stroke: GREEN, 'stroke-width': 3.5, 'stroke-opacity': 0.13, 'stroke-linejoin': 'round' }, g);
      b.core = S('polygon', { fill: 'none', stroke: GREEN, 'stroke-width': 1, 'stroke-opacity': 0.9, 'stroke-linejoin': 'round' }, g);
      b.tUp = S('text', { class: 'ab-t', 'text-anchor': 'start' }, lv);
      b.tDn = S('text', { class: 'ab-t is-below', 'text-anchor': 'start' }, lv);
      b.line0 = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
      b.lineL = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
      b.lineR = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
      b.ripT = 0; b.flash = 0; b.ru = 0; b.rv = 0;
      return b;
    }
    const leads = plates.map(() => ({
      line: S('line', { stroke: IVORY, 'stroke-width': 1, 'stroke-opacity': 0.16 }, gLead),
      a: S('circle', { r: 1.6, fill: IVORY, 'fill-opacity': 0.4 }, gLead),
      b: S('circle', { r: 2, fill: GREEN, 'fill-opacity': 0 }, gLead),
    }));
    const cardLead = S('polyline', { fill: 'none', stroke: IVORY, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
    const cardNode = S('circle', { r: 2.2, fill: GREEN, 'fill-opacity': 0 }, gLead);

    /* each plate's surface, in its own plane coordinates (u, v in -1..1), so the projection foreshortens it for free */
    function pattern(p) {
      const g = p.pat, i = p.i, role = N === 8 ? i : (p.above ? (i === bIndex - 1 ? 3 : 2) : 5);
      const line = (d, o, c, extra) => S('path', Object.assign({ d, fill: 'none', stroke: c || IVORY, 'stroke-opacity': o, 'vector-effect': NSS }, extra || {}), g);
      const sq = (u, v, s, attrs) => S('rect', Object.assign({ x: f3(u - s), y: f3(v - s), width: f3(2 * s), height: f3(2 * s) }, attrs), g);
      const beadsAt = (n, spread, rMin, rMax, amp, h0) => {
        for (let k = 0; k < n; k++) {
          const b = { u0: (rnd() - 0.5) * 2 * spread, v0: (rnd() - 0.5) * 2 * spread, h0: h0 + rnd() * 0.05, a: amp * (0.6 + rnd() * 0.8), w1: 2.4 + rnd() * 3.2, w2: 2 + rnd() * 3.6, p1: rnd() * 6.28, p2: rnd() * 6.28 };
          b.el = S('circle', { r: f1(rMin + rnd() * (rMax - rMin)), fill: gBead, 'fill-opacity': f3(0.55 + rnd() * 0.45) }, p.bead);
          p.beads.push(b);
        }
      };
      if (role === 0) { // Signal Intelligence: a sensing field; motes drift in from the edge and are absorbed
        [0.3, 0.6, 0.9].forEach((r, k) => S('circle', { r, fill: 'none', stroke: IVORY, 'stroke-opacity': 0.09 + k * 0.03, 'vector-effect': NSS, 'stroke-dasharray': k === 2 ? '2 5' : null }, g));
        line('M-1 0H-.82M.82 0H1M0 -1V-.82M0 .82V1', 0.35);
        S('circle', { r: 0.05, fill: GREEN, 'fill-opacity': 0.8 }, g);
        for (let k = 0; k < 20; k++) {
          const b = { mote: true, a: rnd() * 6.283, sp: 0.16 + rnd() * 0.18, ph: rnd(), h0: 0.03 };
          b.el = S('circle', { r: f1(1 + rnd() * 0.8), fill: IVORY, 'fill-opacity': 0 }, p.bead);
          p.beads.push(b);
        }
      } else if (role === 1) { // Model Layer: a matrix of learned weights, and attention wandering over it
        p.att = S('circle', { r: 0.46, fill: gAtt, cx: 0, cy: 0 }, g);
        for (let a = -4; a <= 4; a++) for (let b = -4; b <= 4; b++) {
          const u = a * 0.2, v = b * 0.2, n = 0.5 + 0.5 * Math.sin(u * 3.1 + v * 1.7 + 0.6) * Math.cos(v * 2.3 - u * 0.9);
          sq(u, v, 0.022 + 0.046 * n, { fill: IVORY, 'fill-opacity': f3(0.1 + 0.42 * n) });
        }
        beadsAt(7, 0.7, 1.2, 1.7, 0.035, 0.04);
      } else if (role === 2) { // Domain-Specific Agents: the swarm, each agent estimating, a few carrying proposals
        beadsAt(52, 0.84, 1.3, 2.3, 0.032, 0.02);
        for (let k = 0; k < 5; k++) {
          const b = { u0: (rnd() - 0.5) * 1.5, v0: (rnd() - 0.5) * 1.5, h0: 0.06, a: 0.04, w1: 1.6 + rnd(), w2: 1.4 + rnd(), p1: rnd() * 6.28, p2: rnd() * 6.28 };
          b.el = S('circle', { r: 3.2, fill: 'none', stroke: GREEN, 'stroke-width': 1.2, 'stroke-opacity': 0.9 }, p.bead);
          p.beads.push(b);
        }
      } else if (role === 3) { // Execution Council: the aperture; it pulses once per decision
        let d = '';
        for (let k = 0; k < 72; k++) { const a = k / 72 * 6.2832, r2 = k % 6 === 0 ? 0.5 : 0.45; d += `M${f3(Math.cos(a) * 0.37)} ${f3(Math.sin(a) * 0.37)}L${f3(Math.cos(a) * r2)} ${f3(Math.sin(a) * r2)}`; }
        p.ticks = line(d, 0.55);
        S('circle', { r: 0.28, fill: 'none', stroke: GREEN, 'stroke-opacity': 0.55, 'vector-effect': NSS }, g);
        p.pulse = S('circle', { r: 0.5, fill: 'none', stroke: GREEN, 'stroke-opacity': 0, 'vector-effect': NSS, 'stroke-width': 1.5 }, g);
        S('circle', { r: 0.045, fill: GREEN }, g);
        for (let k = 0; k < 9; k++) {
          const a = k / 9 * 6.283 + 0.3, b = { u0: Math.cos(a) * 0.72, v0: Math.sin(a) * 0.72, h0: 0.04, a: 0.03, w1: 2.6 + rnd() * 2, w2: 2.2 + rnd() * 2, p1: rnd() * 6.28, p2: rnd() * 6.28 };
          b.el = S('circle', { r: 2.8, fill: 'none', stroke: GREEN, 'stroke-width': 1.1, 'stroke-opacity': 0.75 }, p.bead);
          p.beads.push(b);
        }
      } else if (role === 4) { // Routing Layer: Manhattan routes from the hub to the rails; the scored best path in green
        line('M-.75 -1V1M-.5 -1V1M-.25 -1V1M0 -1V1M.25 -1V1M.5 -1V1M.75 -1V1M-1 -.75H1M-1 -.5H1M-1 -.25H1M-1 0H1M-1 .25H1M-1 .5H1M-1 .75H1', 0.05);
        line('M0 0H-.5V-1M0 0V-.5H-1M0 0V.5H-1M0 0H.75V-1', 0.32, KHAKI);
        line('M0 0H.25V-.5H.5V-1', 0.95, GREEN, { 'stroke-width': 1.4 });
        [[0, 0], [-0.5, 0], [0, -0.5], [0, 0.5], [0.75, 0], [0.25, 0], [0.25, -0.5], [0.5, -0.5]].forEach(([u, v], k) => sq(u, v, 0.045, { fill: k > 4 || k === 0 ? GREEN : KHAKI, 'fill-opacity': k > 4 || k === 0 ? 0.95 : 0.6 }));
        line('M-.5 -1V-1.1M-1 -.5H-1.1M-1 .5H-1.1M.75 -1V-1.1M.5 -1V-1.1', 0.55, IVORY);
      } else if (role === 5) { // Execution Layer: a state machine; one step at a time, on the grid
        p.cells = [];
        for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) p.cells.push({ r, c, el: sq(-0.6 + c * 0.3, 0.32 - r * 0.32, 0.085, { fill: GREEN, 'fill-opacity': 0, stroke: KHAKI, 'stroke-opacity': 0.5, 'vector-effect': NSS }) });
        line('M-.6 .6H.6M-.6 -.6H.6', 0.12);
        line('M-.48 .32H-.42M-.18 .32H-.12M.12 .32H.18M.42 .32H.48M-.48 0H-.42M-.18 0H-.12M.12 0H.18M.42 0H.48M-.48 -.32H-.42M-.18 -.32H-.12M.12 -.32H.18M.42 -.32H.48', 0.4, KHAKI);
      } else if (role === 6) { // MCP Server: pins along the edges, ports wired to them
        let d = '';
        for (let k = -4; k <= 4; k++) d += `M-1 ${k * 0.2}H-1.1M${k * 0.2} -1V-1.1`;
        line(d, 0.55);
        line('M-.45 .35H-1M.35 .45V.1H-.2V-1M.3 -.35V-.6H.6V-1M-.45 .35V-.2H-1', 0.18);
        p.ports = [[-0.45, 0.35], [0.35, 0.45], [0.3, -0.35]].map(([u, v]) => sq(u, v, 0.07, { fill: GREEN, 'fill-opacity': 0, stroke: KHAKI, 'stroke-opacity': 0.7, 'vector-effect': NSS }));
      } else { // Authentication Layer: nested scopes; a permit at the centre
        [[0.8, 0.32, '3 4'], [0.54, 0.42, '3 4'], [0.28, 0.6, null]].forEach(([h, o, dash]) => sq(0, 0, h, { fill: 'none', stroke: KHAKI, 'stroke-opacity': o, 'vector-effect': NSS, 'stroke-dasharray': dash }));
        line('M-.92 -.7V-.92H-.7M.7 -.92H.92V-.7M.92 .7V.92H.7M-.7 .92H-.92V.7', 0.5);
        p.permit = sq(0, 0, 0.1, { fill: GREEN, 'fill-opacity': 0.3 });
      }
    }

    /* ---------------- 4 · geometry ---------------- */
    let wide = false, W = 1, Hh = 1, cx = 0, halfW = 150, Sc = 1, F0 = 19 * DEG, thick = 7, figH = 0, minH = 0;
    let base = new Array(N).fill(0), rowC = new Array(N).fill(0), by = 0, fy = 0, readL = 0, readR = 0, readTop = 0, listL = 0, listR = 0;
    const view = { T: 45 * DEG, F: 19 * DEG, tT: 45 * DEG, tF: 19 * DEG };
    let geoDirty = true;
    const proj = (u, v, h) => {
      const c = Math.cos(view.T), s = Math.sin(view.T), sp = Math.sin(view.F), cp = Math.cos(view.F);
      return [Sc * (u * c - v * s), -Sc * ((u * s + v * c) * sp + h * cp)];
    };
    const pts = (arr) => arr.map((q) => f1(q[0]) + ',' + f1(q[1])).join(' ');
    const dn = (q, t) => [q[0], q[1] + t];
    function shape() {
      const c = Math.cos(view.T), s = Math.sin(view.T), sp = Math.sin(view.F);
      const m = `matrix(${f3(Sc * c)} ${f3(-Sc * s * sp)} ${f3(-Sc * s)} ${f3(-Sc * c * sp)} 0 0)`;
      const A = proj(-1, 1, 0), B = proj(1, 1, 0), C = proj(1, -1, 0), D = proj(-1, -1, 0);
      plates.forEach((p) => {
        setA(p.top, 'points', pts([A, B, C, D])); setA(p.glow, 'points', pts([A, B, C, D]));
        setA(p.sideL, 'points', pts([A, D, dn(D, thick), dn(A, thick)]));
        setA(p.sideR, 'points', pts([D, C, dn(C, thick), dn(D, thick)]));
        setA(p.edgeB, 'points', pts([dn(A, thick), dn(D, thick), dn(C, thick)]));
        setA(p.far, 'points', pts([A, B, C]));
        setA(p.rim, 'points', pts([A, D, C]));
        setA(p.key, 'x1', f1(A[0])); setA(p.key, 'y1', f1(A[1])); setA(p.key, 'x2', f1(B[0])); setA(p.key, 'y2', f1(B[1]));
        setA(p.hit, 'points', pts([A, B, C, dn(C, thick), dn(D, thick), dn(A, thick)]));
        setA(p.pat, 'transform', m);
      });
      const k = 1.16, bp = pts([proj(-k, k, 0), proj(k, k, 0), proj(k, -k, 0), proj(-k, -k, 0)]);
      [bound.fill, bound.glow1, bound.glow2, bound.core].forEach((e) => setA(e, 'points', bp));
      setA(bound.pat, 'transform', m);
    }
    function measure() {
      let fr = fig.getBoundingClientRect();
      W = Math.max(1, fr.width);
      if (wide) {
        readTop = read.getBoundingClientRect().top - fr.top;
        reserve(); // may grow the instrument, so the rest is measured after it
        fr = fig.getBoundingClientRect();
        Hh = Math.max(1, fr.height);
        const rr = read.getBoundingClientRect(), lr = list.getBoundingClientRect();
        readL = rr.left - fr.left; readR = rr.right - fr.left; readTop = rr.top - fr.top;
        listL = lr.left - fr.left; listR = lr.right - fr.left;
        rowC = btns.map((b) => { const r = b.getBoundingClientRect(); return r.top - fr.top + r.height / 2; });
        const br = bRow.getBoundingClientRect(); by = br.top - fr.top + br.height / 2;
        if (fRow) { const r = fRow.getBoundingClientRect(); fy = r.top - fr.top + r.height / 2; } // level with its label
        cx = (readR + listL) / 2; halfW = clamp((listL - readR) / 2 - 42, 96, 178);
        F0 = 19 * DEG; thick = 7; base = rowC.slice();
      } else {
        reserve();
        halfW = clamp(W * (W < 560 ? 0.29 : 0.27), 84, 196); cx = W * (W < 560 ? 0.39 : 0.38);
        F0 = (W < 560 ? 22 : 18) * DEG; thick = W < 560 ? 6 : 7;
        const hh = halfW * Math.sin(F0), pitch = Math.max(30, hh * (W < 560 ? 0.92 : 0.86)), gap = pitch * 1.5, top = 30 + hh;
        base = []; for (let i = 0; i < N; i++) base.push(top + i * pitch + (i >= bIndex ? 2 * gap - pitch : 0));
        by = top + (bIndex - 1) * pitch + gap;
        let bottom = base[N - 1] + hh + thick;
        if (floor) { fy = bottom + 12; bottom = fy + 10 + fitFloor() * 14; } else bottom += 10; // the floor and its label, under 08
        const need = Math.ceil(bottom + 24);
        if (need !== figH) { figH = need; inst.style.setProperty('--fig-h', figH + 'px'); }
        Hh = figH; rowC = base.slice();
      }
      Sc = halfW / Math.SQRT2;
      view.tF = F0; if (!pointerOn) view.F = F0;
      setA(svg, 'viewBox', `0 0 ${f1(W)} ${f1(Hh)}`);
      field.style.setProperty('--seam', f1(by) + 'px'); field.style.setProperty('--cx', f1(cx) + 'px');
      figTop = fig.getBoundingClientRect().top; navHc = navH();
      geoDirty = true;
    }
    // the floor's label under the drawing (narrow): one line if it fits, else two, split at the middle dot nearest the middle
    let fLines = 0;
    function fitFloor() {
      floor.t1.textContent = floorTxt; floor.t2.textContent = '';
      floor.w1 = floor.t1.getComputedTextLength(); floor.w2 = 0;
      if (floor.w1 <= W - 28 || fParts.length < 2) return (fLines = 1);
      floor.t1.textContent = fParts.slice(0, fMid).join(' · '); floor.t2.textContent = fParts.slice(fMid).join(' · ');
      floor.w1 = floor.t1.getComputedTextLength(); floor.w2 = floor.t2.getComputedTextLength();
      return (fLines = 2);
    }

    /* ---------------- 5 · state ---------------- */
    let hover = -1, focus = -1, open = -1, hot = -2, kbd = false, hoverTimer = 0, pointerOn = false;
    let reduced = reduceMQ.matches, paused = false, visible = false, started = false, exStart = -1, ex = 0, t = 0;
    const cardY = { x: 0, v: 0 };
    let cardTop = 0, cardH = 0, titleOff = 0, cardVis = 0, figTop = 0, navHc = 72;
    const measureCard = () => { cardH = card.offsetHeight; titleOff = snm.offsetTop + snm.offsetHeight / 2; };
    // at rest the stack breathes: a slow wave runs down it, a pixel or two
    const plateY = (i) => by + (base[i] - by) * exOf(i) + plates[i].off.x + (reduced ? 0 : 1.4 * Math.sin(t * 1.15 - i * 0.55) * (1 - plates[i].heat.x));
    const exOf = (i) => {
      if (ex >= 1) return 1;
      const d = Math.abs(i - (bIndex - 0.5)) * 0.06; // the stack opens from the boundary outward
      return ease3(clamp((ex * 1.5 - d) / 1, 0, 1));
    };
    function fillSum(i) {
      const it = items[i], above = i < bIndex;
      skL.textContent = `${it.num} / ${pad2(N)} · ${it.verb}`;
      skR.textContent = above ? 'Decides' : 'Executes';
      snm.textContent = it.name; sjob.textContent = it.job; sjob.hidden = !it.job;
      sIn.textContent = it.inp; sOut.textContent = it.out; sio.hidden = !(it.inp || it.out);
      sside.textContent = '';
      sside.appendChild(glyph(i));
      const sl = H('span', 'sl', sside);
      H('span', '', sl, above ? '↑ Above the boundary' : '↓ Below the boundary');
      H('span', '', sl, noDot(above ? UP.t : DN.t));
      sside.classList.toggle('is-below', !above);
      scue.textContent = open === i ? '' : spec ? (fineMQ.matches ? 'Click, or press Enter, to read its spec below' : 'Tap to read its spec below')
        : fineMQ.matches ? 'Click, or press Enter, to read more' : 'Tap to read more';
      scue.hidden = open === i;
    }
    /* One layer's summary gives way to the next out, then in, never both at once: the old one fades to nothing (90 ms), the
       text changes, the new one rises in (220 ms). A key that arrives while the old one is still fading swaps at once. */
    let swapTimer = 0, swapTo = -1;
    function swapIn(i) {
      swapTo = -1; clearTimeout(swapTimer);
      fillSum(i);
      sum.classList.remove('is-out', 'is-swap'); void sum.offsetWidth; sum.classList.add('is-swap');
      measureCard();
    }
    function fillCard(i, showing) {
      if (reduced || !showing) { swapTo = -1; clearTimeout(swapTimer); fillSum(i); sum.classList.remove('is-out', 'is-swap'); measureCard(); return; }
      if (swapTo >= 0) { swapIn(i); return; } // mid-fade: no waiting
      swapTo = i;
      sum.classList.remove('is-swap'); sum.classList.add('is-out');
      swapTimer = setTimeout(() => { if (swapTo >= 0) swapIn(hot >= 0 ? hot : swapTo); }, 90);
    }
    /* The instrument never changes height while you point around it: it reserves room for the tallest card once per layout
       (and for the open layer's card while one is open), so the page below does not jump on hover. Its wide height is
       already held in CSS (--arch-minh); this only adds room when a card needs more (--arch-cardh). */
    let peekMax = 0, openH = 0;
    function reserve() {
      if (!wide) { if (minH) { minH = 0; inst.style.removeProperty('--arch-cardh'); } return; }
      const was = card.classList.contains('is-peek');
      card.classList.add('is-peek');
      peekMax = 0;
      items.forEach((_, i) => { fillSum(i); peekMax = Math.max(peekMax, card.offsetHeight); });
      openH = 0;
      if (open >= 0) { fillSum(open); card.classList.remove('is-peek'); openH = card.offsetHeight; }
      card.classList.toggle('is-peek', was);
      if (hot >= 0) fillSum(hot);
      measureCard();
      const need = Math.ceil(readTop + Math.max(peekMax, openH) + 40);
      if (Math.abs(need - minH) > 1) { minH = need; inst.style.setProperty('--arch-cardh', need + 'px'); }
    }
    let hotQ = 0; // a blur followed at once by a focus (arrow keys, Tab) must not drop the card for a frame in between
    function setHot(deferred) {
      if (deferred) { if (!hotQ) hotQ = requestAnimationFrame(() => { hotQ = 0; setHot(); }); return; }
      const h = hover >= 0 ? hover : focus >= 0 ? focus : open;
      if (h === hot) return;
      const was = hot;
      hot = h;
      inst.classList.toggle('has-hot', hot >= 0 && wide);
      btns.forEach((b, i) => b.classList.toggle('is-hot', i === hot));
      plates.forEach((p, i) => setA(p.num, 'class', 'ap-num' + (i === hot ? ' is-hot' : '')));
      card.classList.toggle('is-peek', hot !== open);
      if (hot >= 0) { figTop = fig.getBoundingClientRect().top; fillCard(hot, wide && was >= 0 && cardVis > 0.5); }
      kick();
    }
    function placePanels() {
      if (spec) return; // the spec's entries stay where they are
      panels.forEach((p, i) => {
        if (wide && i === open) { if (p.parentNode !== card) card.appendChild(p); }
        else if (p.previousElementSibling !== heads[i]) heads[i].after(p);
      });
    }
    function setOpen(i) {
      if (open >= 0) { btns[open].setAttribute('aria-expanded', 'false'); panels[open].hidden = true; }
      open = i;
      if (open >= 0) { btns[open].setAttribute('aria-expanded', 'true'); panels[open].hidden = false; }
      inst.classList.toggle('has-open', open >= 0);
      placePanels();
      hot = -2; setHot();
      reserve();
      kick();
    }
    // spec mode: a layer leads to its entry in the spec below; the entry takes focus and lights up
    let litT = 0;
    function jump(i) {
      const e = items[i].el;
      items.forEach((it, k) => it.el.classList.toggle('is-lit', k === i));
      e.classList.remove('is-flash'); void e.offsetWidth; e.classList.add('is-flash');
      clearTimeout(litT); litT = setTimeout(() => e.classList.remove('is-flash'), 2400);
      e.scrollIntoView({ block: 'start', behavior: reduced ? 'instant' : 'smooth' });
      e.focus({ preventScroll: true });
    }
    function setMode(w) {
      wide = w;
      inst.classList.toggle('is-wide', wide); inst.classList.toggle('is-narrow', !wide);
      inst.style.removeProperty('--arch-cardh'); minH = 0;
      placePanels();
      hint.textContent = spec ? (wide && fineMQ.matches ? 'Point at a layer · ↑ ↓ · Enter for its spec' : fineMQ.matches ? 'Click a plate for its spec' : 'Tap a plate for its spec')
        : wide && fineMQ.matches ? 'Point at a layer · ↑ ↓ to move · Enter to open' : fineMQ.matches ? 'Click a layer to open it' : 'Tap a layer to open it';
      hot = -2; setHot();
      measure(); kick(true);
    }

    /* ---------------- 6 · input ---------------- */
    const hoverIn = (i) => { if (kbd) return; clearTimeout(hoverTimer); hover = i; setHot(); };
    const hoverOut = (i) => { clearTimeout(hoverTimer); hoverTimer = setTimeout(() => { if (hover === i) { hover = -1; setHot(); } }, 110); };
    const isMouse = (e) => e.pointerType === 'mouse' || e.pointerType === 'pen';
    btns.forEach((b, i) => {
      b.addEventListener('click', () => { if (spec) jump(i); else setOpen(open === i ? -1 : i); });
      b.addEventListener('focus', () => { focus = i; setHot(); });
      b.addEventListener('blur', () => { if (focus === i) { focus = -1; setHot(true); } });
      b.addEventListener('pointerenter', (e) => { if (isMouse(e)) hoverIn(i); });
      b.addEventListener('pointerleave', (e) => { if (isMouse(e)) hoverOut(i); });
      b.addEventListener('keydown', (e) => {
        let j = -1;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') j = Math.min(N - 1, i + 1);
        else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') j = Math.max(0, i - 1);
        else if (e.key === 'Home') j = 0;
        else if (e.key === 'End') j = N - 1;
        else if (e.key === 'Escape' && open >= 0) { e.preventDefault(); const o = open; setOpen(-1); btns[o].focus(); return; }
        else { if (e.key === 'Enter' || e.key === ' ') { kbd = true; clearTimeout(hoverTimer); hover = -1; } return; }
        e.preventDefault();
        kbd = true; clearTimeout(hoverTimer); hover = -1;
        if (j !== i) btns[j].focus(); else setHot();
      });
    });
    plates.forEach((p, i) => {
      p.hit.addEventListener('pointerenter', (e) => { if (isMouse(e)) hoverIn(i); });
      p.hit.addEventListener('pointerleave', (e) => { if (isMouse(e)) hoverOut(i); });
      p.hit.addEventListener('click', () => {
        if (spec) { jump(i); return; }
        setOpen(open === i ? -1 : i);
        btns[i].focus({ preventScroll: true });
        if (open !== i || wide) return;
        // narrow: the layer opens in the list under the drawing; bring its heading and text into view
        const nh = navH(), top = btns[i].getBoundingClientRect().top, bottom = panels[i].getBoundingClientRect().bottom;
        if (top < nh + 4 || bottom > window.innerHeight - 8) window.scrollTo({ top: Math.max(0, window.scrollY + top - nh - 10), behavior: reduced ? 'auto' : 'smooth' });
      });
    });
    inst.addEventListener('pointermove', (e) => {
      if (!isMouse(e)) return;
      if (kbd) { // the pointer takes over from the keyboard: hover what it is on now (its enter event came while keys ruled)
        kbd = false;
        const b = e.target.closest ? e.target.closest('.arch-layer') : null, i = b ? btns.indexOf(b) : plates.findIndex((p) => p.hit === e.target);
        if (i >= 0) hoverIn(i);
      }
      if (reduced || !wide) return;
      const r = fig.getBoundingClientRect();
      const px = clamp(((e.clientX - r.left) / r.width - 0.5) * 2, -1, 1), py = clamp(((e.clientY - r.top) / r.height - 0.5) * 2, -1, 1);
      pointerOn = true; view.tT = (45 + px * 3.2) * DEG; view.tF = F0 + -py * 1.4 * DEG;
      kick();
    }, { passive: true });
    inst.addEventListener('pointerleave', () => { pointerOn = false; view.tT = 45 * DEG; view.tF = F0; kick(); });
    motionBtn.addEventListener('click', () => {
      paused = !paused;
      motionBtn.textContent = paused ? 'Resume motion' : 'Pause motion';
      inst.classList.toggle('is-paused', paused);
      kick();
    });

    /* ---------------- 7 · the illustrative flow: one proposal's way down the stack ---------------- */
    const flows = [];
    let nextSpawn = 0.6, council = bIndex - 1, step = 0, stepT = 0, pulse = 0, permit = 0;
    const DWELL_UP = 0.46, DWELL_DN = 0.3, DWELL_COUNCIL = 0.78, MOVE = 0.56;
    const snapG = (x) => Math.round(clamp(x, -0.75, 0.75) * 4) / 4;
    function spawn() {
      const st = [];
      for (let k = 0; k < N; k++) {
        if (k < council) st.push({ u: (rnd() - 0.5) * 1.1, v: (rnd() - 0.5) * 1.1 });
        else if (k === council) st.push({ u: 0, v: 0 });
        else st.push({ u: snapG((rnd() - 0.5) * 1.5), v: snapG((rnd() - 0.5) * 1.5) });
      }
      const segs = [{ type: 'enter', at: 0, d: 0.8 }];
      for (let k = 0; k < N; k++) {
        segs.push({ type: 'dwell', at: k, d: k === council ? DWELL_COUNCIL : k < council ? DWELL_UP : DWELL_DN });
        if (k < N - 1) segs.push({ type: 'move', from: k, to: k + 1, d: MOVE });
      }
      segs.push({ type: 'exit', at: N - 1, d: 0.95 });
      const g = S('g', null);
      const f = { st, segs, s: 0, t: 0, reject: rnd() < 0.16, decided: false, kind: 'signal', g, lvl: null, alpha: 0, x: 0, y: 0, side: rnd() < 0.5 ? -1 : 1, ringR: 3.6, regT: -1, sqT: -1 };
      f.halo = S('circle', { r: 8, fill: IVORY, 'fill-opacity': 0.1 }, g);
      f.dot = S('circle', { r: 1.9, fill: IVORY }, g);
      // one mark for the proposal and what it becomes: a ring (rx = half its size), still a ring below the boundary, that
      // squares up only on the last plate, as the swarm lab settles its own at 06 Settle
      f.mk = S('rect', { fill: GREEN, 'fill-opacity': 0, stroke: GREEN, 'stroke-width': 1.4, display: 'none' }, g);
      // registration ticks: they close on the mark as it settles
      f.reg = S('path', { d: 'M-5.5 -2.5V-5.5H-2.5M2.5 -5.5H5.5V-2.5M5.5 2.5V5.5H2.5M-2.5 5.5H-5.5V2.5', fill: 'none', stroke: GREEN, 'stroke-width': 1, 'stroke-opacity': 0, 'vector-effect': NSS }, g);
      flows.push(f);
    }
    const stationXY = (k, u, v, h) => { const q = proj(u, v, h); return [cx + q[0], plateY(k) + q[1]]; };
    function setMark(f, m) { // m: 0 = the proposal's ring, 1 = a settled square
      const s = 2 * f.ringR * (1 - m) + 5.6 * m, rx = (s / 2) * (1 - m) + 0.4 * m;
      setA(f.mk, 'x', f1(-s / 2)); setA(f.mk, 'y', f1(-s / 2)); setA(f.mk, 'width', f1(s)); setA(f.mk, 'height', f1(s)); setA(f.mk, 'rx', f1(rx));
      setA(f.mk, 'fill-opacity', f3(m)); setA(f.mk, 'stroke-opacity', f3(1 - m));
    }
    function setKind(f, kind) {
      f.kind = kind;
      setA(f.dot, 'display', kind === 'signal' || kind === 'reject' ? 'inline' : 'none');
      setA(f.dot, 'fill', kind === 'reject' ? RED : IVORY); setA(f.dot, 'r', kind === 'reject' ? '2.6' : '1.9');
      setA(f.mk, 'display', kind === 'proposal' || kind === 'settled' ? 'inline' : 'none');
      if (kind === 'proposal') setMark(f, 0); else if (kind === 'settled') setMark(f, 1);
      setA(f.halo, 'fill', kind === 'signal' ? IVORY : kind === 'reject' ? RED : GREEN);
      setA(f.halo, 'fill-opacity', kind === 'signal' ? '0.1' : '0.16');
    }
    function toLevel(f, key) { if (f.lvl !== key) { f.lvl = key; (key === 'bottom' ? gBot : key === 'front' ? gFront : levels[key]).appendChild(f.g); } }
    function flowStep(dt) {
      if (ex >= 1 && (nextSpawn -= dt) <= 0) { if (flows.length < 4) spawn(); nextSpawn = 1.25 + rnd() * 0.9; }
      for (let n = flows.length - 1; n >= 0; n--) {
        const f = flows[n];
        f.t += dt;
        let seg = f.segs[f.s];
        while (seg && f.t >= seg.d) { f.t -= seg.d; f.s++; seg = f.segs[f.s]; if (seg) onSeg(f, seg); }
        if (!seg) { f.g.remove(); flows.splice(n, 1); continue; }
        const p = f.t / seg.d;
        let x, y, a = 1;
        if (seg.type === 'enter') {
          const s0 = f.st[0], A = stationXY(0, s0.u, s0.v, 1.15), B = stationXY(0, s0.u, s0.v, 0.03), e = ease3(p);
          x = A[0] + (B[0] - A[0]) * e; y = A[1] + (B[1] - A[1]) * e; a = Math.min(1, p * 2.2); toLevel(f, 0);
          if (f.kind !== 'signal') setKind(f, 'signal');
        } else if (seg.type === 'dwell') {
          const k = seg.at, s0 = f.st[k];
          let u = s0.u, v = s0.v;
          if (k < council) { u += 0.03 * Math.sin(t * 7 + n); v += 0.03 * Math.cos(t * 6.1 + n * 2); }
          [x, y] = stationXY(k, u, v, 0.03); toLevel(f, k);
          if (k === council && !f.decided && p > 0.45) decide(f);
          if (f.kind === 'reject') { const q = clamp((p - 0.45) / 0.55, 0, 1); x += f.side * 26 * q; y += 30 * q * q; a = 1 - q; toLevel(f, 'front'); }
        } else if (seg.type === 'move') {
          const sa = f.st[seg.from], sb = f.st[seg.to];
          const A = stationXY(seg.from, sa.u, sa.v, 0.03), B = stationXY(seg.to, sb.u, sb.v, 0.03);
          let e;
          if (seg.to <= council) { // estimation: a curved path, eased
            e = inout(p); x = A[0] + (B[0] - A[0]) * e + Math.sin(Math.PI * p) * 12 * f.side; y = A[1] + (B[1] - A[1]) * e;
          } else { // deterministic: straight, and it snaps in at the end
            e = p < 0.78 ? inout(p / 0.78) * 0.97 : 0.97 + 0.03 * ease3((p - 0.78) / 0.22); x = A[0] + (B[0] - A[0]) * e; y = A[1] + (B[1] - A[1]) * e;
          }
          if (seg.from === council) { // the approved ring crosses the plane (it flashes) and lands on the grid below, a ring still
            const u = sa.u + (sb.u - sa.u) * e, v = sa.v + (sb.v - sa.v) * e;
            if (y < by + proj(u, v, 0)[1]) toLevel(f, 'B'); // still above the plane's surface
            else {
              toLevel(f, seg.to);
              if (!f.crossed) { f.crossed = true; bound.flash = 1; bound.ripT = 1; bound.ru = u; bound.rv = v; }
            }
          } else toLevel(f, seg.to);
        } else if (floor) { // exit: the settled square drops from the last plate to the floor, lands, and is taken in
          const sN = f.st[N - 1], A = stationXY(N - 1, sN.u, sN.v, 0.03), q = clamp(p / 0.55, 0, 1), e = q * q;
          x = A[0]; y = A[1] + (fy - 4 - A[1]) * e; toLevel(f, 'bottom');
          if (q >= 1 && !f.landed) { f.landed = true; floor.land = 1; floor.lx = x; }
          a = p < 0.62 ? 1 : 1 - (p - 0.62) / 0.38;
        } else { // exit, under the last plate
          const sN = f.st[N - 1], A = stationXY(N - 1, sN.u, sN.v, 0.03), B = stationXY(N - 1, sN.u, sN.v, -1.5), e = p * p;
          x = A[0] + (B[0] - A[0]) * e; y = A[1] + (B[1] - A[1]) * e; a = 1 - p; toLevel(f, 'bottom');
        }
        if (f.sqT >= 0) { // settling, on the last plate: the ring closes into a square in ~220 ms
          f.sqT += dt;
          setMark(f, ease3(Math.min(1, f.sqT / 0.22)));
          if (f.sqT >= 0.22) f.sqT = -1;
        }
        if (f.regT >= 0) { // the snap: ticks close on the square in ~220 ms, then let go
          f.regT += dt;
          const r = f.regT, k = 1 + 1.3 * (1 - ease3(Math.min(1, r / 0.22)));
          setA(f.reg, 'transform', `scale(${f3(k)})`);
          setA(f.reg, 'stroke-opacity', f3(r < 0.22 ? 0.95 : Math.max(0, 0.95 * (1 - (r - 0.22) / 0.34))));
          if (r > 0.56) { f.regT = -1; setA(f.reg, 'stroke-opacity', '0'); }
        }
        f.x = x; f.y = y;
        setA(f.g, 'transform', `translate(${f1(x)} ${f1(y)})`);
        setA(f.g, 'opacity', f3(clamp(a, 0, 1)));
      }
    }
    function onSeg(f, seg) {
      if (seg.type === 'dwell' && seg.at === 2 && f.kind === 'signal') setKind(f, 'proposal');
      if (seg.type === 'move' && seg.to === 2 && f.kind === 'signal') setKind(f, 'proposal');
      if (seg.type === 'dwell' && seg.at === N - 1) {
        permit = 1;
        if (f.kind === 'proposal' && f.decided) { f.kind = 'settled'; f.sqT = 0; f.regT = 0; } // the last plate settles it
      }
      // the readout's In and Out tick as work reaches, and leaves, the layer you are looking at
      if (hot >= 0 && wide) {
        if (seg.type === 'dwell' && seg.at === hot) tick(sIn);
        else if ((seg.type === 'move' && seg.from === hot) || (seg.type === 'exit' && hot === N - 1)) tick(sOut);
      }
    }
    function tick(dd) { const row = dd.parentNode; row.classList.remove('is-tick'); void row.offsetWidth; row.classList.add('is-tick'); }
    function decide(f) {
      f.decided = true; pulse = 1;
      if (f.reject) { setKind(f, 'reject'); f.segs.length = f.s + 1; } // its way ends here: it falls away
      else { f.ringR = 4.2; setA(f.mk, 'stroke-width', '2'); setMark(f, 0); } // approved: the ring brightens and goes on
    }

    /* ---------------- 8 · the frame ---------------- */
    let raf = 0, last = 0;
    function targets() {
      plates.forEach((p, i) => {
        p.tOff = hot < 0 ? 0 : i === hot ? -14 : i < hot ? -9 : 9;
        p.tHeat = i === hot ? 1 : 0;
        // only the plate right above overlaps the lifted one (not across the boundary's gap): it turns to glass; the rest step back
        p.tFade = hot < 0 || i === hot ? 0 : i === hot - 1 && hot !== bIndex ? 1 : 0.5;
      });
    }
    function animate(dt, snap) { // advances the springs; returns true while anything is still settling
      targets();
      let busy = false;
      snap = snap || reduced;
      plates.forEach((p) => {
        if (snap) { p.off.x = p.tOff; p.off.v = 0; p.heat.x = p.tHeat; p.heat.v = 0; p.fade.x = p.tFade; p.fade.v = 0; }
        else if (dt > 0) { spring(p.off, p.tOff, dt, 17); spring(p.heat, p.tHeat, dt, 16); spring(p.fade, p.tFade, dt, 14); }
        if (!still(p.off, p.tOff) || Math.abs(p.heat.x - p.tHeat) > 0.004 || Math.abs(p.fade.x - p.tFade) > 0.004) busy = true;
      });
      if (Math.abs(view.T - view.tT) > 1e-4 || Math.abs(view.F - view.tF) > 1e-4) {
        const k = snap ? 1 : 1 - Math.exp(-dt * 6);
        view.T += (view.tT - view.T) * k; view.F += (view.tF - view.F) * k; geoDirty = true;
        if (Math.abs(view.T - view.tT) > 1e-4 || Math.abs(view.F - view.tF) > 1e-4) busy = true;
      }
      if (exStart >= 0 && ex < 1) { ex = reduced ? 1 : clamp((performance.now() - exStart) / 1300, 0, 1); if (ex < 1) busy = true; }
      if (ex >= 1 && !inst.classList.contains('is-ready')) inst.classList.add('is-ready'); // the stack is open (a hook for tests)
      const cvT = wide && hot >= 0 ? 1 : 0;
      cardVis = snap ? cvT : cardVis + (cvT - cardVis) * (1 - Math.exp(-dt * 11));
      if (Math.abs(cardVis - cvT) > 0.01) busy = true; else cardVis = cvT;
      // the readout card follows the plate you point at (wide)
      if (wide && hot >= 0) {
        const inLo = readTop, inHi = Math.max(readTop, Hh - 40 - cardH);       // inside the instrument
        const vTop = navHc + 14 - figTop, vBot = window.innerHeight - 14 - figTop; // on screen, in the drawing's coordinates
        let lo = Math.max(inLo, vTop), hi = Math.min(inHi, vBot - cardH);
        if (lo > hi) { lo = Math.max(14, vTop); hi = Math.max(lo, Math.min(Hh - 14 - cardH, vBot - cardH)); } // tight: use the padding too
        const target = clamp(plateY(hot) - titleOff, lo, hi) - readTop;
        if (snap || !card.__placed) { cardY.x = target; cardY.v = 0; card.__placed = true; } else if (dt > 0) spring(cardY, target, dt, 15);
        if (!still(cardY, target)) busy = true;
        card.style.transform = `translateY(${f1(cardY.x)}px)`;
        cardTop = readTop + cardY.x + titleOff;
      } else card.__placed = false;
      return busy;
    }
    function render() {
      if (geoDirty) { shape(); geoDirty = false; }
      const C = proj(1, -1, 0), A = proj(-1, 1, 0);
      plates.forEach((p, i) => {
        const y = plateY(i), f = p.fade.x, h = p.heat.x, vis = 1 - 0.62 * f;
        setA(p.g, 'transform', `translate(${f1(cx)} ${f1(y)})`);
        setA(p.hit, 'transform', `translate(${f1(cx)} ${f1(by + (base[i] - by) * exOf(i))})`);
        setA(p.top, 'fill-opacity', f3(0.93 - 0.6 * f));
        setA(p.glow, 'fill-opacity', f3(0.075 * h));
        setA(p.sideL, 'fill-opacity', f3(0.97 - 0.5 * f)); setA(p.sideR, 'fill-opacity', f3(0.97 - 0.5 * f));
        setA(p.rim, 'stroke-opacity', f3((0.4 + 0.55 * h) * (1 - 0.45 * f)));
        setA(p.far, 'stroke-opacity', f3((0.15 + 0.3 * h) * (1 - 0.35 * f)));
        setA(p.key, 'stroke-opacity', f3((0.16 + 0.66 * h) * (1 - 0.5 * f))); // the green key light, from the upper left
        setA(p.pat, 'opacity', f3((0.74 + 0.26 * h) * vis));
        setA(p.bead, 'opacity', f3((0.8 + 0.2 * h) * vis));
        // beads: estimation above the boundary
        p.beads.forEach((b, k) => {
          let u, v, hh;
          if (b.mote) {
            const ph = (t * b.sp + b.ph) % 1, r = 0.95 - ph * 0.86;
            u = Math.cos(b.a) * r; v = Math.sin(b.a) * r; hh = b.h0;
            setA(b.el, 'fill-opacity', f3(Math.min(1, ph * 5, (1 - ph) * 3) * 0.75));
          } else {
            const tt = t;
            u = b.u0 + b.a * Math.sin(b.w1 * tt + b.p1); v = b.v0 + b.a * Math.cos(b.w2 * tt + b.p2); hh = b.h0 + 0.015 * Math.sin(b.w1 * 0.6 * tt + b.p2);
          }
          const q = proj(u, v, hh);
          setA(b.el, 'cx', f1(q[0])); setA(b.el, 'cy', f1(q[1]));
        });
        if (p.att) { setA(p.att, 'cx', f3(0.42 * Math.sin(t * 0.31 + 0.4))); setA(p.att, 'cy', f3(0.38 * Math.sin(t * 0.23 + 1.3))); }
        if (p.ticks) { setA(p.ticks, 'stroke-opacity', f3(0.5 + 0.45 * pulse)); setA(p.pulse, 'r', f3(0.5 + 0.28 * (1 - pulse))); setA(p.pulse, 'stroke-opacity', f3(0.75 * pulse)); }
        if (p.cells) p.cells.forEach((c) => { const on = (step + c.r * 2) % 5; setA(c.el, 'fill-opacity', c.c === on ? '0.95' : c.c < on ? '0.16' : '0'); });
        if (p.ports) p.ports.forEach((e, k) => setA(e, 'fill-opacity', step % 3 === k ? '0.9' : '0'));
        if (p.permit) setA(p.permit, 'fill-opacity', f3(0.3 + 0.65 * permit));
        // labels (narrow): numbers beside the plates
        const xr = cx + C[0] + 12;
        setA(p.num, 'x', f1(xr)); setA(p.num, 'y', f1(y + C[1]));
      });
      // explosion lines between the plates' corners; they stretch as a plate lifts
      const gA = clamp((ex - 0.6) / 0.4, 0, 1);
      if (gA > 0) {
        const D = proj(-1, -1, 0);
        let d = '';
        for (let i = 0; i < N - 1; i++) {
          const y0 = plateY(i), y1 = plateY(i + 1);
          for (const K of [A, D, C]) { const ya = y0 + K[1] + thick + 3, yb = y1 + K[1] - 3; if (yb - ya > 6) d += `M${f1(cx + K[0])} ${f1(ya)}V${f1(yb)}`; }
        }
        setA(guides, 'd', d);
      }
      setA(guides, 'stroke-opacity', f3(0.24 * gA));
      // the boundary plane and its line across the instrument
      const bk = 1.16, BL = proj(-bk, bk, 0), BR = proj(bk, -bk, 0);
      setA(bound.g, 'transform', `translate(${f1(cx)} ${f1(by)})`);
      setA(bound.core, 'stroke-opacity', f3(0.82 + 0.18 * bound.flash));
      setA(bound.glow1, 'stroke-opacity', f3(0.13 + 0.3 * bound.flash));
      setA(bound.ripple, 'r', f3(0.06 + 0.42 * (1 - bound.ripT))); setA(bound.ripple, 'stroke-opacity', f3(0.8 * bound.ripT));
      setA(bound.ripple, 'cx', f3(bound.ru)); setA(bound.ripple, 'cy', f3(bound.rv));
      const x0 = wide ? readL : 14, x1 = wide ? listR : W - 14, xs = wide ? readR + 14 : x0;
      const bl = clamp((ex - 0.55) / 0.35, 0, 1);
      // the line runs the width of the instrument; under the readout it gives way while a card is showing
      setA(bound.line0, 'x1', f1(x0)); setA(bound.line0, 'x2', f1(xs)); setA(bound.line0, 'y1', f1(by)); setA(bound.line0, 'y2', f1(by));
      setA(bound.lineL, 'x1', f1(xs)); setA(bound.lineL, 'x2', f1(cx + BL[0] - 8)); setA(bound.lineL, 'y1', f1(by)); setA(bound.lineL, 'y2', f1(by));
      setA(bound.lineR, 'x1', f1(cx + BR[0] + 8)); setA(bound.lineR, 'x2', f1(x1)); setA(bound.lineR, 'y1', f1(by)); setA(bound.lineR, 'y2', f1(by));
      setA(bound.line0, 'stroke-opacity', f3(0.5 * bl * (1 - cardVis))); setA(bound.lineL, 'stroke-opacity', f3(0.5 * bl)); setA(bound.lineR, 'stroke-opacity', f3(0.5 * bl));
      if (!wide) {
        const roomy = W - (cx + BR[0] + 12) > 170;
        setA(bound.tUp, 'x', f1(cx + BR[0] + 12)); setA(bound.tUp, 'y', f1(by - 8));
        setA(bound.tDn, 'x', f1(cx + BR[0] + 12)); setA(bound.tDn, 'y', f1(by + 16));
        setA(bound.tUp, 'opacity', f3(bl)); setA(bound.tDn, 'opacity', f3(bl));
        const up = '↑ ' + (roomy ? noDot(UP.t) : 'Decides'), dnT = '↓ ' + (roomy ? noDot(DN.t) : 'Executes');
        if (bound.tUp.textContent !== up) bound.tUp.textContent = up;
        if (bound.tDn.textContent !== dnT) bound.tDn.textContent = dnT;
        plates.forEach((p, i) => { const t2 = roomy ? p.numLong : p.numShort; if (p.num.textContent !== t2) p.num.textContent = t2; setA(p.num, 'opacity', f3(clamp((exOf(i) - 0.8) / 0.2, 0, 1))); });
      }
      // the floor: a ground line under the stack, hatched beneath it as in a technical drawing; wide, a dotted leader
      // carries it on to its row in the list; narrow, its label sits under it. A settled action lands on it with a mark.
      if (floor) {
        const fa = clamp((ex - 0.7) / 0.3, 0, 1), xa = cx - halfW * 1.3, xb = cx + halfW * 1.3;
        setA(floor.line, 'x1', f1(xa)); setA(floor.line, 'x2', f1(xb)); setA(floor.line, 'y1', f1(fy)); setA(floor.line, 'y2', f1(fy));
        setA(floor.line, 'stroke-opacity', f3(0.55 * fa));
        const hk = `${f1(xa)} ${f1(xb)} ${f1(fy)}`;
        if (floor.hk !== hk) {
          floor.hk = hk;
          let d = '';
          for (let x = xa + 6; x <= xb - 2; x += 7) d += `M${f1(x)} ${f1(fy + 1.5)}l-5 5.5`;
          setA(floor.hatch, 'd', d);
        }
        setA(floor.hatch, 'stroke-opacity', f3(0.3 * fa));
        setA(floor.lead, 'display', wide ? 'inline' : 'none'); setA(floor.node, 'display', wide ? 'inline' : 'none');
        if (wide) {
          setA(floor.lead, 'x1', f1(xb + 6)); setA(floor.lead, 'x2', f1(listL - 6)); setA(floor.lead, 'y1', f1(fy)); setA(floor.lead, 'y2', f1(fy));
          setA(floor.lead, 'stroke-opacity', f3(0.5 * fa));
          setA(floor.node, 'cx', f1(listL - 4)); setA(floor.node, 'cy', f1(fy)); setA(floor.node, 'fill-opacity', f3(0.7 * fa));
        } else {
          const at = (w) => f1(clamp(cx, w / 2 + 14, W - w / 2 - 14));
          setA(floor.t1, 'x', at(floor.w1 || 0)); setA(floor.t1, 'y', f1(fy + 19));
          setA(floor.t2, 'x', at(floor.w2 || 0)); setA(floor.t2, 'y', f1(fy + 33));
          setA(floor.t1, 'opacity', f3(fa)); setA(floor.t2, 'opacity', f3(fa));
        }
        setA(floor.mark, 'x1', f1(floor.lx - 9)); setA(floor.mark, 'x2', f1(floor.lx + 9)); setA(floor.mark, 'y1', f1(fy)); setA(floor.mark, 'y2', f1(fy));
        setA(floor.mark, 'stroke-opacity', f3(0.95 * floor.land));
      }
      // leader lines: plate -> its button (wide), plate -> readout card (wide, the plate you point at)
      plates.forEach((p, i) => {
        const L = leads[i];
        if (!wide) { setA(L.line, 'display', 'none'); setA(L.a, 'display', 'none'); setA(L.b, 'display', 'none'); return; }
        setA(L.line, 'display', 'inline'); setA(L.a, 'display', 'inline'); setA(L.b, 'display', 'inline');
        const y = plateY(i), xa = cx + C[0] + 9, ya = y + C[1], xb = listL - 4, yb = rowC[i], h = p.heat.x, on = clamp((exOf(i) - 0.82) / 0.18, 0, 1);
        setA(L.line, 'x1', f1(xa)); setA(L.line, 'y1', f1(ya)); setA(L.line, 'x2', f1(xb)); setA(L.line, 'y2', f1(yb));
        setA(L.line, 'stroke-opacity', f3((0.15 + 0.55 * h) * (1 - 0.4 * p.fade.x) * on));
        setA(L.a, 'cx', f1(xa)); setA(L.a, 'cy', f1(ya)); setA(L.a, 'fill-opacity', f3((0.35 + 0.6 * h) * on));
        setA(L.b, 'cx', f1(xb)); setA(L.b, 'cy', f1(yb)); setA(L.b, 'fill-opacity', f3(h * on));
      });
      if (wide && hot >= 0) { // a technical callout: out of the plate, along, and into the readout at its title
        const y = plateY(hot), xa = cx + A[0] - 9, ya = y + A[1], xe = readR + 14, xm = Math.max(xe + 6, Math.min(xa - 12, readR + 30));
        setA(cardLead, 'points', `${f1(xa)},${f1(ya)} ${f1(xm)},${f1(ya)} ${f1(xm)},${f1(cardTop)} ${f1(xe)},${f1(cardTop)}`);
        setA(cardLead, 'stroke-opacity', f3(0.5 * plates[hot].heat.x));
        setA(cardNode, 'cx', f1(xa)); setA(cardNode, 'cy', f1(ya)); setA(cardNode, 'fill-opacity', f3(plates[hot].heat.x));
      } else { setA(cardLead, 'stroke-opacity', '0'); setA(cardNode, 'fill-opacity', '0'); }
      if (wide) { const ovT = `translateY(${f1(by - readTop)}px)`; if (ov.style.transform !== ovT) ov.style.transform = ovT; }
      setA(ov, 'data-in', ex >= 0.9 ? '1' : '0');
    }
    function frame(now) {
      raf = 0;
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000)); last = now;
      const ambient = !reduced && !paused && started;
      if (ambient) {
        t += dt;
        flowStep(dt);
        pulse = Math.max(0, pulse - dt / 0.3); permit = Math.max(0, permit - dt / 0.55);
        bound.flash = Math.max(0, bound.flash - dt / 0.22); bound.ripT = Math.max(0, bound.ripT - dt / 0.6);
        if (floor) floor.land = Math.max(0, floor.land - dt / 0.6);
        if ((stepT += dt) > 0.7) { stepT = 0; step++; }
      }
      const busy = animate(dt, false);
      render();
      if ((ambient || busy) && visible && !document.hidden) raf = requestAnimationFrame(frame);
    }
    function kick(force) {
      if (reduced || !visible || document.hidden) { // no loop: settle to the final state and draw once
        if (raf) { cancelAnimationFrame(raf); raf = 0; }
        if (reduced && exStart >= 0) ex = 1;
        animate(0, true); render();
        return;
      }
      if (force) { animate(0, false); render(); } // a new layout: draw it now, the springs carry on in the loop
      if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
    }

    /* ---------------- 9 · wiring ---------------- */
    setMode(wideMQ.matches);
    inst.classList.remove('is-building');
    motionBtn.hidden = reduced;
    wideMQ.addEventListener('change', (e) => setMode(e.matches));
    fineMQ.addEventListener('change', () => setMode(wideMQ.matches));
    reduceMQ.addEventListener('change', (e) => {
      reduced = e.matches; motionBtn.hidden = reduced;
      if (reduced) { flows.splice(0).forEach((f) => f.g.remove()); pulse = permit = 0; bound.flash = bound.ripT = 0; if (floor) floor.land = 0; ex = exStart >= 0 ? 1 : ex; }
      kick(true);
    });
    // a new size is measured in the next frame, not inside the observer: measuring can resize the instrument (the room it
    // reserves for the card), and resizing an observed box inside its own callback is a ResizeObserver loop
    let roQueued = false;
    const ro = new ResizeObserver(() => {
      if (roQueued) return;
      roQueued = true;
      requestAnimationFrame(() => { roQueued = false; measure(); measureCard(); kick(true); });
    });
    ro.observe(bodyEl); ro.observe(list);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measure(); measureCard(); kick(true); });
    new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        visible = e.isIntersecting;
        // open the stack once a fair part of it is on screen (a tall instrument on a short screen never reaches a fixed ratio)
        const seen = e.intersectionRect.height >= Math.min(window.innerHeight * 0.32, e.boundingClientRect.height * 0.3);
        if (visible && seen && exStart < 0) { exStart = performance.now(); started = true; if (reduced) ex = 1; }
      });
      kick();
    }, { threshold: [0, 0.05, 0.1, 0.2, 0.3, 0.5] }).observe(inst);
    document.addEventListener('visibilitychange', () => kick());
    window.addEventListener('scroll', () => { if (wide && hot >= 0 && visible) { figTop = fig.getBoundingClientRect().top; kick(); } }, { passive: true });
    // printing: every layer's detail, inline, in order (the spec prints as it stands; CSS leaves its stage out)
    if (!spec) {
      window.addEventListener('beforeprint', () => { panels.forEach((p) => { p.hidden = false; }); if (wide) { wide = false; inst.classList.remove('is-wide'); inst.classList.add('is-narrow'); placePanels(); } });
      window.addEventListener('afterprint', () => { panels.forEach((p, i) => { p.hidden = i !== open; }); setMode(wideMQ.matches); });
    }
  }
})();
