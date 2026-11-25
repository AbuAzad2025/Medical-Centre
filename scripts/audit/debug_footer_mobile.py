from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = 'Audit@2026Pass'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 390, 'height': 844})
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
    print(pg.evaluate(
        """() => { const f=document.querySelector('.luxury-footer'); const r=f.getBoundingClientRect();
          const sb=document.querySelector('.clinical-sidebar');
          return {box:[r.x,r.y,r.width,r.height], display:getComputedStyle(f).display,
            sidebarDisplay:getComputedStyle(sb).display,
            docScrollWidth:document.documentElement.scrollWidth,
            bodyScrollWidth:document.body.scrollWidth,
            viewport:innerWidth}; }"""
    ))
    b.close()
