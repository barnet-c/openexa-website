/* OpenEXA — the lane: Lifecycle 01 drawn as one lane (home §03 Fig. 3.1, Lifecycles §03, Platform §04).
   The drawings are inline SVG and need no script. This only makes the gate list a legend you can work: hovering or
   focusing a gate (in the list or on the plate) lifts that gate and writes its role on one line; a click or tap pins it.
   Nothing here animates by itself, and nothing runs until someone points at a gate. */
(function () {
  'use strict';
  document.querySelectorAll('[data-lane]').forEach(fig => {
    const key = fig.querySelector('[data-lane-key]');
    const line = fig.querySelector('[data-lane-role]');
    if (!key) return;
    const items = [...key.querySelectorAll(':scope > li[data-g]')];
    let pinned = null;

    items.forEach(li => {
      const g = li.dataset.g, lk = li.querySelector('.lk'), role = li.querySelector('.lk-role');
      if (!lk) return;
      // the list item's label becomes a button: focusable, and a tap pins the gate on touch screens
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'lk-btn';
      b.setAttribute('aria-pressed', 'false');
      if (role && role.id) b.setAttribute('aria-describedby', role.id);
      b.append(...lk.childNodes);
      lk.replaceWith(b);
      b.addEventListener('pointerenter', () => show(g));
      b.addEventListener('pointerleave', () => show(pinned));
      b.addEventListener('focus', () => show(g));
      b.addEventListener('blur', () => show(pinned));
      b.addEventListener('click', () => {
        pinned = pinned === g ? null : g;
        items.forEach(o => { const ob = o.querySelector('.lk-btn'); if (ob) ob.setAttribute('aria-pressed', String(o.dataset.g === pinned)); });
        show(pinned || g);
      });
    });

    // the gates on the plate answer the pointer too
    fig.querySelectorAll('.lane-h [data-g]').forEach(el => {
      el.addEventListener('pointerenter', () => show(el.dataset.g));
      el.addEventListener('pointerleave', () => show(pinned));
    });

    function show(g) {
      if (g) fig.dataset.hot = g; else delete fig.dataset.hot;
      items.forEach(li => li.classList.toggle('is-hot', li.dataset.g === g));
      if (!line) return;
      const li = g && items.find(o => o.dataset.g === g);
      if (!li) { line.replaceChildren(); return; }
      const n = li.querySelector('.lk-n'), nm = li.querySelector('.lk-nm'), role = li.querySelector('.lk-role');
      const b = document.createElement('b');
      b.textContent = `${n ? n.textContent : ''} ${nm ? nm.textContent : ''}`.trim();
      const s = document.createElement('span');
      s.textContent = role ? role.textContent : '';
      line.replaceChildren(b, s);
    }

    fig.classList.add('is-on');
  });
})();
