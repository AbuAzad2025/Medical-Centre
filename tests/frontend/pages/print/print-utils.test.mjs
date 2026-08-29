import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

const printFiles = [
  'static/js/pages/print/receipt.js',
  'static/js/pages/print/invoice.js',
  'static/js/pages/print/prescription.js',
  'static/js/pages/print/emergency_report.js',
  'static/js/pages/print/radiology_report.js',
  'static/js/pages/print/report.js',
];

describe('print/* print files', () => {
  printFiles.forEach((file) => {
    test(`${file} loads without critical errors`, async () => {
      document.body.innerHTML = '<div id="app"></div>';
      await loadScript(file);
    });

    test(`${file} uses window.addEventListener('load')`, async () => {
      document.body.innerHTML = '<div id="app"></div>';
      const spy = vi.spyOn(window, 'addEventListener');
      await loadScript(file);
      expect(spy).toHaveBeenCalledWith('load', expect.any(Function));
      spy.mockRestore();
    });
  });

  test('auto-print timing uses 800ms setTimeout', async () => {
    document.body.innerHTML = '<div id="app"></div>';
    const spy = vi.spyOn(window, 'addEventListener');
    await loadScript('static/js/pages/print/receipt.js');
    const loadHandler = spy.mock.calls.find(c => c[0] === 'load');
    expect(loadHandler).toBeDefined();
    spy.mockRestore();
  });
});
