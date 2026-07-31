/**
 * Command Center widget visibility — saves to User.preferences.dashboard.hidden_widgets
 */
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

  document.addEventListener('DOMContentLoaded', function () {
    var panel = document.getElementById('ccWidgetToggles');
    if (!panel) return;
    panel.addEventListener('change', function (e) {
      if (!e.target || !e.target.classList.contains('cc-widget-toggle')) return;
      var hidden = collectHidden();
      save(hidden).then(function () {
        window.location.reload();
      });
    });
  });
})();
