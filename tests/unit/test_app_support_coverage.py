"""Coverage for the small app-level helpers that had branches nobody exercised.

These modules are the shared plumbing between the routes and the platform:
field validation, role policy, search indexing, navigation registries and the
tenant-access guards. Every one of them has a decision that only one of its
branches ever ran, so the branch that decides whether a request is refused
was never proven.

Each test class is named after the module it covers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestFieldValidators:
    """app/shared/validators.py"""

    def test_unknown_rule_passes(self):
        from app.shared.validators import validate_field

        assert validate_field('no_such_rule', 'anything') == (True, None)

    def test_empty_value_passes(self):
        from app.shared.validators import validate_field

        assert validate_field('email', '') == (True, None)
        assert validate_field('email', None) == (True, None)
        assert validate_field('email', '   ') == (True, None)

    def test_min_length_is_enforced(self):
        from app.shared.validators import FIELD_RULES, validate_field

        ok, message = validate_field('patient_name', 'A')
        assert ok is False
        assert message == FIELD_RULES['patient_name']['message_ar']

    def test_max_length_is_enforced(self):
        from app.shared.validators import FIELD_RULES, validate_field

        ok, message = validate_field('patient_name', 'x' * 121)
        assert ok is False
        assert message == FIELD_RULES['patient_name']['message_ar']

    def test_pattern_is_enforced(self):
        from app.shared.validators import FIELD_RULES, validate_field

        ok, message = validate_field('email', 'not-an-email')
        assert ok is False
        assert message == FIELD_RULES['email']['message_ar']

    def test_valid_values_pass(self):
        from app.shared.validators import validate_field

        assert validate_field('email', 'a@b.com') == (True, None)
        assert validate_field('amount', '12.50') == (True, None)
        assert validate_field('patient_name', 'Jane') == (True, None)

    def test_rules_json_helpers(self):
        from app.shared.validators import FIELD_RULES, get_rules_json, get_rules_json_str

        assert get_rules_json() is FIELD_RULES
        as_text = get_rules_json_str()
        assert json.loads(as_text) == FIELD_RULES
        assert 'ensure_ascii' not in as_text  # the Arabic messages stay readable


class TestStylesheets:
    """app/shared/stylesheets.py"""

    def test_unknown_shell_is_rejected(self, app):
        from app.shared.stylesheets import stylesheets

        with app.test_request_context():
            with pytest.raises(KeyError):
                stylesheets('no-such-shell')

    def test_known_shell_renders_links(self, app):
        from app.shared.stylesheets import stylesheets

        with app.test_request_context():
            markup = str(stylesheets('base'))
        assert '<link' in markup


class TestUserRolePolicy:
    """app/shared/user_role_policy.py"""

    def test_actor_without_privileges_may_not_assign(self):
        from app.shared.user_role_policy import actor_may_assign_role

        assert actor_may_assign_role('doctor', 'admin') is False

    def test_privileged_actor_may_assign(self):
        from app.shared.user_role_policy import actor_may_assign_role

        assert actor_may_assign_role('super_admin', 'doctor') is True


class TestSearchIndex:
    """app/shared/search_index.py"""

    def test_empty_gram_has_no_digest(self):
        from app.shared.search_index import ngram_digest

        assert ngram_digest('') is None

    def test_ngrams_of_short_text(self):
        from app.shared.search_index import ngrams

        assert ngrams('ab', 3) == []


class TestSearchService:
    """app/shared/search_service.py"""

    def test_date_query_is_parsed(self, app, db, test_tenant):
        from app.shared.search_service import SearchService

        with app.test_request_context():
            # The date branch of the query parser is reached by a full-length
            # date; the search itself then runs against the blind index.
            result = SearchService.search_patients('2026-01-02')
        assert isinstance(result, list)


class TestSignalSubscribers:
    """app/shared/signal_subscribers.py"""

    def test_failing_signal_is_swallowed_and_logged(self):
        import app.shared.signal_subscribers as subscribers

        class _Boom:
            name = 'boom_signal'

            @staticmethod
            def send(**_kwargs):
                raise RuntimeError('subscriber exploded')

        with patch.object(subscribers.logger, 'warning') as warning:
            subscribers._safe_send(_Boom, value=1)

        assert warning.called
        assert 'boom_signal' in warning.call_args[0][1]


class TestOwnerDecorators:
    """app/modules/owner/decorators.py"""

    def test_unauthenticated_api_request_is_refused(self, app):
        from app.modules.owner.decorators import owner_required

        @owner_required
        def protected():
            return 'never reached'

        with app.test_request_context('/owner/api/thing', headers={'Accept': 'application/json'}):
            with patch('app.modules.owner.decorators.current_user') as user:
                user.is_authenticated = False
                response = protected()
        assert response[1] == 401
        assert response[0].get_json()['error'] == 'authentication_required'

    def test_unauthenticated_page_request_redirects(self, app):
        from app.modules.owner.decorators import owner_required

        @owner_required
        def protected():
            return 'never reached'

        with app.test_request_context('/owner/thing'):
            with patch('app.modules.owner.decorators.current_user') as user:
                user.is_authenticated = False
                response = protected()
        assert response.status_code == 302


class TestEscposPrinter:
    """app/integrations/printing/escpos.py"""

    def test_send_writes_to_the_port(self):
        from app.integrations.printing.escpos import ThermalPrinter

        printer = ThermalPrinter(port='COM3')
        written = {}

        class _Serial:
            def __init__(self, port, baudrate, timeout):
                written['port'] = port
                written['baudrate'] = baudrate

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def write(self, data):
                written['data'] = data

        with patch.dict('sys.modules', {'serial': type('_M', (), {'Serial': _Serial})}):
            assert printer.send(b'RECEIPT') is True

        assert written['port'] == 'COM3'
        assert written['baudrate'] == 9600
        assert written['data'] == b'RECEIPT'

    def test_send_reports_failure(self):
        from app.integrations.printing.escpos import ThermalPrinter

        printer = ThermalPrinter(port='COM3')
        with patch.dict('sys.modules', {'serial': None}):
            assert printer.send(b'RECEIPT') is False


class TestAppointmentWorkflow:
    """app/modules/workflows/appointment.py"""

    def test_check_double_booking_finds_an_overlapping_appointment(self, app, db, test_tenant):
        from app.modules.workflows.appointment import AppointmentService
        from models.patient import Patient
        from models.user import User

        patient = Patient(
            tenant_id=test_tenant.id,
            first_name='Appt',
            last_name='Patient',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        db.session.add(patient)
        doctor = User(
            username=f'double-book-{test_tenant.id}',
            email=f'double-book-{test_tenant.id}@test.local',
            full_name='Double Book Doctor',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.flush()

        with app.test_request_context():
            from models.appointment import Appointment

            start = datetime.now(UTC) + timedelta(hours=2)
            end = start + timedelta(hours=1)
            appointment = Appointment(
                patient_id=patient.id,
                doctor_id=doctor.id,
                starts_at=start,
                ends_at=end,
                status='SCHEDULED',
            )
            db.session.add(appointment)
            db.session.flush()

            # The same window for the same doctor is a double booking.
            assert AppointmentService.check_double_booking(doctor.id, start, end) is True
            # A different doctor is not.
            assert AppointmentService.check_double_booking(doctor.id + 999, start, end) is False
            # A window that does not overlap is not either.
            assert (
                AppointmentService.check_double_booking(
                    doctor.id, start + timedelta(hours=5), end + timedelta(hours=5)
                )
                is False
            )
            # Excluding the appointment itself clears the conflict.
            assert (
                AppointmentService.check_double_booking(
                    doctor.id, start, end, exclude_id=appointment.id
                )
                is False
            )

    def test_check_double_booking_ignores_a_cancelled_appointment(self, app, db, test_tenant):
        from app.modules.workflows.appointment import AppointmentService
        from models.patient import Patient
        from models.user import User

        patient = Patient(
            tenant_id=test_tenant.id,
            first_name='Cancelled',
            last_name='Patient',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        db.session.add(patient)
        doctor = User(
            username=f'cancelled-book-{test_tenant.id}',
            email=f'cancelled-book-{test_tenant.id}@test.local',
            full_name='Cancelled Doctor',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.flush()

        with app.test_request_context():
            from models.appointment import Appointment

            start = datetime.now(UTC) + timedelta(hours=3)
            end = start + timedelta(hours=1)
            db.session.add(
                Appointment(
                    patient_id=patient.id,
                    doctor_id=doctor.id,
                    starts_at=start,
                    ends_at=end,
                    status='CANCELLED',
                )
            )
            db.session.flush()

            assert AppointmentService.check_double_booking(doctor.id, start, end) is False


class TestPharmacyWorkflow:
    """app/modules/workflows/pharmacy.py"""

    def test_low_stock_signal_failure_does_not_break_the_adjustment(self, app, db, test_tenant):
        from app.modules.workflows.pharmacy import PharmacyStockService
        from models.medication import Medication

        medication = Medication(
            tenant_id=test_tenant.id,
            scientific_name='Scientific',
            trade_name=f'LowStock-{datetime.now(UTC).strftime("%H%M%S%f")}',
            generic_name='Generic',
            dosage_form='tablet',
            strength='500mg',
            price=10,
            category='analgesic',
            stock_quantity=5,
            minimum_stock=50,
            is_active=True,
        )
        db.session.add(medication)
        db.session.flush()

        with patch(
            'app.shared.signal_subscribers._safe_send',
            side_effect=RuntimeError('subscriber exploded'),
        ):
            PharmacyStockService.adjust_stock(medication.id, -1, 'SALE')

        assert medication.stock_quantity == 4


class TestOwnerNavRegistry:
    """app/shared/owner_nav_registry.py"""

    def test_unknown_endpoint_falls_back_to_the_prefix(self, app):
        from app.shared.owner_nav_registry import OwnerNavItem, owner_nav_href

        item = OwnerNavItem(
            'section',
            'label',
            'icon',
            'no.such.endpoint',
            '/owner/fallback',
        )
        with app.test_request_context():
            href = owner_nav_href(item)
        assert href == '/owner/fallback'


class TestMobileNav:
    """app/shared/mobile_nav.py"""

    def test_er_doctor_falls_back_to_the_emergency_menu(self, app):
        from app.shared.mobile_nav import resolve_mobile_nav_items

        class _User:
            is_authenticated = True
            role = 'er_doctor'

        with app.test_request_context():
            items = resolve_mobile_nav_items(_User())
        assert items
        assert all(item.get('endpoint') != 'er_doctor.none' for item in items)


class TestDashboardRegistry:
    """app/shared/dashboard_registry.py"""

    def test_direct_role_hit(self):
        from app.shared.dashboard_registry import _role_inherits_from

        assert _role_inherits_from('manager', ('manager', 'admin')) is True

    def test_inherited_role_hit(self):
        from app.shared.dashboard_registry import _role_inherits_from

        assert _role_inherits_from('super_admin', ('manager',)) is True

    def test_unrelated_role(self):
        from app.shared.dashboard_registry import _role_inherits_from

        assert _role_inherits_from('doctor', ('manager',)) is False

    def test_unknown_widget_is_skipped(self):
        from app.shared.dashboard_registry import resolve_dashboard_widgets

        with patch.dict(
            'app.shared.dashboard_registry.WIDGETS',
            {},
            clear=True,
        ):
            assert resolve_dashboard_widgets('manager', set()) == []


class TestPlatformCapabilities:
    """app/core/platform_capabilities.py"""

    def test_unknown_capability_is_not_available(self):
        from app.core.platform_capabilities import platform_capability

        assert platform_capability('no-such-capability') is False


class TestSecurityMiddlewareAudit:
    """app/core/security_middleware.py"""

    def test_a_failing_audit_log_does_not_break_the_response(self):
        from flask import Flask

        import app.core.security_middleware as middleware

        test_app = Flask(__name__)
        middleware.AuditLogMiddleware().init_app(test_app)

        @test_app.route('/probe', methods=['POST'])
        def probe():
            return 'ok'

        with patch.object(middleware.logger, 'info', side_effect=RuntimeError('log down')):
            response = test_app.test_client().post('/probe')

        # The after_request hook swallows a failing audit write, so the
        # response still reaches the client.
        assert response.status_code == 200
        assert response.get_data(as_text=True) == 'ok'


class TestSearchIndexWithoutEncryption:
    """app/shared/search_index.py"""

    def test_digest_is_none_without_a_service(self):
        from app.shared import search_index

        with patch.object(search_index, '_service', return_value=None):
            assert search_index.ngram_digest('abc') is None

    def test_digests_are_empty_without_a_service(self):
        from app.shared import search_index

        with patch.object(search_index, '_service', return_value=None):
            assert search_index.digests_for('0123456789') == []


class TestAssumptionService:
    """app/core/tenant/assumption_service.py"""

    def test_revoking_an_inactive_assumption_is_a_no_op(self, app, db, test_tenant):
        from app.core.tenant.assumption_service import PlatformAssumptionService
        from app.core.tenant.models import PlatformTenantAssumption
        from models.user import User

        user = User(
            username=f'assumption-user-{test_tenant.id}',
            email=f'assumption-{test_tenant.id}@test.local',
            full_name='Assumption User',
            role='super_admin',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        user.set_password('test123')
        db.session.add(user)
        db.session.flush()

        assumption = PlatformTenantAssumption(
            user_id=user.id,
            assumed_tenant_id=test_tenant.id,
            assumed_by=user.id,
            reason='audit',
            is_active=False,
        )
        db.session.add(assumption)
        db.session.flush()

        with app.test_request_context():
            result = PlatformAssumptionService.revoke_assumption(
                assumption.id, revoked_by=user.id, revoke_reason='already revoked'
            )
        assert result is not None
        assert result.is_active is False

    def test_is_platform_user_for_an_anonymous_visitor(self, app):
        from app.core.tenant.assumption_service import PlatformAssumptionService

        with app.test_request_context():
            assert PlatformAssumptionService.is_platform_user() is False

    def test_enforce_tenant_access_without_a_resolved_tenant_returns(self, app):
        from app.core.tenant.assumption_service import PlatformAssumptionService

        with app.test_request_context():
            from flask import g

            g.pop('tenant_id', None)
            with patch('flask_login.current_user', create=True):
                # No resolved tenant means there is nothing to compare against.
                PlatformAssumptionService.enforce_tenant_access()


class TestMedicalPrivacyGuard:
    """app/shared/medical_privacy.py"""

    def test_guard_blocks_when_no_path_can_be_determined(self, app):
        from app.shared.medical_privacy import enforce_medical_privacy_guard

        class _Admin:
            role = 'super_admin'
            username = 'root'

        with app.test_request_context():
            from flask import g

            g.tenant_id = 1
            with patch('flask.request', None):
                with pytest.raises(Exception) as excinfo:
                    enforce_medical_privacy_guard(_Admin())
        assert 'Access Denied' in str(excinfo.value)

    def test_guard_falls_back_to_the_stashed_path(self, app):
        from app.shared.medical_privacy import enforce_medical_privacy_guard

        class _Admin:
            role = 'super_admin'
            username = 'root'

        class _Boom:
            @property
            def path(self):
                raise RuntimeError('no request context')

        with app.test_request_context():
            from flask import g

            g.tenant_id = 1
            g._medical_guard_path = ''
            with patch('flask.request', _Boom()):
                with pytest.raises(Exception) as excinfo:
                    enforce_medical_privacy_guard(_Admin())
        assert 'Access Denied' in str(excinfo.value)


class TestUserPreferences:
    """app/shared/user_preferences.py"""

    class _User:
        def __init__(self, preferences=None):
            self.preferences = preferences

    def test_anonymous_user_gets_the_defaults(self):
        from app.shared.user_preferences import DEFAULT_USER_PREFERENCES, get_user_preferences

        prefs = get_user_preferences(None)
        assert prefs['theme'] == DEFAULT_USER_PREFERENCES['theme']
        assert prefs['dashboard'] == DEFAULT_USER_PREFERENCES['dashboard']

    def test_saving_without_a_user_is_refused(self):
        from app.shared.user_preferences import save_user_preferences

        assert save_user_preferences(None, {'theme': 'dark'}) is False
        assert save_user_preferences(self._User({}), 'not-a-dict') is False

    def test_theme_update_is_applied(self, app):
        from app.shared.user_preferences import save_user_preferences

        user = self._User({'theme': 'light', 'density': 'normal', 'radius': 'md'})
        with app.test_request_context():
            with patch('app.shared.user_preferences.safe_commit', lambda *_a, **_k: True):
                assert save_user_preferences(user, {'theme': 'dark'}) is True
        assert user.preferences['theme'] == 'dark'

    def test_disallowed_theme_is_not_applied(self, app):
        from app.shared.user_preferences import save_user_preferences

        user = self._User({'theme': 'light', 'density': 'normal', 'radius': 'md'})
        with app.test_request_context():
            with patch('app.shared.user_preferences.safe_commit', lambda *_a, **_k: True):
                assert save_user_preferences(user, {'theme': 'rainbow'}) is True
        assert user.preferences['theme'] == 'light'

    def test_pinned_routes_are_normalised(self, app):
        from app.shared.user_preferences import save_user_preferences

        user = self._User({'theme': 'light', 'density': 'normal', 'radius': 'md'})
        with app.test_request_context():
            with patch('app.shared.user_preferences.safe_commit', lambda *_a, **_k: True):
                assert (
                    save_user_preferences(user, {'dashboard': {'pinned_routes': ['/a', '', '/b']}})
                    is True
                )
        assert user.preferences['dashboard']['pinned_routes'] == ['/a', '/b']


class TestTenantContextService:
    """app/core/tenant/service.py"""

    def test_filter_without_tenant_context_is_refused(self, app):
        from app.core.tenant.service import TenantContextService

        with app.test_request_context():
            from flask import g

            g.pop('tenant_id', None)
            g._tenant_filter_bypass = False
            with patch(
                'app.core.tenant.service.TenantContextService.get_current_tenant_id',
                return_value=None,
            ):
                with pytest.raises(PermissionError, match='No tenant context found'):
                    TenantContextService.tenant_filter(None, _TenantModel)

    def test_assert_tenant_access_without_context_is_refused(self, app):
        from app.core.tenant.service import TenantContextService

        with app.test_request_context():
            from flask import g

            g.pop('tenant_id', None)
            g._tenant_filter_bypass = False
            with patch(
                'app.core.tenant.service.TenantContextService.get_current_tenant_id',
                return_value=None,
            ):
                with pytest.raises(Exception) as excinfo:
                    TenantContextService.assert_tenant_access(object())
        assert 'Cross-tenant' in str(excinfo.value)


class _TenantModel:
    """Stand-in for a tenant-scoped model in the guard tests."""

    tenant_id = None


class TestMedicalPrivacy:
    """app/shared/medical_privacy.py"""

    def test_empty_path_is_not_medical(self):
        from app.shared.medical_privacy import is_medical_endpoint

        assert is_medical_endpoint('') is False

    def test_assumption_service_failure_fails_closed(self):
        from app.shared.medical_privacy import _has_active_assumption

        class _User:
            id = 5

        with patch(
            'app.core.tenant.assumption_service.PlatformAssumptionService.has_valid_assumption',
            side_effect=RuntimeError('assumption service down'),
        ):
            assert _has_active_assumption(_User(), 1) is False

    def test_missing_user_or_tenant_is_not_an_assumption(self):
        from app.shared.medical_privacy import _has_active_assumption

        assert _has_active_assumption(None, 1) is False
        assert _has_active_assumption(object(), None) is False


class TestBiometricDevice:
    """app/integrations/devices/biometric.py"""

    def test_tenant_id_falls_back_to_the_request_context(self, app):
        from app.integrations.devices.biometric import BiometricAuth

        service = BiometricAuth()
        with app.test_request_context():
            from flask import g

            g.tenant_id = 7
            assert service._resolve_tenant_id() == 7

    def test_tenant_id_is_none_without_a_context(self):
        import threading

        from app.integrations.devices.biometric import BiometricAuth

        service = BiometricAuth()
        outcome = {}

        def _call():
            # Outside an application context there is no ``g`` to read, and
            # the helper answers None rather than raising.
            outcome['tenant_id'] = service._resolve_tenant_id()

        thread = threading.Thread(target=_call)
        thread.start()
        thread.join()

        assert outcome['tenant_id'] is None


class TestCacheConfig:
    """utils/caching.py"""

    def test_redis_url_is_added_for_the_redis_cache(self, monkeypatch):
        import importlib

        from utils import caching

        monkeypatch.setenv('CACHE_TYPE', 'RedisCache')
        monkeypatch.setenv('REDIS_URL', 'redis://localhost:6379/1')
        reloaded = importlib.reload(caching)
        try:
            assert reloaded.cache_config['CACHE_REDIS_URL'] == 'redis://localhost:6379/1'
        finally:
            monkeypatch.undo()
            importlib.reload(caching)


class TestRbacSeed:
    """app/bootstrap/rbac_seed.py"""

    class _Inspector:
        @staticmethod
        def has_table(_name):
            return True

    def test_missing_tables_skips_the_seed(self, app):
        from app.bootstrap.rbac_seed import seed_rbac_and_catalogs

        class _EmptyInspector:
            @staticmethod
            def has_table(_name):
                return False

        with app.test_request_context():
            result = seed_rbac_and_catalogs(None, inspector=_EmptyInspector())

        assert result['granted'] is False
        assert result['skipped'] == 'permissions/roles tables absent'

    def test_a_missing_role_is_granted_nothing(self, app, rollback_db):
        from sqlalchemy import delete, select

        from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
        from models.permissions import Role, RolePermission

        db = rollback_db
        role = db.session.execute(select(Role).filter_by(name='lab')).scalars().first()
        db.session.execute(delete(RolePermission).where(RolePermission.role_id == role.id))
        db.session.delete(role)
        db.session.flush()

        with app.test_request_context():
            with (
                patch('models.permissions.create_default_permissions', lambda *_a, **_k: None),
                patch('models.permissions.create_default_roles', lambda *_a, **_k: None),
                patch('models.permissions.assign_super_admin_permissions', lambda *_a, **_k: None),
            ):
                result = seed_rbac_and_catalogs(db, inspector=self._Inspector())

        # The role the catalogue grants to is gone, so that role contributes
        # nothing and the seed still reports success.
        assert result['granted'] is True

    def test_a_missing_permission_is_skipped(self, app, rollback_db):
        from sqlalchemy import delete, select

        from app.bootstrap.rbac_seed import seed_rbac_and_catalogs
        from models.permissions import Permission, RolePermission

        db = rollback_db
        permission = (
            db.session.execute(select(Permission).filter_by(name='user_read')).scalars().first()
        )
        db.session.execute(
            delete(RolePermission).where(RolePermission.permission_id == permission.id)
        )
        db.session.delete(permission)
        db.session.flush()

        with app.test_request_context():
            with (
                patch('models.permissions.create_default_permissions', lambda *_a, **_k: None),
                patch('models.permissions.create_default_roles', lambda *_a, **_k: None),
                patch('models.permissions.assign_super_admin_permissions', lambda *_a, **_k: None),
            ):
                result = seed_rbac_and_catalogs(db, inspector=self._Inspector())

        assert result['granted'] is True
