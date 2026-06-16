"""
Backup Restore Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app_factory import db
from models import BackupRestoreLog, Backup
import json
from datetime import datetime, timezone

backup_restore_bp = Blueprint('backup_restore', __name__)


@backup_restore_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        backup_id = request.form.get('backup_id', type=int)
        operation = request.form.get('operation', 'restore')
        backup = Backup.query.get(backup_id) if backup_id else None
        log = BackupRestoreLog(
            backup_id=backup_id,
            operation=operation,
            status='pending',
            initiated_by=current_user.id,
            source_path=backup.file_path if backup else None
        )
        db.session.add(log)
        db.session.commit()

        log.status = 'success'
        log.completed_at = datetime.now(timezone.utc)
        log.duration_seconds = 0
        log.details = json.dumps({'message': 'Restore simulation completed successfully'})
        db.session.commit()
        flash('تمت عملية الاستعادة بنجاح (محاكاة)', 'success')
        return redirect(url_for('backup_restore.index'))

    backups = Backup.query.order_by(Backup.created_at.desc()).all()
    restore_logs = BackupRestoreLog.query.order_by(BackupRestoreLog.started_at.desc()).limit(20).all()
    return render_template('backup_restore/index.html', backups=backups, restore_logs=restore_logs)
