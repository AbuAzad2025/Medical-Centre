"""Finish package-1 seeding: doctor user, third patient, real appointments."""

import os
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
TENANT = 'dr-ahmed-clinic'
ADMIN_PASSWORD = 'Clinic@2026'
SUPER_PASSWORD = os.environ.get('PLATFORM_ADMIN_PASSWORD', 'Azad@1983@2026@11@26')
SHOTS = 'docs/PAGE_AUDIT/package1_seed'
os.makedirs(SHOTS, exist_ok=True)


def login(pg, user, password, tenant=TENANT):
    for _ in range(6):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', tenant)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
        pg.wait_for_timeout(1500)
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    # 1) doctor user for the solo clinic via super-admin UI in tenant 2 context
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    print('super login', login(pg, 'superadmin', SUPER_PASSWORD, TENANT))
    pg.goto(f'{BASE}/t/{TENANT}/super-admin/users/create', wait_until='domcontentloaded')
    pg.fill('input[name="username"]', 'doctor_ahmed')
    pg.fill('input[name="email"]', 'doctor.ahmed@dr-ahmed-clinic.local')
    pg.fill('input[name="full_name"]', 'د. أحمد')
    pg.select_option('select[name="role"]', 'doctor')
    pg.fill('input[name="password"]', 'Doctor@2026Pass')
    pg.fill('input[name="confirm_password"]', 'Doctor@2026Pass')
    form = pg.locator('#createUserForm')
    if not form.count():
        form = pg.locator('form').filter(has=pg.locator('input[name="username"]'))
    form.evaluate('f => f.submit()')
    pg.wait_for_timeout(1200)
    pg.wait_for_load_state('domcontentloaded')
    print('doctor created', pg.url.split('/')[-1])
    pg.close()

    # 2) third patient registration
    pctx = b.new_context(viewport={'width': 1280, 'height': 900})
    pg = pctx.new_page()
    pg.goto(f'{BASE}/t/{TENANT}/booking/register', wait_until='domcontentloaded')
    pg.fill('input[name="full_name"]', 'منى القحطاني')
    pg.fill('input[name="phone"]', '0551110003')
    pg.fill('input[name="email"]', 'mona.qahtani@example.local')
    pg.fill('input[name="password"]', 'Patient@2026Pass')
    pg.locator('form').filter(has=pg.locator('input[name="full_name"]')).evaluate('f => f.submit()')
    pg.wait_for_timeout(1000)
    print('third patient url', pg.url)
    pctx.close()

    # 3) appointments as clinic admin
    actx = b.new_context(viewport={'width': 1280, 'height': 900})
    admin = actx.new_page()
    print('admin login', login(admin, 'admin', ADMIN_PASSWORD))
    people = [
        ('سارة', 'العتيبي', '0551110001'),
        ('خالد', 'حربي', '0551110002'),
        ('منى', 'القحطاني', '0551110003'),
    ]
    for idx, (first, last, phone) in enumerate(people, 1):
        admin.goto(f'{BASE}/t/{TENANT}/booking/create', wait_until='domcontentloaded')
        admin.wait_for_timeout(400)
        admin.fill('input[name="first_name"]', first)
        admin.fill('input[name="last_name"]', last)
        admin.fill('input[name="phone"]', phone)
        depts = [
            o.get_attribute('value')
            for o in admin.locator('select[name="department_id"] option').all()
            if o.get_attribute('value')
        ]
        if depts:
            admin.select_option('select[name="department_id"]', depts[0])
            admin.wait_for_timeout(700)
        docs = [
            o.get_attribute('value')
            for o in admin.locator('select[name="doctor_id"] option').all()
            if o.get_attribute('value')
        ]
        if docs:
            admin.select_option('select[name="doctor_id"]', docs[0])
        admin.fill('input[name="appointment_date"]', (date.today() + timedelta(days=idx)).isoformat())
        times = [
            o.get_attribute('value')
            for o in admin.locator('select[name="appointment_time"] option').all()
            if o.get_attribute('value')
        ]
        if times:
            admin.select_option('select[name="appointment_time"]', times[0])
        admin.locator('form').filter(has=admin.locator('input[name="first_name"]')).evaluate('f => f.submit()')
        admin.wait_for_timeout(900)
        admin.wait_for_load_state('domcontentloaded')
        print('booking', first, admin.url.split('/')[-1])
    admin.screenshot(path=f'{SHOTS}/bookings_final.png')
    admin.goto(f'{BASE}/t/{TENANT}/booking/dashboard', wait_until='domcontentloaded')
    admin.wait_for_timeout(400)
    admin.screenshot(path=f'{SHOTS}/booking_dashboard_final.png')
    b.close()
print('done')
