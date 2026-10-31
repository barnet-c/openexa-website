/* OpenEXA — the Access page's request form (access.html; loaded after site.js).
   No backend: the visitor's own mail app sends the introduction (CSP form-action 'none'), or a configured endpoint
   (form[data-endpoint]) receives it. The mailto URL stays under 1,900 characters.
   v2x (30 Oct): the email is a short letter in the visitor's own words (not key: value lines), and the result panel
   shows it before they send it. The addressee is shown as "OpenEXA", never as the inbox address.
   lab (31 Oct): the letter is on the page from the start, beside the form, and writes itself as the visitor types: each
   blank fills with their words, the part they are typing is marked, a part left empty is drawn dashed (it will be left
   out), and a message too long for one email link says so before they press anything. On "Prepare request" it becomes
   the exact text of the draft. On phones the letter waits for the result panel (it moves there). Without JavaScript it
   is the letter's form with its blanks. */
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
  const SHORT = '… [shortened to fit an email link: paste the rest here]';

  /* ---------------- forms (no backend: mailto handoff or configured endpoint) ---------------- */
  $$('form[data-access]').forEach(form => {
    const result = $('.form-ok', form.parentElement);
    const endpoint = form.dataset.endpoint;
    const submit = $('button[type="submit"]', form);
    const submitLabel = $('[data-submit-label]', form);
    const errorBox = $('[data-form-error]', form);
    const note = $('[data-form-note]', form);
    const name = $('input[name="name"]', form);
    const tick = $('input[name="accredited"]', form);
    const letter = $('[data-letter]');
    const home = letter && letter.parentElement; // where the letter lives beside the form
    const letterBody = letter && $('[data-letter-body]', letter);
    const letterNote = $('[data-letter-note]');
    const narrow = window.matchMedia('(max-width: 600px)');
    if (!result || !submit || !errorBox) {
      console.error('OpenEXA introduction form is missing its result, submit or error element.');
      return;
    }
    if (endpoint) {
      if (submitLabel) submitLabel.textContent = 'Send introduction';
      if (note) note.textContent = 'Your introduction will be submitted to OpenEXA when you send it.';
      const col = letter && letter.closest('.access-letter');
      if (col) col.hidden = true; // the letter is the mailto's body; an endpoint receives the fields instead
    }

    /* the draft: a letter in a fixed order; an empty field leaves its part out; the attestation is the checkbox's own
       sentence, only when it is ticked; the whole mailto URL within 1,900 characters (Windows mail handlers cut longer
       ones, even mid-escape) */
    const attest = tick && tick.closest('label') ? tick.closest('label').textContent.replace(/\s+/g, ' ').trim() : '';
    const read = () => Object.fromEntries(Array.from(new FormData(form), ([key, value]) => [key, typeof value === 'string' ? value.trim() : value]));
    const head = data => `mailto:${CONTACT}?subject=${encodeURIComponent('OpenEXA introduction · ' + data.interest)}&body=`;
    const fits = (data, s) => (head(data) + encodeURIComponent(s)).length <= 1900;
    const bodyWith = (data, msg) => {
      const who = `I am ${data.name}${data.role ? ', ' + data.role : ''}${data.organization ? ' at ' + data.organization : ''}.`;
      const ask = ASK[data.interest] || `talk about ${data.interest}.`;
      const facts = [data.assets ? `Assets we are considering: ${data.assets}.` : '', data.accredited ? attest : ''].filter(Boolean).join('\r\n');
      return ['Hello OpenEXA,', `${who} I would like to ${ask}`, msg, facts, `Please reply to ${data.email}.`, data.name]
        .filter(Boolean).join('\r\n\r\n');
    };
    const cut = (data, text, wrap, mark) => { // longest whole-character prefix that fits, then the mark
      const ch = Array.from(text); let lo = 0, hi = ch.length;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (fits(data, wrap(ch.slice(0, mid).join('') + mark))) lo = mid; else hi = mid - 1; }
      return wrap(ch.slice(0, lo).join('') + mark);
    };
    const draft = data => {
      let body = bodyWith(data, data.message || '');
      if (!fits(data, body)) body = cut(data, data.message || '', m => bodyWith(data, m), SHORT);
      if (!fits(data, body)) body = cut(data, body, s => s, '…');
      return body;
    };

    /* the letter, live: the same order as the draft, with the visitor's words in place of each blank */
    const NOTE = letterNote ? letterNote.textContent : '';
    let focusKey = '';
    const live = () => {
      if (!letter || !letterBody || endpoint || letter.classList.contains('is-final')) return;
      const d = read();
      const t = s => letterBody.appendChild(document.createTextNode(s));
      const slot = (key, text, blank, optional) => {
        const sp = document.createElement('span');
        sp.className = 'slot' + (text ? ' is-filled' : optional ? ' is-opt' : '') + (key === focusKey ? ' is-here' : '');
        sp.dataset.slot = key; sp.textContent = text || blank; letterBody.appendChild(sp);
      };
      letterBody.textContent = '';
      t('Hello OpenEXA,\n\nI am '); slot('name', d.name, 'your name');
      if (d.role) { t(', '); slot('role', d.role); } else slot('role', '', ', your role', true);
      if (d.organization) { t(' at '); slot('organization', d.organization); } else slot('organization', '', ' at your organization', true);
      t('. I would like to '); slot('ask', ASK[d.interest] || `talk about ${d.interest}.`);
      t('\n\n'); slot('message', d.message, 'Your message, if you add one', true);
      t('\n\n');
      if (d.assets) { t('Assets we are considering: '); slot('assets', d.assets); t('.'); } else slot('assets', '', 'Assets we are considering: a range', true);
      t('\n'); slot('accredited', d.accredited ? attest : '', 'The attestation, if you tick it', true);
      t('\n\nPlease reply to '); slot('email', d.email, 'your work email'); t('.\n\n'); slot('name', d.name, 'your name');
      const subject = $('[data-letter-subject]', letter);
      if (subject) subject.textContent = 'OpenEXA introduction · ' + d.interest;
      if (letterNote) { // say so before they press anything: the link has room for about a page, not more
        const long = !!d.message && !fits(d, bodyWith(Object.assign({}, d, { name: d.name || 'x', email: d.email || 'x' }), d.message));
        letterNote.textContent = long ? 'Too long for one email link: the message will be shortened, with a note where to paste the rest.' : NOTE;
        letterNote.classList.toggle('is-long', long);
      }
    };
    const KEYS = { interest: 'ask', name: 'name', email: 'email', organization: 'organization', role: 'role', assets: 'assets', message: 'message', accredited: 'accredited' };
    // r2 (mobile): beside the form the letter's body scrolls inside when the screen is short (company.css); keep the part
    // being typed in view there, without moving the page (one read and one write, in the next frame)
    let keepFrame = 0;
    const keep = () => {
      if (!letterBody || keepFrame) return;
      keepFrame = requestAnimationFrame(() => {
        keepFrame = 0;
        const sp = focusKey && $('.slot.is-here', letterBody);
        if (!sp || letterBody.scrollHeight <= letterBody.clientHeight + 1) return;
        const b = letterBody.getBoundingClientRect(), r = sp.getBoundingClientRect(), pad = 12;
        if (r.bottom - r.top <= b.bottom - b.top - 2 * pad && r.top < b.top + pad) letterBody.scrollTop += r.top - b.top - pad;
        else if (r.bottom > b.bottom - pad) letterBody.scrollTop += r.bottom - b.bottom + pad; // a long message: its newest line
      });
    };
    const here = key => {
      focusKey = key || '';
      if (letterBody) $$('.slot', letterBody).forEach(sp => sp.classList.toggle('is-here', !!key && sp.dataset.slot === key));
      const subject = letter && $('[data-letter-subject]', letter); // choosing a path rewrites the subject line too
      if (subject) subject.classList.toggle('is-here', key === 'ask');
      keep();
    };
    form.addEventListener('input', () => { live(); keep(); });
    form.addEventListener('change', live);
    form.addEventListener('focusin', e => here(KEYS[e.target.name]));
    form.addEventListener('focusout', () => here(''));
    // the letter sits beside the form; on phones it waits for the result panel and appears there, above its buttons
    const place = () => {
      if (!letter || !home) return;
      const inPanel = result.classList.contains('show') && narrow.matches;
      const row = $('.row', result);
      if (inPanel && letter.parentElement !== result) result.insertBefore(letter, row);
      else if (!inPanel && letter.parentElement !== home) home.insertBefore(letter, letterNote && letterNote.parentElement === home ? letterNote : null);
    };
    narrow.addEventListener('change', place);

    // a target that is not drawn hands the landing to its choice. Measured after 'load': WebKit runs deferred scripts
    // before the stylesheets apply, when every box still exists (qa-webkit, 31 Oct)
    const land = (choice, radio) => { if (!choice.getClientRects().length) (radio.closest('.opt') || radio).scrollIntoView({ block: 'center', behavior: 'instant' }); };
    const choosePath = () => {
      const id = location.hash.slice(1);
      if (!id) return; // Firefox warns on getElementById('') (qa-firefox, 31 Oct)
      const choice = document.getElementById(id);
      if (!choice) return;
      // the target is a choice (#lifecycles, #managers, #partners, #investors), or anything that names one via data-interest
      const radio = form.contains(choice) ? $('input[type="radio"]', choice) : (choice.dataset.interest ? $(`input[type="radio"][value="${choice.dataset.interest}"]`, form) : null);
      if (radio) {
        radio.checked = true;
        if (document.readyState === 'complete') land(choice, radio); else window.addEventListener('load', () => land(choice, radio), { once: true });
      }
      live();
    };
    choosePath();
    live();
    window.addEventListener('hashchange', choosePath);
    if (name) name.addEventListener('input', () => name.setCustomValidity(''));
    // keyboard focus on the choices: WebKit stops matching :focus-visible after an arrow key moves the radio, so the
    // group marks keyboard use itself and company.css rings the focused choice (qa-webkit, 31 Oct)
    const seg = $('.seg', form);
    if (seg) { seg.addEventListener('keydown', () => seg.classList.add('is-kbd')); seg.addEventListener('pointerdown', () => seg.classList.remove('is-kbd')); }
    // an invalid field says so under itself (aria-invalid and a line it is described by), not only in the browser's
    // bubble, which goes on the next keystroke; the line clears as soon as the field is valid (lab company-editorial)
    $$('input:not([type="radio"]):not([type="checkbox"]), select, textarea', form).forEach(f => {
      if (!f.id) return;
      const say = text => {
        let m = document.getElementById(f.id + '-err');
        if (!m) {
          m = document.createElement('p'); m.className = 'f-err'; m.id = f.id + '-err';
          f.insertAdjacentElement('afterend', m);
          f.setAttribute('aria-describedby', ((f.getAttribute('aria-describedby') || '') + ' ' + m.id).trim());
        }
        m.textContent = text;
      };
      f.addEventListener('invalid', () => { f.setAttribute('aria-invalid', 'true'); say(f.validationMessage); });
      f.addEventListener('input', () => { if (f.hasAttribute('aria-invalid') && f.checkValidity()) { f.removeAttribute('aria-invalid'); say(''); } });
    });
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
      place();
      result.focus();
    };
    const edit = $('[data-form-edit]', result);
    if (edit) edit.addEventListener('click', () => {
      result.classList.remove('show');
      form.hidden = false;
      if (letter) { letter.classList.remove('is-final'); place(); live(); }
      if (letterNote) letterNote.hidden = false;
      if (name) name.focus();
    });
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (name) name.setCustomValidity(name.value.trim() ? '' : 'Please enter your name.');
      if (!form.reportValidity() || submit.disabled) return;
      errorBox.hidden = true;
      const data = read();
      if (!endpoint) {
        const mail = $('[data-mailto]', result);
        if (!mail) {
          console.error('OpenEXA introduction form has no email-draft link.');
          showError('The email draft could not be prepared. Please reload and try again.');
          return;
        }
        const body = draft(data);
        mail.href = head(data) + encodeURIComponent(body);
        if (letter) { // the letter becomes the draft, word for word
          const put = (sel, text) => { const el = $(sel, letter); if (el) el.textContent = text; };
          put('[data-letter-to]', 'OpenEXA');
          put('[data-letter-subject]', 'OpenEXA introduction · ' + data.interest);
          put('[data-letter-body]', body.replace(/\r\n/g, '\n'));
          letter.classList.add('is-final');
          letter.hidden = false;
          if (letterNote) letterNote.hidden = true;
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
