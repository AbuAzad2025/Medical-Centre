/**
 * Client validation from window.__VALIDATION_RULES__ (G-83)
 */
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

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-validate]').forEach((input) => {
      input.addEventListener('blur', () => validateInput(input));
      input.addEventListener('input', () => {
        if (input.classList.contains('is-invalid')) validateInput(input);
      });
      if (input.dataset.validate === 'national_id') {
        input.addEventListener('input', () => {
          input.value = input.value.replace(/\D/g, '').slice(0, 9);
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
