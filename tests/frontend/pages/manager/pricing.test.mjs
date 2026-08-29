import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="serviceModal"></div>
    <form id="serviceForm">
      <input id="serviceId" value="" />
      <input id="serviceCode" value="" />
      <input id="serviceName" value="" />
      <input id="serviceNameAr" value="" />
      <select id="serviceCategory"><option value="consultation">Consultation</option></select>
      <select id="serviceDepartment"><option value="">Select</option></select>
      <input id="basePrice" value="100" />
      <input id="emergencyPrice" value="" />
      <input id="insurancePrice" value="" />
      <input id="serviceDuration" value="" />
      <input id="serviceMaxDaily" value="" />
      <textarea id="serviceDescription"></textarea>
      <input type="checkbox" id="isActive" checked />
    </form>
    <div id="serviceModalLabel">Add Service</div>
    <input id="searchInput" type="text" />
    <table id="pricingTable"><tbody>
      <tr data-search="consultation test" data-category="consultation"><td>Consultation</td></tr>
      <tr data-search="lab test" data-category="lab"><td>Lab</td></tr>
    </tbody></table>
  `;
  window.__M0__ = 'csrf-token';
  window.__M1__ = 'csrf-token';
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Modal: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('manager/pricing.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
  });

  test('filterServices is a function', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    expect(typeof filterServices).toBe('function');
  });

  test('openAddModal is a function', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    expect(typeof openAddModal).toBe('function');
  });

  test('saveService is a function', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    expect(typeof saveService).toBe('function');
  });

  test('deleteService is a function', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    expect(typeof deleteService).toBe('function');
  });

  test('filterServices shows all when category is all', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    filterServices('all');
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    rows.forEach(r => expect(r.style.display).toBe(''));
  });

  test('filterServices filters by category', async () => {
    await loadScript('static/js/pages/manager/pricing.js');
    filterServices('lab');
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
  });
});
