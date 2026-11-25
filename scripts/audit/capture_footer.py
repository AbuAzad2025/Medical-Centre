"""Capture the redesigned footer at desktop and mobile widths."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'
OUT = os.path.join(ROOT, 'docs', 'PAGE_AUDIT', 'visual_recheck')

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for label, viewport in (
        ('footer_desktop', {'width': 1280, 'height': 900}),
        ('footer_mobile', {'width': 390, 'height': 844}),
    ):
        pg = b.new_page(viewport=viewport)
        for _ in range(5):
            pg.goto(f'{BASE}/auth/login', wait_until='domcontentloaded')
            pg.fill('#username', 'audit_doctor')
            pg.fill('#password', PASSWORD)
            pg.select_option('#tenant_slug', 'full-demo-center')
            pg.click('button[type=submit]')
            pg.wait_for_timeout(1100)
            if '/auth/login' not in pg.url:
                break
        pg.goto(f'{BASE}/t/full-demo-center/doctor/dashboard', wait_until='domcontentloaded')
        pg.wait_for_timeout(600)
        pg.evaluate("document.querySelector('.luxury-footer').scrollIntoView({block:'center'})")
        pg.wait_for_timeout(500)
        path = os.path.join(OUT, label + '.png')
        if label == 'footer_mobile':
            pg.screenshot(path=path, full_page=True)
        else:
            pg.locator('.luxury-footer').screenshot(path=path)
        print(
            label,
            'columns',
            pg.evaluate(
                "getComputedStyle(document.querySelector('.footer-grid')).gridTemplateColumns"
            ),
        )
        pg.close()
    b.close()
