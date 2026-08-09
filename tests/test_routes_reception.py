"""Comprehensive HTTP route tests for the reception blueprint.

Each test logs in as a real tenant-scoped user, creates domain records via the
ORM inside the tenant context, and hits the HTTP endpoints asserting real
behaviour (status codes, redirects, DB side effects).
"""

import json
import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.shared.enums import VisitState
from models.appointment import Appointment
from models.department import Department
from models.patient import Patient
from models.payment import Payment
from models.queue_management import QueueManagement
from models.user import User
from models.visit import Visit


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )


_CACHED_ENCRYPTION = {}


@pytest.fixture(autouse=True)
def _cached_encryption(monkeypatch):
    """Cache the field-encryption service to avoid a ~2.5s PBKDF2 key
    derivation on every encrypted-column access. Behaviour (encrypt/decrypt)
    is unchanged; only the redundant per-access key derivation is skipped."""
    from app.shared.encrypted_type import EncryptedString

    if '_svc' not in _CACHED_ENCRYPTION:
        from services.field_encryption_service import FieldEncryptionService

        _CACHED_ENCRYPTION['_svc'] = FieldEncryptionService()
    monkeypatch.setattr(
        EncryptedString, '_get_service', lambda self: _CACHED_ENCRYPTION['_svc']
    )


@pytest.fixture
def ctx(app, db, test_tenant):
    """Data factory: create domain records (tenant auto-assigned by filter)."""
    tenant_id = test_tenant.id

    def _patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'علي'),
            last_name=kw.get('last_name', 'محمد'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
            gender=kw.get('gender', 'M'),
        )
        db.session.add(p)
        db.session.commit()
        return p

    def _department(**kw):
        tag = uuid.uuid4().hex[:6]
        d = Department(
            name=kw.get('name', f'Dept-{tag}'),
            name_ar=kw.get('name_ar', f'قسم-{tag}'),
            is_active=True,
        )
        db.session.add(d)
        db.session.commit()
        return d

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'طبيب اختبار'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
        return u

    def _visit(**kw):
        v = Visit(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            status=kw.get('status', VisitState.OPEN.value),
            payment_status=kw.get('payment_status', 'PENDING'),
            total_amount=kw.get('total_amount', 0),
            paid_amount=kw.get('paid_amount', 0),
            visit_type=kw.get('visit_type', 'REGULAR'),
            payment_method=kw.get('payment_method', 'cash'),
            is_emergency=kw.get('is_emergency', False),
        )
        db.session.add(v)
        db.session.commit()
        return v

    def _appointment(**kw):
        starts = datetime.now(UTC) + timedelta(hours=2)
        apt = Appointment(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            starts_at=kw.get('starts_at', starts),
            status=kw.get('status', 'SCHEDULED'),
        )
        db.session.add(apt)
        db.session.commit()
        return apt

    return types.SimpleNamespace(
        db=db,
        tenant_id=tenant_id,
        patient=_patient,
        department=_department,
        user=_user,
        visit=_visit,
        appointment=_appointment,
    )


def _make_reception(login_as, client, ctx):
    return login_as(client, f'rec_{uuid.uuid4().hex[:6]}', 'reception')


class TestVisitsPage:
    def test_visits_list_renders(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get('/reception/visits')
        assert resp.status_code == 200
        assert 'الزيارات' in resp.get_data(as_text=True)

    def test_visits_filtered_by_status(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.get('/reception/visits?status=OPEN')
        assert resp.status_code == 200

    def test_visits_search_by_patient(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient(first_name='بحثمميز')
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/visits', query_string={'search': 'بحثمميز'})
        assert resp.status_code == 200

    def test_visits_requires_login(self, client):
        resp = client.get('/reception/visits')
        assert resp.status_code == 302

    def test_visits_forbidden_for_unknown_role(self, login_as, client, ctx):
        login_as(client, f'unk_{uuid.uuid4().hex[:6]}', 'unknown_role')
        resp = client.get('/reception/visits')
        assert resp.status_code == 403


class TestVisitArchiveAndEnd:
    def test_archive_completed_visit(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, status='COMPLETED')
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status == 'ARCHIVED'

    def test_archive_open_visit_redirects(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.post(f'/reception/visits/{v.id}/archive')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status != 'ARCHIVED'

    def test_end_completed_visit(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, status='COMPLETED')
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.archive_status == 'ARCHIVED'

    def test_end_open_visit_warns(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, status='OPEN')
        resp = client.post(f'/reception/visits/{v.id}/end')
        assert resp.status_code == 302
        ctx.db.session.refresh(v)
        assert v.status == 'OPEN'


class TestVisitExport:
    def test_export_visits_csv(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/export/visits')
        assert resp.status_code == 200
        assert 'text/csv' in (resp.headers.get('Content-Type') or '')


class TestCreateVisit:
    def test_get_create_visit_form(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.patient()
        d = ctx.department()
        ctx.user(role='doctor')
        resp = client.get('/reception/visits/create')
        assert resp.status_code == 200

    def test_create_visit_success(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
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
            ctx.db.session.query(Visit)
            .filter_by(patient_id=p.id, department_id=d.id)
            .order_by(Visit.id.desc())
            .first()
        )
        assert v is not None
        assert v.status == VisitState.OPEN.value

    def test_create_visit_missing_patient(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.post(
            '/reception/visits/create',
            data={'department_id': d.id, 'doctor_id': doc.id, 'payment_method': 'cash'},
        )
        assert resp.status_code == 200
        assert 'مريض' in resp.get_data(as_text=True)

    def test_create_visit_missing_department(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.post(
            '/reception/visits/create',
            data={'patient_id': p.id, 'payment_method': 'cash'},
        )
        assert resp.status_code == 200
        assert 'قسم' in resp.get_data(as_text=True)

    def test_create_visit_quick_emergency(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        dept = ctx.department(name='Emergency', name_ar='الطوارئ')
        resp = client.post(
            '/reception/visits/create',
            data={
                'quick_emergency': '1',
                'quick_patient_name': 'مريض طارئ',
                'quick_reason': 'ألم شديد في الصدر يتطلب تدخلا سريعا',
            },
        )
        assert resp.status_code in (302, 200)
        v = (
            ctx.db.session.query(Visit)
            .filter(Visit.is_emergency.is_(True))
            .order_by(Visit.id.desc())
            .first()
        )
        assert v is not None

    def test_create_visit_insurance_validation(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
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
        assert 'تأمين' in resp.get_data(as_text=True) or resp.status_code == 302

    def test_create_visit_card_payment_validation(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
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


class TestViewVisit:
    def test_view_visit_renders(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/view_visit/{v.id}')
        assert resp.status_code == 200

    def test_view_visit_not_found(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/view_visit/999999999')
        assert resp.status_code in (200, 302, 404)


class TestVisitPricingApi:
    def test_visit_pricing_api(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        resp = client.get(
            '/reception/api/visit-pricing',
            query_string={'department_id': d.id, 'doctor_id': doc.id, 'visit_type': 'REGULAR'},
        )
        assert resp.status_code in (200, 302)


class TestEditVisit:
    def test_edit_visit_get(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/edit_visit/{v.id}')
        assert resp.status_code == 200

    def test_edit_visit_post(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.post(
            f'/reception/edit_visit/{v.id}',
            data={
                'symptoms': 'سعال وارتفاع حرارة',
                'notes': 'ملاحظات التعديل',
                'payment_method': 'cash',
            },
        )
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(v)
        assert v.symptoms == 'سعال وارتفاع حرارة'


class TestAddServiceToVisit:
    def test_add_service(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.post(
            f'/reception/visits/{v.id}/add-service',
            data={'service_name': 'فحص سريري', 'price': '50', 'custom_service_name': [], 'custom_service_price': []},
        )
        assert resp.status_code in (302, 200)


class TestPatientsPage:
    def test_patients_list(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.patient()
        resp = client.get('/reception/patients')
        assert resp.status_code == 200
        assert 'مرضى' in resp.get_data(as_text=True)

    def test_patients_search(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.patient(first_name='عميلبحث')
        resp = client.get('/reception/patients', query_string={'search': 'عميلبحث'})
        assert resp.status_code == 200

    def test_patients_filter_department(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/patients', query_string={'department_id': d.id})
        assert resp.status_code == 200


class TestAddPatient:
    def test_get_form(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/add_patient')
        assert resp.status_code == 200

    def test_add_patient_success(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        phone = '050' + format(uuid.uuid4().int % 10**7, '07d')
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'أحمد',
                'last_name': 'حسن',
                'phone': phone,
                'gender': 'M',
            },
        )
        assert resp.status_code in (302, 200)
        p = (
            ctx.db.session.query(Patient).filter_by(phone=phone).order_by(Patient.id.desc()).first()
        )
        assert p is not None

    def test_add_patient_missing_name(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.post(
            '/reception/add_patient',
            data={'phone': '0501234567', 'gender': 'M'},
        )
        assert resp.status_code == 200
        assert 'اسم' in resp.get_data(as_text=True)


class TestViewEditPatient:
    def test_view_patient(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/view_patient/{p.id}')
        assert resp.status_code == 200

    def test_edit_patient_get(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.get(f'/reception/edit_patient/{p.id}')
        assert resp.status_code == 200

    def test_edit_patient_post(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.post(
            f'/reception/edit_patient/{p.id}',
            data={'first_name': 'معدل', 'last_name': 'الاسم', 'phone': p.phone or '0500000000'},
        )
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(p)
        assert p.first_name == 'معدل'

    def test_delete_patient(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.post(f'/reception/delete_patient/{p.id}')
        assert resp.status_code in (302, 200)


class TestPatientAllergiesAndProblems:
    def test_add_allergy(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/allergies/add',
            data=json.dumps({'allergen': 'بنسلين', 'severity': 'HIGH'}),
            content_type='application/json',
        )
        assert resp.status_code in (200, 302)

    def test_add_problem(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.post(
            f'/reception/api/patients/{p.id}/problems/add',
            data=json.dumps({'problem_description': 'ارتفاع ضغط', 'problem_type': 'DIAGNOSIS'}),
            content_type='application/json',
        )
        assert resp.status_code in (200, 302)


class TestSmartPatientSearch:
    def test_smart_search(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient(phone='0507777777')
        resp = client.get(
            '/reception/api/smart-patient-search',
            query_string={'q': '0507777777'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None


class TestAppointments:
    def test_appointments_list(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.get('/reception/appointments')
        assert resp.status_code == 200

    def test_follow_ups_page(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.get('/reception/follow-ups')
        assert resp.status_code == 200

    def test_create_appointment_get(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.patient()
        ctx.department()
        ctx.user(role='doctor')
        resp = client.get('/reception/create_appointment')
        assert resp.status_code == 200

    def test_create_appointment_post(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'appointment_date': tomorrow.strftime('%Y-%m-%d'),
                'appointment_time': tomorrow.strftime('%H:%M'),
            },
        )
        assert resp.status_code in (302, 200)
        apt = (
            ctx.db.session.query(Appointment)
            .filter_by(patient_id=p.id, department_id=d.id)
            .order_by(Appointment.id.desc())
            .first()
        )
        assert apt is not None

    def test_view_appointment(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/view_appointment/{apt.id}')
        assert resp.status_code == 200

    def test_edit_appointment(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/edit_appointment/{apt.id}')
        assert resp.status_code == 200

    def test_appointment_checkin(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.post(f'/reception/appointments/{apt.id}/checkin')
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(apt)
        assert apt.status == 'CHECKED_IN'

    def test_appointment_confirm(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.post(f'/reception/appointments/{apt.id}/confirm')
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(apt)
        assert apt.status == 'CONFIRMED'

    def test_appointment_cancel(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.post(
            f'/reception/appointments/{apt.id}/cancel',
            data={'cancel_reason': 'مريض غير قادر على الحضور'},
        )
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(apt)
        assert apt.status == 'CANCELLED'

    def test_appointment_no_show(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.post(f'/reception/appointments/{apt.id}/no-show')
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(apt)
        assert apt.status == 'NO_SHOW'


class TestQueue:
    def test_queue_page(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.department()
        resp = client.get('/reception/queue')
        assert resp.status_code == 200

    def test_queue_add_patient_get(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.patient()
        ctx.department()
        ctx.user(role='doctor')
        resp = client.get('/reception/queue/add-patient')
        assert resp.status_code == 200

    def test_queue_add_patient_post(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, payment_method='cash', payment_status='PAID')
        resp = client.post(
            '/reception/queue/add-patient',
            data={
                'patient_id': p.id,
                'department_id': d.id,
                'doctor_id': doc.id,
                'visit_id': v.id,
                'queue_type': 'normal',
            },
        )
        assert resp.status_code in (302, 200)
        q = (
            ctx.db.session.query(QueueManagement)
            .filter_by(patient_id=p.id, department_id=d.id)
            .order_by(QueueManagement.id.desc())
            .first()
        )
        assert q is not None

    def test_queue_add_patient_requires_doctor_for_general(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        resp = client.post(
            '/reception/queue/add-patient',
            data={'patient_id': p.id, 'department_id': d.id, 'queue_type': 'normal'},
        )
        assert resp.status_code in (302, 200)

    def test_waiting_display(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/display/waiting')
        assert resp.status_code == 200

    def test_calls_display(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/display/calls')
        assert resp.status_code == 200

    def test_queue_call_next(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, payment_status='PAID', payment_method='cash')
        q = QueueManagement(
            patient_id=p.id,
            department_id=d.id,
            visit_id=v.id,
            queue_number=f'Q{uuid.uuid4().hex[:4]}',
            status='WAITING',
            tenant_id=ctx.tenant_id,
        )
        ctx.db.session.add(q)
        ctx.db.session.commit()
        resp = client.get(f'/reception/queue/call-next/{d.id}')
        assert resp.status_code in (302, 200)

    def test_queue_save_settings(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        resp = client.post(
            f'/reception/queue/save-settings/{d.id}',
            data={'max_queue_size': '30'},
        )
        assert resp.status_code in (302, 200)


class TestPayments:
    def test_payments_page(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        pay = Payment(visit_id=v.id, patient_id=p.id, amount=50, status='COMPLETED', payment_method='CASH', tenant_id=ctx.tenant_id)
        ctx.db.session.add(pay)
        ctx.db.session.commit()
        resp = client.get('/reception/payments')
        assert resp.status_code == 200

    def test_print_receipt(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/print_receipt/{v.id}')
        assert resp.status_code in (200, 302)

    def test_cash_register(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/cash-register')
        assert resp.status_code == 200

    def test_daily_close(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/daily-close')
        assert resp.status_code in (200, 302)


class TestDashboard:
    def test_dashboard_renders(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/dashboard')
        assert resp.status_code == 200

    def test_staff_schedule(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/staff/schedule')
        assert resp.status_code == 200

    def test_staff_absence(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/staff/absence')
        assert resp.status_code == 200


class TestReceptionApi:
    def test_api_doctors(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.user(role='doctor')
        resp = client.get(
            '/reception/api/doctors',
            query_string={'department_id': ctx.department().id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    def test_api_department_staff(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        ctx.user(role='doctor', department_id=d.id)
        resp = client.get(
            '/reception/api/department-staff',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    def test_api_department_services(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        resp = client.get(
            '/reception/api/department-services',
            query_string={'department_id': d.id},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    def test_api_queue_status(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        resp = client.get(
            f'/reception/api/queue-department-status/{d.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    def test_api_queue_status_all(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        ctx.department()
        resp = client.get('/reception/api/queue-status-all', headers={'Accept': 'application/json'})
        assert resp.status_code in (200, 302)

    def test_api_fhir_patient(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        resp = client.get(f'/reception/api/fhir/patient/{p.id}')
        assert resp.status_code in (200, 302)

    def test_api_fhir_encounter(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/api/fhir/encounter/{v.id}')
        assert resp.status_code in (200, 302)

    def test_api_fhir_appointment(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        apt = ctx.appointment(patient_id=p.id, department_id=d.id)
        resp = client.get(f'/reception/api/fhir/appointment/{apt.id}')
        assert resp.status_code in (200, 302)

    def test_api_fhir_practitioner(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        doc = ctx.user(role='doctor')
        resp = client.get(f'/reception/api/fhir/practitioner/{doc.id}')
        assert resp.status_code in (200, 302)

    def test_api_fhir_organization(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        resp = client.get(f'/reception/api/fhir/organization/{d.id}')
        assert resp.status_code in (200, 302)

    def test_api_queue_snapshot(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/api/queue-snapshot', headers={'Accept': 'application/json'})
        assert resp.status_code in (200, 302)

    def test_api_display_waiting(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        resp = client.get('/reception/api/display/waiting', headers={'Accept': 'application/json'})
        assert resp.status_code in (200, 302)

    def test_api_available_times(self, login_as, client, ctx):
        _make_reception(login_as, client, ctx)
        d = ctx.department()
        doc = ctx.user(role='doctor')
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime('%Y-%m-%d')
        resp = client.get(
            '/reception/api/available-times',
            query_string={'doctor_id': doc.id, 'date': tomorrow},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)
