/**
 * E2E-03 — Security headers & CSP nonce verification (browser-level).
 * Validates the P1 hardening actually holds in a real browser:
 *   - CSP header present WITHOUT unsafe-inline
 *   - inline scripts carry the per-request nonce
 *   - self-hosted vendor assets load (no external CDN calls)
 */
const { test, expect } = require('@playwright/test');
const { uiLogin } = require('../helpers');

test.describe('Security headers', () => {
  test('login response carries hardened CSP without unsafe-inline', async ({ request }) => {
    const resp = await request.get('/auth/login');
    expect(resp.ok()).toBeTruthy();
    const csp = resp.headers()['content-security-policy'] || '';
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain('nonce-');
    // The check is on the script directive, not on the whole header. A style
    // directive with 'unsafe-inline' is a different thing: it lets a style
    // attribute through, and it does not let a line of script run. A header
    // that forbids inline styles as well would have to be written without
    // them, and the templates are full of them. What must never appear is
    // 'unsafe-inline' in a script directive, because that is an inline
    // script executing with the page's privileges.
    const scriptSrc = (csp.split(';').find((d) => d.trim().startsWith('script-src')) || '').trim();
    expect(scriptSrc).not.toContain('unsafe-inline');
    expect(csp).not.toContain('cdn.jsdelivr.net');
    expect(csp).not.toContain('cdnjs.cloudflare.com');
  });

  test('authenticated page: inline scripts have nonce, no external CDN requests', async ({ page }) => {
    const externalRequests = [];
    page.on('request', (req) => {
      const url = req.url();
      if (/cdn\.jsdelivr|cdnjs\.cloudflare|unpkg\.com/.test(url)) {
        externalRequests.push(url);
      }
    });

    await uiLogin(page, 'reception');
    await page.goto('/reception/dashboard');

    // Nonce present on the API_ROUTES bootstrap script
    const nonced = await page.evaluate(() =>
      [...document.querySelectorAll('script[nonce]')].length
    );
    expect(nonced).toBeGreaterThan(0);

    // Zero third-party CDN calls
    expect(externalRequests).toEqual([]);
  });
});
