"""
Backup Restore Routes
"""

import json
from datetime import UTC, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models import Backup, BackupRestoreLog
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors

backup_restore_bp = Blueprint('backup_restore', __name__)


@backup_restore_bp.route('/', methods=['GET', 'POST'])
@login_required
@handle_route_errors
def index():
    if request.method == 'POST':
        backup_id = request.form.get('backup_id', type=int)
        operation = request.form.get('operation', 'restore')
        backup = db.session.get(Backup, backup_id) if backup_id else None
        log = BackupRestoreLog(
            backup_id=backup_id,
            operation=operation,
            status='pending',
            initiated_by=current_user.id,
            source_path=backup.file_path if backup else None,
        )
        db.session.add(log)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        log.status = 'success'
        log.completed_at = datetime.now(UTC)
        log.duration_seconds = 0
        log.details = json.dumps({'message': 'Restore simulation completed successfully'})
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تمت عملية الاستعادة بنجاح (محاكاة)', 'success')
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
