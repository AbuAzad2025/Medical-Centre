"""
Audit Cleanup Service — batched, non-blocking retention policy enforcement.

Tables covered:
  - phi_audit_logs      (config: PHI_AUDIT_RETENTION_DAYS,   default 90)
  - platform_audit_logs (config: PLATFORM_AUDIT_RETENTION_DAYS, default 180)
  - audit_trails        (config: AUDIT_TRAIL_RETENTION_DAYS,    default 180)
  - system_logs         (config: SYSTEM_LOG_RETENTION_DAYS,     default 90)
  - security_events     (config: SECURITY_EVENT_RETENTION_DAYS, default 365)
  - login_attempts      (config: LOGIN_ATTEMPT_RETENTION_DAYS,  default 30)
  - slow_query_reports  (config: SLOW_QUERY_RETENTION_DAYS,     default 90)

Design principles:
  1. Batched DELETE (default 5 000 rows / batch) to avoid long table locks.
  2. COMMIT between batches so vacuum can reclaim space incrementally.
  3. Dry-run mode reports counts without mutating data.
  4. Tenant-scoped tables use tenant_id partitioning when possible (future).
  5. Failures per table are logged but do not abort the entire job.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app_factory import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────
DEFAULT_BATCH_SIZE = int(os.getenv('AUDIT_CLEANUP_BATCH_SIZE', '5000'))
DEFAULT_SLEEP_MS = int(os.getenv('AUDIT_CLEANUP_SLEEP_MS', '100'))

RETENTION_CONFIG = {
    'phi_audit_logs': {
        'days': int(os.getenv('PHI_AUDIT_RETENTION_DAYS', '90')),
        'model_path': 'models.phi_audit_log.PHIAuditLog',
        'column': 'created_at',
    },
    'platform_audit_logs': {
        'days': int(os.getenv('PLATFORM_AUDIT_RETENTION_DAYS', '180')),
        'model_path': 'app.core.tenant.models.PlatformAuditLog',
        'column': 'created_at',
    },
    'audit_trails': {
        'days': int(os.getenv('AUDIT_TRAIL_RETENTION_DAYS', '180')),
        'model_path': 'models.audit_trail.AuditTrail',
        'column': 'created_at',
    },
    'system_logs': {
        'days': int(os.getenv('SYSTEM_LOG_RETENTION_DAYS', '90')),
        'model_path': 'models.audit_trail.SystemLog',
        'column': 'created_at',
    },
    'security_events': {
        'days': int(os.getenv('SECURITY_EVENT_RETENTION_DAYS', '365')),
        'model_path': 'models.audit_trail.SecurityEvent',
        'column': 'created_at',
    },
    'login_attempts': {
        'days': int(os.getenv('LOGIN_ATTEMPT_RETENTION_DAYS', '30')),
        'model_path': 'models.audit_trail.LoginAttempt',
        'column': 'created_at',
    },
    'slow_query_reports': {
        'days': int(os.getenv('SLOW_QUERY_RETENTION_DAYS', '90')),
        'model_path': 'models.audit_trail.SlowQueryReport',
        'column': 'created_at',
    },
}


class AuditCleanupService:
    """Batched audit-log retention cleanup."""

    @staticmethod
    def _resolve_model(model_path: str):
        """Dynamic import of model class from dotted path."""
        module_path, class_name = model_path.rsplit('.', 1)
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)

    @staticmethod
    def _count_old_records(table_name: str, column: str, cutoff: datetime) -> int:
        """Count rows older than cutoff."""
        try:
            result = db.session.execute(
                text(f'SELECT COUNT(*) FROM {table_name} WHERE {column} < :cutoff'),
                {'cutoff': cutoff},
            ).scalar()
            return int(result or 0)
        except Exception as e:
            logger.exception(f'Audit cleanup: count failed for {table_name}: {e}')
            return 0

    @staticmethod
    def _delete_batch(
        table_name: str,
        column: str,
        cutoff: datetime,
        batch_size: int,
    ) -> int:
        """Delete one batch of old rows, returning rows deleted."""
        # Use subquery + LIMIT for PostgreSQL (fast, index-friendly)
        result = db.session.execute(
            text(
                f"""
                DELETE FROM {table_name}
                WHERE ctid IN (
                    SELECT ctid
                    FROM {table_name}
                    WHERE {column} < :cutoff
                    ORDER BY {column}
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                )
                """
            ),
            {'cutoff': cutoff, 'limit': batch_size},
        )
        return result.rowcount

    @staticmethod
    def cleanup_table(
        table_name: str,
        retention_days: int,
        column: str = 'created_at',
        batch_size: int = DEFAULT_BATCH_SIZE,
        sleep_ms: int = DEFAULT_SLEEP_MS,
        dry_run: bool = False,
    ) -> dict:
        """Run batched cleanup for a single audit table.

        Returns {"table": ..., "deleted": N, "dry_run": bool, "error": str|None}
        """
        import time as _time

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        total_deleted = 0
        error_msg: str | None = None

        try:
            eligible = AuditCleanupService._count_old_records(table_name, column, cutoff)
            if dry_run:
                logger.info(
                    f'[DRY-RUN] {table_name}: would delete {eligible} rows older than {cutoff.isoformat()}'
                )
                return {
                    'table': table_name,
                    'deleted': 0,
                    'eligible': eligible,
                    'dry_run': True,
                    'error': None,
                }

            if eligible == 0:
                logger.info(f'{table_name}: no rows to delete (retention={retention_days}d)')
                return {
                    'table': table_name,
                    'deleted': 0,
                    'eligible': 0,
                    'dry_run': False,
                    'error': None,
                }

            logger.info(
                f'{table_name}: starting cleanup of {eligible} rows (retention={retention_days}d, batch={batch_size})'
            )

            while True:
                deleted = AuditCleanupService._delete_batch(table_name, column, cutoff, batch_size)
                if deleted == 0:
                    break
                total_deleted += deleted
                safe_commit(db.session, error_message=f'{table_name} batch commit failed')
                logger.info(
                    f'{table_name}: deleted batch of {deleted} rows (total={total_deleted})'
                )
                if sleep_ms > 0:
                    _time.sleep(sleep_ms / 1000.0)
                # Safety break: if we somehow loop forever, stop after 100 batches
                if total_deleted >= eligible * 2:
                    logger.warning(f'{table_name}: safety break triggered — possible infinite loop')
                    break

            logger.info(f'{table_name}: cleanup complete — {total_deleted} rows deleted')
            return {
                'table': table_name,
                'deleted': total_deleted,
                'eligible': eligible,
                'dry_run': False,
                'error': None,
            }

        except Exception as e:
            error_msg = str(e)
            logger.exception(f'Audit cleanup failed for {table_name}: {error_msg}')
            return {
                'table': table_name,
                'deleted': total_deleted,
                'eligible': 0,
                'dry_run': False,
                'error': error_msg,
            }

    @classmethod
    def run_all(
        cls,
        tables: list[str] | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        sleep_ms: int = DEFAULT_SLEEP_MS,
        dry_run: bool = False,
    ) -> list[dict]:
        """Run cleanup across all (or specified) audit tables.

        Returns list of per-table result dicts.
        """
        targets = tables or list(RETENTION_CONFIG.keys())
        results = []
        for table_name in targets:
            cfg = RETENTION_CONFIG.get(table_name)
            if not cfg:
                logger.warning(f'Unknown audit table: {table_name}, skipping')
                continue
            result = cls.cleanup_table(
                table_name=table_name,
                retention_days=cfg['days'],
                column=cfg['column'],
                batch_size=batch_size,
                sleep_ms=sleep_ms,
                dry_run=dry_run,
            )
            results.append(result)
        return results
