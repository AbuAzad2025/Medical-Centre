from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
TENANT = 'dr-ahmed-clinic'
PASSWORD = 'Clinic@2026'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'admin')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    print('login', pg.url)
    paths = [
        '/doctor/dashboard',
        '/doctor/patients',
        '/doctor/patient-queue',
        '/doctor/visits',
        '/reception/patients',
        '/reception/queue',
        '/booking/register',
        '/booking/create',
        '/booking/dashboard',
        '/accountant/dashboard',
    ]
    for path in paths:
        try:
            r = pg.goto(f'{BASE}/t/{TENANT}{path}', wait_until='domcontentloaded', timeout=12000)
            print(r.status, path, '->', pg.url.split('/t/')[-1])
        except Exception as exc:  # noqa: BLE001
            print('ERR', path, str(exc)[:60])
    b.close()
