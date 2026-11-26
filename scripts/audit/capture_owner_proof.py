import os
from datetime import datetime

from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'owner_proof')
os.makedirs(OUT, exist_ok=True)
BASE = 'http://localhost:8000'
PASSWORD = f'Azad@1983@{datetime.now():%Y@%m@%d}'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for width in (1280, 900):
        pg = b.new_page(viewport={'width': width, 'height': 900})
        for _ in range(5):
            pg.goto(f'{BASE}/auth/login')
            pg.fill('#username', 'superadmin')
            pg.fill('#password', PASSWORD)
            pg.select_option('#tenant_slug', 'platform')
            pg.click('button[type=submit]')
            pg.wait_for_timeout(1100)
            if '/auth/login' not in pg.url:
                break
        for path in ('dashboard', 'provision', 'subscriptions'):
            pg.goto(f'{BASE}/t/platform/owner/{path}', wait_until='domcontentloaded')
            pg.wait_for_timeout(350)
            pg.screenshot(path=os.path.join(OUT, f'{width}_{path}.png'))
        pg.goto(f'{BASE}/t/platform/owner/dashboard', wait_until='domcontentloaded')
        pg.wait_for_timeout(300)
        pg.locator('button[aria-label="إعدادات الواجهة"]').first.click()
        pg.wait_for_timeout(250)
        pg.screenshot(path=os.path.join(OUT, f'{width}_dashboard_dropdown.png'))
        pg.close()
    b.close()
print('captured')
