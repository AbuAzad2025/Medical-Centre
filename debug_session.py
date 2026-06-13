"""Debug session handling"""
import requests, re

BASE = 'http://127.0.0.1:8080'

session = requests.Session()

# 1. Get login page
r = session.get(f'{BASE}/auth/login', timeout=10)
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
csrf = csrf.group(1) if csrf else ''

print("Cookies after GET login:")
for k, v in session.cookies.items():
    print(f"  {k}={v[:50]}...")

# 2. Login with allow_redirects=False to capture the response
r2 = session.post(f'{BASE}/auth/login', data={
    'csrf_token': csrf,
    'username': 'manager',
    'password': 'manager123',
}, allow_redirects=False, timeout=10)

print(f"\nPOST status: {r2.status_code}")
print(f"Location: {r2.headers.get('Location', 'none')}")

print("\nCookies after POST login:")
for k, v in session.cookies.items():
    print(f"  {k}={v[:50]}...")

# 3. Manually follow redirect
if r2.status_code in (301, 302):
    loc = r2.headers['Location']
    print(f"\nFollowing redirect to: {loc}")
    r3 = session.get(f'{BASE}{loc}' if loc.startswith('/') else loc, allow_redirects=False, timeout=10)
    print(f"GET status: {r3.status_code}")
    
    print("\nCookies after redirect:")
    for k, v in session.cookies.items():
        print(f"  {k}={v[:50]}...")
    
    if r3.status_code in (301, 302):
        print(f"Another redirect to: {r3.headers.get('Location', 'none')}")
        
    # 4. Access /dashboard with the session
    print("\n--- Testing /dashboard ---")
    r4 = session.get(f'{BASE}/dashboard', allow_redirects=False, timeout=10)
    print(f"GET /dashboard status: {r4.status_code}")
    if r4.status_code in (301, 302):
        print(f"  -> redirect to: {r4.headers.get('Location', 'none')}")

# 5. Try a simple test endpoint that shows if user is logged in
print("\n--- Testing /profile ---")
r5 = session.get(f'{BASE}/profile', allow_redirects=False, timeout=10)
print(f"GET /profile status: {r5.status_code}")
if r5.status_code == 200:
    print(f"  Has 'login' text: {'اسم المستخدم' in r5.text}")
