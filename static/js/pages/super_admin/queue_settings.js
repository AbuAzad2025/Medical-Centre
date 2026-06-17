var __M = window.__M || [];
const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
const tbody = document.getElementById('queueSettingsBody');
const saveBtn = document.getElementById('saveQueueSettingsBtn');

function boolSelect(value) {
  const v = value ? '1' : '0';
  return `
    <select class="form-select form-select-sm" data-type="bool" value="${v}">
      <option value="1" ${v === '1' ? 'selected' : ''}>نعم</option>
      <option value="0" ${v === '0' ? 'selected' : ''}>لا</option>
    </select>
  `;
}

function intInput(value, min, max) {
  const v = (value === null || value === undefined) ? '' : String(value);
  const mn = (min === null || min === undefined) ? '' : `min="${min}"`;
  const mx = (max === null || max === undefined) ? '' : `max="${max}"`;
  return `<input class="form-control form-control-sm" data-type="int" type="number" value="${v}" ${mn} ${mx}>`;
}

async function loadSettings() {
  const r = await fetch(`__M0__?action=load`, { method: 'GET' });
  const data = await r.json().catch(() => ({}));
  if (!data || !data.success) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-danger py-4">فشل التحميل</td></tr>';
    return;
  }
  const items = Array.isArray(data.items) ? data.items : [];
  tbody.innerHTML = '';
  items.forEach(it => {
    const tr = document.createElement('tr');
    tr.dataset.departmentId = it.department_id;
    tr.innerHTML = `
      <td class="ps-3 fw-semibold">${String(it.department_name || it.department_id)}</td>
      <td>${intInput(it.max_queue_size, 1, 999)}</td>
      <td>${boolSelect(it.payment_required)}</td>
      <td>${boolSelect(it.emergency_payment_waived)}</td>
      <td>${boolSelect(it.force_entry_allowed)}</td>
      <td>${intInput(it.average_wait_time, 0, 999)}</td>
      <td>${boolSelect(it.allow_partial_payment)}</td>
      <td>${boolSelect(it.allow_debt)}</td>
    `;
    tbody.appendChild(tr);
  });
  if (items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-4">لا بيانات</td></tr>';
  }
}

function collectSettings() {
  const rows = Array.from(tbody.querySelectorAll('tr[data-department-id]'));
  const items = rows.map(tr => {
    const deptId = parseInt(tr.dataset.departmentId, 10);
    const cells = tr.querySelectorAll('td');
    const inputs = tr.querySelectorAll('input[data-type="int"]');
    const selects = tr.querySelectorAll('select[data-type="bool"]');
    const maxQueue = inputs[0] ? parseInt(inputs[0].value || '0', 10) : 50;
    const avgWait = inputs[1] ? parseInt(inputs[1].value || '0', 10) : 30;
    const bools = Array.from(selects).map(s => (s.value === '1'));
    return {
      department_id: deptId,
      max_queue_size: maxQueue,
      payment_required: bools[0],
      emergency_payment_waived: bools[1],
      force_entry_allowed: bools[2],
      average_wait_time: avgWait,
      allow_partial_payment: bools[3],
      allow_debt: bools[4]
    };
  });
  return { items };
}

if (saveBtn) {
  saveBtn.addEventListener('click', async function () {
    saveBtn.disabled = true;
    const payload = collectSettings();
    const r = await fetch(`__M1__`, {
      method: 'POST',
      headers: Object.assign({ 'Content-Type': 'application/json' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
      body: JSON.stringify(payload)
    });
    saveBtn.disabled = false;
    if (!r.ok) {
      window.alert('فشل الحفظ');
      return;
    }
    const data = await r.json().catch(() => ({}));
    if (data && data.success) {
      window.alert('تم الحفظ');
      loadSettings();
      return;
    }
    window.alert('فشل الحفظ');
  });
}

document.addEventListener('DOMContentLoaded', function () {
  loadSettings();
});
