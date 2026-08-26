var __M = window.__M || [];
const RX_TEMPLATES = __M0__;

function showSafetyModal(alerts, onOverride) {
  const existing = document.getElementById('safetyOverrideModal');
  if (existing) existing.remove();
  const modal = document.createElement('div');
  modal.id = 'safetyOverrideModal';
  modal.className = 'modal fade show';
  modal.style.display = 'block';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  const header = document.createElement('div');
  header.className = 'modal-header bg-danger text-white';
  header.innerHTML = '<h5 class="modal-title"><i class="fas fa-exclamation-triangle me-2"></i>تنبيه أمان سريري</h5>';
  modal.appendChild(header);
  const body = document.createElement('div');
  body.className = 'modal-body';
  body.innerHTML = '<p class="fw-bold">تم اكتشاف تحذيرات أمان حرجة قبل إنشاء الوصفة:</p>';
  const list = document.createElement('ul');
  list.className = 'list-group mb-3';
  alerts.forEach(function (a) {
    const li = document.createElement('li');
    li.className = 'list-group-item list-group-item-' + (a.severity === 'hard_stop' ? 'danger' : 'warning');
    li.textContent = a.message;
    list.appendChild(li);
  });
  body.appendChild(list);
  const formGroup = document.createElement('div');
  formGroup.className = 'mb-3';
  formGroup.innerHTML = '<label class="form-label">سبب التجاوز (إجباري):</label>' +
    '<textarea class="form-control" id="overrideNote" rows="3" required placeholder="أدخل سبب تجاوز تحذير الأمان هذا..."></textarea>';
  body.appendChild(formGroup);
  modal.appendChild(body);
  const footer = document.createElement('div');
  footer.className = 'modal-footer';
  const cancelBtn = document.createElement('button');
  cancelBtn.type = 'button';
  cancelBtn.className = 'btn btn-secondary';
  cancelBtn.textContent = 'إلغاء';
  cancelBtn.addEventListener('click', function () { modal.remove(); });
  footer.appendChild(cancelBtn);
  const confirmBtn = document.createElement('button');
  confirmBtn.type = 'button';
  confirmBtn.className = 'btn btn-danger';
  confirmBtn.textContent = 'تأكيد التجاوز';
  confirmBtn.disabled = true;
  confirmBtn.addEventListener('click', function () {
    const note = document.getElementById('overrideNote').value.trim();
    if (!note) return;
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'جاري المعالجة...';
    onOverride(note);
  });
  footer.appendChild(confirmBtn);
  modal.appendChild(footer);
  document.body.appendChild(modal);
  const backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop fade show';
  document.body.appendChild(backdrop);
  document.addEventListener('keydown', function escHandler(e) {
    if (e.key === 'Escape') { modal.remove(); backdrop.remove(); document.removeEventListener('keydown', escHandler); }
  });
}

function parseMedicationRef(value) {
  const v = (value || '').trim();
  if (!v) return { id: '', label: '' };
  if (v.includes('|')) {
    const parts = v.split('|');
    const id = (parts[0] || '').trim();
    const label = (parts.slice(1).join('|') || '').trim();
    return { id, label };
  }
  return { id: '', label: v };
}

function createRxRow(initial) {
  const tbody = document.querySelector('#rxItemsTable tbody');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>
      <input type="text" class="form-control medication-ref" name="item_medication_ref[]" list="medications_list" placeholder="ابدأ بالكتابة للاختيار" required>
      <input type="hidden" class="medication-id" name="item_medication_id[]">
    </td>
    <td><input type="text" class="form-control" name="item_dosage[]" placeholder="مثال: قرص واحد" required></td>
    <td><input type="text" class="form-control" name="item_frequency[]" placeholder="مثال: مرتين يومياً" required></td>
    <td><input type="number" min="1" class="form-control" name="item_duration_days[]" value="7" required></td>
    <td><input type="number" min="1" class="form-control" name="item_quantity[]" value="1" required></td>
    <td><input type="text" class="form-control" name="item_instructions[]" placeholder="قبل الطعام"></td>
    <td class="text-end">
      <button type="button" class="btn btn-sm btn-outline-danger remove-item-btn" title="حذف" aria-label="حذف البند"><i class="fas fa-times"></i> <span class="btn-label">إزالة</span></button>
    </td>
  `;
  tbody.appendChild(tr);

  const refInput = tr.querySelector('.medication-ref');
  const idInput = tr.querySelector('.medication-id');

  refInput.addEventListener('input', function() {
    const p = parseMedicationRef(this.value);
    idInput.value = p.id || '';
  });

  tr.querySelector('.remove-item-btn').addEventListener('click', function() {
    tr.remove();
    ensureAtLeastOneRow();
  });

  if (initial) {
    if (initial.medication_id) {
      const label = initial.medication_label ? (initial.medication_id + '|' + initial.medication_label) : (String(initial.medication_id));
      refInput.value = label;
      idInput.value = String(initial.medication_id);
    } else if (initial.medication_ref) {
      refInput.value = initial.medication_ref;
      const p = parseMedicationRef(initial.medication_ref);
      idInput.value = p.id || '';
    }
    tr.querySelector('[name="item_dosage[]"]').value = initial.dosage || '';
    tr.querySelector('[name="item_frequency[]"]').value = initial.frequency || '';
    tr.querySelector('[name="item_duration_days[]"]').value = initial.duration_days || 7;
    tr.querySelector('[name="item_quantity[]"]').value = initial.quantity || 1;
    tr.querySelector('[name="item_instructions[]"]').value = initial.instructions || '';
  }
}

function ensureAtLeastOneRow() {
  const tbody = document.querySelector('#rxItemsTable tbody');
  if (!tbody.children.length) createRxRow();
}

document.getElementById('addRxItemBtn').addEventListener('click', function() {
  createRxRow();
});

document.getElementById('applyTemplateBtn').addEventListener('click', function() {
  const tplId = (document.getElementById('templateSelect').value || '').trim();
  if (!tplId) return;
  const tpl = (RX_TEMPLATES || []).find(t => String(t.id) === String(tplId));
  if (!tpl || !tpl.items) return;
  const tbody = document.querySelector('#rxItemsTable tbody');
  tbody.innerHTML = '';
  (tpl.items || []).forEach(it => createRxRow(it));
  ensureAtLeastOneRow();
});

document.addEventListener('DOMContentLoaded', function() {
  ensureAtLeastOneRow();
  const form = document.getElementById('prescriptionForm');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    const items = form.querySelectorAll('.medication-id');
    let hasItems = false;
    items.forEach(function(inp) { if (inp.value.trim()) hasItems = true; });
    if (!hasItems) return;
    e.preventDefault();
    const fd = new FormData(form);
    const csrfEl = form.querySelector('input[name="csrf_token"]') || document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfEl ? (csrfEl.value || csrfEl.content || '') : '';
    fetch(form.action, { method: 'POST', body: fd, credentials: 'same-origin', headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}) })
      .then(function(r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      })
      .then(function(data) {
        if (data.success) { window.location.href = form.getAttribute('data-success-url') || window.location.href; }
        else if (data.hard_stops && data.hard_stops.length) {
          showSafetyModal(data.hard_stops, function(note) {
            fd.append('overridden', '1');
            fd.append('override_note', note);
            fetch(form.action, { method: 'POST', body: fd, credentials: 'same-origin', headers: Object.assign({ 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}) })
              .then(function(r2) {
                if (!r2.ok) throw new Error(r2.status);
                return r2.json();
              })
              .then(function(d2) {
                if (d2.success) { window.location.href = form.getAttribute('data-success-url') || window.location.href; }
                else { showSafetyModal([d2.message || 'خطأ غير معروف'], function(){}); }
              });
          });
        } else {
          var errEl = document.getElementById('prescriptionError');
          if (errEl) { errEl.textContent = data.message || 'حدث خطأ غير متوقع'; errEl.classList.remove('d-none'); }
        }
      });
  });
});
