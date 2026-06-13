import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.app_context():
    from models.user import User
    passwords = {
        'admin': 'admin123',
        'manager': 'manager123',
        'superadmin': 'super123',
        'pharmacist1': 'pharmacy123'
    }
    for u in ['admin', 'manager', 'superadmin', 'pharmacist1']:
        user = User.query.filter_by(username=u).first()
        if user:
            pwd = passwords.get(u, '')
            print(f"{u}: role={user.role}, is_active={user.is_active}, tenant_id={user.tenant_id}")
            print(f"  check_password('{pwd}'): {user.check_password(pwd)}")
        else:
            print(f"{u}: NOT FOUND")
