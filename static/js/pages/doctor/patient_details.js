var __M = window.__M || [];
document.addEventListener('keydown', function(e) {
    if (e.target && ['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
    if (e.altKey && e.key === '1') document.getElementById('diagnosis-tab')?.click();
    if (e.altKey && e.key === '2') document.getElementById('prescriptions-tab')?.click();
    if (e.altKey && e.key === '3') document.getElementById('lab-tab')?.click();
    if (e.altKey && e.key === '4') document.getElementById('radiology-tab')?.click();
    if (e.altKey && e.key === '5') document.getElementById('history-tab')?.click();
    if (e.altKey && e.key.toLowerCase() === 'd') window.location.href = __M0__;
    if (e.altKey && e.key.toLowerCase() === 'r') window.location.href = __M1__;
});
