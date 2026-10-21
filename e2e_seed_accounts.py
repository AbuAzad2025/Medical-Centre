"""Create the accounts the E2E suite logs in with.

The specs expect a reception, a doctor and a pharmacist account. They are
created here against the running application's database, inside the tenant the
application bootstraps, so the suite has something real to log in as.
"""

import os
import sys

os.environ.setdefault(
    'DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test'
)
os.environ.setdefault('DEV_DATABASE_URL', os.environ['DATABASE_URL'])
os.environ.setdefault('SECRET_KEY', 'e2e-local-secret-key-at-least-32-chars-long')

from app.core.tenant.models import Tenant  # noqa: E402
from app.extensions import db  # noqa: E402
from app_factory import create_app  # noqa: E402
from models.user import User  # noqa: E402

PASSWORD = 'ValidPass123!'
ACCOUNTS = [
    ('reception_e2e', 'reception'),
    ('doctor_e2e', 'doctor'),
    ('pharmacist_test', 'pharmacist'),
]
MODULES = [
    'reception',
    'doctor',
    'pharmacy',
    'lab',
    'radiology',
    'emergency',
    'accounting',
    'manager',
    'admin',
    'nursing',
]


def main() -> int:
    app = create_app()
    with app.app_context():
        from app.core.tenant.middleware import bound_tenant_scope

        # A clinical account belongs to a clinical tenant, not to the platform
        # tenant the bootstrap creates first. The slug is the one the suite's
        # own fixtures use.
        tenant = (
            db.session.execute(db.select(Tenant).filter_by(slug='pharmacy-shifa')).scalars().first()
        )
        if tenant is None:
            tenant = (
                db.session.execute(
                    db.select(Tenant).filter(Tenant.slug != 'platform').order_by(Tenant.id)
                )
                .scalars()
                .first()
            )
        if tenant is None:
            print('FATAL: no clinical tenant exists in the database')
            return 1
        print(f'tenant: {tenant.slug} (id={tenant.id})')

        # `users` carries a WITH CHECK policy, so the row has to be written
        # while the tenant it names is the bound one.
        created = 0
        with bound_tenant_scope(tenant):
            for username, role in ACCOUNTS:
                user = (
                    db.session.execute(db.select(User).filter_by(username=username))
                    .scalars()
                    .first()
                )
                if user is None:
                    user = User(
                        username=username,
                        email=f'{username}@e2e.local',
                        full_name=username.replace('_', ' ').title(),
                        role=role,
                        is_active=True,
                        tenant_id=tenant.id,
                    )
                    user.set_password(PASSWORD)
                    db.session.add(user)
                    created += 1
                else:
                    user.role = role
                    user.is_active = True
                    user.set_password(PASSWORD)
                print(f'  {username} ({role}) ready')
            db.session.commit()

        # The module guards are per tenant, and a tenant with no modules
        # activated answers 403 for every clinical route. The accounts exist but
        # cannot reach anything without them.
        from tests.tenant_context import activate_tenant_modules

        with bound_tenant_scope(tenant):
            activate_tenant_modules(app, tenant, MODULES)
        print(f'  modules activated: {", ".join(MODULES)}')

        # Clear the failed login attempts. The lockout counts them, so a handful
        # of harness runs - each one a login that could not find the account -
        # locks the account out for 15 minutes and every later run fails with
        # "too many attempts" instead of the real reason.
        try:
            from models.audit_trail import LoginAttempt

            cleared = (
                db.session.execute(
                    db.delete(LoginAttempt).filter(
                        db.or_(
                            *[LoginAttempt.username == u for u, _ in ACCOUNTS],
                        )
                    )
                ).rowcount
                or 0
            )
            db.session.commit()
            print(f'  cleared {cleared} failed login attempt(s)')
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            print(f'  could not clear failed login attempts: {exc}')

        print(f'created {created} account(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
