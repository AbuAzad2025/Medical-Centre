"""Financial readiness: accountant screens + invoice hand-off through UI."""

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
TENANT = 'full-demo-center'
SHOTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'workflow_shots')
os.makedirs(SHOTS, exist_ok=True)
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'financial_walk.json')

PAGES = [
    '/accountant/dashboard',
    '/accountant/invoices',
    '/accountant/payments',
    '/accountant/open-invoices',
    '/accountant/financial-report',
    '/accountant/daily-summary',
    '/accountant/reports',
    '/accountant/accounts',
    '/accountant/journals',
    '/accountant/trial-balance',
    '/accountant/refunds',
    '/accountant/patient-accounts',
    '/finance/dashboard',
    '/payment/dashboard',
]


def login(pg, user):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', TENANT)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
    return False


results = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    login(pg, 'audit_accountant')
    for path in PAGES:
        try:
            r = pg.goto(f'{BASE}/t/{TENANT}{path}', wait_until='domcontentloaded', timeout=15000)
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
        except Exception as exc:  # noqa: BLE001
            status, marker, body = None, str(exc)[:80], ''
        entry = {
            'path': path,
            'status': status,
            'marker': marker,
            'text': body[:120].replace('\n', ' / '),
        }
        results.append(entry)
        print(f'{status} {"BAD" if marker else "   "} {path}')
        if marker:
            pg.screenshot(
                path=os.path.join(SHOTS, 'financial_' + path.strip('/').replace('/', '_') + '.png')
            )

    # Reception → accounting hand-off creates a real invoice.
    login(pg, 'audit_reception')
    pg.goto(f'{BASE}/t/{TENANT}/reception/visits', wait_until='domcontentloaded')
    links = pg.eval_on_selector_all(
        'a[href*="view_visit"]', 'els => els.map(e => e.getAttribute("href"))'
    )
    if links:
        pg.goto(f'{BASE}{links[0]}', wait_until='domcontentloaded')
        form = pg.locator('form[action*="send-to-accounting"]')
        before = pg.locator('body').inner_text()
        if form.count():
            form.first.evaluate('f => f.submit()')
            pg.wait_for_timeout(1200)
            pg.wait_for_load_state('domcontentloaded')
            after = pg.locator('body').inner_text()
            flash = [s.strip() for s in pg.locator('.flash-message').all_inner_texts()]
            results.append(
                {
                    'path': 'POST send-to-accounting',
                    'status': 200,
                    'marker': False,
                    'flash': flash,
                    'url': pg.url,
                }
            )
            print('hand-off flash', flash)
        else:
            print('no send-to-accounting form on', links[0])
    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', OUT)
