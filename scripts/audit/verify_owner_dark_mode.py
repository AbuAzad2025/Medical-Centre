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
    pg.goto(f'{BASE}/t/platform/owner/provision', wait_until='domcontentloaded')
    pg.wait_for_timeout(300)
    for mode in ('light', 'dark'):
        if mode == 'dark':
            pg.click('#themeToggleBtn')
            pg.wait_for_timeout(350)
        print(
            mode,
            pg.evaluate(
                """() => {
              const i=document.querySelector('input[name="name"]');
              const l=i.closest('.owner-form-group')?.querySelector('label') || document.querySelector('label');
              const bg=getComputedStyle(i).backgroundColor, fg=getComputedStyle(i).color;
              return {theme:document.documentElement.getAttribute('data-theme'), bg, fg,
                      label:l?getComputedStyle(l).color:null, labelText:l?l.innerText.trim():null};
            }"""
            ),
        )
    b.close()
