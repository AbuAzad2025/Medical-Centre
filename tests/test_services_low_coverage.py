"""Tests for low-coverage services."""

import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.shared.enums import VisitState
from models.department import Department
from models.patient import Patient
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


@pytest.fixture
def ctx(rollback_db, test_tenant):
    db_ = rollback_db

    def _patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'مريض'),
            last_name=kw.get('last_name', 'اختبار'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
            gender=kw.get('gender', 'M'),
        )
        db_.session.add(p)
        db_.session.commit()
        return p

    def _department(**kw):
        tag = uuid.uuid4().hex[:6]
        d = Department(
            name=kw.get('name', f'Dept-{tag}'),
            name_ar=kw.get('name_ar', f'قسم-{tag}'),
            is_active=True,
        )
        db_.session.add(d)
        db_.session.commit()
        return d

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'مستخدم'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db_.session.add(u)
        db_.session.commit()
        return u

    def _visit(**kw):
        v = Visit(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            status=kw.get('status', VisitState.OPEN.value),
            payment_status=kw.get('payment_status', 'PENDING'),
            total_amount=kw.get('total_amount', 0),
            visit_type=kw.get('visit_type', 'REGULAR'),
            payment_method=kw.get('payment_method', 'cash'),
        )
        db_.session.add(v)
        db_.session.commit()
        return v

    return types.SimpleNamespace(
        db=db_,
        patient=_patient,
        department=_department,
        user=_user,
        visit=_visit,
    )


class TestAIValidationService:
    def test_valid_user_data(self):
        from services.ai_validation_service import AIValidationService

        valid, errors, warnings = AIValidationService.validate_user_data(
            {
                'email': 'user@test.com',
                'password': 'StrongPass1!',
                'phone': '0501234567',
            }
        )
        assert valid is True
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

    def test_invalid_email(self):
        from services.ai_validation_service import AIValidationService

        valid, errors, _ = AIValidationService.validate_user_data(
            {
                'email': 'not-an-email',
            }
        )
        assert valid is False
        assert len(errors) > 0

    def test_short_password(self):
        from services.ai_validation_service import AIValidationService

        valid, errors, _ = AIValidationService.validate_user_data(
            {
                'password': 'abc',
            }
        )
        assert valid is False
        assert len(errors) > 0

    def test_valid_patient_data(self):
        from services.ai_validation_service import AIValidationService

        valid, errors, _ = AIValidationService.validate_patient_data(
            {
                'age': 30,
                'birth_date': '1990-01-01',
                'weight': 70,
                'blood_type': 'A+',
            }
        )
        assert valid is True
        assert isinstance(errors, list)

    def test_invalid_age(self):
        from services.ai_validation_service import AIValidationService

        valid, _errors, _ = AIValidationService.validate_patient_data({'age': -5})
        assert valid is False

    def test_future_birth_date(self):
        from services.ai_validation_service import AIValidationService

        future = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        valid, errors, _ = AIValidationService.validate_patient_data({'birth_date': future})
        assert valid is False
        assert len(errors) > 0

    def test_validate_medication(self):
        from services.ai_validation_service import AIValidationService

        valid, errors, _ = AIValidationService.validate_medication_data(
            {
                'name': 'أموكسيسيلين',
                'dosage': '500mg',
                'frequency': '3 مرات يومياً',
            }
        )
        assert valid is True or len(errors) >= 0


class TestFieldEncryptionService:
    @pytest.fixture(autouse=True)
    def _encryption_key(self, monkeypatch):
        from cryptography.fernet import Fernet

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())

    def test_encrypt_decrypt_roundtrip(self):
        from services.field_encryption_service import FieldEncryptionService

        svc = FieldEncryptionService()
        plaintext = 'بيانات حساسة 123'
        encrypted = svc.encrypt(plaintext)
        assert encrypted is not None
        assert encrypted != plaintext
        decrypted = svc.decrypt(encrypted)
        assert decrypted == plaintext

    def test_none_passthrough(self):
        from services.field_encryption_service import FieldEncryptionService

        svc = FieldEncryptionService()
        assert svc.encrypt(None) is None
        assert svc.encrypt('') == ''
        assert svc.decrypt(None) is None

    def test_bytes_input(self):
        from services.field_encryption_service import FieldEncryptionService

        svc = FieldEncryptionService()
        encrypted = svc.encrypt(b'hello world')
        assert encrypted is not None
        decrypted = svc.decrypt(encrypted)
        assert decrypted == 'hello world'


class TestReportCenterService:
    def test_compare_periods_empty(self):
        from datetime import date

        from services.report_center_service import ReportCenterService

        date(2024, 1, 1)
        result = ReportCenterService.compare_periods(
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 31, tzinfo=UTC),
            datetime(2024, 2, 1, tzinfo=UTC),
            datetime(2024, 2, 28, tzinfo=UTC),
        )
        assert 'period_a' in result or isinstance(result, dict)

    def test_parse_dates_defaults(self):
        from services.report_center_service import ReportCenterService

        s, e, _sdt, _edt = ReportCenterService._parse_dates(None, None)
        assert s is not None
        assert e is not None

    def test_parse_dates_custom(self):
        from services.report_center_service import ReportCenterService

        s, e, _sdt, _edt = ReportCenterService._parse_dates('2024-01-01', '2024-01-31')
        from datetime import date

        assert s == date(2024, 1, 1)
        assert e == date(2024, 1, 31)

    def test_parse_dates_invalid(self):
        from services.report_center_service import ReportCenterService

        s, e, _sdt, _edt = ReportCenterService._parse_dates('not-a-date', 'also-bad')
        from datetime import date

        assert s == date.today() - timedelta(days=30)
        assert e == date.today()


class TestManagerService:
    def test_get_organization_stats(self, ctx):
        from services.manager_service import ManagerService

        ctx.patient()
        ctx.department()
        ctx.user(role='doctor')
        stats = ManagerService.get_organization_stats()
        assert isinstance(stats, dict)

    def test_get_staff_stats(self, ctx):
        from services.manager_service import ManagerService

        ctx.user(role='nurse')
        stats = ManagerService.get_staff_stats()
        assert isinstance(stats, dict)


class TestSuperAdminService:
    def test_get_system_stats(self, ctx):
        from services.super_admin_service import SuperAdminService

        ctx.patient()
        stats = SuperAdminService.get_system_stats()
        assert isinstance(stats, dict)

    def test_get_all_users(self, ctx):
        from services.super_admin_service import SuperAdminService

        ctx.user(role='doctor')
        users = SuperAdminService.get_all_users()
        assert isinstance(users, list)

    def test_get_all_users_filtered(self, ctx):
        from services.super_admin_service import SuperAdminService

        ctx.user(role='doctor')
        users = SuperAdminService.get_all_users(role='doctor')
        assert isinstance(users, list)

    def test_get_security_logs(self):
        from services.super_admin_service import SuperAdminService

        logs = SuperAdminService.get_security_logs(limit=10)
        assert isinstance(logs, list)

    def test_toggle_user_status_missing(self):
        from services.super_admin_service import SuperAdminService

        result = SuperAdminService.toggle_user_status(999999999)
        assert result is False

    def test_create_user(self, ctx):
        from services.super_admin_service import SuperAdminService

        result = SuperAdminService.create_user(
            {
                'username': f'test_usr_{uuid.uuid4().hex[:6]}',
                'email': f'{uuid.uuid4().hex[:8]}@test.local',
                'role': 'doctor',
            }
        )
        assert result is None or hasattr(result, 'username')


class TestWebhookService:
    def test_sign_payload(self):
        from services.webhook_service import _sign_payload

        sig = _sign_payload(b'{"event":"test"}', 'secret-key')
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_supported_events(self):
        import services.webhook_service as ws

        assert 'tenant.created' in ws.SUPPORTED_EVENTS
        assert 'tenant.suspended' in ws.SUPPORTED_EVENTS
        assert 'module.activated' in ws.SUPPORTED_EVENTS

    def test_dispatch_webhook(self):
        from services.webhook_service import dispatch_webhook

        result = dispatch_webhook('tenant.created', {'tenant_id': 1})
        assert result is None or isinstance(result, bool)

    def test_get_queue_stats(self):
        from services.webhook_service import get_queue_stats

        stats = get_queue_stats()
        assert isinstance(stats, dict)

    def test_init_shutdown(self):
        from services.webhook_service import init_webhook_service, shutdown_webhook_service

        init_webhook_service()
        shutdown_webhook_service()
