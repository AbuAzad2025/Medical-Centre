"""
خدمة التحكم في الوصول المحسنة
Enhanced Access Control Service
"""

from models.user import User
from models.visit import Visit
from models.patient import Patient
from models.appointment import Appointment
from models.medication import Prescription
from models.lab_request import LabResult
from models.radiology_result import RadiologyResult
from models.payment import Payment
from app.shared.enums import VisitState, VisitArchiveStatus
from app_factory import db
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import abort

class AccessControlService:
    """خدمة التحكم في الوصول المحسنة"""
    
    # تعريف الصلاحيات لكل دور (soft-deprecated: use PermissionService.ROLE_PERMISSIONS)
    ROLE_PERMISSIONS = {
        'admin': [
            'manage_users', 'manage_departments', 'manage_roles',
            'view_all_visits', 'view_financial_reports', 'system_settings',
            'modify_archived_visits', 'pricing_management', 'audit_trail',
            'view_all_patients', 'view_all_reports', 'queue_settings_manage'
        ],
        'manager': [
            'manage_doctors', 'view_financial_reports', 'pricing_management',
            'view_all_visits', 'audit_trail', 'view_all_patients',
            'queue_settings_manage', 'manage_catalog', 'manage_staff'
        ],
        'super_admin': [
            'manage_users', 'manage_departments', 'manage_roles',
            'view_all_visits', 'view_financial_reports', 'system_settings',
            'modify_archived_visits', 'pricing_management', 'audit_trail',
            'view_all_patients', 'view_all_reports', 'queue_settings_manage'
        ],
        'doctor': [
            'view_own_visits', 'diagnose_patients', 'prescribe_medications',
            'search_patient_archive', 'view_own_patients'
        ],
        'reception': [
            'create_visits', 'process_payments', 'archive_visits',
            'manage_patients', 'print_receipts', 'manage_queues',
            'modify_visits_30min', 'search_patient_archive', 'view_all_visits',
            'queue_settings_manage'
        ],
        'lab': [
            'view_lab_requests', 'enter_lab_results', 'print_lab_reports',
            'manage_samples', 'view_lab_visits'
        ],
        'radiology': [
            'view_radiology_requests', 'enter_radiology_reports', 
            'upload_images', 'print_radiology_reports', 'view_radiology_visits'
        ],
        'emergency': [
            'quick_patient_entry', 'emergency_prioritization', 
            'emergency_treatment', 'convert_to_full_visit', 'view_emergency_cases'
        ],
        'nurse': [
            'assist_doctors', 'patient_care', 'medication_administration',
            'vital_signs', 'view_nurse_patients'
        ],
        'accountant': [
            'financial_reports', 'payment_processing', 'daily_closure',
            'audit_trail', 'view_financial_data'
        ]
    }
    
    @staticmethod
    def can_access_visit(user_id, visit_id):
        """التحقق من إمكانية الوصول لزيارة معينة"""
        try:
            user = db.session.get(User, user_id)
            if not user:
                return False
            
            visit = db.session.get(Visit, visit_id)
            if not visit:
                return False
            
            # المدير والمدير العام والاستقبال يمكنهم الوصول لجميع الزيارات
            if user.is_admin_user() or user.role == 'reception':
                return True
            
            # الأطباء يمكنهم الوصول لزياراتهم فقط
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return True
            
            # المختبر والأشعة يمكنهم الوصول للزيارات الموجهة لهم
            if user.role == 'lab' and visit.lab_tests_ordered:
                return True
            elif user.role == 'radiology' and visit.radiology_ordered:
                return True
            
            # الطوارئ يمكنهم الوصول لحالات الطوارئ
            if user.role == 'emergency' and visit.is_emergency:
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking visit access: {str(e)}")
            return False
    
    @staticmethod
    def can_modify_visit(user_id, visit_id):
        """التحقق من إمكانية تعديل زيارة"""
        try:
            user = db.session.get(User, user_id)
            if not user:
                return False
            
            visit = db.session.get(Visit, visit_id)
            if not visit:
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
                        created = created.replace(tzinfo=timezone.utc)
                    time_diff = datetime.now(timezone.utc) - created
                    return time_diff <= timedelta(minutes=30)
            
            # الأطباء يمكنهم تعديل زياراتهم غير المؤرشفة
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return not visit.is_archived
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking visit modification: {str(e)}")
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
            user = db.session.get(User, user_id)
            if not user:
                return []
            
            # المدير والمدير العام والاستقبال يمكنهم رؤية جميع الزيارات
            if user.is_admin_user() or user.role == 'reception' or user.role == 'manager':
                return Visit.query.all()
            
            # الأطباء يمكنهم عرض جميع الزيارات دون تعديل
            if user.role == 'doctor':
                return Visit.query.all()
            
            # المختبر والأشعة يرون الزيارات الموجهة لهم
            if user.role == 'lab':
                return Visit.query.filter(Visit.lab_tests_ordered == True).all()
            elif user.role == 'radiology':
                return Visit.query.filter(Visit.radiology_ordered == True).all()
            
            # الطوارئ يرون حالات الطوارئ
            if user.role == 'emergency':
                return Visit.query.filter(Visit.is_emergency == True).all()

            # المحاسب يرى الزيارات ذات الصلة المالية فقط
            if user.role == 'accountant':
                return db.session.query(Visit).join(Payment, Payment.visit_id == Visit.id).distinct().all()
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting accessible visits: {str(e)}")
            return []
    
    @staticmethod
    def get_user_accessible_patients(user_id):
        """الحصول على المرضى المتاحين للمستخدم"""
        try:
            user = db.session.get(User, user_id)
            if not user:
                return []
            
            # المدير والمدير العام والاستقبال يمكنهم رؤية جميع المرضى
            if user.is_admin_user() or user.role == 'reception' or user.role == 'manager':
                return Patient.query.all()
            
            # الأطباء يمكنهم عرض جميع المرضى دون تعديل
            if user.role == 'doctor':
                return Patient.query.all()
            
            # الممرضين يرون مرضى الأطباء الذين يعملون معهم
            if user.role == 'nurse':
                # يمكن تطوير هذا لاحقاً حسب العلاقات
                return Patient.query.all()
            
            # المختبر والأشعة يرون المرضى المرتبطين بفحوصاتهم
            if user.role == 'lab':
                return Patient.query.join(Visit, Visit.patient_id == Patient.id).filter(Visit.lab_tests_ordered == True).distinct().all()
            if user.role == 'radiology':
                return Patient.query.join(Visit, Visit.patient_id == Patient.id).filter(Visit.radiology_ordered == True).distinct().all()

            # المحاسب يرى المرضى الذين لديهم عمليات دفع
            if user.role == 'accountant':
                return Patient.query.join(Payment, Payment.patient_id == Patient.id).distinct().all()

            return []
            
        except Exception as e:
            logging.error(f"Error getting accessible patients: {str(e)}")
            return []
    
    @staticmethod
    def get_user_dashboard_route(user_id):
        """الحصول على مسار لوحة التحكم حسب الدور"""
        try:
            user = db.session.get(User, user_id)
            if not user:
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
                'accountant': '/accountant/dashboard'
            }
            
            return role_routes.get(user.role, '/dashboard')
            
        except Exception as e:
            logging.error(f"Error getting dashboard route: {str(e)}")
            return '/dashboard'
    
    @staticmethod
    def get_user_menu_items(user_id):
        """الحصول على عناصر القائمة حسب الدور"""
        try:
            user = db.session.get(User, user_id)
            if not user:
                return []
            
            # تعريف القوائم لكل دور
            role_menus = {
                'admin': [
                    {'name': 'لوحة التحكم', 'url': '/admin/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'المستخدمين', 'url': '/admin/users', 'icon': 'fas fa-users'},
                    {'name': 'الأقسام', 'url': '/admin/departments', 'icon': 'fas fa-building'},
                    {'name': 'الأدوار', 'url': '/admin/roles', 'icon': 'fas fa-user-shield'},
                    {'name': 'التقارير', 'url': '/admin/reports', 'icon': 'fas fa-chart-bar'},
                    {'name': 'الإعدادات', 'url': '/admin/settings', 'icon': 'fas fa-cog'}
                ],
                'reception': [
                    {'name': 'لوحة التحكم', 'url': '/reception/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'المرضى', 'url': '/patients', 'icon': 'fas fa-user-injured'},
                    {'name': 'الزيارات', 'url': '/visits', 'icon': 'fas fa-calendar-check'},
                    {'name': 'المواعيد', 'url': '/appointments', 'icon': 'fas fa-calendar'},
                    {'name': 'الطوابير', 'url': '/queue', 'icon': 'fas fa-list-ol'},
                    {'name': 'المدفوعات', 'url': '/reception/pending-payments', 'icon': 'fas fa-credit-card'}
                ],
                'doctor': [
                    {'name': 'لوحة التحكم', 'url': '/doctor/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'الزيارات', 'url': '/doctor/visits', 'icon': 'fas fa-stethoscope'},
                    {'name': 'المرضى', 'url': '/doctor/patients', 'icon': 'fas fa-user-injured'},
                    {'name': 'الروشيتات', 'url': '/doctor/prescriptions', 'icon': 'fas fa-prescription'},
                    {'name': 'المواعيد', 'url': '/doctor/appointments', 'icon': 'fas fa-calendar'}
                ],
                'lab': [
                    {'name': 'لوحة التحكم', 'url': '/lab/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'التحاليل', 'url': '/lab/list', 'icon': 'fas fa-flask'},
                    {'name': 'النتائج', 'url': '/lab/results', 'icon': 'fas fa-microscope'},
                    {'name': 'التقارير', 'url': '/lab/reports', 'icon': 'fas fa-file-medical'}
                ],
                'radiology': [
                    {'name': 'لوحة التحكم', 'url': '/radiology/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'الفحوصات', 'url': '/radiology/list', 'icon': 'fas fa-x-ray'},
                    {'name': 'التقارير', 'url': '/radiology/reports', 'icon': 'fas fa-file-medical'},
                    {'name': 'الصور', 'url': '/radiology/images', 'icon': 'fas fa-images'}
                ],
                'emergency': [
                    {'name': 'لوحة التحكم', 'url': '/emergency/dashboard', 'icon': 'fas fa-tachometer-alt'},
                    {'name': 'حالات الطوارئ', 'url': '/emergency/list', 'icon': 'fas fa-ambulance'},
                    {'name': 'إضافة حالة', 'url': '/emergency/add', 'icon': 'fas fa-plus'},
                    {'name': 'الأولويات', 'url': '/emergency/priorities', 'icon': 'fas fa-exclamation-triangle'}
                ]
            }
            
            return role_menus.get(user.role, [])
            
        except Exception as e:
            logging.error(f"Error getting menu items: {str(e)}")
            return []
    
    @staticmethod
    def has_permission(user, permission_name):
        """التحقق من وجود صلاحية للمستخدم — delegates to PermissionService"""
        try:
            from app.core.permission.service import PermissionService
            return PermissionService.has_permission(user, permission_name)
        except Exception as e:
            logging.error(f"Error checking permission '{permission_name}': {e}")
            return False
    
    @staticmethod
    def has_role(user, role_name):
        """التحقق من دور المستخدم"""
        try:
            return user.role == role_name
        except Exception as e:
            logging.error(f"Error checking role '{role_name}': {e}")
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
                user = db.session.get(User, user)
            if not user:
                return []
            if getattr(user, 'is_admin_user', None) and user.is_admin_user():
                return None

            ids = []
            try:
                from sqlalchemy import inspect
                insp = inspect(db.engine)
                if insp.has_table('roles') and insp.has_table('department_permissions'):
                    from models.permissions import Role
                    from models.advanced_permissions import DepartmentPermission
                    role = Role.query.filter_by(name=user.role, is_active=True).first()
                    if role:
                        global_row = DepartmentPermission.query.filter_by(role_id=role.id, department_id=None).first()
                        if global_row and global_row.can_access:
                            return None
                        rows = DepartmentPermission.query.filter_by(role_id=role.id).filter(DepartmentPermission.department_id.isnot(None), DepartmentPermission.can_access == True).all()
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
                extra = UserDepartmentAccess.query.filter_by(user_id=user.id, can_access=True).all()
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
                user = db.session.get(User, user)
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
                    from models.permissions import Role
                    from models.advanced_permissions import DepartmentPermission
                    role = Role.query.filter_by(name=user.role, is_active=True).first()
                    if not role:
                        return True
                    has_any = (DepartmentPermission.query.filter_by(role_id=role.id).count() or 0) > 0
                    if not has_any:
                        return True
                    global_row = DepartmentPermission.query.filter_by(role_id=role.id, department_id=None).first()
                    row = DepartmentPermission.query.filter_by(role_id=role.id, department_id=dep_id).first()
                    if action == 'access':
                        return bool((row and row.can_access) or (global_row and global_row.can_access))
                    if action == 'patients':
                        return bool((row and row.can_manage_patients) or (global_row and global_row.can_manage_patients))
                    if action == 'visits':
                        return bool((row and row.can_manage_visits) or (global_row and global_row.can_manage_visits))
                    if action == 'appointments':
                        return bool((row and row.can_manage_appointments) or (global_row and global_row.can_manage_appointments))
                    if action == 'staff':
                        return bool((row and row.can_manage_staff) or (global_row and global_row.can_manage_staff))
                    if action == 'settings':
                        return bool((row and row.can_manage_department_settings) or (global_row and global_row.can_manage_department_settings))
            except Exception:
                pass

            return True
        except Exception:
            return False

