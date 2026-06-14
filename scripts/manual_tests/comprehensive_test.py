"""Comprehensive system test - login as every role and test dashboards"""
import requests, re, sys

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

errors = []
success = []

def test_user(username, password, role_name):
    session = requests.Session()
    try:
        # Get login page
        r = session.get(f'{BASE}/auth/login', timeout=15)
        if r.status_code != 200:
            errors.append(f"[{role_name}] GET login failed: {r.status_code}")
            return
        
        # Extract CSRF
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        csrf = m.group(1) if m else ''
        
        # Login
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
            'remember': '1'
        }, allow_redirects=True, timeout=15)
        
        # Check if still on login page (failure)
        if '/auth/login' in r2.url or 'اسم المستخدم أو كلمة المرور غير صحيحة' in r2.text:
            errors.append(f"[{role_name}] LOGIN FAILED for {username}")
            return
        
        # Check for dashboard error
        if 'حدث خطأ' in r2.text or 'تعذر' in r2.text or 'Internal Server Error' in r2.text:
            errors.append(f"[{role_name}] DASHBOARD ERROR for {username} at {r2.url}")
            return
        
        success.append(f"[{role_name}] OK - {username} -> {r2.url}")
        
        # Test owner dashboard if super_admin
        if role_name == 'Super Admin':
            r3 = session.get(f'{BASE}/owner/dashboard', timeout=15)
            if r3.status_code != 200 or 'تعذر' in r3.text:
                errors.append(f"[{role_name}] owner/dashboard failed: {r3.status_code}")
            else:
                success.append(f"[{role_name}] owner/dashboard OK")
        
        # Test super-admin dashboard
        if role_name in ['Super Admin', 'Admin']:
            r3 = session.get(f'{BASE}/super-admin/dashboard', timeout=15)
            if r3.status_code != 200 or 'تعذر' in r3.text:
                errors.append(f"[{role_name}] super-admin/dashboard failed: {r3.status_code}")
            else:
                success.append(f"[{role_name}] super-admin/dashboard OK")
        
        # Test manager dashboard
        if role_name in ['Manager', 'Admin']:
            r3 = session.get(f'{BASE}/manager/dashboard', timeout=15)
            if r3.status_code != 200 or 'تعذر' in r3.text:
                errors.append(f"[{role_name}] manager/dashboard failed: {r3.status_code}")
            else:
                success.append(f"[{role_name}] manager/dashboard OK")
        
        # Test specific role dashboards
        role_urls = {
            'Doctor': '/doctor/dashboard',
            'Nurse': '/nurse/dashboard',
            'Reception': '/reception/dashboard',
            'Emergency': '/emergency/dashboard',
            'Radiology': '/radiology/dashboard',
            'Lab': '/lab/dashboard',
            'Accountant': '/accountant/dashboard',
            'Pharmacist': '/medication/dashboard',
        }
        
        if role_name in role_urls:
            url = role_urls[role_name]
            r3 = session.get(f'{BASE}{url}', timeout=15)
            if r3.status_code != 200 or 'تعذر' in r3.text or 'حدث خطأ' in r3.text:
                errors.append(f"[{role_name}] {url} failed: {r3.status_code}")
            else:
                success.append(f"[{role_name}] {url} OK")
        
    except Exception as e:
        errors.append(f"[{role_name}] EXCEPTION: {type(e).__name__}: {e}")

print("=" * 60)
print("COMPREHENSIVE SYSTEM TEST")
print("=" * 60)

for username, password, role_name in users:
    print(f"\nTesting {role_name} ({username})...")
    test_user(username, password, role_name)

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
print(f"Success: {len(success)}")
print(f"Errors: {len(errors)}")

if errors:
    print("\n--- ERRORS ---")
    for e in errors:
        print(e)

if success:
    print("\n--- SUCCESS ---")
    for s in success:
        print(s)

# Save report
with open('TEST_REPORT.txt', 'w', encoding='utf-8') as f:
    f.write("COMPREHENSIVE SYSTEM TEST REPORT\n")
    f.write("=" * 60 + "\n")
    f.write(f"Success: {len(success)}\n")
    f.write(f"Errors: {len(errors)}\n\n")
    if errors:
        f.write("ERRORS:\n")
        for e in errors:
            f.write(f"  {e}\n")
    f.write("\nSUCCESS:\n")
    for s in success:
        f.write(f"  {s}\n")

print(f"\nReport saved to TEST_REPORT.txt")
