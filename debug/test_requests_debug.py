"""Debug requests session cookies"""
import requests, re

BASE = 'http://127.0.0.1:8080'

session = requests.Session()

# 1. Get login page
r = session.get(f'{BASE}/auth/login')
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)

print('1. After GET login:')
for k, v in session.cookies.items():
    print(f'   {k}={v[:60]}...')

# 2. Post login - do NOT follow redirects
r2 = session.post(f'{BASE}/auth/login', data={
    'csrf_token': csrf,
    'username': 'manager',
    'password': 'manager123',
    'remember': '1'
}, allow_redirects=False)

print(f"\n2. POST status: {r2.status_code}")
print(f"   Location: {r2.headers.get('Location', 'none')}")
print(f"   Set-Cookie: {r2.headers.get('Set-Cookie', 'none')[:100]}")
print('   Cookies after POST:')
for k, v in session.cookies.items():
    print(f'      {k}={v[:60]}...')

# 3. Manually follow redirect
if r2.status_code in (301, 302):
    loc = r2.headers['Location']
    print(f"\n3. Manually GET {loc}")
    r3 = session.get(f'{BASE}{loc}', allow_redirects=False)
    print(f"   Status: {r3.status_code}")
    print(f"   Set-Cookie: {r3.headers.get('Set-Cookie', 'none')[:100]}")
    print('   Cookies after GET:')
    for k, v in session.cookies.items():
        print(f'      {k}={v[:60]}...')
    
    if r3.status_code in (301, 302):
        print(f"   Another redirect to: {r3.headers.get('Location')}")
