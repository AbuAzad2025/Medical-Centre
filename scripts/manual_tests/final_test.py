"""Final comprehensive system test - all roles, all dashboards"""
import requests, re, time, sys
from datetime import datetime

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

dashboard_urls = {
    'Admin': '/manager/dashboard',
    'Manager': '/manager/dashboard',
    'Super Admin': '/super-admin/dashboard',
    'Doctor': '/doctor/dashboard',
    'Nurse': '/nurse/dashboard',
    'Reception': '/reception/dashboard',
    'Emergency': '/emergency/dashboard',
    'Radiology': '/radiology/dashboard',
    'Lab': '/lab/dashboard',
    'Accountant': '/accountant/dashboard',
    'Pharmacist': '/medication/dashboard',
}

def test_user(username, password, role_name):
    session = requests.Session()
    try:
        r = session.get(f'{BASE}/auth/login', timeout=15)
        if r.status_code != 200:
            return False, f"GET login failed: {r.status_code}"
        
        csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text)
        csrf = csrf.group(1) if csrf else ''
        
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
            'remember': '1'
        }, allow_redirects=True, timeout=15)
        
        if '/auth/login' in r2.url:
            return False, "Still on login page"
        
        if r2.status_code == 500:
            return False, f"Server error 500 at {r2.url}"
        
        if r2.status_code != 200:
            return False, f"Unexpected status {r2.status_code} at {r2.url}"
        
        return True, f"OK -> {r2.url}"
        
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:100]}"

print("=" * 60)
print("COMPREHENSIVE SYSTEM TEST")
print("=" * 60)
print(f"Started: {datetime.now()}")

all_ok = True
results = []

for username, password, role_name in users:
    success, msg = test_user(username, password, role_name)
    results.append((role_name, success, msg))
    if not success:
        all_ok = False
    print(f"{'[OK]' if success else '[FAIL]'} {role_name:12s} | {msg}")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
success_count = sum(1 for _, s, _ in results if s)
fail_count = len(results) - success_count
print(f"Passed: {success_count}/{len(results)}")
print(f"Failed: {fail_count}/{len(results)}")

if all_ok:
    print("\nALL TESTS PASSED!")
else:
    print("\nSome tests failed.")

with open('FINAL_TEST_REPORT.txt', 'w', encoding='utf-8') as f:
    f.write("COMPREHENSIVE SYSTEM TEST REPORT\n")
    f.write("=" * 60 + "\n")
    f.write(f"Timestamp: {datetime.now()}\n")
    f.write(f"Passed: {success_count}/{len(results)}\n")
    f.write(f"Failed: {fail_count}/{len(results)}\n\n")
    for role, success, msg in results:
        f.write(f"{'[OK]' if success else '[FAIL]'} {role:12s} | {msg}\n")

print("\nReport saved to FINAL_TEST_REPORT.txt")
