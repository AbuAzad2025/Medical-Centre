"""
Backup Restore Routes
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models import Backup, BackupRestoreLog
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

backup_restore_bp = Blueprint('backup_restore', __name__)


@backup_restore_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'owner')
@handle_route_errors
def index():
    if request.method == 'POST':
        backup_id = request.form.get('backup_id', type=int)
        operation = request.form.get('operation', 'restore')
        confirm = request.form.get('confirm') == 'RESTORE'
        if not confirm:
            flash('يجب كتابة RESTORE للتأكيد قبل الاستعادة', 'error')
            return redirect(url_for('backup_restore.index'))
        backup = db.session.get(Backup, backup_id) if backup_id else None
        if not backup or not backup.file_path or not Path(backup.file_path).exists():
            flash('ملف النسخة غير موجود', 'error')
            return redirect(url_for('backup_restore.index'))
        log = BackupRestoreLog(
            backup_id=backup_id,
            operation=operation,
            status='running',
            initiated_by=current_user.id,
            source_path=backup.file_path,
            started_at=datetime.now(UTC),
        )
        db.session.add(log)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        # Real restore via pg_backup_service (supports plain gz and custom)
        start = time.monotonic()
        try:
            from services.pg_backup_service import pg_backup_service

            if hasattr(pg_backup_service, 'restore_backup'):
                ok = pg_backup_service.restore_backup(backup.file_path)
            elif hasattr(pg_backup_service, 'restore_pg_sql_gz'):
                ok = pg_backup_service.restore_pg_sql_gz(backup.file_path)
            else:
                ok = False
            duration = int(time.monotonic() - start)
            log.status = 'success' if ok else 'failed'
            log.completed_at = datetime.now(UTC)
            log.duration_seconds = duration
            log.details = json.dumps(
                {
                    'message': 'Restore completed' if ok else 'Restore failed',
                    'file': backup.file_path,
                }
            )
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash(
                'تمت عملية الاستعادة بنجاح' if ok else 'فشلت الاستعادة — راجع السجلات',
                'success' if ok else 'error',
            )
        except Exception as exc:
            duration = int(time.monotonic() - start)
            log.status = 'failed'
            log.completed_at = datetime.now(UTC)
            log.duration_seconds = duration
            log.details = json.dumps({'error': str(exc)[:500]})
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash(f'فشلت الاستعادة: {exc}', 'error')
        return redirect(url_for('backup_restore.index'))

    backups = db.session.execute(select(Backup).order_by(Backup.created_at.desc())).scalars().all()
    restore_logs = (
        db.session.execute(
            select(BackupRestoreLog).order_by(BackupRestoreLog.started_at.desc()).limit(20)
        )
        .scalars()
        .all()
    )
    return render_template('backup_restore/index.html', backups=backups, restore_logs=restore_logs)
