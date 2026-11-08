import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <div id="aiMessages" class="ai-messages"></div>
    <input type="text" id="aiInput" value="">
    <button id="sendBtn">إرسال</button>
    <button class="quick-command" data-command="analyze">تحليل النظام</button>
    <button class="quick-command" data-command="report">إنشاء تقرير</button>
    <button class="quick-command" data-command="optimize">اقتراحات التحسين</button>
    <button class="quick-command" data-command="backup">نسخة احتياطية</button>
  `;
}

beforeEach(() => {
  baseDom();
  window.__M = [];
  window.API_ROUTES = {};
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }), showLoading: vi.fn() };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ success: true, response: 'إليك تحليل النظام: كل شيء جيد', actions: [] }),
  });
});

describe('super_admin/dashboard.js', () => {
  it('sendBtn click posts the question to the AI endpoint and renders the response', async () => {
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('aiInput');
    input.value = 'حلل أداء النظام';
    document.getElementById('sendBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = global.fetch.mock.calls[0];
    expect(url).toBe('/super-admin/api/ai-assistant');
    expect(init.headers['X-CSRFToken']).toBe('test-csrf');
    expect(JSON.parse(init.body)).toEqual({ message: 'حلل أداء النظام' });
    expect(document.getElementById('aiMessages').textContent).toContain('إليك تحليل النظام');
    expect(document.getElementById('aiMessages').textContent).toContain('حلل أداء النظام');
    expect(input.value).toBe('');
  });

  it('pressing Enter inside the AI input sends the message', async () => {
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const input = document.getElementById('aiInput');
    input.value = 'ما هي التحسينات المقترحة؟';
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).toHaveBeenCalled();
    expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({ message: 'ما هي التحسينات المقترحة؟' });
  });

  it('empty input does not call the endpoint', async () => {
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('aiInput').value = '   ';
    document.getElementById('sendBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('quick-command buttons send their fixed prompts', async () => {
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.querySelector('[data-command="analyze"]').click();
    document.querySelector('[data-command="report"]').click();
    // loadModule re-imports per test, so listeners from earlier tests in the
    // file can multiply-fire; assert both prompts were sent rather than indices.
    await new Promise(r => setTimeout(r, 30));
    const sent = global.fetch.mock.calls.map(c => JSON.parse(c[1].body).message);
    expect(sent).toContain('حلل أداء النظام');
    expect(sent).toContain('أنشئ تقرير ملخص');
  });

  it('server failure renders a gentle error bubble instead of leaking fetch errors', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network'));
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('aiInput').value = 'مرحبا';
    document.querySelector('[data-command="optimize"]').click();
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('aiMessages').textContent).toContain('تعذر معالجة طلبك');
  });

  it('exportSystemData posts to the export endpoint after confirmation', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, message: 'تم', download_url: '/super-admin/download-export/file.json' }),
    });
    document.body.innerHTML += '<a id="tmpAnchor"></a>';
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.exportSystemData();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch).toHaveBeenCalledWith('/super-admin/export-data', expect.objectContaining({ method: 'POST' }));
    clickSpy.mockRestore();
  });

  it('exportSystemData cancel does not call fetch', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.exportSystemData();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

describe('super_admin/dashboard.js remaining arms', () => {
  it('uses API_ROUTES overrides for the AI endpoint', async () => {
    window.API_ROUTES = { ai_assistant: '/custom/ai' };
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.askAiAssistant('?? ?? ??????');
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/ai');
  });

  it('uses API_ROUTES override for the export endpoint', async () => {
    window.API_ROUTES = { export_system_data: '/custom/export' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, message: '??', download_url: '/x' }),
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.exportSystemData();
    await new Promise(r => setTimeout(r, 40));
    expect(global.fetch.mock.calls[0][0]).toBe('/custom/export');
  });

  it('response without d.response renders the fallback bubble', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true }),
    });
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.askAiAssistant('مرحبا');
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('aiMessages').textContent).toContain('تعذر معالجة طلبك');
  });

  it('success:false renders the fallback bubble too', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, response: '?? ????' }),
    });
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.askAiAssistant('?????');
    await new Promise(r => setTimeout(r, 20));
    expect(document.getElementById('aiMessages').textContent).toContain('?? ????');
  });

  it('quick-command with unknown data-command does nothing', async () => {
    document.body.insertAdjacentHTML('beforeend', '<button id="mysteryCmd" class="quick-command" data-command="mystery">x</button>');
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    const before = global.fetch.mock.calls.length;
    document.getElementById('mysteryCmd').click();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls.length).toBe(before);
  });

  it('askAiAssistant with missing aiMessages container does not crash', async () => {
    document.getElementById('aiMessages').remove();
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    expect(() => mod.askAiAssistant('?????')).not.toThrow();
    await new Promise(r => setTimeout(r, 20));
  });

  it('sendBtn click with empty input does not call fetch', async () => {
    await loadModule('static/js/pages/super_admin/dashboard.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));
    document.getElementById('aiInput').value = '';
    const before = global.fetch.mock.calls.length;
    document.getElementById('sendBtn').click();
    await new Promise(r => setTimeout(r, 20));
    expect(global.fetch.mock.calls.length).toBe(before);
  });

  it('exportSystemData failure shows error Swal', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, message: '?? ???? ?????' }),
    });
    const mod = await loadModule('static/js/pages/super_admin/dashboard.js');
    mod.exportSystemData();
    await new Promise(r => setTimeout(r, 40));
    const last = window.Swal.fire.mock.calls[window.Swal.fire.mock.calls.length - 1][0];
    expect(last.icon).toBe('error');
    expect(last.text).toBe('?? ???? ?????');
  });
});
