// Shared helpers for E2E specs.
const fs = require('fs');
const path = require('path');

const STATE_DIR = path.join(__dirname, '.auth');

const CREDS = {
  reception: {
    user: process.env.E2E_RECEPTION_USER || 'reception_e2e',
    pass: process.env.E2E_RECEPTION_PASS || 'ValidPass123!',
  },
  doctor: {
    user: process.env.E2E_DOCTOR_USER || 'doctor_e2e',
    pass: process.env.E2E_DOCTOR_PASS || 'ValidPass123!',
  },
  pharmacist: {
    user: process.env.E2E_PHARMACIST_USER || 'pharmacist_test',
    pass: process.env.E2E_PHARMACIST_PASS || 'ValidPass123!',
  },
};

function stateFile(role) {
  fs.mkdirSync(STATE_DIR, { recursive: true });
  return path.join(STATE_DIR, `${role}.json`);
}

/**
 * Login via the real /auth/login form and persist session storage for reuse.
 */
async function loginAs(request, role) {
  const { user, pass } = CREDS[role];
  const login = await request.post('/auth/login', {
    form: { username: user, password: pass },
    maxRedirects: 0,
  });
  if (login.status() !== 200 && login.status() !== 302) {
    throw new Error(`Login failed for ${role}: HTTP ${login.status()}`);
  }
  return login;
}

/** Login through UI (used by storageState-independent flows). */
async function uiLogin(page, role) {
  const { user, pass } = CREDS[role];
  await page.goto('/auth/login');
  await page.getByLabel(/اسم المستخدم|username/i).or(page.locator('input[name="username"]')).first().fill(user);
  await page.locator('input[name="password"]').first().fill(pass);
  await page.locator('button[type="submit"], input[type="submit"]').first().click();
  await page.waitForLoadState('networkidle');
}

module.exports = { CREDS, stateFile, loginAs, uiLogin };
