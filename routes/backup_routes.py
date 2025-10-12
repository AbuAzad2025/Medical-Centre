"""
مسارات النسخ الاحتياطي - Backup Routes
Medical System Backup Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file
from flask_login import login_required, current_user
from models.backup import Backup, BackupLog
from models.user import User
from app_factory import db
import logging
import os
import shutil
from datetime import datetime
import zipfile

backup_bp = Blueprint('backup', __name__)

@backup_bp.route('/backup/dashboard')
@login_required
def dashboard():
    """لوحة تحكم النسخ الاحتياطي"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # إحصائيات النسخ الاحتياطي
        total_backups = Backup.query.count()
        completed_backups = Backup.query.filter_by(backup_status='COMPLETED').count()
        failed_backups = Backup.query.filter_by(backup_status='FAILED').count()
        scheduled_backups = Backup.query.filter_by(is_scheduled=True).count()
        
        # آخر النسخ الاحتياطي
        recent_backups = Backup.query.order_by(Backup.created_at.desc()).limit(5).all()
        
        stats = {
            'total_backups': total_backups,
            'completed_backups': completed_backups,
            'failed_backups': failed_backups,
            'scheduled_backups': scheduled_backups
        }
        
        return render_template('backup/dashboard.html', stats=stats, recent_backups=recent_backups)
    except Exception as e:
        logging.error(f"Error in backup dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@backup_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_backup():
    """إنشاء نسخة احتياطية جديدة"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        if request.method == 'POST':
            backup_name = request.form.get('backup_name')
            backup_type = request.form.get('backup_type')
            description = request.form.get('description')
            is_encrypted = request.form.get('is_encrypted') == 'on'
            
            # إنشاء النسخة الاحتياطية
            backup = Backup(
                backup_name=backup_name,
                backup_type=backup_type,
                description=description,
                is_encrypted=is_encrypted,
                backup_path=f"backups/{backup_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                created_by=current_user.id
            )
            
            db.session.add(backup)
            db.session.commit()
            
            # إنشاء النسخة الاحتياطية الفعلية
            success = create_backup_file(backup)
            
            if success:
                backup.backup_status = 'COMPLETED'
                backup.completed_at = datetime.utcnow()
                flash('تم إنشاء النسخة الاحتياطية بنجاح', 'success')
            else:
                backup.backup_status = 'FAILED'
                flash('فشل في إنشاء النسخة الاحتياطية', 'error')
            
            db.session.commit()
            return redirect(url_for('backup.dashboard'))
        
        return render_template('backup/create_backup.html')
    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        flash('حدث خطأ في إنشاء النسخة الاحتياطية', 'error')
        return render_template('backup/create_backup.html')

@backup_bp.route('/list')
@login_required
def list_backups():
    """قائمة النسخ الاحتياطية"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        return render_template('backup/list_backups.html', backups=backups)
    except Exception as e:
        logging.error(f"Error listing backups: {str(e)}")
        flash('حدث خطأ في تحميل قائمة النسخ الاحتياطية', 'error')
        return redirect(url_for('backup.dashboard'))

@backup_bp.route('/restore/<int:backup_id>', methods=['POST'])
@login_required
def restore_backup(backup_id):
    """استعادة نسخة احتياطية"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        backup = Backup.query.get_or_404(backup_id)
        
        if not backup.is_restorable():
            flash('لا يمكن استعادة هذه النسخة الاحتياطية', 'error')
            return redirect(url_for('backup.list_backups'))
        
        # استعادة النسخة الاحتياطية
        success = restore_backup_file(backup)
        
        if success:
            backup.restore_count += 1
            backup.last_restore = datetime.utcnow()
            backup.last_restore_by = current_user.id
            db.session.commit()
            flash('تم استعادة النسخة الاحتياطية بنجاح', 'success')
        else:
            flash('فشل في استعادة النسخة الاحتياطية', 'error')
        
        return redirect(url_for('backup.list_backups'))
    except Exception as e:
        logging.error(f"Error restoring backup: {str(e)}")
        flash('حدث خطأ في استعادة النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))

@backup_bp.route('/download/<int:backup_id>')
@login_required
def download_backup(backup_id):
    """تحميل نسخة احتياطية"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        backup = Backup.query.get_or_404(backup_id)
        
        if not os.path.exists(backup.backup_path):
            flash('النسخة الاحتياطية غير موجودة', 'error')
            return redirect(url_for('backup.list_backups'))
        
        return send_file(backup.backup_path, as_attachment=True, download_name=f"{backup.backup_name}.zip")
    except Exception as e:
        logging.error(f"Error downloading backup: {str(e)}")
        flash('حدث خطأ في تحميل النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))

@backup_bp.route('/delete/<int:backup_id>', methods=['POST'])
@login_required
def delete_backup(backup_id):
    """حذف نسخة احتياطية"""
    if not current_user.is_super_admin():
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        backup = Backup.query.get_or_404(backup_id)
        
        # حذف الملف
        if os.path.exists(backup.backup_path):
            os.remove(backup.backup_path)
        
        # حذف من قاعدة البيانات
        db.session.delete(backup)
        db.session.commit()
        
        flash('تم حذف النسخة الاحتياطية بنجاح', 'success')
        return redirect(url_for('backup.list_backups'))
    except Exception as e:
        logging.error(f"Error deleting backup: {str(e)}")
        flash('حدث خطأ في حذف النسخة الاحتياطية', 'error')
        return redirect(url_for('backup.list_backups'))

def create_backup_file(backup):
    """إنشاء ملف النسخة الاحتياطية"""
    try:
        # إنشاء مجلد النسخ الاحتياطية
        os.makedirs(os.path.dirname(backup.backup_path), exist_ok=True)
        
        # إنشاء ملف ZIP
        with zipfile.ZipFile(backup.backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # إضافة ملف قاعدة البيانات
            if os.path.exists('instance/medical_system.db'):
                zipf.write('instance/medical_system.db', 'medical_system.db')
            
            # إضافة الملفات المهمة
            important_files = [
                'app.py',
                'app_factory.py',
                'config.py',
                'requirements.txt'
            ]
            
            for file in important_files:
                if os.path.exists(file):
                    zipf.write(file, file)
        
        # تحديث حجم النسخة الاحتياطية
        backup.backup_size = os.path.getsize(backup.backup_path)
        backup.started_at = datetime.utcnow()
        
        return True
    except Exception as e:
        logging.error(f"Error creating backup file: {str(e)}")
        return False

def restore_backup_file(backup):
    """استعادة ملف النسخة الاحتياطية"""
    try:
        if not os.path.exists(backup.backup_path):
            return False
        
        # استخراج الملفات
        with zipfile.ZipFile(backup.backup_path, 'r') as zipf:
            zipf.extractall('temp_restore')
        
        # استعادة ملف قاعدة البيانات
        if os.path.exists('temp_restore/medical_system.db'):
            shutil.copy2('temp_restore/medical_system.db', 'instance/medical_system.db')
        
        # تنظيف الملفات المؤقتة
        shutil.rmtree('temp_restore', ignore_errors=True)
        
        return True
    except Exception as e:
        logging.error(f"Error restoring backup file: {str(e)}")
        return False



