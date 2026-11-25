from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    for pwd in ('Audit@2026Pass', 'Audit@2026'):
        pg.goto('http://localhost:8000/auth/login')
        pg.fill('#username', 'fulladmin')
        pg.fill('#password', pwd)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1300)
        print(pwd, '->', pg.url, [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
