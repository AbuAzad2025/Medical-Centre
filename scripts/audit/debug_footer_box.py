from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'audit_doctor')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'full-demo-center')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    pg.goto(f'{BASE}/t/full-demo-center/doctor/dashboard')
    pg.wait_for_timeout(500)
    info = pg.evaluate(
        """() => {
          const f=document.querySelector('.luxury-footer');
          const c=f.querySelector('.container');
          const r=f.getBoundingClientRect();
          return {footer:[r.x,r.width], parent:f.parentElement.tagName+' '+f.parentElement.className,
            container:[c.getBoundingClientRect().x,c.getBoundingClientRect().width],
            body:document.body.scrollWidth, viewport:innerWidth};
        }"""
    )
    print(info)
    b.close()
