// Service Worker for Medical System
// Simple service worker for PWA capabilities

const CACHE_NAME = 'medical-system-v1';
const urlsToCache = [
  '/',
  '/static/css/core.css',
  '/static/css/components.css',
  '/static/css/layout.css',
  '/static/js/app.js',
  '/static/js/csrf.js',
  '/static/js/flash.js',
  '/static/js/security.js',
  '/static/js/performance.js'
];

// Install event - cache resources and activate immediately
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching files');
        return cache.addAll(urlsToCache);
      })
      .catch(err => console.log('Service Worker: Cache failed', err))
  );
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Service Worker: Clearing old cache');
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      })
      .catch(() => {
        // Fallback for offline
        return caches.match('/');
      })
  );
});

