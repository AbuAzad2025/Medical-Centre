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
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            break
    pg.goto(f'{BASE}/t/platform/owner/dashboard', wait_until='domcontentloaded')
    pg.wait_for_timeout(500)
    print('url', pg.url, 'sidebar count', pg.locator('.clinical-sidebar').count())
    print(
        pg.evaluate(
            """() => {
          const sb=document.querySelector('.clinical-sidebar').getBoundingClientRect();
          const mc=document.querySelector('.main-container').getBoundingClientRect();
          const cards=Array.from(document.querySelectorAll('.card')).slice(0,4)
            .map(c=>{const r=c.getBoundingClientRect();return [Math.round(r.left),Math.round(r.right)];});
          return {sidebar:[sb.left,sb.right], main:[mc.left,mc.right], cards,
                  bodyClass:document.body.className, dir:document.documentElement.dir};
        }"""
        )
    )
    b.close()
