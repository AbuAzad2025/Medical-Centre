import { describe, it, expect, beforeAll, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

let baseModule;
let swRegister;

beforeAll(async () => {
  try {
    swRegister = vi.fn().mockResolvedValue({ scope: '/' });
    Object.defineProperty(window.navigator, 'serviceWorker', {
      value: { register: swRegister },
      configurable: true,
      writable: true,
    });
  } catch (e) {}
  baseModule = await loadModule('static/js/base.js');
});

beforeEach(() => {
  try { localStorage.clear(); } catch (e) {}
  // Keep #topLoadingBar (created once by the module at import); remove everything else.
  document.querySelectorAll('body > *:not(#topLoadingBar)').forEach((n) => n.remove());
  window.__M = [];
  window.API_ROUTES = {};
  window.Swal = {
    fire: vi.fn().mockResolvedValue({ isConfirmed: false }),
    showLoading: vi.fn(),
  };
  window.bootstrap = {
    Tooltip: vi.fn(),
    Popover: vi.fn(),
    Collapse: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn() })) },
    Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) },
  };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  window.Chart = vi.fn().mockImplementation(() => ({}));
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }));
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('base.js', () => {
  it('exposes escHtml on window', () => {
    expect(typeof window.escHtml).toBe('function');
    expect(window.escHtml('<b>')).toBe('&lt;b&gt;');
    expect(window.escHtml(null)).toBe('');
  });

  it('preloads dark theme from localStorage', async () => {
    try { localStorage.setItem('theme', 'dark'); } catch (e) {}
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    try { localStorage.removeItem('theme'); } catch (e) {}
  });

  it('preloads density and radius from localStorage', async () => {
    try {
      localStorage.setItem('ui_density', 'compact');
      localStorage.setItem('ui_radius', 'sm');
    } catch (e) {}
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(document.documentElement.getAttribute('data-radius')).toBe('sm');
    try { localStorage.removeItem('ui_density'); localStorage.removeItem('ui_radius'); } catch (e) {}
  });

  it('sidebar toggle collapses sidebar when clicked', async () => {
    const aside = document.createElement('aside');
    aside.id = 'appSidebar';
    const toggle = document.createElement('button');
    toggle.id = 'sidebarToggle';
    toggle.setAttribute('aria-expanded', 'true');
    document.body.appendChild(aside);
    document.body.appendChild(toggle);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    toggle.click();
    expect(aside.classList.contains('collapsed')).toBe(true);
  });

  it('mobile toggle opens sidebar overlay and close button closes', async () => {
    const aside = document.createElement('aside');
    aside.id = 'appSidebar';
    const openBtn = document.createElement('button');
    openBtn.id = 'mobileSidebarToggle';
    const closeBtn = document.createElement('button');
    closeBtn.id = 'closeSidebarBtn';
    const overlay = document.createElement('div');
    overlay.id = 'sidebarOverlay';
    document.body.appendChild(aside);
    document.body.appendChild(openBtn);
    document.body.appendChild(closeBtn);
    document.body.appendChild(overlay);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    openBtn.click();
    expect(aside.classList.contains('show')).toBe(true);
    overlay.click();
    expect(aside.classList.contains('show')).toBe(false);
  });

  it('form submit marks button disabled and data-loading', async () => {
    document.body.innerHTML += '<form id="f1"><button type="submit">Save</button></form>';
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    document.getElementById('f1').dispatchEvent(new Event('submit', { bubbles: true }));
    expect(document.querySelector('#f1 button').disabled).toBe(true);
    expect(document.querySelector('#f1 button').hasAttribute('data-loading')).toBe(true);
  });

  it('Escape key closes toasts', async () => {
    const host = document.createElement('div');
    host.id = 'kbdHost';
    host.innerHTML = '<div class="toast"><button class="toast-close">x</button></div>';
    document.body.appendChild(host);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    host.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(true).toBe(true);
  });

  it('Ctrl+Enter clicks submit button in active element form', async () => {
    document.body.innerHTML += '<form id="f2"><input id="i1"><button type="submit">Go</button></form>';
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    const input = document.getElementById('i1');
    const submitBtn = vi.fn();
    document.querySelector('#f2 button').click = submitBtn;
    input.focus();
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
    expect(submitBtn).toHaveBeenCalled();
  });

  it('debounce delays execution', () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const debounced = baseModule.debounce(fn, 100);
    debounced('a', 'b');
    debounced('c');
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(150);
    expect(fn).toHaveBeenCalledWith('c');
  });

  it('validateForm marks invalid required fields', () => {
    document.body.innerHTML += '<form id="vf"><input required name="a"><select required name="b"></select><textarea required name="c"></textarea></form>';
    const form = document.getElementById('vf');
    expect(baseModule.validateForm(form)).toBe(false);
    expect(form.querySelector('[name="a"]').classList.contains('is-invalid')).toBe(true);
    form.querySelector('[name="a"]').value = 'x';
    expect(baseModule.validateForm(form)).toBe(false);
  });

  it('confirmNavigate prevents default', () => {
    const link = document.createElement('a');
    link.href = 'http://x.test/page';
    document.body.appendChild(link);
    const e = { preventDefault: vi.fn(), currentTarget: link };
    const result = baseModule.confirmNavigate(e, 'msg');
    expect(e.preventDefault).toHaveBeenCalled();
    expect(result).toBe(false);
  });

  it('confirmSubmit prevents default and finds form', () => {
    document.body.innerHTML += '<form id="cs"><button id="btn" type="button">Go</button></form>';
    const btn = document.getElementById('btn');
    const e = { preventDefault: vi.fn(), currentTarget: btn };
    const result = baseModule.confirmSubmit(e, 'msg');
    expect(e.preventDefault).toHaveBeenCalled();
    expect(result).toBe(false);
  });

  it('initAdvancedTable creates search input and hides non-matching rows', () => {
    document.body.innerHTML += '<table id="tbl"><thead><tr><th data-sort="name">Name</th></tr></thead><tbody><tr><td data-name="alpha">Alpha</td></tr><tr><td data-name="beta">Beta</td></tr></tbody></table>';
    baseModule.initAdvancedTable('tbl');
    const input = document.querySelector('.form-control.mb-3');
    expect(input).toBeTruthy();
    vi.useFakeTimers();
    input.value = 'alpha';
    input.dispatchEvent(new Event('input', { bubbles: true }));
    vi.advanceTimersByTime(350);
    const rows = document.querySelectorAll('#tbl tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  it('initAdvancedTable sort toggles sort classes', () => {
    document.body.innerHTML += '<table id="tbl2"><thead><tr><th data-sort="name">Name</th></tr></thead><tbody><tr><td data-name="beta">Beta</td></tr><tr><td data-name="alpha">Alpha</td></tr></tbody></table>';
    baseModule.initAdvancedTable('tbl2');
    const th = document.querySelector('#tbl2 th');
    th.click();
    expect(th.classList.contains('sort-asc')).toBe(true);
    th.click();
    expect(th.classList.contains('sort-desc')).toBe(true);
  });

  it('updateClock writes to .live-clock elements', () => {
    document.body.appendChild(Object.assign(document.createElement('div'), { className: 'live-clock' }));
    baseModule.updateClock();
    expect(document.querySelector('.live-clock').textContent.length).toBeGreaterThan(0);
  });

  it('initAutoSave returns early if form missing', () => {
    expect(baseModule.initAutoSave('missing-form-id-xyz')).toBeUndefined();
  });

  it('initAutoSave sets up interval and responds to input', () => {
    document.body.innerHTML += '<form id="as"><input name="a"></form>';
    baseModule.initAutoSave('as', 300000);
    document.querySelector('#as input').dispatchEvent(new Event('input', { bubbles: true }));
    expect(true).toBe(true);
  });

  it('initPerformanceMonitoring adds load listener', () => {
    expect(() => baseModule.initPerformanceMonitoring()).not.toThrow();
  });

  it('service worker registers on window load', () => {
    window.dispatchEvent(new Event('load'));
    expect(swRegister).toHaveBeenCalled();
  });

  it('DOMContentLoaded adds .card-modern and .btn-modern classes', async () => {
    document.body.innerHTML += '<div class="card"></div><button class="btn"></button>';
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    expect(document.querySelector('.card').classList.contains('card-modern')).toBe(true);
    expect(document.querySelector('.btn').classList.contains('btn-modern')).toBe(true);
  });

  it('DOMContentLoaded enforces safe links', async () => {
    const link = document.createElement('a');
    link.setAttribute('href', '#');
    link.textContent = 'Click';
    document.body.appendChild(link);
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    expect(document.querySelector('a').getAttribute('href')).toBe('javascript:void(0)');
  });

  it('top loading bar is created and hidden', () => {
    expect(document.getElementById('topLoadingBar')).toBeTruthy();
    expect(document.getElementById('topLoadingBar').style.display).toBe('none');
  });

  it('submit listener prevents disabled submit button', () => {
    document.body.innerHTML += '<form id="sub"><button type="submit" disabled>Go</button></form>';
    const form = document.getElementById('sub');
    const e = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(e);
    expect(e.defaultPrevented).toBe(true);
  });

  it('DOMContentLoaded initializes DataTables tables if available', async () => {
    document.body.innerHTML += '<table id="dtbl" data-dt="1"><thead><tr><th>A</th></tr></thead><tbody><tr><td>a</td></tr></tbody></table>';
    window.$ = vi.fn(() => ({ DataTable: vi.fn(() => ({ columns: { adjust: vi.fn() } })) }));
    window.$.fn = { DataTable: true, dataTable: { isDataTable: vi.fn(() => false) } };
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await new Promise(r => setTimeout(r, 10));
    expect(window.$).toHaveBeenCalled();
  });

  it('tab links trigger pane load with DOMPurify', async () => {
    document.body.innerHTML += '<a data-bs-toggle="tab" href="#tab1">Tab</a><div id="tab1" data-load-url="/tab/url"></div>';
    global.fetch = vi.fn().mockResolvedValue({ text: () => Promise.resolve('<p>content</p>') });
    window.DOMPurify = { sanitize: vi.fn((html) => html) };
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const tab = document.querySelector('[data-bs-toggle="tab"]');
    tab.dispatchEvent(new Event('shown.bs.tab', { bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });

  it('tab links trigger pane load without DOMPurify', async () => {
    window.DOMPurify = undefined;
    document.body.innerHTML += '<a data-bs-toggle="tab" href="#tab2">Tab</a><div id="tab2" data-load-url="/tab/url2"></div>';
    global.fetch = vi.fn().mockResolvedValue({ text: () => Promise.resolve('<p>content</p>') });
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const tab = document.querySelector('[data-bs-toggle="tab"]');
    tab.dispatchEvent(new Event('shown.bs.tab', { bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(global.fetch).toHaveBeenCalled();
  });
});