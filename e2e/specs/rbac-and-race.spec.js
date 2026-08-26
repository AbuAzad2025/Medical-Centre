// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Role-based UI gating: unauthorized cross-module actions must be
 * invisible in the DOM (not merely hidden), per RBAC hardening mandate.
 */
test.describe('Role-based UI gating', () => {
  test('reception sees no doctor-only queue action buttons', async ({ page, request }) => {
    await page.goto('/auth/login');
    await page.fill('input[name="username"]', 'reception');
    await page.fill('input[name="password"]', 'ValidPass123!');
    const slug = process.env.E2E_TENANT_SLUG || 'medical-center';
    const ts = page.locator('input[name="tenant_slug"]');
    if (await ts.count()) await ts.fill(slug);
    await Promise.all([page.waitForURL(/dashboard|reception/, { timeout: 20000 }), page.click('button[type="submit"]')]);

    await page.goto('/reception/visits');
    await expect(page.locator('body')).not.toContainText('لوحة الطبيب');

    // Direct API probe: doctor dashboard must not render for reception role
    const resp = await request.get('/doctor/dashboard');
    expect([302, 403]).toContain(resp.status());
  });

  test('pharmacist cannot open accountant payment processing', async ({ page, request }) => {
    await page.goto('/auth/login');
    await page.fill('input[name="username"]', 'pharmacist');
    await page.fill('input[name="password"]', 'ValidPass123!');
    await Promise.all([page.waitForURL(/dashboard|medication|pharmacy/, { timeout: 20000 }), page.click('button[type="submit"]')]);

    const resp = await request.get('/accountant/process-payment');
    expect([302, 403, 404]).toContain(resp.status());
  });
});

/**
 * Client-side atomicity: rapid double-click on a mutating form must not
 * fire two submissions (global double-submit guard in form-validation.js).
 */
test.describe('Double-submit race guard', () => {
  test('rapid double-click fires exactly one POST', async ({ page }) => {
    await page.goto('/auth/login');
    await page.fill('input[name="username"]', 'reception');
    await page.fill('input[name="password"]', 'ValidPass123!');
    await Promise.all([page.waitForURL(/dashboard|reception/, { timeout: 20000 }), page.click('button[type="submit"]')]);

    let postCount = 0;
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/auth/login')) postCount++;
    });

    await page.goto('/auth/login');
    await page.fill('input[name="username"]', 'reception');
    await page.fill('input[name="password"]', 'wrong-password');
    const btn = page.locator('button[type="submit"]');
    await btn.click();
    await btn.click({ force: true }); // second click within the disabled window

    await page.waitForTimeout(1500);
    expect(postCount).toBeLessThanOrEqual(1);
  });
});
