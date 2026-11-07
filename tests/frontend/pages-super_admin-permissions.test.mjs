import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { loadModule } from './test-utils.mjs';

function baseDom() {
  document.body.innerHTML = `
    <meta name="csrf-token" content="test-csrf">
    <div id="modalTitle"></div>
    <form id="permissionForm"></form>
    <div id="permissionModal" style="display:none"></div>
  `;
}

beforeEach(() => {
  baseDom();
  window.Swal = { fire: vi.fn().mockResolvedValue({ isConfirmed: true }) };
});

afterEach(() => {
  vi.useRealTimers();
});

describe('super_admin/permissions.js', () => {
  it('createPermission sets title and shows modal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    mod.createPermission();
    expect(document.getElementById('modalTitle').textContent).toContain('إضافة');
    expect(document.getElementById('permissionModal').style.display).toBe('block');
  });

  it('editPermission sets title and shows modal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    mod.editPermission('5');
    expect(document.getElementById('modalTitle').textContent).toContain('تعديل');
    expect(document.getElementById('permissionModal').style.display).toBe('block');
  });

  it('deletePermission confirms and submits a form on confirm', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    const submitCb = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'form') {
        const f = origCreate('form');
        f.submit = submitCb;
        return f;
      }
      return origCreate(tag);
    });
    await mod.deletePermission('5');
    expect(submitCb).toHaveBeenCalled();
    expect(document.createElement).toHaveBeenCalled();
  });

  it('deletePermission cancel does not submit', async () => {
    window.Swal.fire = vi.fn().mockResolvedValue({ isConfirmed: false });
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    const spy = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      if (tag === 'form') {
        const f = origCreate('form');
        f.submit = spy;
        return f;
      }
      return origCreate(tag);
    });
    await mod.deletePermission('5');
    expect(spy).not.toHaveBeenCalled();
  });

  it('closeModal hides modal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    document.getElementById('permissionModal').style.display = 'block';
    mod.closeModal();
    expect(document.getElementById('permissionModal').style.display).toBe('none');
  });

  it('window.onclick click on backdrop closes modal', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    document.getElementById('permissionModal').style.display = 'block';
    window.onclick({ target: document.getElementById('permissionModal') });
    expect(document.getElementById('permissionModal').style.display).toBe('none');
  });

  it('window.onclick click inside modal does not close', async () => {
    const mod = await loadModule('static/js/pages/super_admin/permissions.js');
    document.getElementById('permissionModal').style.display = 'block';
    window.onclick({ target: document.createElement('span') });
    expect(document.getElementById('permissionModal').style.display).toBe('block');
  });
});