import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadScript } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <div id="app"></div>
    <table id="unitsTable"><tbody>
      <tr data-status="active"><td>Reception</td><td>Module</td><td>5</td><td><span class="badge bg-success">نشط</span></td></tr>
      <tr data-status="inactive"><td>Lab</td><td>Module</td><td>3</td><td><span class="badge bg-danger">معطل</span></td></tr>
    </tbody></table>
    <button class="btn-outline-primary">All</button>
    <button class="btn-outline-success">Active</button>
    <button class="btn-outline-danger">Inactive</button>
    <meta name="csrf-token" content="test-token" />
  `;
  window.API_ROUTES = {};
  window.escHtml = (s) => String(s || '');
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
  global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ success: true }) });
  delete window.location;
  window.location = { href: '', reload: vi.fn() };
});

describe('manager/unit_control.js', () => {
  test('loads without critical errors', async () => {
    await loadScript('static/js/pages/manager/unit_control.js');
  });

  test('filterUnits is a function', async () => {
    await loadScript('static/js/pages/manager/unit_control.js');
    expect(typeof filterUnits).toBe('function');
  });

  test('filterUnits with event parameter adds active class', async () => {
    await loadScript('static/js/pages/manager/unit_control.js');
    const btn = document.querySelector('.btn-outline-primary');
    const event = { target: btn };
    filterUnits('all', event);
    expect(btn.classList.contains('active')).toBe(true);
  });

  test('filterUnits filters active rows', async () => {
    await loadScript('static/js/pages/manager/unit_control.js');
    filterUnits('active');
    const rows = document.querySelectorAll('#unitsTable tbody tr');
    expect(rows[0].style.display).toBe('');
    expect(rows[1].style.display).toBe('none');
  });

  test('exportUnitsReport is a function', async () => {
    await loadScript('static/js/pages/manager/unit_control.js');
    expect(typeof exportUnitsReport).toBe('function');
  });
});
