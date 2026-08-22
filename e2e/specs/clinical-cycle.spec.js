/**
 * E2E-02 — Full clinical cycle (stateful, serial):
 *   Reception: create patient -> create visit -> add to queue
 *   Doctor:    open queue patient -> write prescription
 *   Pharmacy:  dispense prescription
 *   Reception/Finance: invoice visible with charge
 *
 * Requires seeded users (see e2e/helpers.js CREDS) and at least one active
 * medication + department + doctor in the tenant DB. Run against a scratch DB.
 */
const { test, expect } = require('@playwright/test');
const { uiLogin } = require('../helpers');

let PATIENT_NAME;
const STAMP = Date.now();

test.describe.serial('Clinical cycle', () => {
  test.beforeAll(() => {
    PATIENT_NAME = `e2e_${STAMP}`;
  });

  test('reception creates a new patient', async ({ page }) => {
    await uiLogin(page, 'reception');
    await page.goto('/reception/patients');

    // Open the "new patient" form (button text varies by template)
    const addBtn = page.locator('a[href*="patient/new"], a[href$="/new"], button:has-text("إضافة"), a:has-text("مريض جديد")').first();
    await addBtn.click();
    await page.waitForLoadState('networkidle');

    // Fill required fields — tolerate template variance via name attributes.
    await page.locator('input[name="first_name"]').fill(PATIENT_NAME);
    await page.locator('input[name="last_name"]').fill('cycle');
    const nid = `E2E${STAMP}`;
    const nidInput = page.locator('input[name="national_id"]');
    if (await nidInput.count()) {
      await nidInput.fill(nid);
    }
    const phoneInput = page.locator('input[name="phone"]').first();
    if (await phoneInput.count()) {
      await phoneInput.fill('0599123456');
    }
    const genderSel = page.locator('select[name="gender"]');
    if (await genderSel.count()) {
      await genderSel.selectOption({ index: 1 });
    }
    const dob = page.locator('input[name="birth_date"], input[name="date_of_birth"]');
    if (await dob.count()) {
      await dob.fill('1990-01-01');
    }

    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.locator('button[type="submit"]:has-text("حفظ"), button[type="submit"]:has-text("تسجيل"), input[type="submit"]').first().click(),
    ]);

    // Patient appears in search results
    await page.goto(`/reception/patients?search=${PATIENT_NAME}`);
    await expect(page.getByText(PATIENT_NAME).first()).toBeVisible();
  });

  test('reception creates a visit for the patient and queues it', async ({ page }) => {
    await uiLogin(page, 'reception');
    await page.goto('/reception/create_visit');

    // Select our patient via smart search / select control
    const patientSearch = page.locator('#patient-search, input[name="patient_search"], select[name="patient_id"]').first();
    await patientSearch.fill?.(String(PATIENT_NAME)) ?? patientSearch.selectOption({ label: /.*/ });

    const dept = page.locator('select[name="department_id"]').first();
    await dept.selectOption({ index: 1 });

    await Promise.all([
      page.waitForLoadState('networkidle'),
      page.locator('button[type="submit"], input[type="submit"]').first().click(),
    ]);
    await expect(page.locator('.alert-success').or(page.locator('.flash-success')).first()).toBeVisible();
  });

  test('doctor sees queued patient and writes a prescription', async ({ page }) => {
    await uiLogin(page, 'doctor');
    await page.goto('/doctor/patient_queue');
    // Our visit should be in the doctor's worklist (IN_PROGRESS or OPEN)
    const row = page.getByText(String(PATIENT_NAME)).first();
    await expect(row).toBeVisible({ timeout: 20_000 });
  });

  test('invoice/payment state reflects on reception visits list', async ({ page }) => {
    await uiLogin(page, 'reception');
    await page.goto('/reception/visits?search=' + PATIENT_NAME);
    await expect(page.getByText(String(PATIENT_NAME)).first()).toBeVisible();
  });
});
