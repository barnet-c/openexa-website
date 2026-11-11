/* OpenEXA: the run on a paper plate (system). Moves at most 24 marks of OXA.run along the authored paths of an inline SVG marked data-run-plate; as authored the SVG is the finished still. window.OXA.runplate */
(function () {
  'use strict';
  const OXA = window.OXA = window.OXA || {}, run = OXA.run, doc = document;
  if (!run || OXA.runplate) return;
  const NS = 'http://www.w3.org/2000/svg', { floor, min, max } = Math, N = 48, MAX = 24;
  const mk = (tag, cls, into) => { const n = doc.createElementNS(NS, tag); n.setAttribute('class', cls); into.append(n); return n; };
  const f = v => (Math.round(v * 100) / 100).toString();
  let QX = 0, QY = 0;
  function lut(path) {
    const len = path.getTotalLength(), a = new Float32Array((N + 1) * 2);
    for (let i = 0; i <= N; i++) { const p = path.getPointAtLength(len * i / N); a[i * 2] = p.x; a[i * 2 + 1] = p.y; }
    return { a, len };
  }
  function at(l, u) {
    const x = (u < 0 ? 0 : u > 1 ? 1 : u) * N, i = min(N - 1, floor(x)), t = x - i, a = l.a;
    QX = a[i * 2] + (a[i * 2 + 2] - a[i * 2]) * t; QY = a[i * 2 + 1] + (a[i * 2 + 3] - a[i * 2 + 1]) * t;
  }
  function mount(svg) {
    if (svg.__plate) return svg.__plate;
    const all = n => Array.from(svg.querySelectorAll(`[data-run="${n}"]`)), luts = n => all(n).filter(p => p.getTotalLength).map(lut);
    const P = { approach: luts('approach'), check: luts('check'), rail: luts('rail'), spur: luts('spur'), chain: luts('chain') };
    if (!P.approach.length) return null;
    const vb = svg.viewBox.baseVal, size = parseFloat(svg.dataset.runSize) || vb.width * 0.011, gap = parseFloat(svg.dataset.runGap) || size * 3.4, nb = parseInt(svg.dataset.runBlocks, 10) || 9;
    const layer = mk('g', 'rp', svg), blocks = mk('path', 'rp-b', layer), fresh = mk('path', 'rp-new', layer), rings = mk('path', 'rp-ring', layer), sqs = mk('path', 'rp-sq', layer), no = mk('path', 'rp-no', layer), no2 = mk('path', 'rp-no rp-no--late', layer), halo = mk('circle', 'rp-halo', layer);
    const tag = svg.querySelector('[data-run="tag"]') || (svg.parentNode && svg.parentNode.querySelector('[data-run="tag"]')), html = !!tag && !(tag instanceof SVGElement);
    const tid = tag && tag.querySelector('[data-run-id]'), tline = tag && tag.querySelector('[data-run-line]'), hash = svg.querySelector('[data-run="hash"]');
    layer.setAttribute('aria-hidden', 'true'); halo.setAttribute('r', f(size * 2.1));
    if (tag && !html) layer.after(tag);
    all('still').forEach(n => n.setAttribute('display', 'none'));
    svg.classList.add('is-live');
    const sq = (x, y, s) => `M${f(x - s / 2)} ${f(y - s / 2)}h${f(s)}v${f(s)}h${f(-s)}z`, ring = (x, y, r) => `M${f(x - r)} ${f(y)}a${f(r)} ${f(r)} 0 1 0 ${f(2 * r)} 0a${f(r)} ${f(r)} 0 1 0 ${f(-2 * r)} 0`;
    const pick = (list, k) => list[k % list.length];
    let seenTag = '', seenLine = '', seenHash = '';
    function draw(S) {
      let dr = '', ds = '', dn = '', dl = '', n = 0, tx = 0, ty = 0, tagged = false;
      for (let i = 0; i < S.n; i++) {
        const k = S.k[i], ph = S.ph[i], u = S.u[i];
        // one in four, and always the tagged one: a place is kept for it while it is still ahead in the list (oldest first)
        if (i !== S.ti && (k % 4 !== 2 || n >= (i < S.ti ? MAX - 1 : MAX))) continue;
        if (ph === 0) at(pick(P.approach, k), u);
        else if (ph === 1) { if (P.check.length) at(pick(P.check, k), u); else at(pick(P.approach, k), 1); }
        else if (ph === 4) { if (!P.spur.length) continue; at(pick(P.spur, k), u); }
        else { if (!P.rail.length) continue; at(pick(P.rail, S.lane[i]), ph === 2 ? u * 0.8 : 0.8 + 0.2 * u); }
        n++;
        if (ph < 2) dr += ring(QX, QY, size * 0.85); else if (ph === 4) { if (u < 0.6) dn += sq(QX, QY, size); else dl += sq(QX, QY, size); } else ds += sq(QX, QY, size);
        if (i === S.ti) { tagged = true; tx = QX; ty = QY; }
      }
      rings.setAttribute('d', dr); sqs.setAttribute('d', ds); no.setAttribute('d', dn); no2.setAttribute('d', dl);
      if (P.chain.length) {
        const c = P.chain[0], top = floor(S.bl) - 1, fr = S.bl - floor(S.bl);
        let db = '', dg = '';
        for (let j = 0; j < nb && top - j >= 0; j++) { const d = (fr + j) * gap; if (d > c.len) break; at(c, d / c.len); const p = `M${f(QX - size)} ${f(QY - size / 2)}h${f(size * 2)}v${f(size)}h${f(-size * 2)}z`; if (!j && !S.halted) dg = p; else db += p; }
        blocks.setAttribute('d', db); fresh.setAttribute('d', dg);
        const h = top >= 0 ? run.block(top).slice(0, 8) : '';
        if (hash && h !== seenHash) hash.textContent = seenHash = h;
      }
      halo.setAttribute('display', tagged ? '' : 'none');
      if (tagged) { halo.setAttribute('cx', f(tx)); halo.setAttribute('cy', f(ty)); }
      if (tag) {
        if (html) tag.hidden = !tagged; else tag.setAttribute('display', tagged ? '' : 'none');
        if (tagged) {
          if (html) { tag.style.left = f(tx / vb.width * 100) + '%'; tag.style.top = f(ty / vb.height * 100) + '%'; tag.classList.toggle('is-left', tx > vb.width * 0.6); }
          else tag.setAttribute('transform', `translate(${f(tx)} ${f(ty)})`);
          if (tid && seenTag !== S.tagId) tid.textContent = seenTag = S.tagId;
          if (tline && seenLine !== S.tagLine) { tline.textContent = seenLine = S.tagLine; tag.classList.toggle('is-no', S.tagTone === 'no'); }
        }
      }
    }
    svg.__plate = { draw, paths: P };
    run.subscribe(draw, svg);
    return svg.__plate;
  }
  OXA.runplate = { mount };
  doc.querySelectorAll('svg[data-run-plate]').forEach(mount);
})();
