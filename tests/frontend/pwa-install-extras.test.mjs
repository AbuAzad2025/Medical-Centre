import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const VISIT_KEY = 'azad_pwa_visits';
const DISMISS_KEY = 'azad_pwa_install_dismissed';

beforeEach(() => {
  document.body.innerHTML = '';
  window.localStorage.clear();
  delete window.__USER_PREFS__;
  window.matchMedia = vi.fn(() => ({ matches: false, media: '', addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla/5.0 (Windows NT 10.0) Chrome/130.0', configurable: true });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('pwa-install.js beforeinstallprompt arms', () => {
  it('beforeinstallprompt with localStorage broken does not show the banner', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem() { throw new Error('quota'); },
        setItem() { throw new Error('quota'); },
        removeItem() {},
        clear() {},
      },
      configurable: true,
    });
    await loadModule('static/js/pwa-install.js');
    const event = new Event('beforeinstallprompt', { cancelable: true });
    window.dispatchEvent(event);
    expect(document.getElementById('pwaInstallBanner')).toBeNull();
    expect(event.defaultPrevented).toBe(true);
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });

  it('iOS with high visits and standalone display shows no banner', async () => {
    Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1', configurable: true });
    window.localStorage.setItem(VISIT_KEY, '5');
    window.matchMedia = vi.fn((query) => ({ matches: query.includes('standalone'), media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    await loadModule('static/js/pwa-install.js');
    expect(document.getElementById('pwaInstallBanner')).toBeNull();
  });

  it('iOS with high visits and non-standalone display shows the banner on load', async () => {
    Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla/5.0 (iPad; CPU OS 15_0 like Mac OS X) AppleWebKit/605.1', configurable: true });
    window.localStorage.setItem(VISIT_KEY, '5');
    await loadModule('static/js/pwa-install.js');
    expect(document.getElementById('pwaInstallBanner')).not.toBeNull();
  });

  it('iOS with iPod UA passes the isIOS check', async () => {
    Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla/5.0 (iPod touch; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1', configurable: true });
    const mod = await loadModule('static/js/pwa-install.js');
    expect(mod.isIOS()).toBe(true);
  });
});

describe('pwa-install.js showBanner edge branches', () => {
  it('showBanner still renders when the dismiss-read throws', async () => {
    const original = window.localStorage;
    Object.defineProperty(window, 'localStorage', {
      value: {
        getItem() { throw new Error('quota'); },
        setItem() {},
        clear() {},
      },
      configurable: true,
    });
    const mod = await loadModule('static/js/pwa-install.js');
    expect(() => mod.showBanner()).not.toThrow();
    expect(document.getElementById('pwaInstallBanner')).not.toBeNull();
    Object.defineProperty(window, 'localStorage', { value: original, configurable: true });
  });

  it('install click with deferred prompt invokes prompt and userChoice resolution', async () => {
    window.localStorage.setItem(VISIT_KEY, '5');
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    const event = new Event('beforeinstallprompt', { cancelable: true });
    event.prompt = vi.fn();
    event.userChoice = Promise.resolve({ outcome: 'accepted' });
    window.dispatchEvent(event);
    document.getElementById('pwaInstallBtn').click();
    expect(event.prompt).toHaveBeenCalled();
    await new Promise(r => setTimeout(r, 30));
    expect(document.getElementById('pwaInstallBanner')).toBeNull();
  });
});
