from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'audit_radiology')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    pg.goto(f'{BASE}/t/{TENANT}/radiology/reports', wait_until='domcontentloaded')
    print('page', pg.title(), 'forms', pg.locator('form').count())
    request_id = (
        pg.locator('input[name="request_id"]').first.get_attribute('value')
        if pg.locator('input[name="request_id"]').count()
        else None
    )
    print('request_id', request_id)
    if request_id:
        pg.fill('textarea[name="findings"]', 'فحص طبيعي — لا توجد شذوذات')
        pg.fill('textarea[name="impression"]', 'لا يوجد انطباع مرضي')
        pg.fill('textarea[name="recommendations"]', 'متابعة عند اللزوم')
        form = pg.locator('form').filter(has=pg.locator('textarea[name="findings"]'))
        form.evaluate('f => f.submit()')
        pg.wait_for_timeout(1300)
        pg.wait_for_load_state('domcontentloaded')
        print('url', pg.url)
        print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
