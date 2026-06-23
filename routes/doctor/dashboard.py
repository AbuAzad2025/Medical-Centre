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
