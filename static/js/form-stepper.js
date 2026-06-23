/**
 * Multi-step form UI — does not remove fields from DOM (G-20)
 */
(function () {
  'use strict';

  function initStepper(root) {
    const form = root.closest('form') || document.querySelector(root.dataset.stepperForm || '#visitForm');
    if (!form) return;

    const panels = form.querySelectorAll('.form-step-panel');
    if (!panels.length) return;

    const items = root.querySelectorAll('.form-stepper-item');
    const btnPrev = root.querySelector('[data-stepper-prev]');
    const btnNext = root.querySelector('[data-stepper-next]');
    let current = 0;

    function showStep(idx) {
      current = Math.max(0, Math.min(idx, panels.length - 1));
      panels.forEach((p, i) => {
        p.hidden = i !== current;
        p.classList.toggle('d-none', i !== current);
      });
      items.forEach((it, i) => it.classList.toggle('active', i === current));
      if (btnPrev) btnPrev.disabled = current === 0;
      if (btnNext) {
        btnNext.textContent = current === panels.length - 1 ? 'مراجعة' : 'التالي';
      }
    }

    root.querySelectorAll('[data-step-go]').forEach((btn) => {
      btn.addEventListener('click', () => showStep(parseInt(btn.dataset.stepGo, 10)));
    });

    if (btnPrev) btnPrev.addEventListener('click', () => showStep(current - 1));
    if (btnNext) btnNext.addEventListener('click', () => {
      if (current < panels.length - 1) showStep(current + 1);
    });

    showStep(0);
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-form-stepper]').forEach(initStepper);
  });
})();
