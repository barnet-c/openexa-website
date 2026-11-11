/* OpenEXA: the stage (home; system wrote v1 at hc31r). A canvas camera on OXA.run: one projector, set-ups as data, a framing box inside the figure, labels and the tag as DOM text, the cut and the move on the clock, the hand. window.OXA.stage */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {}, run = OXA.run, doc = document, root = doc.documentElement;
  if (!run || OXA.stage) return;
  const { GX, LX, RING, RAIL, GATE, tube } = run.world;
  const { sin, cos, sqrt, floor, round, max, min, abs, hypot, PI } = Math, TAU = PI * 2;
  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
  const ease = t => { let u = t; for (let i = 0; i < 5; i++) { const x = 3 * u * (1 - u) * (1 - u) * 0.62 + 3 * u * u * (1 - u) * 0.2 + u * u * u, d = 3 * (1 - u) * (1 - u) * 0.62 + 6 * u * (1 - u) * -0.42 + 3 * u * u * 0.8; u = clamp(u - (x - t) / (d || 1), 0, 1); } return 3 * u * u * (1 - u) + u * u * u; }; // --ease-move: cubic-bezier(.62, 0, .2, 1)
  const rm = window.matchMedia('(prefers-reduced-motion: reduce)');
  const el = (tag, cls, text) => { const n = doc.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const pad2 = n => String(n).padStart(2, '0');
  const LAYER = ['Signal intelligence', 'Model layer', 'Domain-specific agents', 'Execution Council', 'Routing layer', 'Execution layer', 'MCP server', 'Authentication layer'];
  const SX = [-0.8, -0.58, -0.36, -0.14, 0.24, 0.44, 0.64, 0.84], SB = 0.06;
  const axis = x => (x <= GX[3] ? -1 + (x + 1.5) / (GX[3] + 1.5) * (SX[3] + 1) : x <= GX[5] ? SX[3] + (x - GX[3]) / (GX[5] - GX[3]) * (SX[7] - SX[3]) : SX[7] + (x - GX[5]) / (LX - GX[5]) * 0.14);
  /* set-ups are data. fw x fh world units are framed in the box (cover or contain) with the world point `at` on the axis at (fx, fy) of
     that frame (in a framing element, never showing less than `wmin` units across or `hmin` up); `narrow` holds what changes when the box is a phone's width and `tall` when it is less than 8:5; `down` is the wide shot turned for an upright screen */
  const SET = {
    wide: { yaw: -0.34, pitch: 0.13, fw: 2.5, fh: 0.9, fx: 0.535, fy: 0.5, cover: true, wmin: 2.2, hmin: 0.68, k: 0.72, at: GX[3], b: 'ring', narrow: { wmin: 1.05 }, tall: { wmin: 1.05 } },
    section: { roll: -PI / 2, yaw: 0.72, pitch: 0.5, fw: 3.5, fh: 2.5, fx: 0.37, fy: 0.5, px: 0.5, py: 0.5, k: 1.75, axis, at: SB, b: 'plane', lx: 0.66, narrow: { fw: 2.08, fh: 3.3, fx: 0.5, fy: 0.55, lx: 9, col: 10.9 } },
    close: { yaw: -0.3, pitch: 0.16, fw: 1.9, fh: 0.7, fx: 0.69, fy: 0.55, cover: true, hmin: 0.72, k: 0.9, at: GX[3], b: 'ring', glyph: true, tall: { fy: 0.52, hmin: 0.73 }, narrow: { fw: 0.86, fh: 0.9, fx: 0.56, fy: 0.5, k: 0.92, hmin: 0.84 } },
    down: { roll: -PI / 2, yaw: 0.72, pitch: 0.5, fw: 1.9, fh: 2.62, fx: 0.31, fy: 0.5, px: 0.5, py: 0.5, k: 1.3, at: -0.16, b: 'ring', lx: 0.62 },
  };

  const NA = 1500, AX = new Float32Array(NA), AA = new Float32Array(NA), AR = new Float32Array(NA), AP = new Float32Array(NA), AW = new Uint8Array(NA), AB = new Uint16Array(NA);
  for (let i = 0; i < NA; i++) {
    AX[i] = -1.5 + 1.6 * Math.pow(run.u(i, 31), 0.85); AA[i] = TAU * run.u(i, 32); AR[i] = sqrt(run.u(i, 33)); AP[i] = TAU * run.u(i, 34);
    const w = run.u(i, 35); AW[i] = w > 0.86 ? 2 : w > 0.4 ? 1 : 0; AB[i] = floor(run.u(i, 36) * 512) | 16;
  }

  let PX = 0, PY = 0;
  // a phone's section keeps a column for its nine names (`col`, in rem): the stack is framed in what is left of the width, so no plane's corner
  // reaches a name, and its layers stand as far apart as the box's height allows (`ax`: the stack takes .86 of it), so the names keep their lines
  const pick = (c, b, r) => {
    const n = c.narrow && b.w < 600 * r, t = c.tall && b.w < b.h * 1.6;
    if (!n && !t) return c;
    const o = Object.assign({}, c, t && c.tall, n && c.narrow);
    if (o.col) { o.cw = o.col * 16 * r; o.ax = clamp((0.86 * b.h / max(1, min((b.w - o.cw) / o.fw, b.h / o.fh)) - 0.81) / 1.615, 1.3, 2.6); }
    return o;
  };
  function camera(c, b) {
    const W = b.w - (c.cw || 0), H = b.h, cr = cos(c.roll || 0), sr = sin(c.roll || 0), cy = cos(c.yaw), sy = sin(c.yaw), cp = cos(c.pitch), sp = sin(c.pitch), k = c.k;
    const s = c.cover ? min(max(W / c.fw, H / c.fh), b.fit && c.wmin ? W / c.wmin : 1e9, b.fit && c.hmin ? H / c.hmin : 1e9) : min(W / c.fw, H / c.fh), fw = s * c.fw, fh = s * c.fh;
    const L = b.x + (W - fw) * (c.px == null ? c.fx : c.px), T = b.y + (H - fh) * (c.py == null ? c.fy : c.py);
    const at = c.at * (c.ax || 1), a0 = at * cr, u0 = a0 * cy, v0 = at * sr * cp + a0 * sy * sp, ox = L + fw * c.fx, oy = T + fh * c.fy;
    const raw = (x, y, z) => { y *= k; z *= k; const x1 = x * cr - y * sr, y1 = x * sr + y * cr; PX = ox + s * (x1 * cy + z * sy - u0); PY = oy - s * (y1 * cp - (z * cy - x1 * sy) * sp - v0); };
    const ax = c.ax || 1;
    return { s, L, T, fw, fh, raw, pr: c.axis ? (x, y, z) => raw(c.axis(x) * ax, y, z) : raw };
  }
  function edge(c, cam) {
    if (c.b === 'ring') {
      cam.raw(GX[3], 0, 0); const cx = PX, cy = PY;
      cam.raw(GX[3], RING, 0); const ux = PX - cx, uy = PY - cy;
      cam.raw(GX[3], 0, RING); const vx = PX - cx, vy = PY - cy;
      if (!c.roll) { const b = abs(uy), a = abs(vx) || 1, k = vy / (vx || 1); return { l: cx - a, t: cy - b - a * k, w: 2 * a, h: 2 * b, m: [1, k, 0, 1], r: '50%', cx, cy, a, b, lo: cy + b }; }
      const w = hypot(vx, vy) || 1, h = hypot(ux, uy) || 1;
      return { l: cx - vx - ux, t: cy - vy - uy, w: 2 * w, h: 2 * h, m: [vx / w, vy / w, ux / h, uy / h], r: '50%', cx, cy, a: abs(ux) + abs(vx), b: abs(uy) + abs(vy), lo: cy + abs(uy) + abs(vy) };
    }
    const q = 0.6 * 1.16 / c.k, sb = SB * (c.ax || 1); cam.raw(sb, -q, -q); const x0 = PX, y0 = PY;
    cam.raw(sb, q, -q); const ux = PX - x0, uy = PY - y0, w = hypot(ux, uy);
    cam.raw(sb, -q, q); const vx = PX - x0, vy = PY - y0, h = hypot(vx, vy);
    return { l: x0, t: y0, w, h, m: [ux / w, uy / w, vx / h, vy / h], r: '0%' };
  }

  function mount(fig) {
    if (fig.__stage) return fig.__stage;
    const cv = el('canvas', 'stage-cv'), g = cv.getContext('2d'), labs = el('div', 'stage-labels'), tag = el('div', 'stage-tag'), tagA = el('b'), tagB = el('span');
    if (!g) return null;
    [cv, labs].forEach(n => n.setAttribute('aria-hidden', 'true'));
    tag.append(tagA, tagB); tag.hidden = true; labs.append(tag);
    // data-stage-frame names the element the first shot is framed in (its still and its boundary element stand there before this script)
    const frame = fig.dataset.stageFrame ? doc.querySelector(fig.dataset.stageFrame) : null;
    let bd = fig.querySelector('.run-b') || (frame && frame.querySelector('.run-b'));
    if (!bd) { bd = el('i', 'run-b'); bd.setAttribute('aria-hidden', 'true'); }
    // the hand's input is the figure's own, or (data-stage-input) one the page keeps in a box that shares the figure's origin
    const input = fig.dataset.stageHand === 'strict' ? fig.querySelector('input[type="range"]') || (fig.dataset.stageInput ? doc.querySelector(fig.dataset.stageInput) : null) : null, own = !!input && fig.contains(input);
    fig.append(bd, cv, labs);
    if (own) fig.append(input);
    fig.classList.add('stage');
    const st = fig.__stage = { fig, cv, g, labs, tag, tagA, tagB, bd, input, own, ro: (own || !input ? fig : input.parentNode).querySelector('[data-stage-ro]'), handIn: fig.dataset.stageHandIn || '', frame, box: null, name: SET[fig.dataset.stage] ? fig.dataset.stage : 'wide', W: 0, H: 0, D: 1, r: 1, m: 1, c: null, cam: null, e: null, cut: null, lab: [], hits: new Float32Array(768), nh: 0,
      seen: 0, slow: 0, rate: 1, tick: 0, dead: false, held: false, cost: 0, live: false, phone: false, fgc: '245, 242, 236', acc: '#4FCB93', rej: '#D9675D', bgc: '#0E1512', hand: null, sc: null, fly: 0, inAt: 0, liveAt: 0, hov: -1, put: [], lh: 0, tp: -1, tk: -1 };
    const size = () => { layout(st); draw(st, run.sample(), 'still'); };
    if ('ResizeObserver' in window) new ResizeObserver(size).observe(fig); else window.addEventListener('resize', size);
    if (input) {
      input.classList.add('scale');
      st.hand = run.hand(input, { key: 'strict', scale: 0.01, detent: 12, ev: 'Council strictness', unit: '%' });
      // a gesture the browser takes back (a touch that turned into a scroll) leaves the scale where it was and seals nothing: run.js hand()
      doc.addEventListener('oxa:record', e => { if (e.detail && e.detail.ev === 'Council strictness' && st.sc && !rm.matches) st.fly = performance.now(); });
    }
    const near = (e, r) => { const q = cv.getBoundingClientRect(), x = e.clientX - q.left, y = e.clientY - q.top; let best = -1, bd2 = r * r; for (let i = 0; i < st.nh; i++) { const d = (st.hits[i * 3] - x) ** 2 + (st.hits[i * 3 + 1] - y) ** 2; if (d < bd2) { bd2 = d; best = st.hits[i * 3 + 2]; } } return best; };
    const told = k => fig.dispatchEvent(new CustomEvent('stage:follow', { detail: k })); // the page's own controls keep step with a proposal followed here
    fig.addEventListener('pointermove', e => { if (e.pointerType !== 'mouse') return; st.hov = st.held ? -1 : near(e, 14 * st.r); fig.classList.toggle('is-near', st.hov >= 0); });
    fig.addEventListener('pointerleave', () => { st.hov = -1; fig.classList.remove('is-near'); });
    fig.addEventListener('click', e => { if (st.held || e.target.closest('input, button, a')) return; const k = near(e, (e.pointerType === 'mouse' ? 14 : 24) * st.r); if (k >= 0) { run.follow(k); told(k); } });
    fig.addEventListener('keydown', e => {
      if (e.target !== fig || st.held) return;
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); run.follow('next'); told(run.sample().tag); } else if (e.key === 'Escape') { run.follow(null); told(null); }
    });
    layout(st);
    run.subscribe((S, why) => draw(st, S, why), fig);
    return st;
  }

  const boxOf = (st, f) => { if (!f) return { x: 0, y: 0, w: st.W, h: st.H }; const q = f.getBoundingClientRect(), o = st.fig.getBoundingClientRect(); return q.width > 0 && q.height > 0 ? { x: q.left - o.left, y: q.top - o.top, w: q.width, h: q.height, fit: true } : { x: 0, y: 0, w: st.W, h: st.H }; };
  function layout(st) {
    const { fig, cv } = st, q = fig.getBoundingClientRect(), cs = getComputedStyle(fig), W = q.width, H = q.height;
    st.r = (parseFloat(getComputedStyle(root).fontSize) || 16) / 16;
    st.W = W; st.H = H; st.phone = W < 600 * st.r;
    if (!W || !H) return;
    st.D = min(3, window.devicePixelRatio || 1, sqrt(3840 * 2160 / max(1, W * H)));
    const w = round(W * st.D), h = round(H * st.D);
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    st.m = st.r * (st.phone ? 1.5 : 1.7) * clamp(W / (1440 * st.r), 1, 1.35);
    const fg = (cs.color.match(/[\d.]+/g) || [245, 242, 236]).slice(0, 3), ink = +fg[0] + +fg[1] + +fg[2] > 384;
    st.fgc = fg.join(', ');
    st.acc = cs.getPropertyValue('--accent').trim() || (ink ? '#4FCB93' : '#1E7A5A');
    st.rej = cs.getPropertyValue(ink ? '--reject-bright' : '--reject').trim() || '#D9675D';
    st.bgc = cs.getPropertyValue('--bg').trim() || (ink ? '#0E1512' : '#F5F2EC');
    if (st.cut) { st.frame = st.cut.frame; st.name = st.cut.to; endCut(st, true); }
    st.box = boxOf(st, st.frame);
    setup(st, st.name);
  }
  const room = (st, name, b) => (st.input && b.fit && b.w < 600 * st.r && SET[name].b === 'ring' && !SET[name].roll && (!st.handIn || st.handIn === name) ? Object.assign({}, b, { h: b.h - (st.ro ? 104 : 64) * st.r }) : b);
  function setup(st, name) {
    const c = pick(SET[name], st.box, st.r), cam = camera(c, room(st, name, st.box));
    st.name = name; st.c = c; st.cam = cam; st.e = edge(c, cam);
    if (st.fig.dataset.stage !== name) st.fig.dataset.stage = name;
    place(st.bd, st.e);
    scale(st);
    labels(st);
  }
  const css = e => ({ left: e.l.toFixed(2) + 'px', top: e.t.toFixed(2) + 'px', width: e.w.toFixed(2) + 'px', height: e.h.toFixed(2) + 'px', transform: `matrix(${e.m.map(v => v.toFixed(5)).join(', ')}, 0, 0)`, borderRadius: e.r });
  function place(bd, e) { Object.assign(bd.style, css(e), { transformOrigin: '0 0' }); }

  function labels(st) {
    const { c, cam, r, W, H, box } = st, out = [], add = (n, s, x, y, cls) => out.push({ n, s, x, y, cls }), narrow = box.w < 600 * r, rem = 16 * r;
    st.lab.splice(0).forEach(n => n.remove());
    if (c.axis) {
      const q = 0.6 / c.k, lx = min(box.x + (box.w - cam.fw) * (c.px == null ? c.fx : c.px) + cam.fw * c.lx, box.x + box.w - (narrow ? 10.2 : 12.5) * rem);
      st.lx = lx;
      const ax = c.ax || 1;
      SX.forEach((a, i) => { cam.raw(a * ax, q, q * 0.2); add(narrow ? '' : pad2(i + 1), LAYER[i], lx, PY - 0.45 * rem, i === 3 ? 'is-on' : ''); });
      cam.raw(SB * ax, q * 1.16, q * 0.2); add('', 'The boundary', lx, PY - 0.45 * rem, 'is-on is-b');
    } else if (c.roll) {
      const lx = box.x + (box.w - cam.fw) * (c.px == null ? c.fx : c.px) + cam.fw * c.lx;
      st.lx = lx;
      GX.forEach((x, i) => { cam.raw(x, 0.31, 0.05); add(pad2(i + 1), GATE[i], lx, PY - 0.45 * rem, i === 3 ? 'is-on' : ''); });
      cam.raw(LX + 0.05, 0, 0); add('', 'Ledger', lx, PY - 0.45 * rem, '');
    } else if (narrow) {
      cam.raw(GX[3] + 0.03, -0.36, -0.3); const fy = PY; cam.raw(GX[3] + 0.03, -0.36, 0.3); add('', 'Boundary', PX - 0.2 * rem, max(PY, fy) + 0.55 * rem, 'is-on is-b');
      if (c.glyph) { cam.raw(GX[3], 0.36, -0.3); add('04', 'Approve', PX - 0.3 * rem, PY - 1.25 * rem, 'is-on'); }
    } else {
      GX.forEach((x, i) => { if (c.glyph && i > 3) return; if (i === 3) cam.raw(x, 0.36, -0.3); else cam.raw(x, 0.31, -0.25); add(pad2(i + 1), GATE[i], PX - 0.3 * rem, PY - 1.25 * rem, i === 3 ? 'is-on' : ''); });
      if (st.sc) { cam.raw(GX[3] + 0.03, 0.36, -0.3); add('', 'Boundary', PX + 0.6 * rem, PY + 0.5 * rem, 'is-on is-b'); }
      else { cam.raw(GX[3] + 0.03, -0.36, 0.3); add('', 'Boundary', PX - 0.2 * rem, PY + 0.55 * rem, 'is-on is-b'); }
      if (c.glyph) { cam.raw(GX[3] + 0.1, -0.42, 0.08); add('', 'Rejected · falls away', PX + 0.75 * rem, PY - 0.6 * rem, 'is-no'); }
      else {
        cam.raw(LX + 0.03, 0, 0);
        const lx = min(PX, W - 11.5 * rem);
        let ly = PY - 2.4 * rem;
        if (lx < PX) for (let i = 0; i <= 12; i++) { cam.raw(GX[5] + (LX - GX[5]) * i / 12, RAIL[4] * (1 - smooth(0, 1, i / 12)), 0); if (PX > lx - 8 * r) ly = min(ly, PY - 1.75 * rem); }
        add('', 'Ledger · hash-chained', lx, ly, '');
      }
    }
    if (st.sc) { add('', '0', st.sc.x0 - 3 * r, st.sc.y + 12 * r, 'is-n'); add('', '60%', st.sc.x0 + st.sc.len - 12 * r, st.sc.y + 12 * r, 'is-n'); }
    // no label touches another, or the scale: one that would is moved a line up or down, or left out (the scale's own numerals go first)
    const put = [], sc = st.sc, lh = (c.axis ? 13 : 18) * r, top = box.y > 1 ? max(0, box.y - 8 * r) : 0, ro = sc && sc.ro;
    const hit = (x, y, w) => (ro && x < ro[0] + ro[2] + 12 * r && x + w + 12 * r > ro[0] && y < ro[1] + ro[3] + 4 * r && y + lh > ro[1] - 4 * r) || (sc && x < sc.x0 + sc.len + 14 * r && x + w > sc.x0 - 14 * r && y < sc.y + 13 * r && y + lh > sc.y - 13 * r) || put.some(p => x < p[0] + p[2] + 8 * r && x + w + 8 * r > p[0] && y < p[1] + lh && y + lh > p[1]);
    out.sort((a, b) => (b.cls === 'is-n') - (a.cls === 'is-n')).forEach(o => {
      if (c.glyph && o.cls !== 'is-n') o.y = clamp(o.y, top + 10 * r, H - 24 * r);
      if (o.x < -4 || o.x > W - 24 * r || o.y < top || o.y > H - 12 * r) return;
      const n = el('span', 'stage-lab ' + o.cls);
      if (o.n) n.append(el('b', '', o.n), ' ');
      n.append(o.s);
      st.labs.insertBefore(n, st.tag);
      const w = n.offsetWidth;
      if (o.cls !== 'is-n' && hit(o.x, o.y, w)) {
        const y = [-1, -2, 1, 2].map(k => o.y + k * 22 * r).find(v => v >= top + 4 * r && v <= H - 20 * r && !hit(o.x, v, w));
        if (y == null) { n.remove(); return; }
        o.y = y;
      }
      put.push([o.x, o.y, w]);
      n.style.transform = `translate(${o.x.toFixed(1)}px, ${o.y.toFixed(1)}px)`;
      st.lab.push(n);
    });
    st.put = put; st.lh = lh; st.tp = -1;
  }
  // the hand: a 0-60% scale under the Council, the page's own range input laid over it, and (if the page has one) its read-out beside it
  function scale(st) {
    const { input, e, r, W, H, ro } = st;
    st.sc = null;
    if (!input || st.c.b !== 'ring' || st.c.roll || (st.handIn && st.handIn !== st.name)) { if (input && st.own) input.style.display = 'none'; if (ro) ro.hidden = true; return; }
    st.cam.raw(GX[3] + 0.03, -0.36, 0.3);
    const len = min(250 * r, W - 64 * r), x0 = clamp(e.cx - len / 2, 22 * r, W - len - 22 * r), y = min(PY + 42 * r, H - 30 * r);
    st.sc = { x0, y, len };
    Object.assign(input.style, { display: '', position: 'absolute', left: (x0 - 22 * r).toFixed(1) + 'px', top: (y - 22 * r).toFixed(1) + 'px', width: (len + 44 * r).toFixed(1) + 'px' });
    if (ro) {
      ro.hidden = false; ro.classList.remove('is-under');
      const side = x0 + len + 44 * r + ro.offsetWidth <= W - 16 * r;
      ro.classList.toggle('is-under', !side);
      const w = ro.offsetWidth;
      const h = ro.offsetHeight, rx = side ? x0 + len + 44 * r : clamp(e.cx - w / 2, 16 * r, W - w - 16 * r), ry = side ? y - h / 2 : y + 34 * r;
      ro.style.transform = `translate(${rx.toFixed(1)}px, ${ry.toFixed(1)}px)`;
      st.sc.ro = [rx, ry, w, h];
    }
  }

  /* a change of shot, on the clock: to another set-up it is the 240 ms cut (labels out 120 ms, the boundary's outline travels on --ease-move, the
     set-up swaps in one frame at the midpoint, labels in); to another frame of the same set-up it is a move of the camera (480 ms). It always
     completes; a second call retargets it. Paused, reduced motion, a hidden tab or a held stage: one frame. */
  function endCut(st, silent) {
    st.cut = null;
    if (st.anim) { st.anim.cancel(); st.anim = null; }
    st.labs.classList.remove('is-out');
    delete st.fig.dataset.stageCut;
    if (!silent) place(st.bd, st.e);
  }
  const labsIn = st => { st.labs.classList.remove('is-out'); st.labs.classList.add('is-in'); st.inAt = performance.now(); };
  function cut(fig, name, frame) {
    const st = fig.__stage || mount(fig);
    if (!st || !SET[name]) return;
    const tn = st.cut ? st.cut.to : st.name, tf = st.cut ? st.cut.frame : st.frame;
    if (frame === undefined) frame = tf;
    if (name === tn && frame === tf) return;
    if (rm.matches || !st.live || st.held || run.sample().paused || doc.hidden || !st.W) { endCut(st, true); st.frame = frame; st.box = boxOf(st, frame); setup(st, name); draw(st, run.sample(), 'still'); return; }
    const to = boxOf(st, frame), now = performance.now();
    if (name === st.name && !(st.cut && !st.cut.move && !st.cut.swapped)) {
      if (st.anim) { st.anim.cancel(); st.anim = null; }
      st.cut = { to: name, frame, move: true, a: Object.assign({}, st.box), b: to, t0: now };
      st.frame = frame;
    } else {
      const from = st.cut && st.anim ? getComputedStyle(st.bd) : null, a = from ? { left: from.left, top: from.top, width: from.width, height: from.height, transform: from.transform, borderRadius: from.borderTopLeftRadius } : css(st.e);
      const c = pick(SET[name], to, st.r), e = edge(c, camera(c, room(st, name, to)));
      if (st.anim) st.anim.cancel();
      st.anim = st.bd.animate([a, css(e)], { duration: 240, easing: 'cubic-bezier(.62, 0, .2, 1)', fill: 'forwards' });
      st.cut = { to: name, frame, t0: now, swapped: false };
    }
    st.inAt = 0; st.labs.classList.remove('is-in'); st.labs.classList.add('is-out');
    fig.dataset.stageCut = name;
  }
  function cutting(st) {
    const c = st.cut, e = performance.now() - c.t0;
    if (c.move) {
      const u = ease(clamp(e / 480, 0, 1)), a = c.a, b = c.b;
      st.box = { x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, w: a.w + (b.w - a.w) * u, h: a.h + (b.h - a.h) * u, fit: b.fit };
      if (e >= 480) { st.box = b; setup(st, st.name); endCut(st); labsIn(st); return; }
      const cc = pick(SET[st.name], st.box, st.r); st.c = cc; st.cam = camera(cc, room(st, st.name, st.box)); st.e = edge(cc, st.cam); place(st.bd, st.e);
      return;
    }
    if (e >= 120 && !c.swapped) { c.swapped = true; st.frame = c.frame; st.box = boxOf(st, c.frame); setup(st, c.to); labsIn(st); }
    if (e >= 240) endCut(st);
  }

  const BK = [[], [], []];
  function draw(st, S, why) {
    if (!st.W || !st.H || !st.box || st.held) return;
    const t0 = performance.now();
    if (why === 'frame' && (st.dead || (st.rate > 1 && st.tick++ % st.rate))) return;
    if (st.inAt && t0 - st.inAt > 220) { st.inAt = 0; st.labs.classList.remove('is-in'); }
    if (st.cut) { if (why === 'frame') cutting(st); else { const c = st.cut; endCut(st, true); st.frame = c.frame; st.box = boxOf(st, c.frame); setup(st, c.to); } }
    const { g, W, H, D, cam, c, m, fgc, acc, rej, r, e } = st, t = S.t, pr = cam.pr, raw = cam.raw, glyph = !!c.glyph, flat = !c.axis;
    const fg = a => `rgba(${fgc}, ${a})`, snap = v => round(v * D) / D, px = max(1 / D, snap(1));
    const quad = (x, hy, hz) => { raw(x, -hy, -hz); g.moveTo(PX, PY); raw(x, hy, -hz); g.lineTo(PX, PY); raw(x, hy, hz); g.lineTo(PX, PY); raw(x, -hy, hz); g.lineTo(PX, PY); g.closePath(); };
    g.setTransform(D, 0, 0, D, 0, 0); g.clearRect(0, 0, W, H); g.lineWidth = px; g.lineJoin = 'round';

    if (flat) {
      g.beginPath(); GX.forEach((x, i) => { if (i !== 3) quad(x, 0.31, 0.25); });
      g.fillStyle = fg(0.03); g.fill(); g.strokeStyle = fg(0.34); g.stroke();
      if (c.roll) { g.beginPath(); GX.forEach(x => { raw(x, 0.31, 0.05); g.moveTo(PX + 6 * r, PY); g.lineTo(st.lx - 12 * r, PY); }); g.strokeStyle = fg(0.22); g.stroke(); }
    } else {
      const q = 0.6 / c.k, ax = c.ax || 1;
      SX.forEach((a, i) => { g.beginPath(); quad(a * ax, q, q); g.fillStyle = fg(0.035); g.fill(); g.strokeStyle = fg(i === 3 ? 0.5 : 0.3); g.stroke(); });
      g.beginPath(); SX.forEach(a => { raw(a * ax, q, q * 0.2); g.moveTo(PX, PY); g.lineTo(st.lx - 12 * r, PY); });
      g.strokeStyle = fg(0.22); g.stroke();
      g.beginPath(); quad(SB * ax, q * 1.16, q * 1.16); g.fillStyle = acc; g.globalAlpha = 0.07; g.fill(); g.globalAlpha = 1;
      g.beginPath(); raw(SB * ax, q * 1.16, q * 0.2); g.moveTo(PX, PY); g.lineTo(st.lx - 12 * r, PY); g.strokeStyle = acc; g.stroke();
    }

    const na = st.phone ? 700 : NA, sz = glyph ? m * 1.9 : m, d = max(1 / D, snap(sz)), step = sz * 1.5;
    BK[0].length = BK[1].length = BK[2].length = 0;
    for (let i = 0; i < na; i++) {
      const x = AX[i];
      if (x > GX[3] - 0.03 || (glyph && (i % 5 || x < -0.95))) continue;
      const rr = tube(x) * AR[i], an = AA[i] + 0.25 * sin(t * 0.31 + AP[i]);
      pr(x + 0.006 * sin(t * 1.3 + AP[i]), rr * sin(an), rr * cos(an));
      if (PX < -20 || PX > W + 20 || PY < -20 || PY > H + 20) continue;
      const bk = BK[AW[i]];
      if (glyph) { const bits = AB[i]; for (let b = 0; b < 9; b++) if ((bits >> b) & 1) bk.push(PX + ((b % 3) - 1) * step, PY + (floor(b / 3) - 1) * step); } else bk.push(PX, PY);
    }
    for (let i = 0; i < 3; i++) {
      const bk = BK[i];
      g.fillStyle = fg(glyph ? [0.6, 0.6, 0.95][i] : [0.48, 0.66, 0.95][i]); g.beginPath();
      for (let j = 0; j < bk.length; j += 2) g.rect(snap(bk[j] - sz / 2), snap(bk[j + 1] - sz / 2), d, d);
      g.fill();
    }

    g.lineWidth = px; g.strokeStyle = fg(0.26); g.beginPath();
    for (let j = 0; j < 5; j++) for (let i = 0; i <= 24; i++) { const u = i / 24, x = GX[3] + (LX - GX[3]) * u; pr(x, x <= GX[5] ? RAIL[j] : RAIL[j] * (1 - smooth(0, 1, (x - GX[5]) / (LX - GX[5]))), 0); if (i) g.lineTo(PX, PY); else g.moveTo(PX, PY); }
    g.stroke();
    g.strokeStyle = fg(0.4); g.beginPath();
    for (let i = 0; i < 72; i++) { const a = i / 72 * TAU; pr(GX[3], RING * 1.1 * sin(a), RING * 1.1 * cos(a)); g.moveTo(PX, PY); pr(GX[3], RING * 1.27 * sin(a), RING * 1.27 * cos(a)); g.lineTo(PX, PY); }
    g.stroke();
    const lim = 1 - S.strict, sv = st.sc && st.input ? +st.input.value / 100 : S.strict, lv = 1 - sv;
    if (st.sc || S.strict !== 0.12) {
      g.strokeStyle = rej; g.globalAlpha = 0.7; g.beginPath();
      for (let i = 0; i < 72; i++) { const a = (i + 0.5) / 72 * TAU; pr(GX[3], RING * (lv + 0.03) * sin(a), RING * (lv + 0.03) * cos(a)); g.moveTo(PX, PY); pr(GX[3], RING * 0.97 * sin(a), RING * 0.97 * cos(a)); g.lineTo(PX, PY); }
      g.stroke(); g.globalAlpha = 1;
      g.strokeStyle = acc; g.lineWidth = max(px, 1.5 * r); g.beginPath();
      for (let i = 0; i <= 72; i++) { const a = i / 72 * TAU; pr(GX[3], RING * lv * sin(a), RING * lv * cos(a)); if (i) g.lineTo(PX, PY); else g.moveTo(PX, PY); }
      g.stroke(); g.lineWidth = px;
    }
    if (!flat) {
      g.strokeStyle = acc; g.lineWidth = max(px, 1.5 * r); g.beginPath();
      for (let i = 0; i <= 72; i++) { const a = i / 72 * TAU; pr(GX[3], RING * sin(a), RING * cos(a)); if (i) g.lineTo(PX, PY); else g.moveTo(PX, PY); }
      g.stroke(); g.lineWidth = px;
    } else {
      g.beginPath(); quad(GX[3] + 0.03, 0.36, 0.3);
      g.fillStyle = acc; g.globalAlpha = 0.05; g.fill(); g.globalAlpha = 1; g.strokeStyle = acc; g.stroke();
    }

    const nb = floor(S.bl) - 1, bs = snap(flat ? m * 4.4 : m * 3.6), gap = 0.062, nn = c.roll ? 5 : flat ? 30 : st.phone ? 5 : 14;
    for (let i = nb; i > nb - nn && i >= 0; i--) {
      const x = LX + 0.035 + (S.bl - 1 - i) * gap;
      if (flat) pr(x, 0, 0); else raw(SX[7] * (c.ax || 1) + 0.14, 0.07 + (x - LX) * 1.5, 0);
      if (PX > (flat ? W + 20 : st.lx - 28 * r) || PY > H + 20) break;
      g.fillStyle = i === nb && !S.halted ? acc : fg(0.9); g.fillRect(snap(PX - bs / 2), snap(PY - bs / 2), bs, bs);
    }

    let nh = 0, tx = 0, ty = 0, hx = -1, hy = 0;
    const hits = st.hits, rs = m * (glyph ? 4.6 : 2.3), lw = max(px, m * 0.7);
    g.strokeStyle = acc; g.lineWidth = lw; g.beginPath();
    for (let i = 0; i < S.n; i++) {
      pr(S.x[i], S.y[i], S.z[i]);
      if (nh < 256) { hits[nh * 3] = PX; hits[nh * 3 + 1] = PY; hits[nh * 3 + 2] = S.k[i]; nh++; }
      if (i === S.ti) { tx = PX; ty = PY; }
      if (S.k[i] === st.hov && i !== S.ti) { hx = PX; hy = PY; }
      if (S.ph[i] < 2) { g.moveTo(PX + rs, PY); g.arc(PX, PY, rs, 0, TAU); }
    }
    g.stroke(); st.nh = nh;
    if (hx >= 0) { g.strokeStyle = fg(0.8); g.lineWidth = px; g.beginPath(); g.arc(hx, hy, m * 5.4, 0, TAU); g.stroke(); }
    g.strokeStyle = acc; g.globalAlpha = 0.5; g.lineWidth = max(px, m * 0.8); g.beginPath();
    for (let i = 0; i < S.n; i++) if (S.ph[i] === 2 || S.ph[i] === 3) { pr(S.x[i] - 0.05, S.y[i], S.z[i]); g.moveTo(PX, PY); pr(S.x[i], S.y[i], S.z[i]); g.lineTo(PX, PY); }
    g.stroke(); g.globalAlpha = 1;
    const q2 = snap(m * 2.6);
    g.fillStyle = acc; g.beginPath();
    for (let i = 0; i < S.n; i++) if (S.ph[i] === 2 || S.ph[i] === 3) { pr(S.x[i], S.y[i], S.z[i]); g.rect(snap(PX - q2 / 2), snap(PY - q2 / 2), q2, q2); }
    g.fill();
    // a refusal falls away: it is gone before it reaches the hand's scale and read-out
    const q4 = snap(m * 2.4), floorY = st.sc ? st.sc.y - 18 * r : 1e9;
    g.fillStyle = rej;
    for (let b = 0; b < 3; b++) {
      g.globalAlpha = [1, 0.66, 0.3][b]; g.beginPath();
      for (let i = 0; i < S.n; i++) if (S.ph[i] === 4 && min(2, floor(S.u[i] * S.u[i] * 3)) === b) { pr(S.x[i], S.y[i], S.z[i]); if (PY < floorY) g.rect(snap(PX - q4 / 2), snap(PY - q4 / 2), q4, q4); }
      g.fill();
    }
    g.globalAlpha = 1;

    const tag = st.tag, moving = st.cut && (st.cut.move || !st.cut.swapped);
    if (S.ti >= 0 && !moving && (why !== 'frame' || t0 - st.liveAt > 900) && tx > -40 && tx < W + 40 && ty > -40 && ty < H + 40) {
      if (tag.hidden) tag.hidden = false;
      if (st.tagA.textContent !== S.tagId) st.tagA.textContent = S.tagId;
      if (st.tagB.textContent !== S.tagLine) { st.tagB.textContent = S.tagLine; tag.classList.toggle('is-no', S.tagTone === 'no'); }
      // the tag stands up and to the right of its proposal; where it would leave the stage or touch a label it takes the next place that is
      // free (up left, down right, down left; over it on a phone) and keeps that place while it stays free, so it never flickers between two
      const pxl = 12 * r, bw = (max(S.tagId.length, S.tagLine.length) * 8.4 + 22) * r, bh = 51 * r, top = (st.box.y > 1 ? st.box.y : 0) + 4 * r, put = st.put || [], lh = st.lh || 0;
      const at = p => (p === 4 ? [clamp(tx - bw / 2, 8 * r, W - bw - 8 * r), max(top, ty - bh - pxl * 2.4)] : [p & 1 ? tx - pxl * 2.2 - bw : tx + pxl * 2.2, p & 2 ? ty + pxl * 1.3 : max(top, ty - bh - pxl * 1.3)]);
      const free = p => { const q = at(p), x = q[0], y = q[1]; return x >= 8 * r && x + bw <= W - 8 * r && y + bh <= H - 8 * r && !put.some(l => x < l[0] + l[2] + 6 * r && x + bw + 6 * r > l[0] && y < l[1] + lh + 4 * r && y + bh + 4 * r > l[1]); };
      if (st.tk !== S.tag || st.tp < 0 || !free(st.tp)) { const order = st.phone ? [0, 4, 1, 2, 3] : [0, 1, 2, 3]; st.tk = S.tag; st.tp = order.find(free); if (st.tp == null) st.tp = st.phone ? 4 : tx + pxl * 2.2 + bw <= W - 8 * r ? 0 : 1; }
      const tp = st.tp, q = at(tp), bx = q[0], by = q[1], side = tp & 1 ? -1 : 1, dn = tp & 2 ? 1 : -1;
      g.strokeStyle = fg(0.95); g.lineWidth = px; g.beginPath(); g.arc(tx, ty, m * 6.5, 0, TAU); g.stroke();
      g.strokeStyle = fg(0.55); g.beginPath();
      if (tp === 4) { g.moveTo(tx, ty - m * 6.5); g.lineTo(tx, by + bh); } else { g.moveTo(tx + side * m * 4.6, ty + dn * m * 4.6); g.lineTo(side < 0 ? bx + bw : bx, dn < 0 ? by + bh : by); }
      g.stroke();
      tag.style.transform = `translate(${snap(bx)}px, ${snap(by)}px)`;
    } else if (!tag.hidden) tag.hidden = true;

    if (st.sc) {
      const { x0, y, len } = st.sc, xp = x0 + sv * 100 / 60 * len, yy = snap(y) + px / 2;
      g.strokeStyle = fg(0.5); g.lineWidth = px; g.beginPath(); g.moveTo(x0, yy); g.lineTo(x0 + len, yy);
      for (let i = 0; i <= 6; i++) { const x = snap(x0 + i / 6 * len) + px / 2; g.moveTo(x, yy - (i % 3 ? 3 : 6) * r); g.lineTo(x, yy + (i % 3 ? 3 : 6) * r); }
      g.stroke();
      g.strokeStyle = acc; g.lineWidth = max(px, 1.5 * r); g.beginPath(); g.moveTo(x0, yy); g.lineTo(xp, yy); g.stroke(); g.lineWidth = px;
      const ax = e.cx + (xp - e.cx) * 0.25, ay = e.cy + e.b * lv + 3 * r;
      g.setLineDash([2 * r, 3 * r]); g.strokeStyle = fg(0.6); g.beginPath(); g.moveTo(xp, y - 11 * r); g.lineTo(ax, ay); g.stroke(); g.setLineDash([]);
      // a sealed move leaves the hand as a mark: up the leader, then away along a rail
      if (st.fly) {
        const u = (performance.now() - st.fly) / 1400;
        if (u >= 1 || why !== 'frame') st.fly = 0;
        else {
          const v = u < 0.3 ? 0 : (u - 0.3) / 0.7, w = smooth(0, 0.2, v), R = 5 * r;
          pr(GX[3] + (GX[5] - GX[3]) * v, RAIL[1] * w - RING * lv * (1 - w), 0);
          let fx = PX, fy = PY;
          if (u < 0.3) { const k = ease(u / 0.3); fx = xp + (fx - xp) * k; fy = y - 11 * r + (fy - (y - 11 * r)) * k; }
          g.fillStyle = fg(1); g.beginPath(); g.arc(fx, fy, R, 0, TAU); g.fill();
          g.fillStyle = st.bgc; g.beginPath(); g.arc(fx, fy, R * 0.34, 0, TAU); g.fill();
        }
      }
    }
    if (!st.live) { st.live = true; st.liveAt = t0; st.fig.classList.add('is-live'); }
    st.cost = performance.now() - t0;
    if (why === 'frame' && st.rate < 4) {
      st.seen++;
      if (st.cost > 14 * st.rate) st.slow++;
      if (st.seen === 60) { if (st.slow > 30) { st.rate *= 2; st.dead = st.rate > 2; } st.seen = st.slow = 0; }
    }
  }

  OXA.stage = {
    mount, cut,
    // a held stage draws nothing (another picture has the screen); letting go draws it at once
    hold(fig, on) { const st = fig.__stage; if (!st || st.held === !!on) return; st.held = !!on; fig.classList.toggle('is-off', st.held); if (!st.held) { layout(st); draw(st, run.sample(), 'still'); } },
    get: fig => fig.__stage || null,
    sets: SET,
    frame(name, W, H) { const c = SET[name], b = { x: 0, y: 0, w: W || c.fw * 1000, h: H || c.fh * 1000 }, cc = pick(c, b, 1), cam = camera(cc, b); return { fw: cc.fw, fh: cc.fh, edge: edge(cc, cam), at: (x, y, z, plain) => { (plain ? cam.raw : cam.pr)(x, y, z); return [PX, PY]; }, agents: { n: NA, x: AX, a: AA, r: AR, p: AP, w: AW } }; },
  };
  doc.querySelectorAll('[data-stage]').forEach(mount);
})();
