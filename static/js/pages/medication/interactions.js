var __M = window.__M || [];
const csrfToken = __M0__;
async function toggleInteraction(id) {
  const res = await fetch(`/medication/interactions/${id}/toggle`, { method: 'POST', headers: { 'X-CSRFToken': csrfToken } });
  if (res.ok) location.reload();
}
