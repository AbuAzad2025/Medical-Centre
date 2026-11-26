from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'audit_doctor')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    net = []
    pg.on(
        'response',
        lambda r: (
            net.append((r.status, r.url, r.headers.get('location')))
            if 'radiology-request' in r.url
            else None
        ),
    )
    pg.goto(f'{BASE}/t/{TENANT}/doctor/radiology-request/12')
    pg.wait_for_timeout(500)
    print('net', net)
    print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    print('url', pg.url)
    b.close()
