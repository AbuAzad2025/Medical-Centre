"""Infrastructure Celery tasks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete as sa_delete
from sqlalchemy import text as sa_text

from celery_app import get_celery_app
from services.backup_automation_service import BackupAutomationError

logger = logging.getLogger(__name__)

celery = get_celery_app()


def _purge_expired_tokens() -> dict:
    """Unimplemented: the token tables this purged no longer exist.

    It imported ``models.oauth_token.OAuthToken``,
    ``models.password_reset_token.PasswordResetToken`` and
    ``models.email_verification_token.EmailVerificationToken``. None of those
    modules are in the tree, so every call raised ModuleNotFoundError and the
    daily task never purged anything. Password reset tokens are no longer rows
    at all - they live in ``User.preferences`` as ``password_reset_token`` /
    ``password_reset_expires`` (see routes/auth_routes.py), and expiring them
    means rewriting tenant-scoped user rows under each tenant's own scope.

    Refusing loudly is the safe state. The previous body would have deleted
    every row in whichever table it did find, because none of the DELETEs had a
    WHERE clause, so a partial "fix" that guessed at table names would be worse
    than an explicit refusal.
    """
    raise NotImplementedError(
        'token purge is not implemented: the oauth_token / password_reset_token '
        '/ email_verification_token tables were removed. Password reset tokens '
        'now live in User.preferences and need a tenant-scoped rewriter.'
    )


def _purge_old_audit_logs() -> dict:
    """Archive or delete audit logs older than retention period."""
    from flask import g

    from app.extensions import db
    from models.audit_trail import AuditTrail

    retention_days = 90  # Configurable via env later
    # The cutoff was previously computed and thrown away on a bare expression
    # line, and the DELETE below carried no WHERE clause - so this task wiped
    # the entire audit trail on every run, not just rows past retention. It is
    # a scheduled Celery task (tasks.purge_old_audit_logs), so that was live.
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    g._tenant_filter_bypass = True
    # The audit trail is append-only: the row-level policy on it refuses a
    # delete unless the session has declared itself the retention job. This
    # is that declaration, and it is made for this one statement - the rows
    # past the retention window and nothing else. The application never
    # makes it, so nothing it does can remove a row from the trail.
    db.session.execute(sa_text("SET LOCAL app.audit_purge = 'on'"))
    try:
        deleted = (
            sa_delete(AuditTrail)
            .where(AuditTrail.created_at < cutoff)
            .execution_options(synchronize_session=False)
        )
        deleted = db.session.execute(deleted).rowcount
        db.session.commit()
        logger.info(f'Purged {deleted} audit logs older than {retention_days} days')
        return {'deleted': deleted, 'retention_days': retention_days}
    except Exception:
        db.session.rollback()
        logger.exception('Failed to purge old audit logs')
        raise
    finally:
        # The flag is cleared here and not only at the end of the
        # transaction: the transaction the pruning runs in may stay open for
        # longer than the pruning, and a flag that is still set is a session
        # that is still the retention job.
        try:
            db.session.execute(sa_text('RESET app.audit_purge'))
        except Exception:  # noqa: BLE001 - the session may be unusable
            db.session.rollback()
        g.pop('_tenant_filter_bypass', None)


def _purge_stale_notifications() -> dict:
    """Purge read notifications older than 30 days and failed notification retries."""
    from flask import g

    from app.extensions import db
    from app.shared.enums import NotificationState
    from models.notification import Notification, NotificationQueue

    g._tenant_filter_bypass = True
    try:
        # Both cutoffs were previously computed and discarded on bare expression
        # lines, and both DELETEs had no WHERE clause - so this task removed
        # every notification and the entire retry queue on every run, on a daily
        # schedule. Notifications that were unread, and retries that had not
        # failed yet, were destroyed along with the stale ones.
        now = datetime.now(UTC)
        read_cutoff = now - timedelta(days=30)
        retry_cutoff = now - timedelta(days=7)

        # Old read notifications
        deleted_notifs = db.session.execute(
            sa_delete(Notification)
            .where(Notification.is_read.is_(True), Notification.read_at < read_cutoff)
            .execution_options(synchronize_session=False)
        ).rowcount

        # Failed notification retries older than 7 days
        failed_retries = db.session.execute(
            sa_delete(NotificationQueue)
            .where(
                NotificationQueue.status == NotificationState.FAILED,
                NotificationQueue.created_at < retry_cutoff,
            )
            .execution_options(synchronize_session=False)
        ).rowcount

        db.session.commit()
        logger.info(
            f'Purged {deleted_notifs} old notifications and {failed_retries} failed retries'
        )
        return {'notifications': deleted_notifs, 'failed_retries': failed_retries}
    except Exception:
        db.session.rollback()
        logger.exception('Failed to purge stale notifications')
        raise
    finally:
        g.pop('_tenant_filter_bypass', None)


@celery.task(name='tasks.run_system_backup', bind=True)
def run_system_backup(self, backup_id: int, tenant_id: int | None = None) -> dict:
    """Run pg_dump for a queued Backup record outside the web request cycle.

    *tenant_id* is supplied by the queue because the row cannot be discovered
    without a tenant binding: `backups` is RLS-protected by
    `tenant_id = app.tenant_id`, so reading the row to learn its tenant always
    returns nothing. When the caller knows the tenant we bind it and read the
    row under that scope.
    """
    from flask import current_app

    from services.backup_execution_service import execute_backup_by_id
    from services.tenant_job_runner import get_flask_app, with_tenant_context

    app = get_flask_app() or current_app._get_current_object()

    if tenant_id is None:
        backup = _load_backup_without_tenant_context(backup_id)
        if backup is None:
            raise BackupAutomationError(f'Backup record {backup_id} not found')
        tenant_id = backup.tenant_id

    try:
        if tenant_id is not None:
            outcome = with_tenant_context(
                app,
                tenant_id,
                lambda: _backup_result_tuple(execute_backup_by_id, backup_id),
            )
        else:
            outcome = _backup_result_tuple(execute_backup_by_id, backup_id)
    except BackupAutomationError:
        logger.exception('Celery backup task failed backup_id=%s', backup_id)
        raise

    if outcome is None:
        raise BackupAutomationError(f'Backup tenant {tenant_id} not found for backup {backup_id}')

    status, size = outcome
    return {
        'backup_id': backup_id,
        'status': status,
        'size': size,
        'task_id': self.request.id,
    }


def _backup_result_tuple(execute_fn, backup_id: int):
    record = execute_fn(backup_id)
    return record.backup_status, record.backup_size


# ===== MAINTENANCE TASKS =====


@celery.task(name='tasks.purge_expired_tokens', bind=True)
def purge_expired_tokens_task(self) -> dict:
    """Daily task to purge expired OAuth, password reset, and email verification tokens."""
    logger.info('Starting expired tokens purge')
    try:
        result = _purge_expired_tokens()
        result['task_id'] = self.request.id
        return result
    except Exception:
        logger.exception('Expired tokens purge failed')
        raise


@celery.task(name='tasks.purge_old_audit_logs', bind=True)
def purge_old_audit_logs_task(self) -> dict:
    """Weekly task to purge audit logs older than retention period."""
    logger.info('Starting audit logs purge')
    try:
        result = _purge_old_audit_logs()
        result['task_id'] = self.request.id
        return result
    except Exception:
        logger.exception('Audit logs purge failed')
        raise


@celery.task(name='tasks.purge_stale_notifications', bind=True)
def purge_stale_notifications_task(self) -> dict:
    """Daily task to purge old read notifications and failed notification retries."""
    logger.info('Starting stale notifications purge')
    try:
        result = _purge_stale_notifications()
        result['task_id'] = self.request.id
        return result
    except Exception:
        logger.exception('Stale notifications purge failed')
        raise


@celery.task(name='tasks.run_all_maintenance', bind=True)
def run_all_maintenance_task(self) -> dict:
    """Run all maintenance tasks in sequence."""
    logger.info('Starting full maintenance cycle')
    results = {}

    try:
        results['expired_tokens'] = _purge_expired_tokens()
    except Exception as e:
        logger.exception('Token purge failed')
        results['expired_tokens'] = {'error': str(e)}

    try:
        results['audit_logs'] = _purge_old_audit_logs()
    except Exception as e:
        logger.exception('Audit logs purge failed')
        results['audit_logs'] = {'error': str(e)}

    try:
        results['stale_notifications'] = _purge_stale_notifications()
    except Exception as e:
        logger.exception('Stale notifications purge failed')
        results['stale_notifications'] = {'error': str(e)}

    results['task_id'] = self.request.id
    results['completed_at'] = datetime.now(UTC).isoformat()
    logger.info(f'Maintenance cycle completed: {results}')
    return results


def _load_backup_without_tenant_context(backup_id: int):
    """Fallback load for callers that do not pass a tenant.

    `g._tenant_filter_bypass` only silences the ORM filter; it never reaches
    PostgreSQL. `backups` is RLS-protected by `tenant_id = app.tenant_id`, so if
    the GUC names a different tenant this returns None no matter what the ORM
    does, and the caller cannot learn the owning tenant from the row it cannot
    read. That is why `queue_system_backup` and the task both accept
    `tenant_id` and every caller passes it; this exists only so a legacy caller
    that omits it degrades to "not found" instead of guessing a tenant.
    """
    from flask import g

    from app.extensions import db
    from models.backup import Backup

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        return db.session.get(Backup, backup_id)
    finally:
        if prev:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)


def _backup_result_tuple(execute_fn, backup_id: int):
    record = execute_fn(backup_id)
    return record.backup_status, record.backup_size
