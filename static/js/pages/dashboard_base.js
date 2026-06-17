// Hide page loader when DOM is ready
      document.addEventListener('DOMContentLoaded', function() {
        const loader = document.getElementById('pageLoader');
        if (loader) {
          setTimeout(function() { loader.classList.add('hidden'); }, 250);
        }
      });
