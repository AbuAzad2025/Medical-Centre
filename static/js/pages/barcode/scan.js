var __M = window.__M || [];
function submitScan() {
  const barcode = document.getElementById('barcodeInput').value;
  const action = document.getElementById('scanAction').value;
  fetch(__M0__, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': __M1__},
    body: JSON.stringify({barcode: barcode, action: action})
  }).then(r => r.json()).then(data => {
    const el = document.getElementById('scanResult');
    if (data.success) {
      el.innerHTML = '<div class="alert alert-success">'+data.entity_type+' #'+data.entity_id+'</div>';
    } else {
      el.innerHTML = '<div class="alert alert-danger">'+data.message+'</div>';
    }
  }).catch(err => console.error('فشل مسح الباركود:', err));
}
document.getElementById('barcodeInput').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') submitScan();
});
