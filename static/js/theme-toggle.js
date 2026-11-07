'use strict';

export function currentTheme() {
  return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}

export function applyTheme(theme) {
  var next = theme === 'dark' ? 'dark' : 'light';
  if (next === 'light') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  try { localStorage.setItem('theme', next); } catch (e) {}
  updateIcon(next);
}

export function updateIcon(theme) {
  var icon = document.querySelector('[data-theme-icon]');
  if (!icon) return;
  icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
}

export function persist(theme) {
  var token = document.querySelector('meta[name="csrf-token"]');
  var endpoint = (window.API_ROUTES && window.API_ROUTES.user_preferences) || '/api/user/preferences';
  fetch(endpoint, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'X-CSRFToken': token ? token.content : '',
    },
    body: JSON.stringify({ theme: theme }),
  }).catch(function(){ if(window.showToast) window.showToast('تعذر حفظ المظهر','error'); });
}

document.addEventListener('DOMContentLoaded', function () {
  var btn = document.getElementById('themeToggleBtn');
  if (!btn) return;
  updateIcon(currentTheme());
  btn.addEventListener('click', function () {
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    persist(next);
  });
});

// Backward compatibility
if (typeof currentTheme !== 'undefined') window.currentTheme = currentTheme;
if (typeof applyTheme !== 'undefined') window.applyTheme = applyTheme;
if (typeof updateIcon !== 'undefined') window.updateIcon = updateIcon;
if (typeof persist !== 'undefined') window.persist = persist;