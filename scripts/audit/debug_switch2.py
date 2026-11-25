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
    before = [c for c in pg.context.cookies() if c['name'] == 'session'][0]['value']
    pg.goto('http://localhost:8000/t/full-demo-center/set-language/en')
    after = [c for c in pg.context.cookies() if c['name'] == 'session'][0]['value']
    print('session changed', before != after, 'len', len(before), len(after))
    pg.goto('http://localhost:8000/t/full-demo-center/doctor/dashboard')
    print('lang', pg.evaluate('document.documentElement.lang'))
    print('body', pg.locator('body').inner_text()[:120].replace('\n', ' / '))
    b.close()
