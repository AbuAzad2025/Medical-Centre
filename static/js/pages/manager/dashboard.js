var __M = window.__M || [];
const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content;
const runBtn = document.getElementById('runWhatIf');
if (runBtn) {
    runBtn.addEventListener('click', async () => {
        const staff = parseInt(document.getElementById('what_if_staff').value || '0', 10);
        const rooms = parseInt(document.getElementById('what_if_rooms').value || '0', 10);
        try {
            const r = await fetch(__M0__, {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }, csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
                credentials: 'same-origin',
                body: JSON.stringify({ add_staff: staff, add_rooms: rooms })
            });
            if (!r.ok) throw new Error('http_' + r.status);
            const data = await r.json().catch(() => ({}));
            document.getElementById('whatIfThroughput').textContent = data.predicted_throughput ?? '-';
            document.getElementById('whatIfWait').textContent = (data.predicted_wait_minutes ?? '-') + ' دقيقة';
            document.getElementById('whatIfRevenue').textContent = data.predicted_revenue ?? '-';
        } catch (err) {
            if (window.showToast) window.showToast('حدث خطأ أثناء تحميل البيانات'); else alert('حدث خطأ أثناء تحميل البيانات');
        }
    });
}
