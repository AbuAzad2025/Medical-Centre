#!/usr/bin/env python3
"""Create demo tenants for live showcase: standalone_pharmacy and hospital."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault('APP_ENV', 'production')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:123@127.0.0.1:5432/medical_system')
os.environ.setdefault('SECRET_KEY', 'demo-secret')

from app.core.module.models import TenantModule
from app.core.tenant.models import Tenant, get_bundle_for_profile
from app.extensions import db
from app_factory import create_app

app = create_app('production')

DEMO_TENANTS = [
    {
        'slug': 'demo-pharmacy',
        'name': 'صيدلية الدواء الشافي - عرض',
        'contact_email': 'demo-pharmacy@medical.system',
        'profile': 'standalone_pharmacy',
    },
    {
        'slug': 'demo-hospital',
        'name': 'مستشفى الشفاء العام - عرض',
        'contact_email': 'demo-hospital@medical.system',
        'profile': 'hospital',
    },
]


def ensure_demo_tenant(slug, name, email, profile):
    tenant = db.session.execute(db.select(Tenant).filter_by(slug=slug)).scalars().first()
    if tenant:
        print(f'Exists: {slug} ({tenant.product_profile_code})')
        return tenant
    bundle = get_bundle_for_profile(profile)
    tenant = Tenant(
        slug=slug, name=name, contact_email=email, status='active', product_profile_code=profile
    )
    db.session.add(tenant)
    db.session.flush()
    modules = bundle.get_modules() if bundle else []
    for mod in modules:
        db.session.add(TenantModule(tenant_id=tenant.id, module_name=mod, is_active=True))
    db.session.commit()
    print(f'Created: {slug} -> {profile} with modules {modules}')
    return tenant


with app.app_context():
    for cfg in DEMO_TENANTS:
        t = ensure_demo_tenant(cfg['slug'], cfg['name'], cfg['contact_email'], cfg['profile'])
        print(
            f'Tenant {t.slug}: id={t.id}, modules={len(db.session.execute(db.select(TenantModule).filter_by(tenant_id=t.id)).scalars().all())}'
        )

    print('Demo tenants ready for live showcase')
