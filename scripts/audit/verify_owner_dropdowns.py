from datetime import datetime

from playwright.sync_api import sync_playwright

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
        pg.goto(f'{BASE}/t/platform/owner/dashboard', wait_until='domcontentloaded')
        pg.wait_for_timeout(300)

        # Settings dropdown
        prefs = pg.locator('button[aria-label="إعدادات الواجهة"], button[title="مظهر الواجهة"]')
        print(width, 'prefs toggles', prefs.count())
        if prefs.count():
            prefs.first.click()
            pg.wait_for_timeout(250)
            menu = pg.locator('.ui-prefs-menu')
            print('  open', menu.is_visible(), 'z', menu.evaluate('e=>getComputedStyle(e).zIndex'))
            print(
                '  density options',
                pg.locator('#uiDensitySelect option').count(),
                'radius options',
                pg.locator('#uiRadiusSelect option').count(),
            )
            pg.keyboard.press('Escape')
            pg.wait_for_timeout(300)
            print('  closed by Escape', not menu.is_visible())
            prefs.first.click()
            pg.wait_for_timeout(200)
            pg.locator('body').click(position={'x': 5, 'y': 5})
            pg.wait_for_timeout(300)
            print('  closed by outside click', not menu.is_visible())

        # User dropdown
        user = pg.locator('button[aria-label="قائمة المستخدم"]')
        print('  user toggles', user.count())
        if user.count():
            user.first.click()
            pg.wait_for_timeout(250)
            items = pg.locator(
                'button[aria-label="قائمة المستخدم"] + .dropdown-menu .dropdown-item'
            )
            print(
                '  user items',
                items.count(),
                [items.nth(i).inner_text().strip() for i in range(min(items.count(), 3))],
            )
        pg.close()
    b.close()
