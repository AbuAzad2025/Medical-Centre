 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from app_factory import db
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP

manager_bp = Blueprint('manager', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@manager_bp.before_request
def _guard_reporting_module():
    guard_module('reporting')


















def get_smart_analytics():
    """التحليلات الذكية للمانجر"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.payment import Payment
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # تحليل النمو
        patients_this_week = Patient.query.filter(Patient.created_at >= week_ago).count()
        patients_last_week = Patient.query.filter(
            Patient.created_at >= week_ago - timedelta(days=7),
            Patient.created_at < week_ago
        ).count()
        
        growth_rate = ((patients_this_week - patients_last_week) / patients_last_week * 100) if patients_last_week > 0 else 0
        
        # تحليل الإيرادات
        revenue_this_week = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= week_ago
        ).scalar() or 0
        
        revenue_last_week = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= (week_ago - timedelta(days=7)),
            func.date(Payment.payment_date) < week_ago
        ).scalar() or 0
        
        revenue_growth = ((revenue_this_week - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else 0
        
        completion_rate = (Visit.query.filter(Visit.status == VisitState.ARCHIVED).count() / Visit.query.count() * 100) if Visit.query.count() > 0 else 0
        avg_visit_minutes = 0.0
        try:
            avg_seconds = db.session.query(
                func.avg(func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at) - Visit.created_at))
            ).filter(
                Visit.created_at.isnot(None),
                func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
            ).scalar()
            avg_visit_minutes = float(avg_seconds or 0) / 60.0
        except Exception:
            try:
                avg_days = db.session.query(
                    func.avg(func.julianday(func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.julianday(Visit.created_at))
                ).filter(
                    Visit.created_at.isnot(None),
                    func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
                ).scalar()
                avg_visit_minutes = float((avg_days or 0) * 1440)
            except Exception:
                avg_visit_minutes = 0.0
        
        return {
            'patient_growth_rate': round(growth_rate, 2),
            'revenue_growth_rate': round(revenue_growth, 2),
            'avg_visit_duration': round(avg_visit_minutes, 2),
            'completion_rate': round(completion_rate, 2),
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting smart analytics: {str(e)}")
        return {}

def get_business_insights():
    """رؤى الأعمال الذكية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.payment import Payment
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        insights = []
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        except Exception:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 10:
                insights.append({
                    'type': 'peak_hours',
                    'title': 'ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 هي الأكثر ازدحاماً مع {max_hour.count} زيارة',
                    'recommendation': 'توزيع المواعيد على ساعات أخرى لتقليل الازدحام'
                })
        
        # تحليل الأداء المالي
        total_revenue = db.session.query(func.sum(Payment.amount)).scalar() or 0
        avg_revenue_per_visit = total_revenue / Visit.query.count() if Visit.query.count() > 0 else 0
        
        if avg_revenue_per_visit > 100:
            insights.append({
                'type': 'financial',
                'title': 'الأداء المالي',
                'description': f'متوسط الإيراد لكل زيارة: {avg_revenue_per_visit:.2f} ريال',
                'recommendation': 'الأداء المالي ممتاز - يمكن زيادة الخدمات'
            })
        
        # تحليل الموظفين
        active_staff = User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)).count()
        total_staff = User.query.count()
        staff_engagement = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        if staff_engagement < 70:
            insights.append({
                'type': 'staff',
                'title': 'مشاركة الموظفين',
                'description': f'معدل مشاركة الموظفين: {staff_engagement:.1f}%',
                'recommendation': 'تحسين مشاركة الموظفين من خلال التدريب والتطوير'
            })
        
        return insights
    except Exception as e:
        logging.error(f"Error getting business insights: {str(e)}")
        return []

def get_performance_metrics():
    """مقاييس الأداء الذكية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # معدل الإنجاز
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == VisitState.ARCHIVED).count()
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # معدل المواعيد
        total_appointments = Appointment.query.count()
        completed_appointments = Appointment.query.filter(Appointment.status == AppointmentState.DONE).count()
        appointment_rate = (completed_appointments / total_appointments * 100) if total_appointments > 0 else 0
        
        avg_wait_minutes = 0.0
        try:
            avg_seconds = db.session.query(
                func.avg(func.extract('epoch', Visit.completed_at - Visit.created_at))
            ).filter(Visit.completed_at.isnot(None)).scalar()
            avg_wait_minutes = float(avg_seconds or 0) / 60.0
        except Exception:
            avg_days = db.session.query(
                func.avg(func.julianday(Visit.completed_at) - func.julianday(Visit.created_at))
            ).filter(Visit.completed_at.isnot(None)).scalar()
            avg_wait_minutes = float((avg_days or 0) * 1440)
        
        # معدل الرضا (محاكاة)
        satisfaction_rate = min(100, max(0, completion_rate + (100 - completion_rate) * 0.3))
        
        return {
            'completion_rate': round(completion_rate, 2),
            'appointment_rate': round(appointment_rate, 2),
            'avg_wait_time': round(avg_wait_minutes, 2),
            'satisfaction_rate': round(satisfaction_rate, 2),
            'overall_score': round((completion_rate + appointment_rate + satisfaction_rate) / 3, 2)
        }
    except Exception as e:
        logging.error(f"Error getting performance metrics: {str(e)}")
        return {}

def get_financial_forecasting():
    """التنبؤ المالي الذكي"""
    try:
        from models.payment import Payment
        from models.visit import Visit
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل الإيرادات التاريخية
        week_ago = datetime.now().date() - timedelta(days=7)
        month_ago = datetime.now().date() - timedelta(days=30)
        
        revenue_this_week = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= week_ago
        ).scalar() or 0
        
        revenue_last_week = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= week_ago - timedelta(days=7),
            Payment.payment_date < week_ago
        ).scalar() or 0
        
        # حساب معدل النمو
        growth_rate = ((revenue_this_week - revenue_last_week) / revenue_last_week * 100) if revenue_last_week > 0 else 0
        
        # التنبؤ بالأسبوع القادم
        predicted_next_week = revenue_this_week * (1 + growth_rate/100)
        
        # التنبؤ الشهري
        monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) >= month_ago
        ).scalar() or 0
        
        predicted_monthly = monthly_revenue * (1 + growth_rate/100)
        
        return {
            'current_week_revenue': revenue_this_week,
            'growth_rate': round(growth_rate, 2),
            'predicted_next_week': round(predicted_next_week, 2),
            'monthly_revenue': monthly_revenue,
            'predicted_monthly': round(predicted_monthly, 2),
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting financial forecasting: {str(e)}")
        return {}

def get_operational_efficiency():
    """كفاءة العمليات"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل الكفاءة حسب الأقسام
        try:
            department_efficiency = db.session.query(
                func.count(Visit.id).label('visits'),
                func.avg(func.extract('epoch', Visit.completed_at - Visit.created_at)).label('avg_seconds'),
                User.department_id
            ).join(User, Visit.doctor_id == User.id).filter(Visit.completed_at.isnot(None)).group_by(User.department_id).all()
            department_efficiency = [
                type('Row', (), {'visits': d.visits, 'avg_duration': float(d.avg_seconds or 0), 'department_id': d.department_id})
                for d in department_efficiency
            ]
        except Exception:
            dept_eff = db.session.query(
                func.count(Visit.id).label('visits'),
                func.avg(func.julianday(Visit.completed_at) - func.julianday(Visit.created_at)).label('avg_days'),
                User.department_id
            ).join(User, Visit.doctor_id == User.id).filter(Visit.completed_at.isnot(None)).group_by(User.department_id).all()
            department_efficiency = [
                type('Row', (), {'visits': d.visits, 'avg_duration': float((d.avg_days or 0) * 86400), 'department_id': d.department_id})
                for d in dept_eff
            ]
        
        # تحليل استخدام الموارد
        resource_utilization = {
            'total_doctors': User.query.filter(User.role == 'doctor').count(),
            'active_doctors': User.query.filter(
                User.role == 'doctor',
                User.last_login >= datetime.now() - timedelta(days=7)
            ).count(),
            'total_visits_today': Visit.query.filter(
                func.date(Visit.created_at) == datetime.now().date()
            ).count()
        }
        
        # حساب معدل الكفاءة
        if resource_utilization['total_doctors'] > 0:
            efficiency_rate = (resource_utilization['active_doctors'] / resource_utilization['total_doctors'] * 100)
        else:
            efficiency_rate = 0
        
        return {
            'department_efficiency': [
                {
                    'department_id': dept.department_id,
                    'visits': dept.visits,
                    'avg_duration': round(dept.avg_duration or 0, 2)
                } for dept in department_efficiency
            ],
            'resource_utilization': resource_utilization,
            'efficiency_rate': round(efficiency_rate, 2),
            'status': 'optimal' if efficiency_rate > 80 else 'good' if efficiency_rate > 60 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting operational efficiency: {str(e)}")
        return {}

def get_staff_productivity():
    """إنتاجية الموظفين"""
    try:
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل إنتاجية الأطباء
        doctor_productivity = db.session.query(
            User.id,
            User.full_name,
            func.count(Visit.id).label('total_visits'),
            func.avg(Visit.duration).label('avg_duration')
        ).join(Visit, User.id == Visit.doctor_id).filter(
            Visit.created_at >= datetime.now().date() - timedelta(days=30)
        ).group_by(User.id, User.full_name).all()
        
        # تحليل النشاط
        active_staff = User.query.filter(
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_staff = User.query.count()
        engagement_rate = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        return {
            'doctor_productivity': [
                {
                    'doctor_id': doc.id,
                    'doctor_name': doc.full_name,
                    'total_visits': doc.total_visits,
                    'avg_duration': round(doc.avg_duration or 0, 2)
                } for doc in doctor_productivity
            ],
            'engagement_rate': round(engagement_rate, 2),
            'active_staff': active_staff,
            'total_staff': total_staff,
            'status': 'excellent' if engagement_rate > 90 else 'good' if engagement_rate > 70 else 'needs_attention'
        }
    except Exception as e:
        logging.error(f"Error getting staff productivity: {str(e)}")
        return {}

def get_patient_satisfaction():
    """رضا المرضى (محاكاة)"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        # محاكاة معدل الرضا بناءً على البيانات المتاحة
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == VisitState.ARCHIVED).count()
        
        # حساب معدل الرضا بناءً على معدل الإنجاز
        base_satisfaction = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # إضافة عوامل أخرى
        avg_duration = db.session.query(func.avg(Visit.duration)).scalar() or 0
        duration_factor = max(0, 100 - (avg_duration / 60 * 10))  # تقليل الرضا مع زيادة الوقت
        
        # حساب الرضا النهائي
        satisfaction_score = (base_satisfaction + duration_factor) / 2
        
        return {
            'satisfaction_score': round(satisfaction_score, 2),
            'base_satisfaction': round(base_satisfaction, 2),
            'duration_factor': round(duration_factor, 2),
            'status': 'excellent' if satisfaction_score > 90 else 'good' if satisfaction_score > 70 else 'needs_improvement',
            'recommendations': [
                'تحسين أوقات الانتظار' if avg_duration > 30 else 'الأداء ممتاز',
                'زيادة معدل إنجاز الزيارات' if base_satisfaction < 80 else 'معدل الإنجاز جيد'
            ]
        }
    except Exception as e:
        logging.error(f"Error getting patient satisfaction: {str(e)}")
        return {}

def get_resource_optimization():
    """تحسين الموارد"""
    try:
        from models.visit import Visit
        from models.user import User
        from models.patient import Patient
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        optimizations = []
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        except Exception:
            peak_hours = db.session.query(
                func.extract('hour', Visit.visit_time).label('hour'),
                func.count(Visit.id).label('count')
            ).group_by(func.extract('hour', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 15:
                optimizations.append({
                    'type': 'peak_hours',
                    'title': 'توزيع ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 مزدحمة جداً ({max_hour.count} زيارة)',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل الأقسام
        department_load = db.session.query(
            func.count(Visit.id).label('count'),
            User.department_id
        ).join(User, Visit.doctor_id == User.id).group_by(User.department_id).all()
        
        if department_load:
            max_dept = max(department_load, key=lambda x: x.count)
            if max_dept.count > 20:
                optimizations.append({
                    'type': 'department_load',
                    'title': 'توزيع الأحمال',
                    'description': f'القسم {max_dept.department_id} مزدحم ({max_dept.count} زيارة)',
                    'suggestion': 'إضافة موارد إضافية أو إعادة توزيع الأحمال'
                })
        
        # تحليل الموظفين
        active_doctors = User.query.filter(
            User.role == 'doctor',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_doctors = User.query.filter(User.role == 'doctor').count()
        
        if active_doctors < total_doctors * 0.8:
            optimizations.append({
                'type': 'staff_utilization',
                'title': 'استخدام الموظفين',
                'description': f'فقط {active_doctors} من {total_doctors} طبيب نشط',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting resource optimization: {str(e)}")
        return []









def get_bi_insights():
    try:
        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        visits_30d = Visit.query.filter(Visit.created_at >= start_30d).count()
        completed_30d = Visit.query.filter(Visit.status == VisitState.ARCHIVED, Visit.created_at >= start_30d).count()
        appointments_30d = Appointment.query.filter(Appointment.starts_at >= start_30d).count()
        no_show = Appointment.query.filter(Appointment.status == 'no_show', Appointment.starts_at >= start_30d).count()
        cancel = Appointment.query.filter(Appointment.status == 'cancelled', Appointment.starts_at >= start_30d).count()
        conversion_rate = (completed_30d / visits_30d * 100) if visits_30d else 0
        no_show_rate = (no_show / appointments_30d * 100) if appointments_30d else 0
        cancel_rate = (cancel / appointments_30d * 100) if appointments_30d else 0
        return {
            'visits_30d': int(visits_30d or 0),
            'completed_30d': int(completed_30d or 0),
            'appointments_30d': int(appointments_30d or 0),
            'conversion_rate': round(conversion_rate, 2),
            'no_show_rate': round(no_show_rate, 2),
            'cancel_rate': round(cancel_rate, 2)
        }
    except Exception:
        return {}

# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import pricing
from . import staff
from . import reports
from . import financial
from . import approvals
from . import departments
from . import satisfaction
from . import api
from . import settings
