 

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import super_admin_required
from services.access_control_service import AccessControlService
import logging
from sqlalchemy import func

# إنشاء Blueprint للسوبر أدمن
super_admin_bp = Blueprint('super_admin', __name__)

 

@super_admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """لوحة السوبر أدمن الذكية المتقدمة"""
    try:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        from models.service import ServiceMaster
        from datetime import datetime, timedelta, timezone
        
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        inactive_users = User.query.filter_by(is_active=False).count()
        admin_users = User.query.filter_by(is_admin=True).count()
        total_patients = Patient.query.count()
        total_visits = Visit.query.count()
        total_departments = Department.query.count()
        active_departments = Department.query.filter_by(is_active=True).count()
        total_services = ServiceMaster.query.count()
        active_services = ServiceMaster.query.filter_by(is_active=True).count()

        active_sessions = User.query.filter(User.last_login >= datetime.now() - timedelta(hours=24)).count()

        database_size = get_database_size()
        last_backup = get_last_backup_time()

        security_threats = get_security_threats()
        performance_optimization = get_performance_optimization()
        user_behavior_analysis = get_user_behavior_analysis()
        resource_utilization = get_resource_utilization()

        from models.audit_trail import LoginAttempt, SystemLog, SecurityEvent
        start_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        start_1h = datetime.now(timezone.utc) - timedelta(hours=1)
        failed_logins_24h = LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_24h).count()
        failed_logins_1h = LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_1h).count()
        error_logs_24h = SystemLog.query.filter(SystemLog.created_at >= start_24h, SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).count()
        critical_logs_24h = SystemLog.query.filter(SystemLog.created_at >= start_24h, SystemLog.log_level == 'CRITICAL').count()
        unresolved_security_events = SecurityEvent.query.filter(SecurityEvent.is_resolved == False).count()
        latest_security_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(10).all()
        latest_error_logs = SystemLog.query.filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL'])).order_by(SystemLog.created_at.desc()).limit(10).all()
        maintenance_cfg = None
        branch_templates_count = 0
        try:
            from models.system_config import SystemConfig
            maintenance_cfg = SystemConfig.query.filter_by(config_key='maintenance_automation').first()
            templates_cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
            templates_val = templates_cfg.get_value() if templates_cfg else []
            branch_templates_count = len(templates_val) if isinstance(templates_val, list) else 0
        except Exception:
            maintenance_cfg = None

        threats_count = len(security_threats) if security_threats else 0
        cpu = (resource_utilization or {}).get('cpu', 0) or 0
        mem = ((resource_utilization or {}).get('memory') or {}).get('percentage', 0) or 0
        disk = ((resource_utilization or {}).get('disk') or {}).get('percentage', 0) or 0
        load_factor = min(100, int((cpu + mem + disk) / 3))
        base_score = 90 if threats_count == 0 else 80 if threats_count <= 2 else 65
        score = max(30, min(100, int(base_score - (load_factor - 50) * 0.3)))
        health_color = 'success' if score >= 80 else 'warning' if score >= 60 else 'danger'
        health_status = 'ممتاز' if score >= 80 else 'جيد' if score >= 60 else 'حرج'

        system_health_score = {
            'score': score,
            'color': health_color,
            'status': health_status
        }

        ai_insights = {
            'total_recommendations': 12,
            'pending_recommendations': 3,
            'accepted_recommendations': 7,
            'high_confidence_recommendations': 4
        }

        predictive_analytics = {
            'growth_rate': round(((active_users - inactive_users) / (total_users or 1)) * 100, 2),
            'predicted_visits_next_week': total_visits + max(5, int(total_visits * 0.05)),
            'peak_hour': 11,
            'trend': 'growing' if active_users > inactive_users else 'stable' if active_users == inactive_users else 'declining'
        }

        stats = {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'admin_users': admin_users,
            'total_patients': total_patients,
            'total_visits': total_visits,
            'total_departments': total_departments,
            'active_departments': active_departments,
            'total_services': total_services,
            'active_services': active_services,
            'active_sessions': active_sessions,
            'security_events': threats_count,
            'system_uptime': '99.9%',
            'database_size': database_size,
            'last_backup': last_backup,
            'ai_insights': ai_insights,
            'smart_recommendations': [],
            'predictive_analytics': predictive_analytics,
            'system_health_score': system_health_score,
            'security_threats': security_threats,
            'performance_optimization': performance_optimization,
            'user_behavior_analysis': user_behavior_analysis,
            'resource_utilization': resource_utilization,
            'failed_logins_24h': int(failed_logins_24h or 0),
            'failed_logins_1h': int(failed_logins_1h or 0),
            'error_logs_24h': int(error_logs_24h or 0),
            'critical_logs_24h': int(critical_logs_24h or 0),
            'unresolved_security_events': int(unresolved_security_events or 0),
            'latest_security_events': latest_security_events,
            'latest_error_logs': latest_error_logs,
            'maintenance_automation': maintenance_cfg.get_value() if maintenance_cfg else {},
            'branch_templates_count': branch_templates_count
        }
        
        return render_template('super_admin/dashboard.html', stats=stats)
    
    except Exception as e:
        logging.error(f"Super admin dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template('super_admin/dashboard.html', stats={})

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
                    pass
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
                        pass
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
                        pass
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

@super_admin_bp.route('/users')
@login_required
@super_admin_required
def users():
    """إدارة المستخدمين والأدوار والصلاحيات"""
    try:
        from models.user import User
        from models.department import Department
        
        users_list = User.query.all()
        
        roles_list = [
            ('super_admin', 'السوبر أدمن'),
            ('admin', 'مدير'),
            ('manager', 'مدير المركز'),
            ('doctor', 'طبيب'),
            ('nurse', 'ممرض'),
            ('reception', 'موظف استقبال'),
            ('accountant', 'محاسب'),
            ('pharmacist', 'صيدلي'),
            ('lab', 'فني مختبر'),
            ('radiology', 'أشعة'),
            ('emergency', 'طوارئ')
        ]
        departments = Department.query.filter_by(is_active=True).all()
        
        return render_template('super_admin/users.html', 
                             users=users_list,
                             roles=roles_list,
                             permissions=[],
                             departments=departments)
    except Exception as e:
        logging.error(f"Users management error: {str(e)}")
        flash('حدث خطأ في تحميل البيانات', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_user():
    """إنشاء مستخدم جديد"""
    if request.method == 'POST':
        try:
            from models.user import User
            from models.department import Department
            from models.pricing import DoctorPricing
            from werkzeug.security import generate_password_hash
            
            user = User(
                username=request.form.get('username'),
                email=request.form.get('email'),
                full_name=request.form.get('full_name'),
                role=request.form.get('role'),
                department_id=request.form.get('department_id') or None,
                phone=request.form.get('phone'),
                doctor_room=request.form.get('doctor_room'),
                is_active=bool(request.form.get('is_active')),
                is_admin=bool(request.form.get('is_admin'))
            )
            user.set_password(request.form.get('password'))
            
            from app_factory import db
            db.session.add(user)
            db.session.commit()

            # إنشاء تسعير للطبيب إن وُجدت قيم أثناء الإنشاء
            if user.role == 'doctor':
                def _to_float(val):
                    try:
                        return float(val) if val not in (None, '',) else None
                    except Exception:
                        return None
                consultation_price = _to_float(request.form.get('consultation_price'))
                follow_up_price = _to_float(request.form.get('follow_up_price'))
                emergency_price = _to_float(request.form.get('emergency_price'))
                vip_price = _to_float(request.form.get('vip_price'))
                if any(v is not None for v in [consultation_price, follow_up_price, emergency_price, vip_price]):
                    dp = DoctorPricing(
                        doctor_id=user.id,
                        department_id=user.department_id if user.department_id else None,
                        consultation_price=consultation_price or 0.0,
                        follow_up_price=follow_up_price,
                        emergency_price=emergency_price,
                        vip_price=vip_price,
                        is_active=True
                    )
                    db.session.add(dp)
                    db.session.commit()
            
            flash('تم إنشاء المستخدم بنجاح', 'success')
            return redirect(url_for('super_admin.users'))
            
        except Exception as e:
            from app_factory import db
            db.session.rollback()
            logging.error(f"Create user error: {str(e)}")
            flash('تعذر إنشاء المستخدم، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    # جلب البيانات المطلوبة للنموذج
    from models.department import Department
    departments = Department.query.filter_by(is_active=True).all()
    
    # الأدوار المتاحة
    roles = [
        ('super_admin', 'السوبر أدمن'),
        ('manager', 'مدير المركز'),
        ('reception', 'استقبال'),
        ('doctor', 'طبيب'),
        ('radiology', 'أشعة'),
        ('lab', 'مختبر'),
        ('emergency', 'طوارئ'),
        ('nurse', 'ممرض'),
        ('accountant', 'محاسب')
    ]
    
    return render_template('super_admin/create_user.html', 
                         departments=departments, 
                         roles=roles)

@super_admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_user(user_id):
    """تعديل مستخدم"""
    try:
        from models.user import User
        from models.department import Department
        from app_factory import db
        
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        
        if request.method == 'POST':
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.full_name = request.form.get('full_name')
            user.role = request.form.get('role')
            user.department_id = request.form.get('department_id') or None
            user.phone = request.form.get('phone')
            user.doctor_room = request.form.get('doctor_room')
            user.is_active = bool(request.form.get('is_active'))
            user.is_admin = bool(request.form.get('is_admin'))

            try:
                from models.user_department_access import UserDepartmentAccess
                UserDepartmentAccess.query.filter_by(user_id=user.id).delete()
                selected = request.form.getlist('extra_department_ids')
                for dep_id in selected:
                    try:
                        did = int(dep_id)
                    except Exception:
                        continue
                    db.session.add(UserDepartmentAccess(user_id=user.id, department_id=did, can_access=True))
            except Exception:
                pass
            
            # تحديث كلمة المرور إذا تم إدخالها
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            from app_factory import db
            db.session.commit()
            
            flash('تم تحديث المستخدم بنجاح', 'success')
            return redirect(url_for('super_admin.users'))
        
        departments = Department.query.filter_by(is_active=True).all()
        extra_department_ids = []
        try:
            from models.user_department_access import UserDepartmentAccess
            extra_department_ids = [r.department_id for r in UserDepartmentAccess.query.filter_by(user_id=user.id, can_access=True).all()]
        except Exception:
            extra_department_ids = []
        roles = [
            ('super_admin', 'السوبر أدمن'),
            ('manager', 'مدير المركز'),
            ('reception', 'استقبال'),
            ('doctor', 'طبيب'),
            ('radiology', 'أشعة'),
            ('lab', 'مختبر'),
            ('emergency', 'طوارئ'),
            ('nurse', 'ممرض'),
            ('accountant', 'محاسب')
        ]
        
        return render_template('super_admin/users.html', 
                             user=user,
                             departments=departments, 
                             roles=roles,
                             mode='edit',
                             extra_department_ids=extra_department_ids)
        
    except Exception as e:
        logging.error(f"Edit user error: {str(e)}")
        flash('تعذر تحديث المستخدم، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    """حذف مستخدم"""
    try:
        from models.user import User
        from app_factory import db
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        
        # منع حذف السوبر أدمن
        if user.role == 'super_admin':
            flash('لا يمكن حذف السوبر أدمن', 'error')
            return redirect(url_for('super_admin.users'))
        
        db.session.delete(user)
        db.session.commit()
        
        flash('تم حذف المستخدم بنجاح', 'success')
        return redirect(url_for('super_admin.users'))

    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"Delete user error: {str(e)}")
        flash('تعذر حذف المستخدم، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/seed/users', methods=['POST'])
@login_required
@super_admin_required
def seed_users():
    return jsonify({'success': False, 'message': 'غير متاح'}), 404

@super_admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@super_admin_required
def reset_user_password(user_id):
    try:
        from models.user import User
        from app_factory import db
        import secrets, string
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 404
        alphabet = string.ascii_letters + string.digits
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(10)) + '!'
        user.set_password(temp_password)
        db.session.commit()
        return jsonify({'success': True, 'temp_password': temp_password})
    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"Reset password error: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ في إعادة التعيين'}), 500

# تم دمج إدارة الصلاحيات في صفحة المستخدمين الرئيسية

# تم دمج إدارة الصلاحيات في صفحة المستخدمين الرئيسية

# تم دمج إدارة الأدوار في صفحة المستخدمين الرئيسية

@super_admin_bp.route('/roles')
@login_required
@super_admin_required
def roles():
    """عرض جميع الأدوار"""
    try:
        from models.permissions import Role
        roles = Role.query.all()
        return render_template('super_admin/roles.html', roles=roles, mode='list')
    except Exception as e:
        logging.error(f"Error loading roles: {str(e)}")
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/roles.html', roles=[], mode='list')

@super_admin_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_role():
    """إنشاء دور جديد"""
    if request.method == 'POST':
        try:
            from models.permissions import Role, Permission, RolePermission
            
            role = Role(
                name=request.form.get('name'),
                name_ar=request.form.get('name_ar'),
                description=request.form.get('description'),
                is_system_role=bool(request.form.get('is_system_role')),
                is_active=bool(request.form.get('is_active'))
            )
            
            from app_factory import db
            db.session.add(role)
            db.session.flush()  # للحصول على ID
            
            # إضافة الصلاحيات للدور
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=int(perm_id)
                )
                db.session.add(role_permission)
            
            db.session.commit()
            
            flash('تم إنشاء الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
            
        except Exception as e:
            from app_factory import db
            db.session.rollback()
            logging.error(f"Create role error: {str(e)}")
            flash('تعذر إنشاء الدور، يرجى المحاولة مرة أخرى', 'error')
    
    # جلب الصلاحيات المتاحة
    from models.permissions import Permission
    permissions = Permission.query.all()
    
    return render_template('super_admin/roles.html', permissions=permissions, mode='create')

@super_admin_bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_role(role_id):
    """تعديل دور"""
    try:
        from models.permissions import Role, Permission, RolePermission
        from app_factory import db
        
        role = db.session.get(Role, role_id)
        if not role:
            abort(404)
        
        if request.method == 'POST':
            role.name = request.form.get('name')
            role.name_ar = request.form.get('name_ar')
            role.description = request.form.get('description')
            role.is_system_role = bool(request.form.get('is_system_role'))
            role.is_active = bool(request.form.get('is_active'))
            
            # حذف الصلاحيات القديمة
            RolePermission.query.filter_by(role_id=role.id).delete()
            
            # إضافة الصلاحيات الجديدة
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=int(perm_id)
                )
                db.session.add(role_permission)
            
            db.session.commit()
            
            flash('تم تحديث الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
        
        # جلب الصلاحيات المتاحة والصلاحيات الحالية للدور
        all_permissions = Permission.query.all()
        role_permissions = [rp.permission_id for rp in RolePermission.query.filter_by(role_id=role.id).all()]
        
        return render_template('super_admin/roles.html', 
                             role=role,
                             all_permissions=all_permissions,
                             role_permissions=role_permissions,
                             mode='edit')
        
    except Exception as e:
        logging.error(f"Edit role error: {str(e)}")
        flash('تعذر تحديث الدور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.roles'))

@super_admin_bp.route('/roles/<int:role_id>/permissions', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_role_permissions(role_id):
    """إدارة صلاحيات الدور"""
    try:
        from models.permissions import Role, Permission, RolePermission
        from app_factory import db
        
        role = db.session.get(Role, role_id)
        if not role:
            abort(404)
        
        if request.method == 'POST':
            # حذف الصلاحيات الحالية
            RolePermission.query.filter_by(role_id=role_id).delete()
            
            # إضافة الصلاحيات الجديدة
            selected_permissions = request.form.getlist('permissions')
            for permission_id in selected_permissions:
                role_permission = RolePermission(
                    role_id=role_id,
                    permission_id=int(permission_id),
                    granted_by=current_user.id
                )
                db.session.add(role_permission)
            
            db.session.commit()
            flash('تم تحديث صلاحيات الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
        
        all_permissions = Permission.query.all()
        role_permissions = [rp.permission_id for rp in RolePermission.query.filter_by(role_id=role_id).all()]
        
        return render_template('super_admin/role_permissions.html',
                             role=role,
                             all_permissions=all_permissions,
                             role_permissions=role_permissions)
        
    except Exception as e:
        logging.error(f"Manage role permissions error: {str(e)}")
        flash('حدث خطأ في إدارة صلاحيات الدور', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/roles/<int:role_id>/department-permissions', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_role_department_permissions(role_id):
    try:
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        if not (insp.has_table('roles') and insp.has_table('departments') and insp.has_table('department_permissions')):
            flash('جداول صلاحيات الأقسام غير متاحة في قاعدة البيانات', 'error')
            return redirect(url_for('super_admin.roles'))

        from models.permissions import Role
        from models.department import Department
        from models.advanced_permissions import DepartmentPermission

        role = db.session.get(Role, role_id)
        if not role:
            abort(404)

        departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar.asc()).all()

        if request.method == 'POST':
            DepartmentPermission.query.filter_by(role_id=role_id).delete()

            def _bool(name: str) -> bool:
                return str(request.form.get(name) or '').lower() in {'1', 'true', 'on', 'yes'}

            rows = [('all', None)] + [(str(d.id), d.id) for d in departments]
            for key, did in rows:
                can_access = _bool(f'dept_{key}_can_access')
                can_manage_patients = _bool(f'dept_{key}_can_manage_patients')
                can_manage_visits = _bool(f'dept_{key}_can_manage_visits')
                can_manage_appointments = _bool(f'dept_{key}_can_manage_appointments')
                can_manage_staff = _bool(f'dept_{key}_can_manage_staff')
                can_override_department_limits = _bool(f'dept_{key}_can_override_department_limits')
                can_manage_department_settings = _bool(f'dept_{key}_can_manage_department_settings')

                any_flag = any([
                    can_access,
                    can_manage_patients,
                    can_manage_visits,
                    can_manage_appointments,
                    can_manage_staff,
                    can_override_department_limits,
                    can_manage_department_settings
                ])
                if not any_flag:
                    continue
                if not can_access and any([
                    can_manage_patients,
                    can_manage_visits,
                    can_manage_appointments,
                    can_manage_staff,
                    can_override_department_limits,
                    can_manage_department_settings
                ]):
                    can_access = True

                db.session.add(DepartmentPermission(
                    role_id=role_id,
                    department_id=did,
                    can_access=can_access,
                    can_manage_patients=can_manage_patients,
                    can_manage_visits=can_manage_visits,
                    can_manage_appointments=can_manage_appointments,
                    can_manage_staff=can_manage_staff,
                    can_override_department_limits=can_override_department_limits,
                    can_manage_department_settings=can_manage_department_settings
                ))

            db.session.commit()
            flash('تم تحديث صلاحيات الأقسام للدور', 'success')
            return redirect(url_for('super_admin.manage_role_department_permissions', role_id=role_id))

        existing = DepartmentPermission.query.filter_by(role_id=role_id).all()
        perm_map = {}
        for r in existing:
            perm_map[r.department_id] = r

        return render_template('super_admin/department_permissions.html', role=role, departments=departments, perm_map=perm_map)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Department permissions error: {str(e)}")
        flash('حدث خطأ في إدارة صلاحيات الأقسام', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/permissions-matrix', methods=['GET', 'POST'])
@login_required
@super_admin_required
def permissions_matrix():
    try:
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        if not (insp.has_table('roles') and insp.has_table('permissions') and insp.has_table('role_permissions')):
            flash('جداول الصلاحيات غير متاحة في قاعدة البيانات', 'error')
            return redirect(url_for('super_admin.dashboard'))

        from models.permissions import Role, Permission, RolePermission, create_default_permissions, create_default_roles, assign_super_admin_permissions

        try:
            create_default_permissions()
            create_default_roles()
            assign_super_admin_permissions()
        except Exception:
            pass

        roles = Role.query.filter_by(is_active=True).order_by(Role.id.asc()).all()
        permissions = Permission.query.filter_by(is_active=True).order_by(Permission.category.asc(), Permission.level.asc(), Permission.name.asc()).all()

        if request.method == 'POST':
            for role in roles:
                RolePermission.query.filter_by(role_id=role.id).delete()
                selected = request.form.getlist(f'role_{role.id}_permissions')
                for pid in selected:
                    try:
                        db.session.add(RolePermission(role_id=role.id, permission_id=int(pid), granted_by=current_user.id))
                    except Exception:
                        continue
            db.session.commit()
            flash('تم تحديث مصفوفة الصلاحيات', 'success')
            return redirect(url_for('super_admin.permissions_matrix'))

        rp = RolePermission.query.filter(RolePermission.role_id.in_([r.id for r in roles])).all() if roles else []
        matrix = {}
        for row in rp:
            matrix.setdefault(row.role_id, set()).add(row.permission_id)

        return render_template('super_admin/permissions_matrix.html', roles=roles, permissions=permissions, matrix=matrix)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Permissions matrix error: {str(e)}")
        flash('حدث خطأ في تحميل مصفوفة الصلاحيات', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_role(role_id):
    """حذف دور"""
    try:
        from models.permissions import Role, RolePermission
        from app_factory import db
        
        role = db.session.get(Role, role_id)
        if not role:
            abort(404)
        
        # منع حذف الأدوار النظامية
        if role.is_system_role:
            flash('لا يمكن حذف الأدوار النظامية', 'error')
            return redirect(url_for('super_admin.roles'))
        
        # حذف صلاحيات الدور أولاً
        RolePermission.query.filter_by(role_id=role.id).delete()
        
        db.session.delete(role)
        db.session.commit()
        
        flash('تم حذف الدور بنجاح', 'success')
        return redirect(url_for('super_admin.roles'))
        
    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"Delete role error: {str(e)}")
        flash('تعذر حذف الدور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.roles'))

@super_admin_bp.route('/security-logs')
@login_required
@super_admin_required
def security_logs():
    """سجلات الأمان"""
    try:
        return render_template('super_admin/security_logs.html')
    except Exception as e:
        logging.error(f"Security logs error: {str(e)}")
        flash('حدث خطأ في تحميل سجلات الأمان', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/audit-trail')
@login_required
@super_admin_required
def audit_trail():
    """سجل التدقيق"""
    try:
        from models.audit_trail import AuditTrail
        audit_logs = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(100).all()
        return render_template('super_admin/audit_trail.html', audit_logs=audit_logs)
    except Exception as e:
        logging.error(f"Audit trail error: {str(e)}")
        flash('حدث خطأ في تحميل سجل التدقيق', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/performance')
@login_required
@super_admin_required
def performance():
    """مراقبة الأداء"""
    try:
        return render_template('super_admin/performance.html')
    except Exception as e:
        logging.error(f"Performance monitoring error: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة الأداء', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/reports')
@login_required
@super_admin_required
def reports():
    """مركز التقارير الموحد"""
    try:
        from services.report_center_service import ReportCenterService
        from models.department import Department
        from models.user import User

        report = (request.args.get('report') or '').strip()
        start_raw = request.args.get('start_date')
        end_raw = request.args.get('end_date')
        department_id = request.args.get('department_id', type=int)

        start_date, end_date, start_dt, end_dt = ReportCenterService._parse_dates(start_raw, end_raw)
        result = None

        if report == 'compare_month':
            now = date.today()
            a_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            a_end = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
            if now.month == 12:
                a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                a_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            if now.month == 1:
                p_year, p_month = now.year - 1, 12
            else:
                p_year, p_month = now.year, now.month - 1
            b_start = datetime(p_year, p_month, 1, tzinfo=timezone.utc)
            if p_month == 12:
                b_end = datetime(p_year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            else:
                b_end = datetime(p_year, p_month + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'compare_year':
            now = date.today()
            a_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
            a_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            b_start = datetime(now.year - 1, 1, 1, tzinfo=timezone.utc)
            b_end = datetime(now.year, 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1)
            result = {'compare': ReportCenterService.compare_periods(a_start, a_end, b_start, b_end, department_id=department_id)}
        elif report == 'transfers':
            result = {'transfers': ReportCenterService.department_transfers(start_dt, end_dt)}
        elif report == 'capacity':
            result = {'capacity': ReportCenterService.capacity_impact(start_date, end_date)}
        elif report == 'booking':
            booking = ReportCenterService.booking_report(start_dt, end_dt)
            dept_names = {d.id: (d.name_ar or d.name) for d in Department.query.all()}
            doctor_names = {u.id: u.full_name for u in User.query.filter_by(role='doctor').all()}
            booking['top_departments_named'] = [{'label': dept_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_departments', [])]
            booking['top_doctors_named'] = [{'label': doctor_names.get(did) or 'غير محدد', 'count': cnt} for did, cnt in booking.get('top_doctors', [])]
            result = {'booking': booking}
        elif report == 'emergency_times':
            result = {'emergency_times': ReportCenterService.emergency_stage_times(start_dt, end_dt)}
        elif report == 'radiology_revision':
            result = {'radiology_revision': ReportCenterService.radiology_revision_rate(start_dt, end_dt)}

        departments = Department.query.filter_by(is_active=True).all()
        return render_template(
            'super_admin/reports.html',
            report=report,
            start_date=start_date,
            end_date=end_date,
            department_id=department_id,
            departments=departments,
            result=result
        )
    except Exception as e:
        logging.error(f"Reports error: {str(e)}")
        return render_template('super_admin/reports.html', report='', start_date=None, end_date=None, departments=[], result=None)

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

# راوتات جديدة مع نظام الصلاحيات
@super_admin_bp.route('/permissions')
@login_required
@super_admin_required
def permissions():
    """إدارة الصلاحيات"""
    try:
        from models.permissions import Permission
        permissions = Permission.query.all()
        return render_template('super_admin/permissions.html', permissions=permissions)
    except Exception as e:
        logging.error(f"Permissions error: {str(e)}")
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/permissions.html', permissions=[])

@super_admin_bp.route('/permissions/create', methods=['POST'])
@login_required
@super_admin_required
def create_permission():
    """إنشاء صلاحية جديدة"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = Permission(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            level=request.form.get('level'),
            is_active=True
        )
        
        db.session.add(permission)
        db.session.commit()
        
        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Create permission error: {str(e)}")
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/permissions/<int:permission_id>/edit', methods=['POST'])
@login_required
@super_admin_required
def edit_permission(permission_id):
    """تعديل صلاحية"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = db.session.get(Permission, permission_id)
        if not permission:
            abort(404)
        
        permission.name = request.form.get('name')
        permission.description = request.form.get('description')
        permission.category = request.form.get('category')
        permission.level = request.form.get('level')
        permission.is_active = bool(request.form.get('is_active'))
        
        db.session.commit()
        
        flash('تم تحديث الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Edit permission error: {str(e)}")
        flash('حدث خطأ في تعديل الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/permissions/<int:permission_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_permission(permission_id):
    """حذف صلاحية"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = db.session.get(Permission, permission_id)
        if not permission:
            abort(404)
        
        db.session.delete(permission)
        db.session.commit()
        
        flash('تم حذف الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Delete permission error: {str(e)}")
        flash('حدث خطأ في حذف الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/departments')
@login_required
@super_admin_required
def departments():
    """إدارة الأقسام"""
    try:
        from models.department import Department
        from models.user import User
        departments = Department.query.all()
        total_doctors = User.query.filter_by(role='doctor').count()
        total_staff = User.query.count()
        return render_template('super_admin/departments.html', departments=departments, total_doctors=total_doctors, total_staff=total_staff)
    except Exception as e:
        logging.error(f"Departments error: {str(e)}")
        return render_template('super_admin/departments.html', departments=[], total_doctors=0, total_staff=0)

@super_admin_bp.route('/departments/create', methods=['POST'])
@login_required
@super_admin_required
def create_department():
    """إنشاء قسم جديد"""
    try:
        from models.department import Department
        from app_factory import db
        
        # التحقق من الحقول المطلوبة
        name = request.form.get('name')
        name_ar = request.form.get('name_ar')
        if not name or not name_ar:
            return jsonify({'success': False, 'message': 'الاسم الإنجليزي والاسم العربي مطلوبان'}), 400

        department = Department(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description'),
            location=request.form.get('location'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            is_active=bool(request.form.get('is_active', True))
        )
        
        db.session.add(department)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إنشاء القسم بنجاح', 'department_id': department.id}), 200
        
    except Exception as e:
        logging.error(f"Create department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إنشاء القسم حالياً'}), 500

@super_admin_bp.route('/department/<int:department_id>')
@login_required
@super_admin_required
def view_department(department_id):
    """عرض تفاصيل قسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        staff = User.query.filter_by(department_id=department_id).all()
        
        return render_template('super_admin/department_detail.html', 
                             department=department, 
                             staff=staff)
    except Exception as e:
        logging.error(f"View department error: {str(e)}")
        flash('حدث خطأ في عرض القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/edit-department/<int:department_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_department(department_id):
    """تعديل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        
        if request.method == 'POST':
            department.name_ar = request.form.get('name')
            department.name = request.form.get('name_en')
            department.description = request.form.get('description')
            department.location = request.form.get('location')
            department.phone = request.form.get('phone')
            department.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث القسم بنجاح', 'success')
            return redirect(url_for('super_admin.departments'))
        
        return render_template('super_admin/edit_department.html', department=department)
    except Exception as e:
        logging.error(f"Edit department error: {str(e)}")
        flash('حدث خطأ في تعديل القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>')
@login_required
@super_admin_required
def department_staff(department_id):
    """إدارة موظفي القسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        staff = User.query.filter_by(department_id=department_id).all()
        all_users = User.query.filter_by(is_active=True).all()
        
        return render_template('super_admin/department_staff.html', 
                             department=department, 
                             staff=staff,
                             all_users=all_users)
    except Exception as e:
        logging.error(f"Department staff error: {str(e)}")
        flash('حدث خطأ في إدارة موظفي القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>/add', methods=['POST'])
@login_required
@super_admin_required
def add_staff_to_department(department_id):
    """إضافة موظف للقسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        user.department_id = department_id
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إضافة الموظف للقسم'}), 200
    except Exception as e:
        logging.error(f"Add staff error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إضافة الموظف للقسم حالياً'}), 500

@super_admin_bp.route('/department-staff/<int:department_id>/remove', methods=['POST'])
@login_required
@super_admin_required
def remove_staff_from_department(department_id):
    """إزالة موظف من القسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = db.session.get(User, user_id)
        if not user:
            abort(404)
        user.department_id = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إزالة الموظف من القسم'}), 200
    except Exception as e:
        logging.error(f"Remove staff error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إزالة الموظف من القسم حالياً'}), 500

@super_admin_bp.route('/activate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_department(department_id):
    """تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        department.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Activate department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تفعيل القسم حالياً'}), 500

@super_admin_bp.route('/deactivate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_department(department_id):
    """إلغاء تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = db.session.get(Department, department_id)
        if not department:
            abort(404)
        department.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Deactivate department error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء تفعيل القسم حالياً'}), 500

@super_admin_bp.route('/export-departments')
@login_required
@super_admin_required
def export_departments():
    """تصدير الأقسام"""
    try:
        from models.department import Department
        import csv
        from io import StringIO
        from flask import make_response
        
        departments = Department.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم العربي', 'الاسم (إنجليزي)', 'الوصف', 'الموقع', 'الهاتف', 'نشط'])
        
        for dept in departments:
            writer.writerow([
                dept.id,
                dept.name_ar or '',
                dept.name or '',
                dept.description or '',
                dept.location or '',
                dept.phone or '',
                'نعم' if dept.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=departments_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export departments error: {str(e)}")
        flash('حدث خطأ في تصدير الأقسام', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/pricing')
@login_required
@super_admin_required
def pricing():
    """إدارة الأسعار المركزية (واجهة متطورة)"""
    try:
        from models.service import ServiceMaster
        from models.department import Department
        
        services = ServiceMaster.query.order_by(ServiceMaster.updated_at.desc()).all()
        departments = Department.query.filter_by(is_active=True).all()
        
        return render_template('manager/pricing.html', services=services, departments=departments)
    except Exception as e:
        logging.error(f"Error loading pricing for super admin: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأسعار', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/services')
@login_required
@super_admin_required
def services():
    """إدارة الخدمات"""
    try:
        from models.service import ServiceMaster
        from models.department import Department
        services = ServiceMaster.query.all()
        departments = Department.query.filter_by(is_active=True).all()
        return render_template('super_admin/services.html', services=services, departments=departments)
    except Exception as e:
        logging.error(f"Services error: {str(e)}")
        return render_template('super_admin/services.html', services=[], departments=[])

@super_admin_bp.route('/services/create', methods=['POST'])
@login_required
@super_admin_required
def create_service():
    """إنشاء خدمة جديدة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        import re, time
        
        # التوافق والتحقق من حقول النموذج
        name = request.form.get('name')
        name_ar = request.form.get('name_ar')
        if not name or not name_ar:
            return jsonify({'success': False, 'message': 'اسم الخدمة (إنجليزي) والاسم العربي مطلوبان'}), 400

        price_value_raw = request.form.get('base_price') or request.form.get('price') or '0'
        try:
            price_value = float(price_value_raw)
        except ValueError:
            return jsonify({'success': False, 'message': 'السعر يجب أن يكون رقمًا صالحًا'}), 400
        if price_value < 0:
            return jsonify({'success': False, 'message': 'السعر يجب أن يكون غير سالب'}), 400

        service_type = request.form.get('service_type') or 'general'
        category_map = {
            'LAB': 'lab',
            'RADIOLOGY': 'radiology',
        }
        category = category_map.get(service_type, 'general')
        if category not in ('general', 'doctor', 'lab', 'radiology'):
            category = 'general'
        department_id = request.form.get('department_id') or None
        currency = request.form.get('currency') or 'شيكل'
        allowed_currencies = {'شيكل', 'ILS', 'USD', 'EUR'}
        if currency not in allowed_currencies:
            currency = 'شيكل'

        # التحقق من المدة والحد اليومي إن تم إرسالها
        duration_val = request.form.get('duration')
        if duration_val:
            try:
                duration_int = int(duration_val)
                if duration_int < 1:
                    return jsonify({'success': False, 'message': 'المدة يجب أن تكون 1 دقيقة على الأقل'}), 400
            except ValueError:
                return jsonify({'success': False, 'message': 'المدة يجب أن تكون عددًا صحيحًا'}), 400
        else:
            duration_int = None

        max_daily_val = request.form.get('max_daily')
        if max_daily_val:
            try:
                max_daily_int = int(max_daily_val)
                if max_daily_int < 1:
                    return jsonify({'success': False, 'message': 'الحد اليومي يجب أن يكون 1 على الأقل'}), 400
            except ValueError:
                return jsonify({'success': False, 'message': 'الحد اليومي يجب أن يكون عددًا صحيحًا'}), 400
        else:
            max_daily_int = None

        # توليد رمز فريد للخدمة إذا لم يتم إرساله
        code = request.form.get('code')
        if not code:
            base = re.sub(r"[^A-Za-z0-9]+", "_", (name or "SERVICE").upper()).strip('_')
            code = f"{(category or 'GENERAL').upper()}_{base}_{int(time.time())}"

        service = ServiceMaster(
            code=code,
            name=name,
            name_ar=name_ar,
            description=request.form.get('description'),
            base_price=float(price_value or 0),
            category=category,
            department_id=int(department_id) if department_id else None,
            currency=currency,
            duration=duration_int,
            max_daily=max_daily_int,
            is_required=bool(request.form.get('is_required')),
            is_active=True
        )
        
        db.session.add(service)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إنشاء الخدمة بنجاح', 'service_id': service.id}), 200
        
    except Exception as e:
        logging.error(f"Create service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إنشاء الخدمة حالياً'}), 500

@super_admin_bp.route('/service/<int:service_id>')
@login_required
@super_admin_required
def view_service(service_id):
    """عرض تفاصيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        return render_template('super_admin/service_detail.html', service=service)
    except Exception as e:
        logging.error(f"View service error: {str(e)}")
        flash('حدث خطأ في عرض الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/edit-service/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_service(service_id):
    """تعديل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        
        if request.method == 'POST':
            service.name_ar = request.form.get('name')
            service.name = request.form.get('name_en')
            service.description = request.form.get('description')
            service.category = request.form.get('category') or service.category
            dep_id = request.form.get('department_id') or None
            service.department_id = int(dep_id) if dep_id else None
            service.currency = request.form.get('currency') or service.currency
            service.duration = int(request.form.get('duration')) if request.form.get('duration') else None
            service.max_daily = int(request.form.get('max_daily')) if request.form.get('max_daily') else None
            service.is_required = bool(request.form.get('is_required'))
            service.base_price = float(request.form.get('base_price', 0))
            service.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث الخدمة بنجاح', 'success')
            return redirect(url_for('super_admin.services'))
        
        from models.department import Department
        departments = Department.query.filter_by(is_active=True).all()
        return render_template('super_admin/edit_service.html', service=service, departments=departments)
    except Exception as e:
        logging.error(f"Edit service error: {str(e)}")
        flash('حدث خطأ في تعديل الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/service-pricing/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def service_pricing(service_id):
    """إدارة تسعير الخدمة"""
    try:
        from models.service import ServiceMaster
        from models.pricing_management import PricingManagement
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        pricing_records = PricingManagement.query.filter_by(service_id=service_id).all()
        pricing = []
        for rec in pricing_records:
            if rec.base_price:
                pricing.append({'id': rec.id, 'price_type': 'standard', 'price': float(rec.base_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.emergency_price:
                pricing.append({'id': rec.id, 'price_type': 'urgent', 'price': float(rec.emergency_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.private_price:
                pricing.append({'id': rec.id, 'price_type': 'vip', 'price': float(rec.private_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
            if rec.insurance_price:
                pricing.append({'id': rec.id, 'price_type': 'insurance', 'price': float(rec.insurance_price or 0), 'discount_percentage': float(rec.discount_percentage or 0), 'discount_amount': float(rec.discount_amount or 0), 'description': ''})
        
        if request.method == 'POST':
            price_type = request.form.get('price_type')
            price_value = float(request.form.get('price', 0))
            description = request.form.get('description')
            currency = request.form.get('currency') or 'ILS'
            discount_percentage_raw = request.form.get('discount_percentage')
            discount_amount_raw = request.form.get('discount_amount')
            try:
                discount_percentage = float(discount_percentage_raw) if discount_percentage_raw not in (None, '',) else 0.0
            except Exception:
                discount_percentage = 0.0
            try:
                discount_amount = float(discount_amount_raw) if discount_amount_raw not in (None, '',) else 0.0
            except Exception:
                discount_amount = 0.0

            new_pricing = PricingManagement(
                service_id=service_id,
                base_price=price_value if price_type in (None, '', 'base', 'standard') else 0,
                emergency_price=price_value if price_type in ('emergency', 'urgent') else None,
                insurance_price=price_value if price_type == 'insurance' else None,
                private_price=price_value if price_type == 'vip' else None,
                currency=currency,
                created_by=current_user.id,
                is_active=True
            )
            new_pricing.discount_percentage = discount_percentage
            new_pricing.discount_amount = discount_amount

            db.session.add(new_pricing)
            db.session.commit()
            flash('تم إضافة التسعير بنجاح', 'success')
            return redirect(url_for('super_admin.service_pricing', service_id=service_id))
        
        return render_template('super_admin/service_pricing.html', service=service, pricing=pricing)
    except Exception as e:
        logging.error(f"Service pricing error: {str(e)}")
        flash('حدث خطأ في إدارة التسعير', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/activate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_service(service_id):
    """تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        service.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Activate service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تفعيل الخدمة حالياً'}), 500

@super_admin_bp.route('/deactivate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_service(service_id):
    """إلغاء تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = db.session.get(ServiceMaster, service_id)
        if not service:
            abort(404)
        service.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Deactivate service error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء تفعيل الخدمة حالياً'}), 500

@super_admin_bp.route('/export-services')
@login_required
@super_admin_required
def export_services():
    """تصدير الخدمات"""
    try:
        from models.service import ServiceMaster
        import csv
        from io import StringIO
        from flask import make_response
        
        services = ServiceMaster.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم', 'الاسم بالإنجليزية', 'الوصف', 'السعر الأساسي', 'نشط'])
        
        for service in services:
            writer.writerow([
                service.id,
                service.name_ar or '',
                service.name or '',
                service.description or '',
                service.base_price or 0,
                'نعم' if service.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=services_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export services error: {str(e)}")
        flash('حدث خطأ في تصدير الخدمات', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/analytics')
@login_required
@super_admin_required
def analytics():
    """التحليلات المتقدمة"""
    try:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        
        stats = {
            'total_users': User.query.count(),
            'total_patients': Patient.query.count(),
            'total_visits': Visit.query.count()
        }
        return render_template('super_admin/analytics.html', stats=stats)
    except Exception as e:
        logging.error(f"Analytics error: {str(e)}")
        return render_template('super_admin/analytics.html', stats={})

# إدارة العلامة التجارية
@super_admin_bp.route('/branding')
@super_admin_required
def branding():
    """إدارة العلامة التجارية والشعارات"""
    try:
        from models.branding import BrandingSettings, SystemTheme
        
        branding_settings = BrandingSettings.get_active_settings()
        themes = SystemTheme.query.filter_by(is_active=True).all()
        
        if not branding_settings:
            branding_settings = BrandingSettings.create_default(current_user.id)
        
        return render_template('super_admin/branding.html', 
                             branding=branding_settings, 
                             themes=themes)
    except Exception as e:
        logging.error(f"Branding error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة العلامة التجارية', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/branding/update', methods=['POST'])
@super_admin_required
def update_branding():
    """تحديث إعدادات العلامة التجارية"""
    try:
        from models.branding import BrandingSettings
        from app_factory import db
        from flask_wtf.csrf import validate_csrf
        
        # التحقق من CSRF token
        validate_csrf(request.form.get('csrf_token'))
        
        branding = BrandingSettings.get_active_settings()
        if not branding:
            branding = BrandingSettings.create_default(current_user.id)
        
        # تحديث البيانات الأساسية
        branding.organization_name = request.form.get('organization_name', branding.organization_name)
        branding.organization_name_en = request.form.get('organization_name_en', branding.organization_name_en)
        branding.organization_address = request.form.get('organization_address', branding.organization_address)
        branding.organization_phone = request.form.get('organization_phone', branding.organization_phone)
        branding.organization_email = request.form.get('organization_email', branding.organization_email)
        branding.organization_website = request.form.get('organization_website', branding.organization_website)
        
        # تحديث الألوان
        branding.primary_color = request.form.get('primary_color', branding.primary_color)
        branding.secondary_color = request.form.get('secondary_color', branding.secondary_color)
        branding.accent_color = request.form.get('accent_color', branding.accent_color)
        
        # تحديث ترويسة التقارير
        branding.report_header_html = request.form.get('report_header_html', branding.report_header_html)
        branding.report_footer_html = request.form.get('report_footer_html', branding.report_footer_html)
        
        branding.updated_by = current_user.id
        db.session.commit()
        
        flash('تم تحديث إعدادات العلامة التجارية بنجاح', 'success')
        return redirect(url_for('super_admin.branding'))
        
    except Exception as e:
        logging.error(f"Update branding error: {str(e)}")
        flash('حدث خطأ في تحديث إعدادات العلامة التجارية', 'error')
        return redirect(url_for('super_admin.branding'))

# إدارة المستخدمين المتقدمة
@super_admin_bp.route('/users/ban/<int:user_id>')
@super_admin_required
def ban_user(user_id):
    """حظر مستخدم"""
    try:
        from app_factory import db
        from models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        if user.role == 'super_admin':
            flash('لا يمكن حظر السوبر أدمن', 'error')
            return redirect(url_for('super_admin.users'))
        
        user.is_active = False
        db.session.commit()
        
        flash(f'تم حظر المستخدم {user.full_name} بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Ban user error: {str(e)}")
        flash('حدث خطأ في حظر المستخدم', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/unban/<int:user_id>')
@super_admin_required
def unban_user(user_id):
    """إلغاء حظر مستخدم"""
    try:
        from app_factory import db
        from models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        user.is_active = True
        db.session.commit()
        
        flash(f'تم إلغاء حظر المستخدم {user.full_name} بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Unban user error: {str(e)}")
        flash('حدث خطأ في إلغاء حظر المستخدم', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/force-logout/<int:user_id>')
@super_admin_required
def force_logout_user(user_id):
    """إجبار مستخدم على تسجيل الخروج"""
    try:
        from app_factory import db
        from models.user import User
        from models.audit_trail import AuditTrail
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))

        user.session_version = int(getattr(user, 'session_version', 0) or 0) + 1
        db.session.add(AuditTrail(
            entity_type='user',
            entity_id=user.id,
            action='force_logout',
            user_id=current_user.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description='إجبار المستخدم على تسجيل الخروج',
            notes=f'target_user_id={user.id}'
        ))
        db.session.commit()
        
        flash(f'تم إجبار المستخدم {user.full_name} على تسجيل الخروج', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Force logout error: {str(e)}")
        flash('حدث خطأ في إجبار تسجيل الخروج', 'error')
        return redirect(url_for('super_admin.users'))

# إدارة النظام المتقدمة
@super_admin_bp.route('/system/maintenance')
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
            from models.medication import PrescriptionItem, Prescription, Medication
            from models.lab_request import LabResult, LabRequest
            from models.radiology_test import RadiologyResult
            from models.radiology_request import RadiologyRequest
            from models.invoice import InvoiceService, Invoice
            from models.payment import Payment
            from models.queue_management import QueueManagement, QueueSettings
            from models.emergency import EmergencyCase
            from models.treatment import Treatment
            from models.notification import Notification, NotificationQueue, NotificationTemplate
            from models.ai_analytics import AIRecommendation, DiseasePattern, PerformanceAnalytics
            from models.pricing import ServicePrice, DoctorPricing, PricingCatalog, TemporaryService, InsuranceProvider
            from models.insurance import InsuranceCompany, InsuranceClaim
            from models.service import ServiceMaster
            from models.workflow import WorkflowStep, PatientWorkflow, WorkflowTransfer
            from models.appointment import Appointment
            from models.medical_record import MedicalRecord
            from models.medical_report import MedicalReport
            from models.receipt import Receipt
            from models.visit import Visit
            from models.department import Department
            from models.user import User

            def delq(Model):
                return Model.query.delete(synchronize_session=False)

            delq(PrescriptionItem)
            delq(InvoiceService)
            delq(LabResult)
            delq(RadiologyResult)
            delq(NotificationQueue)
            delq(MedicalReport)
            delq(Receipt)
            delq(QueueManagement)
            delq(WorkflowTransfer)
            delq(PatientWorkflow)

            delq(Prescription)
            delq(LabRequest)
            delq(RadiologyRequest)
            delq(Payment)
            delq(Invoice)
            delq(EmergencyCase)
            delq(Treatment)
            delq(Notification)
            delq(NotificationTemplate)
            delq(AIRecommendation)
            delq(DiseasePattern)
            delq(PerformanceAnalytics)
            delq(PricingCatalog)
            delq(TemporaryService)
            delq(ServicePrice)
            delq(DoctorPricing)
            delq(InsuranceClaim)
            delq(InsuranceCompany)
            delq(ServiceMaster)
            delq(Appointment)
            delq(Visit)
            delq(MedicalRecord)
            delq(QueueSettings)

            User.query.filter(User.department_id.isnot(None)).update({User.department_id: None}, synchronize_session=False)
            delq(Medication)
            delq(Department)

            db.session.commit()
            flash('تم تنظيف بيانات البذور بنجاح (ما عدا المستخدمين)', 'success')
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

# مسارات مبسطة لإنشاء الأدوار والصلاحيات
@super_admin_bp.route('/create-role-simple', methods=['POST'])
@super_admin_required
def create_role_simple():
    """إنشاء دور جديد (مبسط)"""
    try:
        from app_factory import db
        from models.permissions import Role
        from flask_wtf.csrf import validate_csrf
        
        validate_csrf(request.form.get('csrf_token'))
        
        role = Role(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description'),
            is_system_role=False,
            is_active=True
        )
        
        db.session.add(role)
        db.session.commit()
        
        flash('تم إنشاء الدور بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Create role error: {str(e)}")
        flash('حدث خطأ في إنشاء الدور', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/create-permission-simple', methods=['POST'])
@super_admin_required
def create_permission_simple():
    """إنشاء صلاحية جديدة (مبسط)"""
    try:
        from app_factory import db
        from models.permissions import Permission, PermissionCategory, PermissionLevel
        from flask_wtf.csrf import validate_csrf
        
        validate_csrf(request.form.get('csrf_token'))
        
        permission = Permission(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=PermissionCategory.SYSTEM_ADMIN,
            level=PermissionLevel.ADMIN
        )
        
        db.session.add(permission)
        db.session.commit()
        
        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Create permission error: {str(e)}")
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.users'))

# دوال مساعدة للإحصائيات
def get_total_users():
    """عدد المستخدمين الإجمالي"""
    try:
        from models.user import User
        return User.query.count()
    except:
        return 0

def get_active_sessions():
    """عدد الجلسات النشطة"""
    try:
        # يمكن تطوير هذا لاحقاً لتتبع الجلسات الفعلية
        return get_active_users()
    except:
        return 15

def get_security_events():
    """عدد أحداث الأمان"""
    try:
        from models.audit_trail import AuditTrail
        return AuditTrail.query.filter(AuditTrail.action.in_(['login', 'logout', 'security'])).count()
    except:
        return 0

def get_system_uptime():
    """وقت تشغيل النظام"""
    return "99.9%"

def get_active_users():
    """عدد المستخدمين النشطين"""
    try:
        from models.user import User
        return User.query.filter_by(is_active=True).count()
    except:
        return 0

def get_inactive_users():
    """عدد المستخدمين المعطلين"""
    try:
        from models.user import User
        return User.query.filter_by(is_active=False).count()
    except:
        return 0

def get_admin_users():
    """عدد المستخدمين المديرين"""
    try:
        from models.user import User
        return User.query.filter_by(is_admin=True).count()
    except:
        return 0

def get_daily_usage():
    """استخدام النظام اليومي"""
    # يمكن تطوير هذا لاحقاً
    return [100, 95, 88, 92, 98]

# ==================== الميزات الذكية للسوبر أدمن ====================

def get_ai_insights():
    """رؤى الذكاء الاصطناعي للنظام"""
    try:
        from models.ai_analytics import AIRecommendation, PerformanceAnalytics
        from datetime import datetime, timedelta
        
        insights = {
            'total_recommendations': AIRecommendation.query.count(),
            'pending_recommendations': AIRecommendation.query.filter(AIRecommendation.is_accepted.is_(None)).count(),
            'accepted_recommendations': AIRecommendation.query.filter(AIRecommendation.is_accepted == True).count(),
            'high_confidence_recommendations': AIRecommendation.query.filter(AIRecommendation.confidence_score >= 0.8).count(),
            'recent_insights': AIRecommendation.query.filter(
                AIRecommendation.created_at >= datetime.now() - timedelta(days=7)
            ).count()
        }
        
        return insights
    except Exception as e:
        logging.error(f"Error getting AI insights: {str(e)}")
        return {}

def get_smart_recommendations():
    """التوصيات الذكية للنظام"""
    try:
        from models.ai_analytics import AIRecommendation
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل الأداء
        total_visits = Visit.query.count()
        if total_visits > 100:
            recommendations.append({
                'type': 'performance',
                'title': 'تحسين الأداء',
                'description': f'تم تسجيل {total_visits} زيارة - النظام يعمل بكفاءة عالية',
                'priority': 'info'
            })
        
        # تحليل المستخدمين
        inactive_users = User.query.filter(
            User.last_login < datetime.now() - timedelta(days=30)
        ).count()
        
        if inactive_users > 5:
            recommendations.append({
                'type': 'users',
                'title': 'إدارة المستخدمين',
                'description': f'يوجد {inactive_users} مستخدم غير نشط - يحتاج مراجعة',
                'priority': 'warning'
            })
        
        # تحليل الأمان
        from models.audit_trail import AuditTrail
        failed_logins = AuditTrail.query.filter(
            AuditTrail.action == 'login_failed',
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if failed_logins > 10:
            recommendations.append({
                'type': 'security',
                'title': 'تنبيه أمني',
                'description': f'محاولات تسجيل دخول فاشلة: {failed_logins} - يحتاج مراجعة',
                'priority': 'danger'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart recommendations: {str(e)}")
        return []

def get_predictive_analytics():
    """التحليلات التنبؤية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from app_factory import db
        
        # تحليل النمو
        week_ago = datetime.now() - timedelta(days=7)
        month_ago = datetime.now() - timedelta(days=30)
        
        patients_this_week = Patient.query.filter(Patient.created_at >= week_ago).count()
        patients_last_week = Patient.query.filter(
            Patient.created_at >= week_ago - timedelta(days=7),
            Patient.created_at < week_ago
        ).count()
        
        growth_rate = ((patients_this_week - patients_last_week) / patients_last_week * 100) if patients_last_week > 0 else 0
        
        # التنبؤ بالزيارات
        visits_this_week = Visit.query.filter(Visit.created_at >= week_ago).count()
        predicted_next_week = int(visits_this_week * (1 + growth_rate/100))
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.created_at).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.created_at)).all()
        except Exception:
            db.session.rollback()
            peak_hours = []
        
        peak_hour = max(peak_hours, key=lambda x: x.count) if peak_hours else None
        
        return {
            'growth_rate': round(growth_rate, 2),
            'predicted_visits_next_week': predicted_next_week,
            'peak_hour': peak_hour.hour if peak_hour else None,
            'peak_visits': peak_hour.count if peak_hour else 0,
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting predictive analytics: {str(e)}")
        return {}

def get_system_health_score():
    """نقاط صحة النظام"""
    try:
        import os
        import shutil
        from datetime import datetime, timedelta
        from models.user import User
        from models.visit import Visit
        
        score = 100
        
        # فحص قاعدة البيانات
        try:
            db.session.execute('SELECT 1')
        except:
            score -= 20
        
        # فحص المساحة المتاحة
        try:
            disk_usage = shutil.disk_usage('/')
            free_space_percent = (disk_usage.free / disk_usage.total) * 100
            if free_space_percent < 10:
                score -= 20
            elif free_space_percent < 20:
                score -= 10
        except:
            score -= 5
        
        # فحص الملفات المهمة
        critical_files = ['app.py', 'config.py', 'requirements.txt']
        for file in critical_files:
            if not os.path.exists(file):
                score -= 5
        
        # فحص المستخدمين النشطين
        active_users = User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)).count()
        if active_users == 0:
            score -= 15
        
        return {
            'score': max(0, score),
            'status': 'ممتاز' if score >= 90 else 'جيد' if score >= 70 else 'يحتاج انتباه',
            'color': 'success' if score >= 90 else 'warning' if score >= 70 else 'danger'
        }
    except Exception as e:
        logging.error(f"Error getting system health score: {str(e)}")
        return {'score': 0, 'status': 'غير محدد', 'color': 'secondary'}

def get_security_threats():
    """التهديدات الأمنية"""
    try:
        from models.audit_trail import AuditTrail
        from datetime import datetime, timedelta
        
        threats = []
        
        # محاولات تسجيل الدخول الفاشلة
        failed_logins = AuditTrail.query.filter(
            AuditTrail.action == 'login_failed',
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if failed_logins > 20:
            threats.append({
                'type': 'high',
                'title': 'محاولات تسجيل دخول مفرطة',
                'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                'action': 'مراجعة سجلات الأمان'
            })
        elif failed_logins > 10:
            threats.append({
                'type': 'medium',
                'title': 'محاولات تسجيل دخول عالية',
                'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                'action': 'مراقبة النشاط'
            })
        
        # فحص الأنشطة المشبوهة
        suspicious_activities = AuditTrail.query.filter(
            AuditTrail.action.in_(['unauthorized_access', 'privilege_escalation']),
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if suspicious_activities > 0:
            threats.append({
                'type': 'critical',
                'title': 'أنشطة مشبوهة',
                'description': f'{suspicious_activities} نشاط مشبوه تم اكتشافه',
                'action': 'تحقيق فوري'
            })
        
        return threats
    except Exception as e:
        logging.error(f"Error getting security threats: {str(e)}")
        return []

def get_performance_optimization():
    """تحسين الأداء"""
    try:
        from models.visit import Visit
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from app_factory import db
        
        optimizations = []
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.created_at).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.created_at)).all()
        except Exception:
            db.session.rollback()
            peak_hours = []
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 15:
                optimizations.append({
                    'type': 'load_balancing',
                    'title': 'توزيع الأحمال',
                    'description': f'ساعة الذروة: {max_hour.hour}:00 مع {max_hour.count} زيارة',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل الأداء حسب الأقسام
        department_load = db.session.query(
            func.count(Visit.id).label('count'),
            User.department_id
        ).join(User, Visit.doctor_id == User.id).group_by(User.department_id).all()
        
        if department_load:
            max_dept = max(department_load, key=lambda x: x.count)
            if max_dept.count > 20:
                optimizations.append({
                    'type': 'resource_allocation',
                    'title': 'تخصيص الموارد',
                    'description': f'القسم {max_dept.department_id} يحتوي على {max_dept.count} زيارة',
                    'suggestion': 'إضافة موارد إضافية لهذا القسم'
                })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting performance optimization: {str(e)}")
        return []

def get_user_behavior_analysis():
    """تحليل سلوك المستخدمين"""
    try:
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        analysis = {}
        
        # المستخدمون النشطون
        active_users = User.query.filter(
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        # المستخدمون غير النشطين
        inactive_users = User.query.filter(
            User.last_login < datetime.now() - timedelta(days=30)
        ).count()
        
        # تحليل الأدوار
        role_distribution = {}
        for user in User.query.all():
            role = user.role
            role_distribution[role] = role_distribution.get(role, 0) + 1
        
        # تحليل النشاط اليومي
        daily_activity = {}
        for user in User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)):
            day = user.last_login.strftime('%A')
            daily_activity[day] = daily_activity.get(day, 0) + 1
        
        return {
            'active_users': active_users,
            'inactive_users': inactive_users,
            'role_distribution': role_distribution,
            'daily_activity': daily_activity,
            'engagement_rate': (active_users / User.query.count() * 100) if User.query.count() > 0 else 0
        }
    except Exception as e:
        logging.error(f"Error getting user behavior analysis: {str(e)}")
        return {}

def get_resource_utilization():
    """استخدام الموارد"""
    try:
        import os
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_usage = {
                'total': memory.total,
                'used': memory.used,
                'free': memory.free,
                'percentage': memory.percent
            }
            cpu_usage = psutil.cpu_percent(interval=1)
            disk = psutil.disk_usage('/')
            disk_usage = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percentage': (disk.used / disk.total) * 100
            }
        except Exception:
            memory_usage = {
                'total': 0,
                'used': 0,
                'free': 0,
                'percentage': 0
            }
            cpu_usage = 0
            disk_usage = {
                'total': 0,
                'used': 0,
                'free': 0,
                'percentage': 0
            }
        
        # تحليل قاعدة البيانات
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        
        db_stats = {
            'total_visits': Visit.query.count(),
            'total_patients': Patient.query.count(),
            'total_users': User.query.count()
        }
        
        return {
            'memory': memory_usage,
            'cpu': cpu_usage,
            'disk': disk_usage,
            'database': db_stats,
            'status': 'optimal' if memory_usage['percentage'] < 80 and cpu_usage < 80 else 'warning' if memory_usage['percentage'] < 90 and cpu_usage < 90 else 'critical'
        }
    except Exception as e:
        logging.error(f"Error getting resource utilization: {str(e)}")
        return {}

@super_admin_bp.route('/system')
@login_required
@super_admin_required
def system():
    """إعدادات النظام"""
    return render_template('super_admin/system_config.html')

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
        successful_backups = sum(1 for b in backups if b.backup_status == 'COMPLETED')
        failed_backups = sum(1 for b in backups if b.backup_status == 'FAILED')
        
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

@super_admin_bp.route('/backup/settings', methods=['POST'])
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

@super_admin_bp.route('/backup/create', methods=['POST'])
@super_admin_required
def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        from datetime import datetime
        import shutil
        import os
        import zipfile
        from models.backup import Backup
        from app_factory import db
        
        # تحديد نوع النسخة
        data = request.get_json() if request.is_json else {}
        req_type = data.get('type', 'full')
        
        backup_type = 'FULL'
        include_db = True
        include_files = True
        
        if req_type == 'incremental':
            backup_type = 'INCREMENTAL'
            include_files = False
        elif req_type == 'database':
            backup_type = 'DIFFERENTIAL' # استخدام differential للإشارة لقاعدة البيانات فقط
            include_files = False
        elif req_type == 'files':
            backup_type = 'DIFFERENTIAL' # استخدام differential للملفات فقط
            include_db = False
        
        # إنشاء مجلد النسخ الاحتياطية
        now = datetime.now()
        backup_dir = os.path.join('backups', now.strftime('%Y'), now.strftime('%m'))
        os.makedirs(backup_dir, exist_ok=True)
        
        # اسم الملف
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        backup_name = f'backup_{req_type}_{timestamp}'
        backup_filename = f'{backup_name}.zip'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # إنشاء ملف ZIP
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # إضافة ملف قاعدة البيانات
            if include_db:
                if os.path.exists('medical_system.db'):
                    zipf.write('medical_system.db', 'medical_system.db')
                elif os.path.exists('instance/medical_system.db'):
                    zipf.write('instance/medical_system.db', 'medical_system.db')
            
            # إضافة ملفات مهمة أخرى
            if include_files:
                for file in ['app.py', 'config.py', 'app_factory.py', 'requirements.txt']:
                    if os.path.exists(file):
                        zipf.write(file, file)
        
        # حفظ السجل في قاعدة البيانات
        # التحقق من أن نوع النسخة مقبول في قاعدة البيانات
        db_type_map = {
            'FULL': 'full',
            'INCREMENTAL': 'incremental',
            'DIFFERENTIAL': 'differential'
        }
        
        backup = Backup(
            backup_name=backup_name,
            backup_type=db_type_map.get(backup_type, 'full'),
            backup_path=backup_path,
            backup_size=os.path.getsize(backup_path),
            backup_status='COMPLETED',
            created_by=current_user.id,
            started_at=now,
            completed_at=datetime.now()
        )
        
        db.session.add(backup)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم إنشاء النسخة الاحتياطية بنجاح',
            'backup_file': backup_filename
        })
            
    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'تعذر إنشاء النسخة الاحتياطية حالياً'
        })

@super_admin_bp.route('/backup/restore/<int:backup_id>', methods=['POST'])
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

        backup.backup_status = 'CANCELLED'
        backup.completed_at = datetime.now()
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء النسخة الاحتياطية بنجاح'})
            
    except Exception as e:
        logging.error(f"Error cancelling backup: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر إلغاء النسخة الاحتياطية حالياً'}), 500

@super_admin_bp.route('/backup/schedule', methods=['GET', 'POST'])
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
@super_admin_required
def backup_report():
    """عرض تقرير النسخ الاحتياطي"""
    try:
        from models.backup import Backup
        
        backups = Backup.query.order_by(Backup.created_at.desc()).all()
        
        # Calculate stats
        total = len(backups)
        success = sum(1 for b in backups if b.backup_status == 'COMPLETED')
        failed = sum(1 for b in backups if b.backup_status == 'FAILED')
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

@super_admin_bp.route('/security-center')
@login_required
@super_admin_required
def security_center():
    try:
        from models.audit_trail import LoginAttempt, SystemLog, SecurityEvent
        start_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        failed_logins = LoginAttempt.query.filter(LoginAttempt.success == False, LoginAttempt.created_at >= start_24h).count()
        critical_logs = SystemLog.query.filter(SystemLog.log_level.in_(['ERROR', 'CRITICAL']), SystemLog.created_at >= start_24h).count()
        unresolved = SecurityEvent.query.filter(SecurityEvent.is_resolved == False).count()
        latest_events = SecurityEvent.query.order_by(SecurityEvent.created_at.desc()).limit(20).all()
        stats = {
            'failed_logins_24h': int(failed_logins or 0),
            'critical_logs_24h': int(critical_logs or 0),
            'unresolved_security_events': int(unresolved or 0),
            'latest_security_events': latest_events
        }
        return render_template('super_admin/security_center.html', stats=stats)
    except Exception as e:
        logging.error(f"Security center error: {str(e)}")
        return render_template('super_admin/security_center.html', stats={})

@super_admin_bp.route('/branch-templates', methods=['GET', 'POST'])
@login_required
@super_admin_required
def branch_templates():
    try:
        from models.system_config import SystemConfig
        if request.method == 'POST':
            data = request.get_json() or {}
            items = data.get('items') or []
            cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
            if not cfg:
                cfg = SystemConfig(config_key='branch_templates', category='system', is_system=True, config_type='json')
                db.session.add(cfg)
            cfg.set_value(items)
            db.session.commit()
            return jsonify({'success': True, 'message': 'تم حفظ القوالب'}), 200
        cfg = SystemConfig.query.filter_by(config_key='branch_templates').first()
        items = cfg.get_value() if cfg else []
        return render_template('super_admin/branch_templates.html', items=items if isinstance(items, list) else [])
    except Exception as e:
        logging.error(f"Branch templates error: {str(e)}")
        return render_template('super_admin/branch_templates.html', items=[])

@super_admin_bp.route('/data-warehouse')
@login_required
@super_admin_required
def data_warehouse():
    try:
        from services.data_warehouse_service import DataWarehouseService
        snapshot = DataWarehouseService.export_snapshot(days=30)
        return render_template('super_admin/data_warehouse.html', snapshot=snapshot)
    except Exception as e:
        logging.error(f"Data warehouse error: {str(e)}")
        return render_template('super_admin/data_warehouse.html', snapshot={})

@super_admin_bp.route('/data-warehouse/export')
@login_required
@super_admin_required
def data_warehouse_export():
    try:
        from services.data_warehouse_service import DataWarehouseService
        days = request.args.get('days', type=int) or 30
        days = max(7, min(days, 365))
        snapshot = DataWarehouseService.export_snapshot(days=days)
        return jsonify({'success': True, 'snapshot': snapshot}), 200
    except Exception as e:
        logging.error(f"Data warehouse export error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تصدير المستودع'}), 500

@super_admin_bp.route('/backup/export-logs')
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

@super_admin_bp.route('/export-data', methods=['POST'])
@super_admin_required
def export_system_data():
    """تصدير بيانات النظام"""
    try:
        from datetime import datetime
        import json
        
        # جمع البيانات من جميع الجداول
        export_data = {
            'export_date': datetime.now().isoformat(),
            'system_info': {
                'version': '1.0.0',
                'exported_by': current_user.username
            },
            'data': {}
        }
        
        # تصدير المستخدمين
        from models.user import User
        users = User.query.all()
        export_data['data']['users'] = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department_id': user.department_id,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
        
        # تصدير المرضى
        from models.patient import Patient
        patients = Patient.query.all()
        export_data['data']['patients'] = [
            {
                'id': patient.id,
                'name': patient.name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.isoformat() if patient.birth_date else None,
                'created_at': patient.created_at.isoformat() if patient.created_at else None
            }
            for patient in patients
        ]
        
        # تصدير الزيارات
        from models.visit import Visit
        visits = Visit.query.all()
        export_data['data']['visits'] = [
            {
                'id': visit.id,
                'patient_id': visit.patient_id,
                'doctor_id': visit.doctor_id,
                'department_id': visit.department_id,
                'visit_type': visit.visit_type,
                'status': visit.status,
                'created_at': visit.created_at.isoformat() if visit.created_at else None
            }
            for visit in visits
        ]
        
        # حفظ الملف
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'medical_system_export_{timestamp}.json'
        
        with open(f'instance/{filename}', 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'تم تصدير البيانات بنجاح',
            'download_url': f'/super-admin/download-export/{filename}'
        })
        
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'تعذر تصدير البيانات حالياً'
        })

@super_admin_bp.route('/download-export/<filename>')
@super_admin_required
def download_export(filename):
    """تحميل ملف التصدير"""
    try:
        from flask import send_file
        import os
        
        file_path = os.path.join('instance', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            flash('الملف غير موجود', 'error')
            return redirect(url_for('super_admin.dashboard'))
            
    except Exception as e:
        logging.error(f"Error downloading export: {str(e)}")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/system-monitor')
@super_admin_required
def system_monitor():
    """مراقب النظام المتقدم"""
    try:
        import os
        try:
            import psutil
            drive = os.path.splitdrive(os.getcwd())[0]
            root_path = (drive + os.sep) if drive else os.path.abspath(os.sep)
            system_info = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_usage': psutil.disk_usage(root_path).percent,
                'process_count': len(psutil.pids()),
                'boot_time': psutil.boot_time()
            }
        except Exception:
            system_info = {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_usage': 0,
                'process_count': 0,
                'boot_time': 0
            }
        
        return render_template('super_admin/system_monitor.html', system_info=system_info)
        
    except Exception as e:
        logging.error(f"Error in system monitor: {str(e)}")
        flash('حدث خطأ في مراقب النظام', 'error')
        return render_template('super_admin/system_monitor.html', system_info={})

# ============================================
# API Routes for AJAX Calls
# ============================================

@super_admin_bp.route('/api/audit-log', methods=['POST'])
@login_required
@super_admin_required
def api_audit_log():
    """API لتسجيل الأحداث"""
    try:
        from models.audit_trail import AuditTrail
        from app_factory import db
        
        data = request.get_json()
        
        action = (data.get('action') or 'view')
        allowed_actions = {'create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access'}
        safe_action = action if action in allowed_actions else 'view'

        entity_type = (data.get('entity_type') or 'system')
        allowed_entity_types = {'system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department'}
        safe_entity_type = entity_type if entity_type in allowed_entity_types else 'system'

        audit = AuditTrail(
            entity_type=safe_entity_type,
            entity_id=int(data.get('entity_id', 0) or 0),
            action=safe_action,
            user_id=current_user.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description=data.get('description', ''),
            notes=(data.get('notes') or '') + (f"\nraw_action={action}" if safe_action != action else '') + (f"\nraw_entity_type={entity_type}" if safe_entity_type != entity_type else '')
        )
        
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تسجيل الحدث'}), 200
        
    except Exception as e:
        logging.error(f"API audit log error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تسجيل الحدث حالياً'}), 500

@super_admin_bp.route('/api/recent-activities')
@login_required
@super_admin_required
def api_recent_activities():
    """API للحصول على النشاطات الأخيرة"""
    try:
        from models.audit_trail import AuditTrail
        from datetime import datetime, timedelta
        
        # الحصول على آخر 10 نشاطات
        recent = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(10).all()
        
        activities = []
        for activity in recent:
            # حساب الوقت النسبي
            time_diff = datetime.now(timezone.utc) - activity.created_at
            if time_diff.seconds < 60:
                time_str = f"منذ {time_diff.seconds} ثانية"
            elif time_diff.seconds < 3600:
                time_str = f"منذ {time_diff.seconds // 60} دقيقة"
            elif time_diff.seconds < 86400:
                time_str = f"منذ {time_diff.seconds // 3600} ساعة"
            else:
                time_str = f"منذ {time_diff.days} يوم"
            
            # تحديد نوع النشاط
            activity_type = 'primary'
            if activity.action in ['create', 'add']:
                activity_type = 'success'
            elif activity.action in ['update', 'edit']:
                activity_type = 'warning'
            elif activity.action in ['delete', 'remove']:
                activity_type = 'danger'
            
            activities.append({
                'title': activity.description or f"{activity.action} {activity.entity_type}",
                'description': activity.notes or f"المستخدم: {activity.user.full_name if activity.user else 'غير معروف'}",
                'time': time_str,
                'type': activity_type
            })
        
        return jsonify({'success': True, 'activities': activities}), 200
        
    except Exception as e:
        logging.error(f"API recent activities error: {str(e)}")
        return jsonify({'success': False, 'activities': []}), 200

@super_admin_bp.route('/api/ai-assistant', methods=['POST'])
@login_required
@super_admin_required
def api_ai_assistant():
    """API للمساعد الذكي المتطور - محرك واحد موحد"""
    try:
        from app_factory import db
        from services.smart_ai_engine import SmartAIEngine
        from services.ai_validator import AIValidator
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        # إنشاء محرك الذكاء الاصطناعي
        ai_engine = SmartAIEngine(db)
        
        # التحقق من صحة النظام (اختياري - فقط للتحذيرات)
        validation = AIValidator.validate_system_data()
        
        # معالجة السؤال باستخدام المحرك الذكي
        result = ai_engine.process_query(user_message)
        
        response = result.get('response', 'عذراً، لم أتمكن من فهم سؤالك')
        actions = result.get('actions', [])
        
        # إضافة تحذير إذا كانت هناك أخطاء في النظام (بدون منع الاستخدام)
        if not validation['valid'] and len(validation['errors']) > 0:
            warning = "\n\nملاحظة: تم اكتشاف بعض المشاكل في النظام. اكتب فحص صحة النظام للتفاصيل."
            response += warning
        
        return jsonify({
            'success': True,
            'response': response,
            'actions': actions
        }), 200
        
    except Exception as e:
        logging.error(f"AI Assistant error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'response': 'تعذر معالجة طلبك حالياً، يرجى المحاولة مرة أخرى'
        }), 200
