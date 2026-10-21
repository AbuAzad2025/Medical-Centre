// Playwright global setup.
//
// The suite logs in as three accounts that have to exist, in a tenant that has
// to have its modules activated, before any test can run. Doing that by hand
// meant the suite failed for reasons that had nothing to do with what it
// tests, so it is done here instead.
//
// The accounts are seeded after any pytest run: the test harness rebuilds the
// schema, and the accounts go with it.
const { execFileSync } = require('child_process');
const path = require('path');

const ROOT = path.join(__dirname, '..');

module.exports = async () => {
  const script = path.join(ROOT, 'e2e_seed_accounts.py');
  const python = process.env.PYTHON || path.join(ROOT, '.venv', 'Scripts', 'python.exe');

  try {
    const out = execFileSync(python, [script], {
      cwd: ROOT,
      encoding: 'utf-8',
      stdio: 'pipe',
    });
    // The seeder prints a line per account; surface them so a failed login
    // can be read back against what was actually created.
    process.stdout.write(out);
  } catch (err) {
    const detail = (err.stdout || '') + (err.stderr || '');
    process.stderr.write(`e2e account seeding failed:\n${detail}\n`);
    throw err;
  }
};
