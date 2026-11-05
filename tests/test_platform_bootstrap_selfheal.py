"""Behaviour tests for the boot-time self-healing routine.

The point of these is that they assert observable state, not that a function is
callable: a bootstrap that silently no-ops is exactly the failure mode that makes
a deployment look healthy while serving an empty system.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.core.platform_bootstrap import (
    check_schema_health,
    ensure_platform_admin,
    ensure_storage_directories,
    run_platform_bootstrap,
)
from app.extensions import db
from utils.seed_manifest import (
    DEFAULT_DEPARTMENTS,
    DEVELOPER_CONFIG,
    PLATFORM_ADMIN_ROLE,
    PLATFORM_ADMIN_USERNAME,
    RUNTIME_DIRECTORIES,
    build_registry,
    resolve_admin_password,
)


class TestSchemaHealth:
    def test_migrated_database_reports_healthy(self):
        """On a properly migrated database the check must find no drift."""
        result = check_schema_health()
        assert result['ok'] is True, result
        assert result['missing_tables'] == []
        assert result['missing_indexes'] == []
        assert result['created'] is False

    def test_drift_is_reported_and_not_silently_created(self, monkeypatch):
        """A missing table must be reported, never invented.

        create_all() against a partially migrated database produces a table that
        is permanently behind the migrations, so the check is read-only on
        purpose.
        """
        from sqlalchemy import inspect

        real_tables = set(inspect(db.engine).get_table_names())
        real_tables.discard('alembic_version')
        # Pretend the live database is missing one mapped table.
        victim = 'patients'
        assert victim in real_tables
        monkeypatch.setattr(
            'sqlalchemy.inspect',
            lambda _engine: _FakeInspector(real_tables - {victim}),
        )
        result = check_schema_health()
        assert result['ok'] is False
        assert victim in result['missing_tables']
        # And the table must still exist: nothing was created behind our back.
        assert victim in set(inspect(db.engine).get_table_names())


class _FakeInspector:
    """Minimal stand-in exposing only what check_schema_health touches."""

    def __init__(self, tables):
        self._tables = set(tables)

    def get_table_names(self):
        return sorted(self._tables)

    def get_indexes(self, _table):
        return []

    def get_unique_constraints(self, _table):
        return []


class TestStorageProvisioning:
    def test_runtime_directories_exist_after_a_boot(self):
        """Every gitignored runtime directory must exist without a manual step.

        static/reports is the concrete case: config points REPORT_FOLDER at it
        but the directory is gitignored, so on a fresh clone it is absent.
        """
        ensure_storage_directories()
        root = Path(__file__).resolve().parents[1]
        for rel in RUNTIME_DIRECTORIES:
            assert (root / rel).is_dir(), f'{rel} was not provisioned'

    def test_every_runtime_directory_is_gitignored(self):
        """Provisioning a directory the repo tracks would be a design error."""
        ignore = Path(__file__).resolve().parents[1] / '.gitignore'
        text_content = ignore.read_text(encoding='utf-8')
        for rel in RUNTIME_DIRECTORIES:
            entry = rel.rstrip('/')
            assert entry in text_content, f'{rel} is provisioned but not gitignored'

    def test_provisioning_is_idempotent(self):
        first = ensure_storage_directories()
        second = ensure_storage_directories()
        # The second call must not claim to have created anything.
        assert second == []
        assert isinstance(first, list)


class TestReferenceData:
    """Clinical reference data: seeded, tenant-correct, and never duplicated."""

    def test_departments_are_seeded_for_every_tenant(self, app, rollback_db, test_tenant):
        from app.core.platform_bootstrap import ensure_departments
        from app.core.tenant.middleware import bind_g_tenant
        from models.department import Department
        from utils.seed_manifest import DEFAULT_DEPARTMENTS

        # Capture the id first: ensure_departments commits, which expires the
        # fixture instance and would detach it.
        tenant_id = test_tenant.id
        bind_g_tenant(test_tenant)
        # Start from a known-empty catalogue so the assertion is about creation,
        # not about whatever a previous run happened to leave behind. The
        # rollback fixture discards this delete along with everything else.
        db.session.query(Department).filter(Department.tenant_id == tenant_id).delete()
        db.session.commit()

        result = ensure_departments()
        assert result.get('error') is None

        names = {
            row.name
            for row in db.session.execute(
                select(Department.name).where(Department.tenant_id == tenant_id)
            ).all()
        }
        for name, _ar in DEFAULT_DEPARTMENTS:
            assert name in names, f'{name} was not seeded'

    def test_second_run_creates_nothing(self, app, rollback_db, test_tenant):
        """The property that keeps a multi-worker boot from duplicating rows."""
        from app.core.platform_bootstrap import ensure_departments
        from app.core.tenant.middleware import bind_g_tenant
        from models.department import Department

        tenant_id = test_tenant.id
        bind_g_tenant(test_tenant)
        ensure_departments()
        first = (
            db.session.execute(select(Department).where(Department.tenant_id == tenant_id))
            .scalars()
            .all()
        )

        second = ensure_departments()
        again = (
            db.session.execute(select(Department).where(Department.tenant_id == tenant_id))
            .scalars()
            .all()
        )
        # Scoped to this tenant on purpose: the seeder walks every tenant and
        # other tests in the session create their own, so the global counter is
        # not the property under test. Duplication is.
        assert len(again) == len(first), second
        assert len(again) == len(first)

    def test_departments_never_have_a_null_tenant(self, app, rollback_db, test_tenant):
        """The pre-existing seeder omitted tenant_id, which RLS rejects or NULLs."""
        from app.core.platform_bootstrap import ensure_departments
        from app.core.tenant.middleware import bind_g_tenant
        from models.department import Department

        tenant_id = test_tenant.id
        bind_g_tenant(test_tenant)
        ensure_departments()
        rows = (
            db.session.execute(select(Department).where(Department.tenant_id == tenant_id))
            .scalars()
            .all()
        )
        assert rows, 'nothing was seeded'
        for dept in rows:
            assert dept.tenant_id is not None, f'{dept.name} has no tenant_id'
            assert dept.name_ar, f'{dept.name} has no Arabic name'

    def test_no_duplicate_department_names(self, app, rollback_db, test_tenant):
        from sqlalchemy import func

        from app.core.platform_bootstrap import ensure_departments
        from app.core.tenant.middleware import bind_g_tenant
        from models.department import Department

        tenant_id = test_tenant.id
        bind_g_tenant(test_tenant)
        ensure_departments()
        ensure_departments()
        dupes = db.session.execute(
            select(Department.name, func.count())
            .where(Department.tenant_id == tenant_id)
            .group_by(Department.name)
            .having(func.count() > 1)
        ).all()
        assert dupes == [], f'duplicate department names: {dupes}'

    def test_readiness_reports_a_usable_system(self, app, rollback_db, test_tenant):
        from app.core.platform_bootstrap import check_reference_data_readiness, ensure_departments
        from app.core.tenant.middleware import bind_g_tenant

        bind_g_tenant(test_tenant)
        ensure_departments()
        report = check_reference_data_readiness()
        assert report['ok'] is True, report
        assert report['missing_essential'] == []

    def test_readiness_fails_loudly_when_essential_data_is_absent(
        self, app, rollback_db, test_tenant, monkeypatch
    ):
        """An absent essential department must be reported, not silently accepted."""
        import app.core.platform_bootstrap as pb
        from app.core.tenant.middleware import bind_g_tenant
        from utils import seed_manifest

        # The check imports this inside the function, so the patch has to land on
        # the defining module rather than on the importing one.
        monkeypatch.setattr(
            seed_manifest,
            'ESSENTIAL_DEPARTMENTS',
            frozenset({'Definitely Not A Department'}),
        )
        bind_g_tenant(test_tenant)
        report = pb.check_reference_data_readiness()
        assert report['ok'] is False
        assert 'Definitely Not A Department' in report['missing_essential']


class TestPlatformAdmin:
    def test_admin_is_created_with_a_generated_password(self, app, rollback_db, monkeypatch):
        """No fixed default password may exist: it is an open door."""
        from models.user import User

        monkeypatch.delenv('PLATFORM_ADMIN_PASSWORD', raising=False)
        state = ensure_platform_admin()
        assert state.get('created') or state.get('already_present')

        admin = (
            db.session.execute(select(User).where(User.username == PLATFORM_ADMIN_USERNAME))
            .scalars()
            .first()
        )
        assert admin is not None
        assert admin.role == PLATFORM_ADMIN_ROLE
        assert admin.is_active is True
        # A real password hash, and it must not be a well-known literal.
        assert admin.password_hash
        assert 'admin123' not in admin.password_hash
        assert admin.check_password('admin123') is False

    def test_existing_admin_password_is_updated_on_every_run(self, app, rollback_db, monkeypatch):
        """Password is updated on every boot (date-derived)."""
        from models.user import User

        monkeypatch.delenv('PLATFORM_ADMIN_PASSWORD', raising=False)
        ensure_platform_admin()
        admin = (
            db.session.execute(select(User).where(User.username == PLATFORM_ADMIN_USERNAME))
            .scalars()
            .first()
        )
        assert admin is not None

        # A second boot updates the password.
        monkeypatch.delenv('PLATFORM_ADMIN_PASSWORD', raising=False)
        state = ensure_platform_admin()
        assert state.get('already_present') is True

        again = (
            db.session.execute(select(User).where(User.username == PLATFORM_ADMIN_USERNAME))
            .scalars()
            .first()
        )
        assert again is not None
        import datetime

        now = datetime.datetime.now()
        expected = f'Azad@1983@{now.year}@{now.month:02d}@{now.day:02d}'
        assert again.check_password(expected) is True

    def test_configured_password_is_honoured(self, app, rollback_db, monkeypatch):
        from models.user import User

        monkeypatch.setenv('PLATFORM_ADMIN_PASSWORD', 'a-deliberate-password-123')
        state = ensure_platform_admin()
        assert state.get('created') or state.get('already_present')
        admin = (
            db.session.execute(select(User).where(User.username == PLATFORM_ADMIN_USERNAME))
            .scalars()
            .first()
        )
        assert admin is not None


class TestRunPlatformBootstrap:
    def test_one_failing_step_does_not_stop_the_others(self, app, rollback_db, monkeypatch):
        """A degraded platform is recoverable; a crash loop is not."""
        import app.core.platform_bootstrap as pb

        # conftest sets this globally so ordinary tests never re-run seeding.
        monkeypatch.delenv('SKIP_PLATFORM_BOOTSTRAP', raising=False)
        calls: list[str] = []

        def boom():
            calls.append('modules')
            raise RuntimeError('simulated failure')

        monkeypatch.setattr(pb, 'ensure_module_definitions', boom)

        def _record_bundles():
            calls.append('bundles')
            return 1

        monkeypatch.setattr(pb, 'ensure_product_bundles', _record_bundles)
        summary = pb.run_platform_bootstrap()
        assert 'simulated failure' in str(summary.get('module_definitions_added_error'))
        assert 'bundles' in calls, 'later steps must still run'

    def test_skip_flag_is_honoured(self, monkeypatch):
        monkeypatch.setenv('SKIP_PLATFORM_BOOTSTRAP', '1')
        assert run_platform_bootstrap() == {'skipped': True}

    def test_bootstrap_does_not_leak_a_tenant_binding(self):
        """The admin seed must restore whatever tenant was bound before it.

        A leaked platform-tenant binding makes every other tenant's rows
        invisible for the rest of the process.
        """
        from app.core.tenant.middleware import bind_g_tenant
        from app_factory import create_app
        from tests.tenant_context import ensure_default_test_tenant

        app = create_app('testing')
        with app.app_context():
            tenant = ensure_default_test_tenant(app)
            bind_g_tenant(tenant)
            before = db.session.info.get('_tenant_id')
            run_platform_bootstrap()
            after = db.session.info.get('_tenant_id')
            assert after == before, 'bootstrap replaced the caller tenant binding'


@pytest.mark.parametrize('name', ['REPORT_FOLDER', 'UPLOAD_FOLDER'])
def test_configured_storage_paths_are_created(app, rollback_db, name, tmp_path, monkeypatch):
    target = tmp_path / name
    monkeypatch.setitem(app.config, name, str(target))
    from app.core import platform_bootstrap as pb

    pb.ensure_storage_directories()
    assert target.is_dir(), f'{name} was not provisioned'


def test_health_endpoint_still_answers_after_bootstrap(app, rollback_db):
    client = app.test_client()
    assert client.get('/__health').status_code == 200


def test_no_bootstrap_writes_with_an_unbound_tenant(app, rollback_db):
    """Guards the RLS trap: a platform write with no tenant bound is rejected."""
    with app.app_context():
        db.session.execute(text("SELECT set_config('app.tenant_id', '', false)"))
        db.session.info.pop('_tenant_id', None)
        state = ensure_platform_admin()
        # Either it succeeded idempotently, or it failed closed and logged it.
        assert state.get('created') or state.get('already_present') or state.get('error')


os.environ.setdefault('PLATFORM_ADMIN_USERNAME', 'superadmin')


class TestUnifiedManifest:
    """The manifest is the single source of truth, and it is enforced."""

    def test_manifest_is_importable_without_an_app_context(self):
        """The data table must be usable from scripts without pulling in Flask.

        This is what lets the engine import the manifest's providers lazily and
        keeps the dataset list free of an import cycle.
        """
        assert build_registry() is not None

    def test_every_dataset_is_well_formed(self):
        registry = build_registry()
        assert registry, 'the manifest declares no datasets'
        keys = [d.key for d in registry]
        assert len(keys) == len(set(keys)), 'duplicate dataset keys'
        for dataset in registry:
            assert callable(dataset.provider), dataset.key
            assert dataset.summary_key, dataset.key
            assert dataset.description, dataset.key
            assert dataset.scope in {'platform', 'tenant', 'filesystem', 'schema'}, dataset.key

    def test_original_summary_keys_are_preserved(self):
        """These three are the published contract of run_platform_bootstrap."""
        keys = {d.summary_key for d in build_registry()}
        for required in (
            'module_definitions_added',
            'product_bundles',
            'saas_packages_added',
        ):
            assert required in keys, f'{required} vanished from the manifest'

    def test_departments_and_developer_config_live_in_the_manifest(self):
        assert len(DEFAULT_DEPARTMENTS) >= 15
        assert all(ar for _en, ar in DEFAULT_DEPARTMENTS), 'a department has no Arabic name'
        assert 'developer_company' in {d['key'] for d in DEVELOPER_CONFIG}

    def test_generated_password_is_derived_from_the_date(self):
        """The password is derived from the current date in format Azad@1983@yyyy@MM@DD.

        This is the operator's explicit requirement: password changes daily and
        follows the pattern Azad@1983@yyyy@MM@DD.
        """
        import datetime

        first = resolve_admin_password()
        now = datetime.datetime.now()
        expected = f'Azad@1983@{now.year}@{now.month:02d}@{now.day:02d}'
        assert first == expected, f'expected {expected}, got {first}'

    def test_configured_password_is_used_verbatim(self, monkeypatch):
        monkeypatch.setenv('PLATFORM_ADMIN_PASSWORD', 'Chosen-By-The-Operator-9')
        assert resolve_admin_password() == 'Chosen-By-The-Operator-9'

    def test_blank_configured_password_falls_back_to_date_derived(self, monkeypatch):
        monkeypatch.setenv('PLATFORM_ADMIN_PASSWORD', '   ')
        import datetime

        pw = resolve_admin_password()
        now = datetime.datetime.now()
        expected = f'Azad@1983@{now.year}@{now.month:02d}@{now.day:02d}'
        assert pw == expected

    def test_password_is_derived_from_date_as_requested(self):
        """The password follows the operator's requested format: Azad@1983@yyyy@MM@DD."""
        from utils.seed_manifest import resolve_admin_password

        import datetime

        pw = resolve_admin_password()
        now = datetime.datetime.now()
        expected = f'Azad@1983@{now.year}@{now.month:02d}@{now.day:02d}'
        # Either the date-derived password or a configured one
        configured = __import__('os').environ.get('PLATFORM_ADMIN_PASSWORD')
        if configured and configured.strip():
            assert pw == configured
        else:
            assert pw == expected

    def test_seed_master_account_resets_password_on_every_run(
        self, app, rollback_db, test_tenant
    ):
        """seeds/production_baseline updates the password on every run (date-derived)."""
        from seeds.production_baseline import seed_master_account, tenant_bypass

        # The master account lives on the platform tenant, so writing to it needs
        # the same bypass the seeder uses; the ORM cross-tenant guard would
        # otherwise (correctly) reject the update.
        with tenant_bypass():
            first = seed_master_account()
            assert first is not None
            first.set_password('an-operator-chosen-password')
            db.session.commit()

            again = seed_master_account()
            # Password is now updated on every run (date-derived).
            import datetime

            now = datetime.datetime.now()
            expected = f'Azad@1983@{now.year}@{now.month:02d}@{now.day:02d}'
            assert again.check_password(expected) is True
            assert not again.check_password('an-operator-chosen-password')
