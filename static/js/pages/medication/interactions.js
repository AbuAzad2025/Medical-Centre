var __M = window.__M || [];
const csrfToken = __M0__;
async function toggleInteraction(id) {
  try {
    const url = ((window.API_ROUTES && window.API_ROUTES.medication_toggle_interaction) || '/medication/interactions/0/toggle').replace('/0', '/' + id);
    const res = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': csrfToken } });
    if (res.ok) location.reload();
  } catch (err) {
    /* فشل تبديل حالة التفاعل: */
  }
}
