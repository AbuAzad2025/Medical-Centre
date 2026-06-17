var __M = window.__M || [];
const RX_TEMPLATES = __M0__;

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
});
