"""
Real HTTP coverage for routes/backup_routes.py.

Every endpoint and helper in the module is exercised through the Flask test
client against the migrated test schema. Writes go through ``rollback_db`` so
the session-scoped test database stays pristine. External side effects
(pg_dump/psql subprocesses, the Celery queue) are replaced with explicit
fakes whose behaviour the tests assert on — nothing here pretends a dump
happened when it did not.
"""

from __future__ import annotations

import gzip
import io
import os
import subprocess
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _login(client, db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role=role, password=password)
    login_test_client(client, user, tenant, password)
    return user


def _make_backup(db, tenant, **kw):
    from app.shared.enums import BackupStatus
    from models.backup import Backup

    row = Backup(
        tenant_id=tenant.id,
        backup_name=kw.get('backup_name', _uniq('backup')),
        backup_type=kw.get('backup_type', 'full'),
        backup_path=kw.get('backup_path', f'backups/{_uniq("file")}.sql.gz'),
        backup_status=kw.get('backup_status', BackupStatus.COMPLETED),
        description=kw.get('description'),
        is_encrypted=kw.get('is_encrypted', False),
        is_scheduled=kw.get('is_scheduled', False),
        backup_size=kw.get('backup_size'),
        restore_count=kw.get('restore_count', 0),
    )
    db.session.add(row)
    db.session.commit()
    return row


def _patch_backup_path(monkeypatch, target):
    def _fake_build_backup_path(base_dir, backup_name, when=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        return str(target)

    monkeypatch.setattr('routes.backup_routes.build_backup_path', _fake_build_backup_path)
    return target


def _force_sync_backup_path(monkeypatch):
    monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
    monkeypatch.setattr('celery_app.task_always_eager', lambda: False)


def _make_fake_popen(recorded, stdout_bytes, returncode, stderr_bytes=b'dump: connection refused'):
    """Build a fake subprocess.Popen constructor recording argv+env."""

    def _ctor(cmd, env=None, stdout=None, stderr=None):
        recorded.append({'cmd': list(cmd), 'env': env or {}})
        proc = type('FakePopen', (), {})()
        proc.cmd = list(cmd)
        proc.env = env or {}
        proc.stdout = io.BytesIO(stdout_bytes)
        proc.stderr = io.BytesIO(b'' if returncode == 0 else stderr_bytes)
        proc.returncode = returncode
        proc.wait = lambda **_kwargs: returncode
        proc.poll = lambda: returncode
        proc.kill = lambda: None
        return proc

    return _ctor


def _fake_subprocess_namespace(popen):
    return SimpleNamespace(
        Popen=popen,
        PIPE=-1,
        TimeoutExpired=subprocess.TimeoutExpired,
    )


class TestBackupDashboard:
    def test_dashboard_requires_login(self, client):
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_dashboard_rejects_non_admin_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakrec'), 'reception')
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' not in resp.headers['Location']

    def test_dashboard_renders_for_super_admin(self, app, client, db, test_tenant, rollback_db):
        from app.shared.enums import BackupStatus

        _login(client, db, test_tenant, _uniq('bakdash'), 'super_admin')
        _make_backup(db, test_tenant, backup_status=BackupStatus.COMPLETED, backup_size=2048)
        _make_backup(db, test_tenant, backup_status=BackupStatus.FAILED)
        _make_backup(db, test_tenant, is_scheduled=True)
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 200

    def test_dashboard_legacy_alias_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('baklegacy'), 'super_admin')
        resp = client.get('/backup/backup/dashboard')
        assert resp.status_code == 200

    def test_dashboard_exception_redirects_to_main(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('bakdasherr'), 'super_admin')

        def _boom(*_args, **_kwargs):
            raise RuntimeError('template exploded')

        monkeypatch.setattr('routes.backup_routes.render_template', _boom)
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 302


class TestBackupCreate:
    def test_create_get_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakget'), 'super_admin')
        resp = client.get('/backup/create')
        assert resp.status_code == 200

    def test_create_post_defaults_when_form_empty(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdef'), 'super_admin')
        _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'default.sql.gz')
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: True)
        monkeypatch.setattr(queue_service, 'queue_system_backup', lambda *_a, **_k: 'task-1')

        resp = client.post('/backup/create', data={})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_name == 'medical_backup'
        assert row.backup_type == 'full'
        assert row.is_encrypted is False

    def test_create_sync_success_marks_completed(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from models.backup import Backup

        admin = _login(client, db, test_tenant, _uniq('bakok'), 'super_admin')
        target = _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'nightly.sql.gz')
        _force_sync_backup_path(monkeypatch)
        monkeypatch.setenv(
            'DATABASE_URL', 'postgresql://dumpuser:dumppass@dbhost.internal:5544/dumpdb'
        )
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)

        recorded = []
        popen = _make_fake_popen(recorded, b'-- mock pg_dump output\nCREATE TABLE t(id int);\n', 0)
        monkeypatch.setattr(
            'services.pg_backup_service.subprocess', _fake_subprocess_namespace(popen)
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/fake/{name}'
        )

        resp = client.post(
            '/backup/create',
            data={
                'backup_name': 'nightly backup',
                'backup_type': 'full',
                'description': 'nightly snapshot',
                'is_encrypted': 'on',
            },
        )
        assert resp.status_code == 302
        assert '/backup/dashboard' in resp.headers['Location']

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'COMPLETED'
        assert row.backup_size and row.backup_size > 0
        assert row.is_encrypted is True
        assert row.description == 'nightly snapshot'
        assert row.created_by == admin.id
        assert row.completed_at is not None

        assert len(recorded) == 1
        cmd = recorded[0]['cmd']
        assert cmd[0] == '/fake/pg_dump'
        assert '--host' in cmd and 'dbhost.internal' in cmd
        assert '--port' in cmd and '5544' in cmd
        assert '--username' in cmd and 'dumpuser' in cmd
        assert '--dbname' in cmd and 'dumpdb' in cmd
        assert '--no-owner' in cmd and '--no-acl' in cmd
        assert recorded[0]['env'].get('PGPASSWORD') == 'dumppass'

        with gzip.open(target, 'rb') as fh:
            assert fh.read() == b'-- mock pg_dump output\nCREATE TABLE t(id int);\n'

    def test_create_sync_nonzero_exit_marks_failed_and_removes_artifact(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakfail'), 'super_admin')
        target = _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'doomed.sql.gz')
        _force_sync_backup_path(monkeypatch)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://dumpuser:dumppass@dbhost:5432/dumpdb')
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)

        recorded = []
        popen = _make_fake_popen(recorded, b'', 1)
        monkeypatch.setattr(
            'services.pg_backup_service.subprocess', _fake_subprocess_namespace(popen)
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/fake/{name}'
        )

        resp = client.post('/backup/create', data={'backup_name': 'doomed'})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'FAILED'
        assert 'connection refused' in (row.backup_notes or '')
        # the route removes the partial artifact pg_dump left behind
        assert not os.path.exists(target)

    def test_create_sync_pg_dump_missing_marks_failed_without_artifact(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from models.backup import Backup
        from routes import backup_routes as br

        PgBackupError = br.PgBackupError
        _login(client, db, test_tenant, _uniq('baknodump'), 'super_admin')
        target = _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'no_dump.sql.gz')
        _force_sync_backup_path(monkeypatch)

        def _missing(_backup):
            raise PgBackupError('pg_dump not found on PATH — install PostgreSQL client tools')

        monkeypatch.setattr('routes.backup_routes.create_backup_file', _missing)

        resp = client.post('/backup/create', data={'backup_name': 'no pg_dump around'})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'FAILED'
        assert 'pg_dump' in (row.backup_notes or '')
        assert not target.exists()

    def test_create_sync_pg_backup_error_removes_existing_artifact(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from models.backup import Backup
        from routes import backup_routes as br

        PgBackupError = br.PgBackupError
        _login(client, db, test_tenant, _uniq('bakart'), 'super_admin')
        target = _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'stale.sql.gz')
        _force_sync_backup_path(monkeypatch)

        def _create_and_fail(_backup):
            # simulate a failure that leaves a partial artifact behind
            target.write_bytes(b'partial')
            raise PgBackupError('disk full mid-dump')

        monkeypatch.setattr('routes.backup_routes.create_backup_file', _create_and_fail)

        resp = client.post('/backup/create', data={'backup_name': 'stale artifact'})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'FAILED'
        assert 'disk full' in (row.backup_notes or '')
        assert not target.exists()

    def test_create_queues_when_celery_enabled(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakq1'), 'super_admin')
        target = _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'queued.sql.gz')
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: True)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)

        queued = []

        def _fake_queue(backup_id, tenant_id=None):
            queued.append({'backup_id': backup_id, 'tenant_id': tenant_id})
            return 'task-123'

        monkeypatch.setattr(queue_service, 'queue_system_backup', _fake_queue)

        resp = client.post('/backup/create', data={'backup_name': 'queued backup'})
        assert resp.status_code == 302
        assert '/backup/dashboard' in resp.headers['Location']

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'IN_PROGRESS'
        assert queued and queued[0]['backup_id'] == row.id
        assert queued[0]['tenant_id'] == row.tenant_id
        assert not target.exists()

    def test_create_queues_when_task_always_eager(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service

        _login(client, db, test_tenant, _uniq('bakq2'), 'super_admin')
        _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'eager.sql.gz')
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: True)

        queued = []
        monkeypatch.setattr(
            queue_service,
            'queue_system_backup',
            lambda backup_id, **_kwargs: queued.append(backup_id) or 'task-9',
        )

        resp = client.post('/backup/create', data={'backup_name': 'eager backup'})
        assert resp.status_code == 302
        assert '/backup/dashboard' in resp.headers['Location']
        assert queued

    def test_create_queue_error_redirects_to_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakqerr'), 'super_admin')
        _patch_backup_path(monkeypatch, tmp_path / 'backups' / 'queue_fail.sql.gz')
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: True)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)

        def _boom_queue(_backup_id, tenant_id=None):
            raise queue_service.BackupQueueError('celery_not_configured')

        monkeypatch.setattr(queue_service, 'queue_system_backup', _boom_queue)

        resp = client.post('/backup/create', data={'backup_name': 'queue fail backup'})
        assert resp.status_code == 302
        assert 'create' in resp.headers['Location']

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        # the row stays IN_PROGRESS: the failure to enqueue is reported to the
        # user but the backup record is kept for inspection/retry
        assert row.backup_status == 'IN_PROGRESS'

    def test_create_unexpected_exception_renders_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('bakerr'), 'super_admin')

        def _boom(*_args, **_kwargs):
            raise RuntimeError('disk gone')

        monkeypatch.setattr('routes.backup_routes.build_backup_path', _boom)
        resp = client.post('/backup/create', data={'backup_name': 'kaboom'})
        assert resp.status_code == 200


class TestBackupList:
    def test_list_renders_with_seeded_rows(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('baklist'), 'super_admin')
        _make_backup(db, test_tenant, backup_name=_uniq('listed'))
        resp = client.get('/backup/list')
        assert resp.status_code == 200

    def test_list_exception_redirects_to_dashboard(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('baklisterr'), 'super_admin')

        def _boom(*_args, **_kwargs):
            raise RuntimeError('template exploded')

        monkeypatch.setattr('routes.backup_routes.render_template', _boom)
        resp = client.get('/backup/list')
        assert resp.status_code == 302
        assert '/backup/dashboard' in resp.headers['Location']


class TestBackupRestore:
    def _completed_backup(self, db, tenant, tmp_path, name=None):
        name = name or _uniq('restore_src')
        artifact = tmp_path / f'{name}.sql.gz'
        with gzip.open(artifact, 'wb') as fh:
            fh.write(b'SELECT 1;\n')
        return _make_backup(
            db, tenant, backup_name=name, backup_path=str(artifact), restore_count=0
        )

    def test_restore_success_increments_counters(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakrestore'), 'super_admin')
        row = self._completed_backup(db, test_tenant, tmp_path)

        calls = []

        def _fake_restore(path):
            calls.append(path)

        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', _fake_restore)

        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302
        assert calls == [row.backup_path]

        from models.backup import Backup

        db.session.expire_all()
        refreshed = db.session.get(Backup, row.id)
        assert refreshed.restore_count == 1
        assert refreshed.last_restore is not None
        assert refreshed.last_restore_by is not None

    def test_restore_pg_error_keeps_counters(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from services.pg_backup_service import PgBackupError

        _login(client, db, test_tenant, _uniq('bakresfail'), 'super_admin')
        row = self._completed_backup(db, test_tenant, tmp_path, 'restore_fail')

        def _boom(_path):
            raise PgBackupError('simulated restore failure')

        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', _boom)

        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302

        from models.backup import Backup

        db.session.expire_all()
        refreshed = db.session.get(Backup, row.id)
        assert refreshed.restore_count == 0

    def test_restore_rejects_non_restorable_backup(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from app.shared.enums import BackupStatus

        _login(client, db, test_tenant, _uniq('bakpend'), 'super_admin')
        row = _make_backup(
            db,
            test_tenant,
            backup_name=_uniq('pending'),
            backup_path=str(tmp_path / 'pending.sql.gz'),
            backup_status=BackupStatus.IN_PROGRESS,
        )

        called = []
        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', called.append)
        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302
        assert called == []

    def test_restore_missing_backup_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bak404'), 'super_admin')
        resp = client.post('/backup/restore/999999999')
        assert resp.status_code == 404

    def test_restore_unexpected_exception_redirects_to_list(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakreserr'), 'super_admin')
        row = self._completed_backup(db, test_tenant, tmp_path, 'restore_err')

        def _boom(_backup):
            raise RuntimeError('restore exploded')

        monkeypatch.setattr('routes.backup_routes.restore_backup_file', _boom)
        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302
        assert '/backup/list' in resp.headers['Location']


class TestBackupDownload:
    def test_download_sends_artifact_bytes(
        self, app, client, db, test_tenant, rollback_db, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakdl'), 'super_admin')
        payload = b'\x1f\x8b-fake-artifact-bytes'
        artifact = tmp_path / 'download_me.sql.gz'
        artifact.write_bytes(payload)
        row = _make_backup(db, test_tenant, backup_name='download_me', backup_path=str(artifact))

        resp = client.get(f'/backup/download/{row.id}')
        assert resp.status_code == 200
        assert resp.data == payload
        assert 'download_me' in (resp.headers.get('Content-Disposition') or '')

    def test_download_missing_file_redirects(
        self, app, client, db, test_tenant, rollback_db, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakdlmiss'), 'super_admin')
        row = _make_backup(
            db,
            test_tenant,
            backup_name=_uniq('ghost'),
            backup_path=str(tmp_path / 'does_not_exist.sql.gz'),
        )
        resp = client.get(f'/backup/download/{row.id}')
        assert resp.status_code == 302
        assert '/backup/list' in resp.headers['Location']

    def test_download_missing_row_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakdl404'), 'super_admin')
        resp = client.get('/backup/download/999999999')
        assert resp.status_code == 404

    def test_download_send_file_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakdlerr'), 'super_admin')
        artifact = tmp_path / 'send_fail.sql.gz'
        artifact.write_bytes(b'data')
        row = _make_backup(db, test_tenant, backup_name='send_fail', backup_path=str(artifact))

        def _boom(*_args, **_kwargs):
            raise RuntimeError('disk read error')

        monkeypatch.setattr('routes.backup_routes.send_file', _boom)
        resp = client.get(f'/backup/download/{row.id}')
        assert resp.status_code == 302
        assert '/backup/list' in resp.headers['Location']


class TestBackupDelete:
    def test_delete_removes_file_and_row(self, app, client, db, test_tenant, rollback_db, tmp_path):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdel'), 'super_admin')
        artifact = tmp_path / 'delete_me.sql.gz'
        artifact.write_bytes(b'data')
        row = _make_backup(db, test_tenant, backup_name='delete_me', backup_path=str(artifact))
        row_id = row.id

        resp = client.post(f'/backup/delete/{row_id}')
        assert resp.status_code == 302
        assert not artifact.exists()
        assert db.session.get(Backup, row_id) is None

    def test_delete_without_file_still_removes_row(
        self, app, client, db, test_tenant, rollback_db, tmp_path
    ):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdelmiss'), 'super_admin')
        row = _make_backup(
            db,
            test_tenant,
            backup_name=_uniq('no_file'),
            backup_path=str(tmp_path / 'never_existed.sql.gz'),
        )

        resp = client.post(f'/backup/delete/{row.id}')
        assert resp.status_code == 302
        assert db.session.get(Backup, row.id) is None

    def test_delete_missing_row_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakdel404'), 'super_admin')
        resp = client.post('/backup/delete/999999999')
        assert resp.status_code == 404

    def test_delete_commit_failure_redirects_to_list(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakdelerr'), 'super_admin')
        artifact = tmp_path / 'delete_fail.sql.gz'
        artifact.write_bytes(b'data')
        row = _make_backup(db, test_tenant, backup_name='delete_fail', backup_path=str(artifact))

        def _boom(*_args, **_kwargs):
            raise RuntimeError('commit exploded')

        monkeypatch.setattr('routes.backup_routes.safe_commit', _boom)
        resp = client.post(f'/backup/delete/{row.id}')
        assert resp.status_code == 302
        assert '/backup/list' in resp.headers['Location']
        # os.remove already ran before the commit failed: the file is gone even
        # though the failure is reported instead of pretending success
        assert not artifact.exists()


class TestBackupHelpers:
    def test_create_backup_file_delegates_to_pg_dump(self, monkeypatch):
        from routes import backup_routes

        monkeypatch.setattr(
            backup_routes, 'run_pg_dump_sql_gz', lambda path: 4242 if path == 'x.sql.gz' else -1
        )
        backup = SimpleNamespace(backup_path='x.sql.gz')
        assert backup_routes.create_backup_file(backup) == 4242

    def test_restore_backup_file_success(self, monkeypatch):
        from routes import backup_routes

        calls = []
        monkeypatch.setattr(backup_routes, 'restore_pg_sql_gz', calls.append)
        backup = SimpleNamespace(id=7, backup_path='y.sql.gz')
        assert backup_routes.restore_backup_file(backup) is True
        assert calls == ['y.sql.gz']

    def test_restore_backup_file_pg_error_returns_false(self, monkeypatch):
        from routes import backup_routes

        def _boom(_path):
            raise backup_routes.PgBackupError('psql exploded')

        monkeypatch.setattr(backup_routes, 'restore_pg_sql_gz', _boom)
        backup = SimpleNamespace(id=8, backup_path='z.sql.gz')
        assert backup_routes.restore_backup_file(backup) is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
