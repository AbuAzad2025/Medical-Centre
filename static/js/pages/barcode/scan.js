var __M = window.__M || [];
export function submitScan() {
  const barcode = document.getElementById('barcodeInput').value;
  const action = document.getElementById('scanAction').value;
  fetch(window.__M0__, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': window.__M1__},
    body: JSON.stringify({barcode: barcode, action: action})
  }).then(r => r.json()).then(data => {
    const el = document.getElementById('scanResult');
    if (data.success) {
      el.innerHTML = '<div class="alert alert-success"></div>';
      el.firstElementChild.textContent = data.entity_type+' #'+data.entity_id;
    } else {
      el.innerHTML = '<div class="alert alert-danger"></div>';
      el.firstElementChild.textContent = data.message;
    }
  }).catch(err => {  });
}
document.getElementById('barcodeInput').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') submitScan();
});


// Backward compatibility
if (typeof submitScan !== "undefined") window.submitScan = submitScan;
