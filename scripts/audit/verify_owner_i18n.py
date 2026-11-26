from datetime import datetime

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = f'Azad@1983@{datetime.now():%Y@%m@%d}'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'superadmin')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'platform')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    pg.goto(f'{BASE}/t/platform/owner/dashboard')
    pg.locator('button[aria-label="إعدادات الواجهة"]').first.click()
    pg.wait_for_timeout(250)
    pg.screenshot(path='docs/PAGE_AUDIT/owner_proof/1280_dashboard_dropdown_fixed.png')
    pg.keyboard.press('Escape')

    for lang in ('ar', 'en'):
        if lang == 'en':
            pg.goto(f'{BASE}/t/platform/set-language/en')
            pg.wait_for_timeout(400)
        pg.goto(f'{BASE}/t/platform/owner/system-config', wait_until='domcontentloaded')
        pg.wait_for_timeout(400)
        print(
            lang,
            pg.evaluate(
                """() => ({
              head:document.querySelector('.owner-header-title')?.innerText.trim(),
              headers:Array.from(document.querySelectorAll('table thead th')).map(e=>e.innerText.trim()),
              types:Array.from(document.querySelectorAll('.owner-table .badge.bg-info-light')).slice(0,4).map(e=>e.innerText.trim()),
              cats:Array.from(document.querySelectorAll('.owner-table .badge.bg-light')).slice(0,4).map(e=>e.innerText.trim()),
              typeOptions:Array.from(document.querySelectorAll('[name="new_config_type"] option')).map(e=>e.text),
              catOptions:Array.from(document.querySelectorAll('[name="new_config_category"] option')).map(e=>e.text)
            })"""
            ),
        )
        pg.screenshot(path=f'docs/PAGE_AUDIT/owner_proof/system_config_{lang}.png')
    b.close()
