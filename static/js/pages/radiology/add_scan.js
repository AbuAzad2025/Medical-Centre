document.addEventListener('DOMContentLoaded', function() {
    const scanDateInput = document.querySelector('input[name="scan_date"]');
    if (!scanDateInput) return;
    scanDateInput.value = new Date().toISOString().split('T')[0];
});

export {};
