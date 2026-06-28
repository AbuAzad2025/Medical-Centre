"""backup routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
import logging
from sqlalchemy import func
from app.shared.enums import BackupStatus
from datetime import datetime, timezone, timedelta


# =============================================
# BACKUP ROUTES
# =============================================

@super_admin_bp.route('/backup')
@login_required
@super_admin_required
def backup():
    """النسخ الاحتياطي - عرض القائمة والإحصائيات"""
    try:
        from models.backup import Backup
        from datetime import datetime, timedelta
        
        # جلب جميع النسخ مرتبة بالأحدث
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        
        # حساب الإحصائيات
        total_backups = len(backups)
        successful_backups = sum(1 for b in backups if b.backup_status == BackupStatus.COMPLETED)
        failed_backups = sum(1 for b in backups if b.backup_status == BackupStatus.FAILED)
        
        # حساب الحجم الإجمالي
        total_size_bytes = sum(b.backup_size for b in backups if b.backup_size)
        total_size_gb = round(total_size_bytes / (1024 * 1024 * 1024), 2)
        
        # تحديد وقت آخر نسخة
        last_backup_time = "لا يوجد"
        if backups:
            last_backup = backups[0]
            diff = datetime.now() - last_backup.created_at
            if diff.days > 0:
                last_backup_time = f"منذ {diff.days} يوم"
            elif diff.seconds > 3600:
                last_backup_time = f"منذ {diff.seconds // 3600} ساعة"
            elif diff.seconds > 60:
                last_backup_time = f"منذ {diff.seconds // 60} دقيقة"
            else:
                last_backup_time = "منذ لحظات"
                
        stats = {
            'total': total_backups,
            'success': successful_backups,
            'failed': failed_backups,
            'size': total_size_gb,
            'last_backup': last_backup_time
        }

        # استرجاع إعدادات النسخ الاحتياطي
        from models.system_config import SystemConfig
        
        def get_config_value(key, default):
            config = SystemConfig.query.filter_by(config_key=key).first()
            return config.get_value() if config else default
            
        settings = {
            'frequency': get_config_value('backup_frequency', 'daily'),
            'retention': get_config_value('backup_retention', 7),
            'location': get_config_value('backup_location', '/backups'),
            'compression': get_config_value('backup_compression', 'zip'),
            'auto_backup': get_config_value('backup_auto_enabled', True)
        }

        return render_template('super_admin/system_backup.html', backups=backups, stats=stats, settings=settings)
    except Exception as e:
        logging.error(f"Error loading backups: {str(e)}")
        return render_template('super_admin/system_backup.html', backups=[], stats={}, settings={})

@super_admin_bp.route('/backup/create', methods=['POST'])
@login_required
@super_admin_required
def create_backup():
    """إنشاء نسخة احتياطية PostgreSQL عبر pg_dump"""
    try:
        from datetime import datetime, timezone
        import os
        from models.backup import Backup
        from app_factory import db
        from services.pg_backup_service import PgBackupError, build_backup_path, run_pg_dump_sql_gz
        from app.shared.enums import BackupStatus

        data = request.get_json() if request.is_json else {}
        req_type = data.get('type', 'full')
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{req_type}_{timestamp}'
        backup_path = build_backup_path('backups', backup_name)

        backup = Backup(
            backup_name=backup_name,
            backup_type='full' if req_type == 'full' else req_type,
            backup_path=backup_path,
            backup_status=BackupStatus.IN_PROGRESS,
            created_by=current_user.id,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(backup)
        db.session.commit()

        try:
            size = run_pg_dump_sql_gz(backup_path)
            backup.backup_size = size
            backup.backup_status = BackupStatus.COMPLETED
            backup.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'تم إنشاء النسخة الاحتياطية بنجاح',
                'backup_file': os.path.basename(backup_path),
            })
        except PgBackupError as exc:
            backup.backup_status = BackupStatus.FAILED
            backup.backup_notes = str(exc)
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError:
                    pass
            db.session.commit()
            return jsonify({'success': False, 'message': str(exc)}), 500

    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'تعذر إنشاء النسخة الاحتياطية حالياً'
        }), 500

@super_admin_bp.route('/backup/restore/<int:backup_id>', methods=['POST'])
@login_required
@super_admin_required
def restore_backup(backup_id):
    """استعادة نسخة احتياطية"""
    try:
        from models.backup import Backup
        from app_factory import db
        from routes.backup_routes import restore_backup_file
        
        backup = db.session.get(Backup, backup_id)
        if not backup:
            return jsonify({'success': False, 'message': 'النسخة الاحتياطية غير موجودة'}), 404
            
        success = restore_backup_file(backup)
        
        if success:
            backup.restore_count += 1
            backup.last_restore = datetime.now(timezone.utc)
            backup.last_restore_by = current_user.id
            db.session.commit()
            return jsonify({'success': True, 'message': 'تم استعادة النسخة الاحتياطية بنجاح'})
        else:
            return jsonify({'success': False, 'message': 'فشل في استعادة النسخة الاحتياطية'}), 500
            
    except Exception as e:
        logging.error(f"Error restoring backup: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر استعادة النسخة الاحتياطية حالياً'}), 500

@super_admin_bp.route('/backup/delete/<int:backup_id>', methods=['POST'])
@login_required
@super_admin_required
def delete_backup(backup_id):
    """حذف نسخة احتياطية"""
    try:
        from models.backup import Backup
        from app_factory import db
        import os
        
        backup = db.session.get(Backup, backup_id)
        if not backup:
            return jsonify({'success': False, 'message': 'النسخة الاحتياطية غير موجودة'}), 404
            
        # حذف الملف
        if backup.backup_path and os.path.exists(backup.backup_path):
            try:
                os.remove(backup.backup_path)
            except Exception as e:
                logging.error(f"Error deleting backup file: {str(e)}")
        
        db.session.delete(backup)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم حذف النسخة الاحتياطية بنجاح'})
            
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر حذف النسخة الاحتياطية حالياً'}), 500

@super_admin_bp.route('/backup/cancel/<int:backup_id>', methods=['POST'])
@login_required
@super_admin_required
def cancel_backup(backup_id):
    """إلغاء (أو تحديث حالة) نسخة احتياطية عالقة"""
    try:
        from models.backup import Backup
        from app_factory import db
        from datetime import datetime
        
        backup = db.session.get(Backup, backup_id)
        if not backup:
            return jsonify({'success': False, 'message': 'النسخة الاحتياطية غير موجودة'}), 404
            
        if backup.backup_status not in ['PENDING', 'IN_PROGRESS']:
             return jsonify({'success': False, 'message': 'لا يمكن إلغاء هذه النسخة لأنها مكتملة أو فاشلة بالفعل'}), 400

        backup.backup_status = BackupStatus.CANCELLED
        backup.completed_at = datetime.now()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء النسخة الاحتياطية بنجاح'})
            
    except Exception as e:
        logging.error(f"Error cancelling backup: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء النسخة الاحتياطية حالياً'}), 500

@super_admin_bp.route('/backup/schedule', methods=['GET', 'POST'])
@login_required
@super_admin_required
def backup_schedule():
    """إدارة جدولة النسخ الاحتياطي"""
    try:
        from models.system_config import SystemConfig
        from app_factory import db
        
        if request.method == 'POST':
            data = request.get_json()
            
            # Helper to update or create config
            def update_config(key, value, type='string'):
                config = SystemConfig.query.filter_by(config_key=key).first()
                if not config:
                    config = SystemConfig(config_key=key, category='backup', is_system=True)
                    db.session.add(config)
                
                config.config_type = type
                config.set_value(value)
            
            update_config('backup_schedule_enabled', data.get('enabled', False), 'boolean')
            update_config('backup_schedule_type', data.get('type', 'daily'), 'string')
            update_config('backup_schedule_time', data.get('time', '00:00'), 'string')
            
            db.session.commit()
            return jsonify({'success': True, 'message': 'تم حفظ إعدادات الجدولة بنجاح'})
            
        else:
            # Get current settings
            def get_config(key, default):
                config = SystemConfig.query.filter_by(config_key=key).first()
                return config.get_value() if config else default
                
            return jsonify({
                'success': True,
                'enabled': get_config('backup_schedule_enabled', False),
                'type': get_config('backup_schedule_type', 'daily'),
                'time': get_config('backup_schedule_time', '00:00')
            })
            
    except Exception as e:
        logging.error(f"Error in backup schedule: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر حفظ جدولة النسخ الاحتياطي حالياً'}), 500

@super_admin_bp.route('/backup/report')
@login_required
@super_admin_required
def backup_report():
    """عرض تقرير النسخ الاحتياطي"""
    try:
        from models.backup import Backup
        
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        
        # Calculate stats
        total = len(backups)
        success = sum(1 for b in backups if b.backup_status == BackupStatus.COMPLETED)
        failed = sum(1 for b in backups if b.backup_status == BackupStatus.FAILED)
        size_bytes = sum(b.backup_size for b in backups if b.backup_size)
        size_gb = round(size_bytes / (1024 * 1024 * 1024), 2)
        
        stats = {
            'total': total,
            'success': success,
            'failed': failed,
            'size': size_gb
        }
        
        return render_template('super_admin/backup_report.html', backups=backups, stats=stats)
    except Exception as e:
        logging.error(f"Error generating backup report: {str(e)}")
        flash('حدث خطأ في إنشاء التقرير', 'error')
        return redirect(url_for('super_admin.backup'))

@super_admin_bp.route('/backup/export-logs')
@login_required
@super_admin_required
def export_backup_logs():
    """تصدير سجلات النسخ الاحتياطي CSV"""
    try:
        from models.backup import Backup
        import csv
        import io
        from flask import make_response
        
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Type', 'Status', 'Path', 'Size (Bytes)', 'Created At', 'Completed At'])
        
        for b in backups:
            cw.writerow([
                b.id,
                b.backup_type,
                b.backup_status,
                b.backup_path,
                b.backup_size,
                b.created_at,
                b.completed_at
            ])
            
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=backup_logs.csv"
        output.headers["Content-type"] = "text/csv"
        return output
        
    except Exception as e:
        logging.error(f"Error exporting backup logs: {str(e)}")
        flash('حدث خطأ في تصدير السجلات', 'error')
        return redirect(url_for('super_admin.backup'))

@super_admin_bp.route('/backup/history')
@login_required
@super_admin_required
def backup_history():
    """API للحصول على تاريخ النسخ الاحتياطي"""
    try:
        from models.backup import Backup
        
        backups = Backup.query.order_by(Backup.created_at.desc()).limit(50).all()
        
        history = [{
            'id': b.id,
            'created_at': b.created_at.strftime('%Y-%m-%d %H:%M'),
            'type': b.backup_type,
            'status': b.backup_status,
            'size': b.backup_size,
            'message': f"نسخة {b.backup_type} - {b.backup_status}"
        } for b in backups]
        
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        logging.error(f"Error getting backup history: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب سجل النسخ الاحتياطي حالياً'}), 500
