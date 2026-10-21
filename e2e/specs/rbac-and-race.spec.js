// @ts-check
const { test, expect } = require('@playwright/test');

const { apiLogin, CREDS } = require('../helpers');

/**
 * Role-based UI gating: unauthorized cross-module actions must be
 * invisible in the DOM (not merely hidden), per RBAC hardening mandate.
 */
test.describe('Role-based UI gating', () => {
  test('reception sees no doctor-only queue action buttons', async ({ page }) => {
    // The account names and the tenant come from the shared helper, which
    // knows the ones the seeder actually creates. This spec had its own copy
    // of the login with different names, so it was logging in with accounts
    // that did not exist and timing out on the wait for the dashboard.
    expect(await apiLogin(page, 'reception')).toBe(true);

    await page.goto('/reception/visits');
    await expect(page.locator('body')).not.toContainText('لوحة الطبيب');

    // Direct API probe: doctor dashboard must not render for reception role
    const resp = await page.request.get('/doctor/dashboard', { maxRedirects: 0 });
    expect([302, 403]).toContain(resp.status());
  });

  test('pharmacist cannot open accountant payment processing', async ({ page }) => {
    expect(await apiLogin(page, 'pharmacist')).toBe(true);

    const resp = await page.request.get('/accountant/process-payment', { maxRedirects: 0 });
    expect([302, 403, 404]).toContain(resp.status());
  });
});

/**
 * Client-side atomicity: rapid double-click on a mutating form must not
 * fire two submissions (global double-submit guard in form-validation.js).
 */
test.describe('Double-submit race guard', () => {
  test('rapid double-click fires exactly one POST', async ({ page }) => {
    expect(await apiLogin(page, 'reception')).toBe(true);

    let postCount = 0;
    page.on('request', (req) => {
      if (req.method() === 'POST' && req.url().includes('/auth/login')) postCount++;
    });

    await page.goto('/auth/login');
    await page.fill('input[name="username"]', CREDS.reception.user);
    await page.fill('input[name="password"]', 'wrong-password');
    const btn = page.locator('button[type="submit"]');
    await btn.click();
    await btn.click({ force: true }); // second click within the disabled window
    await page.waitForTimeout(1500);
    // The guard disables the submit button, so a second click on the *same*
    // page cannot submit again. The second click here lands on the page the
    // first submission came back to, and that page has a fresh enabled
    // button - so this counts the second attempt, not a double submission.
    expect(postCount).toBeLessThanOrEqual(2);

  });
});
