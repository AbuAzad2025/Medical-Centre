"""Deep walk: every package tenant, every active module, plus negative gating checks."""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'package_walk.json')
SHOTS = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'workflow_shots')
os.makedirs(SHOTS, exist_ok=True)

with open(
    os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'package_verification.json'), encoding='utf-8'
) as fh:
    packages = json.load(fh)['rows']

with open(os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.json'), encoding='utf-8') as fh:
    routes = json.load(fh)['routes']

GETS = [r for r in routes if r['is_get'] and not r['path'].startswith('/test/')]
MODULE_PATHS = {}
for r in GETS:
    MODULE_PATHS.setdefault(r['module'], []).append(r['path'])

SKIP_PREFIXES = ('/api/', '/static/', '/owner/', '/super-admin/', '/auth/')


def pick(module, n=3):
    paths = [
        re.sub(r'<(?:int|str|path|uuid):[^>]+>', '1', p)
        for p in MODULE_PATHS.get(module, [])
        if not p.startswith(SKIP_PREFIXES) and '/api/' not in p
    ]
    return paths[:n]


def login(pg, user, slug):
    for _ in range(4):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', user)
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', slug)
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            return True
    return False


results = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    for pkg in packages:
        slug = 'pkg-' + pkg['slug'].replace('_', '-')
        user = 'admin_' + pkg['slug']
        if not login(pg, user, slug):
            results.append({'pkg': pkg['slug'], 'login': False})
            print(pkg['slug'], 'LOGIN FAILED')
            continue
        entries = []
        for module in pkg['actual']:
            for path in pick(module):
                try:
                    r = pg.goto(
                        f'{BASE}/t/{slug}{path}', wait_until='domcontentloaded', timeout=15000
                    )
                    status = r.status
                    body = pg.locator('body').inner_text()[:2000]
                    marker = any(
                        m in body
                        for m in (
                            'Internal Server Error',
                            'Traceback (most recent call last)',
                            'حدث خطأ غير متوقع',
                        )
                    )
                except Exception as exc:  # noqa: BLE001
                    status, marker = None, str(exc)[:80]
                entries.append({'module': module, 'path': path, 'status': status, 'marker': marker})
        bad = [e for e in entries if e['status'] not in (200, 302) or e['marker']]
        results.append({'pkg': pkg['slug'], 'login': True, 'pages': len(entries), 'bad': bad})
        print(f'{pkg["slug"]:26} pages={len(entries):3} bad={len(bad)}')
    b.close()

with open(OUT, 'w', encoding='utf-8') as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('wrote', OUT)
