"""Provision a full-module demo tenant and one real user per operating role.

Everything goes through the real UI (owner provisioning form + super-admin user
creation form). No seed scripts, no direct DB writes.
"""

import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get(
    'PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{__import__("datetime").datetime.now():%Y@%m@%d}'
)
STAFF_PASSWORD = 'Audit@2026Pass'
TENANT_SLUG = 'full-demo-center'
TENANT_NAME = 'المركز الطبي الشامل'
ADMIN_USER = 'fulladmin'
PACKAGE_VERSION_ID = '21'  # hospital

STAFF_ROLES = [
    ('manager', 'مدير الجولة'),
    ('reception', 'استقبال الجولة'),
    ('doctor', 'طبيب الجولة'),
    ('lab', 'مختبر الجولة'),
    ('radiology', 'أشعة الجولة'),
    ('pharmacist', 'صيدلي الجولة'),
    ('nurse', 'ممرضة الجولة'),
    ('emergency', 'طوارئ الجولة'),
    ('accountant', 'محاسب الجولة'),
    ('technician', 'فني الجولة'),
]


def login(page, username, password, tenant_slug):
    for attempt in range(4):
        page.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        page.select_option('#tenant_slug', tenant_slug)
        page.click('button[type="submit"]')
        page.wait_for_load_state('domcontentloaded')
        page.wait_for_timeout(1500)
        if '/auth/login' not in page.url:
            return page.url
        print(f'  login attempt {attempt + 1} failed; retrying')
    raise RuntimeError(f'could not log in as {username}')


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        print('LOGIN superadmin ->', login(page, 'superadmin', ADMIN_PASSWORD, 'platform'))
        print('URL:', page.url)

        # --- Provision the full-module tenant through the owner UI ---
        if os.environ.get('SKIP_PROVISION') != '1':
            page.goto(f'{BASE}/t/platform/owner/provision', wait_until='domcontentloaded')
            page.fill('input[name="name"]', TENANT_NAME)
            page.fill('input[name="slug"]', TENANT_SLUG)
            page.fill('input[name="contact_email"]', f'admin@{TENANT_SLUG}.local')
            page.select_option('select[name="product_profile_code"]', 'multi_department_center')
            page.select_option('select[name="package_version_id"]', PACKAGE_VERSION_ID)
            page.fill('input[name="admin_username"]', ADMIN_USER)
            page.fill('input[name="admin_password"]', STAFF_PASSWORD)
            page.fill('input[name="admin_full_name"]', 'مدير المركز الشامل')
            page.click('button[type="submit"], input[type="submit"]')
            page.wait_for_load_state('domcontentloaded')
            time.sleep(1)
            print('AFTER PROVISION:', page.url)
            print(
                'FLASH:',
                [
                    s.encode('ascii', 'replace').decode()
                    for s in page.locator('.alert').all_inner_texts()[:3]
                ],
            )

        # --- Create staff users as superadmin in the new tenant's context ---
        page.goto(f'{BASE}/t/{TENANT_SLUG}/super-admin/users/create', wait_until='domcontentloaded')
        print('USER CREATE PAGE:', page.url, page.title())
        create_url = f'{BASE}/t/{TENANT_SLUG}/super-admin/users/create'
        for role, full_name in STAFF_ROLES:
            username = f'audit_{role}'
            page.goto(create_url, wait_until='domcontentloaded')
            page.fill('input[name="username"]', username)
            page.fill('input[name="email"]', f'{username}@{TENANT_SLUG}.local')
            page.fill('input[name="full_name"]', full_name)
            page.select_option('select[name="role"]', role)
            page.fill('input[name="password"]', STAFF_PASSWORD)
            page.fill('input[name="confirm_password"]', STAFF_PASSWORD)
            page.check('input[name="is_active"]')
            page.click('button[type="submit"]')
            page.wait_for_load_state('domcontentloaded')
            time.sleep(0.3)
            print(f'  submitted {username}: {page.url}')
        print('PAGE ERRORS:', errors[:10])
        browser.close()


if __name__ == '__main__':
    main()
