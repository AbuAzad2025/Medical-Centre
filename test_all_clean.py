"""Test each dashboard - clean output"""
import os, re, sys
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

users = [
    ('admin', 'admin123', 'Admin', '/manager/dashboard'),
    ('manager', 'manager123', 'Manager', '/manager/dashboard'),
    ('superadmin', 'super123', 'Super Admin', '/super-admin/dashboard'),
    ('doctor1', 'doctor123', 'Doctor', '/doctor/dashboard'),
    ('nurse1', 'nurse123', 'Nurse', '/nurse/dashboard'),
    ('reception1', 'reception123', 'Reception', '/reception/dashboard'),
    ('emergency1', 'emergency123', 'Emergency', '/emergency/dashboard'),
    ('radiology1', 'radiology123', 'Radiology', '/radiology/dashboard'),
    ('lab1', 'lab123', 'Lab', '/lab/dashboard'),
    ('accountant1', 'accountant123', 'Accountant', '/accountant/dashboard'),
    ('pharmacist1', 'pharmacy123', 'Pharmacist', '/medication/dashboard'),
]

with app.test_client() as client:
    for username, password, role_name, dashboard_url in users:
        try:
            r = client.get('/auth/login')
            csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode()).group(1)
            
            client.post('/auth/login', data={
                'csrf_token': csrf,
                'username': username,
                'password': password,
            }, follow_redirects=False)
            
            r3 = client.get(dashboard_url, follow_redirects=False)
            
            if r3.status_code == 200:
                print(f"{role_name}: OK (200)")
            elif r3.status_code == 500:
                err = r3.data.decode()[:200]
                print(f"{role_name}: ERROR 500 - {err}")
            elif r3.status_code in (301, 302):
                loc = r3.headers.get('Location', 'none')
                r4 = client.get(loc, follow_redirects=False)
                print(f"{role_name}: REDIRECT {r3.status_code} -> {loc} -> {r4.status_code}")
            else:
                print(f"{role_name}: {r3.status_code}")
        except Exception as e:
            print(f"{role_name}: EXCEPTION {type(e).__name__}: {str(e)[:200]}")
