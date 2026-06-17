function refreshQueue() {
    location.reload();
}

// Auto-refresh every 15 seconds for emergency cases
setInterval(function() {
    // Only refresh if there are emergency cases
    const table = document.querySelector('table tbody');
    if (table && table.children.length > 0) {
        refreshQueue();
    }
}, 15000);

// Add click handlers for better UX
document.addEventListener('DOMContentLoaded', function() {
    // Add hover effects to table rows
    const rows = document.querySelectorAll('table tbody tr');
    rows.forEach(row => {
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8f9fa';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // Add loading states to buttons
    const buttons = document.querySelectorAll('button[type="submit"]');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>جاري المعالجة...';
            this.disabled = true;
        });
    });
    
    // Highlight critical cases
    const criticalRows = document.querySelectorAll('tr.table-danger');
    criticalRows.forEach(row => {
        row.style.animation = 'pulse 2s infinite';
    });
});
