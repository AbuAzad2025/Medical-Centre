"""Apply a calm medical colour palette through the branding UI."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = os.environ.get(
    'PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{__import__("datetime").datetime.now():%Y@%m@%d}'
)
COLORS = {
    'primary_color': '#0e7490',
    'secondary_color': '#059669',
    'accent_color': '#06b6d4',
}
TENANTS = ('full-demo-center',)


def login(pg):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'fulladmin')
        pg.fill('#password', 'Audit@2026Pass')
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError('login failed')


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    login(pg)
    for tenant in TENANTS:
        pg.goto(f'{BASE}/t/{tenant}/super-admin/branding', wait_until='domcontentloaded')
        for name, value in COLORS.items():
            locator = pg.locator(f'input[name="{name}"]')
            if locator.count():
                locator.first.fill(value)
        form = pg.locator('#brandingForm')
        form.evaluate('f => f.submit()')
        pg.wait_for_timeout(1200)
        pg.wait_for_load_state('domcontentloaded')
        try:
            messages = [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]
        except Exception:  # noqa: BLE001
            messages = []
        print(tenant, 'saved', messages)
    b.close()
