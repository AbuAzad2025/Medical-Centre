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
    for path in ('/owner/dashboard', '/owner/provision', '/owner/subscriptions'):
        pg.goto(f'{BASE}/t/platform{path}', wait_until='domcontentloaded')
        pg.wait_for_timeout(400)
        print('---', path)
        print(
            pg.evaluate(
                """() => {
              const nav=document.querySelector('.platform-navbar');
              const kids=Array.from(nav.querySelectorAll(':scope > .container-fluid > *')).map(e=>({
                cls:(e.className||'').toString().slice(0,40),
                h:Math.round(e.getBoundingClientRect().height),
                txt:(e.innerText||'').slice(0,30)
              }));
              const brand=nav.querySelector('.navbar-brand');
              return {navH:Math.round(nav.getBoundingClientRect().height),
                navPad:getComputedStyle(nav).padding, kids,
                brandH:brand?Math.round(brand.getBoundingClientRect().height):null,
                brandImg:!!nav.querySelector('.navbar-brand img')};
            }"""
            )
        )
    b.close()
