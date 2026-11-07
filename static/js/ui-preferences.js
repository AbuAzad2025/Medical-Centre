'use strict';

export function csrf() {
  var m = document.querySelector('meta[name="csrf-token"]');
  return m ? m.content : '';
}

const ENDPOINT = (window.API_ROUTES && window.API_ROUTES.user_preferences) || '/api/user/preferences';

export function persist(updates) {
  return fetch(ENDPOINT, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-CSRFToken': csrf(),
    },
    body: JSON.stringify(updates),
  }).catch(function(){ if(window.showToast) window.showToast('تعذر حفظ التفضيلات','error'); });
}

export function applyDensity(value) {
  var v = value || 'normal';
  if (v === 'normal') {
    document.documentElement.removeAttribute('data-density');
  } else {
    document.documentElement.setAttribute('data-density', v);
  }
  try { localStorage.setItem('ui_density', v); } catch (e) {}
  if (window.__USER_PREFS__) window.__USER_PREFS__.density = v;
}

export function applyRadius(value) {
  var v = value || 'md';
  if (v === 'md') {
    document.documentElement.removeAttribute('data-radius');
  } else {
    document.documentElement.setAttribute('data-radius', v);
  }
  try { localStorage.setItem('ui_radius', v); } catch (e) {}
  if (window.__USER_PREFS__) window.__USER_PREFS__.radius = v;
}

export function bindSelect(id, applyFn, key) {
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

// Backward compatibility
if (typeof csrf !== 'undefined') window.csrf = csrf;
if (typeof persist !== 'undefined') window.persist = persist;
if (typeof applyDensity !== 'undefined') window.applyDensity = applyDensity;
if (typeof applyRadius !== 'undefined') window.applyRadius = applyRadius;
if (typeof bindSelect !== 'undefined') window.bindSelect = bindSelect;