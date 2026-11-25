"""Exercise the advanced UI controls and record whether they really work."""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get('PLATFORM_ADMIN_PASSWORD', 'Azad@1983@2026@11@25')
STAFF_PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'feature_probe.json')


def login(pg, user, password, tenant):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', tenant)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return True
    return False


results = []


def record(name, ok, detail):
    results.append({'feature': name, 'status': 'works' if ok else 'not-verified', 'detail': detail})
    print(f'{"OK " if ok else "?? "} {name}: {detail}')


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})

    # staff shell: search, prefs, notifications
    login(pg, 'audit_doctor', STAFF_PASSWORD, 'full-demo-center')
    pg.goto(f'{BASE}/t/full-demo-center/doctor/dashboard', wait_until='domcontentloaded')
    pg.fill('#globalSearchInput', 'مريض')
    pg.wait_for_timeout(900)
    dropdown = pg.locator('#globalSearchResults')
    record(
        'global search',
        dropdown.count() > 0 and 'd-none' not in (dropdown.get_attribute('class') or ''),
        'search dropdown responds',
    )

    pg.click('#themeToggleBtn')
    pg.wait_for_timeout(300)
    theme_attr = pg.evaluate("document.documentElement.getAttribute('data-theme')")
    record('theme toggle', theme_attr == 'dark', f'data-theme={theme_attr}')
    pg.click('#themeToggleBtn')

    pg.click('#notificationDropdown button')
    pg.wait_for_timeout(300)
    note = pg.locator('#notificationList').inner_text()
    record('notification bell', len(note.strip()) > 0, note.strip()[:70])

    pg.goto(f'{BASE}/t/full-demo-center/api/user/preferences', wait_until='domcontentloaded')
    record(
        'user preferences API',
        pg.locator('body').inner_text().strip().startswith('{'),
        'JSON response',
    )

    # platform: theme default + AI assistant
    login(pg, 'superadmin', ADMIN_PASSWORD, 'platform')
    pg.goto(f'{BASE}/t/platform/owner/themes', wait_until='domcontentloaded')
    before = pg.locator('body').inner_text()
    buttons = pg.locator('form button[type=submit]').count()
    record('theme catalogue', buttons > 0, f'{buttons} theme action buttons rendered')

    pg.goto(f'{BASE}/t/platform/super-admin/dashboard', wait_until='domcontentloaded')
    pg.click('#intelligence-tab')
    pg.wait_for_timeout(400)
    pg.fill('#aiInput', 'حلل أداء النظام')
    pg.click('#sendBtn')
    pg.wait_for_timeout(1800)
    bubbles = pg.locator('.ai-message').count()
    body = pg.locator('body').inner_text()
    record(
        'AI assistant',
        'تعذر' not in body[-500:] and bubbles > 0,
        f'{bubbles} bubbles, response present',
    )

    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', OUT)
