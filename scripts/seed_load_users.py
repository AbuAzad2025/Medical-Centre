"""Seed load test users — standalone (no pytest fixtures)."""

import sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.extensions import db
from app_factory import create_app

app = create_app('testing')

with app.app_context():
    from sqlalchemy import select, text

    # Get or create default tenant
    from app.core.tenant.models import Tenant

    tenant = db.session.execute(select(Tenant).filter_by(slug='medical-center')).scalars().first()
    if not tenant:
        tenant = Tenant(
            slug='medical-center',
            name='medical-center',
            name_ar='المركز الطبي',
            contact_email='admin@mc.local',
            product_profile_code='multi_department_center',
        )
        db.session.add(tenant)
        db.session.commit()
    tid = tenant.id
    print(f'Tenant: {tenant.slug} (id={tid})')

    # Bind tenant context for ORM queries
    db.session.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))

    from models.user import User

    accounts = [
        ('reception', 'reception', 'ValidPass123!'),
        ('doctor', 'doctor', 'ValidPass123!'),
        ('pharmacist', 'pharmacist', 'ValidPass123!'),
        ('manager', 'manager', 'ValidPass123!'),
    ]
    created = 0
    for username, role, password in accounts:
        existing = db.session.execute(select(User).filter_by(username=username)).scalars().first()
        if not existing:
            u = User(
                tenant_id=tid,
                username=username,
                email=f'{username}@load.local',
                full_name=username.title(),
                role=role,
                is_active=True,
            )
            u.set_password(password)
            db.session.add(u)
            created += 1
    db.session.commit()
    print(f'Load users ready (created={created})')
