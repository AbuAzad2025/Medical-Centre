var __M = window.__M || [];
const entities = __M0__;
const previewUrl = __M1__;
const csrfToken = __M2__;
const saveUrl = __M3__;
const listUrl = __M4__;
const initialConfig = __M5__ || {};
let activeTemplateId = __M6__;

function renderFieldsForEntity(key, selectedFields) {
  const container = document.getElementById('fieldsContainer');
  container.innerHTML = '';
  if (!key || !entities[key]) return;
  const selected = new Set(selectedFields || []);
  entities[key].fields.forEach(f => {
    const checked = selected.size ? selected.has(f) : true;
    container.innerHTML += '<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" name="fields" value="'+f+'"'+(checked?' checked':'')+'><label class="form-check-label">'+f+'</label></div>';
  });
}

document.getElementById('entitySelect').addEventListener('change', function() {
  renderFieldsForEntity(this.value, []);
});

document.getElementById('templateSelect').addEventListener('change', function() {
  const id = this.value;
  if (!id) {
    activeTemplateId = null;
    document.getElementById('templateName').value = '';
    document.getElementById('runTemplateBtn').disabled = true;
    return;
  }
  window.location.href = window.location.pathname + '?template=' + id;
});

function collectPayload() {
  return {
    entity: document.getElementById('entitySelect').value,
    fields: Array.from(document.querySelectorAll('input[name="fields"]:checked')).map(cb => cb.value),
    limit: document.getElementById('limitInput').value,
    name: document.getElementById('templateName').value.trim(),
    template_id: activeTemplateId,
  };
}

function renderTable(data) {
  const el = document.getElementById('reportResult');
  if (!data.success) {
    el.innerHTML = '<div class="alert alert-danger">'+ (data.message || 'تعذّر إنشاء التقرير') +'</div>';
    return;
  }
  let html = '<table class="table table-sm table-bordered"><thead><tr>';
  data.headers.forEach(h => html += '<th>'+h+'</th>');
  html += '</tr></thead><tbody>';
  data.rows.forEach(row => {
    html += '<tr>'; data.headers.forEach(h => html += '<td>'+(row[h]||'')+'</td>'); html += '</tr>';
  });
  html += '</tbody></table>';
  el.innerHTML = html;
}

function generateReport() {
  const payload = collectPayload();
  fetch(previewUrl, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(renderTable).catch(() => {
    document.getElementById('reportResult').innerHTML = '<div class="alert alert-danger">انقطع الاتصال. حاول مرة أخرى.</div>';
  });
}

document.getElementById('generateBtn').addEventListener('click', generateReport);

document.getElementById('saveTemplateBtn').addEventListener('click', function() {
  const payload = collectPayload();
  if (!payload.name) {
    document.getElementById('reportResult').innerHTML = '<div class="alert alert-warning">أدخل اسماً للقالب قبل الحفظ.</div>';
    return;
  }
  fetch(saveUrl, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: JSON.stringify(payload)
  }).then(r => r.json()).then(data => {
    if (!data.success) {
      document.getElementById('reportResult').innerHTML = '<div class="alert alert-danger">'+ (data.message || 'تعذّر حفظ القالب') +'</div>';
      return;
    }
    activeTemplateId = data.template.id;
    document.getElementById('runTemplateBtn').disabled = false;
    document.getElementById('reportResult').innerHTML = '<div class="alert alert-success">تم حفظ القالب بنجاح.</div>';
  });
});

document.getElementById('runTemplateBtn').addEventListener('click', function() {
  if (!activeTemplateId) return;
  const runUrl = __M7__ + activeTemplateId + '/run';
  fetch(runUrl, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
    body: '{}'
  }).then(r => r.json()).then(renderTable);
});

if (initialConfig.entity) {
  renderFieldsForEntity(initialConfig.entity, initialConfig.fields || []);
  if (activeTemplateId) {
    document.getElementById('runTemplateBtn').disabled = false;
  }
}
