import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

vi.mock('../../static/js/csrf.js', () => ({ initCsrf: undefined, default: undefined }));
vi.mock('../../static/js/flash.js', () => ({ initFlashAutoHide: undefined, default: undefined }));
vi.mock('../../static/js/digits-ar.js', () => ({ normalizeArabicDigits: undefined, default: undefined }));
vi.mock('../../static/js/datatables-init.js', () => ({ initDataTables: undefined, default: undefined }));

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
});
afterEach(() => iso.cleanup());

describe('app.js modules with no usable export', () => {
  it('are skipped without crashing the handler', async () => {
    await loadModule('static/js/app.js');
    await expect(iso.dispatchAndSettle()).resolves.toBeUndefined();
  });
});
