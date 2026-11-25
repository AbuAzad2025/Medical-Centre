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
    net = []
    pg.on(
        'response',
        lambda r: (
            net.append((r.status, r.url, r.headers.get('location'), r.headers.get('set-cookie')))
            if 'set-language' in r.url
            else None
        ),
    )
    pg.goto('http://localhost:8000/t/full-demo-center/set-language/en')
    pg.wait_for_timeout(300)
    for item in net:
        print(item)
    b.close()
