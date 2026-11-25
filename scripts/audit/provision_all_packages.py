"""Provision one tenant per package through the owner UI (production readiness)."""

import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get('PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{datetime.now():%Y@%m@%d}')
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'package_tenants.json')

PACKAGES = [
    (1, 'private_doctor_clinic', 'private_doctor_clinic'),
    (2, 'doctor_clinic_reception', 'private_doctor_clinic'),
    (3, 'doctor_clinic_full', 'private_doctor_clinic'),
    (4, 'small_clinic', 'small_clinic'),
    (5, 'clinic_with_lab', 'small_clinic'),
    (6, 'clinic_with_radiology', 'small_clinic'),
    (7, 'clinic_with_lab_radiology', 'small_clinic'),
    (8, 'standalone_lab', 'standalone_lab'),
    (9, 'lab_with_reception', 'standalone_lab'),
    (10, 'standalone_radiology', 'standalone_radiology'),
    (11, 'radiology_with_reception', 'standalone_radiology'),
    (12, 'standalone_pharmacy', 'standalone_pharmacy'),
    (13, 'standalone_emergency', 'multi_department_center'),
    (14, 'walkin_clinic', 'small_clinic'),
    (15, 'urgent_care', 'multi_department_center'),
    (16, 'diagnostic_center', 'standalone_lab'),
    (17, 'community_clinic', 'multi_department_center'),
    (18, 'nursing_home', 'multi_department_center'),
    (19, 'multi_department_center', 'multi_department_center'),
    (20, 'polyclinic', 'multi_department_center'),
    (21, 'hospital', 'multi_department_center'),
    (22, 'billing_only', 'custom'),
    (23, 'custom', 'custom'),
]


def login(pg):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'superadmin')
        pg.fill('#password', ADMIN_PASSWORD)
        pg.select_option('#tenant_slug', 'platform')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError('login failed')


results = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    login(pg)
    for version_id, slug, profile in PACKAGES:
        tenant_slug = 'pkg-' + slug.replace('_', '-')
        for attempt in range(4):
            try:
                pg.goto(f'{BASE}/t/platform/owner/provision', wait_until='domcontentloaded')
                pg.wait_for_timeout(250)
                break
            except Exception:  # noqa: BLE001
                pg.wait_for_timeout(600)
        pg.fill('input[name="name"]', f'Package {slug}')
        pg.fill('input[name="slug"]', tenant_slug)
        pg.fill('input[name="contact_email"]', f'admin@{tenant_slug}.local')
        pg.select_option('select[name="product_profile_code"]', profile)
        pg.select_option('select[name="package_version_id"]', str(version_id))
        pg.fill('input[name="admin_username"]', f'admin_{slug}')
        pg.fill('input[name="admin_password"]', PASSWORD)
        pg.fill('input[name="admin_full_name"]', f'Admin {slug}')
        form = pg.locator('form').filter(has=pg.locator('input[name="admin_username"]')).first
        form.evaluate('f => f.submit()')
        pg.wait_for_timeout(1500)
        pg.wait_for_load_state('domcontentloaded')
        pg.wait_for_timeout(250)
        try:
            flash = [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]
        except Exception:  # noqa: BLE001
            flash = []
        ok = 'تم إنشاء العميل' in ' '.join(flash) or 'tenant' in pg.url
        results.append(
            {
                'version_id': version_id,
                'slug': slug,
                'tenant_slug': tenant_slug,
                'ok': ok,
                'flash': flash,
                'url': pg.url,
            }
        )
        print(f'{version_id:2} {slug:26} {"OK" if ok else "CHECK"} {str(flash)[:90]}')
    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', OUT)
