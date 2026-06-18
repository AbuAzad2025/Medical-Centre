var __M = window.__M || [];
function loadDoctors(){
  const dept = document.getElementById('department_id').value;
  const url = __M0__ + (dept ? ('?department_id='+dept) : '');
  fetch(url).then(r=>r.json()).then(d=>{
    const sel = document.getElementById('doctor_id'); sel.innerHTML = '<option value="">اختر الطبيب</option>';
    (d.doctors||[]).forEach(x=>{ const o=document.createElement('option'); o.value=x.id; o.textContent=x.full_name; sel.appendChild(o); });
  }).catch(err => console.error('فشل تحميل الأطباء:', err));
}
function loadTimes(){
  const doc = document.getElementById('doctor_id').value;
  const dt = document.getElementById('appointment_date').value;
  if(!doc || !dt) return;
  const url = __M1__ + `?doctor_id=${doc}&date=${dt}`;
  fetch(url).then(r=>r.json()).then(d=>{
    const sel = document.getElementById('appointment_time'); sel.innerHTML = '<option value="">اختر الوقت</option>';
    (d.available_times||[]).forEach(t=>{ const o=document.createElement('option'); o.value=t; o.textContent=t; sel.appendChild(o); });
  }).catch(err => console.error('فشل تحميل المواعيد:', err));
}
