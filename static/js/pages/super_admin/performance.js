// محاكاة تحديث البيانات
function updatePerformanceData() {
    document.getElementById('cpu-usage').textContent = Math.floor(Math.random() * 100) + '%';
    document.getElementById('memory-usage').textContent = Math.floor(Math.random() * 100) + '%';
    document.getElementById('disk-usage').textContent = Math.floor(Math.random() * 100) + '%';
    document.getElementById('uptime').textContent = Math.floor(Math.random() * 24);
}

// تحديث البيانات كل 5 ثوانٍ
setInterval(updatePerformanceData, 5000);
updatePerformanceData();
