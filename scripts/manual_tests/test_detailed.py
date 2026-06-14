"""Detailed test to see actual status codes and error messages"""
import requests, re

BASE = 'http://127.0.0.1:8080'

def test_user(username, password, role_name):
    session = requests.Session()
    try:
        r = session.get(f'{BASE}/auth/login', timeout=15)
        csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
        
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
        }, allow_redirects=True, timeout=15)
        
        print(f"\n{'='*50}")
        print(f"{role_name} ({username}):")
        print(f"  Final URL: {r2.url}")
        print(f"  Status: {r2.status_code}")
        print(f"  Has 'login error': {'اسم المستخدم أو كلمة المرور غير صحيحة' in r2.text}")
        print(f"  Has 'dashboard error': {'حدث خطأ في تحميل لوحة التحكم' in r2.text or 'تعذر تنفيذ' in r2.text}")
        print(f"  Text length: {len(r2.text)}")
        
        # If it's a dashboard error, show the first part of the HTML
        if r2.status_code == 500:
            print(f"  500 Response preview: {r2.text[:500]}")
        elif 'حدث خطأ في تحميل لوحة التحكم' in r2.text:
            print(f"  Dashboard error found in HTML")
            
    except Exception as e:
        print(f"\n{role_name} ({username}): EXCEPTION: {type(e).__name__}: {e}")

for u, p, r in [
    ('admin', 'admin123', 'Admin'),
    ('manager', 'manager123', 'Manager'),
    ('superadmin', 'super123', 'Super Admin'),
    ('pharmacist1', 'pharmacy123', 'Pharmacist'),
]:
    test_user(u, p, r)
