"""Targeted visual re-check after the CSS fixes (fresh screenshots + diagnostics)."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'visual_recheck')
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ('audit_doctor', 'full-demo-center', '/doctor/dashboard', 'doctor_dashboard'),
    ('audit_reception', 'full-demo-center', '/reception/patients', 'reception_patients'),
    ('audit_accountant', 'full-demo-center', '/accountant/pending-payments', 'accountant_pending'),
    ('audit_manager', 'full-demo-center', '/manager/unit-control', 'manager_units'),
    ('patient_0501112233', 'full-demo-center', '/portal/dashboard', 'portal_dashboard'),
]


def login(pg, user, tenant):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', tenant)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return True
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for user, tenant, path, name in PAGES:
        pg = b.new_page(viewport={'width': 1280, 'height': 800})
        login(pg, user, tenant)
        pg.goto(f'{BASE}/t/{tenant}{path}', wait_until='domcontentloaded')
        pg.wait_for_timeout(500)
        diagnostics = pg.evaluate(
            """() => {
                const skip = document.querySelector('.skip-link');
                const btn = document.querySelector('a.btn-primary');
                const badButtons = Array.from(document.querySelectorAll('a.btn-primary, button.btn-primary'))
                    .filter(e => getComputedStyle(e).color === getComputedStyle(e).backgroundColor).length;
                const text = document.body.innerText;
                return {
                    skipTop: skip ? getComputedStyle(skip).top : 'none',
                    buttonColor: btn ? getComputedStyle(btn).color : 'none',
                    buttonBg: btn ? getComputedStyle(btn).backgroundColor : 'none',
                    invisibleButtons: badButtons,
                    englishPagination: /Page \\d+ of \\d+/.test(text),
                };
            }"""
        )
        pg.screenshot(path=os.path.join(OUT, f'{name}.png'))
        print(name, diagnostics)
        pg.close()
    b.close()
