"""Actually return a mistakenly called patient to the queue through the UI."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

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
    pg.goto(f'{BASE}/t/full-demo-center/reception/queue', wait_until='domcontentloaded')
    pg.wait_for_timeout(2500)
    btn = pg.locator('button[aria-label="إرجاع للطابور"]').first
    print('buttons', pg.locator('button[aria-label="إرجاع للطابور"]').count())
    net = []
    pg.on('response', lambda r: net.append((r.status, r.url)) if 'return-to-queue' in r.url else None)
    btn.click()
    pg.wait_for_timeout(500)
    print('swal input', pg.locator('.swal2-input').count(), 'confirm', pg.locator('.swal2-confirm').count())
    pg.fill('.swal2-input', 'استدعاء بالخطأ — يعاد للطابور')
    pg.click('.swal2-confirm')
    pg.wait_for_timeout(1500)
    print('network', net)
    print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
