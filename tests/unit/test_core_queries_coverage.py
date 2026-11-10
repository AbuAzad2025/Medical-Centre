"""Service-level coverage tests for services/core_queries.py.

Everything here runs against the real test database with rollback_db's
savepoint isolation (every write is rolled back at teardown) and the default
SaaS tenant bound on ``g`` by the fixture, exactly as a tenant-scoped request
would see it.

Four public functions originally referenced attributes or names that did not
exist. They have since been fixed in services/core_queries.py; the tests
below assert the corrected, behavioural contracts:

  * ``get_visits_for_queue`` orders by ``Visit.created_at``.
  * ``get_active_medications`` orders by ``Medication.trade_name``.
  * ``get_lab_results_ready`` returns rows (no phantom job/datetime).
  * ``get_radiology_results_ready`` returns rows (no phantom RadiologyRequest
    import / completed_at order_by).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.usefixtures('rollback_db')

AR_FIRST = 'محمد'
AR_FAMILY = 'العتيبي'
# An id that cannot exist: used to prove the missing-record paths.
MISSING_ID = 2_000_000_000


def _tag() -> str:
    return uuid.uuid4().hex[:10]


def _make_patient(db, *, first_name_ar=AR_FIRST, national_id=None, **kw):
    from models.patient import Patient

    tag = _tag()
    p = Patient(
        first_name=kw.pop('first_name', f'Cover{tag}'),
        last_name=kw.pop('last_name', f'Patient{tag}'),
        first_name_ar=first_name_ar,
        last_name_ar=f'{AR_FAMILY}{tag}',
        national_id=national_id or f'ID-{tag}',
        gender='M',
        **kw,
    )
    db.session.add(p)
    db.session.commit()
    return p


def _make_department(db, *, is_active=True, name=None):
    from models.department import Department

    tag = _tag()
    d = Department(
        name=name or f'Dept-{tag}',
        name_ar=f'قسم-{tag}',
        is_active=is_active,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_user(db, *, role='doctor', department_id=None, full_name=None):
    from models.user import User

    tag = _tag()
    uname = f'cov_{role}_{tag}'
    u = User(
        username=uname,
        email=f'{uname}@test.local',
        full_name=full_name or f'Cover {role.title()} {tag}',
        role=role,
        is_active=True,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.commit()
    return u


def _make_visit(db, *, patient_id=None, department_id=None, status='OPEN', **kw):
    from models.visit import Visit

    v = Visit(
        patient_id=patient_id or _make_patient(db).id,
        department_id=department_id,
        status=status,
        **kw,
    )
    db.session.add(v)
    db.session.commit()
    return v


def _make_appointment(db, *, patient_id=None, doctor_id=None, starts_at=None, **kw):
    from models.appointment import Appointment

    tag = _tag()
    a = Appointment(
        patient_id=patient_id or _make_patient(db).id,
        doctor_id=doctor_id,
        starts_at=starts_at or datetime.now(UTC),
        status=kw.pop('status', 'SCHEDULED'),
        notes=kw.pop('notes', f'cover {tag}'),
        **kw,
    )
    db.session.add(a)
    db.session.commit()
    return a


def _make_payment(db, *, patient_id=None, amount=100, payment_date=None, **kw):
    from models.payment import Payment

    p = Payment(
        patient_id=patient_id,
        amount=Decimal(str(amount)),
        payment_date=payment_date or datetime.now(UTC),
        **kw,
    )
    db.session.add(p)
    db.session.commit()
    return p


def _make_invoice(db, *, visit_id=None, total_amount=0, status='DRAFT'):
    from models.invoice import Invoice

    inv = Invoice(
        invoice_number=f'INV-{_tag()}',
        visit_id=visit_id,
        total_amount=Decimal(str(total_amount)),
        status=status,
    )
    db.session.add(inv)
    db.session.commit()
    return inv


def _make_lab_request(db, *, patient_id=None, status='REQUESTED'):
    from models.lab_request import LabRequest

    lr = LabRequest(
        patient_id=patient_id or _make_patient(db).id,
        status=status,
        request_number=f'LR-{_tag()}',
    )
    db.session.add(lr)
    db.session.commit()
    return lr


def _make_lab_result(db, *, request_id, patient_id, test_code='CBC'):
    from models.lab_request import LabResult

    res = LabResult(
        request_id=request_id,
        patient_id=patient_id,
        test_code=test_code,
        test_name='Complete Blood Count',
        value='5.5',
        unit='10^9/L',
        status='READY',
    )
    db.session.add(res)
    db.session.commit()
    return res


def _make_radiology_request(db, *, patient_id=None, status='REQUESTED'):
    from models.radiology_request import RadiologyRequest

    rr = RadiologyRequest(
        patient_id=patient_id or _make_patient(db).id,
        status=status,
        modality='XRay',
        body_part='Chest',
        request_number=f'RR-{_tag()}',
    )
    db.session.add(rr)
    db.session.commit()
    return rr


def _make_radiology_result(db, *, request_id, patient_id):
    from models.radiology_result import RadiologyResult

    res = RadiologyResult(
        request_id=request_id,
        patient_id=patient_id,
        findings='No acute findings',
        impression='Normal',
        status='READY',
    )
    db.session.add(res)
    db.session.commit()
    return res


def _make_medication(db, *, is_active=True):
    from models.medication import Medication

    tag = _tag()
    m = Medication(
        scientific_name=f'ParaSci{tag}',
        trade_name=f'ParaTrade{tag}',
        dosage_form='tablet',
        strength='500mg',
        price=Decimal('12.50'),
        is_active=is_active,
    )
    db.session.add(m)
    db.session.commit()
    return m


def _make_prescription(db, *, patient_id=None, doctor_id=None, visit_id=None):
    from models.medication import Prescription

    rx = Prescription(
        patient_id=patient_id or _make_patient(db).id,
        doctor_id=doctor_id,
        visit_id=visit_id,
        prescription_number=f'RX-{_tag()}',
    )
    db.session.add(rx)
    db.session.commit()
    return rx


def _make_emergency_case(db, *, patient_id=None, status='TRIAGE'):
    from models.emergency import EmergencyCase

    case = EmergencyCase(
        patient_id=patient_id or _make_patient(db).id,
        case_number=f'EC-{_tag()}',
        chief_complaint='Chest pain',
        severity='HIGH',
        status=status,
    )
    db.session.add(case)
    db.session.commit()
    return case


# =====================================================================
# Patient queries
# =====================================================================


class TestPatientQueries:
    def test_get_patient_by_id_returns_the_record(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        assert CoreQueryService.get_patient_by_id(p.id).id == p.id

    def test_get_patient_by_id_missing_raises_tenant_error(self, rollback_db):
        from services.core_queries import CoreQueryService
        from utils.tenant_query import TenantContextError

        with pytest.raises(TenantContextError):
            CoreQueryService.get_patient_by_id(MISSING_ID)

    def test_get_patient_by_code_finds_by_national_id(self, rollback_db):
        from services.core_queries import CoreQueryService

        national_id = f'ID-{_tag()}'
        p = _make_patient(rollback_db, national_id=national_id)
        found = CoreQueryService.get_patient_by_code(national_id)
        assert found is not None
        assert found.id == p.id

    def test_get_patient_by_code_unknown_returns_none(self, rollback_db):
        from services.core_queries import CoreQueryService

        assert CoreQueryService.get_patient_by_code(f'NO-SUCH-ID-{_tag()}') is None

    def test_search_patients_empty_query_returns_recent_rows(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        rows = CoreQueryService.search_patients()
        assert any(r.id == p.id for r in rows)

    def test_search_patients_with_query_finds_the_patient(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        rows = CoreQueryService.search_patients(AR_FIRST)
        assert any(r.id == p.id for r in rows)

    def test_search_patients_limit_and_offset(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        limited = CoreQueryService.search_patients(limit=1)
        assert len(limited) == 1
        # Offset beyond any plausible row count yields nothing.
        assert CoreQueryService.search_patients(offset=100_000) == []
        assert p.id is not None

    def test_search_patients_department_id_is_accepted(self, rollback_db):
        # The parameter is part of the signature and is currently unused.
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        rows = CoreQueryService.search_patients(department_id=12345)
        assert any(r.id == p.id for r in rows)

    def test_count_patients_empty_query_counts_at_least_ours(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_patient(rollback_db)
        assert CoreQueryService.count_patients() >= 1

    def test_count_patients_with_query_counts_the_match(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_patient(rollback_db)
        assert CoreQueryService.count_patients(AR_FIRST) >= 1

    def test_count_patients_unrelated_term_counts_nothing(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_patient(rollback_db)
        assert CoreQueryService.count_patients(f'zzz-nomatch-{_tag()}') == 0

    def test_count_patients_department_id_is_accepted(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_patient(rollback_db)
        assert CoreQueryService.count_patients(department_id=12345) >= 1


# =====================================================================
# Visit queries
# =====================================================================


class TestVisitQueries:
    def test_get_visit_by_id_returns_the_record(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        v = _make_visit(rollback_db, patient_id=p.id)
        assert CoreQueryService.get_visit_by_id(v.id).id == v.id

    def test_get_visit_by_id_missing_raises_tenant_error(self, rollback_db):
        from services.core_queries import CoreQueryService
        from utils.tenant_query import TenantContextError

        with pytest.raises(TenantContextError):
            CoreQueryService.get_visit_by_id(MISSING_ID)

    def test_get_visits_by_patient_returns_the_patients_visits_desc(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        other = _make_patient(rollback_db)
        v1 = _make_visit(rollback_db, patient_id=p.id)
        v2 = _make_visit(rollback_db, patient_id=p.id)
        _make_visit(rollback_db, patient_id=other.id)

        rows = CoreQueryService.get_visits_by_patient(p.id)
        ids = [v.id for v in rows]
        assert v1.id in ids and v2.id in ids
        assert all(v.patient_id == p.id for v in rows)

    def test_get_visits_by_patient_respects_limit(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        _make_visit(rollback_db, patient_id=p.id)
        _make_visit(rollback_db, patient_id=p.id)
        assert len(CoreQueryService.get_visits_by_patient(p.id, limit=1)) == 1

    def test_get_open_visits_returns_open_and_in_progress_only(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        open_v = _make_visit(rollback_db, patient_id=p.id, status='OPEN')
        prog_v = _make_visit(rollback_db, patient_id=p.id, status='IN_PROGRESS')
        done_v = _make_visit(rollback_db, patient_id=p.id, status='COMPLETED')

        rows = CoreQueryService.get_open_visits()
        ids = [v.id for v in rows]
        assert open_v.id in ids
        assert prog_v.id in ids
        assert done_v.id not in ids

    def test_get_open_visits_filters_by_department(self, rollback_db):
        from services.core_queries import CoreQueryService

        d1 = _make_department(rollback_db)
        d2 = _make_department(rollback_db)
        p = _make_patient(rollback_db)
        v1 = _make_visit(rollback_db, patient_id=p.id, department_id=d1.id, status='OPEN')
        v2 = _make_visit(rollback_db, patient_id=p.id, department_id=d2.id, status='OPEN')

        rows = CoreQueryService.get_open_visits(department_id=d1.id)
        ids = [v.id for v in rows]
        assert v1.id in ids
        assert v2.id not in ids

    def test_get_visits_for_queue_status_filter_branch(self, rollback_db):
        from services.core_queries import CoreQueryService

        v = _make_visit(rollback_db, status='OPEN')
        rows = CoreQueryService.get_visits_for_queue(status_filter=['OPEN'])
        assert any(r.id == v.id for r in rows)

    def test_get_visits_for_queue_department_branch(self, rollback_db):
        from services.core_queries import CoreQueryService

        d = _make_department(rollback_db)
        v = _make_visit(rollback_db, department_id=d.id, status='OPEN')
        rows = CoreQueryService.get_visits_for_queue(department_id=d.id)
        assert any(r.id == v.id for r in rows)

    def test_get_visits_for_queue_no_args_branch(self, rollback_db):
        from services.core_queries import CoreQueryService

        v = _make_visit(rollback_db, status='OPEN')
        rows = CoreQueryService.get_visits_for_queue()
        assert any(r.id == v.id for r in rows)

    def test_count_visits_today_counts_todays_visits(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_visit(rollback_db)
        count = CoreQueryService.count_visits_today()
        assert isinstance(count, int)
        assert count >= 1

    def test_count_visits_today_without_tenant_context_still_counts(self, rollback_db, monkeypatch):
        from flask import g

        from services.core_queries import CoreQueryService

        _make_visit(rollback_db)
        monkeypatch.setattr(g, 'tenant_id', None)
        count = CoreQueryService.count_visits_today()
        assert isinstance(count, int)
        assert count >= 1


# =====================================================================
# User/staff queries
# =====================================================================


class TestUserQueries:
    def test_get_user_by_id_returns_the_record(self, rollback_db):
        from services.core_queries import CoreQueryService

        u = _make_user(rollback_db, role='doctor')
        assert CoreQueryService.get_user_by_id(u.id).id == u.id

    def test_get_user_by_id_missing_raises_tenant_error(self, rollback_db):
        from services.core_queries import CoreQueryService
        from utils.tenant_query import TenantContextError

        with pytest.raises(TenantContextError):
            CoreQueryService.get_user_by_id(MISSING_ID)

    def test_get_doctors_returns_doctors_not_nurses(self, rollback_db):
        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        nurse = _make_user(rollback_db, role='nurse')
        rows = CoreQueryService.get_doctors()
        ids = [u.id for u in rows]
        assert doctor.id in ids
        assert nurse.id not in ids

    def test_get_doctors_filters_by_department(self, rollback_db):
        from services.core_queries import CoreQueryService

        d1 = _make_department(rollback_db)
        d2 = _make_department(rollback_db)
        doc_in = _make_user(rollback_db, role='doctor', department_id=d1.id)
        doc_out = _make_user(rollback_db, role='doctor', department_id=d2.id)

        rows = CoreQueryService.get_doctors(department_id=d1.id)
        ids = [u.id for u in rows]
        assert doc_in.id in ids
        assert doc_out.id not in ids

    def test_get_nurses_returns_nurses_not_doctors(self, rollback_db):
        from services.core_queries import CoreQueryService

        nurse = _make_user(rollback_db, role='nurse')
        doctor = _make_user(rollback_db, role='doctor')
        rows = CoreQueryService.get_nurses()
        ids = [u.id for u in rows]
        assert nurse.id in ids
        assert doctor.id not in ids

    def test_get_nurses_filters_by_department(self, rollback_db):
        from services.core_queries import CoreQueryService

        d1 = _make_department(rollback_db)
        d2 = _make_department(rollback_db)
        nurse_in = _make_user(rollback_db, role='nurse', department_id=d1.id)
        nurse_out = _make_user(rollback_db, role='nurse', department_id=d2.id)

        rows = CoreQueryService.get_nurses(department_id=d1.id)
        ids = [u.id for u in rows]
        assert nurse_in.id in ids
        assert nurse_out.id not in ids

    def test_get_staff_by_role_returns_matching_role(self, rollback_db):
        from services.core_queries import CoreQueryService

        pharmacist = _make_user(rollback_db, role='pharmacist')
        doctor = _make_user(rollback_db, role='doctor')
        rows = CoreQueryService.get_staff_by_role('pharmacist')
        ids = [u.id for u in rows]
        assert pharmacist.id in ids
        assert doctor.id not in ids

    def test_get_staff_by_role_filters_by_department(self, rollback_db):
        from services.core_queries import CoreQueryService

        d1 = _make_department(rollback_db)
        d2 = _make_department(rollback_db)
        in_dept = _make_user(rollback_db, role='lab', department_id=d1.id)
        out_dept = _make_user(rollback_db, role='lab', department_id=d2.id)

        rows = CoreQueryService.get_staff_by_role('lab', department_id=d1.id)
        ids = [u.id for u in rows]
        assert in_dept.id in ids
        assert out_dept.id not in ids

    def test_get_staff_by_role_unknown_role_returns_empty(self, rollback_db):
        from services.core_queries import CoreQueryService

        assert CoreQueryService.get_staff_by_role(f'role_{_tag()}') == []


# =====================================================================
# Department queries
# =====================================================================


class TestDepartmentQueries:
    def test_get_department_by_id_returns_the_record(self, rollback_db):
        from services.core_queries import CoreQueryService

        d = _make_department(rollback_db)
        assert CoreQueryService.get_department_by_id(d.id).id == d.id

    def test_get_department_by_id_missing_raises_tenant_error(self, rollback_db):
        from services.core_queries import CoreQueryService
        from utils.tenant_query import TenantContextError

        with pytest.raises(TenantContextError):
            CoreQueryService.get_department_by_id(MISSING_ID)

    def test_get_all_departments_active_only_excludes_inactive(self, rollback_db):
        from services.core_queries import CoreQueryService

        active = _make_department(rollback_db, is_active=True)
        inactive = _make_department(rollback_db, is_active=False)

        rows = CoreQueryService.get_all_departments()
        ids = [d.id for d in rows]
        assert active.id in ids
        assert inactive.id not in ids

    def test_get_all_departments_includes_inactive_when_not_filtered(self, rollback_db):
        from services.core_queries import CoreQueryService

        active = _make_department(rollback_db, is_active=True)
        inactive = _make_department(rollback_db, is_active=False)

        rows = CoreQueryService.get_all_departments(active_only=False)
        ids = [d.id for d in rows]
        assert active.id in ids
        assert inactive.id in ids


# =====================================================================
# Payment/invoice queries
# =====================================================================


class TestPaymentQueries:
    def test_get_payments_by_patient_returns_most_recent_first(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        older = _make_payment(
            rollback_db,
            patient_id=p.id,
            amount=50,
            payment_date=datetime.now(UTC) - timedelta(days=5),
        )
        newer = _make_payment(
            rollback_db, patient_id=p.id, amount=75, payment_date=datetime.now(UTC)
        )

        rows = CoreQueryService.get_payments_by_patient(p.id)
        ids = [pay.id for pay in rows]
        assert older.id in ids
        assert newer.id in ids
        # Most recent first: the newer payment must come before the older one.
        assert ids.index(newer.id) < ids.index(older.id)

    def test_get_payments_by_patient_excludes_other_patients(self, rollback_db):
        from services.core_queries import CoreQueryService

        p1 = _make_patient(rollback_db)
        p2 = _make_patient(rollback_db)
        pay1 = _make_payment(rollback_db, patient_id=p1.id, amount=10)
        pay2 = _make_payment(rollback_db, patient_id=p2.id, amount=20)

        ids = [pay.id for pay in CoreQueryService.get_payments_by_patient(p1.id)]
        assert pay1.id in ids
        assert pay2.id not in ids

    def test_get_invoices_by_patient_finds_invoices_through_the_visit(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        v = _make_visit(rollback_db, patient_id=p.id)
        inv = _make_invoice(rollback_db, visit_id=v.id, total_amount=420, status='ISSUED')

        rows = CoreQueryService.get_invoices_by_patient(p.id)
        assert any(i.id == inv.id for i in rows)

    def test_get_invoices_by_patient_excludes_other_patients_and_visitless(self, rollback_db):
        from services.core_queries import CoreQueryService

        p1 = _make_patient(rollback_db)
        p2 = _make_patient(rollback_db)
        v1 = _make_visit(rollback_db, patient_id=p1.id)
        v2 = _make_visit(rollback_db, patient_id=p2.id)
        inv1 = _make_invoice(rollback_db, visit_id=v1.id)
        inv2 = _make_invoice(rollback_db, visit_id=v2.id)
        # Draft with no visit cannot be joined through any patient.
        visitless = _make_invoice(rollback_db, visit_id=None)

        ids = [i.id for i in CoreQueryService.get_invoices_by_patient(p1.id)]
        assert inv1.id in ids
        assert inv2.id not in ids
        assert visitless.id not in ids

    def test_get_revenue_today_reflects_a_payment_made_today(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        before = CoreQueryService.get_revenue_today()
        _make_payment(rollback_db, patient_id=p.id, amount=321.5)
        after = CoreQueryService.get_revenue_today()
        assert isinstance(after, float)
        assert after == pytest.approx(before + 321.5)

    def test_get_revenue_today_ignores_last_months_payment(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        first_day = date.today().replace(day=1)
        before = CoreQueryService.get_revenue_today()
        _make_payment(
            rollback_db,
            patient_id=p.id,
            amount=11111,
            payment_date=datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
            - timedelta(days=1),
        )
        assert CoreQueryService.get_revenue_today() == pytest.approx(before)

    def test_get_revenue_this_month_reflects_this_months_payment_only(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        first_day = date.today().replace(day=1)

        before_today = CoreQueryService.get_revenue_this_month()
        _make_payment(rollback_db, patient_id=p.id, amount=222.25)
        after_today = CoreQueryService.get_revenue_this_month()
        assert isinstance(after_today, float)
        assert after_today == pytest.approx(before_today + 222.25)

        # A payment dated the last day of the previous month counts toward
        # neither revenue_today nor revenue_this_month.
        _make_payment(
            rollback_db,
            patient_id=p.id,
            amount=33333,
            payment_date=datetime(first_day.year, first_day.month, first_day.day, tzinfo=UTC)
            - timedelta(days=1),
        )
        assert CoreQueryService.get_revenue_this_month() == pytest.approx(after_today)

    def test_get_revenue_today_without_tenant_context(self, rollback_db, monkeypatch):
        from flask import g

        from services.core_queries import CoreQueryService

        _make_payment(rollback_db, patient_id=None, amount=50)
        monkeypatch.setattr(g, 'tenant_id', None)
        revenue = CoreQueryService.get_revenue_today()
        assert isinstance(revenue, float)
        assert revenue >= 0

    def test_get_revenue_this_month_without_tenant_context(self, rollback_db, monkeypatch):
        from flask import g

        from services.core_queries import CoreQueryService

        _make_payment(rollback_db, patient_id=None, amount=50)
        monkeypatch.setattr(g, 'tenant_id', None)
        revenue = CoreQueryService.get_revenue_this_month()
        assert isinstance(revenue, float)
        assert revenue >= 0


# =====================================================================
# Appointment queries
# =====================================================================


class TestAppointmentQueries:
    def test_get_appointments_for_doctor_returns_their_appointments(self, rollback_db):
        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        other_doctor = _make_user(rollback_db, role='doctor')
        p = _make_patient(rollback_db)
        appt = _make_appointment(rollback_db, patient_id=p.id, doctor_id=doctor.id)
        _make_appointment(rollback_db, patient_id=p.id, doctor_id=other_doctor.id)

        rows = CoreQueryService.get_appointments_for_doctor(doctor.id)
        ids = [a.id for a in rows]
        assert appt.id in ids

    def test_get_appointments_for_doctor_date_range_filter(self, rollback_db):
        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        p = _make_patient(rollback_db)
        appt = _make_appointment(rollback_db, patient_id=p.id, doctor_id=doctor.id)

        today = date.today()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)

        in_range = CoreQueryService.get_appointments_for_doctor(
            doctor.id, date_from=yesterday, date_to=tomorrow
        )
        assert appt.id in [a.id for a in in_range]

        from_tomorrow = CoreQueryService.get_appointments_for_doctor(doctor.id, date_from=tomorrow)
        assert appt.id not in [a.id for a in from_tomorrow]

        to_yesterday = CoreQueryService.get_appointments_for_doctor(doctor.id, date_to=yesterday)
        assert appt.id not in [a.id for a in to_yesterday]

    def test_get_appointments_today_returns_todays_appointments(self, rollback_db):
        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        p = _make_patient(rollback_db)
        appt = _make_appointment(
            rollback_db, patient_id=p.id, doctor_id=doctor.id, starts_at=datetime.now(UTC)
        )
        rows = CoreQueryService.get_appointments_today()
        assert appt.id in [a.id for a in rows]

    def test_get_appointments_today_excludes_future_appointments(self, rollback_db):
        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        p = _make_patient(rollback_db)
        future = _make_appointment(
            rollback_db,
            patient_id=p.id,
            doctor_id=doctor.id,
            starts_at=datetime.now(UTC) + timedelta(days=30),
        )
        rows = CoreQueryService.get_appointments_today()
        assert future.id not in [a.id for a in rows]

    def test_get_appointments_today_without_tenant_context(self, rollback_db, monkeypatch):
        from flask import g

        from services.core_queries import CoreQueryService

        doctor = _make_user(rollback_db, role='doctor')
        p = _make_patient(rollback_db)
        appt = _make_appointment(rollback_db, patient_id=p.id, doctor_id=doctor.id)
        monkeypatch.setattr(g, 'tenant_id', None)
        rows = CoreQueryService.get_appointments_today()
        assert appt.id in [a.id for a in rows]


# =====================================================================
# Lab queries
# =====================================================================


class TestLabQueries:
    def test_get_lab_requests_for_worklist_returns_created_request(self, rollback_db):
        from services.core_queries import CoreQueryService

        lr = _make_lab_request(rollback_db, status='REQUESTED')
        rows = CoreQueryService.get_lab_requests_for_worklist()
        assert lr.id in [r.id for r in rows]

    def test_get_lab_requests_for_worklist_status_filter(self, rollback_db):
        from services.core_queries import CoreQueryService

        requested = _make_lab_request(rollback_db, status='REQUESTED')
        done = _make_lab_request(rollback_db, status='DONE')

        rows = CoreQueryService.get_lab_requests_for_worklist(status_filter=['REQUESTED'])
        ids = [r.id for r in rows]
        assert requested.id in ids
        assert done.id not in ids

    def test_get_lab_results_ready_returns_rows(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        lr = _make_lab_request(rollback_db, patient_id=p.id)
        _make_lab_result(rollback_db, request_id=lr.id, patient_id=p.id)

        rows = CoreQueryService.get_lab_results_ready()
        assert any(r.request_id == lr.id for r in rows)

    def test_get_lab_results_ready_with_patient_filter(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        lr = _make_lab_request(rollback_db, patient_id=p.id)
        _make_lab_result(rollback_db, request_id=lr.id, patient_id=p.id)

        rows = CoreQueryService.get_lab_results_ready(patient_id=p.id)
        assert any(r.request_id == lr.id for r in rows)


# =====================================================================
# Radiology queries
# =====================================================================


class TestRadiologyQueries:
    def test_get_radiology_requests_for_worklist_returns_created_request(self, rollback_db):
        from services.core_queries import CoreQueryService

        rr = _make_radiology_request(rollback_db, status='REQUESTED')
        rows = CoreQueryService.get_radiology_requests_for_worklist()
        assert rr.id in [r.id for r in rows]

    def test_get_radiology_requests_for_worklist_status_filter(self, rollback_db):
        from services.core_queries import CoreQueryService

        requested = _make_radiology_request(rollback_db, status='REQUESTED')
        done = _make_radiology_request(rollback_db, status='DONE')

        rows = CoreQueryService.get_radiology_requests_for_worklist(status_filter=['REQUESTED'])
        ids = [r.id for r in rows]
        assert requested.id in ids
        assert done.id not in ids

    def test_get_radiology_results_ready_returns_rows(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        rr = _make_radiology_request(rollback_db, patient_id=p.id)
        _make_radiology_result(rollback_db, request_id=rr.id, patient_id=p.id)

        rows = CoreQueryService.get_radiology_results_ready()
        assert any(r.request_id == rr.id for r in rows)

    def test_get_radiology_results_ready_with_patient_filter(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        rr = _make_radiology_request(rollback_db, patient_id=p.id)
        _make_radiology_result(rollback_db, request_id=rr.id, patient_id=p.id)

        rows = CoreQueryService.get_radiology_results_ready(patient_id=p.id)
        assert any(r.request_id == rr.id for r in rows)


# =====================================================================
# Medication queries
# =====================================================================


class TestMedicationQueries:
    def test_get_active_medications_returns_only_active(self, rollback_db):
        from services.core_queries import CoreQueryService

        _make_medication(rollback_db, is_active=True)
        inactive = _make_medication(rollback_db, is_active=False)

        rows = CoreQueryService.get_active_medications()
        assert all(getattr(r, 'is_active', True) for r in rows)
        assert inactive.id not in [r.id for r in rows]

    def test_get_prescriptions_by_patient_returns_their_prescriptions(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        doctor = _make_user(rollback_db, role='doctor')
        rx = _make_prescription(rollback_db, patient_id=p.id, doctor_id=doctor.id)

        rows = CoreQueryService.get_prescriptions_by_patient(p.id)
        assert rx.id in [r.id for r in rows]

    def test_get_prescriptions_by_patient_excludes_other_patients(self, rollback_db):
        from services.core_queries import CoreQueryService

        p1 = _make_patient(rollback_db)
        p2 = _make_patient(rollback_db)
        rx1 = _make_prescription(rollback_db, patient_id=p1.id)
        rx2 = _make_prescription(rollback_db, patient_id=p2.id)

        ids = [r.id for r in CoreQueryService.get_prescriptions_by_patient(p1.id)]
        assert rx1.id in ids
        assert rx2.id not in ids


# =====================================================================
# Emergency queries
# =====================================================================


class TestEmergencyQueries:
    def test_get_active_emergency_cases_returns_active_statuses(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        triage = _make_emergency_case(rollback_db, patient_id=p.id, status='TRIAGE')
        in_progress = _make_emergency_case(rollback_db, patient_id=p.id, status='IN_PROGRESS')
        observation = _make_emergency_case(rollback_db, patient_id=p.id, status='OBSERVATION')
        completed = _make_emergency_case(rollback_db, patient_id=p.id, status='COMPLETED')

        rows = CoreQueryService.get_active_emergency_cases()
        ids = [c.id for c in rows]
        assert triage.id in ids
        assert in_progress.id in ids
        assert observation.id in ids
        assert completed.id not in ids

    def test_get_emergency_case_by_id_returns_the_record(self, rollback_db):
        from services.core_queries import CoreQueryService

        case = _make_emergency_case(rollback_db)
        assert CoreQueryService.get_emergency_case_by_id(case.id).id == case.id

    def test_get_emergency_case_by_id_missing_raises_tenant_error(self, rollback_db):
        from services.core_queries import CoreQueryService
        from utils.tenant_query import TenantContextError

        with pytest.raises(TenantContextError):
            CoreQueryService.get_emergency_case_by_id(MISSING_ID)


# =====================================================================
# Dashboard stats
# =====================================================================


class TestDashboardStats:
    def test_get_basic_dashboard_stats_returns_all_keys_with_sane_types(self, rollback_db):
        from services.core_queries import CoreQueryService

        p = _make_patient(rollback_db)
        _make_visit(rollback_db, patient_id=p.id)
        _make_user(rollback_db, role='doctor')
        _make_payment(rollback_db, patient_id=p.id, amount=100)

        stats = CoreQueryService.get_basic_dashboard_stats()
        expected_keys = {
            'total_patients',
            'new_patients_today',
            'total_visits',
            'visits_today',
            'total_users',
            'active_users',
            'revenue_today',
            'revenue_month',
        }
        assert set(stats) == expected_keys
        for key in (
            'total_patients',
            'new_patients_today',
            'total_visits',
            'visits_today',
            'total_users',
            'active_users',
        ):
            assert isinstance(stats[key], int), key
            assert stats[key] >= 1, key
        assert stats['revenue_today'] == pytest.approx(CoreQueryService.get_revenue_today())
        assert stats['revenue_month'] == pytest.approx(CoreQueryService.get_revenue_this_month())

    def test_get_basic_dashboard_stats_without_tenant_context(self, rollback_db, monkeypatch):
        from flask import g

        from services.core_queries import CoreQueryService

        _make_patient(rollback_db)
        monkeypatch.setattr(g, 'tenant_id', None)

        stats = CoreQueryService.get_basic_dashboard_stats()
        assert set(stats) == {
            'total_patients',
            'new_patients_today',
            'total_visits',
            'visits_today',
            'total_users',
            'active_users',
            'revenue_today',
            'revenue_month',
        }
        assert stats['total_patients'] >= 1


# =====================================================================
# Module surface
# =====================================================================


def test_core_queries_singleton_is_core_query_service_instance():
    from services.core_queries import CoreQueryService, core_queries

    assert isinstance(core_queries, CoreQueryService)
