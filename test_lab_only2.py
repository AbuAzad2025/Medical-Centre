"""Test lab dashboard only - write to file"""
import os, re
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

results = []

with app.test_client() as client:
    r = client.get('/auth/login')
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode()).group(1)
    
    r2 = client.post('/auth/login', data={
        'csrf_token': csrf,
        'username': 'lab1',
        'password': 'lab123',
    }, follow_redirects=False)
    
    results.append(f'Login status: {r2.status_code}')
    results.append(f'Login redirect: {r2.headers.get("Location")}')
    
    r3 = client.get('/lab/dashboard', follow_redirects=False)
    results.append(f'Dashboard status: {r3.status_code}')
    
    if r3.status_code == 500:
        err = r3.data.decode()[:2000].replace('\n', ' ')
        results.append(f'ERROR: {err}')
    elif r3.status_code in (301, 302):
        loc = r3.headers.get('Location')
        results.append(f'Redirect to: {loc}')
        r4 = client.get(loc, follow_redirects=False)
        results.append(f'Follow redirect status: {r4.status_code}')

with open('lab_only_results.txt', 'w', encoding='utf-8') as f:
    for r in results:
        f.write(r + '\n')

for r in results:
    print(r)
