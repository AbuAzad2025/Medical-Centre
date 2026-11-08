document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form');
    if (!form) return;
    const inputs = form.querySelectorAll('input, textarea');

    inputs.forEach(input => {
        input.addEventListener('input', function() {
            form.classList.add('dirty');
        });
    });

    window.addEventListener('beforeunload', function(e) {
        if (form.classList.contains('dirty')) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});

export {};
