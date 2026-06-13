"""Simple HTTP test for all roles"""
import requests, re

BASE = 'http://127.0.0.1:8080'

users = [
    ('admin', 'admin123', 'Admin'),
    ('manager', 'manager123', 'Manager'),
    ('superadmin', 'super123', 'Super Admin'),
    ('doctor1', 'doctor123', 'Doctor'),
    ('nurse1', 'nurse123', 'Nurse'),
    ('reception1', 'reception123', 'Reception'),
    ('emergency1', 'emergency123', 'Emergency'),
    ('radiology1', 'radiology123', 'Radiology'),
    ('lab1', 'lab123', 'Lab'),
    ('accountant1', 'accountant123', 'Accountant'),
    ('pharmacist1', 'pharmacy123', 'Pharmacist'),
]

results = []

for username, password, role in users:
    session = requests.Session()
    try:
        r = session.get(f'{BASE}/auth/login', timeout=15)
        csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
        
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
            'remember': '1'
        }, allow_redirects=True, timeout=15)
        
        status = r2.status_code
        url = r2.url
        has_login_error = 'اسم المستخدم أو كلمة المرور غير صحيحة' in r2.text
        
        if has_login_error:
            results.append(f"{role}: LOGIN FAILED")
        elif status == 200 and '/auth/login' not in url:
            results.append(f"{role}: OK ({status}) at {url}")
        elif status == 500:
            results.append(f"{role}: SERVER ERROR 500 at {url}")
        else:
            results.append(f"{role}: status={status} url={url}")
    except Exception as e:
        results.append(f"{role}: EXCEPTION {type(e).__name__}: {e}")

for r in results:
    print(r)
