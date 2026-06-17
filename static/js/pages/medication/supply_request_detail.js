var __M = window.__M || [];
const csrfToken = __M0__;
document.getElementById('approveBtn')?.addEventListener('click', async () => {
  const res = await fetch(__M1__, { method: 'POST', headers: { 'X-CSRFToken': csrfToken } });
  if (res.ok) location.reload();
});
