/* Lazy loading for images and heavy components - TypeScript */
(function(): void {
  'use strict';

  // Lazy load images with IntersectionObserver
  function initLazyImages(): void {
    const images = document.querySelectorAll('img[data-src]');
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const img = entry.target as HTMLImageElement;
            img.src = img.dataset.src || '';
            if (img.dataset.srcset) img.srcset = img.dataset.srcset;
            img.classList.add('loaded');
            observer.unobserve(img);
          }
        });
      }, { rootMargin: '50px' });

      images.forEach((img) => observer.observe(img));
    } else {
      // Fallback for older browsers
      images.forEach((img) => {
        const el = img as HTMLImageElement;
        el.src = el.dataset.src || '';
      });
    }
  }

  // Lazy load heavy components (charts, tables)
  function initLazyComponents(): void {
    const components = document.querySelectorAll('[data-lazy-component]');
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const el = entry.target as HTMLElement;
            const componentName = el.dataset.lazyComponent;
            if (componentName) {
              // Load component
              el.classList.add('loaded');
              observer.unobserve(el);
            }
          }
        });
      }, { rootMargin: '100px' });

      components.forEach((comp) => observer.observe(comp));
    }
  }

  // Preload critical resources
  function preloadCritical(): void {
    const links = [
      { rel: 'preload', href: '/static/css/medical-professional.css', as: 'style' },
      { rel: 'preload', href: '/static/js/dark-mode.js', as: 'script' },
    ];
    links.forEach((link) => {
      const el = document.createElement('link');
      el.rel = link.rel;
      el.href = link.href;
      el.as = link.as;
      document.head.appendChild(el);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initLazyImages();
    initLazyComponents();
    preloadCritical();
  });
})();