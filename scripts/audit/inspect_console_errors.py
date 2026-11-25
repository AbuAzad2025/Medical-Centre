"""Inspect which sub-resources produce console errors on sample pages."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

PAGES = [
    ('accountant', 'audit_accountant', '/accountant/accounts'),
    ('pharmacist', 'audit_pharmacist', '/medications'),
    ('radiology', 'audit_radiology', '/radiology/'),
]

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for role, user, path in PAGES:
        pg = b.new_page(viewport={'width': 1280, 'height': 800})
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        bad = []

        def record_bad(r, _sink=bad):
            if r.status >= 400:
                _sink.append((r.status, r.url))

        pg.on('response', record_bad)
        pg.goto(f'{BASE}/t/full-demo-center{path}', wait_until='domcontentloaded')
        pg.wait_for_timeout(1500)
        print(f'--- {role} {path}')
        for status, url in bad[:12]:
            print(' ', status, url.replace(BASE, '')[:130])
        pg.close()
    b.close()
