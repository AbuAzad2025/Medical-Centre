"""
خدمة التقارير المتقدمة - Advanced Report Service
Medical System Advanced Report Service
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, select

from app.extensions import db
from app.shared.enums import AppointmentState, InvoiceStatus, VisitArchiveStatus, VisitState
from models.appointment import Appointment
from models.audit_trail import AuditTrail, SecurityEvent, SystemLog
from models.department import Department
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit


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
            patients_query = select(Patient)

            if department_id:
                patients_query = patients_query.join(Visit).filter(
                    Visit.department_id == department_id
                )

            patients = db.session.execute(patients_query).scalars().all()
            total_patients = len(patients)
            new_patients = total_patients

            gender_stats = {
                'M': sum(1 for p in patients if p.gender == 'M'),
                'F': sum(1 for p in patients if p.gender == 'F'),
            }

            def _age_years(birth_date):
                if not birth_date:
                    return None
                today = datetime.now().date()
                years = today.year - birth_date.year
                if (today.month, today.day) < (birth_date.month, birth_date.day):
                    years -= 1
                return years

            ages = [_age_years(p.birth_date) for p in patients]
            age_groups = {
                '0-18': sum(1 for a in ages if a is not None and 0 <= a <= 18),
                '19-35': sum(1 for a in ages if a is not None and 19 <= a <= 35),
                '36-50': sum(1 for a in ages if a is not None and 36 <= a <= 50),
                '51-65': sum(1 for a in ages if a is not None and 51 <= a <= 65),
                '65+': sum(1 for a in ages if a is not None and a > 65),
            }

            active_count = 0
            for p in patients:
                vcnt = db.session.execute(
                    select(func.count())
                    .select_from(Visit)
                    .filter(
                        and_(
                            Visit.patient_id == p.id,
                            Visit.visit_date >= start_date.date(),
                            Visit.visit_date <= end_date.date(),
                        )
                    )
                ).scalar()
                if vcnt > 0:
                    active_count += 1
            status_stats = {
                'active': active_count,
                'inactive': max(total_patients - active_count, 0),
            }

            return {
                'success': True,
                'analytics': {
                    'total_patients': total_patients,
                    'new_patients': new_patients,
                    'gender_distribution': gender_stats,
                    'age_groups': age_groups,
                    'status_distribution': status_stats,
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating patient analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل بيانات المرضى حالياً'}

    @staticmethod
    def generate_visit_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل بيانات الزيارات"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()

            # إحصائيات الزيارات
            visits_query = select(Visit)

            if department_id:
                visits_query = visits_query.filter(Visit.department_id == department_id)

            total_visits = (
                db.session.execute(
                    select(func.count()).select_from(visits_query.subquery())
                ).scalar()
                or 0
            )

            # حسب الحالة
            status_stats = {}
            for status in [VisitState.OPEN, VisitState.COMPLETED]:
                count = (
                    db.session.execute(
                        select(func.count()).select_from(
                            visits_query.filter(Visit.status == status).subquery()
                        )
                    ).scalar()
                    or 0
                )
                status_stats[status] = count
            status_stats[VisitArchiveStatus.ARCHIVED] = (
                db.session.execute(
                    select(func.count()).select_from(
                        visits_query.filter(
                            Visit.archive_status == VisitArchiveStatus.ARCHIVED
                        ).subquery()
                    )
                ).scalar()
                or 0
            )

            # حسب نوع الزيارة
            visit_type_stats = {}
            for visit_type in ['CONSULTATION', 'FOLLOW_UP', 'EMERGENCY', 'REGULAR']:
                count = (
                    db.session.execute(
                        select(func.count()).select_from(
                            visits_query.filter(Visit.visit_type == visit_type).subquery()
                        )
                    ).scalar()
                    or 0
                )
                visit_type_stats[visit_type] = count

            # حسب الوجهة
            destination_stats = {}
            # لا يوجد حقل destination في نموذج الزيارة الحالي؛ يتم تجاوز هذا القسم

            # حسب اليوم
            daily_stats = {}
            for i in range((end_date - start_date).days + 1):
                date = start_date + timedelta(days=i)
                count = (
                    db.session.execute(
                        select(func.count()).select_from(
                            visits_query.filter(Visit.visit_date == date.date()).subquery()
                        )
                    ).scalar()
                    or 0
                )
                daily_stats[date.strftime('%Y-%m-%d')] = count

            return {
                'success': True,
                'analytics': {
                    'total_visits': total_visits,
                    'status_distribution': status_stats,
                    'visit_type_distribution': visit_type_stats,
                    'destination_distribution': destination_stats,
                    'daily_visits': daily_stats,
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating visit analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل بيانات الزيارات حالياً'}

    @staticmethod
    def generate_financial_analytics(start_date=None, end_date=None, department_id=None):
        """تحليل البيانات المالية"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()

            # إحصائيات المدفوعات
            payments_query = select(Payment)

            if department_id:
                payments_query = payments_query.join(Visit).filter(
                    Visit.department_id == department_id
                )

            total_payments = (
                db.session.execute(
                    select(func.count()).select_from(payments_query.subquery())
                ).scalar()
                or 0
            )
            total_revenue = (
                db.session.execute(
                    select(func.coalesce(func.sum(Payment.amount), 0)).select_from(
                        payments_query.subquery()
                    )
                ).scalar()
                or 0
            )

            # حسب طريقة الدفع
            payment_method_stats = {}
            for method in ['CASH', 'CARD', 'INSURANCE', 'WIRE']:
                count = (
                    db.session.execute(
                        select(func.count()).select_from(
                            payments_query.filter(Payment.method == method).subquery()
                        )
                    ).scalar()
                    or 0
                )
                amount = (
                    db.session.execute(
                        select(func.coalesce(func.sum(Payment.amount), 0)).select_from(
                            payments_query.filter(Payment.method == method).subquery()
                        )
                    ).scalar()
                    or 0
                )
                payment_method_stats[method] = {'count': count, 'amount': float(amount)}

            # حسب اليوم
            daily_revenue = {}
            for i in range((end_date - start_date).days + 1):
                date = start_date + timedelta(days=i)
                amount = (
                    db.session.execute(
                        select(func.coalesce(func.sum(Payment.amount), 0)).filter(
                            and_(
                                Payment.payment_date >= date,
                                Payment.payment_date < date + timedelta(days=1),
                            )
                        )
                    ).scalar()
                    or 0
                )
                daily_revenue[date.strftime('%Y-%m-%d')] = amount

            # إحصائيات الفواتير
            invoices_query = select(Invoice)

            if department_id:
                invoices_query = invoices_query.join(InvoiceService).filter(
                    InvoiceService.department_id == department_id
                )

            total_invoices = (
                db.session.execute(
                    select(func.count()).select_from(invoices_query.subquery())
                ).scalar()
                or 0
            )
            total_invoice_amount = (
                db.session.execute(
                    select(func.coalesce(func.sum(Invoice.total_amount), 0)).select_from(
                        invoices_query.subquery()
                    )
                ).scalar()
                or 0
            )
            paid_invoices = (
                db.session.execute(
                    select(func.count()).select_from(
                        invoices_query.filter(Invoice.status == InvoiceStatus.PAID).subquery()
                    )
                ).scalar()
                or 0
            )
            pending_invoices = (
                db.session.execute(
                    select(func.count()).select_from(
                        invoices_query.filter(
                            Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.DRAFT])
                        ).subquery()
                    )
                ).scalar()
                or 0
            )

            return {
                'success': True,
                'analytics': {
                    'payments': {
                        'total_count': total_payments,
                        'total_revenue': total_revenue,
                        'method_distribution': payment_method_stats,
                        'daily_revenue': daily_revenue,
                    },
                    'invoices': {
                        'total_count': total_invoices,
                        'total_amount': total_invoice_amount,
                        'paid_count': paid_invoices,
                        'pending_count': pending_invoices,
                    },
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating financial analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل البيانات المالية حالياً'}

    @staticmethod
    def generate_doctor_performance_analytics(start_date=None, end_date=None, doctor_id=None):
        """تحليل أداء الأطباء"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()

            # إحصائيات الأطباء
            doctors_query = select(User)

            if doctor_id:
                doctors_query = doctors_query.filter(User.id == doctor_id)

            doctors = db.session.execute(doctors_query).scalars().all()
            doctor_performance = []

            for doctor in doctors:
                # زيارات الطبيب
                visits = (
                    db.session.execute(
                        select(Visit).filter(
                            and_(
                                Visit.doctor_id == doctor.id,
                                Visit.visit_date >= start_date.date(),
                                Visit.visit_date <= end_date.date(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                # مواعيد الطبيب
                appointments = (
                    db.session.execute(
                        select(Appointment).filter(
                            and_(
                                Appointment.doctor_id == doctor.id,
                                func.date(Appointment.starts_at) >= start_date.date(),
                                func.date(Appointment.starts_at) <= end_date.date(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                # الإحصائيات
                total_visits = len(visits)
                completed_visits = len([v for v in visits if v.status == VisitState.COMPLETED])
                total_appointments = len(appointments)
                completed_appointments = len(
                    [a for a in appointments if a.status == AppointmentState.DONE]
                )
                cancelled_appointments = len(
                    [a for a in appointments if a.status == AppointmentState.CANCELLED]
                )

                # الإيرادات
                total_revenue = sum(visit.total_amount for visit in visits if visit.total_amount)
                paid_revenue = sum(visit.paid_amount for visit in visits if visit.paid_amount)

                # معدل الإنجاز
                completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
                appointment_completion_rate = (
                    (completed_appointments / total_appointments * 100)
                    if total_appointments > 0
                    else 0
                )

                doctor_performance.append(
                    {
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
                        'paid_revenue': paid_revenue,
                    }
                )

            return {
                'success': True,
                'analytics': {
                    'doctor_performance': doctor_performance,
                    'total_doctors': len(doctors),
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating doctor performance analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل أداء الأطباء حالياً'}

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
                visits = (
                    db.session.execute(
                        select(Visit).filter(
                            and_(
                                Visit.department_id == department.id,
                                Visit.visit_date >= start_date.date(),
                                Visit.visit_date <= end_date.date(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                # مواعيد القسم
                appointments = (
                    db.session.execute(
                        select(Appointment).filter(
                            and_(
                                Appointment.department_id == department.id,
                                func.date(Appointment.starts_at) >= start_date.date(),
                                func.date(Appointment.starts_at) <= end_date.date(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

                # الإحصائيات
                total_visits = len(visits)
                completed_visits = len([v for v in visits if v.status == VisitState.COMPLETED])
                total_appointments = len(appointments)
                completed_appointments = len(
                    [a for a in appointments if a.status == AppointmentState.DONE]
                )

                # الإيرادات
                total_revenue = sum(visit.total_amount for visit in visits if visit.total_amount)
                paid_revenue = sum(visit.paid_amount for visit in visits if visit.paid_amount)

                # معدل الإنجاز
                completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
                appointment_completion_rate = (
                    (completed_appointments / total_appointments * 100)
                    if total_appointments > 0
                    else 0
                )

                department_analytics.append(
                    {
                        'department_id': department.id,
                        'department_name': department.name_ar,
                        'total_visits': total_visits,
                        'completed_visits': completed_visits,
                        'completion_rate': round(completion_rate, 2),
                        'total_appointments': total_appointments,
                        'completed_appointments': completed_appointments,
                        'appointment_completion_rate': round(appointment_completion_rate, 2),
                        'total_revenue': total_revenue,
                        'paid_revenue': paid_revenue,
                    }
                )

            return {
                'success': True,
                'analytics': {
                    'department_analytics': department_analytics,
                    'total_departments': len(departments),
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating department analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل بيانات الأقسام حالياً'}

    @staticmethod
    def generate_system_usage_analytics(start_date=None, end_date=None):
        """تحليل استخدام النظام"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()

            # إحصائيات المستخدمين
            users_query = select(User)

            total_users = (
                db.session.execute(
                    select(func.count()).select_from(users_query.subquery())
                ).scalar()
                or 0
            )
            active_users = (
                db.session.execute(
                    select(func.count()).select_from(
                        users_query.filter(User.is_active).subquery()
                    )
                ).scalar()
                or 0
            )

            # حسب الدور
            role_stats = {}
            for role in [
                'admin',
                'manager',
                'doctor',
                'nurse',
                'reception',
                'accountant',
                'lab',
                'radiology',
                'emergency',
            ]:
                count = (
                    db.session.execute(
                        select(func.count()).select_from(
                            users_query.filter(User.role == role).subquery()
                        )
                    ).scalar()
                    or 0
                )
                role_stats[role] = count

            # إحصائيات السجلات
            audit_trails = db.session.execute(
                select(func.count())
                .select_from(AuditTrail)
                .filter(
                    and_(AuditTrail.created_at >= start_date, AuditTrail.created_at <= end_date)
                )
            ).scalar()

            system_logs = db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(and_(SystemLog.created_at >= start_date, SystemLog.created_at <= end_date))
            ).scalar()

            security_events = db.session.execute(
                select(func.count())
                .select_from(SecurityEvent)
                .filter(
                    and_(
                        SecurityEvent.created_at >= start_date, SecurityEvent.created_at <= end_date
                    )
                )
            ).scalar()

            # إحصائيات الإشعارات
            # لا يوجد نموذج Notification؛ نستخدم SystemLog كبديل للإشعارات
            notifications = db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(and_(SystemLog.created_at >= start_date, SystemLog.created_at <= end_date))
            ).scalar()

            # نفترض أن unread = الأحداث من المستوى 'info' خلال الفترة
            unread_notifications = db.session.execute(
                select(func.count())
                .select_from(SystemLog)
                .filter(
                    and_(
                        SystemLog.created_at >= start_date,
                        SystemLog.created_at <= end_date,
                        SystemLog.log_level.in_(['INFO', 'WARNING']),
                    )
                )
            ).scalar()

            return {
                'success': True,
                'analytics': {
                    'total_users': total_users,
                    'active_users': active_users,
                    'users': {
                        'total': total_users,
                        'active': active_users,
                        'role_distribution': role_stats,
                    },
                    'logs': {
                        'audit_trails': audit_trails,
                        'system_logs': system_logs,
                        'security_events': security_events,
                    },
                    'notifications': {'total': notifications, 'unread': unread_notifications},
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
            }

        except Exception as e:
            logging.exception(f'Error generating system usage analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تحليل استخدام النظام حالياً'}

    @staticmethod
    def generate_comprehensive_report(start_date=None, end_date=None, department_id=None):
        """تقرير شامل"""
        try:
            if not start_date:
                start_date = datetime.now() - timedelta(days=30)
            if not end_date:
                end_date = datetime.now()

            # جمع جميع التحليلات
            patient_analytics = AdvancedReportService.generate_patient_analytics(
                start_date, end_date, department_id
            )
            visit_analytics = AdvancedReportService.generate_visit_analytics(
                start_date, end_date, department_id
            )
            financial_analytics = AdvancedReportService.generate_financial_analytics(
                start_date, end_date, department_id
            )
            doctor_performance = AdvancedReportService.generate_doctor_performance_analytics(
                start_date, end_date
            )
            department_analytics = AdvancedReportService.generate_department_analytics(
                start_date, end_date, department_id
            )
            system_usage = AdvancedReportService.generate_system_usage_analytics(
                start_date, end_date
            )

            return {
                'success': True,
                'comprehensive_report': {
                    'patient_analytics': patient_analytics.get('analytics', {}),
                    'visit_analytics': visit_analytics.get('analytics', {}),
                    'financial_analytics': financial_analytics.get('analytics', {}),
                    'doctor_performance': doctor_performance.get('analytics', {}),
                    'department_analytics': department_analytics.get('analytics', {}),
                    'system_usage': system_usage.get('analytics', {}),
                },
                'period': {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()},
                'generated_at': datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logging.exception(f'Error generating comprehensive report: {e!s}')
            return {'success': False, 'message': 'تعذر إنشاء التقرير الشامل حالياً'}

    @staticmethod
    def export_analytics(analytics_data, format='json'):
        """تصدير التحليلات"""
        try:
            if format == 'json':
                return {'success': True, 'data': analytics_data}
            if format == 'csv':
                # تحويل إلى CSV
                import csv
                import io

                output = io.StringIO()
                if analytics_data and len(analytics_data) > 0:
                    writer = csv.DictWriter(output, fieldnames=analytics_data[0].keys())
                    writer.writeheader()
                    writer.writerows(analytics_data)

                return {'success': True, 'data': output.getvalue()}
            return {'success': False, 'message': 'تنسيق التصدير غير مدعوم'}

        except Exception as e:
            logging.exception(f'Error exporting analytics: {e!s}')
            return {'success': False, 'message': 'تعذر تصدير التحليلات حالياً'}
