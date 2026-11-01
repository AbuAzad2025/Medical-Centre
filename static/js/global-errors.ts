/* Global error handling - TypeScript */
interface ErrorInfo {
  message: string;
  status?: number;
  url?: string;
}

function handleError(error: ErrorInfo): void {
  console.error('Global error:', error);
  if (error.status === 401) {
    window.location.href = '/auth/login';
    return;
  }
  if (error.status === 403) {
    if (typeof (window as any).showFlash === 'function') {
      (window as any).showFlash({ type: 'error', message: 'ليس لديك صلاحية للوصول' });
    }
    return;
  }
  if (error.status === 500) {
    if (typeof (window as any).showFlash === 'function') {
      (window as any).showFlash({ type: 'error', message: 'حدث خطأ في الخادم' });
    }
    return;
  }
}

window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
  handleError({ message: String(event.reason) });
});

window.addEventListener('error', (event: ErrorEvent) => {
  handleError({ message: event.message, url: event.filename });
});

(window as any).handleError = handleError;