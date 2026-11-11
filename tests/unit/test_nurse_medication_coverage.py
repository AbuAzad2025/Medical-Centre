"""Coverage tests for routes.nurse_routes.medication.py"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytest_plugins = ['tests._isolated_tenant']


@pytest.fixture
def login_nurse(app, db):
    """Log a nurse in and hand back (tenant, user) so tests can attach a profile."""
    from tests.tenant_context import (
        ensure_default_test_tenant,
        ensure_test_user,
        login_test_client,
    )

    def _login(client, username='nurse_med_user'):
        tenant = ensure_default_test_tenant(app)
        user = ensure_test_user(
            db, tenant, username=username, role='nurse', password='ValidPass123!'
        )
        login_test_client(client, user, tenant, 'ValidPass123!')
        return tenant, user

    return _login


def _make_patient(db, tenant_id, first_name='Nurse', last_name='Patient'):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_department(db, tenant_id, name='NurseDept'):
    from models.department import Department

    d = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(d)
    db.session.flush()
    return d


def _make_visit(db, tenant_id, patient, department):
    from models.visit import Visit

    v = Visit(
        patient_id=patient.id,
        department_id=department.id,
        doctor_id=None,
        status='OPEN',
        payment_status='PENDING',
        total_amount=0,
        paid_amount=0,
        visit_type='REGULAR',
        payment_method='cash',
        is_emergency=False,
        created_at=datetime.now(UTC),
        visit_date=datetime.now(UTC).date(),
    )
    db.session.add(v)
    db.session.flush()
    return v


def _make_medication(db, tenant_id, trade_name='TestMed'):
    from models.medication import Medication

    m = Medication(
        tenant_id=tenant_id,
        scientific_name='Scientific Name',
        trade_name=f'{trade_name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        generic_name='Generic',
        dosage_form='tablet',
        strength='500mg',
        price=Decimal('10.00'),
        category='analgesic',
        stock_quantity=100,
        is_active=True,
    )
    db.session.add(m)
    db.session.flush()
    return m


def _make_prescription(db, tenant_id, patient, visit):
    from models.medication import Prescription

    p = Prescription(
        tenant_id=tenant_id,
        patient_id=patient.id,
        doctor_id=None,
        visit_id=visit.id if visit is not None else None,
        prescription_number=f'RX-{datetime.now(UTC).strftime("%H%M%S%f")}',
        diagnosis='Test diagnosis',
        total_cost=Decimal('100.00'),
        status='active',
        created_at=datetime.now(UTC),
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_prescription_item(db, tenant_id, prescription, medication):
    from models.medication import PrescriptionItem

    item = PrescriptionItem(
        tenant_id=tenant_id,
        prescription_id=prescription.id,
        medication_id=medication.id,
        dosage='1 tablet twice daily',
        quantity=10,
        duration_days=5,
        instructions='After meals',
        unit_price=Decimal('10.00'),
        total_price=Decimal('100.00'),
        created_at=datetime.now(UTC),
    )
    db.session.add(item)
    db.session.flush()
    return item


def _make_nurse(db, tenant_id, user):
    from models.nurse import Nurse

    n = Nurse(
        tenant_id=tenant_id,
        user_id=user.id,
        license_number=f'LIC-{datetime.now(UTC).strftime("%H%M%S%f")}',
        specialization='General',
        experience_years=3,
        is_active=True,
    )
    db.session.add(n)
    db.session.flush()
    return n


class TestNurseMedicationRoutes:
    def test_medication_administration_page(self, app, client, login_as):
        login_as(client, 'nurse_med_page', 'nurse')
        resp = client.get('/nurse/medication-administration')
        assert resp.status_code in (200, 302)

    def test_medication_administration_with_visit(self, app, client, login_nurse, db):
        from app.extensions import db as _db

        tenant, _user = login_nurse(client, 'nurse_med_visit')
        dept = _make_department(_db, tenant.id)
        patient = _make_patient(_db, tenant.id)
        visit = _make_visit(_db, tenant.id, patient, dept)

        resp = client.get(f'/nurse/medication-administration?visit_id={visit.id}')
        assert resp.status_code in (200, 302)

    def test_medications_alias(self, app, client, login_as):
        login_as(client, 'nurse_meds_alias', 'nurse')
        resp = client.get('/nurse/medications')
        assert resp.status_code in (200, 302)

    def test_administer_medication_no_nurse_profile(self, app, client, login_nurse):
        tenant, _user = login_nurse(client, 'nurse_admin_no_profile')
        resp = client.post('/nurse/administer-medication/1')
        assert resp.status_code in (302, 200)

    def test_administer_medication_item_not_found(self, app, client, login_nurse, db):
        from app.extensions import db as _db

        tenant, user = login_nurse(client, 'nurse_admin_nf')
        _make_nurse(_db, tenant.id, user)

        resp = client.post('/nurse/administer-medication/99999')
        assert resp.status_code in (302, 200)

    def test_administer_medication_prescription_without_visit(self, app, client, login_nurse, db):
        from app.extensions import db as _db

        tenant, user = login_nurse(client, 'nurse_admin_no_visit')
        _make_nurse(_db, tenant.id, user)

        patient = _make_patient(_db, tenant.id)
        medication = _make_medication(_db, tenant.id)
        prescription = _make_prescription(_db, tenant.id, patient, None)
        item = _make_prescription_item(_db, tenant.id, prescription, medication)

        resp = client.post(f'/nurse/administer-medication/{item.id}')
        assert resp.status_code in (302, 200)

    def test_administer_medication_success(self, app, client, login_nurse, db):
        from app.extensions import db as _db
        from models.nurse import MedicationAdministrationLog

        tenant, user = login_nurse(client, 'nurse_admin_ok')
        _make_nurse(_db, tenant.id, user)

        dept = _make_department(_db, tenant.id)
        patient = _make_patient(_db, tenant.id)
        visit = _make_visit(_db, tenant.id, patient, dept)
        medication = _make_medication(_db, tenant.id)
        prescription = _make_prescription(_db, tenant.id, patient, visit)
        item = _make_prescription_item(_db, tenant.id, prescription, medication)
        # The request runs in its own app context and therefore its own
        # database session, so the fixtures have to be committed to be visible.
        _db.session.commit()

        resp = client.post(
            f'/nurse/administer-medication/{item.id}',
            data={'notes': 'Given after breakfast'},
        )
        assert resp.status_code in (302, 200)
        # The success path is the only one that redirects back with the visit id.
        assert f'visit_id={visit.id}' in resp.headers.get('Location', '')

        # The row is committed by the route, so re-bind the tenant before reading
        # it back: RLS hides rows written under a tenant the connection is not
        # currently bound to.
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=_db.session)

        log = (
            _db.session.execute(
                _db.select(MedicationAdministrationLog).where(
                    MedicationAdministrationLog.prescription_item_id == item.id
                )
            )
            .scalars()
            .first()
        )
        assert log is not None
        assert log.notes == 'Given after breakfast'
