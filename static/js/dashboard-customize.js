(function () {
  'use strict';

  const ENDPOINT = (window.API_ROUTES && window.API_ROUTES.user_preferences) || '/api/user/preferences';

  function csrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : '';
  }

  function collectHidden() {
    var hidden = [];
    document.querySelectorAll('.cc-widget-toggle').forEach(function (cb) {
      if (!cb.checked) hidden.push(cb.value);
    });
    return hidden;
  }

  function save(hidden) {
  if (window.UIPreferences && window.UIPreferences.persist) {
      return window.UIPreferences.persist({ dashboard: { hidden_widgets: hidden } });
    }
    return fetch(ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify({ dashboard: { hidden_widgets: hidden } }),
    });
  }

  function toggleWidgetVisibility(hidden) {
    document.querySelectorAll('.cc-widget-toggle').forEach(function (cb) {
      var widget = document.querySelector('[data-widget="' + cb.value + '"]');
      if (widget) widget.style.display = cb.checked ? '' : 'none';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.getElementById('ccWidgetToggles');
    if (!panel) return;
    panel.addEventListener('change', function (e) {
      if (!e.target || !e.target.classList.contains('cc-widget-toggle')) return;
      var hidden = collectHidden();
      toggleWidgetVisibility(hidden);
      save(hidden)
        .then(function () {
          if (window.notifications) window.notifications.show('تم حفظ التفضيلات', 'success');
        })
        .catch(function () {
          if (window.notifications) window.notifications.show('فشل حفظ التفضيلات', 'error');
        });
    });
  });
})();
