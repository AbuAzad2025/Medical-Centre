"""Test advanced plan modules accessibility"""
import os, requests, re
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

BASE = 'http://127.0.0.1:8080'

# Test with different users who have appropriate roles
modules = [
    ('nurse1', 'nurse123', '/emar/dashboard', 'eMAR Dashboard'),
    ('doctor1', 'doctor123', '/pathway/pathways', 'Clinical Pathway'),
    ('admin', 'admin123', '/data-warehouse/', 'Data Warehouse'),
    ('radiology1', 'radiology123', '/dicom/studies', 'DICOM Studies'),
    ('admin', 'admin123', '/population-health/dashboard', 'Population Health'),
]

results = []

for username, password, url, name in modules:
    session = requests.Session()
    try:
        r = session.get(f'{BASE}/auth/login', timeout=15)
        csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
        
        r2 = session.post(f'{BASE}/auth/login', data={
            'csrf_token': csrf,
            'username': username,
            'password': password,
        }, allow_redirects=True, timeout=15)
        
        r3 = session.get(f'{BASE}{url}', timeout=15)
        
        if r3.status_code == 200:
            results.append(f"[OK] {name}: HTTP 200")
        elif r3.status_code == 500:
            results.append(f"[FAIL] {name}: Server Error 500")
        elif r3.status_code in (301, 302):
            results.append(f"[REDIRECT] {name}: -> {r3.headers.get('Location')}")
        else:
            results.append(f"[FAIL] {name}: HTTP {r3.status_code}")
    except Exception as e:
        results.append(f"[ERROR] {name}: {type(e).__name__}: {str(e)[:100]}")

for r in results:
    print(r)
