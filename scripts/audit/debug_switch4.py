import os

from dotenv import load_dotenv
from flask.sessions import TaggedJSONSerializer
from itsdangerous import URLSafeTimedSerializer
from playwright.sync_api import sync_playwright

load_dotenv()
serializer = URLSafeTimedSerializer(
    os.environ['SECRET_KEY'], salt='cookie-session', serializer=TaggedJSONSerializer()
)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto('http://localhost:8000/auth/login')
    pg.fill('#username', 'audit_doctor')
    pg.fill('#password', 'Audit@2026Pass')
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)

    def show(tag):
        cookies = [c for c in pg.context.cookies() if c['name'] == 'session']
        if cookies:
            try:
                print(tag, serializer.loads(cookies[0]['value']))
            except Exception as exc:
                print(tag, 'decode failed', exc)

    show('before')
    pg.goto('http://localhost:8000/t/full-demo-center/set-language/en')
    show('after')
    b.close()
