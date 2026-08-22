#!/usr/bin/env python3
"""Seed role accounts used by the load-test suite (idempotent).

Creates one user per simulated role under the default test tenant so
locustfile.py can log in as reception/doctor/pharmacist/manager.

Usage:
    python scripts/seed_load_users.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app_factory import create_app  # noqa: E402


ROLES = {
    'reception': 'reception',
    'doctor': 'doctor',
    'pharmacist': 'pharmacist',
    'manager': 'manager',
}
PASSWORD = 'ValidPass123!'


def main() -> int:
    app = create_app('testing')
    with app.app_context():
        from sqlalchemy import select

        from app.extensions import db
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)

        from models.user import User

        created = 0
        for username, role in ROLES.items():
            existing = (
                db.session.execute(select(User).filter_by(username=username)).scalars().first()
            )
            if existing:
                existing.role = role
                existing.is_active = True
                continue
            u = User(
                tenant_id=tenant.id,
                username=username,
                email=f'{username}@load.local',
                full_name=f'Load {role.title()}',
                role=role,
                is_active=True,
            )
            u.set_password(PASSWORD)
            db.session.add(u)
            created += 1
        db.session.commit()
        print(f'load users ready (created={created}, tenant={tenant.slug})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
