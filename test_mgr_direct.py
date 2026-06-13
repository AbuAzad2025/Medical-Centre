"""Test manager dashboard directly"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
app = create_app()

with app.app_context():
    from models.user import User
    user = User.query.filter_by(username='manager').first()
    
    # Simulate login
    from flask_login import login_user
    login_user(user)
    
    # Now try to access the dashboard
    with app.test_client() as client:
        # Login first
        r = client.get('/auth/login')
        csrf = r.data.decode()
        import re
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', csrf)
        csrf = m.group(1) if m else ''
        
        r2 = client.post('/auth/login', data={
            'csrf_token': csrf,
            'username': 'manager',
            'password': 'manager123'
        }, follow_redirects=False)
        
        print('Login status:', r2.status_code)
        print('Login cookies:', dict(r2.headers))
        
        # Access manager dashboard
        r3 = client.get('/manager/dashboard', follow_redirects=False)
        print('Dashboard status:', r3.status_code)
        print('Dashboard location:', r3.headers.get('Location', 'none'))
        
        if r3.status_code == 200:
            print('Dashboard loaded OK, length:', len(r3.data))
        elif r3.status_code == 500:
            print('Dashboard ERROR 500')
            print(r3.data.decode()[:1000])
        
        # Check what /dashboard returns
        r4 = client.get('/dashboard', follow_redirects=False)
        print('/dashboard status:', r4.status_code)
        print('/dashboard location:', r4.headers.get('Location', 'none'))
