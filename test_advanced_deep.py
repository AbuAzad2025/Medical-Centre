"""Deep test of all advanced module routes"""
import os, requests, re
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
BASE = 'http://127.0.0.1:8080'

def login(session, username, password):
    r = session.get(f'{BASE}/auth/login', timeout=15)
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.text).group(1)
    session.post(f'{BASE}/auth/login', data={'csrf_token': csrf, 'username': username, 'password': password}, allow_redirects=True, timeout=15)

routes = [
    ('nurse1', 'nurse123', '/emar/dashboard', 'eMAR Dashboard'),
    ('nurse1', 'nurse123', '/emar/patient/1', 'eMAR Patient MAR'),
    ('doctor1', 'doctor123', '/pathway/pathways', 'Pathway List'),
    ('doctor1', 'doctor123', '/pathway/pathway/1', 'Pathway Detail'),
    ('doctor1', 'doctor123', '/pathway/patient/1/care-plans', 'Patient Care Plans'),
    ('admin', 'admin123', '/data-warehouse/', 'DW Dashboard'),
    ('radiology1', 'radiology123', '/dicom/studies', 'DICOM Studies'),
    ('radiology1', 'radiology123', '/dicom/study/1', 'DICOM Study Detail'),
    ('radiology1', 'radiology123', '/dicom/viewer/1', 'DICOM Viewer'),
    ('admin', 'admin123', '/population-health/dashboard', 'Pop Health Dashboard'),
    ('admin', 'admin123', '/population-health/disease-registry', 'Disease Registry'),
    ('admin', 'admin123', '/population-health/quality-measures', 'Quality Measures'),
]

results = []
for username, password, url, name in routes:
    session = requests.Session()
    try:
        login(session, username, password)
        r = session.get(f'{BASE}{url}', timeout=15)
        if r.status_code == 200:
            results.append(f"[OK] {name}: HTTP 200")
        elif r.status_code == 404:
            results.append(f"[INFO] {name}: HTTP 404 (no data yet)")
        elif r.status_code == 403:
            results.append(f"[FAIL] {name}: HTTP 403 (permission)")
        else:
            results.append(f"[FAIL] {name}: HTTP {r.status_code}")
    except Exception as e:
        results.append(f"[ERROR] {name}: {type(e).__name__}: {str(e)[:80]}")

for r in results:
    print(r)
