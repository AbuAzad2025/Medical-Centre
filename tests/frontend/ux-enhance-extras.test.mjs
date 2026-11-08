import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
  document.documentElement.removeAttribute('style');
  delete window.__uxFetchPatched;
  delete window.__uxProgressBar;
  if (window.scrollTo) window.scrollTo = vi.fn();
});

afterEach(() => {
  iso.cleanup();
  vi.useRealTimers();
});

describe('ux-enhance.js remaining arms', () => {
  it('form with data-ajax-form="1" skips scheduling the stop', async () => {
    vi.useFakeTimers();
    document.body.innerHTML = '<form method="post" data-ajax-form="1" id="f"><button type="submit">Go</button></form>';
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('__uxProgressBar')).not.toBeNull();
    expect(document.querySelector('#__uxProgressBar .__ux-bar').style.width).not.toBe('100%');
    vi.useRealTimers();
  });

  it('non-POST form without data-validate-form is not wired', async () => {
    document.body.innerHTML = '<form method="get" id="f"><button type="submit">Go</button></form>';
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('__uxProgressBar')).toBeNull();
  });

  it('form with data-validate-form is wired even without POST method', async () => {
    document.body.innerHTML = '<form method="get" data-validate-form id="f"><button type="submit">Go</button></form>';
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('f').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(document.getElementById('__uxProgressBar')).not.toBeNull();
  });

  it('window.fetch patch is skipped when fetch does not exist', async () => {
    delete window.fetch;
    await loadModule('static/js/ux-enhance.js');
    expect(() => document.dispatchEvent(new Event('DOMContentLoaded'))).not.toThrow();
    expect(window.__uxFetchPatched).toBeUndefined();
  });

  it('window.fetch is patched only once across repeated loads', async () => {
    const originalFetch = vi.fn().mockResolvedValue({ ok: true });
    window.fetch = originalFetch;
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const patched = window.fetch;
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    expect(window.fetch).toBe(patched);
    expect(window.__uxFetchPatched).toBe(true);
    const res = await window.fetch('/api/x');
    expect(res.ok).toBe(true);
    expect(originalFetch).toHaveBeenCalled();
  });

  it('patched fetch stops progress even when the request fails', async () => {
    window.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/ux-enhance.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    await expect(window.fetch('/api/x')).rejects.toThrow('network');
    expect(document.querySelector('#__uxProgressBar .__ux-bar').style.width).toBe('100%');
  });
});
