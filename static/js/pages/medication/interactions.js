var __M = window.__M || [];
const csrfToken = __M0__;
async function toggleInteraction(id) {
  try {
    const url = ((window.API_ROUTES && window.API_ROUTES.medication_toggle_interaction) || '/medication/interactions/0/toggle').replace('/0', '/' + id);
    const res = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
    if (!res.ok) throw new Error('http_' + res.status);
    if (res.ok) location.reload();
  } catch (err) {
    if (window.showToast) window.showToast('حدث خطأ أثناء تبديل حالة التفاعل'); else alert('حدث خطأ أثناء تحميل البيانات');
  }
}
