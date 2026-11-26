from datetime import datetime

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8000'
PASSWORD = f'Azad@1983@{datetime.now():%Y@%m@%d}'

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    for width in (1280, 900):
        pg = b.new_page(viewport={'width': width, 'height': 900})
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
            pg.wait_for_timeout(400)
            print(f'--- {width} {path}')
            print(
                pg.evaluate(
                    """() => {
                  const r=e=>{if(!e)return null;const b=e.getBoundingClientRect();return [Math.round(b.left),Math.round(b.top),Math.round(b.right),Math.round(b.bottom)];};
                  const nav=document.querySelector('.platform-navbar'), aside=document.querySelector('.owner-sidebar, .clinical-sidebar');
                  const fields=Array.from(document.querySelectorAll('input:not([type=hidden]),select,textarea')).slice(0,6)
                    .map(e=>({name:e.name||e.id, bg:getComputedStyle(e).backgroundColor, color:getComputedStyle(e).color}));
                  const tables=Array.from(document.querySelectorAll('table')).slice(0,3).map(t=>({
                    wrap:!!t.closest('.table-responsive'), scrollW:t.scrollWidth,
                    parentW:t.parentElement?t.parentElement.clientWidth:null,
                    actions:Array.from(t.querySelectorAll('button,a.btn')).slice(0,8)
                      .map(x=>({title:x.getAttribute('title'),aria:x.getAttribute('aria-label'),text:(x.innerText||'').trim().slice(0,16)}))
                  }));
                  const dd=Array.from(document.querySelectorAll('.dropdown-menu')).slice(0,4).map(m=>({z:getComputedStyle(m).zIndex, box:r(m)}));
                  return {nav:r(nav), aside:r(aside), docScroll:document.documentElement.scrollWidth, vw:innerWidth,
                          fields, tables, dropdowns:dd};
                }"""
                )
            )
        pg.close()
    b.close()
