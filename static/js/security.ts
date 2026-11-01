/* Security utilities - TypeScript */
function sanitizeHtml(str: string): string {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str: string): string {
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function validateCsrfToken(token: string): boolean {
  return token.length > 0;
}

function secureFetch(url: string, options?: RequestInit): Promise<Response> {
  const csrfToken = (window as any).getCsrfToken?.() || '';
  const headers = {
    ...((options?.headers as Record<string, string>) || {}),
    'X-CSRFToken': csrfToken,
  };
  return fetch(url, { ...options, headers, credentials: 'same-origin' });
}

(window as any).sanitizeHtml = sanitizeHtml;
(window as any).escapeAttr = escapeAttr;
(window as any).validateCsrfToken = validateCsrfToken;
(window as any).secureFetch = secureFetch;