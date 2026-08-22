/**
 * E2E-01 — Authentication flows.
 * Covers: login success, wrong password, logout, forgot-password page reachable.
 */
const { test, expect } = require('@playwright/test');
const { CREDS, uiLogin } = require('../helpers');

test.describe('Authentication', () => {
  test('login page renders with CSRF + form fields', async ({ page }) => {
    await page.goto('/auth/login');
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    // CSRF meta tag present (nonce/CSP hardened pages must still expose it)
    await expect(page.locator('meta[name="csrf-token"]')).toHaveCount(1);
  });

  test('wrong password shows Arabic error and stays on login', async ({ page }) => {
    await page.goto('/auth/login');
    await page.locator('input[name="username"]').first().fill(CREDS.reception.user);
    await page.locator('input[name="password"]').first().fill('definitely-wrong-pass');
    await page.locator('button[type="submit"], input[type="submit"]').first().click();

    await expect(page).not.toHaveURL(/dashboard/i);
    const err = page.locator('.alert-error, .alert, [role="alert"]').filter({
      hasText: /غير صحيح|خطأ/i,
    });
    await expect(err.first()).toBeVisible({ timeout: 10_000 });
  });

  test('successful login redirects to a role dashboard', async ({ page }) => {
    await uiLogin(page, 'reception');
    await expect(page).not.toHaveURL(/\/auth\/login/);
    // Any authenticated shell element
    await expect(
      page.locator('#mainContent, .main-container, .sidebar').first()
    ).toBeVisible();
  });

  test('logout returns to login page', async ({ page }) => {
    await uiLogin(page, 'reception');
    await page.goto('/auth/logout');
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test('forgot password page is reachable and has identifier field', async ({ page }) => {
    await page.goto('/auth/forgot-password');
    await expect(page.locator('#identifier')).toBeVisible();
    await expect(page.locator('form#forgotPasswordForm')).toBeVisible();
  });
});
