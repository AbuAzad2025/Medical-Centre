"""Capture an English-mode dashboard as evidence for the translation work."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'visual_recheck', 'english_dashboard.png')

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.goto(f'{BASE}/auth/login')
    pg.fill('#username', 'audit_doctor')
    pg.fill('#password', PASSWORD)
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)
    pg.goto(f'{BASE}/t/full-demo-center/doctor/dashboard', wait_until='domcontentloaded')
    pg.click('button[title="تغيير اللغة / Language"]')
    pg.wait_for_timeout(250)
    pg.click('a[href$="/set-language/en"]')
    pg.wait_for_timeout(500)
    print('lang', pg.evaluate('document.documentElement.lang'))
    print('body', pg.locator('body').inner_text()[:180].replace('\n', ' / '))
    pg.screenshot(path=OUT)
    b.close()
