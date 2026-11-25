from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(f'{BASE}/auth/login')
    pg.fill('#username', 'audit_reception')
    pg.fill('#password', PASSWORD)
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)
    pg.goto(f'{BASE}/t/full-demo-center/reception/queue/add-patient')
    for name in ('patient_id', 'department_id', 'doctor_id', 'queue_type', 'payment_status'):
        vals = pg.eval_on_selector_all(
            f'select[name="{name}"] option', 'els => els.map(e => [e.value, e.textContent.trim()])'
        )
        print(name, vals[:8])
    b.close()
