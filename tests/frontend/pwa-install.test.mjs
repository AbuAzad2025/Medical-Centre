import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = '';
  localStorage.clear();
  vi.resetModules();
});

describe('pwa-install.js', () => {
  it('visitCount increments after import bump', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    expect(mod.visitCount()).toBe(2);
    expect(mod.visitCount()).toBe(2);
  });

  it('bumpVisits writes to storage', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    mod.bumpVisits();
    expect(localStorage.getItem('azad_pwa_visits')).toBe('2');
  });

  it('isIOS returns false on desktop UA', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    expect(mod.isIOS()).toBe(false);
  });

  it('isIOS detects iPhone UA via userAgent override', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    Object.defineProperty(window.navigator, 'userAgent', {
      get: () => 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15',
      configurable: true,
    });
    expect(mod.isIOS()).toBe(true);
  });

  it('showBanner injects banner into DOM', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    expect(document.getElementById('pwaInstallBanner')).toBeTruthy();
  });

  it('showBanner does not duplicate the banner', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    mod.showBanner();
    expect(document.querySelectorAll('#pwaInstallBanner').length).toBe(1);
  });

  it('showBanner hidden when already dismissed', async () => {
    localStorage.setItem('azad_pwa_install_dismissed', '1');
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    expect(document.getElementById('pwaInstallBanner')).toBeNull();
  });

  it('dismiss button removes banner and sets dismissed key', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    document.getElementById('pwaInstallDismiss').click();
    expect(document.getElementById('pwaInstallBanner')).toBeNull();
    expect(localStorage.getItem('azad_pwa_install_dismissed')).toBe('1');
  });

  it('install button with deferred prompt calls prompt and userChoice', async () => {
    const prompt = vi.fn();
    const userChoice = Promise.resolve({ outcome: 'accepted' });
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    const evt = new Event('beforeinstallprompt');
    evt.prompt = prompt;
    evt.userChoice = userChoice;
    window.dispatchEvent(evt);
    document.getElementById('pwaInstallBtn').click();
    expect(prompt).toHaveBeenCalled();
  });

  it('install button shows iOS instructions when no deferred prompt', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    mod.showBanner();
    Object.defineProperty(window.navigator, 'userAgent', {
      get: () => 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15',
      configurable: true,
    });
    document.getElementById('pwaInstallBtn').click();
    expect(document.getElementById('pwaInstallText').textContent).toContain('الشاشة الرئيسية');
  });

  it('visitCount returns 1 when localStorage throws', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    const orig = Object.getOwnPropertyDescriptor(window, 'localStorage');
    Object.defineProperty(window, 'localStorage', {
      get() { throw new Error('ssr'); },
      configurable: true,
    });
    expect(mod.visitCount()).toBe(1);
    Object.defineProperty(window, 'localStorage', orig);
  });

  it('bumpVisits swallows localStorage errors', async () => {
    const mod = await loadModule('static/js/pwa-install.js');
    const orig = Object.getOwnPropertyDescriptor(window, 'localStorage');
    Object.defineProperty(window, 'localStorage', {
      get() { throw new Error('ssr'); },
      configurable: true,
    });
    expect(() => mod.bumpVisits()).not.toThrow();
    Object.defineProperty(window, 'localStorage', orig);
  });

  it('beforeinstallprompt with high visit count shows banner', async () => {
    localStorage.setItem('azad_pwa_visits', '3');
    await loadModule('static/js/pwa-install.js');
    const evt = new Event('beforeinstallprompt');
    window.dispatchEvent(evt);
    expect(document.getElementById('pwaInstallBanner')).toBeTruthy();
  });
});