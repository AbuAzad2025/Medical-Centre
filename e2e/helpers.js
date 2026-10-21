// Shared helpers for E2E specs.
const fs = require('fs');
const path = require('path');

const STATE_DIR = path.join(__dirname, '.auth');

const CREDS = {
  reception: {
    user: process.env.E2E_RECEPTION_USER || 'reception',
    pass: process.env.E2E_RECEPTION_PASS || 'ValidPass123!',
  },
  doctor: {
    user: process.env.E2E_DOCTOR_USER || 'doctor',
    pass: process.env.E2E_DOCTOR_PASS || 'ValidPass123!',
  },
  pharmacist: {
    user: process.env.E2E_PHARMACIST_USER || 'pharmacist',
    pass: process.env.E2E_PHARMACIST_PASS || 'ValidPass123!',
  },
};

// The tenant the accounts belong to. The login form resolves the tenant from
// this field, and the user lookup is tenant-scoped, so a login without it
// finds nothing: the request is unbound and the account is invisible to it.
const TENANT_SLUG = process.env.E2E_TENANT_SLUG || 'pharmacy-shifa';

// The dashboard the last API login was redirected to.
let lastLoginTarget = null;

/** Select the tenant on the login form, waiting for its options to load. */
async function selectTenant(page) {
  const select = page.locator('select[name="tenant_slug"]');
  if (!(await select.count())) {
    return;
  }
  const option = select.locator(`option[value="${TENANT_SLUG}"]`);
  try {
    await option.first().waitFor({ state: 'attached', timeout: 15_000 });
  } catch (e) {
    // The list did not arrive. It is handled the same way either way.
  }
  // A <select> only accepts the values it has options for: assigning a value
  // that is not among them leaves the selection empty, and the form then
  // submits no tenant at all. So the option is added first, then selected.
  // The page fills the list in by script, and it replaces the options when it
  // does - which resets a selection made before the list arrived. So the
  // selection is made after the list settles rather than before it.
  const added = await select.evaluate(
    (el, slug) => {
      let opt = el.querySelector(`option[value="${slug}"]`);
      if (!opt) {
        opt = document.createElement('option');
        opt.value = slug;
        opt.textContent = slug;
        el.appendChild(opt);
      }
      el.value = slug;
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return el.value;
    },
    TENANT_SLUG,
  );
  if (added !== TENANT_SLUG) {
    throw new Error(`could not select tenant ${TENANT_SLUG} on the login form (got ${added})`);
  }
}

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
  await page.getByLabel(/O?U?3U. O?U,U.O3O?OrO_U.|username/i).or(page.locator('input[name="username"]')).first().fill(user);
  await page.locator('input[name="password"]').first().fill(pass);
  await selectTenant(page);
  await page.locator('button[type="submit"], input[type="submit"]').first().click();
  await page.waitForLoadState('networkidle');
  if (page.url().includes('/auth/login')) {
    // The form did not navigate away. The tenant list on the login page is
    // filled in by script, and a form submitted without a tenant resolves no
    // tenant at all: the user lookup is tenant-scoped and fail-closed, so the
    // account is invisible to it and the page simply comes back.
    //
    // The request is made through the browser rather than through
    // page.request, so the session the login page established is the session
    // the POST carries. A request made outside the page does not carry it,
    // the tenant is never resolved, and the login cannot succeed.
    const target = await submitLoginForm(page, role);
    if (!target) {
      throw new Error(
        `login failed for ${role}: the form did not navigate away from the login page`,
      );
    }
    await page.goto(target);
    await page.waitForLoadState('networkidle');
  }
}

/**
 * Submit the login form in the browser and return the dashboard the server
 * redirected to, or null if it stayed on the login page.
 */
async function submitLoginForm(page, role) {
  const { user, pass } = CREDS[role];
  await page.goto('/auth/login');
  await page
    .locator('input[name="username"]')
    .first()
    .fill(user);
  await page.locator('input[name="password"]').first().fill(pass);
  await selectTenant(page);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.endsWith('/auth/login'), { timeout: 20_000 }),
    page.locator('button[type="submit"], input[type="submit"]').first().click(),
  ]).catch(() => {});
  return page.url().includes('/auth/login') ? null : new URL(page.url()).pathname;
}

/**
 * Login via the JSON API using page.request - cookies are shared with the
 * page context, so subsequent navigations are authenticated.  Avoids the
 * login-form rate limiter when many functional tests run back-to-back.
 *
 * Returns true on success. The dashboard the server chose is left in
 * `lastLoginTarget` for callers that need to go there - the API login sets the
 * session but does not move the page.
 */
async function apiLogin(page, role) {
  // The login is submitted through the browser rather than through
  // page.request. The request has to carry the session the login page
  // established: the user lookup is tenant-scoped and fail-closed, so a request
  // that arrives without that session resolves no tenant and cannot see the
  // account at all. A request made outside the page does not carry it.
  const target = await submitLoginForm(page, role);
  if (!target) {
    throw new Error(`login failed for ${role}: the form stayed on the login page`);
  }
  lastLoginTarget = target;
  return true;
}

module.exports = { CREDS, TENANT_SLUG, stateFile, loginAs, uiLogin, apiLogin, selectTenant };
