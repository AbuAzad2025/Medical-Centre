import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const { defSpy } = vi.hoisted(() => ({ defSpy: vi.fn() }));

vi.mock('../../static/js/csrf.js', () => ({ initCsrf: vi.fn() }));
vi.mock('../../static/js/flash.js', () => ({ initFlashAutoHide: undefined, default: { initFlashAutoHide: defSpy } }));
vi.mock('../../static/js/digits-ar.js', () => ({ normalizeArabicDigits: vi.fn() }));
vi.mock('../../static/js/datatables-init.js', () => ({ initDataTables: vi.fn() }));

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
  defSpy.mockClear();
});
afterEach(() => iso.cleanup());

describe('app.js flash default export fallback', () => {
  it('uses default.initFlashAutoHide when named export is missing', async () => {
    await loadModule('static/js/app.js');
    await iso.dispatchAndSettle();
    expect(defSpy).toHaveBeenCalled();
  });
});
