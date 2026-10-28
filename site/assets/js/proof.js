/* OpenEXA — proof: the Lifecycle 01 performance report (home §04 · Proof §01)

   One record per page: <script type="application/json" id="oxa-sessions">
     { "lifecycle": "...", "unit": "bps", "floor": 10,
       "sessions": [ { "day": "Day 01", "regime": "Discount", "value": ">10", "confirmation": "Broker confirmation", "status": "Settled" }, ... ] }
   Everything on the page that describes the sessions is drawn or counted from that record:
     [data-proof-chart]  the session chart (it replaces its static fallback; a [data-proof-fig] wrapper is un-hidden)
     [data-proof-table]  a table of the sessions: rows rebuilt from the record, linked to the chart on hover
     [data-proof="k"]    a derived count, k = total · above · premium · discount · confirmed · settled · floor, or "regimes"
                         (the sentence "Five premium, five discount."); data-proof-as="words" | "Words" spells it out. It is
                         written once, final: no count-up, so every frame, screen reader and in-page search reads the record.
   The static HTML says the same thing for readers without JavaScript. Nothing is invented: a value is drawn only as the
   record states it (">10" = above the floor, exact value not published) and a missing field reads "Not stated".
   The chart: one column per session, one block per basis point up to the floor and open blocks above it; the NAV regime
   as a trace above or below the NAV line; a tick where the broker confirmed and the session settled. Hover, focus or tap
   a session for its record in the inspector; Left / Right / Home / End move between sessions, Enter or a second tap
   lets go, Esc returns to the summary. Reduced motion: no entrance, no idle motion; idle motion also stops off-screen and
   in hidden tabs. No WebGL, no canvas: plain DOM that stays crisp at any pixel ratio and prints. */
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
  const valueText = s => !s.value ? NOT : Number.isFinite(s.amount) ? s.value.replace(/\s+/g, '') + ' ' + unit : s.value;
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
  const charts = [], tables = [];
  const hot = i => tables.forEach(t => t.hot(i));
  const preview = i => charts.forEach(c => c.preview(i));
  const sameValue = sessions.every(s => s.value === sessions[0].value);
  const SUMMARY = [
    ['All ' + C.total, lifecycle || 'sessions'],
    [C.premium + ' · ' + C.discount, 'premium · discount'],
    [sameValue ? valueText(sessions[0]) : 'Varies', C.above === C.total ? 'in every session' : C.above + ' of ' + C.total + ' above the floor'],
    [C.confirmed + ' of ' + C.total, 'broker-confirmed'],
    [C.settled + ' of ' + C.total, 'settled']
  ];
  const recordOf = (s, i) => [
    [s.day, (i + 1) + ' of ' + C.total],
    [s.regime, s.side > 0 ? 'price above NAV' : s.side < 0 ? 'price below NAV' : ''],
    [valueText(s), s.above ? 'above the floor' : Number.isFinite(s.amount) ? 'not above the floor' : ''],
    [s.confirmation, ''],
    [s.status, '']
  ];
  const summarySaid = cap(words(C.total)) + ' sessions' + (lifecycle ? ' of ' + lifecycle : '') + ': ' +
    (C.above === C.total ? 'all' : words(C.above) + ' of ' + words(C.total)) + ' above the ' + floor + ' ' + unit + ' floor, exact values above it not published. ' +
    cap(words(C.premium)) + ' in a premium regime, price above NAV; ' + words(C.discount) + ' in a discount regime, price below NAV. ' +
    cap(words(C.confirmed)) + ' of ' + words(C.total) + ' confirmed by the broker; ' + words(C.settled) + ' settled.';

  /* ---------------- the evidence table: rows from the record, linked to the chart ---------------- */
  function buildTable(table) {
    let tb = table.tBodies[0];
    if (!tb) { tb = h('tbody'); table.append(tb); }
    // each cell names its column (data-th): on phones the rows restack and the cells carry their own labels
    const head = table.tHead && table.tHead.rows[0] ? Array.from(table.tHead.rows[0].cells, c => c.textContent.trim()) : [];
    const TH = ['Session', 'NAV regime', 'Captured', 'Verification', 'Status'].map((k, j) => head[j] || k);
    const rows = sessions.map((s, i) => {
      const tr = h('tr');
      const td = (cls, ...kids) => { const c = h('td', cls); c.dataset.th = TH[tr.cells.length]; c.append(...kids); tr.append(c); };
      const mini = mute(h('i', 'pf-mini')); mini.dataset.side = String(s.side);
      td('lab', s.day); td(null, mini, s.regime); td('num', valueText(s)); td(null, s.confirmation);
      td(null, h('span', 'tag' + (s.settled ? ' on' : ''), s.status));
      tr.addEventListener('pointerenter', e => { if (e.pointerType !== 'touch') preview(i); });
      return tr;
    });
    tb.replaceChildren(...rows);
    tb.addEventListener('pointerleave', () => preview(-1));
    tables.push({ hot: i => rows.forEach((tr, j) => tr.classList.toggle('is-hot', j === i)) });
  }

  /* ---------------- the chart ---------------- */
  const ENTRANCE_MS = 1400; // the CSS entrance ends by ~1.1 s; then its delayed transitions are dropped
  function buildChart(host, n) {
    const N = sessions.length, id = 'oxa-proof-' + n;
    const per = floor <= 20 ? 1 : Math.ceil(floor / 10);   // basis points per block: one each, up to a 20 bps floor
    const nb = Math.ceil(floor / per), NG = 4;              // blocks up to the floor · open blocks above it
    const fig = host.closest('[data-proof-fig]');
    if (fig) fig.hidden = false;
    host.textContent = '';                                   // the static fallback gives way to the chart
    host.classList.add('proof', 'is-built');
    const pf = h('div', 'pf');
    pf.style.setProperty('--cols', N); pf.style.setProperty('--n', nb); pf.style.setProperty('--ng', NG);

    // direct labels, in a gutter that shares the lanes' rows
    const gut = mute(h('div', 'pf-gut'));
    // a long label carries a short form too (.pf-ls), shown only where the gutter is narrowest (phones under ~340 px)
    const lab = (cls, k, note, short) => {
      const e = h('span', 'pf-y ' + cls), b = h('b');
      if (short) b.append(h('span', 'pf-lw', k), h('span', 'pf-ls', short)); else b.textContent = k;
      e.append(b); if (note) e.append(h('small', null, note)); gut.append(e); return e;
    };
    lab('y-above', 'Above', 'exact value not published');
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
    // a faint wash between each segment and NAV: the side of the NAV reads at a glance
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

    // the inspector: the summary, or the record of the session in hand
    const read = mute(h('div', 'pf-read'));
    const bracket = h('i', 'pf-bracket');
    const cells = h('div', 'pf-cells');
    const out = ['Session', 'NAV regime', 'Captured', 'Verification', 'Status'].map(k => {
      const cell = h('div', 'pf-cell'), v = h('span', 'pf-v'), note = h('span', 'pf-s');
      cell.append(h('span', 'pf-k', k), v, note); cells.append(cell); return { v, note };
    });
    read.append(bracket, cells);
    const said = h('p', 'sr-only', summarySaid); said.id = id + '-sum';
    pf.append(body, read, said);
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
      bracket.style.setProperty('--i', i >= 0 ? i : 0);
      bracket.style.setProperty('--span', i >= 0 ? 1 : N);
      const vals = i >= 0 ? recordOf(sessions[i], i) : SUMMARY;
      out.forEach((o, k) => {
        const v = vals[k][0], note = vals[k][1] || ' ';
        if (o.v.textContent === v && o.note.textContent === note) return;
        o.v.textContent = v; o.note.textContent = note;
        if (!reduce.matches && o.v.animate && host.classList.contains('is-in')) {
          o.v.animate([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 280, easing: 'cubic-bezier(.2,.7,.2,1)' });
        }
      });
      hot(i);
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

    /* entrance once, when it is reached from above and a quarter of it is in view (not under reduced motion); idle
       motion only while visible */
    let inView = false, seen = false;
    const live = () => host.classList.toggle('is-live', inView && !document.hidden && !reduce.matches);
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
          // reached from below (scrolling up, a reload mid-page) or already more than half in view (a jump, a deep link):
          // rows that wait their turn would be blank frames, so the chart is shown whole
          if (e.boundingClientRect.top < 0 || e.intersectionRatio > 0.5) { seen = true; whole(); }
          else if (e.intersectionRatio >= 0.24) {
            seen = true;
            host.classList.add('is-in');
            setTimeout(() => host.classList.remove('is-armed'), ENTRANCE_MS);
          }
        }
        live();
      }), { threshold: [0, 0.25, 0.5] }).observe(host);
    } else {
      host.classList.add('is-in');
      if ('IntersectionObserver' in window) new IntersectionObserver(entries => entries.forEach(e => { inView = e.isIntersecting; live(); })).observe(host);
    }
    document.addEventListener('visibilitychange', live);
    if (reduce.addEventListener) reduce.addEventListener('change', () => { if (reduce.matches) host.classList.remove('is-armed'); host.classList.add('is-in'); live(); });
    charts.push({ preview: i => { pre = i; render(); } });
  }

  document.querySelectorAll('table[data-proof-table]').forEach(buildTable);
  document.querySelectorAll('[data-proof-chart]').forEach((host, i) => buildChart(host, i + 1));
})();
