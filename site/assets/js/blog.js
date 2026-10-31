/* OpenEXA — blog collections filter. Chips narrow the page to one collection; the hash keeps it linkable
   (/blog/#markets). Without JavaScript the chips are plain jump links and every collection shows. */
(function () {
  'use strict';
  const chips = Array.from(document.querySelectorAll('[data-blog-filter]'));
  const sections = Array.from(document.querySelectorAll('[data-blog-collection]'));
  if (!chips.length || !sections.length) return;
  const keys = sections.map(s => s.dataset.blogCollection);
  function apply(key, scroll) {
    const k = keys.includes(key) ? key : 'all';
    const shown = []; // lab blog-moment: only what the filter has just un-hidden is revealed at once
    sections.forEach(s => { const was = s.hidden; s.hidden = k !== 'all' && s.dataset.blogCollection !== k; if (was && !s.hidden) shown.push(s); });
    const series = document.querySelector('[data-blog-series]');
    if (series) { const was = series.hidden; series.hidden = !(k === 'all' || k === 'ai'); if (was && !series.hidden) shown.push(series); }
    chips.forEach(c => { if (c.dataset.blogFilter === k) c.setAttribute('aria-current', 'true'); else c.removeAttribute('aria-current'); });
    // keep the active chip visible in the horizontally scrolling row (phones) without moving the page
    const active = chips.find(c => c.dataset.blogFilter === k), row = active && active.parentElement;
    if (row && row.scrollWidth > row.clientWidth) row.scrollLeft += active.getBoundingClientRect().left - row.getBoundingClientRect().left - (row.clientWidth - active.offsetWidth) / 2;
    // revealed-on-scroll content inside a newly shown section must not stay hidden; the rest keeps arriving on scroll
    // (v2x forced every visible reveal in at load, so the series rail drew itself off-screen before anyone got there)
    shown.forEach(s => s.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('is-in')));
    if (scroll) {
      const bar = document.querySelector('.blog-chips-bar');
      const y = bar ? bar.getBoundingClientRect().top + window.scrollY - (parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--nav-h')) || 72) : 0;
      window.scrollTo({ top: Math.max(0, y), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
  }
  chips.forEach(c => c.addEventListener('click', e => {
    e.preventDefault();
    const k = c.dataset.blogFilter;
    history.replaceState(null, '', k === 'all' ? location.pathname : '#' + k);
    apply(k, true);
  }));
  window.addEventListener('hashchange', () => apply(location.hash.slice(1), false));
  apply(location.hash.slice(1), false);
})();
