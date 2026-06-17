var __M = window.__M || [];
const presetDoctorId = __M0__;
const presetTime = __M1__;

function loadDoctors(){
  const dept = document.getElementById('department_id').value;
  const url = __M2__ + (dept ? ('?department_id='+dept) : '');
  fetch(url).then(r=>r.json()).then(d=>{
    const sel = document.getElementById('doctor_id');
    const current = sel.value || (presetDoctorId ? String(presetDoctorId) : '');
    sel.innerHTML = '<option value="">اختر الطبيب</option>';
    (d.doctors||[]).forEach(x=>{
      const o=document.createElement('option');
      o.value=x.id;
      o.textContent=x.full_name;
      if (current && String(x.id) === String(current)) o.selected = true;
      sel.appendChild(o);
    });
    loadTimes();
  });
}

function loadTimes(){
  const doc = document.getElementById('doctor_id').value;
  const dt = document.getElementById('appointment_date').value;
  const sel = document.getElementById('appointment_time');
  if(!doc || !dt){
    if (!sel.value) sel.innerHTML = '<option value="">اختر الوقت</option>';
    return;
  }
  const url = __M3__ + `?doctor_id=${doc}&date=${dt}`;
  fetch(url).then(r=>r.json()).then(d=>{
    const current = sel.value || presetTime || '';
    sel.innerHTML = '<option value="">اختر الوقت</option>';
    (d.available_times||[]).forEach(t=>{
      const o=document.createElement('option');
      o.value=t;
      o.textContent=t;
      if (current && String(t) === String(current)) o.selected = true;
      sel.appendChild(o);
    });
  });
}

function loadSmartSlots(){
  const doc = document.getElementById('doctor_id').value;
  const dt = document.getElementById('appointment_date').value;
  const hint = document.getElementById('smartSlotsHint');
  if(!doc || !dt){
    if (hint) hint.textContent = 'اختر الطبيب والتاريخ أولاً';
    return;
  }
  const url = __M4__ + `?doctor_id=${doc}&date=${dt}`;
  fetch(url).then(r=>r.json()).then(d=>{
    const list = d.suggested_times || [];
    if (hint) hint.textContent = list.length ? ('الأوقات المقترحة: ' + list.join('، ')) : 'لا توجد أوقات مقترحة';
    if (list.length) {
      const sel = document.getElementById('appointment_time');
      const current = sel.value;
      if (!current) {
        sel.value = list[0];
      }
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  const dept = document.getElementById('department_id');
  if (dept && dept.value) {
    loadDoctors();
  }
});
