"""Tests for Celery / background tenant context binding."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup


def _unique_slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestWithTenantContext:
    def test_with_tenant_context_sets_g_tenant_id(self, app):
        from services.tenant_job_runner import with_tenant_context
        from app.core.tenant.models import Tenant, TenantStatus
        from flask import g

        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('ctx'),
                name='Ctx Tenant',
                contact_email='ctx@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()

            captured = {}

            def job():
                captured['tenant_id'] = g.get('tenant_id')
                return 'ok'

            result = with_tenant_context(app, tenant.id, job)
            assert result == 'ok'
            assert captured['tenant_id'] == tenant.id


class TestRunSystemBackupTenantContext:
    @pytest.fixture
    def celery_eager(self, monkeypatch):
        monkeypatch.setenv('CELERY_ENABLED', 'true')
        monkeypatch.setenv('CELERY_TASK_ALWAYS_EAGER', 'true')
        from celery_app import get_celery_app
        get_celery_app().conf.task_always_eager = True

    def test_run_system_backup_uses_tenant_context(self, app, test_user, celery_eager, monkeypatch, tmp_path):
        from celery_app import init_celery_app
        from app.core.tenant.models import Tenant, TenantStatus
        from services.pg_backup_service import build_backup_path
        from tasks.system_tasks import run_system_backup

        init_celery_app(app)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/medical')
        monkeypatch.setenv('BACKUP_LOCAL_DIR', str(tmp_path))

        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('backup-t'),
                name='Backup Tenant',
                contact_email='backup@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()

            path = build_backup_path(str(tmp_path), 'tenant_ctx_backup')
            backup = Backup(
                tenant_id=tenant.id,
                backup_name='tenant_ctx_backup',
                backup_type='full',
                backup_path=path,
                backup_status=BackupStatus.PENDING,
                created_by=test_user.id,
            )
            db.session.add(backup)
            db.session.commit()
            backup_id = backup.id
            tenant_id = tenant.id

        tenant_ids_seen = []

        def fake_execute(backup_id_arg):
            from flask import g
            tenant_ids_seen.append(g.get('tenant_id'))
            backup_row = db.session.get(Backup, backup_id_arg)
            backup_row.backup_status = BackupStatus.COMPLETED
            backup_row.backup_size = 64
            db.session.commit()
            return backup_row

        with patch('services.backup_execution_service.execute_backup_by_id', side_effect=fake_execute):
            result = run_system_backup(backup_id)

        assert result['backup_id'] == backup_id
        assert tenant_ids_seen == [tenant_id]


class TestTenantTaskDecorator:
    def test_tenant_task_wraps_with_context(self, app):
        from flask import g
        from services.tenant_job_runner import bind_flask_app, tenant_task, with_tenant_context
        from app.core.tenant.models import Tenant, TenantStatus

        bind_flask_app(app)
        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('task'),
                name='Task Tenant',
                contact_email='task@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()
            tenant_id = tenant.id

        captured = []

        @tenant_task()
        def sample_job(*, tenant_id=None):
            captured.append(g.get('tenant_id'))
            return 'done'

        with app.app_context():
            assert sample_job(tenant_id=tenant_id) == 'done'
        assert captured == [tenant_id]

    def test_tenant_task_without_tenant_id_runs_unscoped(self, app):
        from services.tenant_job_runner import bind_flask_app, tenant_task

        bind_flask_app(app)

        @tenant_task()
        def global_job():
            return 'global'

        with app.app_context():
            assert global_job() == 'global'


class TestWithTenantContextEdgeCases:
    def test_missing_tenant_returns_none(self, app):
        from services.tenant_job_runner import with_tenant_context

        with app.app_context():
            result = with_tenant_context(app, 99999999, lambda: 'should not run')
        assert result is None

    def test_reuses_existing_app_context(self, app):
        from flask import g
        from services.tenant_job_runner import with_tenant_context
        from app.core.tenant.models import Tenant, TenantStatus

        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('nested'),
                name='Nested',
                contact_email='nested@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()

            seen = []
            with_tenant_context(app, tenant.id, lambda: seen.append(g.get('tenant_id')))
            assert seen == [tenant.id]


class TestForEachTenantResilience:
    def test_continues_when_single_tenant_job_fails(self, app, monkeypatch):
        from services.tenant_job_runner import for_each_tenant
        from app.core.tenant.models import Tenant, TenantStatus
        from app.extensions import db

        with app.app_context():
            t_ok = Tenant(
                slug=_unique_slug('ok-job'),
                name='OK',
                contact_email='ok@example.com',
                status=TenantStatus.ACTIVE,
            )
            t_fail = Tenant(
                slug=_unique_slug('fail-job'),
                name='Fail',
                contact_email='fail@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add_all([t_ok, t_fail])
            db.session.commit()
            ok_id, fail_id = t_ok.id, t_fail.id

        seen = []

        def job(tenant_id):
            if tenant_id == fail_id:
                raise RuntimeError('job failed')
            seen.append(tenant_id)

        for_each_tenant(app, job)
        assert ok_id in seen

    def test_tenant_task_uses_current_app_when_unbound(self, app):
        from flask import g
        from services.tenant_job_runner import tenant_task, with_tenant_context
        from app.core.tenant.models import Tenant, TenantStatus
        from app.extensions import db

        with app.app_context():
            tenant = Tenant(
                slug=_unique_slug('curapp'),
                name='CurApp',
                contact_email='cur@example.com',
                status=TenantStatus.ACTIVE,
            )
            db.session.add(tenant)
            db.session.commit()
            tenant_id = tenant.id

        captured = []

        @tenant_task()
        def job(*, tenant_id=None):
            captured.append(g.get('tenant_id'))
            return 'ok'

        with app.app_context():
            assert job(tenant_id=tenant_id) == 'ok'
        assert captured == [tenant_id]
