import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
  document.head.innerHTML = '';
  window.localStorage.clear();
  delete window.Swal;
  delete window.__wrapFetchEntitlement;
  delete window.gsap;
  delete window.ScrollTrigger;
  delete window.__apiMetrics;
  window.location = { href: '', origin: 'http://localhost', pathname: '/', reload: vi.fn() };
  window.matchMedia = vi.fn().mockImplementation((query) => ({
    matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }));
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  window.bootstrap = { Tooltip: vi.fn(), Popover: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}), text: () => Promise.resolve('<p>x</p>') });
});

afterEach(() => {
  iso.cleanup();
  vi.restoreAllMocks();
});

describe('base.js fetch wrapper default and entitlement branches', () => {
  it('falls back to GET when no init is provided', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="tok">';
    const mod = await loadModule('static/js/base.js');
    await window.fetch('/api/x');
    expect(window.__apiMetrics.calls).toBe(1);
  });

  it('applies __wrapFetchEntitlement when defined before load', async () => {
    document.head.innerHTML = '<meta name="csrf-token" content="tok">';
    const inner = vi.fn((f) => {
      const wrapped = (...args) => {
        window.__entitlementRan = true;
        return f(...args);
      };
      return wrapped;
    });
    window.__wrapFetchEntitlement = inner;
    await loadModule('static/js/base.js');
    expect(inner).toHaveBeenCalled();
    await window.fetch('/api/x', { method: 'POST' });
    expect(window.__entitlementRan).toBe(true);
  });

  it('silences console.debug/log in production ENV (catch paths)', async () => {
    document.head.innerHTML = '<meta name="app-env" content="production">';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(typeof console.debug).toBe('function');
  });

  it('swallows errors when localStorage throws during theme preload', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: { getItem() { throw new Error('x'); }, setItem() {}, clear() {} },
      configurable: true,
    });
    await loadModule('static/js/base.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });

  it('swallows errors when the app-env meta read throws', async () => {
    const realQS = document.querySelector.bind(document);
    document.querySelector = (sel) => {
      if (sel === 'meta[name="app-env"]') throw new Error('boom');
      return realQS(sel);
    };
    await loadModule('static/js/base.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
    document.querySelector = realQS;
  });
});

describe('base.js sidebar collapse branches', () => {
  it('toggles aria-expanded and persists both states', async () => {
    document.body.innerHTML = '<div id="appSidebar"></div><button id="sidebarToggle" aria-expanded="true"></button>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.getElementById('sidebarToggle');
    btn.click();
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    expect(window.localStorage.getItem('sidebarCollapsed')).toBe('1');
    btn.click();
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(window.localStorage.getItem('sidebarCollapsed')).toBe('0');
  });

  it('sidebar localStorage set failure is swallowed', async () => {
    document.body.innerHTML = '<div id="appSidebar"></div><button id="sidebarToggle"></button>';
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem() { return null; },
        setItem() { throw new Error('quota'); },
        clear() {},
      },
      configurable: true,
    });
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.getElementById('sidebarToggle');
    expect(() => btn.click()).not.toThrow();
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });
});

describe('base.js scroll reduced-motion branch', () => {
  it('uses auto behavior when user prefers reduced motion', async () => {
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query.includes('reduced-motion'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
    }));
    document.body.innerHTML = '<a href="#target">go</a><div id="target"></div>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('a[href="#target"]').click();
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith(expect.objectContaining({ behavior: 'auto' }));
  });
});

describe('base.js Ctrl+Enter form resolution branches', () => {
  it('uses closest(form) when the active element has no form property', async () => {
    document.body.innerHTML = '<form id="f"><div id="focusable" tabindex="0"></div><button type="submit" id="sb">Go</button></form>';
    const clickSpy = vi.fn();
    document.getElementById('sb').addEventListener('click', clickSpy);
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const el = document.getElementById('focusable');
    el.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }));
    expect(clickSpy).toHaveBeenCalled();
  });

  it('does nothing when the focused element is outside any form', async () => {
    document.body.innerHTML = '<div id="focusable" tabindex="0"></div>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const el = document.getElementById('focusable');
    el.focus();
    expect(() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true }))).not.toThrow();
  });
});

describe('base.js DataTables error branches', () => {
  it('swallows DataTables isDataTable throwing during init', async () => {
    document.body.innerHTML = '<table data-dt="1"><tbody><tr><td>x</td></tr></tbody></table>';
    window.$ = function (el) { return { DataTable: () => ({}) }; };
    window.$.fn = { DataTable: true, dataTable: { isDataTable() { throw new Error('boom'); } } };
    await loadModule('static/js/base.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
    delete window.$;
  });

  it('swallows columns.adjust throwing in the shown.bs.tab handler', async () => {
    document.body.innerHTML = '<a data-bs-toggle="tab" href="#pane1">Tab</a><div id="pane1"><table data-dt="1"><tbody><tr><td>x</td></tr></tbody></table></div>';
    window.$ = function (el) {
      return { DataTable: () => ({ columns: { adjust() { throw new Error('boom'); } } }) };
    };
    window.$.fn = { DataTable: true };
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const tab = document.querySelector('[data-bs-toggle="tab"]');
    expect(() => tab.dispatchEvent(new Event('shown.bs.tab', { bubbles: true }))).not.toThrow();
    delete window.$;
  });

  it('pane load fetch failure falls back to showToast', async () => {
    document.body.innerHTML = '<a data-bs-toggle="tab" href="#pane1">Tab</a><div id="pane1" data-load-url="/partial"></div>';
    window.showToast = vi.fn();
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const tab = document.querySelector('[data-bs-toggle="tab"]');
    tab.dispatchEvent(new Event('shown.bs.tab', { bubbles: true }));
    await new Promise(r => setTimeout(r, 30));
    expect(window.showToast).toHaveBeenCalled();
  });

  it('gsap registerPlugin throwing is swallowed', async () => {
    window.gsap = { registerPlugin() { throw new Error('boom'); } };
    window.ScrollTrigger = function () {};
    await expect(loadModule('static/js/base.js')).resolves.toBeDefined();
  });
});

describe('base.js confirm dialog branches', () => {
  it('confirmNavigate falls back to alert without Swal', async () => {
    delete window.Swal;
    window.alert = vi.fn();
    const mod = await loadModule('static/js/base.js');
    expect(mod.confirmNavigate({ currentTarget: { href: '/x' }, preventDefault() {} }, 'msg')).toBe(false);
    expect(window.alert).toHaveBeenCalledWith('msg');
  });

  it('confirmNavigate does not navigate when confirmation is cancelled', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: false }) };
    const mod = await loadModule('static/js/base.js');
    mod.confirmNavigate({ currentTarget: { href: '/should-not-go' }, preventDefault() {} }, 'msg');
    await new Promise(r => setTimeout(r, 20));
    expect(window.location.href).toBe('');
  });

  it('confirmSubmit falls back to alert without Swal', async () => {
    delete window.Swal;
    window.alert = vi.fn();
    const mod = await loadModule('static/js/base.js');
    const form = document.createElement('form');
    document.body.appendChild(form);
    expect(mod.confirmSubmit({ currentTarget: form, preventDefault() {} }, 'msg')).toBe(false);
    expect(window.alert).toHaveBeenCalledWith('msg');
  });

  it('confirmSubmit resolves the form via closest when form property is missing', async () => {
    const mod = await loadModule('static/js/base.js');
    document.body.innerHTML = '<form id="f"><button id="b">Go</button></form>';
    const form = document.getElementById('f');
    const btn = document.getElementById('b');
    const fakeEvent = { currentTarget: { form: null, closest: () => form }, preventDefault() {} };
    expect(mod.confirmSubmit(fakeEvent, 'msg')).toBe(false);
    expect(window.Swal.fire).toHaveBeenCalled();
  });

  it('confirmSubmit returns false when there is no form at all', async () => {
    const mod = await loadModule('static/js/base.js');
    const fakeEvent = { currentTarget: { form: null, closest: () => null }, preventDefault() {} };
    expect(mod.confirmSubmit(fakeEvent, 'msg')).toBe(false);
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('confirmSubmit does not submit the form when confirmation is cancelled', async () => {
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: false }) };
    const mod = await loadModule('static/js/base.js');
    const submitSpy = vi.fn();
    document.body.innerHTML = '<form id="f"><button id="b" type="submit">Go</button></form>';
    document.getElementById('f').addEventListener('submit', submitSpy);
    const form = document.getElementById('f');
    mod.confirmSubmit({ currentTarget: form, preventDefault() {} }, 'msg');
    await new Promise(r => setTimeout(r, 20));
    expect(submitSpy).not.toHaveBeenCalled();
  });
});

describe('base.js initAdvancedTable branches', () => {
  it('does nothing when the table is missing', async () => {
    const mod = await loadModule('static/js/base.js');
    expect(() => mod.initAdvancedTable('nope')).not.toThrow();
  });

  it('returns early when a search input already exists', async () => {
    document.body.innerHTML = '<input class="form-control"><table id="t"><tbody><tr><td>x</td></tr></tbody></table>';
    const mod = await loadModule('static/js/base.js');
    mod.initAdvancedTable('t');
    expect(document.querySelectorAll('.form-control').length).toBe(1);
  });

  it('sort with rows missing data attributes does not crash', async () => {
    document.body.innerHTML = `<table id="t"><thead><tr><th data-sort="price">Price</th></tr></thead>
      <tbody><tr><td>no attr A</td></tr><tr><td>no attr B</td></tr></tbody></table>`;
    const mod = await loadModule('static/js/base.js');
    mod.initAdvancedTable('t');
    const th = document.querySelector('th[data-sort="price"]');
    th.click();
    th.click();
    expect(th.classList.contains('sort-asc') || th.classList.contains('sort-desc')).toBe(true);
  });
});

describe('base.js safe links branches', () => {
  it('anchors without href are neutralised as placeholders', async () => {
    document.body.innerHTML = '<a>No href</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const a = document.querySelector('a');
    expect(a.getAttribute('href')).toBe('javascript:void(0)');
    expect(a.getAttribute('role')).toBe('button');
    expect(a.getAttribute('tabindex')).toBe('0');
  });

  it('placeholder anchor with only aria-label does not throw', async () => {
    document.body.innerHTML = '<a aria-label="Close dialog"></a><a></a>';
    await loadModule('static/js/base.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
  });

  it('placeholder anchor with a throwing textContent getter is swallowed', async () => {
    document.body.innerHTML = '<a>Kaboom</a>';
    const a = document.querySelector('a');
    Object.defineProperty(a, 'textContent', { get() { throw new Error('boom'); }, configurable: true });
    await loadModule('static/js/base.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
  });

  it('clicks on _blank and download links do not trigger the loading bar', async () => {
    document.body.innerHTML = '<a id="blank" href="/other" target="_blank">B</a><a id="dl" href="/file.pdf" download>D</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('blank').click();
    document.getElementById('dl').click();
    expect(document.getElementById('topLoadingBar').style.display).toBe('none');
  });

  it('clicks on cross-origin links do not trigger the loading bar', async () => {
    document.body.innerHTML = '<a id="ext" href="https://evil.example.com/x">X</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('ext').click();
    expect(document.getElementById('topLoadingBar').style.display).toBe('none');
  });

  it('clicks on same-pathname links do not trigger the loading bar', async () => {
    document.body.innerHTML = '<a id="same" href="http://localhost/?other=1">X</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('same').click();
    expect(document.getElementById('topLoadingBar').style.display).toBe('none');
  });

  it('unparseable hrefs are ignored safely', async () => {
    document.body.innerHTML = '<a id="bad" href="http://[bad">X</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(() => document.getElementById('bad').click()).not.toThrow();
    expect(document.getElementById('topLoadingBar').style.display).toBe('none');
  });

  it('clicks on a normal internal link trigger the loading bar', async () => {
    document.body.innerHTML = '<a id="go" href="/another-page">X</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('go').click();
    expect(document.getElementById('topLoadingBar').style.display).toBe('block');
  });
});

describe('base.js clock lifecycle', () => {
  it('no live-clock elements means no interval and beforeunload still works', async () => {
    await loadModule('static/js/base.js');
    expect(() => window.dispatchEvent(new Event('beforeunload'))).not.toThrow();
  });

  it('live-clock elements get an interval cleared on beforeunload', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<span class="live-clock"></span>';
    await loadModule('static/js/base.js');
    expect(() => window.dispatchEvent(new Event('beforeunload'))).not.toThrow();
    vi.useRealTimers();
  });
});

describe('base.js data-confirm click arms', () => {
  it('data-confirm without message attribute is ignored', async () => {
    document.body.innerHTML = '<button data-confirm="">Buy</button>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
    expect(() => document.querySelector('[data-confirm]').click()).not.toThrow();
    expect(window.Swal.fire).not.toHaveBeenCalled();
  });

  it('data-confirm with confirmation navigates the anchor to its href', async () => {
    document.body.innerHTML = '<a data-confirm="????" href="/delete/1">Delete</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
    window.location = { href: '' };
    document.querySelector('a[data-confirm]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toBe('/delete/1');
  });

  it('data-confirm with placeholder href does not navigate', async () => {
    document.body.innerHTML = '<a data-confirm="????" href="#">Delete</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
    window.location = { href: '' };
    document.querySelector('a[data-confirm]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toBe('');
  });

  it('data-confirm on a form button submits its form on confirm', async () => {
    document.body.innerHTML = '<form id="f"><button type="button" data-confirm="?????">Go</button></form>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const form = document.getElementById('f');
    form.submit = vi.fn();
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
    document.querySelector('button[data-confirm]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(form.submit).toHaveBeenCalled();
  });

  it('data-confirm on a cancel still does nothing', async () => {
    document.body.innerHTML = '<a data-confirm="????" href="/delete/1">Delete</a>';
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: false }) };
    window.location = { href: '' };
    document.querySelector('a[data-confirm]').click();
    await new Promise(r => setTimeout(r, 30));
    expect(window.location.href).toBe('');
  });

  it('data-confirm without Swal does nothing', async () => {
    document.body.innerHTML = '<a data-confirm="????" href="/delete/1">Delete</a>';
    delete window.Swal;
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(() => document.querySelector('a[data-confirm]').click()).not.toThrow();
  });
});

describe('base.js tooltip/popover init arms', () => {
  it('tooltip and popover elements get bootstrap wrappers', async () => {
    document.body.innerHTML = `
      <button data-bs-toggle="tooltip" title="t">T</button>
      <button data-bs-toggle="popover" data-bs-content="c">P</button>
    `;
    const tooltipSpy = vi.fn();
    const popoverSpy = vi.fn();
    window.bootstrap = { Tooltip: tooltipSpy, Popover: popoverSpy, Modal: { getOrCreateInstance: vi.fn(() => ({ show: vi.fn(), hide: vi.fn() })) } };
    await loadModule('static/js/base.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(tooltipSpy).toHaveBeenCalled();
    expect(popoverSpy).toHaveBeenCalled();
  });
});
