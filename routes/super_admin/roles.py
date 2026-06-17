"""roles routes - extracted from monolithic super_admin.py"""

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
# ROLES ROUTES
# =============================================

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
@super_admin_bp.route('/create-role-simple', methods=['POST'])
@login_required
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
@login_required
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
