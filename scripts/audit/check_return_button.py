"""Verify the reception-side 'return to queue' control is visible."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'workflow_shots', 'reception_return.png')

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'audit_reception')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            break
    r = pg.goto(f'{BASE}/t/full-demo-center/reception/queue', wait_until='domcontentloaded')
    pg.wait_for_timeout(1200)
    body = pg.locator('body').inner_text()
    buttons = pg.locator(
        'button[aria-label="إرجاع للطابور"], button[title="إرجاع للطابور"]'
    ).count()
    print('status', r.status, 'return buttons', buttons)
    print('has return text', 'إرجاع' in body)
    pg.screenshot(path=OUT)
    print('screenshot', OUT)
    b.close()
