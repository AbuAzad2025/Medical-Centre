from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('http://localhost:8000/auth/login')
    pg.fill('#username', 'audit_doctor')
    pg.fill('#password', 'Audit@2026Pass')
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)
    print('after login', pg.url)
    r = pg.goto(
        'http://localhost:8000/t/full-demo-center/set-language/en', wait_until='domcontentloaded'
    )
    print('switch', r.status, pg.url)
    print('cookies', [c['name'] for c in pg.context.cookies()])
    r2 = pg.goto(
        'http://localhost:8000/t/full-demo-center/doctor/dashboard', wait_until='domcontentloaded'
    )
    print('dashboard', r2.status, pg.evaluate('document.documentElement.lang'))
    b.close()
