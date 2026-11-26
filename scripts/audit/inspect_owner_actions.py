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
    pg.wait_for_timeout(300)
    print(
        pg.evaluate(
            """() => Array.from(document.querySelectorAll('.owner-header-actions a, .owner-header-actions button'))
          .map(e=>({text:e.innerText.trim(), html:e.outerHTML.slice(0,200),
                    color:getComputedStyle(e).color, bg:getComputedStyle(e).backgroundColor,
                    display:getComputedStyle(e).display, vis:getComputedStyle(e).visibility,
                    opacity:getComputedStyle(e).opacity, w:Math.round(e.getBoundingClientRect().width)}))"""
        )
    )
    b.close()
