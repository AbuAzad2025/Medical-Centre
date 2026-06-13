"""Continuous system test - runs indefinitely testing all roles"""
import requests, re, time, sys
from datetime import datetime

BASE = 'http://127.0.0.1:8080'
INTERVAL = 60  # seconds between test cycles

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
            return False, f"Server error 500"
        
        if r2.status_code != 200:
            return False, f"Status {r2.status_code}"
        
        return True, "OK"
        
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"

cycle = 0
print("=" * 60)
print("CONTINUOUS SYSTEM TEST")
print("Tests all 11 roles every 60 seconds")
print("Press Ctrl+C to stop")
print("=" * 60)

try:
    while True:
        cycle += 1
        print(f"\n--- Cycle {cycle} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        all_ok = True
        for username, password, role_name in users:
            success, msg = test_user(username, password, role_name)
            status = "OK" if success else "FAIL"
            if not success:
                all_ok = False
            print(f"  [{status}] {role_name:12s} | {msg}")
        
        if all_ok:
            print(f"  ALL PASS ({len(users)}/{len(users)})")
        else:
            print(f"  SOME FAILED")
        
        with open('CONTINUOUS_TEST_LOG.txt', 'a', encoding='utf-8') as f:
            f.write(f"Cycle {cycle} at {datetime.now()}: {'ALL PASS' if all_ok else 'SOME FAILED'}\n")
        
        time.sleep(INTERVAL)
        
except KeyboardInterrupt:
    print("\n\nStopped by user.")
    print(f"Total cycles completed: {cycle}")
