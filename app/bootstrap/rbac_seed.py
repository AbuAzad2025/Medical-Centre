"""RBAC seeding, extracted from the application factory.

create_app used to inline the permission catalogue, the role catalogue and the
role-to-permission grants. That made the catalogue a side effect of building the
app, which the test harness could not reach: conftest migrates the test schema
*after* create_app returns, so on every test run create_app found no
`permissions` table, skipped the whole block, and the test database was left
with no role grants at all. Every route behind
``AccessControlService.require_permission`` then answered 403.

Keeping it here lets both callers run it: create_app at startup, and the test
bootstrap once the schema exists.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

logger = logging.getLogger(__name__)


def seed_rbac_and_catalogs(db, *, inspector=None) -> dict[str, Any]:
    """Seed permissions, roles and the role grants. Safe to call repeatedly.

    ``db`` is the SQLAlchemy instance. Returns what it did, so a caller can
    assert on it rather than discovering the outcome through a 403 later.
    """
    insp = inspector or sa_inspect(db.engine)
    result: dict[str, Any] = {'granted': False}

    if not (insp.has_table('permissions') and insp.has_table('roles')):
        result['skipped'] = 'permissions/roles tables absent'
        return result

    from models.permissions import (
        Permission,
        Role,
        RolePermission,
        assign_super_admin_permissions,
        create_default_permissions,
        create_default_roles,
    )

    create_default_permissions()
    create_default_roles()
    assign_super_admin_permissions()

    from flask import g

    _assign_counts: dict[str, int] = {}

    def _assign(role_name: str, perm_names: list[str]) -> int:
        role_obj = db.session.execute(select(Role).filter_by(name=role_name)).scalars().first()
        if not role_obj:
            return 0
        # role_permissions is one of the six RBAC definition tables: deliberately
        # unfiltered at the ORM layer so every tenant resolves the same
        # catalogue, but its RLS policy still requires the row to name the
        # platform tenant. Being exempt from auto-assign, the grant must set
        # tenant_id itself or the WITH CHECK clause rejects it.
        grant_tenant_id = getattr(g, 'tenant_id', None)
        added = 0
        for pname in perm_names:
            p = db.session.execute(select(Permission).filter_by(name=pname)).scalars().first()
            if not p:
                continue
            exists = (
                db.session.execute(
                    select(RolePermission).filter_by(role_id=role_obj.id, permission_id=p.id)
                )
                .scalars()
                .first()
            )
            if exists:
                continue
            db.session.add(
                RolePermission(
                    role_id=role_obj.id,
                    permission_id=p.id,
                    tenant_id=grant_tenant_id,
                )
            )
            added += 1
        _assign_counts[role_name] = _assign_counts.get(role_name, 0) + added
        return added

    _assign(
        'admin',
        [
            'user_read',
            'user_update',
            'user_create',
            'user_manage_roles',
            'system_settings',
            'system_logs',
            'system_monitoring',
            'reports_view',
            'reports_create',
            'reports_export',
            'queue_settings_manage',
            'admin.access',
        ],
    )
    _assign(
        'manager',
        [
            'reports_view',
            'reports_create',
            'financial_reports',
            'financial_view',
            'pricing_manage',
            'patient_read',
            'patient_update',
            'queue_settings_manage',
            'finance.view',
        ],
    )
    _assign(
        'reception',
        [
            'patient_create',
            'patient_read',
            'patient_update',
            'medical_records_read',
            'queue_settings_manage',
            'reception.manage',
        ],
    )
    _assign(
        'doctor',
        [
            'medical_records_create',
            'medical_records_read',
            'medical_records_update',
            'patient_read',
            'doctor.access',
            'finance.view',
        ],
    )
    _assign('nurse', ['patient_read', 'medical_records_read', 'medical_records_update'])
    _assign('lab', ['reports_view', 'medical_records_read'])
    _assign('radiology', ['reports_view', 'medical_records_read'])
    _assign(
        'emergency',
        ['patient_create', 'patient_update', 'patient_read', 'medical_records_create'],
    )
    _assign(
        'accountant',
        [
            'financial_view',
            'financial_manage',
            'financial_reports',
            'financial_export',
            'pricing_manage',
        ],
    )
    _assign(
        'pharmacist',
        ['medical_records_read', 'reports_view', 'pharmacy.manage'],
    )

    db.session.commit()
    result['granted'] = True
    result['grants'] = sum(_assign_counts.values())
    return result
