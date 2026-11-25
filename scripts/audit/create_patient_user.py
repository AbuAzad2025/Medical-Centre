"""Create a real patient account through the public booking registration UI."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    url = f'{BASE}/t/full-demo-center/booking/register'
    pg.goto(url, wait_until='domcontentloaded')
    print('PAGE', pg.url, pg.title())
    pg.fill('input[name="full_name"]', 'مريض الجولة')
    pg.fill('input[name="phone"]', '0501112233')
    pg.fill('input[name="email"]', 'audit_patient@full-demo-center.local')
    pg.fill('input[name="password"]', PASSWORD)
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)
    pg.wait_for_load_state('domcontentloaded')
    print('AFTER', pg.url)
    print('FLASH', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
