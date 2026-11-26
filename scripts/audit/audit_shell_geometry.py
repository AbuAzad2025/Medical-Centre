"""Measure sidebar/navbar/main geometry on every shell type."""

import os
import sys
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN = os.environ.get('PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{datetime.now():%Y@%m@%d}')
STAFF = 'Audit@2026Pass'

CASES = [
    ('superadmin', ADMIN, 'platform', '/owner/dashboard'),
    ('superadmin', ADMIN, 'platform', '/owner/bundles'),
    ('superadmin', ADMIN, 'platform', '/owner/provision'),
    ('superadmin', ADMIN, 'platform', '/super-admin/dashboard'),
    ('audit_doctor', STAFF, 'full-demo-center', '/doctor/dashboard'),
    ('audit_reception', STAFF, 'full-demo-center', '/reception/patients'),
    ('audit_doctor', STAFF, 'full-demo-center', '/manager/dashboard'),
    ('audit_pharmacist', STAFF, 'full-demo-center', '/medication/dashboard'),
    ('patient_0501112233', STAFF, 'full-demo-center', '/portal/dashboard'),
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


JS = """() => {
  const rect = e => { if(!e) return null; const r=e.getBoundingClientRect();
    return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)]; };
  const sidebars = Array.from(document.querySelectorAll('aside, .owner-sidebar, .portal-sidebar'))
    .map(e => ({cls:(e.className||'').toString().slice(0,50), box:rect(e), z:getComputedStyle(e).zIndex, top:getComputedStyle(e).top}));
  const navs = Array.from(document.querySelectorAll('nav.navbar, .platform-navbar, .portal-navbar, header'))
    .slice(0,3).map(e => ({cls:(e.className||'').toString().slice(0,40), box:rect(e), z:getComputedStyle(e).zIndex}));
  const main = document.querySelector('main');
  return {body:document.body.className, sidebars, navs, main:rect(main),
          mainML:main?getComputedStyle(main).marginLeft:null, mainMR:main?getComputedStyle(main).marginRight:null,
          docScroll:document.documentElement.scrollWidth, vw:innerWidth};
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    current = None
    for user, password, tenant, path in CASES:
        if (user, tenant) != current:
            login(pg, user, password, tenant)
            current = (user, tenant)
        pg.goto(f'{BASE}/t/{tenant}{path}', wait_until='domcontentloaded')
        pg.wait_for_timeout(450)
        data = pg.evaluate(JS)
        print(f'--- {path}')
        print('  body', data['body'])
        print('  sidebars', data['sidebars'])
        print('  navs', data['navs'])
        print(
            '  main',
            data['main'],
            data['mainML'],
            data['mainMR'],
            'scroll',
            data['docScroll'],
            data['vw'],
        )
    b.close()
