"""Infrastructure Celery tasks."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from celery_app import get_celery_app
from services.backup_automation_service import BackupAutomationError

logger = logging.getLogger(__name__)

celery = get_celery_app()


def _load_backup_without_tenant_context(backup_id: int):
    """Load a Backup row bypassing ORM tenant filters (Celery has no request tenant)."""
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


def _purge_expired_tokens() -> dict:
    """Purge expired OAuth tokens, password reset tokens, and email verification tokens."""
    from flask import g

    from app.extensions import db
    from models.email_verification_token import EmailVerificationToken
    from models.oauth_token import OAuthToken
    from models.password_reset_token import PasswordResetToken

    g._tenant_filter_bypass = True
    try:
        datetime.utcnow()
        deleted = 0

        # Expired OAuth tokens
        oauth_expired = select(OAuthToken).delete(synchronize_session=False)
        deleted += oauth_expired

        # Expired password reset tokens
        pwd_expired = select(PasswordResetToken).delete(synchronize_session=False)
        deleted += pwd_expired

        # Expired email verification tokens
        email_expired = select(EmailVerificationToken).delete(synchronize_session=False)
        deleted += email_expired

        db.session.commit()
        logger.info(f'Purged {deleted} expired tokens')
        return {
            'deleted': deleted,
            'types': {
                'oauth': oauth_expired,
                'password_reset': pwd_expired,
                'email_verification': email_expired,
            },
        }
    except Exception:
        db.session.rollback()
        logger.exception('Failed to purge expired tokens: %s')
        raise
    finally:
        g.pop('_tenant_filter_bypass', None)


def _purge_old_audit_logs() -> dict:
    """Archive or delete audit logs older than retention period."""
    from flask import g

    from app.extensions import db
    from models.audit_trail import AuditTrail

    retention_days = 90  # Configurable via env later
    datetime.utcnow() - timedelta(days=retention_days)

    g._tenant_filter_bypass = True
    try:
        deleted = select(AuditTrail).delete(synchronize_session=False)
        db.session.commit()
        logger.info(f'Purged {deleted} audit logs older than {retention_days} days')
        return {'deleted': deleted, 'retention_days': retention_days}
    except Exception:
        db.session.rollback()
        logger.exception('Failed to purge old audit logs: %s')
        raise
    finally:
        g.pop('_tenant_filter_bypass', None)


def _purge_stale_notifications() -> dict:
    """Purge read notifications older than 30 days and failed notification retries."""
    from flask import g

    from app.extensions import db
    from models.notification import Notification
    from models.notification_queue import NotificationQueue

    g._tenant_filter_bypass = True
    try:
        datetime.utcnow() - timedelta(days=30)
        datetime.utcnow() - timedelta(days=7)

        # Old read notifications
        deleted_notifs = select(Notification).delete(synchronize_session=False)

        # Failed notification retries older than 7 days
        failed_retries = select(NotificationQueue).delete(synchronize_session=False)

        db.session.commit()
        logger.info(
            f'Purged {deleted_notifs} old notifications and {failed_retries} failed retries'
        )
        return {'notifications': deleted_notifs, 'failed_retries': failed_retries}
    except Exception:
        db.session.rollback()
        logger.exception('Failed to purge stale notifications: %s')
        raise
    finally:
        g.pop('_tenant_filter_bypass', None)


@celery.task(name='tasks.run_system_backup', bind=True)
def run_system_backup(self, backup_id: int) -> dict:
    """Run pg_dump for a queued Backup record outside the web request cycle."""
    from flask import current_app

    from services.backup_execution_service import execute_backup_by_id
    from services.tenant_job_runner import get_flask_app, with_tenant_context

    app = get_flask_app() or current_app._get_current_object()
    backup = _load_backup_without_tenant_context(backup_id)
    if backup is None:
        raise BackupAutomationError(f'Backup record {backup_id} not found')

    try:
        if backup.tenant_id is not None:
            outcome = with_tenant_context(
                app,
                backup.tenant_id,
                lambda: _backup_result_tuple(execute_backup_by_id, backup_id),
            )
        else:
            outcome = _backup_result_tuple(execute_backup_by_id, backup_id)
    except BackupAutomationError:
        logger.exception('Celery backup task failed backup_id=%s: %s')
        raise

    if outcome is None:
        raise BackupAutomationError(
            f'Backup tenant {backup.tenant_id} not found for backup {backup_id}'
        )

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
        logger.exception('Expired tokens purge failed: %s')
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
        logger.exception('Audit logs purge failed: %s')
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
        logger.exception('Stale notifications purge failed: %s')
        raise


@celery.task(name='tasks.run_all_maintenance', bind=True)
def run_all_maintenance_task(self) -> dict:
    """Run all maintenance tasks in sequence."""
    logger.info('Starting full maintenance cycle')
    results = {}

    try:
        results['expired_tokens'] = _purge_expired_tokens()
    except Exception as e:
        logger.exception('Token purge failed: %s')
        results['expired_tokens'] = {'error': str(e)}

    try:
        results['audit_logs'] = _purge_old_audit_logs()
    except Exception as e:
        logger.exception('Audit logs purge failed: %s')
        results['audit_logs'] = {'error': str(e)}

    try:
        results['stale_notifications'] = _purge_stale_notifications()
    except Exception as e:
        logger.exception('Stale notifications purge failed: %s')
        results['stale_notifications'] = {'error': str(e)}

    results['task_id'] = self.request.id
    results['completed_at'] = datetime.utcnow().isoformat()
    logger.info(f'Maintenance cycle completed: {results}')
    return results


def _load_backup_without_tenant_context(backup_id: int):
    """Load a Backup row bypassing ORM tenant filters (Celery has no request tenant)."""
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
