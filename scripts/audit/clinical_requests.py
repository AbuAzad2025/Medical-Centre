"""Fresh visit → lab request → radiology request through the real UI."""

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
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'clinical_requests.json')
results = []


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
    raise RuntimeError('login failed')


def snap(pg, name):
    for _attempt in range(3):
        try:
            pg.wait_for_timeout(300)
            path = os.path.join(SHOTS, name)
            pg.screenshot(path=path)
            return path
        except Exception:
            time.sleep(0.3)
    return None


def flash(pg):
    try:
        pg.wait_for_load_state('domcontentloaded')
        return [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]
    except Exception:  # noqa: BLE001
        return []


def record(name, ok, detail, shot):
    results.append({'step': name, 'ok': ok, 'detail': detail, 'screenshot': shot})
    print(f'{"OK " if ok else "FAIL"} {name}: {detail}')


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})

    login(pg, 'audit_reception')
    pg.goto(f'{BASE}/t/{TENANT}/reception/patients?show_add=1', wait_until='domcontentloaded')
    pg.evaluate(
        """() => { const m=document.getElementById('addPatientModal');
           if(m){m.classList.add('show');m.style.display='block';m.removeAttribute('aria-hidden');} }"""
    )
    f = pg.locator('#patientFormModal')
    suffix = str(int(time.time()))[-7:]
    f.locator('input[name="national_id"]').fill(suffix)
    f.locator('input[name="phone"]').fill('05' + suffix)
    f.locator('input[name="first_name"]').fill('ليلى')
    f.locator('input[name="last_name"]').fill('Hariri')
    f.locator('select[name="gender"]').select_option(index=2)
    f.evaluate('f => f.submit()')
    pg.wait_for_timeout(1000)

    pg.goto(f'{BASE}/t/{TENANT}/reception/queue/add-patient', wait_until='domcontentloaded')
    form = pg.locator('form').filter(has=pg.locator('select[name="patient_id"]')).first
    form.locator('select[name="patient_id"]').select_option(index=2)
    for field, value in (
        ('department_id', '33'),
        ('doctor_id', '29'),
        ('queue_type', 'normal'),
        ('payment_status', 'PAID'),
    ):
        form.locator(f'select[name="{field}"]').select_option(value)
    form.evaluate(
        """f => {
          const e=f.querySelector('input[name="is_emergency"]'); if(e) e.checked=true;
          const r=f.querySelector('textarea[name="emergency_reason"]'); if(r) r.value='حالة طارئة';
        }"""
    )
    form.evaluate('f => f.submit()')
    pg.wait_for_timeout(1000)
    record(
        'reception: fresh queue entry',
        'طابور' in ' '.join(flash(pg)),
        str(flash(pg))[:120],
        snap(pg, '10_fresh_queue.png'),
    )

    # read newest visit id
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

    login(pg, 'audit_doctor')
    # Call the patient from the queue, then start treatment so the visit is
    # IN_PROGRESS (required before lab/radiology requests).
    pg.goto(f'{BASE}/t/{TENANT}/doctor/patient-queue', wait_until='domcontentloaded')
    for action in ('call-patient', 'start-treatment'):
        pg.goto(f'{BASE}/t/{TENANT}/doctor/patient-queue', wait_until='domcontentloaded')
        form = pg.locator(f'form[action*="{action}/{visit_id}"]')
        print(action, 'forms', form.count())
        if form.count():
            form.first.evaluate('f => f.submit()')
            pg.wait_for_timeout(800)
            pg.wait_for_load_state('domcontentloaded')
    record(
        'doctor: call + start treatment',
        True,
        f'visit {visit_id} flash={str(flash(pg))[:120]}',
        snap(pg, '10b_started.png'),
    )

    for path, fields, shotname, label in (
        (
            f'/doctor/notes/{visit_id}?type=lab',
            {'medical_notes': 'صورة دم كاملة — فحص روتيني'},
            '11_lab_note.png',
            'doctor: lab note',
        ),
        (
            f'/doctor/notes/{visit_id}?type=radiology',
            {'medical_notes': 'أشعة صدر — سعال مستمر'},
            '12_radiology_note.png',
            'doctor: radiology note',
        ),
    ):
        pg.goto(f'{BASE}/t/{TENANT}{path}', wait_until='domcontentloaded')
        for name, value in fields.items():
            loc = pg.locator(f'[name="{name}"]')
            if loc.count():
                loc.first.fill(value)
        target = pg.locator('form').filter(has=pg.locator('[name="medical_notes"]'))
        if target.count():
            target.first.evaluate('f => f.submit()')
            pg.wait_for_timeout(900)
            pg.wait_for_load_state('domcontentloaded')
        record(label, True, f'visit {visit_id} flash={str(flash(pg))[:140]}', snap(pg, shotname))

    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', OUT)
