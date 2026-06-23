/**
 * Smart patient/staff search — debounced dropdown (G-81)
 */
(function () {
  'use strict';

  function debounce(fn, ms) {
    let t;
    return function (...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function initSmartSearch(root) {
    const api = root.dataset.api || '/api/search/patients';
    const minChars = parseInt(root.dataset.min || '2', 10);
    const input = root.querySelector('[data-smart-search-input]') || root.querySelector('input[type="text"]');
    const results = root.querySelector('[data-smart-search-results]') || root.querySelector('.smart-search-results');
    const hiddenId = root.dataset.targetId
      ? document.getElementById(root.dataset.targetId)
      : root.querySelector('input[type="hidden"]');
    const infoEl = root.dataset.infoId ? document.getElementById(root.dataset.infoId) : null;
    const onSelect = root.dataset.onSelect;

    if (!input || !results) return;

    const showResults = (html, visible) => {
      results.innerHTML = html;
      results.hidden = !visible;
      results.classList.toggle('d-none', !visible);
      results.style.display = visible ? 'block' : 'none';
    };

    const selectPatient = (patient) => {
      if (hiddenId) hiddenId.value = patient.id;
      if (infoEl) {
        infoEl.innerHTML = `<strong>المريض المحدد:</strong> ${patient.full_name} | الهوية: ${patient.national_id || '-'} | الهاتف: ${patient.phone || '-'}`;
        infoEl.classList.remove('d-none');
        infoEl.style.display = 'block';
      }
      input.value = '';
      showResults('', false);
      root.dispatchEvent(new CustomEvent('smart-search:select', { detail: patient, bubbles: true }));
      if (onSelect && typeof window[onSelect] === 'function') {
        window[onSelect](patient);
      }
    };

    const runSearch = debounce(() => {
      const q = input.value.trim();
      if (q.length < minChars) {
        showResults('', false);
        return;
      }
      showResults('<div class="list-group-item text-muted">جاري البحث...</div>', true);
      fetch(`${api}?q=${encodeURIComponent(q)}`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      })
        .then((r) => r.json())
        .then((data) => {
          const list = data.patients || [];
          if (!list.length) {
            showResults('<div class="list-group-item text-muted">لا توجد نتائج</div>', true);
            return;
          }
          results.innerHTML = '';
          list.forEach((patient) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'list-group-item list-group-item-action text-start';
            item.innerHTML = `<div class="d-flex justify-content-between"><strong>${patient.full_name}</strong><small>${patient.national_id || ''}</small></div><small class="text-muted">${patient.phone || ''}</small>`;
            item.addEventListener('click', () => selectPatient(patient));
            results.appendChild(item);
          });
          showResults('', true);
        })
        .catch(() => {
          showResults('<div class="list-group-item text-danger">خطأ في البحث</div>', true);
        });
    }, 300);

    input.addEventListener('input', runSearch);
    document.addEventListener('click', (e) => {
      if (!root.contains(e.target)) showResults('', false);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-smart-search]').forEach(initSmartSearch);
  });

  window.initSmartSearch = initSmartSearch;
})();
