import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

const PRINT_FILES = [
  'invoice.js', 'receipt.js', 'prescription.js',
  'radiology_report.js', 'emergency_report.js', 'report.js',
];

describe('print/*.js auto-print pages', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.print = vi.fn();
  });

  it('window load + 800ms triggers print from every loaded print page', async () => {
    for (const file of PRINT_FILES) {
      await loadModule(`static/js/pages/print/${file}`);
    }
    window.dispatchEvent(new Event('load'));
    // before the 800ms elapses nothing prints
    vi.advanceTimersByTime(799);
    expect(window.print).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    // one print call per module loaded
    expect(window.print).toHaveBeenCalledTimes(PRINT_FILES.length);
    vi.useRealTimers();
  });
});