'use strict';

// Standalone-safe escaping: the kiosk shell does load base.js, but this page
// must never render server data raw even if that script fails to arrive.
function escapeHtml(v) {
  return String(v == null ? '' : v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function doCheckIn() {
  var input = document.getElementById('nationalId');
  var result = document.getElementById('kioskResult');
  var submit = document.getElementById('kioskSubmit');
  var nid = (input.value || '').trim();
  if (!nid) {
    showResult(false, 'أدخل رقم الهوية');
    return;
  }
  submit.disabled = true;
  var endpoint = submit.dataset.apiUrl || '/kiosk/api/check-in';
  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ national_id: nid }),
  })
    .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
    .then(function (res) {
      var d = res.data || {};
      if (d.success) {
        var q = d.queue_number ? '<div class="display-6 my-2">' + escapeHtml(d.queue_number) + '</div>' : '';
        showResult(true, '<strong>' + escapeHtml(d.patient_name || '') + '</strong><br>' + escapeHtml(d.message || '') + q);
        if (navigator.vibrate) navigator.vibrate(10);
        input.value = '';
        setTimeout(function () { result.hidden = true; }, 8000);
      } else {
        showResult(false, escapeHtml(d.message || 'تعذر تسجيل الوصول'));
      }
    })
    .catch(function () {
      showResult(false, 'خطأ في الاتصال — حاول مرة أخرى');
    })
    .finally(function () {
      submit.disabled = false;
    });
}

export function showResult(ok, html) {
  var result = document.getElementById('kioskResult');
  result.hidden = false;
  result.className = 'mt-4 ' + (ok ? 'kiosk-result--ok' : 'kiosk-result--err');
  result.innerHTML = html;
}

var input = document.getElementById('nationalId');
var keypad = document.getElementById('kioskKeypad');
var submit = document.getElementById('kioskSubmit');
var result = document.getElementById('kioskResult');
if (!input || !keypad || !submit) {
  // skip
} else {
  var keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '⌫', '0', '✓'];
  keys.forEach(function (k) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline-secondary kiosk-key';
    btn.textContent = k;
    btn.addEventListener('click', function () {
      if (k === '⌫') {
        input.value = input.value.slice(0, -1);
      } else if (k === '✓') {
        submit.click();
      } else {
        input.value += k;
      }
      input.focus();
    });
    keypad.appendChild(btn);
  });
}

if (submit) {
  submit.addEventListener('click', doCheckIn);
}

// Backward compatibility
if (typeof doCheckIn !== 'undefined') window.doCheckIn = doCheckIn;
if (typeof showResult !== 'undefined') window.showResult = showResult;