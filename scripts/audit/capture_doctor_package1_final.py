"""Visual proof of the package-1 doctor shell after the adaptive polish."""

import os

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'
TENANT = 'dr-ahmed-clinic'
OUT = 'docs/PAGE_AUDIT/doctor_pkg1_final'
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ('dashboard', '/doctor/dashboard'),
    ('queue', '/doctor/patient-queue'),
    ('patient_details', '/doctor/patient-details/17'),
    ('prescriptions', '/doctor/prescriptions'),
    ('appointments', '/doctor/appointments'),
    ('inbox', '/inbox'),
    ('settings', '/doctor/settings'),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for width in (1280, 900):
        ctx = browser.new_context(viewport={'width': width, 'height': 900})
        page = ctx.new_page()
        for _ in range(6):
            page.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
            page.fill('#username', 'admin')
            page.fill('#password', 'Clinic@2026')
            page.select_option('#tenant_slug', TENANT)
            page.click('button[type=submit]')
            page.wait_for_timeout(1100)
            if '/auth/login' not in page.url:
                break
        for name, path in PAGES:
            page.goto(f'{BASE}/t/{TENANT}{path}', wait_until='domcontentloaded')
            page.wait_for_timeout(450)
            page.screenshot(path=f'{OUT}/{width}_{name}.png')
        ctx.close()
    browser.close()
print('captured', OUT)
