if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/pwa/sw.js', { scope: '/' });
}
