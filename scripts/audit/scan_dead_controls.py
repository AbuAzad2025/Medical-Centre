from datetime import datetime

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = f'Azad@1983@{datetime.now():%Y@%m@%d}'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1280, 'height': 900})
    for _ in range(5):
        pg.goto(f'{BASE}/auth/login')
        pg.fill('#username', 'superadmin')
        pg.fill('#password', PASSWORD)
        pg.select_option('#tenant_slug', 'platform')
        pg.click('button[type=submit]')
        pg.wait_for_timeout(1100)
        if '/auth/login' not in pg.url:
            break
    for path in ('/owner/dashboard', '/owner/provision', '/owner/subscriptions'):
        pg.goto(f'{BASE}/t/platform{path}', wait_until='domcontentloaded')
        pg.wait_for_timeout(300)
        found = pg.evaluate(
            """() => {
              const out=[];
              document.querySelectorAll('button, a').forEach(e=>{
                if(e.offsetParent===null && getComputedStyle(e).position!=='fixed') return;
                const txt=(e.innerText||'').trim();
                const aria=e.getAttribute('aria-label'), title=e.getAttribute('title');
                const icon=e.querySelector('i.fas, i.fa, i.bi');
                const href=e.getAttribute('href');
                const onclick=e.getAttribute('onclick')||'';
                if(!txt && !aria && !title && !icon) out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,50), why:'no label'});
                if(href==='#' || (href||'').startsWith('javascript:void')) out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,50), why:'placeholder href '+href});
                if(onclick.includes('_(')) out.push({tag:e.tagName, cls:(e.className||'').toString().slice(0,50), why:'Jinja _ in onclick'});
              });
              return out.slice(0,25);
            }"""
        )
        print(path, 'suspicious', len(found))
        for item in found:
            print('  ', item)
    b.close()
