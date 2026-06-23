/**
 * UI preferences — density, radius; syncs localStorage + server.
 */
(function () {
  'use strict';

  function csrf() {
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.content : '';
  }

  function persist(updates) {
    return fetch('/api/user/preferences', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify(updates),
    }).catch(function () {});
  }

  function applyDensity(value) {
    var v = value || 'normal';
    if (v === 'normal') {
      document.documentElement.removeAttribute('data-density');
    } else {
      document.documentElement.setAttribute('data-density', v);
    }
    try { localStorage.setItem('ui_density', v); } catch (e) {}
    if (window.__USER_PREFS__) window.__USER_PREFS__.density = v;
  }

  function applyRadius(value) {
    var v = value || 'md';
    if (v === 'md') {
      document.documentElement.removeAttribute('data-radius');
    } else {
      document.documentElement.setAttribute('data-radius', v);
    }
    try { localStorage.setItem('ui_radius', v); } catch (e) {}
    if (window.__USER_PREFS__) window.__USER_PREFS__.radius = v;
  }

  function bindSelect(id, applyFn, key) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', function () {
      var val = el.value;
      applyFn(val);
      var payload = {};
      payload[key] = val;
      persist(payload);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var prefs = window.__USER_PREFS__ || {};
    var densityEl = document.getElementById('uiDensitySelect');
    if (densityEl && prefs.density) densityEl.value = prefs.density;
    var radiusEl = document.getElementById('uiRadiusSelect');
    if (radiusEl && prefs.radius) radiusEl.value = prefs.radius;
    bindSelect('uiDensitySelect', applyDensity, 'density');
    bindSelect('uiRadiusSelect', applyRadius, 'radius');
  });

  window.UIPreferences = {
    applyDensity: applyDensity,
    applyRadius: applyRadius,
    persist: persist,
  };
})();
