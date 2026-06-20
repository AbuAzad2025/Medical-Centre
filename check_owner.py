import sys; sys.path.insert(0, '.')
import os
from dotenv import load_dotenv
load_dotenv()
from app_factory import create_app
from models.user import User

app = create_app()
with app.app_context():
    owner = User.query.filter_by(username='owner').first()
    if owner:
        print(f'Owner found: id={owner.id}, role={owner.role}, is_admin={owner.is_admin}')
        from werkzeug.security import check_password_hash
        pwd = 'Azad@1983@2026@06@20'
        print(f'Password check for "{pwd}": {check_password_hash(owner.password_hash, pwd)}')
    else:
        print('Owner user NOT found! Checking all users...')
        for u in User.query.all():
            print(f'  id={u.id} username={u.username} role={u.role} is_admin={u.is_admin}')
