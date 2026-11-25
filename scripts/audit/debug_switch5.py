from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for url in (
        'http://localhost:8000/set-language/en',
        'http://localhost:8000/t/full-demo-center/set-language/en',
    ):
        pg = b.new_page()
        pg.goto('http://localhost:8000/auth/login')
        pg.fill('#username', 'audit_doctor')
        pg.fill('#password', 'Audit@2026Pass')
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        r = pg.goto(url)
        print(url, '->', r.status, pg.url)
        pg.goto('http://localhost:8000/t/full-demo-center/doctor/dashboard')
        print('  lang', pg.evaluate('document.documentElement.lang'))
        pg.close()
    b.close()
