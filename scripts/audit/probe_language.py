"""Check whether the language switch actually changes rendered text."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'


def login(pg):
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
        pg.fill('#username', 'audit_doctor')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1200)
        if '/auth/login' not in pg.url:
            return
    raise RuntimeError('login failed')


with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    login(pg)
    url = f'{BASE}/t/full-demo-center/doctor/dashboard'
    pg.goto(url, wait_until='domcontentloaded')
    print(
        'AR title/text:',
        pg.title(),
        '|',
        pg.locator('body').inner_text()[:160].replace('\n', ' / '),
    )
    links = pg.eval_on_selector_all(
        'a[href*="set-language"]', 'els => els.map(e => e.getAttribute("href"))'
    )
    print('switch links:', links)
    pg.goto(f'{BASE}/t/full-demo-center/set-language/en', wait_until='domcontentloaded')
    print('after switch url:', pg.url)
    pg.goto(url, wait_until='domcontentloaded')
    body = pg.locator('body').inner_text()
    print('EN title/text:', pg.title(), '|', body[:160].replace('\n', ' / '))
    print(
        'session lang ->',
        pg.evaluate('document.documentElement.lang'),
        'dir',
        pg.evaluate('document.documentElement.dir'),
    )
    print('has Arabic after switch:', any('\u0600' <= c <= '\u06ff' for c in body[:400]))
    b.close()
