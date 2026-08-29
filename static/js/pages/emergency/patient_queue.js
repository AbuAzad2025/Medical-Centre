function refreshQueue() {
    location.reload();
}

setInterval(function() {

    const table = document.querySelector('table tbody');
    if (table && table.children.length > 0) {
        refreshQueue();
    }
}, 15000);

document.addEventListener('DOMContentLoaded', function() {

    const rows = document.querySelectorAll('table tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });

    const buttons = document.querySelectorAll('button[type="submit"]');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>جاري المعالجة...';
            this.disabled = true;
        });
    });

    const criticalRows = document.querySelectorAll('tr.table-danger');
    criticalRows.forEach(row => {
        row.style.animation = 'pulse 2s infinite';
    });
});
