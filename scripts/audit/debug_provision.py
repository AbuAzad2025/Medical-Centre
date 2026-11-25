from datetime import datetime

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = f'Azad@1983@{datetime.now():%Y@%m@%d}'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    pg.goto(f'{BASE}/auth/login')
    pg.fill('#username', 'superadmin')
    pg.fill('#password', PASSWORD)
    pg.select_option('#tenant_slug', 'platform')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1300)
    print('login', pg.url)
    pg.goto(f'{BASE}/t/platform/owner/provision')
    pg.fill('input[name="name"]', 'Package private_doctor_clinic')
    pg.fill('input[name="slug"]', 'pkg-private_doctor_clinic')
    pg.fill('input[name="contact_email"]', 'admin@pkg-private_doctor_clinic.local')
    pg.select_option('select[name="product_profile_code"]', 'private_doctor_clinic')
    pg.select_option('select[name="package_version_id"]', '1')
    pg.fill('input[name="admin_username"]', 'admin_private_doctor_clinic')
    pg.fill('input[name="admin_password"]', 'Audit@2026Pass')
    pg.fill('input[name="admin_full_name"]', 'Admin private_doctor_clinic')
    form = pg.locator('form').filter(has=pg.locator('input[name="admin_username"]')).first
    print('form action', form.get_attribute('action'))
    form.evaluate('f => f.submit()')
    pg.wait_for_timeout(1500)
    print('after', pg.url)
    print('flash', [s.strip() for s in pg.locator('.flash-message').all_inner_texts()])
    print('body', pg.locator('body').inner_text()[:400])
    b.close()
