"""Detailed debug of login flow"""
import requests, re

BASE = 'http://127.0.0.1:8080'

def test_login(username, password):
    session = requests.Session()
    
    # Step 1: Get login page
    r = session.get(f'{BASE}/auth/login', timeout=10)
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
    csrf = csrf.group(1) if csrf else ''
    print(f"\n{'='*50}")
    print(f"Testing: {username}")
    print(f"CSRF: {csrf[:30]}...")
    print(f"Session cookies after GET: {dict(session.cookies)}")
    
    # Step 2: Post login WITHOUT following redirects
    r2 = session.post(f'{BASE}/auth/login', data={
        'csrf_token': csrf,
        'username': username,
        'password': password,
    }, allow_redirects=False, timeout=10)
    
    print(f"POST status: {r2.status_code}")
    print(f"Location header: {r2.headers.get('Location', 'none')}")
    print(f"Set-Cookie: {'session' in str(r2.headers.get('Set-Cookie', ''))}")
    print(f"Session cookies after POST: {dict(session.cookies)}")
    
    # Step 3: Follow redirect manually
    if r2.status_code in (301, 302, 303, 307, 308):
        loc = r2.headers['Location']
        print(f"\nFollowing redirect to: {loc}")
        r3 = session.get(f'{BASE}{loc}' if loc.startswith('/') else loc, allow_redirects=False, timeout=10)
        print(f"GET {loc} status: {r3.status_code}")
        print(f"Session cookies after redirect: {dict(session.cookies)}")
        if r3.status_code in (301, 302):
            print(f"Another redirect to: {r3.headers.get('Location', 'none')}")
        if r3.status_code == 200:
            print(f"Final page has 'login' text: {'اسم المستخدم' in r3.text}")
            print(f"Final page has error text: {'حدث خطأ' in r3.text or 'تعذر' in r3.text}")
            print(f"Final page length: {len(r3.text)}")
    
    # Step 4: Try to access a protected page
    r4 = session.get(f'{BASE}/dashboard', allow_redirects=False, timeout=10)
    print(f"\nGET /dashboard status: {r4.status_code}")
    if r4.status_code in (301, 302):
        print(f"  -> redirect to: {r4.headers.get('Location', 'none')}")
    
    return session

# Test specific users
for u, p in [('manager', 'manager123'), ('admin', 'admin123')]:
    test_login(u, p)
