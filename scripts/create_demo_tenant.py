#!/usr/bin/env python3
"""Create a demo tenant with sample data for buyer evaluation."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.module.models import TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.core.tenant.models import Tenant
from app.extensions import db
from app.shared.enums import TenantStatus
from app_factory import create_app
from models.user import User

app = create_app('development')
with app.app_context():
    # Create demo tenant
    demo = Tenant.query.filter_by(slug='demo').first()
    if not demo:
        demo = Tenant(
            name='Demo Clinic',
            name_ar='عيادة تجريبية',
            slug='demo',
            status=TenantStatus.ACTIVE,
            contact_email='demo@azad.local',
            contact_phone='+968 9000 0000',
        )
        db.session.add(demo)
        db.session.flush()
        print(f'Created demo tenant: {demo.slug} (id={demo.id})')
    else:
        print(f'Demo tenant already exists: {demo.slug} (id={demo.id})')

    tenant_id = demo.id

    # Enable all modules for demo tenant
    for module_name in MODULE_REGISTRY.keys():
        existing = TenantModule.query.filter_by(
            tenant_id=tenant_id, module_name=module_name
        ).first()
        if not existing:
            tm = TenantModule(
                tenant_id=tenant_id,
                module_name=module_name,
                is_active=True,
            )
            db.session.add(tm)
    db.session.commit()
    print(f'Enabled {len(MODULE_REGISTRY)} modules for demo tenant')

    # Create demo users
    demo_users = [
        ('demo_admin', 'admin', 'مدير العيادة', 'demo_admin@demo.local'),
        ('demo_doctor', 'doctor', 'طبيب', 'demo_doctor@demo.local'),
        ('demo_reception', 'reception', 'موظف استقبال', 'demo_reception@demo.local'),
        ('demo_nurse', 'nurse', 'ممرض', 'demo_nurse@demo.local'),
        ('demo_pharmacist', 'pharmacist', 'صيدلي', 'demo_pharmacist@demo.local'),
        ('demo_lab', 'lab', 'فني مختبر', 'demo_lab@demo.local'),
        ('demo_manager', 'manager', 'مدير', 'demo_manager@demo.local'),
    ]

    for username, role, name, email in demo_users:
        existing = User.query.filter_by(username=username, tenant_id=tenant_id).first()
        if not existing:
            user = User(
                username=username,
                full_name=name,
                email=email,
                role=role,
                tenant_id=tenant_id,
                is_active=True,
            )
            user.set_password('Demo@123')
            db.session.add(user)
            print(f'  Created: {username} ({role})')
        else:
            print(f'  Already exists: {username}')

    db.session.commit()
    print(f'Demo tenant created: {demo.slug} (id={demo.id})')
    print('Login: demo_admin / Demo@123')
