var __M = window.__M || [];
const csrfToken = __M0__;
document.getElementById('approveBtn')?.addEventListener('click', async () => {
  try {
    const res = await fetch(__M1__, { method: 'POST', headers: { 'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
    if (!res.ok) throw new Error('http_' + res.status);
    if (res.ok) location.reload();
  } catch (err) {
    if (window.showToast) window.showToast('حدث خطأ أثناء الموافقة على طلب التوريد'); else alert('حدث خطأ أثناء تحميل البيانات');
  }
});
