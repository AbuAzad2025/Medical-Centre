"""Dump form field names on the key workflow pages."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
PAGES = [
    ('audit_reception', '/reception/patients?show_add=1'),
    ('audit_reception', '/reception/add_patient_to_queue'),
    ('audit_reception', '/reception/queue_management'),
    ('audit_doctor', '/doctor/patient-queue'),
    ('audit_doctor', '/doctor/diagnosis/1'),
    ('audit_doctor', '/doctor/prescription/1'),
    ('audit_doctor', '/doctor/lab-request/1'),
    ('audit_lab', '/lab/worklist'),
    ('audit_radiology', '/radiology/requests'),
    ('audit_pharmacist', '/medication/prescriptions'),
    ('audit_accountant', '/accountant/pending-payments'),
    ('audit_nurse', '/nurse/vitals'),
    ('audit_emergency', '/emergency/cases'),
]


def login(pg, user):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
    return False


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    current = None
    for user, path in PAGES:
        if user != current:
            login(pg, user)
            current = user
        r = pg.goto(f'{BASE}/t/full-demo-center{path}', wait_until='domcontentloaded')
        forms = pg.eval_on_selector_all(
            'form',
            """els => els.slice(0,6).map(f => ({
                action: f.getAttribute('action'),
                method: f.getAttribute('method'),
                fields: Array.from(f.querySelectorAll('input,select,textarea')).slice(0,20)
                    .map(e => e.name + '[' + e.tagName + ']')
            }))""",
        )
        print(f'--- {user} {path} -> {r.status}')
        for form in forms:
            print('   ', form)
    b.close()
