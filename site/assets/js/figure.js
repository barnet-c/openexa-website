/* OpenEXA — figures
   The research figures (the index's plate, each note's hero). hc30r (RETHINK-hc30 RES-1): every formation is a lattice of
   hard square marks, drawn where a plotter would put them: rows of latitude for a sphere, rings, dot grids, fused blocks.
   A mark is a whole number of device pixels, in paper white, paper white at 60 %, signal green, or red for a refusal.
   Nothing drifts: a formation stands still. What moves: on the index, the marks of one formation travel to the next when
   another note is pointed at (.62 s, --ease-move, left to right), and once they land one pass of light walks the idea's own
   path (the record in order, proposals through the Council) and names each part it passes (.fl.is-lit). A note's hero is
   its still (build_research.py draws the same lattice as SVG) and has no canvas: here its labels are set, and the same
   pass runs once (OXA.actOnce) as the still's own (.is-pass; research.css .pt). Reduced motion: the new formation at
   once, no pass.
   The lattice (F, FORMS) is ported line for line in tools/build_research.py: a change to a formation here needs the
   same change there (the still would then disagree with the plate). A hero's hedge hangs from the lattice's box in
   research.css (.fg > .figcap): no script places it.
   Labels (.fig-labels, from <template data-labels>): data-at="x,y" in the formation's cells; words stand only inside the
   page's content edge and below the bar; words without room swap sides; words never cross words or another label's
   point; a label that cannot stand whole is not shown; a hedge label (data-keep) is placed first, and if it cannot
   stand, none is. */
(function () {
  'use strict';
  const stages = Array.from(document.querySelectorAll('[data-figure]'));
  if (!stages.length) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const OXA = window.OXA = window.OXA || {};
  const PI = Math.PI, TILT = 0.36; // the spheres are seen from a little above, as Home's globe
  const Q = v => Math.floor(v * 4 + 0.5 + 1e-9) / 4, R = v => Math.floor(v + 0.5 + 1e-9);

  /* ---------------- the lattice (cells; x right, y down) ----------------
     a mark: [x, y, kind, ph, bw, bh]: its top-left cell; kind 0 paper white · 1 paper white at 60 % · 2 green · 3 red;
     ph where it lies on the formation's path (0..1, or -1); a fused block spans bw x bh cells; a rule is bw long, bh 0;
     an open unit (bw < 0) is a hairline square through the centres of the marks at its corners */
  function F(w, h) {
    const m = new Map(), key = (x, y) => (R(x * 4) + 4096) * 16384 + R(y * 4) + 4096;
    const f = {
      w, h, m,
      del(x, y) { m.delete(key(x, y)); },
      dot(x, y, k, ph) { m.set(key(x, y), [x, y, k, ph === undefined ? -1 : ph, 1, 1]); },
      blk(x, y, bw, bh, k, ph) { m.set(key(x, y), [x, y, k, ph === undefined ? -1 : ph, bw, bh]); },
      rule(x, y, n, k) { m.set(key(x, y), [x, y, k, -1, n, 0]); },
      open(x, y, bw, bh, k) { m.set(key(x, y), [x, y, k, -1, -bw, bh]); },
      run(x, y, n, dx, dy, k, p0, p1) { for (let i = 0; i < n; i++) f.dot(x + i * dx, y + i * dy, k, p1 === undefined || n < 2 ? p0 : p0 + (p1 - p0) * i / (n - 1)); },
      grid(x, y, cols, rows, dx, dy, k, ph) { for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) f.dot(x + c * dx, y + r * dy, k, ph); },
      line(x0, y0, x1, y1, step, k, p0, p1) {
        const n = Math.max(1, Math.floor(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / step));
        for (let i = 0; i <= n; i++) f.dot(R(x0 + (x1 - x0) * i / n), R(y0 + (y1 - y0) * i / n), k, p1 === undefined ? p0 : p0 + (p1 - p0) * i / n);
      },
      // a sphere as rows of latitude: a row every dy cells down the meridian, its marks s cells apart round it; the near
      // side only; no two of its marks in one half cell; none within 1.2 cells of a point of avoid (an orbit in front)
      ball(cx, cy, r, k, ph, dy, s, avoid) {
        dy = dy || 2; s = s || 2;
        const nr = R(PI * r / dy), seen = new Set(), ce = Math.cos(TILT), se = Math.sin(TILT);
        for (let i = 0; i < nr; i++) {
          const la = (i + 0.5) * PI / nr - PI / 2, rr = Math.cos(la), n = Math.max(1, R(2 * PI * r * rr / s));
          for (let j = 0; j < n; j++) {
            const lo = (j + 0.5) * 2 * PI / n, X = rr * Math.sin(lo), Y = Math.sin(la), Z = rr * Math.cos(lo);
            if (Y * se + Z * ce < 0.03) continue;
            const x = cx + r * X, y = cy - r * (Y * ce - Z * se), id = Math.floor(x * 2 + 1e-9) * 4096 + Math.floor(y * 2 + 1e-9);
            if (seen.has(id) || (avoid && avoid.some(p => Math.abs(x - p[0]) < 1.2 && Math.abs(y - p[1]) < 1.2))) continue;
            seen.add(id); f.dot(Q(x - 0.25), Q(y - 0.25), k, ph);
          }
        }
      },
      // n marks at equal steps round an ellipse turned by rot; its far half is hidden behind a ball of radius hide at its
      // centre; front collects the near half's points over that ball
      orbit(cx, cy, rx, ry, rot, n, k, p0, p1, hide, front) {
        const co = Math.cos(rot), si = Math.sin(rot);
        for (let i = 0; i < n; i++) {
          const a = 2 * PI * i / n, ex = rx * Math.cos(a), ey = ry * Math.sin(a), x = ex * co - ey * si, y = ex * si + ey * co;
          if (hide && Math.hypot(x, y) < hide) { if (Math.sin(a) < 0) continue; if (front) front.push([cx + x, cy + y]); }
          f.dot(Q(cx + x - 0.25), Q(cy + y - 0.25), k, p1 === undefined ? p0 : p0 + (p1 - p0) * i / n);
        }
      },
    };
    return f;
  }
  const FORMS = {
    // 01 · Compounding error: a monolithic run decays as p to the n; a gated run is caught at every gate and stays high
    horizon() {
      const f = F(91, 56), ys = [];
      f.run(0, 54, 46, 2, 0, 1);
      for (let c = 0; c < 92; c++) ys.push(R(52 - 46 * Math.pow(0.986, c * 160 / 90)));
      for (let c = 0; c < 91; c++) for (let y = ys[c]; y <= Math.max(ys[c] + 1, ys[c + 1] - 1); y++) f.dot(c, y, 0, c / 90);
      for (let s = 0; s < 11; s++) f.run(s * 9, 0, 13, 0, 1, 1, s / 10);
      for (let c = 0; c < 91; c++) { if (c % 9 === 0) continue; const y = 6 + R(4 * (c % 9 - 1) / 7); f.dot(c, y, 2, c / 90); f.dot(c, y + 1, 2, c / 90); }
      return f;
    },
    // 02 · One base model, rings of adapters, the record below
    weights() {
      const f = F(84, 55), cx = 42.25, cy = 22.25, fr = [];
      f.orbit(cx, cy, 31, 7, -0.42, 104, 1, 0, 0.5, 17.5, fr);
      f.orbit(cx, cy, 30, 11, 0.5, 108, 2, 0, 0.5, 17.5, fr);
      f.orbit(cx, cy, 27, 3.5, 0.05, 88, 1, 0, 0.5, 17.5, fr);
      f.ball(cx, cy, 17, 0, -1, 2, 2, fr);
      for (let b = 0; b < 5; b++) {
        const x = 12 + b * 13, p = 0.55 + b * 0.1;
        f.run(x, 45, 9, 1, 0, 2, p); f.run(x, 50, 9, 1, 0, 2, p); f.run(x, 46, 4, 0, 1, 2, p); f.run(x + 8, 46, 4, 0, 1, 2, p);
        f.run(x + 2, 47, 5, 1, 0, 2, p);
        if (b) f.run(x - 3, 48, 2, 1, 0, 2, p - 0.05);
      }
      return f;
    },
    // 03 · Not tasks, lifecycles: one loop of six gates, agents on its middle track, the last gate lit
    lifecycle() {
      const f = F(92, 56), cx = 46.25, cy = 28.25, rx = 42, ry = 24, a0 = -5 * PI / 6, gates = [];
      for (let n = 0; n < 6; n++) gates.push([R(cx + rx * 0.92 * Math.cos(a0 + n * PI / 3) - 2.25), R(cy + ry * 0.86 * Math.sin(a0 + n * PI / 3) - 2.25)]);
      for (let t = 0; t < 3; t++) {
        const n = 156 - t * 14, sx = 1 - t * 0.08, sy = 1 - t * 0.14;
        for (let i = 0; i < n; i++) {
          const a = a0 + 2 * PI * i / n, x = Q(cx + rx * sx * Math.cos(a) - 0.25), y = Q(cy + ry * sy * Math.sin(a) - 0.25);
          if (gates.some(g => g[0] - 2 < x && x < g[0] + 6 && g[1] - 2 < y && y < g[1] + 6)) continue;
          f.dot(x, y, t === 1 ? 0 : 1, Math.min(1, i / n * 6 / 5.4));
        }
      }
      gates.forEach((g, n) => { if (n === 5) f.blk(g[0], g[1], 5, 5, 2, 1); else f.grid(g[0], g[1], 5, 5, 1, 1, 0, n / 5.4); });
      return f;
    },
    // 04 · One large agent beside a lattice of small ones, each with its gate
    swarm() {
      const f = F(92, 48);
      f.ball(21.25, 23.25, 21, 1);
      for (let gy = 0; gy < 7; gy++) for (let gx = 0; gx < 7; gx++) { const x = 50 + gx * 6, y = 5 + gy * 6, p = (gx + gy) / 12; f.grid(x, y, 2, 2, 1, 1, 0, p); f.run(x + 3, y, 2, 0, 1, 2, p); }
      return f;
    },
    // 05 · Eight layers, one boundary: agents decide above the bright plane, code executes below
    boundary() {
      const f = F(70, 71);
      for (let l = 0; l < 8; l++) { const y0 = l * 8 + (l > 3 ? 9 : 0), p = (l + (l > 3 ? 1 : 0)) / 9; for (let d = 0; d < 5; d++) f.run(4 + (4 - d) * 2, y0 + d, 27, 2, 0, l < 4 ? 0 : 1, p); }
      for (let d = 0; d < 5; d++) f.run((4 - d) * 2, 33 + d, 62, 1, 0, 2, 4 / 9);
      return f;
    },
    // 06 · The rulebook moves into the weights: a dense cube with a lit core, six documents drifting in
    rulebook() {
      const f = F(88, 52);
      for (let d = 1; d < 6; d++) { f.run(35 + d, 17 - d, 19, 1, 0, 1, 0.96); f.run(53 + d, 18 - d, 18, 0, 1, 1, 0.96); }
      f.grid(35, 17, 19, 19, 1, 1, 0, 0.96);
      for (let yy = 23; yy < 30; yy++) for (let xx = 41; xx < 48; xx++) f.del(xx, yy);
      f.blk(41, 23, 7, 7, 2, 0.96);
      for (let i = 0; i < 6; i++) {
        const x = i < 3 ? 3 : 78, y = 3 + (i % 3) * 18;
        f.run(x, y, 7, 1, 0, 0, 0.08); f.run(x, y + 8, 7, 1, 0, 0, 0.08); f.run(x, y + 1, 7, 0, 1, 0, 0.08); f.run(x + 6, y + 1, 7, 0, 1, 0, 0.08);
        for (let r = 2; r < 7; r += 2) f.run(x + 2, y + r, 3, 1, 0, 0, 0.08);
        f.line(i < 3 ? x + 9 : x - 3, y + 4, i < 3 ? 32 : 61, 26 + ((i % 3) - 1) * 6, 2, 1, 0.12, 0.9);
      }
      return f;
    },
    // 07 · The council: proposals arrive from above, approved go on down to the record, rejected leave to the side
    council() {
      const f = F(82, 60), cx = 38;
      for (let r = 0; r < 8; r++) for (let j = 0; j < 8 - r; j++) f.dot(cx - (7 - r) * 2 + j * 4, r * 2, 1, r / 7 * 0.4);
      [[13, 60], [10, 46], [7, 32]].forEach(q => f.orbit(cx + 0.25, 30.25, q[0], q[0], 0, q[1], 0, 0.42));
      f.run(cx, 45, 10, 0, 1, 2, 0.46, 0.9);
      f.run(22, 56, 33, 1, 0, 2, 0.92); f.run(22, 57, 33, 1, 0, 2, 0.92);
      f.run(cx + 15, 30, 8, 2, 0, 3, 0.46, 0.9);
      f.grid(69, 29, 3, 3, 1, 1, 3, 0.9);
      return f;
    },
    // 08 · A ledger nobody can edit: eight blocks in a chain, each holding the hash of the one before
    ledger() {
      const f = F(86, 55);
      for (let b = 0; b < 8; b++) {
        const x = b * 11, y = 1 + b * 7;
        if (b === 7) f.blk(x, y, 9, 5, 2, b / 8); else f.grid(x, y, 9, 5, 1, 1, 0, b / 8);
        if (b) { f.run(x - 7, y - 1, 4, 0, 1, 2, (b - 1) / 8, (b - 0.5) / 8); f.run(x - 6, y + 2, 5, 1, 0, 2, (b - 0.5) / 8, b / 8); }
      }
      return f;
    },
    // 09 · Ten sessions, drawn as Proof draws them: ten blocks to the floor, one per basis point, and one open unit above
    // it (how far above is not published, so nothing taller is drawn); the floor and the 0 line are rules
    sessions() {
      const f = F(76, 46);
      for (let c = 0; c < 10; c++) {
        const x = c * 8;
        f.open(x, 0, 4, 4, 2);
        for (let r = 0; r < 10; r++) f.blk(x, 5 + r * 4, 4, 4, 2);
      }
      f.rule(-1, 4, 78, 0); f.rule(-1, 45, 78, 1);
      return f;
    },
    // 10 · Master and copy: one proven agent, its copies below on one bus, one control plane
    mastercopy() {
      const f = F(92, 66);
      f.ball(46.25, 11.25, 11, 2, 0.04, 1.5, 1.5);
      f.run(46, 24, 4, 0, 1, 1, 0.1, 0.2);
      f.run(10, 28, 73, 1, 0, 1, 0.2, 0.2);
      for (let c = 0; c < 5; c++) { const x = 10 + c * 18; f.run(x, 29, 4, 0, 1, 1, 0.3, 0.6); f.ball(x + 0.25, 40.25, 6, 1, 0.74, 1.5, 1.5); }
      f.run(0, 60, 92, 1, 0, 1, 0.9);
      return f;
    },
  };
  // a formation's marks in drawing order (left to right, then down), as one array of six numbers a mark. Its box is
  // trimmed to the drawing (build_research.py _F.trim, which moves the labels with it): the marks move to its top-left
  // corner by whole cells, and w, h are where the last mark ends (a mark is half a cell; a rule has no height of its own).
  // b > 1: binned b cells to one for a stage too small for the lattice (the index's 44 px strip), in each bin's strongest
  // tone: a dot or an open unit marks its own bin, a rule every bin along it, a block the bins whose centres it covers
  function make(name, b) {
    const f = FORMS[name](); let ms = Array.from(f.m.values()), w = 0, h = 0;
    const x0 = Math.floor(Math.min(...ms.map(q => q[0]))), y0 = Math.floor(Math.min(...ms.map(q => q[1])));
    ms.forEach(q => { q[0] -= x0; q[1] -= y0; w = Math.max(w, q[0] + (q[5] ? Math.abs(q[4]) - 0.5 : q[4])); h = Math.max(h, q[1] + Math.max(q[5], 1) - 0.5); });
    if (b > 1) {
      const bin = new Map(), rank = [1, 0, 2, 3], put = (x, y, k) => { const id = y * 4096 + x, o = bin.get(id); if (!o || rank[k] > rank[o[2]]) bin.set(id, [x, y, k, -1, 1, 1]); };
      ms.forEach(q => {
        const X = Math.floor(q[0] / b), Y = Math.floor(q[1] / b), bw = q[4], bh = q[5]; let any = false;
        if (!bh) for (let x = X, x1 = Math.floor((q[0] + bw - 0.5) / b); x <= x1; x++) put(x, Y, q[2]);
        else if (bw > 1) for (let y = Math.ceil(q[1] / b - 0.5); (y + 0.5) * b <= q[1] + bh - 0.5; y++) for (let x = Math.ceil(q[0] / b - 0.5); (x + 0.5) * b <= q[0] + bw - 0.5; x++) { put(x, y, q[2]); any = true; }
        if (bh && !any) put(X, Y, q[2]);
      });
      ms = Array.from(bin.values()); w = Math.ceil(w / b); h = Math.ceil(h / b);
    }
    ms.sort((p, q) => (p[0] - q[0]) || (p[1] - q[1]));
    const d = new Float32Array(ms.length * 6); ms.forEach((q, i) => d.set(q, i * 6));
    return { w, h, n: ms.length, d };
  }

  // --ease-move: cubic-bezier(.62, 0, .2, 1)
  function ease(t) {
    let v = t;
    for (let i = 0; i < 6; i++) { const q = 1 - v, x = 1.86 * q * q * v + 0.6 * q * v * v + v * v * v - t, dx = 1.86 * q * q - 2.52 * q * v + 2.4 * v * v; if (Math.abs(dx) < 1e-6) break; v = Math.min(1, Math.max(0, v - x / dx)); }
    return 3 * (1 - v) * v * v + v * v * v;
  }
  const hex = (s, f) => { const m = /^#?([0-9a-f]{6})$/i.exec((s || '').trim()), n = m ? parseInt(m[1], 16) : f; return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
  const DUR = 460, LAG = 160, PASS = 1500; // a mark's travel, the left-to-right stagger, one pass of the light (ms)

  // a stage that cannot draw says so to its page: a caption must not describe a figure that is not there (research.js)
  const none = stage => { stage.classList.add('no-figure'); stage.dispatchEvent(new CustomEvent('figure:none', { bubbles: true })); };
  function init(stage) {
    stage.querySelectorAll(':scope > template[data-labels]').forEach(t => t.replaceWith(t.content));
    const cv = stage.querySelector('canvas'), box = stage.querySelector('.fg'), still = !cv;
    let current = stage.dataset.figure, ctx = null;
    if (!box || !FORMS[current]) return;
    // a hero's box holds the note's still (the same lattice, as SVG): it is the picture, and nothing is drawn here. The
    // index's plate is drawn here, whole: its still (the first note's) stands until the first frame, then goes
    if (cv) { try { ctx = cv.getContext('2d'); } catch (e) {} if (!ctx) { none(stage); return; } }
    let first = still ? null : box.querySelector('svg');
    const cs = getComputedStyle(document.documentElement), ink = hex(cs.getPropertyValue('--ink'), 0x0E1512), paper = hex(cs.getPropertyValue('--paper'), 0xF5F2EC);
    const COL = [rgb(paper), rgb(paper.map((v, i) => Math.round(ink[i] + (v - ink[i]) * 0.6))), rgb(hex(cs.getPropertyValue('--signal-bright'), 0x4FCB93)), rgb(hex(cs.getPropertyValue('--reject-bright'), 0xD9675D))];
    let W = 1, H = 1, D = 1, u = 1, hair = 1, bin = 1, ox = 0, oy = 0, visible = true, frameId = 0;
    let A = null, B = null, t0 = 0, p0 = 0, lit = NaN; // the formation left, the one on show, when the travel and the pass began
    const built = {}, build = name => built[name + bin] || (built[name + bin] = make(name, bin));
    const groups = {}; let grp = null, grpOn = false, planned = false;
    stage.querySelectorAll('.fig-labels').forEach(el => { groups[el.dataset.for] = { el, pad: el.dataset.pad || '', items: Array.from(el.querySelectorAll('.fl')).map(l => ({ el: l, at: l.dataset.at.split(',').map(Number), side: l.dataset.side || 'r', ph: l.dataset.ph ? l.dataset.ph.split(',').map(Number) : null, to: l.dataset.to ? l.dataset.to.split(',').map(Number) : null, keep: l.hasAttribute('data-keep'), sides: (l.dataset.keep || '').split(' ').filter(Boolean), lead: 19, w: 0, h: 0, w1: 0, h1: 0, drop: 0, one: false, dropSet: 0, oneSet: false, x: NaN, y: NaN, dx: 0, out: false, lit: false })) }; });

    /* the formation's box on the stage. research.css sizes .fg from its --w and --h (cells) and its four pads (the room
       its labels take): the cell is a whole number of device px (--px: one of them, in CSS px), the mark half of it,
       rounded down. A hero's box carries them in the page; the index's plate gets them here, per formation. Returned: the
       formation's marks as device-pixel rects from the canvas's corner (ox, oy from the stage's; a hero: the stage's) */
    function fit(name) {
      let f = build(name);
      if (!still) {
        bin = 1; f = build(name);
        if (Math.min(W, H) < 120) { while (bin < 8 && Math.floor(Math.min(W / Math.ceil(f.w / bin), H / Math.ceil(f.h / bin))) < 2) bin++; f = build(name); }
        const g = groups[name], pad = bin > 1 || !g ? [] : g.pad.split(' ');
        box.style.cssText = `--w:${f.w};--h:${f.h};--pt:${pad[0] || '0rem'};--pr:${pad[1] || '0rem'};--pb:${pad[2] || '0rem'};--pl:${pad[3] || '0rem'}`;
      }
      const sb = stage.getBoundingClientRect(), bb = box.getBoundingClientRect(), px = parseFloat(getComputedStyle(box).getPropertyValue('--px')) || 1;
      const k = bb.width / f.w, gx = bb.left - sb.left, gy = bb.top - sb.top, m = Math.max(px, Math.floor(k / 2 / px + 1e-6) * px);
      // a mark falls where the still's does: the still's root stands half a mark in from the box, on whole px (a browser
      // snaps an svg root), and its origin .016 of a cell in, so no edge rests on half a pixel (build_research _still)
      // R: the near edge of a stroke t px wide whose centre line lies at cell v
      const md = Math.max(1, Math.round(m * D)), hd = Math.max(1, Math.round(hair * D)), kc = k * D;
      const X0 = Math.round((gx + ox) * D + md / 2), Y0 = Math.round((gy + oy) * D + md / 2), R = (v, t) => Math.floor((v + 0.016) * kc - t / 2 + 0.5);
      const n = f.n, x = new Int32Array(n), y = new Int32Array(n), w = new Int32Array(n), h = new Int32Array(n), kd = new Uint8Array(n), ph = new Float32Array(n), o = new Float32Array(n), ho = new Uint8Array(n);
      for (let i = 0; i < n; i++) {
        const q = i * 6, bw = f.d[q + 4], bh = f.d[q + 5];
        const X = f.d[q], Y = f.d[q + 1];
        const t = !bh || bw < 0 ? hd : md;
        x[i] = X0 + R(X, bh ? t : 0); y[i] = Y0 + R(Y, t);
        if (!bh) { w[i] = X0 + R(X + bw, 0) - x[i]; h[i] = hd; }
        else { w[i] = X0 + R(X + Math.abs(bw) - 1, t) - x[i] + t; h[i] = Y0 + R(Y + bh - 1, t) - y[i] + t; if (bw < 0) ho[i] = hd; }
        kd[i] = f.d[q + 2]; ph[i] = f.d[q + 3]; o[i] = Math.min(1, Math.max(0, f.d[q] / f.w));
      }
      return { name, f, k, gx, gy, m, md, n, x, y, w, h, kd, ph, o, ho, path: ph.some(v => v >= 0) };
    }
    function draw(now) {
      if (ctx) ctx.clearRect(0, 0, cv.width, cv.height);
      let more = false, col = -1;
      const ink = k => { if (k !== col) { ctx.fillStyle = COL[k]; col = k; } };
      // a mark at rest: its rect, or (an open unit) the four hairlines round it
      const rest = (F, i) => { const x = F.x[i], y = F.y[i], w = F.w[i], h = F.h[i], t = F.ho[i]; if (!t) ctx.fillRect(x, y, w, h); else { ctx.fillRect(x, y, w, t); ctx.fillRect(x, y + h - t, w, t); ctx.fillRect(x, y + t, t, h - 2 * t); ctx.fillRect(x + w - t, y + t, t, h - 2 * t); } };
      if (A) {
        const e = now - t0, n = Math.max(A.n, B.n);
        if (e >= DUR + LAG) A = null;
        else {
          more = true;
          for (let i = 0; i < n; i++) {
            const a = Math.floor(i * A.n / n), b = Math.floor(i * B.n / n);
            let t = (e - B.o[b] * LAG) / DUR; t = t <= 0 ? 0 : t >= 1 ? 1 : ease(t);
            ink(t < 0.5 ? A.kd[a] : B.kd[b]);
            if (t === 1) rest(B, b); else if (!t) rest(A, a); else ctx.fillRect(Math.round(A.x[a] + (B.x[b] - A.x[a]) * t), Math.round(A.y[a] + (B.y[b] - A.y[a]) * t), Math.max(1, Math.round(A.w[a] + (B.w[b] - A.w[a]) * t)), Math.max(1, Math.round(A.h[a] + (B.h[b] - A.h[a]) * t)));
          }
        }
        if (!A) arrived(now);
      }
      if (!A) {
        // the pass of light: each mark on the path stands a step larger (a quarter of itself each way) while the light is
        // on it; on a hero the still's own marks do (.is-pass), on the same clock
        let f = NaN;
        if (p0) { f = (now - p0) / PASS * 1.3 - 0.1; if (f > 1.2) { p0 = 0; f = NaN; stage.classList.remove('is-pass'); } else more = true; }
        const g = Math.max(1, Math.round(B.md / 4));
        if (ctx) for (let i = 0; i < B.n; i++) {
          const d = f - B.ph[i];
          ink(B.kd[i]);
          if (B.ph[i] >= 0 && d >= 0 && d < 0.1) ctx.fillRect(B.x[i] - g, B.y[i] - g, B.w[i] + 2 * g, B.h[i] + 2 * g); else rest(B, i);
        }
        if (grp) { if (!grpOn) labelsOn(); if (!planned) plan(); if (f === f || lit === lit) light(f); }
        lit = f;
      }
      stage.classList.add('figure-ready');
      if (first) { first.remove(); first = null; }
      if (more) request();
    }
    // the marks have landed: the labels come on, and on the index one pass of light walks the path
    function arrived(now) { if (!still && bin < 2 && B.path && !reduced.matches) p0 = now + 140; }
    function frame(now) { frameId = 0; if (!visible || document.hidden) return; draw(now); }
    function request() { if (!frameId && visible && !document.hidden) frameId = requestAnimationFrame(frame); }
    function resize() {
      W = Math.max(1, stage.clientWidth); H = Math.max(1, stage.clientHeight); D = window.devicePixelRatio || 1;
      const rs = getComputedStyle(document.documentElement);
      u = (parseFloat(rs.fontSize) || 16) / 16; hair = parseFloat(rs.getPropertyValue('--stroke')) || 1; // site.css: a hairline is --stroke px
      // the bitmap is painted one to one wherever the plate stands (pinned, it rests on another fraction of a px): the
      // canvas is a whole number of steps wide and high, a step the fewest CSS px that are whole device px, and its
      // corner lies on a step of the page; ox, oy are how far the stage's own corner lies from it
      if (ctx) {
        let st = 1; while (st < 16 && Math.abs(st * D - Math.round(st * D)) > 1e-3) st++;
        const at = stage.getBoundingClientRect(), X = at.left + window.scrollX, Y = at.top + window.scrollY;
        ox = X - Math.floor(X / st) * st; oy = Y - Math.floor(Y / st) * st;
        const cw = Math.ceil((ox + at.width) / st) * st, ch = Math.ceil((oy + at.height) / st) * st, bw = Math.round(cw * D), bh = Math.round(ch * D);
        if (cv.width !== bw || cv.height !== bh) { cv.width = bw; cv.height = bh; }
        cv.style.cssText = `left:${-ox}px;top:${-oy}px;width:${cw}px;height:${ch}px;max-width:none`;
      }
      stage.classList.remove('is-pass');
      measureSafe(); A = null; p0 = 0; B = fit(current);
      const g = bin > 1 ? null : groups[current] || null;
      if (g !== grp) { labelsOff(); grp = g; } else { grpOn = false; planned = false; } // the same words are measured and set again, in place
      draw(performance.now());
    }

    /* ---------------- labels ---------------- */
    // where the words may stand (stage px): inside the page's content edge, never under the bar (a hero stage starts at
    // the top of the page); a label that cannot stand there whole is not shown
    const safe = { l: 0, r: 1, t: 0 };
    function measureSafe() {
      const r = stage.getBoundingClientRect(), cb = stage.parentElement && stage.parentElement.querySelector(':scope > .container'), bar = document.querySelector('header.nav');
      safe.l = 0; safe.r = r.width;
      if (cb) { const b = cb.getBoundingClientRect(), s = getComputedStyle(cb); safe.l = Math.max(0, b.left + parseFloat(s.paddingLeft) - r.left); safe.r = Math.min(r.width, b.right - parseFloat(s.paddingRight) - r.left); }
      safe.t = bar ? Math.max(0, bar.offsetHeight - (r.top + window.scrollY)) : 0;
    }
    // a point of the formation (cells) on the stage (px)
    const scr = [0, 0];
    function project(x, y) { scr[0] = Math.round(B.gx + x * B.k); scr[1] = Math.round(B.gy + y * B.k); return true; }
    function labelsOn() {
      grpOn = true; planned = false; grp.items.forEach(it => {
        if (it.oneSet) { it.el.classList.remove('is-one'); it.oneSet = false; }
        const t = it.el.firstElementChild; it.w = t ? t.offsetWidth : 0; it.h = t ? t.offsetHeight : 0; it.x = NaN; it.sd = it.side; it.blocked = false; it.drop = 0; it.one = false;
        it.em = (t && parseFloat(getComputedStyle(t).fontSize)) || 11 * u; // the words' own size sets where a beside-the-point first line sits
        if (!it.to) { const l = Math.round(19 * u); if (l !== it.lead) { it.lead = l; it.el.style.setProperty('--lead', `${l}px`); } }
        // a hedge label's words on one line, measured for the slot search
        it.w1 = it.h1 = 0;
        if (it.keep && t && t.querySelector('small')) { it.el.classList.add('is-one'); it.w1 = t.offsetWidth; it.h1 = t.offsetHeight; it.el.classList.remove('is-one'); }
      });
      grp.el.classList.add('is-on');
    }
    function labelsOff() { if (grp) { grp.el.classList.remove('is-on'); grp.items.forEach(it => { if (it.lit) { it.el.classList.remove('is-lit'); it.lit = false; } }); } grpOn = false; planned = false; }
    /* words never stand on their own drawing. Once a formation lands and on a resize, its marks are laid on a grid of
       8 px cells. A label whose words would cover more than six occupied cells takes the other side of its point
       (left/right, above/below), then the slots beside that; if every one is covered, or off the stage, it is not shown:
       the caption says the same words */
    let CELL = 8, occ = null, oc = 0, orow = 0;
    const hits = (x0, y0, x1, y1) => {
      let n = 0; const c0 = Math.max(0, Math.floor(x0 / CELL)), c1 = Math.min(oc - 1, Math.floor(x1 / CELL)), r0 = Math.max(0, Math.floor(y0 / CELL)), r1 = Math.min(orow - 1, Math.floor(y1 / CELL));
      for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) n += occ[r * oc + c];
      return n;
    };
    function plan() {
      planned = true;
      CELL = Math.max(8, Math.round(8 * u)); oc = Math.ceil(W / CELL); orow = Math.ceil(H / CELL);
      if (!occ || occ.length < oc * orow) occ = new Uint16Array(oc * orow); else occ.fill(0);
      for (let i = 0; i < B.n; i++) {
        const x = B.x[i] / D - ox, y = B.y[i] / D - oy;
        const c0 = Math.max(0, Math.floor(x / CELL)), c1 = Math.min(oc - 1, Math.floor((x + (B.w[i] - 1) / D) / CELL)), r0 = Math.max(0, Math.floor(y / CELL)), r1 = Math.min(orow - 1, Math.floor((y + (B.h[i] - 1) / D) / CELL));
        for (let r = r0; r <= r1; r++) for (let c = c0; c <= c1; c++) occ[r * oc + c] = 1;
      }
      place(true); place(false);
    }
    // the light names each part as it passes: a label whose part (data-ph, the span of the path it names) holds the
    // light is lit; it stays lit while the trail goes by
    function light(f) {
      grp.items.forEach(it => { const on = !!it.ph && f >= it.ph[0] - 0.02 && f <= it.ph[it.ph.length - 1] + 0.1; if (on !== it.lit) { it.el.classList.toggle('is-lit', on); it.lit = on; } });
    }
    const mirror = d => d === 'l' ? 'r' : d === 'r' ? 'l' : (d[0] === 't' ? 'b' : 't') + d.slice(1);
    /* a label that carries a hedge (data-keep: note 09 "exact value not published", note 10 "phase two, on the roadmap")
       is listed first, so the claim-side labels yield to it where words would cross. Where its own side and the other
       have no room (a phone's stage), it tries the sides its data-keep allows (all if empty), a rule 8 px shorter or up
       to 96 px longer, and its two lines set as one; the first slot inside the stage, clear of the drawing and of its
       own point, wins. If none does, no label of the group is shown: a part is never named without its hedge */
    const SIDES = ['t', 'b', 'r', 'l', 'tr', 'tl', 'br', 'bl'], DROPS = [0, -8, 12, 24, 36, 48, 60, 72, 84, 96];
    const NEAR = { r: ['tr', 'br'], l: ['tl', 'bl'], t: ['tr', 'tl'], b: ['br', 'bl'], tr: ['t', 'r'], tl: ['t', 'l'], br: ['b', 'r'], bl: ['b', 'l'] };
    const setOut = (it, out) => { if (out !== it.out) { it.el.classList.toggle('is-out', out); it.out = out; } };
    function place(planning) {
      const M = 6 * u, L = safe.l + M, Rt = safe.r - M, T = safe.t + 4 * u, Bt = H - 4 * u, taken = [], pl = [];
      let bare = false; // the hedge label is not shown, so no other label is
      grp.items.forEach(it => {
        project(it.at[0], it.at[1]);
        const px = scr[0], py = scr[1];
        // a label whose point lies inside the drawing (data-to: where its words begin, in cells) reaches out on a longer
        // rule, so its words stand clear of what surrounds the point
        if (it.to && project(it.to[0], it.to[1])) { const lead = Math.max(Math.round(19 * u), Math.round(Math.abs(scr[0] - px))); if (lead !== it.lead) { it.lead = lead; it.el.style.setProperty('--lead', `${lead}px`); } }
        // keep the words inside the safe box: the text slides along its rule, the point stays where it is; a label whose
        // point or words would stand outside it (beyond the content edge, under the bar), or wider than it, is not shown
        const off = (d, w) => d === 'l' ? -it.lead - w : d === 'r' ? it.lead : d.length > 1 ? (d[1] === 'l' ? 6 * u - w : -6 * u) : -w / 2;
        const over = q => Math.max(L - q.left, q.left + q.w - Rt, 0);
        const at = (sd, drop, one) => {
          const w = one ? it.w1 : it.w, h = one ? it.h1 : it.h, left = px + off(sd, w), top = sd[0] === 't' ? py - 18 * u - drop - h : sd[0] === 'b' ? py + 18 * u + drop : py - 0.675 * it.em;
          const dx = left < L ? L - left : left + w > Rt ? Rt - left - w : 0;
          // words beside their point may slide along the rule, never back over the point
          const back = sd === 'l' ? left + dx + w > px - 5 * u : sd === 'r' ? left + dx < px + 5 * u : false;
          return { sd, drop, one, w, h, left, top, dx, bad: top < T || top + h > Bt || Math.abs(dx) > w * 0.5 + 12 * u || w > Rt - L || back };
        };
        if (planning) {
          // words beside a point that lack room on their side (more than a short slide) stand on the other, if they fit
          // there; words that would lie on the drawing do the same, or are not shown
          let g = at(it.side, 0, false);
          if ((g.sd === 'l' || g.sd === 'r') && over(g) > 16 * u) { const o = at(mirror(g.sd), 0, false); if (!over(o)) g = o; }
          const covered = q => hits(q.left + q.dx, q.top, q.left + q.dx + q.w, q.top + q.h) > 6;
          it.blocked = false;
          if (it.w && covered(g)) { const o = at(mirror(g.sd), 0, false); if (!o.bad && !covered(o)) g = o; else it.blocked = true; }
          // a part's name with no room or no clear side tries the two slots nearest its own before it is hidden
          if ((it.blocked || g.bad) && it.w && !it.keep) for (const sd of NEAR[it.side] || []) { const o = at(sd, 0, false); if (!o.bad && !covered(o)) { g = o; it.blocked = false; break; } }
          // then, for words set above or below their point, the same slots on a longer rule (12 or 24 px)
          if ((it.blocked || g.bad) && it.w && !it.keep && /^[tb]/.test(it.side)) drops: for (const d of [12, 24]) for (const sd of [it.side, ...(NEAR[it.side] || [])]) { if (!/^[tb]/.test(sd)) continue; const o = at(sd, Math.round(d * u), false); if (!o.bad && !covered(o)) { g = o; it.blocked = false; break drops; } }
          if (it.keep && it.w && (it.blocked || g.bad)) {
            it.blocked = true;
            const clear = q => hits(q.left + q.dx, q.top, q.left + q.dx + q.w, q.top + q.h) <= 3 && !(px > q.left + q.dx - 4 * u && px < q.left + q.dx + q.w + 4 * u && py > q.top - 3 * u && py < q.top + q.h + 3 * u);
            const sides = [it.side, mirror(it.side), ...SIDES].filter(sd => !it.sides.length || it.sides.includes(sd));
            search: for (const drop of DROPS.map(d => Math.round(d * u))) for (const one of it.w1 ? [false, true] : [false]) for (const sd of sides) {
              if (drop && (sd === 'l' || sd === 'r')) continue;
              const q = at(sd, drop, one); if (!q.bad && clear(q)) { g = q; it.blocked = false; break search; }
            }
          }
          // words never cross words: a part's name whose planned words would touch an earlier label's tries its two
          // nearest slots, then the other side, before it waits
          const bx = q => [q.left + q.dx - 8 * u, q.top - 5 * u, q.left + q.dx + q.w + 8 * u, q.top + q.h + 5 * u];
          const crosses = q => { const a = bx(q); return pl.some(b => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1]); };
          if (it.w && !it.keep && !it.blocked && !g.bad && crosses(g)) for (const sd of [...(NEAR[g.sd] || []), mirror(g.sd)]) { const o = at(sd, 0, false); if (!o.bad && !covered(o) && !crosses(o)) { g = o; break; } }
          if (it.w && !it.blocked && !g.bad) pl.push(bx(g));
          it.sd = g.sd; it.drop = g.drop; it.one = g.one; return;
        }
        const { sd, left, top, dx, bad, w, h } = at(it.sd || it.side, it.drop, it.one);
        if (sd !== it.el.dataset.side) it.el.dataset.side = sd;
        if (it.drop !== it.dropSet) { it.el.style.setProperty('--drop', `${it.drop}px`); it.dropSet = it.drop; }
        if (it.one !== it.oneSet) { it.el.classList.toggle('is-one', it.one); it.oneSet = it.one; }
        let out = bare || it.blocked || px < safe.l || px > safe.r || py < T || py > Bt || bad;
        // words never cross words: a label that would touch one shown before it (the table's order is the priority) waits
        if (!out && w) { const x0 = left + dx - 4 * u, x1 = left + dx + w + 4 * u, p5 = 5 * u; if (taken.some(b => x0 < b[2] && x1 > b[0] && top - 3 * u < b[3] && top + h + 3 * u > b[1])) out = true; else taken.push([x0, top, x1, top + h], [px - p5, py - p5, px + p5, py + p5]); }
        if (it.keep && out) bare = true;
        if (px !== it.x || py !== it.y) { it.el.style.transform = `translate(${px}px, ${py}px)`; it.x = px; it.y = py; }
        if (dx !== it.dx) { it.el.style.setProperty('--dx', `${Math.round(dx)}px`); it.dx = dx; }
        setOut(it, out);
      });
    }

    stage.__figure = {
      show(name) {
        if (!FORMS[name] || name === current) return;
        stage.dataset.figureCurrent = current = name;
        if (!B) return; // not drawn yet: the first draw is this formation
        const from = B;
        labelsOff(); B = fit(name); grp = bin > 1 ? null : groups[name] || null; p0 = 0;
        // the formation on show (or the one it was travelling to) is where the marks leave from; hidden, or under
        // reduced motion, the new formation at once
        if (reduced.matches || !visible || document.hidden) { A = null; if (visible && !document.hidden) draw(performance.now()); }
        else { A = from; t0 = performance.now(); request(); }
      },
      // a hero's one act: the pass of light, once (through OXA.actOnce, below)
      pass() { if (B && B.path && !A && !reduced.matches) { stage.classList.add('is-pass'); p0 = performance.now(); request(); } },
    };
    stage.dataset.figureCurrent = current;
    if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { visible = e.isIntersecting; if (visible && B) request(); }, { threshold: 0 }).observe(stage);
    if (document.fonts) document.fonts.ready.then(() => { if (B && grp) { grpOn = false; planned = false; request(); } }); // labels measured in their own face
    document.addEventListener('visibilitychange', () => { if (!document.hidden && B) request(); });
    if ('ResizeObserver' in window) new ResizeObserver(resize).observe(stage); else { window.addEventListener('resize', resize); resize(); }
    // a move to a display with another pixel ratio changes no CSS size: watch the ratio itself, re-arming each time
    (function watchRatio() { window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`).addEventListener('change', () => { resize(); watchRatio(); }, { once: true }); })();
    if (still) { const go = [stage, () => stage.__figure.pass(), { visible: 0.5, delay: 500 }]; if (OXA.actOnce) OXA.actOnce(...go); else (OXA.q = OXA.q || []).push(go); }
  }
  // after the first paint, one stage per task. On a phone, a stage that is not on the screen at the start (the index's
  // strip, below the screen until the list is read) starts when it first comes on
  const narrow = window.matchMedia('(max-width: 759.98px)');
  requestAnimationFrame(() => stages.forEach(s => {
    if (!narrow.matches || !('IntersectionObserver' in window)) { setTimeout(() => init(s), 0); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { io.disconnect(); setTimeout(() => init(s), 0); } });
    io.observe(s);
  }));
})();
