"""Walk every /portal page as the real patient account created via booking."""

import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
SHOT_DIR = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'screenshots', 'patient')

with open(os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'inventory.json'), encoding='utf-8') as fh:
    routes = [r for r in json.load(fh)['routes'] if r['is_get'] and r['path'].startswith('/portal')]

results = []
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
    pg.fill('#username', 'patient_0501112233')
    pg.fill('#password', PASSWORD)
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1500)
    print('LOGIN', pg.url)
    os.makedirs(SHOT_DIR, exist_ok=True)
    for i, r in enumerate(routes, 1):
        path = re.sub(r'<(?:int|str|path|uuid):[^>]+>', '1', r['path'])
        url = f'{BASE}/t/full-demo-center{path}'
        try:
            resp = pg.goto(url, wait_until='domcontentloaded', timeout=15000)
            status = resp.status if resp else None
            pg.wait_for_timeout(100)
            title = pg.title()
            pg.screenshot(
                path=os.path.join(
                    SHOT_DIR, f'{i:03d}_{re.sub(r"[^A-Za-z0-9_-]+", "_", path).strip("_")}.png'
                )
            )
        except Exception as exc:  # noqa: BLE001
            status, title = str(exc)[:100], ''
        results.append({'path': path, 'status': status, 'title': title, 'final_url': pg.url})
        print(f'  {status} {path}')

with open(
    os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'portal_results.json'), 'w', encoding='utf-8'
) as fh:
    json.dump(results, fh, ensure_ascii=False, indent=2)
    fh.write('\n')
print('done', len(results))
