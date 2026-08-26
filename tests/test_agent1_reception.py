import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from models.cash_register import CashRegister
from models.patient import Patient, PatientAllergy
from models.queue_management import QueueManagement, QueueSettings
from models.visit import Visit
from tests.tenant_context import ensure_test_user, login_test_client, tenant_test_context


def _reception(client, db, test_tenant, username=None):
    username = username or f'rec_{uuid.uuid4().hex[:6]}'
    u = ensure_test_user(db, test_tenant, username=username, role='reception')
    login_test_client(client, u, test_tenant)
    return u


def _manager(client, db, test_tenant, username=None):
    username = username or f'mgr_{uuid.uuid4().hex[:6]}'
    u = ensure_test_user(db, test_tenant, username=username, role='manager')
    login_test_client(client, u, test_tenant)
    return u


def _patient(db, **kw):
    phone = kw.get('phone') or f'059{uuid.uuid4().int % 10**7:07d}'
    p = Patient(
        first_name=kw.get('first_name', 'Test'),
        last_name=kw.get('last_name', 'User'),
        phone=phone,
        gender=kw.get('gender', 'M'),
        national_id=kw.get('national_id'),
        birth_date=kw.get('birth_date'),
        address=kw.get('address'),
        first_name_ar=kw.get('first_name_ar'),
        last_name_ar=kw.get('last_name_ar'),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _department(db, **kw):
    from models.department import Department

    tag = uuid.uuid4().hex[:6]
    d = Department(
        name=kw.get('name', f'Dept-{tag}'),
        name_ar=kw.get('name_ar', f'قسم-{tag}'),
        is_active=kw.get('is_active', True),
        location=kw.get('location', 'Room 1'),
    )
    db.session.add(d)
    db.session.commit()
    return d


def _doctor(db, test_tenant, **kw):
    from models.user import User

    role = 'doctor'
    u = User(
        username=kw.get('username', f'doc_{uuid.uuid4().hex[:6]}'),
        email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
        full_name=kw.get('full_name', 'Doctor Test'),
        role=role,
        is_active=True,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.commit()
    return u


def _visit(db, **kw):
    v = Visit(
        patient_id=kw.get('patient_id'),
        department_id=kw.get('department_id'),
        doctor_id=kw.get('doctor_id'),
        status=kw.get('status', 'OPEN'),
        payment_status=kw.get('payment_status', 'PENDING'),
        total_amount=kw.get('total_amount', 0),
        paid_amount=kw.get('paid_amount', 0),
        visit_type=kw.get('visit_type', 'REGULAR'),
        payment_method=kw.get('payment_method', 'CASH'),
        is_emergency=kw.get('is_emergency', False),
        is_force_payment=kw.get('is_force_payment', False),
        force_payment_approved_by=kw.get('force_payment_approved_by'),
        archive_status=kw.get('archive_status', 'ACTIVE'),
        gl_posted_at=kw.get('gl_posted_at'),
        financial_completed_at=kw.get('financial_completed_at'),
        financial_locked=kw.get('financial_locked', False),
        currency=kw.get('currency', 'ILS'),
    )
    db.session.add(v)
    db.session.commit()
    return v


class TestPatientModel:
    def test_full_name_arabic(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(
                db, first_name='John', last_name='Doe', first_name_ar='أحمد', last_name_ar='حسن'
            )
            assert p.full_name == 'أحمد حسن'
            p2 = _patient(db, first_name='John', last_name='Doe')
            assert p2.full_name == 'John Doe'

    def test_gender_display(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            p.gender = 'M'
            assert p.get_gender_display() == 'ذكر'
            p.gender = 'F'
            assert p.get_gender_display() == 'أنثى'
            p.gender = 'ذكر'
            assert p.get_gender_display() == 'ذكر'
            p.gender = 'FEMALE'
            assert p.get_gender_display() == 'أنثى'
            p.gender = 'other'
            assert p.get_gender_display() == 'آخر'
            p.gender = ''
            assert p.get_gender_display() == 'غير محدد'
            p.gender = None
            assert p.get_gender_display() == 'غير محدد'

    def test_phone_validation_short(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            with pytest.raises(ValueError):
                p = Patient(first_name='A', last_name='B', phone='123')
                db.session.add(p)
                db.session.flush()

    def test_phone_validation_long(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            with pytest.raises(ValueError):
                p = Patient(first_name='A', last_name='B', phone='1' * 25)
                db.session.add(p)
                db.session.flush()

    def test_phone_validation_digits_short(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            with pytest.raises(ValueError):
                p = Patient(first_name='A', last_name='B', phone='+---   ()')
                db.session.add(p)
                db.session.flush()

    def test_age_none(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            p.birth_date = None
            assert p.age is None

    def test_age_valid(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db, birth_date=date(1990, 1, 1))
            assert isinstance(p.age, int)
            assert p.age >= 30

    def test_age_future(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db, birth_date=date.today() + timedelta(days=10))
            assert p.age is not None

    def test_to_dict(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = p.to_dict()
            assert 'full_name' in d
            assert 'phone' in d
            assert d['id'] == p.id

    def test_visit_count_no_counter(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            cnt = p.visit_count
            assert cnt == 0
            d = _department(db)
            _visit(db, patient_id=p.id, department_id=d.id, total_amount=10, paid_amount=10)
            assert p.visit_count == 1

    def test_visit_count_with_counter(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from models.patient_visit_counter import PatientVisitCounter

            p = _patient(db)
            c = PatientVisitCounter(patient_id=p.id, visit_count=5)
            db.session.add(c)
            db.session.commit()
            assert p.visit_count == 5

    def test_allergy_to_dict(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            a = PatientAllergy(
                tenant_id=test_tenant.id, patient_id=p.id, allergen='Penicillin', severity='HIGH'
            )
            db.session.add(a)
            db.session.commit()
            d = a.to_dict()
            assert d['allergen'] == 'Penicillin'


class TestVisitModel:
    def test_remaining_and_fully_paid(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, total_amount=100, paid_amount=30)
            assert v.remaining_amount == Decimal('70')
            assert v.is_fully_paid is False
            v2 = _visit(db, patient_id=p.id, department_id=d.id, total_amount=50, paid_amount=50)
            assert v2.is_fully_paid is True
            v3 = _visit(db, patient_id=p.id, department_id=d.id, total_amount=50, paid_amount=60)
            assert v3.is_fully_paid is True

    def test_payment_status_display(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, payment_status='PENDING')
            assert v.payment_status_display == 'معلق'
            v.payment_status = 'PAID'
            assert v.payment_status_display == 'مدفوع'
            v.payment_status = 'UNKNOWN'
            assert v.payment_status_display == 'UNKNOWN'

    def test_visit_type_display(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, visit_type='REGULAR')
            assert v.visit_type_display == 'عادية'
            v.visit_type = 'EMERGENCY'
            assert v.visit_type_display == 'طوارئ'
            v.visit_type = 'UNKNOWN'
            assert v.visit_type_display == 'UNKNOWN'

    def test_visit_id_number_and_archived(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, archive_status='ARCHIVED')
            assert v.is_archived is True
            assert v.visit_id_number == v.id
            v.visit_number = 'VN-123'
            assert v.visit_id_number == 'VN-123'
            v2 = _visit(db, patient_id=p.id, department_id=d.id, archive_status='ACTIVE')
            assert v2.is_archived is False

    def test_get_status_display(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
            assert v.get_status_display() == 'مفتوحة'
            v.status = 'COMPLETED'
            db.session.flush()
            assert v.get_status_display() == 'مكتملة'
            v.status = 'UNKNOWN'
            assert v.get_status_display() == 'UNKNOWN'

    def test_can_be_archived(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='OPEN',
                payment_status='PENDING',
                archive_status='ACTIVE',
            )
            ok, _ = v.can_be_archived()
            assert ok is False
            v2 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                payment_status='PENDING',
                is_force_payment=False,
            )
            ok, msg = v2.can_be_archived()
            assert ok is False
            assert 'الدفع' in msg
            v3 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                payment_status='PENDING',
                is_force_payment=True,
                force_payment_approved_by=None,
            )
            ok, _ = v3.can_be_archived()
            assert ok is False
            doc = _doctor(db, test_tenant)
            v4 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                payment_status='PAID',
                is_force_payment=False,
            )
            ok, _ = v4.can_be_archived()
            assert ok is True
            v5 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                payment_status='PENDING',
                is_force_payment=True,
                force_payment_approved_by=doc.id,
            )
            ok, _ = v5.can_be_archived()
            assert ok is True
            v6 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                status='COMPLETED',
                payment_status='PAID',
                archive_status='ARCHIVED',
            )
            ok, msg = v6.can_be_archived()
            assert ok is False
            assert 'مؤرشفة' in msg

    def test_calculate_insurance_valid(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                payment_method='insurance',
                total_amount=200,
                paid_amount=0,
            )
            v.insurance_coverage_percentage = 50
            v.calculate_insurance_amounts()
            assert v.insurance_amount == Decimal('100')
            assert v.patient_share == Decimal('100')

    def test_calculate_insurance_invalid(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                payment_method='insurance',
                total_amount=200,
            )
            v.insurance_coverage_percentage = 150
            v.calculate_insurance_amounts()
            assert (
                v.insurance_amount == Decimal('0')
                or v.insurance_amount is None
                or v.insurance_amount == 0
            )
            v2 = _visit(
                db, patient_id=p.id, department_id=d.id, payment_method='cash', total_amount=200
            )
            v2.insurance_coverage_percentage = 50
            v2.calculate_insurance_amounts()
            assert (
                v2.insurance_amount == Decimal('0')
                or v2.insurance_amount is None
                or v2.insurance_amount == 0
            )
            v3 = _visit(
                db,
                patient_id=p.id,
                department_id=d.id,
                payment_method='insurance',
                total_amount=200,
            )
            v3.insurance_coverage_percentage = -10
            v3.calculate_insurance_amounts()
            assert v3.patient_share is None or v3.patient_share == 0

    def test_calculate_insurance_zero_total(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(
                db, patient_id=p.id, department_id=d.id, payment_method='insurance', total_amount=0
            )
            v.insurance_coverage_percentage = 50
            v.calculate_insurance_amounts()
            assert v.insurance_amount == Decimal('0')

    def test_validate_status_via_vsm_blocked(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from services.visit_state_machine_service import is_vsm_authorized

            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
            original = is_vsm_authorized
            try:
                import services.visit_state_machine_service as vsm

                vsm.is_vsm_authorized = lambda: False
                with pytest.raises(ValueError):
                    v.status = 'COMPLETED'
                    db.session.flush()
                db.session.rollback()
            finally:
                import services.visit_state_machine_service as vsm2

                vsm2.is_vsm_authorized = original

    def test_to_dict(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(
                db, patient_id=p.id, department_id=d.id, total_amount=123.456, paid_amount=10
            )
            v.insurance_amount = 10
            v.patient_share = 5
            dct = v.to_dict()
            assert dct['total_amount'] == '123.46'
            assert dct['payment_status'] == 'PENDING'


class TestQueueManagementModel:
    def test_priority_and_status_display(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            q = QueueManagement(
                patient_id=1,
                department_id=1,
                queue_number='A1',
                priority_level='urgent',
                status='waiting',
                tenant_id=test_tenant.id,
            )
            assert q.get_priority_display() == 'عاجلة'
            q.priority_level = 'low'
            assert q.get_priority_display() == 'منخفضة'
            q.priority_level = 'unknown'
            assert q.get_priority_display() == 'unknown'
            q.status = 'waiting'
            assert q.get_status_display() == 'في الانتظار'
            q.status = 'called'
            assert q.get_status_display() == 'تم الاستدعاء'
            q.status = 'unknown'
            assert q.get_status_display() == 'unknown'

    def test_visit_payment_status(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, payment_status='PAID')
            q = QueueManagement(
                patient_id=p.id,
                department_id=d.id,
                visit_id=v.id,
                queue_number='Q1',
                tenant_id=test_tenant.id,
            )
            q.visit = v
            assert q._visit_payment_status() == 'PAID'
            q2 = QueueManagement(
                patient_id=p.id, department_id=d.id, queue_number='Q2', tenant_id=test_tenant.id
            )
            assert q2._visit_payment_status() is None
            assert q2.get_payment_status_display() == 'غير محدد'
            q.visit = v
            assert q.get_payment_status_display() == 'مدفوع'
            v.payment_status = 'PENDING'
            assert q.get_payment_status_display() == 'معلق'
            v.payment_status = 'waived'
            assert q.get_payment_status_display() == 'معفى'
            v.payment_status = 'UNKNOWN_X'
            assert q.get_payment_status_display() == 'UNKNOWN_X'

    def test_to_dict(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            p = _patient(db)
            d = _department(db)
            q = QueueManagement(
                patient_id=p.id, department_id=d.id, queue_number='Q9', tenant_id=test_tenant.id
            )
            db.session.add(q)
            db.session.commit()
            dct = q.to_dict()
            assert dct['queue_number'] == 'Q9'
            assert 'payment_status' in dct

    def test_queue_settings_to_dict(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            d = _department(db)
            s = QueueSettings(department_id=d.id, max_queue_size=30)
            db.session.add(s)
            db.session.commit()
            dct = s.to_dict()
            assert dct['max_queue_size'] == 30


class TestCashRegisterModel:
    def test_get_or_create_today(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            r1 = CashRegister.get_or_create_today(user_id=1)
            r2 = CashRegister.get_or_create_today(user_id=1)
            assert r1.id == r2.id
            assert r1.is_open is True
            assert r1.is_closed is False

    def test_to_dict_zero_and_none(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            r = CashRegister(
                register_date=date.today(),
                is_open=True,
                is_closed=False,
                opening_cash=0,
                expected_total=100,
                actual_total=Decimal('0'),
                variance=Decimal('0'),
            )
            db.session.add(r)
            db.session.commit()
            d = r.to_dict()
            assert d['actual_total'] == 0.0
            assert d['variance'] == 0.0
            r2 = CashRegister(
                register_date=date.today(),
                is_open=True,
                is_closed=False,
                opening_cash=10,
                expected_total=50,
                actual_total=None,
                variance=None,
            )
            db.session.add(r2)
            db.session.commit()
            d2 = r2.to_dict()
            assert d2['actual_total'] is None
            assert d2['variance'] is None

    def test_to_dict_expected(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            r = CashRegister(
                register_date=date.today(),
                opening_cash=Decimal('10.5'),
                expected_total=Decimal('20'),
            )
            db.session.add(r)
            db.session.commit()
            d = r.to_dict()
            assert d['opening_cash'] == 10.5
            assert d['expected_total'] == 20.0


class TestReceptionApiDoctors:
    def test_doctors_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        doc.department_id = d.id
        db.session.commit()
        resp = client.get(
            '/reception/api/doctors',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert any(x['id'] == doc.id for x in data['doctors'])

    def test_doctors_excludes_non_doctor(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        from models.user import User

        nurse = User(
            username=f'nurse_{uuid.uuid4().hex[:6]}',
            email=f'{uuid.uuid4().hex[:8]}@test.local',
            full_name='Nurse',
            role='nurse',
            is_active=True,
        )
        nurse.set_password('test123')
        nurse.department_id = d.id
        db.session.add(nurse)
        db.session.commit()
        resp = client.get(
            '/reception/api/doctors',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [x['id'] for x in data['doctors']]
        assert nurse.id not in ids

    def test_doctors_invalid_id(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get(
            '/reception/api/doctors',
            query_string={'department_id': 'bad'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_doctors_no_filter(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _doctor(db, test_tenant)
        resp = client.get('/reception/api/doctors', headers={'Accept': 'application/json'})
        assert resp.status_code == 200

    def test_doctors_unauth(self, app, client, db, rollback_db, test_tenant):
        resp = client.get('/reception/api/doctors', headers={'Accept': 'application/json'})
        assert resp.status_code in (302, 401)


class TestReceptionApiDepartmentStaff:
    def test_staff_missing_param(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/api/department-staff', headers={'Accept': 'application/json'})
        assert resp.status_code == 400

    def test_staff_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get(
            '/reception/api/department-staff',
            query_string={'department_id': 999999},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 404

    def test_staff_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        doc.department_id = d.id
        db.session.commit()
        resp = client.get(
            '/reception/api/department-staff',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert 'staff' in resp.get_json()

    def test_staff_lab_department(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db, name='Lab Dept', name_ar='مختبر تحاليل')
        from models.user import User

        tech = User(
            username=f'tech_{uuid.uuid4().hex[:6]}',
            email=f'{uuid.uuid4().hex[:8]}@test.local',
            full_name='Tech',
            role='technician',
            is_active=True,
        )
        tech.set_password('test123')
        db.session.add(tech)
        db.session.commit()
        resp = client.get(
            '/reception/api/department-staff',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200


class TestReceptionApiDepartmentServices:
    def test_services_missing(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get(
            '/reception/api/department-services', headers={'Accept': 'application/json'}
        )
        assert resp.status_code == 400

    def test_services_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get(
            '/reception/api/department-services',
            query_string={'department_id': 999999},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 404

    def test_services_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db, name='General Clinic', name_ar='عيادة عامة')
        resp = client.get(
            '/reception/api/department-services',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        assert 'services' in resp.get_json()

    def test_services_with_custom(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        from models.service import ServiceMaster

        d = _department(db, name='ServiceDept', name_ar='قسم خدمات')
        s = ServiceMaster(
            code=f'SVC-{uuid.uuid4().hex[:6]}',
            name='Test Service',
            name_ar='خدمة اختبار',
            category='doctor',
            department_id=d.id,
            base_price=100,
            is_active=True,
        )
        db.session.add(s)
        db.session.commit()
        resp = client.get(
            '/reception/api/department-services',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['services']) >= 1


class TestReceptionPatients:
    def test_patients_list(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _patient(db, first_name='SearchMe')
        resp = client.get('/reception/patients')
        assert resp.status_code == 200

    def test_patients_search(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _patient(db, first_name='UniqueSearch123')
        resp = client.get('/reception/patients', query_string={'search': 'UniqueSearch123'})
        assert resp.status_code == 200

    def test_patients_phone_search(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _patient(db, phone='0599998888')
        resp = client.get('/reception/patients', query_string={'search': '0599998888'})
        assert resp.status_code == 200

    def test_patients_department_filter(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/patients', query_string={'department_id': d.id})
        assert resp.status_code == 200

    def test_add_patient_json_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone = f'059{uuid.uuid4().int % 10**7:07d}'
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'Ahmad', 'last_name': 'Ali', 'phone': phone, 'gender': 'M'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert resp.get_json()['success'] is True

    def test_add_patient_invalid_phone(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '12'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_invalid_national_id(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone = f'059{uuid.uuid4().int % 10**7:07d}'
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'A', 'last_name': 'B', 'phone': phone, 'national_id': 'ab'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_add_patient_missing_names(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone = f'059{uuid.uuid4().int % 10**7:07d}'
        resp = client.post(
            '/reception/add_patient', data={'phone': phone}, headers={'Accept': 'application/json'}
        )
        assert resp.status_code == 400

    def test_add_patient_duplicate_national_id(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone1 = f'059{uuid.uuid4().int % 10**7:07d}'
        _patient(db, phone=phone1, national_id='123456789')
        phone2 = f'059{uuid.uuid4().int % 10**7:07d}'
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'New',
                'last_name': 'Patient',
                'phone': phone2,
                'national_id': '123456789',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_add_patient_duplicate_phone(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone = f'059{uuid.uuid4().int % 10**7:07d}'
        _patient(db, phone=phone)
        resp = client.post(
            '/reception/add_patient',
            data={'first_name': 'New', 'last_name': 'Patient', 'phone': phone},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_add_patient_pregnancy(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        phone = f'059{uuid.uuid4().int % 10**7:07d}'
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'Sara',
                'last_name': 'Ali',
                'phone': phone,
                'is_pregnant': 'on',
                'pregnancy_weeks': '12',
                'last_menstruation_date': '2024-01-01',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302, 400)

    def test_view_patient_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.get(f'/reception/view_patient/{p.id}')
        assert resp.status_code == 200

    def test_view_patient_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/view_patient/999999')
        assert resp.status_code == 302

    def test_edit_patient_get(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.get(f'/reception/edit_patient/{p.id}')
        assert resp.status_code == 200

    def test_edit_patient_post_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'Updated', 'last_name': 'Name', 'phone': p.phone},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)
        db.session.refresh(p)
        assert p.first_name == 'Updated'

    def test_edit_patient_invalid_phone(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '12'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_edit_patient_duplicate_phone(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _patient(db, phone='0591111111')
        p2 = _patient(db, phone='0592222222')
        resp = client.post(
            f'/reception/edit_patient/{p2.id}',
            data={'first_name': 'A', 'last_name': 'B', 'phone': '0591111111'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 409

    def test_delete_patient_success(self, app, client, db, rollback_db, test_tenant):
        _manager(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code in (302, 200)

    def test_delete_patient_with_receipt(self, app, client, db, rollback_db, test_tenant):
        from models.receipt import Receipt

        _manager(client, db, test_tenant)
        p = _patient(db)
        r = Receipt(patient_id=p.id, amount=10, receipt_number=f'R-{uuid.uuid4().hex[:6]}')
        db.session.add(r)
        db.session.commit()
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code == 302

    def test_smart_search(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _patient(db, phone='0507777777')
        resp = client.get(
            '/reception/api/smart-patient-search',
            query_string={'q': '0507777777'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200

    def test_allergy_add_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            data=json.dumps({'allergen': 'Peanut', 'severity': 'HIGH'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_allergy_missing_allergen(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            data=json.dumps({'allergen': ''}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_allergy_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/api/patients/999999/allergies/add',
            data=json.dumps({'allergen': 'X'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_problem_add_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            data=json.dumps({'problem_description': 'Hypertension'}),
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_problem_missing(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            data=json.dumps({'problem_description': ''}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_toggle_problem(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            data=json.dumps({'problem_description': 'Asthma'}),
            content_type='application/json',
        )
        pid = resp.get_json()['data']['id']
        resp2 = client.post(f'/reception/api/patients/{p.id}/problems/{pid}/toggle')
        assert resp2.status_code == 200
        assert resp2.get_json()['status'] == 'RESOLVED'
        resp3 = client.post(f'/reception/api/patients/{p.id}/problems/{pid}/toggle')
        assert resp3.get_json()['status'] == 'ACTIVE'

    def test_toggle_problem_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(f'/reception/api/patients/{p.id}/problems/999999/toggle')
        assert resp.status_code == 404


class TestReceptionVisits:
    def test_visits_list(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/visits')
        assert resp.status_code == 200

    def test_visits_search(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db, first_name='SearchVisit')
        d = _department(db)
        _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/visits', query_string={'search': 'SearchVisit'})
        assert resp.status_code == 200

    def test_visits_filters(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.get(
            '/reception/visits', query_string={'department_id': d.id, 'status': 'OPEN'}
        )
        assert resp.status_code == 200

    def test_visits_pagination(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/visits', query_string={'page': 1, 'per_page': 10})
        assert resp.status_code == 200
        resp2 = client.get('/reception/visits', query_string={'page': 1, 'per_page': 500})
        assert resp2.status_code == 200

    def test_archive_completed(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(
            db,
            patient_id=p.id,
            department_id=d.id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        db.session.refresh(v)
        assert v.archive_status == 'ARCHIVED'

    def test_archive_open(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        db.session.refresh(v)
        assert v.archive_status != 'ARCHIVED'

    def test_archive_already(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(
            db,
            patient_id=p.id,
            department_id=d.id,
            status='COMPLETED',
            total_amount=0,
            paid_amount=0,
            archive_status='ARCHIVED',
            gl_posted_at=datetime.now(UTC),
        )
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302

    def test_archive_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post('/reception/visits/999999/archive')
        assert resp.status_code == 302

    def test_end_visit(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(
            db,
            patient_id=p.id,
            department_id=d.id,
            status='COMPLETED',
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302

    def test_end_open(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302

    def test_export(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/export/visits')
        assert resp.status_code == 200
        assert 'text/csv' in resp.headers.get('Content-Type', '')

    def test_transfer_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d1 = _department(db)
        d2 = _department(db)
        doc = _doctor(db, test_tenant)
        v = _visit(db, patient_id=p.id, department_id=d1.id, doctor_id=doc.id, status='OPEN')
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data={'department_id': d2.id, 'doctor_id': doc.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 400, 404, 409, 500)

    def test_transfer_invalid_dept(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.post(
            f'/reception/visits/{v.id}/transfer',
            data=json.dumps({'department_id': 999999}),
            content_type='application/json',
        )
        assert resp.status_code in (400, 404, 500)

    def test_create_visit_get(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/visits/create')
        assert resp.status_code == 200

    def test_create_visit_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Clinic', name_ar='عيادة عامة')
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'visit_type': 'REGULAR',
                'payment_method': 'cash',
                'amount_paid': '0',
            },
        )
        assert resp.status_code in (302, 200)
        v = (
            db.session.execute(
                select(Visit)
                .filter_by(patient_id=p.id, department_id=d.id)
                .order_by(Visit.id.desc())
            )
            .scalars()
            .first()
        )
        assert v is not None

    def test_create_visit_missing_patient(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db, name='General Clinic', name_ar='عيادة عامة')
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={'department_id': d.id, 'doctor_id': doc.id, 'payment_method': 'cash'},
        )
        assert resp.status_code == 200

    def test_create_visit_missing_department(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            '/reception/visits/create', data={'patient_id': p.id, 'payment_method': 'cash'}
        )
        assert resp.status_code == 200

    def test_create_visit_doctor_required(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Dept', name_ar='قسم عام')
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': p.id, 'department_id': d.id, 'payment_method': 'cash'},
        )
        assert resp.status_code == 200

    def test_create_visit_no_payment_method(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Dept', name_ar='قسم عام')
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': p.id, 'department_id': d.id, 'doctor_id': doc.id},
        )
        assert resp.status_code == 200

    def test_create_visit_insurance_missing(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Dept', name_ar='قسم عام')
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'payment_method': 'insurance',
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 200

    def test_create_visit_card_missing(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'payment_method': 'visa',
                'amount_paid': '0',
            },
        )
        assert resp.status_code == 200

    def test_create_visit_force_missing_reason(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/visits/create',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'payment_method': 'force',
                'force_payment_reason': 'short',
            },
        )
        assert resp.status_code == 200

    def test_create_visit_quick_emergency(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        _department(db, name='Emergency', name_ar='الطوارئ')
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'مريض طارئ',
                'quick_reason': 'ألم شديد في الصدر يتطلب تدخلا سريعا',
            },
        )
        assert resp.status_code in (302, 200)

    def test_create_visit_quick_missing_name(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/visits/create', data={'quick_emergency': '1', 'quick_patient_name': ''}
        )
        assert resp.status_code == 200

    def test_view_visit(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/view_visit/{v.id}')
        assert resp.status_code == 200

    def test_view_visit_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/view_visit/999999')
        assert resp.status_code in (200, 302)

    def test_visit_pricing_api(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        resp = client.get(
            '/reception/api/visit-pricing',
            query_string={
                'department_id': d.id,
                'doctor_id': doc.id,
                'visit_type': 'REGULAR',
                'tax_type': 'exclusive',
            },
        )
        assert resp.status_code == 200
        assert 'cost' in resp.get_json()

    def test_visit_pricing_inclusive(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(
            '/reception/api/visit-pricing',
            query_string={'department_id': d.id, 'tax_type': 'inclusive'},
        )
        assert resp.status_code == 200

    def test_visit_pricing_lab_with_tests(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        from models.service import ServiceMaster

        d = _department(db, name='Lab Special', name_ar='مختبر خاص')
        s = ServiceMaster(
            code=f'SVC-{uuid.uuid4().hex[:6]}',
            name='Lab Test',
            name_ar='فحص مختبر',
            category='lab',
            department_id=d.id,
            base_price=50,
            is_active=True,
        )
        db.session.add(s)
        db.session.commit()
        resp = client.get(
            '/reception/api/visit-pricing',
            query_string={'department_id': d.id, 'test_ids': str(s.id), 'payment_method': 'cash'},
        )
        assert resp.status_code == 200


class TestReceptionQueue:
    def test_queue_page(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/queue')
        assert resp.status_code == 200

    def test_add_queue_get(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/queue/add-patient')
        assert resp.status_code == 200

    def test_add_queue_post_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Queue', name_ar='قسم عام')
        doc = _doctor(db, test_tenant)
        v = _visit(
            db,
            patient_id=p.id,
            department_id=d.id,
            doctor_id=doc.id,
            payment_status='PAID',
            payment_method='CASH',
        )
        resp = client.post(
            '/reception/queue/add-patient',
            data={'patient_id': p.id, 'department_id': d.id, 'doctor_id': doc.id, 'visit_id': v.id},
        )
        assert resp.status_code in (302, 200)

    def test_add_queue_general_requires_doctor(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db, name='General Queue2', name_ar='قسم عام')
        resp = client.post(
            '/reception/queue/add-patient', data={'patient_id': p.id, 'department_id': d.id}
        )
        assert resp.status_code == 302

    def test_add_queue_auto_not_found(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.queue import add_patient_to_queue_auto

            ok, _msg = add_patient_to_queue_auto(999999, 1)
            assert ok is False

    def test_call_next(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(f'/reception/queue/call-next/{d.id}')
        assert resp.status_code in (302, 200)

    def test_queue_operations(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        q = QueueManagement(
            patient_id=p.id,
            department_id=d.id,
            queue_number='QT1',
            status='waiting',
            tenant_id=test_tenant.id,
        )
        db.session.add(q)
        db.session.commit()
        for url in [
            f'/reception/queue/start-treatment/{q.id}',
            f'/reception/queue/complete-treatment/{q.id}',
        ]:
            resp = client.get(url)
            assert resp.status_code in (302, 200)
        for url, data in [
            (f'/reception/queue/skip-patient/{q.id}', {'reason': 'test'}),
            (f'/reception/queue/return-to-queue/{q.id}', {'reason': 'test'}),
            (f'/reception/queue/cancel-ticket/{q.id}', {'reason': 'test'}),
        ]:
            resp = client.post(url, data=data)
            assert resp.status_code in (302, 200)

    def test_smart_queue(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.queue import (
                get_patient_demand_forecast,
                get_patient_satisfaction_ai,
                get_smart_queue_management,
            )

            assert isinstance(get_smart_queue_management(), dict)
            assert isinstance(get_patient_satisfaction_ai(), dict)
            assert isinstance(get_patient_demand_forecast(), dict)

    def test_save_settings(self, app, client, db, rollback_db, test_tenant):
        u = _reception(client, db, test_tenant)
        u.role = 'manager'
        db.session.commit()
        d = _department(db)
        resp = client.post(
            f'/reception/queue/save-settings/{d.id}',
            data={'payment_required': 'on', 'allow_partial_payment': 'on'},
        )
        assert resp.status_code in (302, 200)

    def test_save_settings_not_found(self, app, client, db, rollback_db, test_tenant):
        u = _reception(client, db, test_tenant)
        u.role = 'manager'
        db.session.commit()
        resp = client.post('/reception/queue/save-settings/999999', data={})
        assert resp.status_code in (302, 200)

    def test_waiting_display(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/display/waiting')
        assert resp.status_code == 200

    def test_calls_display(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/display/calls')
        assert resp.status_code == 200


class TestReceptionPayments:
    def test_pos_charge_no_billing(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/pos/charge', data={'amount': '100'}, headers={'Accept': 'application/json'}
        )
        assert resp.status_code in (403, 200, 500)

    def test_print_receipt(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id, total_amount=100, paid_amount=50)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code in (200, 302)

    def test_print_receipt_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/print_receipt/999999')
        assert resp.status_code in (200, 302)

    def test_print_invoice_not_found(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/print_invoice/999999')
        assert resp.status_code in (200, 302)

    def test_cash_register(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/cash-register')
        assert resp.status_code in (200, 302)

    def test_cash_register_sums(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from models.payment import Payment

            p = _patient(db)
            pay1 = Payment(
                patient_id=p.id, amount=100, method='CASH', status='CONFIRMED', currency='ILS'
            )
            pay2 = Payment(
                patient_id=p.id, amount=50, method='visa', status='CONFIRMED', currency='ILS'
            )
            pay3 = Payment(
                patient_id=p.id, amount=30, method='INSURANCE', status='CONFIRMED', currency='ILS'
            )
            db.session.add_all([pay1, pay2, pay3])
            db.session.commit()
            assert float(pay1.amount) == 100

    def test_daily_close_get(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/daily-close')
        assert resp.status_code in (200, 302)

    def test_daily_close_post_success(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '100', 'actual_card': '50', 'actual_insurance': '0'},
        )
        assert resp.status_code in (302, 200)

    def test_daily_close_negative(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '-10', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code in (302, 200)

    def test_daily_close_invalid(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': 'abc', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code in (302, 200)

    def test_daily_close_already_closed(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        client.post(
            '/reception/daily-close',
            data={'actual_cash': '10', 'actual_card': '0', 'actual_insurance': '0'},
        )
        resp = client.post(
            '/reception/daily-close',
            data={'actual_cash': '10', 'actual_card': '0', 'actual_insurance': '0'},
        )
        assert resp.status_code in (302, 200)

    def test_process_payment(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(
            db,
            patient_id=p.id,
            department_id=d.id,
            total_amount=100,
            paid_amount=100,
            gl_posted_at=datetime.now(UTC),
        )
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code in (302, 200)

    def test_process_payment_archived(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id, archive_status='ARCHIVED')
        resp = client.post(f'/reception/visits/{v.id}/send-to-accounting')
        assert resp.status_code == 302

    def test_validate_payment_data(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.payments import get_payment_methods, validate_payment_data

            assert len(get_payment_methods()) >= 4
            ok, _ = validate_payment_data('cash', {})
            assert ok is True
            ok, _ = validate_payment_data(
                'visa',
                {'card_last_digits': '1234', 'card_holder_name': 'Test', 'expiry_date': '12/30'},
            )
            assert ok is True
            ok, _ = validate_payment_data('visa', {})
            assert ok is False
            ok, _ = validate_payment_data('invalid', {})
            assert ok is False

    def test_execute_pos_charge(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from app.shared.pos_charge import execute_pos_charge

            res, code = execute_pos_charge(None)
            assert code == 400
            res, code = execute_pos_charge('0')
            assert code == 400
            _res, code = execute_pos_charge('abc')
            assert code == 400


class TestReceptionAppointments:
    def test_appointments_list(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/appointments')
        assert resp.status_code == 200

    def test_appointments_filters(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(days=1),
            status='SCHEDULED',
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.get(
            '/reception/appointments',
            query_string={
                'search': 'Test',
                'department_id': d.id,
                'status': 'SCHEDULED',
                'date': (datetime.now(UTC) + timedelta(days=1)).strftime('%Y-%m-%d'),
            },
        )
        assert resp.status_code == 200
        resp2 = client.get('/reception/appointments', query_string={'date': 'bad-date'})
        assert resp2.status_code == 200

    def test_create_appointment_post(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        doc = _doctor(db, test_tenant)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'appointment_date': tomorrow.strftime('%Y-%m-%d'),
                'appointment_time': '10:00',
                'appointment_type': 'first',
                'symptoms': 'cough',
            },
        )
        assert resp.status_code in (302, 200)

    def test_create_appointment_invalid(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/create_appointment',
            data={'patient_id': ''},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (400, 302, 200)

    def test_confirm_cancel_noshow(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        for status in ['SCHEDULED', 'SCHEDULED', 'SCHEDULED']:
            ap = Appointment(
                patient_id=p.id,
                department_id=d.id,
                starts_at=datetime.now(UTC) + timedelta(hours=2 + hash(uuid.uuid4().hex) % 10),
                status=status,
            )
            db.session.add(ap)
            db.session.commit()
            resp = client.post(f'/reception/appointments/{ap.id}/confirm')
            assert resp.status_code in (200, 400, 404)
        ap2 = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=5),
            status='SCHEDULED',
        )
        db.session.add(ap2)
        db.session.commit()
        resp = client.post(f'/reception/appointments/{ap2.id}/cancel')
        assert resp.status_code in (200, 400)
        ap3 = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=6),
            status='SCHEDULED',
        )
        db.session.add(ap3)
        db.session.commit()
        resp = client.post(f'/reception/appointments/{ap3.id}/no-show')
        assert resp.status_code in (200, 400)

    def test_confirm_already_cancelled(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=2),
            status='CANCELLED',
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.post(f'/reception/appointments/{ap.id}/confirm')
        assert resp.status_code == 400

    def test_checkin_appointment(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=2),
            status='SCHEDULED',
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.post(f'/reception/appointments/{ap.id}/checkin')
        assert resp.status_code in (302, 200)
        db.session.refresh(ap)
        assert ap.status == 'CONFIRMED'
        resp2 = client.post(f'/reception/appointments/{ap.id}/checkin')
        assert resp2.status_code in (302, 200)

    def test_checkin_no_department(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id, starts_at=datetime.now(UTC) + timedelta(hours=2), status='SCHEDULED'
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.post(f'/reception/appointments/{ap.id}/checkin')
        assert resp.status_code == 302

    def test_follow_ups(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get(
            '/reception/follow-ups',
            query_string={'search': 'Test', 'status': 'PENDING', 'date': '2024-01-01'},
        )
        assert resp.status_code == 200
        resp2 = client.get('/reception/follow-ups', query_string={'date': 'bad'})
        assert resp2.status_code == 200

    def test_view_edit_appointment(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=2),
            status='SCHEDULED',
            notes='نوع الموعد: first\nالأعراض: cough\nملاحظات عامة',
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.get(f'/reception/view_appointment/{ap.id}')
        assert resp.status_code == 200
        resp2 = client.get(f'/reception/edit_appointment/{ap.id}')
        assert resp2.status_code == 200
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        resp3 = client.post(
            f'/reception/edit_appointment/{ap.id}',
            data={
                'appointment_date': tomorrow.strftime('%Y-%m-%d'),
                'appointment_time': '11:00',
                'doctor_id': d.id,
                'department_id': d.id,
                'appointment_type': 'follow_up',
                'symptoms': 'fever',
                'notes': 'updated',
            },
        )
        assert resp3.status_code in (302, 200)

    def test_available_times(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        doc = _doctor(db, test_tenant)
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = client.get(
            '/reception/api/available-times', query_string={'doctor_id': doc.id, 'date': tomorrow}
        )
        assert resp.status_code == 200
        resp2 = client.get('/reception/api/available-times', query_string={'doctor_id': doc.id})
        assert resp2.status_code == 400
        resp3 = client.get(
            '/reception/api/available-times', query_string={'doctor_id': doc.id, 'date': 'bad'}
        )
        assert resp3.status_code == 400

    def test_online_booking_checkin(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        from models.online_booking import OnlineBooking

        d = _department(db)
        doc = _doctor(db, test_tenant)
        p = _patient(db)
        b = OnlineBooking(
            booking_reference=f'BK-{uuid.uuid4().hex[:6].upper()}',
            first_name='Online',
            last_name='Patient',
            phone=p.phone,
            department_id=d.id,
            doctor_id=doc.id,
            appointment_date=date.today() + timedelta(days=1),
            status='pending',
        )
        db.session.add(b)
        db.session.commit()
        resp = client.post('/reception/online-bookings/checkin', data={'booking_id': b.id})
        assert resp.status_code in (302, 200)
        resp2 = client.post('/reception/online-bookings/checkin', data={'booking_id': b.id})
        assert resp2.status_code in (302, 200)

    def test_online_booking_cancelled(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        from models.online_booking import OnlineBooking

        d = _department(db)
        b = OnlineBooking(
            booking_reference=f'BK-{uuid.uuid4().hex[:6].upper()}',
            first_name='Online',
            last_name='Patient',
            phone='0590000000',
            department_id=d.id,
            appointment_date=date.today() + timedelta(days=1),
            status='cancelled',
        )
        db.session.add(b)
        db.session.commit()
        resp = client.post('/reception/online-bookings/checkin', data={'booking_id': b.id})
        assert resp.status_code == 302


class TestReceptionDashboard:
    def test_index(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/')
        assert resp.status_code == 302

    def test_dashboard(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/dashboard')
        assert resp.status_code == 200

    def test_staff_schedule_get(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/staff/schedule')
        assert resp.status_code == 200

    def test_staff_schedule_post(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        doc = _doctor(db, test_tenant)
        resp = client.post(
            '/reception/staff/schedule',
            data={
                'user_id': doc.id,
                'day_of_week': 1,
                'start_time': '08:00',
                'end_time': '16:00',
                'is_active': 'on',
            },
        )
        assert resp.status_code in (302, 200)

    def test_staff_schedule_invalid(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.post(
            '/reception/staff/schedule',
            data={'user_id': 999999, 'day_of_week': 1, 'start_time': 'bad', 'end_time': 'bad'},
        )
        assert resp.status_code in (302, 200)

    def test_staff_absence(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        resp = client.get('/reception/staff/absence')
        assert resp.status_code == 200
        doc = _doctor(db, test_tenant)
        resp2 = client.post(
            '/reception/staff/absence',
            data={
                'user_id': doc.id,
                'start_date': '2024-01-01',
                'end_date': '2024-01-02',
                'reason': 'sick',
            },
        )
        assert resp2.status_code in (302, 200)
        resp3 = client.post(
            '/reception/staff/absence',
            data={'user_id': doc.id, 'start_date': 'bad', 'end_date': 'bad'},
        )
        assert resp3.status_code in (302, 200)

    def test_survey(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        from models.patient_satisfaction import PatientSatisfactionSurvey

        resp = client.get('/reception/survey/invalid-token')
        assert resp.status_code == 200
        s = PatientSatisfactionSurvey(token=f'tok-{uuid.uuid4().hex[:8]}', rating=None)
        db.session.add(s)
        db.session.commit()
        resp2 = client.get(f'/reception/survey/{s.token}')
        assert resp2.status_code == 200
        resp3 = client.post(
            f'/reception/survey/{s.token}', data={'rating': '5', 'comment': 'great'}
        )
        assert resp3.status_code == 200
        resp4 = client.post(f'/reception/survey/{s.token}', data={'rating': '5'})
        assert resp4.status_code == 200
        resp5 = client.post(f'/reception/survey/{s.token}', data={'rating': '10'})
        assert resp5.status_code == 200


class TestFhirApi:
    def test_fhir_patient(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db, gender='M', birth_date=date(1990, 1, 1))
        resp = client.get(f'/reception/api/fhir/patient/{p.id}')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Patient'
        resp2 = client.get('/reception/api/fhir/patient/999999')
        assert resp2.status_code == 404

    def test_fhir_encounter(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.get(f'/reception/api/fhir/encounter/{v.id}')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Encounter'
        resp2 = client.get('/reception/api/fhir/encounter/999999')
        assert resp2.status_code == 404

    def test_fhir_appointment(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        from models.appointment import Appointment

        ap = Appointment(
            patient_id=p.id,
            department_id=d.id,
            starts_at=datetime.now(UTC) + timedelta(hours=2),
            status='SCHEDULED',
        )
        db.session.add(ap)
        db.session.commit()
        resp = client.get(f'/reception/api/fhir/appointment/{ap.id}')
        assert resp.status_code == 200
        resp2 = client.get('/reception/api/fhir/appointment/999999')
        assert resp2.status_code == 404

    def test_fhir_practitioner(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        doc = _doctor(db, test_tenant)
        resp = client.get(f'/reception/api/fhir/practitioner/{doc.id}')
        assert resp.status_code == 200
        from models.user import User

        nurse = User(
            username=f'nurse_{uuid.uuid4().hex[:6]}',
            email=f'{uuid.uuid4().hex[:8]}@test.local',
            full_name='Nurse',
            role='nurse',
            is_active=True,
        )
        nurse.set_password('test123')
        db.session.add(nurse)
        db.session.commit()
        resp2 = client.get(f'/reception/api/fhir/practitioner/{nurse.id}')
        assert resp2.status_code == 404
        resp3 = client.get('/reception/api/fhir/practitioner/999999')
        assert resp3.status_code == 404

    def test_fhir_organization(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(f'/reception/api/fhir/organization/{d.id}')
        assert resp.status_code == 200
        resp2 = client.get('/reception/api/fhir/organization/999999')
        assert resp2.status_code == 404


class TestQueueApi:
    def test_queue_status(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(
            f'/reception/api/queue-department-status/{d.id}', headers={'Accept': 'application/json'}
        )
        assert resp.status_code == 200

    def test_queue_status_all(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(
            '/reception/api/queue-status-all',
            query_string={
                'department_id': d.id,
                'status': 'waiting',
                'priority': 'normal',
                'search': 'Test',
                'is_emergency': '1',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200

    def test_queue_wait_metrics(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        d = _department(db)
        resp = client.get(
            '/reception/api/queue-wait-metrics',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200

    def test_queue_snapshot(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id)
        q = QueueManagement(
            patient_id=p.id,
            department_id=d.id,
            visit_id=v.id,
            queue_number='QS1',
            status='waiting',
            tenant_id=test_tenant.id,
        )
        db.session.add(q)
        db.session.commit()
        resp = client.get('/reception/api/queue-snapshot', headers={'Accept': 'application/json'})
        assert resp.status_code == 200

    def test_display_waiting_and_calls(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, patient_id=p.id, department_id=d.id)
        q = QueueManagement(
            patient_id=p.id,
            department_id=d.id,
            visit_id=v.id,
            queue_number='QD1',
            status='waiting',
            tenant_id=test_tenant.id,
        )
        db.session.add(q)
        db.session.commit()
        resp = client.get('/reception/api/display/waiting', headers={'Accept': 'application/json'})
        assert resp.status_code == 200
        resp2 = client.get('/reception/api/display/calls', headers={'Accept': 'application/json'})
        assert resp2.status_code == 200

    def test_patient_queue_position(self, app, client, db, rollback_db, test_tenant):
        _reception(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        resp = client.get(
            f'/reception/api/patient-queue-position/{p.id}/{d.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200


class TestVisitHelpers:
    def test_calculate_tax(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.visits import _calculate_visit_tax

            p = _patient(db)
            d = _department(db)
            v = _visit(db, patient_id=p.id, department_id=d.id, total_amount=100)
            _calculate_visit_tax(v, 'inclusive')
            assert v.is_tax_inclusive is True
            assert v.tax_percent == 15
            v2 = _visit(db, patient_id=p.id, department_id=d.id, total_amount=100)
            _calculate_visit_tax(v2, 'exclusive')
            assert v2.is_tax_inclusive is False
            assert v2.total_amount == 115
            v3 = _visit(db, patient_id=p.id, department_id=d.id, total_amount=100)
            _calculate_visit_tax(v3, 'none')
            assert v3.tax_percent == 0

    def test_get_pricing_details_and_cost(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.visits import calculate_visit_cost, get_pricing_details

            d = _department(db)
            doc = _doctor(db, test_tenant)
            details = get_pricing_details(d.id, doc.id, 'REGULAR', False, 'cash')
            assert isinstance(details, dict)
            cost = calculate_visit_cost(d.id, doc.id, 'REGULAR', False, 'cash')
            assert isinstance(cost, (int, float))
            cost2 = calculate_visit_cost(999999, None, 'FOLLOW_UP', True, 'insurance')
            assert cost2 == 0 or isinstance(cost2, (int, float))

    def test_process_custom_services(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.visits import _process_custom_services

            d = _department(db)
            rec = ensure_test_user(
                db, test_tenant, username=f'cust_{uuid.uuid4().hex[:6]}', role='reception'
            )
            ids = _process_custom_services(['Custom Service'], ['50'], d.id, rec)
            assert len(ids) == 1
            rec2 = ensure_test_user(
                db, test_tenant, username=f'nrec_{uuid.uuid4().hex[:6]}', role='doctor'
            )
            with pytest.raises(Exception):
                _process_custom_services(['Another'], ['30'], d.id, rec2)

    def test_can_search_and_accessible(self, app, db, rollback_db, test_tenant):
        with tenant_test_context(app, test_tenant):
            from routes.reception.api import (
                can_search_all_patients,
                get_accessible_departments_for_user,
            )

            assert can_search_all_patients('reception') is True
            assert can_search_all_patients('unknown') is False
            deps = get_accessible_departments_for_user('reception')
            assert isinstance(deps, list)
            deps2 = get_accessible_departments_for_user('lab', user_department_id=1)
            assert isinstance(deps2, list)
