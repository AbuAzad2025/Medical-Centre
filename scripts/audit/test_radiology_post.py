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
    pg = b.new_page()
    login(pg, 'audit_doctor')
    pg.goto(f'{BASE}/t/{TENANT}/doctor/patient-details/12')
    csrf = pg.get_attribute('meta[name="csrf-token"]', 'content')
    result = pg.evaluate(
        """async ({csrf, url}) => {
          const body = new URLSearchParams({
            csrf_token: csrf, test_name: 'أشعة صدر', modality: 'XRAY',
            body_part: 'الصدر', notes: 'سعال مستمر'
          });
          const r = await fetch(url, {method:'POST', body, credentials:'same-origin', redirect:'manual'});
          return {status:r.status, location:r.headers.get('location')};
        }""",
        {'csrf': csrf, 'url': f'{BASE}/t/{TENANT}/doctor/radiology-request/12'},
    )
    print('post request', result)

    login(pg, 'audit_radiology')
    pg.goto(f'{BASE}/t/{TENANT}/radiology/reports')
    rid = (
        pg.locator('input[name="request_id"]').first.get_attribute('value')
        if pg.locator('input[name="request_id"]').count()
        else None
    )
    print('report id', rid)
    if rid:
        pg.fill('textarea[name="findings"]', 'لا توجد شذوذات')
        pg.fill('textarea[name="impression"]', 'فحص طبيعي')
        pg.fill('textarea[name="recommendations"]', 'متابعة عند اللزوم')
        pg.locator('form').filter(has=pg.locator('textarea[name="findings"]')).evaluate(
            'f => f.submit()'
        )
        pg.wait_for_timeout(1200)
        pg.wait_for_load_state('domcontentloaded')
        print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    b.close()
