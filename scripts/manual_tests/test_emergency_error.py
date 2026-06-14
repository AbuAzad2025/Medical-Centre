"""Find exact error in emergency dashboard"""
import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.test_client() as client:
    r = client.get('/auth/login')
    import re
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', r.data.decode()).group(1)
    
    client.post('/auth/login', data={
        'csrf_token': csrf,
        'username': 'emergency1',
        'password': 'emergency123',
    }, follow_redirects=False)
    
    r3 = client.get('/emergency/dashboard', follow_redirects=False)
    print('Status:', r3.status_code)
    if r3.status_code == 500:
        print('ERROR:', r3.data.decode()[:2000])
    elif r3.status_code in (301, 302):
        print('Redirect to:', r3.headers.get('Location'))
