"""
مسارات النسخ الاحتياطي - Backup Routes
Medical System Backup Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from models.backup import Backup
from app_factory import db
import logging
import os
from datetime import datetime, timezone
from app.shared.enums import BackupStatus
from services.pg_backup_service import (
    PgBackupError,
    build_backup_path,
    restore_pg_sql_gz,
    run_pg_dump_sql_gz,
)

backup_bp = Blueprint('backup', __name__)
logger = logging.getLogger(__name__)


@backup_bp.route('/backup/dashboard')
@login_required
@super_admin_required
def dashboard():
    """لوحة تحكم النسخ الاحتياطي"""
    try:
        total_backups = Backup.query.count()
        completed_backups = Backup.query.filter_by(backup_status=BackupStatus.COMPLETED).count()
        failed_backups = Backup.query.filter_by(backup_status=BackupStatus.FAILED).count()
        scheduled_backups = Backup.query.filter_by(is_scheduled=True).count()
        recent_backups = Backup.query.order_by(Backup.created_at.desc()).limit(5).all()
        stats = {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'scheduled_backups': scheduled_backups,
        }
        return render_template('backup/dashboard.html', stats=stats, recent_backups=recent_backups)
    except Exception as e:
        logger.error('Error in backup dashboard: %s', e)
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
                started_at=datetime.now(timezone.utc),
                created_by=current_user.id,
            )
            db.session.add(backup)
            db.session.commit()

            try:
                size = create_backup_file(backup)
                backup.backup_size = size
                backup.backup_status = BackupStatus.COMPLETED
                backup.completed_at = datetime.now(timezone.utc)
                flash('تم إنشاء النسخة الاحتياطية بنجاح', 'success')
            except PgBackupError as exc:
                backup.backup_status = BackupStatus.FAILED
                backup.backup_notes = str(exc)
                if os.path.exists(backup.backup_path):
                    try:
                        os.remove(backup.backup_path)
                    except OSError:
                        pass
                flash('فشل في إنشاء النسخة الاحتياطية', 'error')
                logger.error('Backup failed for id=%s: %s', backup.id, exc)

            db.session.commit()
            return redirect(url_for('backup.dashboard'))

        return render_template('backup/create_backup.html')
    except Exception as e:
        logger.error('Error creating backup: %s', e)
        flash('حدث خطأ في إنشاء النسخة الاحتياطية', 'error')
        return render_template('backup/create_backup.html')


@backup_bp.route('/list')
@login_required
@super_admin_required
def list_backups():
    try:
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        return render_template('backup/list_backups.html', backups=backups)
    except Exception as e:
        logger.error('Error listing backups: %s', e)
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
            backup.last_restore = datetime.now(timezone.utc)
            backup.last_restore_by = current_user.id
            db.session.commit()
            flash('تم استعادة النسخة الاحتياطية بنجاح', 'success')
        else:
            flash('فشل في استعادة النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))
    except Exception as e:
        logger.error('Error restoring backup: %s', e)
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
    except Exception as e:
        logger.error('Error downloading backup: %s', e)
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
        db.session.commit()
        flash('تم حذف النسخة الاحتياطية بنجاح', 'success')
        return redirect(url_for('backup.list_backups'))
    except Exception as e:
        logger.error('Error deleting backup: %s', e)
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
    except PgBackupError as exc:
        logger.error('Restore failed for backup id=%s: %s', backup.id, exc)
        return False
