from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'


def login(pg, user):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError(user)


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    login(pg, 'audit_doctor')
    pg.goto(f'{BASE}/t/{TENANT}/doctor/radiology-request/12', wait_until='domcontentloaded')
    print(
        'page',
        pg.url,
        pg.title(),
        [s.strip() for s in pg.locator('.flash-message').all_inner_texts()],
    )
    for name, value in (
        ('test_name', 'أشعة صدر'),
        ('modality', 'XRAY'),
        ('body_part', 'الصدر'),
        ('notes', 'سعال مستمر'),
    ):
        loc = pg.locator(f'[name="{name}"]')
        if loc.count():
            loc.first.fill(value)
    form = pg.locator('form').filter(has=pg.locator('[name="modality"]'))
    print('forms', form.count())
    if form.count():
        form.first.evaluate('f => f.submit()')
        pg.wait_for_timeout(1200)
        pg.wait_for_load_state('domcontentloaded')
        print('created', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])

    login(pg, 'audit_radiology')
    pg.goto(f'{BASE}/t/{TENANT}/radiology/reports', wait_until='domcontentloaded')
    rid = (
        pg.locator('input[name="request_id"]').first.get_attribute('value')
        if pg.locator('input[name="request_id"]').count()
        else None
    )
    print('report request_id', rid)
    if rid:
        pg.fill('textarea[name="findings"]', 'لا توجد شذوذات ظاهرة')
        pg.fill('textarea[name="impression"]', 'فحص طبيعي')
        pg.fill('textarea[name="recommendations"]', 'متابعة عند اللزوم')
        form = pg.locator('form').filter(has=pg.locator('textarea[name="findings"]'))
        form.evaluate('f => f.submit()')
        pg.wait_for_timeout(1300)
        pg.wait_for_load_state('domcontentloaded')
        print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
