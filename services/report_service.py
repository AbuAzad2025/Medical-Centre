"""
خدمة إدارة التقارير - Report Management Service
Medical System Report Management Service
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, or_, func, desc, asc, text
from app_factory import db
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.payment import Payment
from models.invoice import Invoice, InvoiceService
from models.user import User
from models.department import Department
import logging

class ReportService:
    """خدمة إدارة التقارير والإحصائيات"""
    
    @staticmethod
    def get_dashboard_summary(start_date=None, end_date=None, department_id=None):
        """الحصول على ملخص لوحة التحكم"""
        try:
            # تحديد الفترة الزمنية
            if not start_date:
                start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if not end_date:
                end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # إحصائيات المرضى
            patients_query = Patient.query
            if department_id:
                patients_query = patients_query.join(Visit).filter(Visit.department_id == department_id)
            
            total_patients = patients_query.count()
            new_patients_today = patients_query.filter(
                func.date(Patient.created_at) == func.current_date()
            ).count()
            
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
            completed_visits = visits_query.filter(Visit.status == 'COMPLETED').count()
            pending_visits = visits_query.filter(Visit.status == 'OPEN').count()
            
            # إحصائيات المواعيد
            appointments_query = Appointment.query.filter(
                and_(
                    func.date(Appointment.starts_at) >= start_date.date(),
                    func.date(Appointment.starts_at) <= end_date.date()
                )
            )
            
            if department_id:
                appointments_query = appointments_query.filter(Appointment.department_id == department_id)
            
            total_appointments = appointments_query.count()
            completed_appointments = appointments_query.filter(Appointment.status == 'DONE').count()
            cancelled_appointments = appointments_query.filter(Appointment.status == 'CANCELLED').count()
            
            # الإحصائيات المالية
            payments_query = Payment.query.filter(
                and_(
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date
                )
            )
            
            if department_id:
                payments_query = payments_query.join(Visit).filter(Visit.department_id == department_id)
            
            total_revenue = payments_query.with_entities(func.sum(Payment.amount)).scalar() or 0
            cash_payments = payments_query.filter(Payment.method == 'CASH').with_entities(func.sum(Payment.amount)).scalar() or 0
            insurance_payments = payments_query.filter(Payment.method == 'INSURANCE').with_entities(func.sum(Payment.amount)).scalar() or 0
            
            return {
                'success': True,
                'summary': {
                    'patients': {
                        'total': total_patients,
                        'new_today': new_patients_today
                    },
                    'visits': {
                        'total': total_visits,
                        'completed': completed_visits,
                        'pending': pending_visits
                    },
                    'appointments': {
                        'total': total_appointments,
                        'completed': completed_appointments,
                        'cancelled': cancelled_appointments
                    },
                    'financial': {
                        'total_revenue': total_revenue,
                        'cash_payments': cash_payments,
                        'insurance_payments': insurance_payments
                    }
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting dashboard summary: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب ملخص لوحة التحكم حالياً'}
    
    @staticmethod
    def get_patient_report(patient_id, start_date=None, end_date=None):
        """تقرير المريض"""
        try:
            patient = db.session.get(Patient, patient_id)
            if not patient:
                return {'success': False, 'message': 'المريض غير موجود'}
            
            # تحديد الفترة الزمنية
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now() + timedelta(days=1)
            
            # الزيارات
            visits = Visit.query.filter(
                and_(
                    Visit.patient_id == patient_id,
                    Visit.visit_date >= start_date.date(),
                    Visit.visit_date <= end_date.date()
                )
            ).order_by(Visit.visit_date.desc()).all()
            
            # المواعيد
            appointments = Appointment.query.filter(
                and_(
                    Appointment.patient_id == patient_id,
                    func.date(Appointment.starts_at) >= start_date.date(),
                    func.date(Appointment.starts_at) <= end_date.date()
                )
            ).order_by(Appointment.starts_at.desc()).all()
            
            # المدفوعات
            payments = Payment.query.filter(
                and_(
                    Payment.visit_id.in_([v.id for v in visits]),
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date
                )
            ).order_by(Payment.payment_date.desc()).all()
            
            # التحاليل
            lab_requests = []
            for visit in visits:
                lab_requests.extend(visit.lab_requests)
            
            # الأشعة
            radiology_requests = []
            for visit in visits:
                radiology_requests.extend(visit.radiology_requests)
            
            return {
                'success': True,
                'patient': patient.to_dict(),
                'visits': [visit.to_dict() for visit in visits],
                'appointments': [appointment.to_dict() for appointment in appointments],
                'payments': [payment.to_dict() for payment in payments],
                'lab_requests': [request.to_dict() for request in lab_requests],
                'radiology_requests': [request.to_dict() for request in radiology_requests],
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting patient report: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب تقرير المريض حالياً'}
    
    @staticmethod
    def get_department_report(department_id, start_date=None, end_date=None):
        """تقرير القسم"""
        try:
            department = db.session.get(Department, department_id)
            if not department:
                return {'success': False, 'message': 'القسم غير موجود'}
            
            # تحديد الفترة الزمنية
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now() + timedelta(days=1)
            
            # الزيارات
            visits = Visit.query.filter(
                and_(
                    Visit.department_id == department_id,
                    Visit.visit_date >= start_date.date(),
                    Visit.visit_date <= end_date.date()
                )
            ).order_by(Visit.visit_date.desc()).all()
            
            # المواعيد
            appointments = Appointment.query.filter(
                and_(
                    Appointment.department_id == department_id,
                    func.date(Appointment.starts_at) >= start_date.date(),
                    func.date(Appointment.starts_at) <= end_date.date()
                )
            ).order_by(Appointment.starts_at.desc()).all()
            
            # الأطباء
            doctors = User.query.filter(
                and_(
                    User.department_id == department_id,
                    User.role == 'doctor',
                    User.is_active == True
                )
            ).all()
            
            # الإحصائيات
            total_visits = len(visits)
            completed_visits = len([v for v in visits if v.status == 'COMPLETED'])
            pending_visits = len([v for v in visits if v.status == 'OPEN'])
            
            total_appointments = len(appointments)
            completed_appointments = len([a for a in appointments if a.status == 'DONE'])
            cancelled_appointments = len([a for a in appointments if a.status == 'CANCELLED'])
            
            return {
                'success': True,
                'department': department.to_dict(),
                'visits': [visit.to_dict() for visit in visits],
                'appointments': [appointment.to_dict() for appointment in appointments],
                'doctors': [doctor.to_dict() for doctor in doctors],
                'statistics': {
                    'total_visits': total_visits,
                    'completed_visits': completed_visits,
                    'pending_visits': pending_visits,
                    'total_appointments': total_appointments,
                    'completed_appointments': completed_appointments,
                    'cancelled_appointments': cancelled_appointments
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting department report: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب تقرير القسم حالياً'}
    
    @staticmethod
    def get_financial_report(start_date=None, end_date=None, department_id=None):
        """التقرير المالي"""
        try:
            # تحديد الفترة الزمنية
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()
            
            # المدفوعات
            payments_query = Payment.query.filter(
                and_(
                    Payment.payment_date >= start_date,
                    Payment.payment_date <= end_date
                )
            )
            
            if department_id:
                payments_query = payments_query.join(Visit).filter(Visit.department_id == department_id)
            
            payments = payments_query.all()
            
            # الفواتير
            invoices_query = Invoice.query.filter(
                and_(
                    Invoice.created_at >= start_date,
                    Invoice.created_at <= end_date
                )
            )
            
            if department_id:
                invoices_query = invoices_query.join(InvoiceService).filter(InvoiceService.department_id == department_id)
            
            invoices = invoices_query.all()
            
            # الإحصائيات المالية
            total_revenue = sum(payment.amount for payment in payments)
            cash_revenue = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CASH')
            insurance_revenue = sum(p.amount for p in payments if getattr(p, 'method', None) == 'INSURANCE')
            card_revenue = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CARD')
            
            # حسب اليوم
            daily_revenue = {}
            for payment in payments:
                date_str = payment.payment_date.strftime('%Y-%m-%d')
                if date_str not in daily_revenue:
                    daily_revenue[date_str] = 0
                daily_revenue[date_str] += payment.amount
            
            # حسب طريقة الدفع
            payment_methods = {}
            for payment in payments:
                method = getattr(payment, 'method', None)
                if method not in payment_methods:
                    payment_methods[method] = 0
                payment_methods[method] += payment.amount
            
            return {
                'success': True,
                'summary': {
                    'total_revenue': total_revenue,
                    'cash_revenue': cash_revenue,
                    'insurance_revenue': insurance_revenue,
                    'card_revenue': card_revenue,
                    'daily_revenue': daily_revenue,
                    'payment_methods': payment_methods
                },
                'payments': [payment.to_dict() for payment in payments],
                'invoices': [invoice.to_dict() for invoice in invoices],
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting financial report: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب التقرير المالي حالياً'}
    
    @staticmethod
    def get_doctor_performance_report(doctor_id, start_date=None, end_date=None):
        """تقرير أداء الطبيب"""
        try:
            doctor = db.session.get(User, doctor_id)
            if not doctor or doctor.role != 'doctor':
                return {'success': False, 'message': 'الطبيب غير موجود'}
            
            # تحديد الفترة الزمنية
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now() + timedelta(days=1)
            
            # الزيارات
            visits = Visit.query.filter(
                and_(
                    Visit.doctor_id == doctor_id,
                    Visit.visit_date >= start_date.date(),
                    Visit.visit_date <= end_date.date()
                )
            ).order_by(Visit.visit_date.desc()).all()
            
            # المواعيد
            appointments = Appointment.query.filter(
                and_(
                    Appointment.doctor_id == doctor_id,
                    func.date(Appointment.starts_at) >= start_date.date(),
                    func.date(Appointment.starts_at) <= end_date.date()
                )
            ).order_by(Appointment.starts_at.desc()).all()
            
            # الإحصائيات
            total_visits = len(visits)
            completed_visits = len([v for v in visits if v.status == 'COMPLETED'])
            pending_visits = len([v for v in visits if v.status in {'OPEN','IN_PROGRESS'}])
            
            total_appointments = len(appointments)
            completed_appointments = len([a for a in appointments if a.status == 'DONE'])
            cancelled_appointments = len([a for a in appointments if a.status == 'CANCELLED'])
            
            # الإيرادات
            total_revenue = sum(visit.total_amount for visit in visits if visit.total_amount)
            paid_revenue = sum(visit.paid_amount for visit in visits if visit.paid_amount)
            
            return {
                'success': True,
                'doctor': doctor.to_dict(),
                'visits': [visit.to_dict() for visit in visits],
                'appointments': [appointment.to_dict() for appointment in appointments],
                'statistics': {
                    'total_visits': total_visits,
                    'completed_visits': completed_visits,
                    'pending_visits': pending_visits,
                    'total_appointments': total_appointments,
                    'completed_appointments': completed_appointments,
                    'cancelled_appointments': cancelled_appointments,
                    'total_revenue': total_revenue,
                    'paid_revenue': paid_revenue
                },
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting doctor performance report: {str(e)}")
            return {'success': False, 'message': 'تعذر جلب تقرير أداء الطبيب حالياً'}
    
    @staticmethod
    def export_report(report_type, data, format='json'):
        """تصدير التقرير"""
        try:
            if format == 'json':
                return {'success': True, 'data': data}
            elif format == 'csv':
                # تحويل إلى CSV
                import csv
                import io
                
                output = io.StringIO()
                if data and len(data) > 0:
                    writer = csv.DictWriter(output, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                
                return {'success': True, 'data': output.getvalue()}
            else:
                return {'success': False, 'message': 'تنسيق التصدير غير مدعوم'}
                
        except Exception as e:
            logging.error(f"Error exporting report: {str(e)}")
            return {'success': False, 'message': 'تعذر تصدير التقرير حالياً'}
    
    # ==================== تقارير التدقيق (الأسبوع الثاني) ====================
    
    @staticmethod
    def get_daily_audit_report(target_date=None):
        """
        تقرير التدقيق اليومي - Daily Audit Report
        يشمل جميع العمليات المالية والزيارات لليوم المحدد
        """
        try:
            # تحديد التاريخ — نستخدم قاعدة البيانات لتجنب اختلاف التوقيت
            if not target_date:
                target_date = db.session.execute(func.current_date()).scalar()
            elif isinstance(target_date, datetime):
                target_date = target_date.date()
            
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
            # ========== 1. إحصائيات الزيارات ==========
            visits_today = Visit.query.filter(
                func.date(Visit.created_at) == target_date
            ).all()
            
            visits_stats = {
                'total': len(visits_today),
                'by_status': {
                    'OPEN': len([v for v in visits_today if v.status == 'OPEN']),
                    'IN_PROGRESS': len([v for v in visits_today if v.status == 'IN_PROGRESS']),
                    'COMPLETED': len([v for v in visits_today if v.status == 'COMPLETED']),
                    'ARCHIVED': len([v for v in visits_today if v.status == 'ARCHIVED'])
                },
                'by_type': {
                    'REGULAR': len([v for v in visits_today if v.visit_type == 'REGULAR']),
                    'FOLLOW_UP': len([v for v in visits_today if v.visit_type == 'FOLLOW_UP']),
                    'CONSULTATION': len([v for v in visits_today if v.visit_type == 'CONSULTATION']),
                    'EMERGENCY': len([v for v in visits_today if v.visit_type == 'EMERGENCY'])
                }
            }
            
            # ========== 2. إحصائيات الدفع ==========
            payments_today = Payment.query.filter(
                and_(
                    Payment.created_at >= start_time,
                    Payment.created_at <= end_time
                )
            ).all()
            
            # حساب المبالغ حسب طريقة الدفع
            payment_by_method = {}
            for payment in payments_today:
                method = payment.method
                if method not in payment_by_method:
                    payment_by_method[method] = {'count': 0, 'amount': 0}
                payment_by_method[method]['count'] += 1
                payment_by_method[method]['amount'] += float(payment.amount)
            
            # حساب المبالغ حسب الحالة
            payment_by_status = {}
            for payment in payments_today:
                status = payment.status
                if status not in payment_by_status:
                    payment_by_status[status] = {'count': 0, 'amount': 0}
                payment_by_status[status]['count'] += 1
                payment_by_status[status]['amount'] += float(payment.amount)
            
            total_collected = sum(float(p.amount) for p in payments_today if p.status == 'CONFIRMED')
            total_pending = sum(float(p.amount) for p in payments_today if p.status == 'PENDING')
            total_cancelled = sum(float(p.amount) for p in payments_today if p.status == 'CANCELLED')
            
            payment_stats = {
                'total_transactions': len(payments_today),
                'total_collected': total_collected,
                'total_pending': total_pending,
                'total_cancelled': total_cancelled,
                'by_method': payment_by_method,
                'by_status': payment_by_status
            }
            
            # ========== 3. إحصائيات الدفع القسري ==========
            force_payments_today = Visit.query.filter(
                and_(
                    func.date(Visit.created_at) == target_date,
                    Visit.is_force_payment == True
                )
            ).all()
            
            force_approved = [v for v in force_payments_today if v.force_payment_approved_by]
            force_pending = [v for v in force_payments_today if not v.force_payment_approved_by]
            
            force_payment_stats = {
                'total': len(force_payments_today),
                'approved': len(force_approved),
                'pending': len(force_pending),
                'percentage': round(len(force_payments_today) / len(visits_today) * 100, 2) if visits_today else 0,
                'list': [
                    {
                        'visit_id': v.id,
                        'patient_id': v.patient_id,
                        'reason': v.force_payment_reason,
                        'approved_by': v.force_payment_approved_by,
                        'approved_at': v.force_payment_approved_at.isoformat() if v.force_payment_approved_at else None
                    } for v in force_payments_today
                ]
            }
            
            # ========== 4. إحصائيات التأمين ==========
            insurance_visits_today = [v for v in visits_today if (getattr(v, 'payment_method', '') or '').lower() == 'insurance']
            
            total_insurance_amount = sum(float(v.insurance_amount or 0) for v in insurance_visits_today)
            total_patient_share = sum(float(v.patient_share or 0) for v in insurance_visits_today)
            patient_share_collected = sum(float(v.paid_amount or 0) for v in insurance_visits_today)
            
            insurance_stats = {
                'total_visits': len(insurance_visits_today),
                'total_insurance_amount': total_insurance_amount,
                'total_patient_share': total_patient_share,
                'patient_share_collected': patient_share_collected,
                'patient_share_pending': total_patient_share - patient_share_collected,
                'by_provider': {}
            }
            
            # تجميع حسب مزود التأمين
            for visit in insurance_visits_today:
                provider = (visit.insurance_company.name_ar if getattr(visit, 'insurance_company', None) else None) or visit.insurance_provider or 'غير محدد'
                if provider not in insurance_stats['by_provider']:
                    insurance_stats['by_provider'][provider] = {
                        'count': 0,
                        'total_amount': 0,
                        'patient_share': 0
                    }
                insurance_stats['by_provider'][provider]['count'] += 1
                insurance_stats['by_provider'][provider]['total_amount'] += float(visit.insurance_amount or 0)
                insurance_stats['by_provider'][provider]['patient_share'] += float(visit.patient_share or 0)
            
            # ========== 5. قضايا التدقيق (Issues) ==========
            audit_issues = []
            
            # التحقق من زيارات بدون دفع
            unpaid_visits = [v for v in visits_today if v.payment_status == 'PENDING' and not v.is_force_payment]
            if unpaid_visits:
                audit_issues.append({
                    'type': 'UNPAID_VISITS',
                    'severity': 'MEDIUM',
                    'count': len(unpaid_visits),
                    'message': f'{len(unpaid_visits)} زيارة بدون دفع',
                    'details': [{'visit_id': v.id, 'patient_id': v.patient_id} for v in unpaid_visits]
                })
            
            # التحقق من دفع قسري بدون موافقة
            if force_pending:
                audit_issues.append({
                    'type': 'FORCE_PAYMENT_PENDING',
                    'severity': 'HIGH',
                    'count': len(force_pending),
                    'message': f'{len(force_pending)} دفع قسري بانتظار الموافقة',
                    'details': [{'visit_id': v.id, 'reason': v.force_payment_reason} for v in force_pending]
                })
            
            # التحقق من دفعات ملغاة
            cancelled_payments = [p for p in payments_today if p.status == 'CANCELLED']
            if cancelled_payments:
                audit_issues.append({
                    'type': 'CANCELLED_PAYMENTS',
                    'severity': 'MEDIUM',
                    'count': len(cancelled_payments),
                    'message': f'{len(cancelled_payments)} دفعة ملغاة',
                    'details': [
                        {
                            'payment_id': p.id,
                            'amount': float(p.amount),
                            'cancelled_by': p.cancelled_by,
                            'reason': p.cancellation_reason
                        } for p in cancelled_payments
                    ]
                })
            
            # التحقق من مبالغ كبيرة نقدية
            large_cash_payments = [p for p in payments_today if p.method == 'CASH' and float(p.amount) > 1000]
            if large_cash_payments:
                audit_issues.append({
                    'type': 'LARGE_CASH_PAYMENTS',
                    'severity': 'LOW',
                    'count': len(large_cash_payments),
                    'message': f'{len(large_cash_payments)} دفعة نقدية كبيرة (> 1000 شيكل)',
                    'details': [{'payment_id': p.id, 'amount': float(p.amount)} for p in large_cash_payments]
                })
            
            # ========== 6. النتيجة النهائية ==========
            return {
                'success': True,
                'date': target_date.isoformat(),
                'report_generated_at': datetime.now().isoformat(),
                'visits': visits_stats,
                'payments': payment_stats,
                'force_payments': force_payment_stats,
                'insurance': insurance_stats,
                'audit_issues': audit_issues,
                'summary': {
                    'total_visits': len(visits_today),
                    'total_collected': total_collected,
                    'force_payment_percentage': force_payment_stats['percentage'],
                    'insurance_visits': len(insurance_visits_today),
                    'issues_count': len(audit_issues)
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating daily audit report: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': 'تعذر إنشاء تقرير التدقيق اليومي حالياً'
            }
    
    @staticmethod
    def get_monthly_audit_report(year=None, month=None):
        """
        تقرير التدقيق الشهري - Monthly Audit Report
        يشمل ملخص كامل للشهر المحدد
        """
        try:
            # تحديد الشهر والسنة
            if not year:
                year = datetime.now().year
            if not month:
                month = datetime.now().month
            
            # تحديد بداية ونهاية الشهر
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(seconds=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(seconds=1)
            
            # ========== 1. إحصائيات الزيارات الشهرية ==========
            visits_month = Visit.query.filter(
                and_(
                    Visit.created_at >= start_date,
                    Visit.created_at <= end_date
                )
            ).all()
            
            visits_by_day = {}
            for visit in visits_month:
                day = visit.created_at.day
                if day not in visits_by_day:
                    visits_by_day[day] = 0
                visits_by_day[day] += 1
            
            visits_stats = {
                'total': len(visits_month),
                'by_status': {
                    'OPEN': len([v for v in visits_month if v.status == 'OPEN']),
                    'IN_PROGRESS': len([v for v in visits_month if v.status == 'IN_PROGRESS']),
                    'COMPLETED': len([v for v in visits_month if v.status == 'COMPLETED']),
                    'ARCHIVED': len([v for v in visits_month if v.status == 'ARCHIVED'])
                },
                'by_payment_method': {
                    'cash': len([v for v in visits_month if (getattr(v, 'payment_method', '') or '').lower() == 'cash']),
                    'visa': len([v for v in visits_month if (getattr(v, 'payment_method', '') or '').lower() in ['visa', 'card']]),
                    'insurance': len([v for v in visits_month if (getattr(v, 'payment_method', '') or '').lower() == 'insurance']),
                    'force': len([v for v in visits_month if (getattr(v, 'payment_method', '') or '').lower() == 'force' or v.is_force_payment])
                },
                'by_day': visits_by_day,
                'avg_per_day': round(len(visits_month) / (end_date.day), 2)
            }
            
            # ========== 2. إحصائيات المبالغ المالية ==========
            payments_month = Payment.query.filter(
                and_(
                    Payment.created_at >= start_date,
                    Payment.created_at <= end_date,
                    Payment.status == 'CONFIRMED'
                )
            ).all()
            
            total_revenue = sum(float(p.amount) for p in payments_month)
            cash_revenue = sum(float(p.amount) for p in payments_month if p.method == 'CASH')
            card_revenue = sum(float(p.amount) for p in payments_month if p.method == 'CARD')
            insurance_revenue = sum(float(p.amount) for p in payments_month if p.method == 'INSURANCE')
            
            # الإيرادات اليومية
            daily_revenue = {}
            for payment in payments_month:
                day = payment.created_at.day
                if day not in daily_revenue:
                    daily_revenue[day] = 0
                daily_revenue[day] += float(payment.amount)
            
            financial_stats = {
                'total_revenue': total_revenue,
                'cash_revenue': cash_revenue,
                'card_revenue': card_revenue,
                'insurance_revenue': insurance_revenue,
                'total_transactions': len(payments_month),
                'avg_transaction': round(total_revenue / len(payments_month), 2) if payments_month else 0,
                'daily_revenue': daily_revenue,
                'avg_daily_revenue': round(total_revenue / (end_date.day), 2)
            }
            
            # ========== 3. تحليل الدفع القسري ==========
            force_visits_month = [v for v in visits_month if v.is_force_payment]
            force_approved = [v for v in force_visits_month if v.force_payment_approved_by]
            force_rejected = [v for v in force_visits_month if not v.force_payment_approved_by and v.status == 'ARCHIVED']
            force_pending = [v for v in force_visits_month if not v.force_payment_approved_by and v.status != 'ARCHIVED']
            
            force_payment_analysis = {
                'total': len(force_visits_month),
                'approved': len(force_approved),
                'rejected': len(force_rejected),
                'pending': len(force_pending),
                'percentage_of_visits': round(len(force_visits_month) / len(visits_month) * 100, 2) if visits_month else 0,
                'approval_rate': round(len(force_approved) / len(force_visits_month) * 100, 2) if force_visits_month else 0,
                'total_amount': sum(float(v.total_amount or 0) for v in force_visits_month),
                'collected_amount': sum(float(v.paid_amount or 0) for v in force_approved)
            }
            
            # ========== 4. تحليل التأمين ==========
            insurance_visits_month = [v for v in visits_month if (getattr(v, 'payment_method', '') or '').lower() == 'insurance']
            
            total_insurance_billed = sum(float(v.insurance_amount or 0) for v in insurance_visits_month)
            total_patient_share = sum(float(v.patient_share or 0) for v in insurance_visits_month)
            patient_share_collected = sum(float(v.paid_amount or 0) for v in insurance_visits_month)
            
            insurance_analysis = {
                'total_visits': len(insurance_visits_month),
                'percentage_of_visits': round(len(insurance_visits_month) / len(visits_month) * 100, 2) if visits_month else 0,
                'total_billed_to_insurance': total_insurance_billed,
                'total_patient_share': total_patient_share,
                'patient_share_collected': patient_share_collected,
                'patient_share_pending': total_patient_share - patient_share_collected,
                'collection_rate': round(patient_share_collected / total_patient_share * 100, 2) if total_patient_share > 0 else 0
            }
            
            # ========== 5. KPIs الشهرية ==========
            kpis = {
                'collection_rate': round(total_revenue / sum(float(v.total_amount or 0) for v in visits_month) * 100, 2) if visits_month else 0,
                'force_payment_percentage': force_payment_analysis['percentage_of_visits'],
                'avg_visit_value': round(total_revenue / len(visits_month), 2) if visits_month else 0,
                'completed_visits_rate': round(visits_stats['by_status']['COMPLETED'] / len(visits_month) * 100, 2) if visits_month else 0,
                'patient_share_collection_rate': insurance_analysis['collection_rate']
            }
            
            # التحقق من تجاوز الحدود
            kpi_alerts = []
            if kpis['force_payment_percentage'] > 5:
                kpi_alerts.append({
                    'kpi': 'force_payment_percentage',
                    'value': kpis['force_payment_percentage'],
                    'threshold': 5,
                    'message': 'تجاوزت نسبة الدفع القسري الحد المسموح (5%)'
                })
            
            if kpis['collection_rate'] < 90:
                kpi_alerts.append({
                    'kpi': 'collection_rate',
                    'value': kpis['collection_rate'],
                    'threshold': 90,
                    'message': 'نسبة التحصيل أقل من الهدف (90%)'
                })
            
            # ========== 6. الديون المعلقة ==========
            debts = Visit.query.filter(
                and_(
                    Visit.created_at >= start_date,
                    Visit.created_at <= end_date,
                    Visit.payment_status == 'DEBT'
                )
            ).all()
            
            debt_analysis = {
                'total_debts': len(debts),
                'total_amount': sum(float(v.remaining_amount) for v in debts),
                'by_reason': {},
                'oldest_debt': min([v.created_at for v in debts]).isoformat() if debts else None
            }
            
            # ========== 7. النتيجة النهائية ==========
            return {
                'success': True,
                'period': {
                    'year': year,
                    'month': month,
                    'month_name': start_date.strftime('%B'),
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': end_date.day
                },
                'report_generated_at': datetime.now().isoformat(),
                'visits': visits_stats,
                'financial': financial_stats,
                'force_payments': force_payment_analysis,
                'insurance': insurance_analysis,
                'kpis': kpis,
                'kpi_alerts': kpi_alerts,
                'debts': debt_analysis,
                'summary': {
                    'total_visits': len(visits_month),
                    'total_revenue': total_revenue,
                    'collection_rate': kpis['collection_rate'],
                    'force_payment_percentage': kpis['force_payment_percentage'],
                    'alerts_count': len(kpi_alerts)
                }
            }
            
        except Exception as e:
            logging.error(f"Error generating monthly audit report: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': 'تعذر إنشاء تقرير التدقيق الشهري حالياً'
            }
    
    @staticmethod
    def get_debt_tracking_report():
        """
        تقرير تتبع الديون - Debt Tracking Report
        يشمل جميع الديون المعلقة والمتأخرة
        """
        try:
            # الديون المعلقة
            pending_debts = Visit.query.filter(
                or_(
                    Visit.payment_status == 'DEBT',
                    and_(
                        Visit.payment_status == 'PENDING',
                        Visit.is_force_payment == True,
                        Visit.force_payment_approved_by != None
                    )
                )
            ).all()
            
            # تصنيف الديون حسب العمر
            debts_by_age = {
                '0-7_days': [],
                '8-30_days': [],
                '31-60_days': [],
                '60+_days': []
            }
            
            today = datetime.now()
            for debt in pending_debts:
                age = (today - debt.created_at).days
                remaining = float(debt.remaining_amount)
                
                debt_info = {
                    'visit_id': debt.id,
                    'patient_id': debt.patient_id,
                    'patient_name': getattr(getattr(debt, 'patient', None), 'full_name', None),
                    'patient_phone': getattr(getattr(debt, 'patient', None), 'phone', None),
                    'visit_date': debt.visit_date.isoformat() if getattr(debt, 'visit_date', None) else None,
                    'department_name': getattr(getattr(debt, 'department', None), 'name_ar', None),
                    'created_at': debt.created_at.isoformat(),
                    'age_days': age,
                    'total_amount': float(debt.total_amount or 0),
                    'paid_amount': float(debt.paid_amount or 0),
                    'remaining_amount': remaining,
                    'payment_method': debt.payment_method,
                    'is_force_payment': debt.is_force_payment
                }
                
                if age <= 7:
                    debts_by_age['0-7_days'].append(debt_info)
                elif age <= 30:
                    debts_by_age['8-30_days'].append(debt_info)
                elif age <= 60:
                    debts_by_age['31-60_days'].append(debt_info)
                else:
                    debts_by_age['60+_days'].append(debt_info)
            
            # حساب المبالغ
            total_debt = sum(float(d.remaining_amount) for d in pending_debts)
            debt_by_age_amounts = {
                key: sum(d['remaining_amount'] for d in debts)
                for key, debts in debts_by_age.items()
            }
            
            return {
                'success': True,
                'report_date': datetime.now().isoformat(),
                'summary': {
                    'total_debts': len(pending_debts),
                    'total_amount': total_debt,
                    'by_age_count': {key: len(debts) for key, debts in debts_by_age.items()},
                    'by_age_amount': debt_by_age_amounts
                },
                'debts_by_age': debts_by_age,
                'oldest_debt_days': max([d['age_days'] for debts in debts_by_age.values() for d in debts]) if pending_debts else 0
            }
            
        except Exception as e:
            logging.error(f"Error generating debt tracking report: {str(e)}", exc_info=True)
            return {
                'success': False,
                'message': 'تعذر إنشاء تقرير تتبع الديون حالياً'
            }

    @staticmethod
    def get_slow_queries_report(limit=10):
        try:
            reset_time = None
            try:
                reset_time = db.session.execute(text("select reset_time from pg_stat_statements_info")).scalar()
            except Exception:
                reset_time = None

            rows = db.session.execute(text("""
                select
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                from pg_stat_statements
                where query not ilike '%pg_stat_statements%'
                order by mean_time desc
                limit :limit
            """), {'limit': int(limit)}).mappings().all()

            queries = []
            for r in rows:
                queries.append({
                    'query': r.get('query'),
                    'calls': int(r.get('calls') or 0),
                    'total_time': float(r.get('total_time') or 0),
                    'mean_time': float(r.get('mean_time') or 0),
                    'rows': int(r.get('rows') or 0)
                })

            return {
                'success': True,
                'reset_time': reset_time.isoformat() if reset_time else None,
                'queries': queries
            }
        except Exception as e:
            logging.error(f"Error generating slow queries report: {str(e)}")
            return {
                'success': False,
                'message': 'تعذر إنشاء تقرير الاستعلامات البطيئة حالياً'
            }

    @staticmethod
    def capture_weekly_slow_queries(limit=10, created_by=None):
        try:
            report = ReportService.get_slow_queries_report(limit=limit)
            if not report or not report.get('success'):
                return report
            now = datetime.now(timezone.utc)
            period_end = now
            period_start = now - timedelta(days=7)
            from models.audit_trail import SlowQueryReport, SlowQueryEntry
            rq = SlowQueryReport(
                period_start=period_start,
                period_end=period_end,
                reset_time=report.get('reset_time'),
                created_by=created_by
            )
            db.session.add(rq)
            db.session.flush()
            for row in report.get('queries') or []:
                db.session.add(SlowQueryEntry(
                    report_id=rq.id,
                    query=row.get('query') or '',
                    calls=int(row.get('calls') or 0),
                    total_time=row.get('total_time') or 0,
                    mean_time=row.get('mean_time') or 0,
                    rows=int(row.get('rows') or 0)
                ))
            db.session.commit()
            return {'success': True, 'report_id': rq.id}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error capturing weekly slow queries: {str(e)}")
            return {'success': False, 'message': 'تعذر حفظ تقرير الاستعلامات الأسبوعي'}
