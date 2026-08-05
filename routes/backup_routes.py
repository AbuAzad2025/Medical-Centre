"""
مسارات النسخ الاحتياطي - Backup Routes
Medical System Backup Routes
"""

import contextlib
import logging
import os
from datetime import UTC, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup
from services.pg_backup_service import (
    PgBackupError,
    build_backup_path,
    restore_pg_sql_gz,
    run_pg_dump_sql_gz,
)
from utils.db_safety import safe_commit
from utils.decorators import super_admin_required

backup_bp = Blueprint('backup', __name__)
logger = logging.getLogger(__name__)


@backup_bp.route('/backup/dashboard')
@login_required
@super_admin_required
def dashboard():
    """لوحة تحكم النسخ الاحتياطي"""
    try:
        total_backups = db.session.execute(select(func.count()).select_from(Backup)).scalar()
        completed_backups = db.session.execute(
            select(func.count()).select_from(Backup).filter_by(backup_status=BackupStatus.COMPLETED)
        ).scalar()
        failed_backups = db.session.execute(
            select(func.count()).select_from(Backup).filter_by(backup_status=BackupStatus.FAILED)
        ).scalar()
        scheduled_backups = db.session.execute(
            select(func.count()).select_from(Backup).filter_by(is_scheduled=True)
        ).scalar()
        recent_backups = (
            db.session.execute(select(Backup).order_by(Backup.created_at.desc()).limit(5))
            .scalars()
            .all()
        )
        stats = {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'scheduled_backups': scheduled_backups,
        }
        return render_template('backup/dashboard.html', stats=stats, recent_backups=recent_backups)
    except Exception:
        logger.exception('Error in backup dashboard: %s')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))


@backup_bp.route('/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_backup():
    """إنشاء نسخة احتياطية جديدة"""
    try:
        if request.method == 'POST':
            backup_name = (request.form.get('backup_name') or 'medical_backup').strip()
            backup_type = request.form.get('backup_type') or 'full'
            description = request.form.get('description')
            is_encrypted = request.form.get('is_encrypted') == 'on'

            backup_path = build_backup_path('backups', backup_name)
            backup = Backup(
                backup_name=backup_name,
                backup_type=backup_type,
                description=description,
                is_encrypted=is_encrypted,
                backup_path=backup_path,
                backup_status=BackupStatus.IN_PROGRESS,
                started_at=datetime.now(UTC),
                created_by=current_user.id,
            )
            db.session.add(backup)
            safe_commit(db.session, error_message='database commit failed', reraise=True)

            from celery_app import celery_is_enabled, task_always_eager
            from services.backup_queue_service import BackupQueueError, queue_system_backup

            if celery_is_enabled() or task_always_eager():
                try:
                    queue_system_backup(backup.id)
                    flash('تم إرسال النسخة الاحتياطية إلى قائمة الانتظار', 'success')
                    return redirect(url_for('backup.dashboard'))
                except BackupQueueError as exc:
                    flash(f'تعذر جدولة النسخة الاحتياطية: {exc}', 'error')
                    return redirect(url_for('backup.create_backup'))

            try:
                size = create_backup_file(backup)
                backup.backup_size = size
                backup.backup_status = BackupStatus.COMPLETED
                backup.completed_at = datetime.now(UTC)
                flash('تم إنشاء النسخة الاحتياطية بنجاح', 'success')
            except PgBackupError as exc:
                backup.backup_status = BackupStatus.FAILED
                backup.backup_notes = str(exc)
                if os.path.exists(backup.backup_path):
                    with contextlib.suppress(OSError):
                        os.remove(backup.backup_path)
                flash('فشل في إنشاء النسخة الاحتياطية', 'error')
                logger.exception('Backup failed for id=%s: %s')

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            return redirect(url_for('backup.dashboard'))

        return render_template('backup/create_backup.html')
    except Exception:
        logger.exception('Error creating backup: %s')
        flash('حدث خطأ في إنشاء النسخة الاحتياطية', 'error')
        return render_template('backup/create_backup.html')


@backup_bp.route('/list')
@login_required
@super_admin_required
def list_backups():
    try:
        backups = (
            db.session.execute(select(Backup).order_by(Backup.created_at.desc())).scalars().all()
        )
        return render_template('backup/list_backups.html', backups=backups)
    except Exception:
        logger.exception('Error listing backups: %s')
        flash('حدث خطأ في تحميل قائمة النسخ الاحتياطية', 'error')
        return redirect(url_for('backup.dashboard'))


@backup_bp.route('/restore/<int:backup_id>', methods=['POST'])
@login_required
@super_admin_required
def restore_backup(backup_id):
    try:
        backup = db.session.get(Backup, backup_id)
        if not backup:
            abort(404)
        if not backup.is_restorable():
            flash('لا يمكن استعادة هذه النسخة الاحتياطية', 'error')
            return redirect(url_for('backup.list_backups'))

        success = restore_backup_file(backup)
        if success:
            backup.restore_count += 1
            backup.last_restore = datetime.now(UTC)
            backup.last_restore_by = current_user.id
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم استعادة النسخة الاحتياطية بنجاح', 'success')
        else:
            flash('فشل في استعادة النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))
    except Exception:
        logger.exception('Error restoring backup: %s')
        flash('حدث خطأ في استعادة النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))


@backup_bp.route('/download/<int:backup_id>')
@login_required
@super_admin_required
def download_backup(backup_id):
    try:
        backup = db.session.get(Backup, backup_id)
        if not backup:
            abort(404)
        if not os.path.exists(backup.backup_path):
            flash('النسخة الاحتياطية غير موجودة', 'error')
            return redirect(url_for('backup.list_backups'))
        download_name = os.path.basename(backup.backup_path)
        return send_file(backup.backup_path, as_attachment=True, download_name=download_name)
    except Exception:
        logger.exception('Error downloading backup: %s')
        flash('حدث خطأ في تحميل النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))


@backup_bp.route('/delete/<int:backup_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_backup(backup_id):
    try:
        backup = db.session.get(Backup, backup_id)
        if not backup:
            abort(404)
        if os.path.exists(backup.backup_path):
            os.remove(backup.backup_path)
        db.session.delete(backup)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم حذف النسخة الاحتياطية بنجاح', 'success')
        return redirect(url_for('backup.list_backups'))
    except Exception:
        logger.exception('Error deleting backup: %s')
        flash('حدث خطأ في حذف النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))


def create_backup_file(backup) -> int:
    """Create a PostgreSQL .sql.gz backup via native pg_dump."""
    return run_pg_dump_sql_gz(backup.backup_path)


def restore_backup_file(backup) -> bool:
    """Restore a PostgreSQL .sql.gz backup via psql."""
    try:
        restore_pg_sql_gz(backup.backup_path)
        return True
    except PgBackupError:
        logger.exception('Restore failed for backup id=%s: %s')
        return False
