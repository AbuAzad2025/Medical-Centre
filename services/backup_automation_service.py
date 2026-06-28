"""Automated PostgreSQL backup scheduling and encrypted cloud upload."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup
from services.pg_backup_service import PgBackupError, build_backup_path, run_pg_dump_sql_gz

logger = logging.getLogger(__name__)


class BackupAutomationError(RuntimeError):
    """Raised when automated backup or cloud upload fails."""


class BackupAutomationService:
    """Run pg_dump backups on a schedule and optionally upload to object storage."""

    @classmethod
    def _resolve_created_by(cls, created_by: Optional[int]) -> Optional[int]:
        if created_by is not None:
            return created_by
        env_id = os.environ.get('BACKUP_SYSTEM_USER_ID', '').strip()
        if env_id.isdigit():
            return int(env_id)
        from models.user import User
        actor = (
            User.query.filter_by(role='super_admin', is_active=True)
            .order_by(User.id)
            .first()
        )
        if actor is None:
            actor = User.query.filter_by(is_active=True).order_by(User.id).first()
        return actor.id if actor else None

    @classmethod
    def is_enabled(cls) -> bool:
        return os.environ.get('BACKUP_AUTOMATION_ENABLED', 'false').lower() in ('true', '1', 'on')

    @classmethod
    def interval_seconds(cls) -> int:
        return max(3600, int(os.environ.get('BACKUP_INTERVAL_SECONDS', '86400')))

    @classmethod
    def run_scheduled_backup(cls, *, created_by: Optional[int] = None) -> Backup:
        name = f'auto_backup_{datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")}'
        path = build_backup_path(os.environ.get('BACKUP_LOCAL_DIR', 'backups'), name)
        record = Backup(
            backup_name=name,
            backup_type='full',
            backup_path=path,
            backup_status=BackupStatus.IN_PROGRESS,
            is_scheduled=True,
            started_at=datetime.now(timezone.utc),
            created_by=cls._resolve_created_by(created_by),
            description='Automated PostgreSQL pg_dump backup',
        )
        db.session.add(record)
        db.session.commit()

        try:
            size = run_pg_dump_sql_gz(path)
            record.backup_size = size
            record.backup_status = BackupStatus.COMPLETED
            record.completed_at = datetime.now(timezone.utc)
            cloud_uri = cls.upload_to_cloud(path)
            if cloud_uri:
                record.backup_notes = f'cloud_uri={cloud_uri}'
            db.session.commit()
            logger.info('Automated backup completed id=%s path=%s', record.id, path)
            return record
        except PgBackupError as exc:
            record.backup_status = BackupStatus.FAILED
            record.backup_notes = str(exc)
            db.session.commit()
            logger.error('Automated backup failed id=%s: %s', record.id, exc)
            raise BackupAutomationError(str(exc)) from exc

    @classmethod
    def upload_to_cloud(cls, local_path: str) -> Optional[str]:
        bucket = os.environ.get('BACKUP_S3_BUCKET', '').strip()
        if not bucket:
            return None

        key_prefix = os.environ.get('BACKUP_S3_PREFIX', 'medical-system/backups').strip('/')
        filename = os.path.basename(local_path)
        object_key = f'{key_prefix}/{filename}'

        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:
            raise BackupAutomationError('boto3 required for cloud backup upload') from exc

        client_kwargs = {}
        endpoint = os.environ.get('BACKUP_S3_ENDPOINT_URL', '').strip()
        if endpoint:
            client_kwargs['endpoint_url'] = endpoint
        region = os.environ.get('BACKUP_S3_REGION', '').strip()
        if region:
            client_kwargs['region_name'] = region

        client = boto3.client('s3', **client_kwargs)
        extra_args = {}
        kms_key = os.environ.get('BACKUP_S3_KMS_KEY_ID', '').strip()
        if kms_key:
            extra_args['ServerSideEncryption'] = 'aws:kms'
            extra_args['SSEKMSKeyId'] = kms_key
        else:
            extra_args['ServerSideEncryption'] = 'AES256'

        try:
            client.upload_file(local_path, bucket, object_key, ExtraArgs=extra_args)
        except (BotoCoreError, ClientError) as exc:
            raise BackupAutomationError(f'S3 upload failed: {exc}') from exc

        uri = f's3://{bucket}/{object_key}'
        logger.info('Backup uploaded to %s', uri)
        return uri

    @classmethod
    def tick(cls, app) -> None:
        """Invoke from background worker — respects BACKUP_AUTOMATION_ENABLED."""
        if not cls.is_enabled():
            return
        with app.app_context():
            try:
                cls.run_scheduled_backup()
            except BackupAutomationError as exc:
                logger.error('Backup automation tick failed: %s', exc)
