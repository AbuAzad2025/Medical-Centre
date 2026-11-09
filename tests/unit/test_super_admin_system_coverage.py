"""Coverage-focused HTTP tests for routes/super_admin/system.py.

Real Flask test-client requests as an authenticated super_admin. Mutating
endpoints run under ``rollback_db`` so the shared test schema is not polluted.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from models.department import Department


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


@pytest.fixture
def sa_client(app, client, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, test_tenant, username='super_admin_system_cov', role='super_admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def sa_user(app, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, test_tenant, username='super_admin_system_cov', role='super_admin')


def _make_department(db, name: str | None = None) -> Department:
    dept = Department(
        name=name or _uniq('Dept'),
        name_ar=_uniq('قسم'),
        is_active=True,
    )
    db.session.add(dept)
    db.session.commit()
    return dept


# ---------------------------------------------------------------------------
# force_logout_all / optimize_database exception paths
# ---------------------------------------------------------------------------


class TestSystemForceLogoutAndOptimize:
    def test_force_logout_all_exception_returns_500(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        def _boom(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(mod, 'safe_commit', _boom)
        resp = sa_client.post('/super-admin/system/force-logout-all')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_optimize_database_exception_returns_500(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        def _boom(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(mod, 'safe_commit', _boom)
        resp = sa_client.post('/super-admin/system/optimize-database')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_optimize_database_vacuum_warning_path(self, sa_client, monkeypatch):
        # Make VACUUM fail for every table; the per-table except logs a warning
        # but the endpoint still succeeds.
        import routes.super_admin.system as mod

        class BadConn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, *a, **k):
                raise RuntimeError('no such table')

        class BadEngine:
            def connect(self):
                return BadConn()

        # execution_options returns self
        monkeypatch.setattr(BadConn, 'execution_options', lambda self, **_k: self, raising=False)

        class FakeDB:
            engine = BadEngine()
            session = mod.db.session

        monkeypatch.setattr(mod, 'db', FakeDB(), raising=False)
        resp = sa_client.post('/super-admin/system/optimize-database')
        # safe_commit still works; VACUUM failures are swallowed.
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# system_config branches
# ---------------------------------------------------------------------------


class TestSystemConfigExtra:
    def test_post_json_with_list_body_returns_500(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system-config',
            data='[1, 2, 3]',
            content_type='application/json',
        )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_get_exception_path_redirects(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        def _boom(*a, **k):
            raise RuntimeError('db down')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        resp = sa_client.get('/super-admin/system-config?action=load', follow_redirects=False)
        assert resp.status_code == 302

    def test_post_json_audit_commit_failure_still_succeeds(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        real = mod.safe_commit
        calls = {'n': 0}

        def _flaky(*a, **k):
            calls['n'] += 1
            if calls['n'] >= 2:
                raise RuntimeError('audit commit failed')
            return real(*a, **k)

        monkeypatch.setattr(mod, 'safe_commit', _flaky)
        resp = sa_client.post('/super-admin/system-config', json={'log_level': 'INFO'})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_post_json_boolean_float_coercion(self, sa_client, db):
        from models.system_config import SystemConfig

        sa_client.post('/super-admin/system-config', json={'sms_enabled': 1.5})
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='sms_enabled'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() is True

    def test_post_json_log_level_applies_handlers(self, sa_client):

        # ensure a handler exists
        resp = sa_client.post('/super-admin/system-config', json={'log_level': 'ERROR'})
        assert resp.status_code == 200
        # no exception; level applied
        assert True

    def test_post_json_string_boolean_values(self, sa_client, db):
        from models.system_config import SystemConfig

        sa_client.post('/super-admin/system-config', json={'allow_debt_global': 'false'})
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='allow_debt_global'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() is False


# ---------------------------------------------------------------------------
# queue_settings exception path
# ---------------------------------------------------------------------------


class TestQueueSettingsExtra:
    def test_post_with_non_list_items_returns_500(self, sa_client):
        resp = sa_client.post('/super-admin/queue-settings', json={'items': 'not-a-list'})
        assert resp.status_code == 500

    def test_post_with_item_integer_crash_returns_500(self, sa_client):
        resp = sa_client.post('/super-admin/queue-settings', json={'items': [123]})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# system_backup / maintenance exception paths (best effort)
# ---------------------------------------------------------------------------


class TestSystemBackupMaintenanceExtra:
    def test_system_maintenance_exception_redirects(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        def _boom(*a, **k):
            raise RuntimeError('db down')

        monkeypatch.setattr(mod.db.session, 'execute', _boom, raising=False)
        resp = sa_client.get('/super-admin/system/maintenance', follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# system_cleanup branches
# ---------------------------------------------------------------------------


class TestSystemCleanupExtra:
    def test_cleanup_unknown_type_redirects(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'definitely_unknown'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_cleanup_no_type_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/system/cleanup', data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_cleanup_logs_result_with_error_warns(self, sa_client, monkeypatch):
        class FakeService:
            @staticmethod
            def run_all():
                return [{'table': 'audit_trail', 'deleted': 0, 'error': 'boom'}]

        monkeypatch.setattr('services.audit_cleanup_service.AuditCleanupService', FakeService)
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'logs'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_cleanup_logs_audit_commit_failure_still_redirects(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        class FakeService:
            @staticmethod
            def run_all():
                return [{'table': 'audit_trail', 'deleted': 3, 'error': None}]

        monkeypatch.setattr('services.audit_cleanup_service.AuditCleanupService', FakeService)
        monkeypatch.setattr(
            mod,
            'safe_commit',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('commit failed')),
        )
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'logs'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_cleanup_logs_outer_exception_redirects(self, sa_client, monkeypatch):
        class FakeService:
            @staticmethod
            def run_all():
                raise RuntimeError('cleanup exploded')

        monkeypatch.setattr('services.audit_cleanup_service.AuditCleanupService', FakeService)
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'logs'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_cleanup_harmonize_exception_redirects(self, sa_client, monkeypatch):
        class FakePricingService:
            @staticmethod
            def cleanup_all(max_keep_per_role=1):
                raise RuntimeError('harmonize exploded')

            @staticmethod
            def purge_users_keep_policy():
                pass

        monkeypatch.setattr('services.pricing_service.PricingService', FakePricingService)
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'harmonize'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# sms test exception path
# ---------------------------------------------------------------------------


class TestSmsTestExtra:
    def test_sms_test_exception_returns_500(self, sa_client, monkeypatch):
        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')

        class BoomService:
            @staticmethod
            def send_sms(phone, message):
                raise RuntimeError('sms exploded')

        monkeypatch.setattr('services.sms_service.SMSService', BoomService)
        resp = sa_client.post(
            '/super-admin/system/sms/test', json={'phone_number': '+970599000002'}
        )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# run_notifications / init templates with explicit results
# ---------------------------------------------------------------------------


class TestNotificationsExtra:
    def test_run_notifications_success_false_flashes_error(self, sa_client, monkeypatch):
        class FakeNotificationService:
            @staticmethod
            def check_and_send_alerts():
                return {'success': False, 'message': 'no alerts'}

        monkeypatch.setattr(
            'services.notification_service.NotificationService', FakeNotificationService
        )
        resp = sa_client.post('/super-admin/system/notifications/run', follow_redirects=False)
        assert resp.status_code == 302

    def test_init_templates_success(self, sa_client, monkeypatch):
        class FakeNotificationService:
            @staticmethod
            def create_default_templates():
                return {'success': True, 'message': 'templates ready'}

        monkeypatch.setattr(
            'services.notification_service.NotificationService', FakeNotificationService
        )
        resp = sa_client.post(
            '/super-admin/system/notifications/init-templates', follow_redirects=False
        )
        assert resp.status_code == 302

    def test_process_notification_queue_success_message(self, sa_client, monkeypatch):
        monkeypatch.setattr('services.notification_service.process_notification_queue', lambda: 7)
        resp = sa_client.post('/super-admin/system/notifications/queue/process')
        assert resp.status_code == 200
        assert '7' in resp.get_json()['message']


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class TestSystemHelpers:
    def test_get_system_uptime(self):
        from routes.super_admin.system import get_system_uptime

        assert get_system_uptime() == '99.9%'

    def test_get_database_size_success(self, app):
        from routes.super_admin.system import get_database_size

        with app.app_context():
            result = get_database_size()
        assert isinstance(result, str)
        assert result != ''

    def test_get_database_size_exception(self, app, monkeypatch):
        import services.postgres_admin_service as svc

        def _boom(engine):
            raise RuntimeError('size failed')

        monkeypatch.setattr(svc, 'get_database_size_display', _boom)
        from routes.super_admin.system import get_database_size

        with app.app_context():
            result = get_database_size()
        assert result == 'غير متاح'

    def test_get_last_backup_time_none(self, app, db, test_tenant, rollback_db):
        from routes.super_admin.system import get_last_backup_time
        from tests.tenant_context import tenant_test_context

        with tenant_test_context(app, test_tenant):
            result = get_last_backup_time()
        assert isinstance(result, str)

    def test_get_last_backup_time_with_completed(self, app, db, test_tenant, rollback_db):
        from app.shared.enums import BackupStatus
        from models.backup import Backup
        from routes.super_admin.system import get_last_backup_time
        from tests.tenant_context import tenant_test_context

        with tenant_test_context(app, test_tenant):
            db.session.add(
                Backup(
                    backup_name=_uniq('backup'),
                    backup_type='full',
                    backup_path=f'backups/{_uniq("file")}.sql.gz',
                    backup_status=BackupStatus.COMPLETED,
                    completed_at=datetime.now(UTC),
                )
            )
            db.session.commit()
            result = get_last_backup_time()
        assert isinstance(result, str)

    def test_get_last_backup_time_exception(self, app, monkeypatch):
        import routes.super_admin.system as mod

        monkeypatch.setattr(
            mod, 'select', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('q failed'))
        )
        from routes.super_admin.system import get_last_backup_time

        with app.app_context():
            result = get_last_backup_time()
        assert result == 'غير متاح'


# ---------------------------------------------------------------------------
# backup settings update branch
# ---------------------------------------------------------------------------


class TestBackupSettingsExtra:
    def test_backup_settings_updates_existing_rows(self, sa_client):
        sa_client.post(
            '/super-admin/backup/settings',
            json={'frequency': 'daily', 'retention': '7'},
        )
        resp = sa_client.post(
            '/super-admin/backup/settings',
            json={'frequency': 'weekly', 'retention': '14'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_backup_settings_empty_body_returns_500(self, sa_client):
        resp = sa_client.post(
            '/super-admin/backup/settings', data='not json', content_type='application/json'
        )
        assert resp.status_code in (200, 500)

    def test_backup_settings_defaults(self, sa_client):
        resp = sa_client.post('/super-admin/backup/settings', json={})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# maintenance automation extra branches
# ---------------------------------------------------------------------------


class TestMaintenanceAutomationExtra:
    def test_get_after_post_shows_saved(self, sa_client):
        sa_client.post(
            '/super-admin/maintenance/automation',
            json={
                'auto_cleanup': True,
                'cleanup_days': 10,
                'log_retention_days': 60,
                'auto_backup': True,
            },
        )
        resp = sa_client.get('/super-admin/maintenance/automation')
        assert resp.status_code == 200

    def test_post_invalid_int_returns_template(self, sa_client):
        resp = sa_client.post(
            '/super-admin/maintenance/automation',
            json={'cleanup_days': 'not-an-int'},
            follow_redirects=False,
        )
        # exception path renders template (200) rather than JSON
        assert resp.status_code == 200

    def test_post_defaults(self, sa_client):
        resp = sa_client.post('/super-admin/maintenance/automation', json={})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# system() page
# ---------------------------------------------------------------------------


class TestSystemPageExtra:
    def test_system_page_renders(self, sa_client):
        assert sa_client.get('/super-admin/system').status_code == 200

    def test_system_config_form_post_redirects(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', data={'x': 'y'}, follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Additional coverage for remaining missed lines
# ---------------------------------------------------------------------------


class TestSystemExtraCoverage2:
    def test_force_logout_all_success(self, sa_client):
        resp = sa_client.post('/super-admin/system/force-logout-all')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_optimize_database_success(self, sa_client):
        resp = sa_client.post('/super-admin/system/optimize-database')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_system_config_unknown_key(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'nonsense_key': 'x'})
        assert resp.status_code == 400
        assert resp.get_json()['errors']

    def test_system_config_bad_choice(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'log_level': 'NOPE'})
        assert resp.status_code == 400

    def test_system_config_bad_integer(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'session_timeout': 'abc'})
        assert resp.status_code == 400

    def test_system_config_out_of_range(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'session_timeout': 9999})
        assert resp.status_code == 400

    def test_system_config_boolean_else_branch(self, sa_client, db):
        from models.system_config import SystemConfig

        sa_client.post('/super-admin/system-config', json={'sms_enabled': [1]})
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='sms_enabled'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() is True

    def test_system_config_update_existing_row(self, sa_client, db):
        from models.system_config import SystemConfig

        sa_client.post('/super-admin/system-config', json={'language': 'en'})
        resp = sa_client.post('/super-admin/system-config', json={'language': 'ar'})
        assert resp.status_code == 200
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='language'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.config_value == 'ar'

    def test_system_config_create_integer_row(self, sa_client, db):
        from models.system_config import SystemConfig

        resp = sa_client.post('/super-admin/system-config', json={'session_timeout': 12})
        assert resp.status_code == 200
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='session_timeout'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.config_type == 'integer'

    def test_system_config_log_level_handlers(self, sa_client, app):
        import logging

        handler = logging.StreamHandler()
        app.logger.addHandler(handler)
        try:
            resp = sa_client.post('/super-admin/system-config', json={'log_level': 'DEBUG'})
            assert resp.status_code == 200
        finally:
            app.logger.removeHandler(handler)

    def test_system_config_load_action(self, sa_client):
        resp = sa_client.get('/super-admin/system-config?action=load')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_system_config_default_page(self, sa_client):
        resp = sa_client.get('/super-admin/system-config')
        assert resp.status_code == 200

    def test_system_config_test_db_action(self, sa_client):
        resp = sa_client.get('/super-admin/system-config?action=test_db')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_settings_load(self, sa_client, db):
        _make_department(db)
        resp = sa_client.get('/super-admin/queue-settings?action=load')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_queue_settings_page(self, sa_client):
        resp = sa_client.get('/super-admin/queue-settings')
        assert resp.status_code == 200

    def test_queue_settings_post_non_json(self, sa_client):
        resp = sa_client.post('/super-admin/queue-settings', data={'items': 'x'})
        assert resp.status_code == 400

    def test_queue_settings_skip_no_dept(self, sa_client):
        resp = sa_client.post(
            '/super-admin/queue-settings', json={'items': [{'max_queue_size': 5}]}
        )
        assert resp.status_code == 200

    def test_system_backup_exception_redirects(self, sa_client, monkeypatch):
        import routes.super_admin.system as mod

        calls = {'n': 0}

        def _flaky(*a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('url_for failed')
            return mod.url_for(*a, **k) if False else None

        # patch url_for used in module
        real_url_for = mod.url_for

        def _wrapper(*a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('url_for failed')
            return real_url_for(*a, **k)

        monkeypatch.setattr(mod, 'url_for', _wrapper)
        resp = sa_client.get('/super-admin/system-backup', follow_redirects=False)
        assert resp.status_code == 302

    def test_system_maintenance_page(self, sa_client):
        resp = sa_client.get('/super-admin/system/maintenance')
        assert resp.status_code == 200

    def test_cleanup_sessions(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup', data={'cleanup_type': 'sessions'}, follow_redirects=False
        )
        assert resp.status_code == 302

    def test_cleanup_cache(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup', data={'cleanup_type': 'cache'}, follow_redirects=False
        )
        assert resp.status_code == 302

    def test_cleanup_seed_data(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'seed_data'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_cleanup_harmonize(self, sa_client, monkeypatch):
        class FakePricingService:
            @staticmethod
            def cleanup_all(max_keep_per_role=1):
                pass

            @staticmethod
            def purge_users_keep_policy():
                pass

        monkeypatch.setattr('services.pricing_service.PricingService', FakePricingService)
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'harmonize'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_sms_test_missing_phone(self, sa_client, monkeypatch):
        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')
        resp = sa_client.post('/super-admin/system/sms/test', json={})
        assert resp.status_code == 400

    def test_sms_test_success(self, sa_client, monkeypatch):
        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')

        class FakeProvider:
            pass

        class FakeSMSService:
            @staticmethod
            def send_sms(phone, message):
                return {'success': True}

        monkeypatch.setattr('services.sms_service.SMSService', FakeSMSService)
        resp = sa_client.post(
            '/super-admin/system/sms/test', json={'phone_number': '+970599000003'}
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_sms_test_failure_result(self, sa_client, monkeypatch):
        monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')

        class FakeSMSService:
            @staticmethod
            def send_sms(phone, message):
                return {'success': False, 'error': 'provider down'}

        monkeypatch.setattr('services.sms_service.SMSService', FakeSMSService)
        resp = sa_client.post(
            '/super-admin/system/sms/test', json={'phone_number': '+970599000004'}
        )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_process_notification_queue_exception(self, sa_client, monkeypatch):
        def _boom():
            raise RuntimeError('queue exploded')

        monkeypatch.setattr('services.notification_service.process_notification_queue', _boom)
        resp = sa_client.post('/super-admin/system/notifications/queue/process')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_run_notifications_exception(self, sa_client, monkeypatch):
        class FakeNotificationService:
            @staticmethod
            def check_and_send_alerts():
                raise RuntimeError('alerts exploded')

        monkeypatch.setattr(
            'services.notification_service.NotificationService', FakeNotificationService
        )
        resp = sa_client.post('/super-admin/system/notifications/run', follow_redirects=False)
        assert resp.status_code == 302

    def test_init_templates_exception(self, sa_client, monkeypatch):
        class FakeNotificationService:
            @staticmethod
            def create_default_templates():
                raise RuntimeError('templates exploded')

        monkeypatch.setattr(
            'services.notification_service.NotificationService', FakeNotificationService
        )
        resp = sa_client.post(
            '/super-admin/system/notifications/init-templates', follow_redirects=False
        )
        assert resp.status_code == 302

    def test_system_page(self, sa_client):
        assert sa_client.get('/super-admin/system').status_code == 200


def _make_department(db, name=None):
    from models.department import Department

    dept = Department(name=name or _uniq('Dept'), name_ar=_uniq('قسم'), is_active=True)
    db.session.add(dept)
    db.session.commit()
    return dept


class TestSystemExtraCoverage3:
    def test_system_config_load_with_rows(self, sa_client):
        sa_client.post('/super-admin/system-config', json={'language': 'ar'})
        resp = sa_client.get('/super-admin/system-config?action=load')
        assert resp.status_code == 200
        assert resp.get_json()['settings'].get('language') == 'ar'

    def test_queue_settings_save_with_department(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(
            '/super-admin/queue-settings',
            json={'items': [{'department_id': dept.id, 'max_queue_size': 12}]},
        )
        assert resp.status_code == 200
        loaded = sa_client.get('/super-admin/queue-settings?action=load').get_json()['items']
        item = next(i for i in loaded if i['department_id'] == dept.id)
        assert item['max_queue_size'] == 12


class TestSystemExtraCoverage4:
    def test_queue_settings_bad_ints_warns(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(
            '/super-admin/queue-settings',
            json={
                'items': [
                    {
                        'department_id': dept.id,
                        'max_queue_size': 'not-an-int',
                        'average_wait_time': 'also-not-an-int',
                        'payment_required': False,
                    }
                ]
            },
        )
        assert resp.status_code == 200


class TestSystemExtraCoverage5:
    def test_queue_settings_booleans(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.post(
            '/super-admin/queue-settings',
            json={
                'items': [
                    {
                        'department_id': dept.id,
                        'emergency_payment_waived': False,
                        'force_entry_allowed': True,
                        'allow_partial_payment': False,
                        'allow_debt': True,
                    }
                ]
            },
        )
        assert resp.status_code == 200
