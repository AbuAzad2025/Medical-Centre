import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from sqlalchemy import text
from app_factory import create_app
from app.extensions import db

app = create_app('testing')
with app.app_context():
    rows = db.session.execute(text('''
        SELECT username, role, tenant_id
        FROM users
        WHERE is_active = true AND role IN (
            'super_admin','admin','manager','reception','doctor',
            'nurse','lab','radiology','pharmacist','accountant',
            'emergency','technician'
        )
        ORDER BY role, username
    ''')).fetchall()
    print(f'{len(rows)} active staff accounts:')
    print(f'  USERNAME             ROLE           TENANT_ID')
    print('  ' + '-' * 50)
    for u in rows:
        tid = str(u[2]) if u[2] else '-'
        print(f'  {u[0]:<20s} {u[1]:<14s} {tid:>9s}')
