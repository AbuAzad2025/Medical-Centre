var __M = window.__M || [];
const csrfToken = __M0__;
document.getElementById('approveBtn')?.addEventListener('click', async () => {
  try {
    const res = await fetch(__M1__, { method: 'POST', headers: { 'X-CSRFToken': csrfToken } });
    if (res.ok) location.reload();
  } catch (err) {
    console.error('فشل الموافقة على طلب التوريد:', err);
  }
});
