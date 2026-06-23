"""appointments routes - extracted from monolithic reception.py"""

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
from app.shared.enums import AppointmentState
from models.follow_up import FollowUpRequest
from models.online_booking import OnlineBooking
from models.department import Department
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.queue_management import QueueManagement
from models.patient_satisfaction import PatientSatisfactionSurvey
from services.gatekeeper_service import GatekeeperService
from services.reception_service import reception_service
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data, can_delete_patient
from app_factory import db
import logging
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService
from routes.reception.queue import add_patient_to_queue_auto



# ═══════════════════════════════════════
# APPOINTMENT ROUTES
# ═══════════════════════════════════════

@reception_bp.route('/online-bookings/checkin', methods=['POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def checkin_online_booking():
    booking_id = request.form.get('booking_id', type=int)
    booking_reference = (request.form.get('booking_reference') or '').strip().upper() or None

    booking = None
    if booking_id:
        booking = db.session.get(OnlineBooking, booking_id)
    elif booking_reference:
        booking = OnlineBooking.query.filter_by(booking_reference=booking_reference).first()

    if not booking:
        flash('الحجز غير موجود', 'error')
        return redirect(url_for('reception.dashboard'))

    if booking.status in {'cancelled', 'no_show'}:
        flash('لا يمكن تحويل هذا الحجز إلى زيارة', 'warning')
        return redirect(url_for('reception.dashboard'))

    if booking.patient_id:
        patient = db.session.get(Patient, booking.patient_id)
    else:
        patient = None

    if not patient:
        patient = None
        national_id = (booking.national_id or '').strip() or None
        phone = (booking.phone or '').strip() or None

        if national_id:
            patient = Patient.query.filter_by(national_id=national_id).first()
        if not patient and phone:
            patient = Patient.query.filter_by(phone=phone).first()

        if not patient:
            patient = Patient(
                first_name=booking.first_name,
                last_name=booking.last_name,
                national_id=national_id,
                phone=phone,
                birth_date=booking.date_of_birth,
                gender=booking.gender
            )
            db.session.add(patient)
            db.session.flush()

        booking.patient_id = patient.id
        booking.is_new_patient = False

    marker = f"[ONLINE_BOOKING:{booking.booking_reference}]"
    existing_visit = Visit.query.filter(
        Visit.visit_date == booking.appointment_date,
        Visit.patient_id == patient.id,
        Visit.notes.ilike(f"%{marker}%")
    ).order_by(Visit.created_at.desc()).first()
    if existing_visit:
        flash('تم تحويل هذا الحجز مسبقاً إلى زيارة', 'info')
        return redirect(url_for('reception.visits'))

    visit_type = 'CONSULTATION'
    booking_visit_type = (booking.visit_type or '').strip().lower()
    if booking_visit_type in {'follow_up', 'followup'}:
        visit_type = 'FOLLOW_UP'
    elif booking_visit_type in {'emergency'}:
        visit_type = 'EMERGENCY'

    visit_notes_parts = []
    if booking.notes:
        visit_notes_parts.append(booking.notes)
    visit_notes_parts.append(marker)

    visit = Visit(
        patient_id=patient.id,
        department_id=booking.department_id,
        doctor_id=booking.doctor_id,
        visit_type=visit_type,
        visit_date=booking.appointment_date,
        symptoms=booking.symptoms,
        notes="\n".join([p for p in visit_notes_parts if p]),
        status='OPEN',
        payment_method=(booking.payment_method or 'CASH').upper(),
        payment_status='PENDING',
        is_emergency=(visit_type == 'EMERGENCY'),
        created_by=current_user.id,
        currency='ILS',
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(visit)
    db.session.flush()

    booking.status = 'completed'
    booking.confirmed_at = booking.confirmed_at or datetime.now(timezone.utc)
    db.session.commit()

    try:
        queue_result = add_patient_to_queue_auto(visit.id, booking.department_id, booking.doctor_id)
        if isinstance(queue_result, tuple):
            q_success, q_msg = queue_result
        else:
            q_success, q_msg = queue_result, "خطأ غير محدد"
        if q_success:
            flash(f'تمت إضافة المريض للطابور: {q_msg}', 'info')
        else:
            flash(f'تنبيه: لم يتم إضافة المريض للطابور ({q_msg})', 'warning')
    except Exception as queue_error:
        logging.warning(f"Could not add to queue from online booking: {str(queue_error)}")

    flash('تم تحويل الحجز إلى زيارة بنجاح.', 'success')
    return redirect(url_for('reception.visits'))


@reception_bp.route('/appointments/<int:appointment_id>/checkin', methods=['POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def checkin_appointment(appointment_id: int):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        flash('الموعد غير موجود', 'error')
        return redirect(url_for('reception.appointments'))

    if appointment.status in {'CANCELLED', 'NO_SHOW'}:
        flash('لا يمكن تحويل هذا الموعد إلى زيارة', 'warning')
        return redirect(url_for('reception.appointments'))

    if not appointment.department_id:
        flash('لا يمكن تحويل الموعد بدون تحديد قسم', 'warning')
        return redirect(url_for('reception.appointments'))

    patient = db.session.get(Patient, appointment.patient_id) if appointment.patient_id else None
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.appointments'))

    marker = f"[APPOINTMENT:{appointment.id}]"
    appt_date = appointment.starts_at.date() if appointment.starts_at else datetime.now(timezone.utc).date()
    existing_visit = Visit.query.filter(
        Visit.visit_date == appt_date,
        Visit.patient_id == patient.id,
        Visit.notes.ilike(f"%{marker}%")
    ).order_by(Visit.created_at.desc()).first()
    if existing_visit:
        flash('تم تحويل هذا الموعد مسبقاً إلى زيارة', 'info')
        return redirect(url_for('reception.visits'))

    visit_notes_parts = []
    if appointment.notes:
        visit_notes_parts.append(appointment.notes)
    visit_notes_parts.append(marker)

    visit = Visit(
        patient_id=patient.id,
        department_id=appointment.department_id,
        doctor_id=appointment.doctor_id,
        visit_type='CONSULTATION',
        visit_date=appt_date,
        notes="\n".join([p for p in visit_notes_parts if p]),
        status='OPEN',
        payment_method='CASH',
        payment_status='PENDING',
        is_emergency=False,
        created_by=current_user.id,
        currency='ILS',
        created_at=datetime.now(timezone.utc)
    )
    db.session.add(visit)
    db.session.flush()

    if appointment.status == AppointmentState.SCHEDULED:
        appointment.status = AppointmentState.CONFIRMED

    db.session.commit()

    try:
        queue_result = add_patient_to_queue_auto(visit.id, appointment.department_id, appointment.doctor_id)
        if isinstance(queue_result, tuple):
            q_success, q_msg = queue_result
        else:
            q_success, q_msg = queue_result, "خطأ غير محدد"
        if q_success:
            flash(f'تمت إضافة المريض للطابور: {q_msg}', 'info')
        else:
            flash(f'تنبيه: لم يتم إضافة المريض للطابور ({q_msg})', 'warning')
    except Exception as queue_error:
        logging.warning(f"Could not add to queue from appointment: {str(queue_error)}")

    flash('تم تحويل الموعد إلى زيارة بنجاح.', 'success')
    return redirect(url_for('reception.visits'))



# ---------------------------------------\n# HELPERS\n# ---------------------------------------\n\ndef _wants_json():
    """تحديد ما إذا كان الطلب يتوقع JSON (طلبات fetch)"""
    accept = (request.headers.get('Accept') or '').lower()
    xreq = (request.headers.get('X-Requested-With') or '').lower()
    return ('application/json' in accept) or (xreq == 'xmlhttprequest')

@reception_bp.route('/appointments')
@login_required
@role_required('reception', 'manager')

def appointments():
    """قائمة المواعيد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    # البحث والفلترة
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    doctor_id = request.args.get('doctor_id', type=int)
    status = request.args.get('status', '')
    date_str = (request.args.get('date') or '').strip()
    
    query = Appointment.query
    
    if search:
        query = query.join(Patient).filter(
            db.or_(
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.phone.ilike(f'%{search}%'),
                Patient.national_id.ilike(f'%{search}%')
            )
        )
    
    if department_id:
        query = query.filter(Appointment.department_id == department_id)
    
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)

    if status:
        query = query.filter(Appointment.status == status)

    if date_str:
        try:
            from datetime import datetime as _dt
            d0 = _dt.strptime(date_str, '%Y-%m-%d').date()
            from sqlalchemy import func
            query = query.filter(func.date(Appointment.starts_at) == d0)
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
    per_page = request.args.get('per_page', type=int) or 50
    per_page = max(10, min(per_page, 200))
    page = request.args.get('page', type=int) or 1
    page = max(1, page)
    filtered_total = query.count()
    appointments = query.order_by(Appointment.starts_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
    departments = Department.query.all()
    doctors = User.query.filter_by(role='doctor', is_active=True).order_by(User.full_name.asc()).all()

    def _split_appt_notes(notes_text):
        base_lines = []
        appt_type = None
        symptoms = None
        for raw in (notes_text or '').splitlines():
            line = (raw or '').strip()
            if not line:
                continue
            if line.startswith('نوع الموعد:'):
                appt_type = line.replace('نوع الموعد:', '').strip() or appt_type
                continue
            if line.startswith('الأعراض:'):
                symptoms = line.replace('الأعراض:', '').strip() or symptoms
                continue
            base_lines.append(line)
        return "\n".join(base_lines).strip() or None, appt_type, symptoms

    type_labels = {
        'first': 'زيارة أولى',
        'follow_up': 'متابعة',
        'consultation': 'استشارة',
        'emergency': 'طوارئ'
    }
    appt_meta = {}
    for a in appointments:
        base_notes, appt_type, symptoms = _split_appt_notes(getattr(a, 'notes', None))
        appt_meta[a.id] = {
            'appointment_type': appt_type,
            'appointment_type_label': type_labels.get((appt_type or '').strip().lower(), appt_type),
            'symptoms': symptoms,
            'base_notes': base_notes
        }

    # إحصائيات ديناميكية حقيقية
    from sqlalchemy import func
    total_count = db.session.query(func.count(Appointment.id)).scalar() or 0
    today_count = db.session.query(func.count(Appointment.id)).filter(func.date(Appointment.starts_at) == func.current_date()).scalar() or 0
    confirmed_count = db.session.query(func.count(Appointment.id)).filter(Appointment.status == AppointmentState.CONFIRMED).scalar() or 0
    pending_count = db.session.query(func.count(Appointment.id)).filter(Appointment.status == AppointmentState.SCHEDULED).scalar() or 0

    appointments_json = [{
        'id': a.id,
        'patient': {'full_name': a.patient.full_name} if getattr(a, 'patient', None) else None,
        'doctor': {'full_name': a.doctor.full_name} if getattr(a, 'doctor', None) else None,
        'starts_at': a.starts_at.isoformat() if a.starts_at else None,
        'status': (a.status or '').lower(),
        'appointment_type': appt_meta.get(a.id, {}).get('appointment_type'),
    } for a in appointments]

    return render_template('reception/appointments.html', 
                         appointments=appointments, 
                         appointments_json=appointments_json,
                         departments=departments,
                         doctors=doctors,
                         search=search,
                         selected_department=department_id,
                         selected_doctor=doctor_id,
                         selected_status=status,
                         selected_date=date_str,
                         appt_meta=appt_meta,
                         total_count=total_count,
                         today_count=today_count,
                         confirmed_count=confirmed_count,
                         pending_count=pending_count,
                         page=page,
                         per_page=per_page,
                         filtered_total=filtered_total)


@reception_bp.route('/follow-ups')
@login_required
@role_required('reception', 'super_admin', 'manager')
def follow_ups():
    search = (request.args.get('search') or '').strip()
    status = (request.args.get('status') or '').strip().upper()
    date_str = (request.args.get('date') or '').strip()

    query = FollowUpRequest.query.join(Patient, Patient.id == FollowUpRequest.patient_id)

    if search:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{search}%'),
                Patient.last_name.ilike(f'%{search}%'),
                Patient.phone.contains(search),
                Patient.national_id.contains(search)
            )
        )

    if status:
        query = query.filter(FollowUpRequest.status == status)

    if date_str:
        try:
            from datetime import datetime as _dt
            d0 = _dt.strptime(date_str, '%Y-%m-%d').date()
            query = query.filter(FollowUpRequest.suggested_date == d0)
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
    followups = query.order_by(FollowUpRequest.suggested_date.asc(), FollowUpRequest.created_at.desc()).limit(500).all()

    return render_template('reception/follow_ups.html', followups=followups, search=search, selected_status=status, selected_date=date_str)


@reception_bp.route('/appointments/<int:appointment_id>/confirm', methods=['POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def confirm_appointment(appointment_id: int):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'الموعد غير موجود'}), 404
    if appointment.status in {'CANCELLED', 'NO_SHOW', 'DONE'}:
        return jsonify({'success': False, 'message': 'لا يمكن تأكيد هذا الموعد'}), 400
    appointment.status = AppointmentState.CONFIRMED
    appointment.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True})


@reception_bp.route('/appointments/<int:appointment_id>/cancel', methods=['POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def cancel_appointment(appointment_id: int):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'الموعد غير موجود'}), 404
    if appointment.status == AppointmentState.DONE:
        return jsonify({'success': False, 'message': 'لا يمكن إلغاء موعد مكتمل'}), 400
    appointment.status = AppointmentState.CANCELLED
    appointment.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True})


@reception_bp.route('/appointments/<int:appointment_id>/no-show', methods=['POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def no_show_appointment(appointment_id: int):
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        return jsonify({'success': False, 'message': 'الموعد غير موجود'}), 404
    if appointment.status in {'CANCELLED', 'DONE'}:
        return jsonify({'success': False, 'message': 'لا يمكن وضع هذه الحالة'}), 400
    appointment.status = AppointmentState.NO_SHOW
    appointment.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'success': True})

@reception_bp.route('/create_appointment', methods=['GET', 'POST'])
@login_required
def create_appointment():
    """إنشاء موعد جديد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            from datetime import datetime, timedelta
            
            # دمج التاريخ والوقت
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            starts_at = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")

            # حقول إضافية من الواجهة: نوع الموعد، المدة، الأعراض
            appointment_type = (request.form.get('appointment_type') or '').strip() or None
            duration_raw = request.form.get('duration')
            duration_minutes = int(duration_raw) if duration_raw and str(duration_raw).isdigit() else 30
            symptoms = (request.form.get('symptoms') or '').strip() or None
            ends_at = starts_at + timedelta(minutes=duration_minutes)
            
            # دمج الملاحظات مع نوع الموعد والأعراض لضمان حفظها بدون تغيير المخطط
            base_notes = (request.form.get('notes') or '').strip()
            extra_parts = []
            if appointment_type:
                extra_parts.append(f"نوع الموعد: {appointment_type}")
            if symptoms:
                extra_parts.append(f"الأعراض: {symptoms}")
            combined_notes = base_notes
            if extra_parts:
                combined_notes = (base_notes + "\n" + "\n".join(extra_parts)).strip()

            appointment = Appointment(
                patient_id=request.form.get('patient_id'),
                doctor_id=request.form.get('doctor_id'),
                department_id=request.form.get('department_id'),
                starts_at=starts_at,
                ends_at=ends_at,
                notes=combined_notes,
                created_by=current_user.id
            )
            
            db.session.add(appointment)
            db.session.flush()

            follow_up_id = request.form.get('follow_up_id')
            follow_up_id = int(follow_up_id) if follow_up_id and str(follow_up_id).isdigit() else None
            if follow_up_id:
                fu = db.session.get(FollowUpRequest, follow_up_id)
                if fu and fu.status in {'PENDING'}:
                    fu.status = 'SCHEDULED'
                    fu.appointment_id = appointment.id
                    fu.updated_at = datetime.now(timezone.utc)

            db.session.commit()
            
            if _wants_json():
                return jsonify({'success': True, 'appointment_id': appointment.id})
            flash('تم إنشاء الموعد بنجاح.', 'success')
            return redirect(url_for('reception.appointments'))
            
        except Exception as e:
            db.session.rollback()
            if _wants_json():
                return jsonify({'success': False, 'message': 'تعذر إنشاء الموعد، يرجى التحقق من البيانات والمحاولة مرة أخرى'}), 400
            flash('تعذر إنشاء الموعد، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
            logging.error(f"Error creating appointment: {str(e)}")
    
    # جلب البيانات المطلوبة للنموذج
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    from datetime import date
    preselected_patient_id = request.args.get('patient_id', type=int)
    preset_department_id = request.args.get('department_id', type=int)
    preset_doctor_id = request.args.get('doctor_id', type=int)
    preset_date = (request.args.get('date') or '').strip() or None
    preset_type = (request.args.get('type') or '').strip() or None
    preset_duration = (request.args.get('duration') or '').strip() or None
    preset_symptoms = (request.args.get('symptoms') or '').strip() or None
    preset_notes = (request.args.get('notes') or '').strip() or None
    follow_up_id = request.args.get('follow_up_id', type=int)
    today = date.today()
    return render_template('reception/create_appointment.html',
                         patients=patients,
                         departments=departments,
                         doctors=doctors,
                         patient_id=preselected_patient_id,
                         preset_department_id=preset_department_id,
                         preset_doctor_id=preset_doctor_id,
                         preset_date=preset_date,
                         preset_type=preset_type,
                         preset_duration=preset_duration,
                         preset_symptoms=preset_symptoms,
                         preset_notes=preset_notes,
                         follow_up_id=follow_up_id,
                         today=today)

@reception_bp.route('/view_appointment/<int:appointment_id>')
@login_required
@role_required('reception', 'super_admin', 'manager')
def view_appointment(appointment_id):
    """عرض تفاصيل الموعد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        flash('الموعد غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    appt_type = None
    symptoms = None
    base_notes_lines = []
    for raw in (appointment.notes or '').splitlines():
        line = (raw or '').strip()
        if not line:
            continue
        if line.startswith('نوع الموعد:'):
            appt_type = line.replace('نوع الموعد:', '').strip() or appt_type
            continue
        if line.startswith('الأعراض:'):
            symptoms = line.replace('الأعراض:', '').strip() or symptoms
            continue
        base_notes_lines.append(line)
    base_notes = "\n".join(base_notes_lines).strip() or None
    return render_template('reception/view_appointment.html', appointment=appointment, appt_type=appt_type, symptoms=symptoms, base_notes=base_notes)

@reception_bp.route('/edit_appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def edit_appointment(appointment_id):
    """تعديل الموعد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        flash('الموعد غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    
    if request.method == 'POST':
        try:
            from datetime import datetime, timedelta
            
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            starts_at = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            
            duration_raw = request.form.get('duration')
            duration_minutes = int(duration_raw) if duration_raw and str(duration_raw).isdigit() else 30
            ends_at = starts_at + timedelta(minutes=duration_minutes)

            appointment.doctor_id = request.form.get('doctor_id')
            appointment.department_id = request.form.get('department_id')
            appointment.starts_at = starts_at
            appointment.ends_at = ends_at

            appointment_type = (request.form.get('appointment_type') or '').strip() or None
            symptoms = (request.form.get('symptoms') or '').strip() or None

            def _split_appt_notes(notes_text):
                base_lines = []
                for raw in (notes_text or '').splitlines():
                    line = (raw or '').strip()
                    if not line:
                        continue
                    if line.startswith('نوع الموعد:') or line.startswith('الأعراض:'):
                        continue
                    base_lines.append(line)
                return "\n".join(base_lines).strip() or None

            base_notes = _split_appt_notes((request.form.get('notes') or '').strip())
            extra_parts = []
            if appointment_type:
                extra_parts.append(f"نوع الموعد: {appointment_type}")
            if symptoms:
                extra_parts.append(f"الأعراض: {symptoms}")
            combined_notes = base_notes or ''
            if extra_parts:
                combined_notes = (combined_notes + "\n" + "\n".join(extra_parts)).strip()
            appointment.notes = combined_notes or None
            
            db.session.commit()
            flash('تم تحديث الموعد بنجاح.', 'success')
            return redirect(url_for('reception.view_appointment', appointment_id=appointment_id))
            
        except Exception as e:
            db.session.rollback()
            flash('تعذر تحديث الموعد، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
            logging.error(f"Error updating appointment: {str(e)}")
    
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()

    appt_type = None
    symptoms = None
    base_notes_lines = []
    for raw in (appointment.notes or '').splitlines():
        line = (raw or '').strip()
        if not line:
            continue
        if line.startswith('نوع الموعد:'):
            appt_type = line.replace('نوع الموعد:', '').strip() or appt_type
            continue
        if line.startswith('الأعراض:'):
            symptoms = line.replace('الأعراض:', '').strip() or symptoms
            continue
        base_notes_lines.append(line)

    appt_notes_base = "\n".join(base_notes_lines).strip()
    time_value = appointment.starts_at.strftime('%H:%M') if appointment.starts_at else ''
    date_value = appointment.starts_at.strftime('%Y-%m-%d') if appointment.starts_at else ''
    duration_value = 30
    try:
        if appointment.starts_at and appointment.ends_at:
            duration_value = int(max(0, (appointment.ends_at - appointment.starts_at).total_seconds()) // 60)
    except Exception:
        duration_value = 30

    return render_template(
        'reception/create_appointment.html',
        patients=patients,
        departments=departments,
        doctors=doctors,
        appointment=appointment,
        patient_id=appointment.patient_id,
        preset_department_id=appointment.department_id,
        preset_doctor_id=appointment.doctor_id,
        preset_date=date_value,
        preset_time=time_value,
        preset_type=(appt_type or ''),
        preset_duration=str(duration_value),
        preset_symptoms=(symptoms or ''),
        preset_notes=(appt_notes_base or ''),
        mode='edit'
    )

# API endpoints للاستقبال

@reception_bp.route('/api/available-times')
@login_required

def api_available_times():
    """API لجلب الأوقات المتاحة"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    doctor_id = request.args.get('doctor_id', type=int)
    date_str = request.args.get('date')

    if not doctor_id or not date_str:
        return jsonify({'success': False, 'message': 'معاملات مطلوبة'}), 400

    # جلب المواعيد الموجودة للطبيب في التاريخ المحدد
    try:
        from datetime import datetime
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except Exception:
        return jsonify({'success': False, 'message': 'تنسيق التاريخ غير صحيح'}), 400

    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    existing_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.starts_at >= start_of_day,
        Appointment.starts_at <= end_of_day,
        Appointment.status.in_([AppointmentState.SCHEDULED, AppointmentState.CONFIRMED])
    ).all()

    # الأوقات المتاحة (من 8 صباحاً إلى 5 مساءً)
    available_times = []
    for hour in range(8, 17):
        for minute in [0, 30]:
            slot_str = f"{hour:02d}:{minute:02d}"
            is_available = True

            for appointment in existing_appointments:
                if appointment.starts_at.strftime('%H:%M') == slot_str:
                    is_available = False
                    break

            if is_available:
                available_times.append(slot_str)

    return jsonify({
        'success': True,
        'available_times': available_times
    })



