import { describe, it, expect, beforeEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <table><tbody><tr class="table-danger"><td>critical</td></tr><tr><td>normal</td></tr></tbody></table>
    <button type="submit">Save</button>
  `;
  window.location = { reload: vi.fn() };
});

describe('emergency/patient_queue.js', () => {
  it('refreshQueue calls location.reload', async () => {
    const mod = await loadModule('static/js/pages/emergency/patient_queue.js');
    mod.refreshQueue();
    expect(window.location.reload).toHaveBeenCalled();
  });

  it('DOMContentLoaded row hover sets and clears background', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const rows = document.querySelectorAll('tbody tr');
    rows[0].dispatchEvent(new MouseEvent('mouseenter'));
    expect(rows[0].style.backgroundColor).toBe('rgb(248, 249, 250)');
    rows[0].dispatchEvent(new MouseEvent('mouseleave'));
    expect(rows[0].style.backgroundColor).toBe('');
  });

  it('submit buttons are disabled with spinner on click', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const btn = document.querySelector('button[type="submit"]');
    btn.click();
    expect(btn.disabled).toBe(true);
    expect(btn.innerHTML).toContain('fa-spinner');
  });

  it('critical rows get pulse animation', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const critical = document.querySelector('tr.table-danger');
    expect(critical.style.animation).toContain('pulse');
  });

  it('exposes window.refreshQueue', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
    expect(typeof window.refreshQueue).toBe('function');
  });

  it('setInterval triggers reload when table has rows', async () => {
    vi.useFakeTimers();
    await loadModule('static/js/pages/emergency/patient_queue.js');
    vi.advanceTimersByTime(15000);
    expect(window.location.reload).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('setInterval does not trigger reload when table empty', async () => {
    document.body.innerHTML = '<table><tbody></tbody></table>';
    vi.useFakeTimers();
    await loadModule('static/js/pages/emergency/patient_queue.js');
    vi.advanceTimersByTime(15000);
    expect(window.location.reload).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});