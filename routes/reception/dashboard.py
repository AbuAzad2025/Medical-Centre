"""dashboard routes - extracted from monolithic reception.py"""

from routes.reception import reception_bp

# Imports
 
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timezone
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.department import Department
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.queue_management import QueueManagement
from models.patient_satisfaction import PatientSatisfactionSurvey
from services.gatekeeper_service import GatekeeperService
from services.reception_service import reception_service
from services.core_queries import core_queries
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data, can_delete_patient
from app_factory import db
import logging
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService
from routes.reception.queue import (
    get_smart_queue_management,
    get_patient_flow_analysis,
    get_appointment_optimization,
    get_real_time_alerts,
    calculate_queue_efficiency,
    get_workflow_automation,
    get_patient_satisfaction_ai,
    get_resource_planning,
    get_smart_recommendations,
    get_patient_demand_forecast,
)



# ═══════════════════════════════════════
# DASHBOARD ROUTES
# ═══════════════════════════════════════

@reception_bp.route('/')
@login_required
def index():
    """توجيه تلقائي إلى لوحة التحكم"""
    return redirect(url_for('reception.dashboard'))

@reception_bp.route('/dashboard')
@login_required
@role_required('reception', 'super_admin', 'manager')
def dashboard():
    """لوحة تحكم الاستقبال - الوحدة المركزية"""
    
    
    # إحصائيات شاملة عبر CoreQueryService
    stats = core_queries.get_basic_dashboard_stats()
    total_patients = stats["total_patients"]
    today_visits = stats["visits_today"]
    pending_appointments = Appointment.query.filter_by(status='SCHEDULED').count()
    today_visits_list = Visit.query.filter(
        Visit.visit_date == db.func.current_date(),
        Visit.status.in_(['OPEN', 'IN_PROGRESS', 'COMPLETED'])
    ).order_by(Visit.created_at.desc()).limit(20).all()
    
    # إحصائيات الطوابير لكل قسم
    departments = Department.query.all()
    queue_stats = {}
    for dept in departments:
        queue_stats[dept.id] = {
            'name': dept.name_ar,
            'total_queue': 0,  
            'waiting': 0,
            'in_progress': 0
        }
    active_queue_items = QueueManagement.query.filter(
        QueueManagement.status.in_(['waiting', 'called', 'in_progress'])
    ).order_by(QueueManagement.queued_at.asc()).limit(50).all()

    today_online_bookings = OnlineBooking.query.filter(
        OnlineBooking.appointment_date == db.func.current_date(),
        OnlineBooking.status.in_(['pending', 'confirmed'])
    ).order_by(OnlineBooking.appointment_time.asc()).limit(20).all()
    
    # الميزات الذكية
    smart_analytics = get_smart_queue_management()
    patient_flow = get_patient_flow_analysis()
    appointment_optimization = get_appointment_optimization()
    real_time_alerts = get_real_time_alerts()
    workflow_automation = get_workflow_automation()
    patient_satisfaction_ai = get_patient_satisfaction_ai()
    resource_planning = get_resource_planning()
    smart_recommendations = get_smart_recommendations()
    patient_demand_forecast = get_patient_demand_forecast()
    
    # تجميع الإحصائيات
    stats = {
        'smart_queue_management': smart_analytics,
        'patient_flow': patient_flow,
        'patient_flow_analysis': patient_flow,
        'appointment_optimization': appointment_optimization,
        'real_time_alerts': real_time_alerts,
        'workflow_automation': workflow_automation,
        'patient_satisfaction_ai': patient_satisfaction_ai,
        'resource_planning': resource_planning,
        'patient_demand_forecast': patient_demand_forecast,
        'smart_recommendations': smart_recommendations
    }
    
    return render_template('reception/dashboard_new.html',
                         total_patients=total_patients,
                         today_visits=today_visits,
                         today_visits_list=today_visits_list,
                         pending_appointments=pending_appointments,
                         departments=departments,
                         queue_stats=queue_stats,
                         active_queue_items=active_queue_items,
                         today_online_bookings=today_online_bookings,
                         smart_analytics=smart_analytics,
                         patient_flow=patient_flow,
                         appointment_optimization=appointment_optimization,
                         real_time_alerts=real_time_alerts,
                         stats=stats,
                         patient_demand_forecast=patient_demand_forecast)

@reception_bp.route('/staff/schedule', methods=['GET', 'POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')

def reception_staff_schedule():
    if current_user.role not in ['reception', 'manager', 'super_admin']:
        flash('ليس لديك الصلاحيات للوصول', 'danger')
        return redirect(url_for('reception.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            day_of_week = request.form.get('day_of_week', type=int)
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            is_active = request.form.get('is_active') == 'on'
            from datetime import datetime as _dt
            st = _dt.strptime(start_time, '%H:%M').time()
            et = _dt.strptime(end_time, '%H:%M').time()
            s = StaffWorkSchedule.query.filter_by(user_id=user_id, day_of_week=day_of_week).first()
            if s:
                s.start_time = st
                s.end_time = et
                s.is_active = is_active
            else:
                s = StaffWorkSchedule(user_id=user_id, day_of_week=day_of_week, start_time=st, end_time=et, is_active=is_active)
                db.session.add(s)
            db.session.commit()
            flash('تم حفظ جدول العمل', 'success')
            return redirect(url_for('reception.reception_staff_schedule', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في حفظ الجدول', 'danger')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    schedules = []
    if user_id:
        schedules = StaffWorkSchedule.query.filter_by(user_id=user_id).order_by(StaffWorkSchedule.day_of_week.asc()).all()
    return render_template('reception/staff_schedule.html', users=users, schedules=schedules, selected_user_id=user_id)

@reception_bp.route('/staff/absence', methods=['GET', 'POST'])
@login_required
def reception_staff_absence():
    if current_user.role not in ['reception', 'manager', 'super_admin']:
        flash('ليس لديك الصلاحيات للوصول', 'danger')
        return redirect(url_for('reception.dashboard'))
    if request.method == 'POST':
        try:
            user_id = request.form.get('user_id', type=int)
            start_date = request.form.get('start_date')
            end_date = request.form.get('end_date')
            reason = (request.form.get('reason') or '').strip() or None
            from datetime import datetime as _dt
            sd = _dt.strptime(start_date, '%Y-%m-%d').date()
            ed = _dt.strptime(end_date, '%Y-%m-%d').date()
            a = StaffAbsence(user_id=user_id, start_date=sd, end_date=ed, reason=reason)
            db.session.add(a)
            db.session.commit()
            flash('تم إضافة الغياب', 'success')
            return redirect(url_for('reception.reception_staff_absence', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(str(e))
            flash('حدث خطأ في إضافة الغياب', 'danger')
    users = User.query.filter(User.role.in_(['doctor','lab','radiology']), User.is_active == True).all()
    user_id = request.args.get('user_id', type=int)
    absences = []
    if user_id:
        absences = StaffAbsence.query.filter_by(user_id=user_id).order_by(StaffAbsence.start_date.desc()).all()
    return render_template('reception/staff_absence.html', users=users, absences=absences, selected_user_id=user_id)

# مسارات إضافية للاستقبال



@reception_bp.route('/survey/<token>', methods=['GET', 'POST'])
def survey(token):
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey
        survey = PatientSatisfactionSurvey.query.filter_by(token=token).first()
        if not survey:
            return render_template('reception/survey.html', invalid=True)
        if request.method == 'POST':
            if survey.submitted_at:
                return render_template('reception/survey.html', survey=survey, submitted=True)
            rating = request.form.get('rating', type=int)
            comment = (request.form.get('comment') or '').strip()
            if not rating or rating < 1 or rating > 5:
                return render_template('reception/survey.html', survey=survey, error='الرجاء اختيار التقييم')
            survey.rating = rating
            survey.comment = comment if comment else None
            survey.submitted_at = datetime.now(timezone.utc)
            db.session.commit()
            return render_template('reception/survey.html', survey=survey, submitted=True)
        return render_template('reception/survey.html', survey=survey)
    except Exception as e:
        logging.error(f"Error handling survey: {str(e)}")
        return render_template('reception/survey.html', invalid=True)

