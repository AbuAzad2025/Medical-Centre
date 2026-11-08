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

const HIDE = vi.fn();
const SHOW = vi.fn();
const INSTANCE = { show: SHOW, hide: HIDE };

beforeEach(() => {
  setupDom();
  SHOW.mockClear();
  HIDE.mockClear();
  window.__M = [];
  window.escHtml = (s) => s;
  window.__M0__ = 'csrf-save';
  window.__M1__ = 'csrf-delete';
  window.API_ROUTES = { manager_pricing_services: '/api/pricing' };
  window.location = { href: '', reload: vi.fn() };
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: true }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Modal: vi.fn().mockImplementation(() => INSTANCE),
  };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true, message: 'تم' }) });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('pricing.js editService fallback branches', () => {
  it('fills empty defaults when optional fields are missing', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    mod.editService(1, { code: 'L', name: 'Lab', category: 'lab', base_price: 100, is_active: true });
    expect(document.getElementById('serviceNameAr').value).toBe('');
    expect(document.getElementById('serviceDepartment').value).toBe('');
    expect(document.getElementById('emergencyPrice').value).toBe('');
    expect(document.getElementById('insurancePrice').value).toBe('');
    expect(document.getElementById('serviceDuration').value).toBe('');
    expect(document.getElementById('serviceMaxDaily').value).toBe('');
    expect(document.getElementById('serviceDescription').value).toBe('');
    expect(SHOW).toHaveBeenCalled();
  });
});

describe('pricing.js saveService payload branches', () => {
  it('non-numeric price and duration inputs fall back to 0/null', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'Complete Blood Count';
    document.getElementById('serviceNameAr').value = 'صورة دم كاملة';
    document.getElementById('basePrice').value = 'not-a-number';
    document.getElementById('emergencyPrice').value = '';
    document.getElementById('insurancePrice').value = '';
    document.getElementById('serviceDuration').value = '';
    document.getElementById('serviceMaxDaily').value = '';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    const body = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(body.base_price).toBe(0);
    expect(body.emergency_price).toBeNull();
    expect(body.insurance_price).toBeNull();
    expect(body.duration).toBeNull();
    expect(body.max_daily).toBeNull();
  });

  it('missing department sends department_id null', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    document.getElementById('serviceDepartment').value = '';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).department_id).toBeNull();
  });

  it('API_ROUTES manager_pricing_services is honoured', async () => {
    window.API_ROUTES = { manager_pricing_services: '/custom/pricing' };
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/pricing');
  });

  it('saveService non-ok response surfaces the generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0]).toBe('خطأ');
  });

  it('saveService network failure surfaces the generic error', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0]).toBe('خطأ');
  });

  it('saveService success hides the modal and reloads', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(HIDE).toHaveBeenCalled();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('saveService server failure shows server message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'مكرر' }) });
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('serviceCode').value = 'CBC';
    document.getElementById('serviceName').value = 'CBC';
    document.getElementById('serviceNameAr').value = 'صورة دم';
    mod.saveService();
    await new Promise(r => setTimeout(r, 40));
    expect(window.Swal.fire.mock.calls[0][0]).toBe('خطأ');
    expect(window.Swal.fire.mock.calls[0][1]).toBe('مكرر');
  });
});

describe('pricing.js deleteService branches', () => {
  it('cancelled confirmation does not fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('delete uses API_ROUTES endpoint and csrf __M1__ header', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    const call = global.fetch.mock.calls.find(c => String(c[0]).includes('/api/pricing/7'));
    expect(call[1].method).toBe('DELETE');
    expect(call[1].headers['X-CSRFToken']).toBe('csrf-delete');
  });

  it('delete non-ok response shows generic error', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    expect(window.Swal.fire.mock.calls[1][0]).toBe('خطأ');
  });

  it('delete success=false shows server message', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: false, message: 'خدمة مرتبطة بزيارات' }) });
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    expect(window.Swal.fire.mock.calls[1][1]).toBe('خدمة مرتبطة بزيارات');
  });

  it('delete success reloads the page', async () => {
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('API_ROUTES fallback to default delete endpoint when unset', async () => {
    delete window.API_ROUTES;
    const mod = await loadModule('static/js/pages/manager/pricing.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await mod.deleteService(7);
    expect(global.fetch.mock.calls[0][0]).toBe('/manager/api/pricing/services/7');
  });
});
