"""dashboard routes - extracted from monolithic doctor.py"""

import logging
from datetime import UTC, date, datetime, timedelta

# Imports
from flask import flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import OrderState, VisitState
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.medication import Prescription
from models.radiology_request import RadiologyRequest
from models.user import User
from models.visit import Visit
from routes.doctor import doctor_bp
from utils.decorators import role_required, role_required_json

# =============================================
# DASHBOARD ROUTES
# =============================================


@doctor_bp.route('/dashboard-new')
@login_required
@role_required('doctor', 'admin', 'manager')
def dashboard_new():
    """لوحة تحكم الطبيب البسيطة — الإصدار المُحسّن"""
    try:
        from sqlalchemy import func

        from app.shared.enums import OrderState, VisitState
        from models.appointment import Appointment
        from models.lab_request import LabRequest
        from models.medication import Prescription
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit

        today = date.today()

        # Stats cards
        my_visits_count = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(Visit.doctor_id == current_user.id, Visit.visit_date == today)
        ).scalar()

        waiting_patients = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(Visit.doctor_id == current_user.id, Visit.status == VisitState.OPEN)
        ).scalar()

        prescriptions_count = db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Visit)
            .filter(Visit.doctor_id == current_user.id, func.date(Prescription.created_at) == today)
        ).scalar()

        appointments_count = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id, func.date(Appointment.starts_at) == today
            )
        ).scalar()

        # Waiting list (today's visits)
        waiting_list = (
            db.session.execute(
                select(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date == today,
                    Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
                )
                .order_by(Visit.visit_time)
                .limit(10)
            )
            .scalars()
            .all()
        )

        # Today's appointments
        today_appointments = (
            db.session.execute(
                select(Appointment)
                .filter(
                    Appointment.doctor_id == current_user.id,
                    func.date(Appointment.starts_at) == today,
                )
                .order_by(Appointment.starts_at)
                .limit(10)
            )
            .scalars()
            .all()
        )

        # Pending lab requests
        pending_lab_list = (
            db.session.execute(
                select(LabRequest)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                )
                .order_by(LabRequest.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        # Pending radiology requests
        pending_radiology_list = (
            db.session.execute(
                select(RadiologyRequest)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                )
                .order_by(RadiologyRequest.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        # Extra stats for enhanced dashboard
        completed_today = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == current_user.id,
                Visit.visit_date == today,
                Visit.status == VisitState.COMPLETED,
            )
        ).scalar()

        week_start = today - timedelta(days=today.weekday())
        week_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(Visit.doctor_id == current_user.id, Visit.visit_date >= week_start)
        ).scalar()

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
        logging.exception(f'Error in doctor dashboard_new: {e!s}')
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
        logging.exception(f'Error in doctor dashboard: {e!s}')
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
        today_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == doctor_id,
                Visit.visit_date == today,
                Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
            )
        ).scalar()
        pending_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(Visit.doctor_id == doctor_id, Visit.status == VisitState.OPEN)
        ).scalar()
        completed_today = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == doctor_id,
                Visit.visit_date == today,
                Visit.status == VisitState.COMPLETED,
            )
        ).scalar()
        weekly_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == doctor_id,
                Visit.visit_date >= week_ago,
                Visit.status == VisitState.COMPLETED,
            )
        ).scalar()
        prescriptions_today = db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Visit)
            .filter(Visit.doctor_id == doctor_id, Visit.visit_date == today)
        ).scalar()
        pending_lab_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .join(Visit)
            .filter(Visit.doctor_id == doctor_id, LabRequest.status == OrderState.REQUESTED)
        ).scalar()
        pending_radiology_requests = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .join(Visit)
            .filter(Visit.doctor_id == doctor_id, RadiologyRequest.status == OrderState.REQUESTED)
        ).scalar()
        upcoming_patients = (
            db.session.execute(
                select(Visit)
                .filter(
                    Visit.doctor_id == doctor_id,
                    Visit.visit_date == today,
                    Visit.status.in_([VisitState.OPEN, VisitState.CHECKED_IN]),
                )
                .order_by(Visit.visit_time)
                .limit(5)
            )
            .scalars()
            .all()
        )
        stats = {
            'today_visits': today_visits,
            'pending_visits': pending_visits,
            'completed_today': completed_today,
            'weekly_visits': weekly_visits,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests,
        }
        try:
            from decimal import ROUND_HALF_UP, Decimal

            from models.pricing import DoctorPricing

            def compute_fee(v):
                total = Decimal(str(v.total_amount or 0))
                fee = None
                pricing = (
                    db.session.execute(
                        select(DoctorPricing)
                        .filter(
                            DoctorPricing.doctor_id == v.doctor_id,
                            DoctorPricing.department_id == v.department_id,
                            DoctorPricing.is_active,
                        )
                        .order_by(DoctorPricing.effective_from.desc())
                    )
                    .scalars()
                    .first()
                )
                vt = (v.visit_type or '').upper()
                if pricing:
                    if vt in ['FIRST', 'CONSULTATION'] and pricing.consultation_price:
                        fee = Decimal(str(pricing.consultation_price))
                    elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                        fee = Decimal(str(pricing.follow_up_price))
                    elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                        fee = Decimal(str(pricing.emergency_price))
                if fee is None:
                    fee = total * Decimal('0.30')
                fee = min(fee, total)
                return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            month_start = date(today.year, today.month, 1)
            earnings_today = sum(
                compute_fee(v)
                for v in db.session.execute(
                    select(Visit).filter(
                        Visit.doctor_id == doctor_id,
                        Visit.visit_date == today,
                        Visit.status == VisitState.COMPLETED,
                    )
                )
                .scalars()
                .all()
            )
            earnings_week = sum(
                compute_fee(v)
                for v in db.session.execute(
                    select(Visit).filter(
                        Visit.doctor_id == doctor_id,
                        Visit.visit_date >= week_ago,
                        Visit.status == VisitState.COMPLETED,
                    )
                )
                .scalars()
                .all()
            )
            earnings_month = sum(
                compute_fee(v)
                for v in db.session.execute(
                    select(Visit).filter(
                        Visit.doctor_id == doctor_id,
                        Visit.visit_date >= month_start,
                        Visit.status == VisitState.COMPLETED,
                    )
                )
                .scalars()
                .all()
            )
            stats['doctor_earnings_today'] = float(earnings_today)
            stats['doctor_earnings_week'] = float(earnings_week)
            stats['doctor_earnings_month'] = float(earnings_month)
        except Exception:
            stats['doctor_earnings_today'] = 0.0
            stats['doctor_earnings_week'] = 0.0
            stats['doctor_earnings_month'] = 0.0
        return render_template(
            'doctor/dashboard.html',
            stats=stats,
            upcoming_patients=upcoming_patients,
            viewing_doctor=target_doctor,
        )
    except Exception as e:
        logging.exception(f'Error in admin view doctor dashboard: {e!s}')
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
        from app.shared.enums import OrderState, VisitState

        stats = {
            'today_visits': db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(Visit.doctor_id == current_user.id, Visit.visit_date == today)
            ).scalar(),
            'waiting_patients': db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(Visit.doctor_id == current_user.id, Visit.status == VisitState.OPEN)
            ).scalar(),
            'in_progress': db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(Visit.doctor_id == current_user.id, Visit.status == VisitState.IN_PROGRESS)
            ).scalar(),
            'completed_today': db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date == today,
                    Visit.status == VisitState.COMPLETED,
                )
            ).scalar(),
            'prescriptions_today': db.session.execute(
                select(func.count())
                .select_from(Prescription)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id, func.date(Prescription.created_at) == today
                )
            ).scalar(),
            'appointments_today': db.session.execute(
                select(func.count())
                .select_from(Appointment)
                .filter(
                    Appointment.doctor_id == current_user.id,
                    func.date(Appointment.starts_at) == today,
                )
            ).scalar(),
            'pending_lab': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                )
            ).scalar(),
            'pending_radiology': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                )
            ).scalar(),
            'timestamp': datetime.now(UTC).isoformat(),
        }
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logging.exception(f'Error in api_dashboard_stats: {e}')
        return jsonify({'success': False, 'message': 'فشل تحميل الإحصائيات'}), 500


@doctor_bp.route('/api/today-visits')
@login_required
@role_required_json('doctor', 'admin', 'manager')
def api_today_visits():
    """قائمة زيارات اليوم للوحة التحكم الحية"""
    try:
        today = date.today()
        from app.shared.enums import VisitState

        visits = (
            db.session.execute(
                select(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date == today,
                    Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
                )
                .order_by(Visit.visit_time)
            )
            .scalars()
            .all()
        )

        results = []
        for v in visits:
            results.append(
                {
                    'id': v.id,
                    'visit_number': v.visit_number,
                    'patient_name': v.patient.full_name if v.patient else 'غير محدد',
                    'patient_phone': v.patient.phone if v.patient else None,
                    'status': str(v.status),
                    'status_label': v.status.value if hasattr(v.status, 'value') else str(v.status),
                    'visit_type': str(v.visit_type) if v.visit_type else None,
                    'visit_time': v.visit_time.strftime('%H:%M') if v.visit_time else None,
                    'details_url': url_for('doctor.patient_details', visit_id=v.id),
                }
            )
        return jsonify({'success': True, 'visits': results})
    except Exception as e:
        logging.exception(f'Error in api_today_visits: {e}')
        return jsonify({'success': False, 'message': 'فشل تحميل الزيارات'}), 500
