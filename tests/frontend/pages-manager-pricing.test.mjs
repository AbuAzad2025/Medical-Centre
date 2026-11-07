import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function setupDom() {
  document.body.innerHTML = `
    <div id="serviceModal"><div class="modal-content"></div></div>
    <input id="searchInput">
    <table id="pricingTable"><tbody>
      <tr data-search="lab test" data-category="lab"><td>Lab Test</td></tr>
      <tr data-search="x ray" data-category="radiology"><td>X Ray</td></tr>
    </tbody></table>
    <form id="serviceForm"></form>
    <input id="serviceId">
    <input id="serviceCode">
    <input id="serviceName">
    <input id="serviceNameAr">
    <select id="serviceCategory"><option value="lab">lab</option><option value="radiology">radiology</option></select>
    <input id="serviceDepartment">
    <input id="basePrice" value="100">
    <input id="emergencyPrice" value="150">
    <input id="insurancePrice" value="120">
    <input id="serviceDuration" value="30">
    <input id="serviceMaxDaily" value="10">
    <input id="serviceDescription">
    <h5 id="serviceModalLabel"></h5>
    <input type="checkbox" id="isActive" checked>
  `;
}

beforeEach(async () => {
  setupDom();
  window.__M = [];
  window.escHtml = (s) => s;
  window.__M0__ = 'test-csrf';
  window.__M1__ = 'test-csrf';
  window.API_ROUTES = { manager_pricing_services: '/manager/api/pricing/services' };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Modal: vi.fn().mockImplementation(() => ({ show: vi.fn(), hide: vi.fn() })),
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
  };
  window.Chart = vi.fn().mockImplementation(() => ({}));
  if (window.Chart) window.Chart.defaults = { plugins: { tooltip: {}, legend: { labels: { font: {} } } }, font: {} };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'saved' }) });
  await loadModule('static/js/pages/manager/pricing.js');
  document.dispatchEvent(new Event('DOMContentLoaded'));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('pricing.js', () => {
  it('search filters rows by data-search', async () => {
    const input = document.getElementById('searchInput');
    input.value = 'lab';
    input.dispatchEvent(new Event('keyup', { bubbles: true }));
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('filterServices shows all when category=all', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    mod.filterServices('all');
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('');
  });

  it('filterServices shows matching category only', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    mod.filterServices('radiology');
    const rows = document.querySelectorAll('#pricingTable tbody tr');
    expect(rows[0].style.display).toBe('none');
    expect(rows[1].style.display).toBe('');
  });

  it('openAddModal resets form and shows', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceId').value = '42';
    mod.openAddModal();
    expect(document.getElementById('serviceId').value).toBe('');
  });

  it('editService fills fields and shows', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    mod.editService('42', { code: 'C1', name: 'Consult', name_ar: 'استشارة', category: 'lab', department_id: '3', base_price: 50, emergency_price: 80, insurance_price: 60, duration: 30, max_daily: 5, description: 'desc', is_active: false });
    expect(document.getElementById('serviceId').value).toBe('42');
    expect(document.getElementById('serviceCode').value).toBe('C1');
    expect(document.getElementById('serviceName').value).toBe('Consult');
    expect(document.getElementById('isActive').checked).toBe(false);
  });

  it('saveService shows error when required missing', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceId').value = '';
    document.getElementById('serviceCode').value = '';
    document.getElementById('serviceName').value = '';
    document.getElementById('serviceNameAr').value = '';
    await mod.saveService();
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('saveService success posts and reloads', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceId').value = '';
    document.getElementById('serviceCode').value = 'LAB1';
    document.getElementById('serviceName').value = 'Lab';
    document.getElementById('serviceNameAr').value = 'مختبر';
    await mod.saveService();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('saveService edit uses PUT', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceId').value = '42';
    document.getElementById('serviceCode').value = 'LAB1';
    document.getElementById('serviceName').value = 'Lab';
    document.getElementById('serviceNameAr').value = 'مختبر';
    await mod.saveService();
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('saveService network failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceCode').value = 'LAB1';
    document.getElementById('serviceName').value = 'Lab';
    document.getElementById('serviceNameAr').value = 'مختبر';
    await mod.saveService();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('saveService unsuccessful result shows error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'dupe' }) });
    const mod = await import('../../static/js/pages/manager/pricing.js');
    document.getElementById('serviceCode').value = 'LAB1';
    document.getElementById('serviceName').value = 'Lab';
    document.getElementById('serviceNameAr').value = 'مختبر';
    await mod.saveService();
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('deleteService confirmed calls DELETE', async () => {
    const mod = await import('../../static/js/pages/manager/pricing.js');
    await mod.deleteService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
    expect(global.fetch).toHaveBeenCalled();
  });

  it('deleteService not confirmed does not call fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await import('../../static/js/pages/manager/pricing.js');
    await mod.deleteService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('deleteService DELETE failure shows error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await import('../../static/js/pages/manager/pricing.js');
    await mod.deleteService('42');
    await new Promise(r => setTimeout(r, 30));
    expect(window.Swal.fire).toHaveBeenCalled();
  });
});
