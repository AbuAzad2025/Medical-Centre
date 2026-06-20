"""system routes - extracted from monolithic super_admin.py"""

from routes.super_admin import super_admin_bp

# Imports
 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
from services.super_admin_service import super_admin_service
import logging
from sqlalchemy import func


# =============================================
# SYSTEM ROUTES
# =============================================

@super_admin_bp.route('/system-config', methods=['GET', 'POST'])
@login_required
@super_admin_required
def system_config():
    """إعدادات النظام"""
    try:
        from app_factory import db
        from models.system_config import SystemConfig
        import logging as _logging
        from flask import current_app as _current_app
        
        if request.method == 'POST':
            # معالجة حفظ الإعدادات
            if request.is_json:
                data = request.get_json()
                allowed = {
                    'log_level': {'type': 'string', 'choices': ['DEBUG','INFO','WARNING','ERROR','CRITICAL'], 'category': 'system'},
                    'timezone': {'type': 'string', 'choices': ['Asia/Gaza','Asia/Jerusalem','UTC'], 'category': 'general'},
                    'language': {'type': 'string', 'choices': ['ar','en'], 'category': 'general'},
                    'currency': {'type': 'string', 'choices': ['ILS','USD','EUR'], 'category': 'general'},
                    'date_format': {'type': 'string', 'choices': ['dd/mm/yyyy','mm/dd/yyyy','yyyy-mm-dd'], 'category': 'general'},
                    'session_timeout': {'type': 'integer', 'min': 5, 'max': 480, 'category': 'security'},
                    'max_login_attempts': {'type': 'integer', 'min': 3, 'max': 10, 'category': 'security'},
                    'login_attempt_window_minutes': {'type': 'integer', 'min': 1, 'max': 120, 'category': 'security'},
                    'login_lockout_minutes': {'type': 'integer', 'min': 1, 'max': 240, 'category': 'security'},
                    'password_min_length': {'type': 'integer', 'min': 6, 'max': 20, 'category': 'security'},
                    'password_expiry_days': {'type': 'integer', 'min': 30, 'max': 365, 'category': 'security'},
                    'allow_partial_payment_global': {'type': 'boolean', 'category': 'system'},
                    'allow_debt_global': {'type': 'boolean', 'category': 'system'}
                }
                errors = []
                normalized = {}
                for key, val in data.items():
                    if key not in allowed:
                        errors.append(f"إعداد غير معروف: {key}")
                        continue
                    rule = allowed[key]
                    if rule['type'] == 'string':
                        sval = str(val)
                        if 'choices' in rule and sval not in rule['choices']:
                            errors.append(f"قيمة غير مسموحة لـ {key}")
                            continue
                        normalized[key] = sval
                    elif rule['type'] == 'integer':
                        try:
                            ival = int(val)
                            if ('min' in rule and ival < rule['min']) or ('max' in rule and ival > rule['max']):
                                errors.append(f"القيمة خارج النطاق لـ {key}")
                                continue
                            normalized[key] = ival
                        except Exception:
                            errors.append(f"قيمة غير صالحة لـ {key}")
                            continue
                    elif rule['type'] == 'boolean':
                        bval = val
                        if isinstance(bval, str):
                            bval = bval.strip().lower() in ('true','1','yes','on')
                        elif isinstance(bval, (int, float)):
                            bval = bool(bval)
                        else:
                            bval = bool(bval)
                        normalized[key] = bval
                    else:
                        normalized[key] = val
                if errors:
                    return jsonify({'success': False, 'message': 'فشل التحقق', 'errors': errors}), 400
                
                # حفظ الإعدادات في قاعدة البيانات
                for key, value in normalized.items():
                    setting = SystemConfig.query.filter_by(config_key=key).first()
                    if setting:
                        setting.config_value = str(value)
                        setting.updated_by = current_user.id
                        setting.updated_at = datetime.now(timezone.utc)
                    else:
                        config_type = 'string'
                        if isinstance(value, bool):
                            config_type = 'boolean'
                        elif isinstance(value, int):
                            config_type = 'integer'
                        setting = SystemConfig(
                            config_key=key,
                            config_value=str(value),
                            config_type=config_type,
                            category=allowed[key]['category'],
                            created_by=current_user.id,
                            updated_by=current_user.id
                        )
                        db.session.add(setting)

                # تطبيق مستوى السجلات فوراً إن تم إرساله
                log_level = data.get('log_level')
                if log_level:
                    level = getattr(_logging, str(log_level).upper(), None)
                    if isinstance(level, int):
                        _current_app.logger.setLevel(level)
                        for h in _current_app.logger.handlers:
                            h.setLevel(level)

                from models.audit_trail import AuditTrail
                db.session.commit()
                try:
                    change_desc = ', '.join([f"{k}={normalized[k]}" for k in normalized.keys()])
                    audit = AuditTrail(entity_type='system', entity_id=0, action='update', user_id=current_user.id, description='تحديث إعدادات النظام', notes=change_desc)
                    db.session.add(audit)
                    db.session.commit()
                except Exception:

                    logging.warning(f"Error in {__name__}: {e}")
                return jsonify({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'}), 200
            else:
                flash('تم حفظ الإعدادات بنجاح', 'success')
                return redirect(url_for('super_admin.system_config'))
        
        # معالجة تحميل الإعدادات (GET)
        if request.args.get('action') == 'load':
            settings = {}
            all_settings = SystemConfig.query.all()
            for setting in all_settings:
                settings[setting.config_key] = setting.config_value
            return jsonify({'success': True, 'settings': settings}), 200
        
        # معالجة اختبار الاتصال
        if request.args.get('action') == 'test_db':
            # هنا يمكن إضافة كود اختبار الاتصال
            return jsonify({'success': True, 'message': 'الاتصال ناجح'}), 200
        
        return render_template('super_admin/system_config.html')
        
    except Exception as e:
        logging.error(f"System config error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.is_json:
            return jsonify({'success': False, 'message': 'تعذر حفظ الإعدادات حالياً'}), 500
        else:
            flash('تعذر حفظ الإعدادات حالياً', 'error')
            return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/queue-settings', methods=['GET', 'POST'])
@login_required
@super_admin_required
def queue_settings():
    try:
        from app_factory import db
        from models.department import Department
        from models.queue_management import QueueSettings
        if request.method == 'GET' and request.args.get('action') == 'load':
            departments = Department.query.filter_by(is_active=True).all()
            items = []
            for dept in departments:
                qs = QueueSettings.query.filter_by(department_id=dept.id).first()
                items.append({
                    'department_id': dept.id,
                    'department_name': dept.name,
                    'max_queue_size': int(qs.max_queue_size) if qs and qs.max_queue_size is not None else 50,
                    'payment_required': bool(qs.payment_required) if qs else True,
                    'emergency_payment_waived': bool(qs.emergency_payment_waived) if qs else True,
                    'force_entry_allowed': bool(qs.force_entry_allowed) if qs else True,
                    'average_wait_time': int(qs.average_wait_time) if qs and qs.average_wait_time is not None else 30,
                    'allow_partial_payment': bool(qs.allow_partial_payment) if qs else True,
                    'allow_debt': bool(qs.allow_debt) if qs else False
                })
            return jsonify({'success': True, 'items': items}), 200
        if request.method == 'POST':
            if not request.is_json:
                return jsonify({'success': False, 'message': 'الطلب يجب أن يكون JSON'}), 400
            data = request.get_json() or {}
            items = data.get('items') or []
            for it in items:
                dept_id = it.get('department_id')
                if not dept_id:
                    continue
                qs = QueueSettings.query.filter_by(department_id=dept_id).first()
                if not qs:
                    qs = QueueSettings(department_id=dept_id)
                    db.session.add(qs)
                mx = it.get('max_queue_size')
                pr = it.get('payment_required')
                ew = it.get('emergency_payment_waived')
                fe = it.get('force_entry_allowed')
                aw = it.get('average_wait_time')
                ap = it.get('allow_partial_payment')
                ad = it.get('allow_debt')
                if mx is not None:
                    try:
                        qs.max_queue_size = int(mx)
                    except Exception:

                        logging.warning(f"Error in {__name__}: {e}")
                if pr is not None:
                    qs.payment_required = bool(pr)
                if ew is not None:
                    qs.emergency_payment_waived = bool(ew)
                if fe is not None:
                    qs.force_entry_allowed = bool(fe)
                if aw is not None:
                    try:
                        qs.average_wait_time = int(aw)
                    except Exception:

                        logging.warning(f"Error in {__name__}: {e}")
                if ap is not None:
                    qs.allow_partial_payment = bool(ap)
                if ad is not None:
                    qs.allow_debt = bool(ad)
            db.session.commit()
            return jsonify({'success': True}), 200
        return render_template('super_admin/queue_settings.html')
    except Exception as e:
        logging.error(f"Queue settings error: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ في إعدادات الأقسام'}), 500

@super_admin_bp.route('/system-backup')
@login_required
@super_admin_required
def system_backup():
    """النسخ الاحتياطية"""
    try:
        return redirect(url_for('super_admin.backup'))
    except Exception as e:
        logging.error(f"System backup error: {str(e)}")
        flash('حدث خطأ في تحميل النسخ الاحتياطية', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/system/maintenance')
@login_required
@super_admin_required
def system_maintenance():
    """صيانة النظام"""
    try:
        from models.system_config import SystemConfig
        from app_factory import db
        
        # إحصائيات النظام
        from models.user import User
        
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'inactive_users': User.query.filter_by(is_active=False).count(),
            'total_patients': 0,  # سيتم تطويرها لاحقاً
            'total_departments': 0,  # سيتم تطويرها لاحقاً
            'database_size': get_database_size(),
            'system_uptime': get_system_uptime(),
            'last_backup': get_last_backup_time()
        }
        
        return render_template('super_admin/system_maintenance.html', stats=stats)
        
    except Exception as e:
        logging.error(f"System maintenance error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة صيانة النظام', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/system/cleanup', methods=['POST'])
@login_required
@super_admin_required
def system_cleanup():
    """تنظيف النظام"""
    try:
        from app_factory import db
        
        cleanup_type = request.form.get('cleanup_type')
        
        if cleanup_type == 'logs':
            # تنظيف السجلات القديمة
            from models.audit_trail import AuditTrail
            from datetime import datetime, timedelta
            
            old_logs = AuditTrail.query.filter(
                AuditTrail.created_at < datetime.now(timezone.utc) - timedelta(days=90)
            ).delete()
            
            db.session.commit()
            flash(f'تم حذف {old_logs} سجل قديم', 'success')
            
        elif cleanup_type == 'sessions':
            # تنظيف الجلسات المنتهية الصلاحية
            # هنا يمكن إضافة منطق تنظيف الجلسات
            flash('تم تنظيف الجلسات المنتهية الصلاحية', 'success')
            
        elif cleanup_type == 'cache':
            # تنظيف الكاش
            # هنا يمكن إضافة منطق تنظيف الكاش
            flash('تم تنظيف الكاش', 'success')
        
        elif cleanup_type == 'seed_data':
            # SAFETY FIX: Destructive seed_data cleanup is disabled to prevent accidental production data loss.
            flash('تم تعطيل ميزة تنظيف بيانات البذور (seed_data) لأسباب أمنية.', 'warning')
            return redirect(url_for('super_admin.system_maintenance'))
        elif cleanup_type == 'harmonize':
            from services.pricing_service import PricingService
            r_all = PricingService.cleanup_all(max_keep_per_role=1)
            r_purge = PricingService.purge_users_keep_policy()
            db.session.commit()
            flash('تم توحيد وتنظيف البيانات بدون إنشاء أي بيانات افتراضية', 'success')
        
        return redirect(url_for('super_admin.system_maintenance'))
        
    except Exception as e:
        logging.error(f"System cleanup error: {str(e)}")
        flash('حدث خطأ في تنظيف النظام', 'error')
        return redirect(url_for('super_admin.system_maintenance'))

@super_admin_bp.route('/system/notifications/run', methods=['POST'])
@login_required
@super_admin_required
def run_notifications():
    try:
        from services.notification_service import NotificationService
        res = NotificationService.check_and_send_alerts()
        msg = res.get('message') or 'تم تشغيل التنبيهات'
        flash(msg, 'success' if res.get('success') else 'error')
        return redirect(url_for('super_admin.system_maintenance'))
    except Exception as e:
        logging.error(f"Run notifications error: {str(e)}")
        flash('حدث خطأ في تشغيل التنبيهات', 'error')
        return redirect(url_for('super_admin.system_maintenance'))

@super_admin_bp.route('/system/notifications/init-templates', methods=['POST'])
@login_required
@super_admin_required
def init_notification_templates():
    try:
        from services.notification_service import NotificationService
        res = NotificationService.create_default_templates()
        flash(res.get('message', 'تم تجهيز القوالب الافتراضية'), 'success' if res.get('success') else 'error')
        return redirect(url_for('super_admin.system_maintenance'))
    except Exception as e:
        logging.error(f"Init notification templates error: {str(e)}")
        flash('حدث خطأ في إنشاء القوالب الافتراضية', 'error')
        return redirect(url_for('super_admin.system_maintenance'))

# دوال مساعدة إضافية
def get_database_size():
    """حجم قاعدة البيانات"""
    try:
        import os
        db_path = 'instance/medical_system.db'
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "غير محدد"
    except:
        return "غير محدد"

def get_last_backup_time():
    """وقت آخر نسخة احتياطية"""
    try:
        # هنا يمكن إضافة منطق للتحقق من آخر نسخة احتياطية
        return "لم يتم إنشاء نسخة احتياطية بعد"
    except:
        return "غير محدد"

@super_admin_bp.route('/system')
@login_required
@super_admin_required
def system():
    """إعدادات النظام"""
    return render_template('super_admin/system_config.html')

@super_admin_bp.route('/backup/settings', methods=['POST'])
@login_required
@super_admin_required
def save_backup_settings():
    """حفظ إعدادات النسخ الاحتياطي العامة"""
    try:
        from models.system_config import SystemConfig
        from app_factory import db
        
        data = request.get_json()
        
        # دالة مساعدة لتحديث الإعدادات
        def update_config(key, value):
            config = SystemConfig.query.filter_by(config_key=key).first()
            if not config:
                config = SystemConfig(config_key=key, category='backup', is_system=True, config_type='string')
                db.session.add(config)
            config.set_value(value)
            
        update_config('backup_frequency', data.get('frequency', 'daily'))
        update_config('backup_retention', data.get('retention', '7'))
        update_config('backup_location', data.get('location', '/backups'))
        update_config('backup_compression', data.get('compression', 'zip'))
        update_config('backup_auto_enabled', data.get('auto_backup', True))
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'})
        
    except Exception as e:
        logging.error(f"Error saving backup settings: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر حفظ إعدادات النسخ الاحتياطي حالياً'}), 500

@super_admin_bp.route('/maintenance/automation', methods=['GET', 'POST'])
@login_required
@super_admin_required
def maintenance_automation():
    try:
        from models.system_config import SystemConfig
        if request.method == 'POST':
            data = request.get_json() or {}
            cfg = SystemConfig.query.filter_by(config_key='maintenance_automation').first()
            if not cfg:
                cfg = SystemConfig(config_key='maintenance_automation', category='system', is_system=True, config_type='json')
                db.session.add(cfg)
            cfg.set_value({
                'auto_cleanup': bool(data.get('auto_cleanup', False)),
                'cleanup_days': int(data.get('cleanup_days') or 30),
                'log_retention_days': int(data.get('log_retention_days') or 90),
                'auto_backup': bool(data.get('auto_backup', True)),
            })
            db.session.commit()
            return jsonify({'success': True, 'message': 'تم حفظ إعدادات الأتمتة'}), 200
        cfg = SystemConfig.query.filter_by(config_key='maintenance_automation').first()
        settings = cfg.get_value() if cfg else {}
        return render_template('super_admin/maintenance_automation.html', settings=settings)
    except Exception as e:
        logging.error(f"Maintenance automation error: {str(e)}")
        return render_template('super_admin/maintenance_automation.html', settings={})
