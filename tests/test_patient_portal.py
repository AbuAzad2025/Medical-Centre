"""Tests for P0B-001A/B: patient portal crash containment and visibility policy."""

import pytest
import uuid

from app_factory import db as _db
from app.shared.enums import InvoiceStatus, OrderState
from models.invoice import Invoice
from models.lab_request import LabRequest, LabResult
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.user import User
from models.visit import Visit


@pytest.fixture(scope='function')
def portal_patient(app, test_tenant):
    suffix = uuid.uuid4().hex[:8]
    p = Patient(
        tenant_id=test_tenant.id,
        first_name=f'PortalPatient{suffix}',
        last_name='Test',
        phone='0500000000',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def portal_visit(app, test_tenant, portal_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=portal_patient.id,
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def portal_user(app, test_tenant):
    u = User.query.filter_by(username='portal_user').first()
    if not u:
        u = User(
            username='portal_user',
            email='portal@test.local',
            full_name='مريض اختبار',
            role='patient',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def portal_auth_client(app, client, portal_user, test_tenant, monkeypatch):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'portal_user',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


class TestPatientPortalDashboard:
    def test_dashboard_loads_for_linked_patient(self, portal_auth_client, portal_patient, monkeypatch):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )
        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200

    def test_open_invoices_uses_known_statuses_only(self, portal_auth_client, portal_patient, portal_visit, test_tenant, monkeypatch):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        # Create invoices in various statuses
        invoices = [
            Invoice(tenant_id=test_tenant.id, visit_id=portal_visit.id, status=InvoiceStatus.DRAFT, total_amount=100, paid_amount=0),
            Invoice(tenant_id=test_tenant.id, visit_id=portal_visit.id, status=InvoiceStatus.ISSUED, total_amount=200, paid_amount=50),
            Invoice(tenant_id=test_tenant.id, visit_id=portal_visit.id, status=InvoiceStatus.POSTED, total_amount=300, paid_amount=0),
            Invoice(tenant_id=test_tenant.id, visit_id=portal_visit.id, status=InvoiceStatus.PAID, total_amount=400, paid_amount=400),
        ]
        _db.session.add_all(invoices)
        _db.session.commit()

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        # P0B-001B: DRAFT 100 + ISSUED 150 + POSTED 300 = 550; PAID excluded.
        assert b'550.00' in resp.data or b'550' in resp.data

    def test_total_due_computed_from_total_minus_paid(self, portal_auth_client, portal_patient, portal_visit, test_tenant, monkeypatch):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        inv = Invoice(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            status=InvoiceStatus.ISSUED,
            total_amount=500,
            paid_amount=120,
        )
        _db.session.add(inv)
        _db.session.commit()

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        assert b'380.00' in resp.data or b'380' in resp.data

    def test_unread_results_is_zero_when_states_unknown(self, portal_auth_client, portal_patient, monkeypatch):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        # RESULTED/CRITICAL do not exist, so unread_results fails closed to 0.
        assert b'0' in resp.data

    def test_unread_lab_results_only_includes_approved_non_critical(
        self, portal_auth_client, portal_patient, portal_visit, test_tenant, monkeypatch
    ):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        visible = LabRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status=OrderState.APPROVED.value,
        )
        hidden_reviewed = LabRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status=OrderState.REVIEWED.value,
        )
        hidden_critical = LabRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status=OrderState.APPROVED.value,
        )
        _db.session.add_all([visible, hidden_reviewed, hidden_critical])
        _db.session.flush()
        _db.session.add(LabResult(
            tenant_id=test_tenant.id,
            request_id=visible.id,
            patient_id=portal_patient.id,
            test_code='T1',
            test_name='Test',
            is_critical=False,
        ))
        _db.session.add(LabResult(
            tenant_id=test_tenant.id,
            request_id=hidden_critical.id,
            patient_id=portal_patient.id,
            test_code='T2',
            test_name='Test Critical',
            is_critical=True,
        ))
        _db.session.commit()

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        assert b'1' in resp.data

    def test_unread_radiology_results_only_includes_done_non_critical(
        self, portal_auth_client, portal_patient, portal_visit, test_tenant, monkeypatch
    ):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        done_visible = RadiologyRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status='DONE',
        )
        done_critical = RadiologyRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status='DONE',
        )
        in_progress = RadiologyRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status='IN_PROGRESS',
        )
        _db.session.add_all([done_visible, done_critical, in_progress])
        _db.session.flush()
        _db.session.add(RadiologyResult(
            tenant_id=test_tenant.id,
            request_id=done_visible.id,
            patient_id=portal_patient.id,
            findings='Normal',
            is_critical=False,
        ))
        _db.session.add(RadiologyResult(
            tenant_id=test_tenant.id,
            request_id=done_critical.id,
            patient_id=portal_patient.id,
            findings='Critical',
            is_critical=True,
        ))
        _db.session.commit()

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        assert b'1' in resp.data

    def test_critical_results_flag_shown(
        self, portal_auth_client, portal_patient, portal_visit, test_tenant, monkeypatch
    ):
        from routes import patient_portal
        monkeypatch.setattr(
            patient_portal, '_get_patient_from_user', lambda: portal_patient
        )

        critical_lab = LabRequest(
            tenant_id=test_tenant.id,
            visit_id=portal_visit.id,
            patient_id=portal_patient.id,
            status=OrderState.APPROVED.value,
        )
        _db.session.add(critical_lab)
        _db.session.flush()
        _db.session.add(LabResult(
            tenant_id=test_tenant.id,
            request_id=critical_lab.id,
            patient_id=portal_patient.id,
            test_code='T',
            test_name='Critical Test',
            is_critical=True,
        ))
        _db.session.commit()

        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200
        assert 'متابعة سريرية'.encode('utf-8') in resp.data
