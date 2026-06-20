"""users routes - extracted from monolithic super_admin.py"""

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
# USERS ROUTES
# =============================================

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

                logging.warning(f"Error in {__name__}: {e}")
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

# إدارة المستخدمين المتقدمة
@super_admin_bp.route('/users/ban/<int:user_id>')
@login_required
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
@login_required
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
@login_required
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


