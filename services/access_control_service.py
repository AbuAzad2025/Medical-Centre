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
from models.radiology_test import RadiologyResult
from app_factory import db
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import abort

class AccessControlService:
    """خدمة التحكم في الوصول المحسنة"""
    
    # تعريف الصلاحيات لكل دور
    ROLE_PERMISSIONS = {
        'admin': [
            'manage_users', 'manage_departments', 'manage_roles',
            'view_all_visits', 'view_financial_reports', 'system_settings',
            'modify_archived_visits', 'pricing_management', 'audit_trail',
            'view_all_patients', 'view_all_reports'
        ],
        'manager': [
            'manage_doctors', 'view_financial_reports', 'pricing_management',
            'view_all_visits', 'audit_trail', 'view_all_patients'
        ],
        'doctor': [
            'view_own_visits', 'diagnose_patients', 'prescribe_medications',
            'request_lab_tests', 'request_radiology', 'search_patient_archive',
            'complete_visits', 'view_own_patients'
        ],
        'reception': [
            'create_visits', 'process_payments', 'archive_visits',
            'manage_patients', 'print_receipts', 'manage_queues',
            'modify_visits_30min', 'search_patient_archive', 'view_all_visits'
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
    def has_permission(user_id, permission):
        """التحقق من وجود صلاحية معينة"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            # المدير له جميع الصلاحيات
            if user.is_admin_user():
                return True
            
            # التحقق من صلاحيات الدور
            user_permissions = AccessControlService.ROLE_PERMISSIONS.get(user.role, [])
            return permission in user_permissions
            
        except Exception as e:
            logging.error(f"Error checking permission: {str(e)}")
            return False
    
    @staticmethod
    def can_access_visit(user_id, visit_id):
        """التحقق من إمكانية الوصول لزيارة معينة"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            visit = Visit.query.get(visit_id)
            if not visit:
                return False
            
            # المدير والمدير العام والاستقبال يمكنهم الوصول لجميع الزيارات
            if user.is_admin_user() or user.role == 'reception':
                return True
            
            # الأطباء يمكنهم الوصول لزياراتهم فقط
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return True
            
            # المختبر والأشعة يمكنهم الوصول للزيارات الموجهة لهم
            if user.role == 'lab' and visit.requested_labs:
                return True
            elif user.role == 'radiology' and visit.requested_radiology:
                return True
            
            # الطوارئ يمكنهم الوصول لحالات الطوارئ
            if user.role == 'emergency' and visit.status == 'EMERGENCY':
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking visit access: {str(e)}")
            return False
    
    @staticmethod
    def can_modify_visit(user_id, visit_id):
        """التحقق من إمكانية تعديل زيارة"""
        try:
            user = User.query.get(user_id)
            if not user:
                return False
            
            visit = Visit.query.get(visit_id)
            if not visit:
                return False
            
            # المدير فقط يمكنه تعديل الزيارات المؤرشفة
            if visit.status == 'ARCHIVED':
                return user.is_admin_user()
            
            # الاستقبال يمكنه تعديل الزيارات خلال 30 دقيقة
            if user.role == 'reception':
                if visit.created_at:
                    time_diff = datetime.utcnow() - visit.created_at
                    return time_diff <= timedelta(minutes=30)
            
            # الأطباء يمكنهم تعديل زياراتهم غير المؤرشفة
            if user.role == 'doctor' and visit.doctor_id == user.id:
                return visit.status != 'ARCHIVED'
            
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
            user = User.query.get(user_id)
            if not user:
                return []
            
            # المدير والمدير العام والاستقبال يمكنهم رؤية جميع الزيارات
            if user.is_admin_user() or user.role == 'reception':
                return Visit.query.all()
            
            # الأطباء يرون زياراتهم فقط
            if user.role == 'doctor':
                return Visit.query.filter_by(doctor_id=user.id).all()
            
            # المختبر والأشعة يرون الزيارات الموجهة لهم
            if user.role == 'lab':
                return Visit.query.filter(Visit.requested_labs.isnot(None)).all()
            elif user.role == 'radiology':
                return Visit.query.filter(Visit.requested_radiology.isnot(None)).all()
            
            # الطوارئ يرون حالات الطوارئ
            if user.role == 'emergency':
                return Visit.query.filter_by(status='EMERGENCY').all()
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting accessible visits: {str(e)}")
            return []
    
    @staticmethod
    def get_user_accessible_patients(user_id):
        """الحصول على المرضى المتاحين للمستخدم"""
        try:
            user = User.query.get(user_id)
            if not user:
                return []
            
            # المدير والمدير العام والاستقبال يمكنهم رؤية جميع المرضى
            if user.is_admin_user() or user.role == 'reception':
                return Patient.query.all()
            
            # الأطباء يرون مرضاهم فقط
            if user.role == 'doctor':
                return Patient.query.join(Visit).filter(Visit.doctor_id == user.id).distinct().all()
            
            # الممرضين يرون مرضى الأطباء الذين يعملون معهم
            if user.role == 'nurse':
                # يمكن تطوير هذا لاحقاً حسب العلاقات
                return Patient.query.all()
            
            return []
            
        except Exception as e:
            logging.error(f"Error getting accessible patients: {str(e)}")
            return []
    
    @staticmethod
    def get_user_dashboard_route(user_id):
        """الحصول على مسار لوحة التحكم حسب الدور"""
        try:
            user = User.query.get(user_id)
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
            user = User.query.get(user_id)
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
        """التحقق من وجود صلاحية للمستخدم"""
        try:
            # التحقق من الصلاحيات المبنية على الدور
            if user.role in AccessControlService.ROLE_PERMISSIONS:
                return permission_name in AccessControlService.ROLE_PERMISSIONS[user.role]
            return False
            
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

