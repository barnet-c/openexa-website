/* OpenEXA · the architecture explorer (Platform §01): a .layers[data-arch] list made an instrument. hc6 (HC6 item 5): the
   stack and its index, one text system: no readout; a layer's sentence opens under its row; the boundary is a green
   hairline through the index, level with the plane, its label on it. */
(function () {
  'use strict';
  const roots = Array.from(document.querySelectorAll('.layers[data-arch]'));
  // no instrument here: the list stays a list (.is-plain lifts the room CSS holds for the instrument)
  if (!roots.length || !('ResizeObserver' in window) || !('IntersectionObserver' in window)) { roots.forEach((r) => r.classList.add('is-plain')); return; }

  const NS = 'http://www.w3.org/2000/svg';
  const reduceMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
  // (hc6) the stack and its index side by side from tablets up (two columns since the readout went); a phone on its side
  // keeps the drawing over the list (shortMQ's fit)
  const wideMQ = window.matchMedia('(min-width: 1000px), (min-width: 760px) and (min-height: 560px)');
  const fineMQ = window.matchMedia('(hover: hover) and (pointer: fine)');
  const shortMQ = window.matchMedia('(max-height: 520px) and (min-aspect-ratio: 23/20)');
  const IVORY = '#F5F2EC', GREEN = '#4FCB93', KHAKI = '#ACA68E', RED = '#D9675D';
  const DEG = Math.PI / 180;
  const pad2 = (n) => String(n).padStart(2, '0');
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const ease3 = (t) => 1 - Math.pow(1 - t, 3);
  const inout = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
  const f1 = (v) => (Math.round(v * 10) / 10).toString();
  const f2 = (v) => (Math.round(v * 100) / 100).toString();
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
  function setS(e, k, v) { const c = e.__s || (e.__s = {}); if (c[k] !== v) { c[k] = v; e.style[k] = v; } }
  // a layer's name in the serif: each hyphen in the site's span, the face's wide bearings taken in (.hy; r3)
  function nameInto(el, s) {
    el.textContent = '';
    const re = /\p{L}[-‐](?=\p{L})/gu;
    let at = 0, m;
    while ((m = re.exec(s))) { const cut = m.index + m[0].length - 1; el.append(s.slice(at, cut)); H('span', 'hy', el, '-'); at = cut + 1; }
    el.append(s.slice(at));
  }
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
  const buildAll = () => roots.forEach((root) => explorer(root, uid++));
  // (award a3, a3-dev) a page reached by a view transition, at its top, builds its explorers once the transition is over
  // (they sit a screen or more below): built at once, the build ran inside the transition's frames
  const vt = !location.hash && document.activeViewTransition;
  if (vt && vt.finished) vt.finished.then(buildAll, buildAll); else buildAll();

  function explorer(root, id) {
    const pre = `arch${id}`;
    const spec = root.hasAttribute('data-arch-spec'); // Platform: the list stays, as the spec under the instrument
    const scn = !spec && root.closest('.stack-scene'), stage = scn && scn.firstElementChild;
    const hp = scn && scn.querySelector('.hero-plate--stack'), hsvg = hp && hp.querySelector('.hp-art > svg'), sect = scn && root.closest('section');
    let pin = false, sp = 1, sA = 0, sZ = 1, sm = 0;
    /* ---------------- 1 · read the list (also what readers without JavaScript get) ---------------- */
    const items = [];
    let bIndex = -1, bEl = null, fEl = null;
    const txt = (n) => (n ? n.textContent : '').replace(/\s+/g, ' ').trim();
    Array.from(root.children).forEach((el) => {
      if (el.classList.contains('layer')) {
        const k = el.querySelector('.k'), h3 = el.querySelector('h3'), small = h3 && h3.querySelector('small'), body = el.lastElementChild;
        const name = h3 ? Array.from(h3.childNodes).filter((n) => n !== small).map((n) => n.textContent).join('').replace(/\s+/g, ' ').trim() : '';
        const dd = body ? body.querySelectorAll('dl.io dd') : [];
        items.push({ el, body, num: txt(k) || pad2(items.length + 1), name, job: el.dataset.job || '', inp: txt(dd[0]), out: txt(dd[1]), more: !!(body && body.children.length) });
      } else if (el.classList.contains('layer-boundary')) { bIndex = items.length; bEl = el; }
      else if (el.classList.contains('layer-floor')) fEl = el;
    });
    const N = items.length;
    if (N < 2 || items.some((it) => !it.body || it.body.tagName !== 'DIV' || !it.name)) { root.classList.add('is-plain'); return; } // not the markup this expects: leave the list
    if (bIndex < 1 || bIndex >= N) bIndex = Math.ceil(N / 2);
    const floorTxt = fEl ? txt(fEl.querySelector('p') || fEl).replace(/^[—–-]\s*/, '') : ''; // what the stack stands on: the rails
    const lbt = bEl && bEl.querySelector('.lb-t');
    const bTitle = (lbt && lbt.firstChild && lbt.firstChild.textContent.trim()) || 'The boundary';
    // the boundary's one line (Platform): its label on the green hairline that runs on from the plane through the index
    const bLine = bEl && bEl.querySelector('.lb-line') ? txt(bEl.querySelector('.lb-line')) : '';

    /* ---------------- 2 · the instrument ---------------- */
    // inst is the instrument: the list itself (it becomes the explorer), or, in spec mode
    const inst = spec ? document.createElement('div') : root;
    if (!spec) root.classList.remove('layers');
    inst.classList.add('arch', 'is-building');
    if (spec) inst.classList.add('arch--spec');
    const head = H('div', 'arch-head');
    // the label in the caption register: the figure's mark in mono, its title in Inter, the separator for assistive tech
    const lab = H('span', 'arch-lab', head), labTxt = root.dataset.archLabel || 'The agentic stack';
    const lm = /^(Fig\.\s*\d[\d.]*?)\.?(?:\s+[—–·:-])?\s+(\S.*)$/.exec(labTxt);
    if (lm) { H('b', 'fc-n', lab, lm[1].replace(/\s+/, ' ')); H('span', 'fc-d', lab, ' · '); lab.append(lm[2]); } else lab.textContent = labTxt;
    // (hc30r, one hedge in the foot) the hedge is the instrument's foot caption (below), not the first word of its head
    const legend = H('span', 'arch-legend', head);
    legend.setAttribute('aria-hidden', 'true');
    [['lg-bead', 'Agent'], ['lg-ring', 'Proposal'], ['lg-sq', 'Settled']].forEach(([c, t]) => { const s = H('span', '', legend); H('i', c, s); s.appendChild(document.createTextNode(t)); });
    // (hc1, director item 2) the keys' hint shows only while the keyboard is in the instrument (focusin below)
    const hint = H('span', 'arch-hint', head);
    hint.hidden = true;
    const bodyEl = H('div', 'arch-body');
    const fig = H('div', 'arch-fig', bodyEl);
    fig.setAttribute('aria-hidden', 'true');
    // the ground on either side of the boundary: scattered motes above it (estimation)
    const field = H('div', 'arch-field', fig);
    H('i', 'af-up', field); H('i', 'af-dn', field);
    const svg = S('svg', { class: 'arch-svg', focusable: 'false' }, fig);
    const list = H('div', 'arch-list', bodyEl);

    const btns = [], panels = [], heads = [];
    let bRow = null, bRule = null, fRow = null;
    items.forEach((it, i) => {
      // spec mode: the entries below carry the headings
      const hd = H(spec ? 'div' : 'h3', 'arch-h', list);
      const b = H('button', 'arch-layer', hd);
      b.type = 'button'; b.id = `${pre}-b${i + 1}`;
      // (hc1, director item 2) no verb column: the layer's name says it; arch.css's grid is number, name, "+"
      H('span', 'n', b, it.num); nameInto(H('span', 'nm', b), it.name);
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
        if (!p.children.length && it.job) H('p', '', p, it.job); // a layer given only its job: the job is its panel
        list.appendChild(p);
      }
      btns.push(b); panels.push(p); heads.push(hd);
      hd.style.setProperty('--ri', i < bIndex ? i : i + 1);
      if (i === bIndex - 1) {
        // (hc6) the boundary in the index: its label, then the hairline the plane sits level with (wide)
        bRow = H('div', 'arch-bound', list);
        bRow.style.setProperty('--ri', bIndex);
        if (bLine) { bRow.classList.add('has-line'); const l = H('p', 'ab-line', bRow); H('span', 'sr-only', l, bTitle + ': '); l.append(bLine); }
        else H('span', 'chip', bRow, bTitle);
        bRule = H('span', 'ab-rule', bRow); bRule.setAttribute('aria-hidden', 'true');
      }
    });
    // the floor under 08: the rails the stack connects to
    const fParts = floorTxt.split(' · ');
    let fMid = 1;
    for (let j = 1, bd = Infinity; j < fParts.length; j++) { const d = Math.abs(fParts.slice(0, j).join(' · ').length - floorTxt.length / 2); if (d < bd) { bd = d; fMid = j; } }
    if (floorTxt) {
      fRow = H('div', 'arch-floor', list); H('span', 'gl', fRow).setAttribute('aria-hidden', 'true');
      const ft = H('span', 'ft', fRow);
      if (fParts.length > 1) { H('span', 'fa', ft, fParts.slice(0, fMid).join(' · ')); H('span', 'fs', ft, ' · '); H('span', 'fb', ft, fParts.slice(fMid).join(' · ')); }
      else ft.textContent = floorTxt;
    }

    inst.append(head, bodyEl);
    if (spec) { root.insertBefore(inst, root.firstChild); root.classList.add('is-built'); } // takes the room CSS held for it
    else {
      items.forEach((it) => it.el.remove()); if (bEl) bEl.remove(); if (fEl) fEl.remove();
      if (bEl && bEl.id && bRow) bRow.id = bEl.id; // an anchor on the boundary (Platform #boundary) lands on its row
    }
    // the hedge: a foot caption under the instrument, in the caption register (.fc-h: Illustrative), as every instrument's
    const cap = H('p', 'figure-cap arch-cap'); H('span', 'fc-h', cap, 'Illustrative');
    cap.style.setProperty('--ri', N + 2); // Platform's scene: it arrives after the last row (platform.css)
    inst.after(cap);
    // the explorer is an ink instrument: once it stands, its chapter says so (platform.css puts the chapter on ink where the
    // scene is not pinned, once site.js gives the bar that tone); without JavaScript the list stays on paper
    const sec = !spec && root.closest('section'); if (sec) sec.dataset.tone = 'dark';

    /* ---------------- 3 · the drawing ---------------- */
    // circles drawn in CSS px: above 1920 they grow with the root (RK = root / 16; measure() sets it) (award a2, 4K)
    let RK = 1;
    const pxR = [];
    const PX = (e) => { pxR.push([e, parseFloat(e.getAttribute('r'))]); return e; };
    const defs = S('defs', null, svg);
    const grad = (tag, gid, attrs, stops) => { const g = S(tag, Object.assign({ id: `${pre}-${gid}` }, attrs), defs); stops.forEach(([o, c, a]) => S('stop', { offset: o, 'stop-color': c, 'stop-opacity': a }, g)); return `url(#${pre}-${gid})`; };
    const gTop = grad('linearGradient', 'top', { x1: 0, y1: 0, x2: 1, y2: 1 }, [[0, '#2A3530', 1], [0.5, '#18211D', 1], [1, '#111815', 1]]);
    const gSide = grad('linearGradient', 'side', { x1: 0, y1: 0, x2: 0, y2: 1 }, [[0, '#0D1311', 1], [1, '#070B09', 1]]);
    const gBead = grad('radialGradient', 'bead', { cx: 0.36, cy: 0.34, r: 0.72 }, [[0, IVORY, 1], [0.55, IVORY, 0.78], [1, IVORY, 0.28]]);
    const gPlane = grad('radialGradient', 'plane', { cx: 0.5, cy: 0.5, r: 0.5 }, [[0, GREEN, 0.2], [0.7, GREEN, 0.06], [1, GREEN, 0]]);
    const gAtt = grad('radialGradient', 'att', { cx: 0.5, cy: 0.5, r: 0.5 }, [[0, GREEN, 0.42], [1, GREEN, 0]]);
    // the floor under the stack: a ground line with the hatching of a technical drawing
    const floor = floorTxt ? (() => {
      const g = S('g', { class: 'af' }, svg);
      const fl = { g, land: 0, lx: 0 };
      fl.hatch = S('path', { fill: 'none', stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1 }, g);
      fl.line = S('line', { stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1 }, g);
      fl.lead = S('line', { stroke: KHAKI, 'stroke-opacity': 0, 'stroke-width': 1, 'stroke-dasharray': '1 3' }, g);
      fl.node = PX(S('circle', { r: 1.8, fill: KHAKI, 'fill-opacity': 0 }, g));
      fl.mark = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1.6 }, g); // where a settled action lands
      fl.t1 = S('text', { class: 'af-t', 'text-anchor': 'middle' }, g);
      fl.t2 = S('text', { class: 'af-t', 'text-anchor': 'middle' }, g);
      return fl;
    })() : null;
    const gBot = S('g', { class: 'lv-bottom' }, svg);   // what falls out under the stack
    let seed = 11 + id * 7;
    const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };

    // plates, drawn lowest first so the upper ones cover them
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
    // the explosion lines of a technical drawing: dashed
    const guides = S('path', { class: 'guides', fill: 'none', stroke: IVORY, 'stroke-opacity': 0, 'stroke-width': 1, 'stroke-dasharray': '2 3' }, svg);
    svg.appendChild(gLead);
    const gFront = S('g', { class: 'lv-front' }, svg);
    // pointer targets, one per plate, held at the plates' resting places
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
      p.bg = [S('g', null, p.bead), S('g', null, p.bead), S('g', null, p.bead)]; // the beads drift in three groups
      p.num = S('text', { class: 'ap-num', 'dominant-baseline': 'middle' }, lv);
      p.num.textContent = items[p.i].num; // (hc1) the plate's number only: no verb column
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
      b.lineL = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
      b.lineR = S('line', { stroke: GREEN, 'stroke-opacity': 0, 'stroke-width': 1 }, gLead);
      b.ripT = 0; b.flash = 0; b.ru = 0; b.rv = 0;
      return b;
    }
    const leads = plates.map(() => ({
      line: S('line', { stroke: IVORY, 'stroke-width': 1, 'stroke-opacity': 0.16 }, gLead),
      a: PX(S('circle', { r: 1.6, fill: IVORY, 'fill-opacity': 0.4 }, gLead)),
      b: PX(S('circle', { r: 2, fill: GREEN, 'fill-opacity': 0 }, gLead)),
    }));

    /* each plate's surface, in its own plane coordinates (u, v in -1..1) */
    function pattern(p) {
      const g = p.pat, i = p.i, role = N === 8 ? i : (p.above ? (i === bIndex - 1 ? 3 : 2) : 5);
      const line = (d, o, c, extra) => S('path', Object.assign({ d, fill: 'none', stroke: c || IVORY, 'stroke-opacity': o, 'vector-effect': NSS }, extra || {}), g);
      const sq = (u, v, s, attrs) => S('rect', Object.assign({ x: f3(u - s), y: f3(v - s), width: f3(2 * s), height: f3(2 * s) }, attrs), g);
      const beadsAt = (n, spread, rMin, rMax, amp, h0) => {
        for (let k = 0; k < n; k++) {
          const b = { u0: (rnd() - 0.5) * 2 * spread, v0: (rnd() - 0.5) * 2 * spread, h0: h0 + rnd() * 0.05, a: amp * (0.6 + rnd() * 0.8), w1: 2.4 + rnd() * 3.2, w2: 2 + rnd() * 3.6, p1: rnd() * 6.28, p2: rnd() * 6.28 };
          b.el = PX(S('circle', { r: f1(rMin + rnd() * (rMax - rMin)), fill: gBead, 'fill-opacity': f3(0.55 + rnd() * 0.45) }, p.bg[p.beads.length % 3]));
          p.beads.push(b);
        }
      };
      if (role === 0) { // Signal Intelligence: a sensing field; motes drift in from the edge and are absorbed
        [0.3, 0.6, 0.9].forEach((r, k) => S('circle', { r, fill: 'none', stroke: IVORY, 'stroke-opacity': 0.09 + k * 0.03, 'vector-effect': NSS, 'stroke-dasharray': k === 2 ? '2 5' : null }, g));
        line('M-1 0H-.82M.82 0H1M0 -1V-.82M0 .82V1', 0.35);
        S('circle', { r: 0.05, fill: GREEN, 'fill-opacity': 0.8 }, g);
        for (let k = 0; k < 20; k++) {
          const b = { mote: true, a: rnd() * 6.283, sp: 0.16 + rnd() * 0.18, ph: rnd(), h0: 0.03 };
          b.el = PX(S('circle', { r: f1(1 + rnd() * 0.8), fill: IVORY, 'fill-opacity': 0 }, p.bg[p.beads.length % 3]));
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
          b.el = PX(S('circle', { r: 3.2, fill: 'none', stroke: GREEN, 'stroke-width': 1.2, 'stroke-opacity': 0.9 }, p.bg[p.beads.length % 3]));
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
          b.el = PX(S('circle', { r: 2.8, fill: 'none', stroke: GREEN, 'stroke-width': 1.1, 'stroke-opacity': 0.75 }, p.bg[p.beads.length % 3]));
          p.beads.push(b);
        }
      } else if (role === 4) { // Routing Layer: Manhattan routes from the hub to the rails; the scored best path in green
        line('M-.75 -1V1M-.5 -1V1M-.25 -1V1M0 -1V1M.25 -1V1M.5 -1V1M.75 -1V1M-1 -.75H1M-1 -.5H1M-1 -.25H1M-1 0H1M-1 .25H1M-1 .5H1M-1 .75H1', 0.05);
        line('M0 0H-.5V-1M0 0V-.5H-1M0 0V.5H-1M0 0H.75V-1', 0.32, KHAKI);
        line('M0 0H.25V-.5H.5V-1', 0.95, GREEN, { 'stroke-width': 1.4 });
        // the nodes; on the scored path, green outlines
        [[0, 0], [-0.5, 0], [0, -0.5], [0, 0.5], [0.75, 0], [0.25, 0], [0.25, -0.5], [0.5, -0.5]].forEach(([u, v], k) => sq(u, v, 0.045, k > 4 || k === 0 ? { fill: GREEN, 'fill-opacity': 0.12, stroke: GREEN, 'stroke-opacity': 0.95, 'vector-effect': NSS } : { fill: KHAKI, 'fill-opacity': 0.6 }));
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
    let wide = false, tags = false, W = 1, Hh = 1, cx = 0, halfW = 150, Sc = 1, F0 = 19 * DEG, thick = 7, figH = 0, minH = 0, tagH = 24, stag = false;
    let base = new Array(N).fill(0), rowC = new Array(N).fill(0), by = 0, fy = 0, padL = 0, listL = 0, listR = 0, roomyP = false;
    // (hc6) where the plates rest (baseT, byT: level with their rows and the boundary's hairline); a row opened or closed
    // moves the rows under it, and the plates follow on springs (bOff, byOff carry them from where they were)
    let baseT = new Array(N).fill(0), byT = 0, glideTo = 0, dpr = 1, lineW = 1;
    const snapTo = (v) => (Math.round(v * dpr - lineW / 2) + lineW / 2) / dpr; // a line's centre on a device row (its width odd) or edge (even)
    const bOff = items.map(() => ({ x: 0, v: 0 })), byOff = { x: 0, v: 0 };
    const view = { T: 45 * DEG, F: 19 * DEG, tT: 45 * DEG, tF: 19 * DEG };
    let geoDirty = true;
    const proj = (u, v, h) => {
      const c = Math.cos(view.T), s = Math.sin(view.T), sf = Math.sin(view.F), cp = Math.cos(view.F);
      const x = Sc * (u * c - v * s), y = -Sc * ((u * s + v * c) * sf + h * cp);
      if (!sm) return [x, y];
      const k = halfW / 115;
      return [x + sm * (k * (69 * u - 46 * v) - x), y + sm * (-k * 8.5 * (u + v) - Sc * h * cp - y)];
    };
    const pts = (arr) => arr.map((q) => f1(q[0]) + ',' + f1(q[1])).join(' ');
    const dn = (q, t) => [q[0], q[1] + t];
    function shape() {
      const c = Math.cos(view.T), s = Math.sin(view.T), sf = Math.sin(view.F), ek = halfW / 115, mx = (o, e) => o + sm * (e - o);
      const m = `matrix(${f3(mx(Sc * c, 69 * ek))} ${f3(mx(-Sc * s * sf, -8.5 * ek))} ${f3(mx(-Sc * s, -46 * ek))} ${f3(mx(-Sc * c * sf, -8.5 * ek))} 0 0)`;
      const A = proj(-1, 1, 0), B = proj(1, 1, 0), C = proj(1, -1, 0), D = proj(-1, -1, 0), th = thick * (1 - sm);
      plates.forEach((p) => {
        setA(p.top, 'points', pts([A, B, C, D])); setA(p.glow, 'points', pts([A, B, C, D]));
        setA(p.sideL, 'points', pts([A, D, dn(D, th), dn(A, th)]));
        setA(p.sideR, 'points', pts([D, C, dn(C, th), dn(D, th)]));
        setA(p.edgeB, 'points', pts([dn(A, th), dn(D, th), dn(C, th)]));
        setA(p.far, 'points', pts([A, B, C]));
        setA(p.rim, 'points', pts([A, D, C]));
        setA(p.key, 'x1', f1(A[0])); setA(p.key, 'y1', f1(A[1])); setA(p.key, 'x2', f1(B[0])); setA(p.key, 'y2', f1(B[1]));
        setA(p.hit, 'points', pts([A, B, C, dn(C, th), dn(D, th), dn(A, th)]));
        setA(p.pat, 'transform', m);
      });
      const k = 1.16, bp = pts([proj(-k, k, 0), proj(k, k, 0), proj(k, -k, 0), proj(-k, -k, 0)]);
      [bound.fill, bound.glow1, bound.glow2, bound.core].forEach((e) => setA(e, 'points', bp));
      setA(bound.pat, 'transform', m);
      beadsDirty = true; // a new projection: every bead is placed again
    }
    function measure() {
      // above 1920 the page grows with the window (root = 100vw / 120): the drawing's px caps and radii grow with it (a1, a2: 4K)
      const k = Math.max(1, (parseFloat(getComputedStyle(document.documentElement).fontSize) || 16) / 16);
      if (k !== RK) { RK = k; pxR.forEach(([e, r]) => setA(e, 'r', f1(r * k))); }
      let fr = fig.getBoundingClientRect();
      W = Math.max(1, fr.width);
      const prevB = base.slice(), prevBy = by, keep = !reduced && performance.now() < glideTo; // every measure inside the window
      if (wide) {
        // (hc6) the stack in the middle of the room left of the index (widths first: the room held below depends on them)
        const lr = list.getBoundingClientRect();
        padL = parseFloat(getComputedStyle(bodyEl).paddingLeft) || 0;
        listL = lr.left - fr.left; listR = lr.right - fr.left;
        cx = (padL + listL) / 2; halfW = clamp((listL - padL) / 2 - 56 * k, 96 * k, 178 * k);
        if (scn) { sceneRead(); if (pin) halfW = Math.max(96 * k, Math.min((listL - padL) / 2 - 56 * k, (btns[1].getBoundingClientRect().top - btns[0].getBoundingClientRect().top) * 230 / 74)); }
        F0 = 19 * DEG; thick = 7 * k;
        reserve(halfW * Math.sin(F0) + thick + 25 * k); // may grow the instrument, so the rest is measured after it
        fr = fig.getBoundingClientRect();
        Hh = Math.max(1, fr.height);
        rowC = btns.map((b) => { const r = b.getBoundingClientRect(); return r.top - fr.top + r.height / 2; });
        const br = bRule.getBoundingClientRect(); byT = br.top - fr.top + br.height / 2; // the plane, level with the hairline
        if (fRow) { const r = fRow.getBoundingClientRect(); fy = r.top - fr.top + r.height / 2; } // level with its label
        baseT = rowC.slice();
      } else {
        reserve();
        halfW = clamp(W * (W < 560 ? 0.29 : 0.27), 84, 196); cx = W * (W < 560 ? 0.39 : 0.38);
        F0 = (W < 560 ? 22 : 18) * DEG; thick = W < 560 ? 6 : 7;
        const k = W < 560 ? 0.92 : 0.86, flH = floor ? 22 + fitFloor() * 14 : 10;
        // a phone on its side: the whole stack fits under the bar (v2x r2)
        const room = shortMQ.matches ? window.innerHeight - navH() - 24 : 0, g = room ? 1.75 : 1.5;
        if (room) halfW = Math.min(halfW, Math.max(56, (room - 20 - thick - flH - 10) / (2 + (N - 2 + 2 * g) * k) / Math.sin(F0)));
        // the plates' numbers right of the stack: mono, measured (one read per measure): Plex Mono advances .6em, plus the
        // tracking (11 px label at .12em: 7.9 px a character; Home's phones set 12 px) (integrate a1, home's request). (hc1) The
        // plane carries no words beside it on either page (the boundary row under the drawing says it), so no room is held for them
        const tcs = svg.querySelector('text') && getComputedStyle(svg.querySelector('text')), tfs = tcs ? parseFloat(tcs.fontSize) || 11 : 11;
        const tls = tcs ? parseFloat(tcs.letterSpacing) : NaN, cw = 1.015 * (tfs * 0.6 + (isFinite(tls) ? tls : tfs * 0.12));
        const wl = (s) => (s.length + 2) * cw, roomB = () => W - 8 - (cx + 1.16 * halfW + 12);
        roomyP = W - 8 - (cx + halfW + 12) >= Math.max(...plates.map((p) => wl(p.num.textContent) - 14));
        const hh = halfW * Math.sin(F0), pitch = Math.max(room ? 14 : 30, hh * k);
        // short windows: the tags take both sides of the stack (odd layers left), each 24 px tall at twice the pitch (r4 a11y),
        // and the boundary keeps 36 px each side, so a focused tag's ring clears its two labels
        stag = tags && pitch < 24; list.classList.toggle('is-stag', stag);
        const gap = Math.max(pitch * g, stag ? 36 : 0), top = (room ? 20 : 30) + hh;
        if (stag) { // room for the left tags: the stack moves right while its right side still fits, else numbers only
          const lo = (t) => halfW + 26 + t.length * cw, lft = Math.max(...plates.map((p) => lo(p.num.textContent)));
          if (roomyP && cx < lft && W - 8 - (lft + halfW + 12) >= lft - halfW - 26 && roomB() + cx - lft >= 0) cx = lft;
          if (cx < lft) roomyP = false;
          cx = Math.max(cx, lo('01'));
        }
        const th = stag ? 24 : Math.min(24, Math.floor(pitch));
        if (th !== tagH) { tagH = th; list.style.setProperty('--tag-h', th + 'px'); }
        baseT = []; for (let i = 0; i < N; i++) baseT.push(top + i * pitch + (i >= bIndex ? 2 * gap - pitch : 0));
        byT = top + (bIndex - 1) * pitch + gap;
        let bottom = baseT[N - 1] + hh + thick;
        if (floor) { fy = bottom + 12; bottom = fy + flH - 12; } else bottom += 10; // the floor and its label, under 08
        const need = Math.ceil(bottom + (room ? 10 : 24));
        if (need !== figH) { figH = need; inst.style.setProperty('--fig-h', figH + 'px'); }
        Hh = figH; rowC = baseT.slice();
      }
      // a re-measure after a row opened or closed: the plates glide to their new places; after any other, they are there
      bOff.forEach((o, i) => { o.x = keep ? prevB[i] - baseT[i] : 0; if (!keep) o.v = 0; base[i] = baseT[i] + o.x; });
      byOff.x = keep ? prevBy - byT : 0; if (!keep) byOff.v = 0; by = byT + byOff.x;
      Sc = halfW / Math.SQRT2;
      view.tF = F0; if (!pointerOn) view.F = F0;
      setA(svg, 'viewBox', `0 0 ${f1(W)} ${f1(Hh)}`);
      if (scn) scenePlace();
      field.style.setProperty('--seam', f1(byT) + 'px'); field.style.setProperty('--cx', f1(cx) + 'px');
      // the boundary's line is as heavy as the index's hairline (site.css --stroke: 1, 1.5 or 2 px), on whole device rows;
      // wide, the index's hairline itself reaches left to the plane's corner (--ab-reach), so the two are one line
      const sw = parseFloat(getComputedStyle(inst).getPropertyValue('--stroke')) || 1;
      dpr = window.devicePixelRatio || 1; lineW = Math.max(1, Math.round(sw * dpr));
      setA(bound.lineL, 'stroke-width', f2(lineW / dpr)); setA(bound.lineR, 'stroke-width', f2(lineW / dpr));
      if (wide) bRow.style.setProperty('--ab-reach', f1(Math.max(0, listL - cx - 1.16 * halfW - 8 * k)) + 'px'); else bRow.style.removeProperty('--ab-reach');
      geoDirty = true;
    }
    // the floor's label under the drawing (narrow): one line if it fits, else two
    let fLines = 0;
    function fitFloor() {
      floor.t1.textContent = floorTxt; floor.t2.textContent = '';
      floor.w1 = floor.t1.getComputedTextLength(); floor.w2 = 0;
      if (floor.w1 <= W - 28 || fParts.length < 2) return (fLines = 1);
      floor.t1.textContent = fParts.slice(0, fMid).join(' · '); floor.t2.textContent = fParts.slice(fMid).join(' · ');
      floor.w1 = floor.t1.getComputedTextLength(); floor.w2 = floor.t2.getComputedTextLength();
      return (fLines = 2);
    }

    const EY = [30, 62, 94, 126, 192, 224, 256, 288], sstep = (x) => x * x * (3 - 2 * x);
    // (hc27) the ink's edge rises from the stage's foot at .45, holds .04 level with the boundary plane, then rises on (.2
    // of moving time, each leg eased); each row draws in as the edge reaches it, the head rises once the edge is past it,
    // and the camera turns once the edge has cleared the stack. platform.css reads --st-bw (the plane's height in the
    // section, from its foot), --st-h0 (the head's start) and each row's --r0, written here once per layout
    const IA = 0.45, IM = 0.2, IP = 0.04, RD = 0.04, CT = 0.2;
    let bw = 0.46, ct0 = 0.66, R0 = null;
    const iss = (s) => 0.5 - Math.sin(Math.asin(clamp(1 - 2 * s, -1, 1)) / 3); // smoothstep's inverse
    const inkAt = (w) => (w <= bw ? IA + IM * bw * iss(w / bw) : IA + IM * bw + IP + IM * (1 - bw) * iss((w - bw) / (1 - bw)));
    const rowOn = (r) => (pin ? clamp((sp - (R0 ? R0[r] : 0.5 + r * 0.012)) / RD, 0, 1) : 1);
    const smOf = (p) => (pin ? 1 - sstep(clamp((p - ct0) / CT, 0, 1)) : 0);
    function sceneRead() {
      pin = !!(stage && getComputedStyle(stage).position === 'sticky');
      if (pin) { const r = scn.getBoundingClientRect(); sA = r.top + window.scrollY; sZ = sA + scn.offsetHeight - document.documentElement.clientHeight; }
      sp = sceneP(); sm = smOf(sp);
    }
    function sceneP() { return pin ? clamp((window.scrollY - sA) / Math.max(1, sZ - sA), 0, 1) : 1; }
    const ST = ['--st-s', '--st-x', '--st-y', '--st-au', '--st-gu', '--st-ad', '--st-gd', '--st-upx'], ST2 = ['--st-bw', '--st-h0'];
    function scenePlace() {
      sceneRead();
      let e = hp, ox = 0, oy = 0;
      while (e && e !== stage) { ox += e.offsetLeft; oy += e.offsetTop; e = e.offsetParent; }
      if (!pin || !wide || !hsvg || N !== 8 || e !== stage) { ST.concat(ST2).forEach((k) => scn.style.removeProperty(k)); R0 = null; return; }
      if (exStart < 0) { exStart = performance.now(); ex = 1; started = true; }
      const s0 = parseFloat(getComputedStyle(hp).scale) || 1, st = stage.getBoundingClientRect(), fr0 = hp.getBoundingClientRect(), sr = hsvg.getBoundingClientRect(), fa = fig.getBoundingClientRect();
      const u = sr.width / s0 / (hsvg.viewBox.baseVal.width || 420);
      if (!(u > 0)) return;
      const S = (2 * halfW) / (230 * u), X = fa.left + cx, Y = fa.top + byT, su = S * u;
      const dy = EY.map((y, i) => (fa.top + baseT[i] - Y) / su - (y - 159));
      const au = (dy[3] - dy[0]) / 3, ad = (dy[7] - dy[4]) / 3;
      const v = [S, X - st.left - ox - S * ((sr.left - fr0.left) / s0 + 149 * u), Y - st.top - oy - S * ((sr.top - fr0.top) / s0 + 159 * u), au, dy[3] + au, ad, dy[4] - ad, u];
      ST.forEach((k, i) => scn.style.setProperty(k, f3(v[i])));
      const sc = sect.getBoundingClientRect(), Hs = Math.max(1, sc.height), wAt = (y) => clamp(1 - (y - sc.top) / Hs, 0, 1);
      const mid = (el) => { const r = el.getBoundingClientRect(); return (r.top + r.bottom) / 2; }, chH = sect.querySelector('.ch-head');
      const dp = window.devicePixelRatio || 1; bw = clamp(wAt(Math.round((Y - 0.5) * dp) / dp), 0.2, 0.8); R0 = []; // the edge's hairline on the device row under the plane's line
      heads.forEach((hd, i) => { const r = i < bIndex ? i : i + 1; R0[r] = inkAt(wAt(mid(hd))); hd.style.setProperty('--r0', f3(R0[r])); });
      R0[bIndex] = IA + IM * bw; bRow.style.setProperty('--r0', f3(R0[bIndex])); // the boundary draws while the edge holds on it
      head.style.setProperty('--r0', f3(inkAt(wAt(mid(head)))));
      scn.style.setProperty('--st-bw', bw.toFixed(5)); scn.style.setProperty('--st-h0', f3(chH ? inkAt(wAt(chH.getBoundingClientRect().bottom)) : 0.62));
      ct0 = Math.max(0.6, inkAt(wAt(fa.top + baseT[0] - halfW * Math.sin(F0) - 4)) + 0.01); // the stack's top, in the explorer's own camera
      const m = smOf(sp); if (m !== sm) { sm = m; geoDirty = true; }
    }

    /* ---------------- 5 · state ---------------- */
    let hover = -1, focus = -1, open = -1, hot = -2, kbd = false, hoverTimer = 0, pointerOn = false;
    let reduced = reduceMQ.matches, paused = false, visible = false, started = false, exStart = -1, ex = 0, t = 0;
    // (award a1, a1-dev) the first measure waits until the instrument is within a screen of the window: an arrival (and its
    // view transition) lays out no explorer it cannot see, and a chapter skipped by content-visibility stays skipped
    let near = false;
    let moved = false;
    const shown = () => visible && (!pin || sp > 0.44);
    let beadsDirty = true, pointerIn = false, focusIn = false, lastActive = performance.now(), wasBusy = true; // for the idle stop
    let restAcc = 1, lastF = 0; // frames owed at the rest rate: 20 a second with nobody at the instrument, 30 with someone
    let prerolled = false; // the flow, run ahead once when the stack opens
    // at rest the plates hold still (the beads, the flow and the Council's pulse carry the motion)
    const plateY = (i) => by + (base[i] - by) * exOf(i) + plates[i].off.x;
    const exOf = (i) => {
      if (ex >= 1) return 1;
      const d = Math.abs(i - (bIndex - 0.5)) * 0.06; // the stack opens from the boundary outward
      return ease3(clamp((ex * 1.5 - d) / 1, 0, 1));
    };
    /* (hc6) wide, the instrument is its content: the index (a layer opens under its row, like an accordion, and the plates
       under it glide down with their rows) and the last plate, which hangs under its row's centre (hang); --arch-minh holds
       it before the build. Pointing never changes its height */
    function reserve(hang) {
      if (!wide) { if (minH) { minH = 0; inst.style.removeProperty('--arch-cardh'); } return; }
      const lb = btns[N - 1].getBoundingClientRect();
      const need = Math.ceil(lb.top + lb.height / 2 - bodyEl.getBoundingClientRect().top + (hang || 0));
      if (Math.abs(need - minH) > 1) { minH = need; inst.style.setProperty('--arch-cardh', need + 'px'); }
    }
    let hotQ = 0; // a blur followed at once by a focus (arrow keys, Tab) must not drop the plate's light for a frame in between
    function setHot(deferred) {
      if (deferred) { if (!hotQ) hotQ = requestAnimationFrame(() => { hotQ = 0; setHot(); }); return; }
      const h = hover >= 0 ? hover : focus >= 0 ? focus : open;
      if (h === hot) return;
      hot = h;
      inst.classList.toggle('has-hot', hot >= 0 && wide);
      btns.forEach((b, i) => b.classList.toggle('is-hot', i === hot));
      plates.forEach((p, i) => setA(p.num, 'class', 'ap-num' + (i === hot ? ' is-hot' : '')));
      kick();
    }
    function placePanels() {
      if (spec) return; // the spec's entries stay where they are
      panels.forEach((p, i) => { if (p.previousElementSibling !== heads[i]) heads[i].after(p); }); // under its row, at every width
    }
    function setOpen(i) {
      if (open >= 0) { btns[open].setAttribute('aria-expanded', 'false'); panels[open].hidden = true; }
      open = i;
      if (open >= 0) { btns[open].setAttribute('aria-expanded', 'true'); panels[open].hidden = false; }
      inst.classList.toggle('has-open', open >= 0);
      placePanels();
      hot = -2; setHot();
      glideTo = performance.now() + 450; // the rows under it move: the plates follow (re-measured next frame, and on the list's resize)
      remeasure();
      kick();
      // (hc27) pinned, the stage grows under a still page (platform.css: no scroll anchoring in the scene), so the row
      // stays under the pointer; only a panel that ends below the window brings itself into view
      if (pin && wide && open >= 0) requestAnimationFrame(() => { const o = open >= 0 ? panels[open].getBoundingClientRect().bottom - window.innerHeight + 12 : 0; if (o > 0) window.scrollBy({ top: o, behavior: 'smooth' }); });
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
    function setMode(w, defer) {
      wide = w;
      inst.classList.toggle('is-wide', wide); inst.classList.toggle('is-narrow', !wide);
      // spec, narrow: the list under the drawing is not shown, so the plates' labels become the layer buttons (keyboard
      // and pointer: Tab to a layer, Up/Down to move, Enter to its entry), placed over the drawing by render()
      tags = spec && !wide;
      list.classList.toggle('is-tags', tags);
      if (!tags) heads.forEach((hd) => { setS(hd, 'transform', ''); setS(hd, 'opacity', ''); });
      inst.style.removeProperty('--arch-cardh'); minH = 0;
      placePanels();
      // one sentence in Inter (award a2, ux): the keys stay in it, as the way in without a pointer
      hint.textContent = wide && fineMQ.matches ? 'Choose a layer, or use ↑ ↓ and Enter' : spec ? (fineMQ.matches ? 'Click a plate for its spec' : 'Tap a plate for its spec')
        : fineMQ.matches ? 'Click a layer to open it' : 'Tap a layer to open it';
      hot = -2; setHot();
      if (!near) return; // measured when it comes near (below)
      if (defer) requestAnimationFrame(() => { measure(); kick(true); }); // the build reads no layout: geometry in its first frame
      else { measure(); kick(true); }
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
      if (kbd) { // the pointer takes over from the keyboard: hover what it is on now
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
    // what keeps it awake: a pointer or focus in it
    const wake = () => { lastActive = performance.now(); kick(); };
    inst.addEventListener('pointerenter', () => { pointerIn = true; wake(); });
    inst.addEventListener('pointerleave', () => { pointerIn = false; lastActive = performance.now(); });
    // (hc1) the keys' hint: shown while the keyboard is in the instrument (a focus the browser rings), gone with it
    const kbdFocus = (el) => { try { return el.matches(':focus-visible'); } catch (_) { return true; } };
    inst.addEventListener('focusin', (e) => { focusIn = true; hint.hidden = !kbdFocus(e.target); wake(); });
    inst.addEventListener('focusout', (e) => { if (!inst.contains(e.relatedTarget)) { focusIn = false; hint.hidden = true; lastActive = performance.now(); } });
    // hc31r: the explorer obeys the run. The header's pause and a halt hold its ambient motion; it has no Pause of its own
    // (OXA.run fires oxa:run once when it is ready and after every change of state)
    const obey = () => {
      const run = window.OXA && window.OXA.run;
      if (!run) return;
      const R = run.sample(), p = R.paused || R.halted;
      if (p === paused) return;
      paused = p; inst.classList.toggle('is-paused', paused); kick();
    };
    document.addEventListener('oxa:run', obey);

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
      f.halo = S('circle', { r: f1(8 * RK), fill: IVORY, 'fill-opacity': 0.1 }, g);
      f.dot = S('circle', { r: f1(1.9 * RK), fill: IVORY }, g);
      // one mark for the proposal and what it becomes
      f.mk = S('rect', { fill: GREEN, 'fill-opacity': 0, stroke: GREEN, 'stroke-width': 1.4, display: 'none' }, g);
      // registration ticks: they close on the mark as it settles
      f.reg = S('path', { d: 'M-5.5 -2.5V-5.5H-2.5M2.5 -5.5H5.5V-2.5M5.5 2.5V5.5H2.5M-2.5 5.5H-5.5V2.5', fill: 'none', stroke: GREEN, 'stroke-width': 1, 'stroke-opacity': 0, 'vector-effect': NSS }, g);
      flows.push(f);
    }
    const stationXY = (k, u, v, h) => { const q = proj(u, v, h); return [cx + q[0], plateY(k) + q[1]]; };
    function setMark(f, m) { // m: 0 = the proposal's ring, 1 = a settled square
      const s0 = 2 * f.ringR * (1 - m) + 5.6 * m, s = s0 * RK, rx = ((s0 / 2) * (1 - m) + 0.4 * m) * RK;
      setA(f.mk, 'x', f1(-s / 2)); setA(f.mk, 'y', f1(-s / 2)); setA(f.mk, 'width', f1(s)); setA(f.mk, 'height', f1(s)); setA(f.mk, 'rx', f1(rx));
      setA(f.mk, 'fill-opacity', f3(m)); setA(f.mk, 'stroke-opacity', f3(1 - m));
    }
    function setKind(f, kind) {
      f.kind = kind;
      setA(f.dot, 'display', kind === 'signal' || kind === 'reject' ? 'inline' : 'none');
      setA(f.dot, 'fill', kind === 'reject' ? RED : IVORY); setA(f.dot, 'r', f1((kind === 'reject' ? 2.6 : 1.9) * RK));
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
          if (f.kind === 'reject') { const q = clamp((p - 0.45) / 0.55, 0, 1); x += f.side * 26 * RK * q; y += 30 * RK * q * q; a = 1 - q; toLevel(f, 'front'); }
        } else if (seg.type === 'move') {
          const sa = f.st[seg.from], sb = f.st[seg.to];
          const A = stationXY(seg.from, sa.u, sa.v, 0.03), B = stationXY(seg.to, sb.u, sb.v, 0.03);
          let e;
          if (seg.to <= council) { // estimation: a curved path, eased
            e = inout(p); x = A[0] + (B[0] - A[0]) * e + Math.sin(Math.PI * p) * 12 * RK * f.side; y = A[1] + (B[1] - A[1]) * e;
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
          setA(f.reg, 'transform', `scale(${f3(k * RK)})`);
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
    }
    function decide(f) {
      f.decided = true; pulse = 1;
      if (f.reject) { setKind(f, 'reject'); f.segs.length = f.s + 1; } // its way ends here: it falls away
      else { f.ringR = 4.2; setA(f.mk, 'stroke-width', '1.6'); setMark(f, 0); } // approved: the ring brightens and goes on (1.6: arch.css's --stroke-2, whole device px; a4)
    }

    /* ---------------- 8 · the frame ---------------- */
    let raf = 0, last = 0;
    function targets() {
      plates.forEach((p, i) => {
        p.tOff = (hot < 0 ? 0 : i === hot ? -14 : i < hot ? -9 : 9) * RK;
        p.tHeat = i === hot ? 1 : 0;
        // only the plate right above overlaps the lifted one (not across the boundary's gap)
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
      // (hc6) the plates' glide to rows that moved
      bOff.forEach((o, i) => { if (snap) { o.x = 0; o.v = 0; } else if (dt > 0) spring(o, 0, dt, 15); if (!still(o, 0)) busy = true; base[i] = baseT[i] + o.x; });
      if (snap) { byOff.x = 0; byOff.v = 0; } else if (dt > 0) spring(byOff, 0, dt, 15);
      if (!still(byOff, 0)) busy = true;
      by = byT + byOff.x;
      if (exStart >= 0 && ex < 1) { ex = reduced ? 1 : clamp((performance.now() - exStart) / 1300, 0, 1); if (ex < 1) busy = true; }
      if (ex >= 1 && !inst.classList.contains('is-ready')) inst.classList.add('is-ready'); // the stack is open (a hook for tests)
      return busy;
    }
    function placeBeads(p, tt) { // each bead where its own motion has it at time tt
      p.beads.forEach((b) => {
        let u, v, hh;
        if (b.mote) {
          const ph = (tt * b.sp + b.ph) % 1, r = 0.95 - ph * 0.86;
          u = Math.cos(b.a) * r; v = Math.sin(b.a) * r; hh = b.h0;
          setA(b.el, 'fill-opacity', f3(Math.min(1, ph * 5, (1 - ph) * 3) * 0.75));
        } else {
          u = b.u0 + b.a * Math.sin(b.w1 * tt + b.p1); v = b.v0 + b.a * Math.cos(b.w2 * tt + b.p2); hh = b.h0 + 0.015 * Math.sin(b.w1 * 0.6 * tt + b.p2);
        }
        const q = proj(u, v, hh);
        setA(b.el, 'cx', f1(q[0])); setA(b.el, 'cy', f1(q[1]));
      });
    }
    function render() {
      if (geoDirty) { shape(); geoDirty = false; }
      const engaged = pointerIn || focusIn; // someone at the instrument
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
        // beads: estimation above the boundary.
        if (p.beads.length) {
          const own = i === hot && !reduced && !paused, sway = !own && engaged && !reduced && !paused;
          if (own || beadsDirty) placeBeads(p, t);
          p.bg.forEach((bg, k) => setA(bg, 'transform', !sway ? 'translate(0 0)'
            : `translate(${f1(Sc * 0.022 * Math.sin(t * (0.9 + 0.35 * k) + k * 2.1 + i))} ${f1(Sc * 0.014 * Math.cos(t * (0.75 + 0.3 * k) + k * 1.3 + i))})`));
        }
        if (p.att && (engaged || i === hot)) { setA(p.att, 'cx', f3(0.42 * Math.sin(t * 0.31 + 0.4))); setA(p.att, 'cy', f3(0.38 * Math.sin(t * 0.23 + 1.3))); }
        if (p.ticks) { setA(p.ticks, 'stroke-opacity', f3(0.5 + 0.45 * pulse)); setA(p.pulse, 'r', f3(0.5 + 0.28 * (1 - pulse))); setA(p.pulse, 'stroke-opacity', f3(0.75 * pulse)); }
        // 06's state machine and 07's ports light as green outlines over a faint tint
        if (p.cells) p.cells.forEach((c) => { const on = (step + c.r * 2) % 5, lit = c.c === on; setA(c.el, 'fill-opacity', lit ? '0.12' : c.c < on ? '0.06' : '0'); setA(c.el, 'stroke', lit ? GREEN : KHAKI); setA(c.el, 'stroke-opacity', lit ? '0.95' : '0.5'); });
        if (p.ports) p.ports.forEach((e, k) => { const lit = step % 3 === k; setA(e, 'fill-opacity', lit ? '0.12' : '0'); setA(e, 'stroke', lit ? GREEN : KHAKI); setA(e, 'stroke-opacity', lit ? '0.95' : '0.7'); });
        if (p.permit) setA(p.permit, 'fill-opacity', f3(0.3 + 0.65 * permit));
        // labels (narrow): numbers beside the plates
        const xr = cx + C[0] + 12;
        setA(p.num, 'x', f1(xr)); setA(p.num, 'y', f1(y + C[1]));
        p.lx = xr; p.ly = y + C[1];
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
      // the line runs the width of the instrument; wide, right of the plane it is the index's hairline (hc6), drawn at once
      // like the plane and the label on it: the line left of the plane comes in as the stack starts to open
      const x0 = wide ? padL : 14, x1 = W - 14, bl = clamp((ex - 0.1) / 0.35, 0, 1), ly = f2(snapTo(by));
      setA(bound.lineL, 'x1', f1(x0)); setA(bound.lineL, 'x2', f1(cx + BL[0] - 8)); setA(bound.lineL, 'y1', ly); setA(bound.lineL, 'y2', ly);
      setA(bound.lineR, 'x1', f1(cx + BR[0] + 8)); setA(bound.lineR, 'x2', f1(x1)); setA(bound.lineR, 'y1', ly); setA(bound.lineR, 'y2', ly);
      setA(bound.lineL, 'stroke-opacity', f3(0.5 * bl * rowOn(bIndex))); setA(bound.lineR, 'stroke-opacity', wide ? '0' : f3(0.5 * bl));
      if (!wide) {
        // the boundary says it once, on its row under the drawing (hc1, both pages): beside the plane, the plane alone
        plates.forEach((p, i) => setA(p.num, 'opacity', f3(clamp((exOf(i) - 0.8) / 0.2, 0, 1))));
        if (tags) { // the labels are the layer buttons: each sits where its plate's label is drawn, and shows as it does
          list.classList.toggle('is-short', !roomyP);
          plates.forEach((p, i) => {
            setS(heads[i], 'transform', stag && !(i % 2) ? `translate(calc(${f1(cx + A[0] - 6)}px - 100%), ${f1(p.ly - C[1] + A[1] - tagH / 2)}px)` : `translate(${f1(p.lx - 6)}px, ${f1(p.ly - tagH / 2)}px)`);
            setS(heads[i], 'opacity', f3(focus === i ? 1 : clamp((exOf(i) - 0.8) / 0.2, 0, 1)));
          });
        }
      }
      // the floor: a ground line under the stack, hatched beneath it as in a technical drawing
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
        setA(floor.mark, 'x1', f1(floor.lx - 9 * RK)); setA(floor.mark, 'x2', f1(floor.lx + 9 * RK)); setA(floor.mark, 'y1', f1(fy)); setA(floor.mark, 'y2', f1(fy));
        setA(floor.mark, 'stroke-opacity', f3(0.95 * floor.land));
      }
      // leader lines: plate -> its row (wide)
      plates.forEach((p, i) => {
        const L = leads[i];
        if (!wide) { setA(L.line, 'display', 'none'); setA(L.a, 'display', 'none'); setA(L.b, 'display', 'none'); return; }
        setA(L.line, 'display', 'inline'); setA(L.a, 'display', 'inline'); setA(L.b, 'display', 'inline');
        const y = plateY(i), xa = cx + C[0] + 9 * RK, ya = y + C[1], xb = listL - 4 * RK, yb = rowC[i], h = p.heat.x, on = clamp((exOf(i) - 0.82) / 0.18, 0, 1) * rowOn(i < bIndex ? i : i + 1);
        setA(L.line, 'x1', f1(xa)); setA(L.line, 'y1', f1(ya)); setA(L.line, 'x2', f1(xb)); setA(L.line, 'y2', f1(yb));
        setA(L.line, 'stroke-opacity', f3((0.15 + 0.55 * h) * (1 - 0.4 * p.fade.x) * on));
        setA(L.a, 'cx', f1(xa)); setA(L.a, 'cy', f1(ya)); setA(L.a, 'fill-opacity', f3((0.35 + 0.6 * h) * on));
        setA(L.b, 'cx', f1(xb)); setA(L.b, 'cy', f1(yb)); setA(L.b, 'fill-opacity', f3(h * on));
      });
      beadsDirty = false;
    }
    // awake: a pointer or focus in the instrument, or under 8 s since the last of them
    const awake = (now) => pointerIn || focusIn || now - lastActive < 8000;
    function frame(now) {
      raf = 0;
      // at rest (no plate pointed at, nothing settling) it is drawn at 20 Hz, or 30 with someone at it
      const df = lastF ? now - lastF : 0; lastF = now;
      if (hot < 0 && !wasBusy && !moved) {
        restAcc = Math.min(1, restAcc + df * (pointerIn || focusIn ? 0.031 : 0.021));
        if (restAcc < 1) { raf = requestAnimationFrame(frame); return; }
        restAcc -= 1;
      } else restAcc = 1;
      const dt = Math.min(0.05, Math.max(0, (now - last) / 1000)); last = now;
      const ambient = !reduced && !paused && started && awake(now);
      if (ambient) {
        t += dt;
        // the stack is already at work when it opens: the flow is run 5 s ahead, unseen
        if (ex >= 1 && !prerolled) { prerolled = true; for (let k = 0; k < 100; k++) flowStep(0.05); pulse = permit = 0; bound.flash = bound.ripT = 0; if (floor) floor.land = 0; }
        flowStep(dt);
        pulse = Math.max(0, pulse - dt / 0.3); permit = Math.max(0, permit - dt / 0.55);
        bound.flash = Math.max(0, bound.flash - dt / 0.22); bound.ripT = Math.max(0, bound.ripT - dt / 0.6);
        if (floor) floor.land = Math.max(0, floor.land - dt / 0.6);
        if ((stepT += dt) > 0.7) { stepT = 0; step++; }
      }
      const busy = animate(dt, false);
      wasBusy = busy;
      render(); moved = false;
      if ((ambient || busy) && shown() && !document.hidden) raf = requestAnimationFrame(frame);
    }
    function kick(force) {
      if (reduced || !shown() || document.hidden) { // no loop: settle to the final state and draw once
        if (raf) { cancelAnimationFrame(raf); raf = 0; }
        if (reduced && exStart >= 0) ex = 1;
        animate(0, true); render();
        return;
      }
      if (force) { animate(0, false); render(); } // a new layout: draw it now, the springs carry on in the loop
      if (!raf) { last = lastF = performance.now(); raf = requestAnimationFrame(frame); }
    }

    /* ---------------- 9 · wiring ---------------- */
    setMode(wideMQ.matches, true);
    inst.classList.remove('is-building');
    obey();
    wideMQ.addEventListener('change', (e) => setMode(e.matches));
    fineMQ.addEventListener('change', () => setMode(wideMQ.matches));
    reduceMQ.addEventListener('change', (e) => {
      reduced = e.matches;
      if (reduced) { flows.splice(0).forEach((f) => f.g.remove()); pulse = permit = 0; bound.flash = bound.ripT = 0; if (floor) floor.land = 0; ex = exStart >= 0 ? 1 : ex; }
      kick(true);
    });
    // a new size is measured in the next frame, not inside the observer; every trigger shares one queued measure
    let mQ = 0;
    const remeasure = () => { if (near && !mQ) mQ = requestAnimationFrame(() => { mQ = 0; measure(); kick(true); }); };
    const ro = new ResizeObserver(remeasure);
    ro.observe(bodyEl); ro.observe(list);
    // (award a2, a2-dev) document.fonts.ready is read only once the explorer is near: reading it while the script is
    // evaluated forced the page's first style and layout inside arch.js (~270 ms at 4x CPU on a phone)
    const nearIO = new IntersectionObserver((entries) => {
      if (near || !entries.some((e) => e.isIntersecting && (e.target === inst || getComputedStyle(stage).position === 'sticky'))) return;
      near = true; nearIO.disconnect();
      remeasure();
      if (document.fonts && document.fonts.status !== 'loaded') document.fonts.ready.then(remeasure);
    }, { rootMargin: '100% 0px' });
    nearIO.observe(inst); if (scn) nearIO.observe(scn);
    new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting && !visible) lastActive = performance.now(); // back in view: awake again
        visible = e.isIntersecting;
        // open the stack once a fair part of it is on screen
        const seen = e.intersectionRect.height >= Math.min(window.innerHeight * 0.32, e.boundingClientRect.height * 0.3);
        if (visible && seen && exStart < 0) { exStart = performance.now(); started = true; if (reduced) ex = 1; }
      });
      kick();
    }, { threshold: [0, 0.05, 0.1, 0.2, 0.3, 0.5] }).observe(inst);
    document.addEventListener('visibilitychange', () => kick());
    if (scn) {
      window.addEventListener('scroll', () => {
        if (!pin) return;
        const q = sceneP();
        if (q === sp) return;
        const was = sp > 0.44;
        sp = q;
        const m = smOf(sp);
        if (m !== sm) { sm = m; geoDirty = true; }
        if (sp > 0.44) { if (!was) lastActive = performance.now(); moved = true; kick(); } else if (was) kick();
      }, { passive: true });
      const hero = scn.querySelector('.page-hero');
      if (hero) hero.addEventListener('focusin', () => requestAnimationFrame(() => requestAnimationFrame(() => { if (pin && hero.contains(document.activeElement) && sceneP() > 0.12) window.scrollTo({ top: sA, behavior: 'instant' }); })));
    }
    // printing: every layer's detail, inline, in order
    if (!spec) {
      window.addEventListener('beforeprint', () => { panels.forEach((p) => { p.hidden = false; }); if (wide) { wide = false; inst.classList.remove('is-wide'); inst.classList.add('is-narrow'); placePanels(); } });
      window.addEventListener('afterprint', () => { panels.forEach((p, i) => { p.hidden = i !== open; }); setMode(wideMQ.matches); });
    }
  }
})();
