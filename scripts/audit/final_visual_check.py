"""Final UX regression check: overlap, horizontal overflow, 500s, markers."""

import json
import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get('PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{datetime.now():%Y@%m@%d}')
STAFF_PASSWORD = 'Audit@2026Pass'
SHOTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'visual_recheck')
os.makedirs(SHOTS, exist_ok=True)
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'final_visual_check.json')

CHECKS = [
    ('superadmin', ADMIN_PASSWORD, 'platform', '/owner/dashboard'),
    ('superadmin', ADMIN_PASSWORD, 'platform', '/owner/themes'),
    ('superadmin', ADMIN_PASSWORD, 'platform', '/super-admin/dashboard'),
    ('audit_doctor', STAFF_PASSWORD, 'full-demo-center', '/doctor/dashboard'),
    ('audit_doctor', STAFF_PASSWORD, 'full-demo-center', '/doctor/patient-queue'),
    ('audit_reception', STAFF_PASSWORD, 'full-demo-center', '/reception/patients'),
    ('audit_reception', STAFF_PASSWORD, 'full-demo-center', '/reception/queue'),
    ('audit_accountant', STAFF_PASSWORD, 'full-demo-center', '/accountant/invoices'),
    ('audit_manager', STAFF_PASSWORD, 'full-demo-center', '/manager/unit-control'),
    ('audit_nurse', STAFF_PASSWORD, 'full-demo-center', '/nurse/dashboard'),
    ('audit_pharmacist', STAFF_PASSWORD, 'full-demo-center', '/medication/dashboard'),
    ('patient_0501112233', STAFF_PASSWORD, 'full-demo-center', '/portal/dashboard'),
]


def login(pg, user, password, tenant):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', tenant)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
    return False


results = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    current = None
    for user, password, tenant, path in CHECKS:
        if (user, tenant) != current:
            login(pg, user, password, tenant)
            current = (user, tenant)
        try:
            r = pg.goto(f'{BASE}/t/{tenant}{path}', wait_until='domcontentloaded', timeout=15000)
            pg.wait_for_timeout(400)
            status = r.status
            body = pg.locator('body').inner_text()[:3000]
            marker = any(
                m in body
                for m in (
                    'Internal Server Error',
                    'Traceback (most recent call last)',
                    'حدث خطأ غير متوقع',
                )
            )
            geom = pg.evaluate(
                """() => {
                  const aside=document.querySelector('aside');
                  const main=document.querySelector('main');
                  if(!aside||!main) return {overlap:null,overflow:document.body.scrollWidth>innerWidth+4};
                  const a=aside.getBoundingClientRect(), m=main.getBoundingClientRect();
                  return {aside:[Math.round(a.left),Math.round(a.right)],
                          main:[Math.round(m.left),Math.round(m.right)],
                          overlap: (Math.min(a.right,m.right)-Math.max(a.left,m.left))>4,
                          overflow: document.body.scrollWidth>innerWidth+4};
                }"""
            )
        except Exception as exc:  # noqa: BLE001
            status, marker, geom = None, str(exc)[:100], {}
        entry = {'user': user, 'path': path, 'status': status, 'marker': marker, 'geometry': geom}
        results.append(entry)
        print(f'{status} overlap={geom.get("overlap")} overflow={geom.get("overflow")} {path}')
        if marker or geom.get('overlap'):
            pg.screenshot(
                path=os.path.join(SHOTS, 'final_' + path.strip('/').replace('/', '_') + '.png')
            )
    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
bad = [
    r
    for r in results
    if r['status'] not in (200, 302) or r['marker'] or (r['geometry'] or {}).get('overlap')
]
print('problems', len(bad))
print('wrote', OUT)
