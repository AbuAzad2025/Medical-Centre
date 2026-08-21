// Playwright E2E configuration — Medical System clinical cycle tests.
// Run:  npm run e2e        (headed: npm run e2e:headed)
// Prereq: app running at BASE_URL (default http://127.0.0.1:8080) in SaaS test mode
// with seed data from seeds/ and a reception + doctor + pharmacist account.
// Credentials via env: E2E_RECEPTION_USER / E2E_DOCTOR_USER / E2E_PHARMacist_USER (+ _PASS).
const { defineConfig, devices } = require('@playwright/test');

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:8080';

module.exports = defineConfig({
  testDir: './e2e/specs',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // clinical flow is stateful — run serially
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'e2e/report', open: 'never' }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    locale: 'ar',
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  outputDir: 'e2e/artifacts',
});
