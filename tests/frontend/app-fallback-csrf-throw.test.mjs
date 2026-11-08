import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

vi.mock('../../static/js/csrf.js', () => { throw new Error('boom'); });
vi.mock('../../static/js/flash.js', () => ({ initFlashAutoHide: vi.fn() }));
vi.mock('../../static/js/digits-ar.js', () => ({ normalizeArabicDigits: vi.fn() }));
vi.mock('../../static/js/datatables-init.js', () => ({ initDataTables: vi.fn() }));

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.head.innerHTML = '<meta name="csrf-token" content="fallback-tok">';
  delete window.csrfToken;
  delete window.__csrfInitialized;
});
afterEach(() => {
  iso.cleanup();
  document.head.innerHTML = '';
});

describe('app.js csrf module that throws on import', () => {
  it('falls back to initCsrfManual', async () => {
    await loadModule('static/js/app.js');
    await iso.dispatchAndSettle();
    expect(window.csrfToken).toBe('fallback-tok');
    expect(window.__csrfInitialized).toBe(true);
  });
});
