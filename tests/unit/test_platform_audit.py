"""Tests for platform_audit_logs writes and the fail-closed audit contract.

`platform_audit_logs` is RLS-protected by `tenant_id = app.tenant_id`, so a
platform action can only be recorded while the platform tenant is bound. That
binding has two non-obvious requirements, both of which this file pins:

1. All three of `g.tenant_id`, `db.session.info['_tenant_id']` and the
   connection GUC must move together. A bare `SET app.tenant_id = ...` is not
   enough - the `tenant_filter` `reassert_set_local` hook re-issues the GUC
   from session/g before every ORM statement, undoing it before the INSERT is
   evaluated.
2. A failed write must raise. The previous implementation swallowed every
   exception, so owner routes returned 200 while recording nothing.
"""

import pytest

from app.extensions import db


@pytest.mark.usefixtures('app')
class TestPlatformTenantScope:
    def test_scope_binds_the_platform_tenant_by_slug(self, app):
        """The platform tenant is resolved by slug, not by a hard-coded id."""
        from sqlalchemy import text

        from app.core.tenant.middleware import platform_tenant_scope

        with app.test_request_context():
            with platform_tenant_scope() as tenant:
                assert tenant.slug == (app.config.get('PLATFORM_TENANT_SLUG') or 'platform').lower()
                assert db.session.info['_tenant_id'] == tenant.id
                guc = db.session.execute(text('SELECT current_setting($$app.tenant_id$$)')).scalar()
                assert guc == str(tenant.id)

    def test_scope_restores_the_previous_tenant(self, app):
        """Leaving the scope must not repoint the rest of the process.

        Leaving a platform binding behind would make every other tenant's rows
        invisible for the remainder of the request.
        """
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        from app.core.tenant.middleware import platform_tenant_scope

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant.id
            db.session.info['_tenant_id'] = tenant.id

            with platform_tenant_scope() as platform:
                assert g.tenant_id == platform.id

            assert g.tenant_id == tenant.id
            assert db.session.info['_tenant_id'] == tenant.id

    def test_missing_platform_tenant_raises_rather_than_creating_one(self, app, monkeypatch):
        """An absent platform tenant is an error, not something to paper over.

        `seeds.production_baseline._resolve_platform_tenant` creates a tenant
        as a fallback. Doing that from an audit write would hide a broken
        deployment behind a side effect, so `platform_tenant_scope` refuses.
        """
        from app.core.tenant.middleware import PlatformTenantMissingError, platform_tenant_scope

        monkeypatch.setitem(app.config, 'PLATFORM_TENANT_SLUG', 'no-such-platform-tenant')

        with app.test_request_context(), pytest.raises(PlatformTenantMissingError):
            with platform_tenant_scope():
                pass


@pytest.mark.usefixtures('app')
class TestPlatformAuditWrite:
    def _write(self, action):
        from app.core.tenant.middleware import platform_tenant_scope
        from app.core.tenant.models import PlatformAuditLog

        with platform_tenant_scope() as platform:
            row = PlatformAuditLog(
                user_id=None,
                tenant_id=platform.id,
                action=action,
                entity_type='system',
                entity_id=1,
            )
            db.session.add(row)
            # Capture the id before the commit. The commit expires every
            # attribute, and the session teardown detaches the instance, so
            # reading row.id afterwards tries to refresh a detached instance and
            # raises DetachedInstanceError on a row that was written fine.
            db.session.flush()
            row_id = row.id
            db.session.commit()
            return row_id

    def test_write_under_platform_scope_succeeds(self, app):
        """The whole point: a platform audit row must actually be written.

        Before the fix this raised InsufficientPrivilege, because the GUC was
        re-asserted from the ambient tenant before the INSERT was checked.
        """
        row_id = self._write('TEST_PLATFORM_SCOPE')

        from sqlalchemy import select

        from app.core.tenant.middleware import platform_tenant_scope
        from app.core.tenant.models import PlatformAuditLog

        with app.test_request_context(), platform_tenant_scope():
            # A fresh SELECT rather than session.get: the instance written above
            # is still in the identity map with its attributes expired, and
            # reloading it outside the write scope raised ObjectDeletedError.
            rows = (
                db.session.execute(select(PlatformAuditLog).where(PlatformAuditLog.id == row_id))
                .scalars()
                .all()
            )
            assert len(rows) == 1, 'the audit row was not persisted'
            assert rows[0].action == 'TEST_PLATFORM_SCOPE'
            assert rows[0].tenant_id is not None, (
                'the row must be attributed to the platform tenant, not NULL'
            )

    def test_write_failure_raises_instead_of_being_swallowed(self, app, monkeypatch):
        """A dropped audit row must be a visible error.

        The old implementation wrapped the write in `except Exception:
        safe_rollback(...)`, so every failure - missing platform tenant, RLS
        rejection, constraint violation - returned silently and the caller
        believed the action had been recorded.
        """
        from app.modules.owner import routes as owner_routes

        monkeypatch.setitem(app.config, 'PLATFORM_TENANT_SLUG', 'no-such-platform-tenant')

        with app.test_request_context():
            with pytest.raises(Exception) as exc:
                owner_routes._log_action('TEST_FAILS_CLOSED', 'system', entity_id=1)
            assert 'no-such-platform-tenant' in str(exc.value)
