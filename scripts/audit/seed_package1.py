"""Seed package 1 (private doctor clinic) with realistic data through the UI."""

import os
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
TENANT = 'dr-ahmed-clinic'
ADMIN = ('admin', 'Clinic@2026')
SHOTS = 'docs/PAGE_AUDIT/package1_seed'
os.makedirs(SHOTS, exist_ok=True)

PATIENTS = [
    ('سارة العتيبي', '0551110001', 'sara.otaibi@example.local'),
    ('خالد الحربي', '0551110002', 'khaled.harbi@example.local'),
    ('منى القحطاني', '0551110003', 'mona.qahtani@example.local'),
]


def login(pg, user, password, slug=TENANT):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', slug)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    admin_ctx = b.new_context(viewport={'width': 1280, 'height': 900})
    admin = admin_ctx.new_page()
    assert login(admin, *ADMIN), 'admin login failed'
    print('admin', admin.url)

    # 1. Patients via the public booking registration (creates Patient + account)
    for idx, (name, phone, email) in enumerate(PATIENTS, 1):
        pctx = b.new_context(viewport={'width': 1280, 'height': 900})
        pg = pctx.new_page()
        pg.goto(f'{BASE}/t/{TENANT}/booking/register', wait_until='domcontentloaded')
        pg.fill('input[name="full_name"]', name)
        pg.fill('input[name="phone"]', phone)
        pg.fill('input[name="email"]', email)
        pg.fill('input[name="password"]', 'Patient@2026Pass')
        form = pg.locator('form').filter(has=pg.locator('input[name="full_name"]'))
        form.evaluate('f => f.submit()')
        pg.wait_for_timeout(900)
        pg.wait_for_load_state('domcontentloaded')
        try:
            flash = [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]
        except Exception:  # noqa: BLE001
            flash = []
        print('patient', name, flash)
        pg.screenshot(path=f'{SHOTS}/patient_{idx}.png')
        pctx.close()

    # 2. Appointments via the real booking form as the clinic admin
    admin.goto(f'{BASE}/t/{TENANT}/booking/create', wait_until='domcontentloaded')
    admin.wait_for_timeout(400)
    dept = admin.locator('select[name="department_id"] option')
    dept_values = [o.get_attribute('value') for o in dept.all() if o.get_attribute('value')]
    print('departments', len(dept_values))
    if dept_values:
        admin.select_option('select[name="department_id"]', dept_values[0])
        admin.wait_for_timeout(700)
        doc = admin.locator('select[name="doctor_id"] option')
        doc_values = [o.get_attribute('value') for o in doc.all() if o.get_attribute('value')]
        print('doctors', len(doc_values))
    for idx, (name, phone, _email) in enumerate(PATIENTS, 1):
        admin.goto(f'{BASE}/t/{TENANT}/booking/create', wait_until='domcontentloaded')
        admin.wait_for_timeout(350)
        parts = name.split(' ', 1)
        admin.fill('input[name="first_name"]', parts[0])
        admin.fill('input[name="last_name"]', parts[1] if len(parts) > 1 else '-')
        admin.fill('input[name="phone"]', phone)
        if dept_values:
            admin.select_option('select[name="department_id"]', dept_values[0])
            admin.wait_for_timeout(600)
        doc_values = [
            o.get_attribute('value')
            for o in admin.locator('select[name="doctor_id"] option').all()
            if o.get_attribute('value')
        ]
        if doc_values:
            admin.select_option('select[name="doctor_id"]', doc_values[0])
        admin.fill('input[name="appointment_date"]', (date.today() + timedelta(days=idx)).isoformat())
        times = [
            o.get_attribute('value')
            for o in admin.locator('select[name="appointment_time"] option').all()
            if o.get_attribute('value')
        ]
        if times:
            admin.select_option('select[name="appointment_time"]', times[0])
        form = admin.locator('form').filter(has=admin.locator('input[name="first_name"]'))
        form.evaluate('f => f.submit()')
        admin.wait_for_timeout(800)
        admin.wait_for_load_state('domcontentloaded')
        print('booking', name, admin.url.split('/')[-1])
    admin.screenshot(path=f'{SHOTS}/bookings.png')

    admin.goto(f'{BASE}/t/{TENANT}/booking/dashboard', wait_until='domcontentloaded')
    admin.wait_for_timeout(400)
    admin.screenshot(path=f'{SHOTS}/booking_dashboard.png')
    admin.goto(f'{BASE}/t/{TENANT}/doctor/patients', wait_until='domcontentloaded')
    admin.wait_for_timeout(400)
    admin.screenshot(path=f'{SHOTS}/doctor_patients.png')
    b.close()
print('done')
