/* Unified PWA service worker — §25.4 (staff + portal) */
const CACHE_NAME = 'azad-med-pwa-v1';
const OFFLINE_URL = '/pwa/offline';

const SHELL = [
  '/',
  '/auth/login',
  OFFLINE_URL,
  '/static/manifest.json',
  '/static/css/design-tokens.css',
  '/static/css/clinical.css',
  '/static/css/core.css',
  '/static/css/components.css',
  '/static/css/layout.css',
  '/static/css/mobile.css',
  '/static/css/touch.css',
  '/static/js/base.js',
  '/static/js/pwa-install.js',
  '/static/img/icon-192x192.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL).catch(() => Promise.resolve()))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/socket.io')) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => {
        if (cached) return cached;
        if (event.request.mode === 'navigate') {
          return caches.match(OFFLINE_URL);
        }
        return new Response('Offline', { status: 503, statusText: 'Offline' });
      }))
  );
});
