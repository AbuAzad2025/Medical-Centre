"""dashboard routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.drug_interaction import DrugInteraction
from models.audit_trail import AuditTrail
from models.system_config import SystemConfig
from services.core_queries import core_queries
from app_factory import db
from app.shared.enums import VisitState, OrderState, AppointmentState
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# DASHBOARD ROUTES
# =============================================

@doctor_bp.route('/dashboard-new')
@login_required
@role_required('doctor', 'admin', 'manager')
def dashboard_new():
    """لوحة تحكم الطبيب البسيطة — الإصدار المُحسّن"""
    try:
        from app_factory import db
        from sqlalchemy import func
        from app.shared.enums import VisitState, OrderState, AppointmentState
        from models.visit import Visit
        from models.appointment import Appointment
        from models.medication import Prescription
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest

        today = date.today()

        # Stats cards
        my_visits_count = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today
        ).count()

        waiting_patients = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == VisitState.OPEN
        ).count()

        prescriptions_count = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            func.date(Prescription.created_at) == today
        ).count()

        appointments_count = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            func.date(Appointment.starts_at) == today
        ).count()

        # Waiting list (today's visits)
        waiting_list = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])
        ).order_by(Visit.visit_time).limit(10).all()

        # Today's appointments
        today_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            func.date(Appointment.starts_at) == today
        ).order_by(Appointment.starts_at).limit(10).all()

        # Pending lab requests
        pending_lab_list = LabRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
        ).order_by(LabRequest.created_at.desc()).limit(10).all()

        # Pending radiology requests
        pending_radiology_list = RadiologyRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
        ).order_by(RadiologyRequest.created_at.desc()).limit(10).all()

        # Extra stats for enhanced dashboard
        completed_today = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status == VisitState.COMPLETED
        ).count()

        week_start = today - timedelta(days=today.weekday())
        week_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= week_start
        ).count()

        return render_template(
            'doctor/dashboard_new.html',
            my_visits_count=my_visits_count,
            waiting_patients=waiting_patients,
            prescriptions_count=prescriptions_count,
            appointments_count=appointments_count,
            waiting_list=waiting_list,
            today_appointments=today_appointments,
            pending_lab_list=pending_lab_list,
            pending_radiology_list=pending_radiology_list,
            completed_today=completed_today,
            week_visits=week_visits,
        )
    except Exception as e:
        logging.error(f"Error in doctor dashboard_new: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/dashboard')
@login_required
@role_required('doctor', 'admin', 'manager')
def dashboard():
    """لوحة قيادة الطبيب — Command Center"""
    try:
        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user)
    except Exception as e:
        logging.error(f"Error in doctor dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/dashboard/<int:doctor_id>')
@login_required
@role_required('manager', 'super_admin', 'accountant')
def dashboard_for_doctor(doctor_id):
    """لوحة تحكم لطبيب محدد (عرض إداري)"""
    try:
        target_doctor = db.session.get(User, doctor_id)
        if not target_doctor or target_doctor.role != 'doctor':
            flash('الطبيب غير موجود', 'error')
            return redirect(url_for('main.dashboard'))
        today = date.today()
        week_ago = today - timedelta(days=7)
        today_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])).count()
        pending_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.status == VisitState.OPEN).count()
        completed_today = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status == VisitState.COMPLETED).count()
        weekly_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= week_ago, Visit.status == VisitState.COMPLETED).count()
        prescriptions_today = Prescription.query.join(Visit).filter(Visit.doctor_id == doctor_id, Visit.visit_date == today).count()
        pending_lab_requests = LabRequest.query.join(Visit).filter(Visit.doctor_id == doctor_id, LabRequest.status == OrderState.REQUESTED).count()
        pending_radiology_requests = RadiologyRequest.query.join(Visit).filter(Visit.doctor_id == doctor_id, RadiologyRequest.status == OrderState.REQUESTED).count()
        upcoming_patients = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status.in_([VisitState.OPEN, VisitState.CHECKED_IN])).order_by(Visit.visit_time).limit(5).all()
        stats = {
            'today_visits': today_visits,
            'pending_visits': pending_visits,
            'completed_today': completed_today,
            'weekly_visits': weekly_visits,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests
        }
        try:
            from decimal import Decimal, ROUND_HALF_UP
            from models.pricing import DoctorPricing
            def compute_fee(v):
                total = Decimal(str(v.total_amount or 0))
                fee = None
                pricing = DoctorPricing.query.filter(DoctorPricing.doctor_id == v.doctor_id, DoctorPricing.department_id == v.department_id, DoctorPricing.is_active == True).order_by(DoctorPricing.effective_from.desc()).first()
                vt = (v.visit_type or '').upper()
                if pricing:
                    if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                        fee = Decimal(str(pricing.consultation_price))
                    elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                        fee = Decimal(str(pricing.follow_up_price))
                    elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                        fee = Decimal(str(pricing.emergency_price))
                if fee is None:
                    fee = (total * Decimal('0.30'))
                if fee > total:
                    fee = total
                return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            month_start = date(today.year, today.month, 1)
            earnings_today = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status == VisitState.COMPLETED).all())
            earnings_week = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= week_ago, Visit.status == VisitState.COMPLETED).all())
            earnings_month = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= month_start, Visit.status == VisitState.COMPLETED).all())
            stats['doctor_earnings_today'] = float(earnings_today)
            stats['doctor_earnings_week'] = float(earnings_week)
            stats['doctor_earnings_month'] = float(earnings_month)
        except Exception:
            stats['doctor_earnings_today'] = 0.0
            stats['doctor_earnings_week'] = 0.0
            stats['doctor_earnings_month'] = 0.0
        return render_template('doctor/dashboard.html', stats=stats, upcoming_patients=upcoming_patients, viewing_doctor=target_doctor)
    except Exception as e:
        logging.error(f"Error in admin view doctor dashboard: {str(e)}")
        flash('حدث خطأ في عرض لوحة الطبيب', 'error')
        return redirect(url_for('main.dashboard'))


# ═══════════════════════════════════════
# DASHBOARD API — Live stats & helpers
# ═══════════════════════════════════════

@doctor_bp.route('/api/dashboard-stats')
@login_required
@role_required_json('doctor', 'admin', 'manager')
def api_dashboard_stats():
    """إحصائيات حية للوحة التحكم"""
    try:
        today = date.today()
        from app.shared.enums import VisitState, OrderState, AppointmentState

        stats = {
            'today_visits': Visit.query.filter(
                Visit.doctor_id == current_user.id,
                Visit.visit_date == today
            ).count(),
            'waiting_patients': Visit.query.filter(
                Visit.doctor_id == current_user.id,
                Visit.status == VisitState.OPEN
            ).count(),
            'in_progress': Visit.query.filter(
                Visit.doctor_id == current_user.id,
                Visit.status == VisitState.IN_PROGRESS
            ).count(),
            'completed_today': Visit.query.filter(
                Visit.doctor_id == current_user.id,
                Visit.visit_date == today,
                Visit.status == VisitState.COMPLETED
            ).count(),
            'prescriptions_today': Prescription.query.join(Visit).filter(
                Visit.doctor_id == current_user.id,
                func.date(Prescription.created_at) == today
            ).count(),
            'appointments_today': Appointment.query.filter(
                Appointment.doctor_id == current_user.id,
                func.date(Appointment.starts_at) == today
            ).count(),
            'pending_lab': LabRequest.query.join(Visit).filter(
                Visit.doctor_id == current_user.id,
                LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
            ).count(),
            'pending_radiology': RadiologyRequest.query.join(Visit).filter(
                Visit.doctor_id == current_user.id,
                RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
            ).count(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logging.error(f"Error in api_dashboard_stats: {e}")
        return jsonify({'success': False, 'message': 'فشل تحميل الإحصائيات'}), 500


@doctor_bp.route('/api/today-visits')
@login_required
@role_required_json('doctor', 'admin', 'manager')
def api_today_visits():
    """قائمة زيارات اليوم للوحة التحكم الحية"""
    try:
        today = date.today()
        from app.shared.enums import VisitState

        visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS])
        ).order_by(Visit.visit_time).all()

        results = []
        for v in visits:
            results.append({
                'id': v.id,
                'visit_number': v.visit_number,
                'patient_name': v.patient.full_name if v.patient else 'غير محدد',
                'patient_phone': v.patient.phone if v.patient else None,
                'status': str(v.status),
                'status_label': v.status.value if hasattr(v.status, 'value') else str(v.status),
                'visit_type': str(v.visit_type) if v.visit_type else None,
                'visit_time': v.visit_time.strftime('%H:%M') if v.visit_time else None,
                'details_url': url_for('doctor.patient_details', visit_id=v.id),
            })
        return jsonify({'success': True, 'visits': results})
    except Exception as e:
        logging.error(f"Error in api_today_visits: {e}")
        return jsonify({'success': False, 'message': 'فشل تحميل الزيارات'}), 500

