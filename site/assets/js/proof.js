/* OpenEXA — proof: the Lifecycle 01 performance report (home §04 · the Proof hero), drawn from the one record
   <script type="application/json" id="oxa-sessions"> { lifecycle, unit, floor, sessions: [{ day, regime, value, confirmation, status }] }.
   [data-proof-chart] the chart (replaces its fallback; un-hides a [data-proof-fig]) · [data-proof="k"] a count (total above
   premium discount confirmed settled floor, or "regimes"), data-proof-as "words"/"Words" spells it; written once, final.
   The static HTML says the same without JS (Proof's no-JS record is a table in a <noscript>). Nothing is invented: ">10" is
   drawn as above the floor, value not published; a missing field reads "Not stated". Lanes: hover, focus or tap to light a
   session (each lane names its record to assistive tech); arrows, Home/End, Enter, Esc. One entrance, then still; none
   under reduced motion. hc4: the inspector under the chart and the table builder went (Proof's chart moved into its hero,
   where the lanes and the lede carry the record; the table has been <noscript> only since the 1 Nov cut). Plain DOM. */
(function () {
  'use strict';
  const src = document.getElementById('oxa-sessions');
  if (!src) return;
  let rec = null;
  try { rec = JSON.parse(src.textContent); } catch (e) { return; } // an unreadable record leaves the static page as written
  const floor = rec ? Number(rec.floor) : NaN;
  const raw = rec && Array.isArray(rec.sessions) ? rec.sessions.filter(s => s && typeof s === 'object') : [];
  if (!raw.length || !(floor > 0)) return;

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const NUM = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split(' ');
  const words = n => NUM[n] || String(n);
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const str = v => (v == null ? '' : String(v)).trim();
  const NOT = 'Not stated';
  const unit = str(rec.unit) || 'bps';
  const lifecycle = str(rec.lifecycle);

  /* ---------------- the record, read once ---------------- */
  const sessions = raw.map((s, i) => {
    const day = str(s.day) || 'Session ' + (i + 1);
    const regime = str(s.regime), r = regime.toLowerCase();
    const value = str(s.value);
    const m = /^(>=|≥|>)?\s*(\d+(?:\.\d+)?)$/.exec(value);
    const bound = m ? m[1] || '' : '', amount = m ? Number(m[2]) : NaN;
    const confirmation = str(s.confirmation), status = str(s.status);
    return {
      day, num: (day.match(/\d+/) || [String(i + 1).padStart(2, '0')])[0],
      regime: regime || NOT, side: r.startsWith('prem') ? 1 : r.startsWith('disc') ? -1 : 0,
      value, bound, amount, above: !!m && (bound === '>' ? amount >= floor : amount > floor),
      confirmation: confirmation || NOT, confirmed: /confirm/i.test(confirmation) && !/pending|awaiting|unconfirm|^not\b/i.test(confirmation),
      status: status || NOT, settled: /^settled$/i.test(status)
    };
  });
  const count = f => sessions.filter(f).length;
  const C = {
    total: sessions.length, above: count(s => s.above), premium: count(s => s.side > 0), discount: count(s => s.side < 0),
    confirmed: count(s => s.confirmed), settled: count(s => s.settled), floor
  };
  const valueSaid = s => !Number.isFinite(s.amount) ? (s.value ? s.value : 'value not stated')
    : (s.bound === '>' ? 'more than ' : s.bound ? 'at least ' : '') + s.amount + ' ' + unit;
  const regimeSaid = s => s.side > 0 ? 'premium regime, price above NAV' : s.side < 0 ? 'discount regime, price below NAV' : 'NAV regime not stated';

  /* ---------------- derived counts in the copy ---------------- */
  const derived = (key, as) => {
    if (key === 'regimes') return cap(words(C.premium)) + ' premium, ' + words(C.discount) + ' discount.';
    if (!Object.prototype.hasOwnProperty.call(C, key)) return null;
    const n = C[key];
    return as === 'words' ? words(n) : as === 'Words' ? cap(words(n)) : String(n);
  };
  document.querySelectorAll('[data-proof]').forEach(el => {
    const text = derived(el.dataset.proof, el.dataset.proofAs);
    if (text != null && el.textContent !== text) el.textContent = text; // the final value only (the static text already is)
  });

  /* ---------------- helpers ---------------- */
  const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const NS = 'http://www.w3.org/2000/svg';
  const sv = (tag, attrs) => { const e = document.createElementNS(NS, tag); Object.keys(attrs).forEach(k => e.setAttribute(k, attrs[k])); return e; };
  const mute = e => { e.setAttribute('aria-hidden', 'true'); return e; };
  const summarySaid = cap(words(C.total)) + ' sessions' + (lifecycle ? ' of ' + lifecycle : '') + ': ' +
    (C.above === C.total ? 'all' : words(C.above) + ' of ' + words(C.total)) + ' above the ' + floor + ' ' + unit + ' floor, exact values above it not published. ' +
    cap(words(C.premium)) + ' in a premium regime, price above NAV; ' + words(C.discount) + ' in a discount regime, price below NAV. ' +
    cap(words(C.confirmed)) + ' of ' + words(C.total) + ' confirmed by the broker; ' + words(C.settled) + ' settled.';

  /* ---------------- the chart ---------------- */
  const ENTRANCE_MS = 1400; // the CSS entrance ends by ~1.1 s; then its delayed transitions are dropped
  function buildChart(host, n) {
    const N = sessions.length, id = 'oxa-proof-' + n;
    const per = floor <= 20 ? 1 : Math.ceil(floor / 10);   // basis points per block: one each, up to a 20 bps floor
    const nb = Math.ceil(floor / per), NG = 1;              // blocks up to the floor · ONE open block above it (the value above is not published)
    const fig = host.closest('[data-proof-fig]');
    if (fig) fig.hidden = false;
    host.textContent = '';                                   // the static fallback gives way to the chart
    host.classList.add('proof', 'is-built');
    const pf = h('div', 'pf');
    pf.style.setProperty('--cols', N); pf.style.setProperty('--n', nb); pf.style.setProperty('--ng', NG);

    // direct labels, in a gutter that shares the lanes' rows
    const gut = mute(h('div', 'pf-gut'));
    // .pf-ls: a short form for the narrowest gutter
    const lab = (cls, k, note, short) => {
      const e = h('span', 'pf-y ' + cls), b = h('b');
      if (short) b.append(h('span', 'pf-lw', k), h('span', 'pf-ls', short)); else b.textContent = k;
      e.append(b); if (note) e.append(h('small', null, note)); gut.append(e); return e;
    };
    lab('y-above', 'Above the floor', 'exact value not published'); // hc9: two lines, as the floor's and Note 09's
    lab('y-floor', 'Floor', floor + ' ' + unit + (per > 1 ? ' · 1 block = ' + per + ' bps' : ''));
    lab('y-zero', '0');
    lab('y-prem', 'Premium', null, 'Prem.').append(h('i', 'pf-n', String(C.premium)));
    lab('y-nav', 'NAV');
    lab('y-disc', 'Discount', null, 'Disc.').append(h('i', 'pf-n', String(C.discount)));
    lab('y-day', 'Day');
    lab('y-ok', 'Confirmed', null, 'Conf.');

    // the NAV regime as a trace between the two levels, one segment per session
    const Y = side => side > 0 ? 22 : side < 0 ? 78 : 50;
    const trace = sv('svg', { class: 'pf-trace', viewBox: '0 0 ' + N * 100 + ' 100', preserveAspectRatio: 'none', 'aria-hidden': 'true', focusable: 'false' });
    let risers = '';
    sessions.forEach((s, i) => { const nx = sessions[i + 1]; if (nx && nx.side !== s.side) risers += 'M' + (i + 1) * 100 + ' ' + Y(s.side) + 'V' + Y(nx.side); });
    // a faint wash between each segment and NAV
    const areas = sessions.map((s, i) => sv('rect', { x: i * 100, y: Math.min(Y(s.side), 50), width: 100, height: Math.abs(Y(s.side) - 50), class: 'pf-area' }));
    trace.append(...areas);
    if (risers) trace.append(sv('path', { d: risers, class: 'pf-riser', 'vector-effect': 'non-scaling-stroke' }));
    const segs = sessions.map((s, i) => sv('path', { d: 'M' + i * 100 + ' ' + Y(s.side) + 'H' + (i + 1) * 100, class: 'pf-seg', 'vector-effect': 'non-scaling-stroke' }));
    trace.append(...segs);

    // one lane per session: an option in a listbox, named by its record
    const box = h('div', 'pf-lanes');
    box.setAttribute('role', 'listbox');
    box.setAttribute('aria-orientation', 'horizontal');
    box.setAttribute('aria-label', (lifecycle ? lifecycle + ' sessions' : 'Sessions') + ' — choose one for its record');
    box.setAttribute('aria-describedby', id + '-sum');
    const lanes = sessions.map((s, i) => {
      const lane = h('div', 'pf-lane');
      lane.id = id + '-' + i; lane.tabIndex = i ? -1 : 0;
      lane.setAttribute('role', 'option'); lane.setAttribute('aria-selected', 'false');
      lane.dataset.side = String(s.side); lane.style.setProperty('--l', i);
      const g = mute(h('span', 'pf-g')), c = mute(h('span', 'pf-c'));
      const filled = s.above ? nb : Number.isFinite(s.amount) ? Math.max(0, Math.min(nb, Math.floor(s.amount / per))) : 0;
      for (let k = 0; k < nb; k++) { const b = h('i', k < filled ? null : 'is-void'); b.style.setProperty('--k', k); c.append(b); }
      if (s.above) for (let k = 0; k < NG; k++) { const b = h('i'); b.style.setProperty('--k', k); g.append(b); }
      else g.classList.add('is-none');
      const r = mute(h('span', 'pf-r')); r.append(h('i'));
      const ok = mute(h('span', 'pf-o'));
      if (s.confirmed && s.settled) { const t = sv('svg', { viewBox: '0 0 12 12', focusable: 'false' }); t.append(sv('path', { d: 'M2.4 6.5 5 9 9.7 3.3', pathLength: '1' })); ok.append(t); }
      else ok.append(h('i', 'pf-o-no'));
      lane.append(g, c, r, mute(h('span', 'pf-d', s.num)), ok,
        h('span', 'sr-only', s.day + ': ' + regimeSaid(s) + '; ' + valueSaid(s) + ' captured' + (s.above ? ', above the ' + floor + ' ' + unit + ' floor' : '') + '; ' + s.confirmation.toLowerCase() + '; ' + s.status.toLowerCase() + '.'));
      return lane;
    });
    box.append(...lanes);
    const plot = h('div', 'pf-plot');
    plot.append(trace, box);
    const body = h('div', 'pf-body');
    body.append(gut, plot, mute(h('i', 'pf-floor')), mute(h('i', 'pf-base')), mute(h('i', 'pf-nav')));

    const said = h('p', 'sr-only', summarySaid); said.id = id + '-sum';
    pf.append(body, said);
    host.append(pf);

    /* state: the session in hand (sel), the one under the pointer (pre), the lane that takes Tab (tab) */
    let sel = -1, pre = -1, tab = 0, shown = null;
    function render() {
      const i = pre >= 0 ? pre : sel;
      if (i === shown) return;
      shown = i;
      lanes.forEach((lane, j) => lane.classList.toggle('is-on', j === i));
      segs.forEach((p, j) => p.classList.toggle('is-on', j === i));
      areas.forEach((a, j) => a.classList.toggle('is-on', j === i));
      host.classList.toggle('has-on', i >= 0);
      host.dataset.side = i >= 0 ? String(sessions[i].side) : '';
    }
    function select(i) {
      sel = i;
      lanes.forEach((lane, j) => lane.setAttribute('aria-selected', String(j === i)));
      render();
    }
    function moveTab(j) { if (tab !== j) { lanes[tab].tabIndex = -1; tab = j; lanes[j].tabIndex = 0; } }
    let downAt = -1e9;
    box.addEventListener('pointerdown', () => { downAt = performance.now(); });
    const byKeyboard = lane => { try { return lane.matches(':focus-visible'); } catch (e) { return performance.now() - downAt > 600; } };
    lanes.forEach((lane, j) => {
      lane.addEventListener('focus', () => { moveTab(j); if (byKeyboard(lane)) select(j); }); // keyboard focus selects; a click does in its own handler
      lane.addEventListener('click', () => select(sel === j ? -1 : j));
      lane.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') { pre = j; render(); } });
    });
    box.addEventListener('pointerleave', () => { if (pre >= 0) { pre = -1; render(); } });
    box.addEventListener('keydown', e => {
      const j = lanes.indexOf(document.activeElement);
      if (j < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
      let to;
      if (e.key === 'ArrowRight') to = Math.min(N - 1, j + 1);
      else if (e.key === 'ArrowLeft') to = Math.max(0, j - 1);
      else if (e.key === 'Home') to = 0;
      else if (e.key === 'End') to = N - 1;
      else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(sel === j ? -1 : j); return; }
      else if (e.key === 'Escape') { if (sel >= 0) { e.preventDefault(); select(-1); } return; }
      else return;
      e.preventDefault();
      moveTab(to); lanes[to].focus(); select(to);
    });
    render();

    /* entrance once, when it is reached from above and a quarter of it is in view, or when it is in the first screen of a
       page opened at its top (Proof's hero, hc4); not under reduced motion. */
    let inView = false, seen = false;
    const away = () => host.classList.toggle('is-away', !inView);
    const whole = () => { // no entrance: the final state in one style change, with no transition on the way
      host.classList.add('pf-now'); host.classList.remove('is-armed'); host.classList.add('is-in');
      void host.offsetWidth;
      requestAnimationFrame(() => host.classList.remove('pf-now'));
    };
    if ('IntersectionObserver' in window && !reduce.matches) {
      host.classList.add('is-armed');
      new IntersectionObserver(entries => entries.forEach(e => {
        inView = e.isIntersecting;
        if (inView && !seen) {
          // reached from below (scrolling up, a reload mid-page) or already more than half in view, except in the first
          // screen of a page at its top, where the entrance is the page's opening
          const first = window.scrollY < 2 && e.boundingClientRect.top >= 0 && e.boundingClientRect.top < window.innerHeight * 0.75;
          if (!first && (e.boundingClientRect.top < 0 || e.intersectionRatio > 0.5)) { seen = true; whole(); }
          else if (e.intersectionRatio >= 0.24) {
            seen = true;
            host.classList.add('is-in');
            setTimeout(() => host.classList.remove('is-armed'), ENTRANCE_MS);
          }
        }
        away();
      }), { threshold: [0, 0.25, 0.5] }).observe(host);
    } else {
      host.classList.add('is-in');
      if ('IntersectionObserver' in window) new IntersectionObserver(entries => entries.forEach(e => { inView = e.isIntersecting; away(); })).observe(host);
    }
    if (reduce.addEventListener) reduce.addEventListener('change', () => { if (reduce.matches) host.classList.remove('is-armed'); host.classList.add('is-in'); });
  }

  document.querySelectorAll('[data-proof-chart]').forEach((host, i) => buildChart(host, i + 1));
})();

/* The cost figure (home §05 · Proof §02). (hc5, HC5 item 6) One reveal of at most 600 ms, both rows at once: the solid
   blocks first, in one sweep through both rows column by column (the Agentic row's survivors land with the Traditional
   blocks above them), then the outlines (what is eliminated and what shrank away). Each block's delay is set here (0-160 ms
   solid, 200-280 ms outlines) and proofchart.css gives it --dur-move (.32 s), so the last block is whole at ~600 ms after
   site.js reveals the rows. Under reduced motion, in print and on a jump, proofchart.css / site.css drop the transition
   (!important beats these inline delays): the final state at once. */
(function () {
  'use strict';
  const SOLID_MS = 160, OUTLINE_AT = 200, OUTLINE_MS = 80;
  const weight = el => parseFloat(el.style.getPropertyValue('--w'));
  const runsOf = bar => Array.from(bar.children).filter(e => e.tagName === 'I');
  document.querySelectorAll('[data-cost]').forEach(fig => {
    const bars = Array.from(fig.querySelectorAll('.cost-bar'));
    const base = bars.length ? runsOf(bars[0]).map(weight) : [];
    if (!base.length || base.some(v => !(v > 0)) || Math.abs(base.reduce((a, b) => a + b, 0) - 100) > 0.01) return;
    const plans = bars.map((bar, n) => {
      const out = [];
      let slot = 0, x = 0;
      for (const run of runsOf(bar)) {
        const v = weight(run), c = run.style.getPropertyValue('--c');
        if (!(v > 0)) return null;
        run.style.setProperty('--x', x + '%'); x += v;
        if (n === 0) { out.push({ n: v, solid: v, c }); slot++; }
        else if (run.classList.contains('cost-gone')) {
          let left = v;
          while (left > 0.01 && slot < base.length) left -= base[slot++];
          if (Math.abs(left) > 0.01) return null;
          out.push({ n: v, gone: true });
        } else {
          const place = parseFloat(run.style.getPropertyValue('--s')); // the place it states (the flat fallback keeps it)
          if (slot >= base.length || v > base[slot] + 0.01 || (place && Math.abs(place - base[slot]) > 0.01)) return null;
          out.push({ n: base[slot++], solid: v, c });
        }
      }
      return out;
    });
    if (plans.some(p => !p)) return;
    bars.forEach((bar, n) => {
      const grid = document.createElement('span');
      grid.className = 'cost-blk';
      grid.setAttribute('aria-hidden', 'true');
      let j = 0;
      plans[n].forEach(r => {
        for (let k = 0; k < Math.round(r.n); k++) {
          const b = document.createElement('i'), fill = r.solid - k;
          b.style.setProperty('--j', j++);
          if (r.gone) b.className = 'is-gone';
          else {
            b.style.setProperty('--c', r.c);
            if (fill <= 0) b.className = 'is-rest';
            else if (fill < 1) { b.className = 'is-part'; b.style.setProperty('--f', Math.round(fill * 100) + '%'); }
          }
          grid.append(b);
        }
      });
      // the reveal's order: solid by column (the same block index is the same column in both rows), then the outlines
      const all = Array.from(grid.children), outline = b => b.matches('.is-gone, .is-rest');
      const last = Math.max(1, all.length - 1), lastOut = Math.max(1, all.filter(outline).length - 1);
      let o = 0;
      all.forEach((b, i) => {
        b.style.transitionDelay = Math.round(outline(b) ? OUTLINE_AT + o++ * OUTLINE_MS / lastOut : i * SOLID_MS / last) + 'ms';
      });
      bar.append(grid);
      bar.classList.add('is-blocks');
    });
  });
})();
