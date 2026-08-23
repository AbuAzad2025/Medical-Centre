/**
 * Accessibility: Focus trap for Bootstrap modals.
 * Ensures Tab/Shift+Tab cycle within the modal instead of escaping to
 * background content. Auto-cleans on modal hide.
 *
 * Usage: automatic — applies to every .modal.show element via MutationObserver.
 */
(function () {
  'use strict';

  var FOCUSABLE = 'a[href], area[href], input:not([disabled]):not([type="hidden"]), '
    + 'select:not([disabled]), textarea:not([disabled]), button:not([disabled]), '
    + 'iframe, object, embed, [tabindex]:not([tabindex="-1"]), [contenteditable]';

  function trapFocus(modal) {
    var focusables = modal.querySelectorAll(FOCUSABLE);
    if (!focusables.length) return;
    var first = focusables[0];
    var last = focusables[focusables.length - 1];

    function handler(e) {
      if (e.key !== 'Tab') return;
      // Re-query in case DOM changed since open
      var items = modal.querySelectorAll(FOCUSABLE);
      if (!items.length) return;
      var cur = document.activeElement;
      var firstItem = items[0];
      var lastItem = items[items.length - 1];

      if (e.shiftKey) {
        if (cur === firstItem || !modal.contains(cur)) {
          e.preventDefault();
          lastItem.focus();
        }
      } else {
        if (cur === lastItem || !modal.contains(cur)) {
          e.preventDefault();
          firstItem.focus();
        }
      }
    }

    modal.addEventListener('keydown', handler);
    modal.addEventListener('hidden.bs.modal', function () {
      modal.removeEventListener('keydown', handler);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Watch for modals being shown dynamically
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          var modals = node.classList && node.classList.contains('modal')
            ? [node]
            : Array.from(node.querySelectorAll ? node.querySelectorAll('.modal') : []);
          modals.forEach(function (m2) {
            m2.addEventListener('shown.bs.modal', function () { trapFocus(m2); });
          });
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Also handle existing modals
    document.querySelectorAll('.modal').forEach(function (m) {
      m.addEventListener('shown.bs.modal', function () { trapFocus(m); });
    });
  });
})();
