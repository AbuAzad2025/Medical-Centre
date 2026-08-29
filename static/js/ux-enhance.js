(function () {
  'use strict';

  function injectProgressBar() {
    if (document.getElementById('__uxProgressBar')) return;
    var bar = document.createElement('div');
    bar.id = '__uxProgressBar';
    bar.innerHTML =
      '<div class="__ux-bar" style="' +
      'position:fixed;top:0;left:0;right:0;height:3px;z-index:99999;' +
      'background:linear-gradient(90deg,var(--color-primary,#0f4c81),var(--color-info,#0ea5e9));' +
      'width:0%;transition:width .3s ease;pointer-events:none;' +
      'box-shadow:0 0 8px rgba(15,76,129,.4)"></div>';
    document.body.appendChild(bar);
  }

  function startProgress() {
    injectProgressBar();
    var bar = document.querySelector('#__uxProgressBar .__ux-bar');
    if (!bar) return;
    bar.style.width = '0%';
    bar.style.opacity = '1';

    setTimeout(function () { bar.style.width = '30%'; }, 100);
    setTimeout(function () { bar.style.width = '60%'; }, 800);
    setTimeout(function () { bar.style.width = '80%'; }, 1800);
  }

  function stopProgress() {
    var bar = document.querySelector('#__uxProgressBar .__ux-bar');
    if (!bar) return;
    bar.style.width = '100%';
    setTimeout(function () {
      bar.style.opacity = '0';
      bar.style.transition = 'opacity .4s ease';
    }, 300);
  }

  function showFieldErrors(form, errors) {
    if (!errors || typeof errors !== 'object') return false;
    var shown = false;

    Object.keys(errors).forEach(function (fieldName) {
      var msg = errors[fieldName];
      if (typeof msg !== 'string') {
        if (Array.isArray(msg)) msg = msg.join('. ');
        else return;
      }

      var input = form.querySelector(
        '[name="' + fieldName + '"], [name="' + fieldName + '_modal"], '
        + '[name="' + fieldName + '_edit"], #' + fieldName
      );
      if (!input) return;

      input.classList.add('is-invalid');
      input.setAttribute('aria-invalid', 'true');

      var feedback = input.parentElement.querySelector('.invalid-feedback')
        || form.querySelector('[data-error-for="' + fieldName + '"]');
      if (!feedback) {
        feedback = document.createElement('div');
        feedback.className = 'invalid-feedback d-block';
        input.insertAdjacentElement('afterend', feedback);
      }
      feedback.textContent = msg;
      shown = true;
    });

    if (shown) {
      var firstInvalid = form.querySelector('.is-invalid');
      if (firstInvalid) firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    return shown;
  }

  function scrollToErrors() {
    var errorFlash = document.querySelector(
      '.flash-error, .alert-danger, .alert-error, [class*="flash-error"]'
    );
    if (errorFlash) {
      errorFlash.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {

      var successFlash = document.querySelector('.flash-success, .alert-success');
      if (successFlash) window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {

    scrollToErrors();

    document.querySelectorAll('form').forEach(function (form) {
      var method = (form.getAttribute('method') || '').toUpperCase();
      if (method !== 'POST' && !form.hasAttribute('data-validate-form')) return;

      form.addEventListener('submit', function () {
        startProgress();

        if (form.hasAttribute('data-ajax') || form.dataset.ajaxForm === '1') return;

        setTimeout(stopProgress, 5000);
      });
    });

    if (window.fetch && !window.__uxFetchPatched) {
      window.__uxFetchPatched = true;
      var _origFetch = window.fetch;
      window.fetch = function () {
        startProgress();
        return _origFetch.apply(this, arguments).then(function (response) {
          stopProgress();
          return response;
        }).catch(function (err) {
          stopProgress();
          throw err;
        });
      };
    }
  });

  window.UXEnhance = {
    showFieldErrors: showFieldErrors,
    startProgress: startProgress,
    stopProgress: stopProgress
  };
})();
