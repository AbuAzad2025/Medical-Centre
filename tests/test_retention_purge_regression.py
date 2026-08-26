"""Regression tests for DataRetentionService.delete_expired_session_logs cutoff enforcement.

Proves the purge bugfix:
1. ``dry_run=True`` reports expired counts without deleting anything.
2. ``dry_run=False`` deletes ONLY session logs older than the retention cutoff.
3. A second purge run is idempotent (deletes nothing further).
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from services.data_retention_service import DataRetentionService


@pytest.mark.usefixtures('app')
class TestDeleteExpiredSessionLogsCutoff:
    def _prepare(self, app):
        from models.digital_signature import SessionLog
        from tests.tenant_context import bind_tenant_on_g, ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            stale = db.session.execute(select(SessionLog)).scalars().all()
            for row in stale:
                db.session.delete(row)
            db.session.commit()

            now = datetime.now(UTC)
            rows = [
                SessionLog(
                    tenant_id=tenant.id,
                    session_id='ret-old-1',
                    created_at=now - timedelta(days=800),
                ),
                SessionLog(
                    tenant_id=tenant.id,
                    session_id='ret-old-2',
                    created_at=now - timedelta(days=731),
                ),
                SessionLog(
                    tenant_id=tenant.id,
                    session_id='ret-fresh-1',
                    created_at=now - timedelta(days=30),
                ),
                SessionLog(
                    tenant_id=tenant.id,
                    session_id='ret-fresh-2',
                    created_at=now - timedelta(days=1),
                ),
            ]
            db.session.add_all(rows)
            db.session.commit()
            ids = {r.session_id: r.id for r in rows}
        return tenant, ids

    def _remaining(self, app, tenant):
        from models.digital_signature import SessionLog
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            rows = db.session.execute(select(SessionLog)).scalars().all()
            return {r.session_id for r in rows}

    def test_dry_run_reports_expired_without_deleting(self, app):
        tenant, ids = self._prepare(app)
        count, reported = DataRetentionService().delete_expired_session_logs(
            tenant.id, dry_run=True
        )

        assert count == 2
        assert set(reported) == {ids['ret-old-1'], ids['ret-old-2']}
        assert self._remaining(app, tenant) == {
            'ret-old-1',
            'ret-old-2',
            'ret-fresh-1',
            'ret-fresh-2',
        }

    def test_purge_deletes_only_expired_and_keeps_fresh(self, app):
        tenant, ids = self._prepare(app)
        count, deleted = DataRetentionService().delete_expired_session_logs(
            tenant.id, dry_run=False
        )

        assert count == 2
        assert set(deleted) == {ids['ret-old-1'], ids['ret-old-2']}
        remaining = self._remaining(app, tenant)
        assert 'ret-old-1' not in remaining
        assert 'ret-old-2' not in remaining
        assert {'ret-fresh-1', 'ret-fresh-2'} <= remaining

    def test_second_purge_is_idempotent(self, app):
        tenant, _ids = self._prepare(app)
        service = DataRetentionService()
        first_count, _first_deleted = service.delete_expired_session_logs(tenant.id, dry_run=False)
        second_count, second_deleted = service.delete_expired_session_logs(tenant.id, dry_run=False)

        assert first_count == 2
        assert second_count == 0
        assert second_deleted == []
        assert self._remaining(app, tenant) == {'ret-fresh-1', 'ret-fresh-2'}
