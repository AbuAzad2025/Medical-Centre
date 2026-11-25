from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'audit_reception')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    pg.goto(f'{BASE}/t/{TENANT}/reception/view_visit/11', wait_until='domcontentloaded')
    print('url', pg.url, 'title', pg.title())
    forms = pg.eval_on_selector_all('form', 'els => els.map(f => f.getAttribute("action"))')
    print('forms', forms)
    form = pg.locator('form[action*="send-to-accounting"]')
    print('handoff forms', form.count())
    if form.count():
        form.first.evaluate('f => f.submit()')
        pg.wait_for_timeout(1300)
        pg.wait_for_load_state('domcontentloaded')
        print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
