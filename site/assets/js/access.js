/* OpenEXA — the Access page's request form (access.html; loaded after site.js).
   No backend: the visitor's own mail app sends the introduction (CSP form-action 'none'), or a configured endpoint
   (form[data-endpoint]) receives it. The mailto URL stays under 1,900 characters.
   v2x (30 Oct): the email is a short letter in the visitor's own words (not key: value lines), and the result panel
   shows it before they send it. The addressee is shown as "OpenEXA", never as the inbox address. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const CONTACT = document.body.dataset.contact || 'access@openexa.com'; // the inbox: data-contact on <body>
  // what each path asks for, in the path's own words on the page (PAGES A-08); D stays neutral on purpose
  const ASK = {
    'Bring a lifecycle': 'bring a lifecycle to OpenEXA and scope it against the six traits.',
    'Manager platform': 'talk about deploying our own agents on OpenEXA’s eight layers.',
    'Platform partnership': 'talk about connecting a rail, a feed or a channel to a lifecycle.',
    'Qualified investor': 'talk about the qualified-investor path for Lifecycle 01.',
  };

  /* ---------------- forms (no backend: mailto handoff or configured endpoint) ---------------- */
  $$('form[data-access]').forEach(form => {
    const result = $('.form-ok', form.parentElement);
    const endpoint = form.dataset.endpoint;
    const submit = $('button[type="submit"]', form);
    const submitLabel = $('[data-submit-label]', form);
    const errorBox = $('[data-form-error]', form);
    const note = $('[data-form-note]', form);
    const name = $('input[name="name"]', form);
    if (!result || !submit || !errorBox) {
      console.error('OpenEXA introduction form is missing its result, submit or error element.');
      return;
    }
    if (endpoint) {
      if (submitLabel) submitLabel.textContent = 'Send introduction';
      if (note) note.textContent = 'Your introduction will be submitted to OpenEXA when you send it.';
    }
    const choosePath = () => {
      const choice = document.getElementById(location.hash.slice(1));
      if (!choice) return;
      // the target may be a form option, or a description elsewhere on the page that names its option via data-interest
      const radio = form.contains(choice) ? $('input[type="radio"]', choice) : (choice.dataset.interest ? $(`input[type="radio"][value="${choice.dataset.interest}"]`, form) : null);
      if (radio) radio.checked = true;
      // on phones the path list folds into the choices: a link to a path lands on its choice instead
      if (radio && !choice.getClientRects().length) (radio.closest('.opt') || radio).scrollIntoView({ block: 'center' });
    };
    choosePath();
    window.addEventListener('hashchange', choosePath);
    if (name) name.addEventListener('input', () => name.setCustomValidity(''));
    const showError = message => {
      errorBox.textContent = message;
      errorBox.hidden = false;
    };
    const showResult = sent => {
      const heading = $('[data-result-title]', result);
      const body = $('[data-result-body]', result);
      const mail = $('[data-mailto]', result);
      if (heading) heading.textContent = sent ? 'Introduction submitted.' : 'Your draft is ready.';
      if (body) body.textContent = sent
        ? 'Your introduction was accepted. You can return to the platform or edit your details to prepare another request.'
        : 'Open it in your email app, review it and press send. Preparing the draft has not submitted your details to OpenEXA.';
      if (mail) mail.hidden = sent;
      if (letter && sent) letter.hidden = true;
      form.hidden = true;
      result.classList.add('show');
      result.focus();
    };
    const letter = $('[data-letter]', result);
    const edit = $('[data-form-edit]', result);
    if (edit) edit.addEventListener('click', () => {
      result.classList.remove('show');
      form.hidden = false;
      if (name) name.focus();
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (name) name.setCustomValidity(name.value.trim() ? '' : 'Please enter your name.');
      if (!form.reportValidity() || submit.disabled) return;
      errorBox.hidden = true;
      const data = Object.fromEntries(Array.from(new FormData(form), ([key, value]) => [key, typeof value === 'string' ? value.trim() : value]));
      if (!endpoint) {
        const mail = $('[data-mailto]', result);
        if (!mail) {
          console.error('OpenEXA introduction form has no email-draft link.');
          showError('The email draft could not be prepared. Please reload and try again.');
          return;
        }
        // Windows mail handlers cut mailto URLs past ~2,000 characters, even mid-escape
        const head = `mailto:${CONTACT}?subject=${encodeURIComponent('OpenEXA introduction - ' + data.interest)}&body=`;
        const fits = s => (head + encodeURIComponent(s)).length <= 1900;
        // the letter: paragraphs in a fixed order; an empty field leaves its part out; the attestation is the
        // checkbox's own sentence, only when it is ticked
        const tick = $('input[name="accredited"]', form);
        const attest = tick && tick.closest('label') ? tick.closest('label').textContent.replace(/\s+/g, ' ').trim() : '';
        const bodyWith = msg => {
          const who = `I am ${data.name}${data.role ? ', ' + data.role : ''}${data.organization ? ' at ' + data.organization : ''}.`;
          const ask = ASK[data.interest] || `talk about ${data.interest}.`;
          const facts = [data.assets ? `Assets we are considering: ${data.assets}.` : '', data.accredited ? attest : ''].filter(Boolean).join('\r\n');
          return ['Hello OpenEXA,', `${who} I would like to ${ask}`, msg, facts, `Please reply to ${data.email}.`, data.name]
            .filter(Boolean).join('\r\n\r\n');
        };
        const cut = (text, wrap, mark) => { // longest whole-character prefix that fits, then the mark
          const ch = Array.from(text); let lo = 0, hi = ch.length;
          while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (fits(wrap(ch.slice(0, mid).join('') + mark))) lo = mid; else hi = mid - 1; }
          return wrap(ch.slice(0, lo).join('') + mark);
        };
        let body = bodyWith(data.message || '');
        if (!fits(body)) body = cut(data.message || '', bodyWith, '… [shortened to fit an email link: paste the rest here]');
        if (!fits(body)) body = cut(body, s => s, '…');
        mail.href = head + encodeURIComponent(body);
        if (letter) {
          const put = (sel, text) => { const el = $(sel, letter); if (el) el.textContent = text; };
          put('[data-letter-to]', 'OpenEXA');
          put('[data-letter-subject]', 'OpenEXA introduction - ' + data.interest);
          put('[data-letter-body]', body.replace(/\r\n/g, '\n'));
          letter.hidden = false;
        }
        showResult(false);
        return;
      }
      submit.disabled = true;
      form.setAttribute('aria-busy', 'true');
      if (submitLabel) submitLabel.textContent = 'Sending...';
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      let response;
      try {
        response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data), signal: controller.signal });
      } catch (error) {
        if (error instanceof TypeError || (error instanceof DOMException && error.name === 'AbortError')) {
          showError(controller.signal.aborted ? 'The request timed out. Your details are still here; please try again.' : 'The request could not reach OpenEXA. Check your connection and try again.');
          return;
        }
        throw error;
      } finally {
        clearTimeout(timeout);
        submit.disabled = false;
        form.removeAttribute('aria-busy');
        if (submitLabel) submitLabel.textContent = 'Send introduction';
      }
      if (!response.ok) {
        showError(`Your introduction was not accepted (HTTP ${response.status}). Your details are still here; please try again.`);
        return;
      }
      showResult(true);
    });
  });
})();
