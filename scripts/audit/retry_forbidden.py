"""For pages that answered 403 in the main walk, try the other real roles.

A 403 is correct isolation if at least one entitled role can open the page.
A page that is 403 for every real role is a genuine dead end.
"""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get(
    'PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{__import__("datetime").datetime.now():%Y@%m@%d}'
)
STAFF_PASSWORD = 'Audit@2026Pass'
ALT_ROLES = [
    ('admin', 'fulladmin', STAFF_PASSWORD, 'full-demo-center'),
    ('manager', 'audit_manager', STAFF_PASSWORD, 'full-demo-center'),
    ('doctor', 'audit_doctor', STAFF_PASSWORD, 'full-demo-center'),
    ('reception', 'audit_reception', STAFF_PASSWORD, 'full-demo-center'),
    ('super_admin', 'superadmin', ADMIN_PASSWORD, 'platform'),
]

PLACEHOLDER = re.compile(r'<(?:int|str|path|uuid):[^>]+>|<int:[^>]+>')


def login(pg, user, password, tenant):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', tenant)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return True
    return False


def main():
    src = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'walk_results.json')
    out = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'forbidden_retry.json')
    with open(src, encoding='utf-8') as fh:
        results = json.load(fh)['results']

    forbidden = [r for r in results if r.get('status') == 403]
    print(f'retrying {len(forbidden)} forbidden pages')
    findings = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        pg = browser.new_page(viewport={'width': 1280, 'height': 800})
        for label, user, password, tenant in ALT_ROLES:
            if not login(pg, user, password, tenant):
                print(f'LOGIN FAILED {label}')
                continue
            for r in forbidden:
                path = PLACEHOLDER.sub('1', r['path'])
                url = f'{BASE}/t/{tenant}{path}' if tenant != 'platform' else f'{BASE}{path}'
                try:
                    resp = pg.goto(url, wait_until='domcontentloaded', timeout=15000)
                    status = resp.status if resp else None
                except Exception as exc:  # noqa: BLE001
                    status = str(exc)[:40]
                findings.append(
                    {
                        'path': path,
                        'original_role': r['role'],
                        'tried_role': label,
                        'status': status,
                        'final_url': pg.url,
                    }
                )
        browser.close()

    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'total': len(findings), 'results': findings}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    by_path = {}
    for f in findings:
        by_path.setdefault(f['path'], {})[f['tried_role']] = f['status']
    dead = [p for p, roles in by_path.items() if not any(s == 200 for s in roles.values())]
    print(f'paths={len(by_path)} dead_ends={len(dead)}')
    for p in dead:
        print('  DEAD', p, by_path[p])


if __name__ == '__main__':
    main()
