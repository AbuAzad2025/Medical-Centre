"""dashboard routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask.typing import ResponseReturnValue
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
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
from services.manager_service import manager_service
from services.core_queries import core_queries
from app_factory import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# DASHBOARD ROUTES
# =============================================


@manager_bp.route('/dashboard')
@login_required
@role_required('manager', 'admin', 'super_admin')
def dashboard() -> ResponseReturnValue:
    """لوحة تحكم المدير"""
    
    
    try:
        # إحصائيات أساسية عبر CoreQueryService
        base_stats = core_queries.get_basic_dashboard_stats()
        total_patients = base_stats["total_patients"]
        total_visits = base_stats["total_visits"]
        total_users = base_stats["total_users"]
        # Note: new_patients_today, visits_today need today-specific queries
        today = date.today()
        this_month = today.replace(day=1)
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())
        
        new_patients_today = Patient.query.filter(
            Patient.created_at >= start_of_day,
            Patient.created_at <= end_of_day
        ).count()
        
        visits_today = Visit.query.filter(
            Visit.created_at >= start_of_day,
            Visit.created_at <= end_of_day
        ).count()
        completed_visits_today = Visit.query.filter(
            Visit.status == VisitState.ARCHIVED,
            Visit.completed_at >= datetime.combine(today, datetime.min.time())
        ).count()
        
        today_revenue = base_stats["revenue_today"]
        month_revenue = base_stats["revenue_month"]
        total_users = base_stats["total_users"]
        active_users = base_stats["active_users"]
        
        departments = core_queries.get_all_departments()

        smart_analytics = get_smart_analytics()
        business_insights = get_business_insights()
        performance_metrics = get_performance_metrics()
        financial_forecasting = get_financial_forecasting()
        bi_insights = get_bi_insights()

        start_30d = datetime.now(timezone.utc) - timedelta(days=30)
        end_now = datetime.now(timezone.utc)

        department_performance = []
        for dept in departments:
            dept_id = getattr(dept, 'id', None)
            if not dept_id:
                continue
            open_count = Visit.query.filter(Visit.department_id == dept_id, Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])).count()
            done_30d = Visit.query.filter(Visit.department_id == dept_id, Visit.status == VisitState.ARCHIVED, Visit.created_at >= start_30d).count()
            avg_sec = None
            try:
                avg_sec = db.session.query(
                    func.avg(
                        func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                    )
                ).filter(
                    Visit.department_id == dept_id,
                    Visit.status == VisitState.ARCHIVED,
                    Visit.created_at >= start_30d,
                    func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at).isnot(None)
                ).scalar()
            except Exception:
                db.session.rollback()
                avg_sec = None
            department_performance.append({
                'department_id': dept_id,
                'department_name': getattr(dept, 'name_ar', None) or getattr(dept, 'name', None) or str(dept_id),
                'open_visits': int(open_count or 0),
                'archived_30d': int(done_30d or 0),
                'avg_minutes_30d': (float(avg_sec or 0) / 60.0) if avg_sec is not None else 0.0
            })
        department_performance.sort(key=lambda x: (x.get('open_visits', 0), x.get('archived_30d', 0)), reverse=True)

        doctor_performance = []
        try:
            rows = db.session.query(
                User.id.label('doctor_id'),
                User.full_name.label('doctor_name'),
                func.count(Visit.id).label('archived_count'),
                func.avg(
                    func.extract('epoch', func.coalesce(Visit.archived_at, Visit.completed_at, Visit.updated_at)) - func.extract('epoch', Visit.created_at)
                ).label('avg_sec')
            ).join(
                Visit, Visit.doctor_id == User.id
            ).filter(
                User.role == 'doctor',
                Visit.status == VisitState.ARCHIVED,
                Visit.created_at >= start_30d
            ).group_by(User.id, User.full_name).order_by(func.count(Visit.id).desc()).limit(10).all()
            for r in rows:
                doctor_performance.append({
                    'doctor_id': int(r.doctor_id),
                    'doctor_name': r.doctor_name,
                    'archived_30d': int(r.archived_count or 0),
                    'avg_minutes_30d': float(r.avg_sec or 0) / 60.0
                })
        except Exception:
            db.session.rollback()
            doctor_performance = []
        
        # موافقات معلّقة (الدفع القسري/الإدخال بدون دفع)
        pending_force_payment_approvals = Visit.query.filter(
            Visit.is_force_payment == True,
            Visit.force_payment_approved_by.is_(None)
        ).count()
        
        stats = {
            'total_patients': total_patients,
            'new_patients_today': new_patients_today,
            'total_visits': total_visits,
            'visits_today': visits_today,
            'completed_visits_today': completed_visits_today,
            'today_revenue': float(today_revenue),
            'month_revenue': float(month_revenue),
            'total_users': total_users,
            'active_users': active_users,
            'departments': departments,
            'pending_force_payment_approvals': pending_force_payment_approvals,
            'smart_analytics': smart_analytics,
            'business_insights': business_insights,
            'performance_metrics': performance_metrics,
            'financial_forecasting': financial_forecasting,
            'bi_insights': bi_insights,
            'department_performance': department_performance,
            'doctor_performance': doctor_performance
        }
        
        return render_template('manager/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in manager dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
