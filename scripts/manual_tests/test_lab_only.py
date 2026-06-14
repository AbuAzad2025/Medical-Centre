"""Test lab dashboard only"""
import os, re
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.test_client() as client:
    r = client.get('/auth/login')
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode()).group(1)
    
    r2 = client.post('/auth/login', data={
        'csrf_token': csrf,
        'username': 'lab1',
        'password': 'lab123',
    }, follow_redirects=False)
    
    print('Login status:', r2.status_code)
    print('Login redirect:', r2.headers.get('Location'))
    
    r3 = client.get('/lab/dashboard', follow_redirects=False)
    print('Dashboard status:', r3.status_code)
    
    if r3.status_code == 500:
        print('ERROR:', r3.data.decode()[:2000])
    elif r3.status_code in (301, 302):
        print('Redirect to:', r3.headers.get('Location'))
        r4 = client.get(r3.headers.get('Location'), follow_redirects=False)
        print('Follow redirect status:', r4.status_code)
