"""Debug login for each user"""
import requests, re

BASE = 'http://127.0.0.1:8080'

users = [
    ('admin', 'admin123', 'Admin'),
    ('manager', 'manager123', 'Manager'),
    ('superadmin', 'super123', 'Super Admin'),
    ('doctor1', 'doctor123', 'Doctor'),
    ('reception1', 'reception123', 'Reception'),
    ('pharmacist1', 'pharmacy123', 'Pharmacist'),
]

for username, password, role in users:
    session = requests.Session()
    try:
        r = session.get(f'{BASE}/auth/login', timeout=10)
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        csrf = m.group(1) if m else ''
        
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
        }, allow_redirects=True, timeout=10)
        
        print(f"\n{role} ({username}):")
        print(f"  Final URL: {r2.url}")
        print(f"  Status: {r2.status_code}")
        print(f"  Has error text: {'اسم المستخدم' in r2.text}")
        print(f"  Text length: {len(r2.text)}")
        
        # Look for redirect chain
        if r2.history:
            print(f"  Redirect chain: {[h.url for h in r2.history]}")
            
    except Exception as e:
        print(f"\n{role} ({username}): ERROR: {e}")
