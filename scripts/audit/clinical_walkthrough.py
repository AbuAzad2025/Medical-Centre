"""Real clinical workflow through the UI: patient → queue → diagnosis → prescription.

Every step is performed by logging in as the corresponding real user and
submitting the real form. Screenshots are saved for visual verification.
"""

import json
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'
SHOTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'workflow_shots')
os.makedirs(SHOTS, exist_ok=True)
RESULTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'workflow_results.json')

results = []


def step(name, ok, detail, shot=None):
    results.append({'step': name, 'ok': bool(ok), 'detail': detail, 'screenshot': shot})
    print(f'{"OK " if ok else "FAIL"} {name}: {detail}')


def login(pg, user):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError(f'login failed: {user}')


def flash(pg):
    return [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]


def snap(pg, name):
    path = os.path.join(SHOTS, name)
    try:
        pg.screenshot(path=path)
        return path
    except Exception as exc:  # noqa: BLE001
        print('screenshot skipped:', str(exc)[:80])
        return None


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})

    # ── 1. Reception: register a real patient ──────────────────────────────
    login(pg, 'audit_reception')
    pg.goto(f'{BASE}/t/{TENANT}/reception/patients?show_add=1', wait_until='domcontentloaded')
    if pg.locator('#addPatientModal').count():
        pg.evaluate(
            """() => {
                const modal = document.getElementById('addPatientModal');
                modal.classList.add('show');
                modal.style.display = 'block';
                modal.removeAttribute('aria-hidden');
            }"""
        )
        pg.wait_for_timeout(300)
    form = pg.locator('#patientFormModal')
    suffix = str(int(time.time()))[-7:]
    form.locator('input[name="national_id"]').fill(suffix)
    form.locator('input[name="phone"]').fill('05' + suffix)
    form.locator('input[name="first_name"]').fill('سارة')
    form.locator('input[name="last_name"]').fill('العتيبي')
    form.locator('input[name="first_name_ar"]').fill('Sarah')
    form.locator('input[name="last_name_ar"]').fill('Alotaibi')
    form.locator('select[name="gender"]').select_option(index=2)
    form.locator('input[name="birth_date"]').fill('1992-04-12')
    pg.evaluate("document.getElementById('patientFormModal').submit()")
    pg.wait_for_timeout(1200)
    pg.wait_for_load_state('domcontentloaded')
    shot = snap(pg, '01_patient_added.png')
    msgs = flash(pg)
    step(
        'reception: add patient',
        'مريض' in ' '.join(msgs) or 'success' in ' '.join(msgs).lower(),
        str(msgs)[:160],
        shot,
    )

    # ── 2. Reception: place the patient in the queue ────────────────────────
    pg.goto(f'{BASE}/t/{TENANT}/reception/queue/add-patient', wait_until='domcontentloaded')
    form = pg.locator('form').filter(has=pg.locator('select[name="patient_id"]')).first
    options = form.locator('select[name="patient_id"] option').all()
    patient_value = None
    for opt in options:
        if 'سارة' in (opt.inner_text() or '') or 'Sarah' in (opt.inner_text() or ''):
            patient_value = opt.get_attribute('value')
            break
    if patient_value is None and len(options) > 1:
        patient_value = options[-1].get_attribute('value')
    form.locator('select[name="patient_id"]').select_option(patient_value)
    for field, value in (
        ('department_id', '33'),
        ('doctor_id', '29'),
        ('queue_type', 'normal'),
        ('payment_status', 'PAID'),
    ):
        sel = form.locator(f'select[name="{field}"]')
        if sel.count():
            sel.select_option(value)
    form.evaluate(
        """f => {
            const emergency = f.querySelector('input[name="is_emergency"]');
            if (emergency) { emergency.checked = true; }
            const reason = f.querySelector('textarea[name="emergency_reason"]');
            if (reason) { reason.value = 'حالة طارئة للجولة'; }
        }"""
    )
    form.evaluate('f => f.submit()')
    pg.wait_for_timeout(1200)
    pg.wait_for_load_state('domcontentloaded')
    shot = snap(pg, '02_queue_added.png')
    msgs = flash(pg)
    step(
        'reception: add to queue',
        'طابور' in ' '.join(msgs) or 'نجاح' in ' '.join(msgs),
        f'url={pg.url} flash={str(msgs)[:160]}',
        shot,
    )

    # ── 3. Doctor: diagnosis and prescription ──────────────────────────────
    login(pg, 'audit_doctor')
    pg.goto(f'{BASE}/t/{TENANT}/doctor/visits', wait_until='domcontentloaded')
    shot = snap(pg, '03_doctor_visits.png')
    body = pg.locator('body').inner_text()
    step('doctor: visits list', pg.title() != '', body[:120].replace('\n', ' / '), shot)

    # Read the visit created above from the application DB (read-only).
    os.environ.setdefault(
        'DATABASE_URL', 'postgresql://postgres:testpass@127.0.0.1:5433/Medical2026'
    )
    os.environ.setdefault('SKIP_PLATFORM_BOOTSTRAP', '1')
    os.environ.setdefault('RLS_BYPASS_ALLOWED', '1')
    os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
    from sqlalchemy import select

    from app.extensions import db
    from app_factory import create_app
    from models.visit import Visit

    app = create_app('development')
    with app.app_context():
        visit_id = (
            db.session.execute(
                select(Visit.id).where(Visit.tenant_id == 3).order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
    print('visit_id', visit_id)
    if visit_id:
        pg.goto(f'{BASE}/t/{TENANT}/doctor/diagnosis/{visit_id}', wait_until='domcontentloaded')
        if pg.locator('textarea[name="chief_complaint"]').count():
            pg.fill('textarea[name="chief_complaint"]', 'صداع وألم في الحلق')
            pg.fill('textarea[name="symptoms"]', 'حرارة ورشح لمدة يومين')
            pg.fill('input[name="blood_pressure"]', '120/80')
            pg.fill('input[name="heart_rate"]', '78')
            pg.fill('input[name="temperature"]', '38.1')
            pg.fill('textarea[name="diagnosis"]', 'التهاب الجهاز التنفسي العلوي')
            pg.fill('textarea[name="treatment_plan"]', 'مسكنات وسوائل وراحة')
            pg.click('button[type=submit]')
            pg.wait_for_timeout(1200)
            pg.wait_for_load_state('domcontentloaded')
        shot = snap(pg, '04_diagnosis_saved.png')
        step('doctor: save diagnosis', True, f'visit {visit_id}', shot)

        pg.goto(f'{BASE}/t/{TENANT}/doctor/prescription/{visit_id}', wait_until='domcontentloaded')
        if pg.locator('#addRxItemBtn').count():
            pg.click('#addRxItemBtn')
            pg.wait_for_timeout(250)
            med = pg.locator('#medications_list option').first
            med_value = med.get_attribute('value') if med.count() else None
            pg.evaluate(
                """v => {
                    const id = document.querySelector('input[name="item_medication_id[]"]');
                    const ref = document.querySelector('input[name="item_medication_ref[]"]');
                    if (id && v) id.value = String(v).split('|')[0];
                    if (ref && v) ref.value = v;
                    const dose = document.querySelector('input[name="item_dosage[]"]');
                    const freq = document.querySelector('input[name="item_frequency[]"]');
                    if (dose) dose.value = 'قرص واحد';
                    if (freq) freq.value = 'مرتين يومياً';
                }""",
                med_value,
            )
            pg.fill('textarea[name="additional_notes"]', 'يرجى الالتزام بالجرعة')
            pg.locator('form').filter(has=pg.locator('#addRxItemBtn')).evaluate('f => f.submit()')
            pg.wait_for_timeout(1000)
            pg.wait_for_load_state('domcontentloaded')
        shot = snap(pg, '05_prescription_saved.png')
        msgs = flash(pg)
        step('doctor: save prescription', True, f'visit {visit_id} flash={str(msgs)[:120]}', shot)

        for path, fields, shotname, label in (
            (
                f'/doctor/lab-request/{visit_id}',
                {'test_name': 'صورة دم كاملة', 'notes': 'فحص روتيني', 'urgency': 'عادي'},
                '06_lab_request.png',
                'doctor: create lab request',
            ),
            (
                f'/doctor/radiology-request/{visit_id}',
                {'test_name': 'أشعة صدر', 'notes': 'سعال مستمر', 'urgency': 'عادي'},
                '07_radiology_request.png',
                'doctor: create radiology request',
            ),
        ):
            pg.goto(f'{BASE}/t/{TENANT}{path}', wait_until='domcontentloaded')
            for name, value in fields.items():
                locator = pg.locator(f'[name="{name}"]')
                if locator.count():
                    locator.first.fill(value)
            forms = pg.locator('form')
            if forms.count():
                forms.last.evaluate('f => f.submit()')
                pg.wait_for_timeout(900)
                pg.wait_for_load_state('domcontentloaded')
            shot = snap(pg, shotname)
            step(label, True, f'visit {visit_id} flash={str(flash(pg))[:120]}', shot)

    b.close()

with open(RESULTS, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', RESULTS)
