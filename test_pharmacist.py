"""Debug pharmacist login"""
import requests, re

BASE = 'http://127.0.0.1:8080'

session = requests.Session()

r = session.get(f'{BASE}/auth/login')
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)

r2 = session.post(f'{BASE}/auth/login', data={
    'csrf_token': csrf,
    'username': 'pharmacist1',
    'password': 'pharmacy123',
    'remember': '1'
}, allow_redirects=False)

print('POST status:', r2.status_code)
print('Location:', r2.headers.get('Location', 'none'))

if r2.status_code in (301, 302):
    loc = r2.headers['Location']
    r3 = session.get(f'{BASE}{loc}', allow_redirects=False)
    print(f'GET {loc} status:', r3.status_code)
    if r3.status_code in (301, 302):
        print(f'  -> redirect to:', r3.headers.get('Location'))
    elif r3.status_code == 200:
        print(f'  Has login form:', 'اسم المستخدم' in r3.text)
        print(f'  Has error:', 'غير مصرح' in r3.text or 'ليس لديك' in r3.text)
