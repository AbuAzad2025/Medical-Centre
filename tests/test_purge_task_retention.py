"""Regression tests for the scheduled Celery purge tasks in tasks/system_tasks.py.

These tasks used to compute a retention cutoff and then throw it away on a bare
expression line, leaving the DELETE with no WHERE clause at all. Both are
scheduled tasks (tasks.purge_old_audit_logs, tasks.purge_stale_notifications),
so the effect was that each run deleted every row in the table - the entire
audit trail, and every notification plus the whole retry queue - while logging
a reassuring "purged N rows older than 90 days".

The tests below seed one row inside the retention window and one outside it,
run the purge, and assert the fresh row survives. A task that deleted
everything would fail these.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db


@pytest.mark.usefixtures('app')
class TestPurgeOldAuditLogsRespectsRetention:
    def _seed(self, app):
        from models.audit_trail import AuditTrail
        from tests.tenant_context import bind_tenant_on_g, ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        now = datetime.now(UTC)
        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            for row in db.session.execute(select(AuditTrail)).scalars().all():
                db.session.delete(row)
            db.session.commit()

            stale = AuditTrail(
                tenant_id=tenant.id,
                action='backup',
                entity_type='system',
                entity_id=1,
                created_at=now - timedelta(days=400),
            )
            fresh = AuditTrail(
                tenant_id=tenant.id,
                action='restore',
                entity_type='system',
                entity_id=2,
                created_at=now - timedelta(days=2),
            )
            db.session.add_all([stale, fresh])
            db.session.commit()
            return tenant, stale.id, fresh.id

    def _remaining_actions(self, app, tenant):
        from models.audit_trail import AuditTrail
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            rows = db.session.execute(select(AuditTrail)).scalars().all()
            return {r.action for r in rows}

    def test_fresh_audit_rows_survive_the_purge(self, app):
        from tasks.system_tasks import _purge_old_audit_logs

        tenant, _stale_id, _fresh_id = self._seed(app)
        result = _purge_old_audit_logs()

        assert result['deleted'] >= 1
        remaining = self._remaining_actions(app, tenant)
        assert 'restore' in remaining, (
            'the purge removed audit rows that are inside the retention window; '
            'it deleted the whole table instead of filtering on created_at'
        )
        assert 'backup' not in remaining


@pytest.mark.usefixtures('app')
class TestPurgeStaleNotificationsRespectsRetention:
    def _seed(self, app):
        from models.notification import Notification, NotificationQueue
        from tests.tenant_context import bind_tenant_on_g, ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)
        now = datetime.now(UTC)
        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            for row in db.session.execute(select(Notification)).scalars().all():
                db.session.delete(row)
            for row in db.session.execute(select(NotificationQueue)).scalars().all():
                db.session.delete(row)
            db.session.commit()

            unread_fresh = Notification(
                tenant_id=tenant.id,
                title='keep-unread',
                message='unread but recent',
                notification_type='info',
                is_read=False,
                sent_at=now - timedelta(days=1),
            )
            read_fresh = Notification(
                tenant_id=tenant.id,
                title='keep-read',
                message='read but recent',
                notification_type='info',
                is_read=True,
                read_at=now - timedelta(days=1),
                sent_at=now - timedelta(days=2),
            )
            pending_retry = NotificationQueue(
                tenant_id=tenant.id,
                user_id=None,
                notification_type='email',
                recipient='pending@example.invalid',
                content='pending',
                status='pending',
                created_at=now - timedelta(days=1),
            )
            db.session.add_all([unread_fresh, read_fresh, pending_retry])
            db.session.commit()
            return tenant

    def _remaining_titles(self, app, tenant):
        from models.notification import Notification
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            rows = db.session.execute(select(Notification)).scalars().all()
            return {r.title for r in rows}

    def test_unread_and_recent_notifications_survive(self, app):
        from tasks.system_tasks import _purge_stale_notifications

        tenant = self._seed(app)
        _purge_stale_notifications()

        remaining = self._remaining_titles(app, tenant)
        assert remaining, (
            'every notification was deleted; the purge filtered on nothing and '
            'removed the whole table'
        )
        assert 'keep-unread' in remaining, 'an unread notification was purged'
        assert 'keep-read' in remaining, 'a recently-read notification was purged'


@pytest.mark.usefixtures('app')
class TestTokenPurgeRefusesExplicitly:
    def test_expired_token_purge_raises_rather_than_deleting_blindly(self, app):
        """The token tables were removed; the task must refuse, not guess.

        It used to import models.oauth_token / password_reset_token /
        email_verification_token, none of which exist, and its DELETEs had no
        WHERE clause. A refusal is the safe state: guessing table names would
        risk deleting live data.
        """
        from tasks.system_tasks import _purge_expired_tokens

        with app.app_context(), pytest.raises(NotImplementedError):
            _purge_expired_tokens()
