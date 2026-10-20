import { describe, test, expect, beforeEach, vi } from 'vitest';
import { loadModule } from '../../test-utils.mjs';

beforeEach(() => {
  document.body.innerHTML = `
    <table><tbody>
      <tr><td>Patient 1</td></tr>
    </tbody></table>
  `;
  window.API_ROUTES = {};
});

describe('emergency/patient_queue.js', () => {
  test('loads without critical errors', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
  });

  test('refreshQueue is a function', async () => {
    await loadModule('static/js/pages/emergency/patient_queue.js');
    expect(typeof refreshQueue).toBe('function');
  });
});
