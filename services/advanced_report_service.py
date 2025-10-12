"""
خدمة التقارير المتقدمة - Advanced Report Service
Medical System Advanced Report Service
"""

from datetime import datetime, timedelta
from sqlalchemy import and_, or_, func, desc, asc, text
from app_factory import db
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.payment import Payment
from models.invoice import Invoice
from models.user import User
from models.department import Department
from models.lab_request import LabRequest
from models.radiology_test import RadiologyResult
from models.audit_trail import SystemLog
from models.audit_trail import AuditTrail, SystemLog, SecurityEvent
import logging
import json

class AdvancedReportService:
    """خدمة التقارير المتقدمة"""
    
    @staticmethod
    def generate_patient_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل بيانات المرضى"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات المرضى
            patients_query = Patient.query.filter(
                and_(
                    Patient.created_at >= start_date,
                    Patient.created_at <= end_date
                )
            )
            
            if department_id:
                patients_query = patients_query.join(Visit).filter(Visit.department_id == department_id)
            
            total_patients = patients_query.count()
            new_patients = patients_query.filter(Patient.is_active == True).count()
            
            # حسب الجنس
            gender_stats = {}
            for gender in ['M', 'F']:
                count = patients_query.filter(Patient.gender == gender).count()
                gender_stats[gender] = count
            
            # حسب العمر
            age_groups = {
                '0-18': patients_query.filter(Patient.age.between(0, 18)).count(),
                '19-35': patients_query.filter(Patient.age.between(19, 35)).count(),
                '36-50': patients_query.filter(Patient.age.between(36, 50)).count(),
                '51-65': patients_query.filter(Patient.age.between(51, 65)).count(),
                '65+': patients_query.filter(Patient.age > 65).count()
            }
            
            # حسب الحالة
            status_stats = {
                'active': patients_query.filter(Patient.is_active == True).count(),
                'inactive': patients_query.filter(Patient.is_active == False).count()
            }
            
            return {
                'success': True,
                'analytics': {
                    'total_patients': total_patients,
                    'new_patients': new_patients,
                    'gender_distribution': gender_stats,
                    'age_groups': age_groups,
                    'status_distribution': status_stats
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating patient analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل بيانات المرضى: {str(e)}'}
    
    @staticmethod
    def generate_visit_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل بيانات الزيارات"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات الزيارات
            visits_query = Visit.query.filter(
                and_(
                    Visit.visit_date >= start_date.date(),
                    Visit.visit_date <= end_date.date()
                )
            )
            
            if department_id:
                visits_query = visits_query.filter(Visit.department_id == department_id)
            
            total_visits = visits_query.count()
            
            # حسب الحالة
            status_stats = {}
            for status in ['pending', 'completed', 'cancelled']:
                count = visits_query.filter(Visit.status == status).count()
                status_stats[status] = count
            
            # حسب نوع الزيارة
            visit_type_stats = {}
            for visit_type in ['consultation', 'follow_up', 'emergency', 'examination']:
                count = visits_query.filter(Visit.visit_type == visit_type).count()
                visit_type_stats[visit_type] = count
            
            # حسب الوجهة
            destination_stats = {}
            for destination in ['doctor', 'lab', 'radiology', 'emergency']:
                count = visits_query.filter(Visit.destination == destination).count()
                destination_stats[destination] = count
            
            # حسب اليوم
            daily_stats = {}
            for i in range((end_date - start_date).days + 1):
                date = start_date + timedelta(days=i)
                count = visits_query.filter(Visit.visit_date == date.date()).count()
                daily_stats[date.strftime('%Y-%m-%d')] = count
            
            return {
                'success': True,
                'analytics': {
                    'total_visits': total_visits,
                    'status_distribution': status_stats,
                    'visit_type_distribution': visit_type_stats,
                    'destination_distribution': destination_stats,
                    'daily_visits': daily_stats
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating visit analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل بيانات الزيارات: {str(e)}'}
    
    @staticmethod
    def generate_financial_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل البيانات المالية"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات المدفوعات
            payments_query = Payment.query.filter(
                and_(
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date
                )
            )
            
            if department_id:
                payments_query = payments_query.join(Visit).filter(Visit.department_id == department_id)
            
            total_payments = payments_query.count()
            total_revenue = payments_query.with_entities(func.sum(Payment.amount)).scalar() or 0
            
            # حسب طريقة الدفع
            payment_method_stats = {}
            for method in ['cash', 'card', 'insurance', 'bank_transfer']:
                count = payments_query.filter(Payment.payment_method == method).count()
                amount = payments_query.filter(Payment.payment_method == method).with_entities(func.sum(Payment.amount)).scalar() or 0
                payment_method_stats[method] = {'count': count, 'amount': amount}
            
            # حسب اليوم
            daily_revenue = {}
            for i in range((end_date - start_date).days + 1):
                date = start_date + timedelta(days=i)
                amount = payments_query.filter(
                    and_(
                        Payment.payment_date >= date,
                        Payment.payment_date < date + timedelta(days=1)
                    )
                ).with_entities(func.sum(Payment.amount)).scalar() or 0
                daily_revenue[date.strftime('%Y-%m-%d')] = amount
            
            # إحصائيات الفواتير
            invoices_query = Invoice.query.filter(
                and_(
                    Invoice.created_at >= start_date,
                    Invoice.created_at <= end_date
                )
            )
            
            if department_id:
                invoices_query = invoices_query.join(InvoiceService).filter(InvoiceService.department_id == department_id)
            
            total_invoices = invoices_query.count()
            total_invoice_amount = invoices_query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
            paid_invoices = invoices_query.filter(Invoice.status == 'PAID').count()
            pending_invoices = invoices_query.filter(Invoice.status == 'PENDING').count()
            
            return {
                'success': True,
                'analytics': {
                    'payments': {
                        'total_count': total_payments,
                        'total_revenue': total_revenue,
                        'method_distribution': payment_method_stats,
                        'daily_revenue': daily_revenue
                    },
                    'invoices': {
                        'total_count': total_invoices,
                        'total_amount': total_invoice_amount,
                        'paid_count': paid_invoices,
                        'pending_count': pending_invoices
                    }
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating financial analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل البيانات المالية: {str(e)}'}
    
    @staticmethod
    def generate_doctor_performance_analytics(start_date=None, end_date=None, doctor_id=None):
        """تحليل أداء الأطباء"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات الأطباء
            doctors_query = User.query.filter(User.role == 'doctor')
            
            if doctor_id:
                doctors_query = doctors_query.filter(User.id == doctor_id)
            
            doctors = doctors_query.all()
            doctor_performance = []
            
            for doctor in doctors:
                # زيارات الطبيب
                visits = Visit.query.filter(
                    and_(
                        Visit.doctor_id == doctor.id,
                        Visit.visit_date >= start_date.date(),
                        Visit.visit_date <= end_date.date()
                    )
                ).all()
                
                # مواعيد الطبيب
                appointments = Appointment.query.filter(
                    and_(
                        Appointment.doctor_id == doctor.id,
                        Appointment.appointment_date >= start_date.date(),
                        Appointment.appointment_date <= end_date.date()
                    )
                ).all()
                
                # الإحصائيات
                total_visits = len(visits)
                completed_visits = len([v for v in visits if v.status == 'completed'])
                total_appointments = len(appointments)
                completed_appointments = len([a for a in appointments if a.status == 'completed'])
                cancelled_appointments = len([a for a in appointments if a.status == 'cancelled'])
                
                # الإيرادات
                total_revenue = sum(visit.total_amount for visit in visits if visit.total_amount)
                paid_revenue = sum(visit.paid_amount for visit in visits if visit.paid_amount)
                
                # معدل الإنجاز
                completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
                appointment_completion_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
                
                doctor_performance.append({
                    'doctor_id': doctor.id,
                    'doctor_name': doctor.full_name,
                    'department': doctor.department.name_ar if doctor.department else None,
                    'total_visits': total_visits,
                    'completed_visits': completed_visits,
                    'completion_rate': round(completion_rate, 2),
                    'total_appointments': total_appointments,
                    'completed_appointments': completed_appointments,
                    'cancelled_appointments': cancelled_appointments,
                    'appointment_completion_rate': round(appointment_completion_rate, 2),
                    'total_revenue': total_revenue,
                    'paid_revenue': paid_revenue
                })
            
            return {
                'success': True,
                'analytics': {
                    'doctor_performance': doctor_performance,
                    'total_doctors': len(doctors)
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating doctor performance analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل أداء الأطباء: {str(e)}'}
    
    @staticmethod
    def generate_department_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل بيانات الأقسام"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات الأقسام
            departments_query = Department.query
            
            if department_id:
                departments_query = departments_query.filter(Department.id == department_id)
            
            departments = departments_query.all()
            department_analytics = []
            
            for department in departments:
                # زيارات القسم
                visits = Visit.query.filter(
                    and_(
                        Visit.department_id == department.id,
                        Visit.visit_date >= start_date.date(),
                        Visit.visit_date <= end_date.date()
                    )
                ).all()
                
                # مواعيد القسم
                appointments = Appointment.query.filter(
                    and_(
                        Appointment.department_id == department.id,
                        Appointment.appointment_date >= start_date.date(),
                        Appointment.appointment_date <= end_date.date()
                    )
                ).all()
                
                # الإحصائيات
                total_visits = len(visits)
                completed_visits = len([v for v in visits if v.status == 'completed'])
                total_appointments = len(appointments)
                completed_appointments = len([a for a in appointments if a.status == 'completed'])
                
                # الإيرادات
                total_revenue = sum(visit.total_amount for visit in visits if visit.total_amount)
                paid_revenue = sum(visit.paid_amount for visit in visits if visit.paid_amount)
                
                # معدل الإنجاز
                completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
                appointment_completion_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
                
                department_analytics.append({
                    'department_id': department.id,
                    'department_name': department.name_ar,
                    'total_visits': total_visits,
                    'completed_visits': completed_visits,
                    'completion_rate': round(completion_rate, 2),
                    'total_appointments': total_appointments,
                    'completed_appointments': completed_appointments,
                    'appointment_completion_rate': round(appointment_completion_rate, 2),
                    'total_revenue': total_revenue,
                    'paid_revenue': paid_revenue
                })
            
            return {
                'success': True,
                'analytics': {
                    'department_analytics': department_analytics,
                    'total_departments': len(departments)
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating department analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل بيانات الأقسام: {str(e)}'}
    
    @staticmethod
    def generate_system_usage_analytics(start_date=None, end_date=None):
        """تحليل استخدام النظام"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # إحصائيات المستخدمين
            users_query = User.query.filter(
                and_(
                    User.created_at >= start_date,
                    User.created_at <= end_date
                )
            )
            
            total_users = users_query.count()
            active_users = users_query.filter(User.is_active == True).count()
            
            # حسب الدور
            role_stats = {}
            for role in ['admin', 'manager', 'doctor', 'nurse', 'reception', 'accountant', 'lab', 'radiology', 'emergency']:
                count = users_query.filter(User.role == role).count()
                role_stats[role] = count
            
            # إحصائيات السجلات
            audit_trails = AuditTrail.query.filter(
                and_(
                    AuditTrail.created_at >= start_date,
                    AuditTrail.created_at <= end_date
                )
            ).count()
            
            system_logs = SystemLog.query.filter(
                and_(
                    SystemLog.created_at >= start_date,
                    SystemLog.created_at <= end_date
                )
            ).count()
            
            security_events = SecurityEvent.query.filter(
                and_(
                    SecurityEvent.created_at >= start_date,
                    SecurityEvent.created_at <= end_date
                )
            ).count()
            
            # إحصائيات الإشعارات
            # لا يوجد نموذج Notification؛ نستخدم SystemLog كبديل للإشعارات
            notifications = SystemLog.query.filter(
                and_(
                    SystemLog.created_at >= start_date,
                    SystemLog.created_at <= end_date
                )
            ).count()
            
            # نفترض أن unread = الأحداث من المستوى 'info' خلال الفترة
            unread_notifications = SystemLog.query.filter(
                and_(
                    SystemLog.created_at >= start_date,
                    SystemLog.created_at <= end_date,
                    SystemLog.level.in_(['info','warning'])
                )
            ).count()
            
            return {
                'success': True,
                'analytics': {
                    'users': {
                        'total': total_users,
                        'active': active_users,
                        'role_distribution': role_stats
                    },
                    'logs': {
                        'audit_trails': audit_trails,
                        'system_logs': system_logs,
                        'security_events': security_events
                    },
                    'notifications': {
                        'total': notifications,
                        'unread': unread_notifications
                    }
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating system usage analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تحليل استخدام النظام: {str(e)}'}
    
    @staticmethod
    def generate_comprehensive_report(start_date=None, end_date=None, department_id=None):
        """تقرير شامل"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # جمع جميع التحليلات
            patient_analytics = AdvancedReportService.generate_patient_analytics(start_date, end_date, department_id)
            visit_analytics = AdvancedReportService.generate_visit_analytics(start_date, end_date, department_id)
            financial_analytics = AdvancedReportService.generate_financial_analytics(start_date, end_date, department_id)
            doctor_performance = AdvancedReportService.generate_doctor_performance_analytics(start_date, end_date)
            department_analytics = AdvancedReportService.generate_department_analytics(start_date, end_date, department_id)
            system_usage = AdvancedReportService.generate_system_usage_analytics(start_date, end_date)
            
            return {
                'success': True,
                'comprehensive_report': {
                    'patient_analytics': patient_analytics.get('analytics', {}),
                    'visit_analytics': visit_analytics.get('analytics', {}),
                    'financial_analytics': financial_analytics.get('analytics', {}),
                    'doctor_performance': doctor_performance.get('analytics', {}),
                    'department_analytics': department_analytics.get('analytics', {}),
                    'system_usage': system_usage.get('analytics', {})
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logging.error(f"Error generating comprehensive report: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في إنشاء التقرير الشامل: {str(e)}'}
    
    @staticmethod
    def export_analytics(analytics_data, format='json'):
        """تصدير التحليلات"""
        try:
            if format == 'json':
                return {'success': True, 'data': analytics_data}
            elif format == 'csv':
                # تحويل إلى CSV
                import csv
                import io
                
                output = io.StringIO()
                if analytics_data and len(analytics_data) > 0:
                    writer = csv.DictWriter(output, fieldnames=analytics_data[0].keys())
                    writer.writeheader()
                    writer.writerows(analytics_data)
                
                return {'success': True, 'data': output.getvalue()}
            else:
                return {'success': False, 'message': 'تنسيق التصدير غير مدعوم'}
                
        except Exception as e:
            logging.error(f"Error exporting analytics: {str(e)}")
            return {'success': False, 'message': f'حدث خطأ في تصدير التحليلات: {str(e)}'}
