"""Unit tests for services.feature_gate_service decision branches."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from werkzeug.exceptions import HTTPException

from app.core.tenant.models import TenantFeatureFlag
from app.extensions import db
from app.shared.enums import TenantStatus
from app.shared.http_errors import SubscriptionRequired
from services.feature_gate_service import (
    FeatureGateService,
    FeatureNotEnabledError,
    _check_tenant_payment_status,
    module_gate_active,
    require_feature,
    require_feature_service,
    require_module,
    require_module_route,
)
from utils.exceptions import ModuleNotEnabledError


class TestTenantPaymentStatus:
    def test_active_and_trial_are_valid(self):
        assert _check_tenant_payment_status(SimpleNamespace(status=TenantStatus.ACTIVE)) is True
        assert _check_tenant_payment_status(SimpleNamespace(status=TenantStatus.TRIAL)) is True

    def test_pending_cancelled_are_invalid(self):
        assert _check_tenant_payment_status(SimpleNamespace(status=TenantStatus.PENDING)) is False
        assert _check_tenant_payment_status(SimpleNamespace(status=TenantStatus.CANCELLED)) is False

    def test_missing_status_is_valid_backward_compat(self):
        assert _check_tenant_payment_status(SimpleNamespace(status=None)) is True
        assert _check_tenant_payment_status(SimpleNamespace()) is True


class TestFeatureGateServiceStatic:
    def test_module_enabled_reads_active_modules(self, test_tenant):
        # test_tenant fixture enables the full module set for the tenant
        assert FeatureGateService.module_enabled(test_tenant.id, 'reception') is True
        assert FeatureGateService.module_enabled(test_tenant.id, 'no-such-module') is False

    def test_feature_enabled_checks_flag_rows(self, test_tenant):
        flag_key = 'test-feature-gate-unit'
        flag = TenantFeatureFlag(
            tenant_id=test_tenant.id,
            feature_key=flag_key,
            is_enabled=True,
        )
        db.session.add(flag)
        db.session.commit()
        assert FeatureGateService.feature_enabled(test_tenant.id, flag_key) is True

        flag.is_enabled = False
        db.session.commit()
        assert FeatureGateService.feature_enabled(test_tenant.id, flag_key) is False
        assert FeatureGateService.feature_enabled(test_tenant.id, 'absent-flag') is False

    def test_can_use_true(self, monkeypatch):
        monkeypatch.setattr(
            'services.access_control_service.AccessControlService.has_permission',
            staticmethod(lambda _u, _a: True),
        )
        assert FeatureGateService.can_use(SimpleNamespace(), 'anything') is True

    def test_can_use_false(self, monkeypatch):
        monkeypatch.setattr(
            'services.access_control_service.AccessControlService.has_permission',
            staticmethod(lambda _u, _a: False),
        )
        assert FeatureGateService.can_use(SimpleNamespace(), 'anything') is False

    def test_can_use_fails_closed_when_check_blows_up(self, monkeypatch):
        def boom(_u, _a):
            raise RuntimeError('acl subsystem down')

        monkeypatch.setattr(
            'services.access_control_service.AccessControlService.has_permission', boom
        )
        assert FeatureGateService.can_use(SimpleNamespace(), 'anything') is False

    def test_product_profile_returns_value(self, test_tenant):
        profile = FeatureGateService.product_profile(test_tenant.id)
        expected = test_tenant.product_profile_code
        assert profile == expected

    def test_product_profile_missing_tenant_returns_none(self):
        assert FeatureGateService.product_profile(999999999) is None

    def test_tenant_has_valid_payment_delegates(self):
        assert (
            FeatureGateService.tenant_has_valid_payment(SimpleNamespace(status=TenantStatus.ACTIVE))
            is True
        )
        assert (
            FeatureGateService.tenant_has_valid_payment(
                SimpleNamespace(status=TenantStatus.CANCELLED)
            )
            is False
        )


@pytest.fixture
def _gate_off(monkeypatch):
    monkeypatch.setattr('services.feature_gate_service.module_gate_active', lambda *_a, **_k: False)


@pytest.fixture
def _gate_on(monkeypatch):
    monkeypatch.setattr('services.feature_gate_service.module_gate_active', lambda *_a, **_k: True)


class TestRequireModule:
    def test_gate_off_calls_function(self, app, _gate_off):
        @require_module('lab')
        def work():
            return 'done'

        assert work() == 'done'

    def test_admin_bypass_for_non_clinical_module(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: True)

        @require_module('reporting')
        def work():
            return 'done'

        assert work() == 'done'

    def test_no_tenant_raises(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)

        @require_module('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.pop('current_tenant', None)
            with pytest.raises(ModuleNotEnabledError) as exc:
                work()
            assert exc.value.module_name == 'lab'

    def test_payment_invalid_raises(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService,
            'tenant_has_valid_payment',
            staticmethod(lambda _tenant: False),
        )

        @require_module('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.PENDING)
            with pytest.raises(ModuleNotEnabledError) as exc:
                work()
            assert 'payment' in str(exc.value).lower()

    def test_module_disabled_raises(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'module_enabled', staticmethod(lambda _tid, _m: False)
        )

        @require_module('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.ACTIVE)
            with pytest.raises(ModuleNotEnabledError):
                work()

    def test_module_enabled_passes(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'module_enabled', staticmethod(lambda _tid, _m: True)
        )

        @require_module('lab')
        def work():
            return 'done'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.ACTIVE)
            assert work() == 'done'


class TestRequireModuleRoute:
    def test_gate_off_calls_function(self, app, _gate_off):
        @require_module_route('lab')
        def work():
            return 'done'

        with app.test_request_context():
            assert work() == 'done'

    def test_admin_bypass(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: True)

        @require_module_route('billing')
        def work():
            return 'done'

        with app.test_request_context():
            assert work() == 'done'

    def test_no_tenant_aborts_403(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)

        @require_module_route('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.pop('current_tenant', None)
            with pytest.raises(HTTPException) as exc:
                work()
            assert exc.value.code == 403

    def test_payment_invalid_raises_subscription_required(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'tenant_has_valid_payment', staticmethod(lambda _t: False)
        )

        @require_module_route('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.PENDING)
            with pytest.raises(SubscriptionRequired):
                work()

    def test_module_disabled_aborts_403(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'module_enabled', staticmethod(lambda _tid, _m: False)
        )

        @require_module_route('lab')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.ACTIVE)
            with pytest.raises(HTTPException) as exc:
                work()
            assert exc.value.code == 403

    def test_module_enabled_passes(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'module_enabled', staticmethod(lambda _tid, _m: True)
        )

        @require_module_route('lab')
        def work():
            return 'done'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1, status=TenantStatus.ACTIVE)
            assert work() == 'done'


class TestRequireFeature:
    def test_gate_off_calls_function(self, app, _gate_off):
        @require_feature('some_flag')
        def work():
            return 'done'

        with app.test_request_context():
            assert work() == 'done'

    def test_admin_bypass_reporting_billing(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: True)

        @require_feature('reporting')
        def work():
            return 'done'

        with app.test_request_context():
            assert work() == 'done'

    def test_no_tenant_aborts_403(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)

        @require_feature('flag')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.pop('current_tenant', None)
            with pytest.raises(HTTPException) as exc:
                work()
            assert exc.value.code == 403

    def test_feature_disabled_aborts_403(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'feature_enabled', staticmethod(lambda _tid, _f: False)
        )

        @require_feature('flag')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1)
            with pytest.raises(HTTPException) as exc:
                work()
            assert exc.value.code == 403

    def test_feature_enabled_passes(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'feature_enabled', staticmethod(lambda _tid, _f: True)
        )

        @require_feature('flag')
        def work():
            return 'done'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1)
            assert work() == 'done'


class TestRequireFeatureService:
    def test_gate_off_calls_function(self, app, _gate_off):
        @require_feature_service('flag')
        def work():
            return 'done'

        assert work() == 'done'

    def test_admin_bypass(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: True)

        @require_feature_service('flag')
        def work():
            return 'done'

        assert work() == 'done'

    def test_no_tenant_raises(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)

        @require_feature_service('flag')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.pop('current_tenant', None)
            with pytest.raises(FeatureNotEnabledError) as exc:
                work()
            assert exc.value.feature_name == 'flag'

    def test_feature_disabled_raises(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'feature_enabled', staticmethod(lambda _tid, _f: False)
        )

        @require_feature_service('flag')
        def work():
            return 'unreachable'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1)
            with pytest.raises(FeatureNotEnabledError):
                work()

    def test_feature_enabled_passes(self, app, _gate_on, monkeypatch):
        monkeypatch.setattr('services.feature_gate_service._is_admin_user', lambda: False)
        monkeypatch.setattr(
            FeatureGateService, 'feature_enabled', staticmethod(lambda _tid, _f: True)
        )

        @require_feature_service('flag')
        def work():
            return 'done'

        with app.test_request_context():
            import flask

            flask.g.current_tenant = SimpleNamespace(id=1)
            assert work() == 'done'


class TestModuleGateActive:
    def test_saas_mode_always_active(self, app):
        previous = app.config.get('ENABLE_SAAS_MODE')
        app.config['ENABLE_SAAS_MODE'] = True
        try:
            assert module_gate_active() is True
        finally:
            app.config['ENABLE_SAAS_MODE'] = previous

    def test_non_saas_no_tenant_is_inactive(self, app, monkeypatch):
        previous = app.config.get('ENABLE_SAAS_MODE')
        app.config['ENABLE_SAAS_MODE'] = False
        try:
            with app.test_request_context():
                import flask

                flask.g.pop('current_tenant', None)
                assert module_gate_active(None) is False
        finally:
            app.config['ENABLE_SAAS_MODE'] = previous

    def test_non_saas_with_registered_modules_is_active(self, app, test_tenant):
        previous = app.config.get('ENABLE_SAAS_MODE')
        app.config['ENABLE_SAAS_MODE'] = False
        try:
            with app.test_request_context():
                import flask

                flask.g.current_tenant = test_tenant
                # The default test tenant is provisioned with a full module set
                assert module_gate_active() is True
        finally:
            app.config['ENABLE_SAAS_MODE'] = previous

    def test_non_saas_with_broken_query_is_inactive(self, app, monkeypatch):
        previous = app.config.get('ENABLE_SAAS_MODE')
        app.config['ENABLE_SAAS_MODE'] = False
        try:
            monkeypatch.setattr(
                'app.core.module.models.TenantModule',
                MagicMock(side_effect=RuntimeError('table missing')),
            )
            with app.test_request_context():
                import flask

                flask.g.current_tenant = SimpleNamespace(id=1)
                assert module_gate_active() is False
        finally:
            app.config['ENABLE_SAAS_MODE'] = previous


class TestFeatureNotEnabledError:
    def test_default_message(self):
        err = FeatureNotEnabledError('sms')
        assert err.feature_name == 'sms'
        assert 'sms' in str(err)

    def test_custom_message(self):
        err = FeatureNotEnabledError('sms', 'custom')
        assert str(err) == 'custom'
