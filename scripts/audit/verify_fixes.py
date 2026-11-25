"""Re-verify the pages that were broken before the fixes."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get('PLATFORM_ADMIN_PASSWORD', 'Azad@1983@2026@11@25')


def login(pg):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'superadmin')
        pg.fill('#password', ADMIN_PASSWORD)
        pg.select_option('#tenant_slug', 'platform')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1300)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError('login failed')


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    login(pg)
    for path in (
        '/super-admin/branding/preview',
        '/super-admin/branding/preview?doc_type=prescription',
        '/backup-restore/',
        '/super-admin/users/create',
    ):
        r = pg.goto(f'{BASE}{path}', wait_until='domcontentloaded')
        body = pg.locator('body').inner_text()[:2000]
        print(
            path,
            '->',
            r.status,
            '| error-marker:',
            'Internal Server Error' in body or 'حدث خطأ غير متوقع' in body,
        )
    roles = (
        pg.eval_on_selector_all('select[name=role] option', 'els => els.map(e => e.value)')
        if pg.locator('select[name=role]').count()
        else []
    )
    print('role options:', roles)
    b.close()
