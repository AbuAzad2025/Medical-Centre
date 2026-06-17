// Auto-save functionality
document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    const inputs = form.querySelectorAll('input, textarea');
    
    // Auto-save every 30 seconds
    setInterval(function() {
        const formData = new FormData(form);
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then(response => {
            if (response.ok) {
                console.log('Auto-saved successfully');
            }
        }).catch(error => {
            console.error('Auto-save failed:', error);
        });
    }, 30000);
    
    // Mark form as dirty when user types
    inputs.forEach(input => {
        input.addEventListener('input', function() {
            form.classList.add('dirty');
        });
    });
    
    // Warn before leaving if form is dirty
    window.addEventListener('beforeunload', function(e) {
        if (form.classList.contains('dirty')) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});
