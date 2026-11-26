"""Seed the dedicated package-1 tenant (pkg-private-doctor-clinic) through the UI."""

import os
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
TENANT = 'pkg-private-doctor-clinic'
ADMIN = ('admin_private_doctor_clinic', 'Audit@2026Pass')
SHOTS = 'docs/PAGE_AUDIT/package1_seed'
os.makedirs(SHOTS, exist_ok=True)

# Generated at runtime so no literal sensitive values live in source.
PHONES = [f'05{int(time.time()) + i}'[-10:] for i in range(2)]
PATIENTS = [
    ('نورة', 'الدوسري', PHONES[0], 'noura.dosari@example.local'),
    ('عبدالله', 'المطيري', PHONES[1], 'abdullah.mutairi@example.local'),
]
EXTRA = ('فاطمة', 'الزهراني', f'05{int(time.time()) + 9}'[-10:])


def login(pg, user, password):
    for _ in range(6):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
        pg.wait_for_timeout(1200)
    return False


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    browser_ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = browser_ctx.new_page()
    assert login(page, *ADMIN), 'tenant-4 admin login failed'
    print('admin', page.url)

    # Two patient accounts is the package-1 cap (admin + 2 patients).
    for idx, (_first, _last, phone, email) in enumerate(PATIENTS, 1):
        ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
        reg = ctx.new_page()
        reg.goto(f'{BASE}/t/{TENANT}/booking/register', wait_until='domcontentloaded')
        reg.fill('input[name="full_name"]', f'{PATIENTS[idx - 1][0]} {PATIENTS[idx - 1][1]}')
        reg.fill('input[name="phone"]', phone)
        reg.fill('input[name="email"]', email)
        reg.fill('input[name="password"]', 'Patient@2026Pass')
        reg.locator('form').filter(has=reg.locator('input[name="full_name"]')).evaluate(
            'f => f.submit()'
        )
        reg.wait_for_timeout(900)
        print('patient', idx, reg.url.split('/')[-1])
        ctx.close()

    # Appointments via the booking endpoint used by the UI.
    page.goto(f'{BASE}/t/{TENANT}/booking/create', wait_until='domcontentloaded')
    page.wait_for_timeout(400)
    departments = [
        option.get_attribute('value')
        for option in page.locator('select[name="department_id"] option').all()
        if option.get_attribute('value')
    ]
    csrf = page.get_attribute('meta[name="csrf-token"]', 'content')
    print('departments', len(departments))
    people = [(first, last, phone) for first, last, phone, _email in PATIENTS] + [EXTRA]
    for idx, (first, last, phone) in enumerate(people, 1):
        result = page.evaluate(
            """({csrf, url, first, last, phone, dept, date}) => {
              const body = new URLSearchParams({
                csrf_token: csrf, first_name: first, last_name: last, phone: phone,
                department_id: dept, appointment_date: date, appointment_time: '10:30',
                visit_type: 'first', notes: 'حجز تجريبي لبذور الحزمة 1'
              });
              return fetch(url, {method: 'POST', body, credentials: 'same-origin', redirect: 'manual'})
                .then(r => ({status: r.status, location: r.headers.get('location')}));
            }""",
            {
                'csrf': csrf,
                'url': f'{BASE}/t/{TENANT}/booking/create',
                'first': first,
                'last': last,
                'phone': phone,
                'dept': departments[0] if departments else '',
                'date': (date.today() + timedelta(days=idx)).isoformat(),
            },
        )
        print('booking', first, result)

    for path, shot in (
        ('/booking/dashboard', 'pkg1_booking_dashboard.png'),
        ('/doctor/dashboard', 'pkg1_doctor_dashboard.png'),
        ('/t/platform/owner/subscriptions', None),
    ):
        url = f'{BASE}{path}' if path.startswith('/t/') else f'{BASE}/t/{TENANT}{path}'
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(400)
        if shot:
            page.screenshot(path=f'{SHOTS}/{shot}')
    browser.close()
print('done')
