"""Test manager dashboard using test client"""
import os, re
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.test_client() as client:
    # Get login page
    r = client.get('/auth/login')
    html = r.data.decode()
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    csrf = m.group(1) if m else ''
    
    # Login
    r2 = client.post('/auth/login', data={
        'csrf_token': csrf,
        'username': 'manager',
        'password': 'manager123'
    }, follow_redirects=False)
    
    print('Login status:', r2.status_code)
    print('Login redirect:', r2.headers.get('Location', 'none'))
    
    # Access manager dashboard
    r3 = client.get('/manager/dashboard', follow_redirects=False)
    print('Dashboard status:', r3.status_code)
    print('Dashboard redirect:', r3.headers.get('Location', 'none'))
    
    if r3.status_code == 500:
        print('ERROR 500 body:')
        print(r3.data.decode()[:2000])
    elif r3.status_code == 200:
        print('Dashboard OK, length:', len(r3.data))
        
    # Check /dashboard
    r4 = client.get('/dashboard', follow_redirects=False)
    print('/dashboard status:', r4.status_code)
    print('/dashboard redirect:', r4.headers.get('Location', 'none'))
