from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 800})
    pg.goto('http://localhost:8000/auth/login')
    pg.fill('#username', 'patient_0501112233')
    pg.fill('#password', 'Audit@2026Pass')
    pg.select_option('#tenant_slug', 'full-demo-center')
    pg.click('button[type=submit]')
    pg.wait_for_timeout(1200)
    pg.goto('http://localhost:8000/t/full-demo-center/portal/dashboard')
    btn = pg.locator('a.btn-primary').first
    print('count', pg.locator('a.btn-primary').count())
    print('text', btn.inner_text())
    print('outer', btn.evaluate('e => e.outerHTML'))
    print('color', btn.evaluate('e => getComputedStyle(e).color'))
    print('bg', btn.evaluate('e => getComputedStyle(e).backgroundColor'))
    print('font', btn.evaluate('e => getComputedStyle(e).fontFamily'))
    btn.screenshot(path='docs/PAGE_AUDIT/screenshots/patient/button_probe.png')
    b.close()
