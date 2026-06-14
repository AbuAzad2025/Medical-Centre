import requests, re

session = requests.Session()

# 1. Get login page
r = session.get('http://127.0.0.1:8080/auth/login', timeout=10)
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
csrf = m.group(1) if m else ''

# 2. Login
r2 = session.post('http://127.0.0.1:8080/auth/login', data={
    'csrf_token': csrf,
    'username': 'admin',
    'password': 'admin123'
}, allow_redirects=True, timeout=10)
print('After login URL:', r2.url)

# 3. Try owner dashboard
r3 = session.get('http://127.0.0.1:8080/owner/dashboard', timeout=10)
print('Owner status:', r3.status_code)
print('Owner URL:', r3.url)
if 'error' in r3.text.lower() or 'تعذر' in r3.text:
    print('ERROR FOUND in page')
    print(r3.text[:800])
else:
    print('Page loaded OK, length:', len(r3.text))
