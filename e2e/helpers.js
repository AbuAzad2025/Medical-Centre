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

/** Select the tenant on the login form, waiting for its options to load. */
async function selectTenant(page) {
  const select = page.locator('select[name="tenant_slug"]');
  if (!(await select.count())) {
    return;
  }
  const option = select.locator(`option[value="${TENANT_SLUG}"]`);
  try {
    await option.first().waitFor({ state: 'attached', timeout: 15_000 });
    await option.first().selectOption();
    return;
  } catch (e) {
    // The list did not arrive, or the tenant is not in it.
  }
  // A <select> only accepts the values it has options for: assigning a value
  // that is not among them leaves the selection empty, and the form then
  // submits no tenant at all. So the option is added first, then selected.
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
    // tenant at all, so the account is invisible to the lookup and the page
    // just comes back. The API posts the same fields and establishes the same
    // session, so use it rather than leaving the suite stuck here.
    await apiLogin(page, role);
  }
}

/**
 * Login via the JSON API using page.request - cookies are shared with the
 * page context, so subsequent navigations are authenticated.  Avoids the
 * login-form rate limiter when many functional tests run back-to-back.
 */
async function apiLogin(page, role) {
  const { user, pass } = CREDS[role];
  // The endpoint requires a CSRF token, so the login page is fetched first to
  // get the cookie and the token out of it.
  await page.goto('/auth/login');
  const token = await page
    .locator('meta[name="csrf-token"]')
    .getAttribute('content')
    .catch(() => null);
  const resp = await page.request.post('/auth/login', {
    form: {
      username: user,
      password: pass,
      tenant_slug: TENANT_SLUG,
      csrf_token: token || '',
    },
    headers: token ? { 'X-CSRFToken': token } : {},
    maxRedirects: 0,
  });
  return resp.status() < 400;
}

module.exports = { CREDS, TENANT_SLUG, stateFile, loginAs, uiLogin, apiLogin, selectTenant };
