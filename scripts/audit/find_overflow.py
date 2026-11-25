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
    print(
        pg.evaluate(
            """() => {
          const out=[];
          document.querySelectorAll('body *').forEach(e=>{
            const r=e.getBoundingClientRect();
            if(r.right>400 || r.left<-10) out.push({tag:e.tagName,cls:(e.className||'').toString().slice(0,60),left:Math.round(r.left),right:Math.round(r.right),w:Math.round(r.width)});
          });
          return out.slice(0,20);
        }"""
        )
    )
    b.close()
