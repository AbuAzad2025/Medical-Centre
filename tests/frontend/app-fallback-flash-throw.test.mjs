import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';
import { isolateDomContentLoaded } from './dom-isolation.mjs';

const { csrfSpy, datatablesSpy } = vi.hoisted(() => ({ csrfSpy: vi.fn(), datatablesSpy: vi.fn() }));

vi.mock('../../static/js/csrf.js', () => ({ initCsrf: csrfSpy }));
vi.mock('../../static/js/flash.js', () => { throw new Error('boom'); });
vi.mock('../../static/js/digits-ar.js', () => ({ normalizeArabicDigits: vi.fn() }));
vi.mock('../../static/js/datatables-init.js', () => ({ initDataTables: datatablesSpy }));

const iso = isolateDomContentLoaded();

beforeEach(() => {
  iso.install();
  document.body.innerHTML = '';
  csrfSpy.mockClear();
  datatablesSpy.mockClear();
});
afterEach(() => iso.cleanup());

describe('app.js flash module that throws on import', () => {
  it('is swallowed and the rest of the handler still runs', async () => {
    await loadModule('static/js/app.js');
    await expect(iso.dispatchAndSettle()).resolves.toBeUndefined();
    expect(csrfSpy).toHaveBeenCalled();
    expect(datatablesSpy).toHaveBeenCalled();
  });
});
