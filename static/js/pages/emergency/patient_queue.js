export function refreshQueue() {
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

    // Native form submission must not be cancelled by mutating the submit
    // button inside its click handler. base.js handles the busy state on submit.

    const criticalRows = document.querySelectorAll('tr.table-danger');
    criticalRows.forEach(row => {
        row.style.animation = 'pulse 2s infinite';
    });
});


// Backward compatibility
if (typeof refreshQueue !== "undefined") window.refreshQueue = refreshQueue;
