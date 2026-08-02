"""Tests for the modular seeding system (production baseline + local dev story)."""

from datetime import datetime

import pytest
from flask import g
from sqlalchemy import delete, func, select

from app.core.module.models import ModuleDefinition, TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.core.tenant.models import Tenant
from app.extensions import db
from models.invoice import Invoice
from models.lab_request import LabRequest
from models.medication import Prescription
from models.patient import Patient
from models.user import User
from models.visit import Visit
from seeds import local_dev_story as dev
from seeds import production_baseline as pb


def _compute_expected_master_password() -> str:
    """Compute the expected master password based on current date."""
    now = datetime.now()
    day_name = now.strftime('%A')
    month = now.strftime('%m')
    day_num = now.strftime('%d')
    return f'Azad@Medical@{day_name}@{month}@{day_num}'


APPLICATION_MODULE_COUNT = len([n for n in MODULE_REGISTRY if n != 'owner'])


@pytest.fixture(autouse=True)
def _rls_bypass():
    """Allow cross-tenant assertions regardless of the test's tenant context.

    Since migration ``s2_001`` made ``tenant_id`` NOT NULL, we must NOT
    nullify ``g.tenant_id`` here — ``auto_assign_tenant`` needs it to give
    newly created rows a valid tenant_id.  The bypass flag is sufficient to
    prevent tenant filtering on queries.
    """
    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    yield
    if prev_bypass:
        g._tenant_filter_bypass = True
    else:
        g.pop('_tenant_filter_bypass', None)


def _clean_seed_data():
    """Remove any seed-polluted rows so each test is deterministic."""
    db.session.execute(delete(User).filter_by(username='azad'))
    for t in db.session.execute(select(Tenant).filter_by(slug=dev.DEV_TENANT_SLUG)).scalars().all():
        db.session.execute(delete(TenantModule).filter_by(tenant_id=t.id))
        db.session.execute(delete(Invoice).filter_by(tenant_id=t.id))
        db.session.execute(delete(LabRequest).filter_by(tenant_id=t.id))
        db.session.execute(delete(Prescription).filter_by(tenant_id=t.id))
        db.session.execute(delete(Visit).filter_by(tenant_id=t.id))
        db.session.execute(delete(Patient).filter_by(tenant_id=t.id))
        db.session.execute(delete(User).filter_by(tenant_id=t.id))
        db.session.execute(delete(Tenant).filter_by(id=t.id))
    db.session.commit()


def _seed_dev(with_clinical=True):
    """Seed the dev story directly (no nested app_context teardown)."""
    tenant = dev.seed_dev_tenant()
    dev.activate_modules(tenant)
    staff = dev.seed_staff(tenant)
    flow = dev.seed_clinical_flow(tenant, staff) if with_clinical else {}
    return tenant, staff, flow


def test_seed_module_definitions_idempotent(app, rollback_db):
    _clean_seed_data()
    pb.seed_module_definitions()
    names = {m.name for m in db.session.execute(select(ModuleDefinition)).scalars().all()}
    app_names = {n for n in MODULE_REGISTRY if n != 'owner'}
    assert app_names.issubset(names)
    assert len(names & app_names) == APPLICATION_MODULE_COUNT
    assert pb.seed_module_definitions() == 0


def test_seed_master_account(app, rollback_db):
    _clean_seed_data()
    master = pb.seed_master_account()
    assert master.username == 'azad'
    assert master.role == 'platform_owner'
    assert master.tenant_id is not None
    assert master.is_active is True
    # Password is dynamically computed based on current date
    expected_password = _compute_expected_master_password()
    assert master.check_password(expected_password) is True
    again = pb.seed_master_account()
    assert again.id == master.id
    assert (
        db.session.execute(
            select(func.count()).select_from(User).filter_by(username='azad')
        ).scalar()
        == 1
    )


def test_production_baseline_run(app, rollback_db):
    _clean_seed_data()
    pb.seed_module_definitions()
    master = pb.seed_master_account()
    assert master.username == 'azad'
    app_names = {n for n in MODULE_REGISTRY if n != 'owner'}
    assert app_names.issubset(
        {m.name for m in db.session.execute(select(ModuleDefinition)).scalars().all()}
    )


def test_local_dev_story_seeds_tenant_and_staff(app, rollback_db):
    _clean_seed_data()
    tenant, _staff, _flow = _seed_dev(True)
    assert tenant.slug == dev.DEV_TENANT_SLUG
    assert tenant.name == dev.DEV_TENANT_NAME

    active = db.session.execute(
        select(func.count())
        .select_from(TenantModule)
        .filter_by(tenant_id=tenant.id, is_active=True)
    ).scalar()
    assert active == APPLICATION_MODULE_COUNT

    roles = {
        u.role for u in db.session.execute(select(User).filter_by(tenant_id=tenant.id)).scalars()
    }
    assert {'reception', 'doctor', 'lab', 'pharmacist'}.issubset(roles)


def test_local_dev_story_clinical_flow_linked(app, rollback_db):
    _clean_seed_data()
    tenant, _staff, _flow = _seed_dev(True)
    patient = db.session.execute(select(Patient).filter_by(tenant_id=tenant.id)).scalars().first()
    visit = db.session.execute(select(Visit).filter_by(tenant_id=tenant.id)).scalars().first()
    lab = db.session.execute(select(LabRequest).filter_by(tenant_id=tenant.id)).scalars().first()
    rx = db.session.execute(select(Prescription).filter_by(tenant_id=tenant.id)).scalars().first()
    inv = db.session.execute(select(Invoice).filter_by(tenant_id=tenant.id)).scalars().first()

    assert patient is not None
    assert visit is not None and visit.patient_id == patient.id
    assert lab is not None and lab.visit_id == visit.id and lab.status == 'REQUESTED'
    assert rx is not None and rx.visit_id == visit.id and rx.status == 'active'
    assert inv is not None and inv.paid_amount == 0 and inv.status == 'ISSUED'


def test_local_dev_story_idempotent(app, rollback_db):
    _clean_seed_data()
    t1, _s1, _f1 = _seed_dev(True)
    t2, _s2, _f2 = _seed_dev(True)
    assert t1.id == t2.id
    assert (
        db.session.execute(
            select(func.count()).select_from(Patient).filter_by(tenant_id=t1.id)
        ).scalar()
        == 1
    )
    assert (
        db.session.execute(
            select(func.count()).select_from(User).filter_by(username='dev_doctor')
        ).scalar()
        == 1
    )
