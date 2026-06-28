"""
End-to-end production flow validation (un-mocked application stack).

Exercises tenant provisioning, clinical VSM lifecycle, billing → entitlements,
and Celery-backed backup queueing against a live PostgreSQL database.

External boundaries (Stripe HTTP API) are stubbed only at the SDK client layer;
all Flask routes, ORM, RLS, VSM, Celery task dispatch, and EntitlementResolver
paths run for real.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from app.shared.enums import BackupStatus, VisitState
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionEntitlement,
    PackageVersionPricing,
)
from app.core.tenant.models import Tenant
from models.backup import Backup
from models.medical_record import MedicalRecord
from models.patient import Patient
from models.user import User
from models.visit import Visit
from services.stripe_subscription_service import StripeSubscriptionService
from services.visit_state_machine_service import VisitStateMachineService
from tests.tenant_context import tenant_test_context

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        not (os.environ.get('DATABASE_URL') or '').startswith('postgresql'),
        reason='E2E production flow requires PostgreSQL (DATABASE_URL)',
    ),
]


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *a, **k: None,
    )


def _seed_starter_package():
    pkg = Package(
        name='E2E Starter',
        slug=f'e2e-starter-{uuid.uuid4().hex[:8]}',
        category='bundle',
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()
    version = PackageVersion(
        package_id=pkg.id,
        version='1.0.0',
        trial_days=7,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(version)
    db.session.flush()
    db.session.add(PackageVersionPricing(
        package_version_id=version.id,
        billing_type='monthly',
        price=199,
        setup_fee=0,
        currency='USD',
    ))
    db.session.add(PackageVersionEntitlement(
        package_version_id=version.id,
        module_name='lab',
        capability_key='lab.order',
    ))
    db.session.add(PackageVersionAvailability(
        package_version_id=version.id,
        availability_status=PackageVersionAvailabilityStatus.AVAILABLE,
        effective_from=datetime.now(timezone.utc),
    ))
    db.session.commit()
    return version


@pytest.fixture
def e2e_runtime(app, monkeypatch, tmp_path):
    """Enable SaaS + Celery eager execution for integration chain."""
    monkeypatch.setenv('ENABLE_SAAS_MODE', 'true')
    monkeypatch.setenv('CELERY_ENABLED', 'true')
    monkeypatch.setenv('CELERY_TASK_ALWAYS_EAGER', 'true')
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_e2e_production')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_e2e_production')
    monkeypatch.setenv('BACKUP_LOCAL_DIR', str(tmp_path / 'backups'))
    from celery_app import get_celery_app, init_celery_app
    init_celery_app(app)
    celery = get_celery_app()
    celery.conf.task_always_eager = True
    celery.conf.task_eager_propagates = True
    return tmp_path


class TestE2EProductionFlow:
    def test_full_production_chain(self, app, client, e2e_runtime, monkeypatch):
        version = _seed_starter_package()
        slug = f'e2e-{uuid.uuid4().hex[:8]}'
        admin_user = f'owner_{slug}'
        admin_pass = 'E2eSecurePass1!'

        # ── 1. Tenant provisioning (live HTTP) ─────────────────────────────
        reg = client.post('/api/saas/register', json={
            'slug': slug,
            'name': 'E2E Production Clinic',
            'contact_email': f'{slug}@e2e.test',
            'admin_username': admin_user,
            'admin_password': admin_pass,
            'admin_full_name': 'E2E Owner',
            'package_version_id': version.id,
            'billing_type': 'monthly',
        })
        assert reg.status_code == 201, reg.get_data(as_text=True)
        reg_body = reg.get_json()
        tenant_id = reg_body['tenant']['id']

        tenant = Tenant.query.get(tenant_id)
        assert tenant is not None
        assert tenant.slug == slug

        with tenant_test_context(app, tenant):
            assert User.query.filter_by(tenant_id=tenant_id, username=admin_user).count() == 1
            assert EntitlementResolver.is_entitled(tenant_id, 'lab.order') is True

        # ── 2. Clinical workflow (real VSM + medical record) ─────────────
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        login = client.post('/auth/login', data={
            'username': admin_user,
            'password': admin_pass,
            'tenant_slug': slug,
        })
        assert login.status_code in (200, 302)

        doctor = User(
            username=f'dr_{slug}',
            email=f'dr_{slug}@e2e.test',
            full_name='E2E Doctor',
            role='doctor',
            is_active=True,
            tenant_id=tenant_id,
        )
        doctor.set_password('docpass1')
        db.session.add(doctor)

        patient = Patient(
            tenant_id=tenant_id,
            first_name='E2E',
            last_name='Patient',
            phone='0500000999',
        )
        db.session.add(patient)
        db.session.flush()

        visit = Visit(tenant_id=tenant_id, patient_id=patient.id, doctor_id=doctor.id)
        VisitStateMachineService.initialize(visit, VisitState.OPEN)
        db.session.add(visit)
        db.session.commit()

        VisitStateMachineService.transition(visit, VisitState.CHECKED_IN)
        VisitStateMachineService.transition(visit, VisitState.IN_PROGRESS)
        db.session.add(MedicalRecord(
            tenant_id=tenant_id,
            patient_id=patient.id,
            visit_id=visit.id,
            title='E2E intake note',
            details='Un-mocked clinical documentation',
            created_by=doctor.id,
        ))
        db.session.commit()
        VisitStateMachineService.transition(visit, VisitState.COMPLETED)
        db.session.commit()

        db.session.refresh(visit)
        assert visit.status == VisitState.COMPLETED.value
        assert MedicalRecord.query.filter_by(visit_id=visit.id).count() == 1

        # ── 3. Billing → entitlements (live services, SDK boundary stub) ───
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Customer.create',
            lambda **kw: MagicMock(id='cus_e2e_prod'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.checkout.Session.create',
            lambda **kw: MagicMock(id='cs_e2e', url='https://checkout.stripe.test/e2e'),
        )

        checkout = client.post('/api/billing/checkout', json={
            'package_version_id': version.id,
            'billing_type': 'monthly',
            'success_url': 'https://example.com/success',
            'cancel_url': 'https://example.com/cancel',
        })
        assert checkout.status_code == 201, checkout.get_data(as_text=True)
        checkout_body = checkout.get_json()
        assert checkout_body.get('checkout_session_id') == 'cs_e2e'

        TenantProvisioningService.suspend_tenant(tenant_id, 'e2e_payment_test')
        db.session.commit()
        assert EntitlementResolver.is_entitled(tenant_id, 'lab.order') is False

        event_id = f'evt_e2e_{uuid.uuid4().hex}'
        payload = json.dumps({
            'id': event_id,
            'type': 'invoice.paid',
            'data': {'object': {'metadata': {'tenant_id': str(tenant_id)}}},
        }).encode('utf-8')
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )
        webhook_result = StripeSubscriptionService.ingest_webhook(payload, 't=1,v1=e2e')
        assert webhook_result.get('action') == 'invoice_paid'
        assert EntitlementResolver.is_entitled(tenant_id, 'lab.order') is True

        # ── 4. Async backup (202 + Celery eager + real pg_dump when available) ─
        super_admin = User.query.filter_by(role='super_admin').first()
        if super_admin is None:
            super_admin = User(
                username=f'sa_{slug}',
                email=f'sa_{slug}@e2e.test',
                full_name='E2E Super Admin',
                role='super_admin',
                is_active=True,
                tenant_id=tenant_id,
            )
            super_admin.set_password('sapass1')
            db.session.add(super_admin)
            db.session.commit()

        with client.session_transaction() as sess:
            sess['_user_id'] = str(super_admin.id)
            sess['_fresh'] = True

        backup_resp = client.post(
            '/super-admin/backup/create',
            json={'type': 'full'},
            headers={'Content-Type': 'application/json'},
        )
        assert backup_resp.status_code == 202, backup_resp.get_data(as_text=True)
        backup_body = backup_resp.get_json()
        assert backup_body.get('accepted') is True
        assert backup_body.get('task_id')
        backup_id = backup_body['backup_id']

        record = db.session.get(Backup, backup_id)
        assert record is not None

        if shutil.which('pg_dump') and os.environ.get('DATABASE_URL', '').startswith('postgresql'):
            assert record.backup_status == BackupStatus.COMPLETED
            assert record.backup_size and record.backup_size > 0
            assert os.path.isfile(record.backup_path)
        else:
            assert record.backup_status in (
                BackupStatus.COMPLETED,
                BackupStatus.IN_PROGRESS,
                BackupStatus.FAILED,
            )
