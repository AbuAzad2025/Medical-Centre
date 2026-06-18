var __M = window.__M || [];
const entities = __M0__;
document.getElementById('entitySelect').addEventListener('change', function() {
  const key = this.value;
  const container = document.getElementById('fieldsContainer');
  container.innerHTML = '';
  if (key && entities[key]) {
    entities[key].fields.forEach(f => {
      container.innerHTML += '<div class="form-check form-check-inline"><input class="form-check-input" type="checkbox" name="fields" value="'+f+'" checked><label class="form-check-label">'+f+'</label></div>';
    });
  }
});
function generateReport() {
  const entity = document.getElementById('entitySelect').value;
  const fields = Array.from(document.querySelectorAll('input[name="fields"]:checked')).map(cb => cb.value);
  const limit = document.getElementById('limitInput').value;
  fetch(__M1__, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': __M2__},
    body: JSON.stringify({entity, fields, limit})
  }).then(r => r.json()).then(data => {
    const el = document.getElementById('reportResult');
    if (!data.success) { el.innerHTML = '<div class="alert alert-danger">'+data.message+'</div>'; return; }
    let html = '<table class="table table-sm table-bordered"><thead><tr>';
    data.headers.forEach(h => html += '<th>'+h+'</th>');
    html += '</tr></thead><tbody>';
    data.rows.forEach(row => {
      html += '<tr>'; data.headers.forEach(h => html += '<td>'+(row[h]||'')+'</td>'); html += '</tr>';
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  }).catch(err => console.error('فشل إنشاء التقرير:', err));
}
