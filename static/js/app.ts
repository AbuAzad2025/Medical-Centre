/* Dark mode (already converted) - re-export */
export { };

/* App initialization - TypeScript */
interface AppConfig {
  debug: boolean;
  apiUrl: string;
  locale: string;
}

const config: AppConfig = {
  debug: false,
  apiUrl: '/api',
  locale: document.documentElement.lang || 'ar',
};

function initApp(): void {
  console.log('AZAD Medical App initialized', config);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}