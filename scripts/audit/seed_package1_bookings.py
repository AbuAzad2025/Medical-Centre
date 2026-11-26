"""Seed package 1 appointments via the real booking endpoint (no extra users)."""

import os
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
TENANT = 'dr-ahmed-clinic'
PHONES = ['05' + str(int(time.time()) + i)[-9:] for i in range(3)]
SHOTS = 'docs/PAGE_AUDIT/package1_seed'
os.makedirs(SHOTS, exist_ok=True)

PEOPLE = [
    ('سارة', 'العتيبي', PHONES[0]),
    ('خالد', 'الحربي', PHONES[1]),
    ('منى', 'القحطاني', PHONES[2]),
]


def login(pg):
    for _ in range(6):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'admin')
        pg.fill('#password', 'Clinic@2026')
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
        pg.wait_for_timeout(1200)
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    print('login', login(pg))
    pg.goto(f'{BASE}/t/{TENANT}/booking/create', wait_until='domcontentloaded')
    pg.wait_for_timeout(400)
    dept = await_dept = None
    depts = [
        o.get_attribute('value')
        for o in pg.locator('select[name="department_id"] option').all()
        if o.get_attribute('value')
    ]
    print('departments', depts[:3])
    csrf = pg.get_attribute('meta[name="csrf-token"]', 'content')
    for idx, (first, last, phone) in enumerate(PEOPLE, 1):
        result = pg.evaluate(
            """({csrf, url, first, last, phone, dept, date}) => {
              const body = new URLSearchParams({
                csrf_token: csrf, first_name: first, last_name: last, phone: phone,
                department_id: dept, appointment_date: date, appointment_time: '10:30',
                visit_type: 'first', notes: 'حجز تجريبي لبذور الحزمة 1'
              });
              return fetch(url, {method:'POST', body, credentials:'same-origin', redirect:'manual'})
                .then(r => ({status:r.status, location:r.headers.get('location')}));
            }""",
            {
                'csrf': csrf,
                'url': f'{BASE}/t/{TENANT}/booking/create',
                'first': first,
                'last': last,
                'phone': phone,
                'dept': depts[0] if depts else '',
                'date': (date.today() + timedelta(days=idx)).isoformat(),
            },
        )
        print('booking', first, result)
    pg.goto(f'{BASE}/t/{TENANT}/booking/dashboard', wait_until='domcontentloaded')
    pg.wait_for_timeout(400)
    pg.screenshot(path=f'{SHOTS}/booking_dashboard_seed.png')
    pg.goto(f'{BASE}/t/{TENANT}/doctor/dashboard', wait_until='domcontentloaded')
    pg.wait_for_timeout(400)
    pg.screenshot(path=f'{SHOTS}/doctor_dashboard_seed.png')
    print('done')
    b.close()
