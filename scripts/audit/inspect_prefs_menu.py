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
    print(
        pg.evaluate(
            """() => {
          const m=document.querySelector('.ui-prefs-menu');
          const s=document.querySelector('#uiDensitySelect');
          const r=e=>{const b=e.getBoundingClientRect();return [Math.round(b.left),Math.round(b.top),Math.round(b.width),Math.round(b.height)];};
          return {menu:r(m), menuPad:getComputedStyle(m).padding, menuFont:getComputedStyle(m).fontSize,
                  select:r(s), selectFont:getComputedStyle(s).fontSize, selectPad:getComputedStyle(s).padding,
                  labelFont:getComputedStyle(m.querySelector('label')).fontSize,
                  optionCount:s.options.length,
                  options:Array.from(s.options).map(o=>o.text)};
        }"""
        )
    )
    b.close()
