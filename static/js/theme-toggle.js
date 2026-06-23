/**
 * Theme toggle — navbar button; syncs localStorage + server preferences.
 */
(function () {
  'use strict';

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    var next = theme === 'dark' ? 'dark' : 'light';
    if (next === 'light') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
    try { localStorage.setItem('theme', next); } catch (e) {}
    updateIcon(next);
  }

  function updateIcon(theme) {
    var icon = document.querySelector('[data-theme-icon]');
    if (!icon) return;
    icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
  }

  function persist(theme) {
    var token = document.querySelector('meta[name="csrf-token"]');
    fetch('/api/user/preferences', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': token ? token.content : '',
      },
      body: JSON.stringify({ theme: theme }),
    }).catch(function () {});
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
})();
