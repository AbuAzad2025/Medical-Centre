"""
خدمة التحكم في الوصول المحسنة
Enhanced Access Control Service
"""

import logging
from datetime import UTC, datetime, timedelta
from functools import wraps

from flask import abort
from sqlalchemy import func, select

from app.extensions import db
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from utils.tenant_query import TenantContextError, get_tenant_record


class AccessControlService:
    """خدمة التحكم في الوصول المحسنة"""

    # تعريف الصلاحيات لكل دور (soft-deprecated: use PermissionService.ROLE_PERMISSIONS)
    ROLE_PERMISSIONS = {
        'admin': [
            'manage_users',
            'manage_departments',
            'manage_roles',
            'view_all_visits',
            'view_financial_reports',
            'system_settings',
            'modify_archived_visits',
            'pricing_management',
            'audit_trail',
            'view_all_patients',
            'view_all_reports',
            'queue_settings_manage',
        ],
        'manager': [
            'manage_doctors',
            'view_financial_reports',
            'pricing_management',
            'view_all_visits',
            'audit_trail',
            'view_all_patients',
            'queue_settings_manage',
            'manage_catalog',
            'manage_staff',
        ],
        'super_admin': [
            'manage_users',
            'manage_departments',
            'manage_roles',
            'view_all_visits',
            'view_financial_reports',
            'system_settings',
            'modify_archived_visits',
            'pricing_management',
            'audit_trail',
            'view_all_patients',
            'view_all_reports',
            'queue_settings_manage',
        ],
        'doctor': [
            'view_own_visits',
            'diagnose_patients',
            'prescribe_medications',
            'search_patient_archive',
            'view_own_patients',
        ],
        'reception': [
            'create_visits',
            'process_payments',
            'archive_visits',
            'manage_patients',
            'print_receipts',
            'manage_queues',
            'modify_visits_30min',
            'search_patient_archive',
            'view_all_visits',
            'queue_settings_manage',
        ],
        'lab': [
            'view_lab_requests',
            'enter_lab_results',
            'print_lab_reports',
            'manage_samples',
            'view_lab_visits',
        ],
        'radiology': [
            'view_radiology_requests',
            'enter_radiology_reports',
            'upload_images',
            'print_radiology_reports',
            'view_radiology_visits',
        ],
        'emergency': [
            'quick_patient_entry',
            'emergency_prioritization',
            'emergency_treatment',
            'convert_to_full_visit',
            'view_emergency_cases',
        ],
        'nurse': [
            'assist_doctors',
            'patient_care',
            'medication_administration',
            'vital_signs',
            'view_nurse_patients',
        ],
        'accountant': [
            'financial_reports',
            'payment_processing',
            'daily_closure',
            'audit_trail',
            'view_financial_data',
        ],
    }

    @staticmethod
    def can_access_visit(user_id, visit_id):
        """التحقق من إمكانية الوصول لزيارة معينة"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return False

            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False

            # المدير والمدير العام والاستقبال يمكنهم الوصول لجميع الزيارات
            if user.is_admin_user() or user.role == 'reception':
                return True

            # الأطباء يمكنهم الوصول لزياراتهم فقط
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return True

            # المختبر والأشعة يمكنهم الوصول للزيارات الموجهة لهم
            if (user.role == 'lab' and visit.lab_tests_ordered) or (
                user.role == 'radiology' and visit.radiology_ordered
            ):
                return True

            # الطوارئ يمكنهم الوصول لحالات الطوارئ
            return bool(user.role == 'emergency' and visit.is_emergency)

        except Exception:
            logging.exception('Error checking visit access: %s')
            return False

    @staticmethod
    def can_modify_visit(user_id, visit_id):
        """التحقق من إمكانية تعديل زيارة"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return False

            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return False

            # المدير فقط يمكنه تعديل الزيارات المؤرشفة
            if visit.is_archived:
                return user.is_admin_user()

            # الاستقبال يمكنه تعديل الزيارات خلال 30 دقيقة
            if user.role == 'reception':
                if visit.created_at:
                    created = visit.created_at
                    # created_at is stored naive (UTC); normalise to avoid a
                    # naive/aware subtraction TypeError that would deny edits.
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=UTC)
                    time_diff = datetime.now(UTC) - created
                    return time_diff <= timedelta(minutes=30)

            # الأطباء يمكنهم تعديل زياراتهم غير المؤرشفة
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return not visit.is_archived

            return False

        except Exception:
            logging.exception('Error checking visit modification: %s')
            return False

    @staticmethod
    def can_create_visit(user_id):
        """التحقق من إمكانية إنشاء زيارة"""
        return AccessControlService.has_permission(user_id, 'create_visits')

    @staticmethod
    def can_process_payment(user_id):
        """التحقق من إمكانية معالجة الدفع"""
        return AccessControlService.has_permission(user_id, 'process_payments')

    @staticmethod
    def can_archive_visit(user_id):
        """التحقق من إمكانية أرشفة زيارة"""
        return AccessControlService.has_permission(user_id, 'archive_visits')

    @staticmethod
    def can_prescribe_medication(user_id):
        """التحقق من إمكانية كتابة روشيتة"""
        return AccessControlService.has_permission(user_id, 'prescribe_medications')

    @staticmethod
    def can_enter_lab_results(user_id):
        """التحقق من إمكانية إدخال نتائج التحاليل"""
        return AccessControlService.has_permission(user_id, 'enter_lab_results')

    @staticmethod
    def can_enter_radiology_reports(user_id):
        """التحقق من إمكانية إدخال تقارير الأشعة"""
        return AccessControlService.has_permission(user_id, 'enter_radiology_reports')

    @staticmethod
    def get_user_accessible_visits(user_id):
        """الحصول على الزيارات المتاحة للمستخدم"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return []

            # Manager and reception access all visits within their tenant
            if user.is_admin_user() or user.role in {'reception', 'manager'}:
                return db.session.execute(select(Visit).filter(Visit.tenant_id == user.tenant_id)).scalars().all()

            # Doctors can view all visits (within tenant) without modification
            if user.role == 'doctor':
                return db.session.execute(select(Visit).filter(Visit.tenant_id == user.tenant_id)).scalars().all()

            # Lab sees visits with lab orders (within tenant)
            if user.role == 'lab':
                return (
                    db.session.execute(select(Visit).filter(Visit.lab_tests_ordered, Visit.tenant_id == user.tenant_id))
                    .scalars()
                    .all()
                )
            if user.role == 'radiology':
                return (
                    db.session.execute(select(Visit).filter(Visit.radiology_ordered, Visit.tenant_id == user.tenant_id))
                    .scalars()
                    .all()
                )

            # Emergency sees emergency cases (within tenant)
            if user.role == 'emergency':
                return db.session.execute(select(Visit).filter(Visit.is_emergency, Visit.tenant_id == user.tenant_id)).scalars().all()

            # Accountant sees visits with payments (within tenant)
            if user.role == 'accountant':
                return (
                    db.session.execute(
                        select(Visit).join(Payment, Payment.visit_id == Visit.id).filter(Visit.tenant_id == user.tenant_id).distinct()
                    )
                    .scalars()
                    .all()
                )

            return []

        except Exception:
            logging.exception('Error getting accessible visits: %s')
            return []

    @staticmethod
    def get_user_accessible_patients(user_id):
        """الحصول على المرضى المتاحين للمستخدم"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return []

            # Manager and reception access all patients within their tenant
            if user.is_admin_user() or user.role in {'reception', 'manager'}:
                return db.session.execute(select(Patient).filter(Patient.tenant_id == user.tenant_id)).scalars().all()

            # Doctors can view all patients (within tenant)
            if user.role == 'doctor':
                return db.session.execute(select(Patient).filter(Patient.tenant_id == user.tenant_id)).scalars().all()

            # Nurses see patients of doctors they work with (within tenant)
            if user.role == 'nurse':
                return db.session.execute(select(Patient).filter(Patient.tenant_id == user.tenant_id)).scalars().all()

            # Lab and Radiology see patients linked to their tests (within tenant)
            if user.role == 'lab':
                return (
                    db.session.execute(
                        select(Patient)
                        .join(Visit, Visit.patient_id == Patient.id)
                        .filter(Visit.lab_tests_ordered, Patient.tenant_id == user.tenant_id)
                        .distinct()
                    )
                    .scalars()
                    .all()
                )
            if user.role == 'radiology':
                return (
                    db.session.execute(
                        select(Patient)
                        .join(Visit, Visit.patient_id == Patient.id)
                        .filter(Visit.radiology_ordered, Patient.tenant_id == user.tenant_id)
                        .distinct()
                    )
                    .scalars()
                    .all()
                )

            # Accountant sees patients with payments (within tenant)
            if user.role == 'accountant':
                return (
                    db.session.execute(
                        select(Patient).join(Payment, Payment.patient_id == Patient.id).filter(Patient.tenant_id == user.tenant_id).distinct()
                    )
                    .scalars()
                    .all()
                )

            return []

        except Exception:
            logging.exception('Error getting accessible patients: %s')
            return []

    @staticmethod
    def get_user_dashboard_route(user_id):
        """الحصول على مسار لوحة التحكم حسب الدور"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return '/dashboard'

            role_routes = {
                'admin': '/admin/dashboard',
                'manager': '/admin/dashboard',
                'doctor': '/doctor/dashboard',
                'reception': '/reception/dashboard',
                'lab': '/lab/dashboard',
                'radiology': '/radiology/dashboard',
                'emergency': '/emergency/dashboard',
                'nurse': '/nurse/dashboard',
                'accountant': '/accountant/dashboard',
            }

            return role_routes.get(user.role, '/dashboard')

        except Exception:
            logging.exception('Error getting dashboard route: %s')
            return '/dashboard'

    @staticmethod
    def get_user_menu_items(user_id):
        """الحصول على عناصر القائمة حسب الدور"""
        try:
            try:
                user = get_tenant_record(User, user_id)
            except TenantContextError:
                return []

            # تعريف القوائم لكل دور
            role_menus = {
                'admin': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/admin/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'المستخدمين', 'url': '/admin/users', 'icon': 'fas fa-users'},
                    {'name': 'الأقسام', 'url': '/admin/departments', 'icon': 'fas fa-building'},
                    {'name': 'الأدوار', 'url': '/admin/roles', 'icon': 'fas fa-user-shield'},
                    {'name': 'التقارير', 'url': '/admin/reports', 'icon': 'fas fa-chart-bar'},
                    {'name': 'الإعدادات', 'url': '/admin/settings', 'icon': 'fas fa-cog'},
                ],
                'reception': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/reception/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'المرضى', 'url': '/patients', 'icon': 'fas fa-user-injured'},
                    {'name': 'الزيارات', 'url': '/visits', 'icon': 'fas fa-calendar-check'},
                    {'name': 'المواعيد', 'url': '/appointments', 'icon': 'fas fa-calendar'},
                    {'name': 'الطوابير', 'url': '/queue', 'icon': 'fas fa-list-ol'},
                    {
                        'name': 'المدفوعات',
                        'url': '/reception/pending-payments',
                        'icon': 'fas fa-credit-card',
                    },
                ],
                'doctor': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/doctor/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'الزيارات', 'url': '/doctor/visits', 'icon': 'fas fa-stethoscope'},
                    {'name': 'المرضى', 'url': '/doctor/patients', 'icon': 'fas fa-user-injured'},
                    {
                        'name': 'الروشيتات',
                        'url': '/doctor/prescriptions',
                        'icon': 'fas fa-prescription',
                    },
                    {'name': 'المواعيد', 'url': '/doctor/appointments', 'icon': 'fas fa-calendar'},
                ],
                'lab': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/lab/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'التحاليل', 'url': '/lab/list', 'icon': 'fas fa-flask'},
                    {'name': 'النتائج', 'url': '/lab/results', 'icon': 'fas fa-microscope'},
                    {'name': 'التقارير', 'url': '/lab/reports', 'icon': 'fas fa-file-medical'},
                ],
                'radiology': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/radiology/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'الفحوصات', 'url': '/radiology/list', 'icon': 'fas fa-x-ray'},
                    {
                        'name': 'التقارير',
                        'url': '/radiology/reports',
                        'icon': 'fas fa-file-medical',
                    },
                    {'name': 'الصور', 'url': '/radiology/images', 'icon': 'fas fa-images'},
                ],
                'emergency': [
                    {
                        'name': 'لوحة التحكم',
                        'url': '/emergency/dashboard',
                        'icon': 'fas fa-tachometer-alt',
                    },
                    {'name': 'حالات الطوارئ', 'url': '/emergency/list', 'icon': 'fas fa-ambulance'},
                    {'name': 'إضافة حالة', 'url': '/emergency/add', 'icon': 'fas fa-plus'},
                    {
                        'name': 'الأولويات',
                        'url': '/emergency/priorities',
                        'icon': 'fas fa-exclamation-triangle',
                    },
                ],
            }

            return role_menus.get(user.role, [])

        except Exception:
            logging.exception('Error getting menu items: %s')
            return []

    @staticmethod
    def has_permission(user, permission_name):
        """التحقق من وجود صلاحية للمستخدم — delegates to PermissionService"""
        try:
            from app.core.permission.service import PermissionService

            return PermissionService.has_permission(user, permission_name)
        except Exception:
            logging.exception("Error checking permission '{permission_name}'")
            return False

    @staticmethod
    def has_role(user, role_name):
        """التحقق من دور المستخدم"""
        try:
            return user.role == role_name
        except Exception:
            logging.exception("Error checking role '{role_name}'")
            return False

    @staticmethod
    def require_permission(permission_name):
        """ديكوراتور للتحقق من الصلاحية"""

        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                from flask_login import current_user

                if not AccessControlService.has_permission(current_user, permission_name):
                    abort(403)
                return f(*args, **kwargs)

            return decorated_function

        return decorator

    @staticmethod
    def require_role(role_name):
        """ديكوراتور للتحقق من الدور"""

        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                from flask_login import current_user

                if not AccessControlService.has_role(current_user, role_name):
                    abort(403)
                return f(*args, **kwargs)

            return decorated_function

        return decorator

    @staticmethod
    def get_accessible_department_ids(user):
        try:
            if user is None:
                return []
            if isinstance(user, int):
                try:
                    user = get_tenant_record(User, user)
                except TenantContextError:
                    return []
            if not user:
                return []
            if getattr(user, 'is_admin_user', None) and user.is_admin_user():
                return None

            ids = []
            try:
                from sqlalchemy import select

                from models.advanced_permissions import DepartmentPermission
                from models.permissions import Role

                role = (
                    db.session.execute(select(Role).where(Role.name == user.role, Role.is_active))
                    .scalars()
                    .first()
                )
                if role:
                    global_row = (
                        db.session.execute(
                            select(DepartmentPermission).where(
                                DepartmentPermission.role_id == role.id,
                                DepartmentPermission.department_id.is_(None),
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if global_row and global_row.can_access:
                        return None
                    rows = (
                        db.session.execute(
                            select(DepartmentPermission).where(
                                DepartmentPermission.role_id == role.id,
                                DepartmentPermission.department_id.isnot(None),
                                DepartmentPermission.can_access,
                            )
                        )
                        .scalars()
                        .all()
                    )
                    ids.extend([int(r.department_id) for r in rows if r.department_id])
            except Exception:
                pass

            try:
                if getattr(user, 'department_id', None):
                    ids.append(int(user.department_id))
            except Exception:
                pass

            try:
                from models.user_department_access import UserDepartmentAccess

                extra = (
                    db.session.execute(
                        select(UserDepartmentAccess).where(
                            UserDepartmentAccess.user_id == user.id,
                            UserDepartmentAccess.can_access,
                        )
                    )
                    .scalars()
                    .all()
                )
                for r in extra:
                    try:
                        ids.append(int(r.department_id))
                    except Exception:
                        continue
            except Exception:
                pass

            out = []
            seen = set()
            for x in ids:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out
        except Exception:
            return []

    @staticmethod
    def can_department_action(user, department_id, action):
        try:
            if user is None:
                return False
            if isinstance(user, int):
                try:
                    user = get_tenant_record(User, user)
                except TenantContextError:
                    return False
            if not user:
                return False
            if getattr(user, 'is_admin_user', None) and user.is_admin_user():
                return True

            dept_ids = AccessControlService.get_accessible_department_ids(user)
            if dept_ids is None:
                return True
            try:
                dep_id = int(department_id) if department_id is not None else None
            except Exception:
                dep_id = None
            if dep_id is None:
                return False
            if dept_ids and dep_id not in dept_ids:
                return False

            try:
                from sqlalchemy import inspect

                insp = inspect(db.engine)
                if insp.has_table('department_permissions') and insp.has_table('roles'):
                    from models.advanced_permissions import DepartmentPermission
                    from models.permissions import Role

                    role = (
                        db.session.execute(select(Role).filter_by(name=user.role, is_active=True))
                        .scalars()
                        .first()
                    )
                    if not role:
                        return True
                    has_any = (
                        db.session.execute(
                            select(func.count())
                            .select_from(DepartmentPermission)
                            .filter_by(role_id=role.id)
                        ).scalar()
                        or 0
                    ) > 0
                    if not has_any:
                        return True
                    global_row = (
                        db.session.execute(
                            select(DepartmentPermission).filter_by(
                                role_id=role.id, department_id=None
                            )
                        )
                        .scalars()
                        .first()
                    )
                    row = (
                        db.session.execute(
                            select(DepartmentPermission).filter_by(
                                role_id=role.id, department_id=dep_id
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if action == 'access':
                        return bool(
                            (row and row.can_access) or (global_row and global_row.can_access)
                        )
                    if action == 'patients':
                        return bool(
                            (row and row.can_manage_patients)
                            or (global_row and global_row.can_manage_patients)
                        )
                    if action == 'visits':
                        return bool(
                            (row and row.can_manage_visits)
                            or (global_row and global_row.can_manage_visits)
                        )
                    if action == 'appointments':
                        return bool(
                            (row and row.can_manage_appointments)
                            or (global_row and global_row.can_manage_appointments)
                        )
                    if action == 'staff':
                        return bool(
                            (row and row.can_manage_staff)
                            or (global_row and global_row.can_manage_staff)
                        )
                    if action == 'settings':
                        return bool(
                            (row and row.can_manage_department_settings)
                            or (global_row and global_row.can_manage_department_settings)
                        )
            except Exception:
                pass

            return True
        except Exception:
            return False
