"""dashboard routes - extracted from monolithic reception.py"""

import logging
from datetime import UTC, datetime

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.user import StaffAbsence, StaffWorkSchedule, User
from routes.reception import reception_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import (
    role_required,
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
    """لوحة قيادة الاستقبال — Command Center"""
    from app.shared.dashboard_service import render_command_center

    return render_command_center(current_user)


@reception_bp.route('/staff/schedule', methods=['GET', 'POST'])
@login_required
@role_required('reception', 'manager')
def reception_staff_schedule():
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
            s = (
                db.session.execute(
                    select(StaffWorkSchedule).filter_by(user_id=user_id, day_of_week=day_of_week)
                )
                .scalars()
                .first()
            )
            if s:
                s.start_time = st
                s.end_time = et
                s.is_active = is_active
            else:
                s = StaffWorkSchedule(
                    user_id=user_id,
                    day_of_week=day_of_week,
                    start_time=st,
                    end_time=et,
                    is_active=is_active,
                )
                db.session.add(s)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم حفظ جدول العمل', 'success')
            return redirect(url_for('reception.reception_staff_schedule', user_id=user_id))
        except Exception as e:
            safe_rollback(db.session, error_message='database rollback')
            logging.exception(str(e))
            flash('حدث خطأ في حفظ الجدول', 'danger')
    users = (
        db.session.execute(
            select(User).filter(
                User.role.in_(['doctor', 'lab', 'radiology']), User.is_active == True
            )
        )
        .scalars()
        .all()
    )
    user_id = request.args.get('user_id', type=int)
    schedules = []
    if user_id:
        schedules = (
            db.session.execute(
                select(StaffWorkSchedule)
                .filter_by(user_id=user_id)
                .order_by(StaffWorkSchedule.day_of_week.asc())
            )
            .scalars()
            .all()
        )
    return render_template(
        'reception/staff_schedule.html', users=users, schedules=schedules, selected_user_id=user_id
    )


@reception_bp.route('/staff/absence', methods=['GET', 'POST'])
@login_required
@role_required('reception', 'manager')
def reception_staff_absence():
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
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إضافة الغياب', 'success')
            return redirect(url_for('reception.reception_staff_absence', user_id=user_id))
        except Exception as e:
            safe_rollback(db.session, error_message='database rollback')
            logging.exception(str(e))
            flash('حدث خطأ في إضافة الغياب', 'danger')
    users = (
        db.session.execute(
            select(User).filter(
                User.role.in_(['doctor', 'lab', 'radiology']), User.is_active == True
            )
        )
        .scalars()
        .all()
    )
    user_id = request.args.get('user_id', type=int)
    absences = []
    if user_id:
        absences = (
            db.session.execute(
                select(StaffAbsence)
                .filter_by(user_id=user_id)
                .order_by(StaffAbsence.start_date.desc())
            )
            .scalars()
            .all()
        )
    return render_template(
        'reception/staff_absence.html', users=users, absences=absences, selected_user_id=user_id
    )


# مسارات إضافية للاستقبال


@reception_bp.route('/survey/<token>', methods=['GET', 'POST'])
def survey(token):
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey

        survey = (
            db.session.execute(select(PatientSatisfactionSurvey).filter_by(token=token))
            .scalars()
            .first()
        )
        if not survey:
            return render_template('reception/survey.html', invalid=True)
        if request.method == 'POST':
            if survey.submitted_at:
                return render_template('reception/survey.html', survey=survey, submitted=True)
            rating = request.form.get('rating', type=int)
            comment = (request.form.get('comment') or '').strip()
            if not rating or rating < 1 or rating > 5:
                return render_template(
                    'reception/survey.html', survey=survey, error='الرجاء اختيار التقييم'
                )
            survey.rating = rating
            survey.comment = comment if comment else None
            survey.submitted_at = datetime.now(UTC)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            return render_template('reception/survey.html', survey=survey, submitted=True)
        return render_template('reception/survey.html', survey=survey)
    except Exception as e:
        logging.exception(f'Error handling survey: {e!s}')
        return render_template('reception/survey.html', invalid=True)
