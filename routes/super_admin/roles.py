"""roles routes - extracted from monolithic super_admin.py"""

import logging

# Imports
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.super_admin import super_admin_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import super_admin_required

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

        roles = db.session.execute(select(Role)).scalars().all()
        return render_template('super_admin/roles.html', roles=roles, mode='list')
    except Exception:
        logging.exception('Error loading roles: %s')
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/roles.html', roles=[], mode='list')


@super_admin_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_role():
    """إنشاء دور جديد"""
    if request.method == 'POST':
        try:
            from models.permissions import Permission, Role, RolePermission

            role = Role(
                name=request.form.get('name'),
                name_ar=request.form.get('name_ar'),
                description=request.form.get('description'),
                is_system_role=bool(request.form.get('is_system_role')),
                is_active=bool(request.form.get('is_active')),
            )

            from app.extensions import db

            db.session.add(role)
            db.session.flush()  # للحصول على ID

            # إضافة الصلاحيات للدور
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(role_id=role.id, permission_id=int(perm_id))
                db.session.add(role_permission)

            safe_commit(db.session, error_message='database commit failed', reraise=True)

            flash('تم إنشاء الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))

        except Exception:
            from app.extensions import db

            safe_rollback(db.session, error_message='database rollback')
            logging.exception('Create role error: %s')
            flash('تعذر إنشاء الدور، يرجى المحاولة مرة أخرى', 'error')

    # جلب الصلاحيات المتاحة
    from models.permissions import Permission

    permissions = db.session.execute(select(Permission)).scalars().all()

    return render_template('super_admin/roles.html', permissions=permissions, mode='create')


@super_admin_bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_role(role_id):
    """تعديل دور"""
    try:
        from app.extensions import db
        from models.permissions import Permission, Role, RolePermission

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
            select(RolePermission).delete()

            # إضافة الصلاحيات الجديدة
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(role_id=role.id, permission_id=int(perm_id))
                db.session.add(role_permission)

            safe_commit(db.session, error_message='database commit failed', reraise=True)

            flash('تم تحديث الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))

        # جلب الصلاحيات المتاحة والصلاحيات الحالية للدور
        all_permissions = db.session.execute(select(Permission)).scalars().all()
        role_permissions = [
            rp.permission_id
            for rp in db.session.execute(select(RolePermission).filter_by(role_id=role.id))
            .scalars()
            .all()
        ]

        return render_template(
            'super_admin/roles.html',
            role=role,
            all_permissions=all_permissions,
            role_permissions=role_permissions,
            mode='edit',
        )

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Edit role error: %s')
        flash('تعذر تحديث الدور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/roles/<int:role_id>/permissions', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_role_permissions(role_id):
    """إدارة صلاحيات الدور"""
    try:
        from app.extensions import db
        from models.permissions import Permission, Role, RolePermission

        role = db.session.get(Role, role_id)
        if not role:
            abort(404)

        if request.method == 'POST':
            # حذف الصلاحيات الحالية
            select(RolePermission).delete()

            # إضافة الصلاحيات الجديدة
            selected_permissions = request.form.getlist('permissions')
            for permission_id in selected_permissions:
                role_permission = RolePermission(
                    role_id=role_id, permission_id=int(permission_id), granted_by=current_user.id
                )
                db.session.add(role_permission)

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تحديث صلاحيات الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))

        all_permissions = db.session.execute(select(Permission)).scalars().all()
        role_permissions = [
            rp.permission_id
            for rp in db.session.execute(select(RolePermission).filter_by(role_id=role_id))
            .scalars()
            .all()
        ]

        return render_template(
            'super_admin/role_permissions.html',
            role=role,
            all_permissions=all_permissions,
            role_permissions=role_permissions,
        )

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Manage role permissions error: %s')
        flash('حدث خطأ في إدارة صلاحيات الدور', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/roles/<int:role_id>/department-permissions', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_role_department_permissions(role_id):
    try:
        from sqlalchemy import inspect

        from app.extensions import db

        insp = inspect(db.engine)
        if not (
            insp.has_table('roles')
            and insp.has_table('departments')
            and insp.has_table('department_permissions')
        ):
            flash('جداول صلاحيات الأقسام غير متاحة في قاعدة البيانات', 'error')
            return redirect(url_for('super_admin.roles'))

        from models.advanced_permissions import DepartmentPermission
        from models.department import Department
        from models.permissions import Role

        role = db.session.get(Role, role_id)
        if not role:
            abort(404)

        departments = (
            db.session.execute(
                select(Department).filter_by(is_active=True).order_by(Department.name_ar.asc())
            )
            .scalars()
            .all()
        )

        if request.method == 'POST':
            select(DepartmentPermission).delete()

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

                any_flag = any(
                    [
                        can_access,
                        can_manage_patients,
                        can_manage_visits,
                        can_manage_appointments,
                        can_manage_staff,
                        can_override_department_limits,
                        can_manage_department_settings,
                    ]
                )
                if not any_flag:
                    continue
                if not can_access and any(
                    [
                        can_manage_patients,
                        can_manage_visits,
                        can_manage_appointments,
                        can_manage_staff,
                        can_override_department_limits,
                        can_manage_department_settings,
                    ]
                ):
                    can_access = True

                db.session.add(
                    DepartmentPermission(
                        role_id=role_id,
                        department_id=did,
                        can_access=can_access,
                        can_manage_patients=can_manage_patients,
                        can_manage_visits=can_manage_visits,
                        can_manage_appointments=can_manage_appointments,
                        can_manage_staff=can_manage_staff,
                        can_override_department_limits=can_override_department_limits,
                        can_manage_department_settings=can_manage_department_settings,
                    )
                )

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تحديث صلاحيات الأقسام للدور', 'success')
            return redirect(
                url_for('super_admin.manage_role_department_permissions', role_id=role_id)
            )

        existing = (
            db.session.execute(select(DepartmentPermission).filter_by(role_id=role_id))
            .scalars()
            .all()
        )
        perm_map = {}
        for r in existing:
            perm_map[r.department_id] = r

        return render_template(
            'super_admin/department_permissions.html',
            role=role,
            departments=departments,
            perm_map=perm_map,
        )
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Department permissions error: %s')
        flash('حدث خطأ في إدارة صلاحيات الأقسام', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/permissions-matrix', methods=['GET', 'POST'])
@login_required
@super_admin_required
def permissions_matrix():
    try:
        from sqlalchemy import inspect

        from app.extensions import db

        insp = inspect(db.engine)
        if not (
            insp.has_table('roles')
            and insp.has_table('permissions')
            and insp.has_table('role_permissions')
        ):
            flash('جداول الصلاحيات غير متاحة في قاعدة البيانات', 'error')
            return redirect(url_for('super_admin.dashboard'))

        from models.permissions import (
            Permission,
            Role,
            RolePermission,
            assign_super_admin_permissions,
            create_default_permissions,
            create_default_roles,
        )

        try:
            create_default_permissions()
            create_default_roles()
            assign_super_admin_permissions()
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        roles = (
            db.session.execute(select(Role).filter_by(is_active=True).order_by(Role.id.asc()))
            .scalars()
            .all()
        )
        permissions = (
            db.session.execute(
                select(Permission)
                .filter_by(is_active=True)
                .order_by(Permission.category.asc(), Permission.level.asc(), Permission.name.asc())
            )
            .scalars()
            .all()
        )

        if request.method == 'POST':
            for role in roles:
                select(RolePermission).delete()
                selected = request.form.getlist(f'role_{role.id}_permissions')
                for pid in selected:
                    try:
                        db.session.add(
                            RolePermission(
                                role_id=role.id, permission_id=int(pid), granted_by=current_user.id
                            )
                        )
                    except Exception:
                        continue
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تحديث مصفوفة الصلاحيات', 'success')
            return redirect(url_for('super_admin.permissions_matrix'))

        rp = (
            db.session.execute(
                select(RolePermission).filter(RolePermission.role_id.in_([r.id for r in roles]))
            )
            .scalars()
            .all()
            if roles
            else []
        )
        matrix = {}
        for row in rp:
            matrix.setdefault(row.role_id, set()).add(row.permission_id)

        return render_template(
            'super_admin/permissions_matrix.html',
            roles=roles,
            permissions=permissions,
            matrix=matrix,
        )
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Permissions matrix error: %s')
        flash('حدث خطأ في تحميل مصفوفة الصلاحيات', 'error')
        return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_role(role_id):
    """حذف دور"""
    try:
        from app.extensions import db
        from models.permissions import Role, RolePermission

        role = db.session.get(Role, role_id)
        if not role:
            abort(404)

        # منع حذف الأدوار النظامية
        if role.is_system_role:
            flash('لا يمكن حذف الأدوار النظامية', 'error')
            return redirect(url_for('super_admin.roles'))

        # حذف صلاحيات الدور أولاً
        select(RolePermission).delete()

        db.session.delete(role)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم حذف الدور بنجاح', 'success')
        return redirect(url_for('super_admin.roles'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Delete role error: %s')
        flash('تعذر حذف الدور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('super_admin.roles'))


@super_admin_bp.route('/permissions')
@login_required
@super_admin_required
def permissions():
    """إدارة الصلاحيات"""
    try:
        from models.permissions import Permission

        permissions = db.session.execute(select(Permission)).scalars().all()
        return render_template('super_admin/permissions.html', permissions=permissions)
    except Exception:
        logging.exception('Permissions error: %s')
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/permissions.html', permissions=[])


@super_admin_bp.route('/permissions/create', methods=['POST'])
@login_required
@super_admin_required
def create_permission():
    """إنشاء صلاحية جديدة"""
    try:
        from app.extensions import db
        from models.permissions import Permission

        permission = Permission(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            level=request.form.get('level'),
            is_active=True,
        )

        db.session.add(permission)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Create permission error: %s')
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))


@super_admin_bp.route('/permissions/<int:permission_id>/edit', methods=['POST'])
@login_required
@super_admin_required
def edit_permission(permission_id):
    """تعديل صلاحية"""
    try:
        from app.extensions import db
        from models.permissions import Permission

        permission = db.session.get(Permission, permission_id)
        if not permission:
            abort(404)

        permission.name = request.form.get('name')
        permission.description = request.form.get('description')
        permission.category = request.form.get('category')
        permission.level = request.form.get('level')
        permission.is_active = bool(request.form.get('is_active'))

        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم تحديث الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Edit permission error: %s')
        flash('حدث خطأ في تعديل الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))


@super_admin_bp.route('/permissions/<int:permission_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_permission(permission_id):
    """حذف صلاحية"""
    try:
        from app.extensions import db
        from models.permissions import Permission

        permission = db.session.get(Permission, permission_id)
        if not permission:
            abort(404)

        db.session.delete(permission)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم حذف الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Delete permission error: %s')
        flash('حدث خطأ في حذف الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))


@super_admin_bp.route('/create-role-simple', methods=['POST'])
@login_required
@super_admin_required
def create_role_simple():
    """إنشاء دور جديد (مبسط)"""
    try:
        from flask_wtf.csrf import validate_csrf

        from app.extensions import db
        from models.permissions import Role

        validate_csrf(request.form.get('csrf_token'))

        role = Role(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description'),
            is_system_role=False,
            is_active=True,
        )

        db.session.add(role)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم إنشاء الدور بنجاح', 'success')
        return redirect(url_for('super_admin.users'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Create role error: %s')
        flash('حدث خطأ في إنشاء الدور', 'error')
        return redirect(url_for('super_admin.users'))


@super_admin_bp.route('/create-permission-simple', methods=['POST'])
@login_required
@super_admin_required
def create_permission_simple():
    """إنشاء صلاحية جديدة (مبسط)"""
    try:
        from flask_wtf.csrf import validate_csrf

        from app.extensions import db
        from models.permissions import Permission, PermissionCategory, PermissionLevel

        validate_csrf(request.form.get('csrf_token'))

        permission = Permission(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=PermissionCategory.SYSTEM_ADMIN,
            level=PermissionLevel.ADMIN,
        )

        db.session.add(permission)
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.users'))

    except Exception:
        from app.extensions import db

        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Create permission error: %s')
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.users'))


# دوال مساعدة للإحصائيات
