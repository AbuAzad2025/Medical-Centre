/**
 * Tom Select wrapper — data-smart-select (G-82)
 */
(function () {
  'use strict';

  function initSmartSelect(el) {
    if (!window.TomSelect || el.tomselect) return el.tomselect;
    const opts = {
      plugins: el.multiple ? ['remove_button'] : ['dropdown_input', 'clear_button'],
      maxOptions: parseInt(el.dataset.maxOptions || '50', 10),
      allowEmptyOption: true,
      create: false,
      direction: 'rtl',
      render: {
        no_results: () => '<div class="no-results px-2 py-1">لا توجد نتائج</div>',
      },
    };
    if (el.dataset.placeholder) opts.placeholder = el.dataset.placeholder;
    el.tomselect = new TomSelect(el, opts);
    return el.tomselect;
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-smart-select]').forEach(initSmartSelect);
  });

  window.initSmartSelect = initSmartSelect;
  window.initSmartSelectAll = (root) => {
    (root || document).querySelectorAll('[data-smart-select]').forEach(initSmartSelect);
  };
})();
