(function () {
  'use strict';

  const rules = window.__VALIDATION_RULES__ || {};

  function validateValue(ruleKey, value) {
    const rule = rules[ruleKey];
    if (!rule) return null;
    const v = (value || '').trim();
    if (!v) return null;
    if (rule.min_length && v.length < rule.min_length) return rule.message_ar;
    if (rule.max_length && v.length > rule.max_length) return rule.message_ar;
    if (rule.pattern) {
      try {
        const re = new RegExp(rule.pattern);
        if (!re.test(v)) return rule.message_ar;
      } catch (e) {
        return null;
      }
    }
    return null;
  }

  function setFieldState(input, message) {
    const feedback = input.parentElement.querySelector('.invalid-feedback')
      || document.querySelector(`[data-error-for="${input.name || input.id}"]`);
    if (message) {
      input.classList.add('is-invalid');
      input.setAttribute('aria-invalid', 'true');
      if (feedback) feedback.textContent = message;
    } else {
      input.classList.remove('is-invalid');
      input.removeAttribute('aria-invalid');
      if (feedback) feedback.textContent = '';
    }
    return !message;
  }

  function validateInput(input) {
    const key = input.dataset.validate;
    if (!key) return true;
    return setFieldState(input, validateValue(key, input.value));
  }

  function preventDoubleSubmit(form) {
    form.addEventListener('submit', function (e) {
      if (form.dataset.submitting === '1') {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }
      form.dataset.submitting = '1';
      form.querySelectorAll('[type="submit"]').forEach(function (btn) {
        btn.disabled = true;
        btn._origHtml = btn.innerHTML;
        btn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>'
          + (btn.textContent.trim() || '\u062c\u0627\u0631\u064a \u0627\u0644\u062d\u0641\u0638...');
      });
    });

    window.addEventListener('pageshow', function () {
      delete form.dataset.submitting;
      form.querySelectorAll('[type="submit"]').forEach(function (btn) {
        if (btn.disabled && btn._origHtml !== undefined) {
          btn.disabled = false;
          btn.innerHTML = btn._origHtml;
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', () => {

    document.querySelectorAll('form[method="POST"], form[method="post"]').forEach(preventDoubleSubmit);

    const GLOBAL_MAXLENGTH = {
      phone: 20, national_id: 32, email: 120, username: 80,
      first_name: 200, last_name: 200, full_name: 120,
      card_last_digits: 4, insurance_number: 50,
      trade_name: 200, scientific_name: 200,
      emergency_contact_phone: 20, passport_number: 20,
      address: 500, insurance_policy_number: 60,
    };
    document.querySelectorAll('input[type="text"], input[type="tel"], input[type="email"]').forEach(function (input) {
      var name = input.name || '';
      var baseName = name.replace(/_(modal|edit|new)$/, '');
      var maxlen = GLOBAL_MAXLENGTH[baseName];
      if (maxlen && !input.hasAttribute('maxlength')) {
        input.setAttribute('maxlength', maxlen);
      }
    });

    document.querySelectorAll(
      'input[type="text"]:not([dir]), input[type="search"]:not([dir]), textarea:not([dir])'
    ).forEach(function (el) {
      el.setAttribute('dir', 'auto');
    });

    document.querySelectorAll('[data-validate]').forEach((input) => {
      input.addEventListener('blur', () => validateInput(input));
      input.addEventListener('input', () => {
        if (input.classList.contains('is-invalid')) validateInput(input);
      });
      if (input.dataset.validate === 'national_id') {
        input.addEventListener('input', () => {
          input.value = input.value.replace(/\D/g, '').slice(0, 20);
        });
      }
    });

    document.querySelectorAll('form[data-validate-form]').forEach((form) => {
      form.addEventListener('submit', (e) => {
        let ok = true;
        let firstBad = null;
        form.querySelectorAll('[data-validate]').forEach((input) => {
          if (!validateInput(input)) {
            ok = false;
            if (!firstBad) firstBad = input;
          }
        });
        if (!ok) {
          e.preventDefault();
          form.classList.add('was-validated');
          if (firstBad) firstBad.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      });
    });
  });

  window.FormValidation = { validateValue, validateInput, setFieldState };
})();
