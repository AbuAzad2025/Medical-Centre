"""Wave-2 HTTP coverage for the super_admin surface (routes/super_admin/*).

Complements tests/unit/test_super_admin_coverage.py with the branches that
file does not reach: boundary/validation matrices for the system-config
endpoint, the pg_dump command construction path (subprocess faked, gzip
round-trip asserted), the SQLAlchemy boolean-negation bug the wave-1 tests
could not see (``not column`` compiles to ``WHERE false``), deeper analytics
helper branches (peak hour, inactive users, recommendations), and assorted
redirect/JSON contracts.

Mutating endpoints run under ``rollback_db`` so the shared test database is
not polluted. Backup creation never invokes a real pg_dump binary: a fake
``subprocess.Popen`` stands in and the command line is asserted honestly.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import os
import re
import subprocess
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from models.department import Department
from models.patient import Patient
from models.user import User
from models.visit import Visit


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


@pytest.fixture
def sa_client(app, client, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, test_tenant, username='super_admin_wave2', role='super_admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def sa_user(app, db, test_tenant, rollback_db):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, test_tenant, username='super_admin_wave2', role='super_admin')


def _csrf_from(client, path: str) -> str:
    resp = client.get(path)
    match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', resp.data)
    if match:
        return match.group(1).decode()
    match = re.search(rb'name="csrf-token"[^>]*content="([^"]+)"', resp.data)
    return match.group(1).decode() if match else ''


def _make_department(db, name: str | None = None) -> Department:
    dept = Department(
        name=name or _uniq('Dept'),
        name_ar=_uniq('AR'),
        is_active=True,
    )
    db.session.add(dept)
    db.session.commit()
    return dept


def _make_patient(db) -> Patient:
    patient = Patient(
        first_name='Cover',
        last_name='Wavetwo',
        phone='05' + str(uuid.uuid4().int)[:8],
        gender='M',
    )
    db.session.add(patient)
    db.session.commit()
    return patient


def _make_visits(db, patient, count: int, *, doctor_id=None, created_at=None) -> list[Visit]:
    from app.shared.enums import VisitState

    visits = []
    for _ in range(count):
        v = Visit(
            patient_id=patient.id,
            doctor_id=doctor_id,
            status=VisitState.OPEN.value,
            payment_status='PENDING',
        )
        if created_at is not None:
            v.created_at = created_at
        db.session.add(v)
        visits.append(v)
    db.session.flush()
    return visits


def _make_backup(db, **kw):
    from app.shared.enums import BackupStatus
    from models.backup import Backup

    defaults = {
        'backup_name': _uniq('backup'),
        'backup_type': 'full',
        'backup_path': f'backups/{_uniq("file")}.sql.gz',
        'backup_status': BackupStatus.COMPLETED,
    }
    defaults.update(kw)
    row = Backup(**defaults)
    db.session.add(row)
    db.session.commit()
    return row


# ---------------------------------------------------------------------------
# routes/super_admin/system.py -- system-config validation matrices
# ---------------------------------------------------------------------------


class TestSystemConfigMatrices:
    _INT_KEYS = [
        ('session_timeout', 5, 480),
        ('max_login_attempts', 3, 10),
        ('login_attempt_window_minutes', 1, 120),
        ('login_lockout_minutes', 1, 240),
        ('password_min_length', 6, 20),
        ('password_expiry_days', 30, 365),
    ]

    @pytest.mark.parametrize(('key', 'lo', 'hi'), _INT_KEYS)
    def test_integer_choices_accepted_at_boundaries(self, sa_client, key, lo, hi):
        resp = sa_client.post('/super-admin/system-config', json={key: lo})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()['success'] is True
        resp = sa_client.post('/super-admin/system-config', json={key: hi})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    @pytest.mark.parametrize(('key', 'lo', 'hi'), _INT_KEYS)
    def test_integer_choices_rejected_outside_range(self, sa_client, key, lo, hi):
        resp = sa_client.post('/super-admin/system-config', json={key: lo - 1})
        assert resp.status_code == 400
        resp = sa_client.post('/super-admin/system-config', json={key: hi + 1})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert body['errors']

    def test_string_choices_roundtrip(self, sa_client):
        for key, value in [
            ('timezone', 'Asia/Jerusalem'),
            ('language', 'ar'),
            ('currency', 'EUR'),
            ('date_format', 'dd/mm/yyyy'),
            ('sms_provider', 'twilio'),
            ('log_level', 'WARNING'),
        ]:
            resp = sa_client.post('/super-admin/system-config', json={key: value})
            assert resp.status_code == 200, f'{key}={value}'
            assert resp.get_json()['success'] is True
        resp = sa_client.get('/super-admin/system-config?action=load')
        settings = resp.get_json()['settings']
        assert settings['timezone'] == 'Asia/Jerusalem'
        assert settings['language'] == 'ar'
        assert settings['currency'] == 'EUR'
        assert settings['date_format'] == 'dd/mm/yyyy'
        assert settings['sms_provider'] == 'twilio'
        assert settings['log_level'] == 'WARNING'

    @pytest.mark.parametrize(
        ('key', 'bad'),
        [
            ('timezone', 'Europe/Berlin'),
            ('language', 'fr'),
            ('currency', 'JPY'),
            ('date_format', 'dd.mm.yyyy'),
            ('sms_provider', 'nexmo'),
            ('log_level', 'VERBOSE'),
        ],
    )
    def test_string_choices_rejected(self, sa_client, key, bad):
        resp = sa_client.post('/super-admin/system-config', json={key: bad})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_boolean_string_and_numeric_coercion(self, sa_client, db):
        from models.system_config import SystemConfig

        sa_client.post('/super-admin/system-config', json={'sms_enabled': 'on'})
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='sms_enabled'))
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.config_type == 'boolean'
        assert cfg.get_value() is True

        sa_client.post('/super-admin/system-config', json={'sms_enabled': 0})
        db.session.expire_all()
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='sms_enabled'))
            .scalars()
            .first()
        )
        assert cfg.get_value() is False

    def test_repeating_key_keeps_single_row(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.system_config import SystemConfig

        before = (
            db.session.execute(
                select(sfunc.count()).select_from(SystemConfig).filter_by(config_key='language')
            ).scalar()
            or 0
        )
        sa_client.post('/super-admin/system-config', json={'language': 'en'})
        sa_client.post('/super-admin/system-config', json={'language': 'ar'})
        after_rows = (
            db.session.execute(select(SystemConfig).filter_by(config_key='language'))
            .scalars()
            .all()
        )
        # The second POST must take the update path, not insert a duplicate.
        assert len(after_rows) <= before + 1
        assert all(r.config_value == 'ar' for r in after_rows)

    def test_unknown_key_and_unknown_integer_type(self, sa_client):
        resp = sa_client.post('/super-admin/system-config', json={'definitely_not_a_key': 'x'})
        assert resp.status_code == 400
        resp = sa_client.post(
            '/super-admin/system-config', json={'session_timeout': 'not-a-number'}
        )
        assert resp.status_code == 400

    def test_multiple_errors_returned_together(self, sa_client):
        resp = sa_client.post(
            '/super-admin/system-config',
            json={'language': 'fr', 'currency': 'JPY', 'session_timeout': 9999},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert len(body['errors']) >= 3

    def test_twilio_and_debt_keys_persist_without_choices(self, sa_client):
        payload = {
            'twilio_account_sid': 'AC-test-sid',
            'twilio_auth_token': 'tok',
            'twilio_phone_number': '+972500000000',
            'allow_partial_payment_global': True,
            'allow_debt_global': False,
        }
        resp = sa_client.post('/super-admin/system-config', json=payload)
        assert resp.status_code == 200
        body = sa_client.get('/super-admin/system-config?action=load').get_json()
        assert body['settings']['twilio_account_sid'] == 'AC-test-sid'
        assert body['settings']['twilio_auth_token'] == 'tok'
        assert body['settings']['twilio_phone_number'] == '+972500000000'

    def test_log_level_update_writes_audit_row(self, sa_client, db):
        from models.audit_trail import AuditTrail

        resp = sa_client.post('/super-admin/system-config', json={'log_level': 'DEBUG'})
        assert resp.status_code == 200
        audit = (
            db.session.execute(
                select(AuditTrail)
                .filter_by(action='update', entity_type='system')
                .order_by(AuditTrail.id.desc())
            )
            .scalars()
            .first()
        )
        assert audit is not None
        assert 'log_level=DEBUG' in (audit.notes or '')

    def test_system_config_test_db_action(self, sa_client):
        resp = sa_client.get('/super-admin/system-config?action=test_db')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# routes/super_admin/system.py -- queue settings, cleanup, notifications
# ---------------------------------------------------------------------------


class TestQueueSettingsExtended:
    def test_save_with_non_integer_values_does_not_crash(self, sa_client, db):
        from models.queue_management import QueueSettings

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
        qs = (
            db.session.execute(select(QueueSettings).filter_by(department_id=dept.id))
            .scalars()
            .first()
        )
        assert qs is not None
        # Bad integers keep the model defaults; the boolean still applied.
        assert bool(qs.payment_required) is False

    def test_save_skips_items_without_department_id(self, sa_client, db):
        resp = sa_client.post(
            '/super-admin/queue-settings',
            json={'items': [{'max_queue_size': 99}]},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_load_returns_active_departments_with_defaults(self, sa_client, db):
        dept = _make_department(db)
        resp = sa_client.get('/super-admin/queue-settings?action=load')
        assert resp.status_code == 200
        items = resp.get_json()['items']
        mine = [i for i in items if i['department_id'] == dept.id]
        assert mine, 'expected the new department in the load payload'
        item = mine[0]
        assert item['max_queue_size'] == 50
        assert item['payment_required'] is True
        assert item['emergency_payment_waived'] is True
        assert item['allow_partial_payment'] is True
        assert item['allow_debt'] is False


class TestSystemCleanupAndNotifications:
    def test_harmonize_calls_pricing_service_with_max_keep_one(self, sa_client, monkeypatch):
        calls = []

        class FakePricingService:
            @staticmethod
            def cleanup_all(max_keep_per_role=2):
                calls.append(('cleanup_all', max_keep_per_role))

            @staticmethod
            def purge_users_keep_policy():
                calls.append(('purge_users_keep_policy', None))

        monkeypatch.setattr('services.pricing_service.PricingService', FakePricingService)
        resp = sa_client.post(
            '/super-admin/system/cleanup',
            data={'cleanup_type': 'harmonize'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert ('cleanup_all', 1) in calls
        assert ('purge_users_keep_policy', None) in calls

    def test_notification_queue_process_error_returns_500(self, sa_client, monkeypatch):
        def _boom():
            raise RuntimeError('queue exploded')

        monkeypatch.setattr('services.notification_service.process_notification_queue', _boom)
        resp = sa_client.post('/super-admin/system/notifications/queue/process')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_run_notifications_error_redirects_with_flash(self, sa_client, monkeypatch):
        class FakeNotificationService:
            @staticmethod
            def check_and_send_alerts():
                raise RuntimeError('alerts exploded')

        monkeypatch.setattr(
            'services.notification_service.NotificationService', FakeNotificationService
        )
        resp = sa_client.post('/super-admin/system/notifications/run', follow_redirects=False)
        assert resp.status_code == 302

    def test_init_notification_templates_error_redirects(self, sa_client, monkeypatch):
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

    def test_system_maintenance_with_completed_backup_shows_timestamp(self, sa_client, db):
        from app.shared.enums import BackupStatus

        _make_backup(db, backup_status=BackupStatus.COMPLETED, completed_at=datetime.now(UTC))
        resp = sa_client.get('/super-admin/system/maintenance')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# routes/super_admin/backup.py -- pg_dump command path
# ---------------------------------------------------------------------------


def _fake_popen_factory(payload: bytes, *, returncode: int = 0, stderr: bytes = b''):
    captured = {}

    class FakePopen:
        def __init__(self, cmd, env=None, stdout=None, stderr_stream=None, **kwargs):
            captured['cmd'] = list(cmd)
            captured['env'] = dict(env or {})
            self._returncode = returncode
            self.returncode = returncode
            self.stdout = io.BytesIO(payload)
            self.stderr = io.BytesIO(stderr)

        def wait(self, timeout=None):
            return self._returncode

        def poll(self):
            return self._returncode

        def kill(self):
            pass

    return captured, FakePopen


class TestBackupCreateCommandPath:
    def _disable_celery(self, monkeypatch):
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)

    def test_create_backup_builds_pg_dump_command(self, sa_client, db, monkeypatch, tmp_path):
        from app.shared.enums import BackupStatus
        from models.backup import Backup

        self._disable_celery(monkeypatch)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://bk_user:bk_pass@dbhost:5544/bkdb')
        target = tmp_path / 'out.sql.gz'
        monkeypatch.setattr(
            'services.pg_backup_service.build_backup_path', lambda _base, _name: str(target)
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/usr/bin/{name}'
        )
        payload = b'-- PostgreSQL database dump\nSELECT 1;\n'
        captured, FakePopen = _fake_popen_factory(payload, returncode=0)
        monkeypatch.setattr('services.pg_backup_service.subprocess.Popen', FakePopen)

        resp = sa_client.post('/super-admin/backup/create', json={'type': 'schema'})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        cmd = captured['cmd']
        assert cmd[0] == '/usr/bin/pg_dump'
        assert cmd[cmd.index('--host') + 1] == 'dbhost'
        assert cmd[cmd.index('--port') + 1] == '5544'
        assert cmd[cmd.index('--username') + 1] == 'bk_user'
        assert cmd[cmd.index('--dbname') + 1] == 'bkdb'
        assert cmd[cmd.index('--format') + 1] == 'plain'
        assert '--no-owner' in cmd
        assert '--no-acl' in cmd
        assert captured['env']['PGPASSWORD'] == 'bk_pass'

        # The gzip artifact really decompresses to the streamed payload.
        with gzip.open(target, 'rb') as fh:
            assert fh.read() == payload

        row = (
            db.session.execute(select(Backup).filter_by(backup_path=str(target))).scalars().first()
        )
        assert row is not None
        assert row.backup_status == BackupStatus.COMPLETED
        assert row.backup_type == 'schema'
        assert row.backup_size > 0

    def test_create_backup_nonzero_exit_marks_failed(self, sa_client, db, monkeypatch, tmp_path):
        from app.shared.enums import BackupStatus
        from models.backup import Backup

        self._disable_celery(monkeypatch)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@dbhost:5432/bkdb')
        target = tmp_path / 'out.sql.gz'
        monkeypatch.setattr(
            'services.pg_backup_service.build_backup_path', lambda _base, _name: str(target)
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/usr/bin/{name}'
        )
        _, FakePopen = _fake_popen_factory(b'partial junk', returncode=2, stderr=b'boom')
        monkeypatch.setattr('services.pg_backup_service.subprocess.Popen', FakePopen)

        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 500
        body = resp.get_json()
        assert body['success'] is False
        assert 'boom' in body['message']

        db.session.expire_all()
        row = (
            db.session.execute(select(Backup).filter_by(backup_path=str(target))).scalars().first()
        )
        assert row.backup_status == BackupStatus.FAILED
        assert row.backup_notes == 'boom'
        assert not target.exists(), 'failed backup artifact must be removed'

    def test_create_backup_empty_artifact_marks_failed(self, sa_client, db, monkeypatch, tmp_path):
        from app.shared.enums import BackupStatus
        from models.backup import Backup

        self._disable_celery(monkeypatch)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@dbhost:5432/bkdb')
        target = tmp_path / 'out.sql.gz'
        monkeypatch.setattr(
            'services.pg_backup_service.build_backup_path', lambda _base, _name: str(target)
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/usr/bin/{name}'
        )
        _, FakePopen = _fake_popen_factory(b'', returncode=0)
        monkeypatch.setattr('services.pg_backup_service.subprocess.Popen', FakePopen)

        resp = sa_client.post('/super-admin/backup/create', json={'type': 'full'})
        assert resp.status_code == 500
        db.session.expire_all()
        row = (
            db.session.execute(select(Backup).filter_by(backup_path=str(target))).scalars().first()
        )
        assert row.backup_status == BackupStatus.FAILED
        assert 'empty' in (row.backup_notes or '').lower()
        assert not target.exists()

    def test_run_pg_dump_timeout_raises_pg_backup_error(self, monkeypatch, tmp_path):
        from services.pg_backup_service import PgBackupError, run_pg_dump_sql_gz

        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@dbhost:5432/bkdb')
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/usr/bin/{name}'
        )

        class TimeoutPopen:
            def __init__(self, cmd, env=None, stdout=None, stderr=None, **kwargs):
                self.returncode = None
                self.stdout = io.BytesIO(b'')
                self.stderr = io.BytesIO(b'')
                self.killed = False

            def wait(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired(cmd='pg_dump', timeout=timeout)
                # After kill() a real wait() reaps the process and returns.
                return -9

            def poll(self):
                return -9 if self.killed else None

            def kill(self):
                self.killed = True

        monkeypatch.setattr('services.pg_backup_service.subprocess.Popen', TimeoutPopen)
        with pytest.raises(PgBackupError, match='timed out'):
            run_pg_dump_sql_gz(str(tmp_path / 'out.sql.gz'))

    def test_parse_database_url_rejects_sqlite_and_bad_scheme(self):
        from services.pg_backup_service import PgBackupError, parse_database_url

        with pytest.raises(PgBackupError):
            parse_database_url('sqlite:///:memory:')
        with pytest.raises(PgBackupError):
            parse_database_url('mysql://u:p@host:3306/db')
        with pytest.raises(PgBackupError):
            parse_database_url('postgresql://u:p@host:5432/')


class TestBackupCancelContract:
    def test_cancel_in_progress_sets_cancelled_and_completed_at(self, sa_client, db):
        from app.shared.enums import BackupStatus

        backup = _make_backup(db, backup_status=BackupStatus.IN_PROGRESS, completed_at=None)
        resp = sa_client.post(f'/super-admin/backup/cancel/{backup.id}')
        assert resp.status_code == 200
        db.session.expire_all()
        db.session.refresh(backup)
        assert backup.backup_status == BackupStatus.CANCELLED
        assert backup.completed_at is not None

    def test_cancel_pending_backup_sets_cancelled(self, sa_client, db):
        from app.shared.enums import BackupStatus

        backup = _make_backup(db, backup_status=BackupStatus.PENDING, completed_at=None)
        resp = sa_client.post(f'/super-admin/backup/cancel/{backup.id}')
        assert resp.status_code == 200
        db.session.expire_all()
        db.session.refresh(backup)
        assert backup.backup_status == BackupStatus.CANCELLED


def _make_role(db, test_tenant, name: str | None = None, is_system_role: bool = False):
    from models.permissions import Role

    role = Role(
        name=name or _uniq('role'),
        name_ar='AR',
        description='wave2 test role',
        is_system_role=is_system_role,
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db.session.add(role)
    db.session.commit()
    return role


def _make_permission(db, test_tenant, name: str | None = None):
    from app.shared.enums import PermissionCategory, PermissionLevel
    from models.permissions import Permission

    perm = Permission(
        name=name or _uniq('perm'),
        description='wave2 test permission',
        category=PermissionCategory.REPORTS,
        level=PermissionLevel.READ,
        is_active=True,
        tenant_id=test_tenant.id,
    )
    db.session.add(perm)
    db.session.commit()
    return perm


def _make_service(db, **kw):
    from models.service import ServiceMaster

    defaults = {
        'code': _uniq('SVC'),
        'name': _uniq('svc'),
        'name_ar': 'AR',
        'base_price': 10.0,
        'category': 'general',
        'is_active': True,
    }
    defaults.update(kw)
    svc = ServiceMaster(**defaults)
    db.session.add(svc)
    db.session.commit()
    return svc


# ---------------------------------------------------------------------------
# routes/super_admin/analytics.py -- deeper helper branches
# ---------------------------------------------------------------------------


class TestAnalyticsHelpersDeep:
    def test_ai_insights_counts_seeded_rows(self, app, db, test_tenant, rollback_db):
        from models.ai_analytics import AIRecommendation

        patient = _make_patient(db)
        for accepted, conf in [(None, 0.5), (True, 0.9), (False, 0.85), (None, 0.95)]:
            db.session.add(
                AIRecommendation(
                    patient_id=patient.id,
                    recommendation_type='treatment',
                    title=_uniq('rec'),
                    description='seeded by wave-2 tests',
                    confidence_score=conf,
                    is_accepted=accepted,
                    tenant_id=test_tenant.id,
                )
            )
        db.session.flush()
        from routes.super_admin.analytics import get_ai_insights

        insights = get_ai_insights()
        # >= semantics: pre-existing committed rows in the shared schema may add more.
        assert insights['total_recommendations'] >= 4
        assert insights['pending_recommendations'] >= 2
        assert insights['accepted_recommendations'] >= 1
        assert insights['high_confidence_recommendations'] >= 3
        assert insights['recent_insights'] >= 4

    def test_smart_recommendations_performance_threshold(self, app, db, test_tenant, rollback_db):
        patient = _make_patient(db)
        _make_visits(db, patient, 101)
        from routes.super_admin.analytics import get_smart_recommendations

        recs = get_smart_recommendations()
        assert any(r['type'] == 'performance' for r in recs)

    def test_smart_recommendations_inactive_users_threshold(
        self, app, db, test_tenant, rollback_db
    ):
        now = datetime.now()
        for _ in range(6):
            u = User(
                username=_uniq('inactive'),
                email=f'{_uniq("inactive")}@example.com',
                full_name='Inactive User',
                role='doctor',
                is_active=True,
                tenant_id=test_tenant.id,
                last_login=now - timedelta(days=40),
            )
            u.set_password('Secret123!')
            db.session.add(u)
        db.session.flush()
        from routes.super_admin.analytics import get_smart_recommendations

        recs = get_smart_recommendations()
        assert any(r['type'] == 'users' for r in recs)

    def test_smart_recommendations_security_threshold(self, app, db, test_tenant, rollback_db):
        from models.audit_trail import AuditTrail

        for _ in range(11):
            db.session.add(
                AuditTrail(
                    entity_type='system',
                    entity_id=0,
                    action='login_failed',
                    user_id=None,
                    description='wave2 seeded failed login',
                    tenant_id=test_tenant.id,
                )
            )
        db.session.flush()
        from routes.super_admin.analytics import get_smart_recommendations

        recs = get_smart_recommendations()
        assert any(r['type'] == 'security' for r in recs)

    def test_security_threats_high_and_critical_after_seeding(
        self, app, db, test_tenant, rollback_db
    ):
        from models.audit_trail import AuditTrail

        for _ in range(21):
            db.session.add(
                AuditTrail(
                    entity_type='system',
                    entity_id=0,
                    action='login_failed',
                    user_id=None,
                    description='wave2 seeded failed login',
                    tenant_id=test_tenant.id,
                )
            )
        db.session.add(
            AuditTrail(
                entity_type='system',
                entity_id=0,
                action='unauthorized_access',
                user_id=None,
                description='wave2 seeded suspicious action',
                tenant_id=test_tenant.id,
            )
        )
        db.session.flush()
        from routes.super_admin.analytics import get_security_threats

        threats = get_security_threats()
        assert any(t['type'] == 'high' for t in threats)
        assert any(t['type'] == 'critical' for t in threats)

    def test_security_threats_medium_after_eleven_failures(self, app, db, test_tenant, rollback_db):
        from models.audit_trail import AuditTrail

        for _ in range(11):
            db.session.add(
                AuditTrail(
                    entity_type='system',
                    entity_id=0,
                    action='login_failed',
                    user_id=None,
                    description='wave2 seeded failed login',
                    tenant_id=test_tenant.id,
                )
            )
        db.session.flush()
        from routes.super_admin.analytics import get_security_threats

        threats = get_security_threats()
        # 11 fresh rows put the 24h tally above the medium threshold; if the shared
        # fixture data already put it above 20 the severity may read 'high' instead.
        assert any(t['type'] in ('medium', 'high') for t in threats)

    def test_performance_optimization_peak_hour_and_department_load(
        self, app, db, test_tenant, rollback_db
    ):
        patient = _make_patient(db)
        dept = _make_department(db)
        doctor = User(
            username=_uniq('heavydoc'),
            email=f'{_uniq("heavydoc")}@example.com',
            full_name='Heavy Doctor',
            role='doctor',
            is_active=True,
            department_id=dept.id,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('Secret123!')
        db.session.add(doctor)
        db.session.flush()
        _make_visits(db, patient, 21, doctor_id=doctor.id, created_at=datetime.now(UTC))
        from routes.super_admin.analytics import get_performance_optimization

        opts = get_performance_optimization()
        kinds = {o['type'] for o in opts}
        assert 'load_balancing' in kinds
        assert 'resource_allocation' in kinds

    def test_predictive_analytics_reports_peak_hour(self, app, db, test_tenant, rollback_db):
        patient = _make_patient(db)
        _make_visits(db, patient, 2, created_at=datetime.now(UTC))
        from routes.super_admin.analytics import get_predictive_analytics

        result = get_predictive_analytics()
        assert result['peak_hour'] is not None
        assert result['peak_visits'] >= 1
        assert isinstance(result['predicted_visits_next_week'], int)

    def test_user_behavior_analysis_counts_day_of_week(self, app, db, test_tenant, rollback_db):
        u = User(
            username=_uniq('behavior'),
            email=f'{_uniq("behavior")}@example.com',
            full_name='Behavior User',
            role='nurse',
            is_active=True,
            tenant_id=test_tenant.id,
            last_login=datetime.now(),
        )
        u.set_password('Secret123!')
        db.session.add(u)
        db.session.flush()
        from routes.super_admin.analytics import get_user_behavior_analysis

        result = get_user_behavior_analysis()
        assert result['active_users'] >= 1
        assert result['daily_activity']
        assert sum(result['role_distribution'].values()) >= 1


# ---------------------------------------------------------------------------
# routes/super_admin/security.py + subscription.py -- SQL boolean NOT fix
# ---------------------------------------------------------------------------


class TestSecurityCenterFailedLoginCount:
    def test_failed_attempts_appear_in_rendered_stats(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.audit_trail import LoginAttempt

        base = (
            db.session.execute(
                select(sfunc.count())
                .select_from(LoginAttempt)
                .filter(
                    ~LoginAttempt.success,
                    LoginAttempt.created_at >= datetime.now(UTC) - timedelta(hours=24),
                )
            ).scalar()
            or 0
        )
        marker = _uniq('wave2fail')
        for _ in range(7):
            db.session.add(LoginAttempt(username=marker, success=False, user_ip='10.11.12.13'))
        db.session.flush()

        resp = sa_client.get('/super-admin/security-center')
        assert resp.status_code == 200
        # The template renders stats.failed_logins_24h inside its KPI card.
        assert f'<div class="h3">{base + 7}</div>' in resp.get_data(as_text=True)


class TestChangePlanListsRealPackages:
    def test_active_non_deprecated_version_is_offered(
        self, sa_client, db, test_tenant, monkeypatch
    ):
        from app.core.saas.models import Package, PackageVersion

        pkg = Package(
            name=_uniq('Wave2Pkg'),
            slug=_uniq('wave2pkg'),
            category='bundle',
            is_active=True,
        )
        db.session.add(pkg)
        db.session.flush()
        version = PackageVersion(
            package_id=pkg.id,
            version='9.9.9',
            changelog='wave2',
            is_deprecated=False,
            published_at=datetime.now(UTC),
        )
        dep_pkg = Package(
            name=_uniq('Wave2Dep'),
            slug=_uniq('wave2dep'),
            category='bundle',
            is_active=True,
        )
        db.session.add(dep_pkg)
        db.session.flush()
        dep_version = PackageVersion(
            package_id=dep_pkg.id,
            version='8.8.8',
            changelog='wave2',
            is_deprecated=True,
            published_at=datetime.now(UTC),
        )
        db.session.add(version)
        db.session.add(dep_version)
        db.session.flush()

        captured = {}

        def fake_render(template, **context):
            captured.update(context)
            return 'ok'

        monkeypatch.setattr('routes.super_admin.subscription.render_template', fake_render)
        resp = sa_client.get('/super-admin/change-plan')
        assert resp.status_code == 200
        offered = {v.package.name for v in captured['available_versions']}
        assert pkg.name in offered
        assert dep_pkg.name not in offered


# ---------------------------------------------------------------------------
# routes/super_admin/roles.py -- deep branches
# ---------------------------------------------------------------------------


class TestDepartmentPermissionsDeep:
    def test_manage_flag_implies_can_access(self, sa_client, db, test_tenant):
        role = _make_role(db, test_tenant)
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={f'dept_{dept.id}_can_manage_visits': 'on'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.advanced_permissions import DepartmentPermission

        rows = (
            db.session.execute(
                select(DepartmentPermission).filter_by(role_id=role.id, department_id=dept.id)
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].can_access is True
        assert rows[0].can_manage_visits is True

    def test_dept_all_manage_flag_implies_can_access(self, sa_client, db, test_tenant):
        role = _make_role(db, test_tenant)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={'dept_all_can_manage_staff': 'on'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.advanced_permissions import DepartmentPermission

        rows = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        )
        all_rows = [r for r in rows if r.department_id is None]
        assert len(all_rows) == 1
        assert all_rows[0].can_access is True
        assert all_rows[0].can_manage_staff is True

    def test_no_flags_inserts_nothing(self, sa_client, db, test_tenant):
        role = _make_role(db, test_tenant)
        dept = _make_department(db)
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/department-permissions',
            data={f'dept_{dept.id}_can_access': '', f'dept_{dept.id}_can_manage_visits': ''},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.advanced_permissions import DepartmentPermission

        rows = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        )
        assert rows == []

    def test_department_permissions_redirects_when_tables_missing(
        self, sa_client, test_tenant, monkeypatch
    ):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', lambda _engine: FakeInsp())
        resp = sa_client.get('/super-admin/roles/1/department-permissions', follow_redirects=False)
        assert resp.status_code == 302


class TestPermissionsMatrixGuards:
    def test_matrix_redirects_when_tables_missing(self, sa_client, monkeypatch):
        class FakeInsp:
            def has_table(self, name):
                return False

        monkeypatch.setattr('sqlalchemy.inspect', lambda _engine: FakeInsp())
        resp = sa_client.get('/super-admin/permissions-matrix', follow_redirects=False)
        assert resp.status_code == 302

    def test_matrix_skips_invalid_permission_ids(self, sa_client, db, test_tenant):
        from models.permissions import RolePermission

        role = _make_role(db, test_tenant)
        perm = _make_permission(db, test_tenant)
        resp = sa_client.post(
            '/super-admin/permissions-matrix',
            data={f'role_{role.id}_permissions': ['not-an-int', str(perm.id)]},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = db.session.execute(select(RolePermission).filter_by(role_id=role.id)).scalars().all()
        assert [r.permission_id for r in rows] == [perm.id]


class TestEditRoleRollback:
    def test_bad_permission_id_rolls_back_delete(self, sa_client, db, test_tenant):
        from models.permissions import RolePermission

        role = _make_role(db, test_tenant)
        perm = _make_permission(db, test_tenant)
        db.session.add(
            RolePermission(role_id=role.id, permission_id=perm.id, tenant_id=test_tenant.id)
        )
        db.session.commit()
        resp = sa_client.post(
            f'/super-admin/roles/{role.id}/edit',
            data={'name': role.name, 'permissions': ['not-an-int']},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = db.session.execute(select(RolePermission).filter_by(role_id=role.id)).scalars().all()
        assert [r.permission_id for r in rows] == [perm.id]


class TestCreateRoleValidation:
    def test_missing_name_persists_no_role(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.permissions import Role

        marker = _uniq('missingname')
        resp = sa_client.post(
            '/super-admin/roles/create',
            data={'name_ar': marker, 'description': 'no name submitted'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302)
        count = db.session.execute(
            select(sfunc.count()).select_from(Role).filter_by(name_ar=marker)
        ).scalar()
        assert count == 0


# ---------------------------------------------------------------------------
# routes/super_admin/users.py -- pricing and department-access edges
# ---------------------------------------------------------------------------


class TestCreateUserPricingEdges:
    def test_doctor_with_unparseable_price_creates_no_pricing_row(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.pricing import DoctorPricing

        username = _uniq('doc')
        resp = sa_client.post(
            '/super-admin/users/create',
            data={
                'username': username,
                'email': f'{username}@example.com',
                'full_name': 'Doctor Wave2',
                'password': 'Secret123!',
                'role': 'doctor',
                'consultation_price': 'bogus',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        user = db.session.execute(select(User).filter_by(username=username)).scalars().first()
        assert user is not None
        count = db.session.execute(
            select(sfunc.count()).select_from(DoctorPricing).filter_by(doctor_id=user.id)
        ).scalar()
        assert count == 0

    def test_non_doctor_with_price_fields_creates_no_pricing_row(self, sa_client, db):
        from sqlalchemy import func as sfunc

        from models.pricing import DoctorPricing

        username = _uniq('nurse')
        resp = sa_client.post(
            '/super-admin/users/create',
            data={
                'username': username,
                'email': f'{username}@example.com',
                'full_name': 'Nurse Wave2',
                'password': 'Secret123!',
                'role': 'nurse',
                'consultation_price': '50',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        user = db.session.execute(select(User).filter_by(username=username)).scalars().first()
        assert user is not None
        count = db.session.execute(
            select(sfunc.count()).select_from(DoctorPricing).filter_by(doctor_id=user.id)
        ).scalar()
        assert count == 0

    def test_doctor_pricing_inherits_department(self, sa_client, db):
        from models.pricing import DoctorPricing

        dept = _make_department(db)
        username = _uniq('doc')
        resp = sa_client.post(
            '/super-admin/users/create',
            data={
                'username': username,
                'email': f'{username}@example.com',
                'full_name': 'Doctor Wave2',
                'password': 'Secret123!',
                'role': 'doctor',
                'department_id': str(dept.id),
                'consultation_price': '80',
                'follow_up_price': '40',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        user = db.session.execute(select(User).filter_by(username=username)).scalars().first()
        assert user is not None
        pricing = (
            db.session.execute(select(DoctorPricing).filter_by(doctor_id=user.id)).scalars().one()
        )
        assert float(pricing.consultation_price) == 80.0
        assert float(pricing.follow_up_price) == 40.0
        assert pricing.department_id == dept.id


class TestEditUserEdges:
    def test_edit_user_changes_password(self, sa_client, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(
            db, test_tenant, username=_uniq('pw'), role='doctor', password='OldSecret123!'
        )
        resp = sa_client.post(
            f'/super-admin/users/{target.id}/edit',
            data={
                'username': target.username,
                'email': target.email,
                'full_name': target.full_name,
                'role': 'doctor',
                'is_active': 'y',
                'new_password': 'NewSecret456!',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(target)
        assert target.check_password('NewSecret456!')

    def test_edit_user_extra_departments_replace_and_skip_invalid(self, sa_client, db, test_tenant):
        from models.user_department_access import UserDepartmentAccess
        from tests.tenant_context import ensure_test_user

        target = ensure_test_user(db, test_tenant, username=_uniq('extra'), role='nurse')
        dept_a = _make_department(db)
        dept_b = _make_department(db)
        db.session.add(
            UserDepartmentAccess(user_id=target.id, department_id=dept_a.id, can_access=True)
        )
        db.session.commit()
        resp = sa_client.post(
            f'/super-admin/users/{target.id}/edit',
            data={
                'username': target.username,
                'email': target.email,
                'full_name': target.full_name,
                'role': 'nurse',
                'is_active': 'y',
                'extra_department_ids': [str(dept_b.id), 'not-an-int'],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(UserDepartmentAccess).filter_by(user_id=target.id))
            .scalars()
            .all()
        )
        assert [r.department_id for r in rows] == [dept_b.id]
        assert all(r.can_access for r in rows)


# ---------------------------------------------------------------------------
# routes/super_admin/services.py -- category, pricing expansion, discounts
# ---------------------------------------------------------------------------


class TestCreateServiceCategoryMapping:
    @pytest.mark.parametrize(
        ('service_type', 'expected'),
        [('LAB', 'lab'), ('RADIOLOGY', 'radiology'), ('widget', 'general')],
    )
    def test_service_type_maps_to_category(self, sa_client, db, service_type, expected):
        from models.service import ServiceMaster

        resp = sa_client.post(
            '/super-admin/services/create',
            data={
                'name': _uniq('svc'),
                'name_ar': f'AR {_uniq("a")}',
                'service_type': service_type,
                'base_price': '10',
            },
        )
        assert resp.status_code == 200
        svc = (
            db.session.execute(select(ServiceMaster).order_by(ServiceMaster.id.desc()))
            .scalars()
            .first()
        )
        assert svc.category == expected

    def test_unsupported_currency_is_coerced(self, sa_client, db):
        from models.service import ServiceMaster

        resp = sa_client.post(
            '/super-admin/services/create',
            data={
                'name': _uniq('svc'),
                'name_ar': f'AR {_uniq("b")}',
                'currency': 'JPY',
                'base_price': '10',
            },
        )
        assert resp.status_code == 200
        svc = (
            db.session.execute(select(ServiceMaster).order_by(ServiceMaster.id.desc()))
            .scalars()
            .first()
        )
        assert svc.currency != 'JPY'

    def test_duration_and_daily_cap_one_is_accepted(self, sa_client, db):
        from models.service import ServiceMaster

        resp = sa_client.post(
            '/super-admin/services/create',
            data={
                'name': _uniq('svc'),
                'name_ar': f'AR {_uniq("c")}',
                'base_price': '10',
                'duration': '1',
                'max_daily': '1',
            },
        )
        assert resp.status_code == 200
        svc = (
            db.session.execute(select(ServiceMaster).order_by(ServiceMaster.id.desc()))
            .scalars()
            .first()
        )
        assert svc.duration == 1
        assert svc.max_daily == 1


class TestServicePricingExpansion:
    def test_pricing_page_lists_all_four_price_kinds(self, sa_client, db, sa_user, monkeypatch):
        from models.pricing_management import PricingManagement

        svc = _make_service(db)
        db.session.add(
            PricingManagement(
                service_id=svc.id,
                base_price=100,
                emergency_price=200,
                private_price=300,
                insurance_price=150,
                discount_percentage=5.0,
                discount_amount=10,
                currency='ILS',
                created_by=sa_user.id,
                is_active=True,
            )
        )
        db.session.commit()

        captured = {}

        def fake_render(template, **context):
            captured.update(context)
            return 'ok'

        monkeypatch.setattr('routes.super_admin.services.render_template', fake_render)
        resp = sa_client.get(f'/super-admin/service-pricing/{svc.id}')
        assert resp.status_code == 200
        kinds = sorted(p['price_type'] for p in captured['pricing'])
        assert kinds == ['insurance', 'standard', 'urgent', 'vip']
        by_kind = {p['price_type']: p for p in captured['pricing']}
        assert by_kind['standard']['price'] == 100.0
        assert by_kind['urgent']['price'] == 200.0
        assert by_kind['vip']['price'] == 300.0
        assert by_kind['insurance']['price'] == 150.0
        assert by_kind['standard']['discount_percentage'] == 5.0

    def test_pricing_post_with_unparseable_discounts_defaults_zero(self, sa_client, db):
        from models.pricing_management import PricingManagement

        svc = _make_service(db)
        resp = sa_client.post(
            f'/super-admin/service-pricing/{svc.id}',
            data={
                'price_type': 'insurance',
                'price': '250',
                'discount_percentage': 'bogus',
                'discount_amount': 'bogus',
                'currency': 'ILS',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rec = (
            db.session.execute(select(PricingManagement).filter_by(service_id=svc.id))
            .scalars()
            .one()
        )
        assert float(rec.insurance_price) == 250.0
        assert float(rec.base_price or 0) == 0.0
        assert float(rec.discount_percentage or 0) == 0.0
        assert float(rec.discount_amount or 0) == 0.0


# ---------------------------------------------------------------------------
# routes/super_admin/data.py + analytics reports + branding theme guards
# ---------------------------------------------------------------------------


class TestDownloadExportRoundTrip:
    def test_download_export_existing_file_roundtrip(self, sa_client):
        name = _uniq('export') + '.json'
        payload = b'{"wave2": true}'
        path = os.path.join('instance', name)
        os.makedirs('instance', exist_ok=True)
        with open(path, 'wb') as fh:
            fh.write(payload)
        try:
            resp = sa_client.get(f'/super-admin/download-export/{name}')
            assert resp.status_code == 200
            assert resp.get_data() == payload
        finally:
            resp.close()
            if os.path.exists(path):
                with contextlib.suppress(OSError):
                    os.remove(path)


class TestReportsExtended:
    @pytest.mark.parametrize('report', ['compare_month', 'compare_year'])
    def test_compare_reports_with_department_filter(self, sa_client, db, report):
        dept = _make_department(db)
        resp = sa_client.get(
            f'/super-admin/reports?report={report}'
            f'&start_date=2026-01-01&end_date=2026-12-31&department_id={dept.id}'
        )
        assert resp.status_code == 200

    def test_unknown_report_renders_without_result(self, sa_client):
        resp = sa_client.get('/super-admin/reports?report=definitely_not_a_report')
        assert resp.status_code == 200


class TestApplyThemeInactive:
    def test_apply_theme_inactive_returns_404(self, sa_client, db):
        from models.branding import SystemTheme

        theme = SystemTheme(
            name=_uniq('theme'),
            name_ar='AR',
            primary_color='#111111',
            secondary_color='#222222',
            accent_color='#333333',
            background_color='#ffffff',
            text_color='#000000',
            is_active=False,
        )
        db.session.add(theme)
        db.session.commit()
        token = _csrf_from(sa_client, '/super-admin/branding')
        resp = sa_client.post(
            f'/super-admin/branding/apply-theme/{theme.id}',
            data={'csrf_token': token},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Access control -- the write verbs must require authentication too
# ---------------------------------------------------------------------------


class TestAccessControlWriteVerbs:
    @pytest.mark.parametrize(
        'path',
        [
            '/super-admin/services/create',
            '/super-admin/users/create',
            '/super-admin/roles/create',
            '/super-admin/permissions/create',
            '/super-admin/department-staff/1/add',
            '/super-admin/service-pricing/delete/1',
        ],
    )
    def test_unauthenticated_post_redirects(self, client, path):
        resp = client.post(path, follow_redirects=False)
        assert resp.status_code in (302, 303)
