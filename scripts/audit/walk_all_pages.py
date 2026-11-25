"""Visual/functional walkthrough of every GET route with real users.

Reads docs/PAGE_AUDIT/inventory.json. For every role it logs in through the
real login form, then visits each GET route whose module belongs to that role.
It records HTTP status, redirects, console errors and page-error markers, and
saves a screenshot per page. Results feed docs/PAGE_AUDIT/findings.md.

Usage:
    python scripts/audit/walk_all_pages.py [--roles manager,doctor,...] [--limit N]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
ADMIN_PASSWORD = os.environ.get(
    'PLATFORM_ADMIN_PASSWORD', f'Azad@1983@{__import__("datetime").datetime.now():%Y@%m@%d}'
)
STAFF_PASSWORD = 'Audit@2026Pass'
SHOT_DIR = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'screenshots')
RESULTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'walk_results.json')

ROLE_USERS = {
    'super_admin': ('superadmin', ADMIN_PASSWORD, 'platform'),
    'any': ('audit_doctor', STAFF_PASSWORD, 'full-demo-center'),
    'manager': ('audit_manager', STAFF_PASSWORD, 'full-demo-center'),
    'reception': ('audit_reception', STAFF_PASSWORD, 'full-demo-center'),
    'doctor': ('audit_doctor', STAFF_PASSWORD, 'full-demo-center'),
    'lab': ('audit_lab', STAFF_PASSWORD, 'full-demo-center'),
    'radiology': ('audit_radiology', STAFF_PASSWORD, 'full-demo-center'),
    'pharmacist': ('audit_pharmacist', STAFF_PASSWORD, 'full-demo-center'),
    'nurse': ('audit_nurse', STAFF_PASSWORD, 'full-demo-center'),
    'emergency': ('audit_emergency', STAFF_PASSWORD, 'full-demo-center'),
    'accountant': ('audit_accountant', STAFF_PASSWORD, 'full-demo-center'),
    'technician': ('audit_technician', STAFF_PASSWORD, 'full-demo-center'),
    'patient': ('audit_doctor', STAFF_PASSWORD, 'full-demo-center'),
}

PLACEHOLDER = re.compile(r'<(?:int|str|path|uuid):[^>]+>|<int:[^>]+>')


def concrete(path):
    return PLACEHOLDER.sub('1', path)


def login(pg, username, password, tenant_slug):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', username)
        pg.fill('#password', password)
        pg.select_option('#tenant_slug', tenant_slug)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return True
    return False


def visit(pg, role, route, shot_index):
    path = concrete(route['path'])
    prefix = '' if role == 'super_admin' else f'/t/{ROLE_USERS[role][2]}'
    url = f'{BASE}{prefix}{path}'
    entry = {
        'role': role,
        'path': path,
        'endpoint': route['endpoint'],
        'module': route['module'],
        'url': url,
    }
    console_errors = []

    def handler(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)

    pg.on('console', handler)
    response = None
    try:
        response = pg.goto(url, wait_until='domcontentloaded', timeout=20000)
        pg.wait_for_timeout(120)
        entry['status'] = response.status if response else None
        entry['final_url'] = pg.url
        entry['title'] = pg.title()
        body = pg.locator('body').inner_text()[:4000] if pg.locator('body').count() else ''
        entry['is_json'] = pg.locator('body').inner_text().strip().startswith(('{', '['))
        markers = []
        for needle in (
            'Traceback (most recent call last)',
            'Internal Server Error',
            'لقد حدث خطأ',
            'حدث خطأ غير متوقع',
            '[^',  # untranslated/i18n placeholder
        ):
            if needle in body:
                markers.append(needle)
        entry['markers'] = markers
        entry['console_errors'] = console_errors[:5]
        if not entry['is_json'] and entry['status'] == 200:
            os.makedirs(os.path.join(SHOT_DIR, role), exist_ok=True)
            slug = re.sub(r'[^A-Za-z0-9_-]+', '_', path).strip('_')[:110] or 'root'
            shot = os.path.join(SHOT_DIR, role, f'{shot_index:04d}_{slug}.png')
            try:
                pg.screenshot(path=shot)
                entry['screenshot'] = os.path.relpath(shot, ROOT).replace('\\', '/')
            except Exception as exc:  # noqa: BLE001
                entry['screenshot_error'] = str(exc)[:120]
    except Exception as exc:  # noqa: BLE001
        entry['status'] = None
        entry['error'] = str(exc)[:200]
    finally:
        pg.remove_listener('console', handler)
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--roles', help='comma-separated roles to walk')
    ap.add_argument('--limit', type=int, default=0, help='max pages per role (0 = all)')
    args = ap.parse_args()

    with open(os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.json'), encoding='utf-8') as fh:
        inventory = json.load(fh)

    by_role = defaultdict(list)
    for route in inventory['routes']:
        if not route['is_get']:
            continue
        if route['classification'] in ('public',):
            continue
        by_role[route['role']].append(route)

    roles = args.roles.split(',') if args.roles else sorted(by_role)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        pg = context.new_page()
        for role in roles:
            routes = by_role.get(role, [])
            if args.limit:
                routes = routes[: args.limit]
            user, password, tenant = ROLE_USERS.get(role, ROLE_USERS['any'])
            if not login(pg, user, password, tenant):
                print(f'[{role}] LOGIN FAILED')
                continue
            print(f'[{role}] walking {len(routes)} pages as {user}')
            for i, route in enumerate(routes, 1):
                entry = visit(pg, role, route, i)
                results.append(entry)
                if i % 20 == 0:
                    print(f'  {i}/{len(routes)}')
        browser.close()

    with open(RESULTS, 'w', encoding='utf-8') as fh:
        json.dump({'total': len(results), 'results': results}, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    statuses = Counter(r.get('status') for r in results)
    print('\nSTATUS COUNTS:', dict(statuses))
    print('WITH MARKERS:', sum(1 for r in results if r.get('markers')))
    print('WITH CONSOLE ERRORS:', sum(1 for r in results if r.get('console_errors')))
    print('SCREENSHOTS:', sum(1 for r in results if r.get('screenshot')))
    print('RESULTS:', RESULTS)


if __name__ == '__main__':
    main()
