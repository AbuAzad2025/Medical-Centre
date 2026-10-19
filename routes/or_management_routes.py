"""
Operating Room Management Routes
"""

from flask import Blueprint, g, render_template, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.or_management import SurgeryChecklist, SurgerySchedule
from utils.decorators import handle_route_errors, role_required

or_bp = Blueprint('or', __name__)


@or_bp.route('/schedule')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def schedule():
    date = request.args.get('date')
    status = request.args.get('status', 'SCHEDULED')
    query = SurgerySchedule.query
    if status:
        query = query.filter_by(status=status)
    if date:
        from datetime import datetime

        try:
            d = datetime.strptime(date, '%Y-%m-%d').date()
            query = query.filter(SurgerySchedule.scheduled_date == d)
        except ValueError:
            pass
    surgeries = (
        query.order_by(SurgerySchedule.scheduled_date, SurgerySchedule.scheduled_start_time)
        .limit(100)
        .all()
    )
    return render_template('or/schedule.html', surgeries=surgeries, status=status)


@or_bp.route('/surgery/<int:surgery_id>')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def surgery_detail(surgery_id):
    surgery = db.get_or_404(SurgerySchedule, surgery_id)
    checklist = (
        db.session.execute(select(SurgeryChecklist).filter_by(surgery_schedule_id=surgery_id))
        .scalars()
        .first()
    )
    return render_template('or/surgery_detail.html', surgery=surgery, checklist=checklist)


@or_bp.route('/schedule', methods=['POST'])
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def schedule_create():
    """Book a patient onto the theatre list.

    The blueprint previously exposed two GET routes and no writer, so
    SurgerySchedule - which has NOT NULL patient_id, procedure_name and
    scheduled_date - was populated by nothing. No surgery could be booked
    through this application at all.

    Only clinical roles may book; reception cannot, and a patient_id from another
    tenant is rejected rather than written.
    """
    from datetime import datetime

    from flask import flash, redirect, url_for

    from utils.db_safety import safe_commit, safe_rollback

    data = request.get_json(silent=True) or request.form

    patient_id = data.get('patient_id')
    procedure_name = (data.get('procedure_name') or '').strip()
    scheduled_date_raw = (data.get('scheduled_date') or '').strip()
    surgery_type = (data.get('surgery_type') or 'ELECTIVE').strip().upper()
    or_room = (data.get('or_room') or '').strip() or None
    surgeon_id = data.get('surgeon_id')
    scheduled_start = (data.get('scheduled_start_time') or '').strip() or None

    errors = []
    if not patient_id:
        errors.append('patient_id is required')
    if not procedure_name:
        errors.append('procedure_name is required')
    if not scheduled_date_raw:
        errors.append('scheduled_date is required')

    parsed_date = None
    if scheduled_date_raw:
        try:
            parsed_date = datetime.strptime(scheduled_date_raw, '%Y-%m-%d').date()
        except ValueError:
            errors.append(f'scheduled_date {scheduled_date_raw!r} is not YYYY-MM-DD')

    parsed_start = None
    if scheduled_start:
        try:
            parsed_start = datetime.strptime(scheduled_start, '%H:%M').time()
        except ValueError:
            errors.append(f'scheduled_start_time {scheduled_start!r} is not HH:MM')

    if surgery_type not in {'ELECTIVE', 'EMERGENCY', 'URGENT'}:
        errors.append(f'surgery_type {surgery_type!r} is not ELECTIVE/EMERGENCY/URGENT')

    # Fail closed on an unparseable or absent tenant: a surgery row written
    # without tenant scope would be invisible to every tenant's RLS policy.
    tenant_id = getattr(g, 'tenant_id', None)
    if tenant_id is None:
        errors.append('tenant context is required')

    if not errors and patient_id:
        from models.patient import Patient

        patient = (
            db.session.execute(
                select(Patient).filter(
                    Patient.id == int(patient_id), Patient.tenant_id == tenant_id
                )
            )
            .scalars()
            .first()
        )
        if not patient:
            # Either absent or owned by another tenant. The two are deliberately
            # not distinguished in the message: telling a caller which patient
            # ids exist is a cross-tenant enumeration oracle.
            errors.append('patient not found in this tenant')

    if errors:
        for message in errors:
            flash(message, 'error')
        return redirect(url_for('or.schedule'))

    surgery = SurgerySchedule(
        tenant_id=tenant_id,
        patient_id=int(patient_id),
        procedure_name=procedure_name,
        procedure_name_ar=(data.get('procedure_name_ar') or '').strip() or None,
        surgery_type=surgery_type,
        scheduled_date=parsed_date,
        scheduled_start_time=parsed_start,
        or_room=or_room,
        estimated_duration_minutes=int(data['estimated_duration_minutes'])
        if (data.get('estimated_duration_minutes') or '').strip().isdigit()
        else None,
        surgeon_id=int(surgeon_id) if str(surgeon_id or '').isdigit() else None,
        status='SCHEDULED',
    )
    db.session.add(surgery)
    try:
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        flash('تعذر حفظ العملية الجراحية حالياً', 'error')
        return redirect(url_for('or.schedule'))

    flash('تمت جدولة العملية الجراحية', 'success')
    return redirect(url_for('or.schedule'))
