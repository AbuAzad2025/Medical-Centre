 
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
from services.gatekeeper_service import GatekeeperService
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data
from app_factory import db
import logging
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService

reception_bp = Blueprint('reception', __name__)

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
    
    
    # إحصائيات شاملة للوحدة المركزية
    total_patients = Patient.query.count()
    today_visits = Visit.query.filter(
        Visit.visit_date == db.func.current_date()
    ).count()
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

@reception_bp.route('/display/waiting')
@login_required
@role_required('reception', 'super_admin', 'manager')
def waiting_display():
    return render_template('reception/waiting_display.html')

@reception_bp.route('/display/calls')
@login_required
@role_required('reception', 'super_admin', 'manager')
def calls_display():
    return render_template('reception/calls_display.html')


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

    if appointment.status == 'SCHEDULED':
        appointment.status = 'CONFIRMED'

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

@reception_bp.route('/patients')
@login_required
@role_required('reception', 'super_admin', 'manager')
def patients():
    """قائمة المرضى - الوحدة المركزية"""
    def _normalize_phone(v):
        if not v:
            return None
        s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
        if not s:
            return None
        if s.startswith('+'):
            digits = ''.join([c for c in s[1:] if c.isdigit()])
            return ('+' + digits) if digits else None
        digits = ''.join([c for c in s if c.isdigit()])
        return digits if digits else None

    def _normalize_national_id(v):
        if not v:
            return None
        s = ''.join([c for c in str(v).strip() if c.isdigit()])
        return s if s else None

    # البحث والفلترة
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    
    query = Patient.query
    
    if search:
        search_norm_phone = _normalize_phone(search)
        search_norm_nid = _normalize_national_id(search)
        conditions = [
            Patient.first_name.ilike(f'%{search}%'),
            Patient.last_name.ilike(f'%{search}%'),
            Patient.phone.ilike(f'%{search}%'),
            Patient.national_id.ilike(f'%{search}%')
        ]
        if search_norm_phone:
            conditions.append(Patient.phone == search_norm_phone)
        if search_norm_nid:
            conditions.append(Patient.national_id == search_norm_nid)
        if search.isdigit():
            try:
                conditions.append(Patient.id == int(search))
            except Exception:
                pass
        query = query.filter(db.or_(*conditions))
    
    if department_id:
        query = query.join(Visit, Visit.patient_id == Patient.id).filter(Visit.department_id == department_id).distinct()
    patients = query.all()
    departments = Department.query.all()
    from models.insurance import InsuranceCompany
    insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    
    return render_template('reception/patients.html', 
                         patients=patients, 
                         departments=departments,
                         insurance_companies=insurance_companies,
                         search=search,
                         selected_department=department_id)

@reception_bp.route('/add_patient', methods=['GET', 'POST'])
@login_required
@role_required('reception')
def add_patient():
    """إضافة مريض جديد - الوحدة المركزية"""
    
    
    if request.method == 'POST':
        try:
            # حقول أساسية
            national_id_raw = (request.form.get('national_id') or '').strip() or None
            phone_raw = (request.form.get('phone') or '').strip() or None
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            first_name_ar = (request.form.get('first_name_ar') or '').strip() or None
            last_name_ar = (request.form.get('last_name_ar') or '').strip() or None
            gender = request.form.get('gender') or None
            address = (request.form.get('address') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            admin_notes = (request.form.get('admin_notes') or '').strip() or None
            insurance_company_id = request.form.get('insurance_company_id')
            insurance_company_id = int(insurance_company_id) if insurance_company_id and str(insurance_company_id).isdigit() else None
            insurance_member_number = (request.form.get('insurance_member_number') or '').strip() or None
            marital_status = (request.form.get('marital_status') or '').strip() or None
            is_pregnant = str(request.form.get('is_pregnant') or '').lower() in ['true', 'on', '1', 'yes']
            pregnancy_weeks_raw = request.form.get('pregnancy_weeks')
            pregnancy_weeks = int(pregnancy_weeks_raw) if pregnancy_weeks_raw and pregnancy_weeks_raw.isdigit() else None
            last_menstruation_date_raw = request.form.get('last_menstruation_date')
            last_menstruation_date = None
            if last_menstruation_date_raw:
                try:
                    from datetime import datetime
                    last_menstruation_date = datetime.strptime(last_menstruation_date_raw, '%Y-%m-%d').date()
                except Exception:
                    last_menstruation_date = None
            pregnancy_notes = (request.form.get('pregnancy_notes') or '').strip() or None

            def _normalize_phone(v):
                if not v:
                    return None
                s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
                if not s:
                    return None
                if s.startswith('+'):
                    digits = ''.join([c for c in s[1:] if c.isdigit()])
                    return ('+' + digits) if digits else None
                digits = ''.join([c for c in s if c.isdigit()])
                return digits if digits else None

            def _normalize_national_id(v):
                if not v:
                    return None
                s = ''.join([c for c in str(v).strip() if c.isdigit()])
                return s if s else None

            def _validate_phone(v):
                if not v:
                    return False
                vv = v[1:] if v.startswith('+') else v
                return vv.isdigit() and (7 <= len(vv) <= 20)

            def _validate_national_id(v):
                if not v:
                    return True
                return v.isdigit() and (6 <= len(v) <= 32)

            phone = _normalize_phone(phone_raw)
            national_id = _normalize_national_id(national_id_raw)
            if not _validate_phone(phone):
                message = 'رقم الهاتف غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)
            if not _validate_national_id(national_id):
                message = 'رقم الهوية غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            # تحقق الحقول المطلوبة
            if not first_name or not last_name or not phone:
                message = 'يرجى ملء الاسم الأول واسم العائلة ورقم الهاتف'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            # منع التكرار: رقم الهوية
            if national_id:
                existing_by_id = Patient.query.filter_by(national_id=national_id).first()
                if existing_by_id:
                    message = f"المريض موجود مسبقاً برقم الهوية {national_id}"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_id.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            # منع التكرار: رقم الهاتف (تحذير قوي)
            if phone:
                existing_by_phone = Patient.query.filter(Patient.phone == phone).first()
                if existing_by_phone:
                    message = f"يوجد مريض بنفس رقم الهاتف ({phone})"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_phone.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            # تحويل تاريخ الميلاد
            birth_date_raw = request.form.get('birth_date')
            birth_date = None
            if birth_date_raw:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(birth_date_raw, '%Y-%m-%d').date()
                except Exception:
                    birth_date = None

            patient = Patient(
                national_id=national_id,
                first_name=first_name,
                last_name=last_name,
                first_name_ar=first_name_ar,
                last_name_ar=last_name_ar,
                phone=phone,
                birth_date=birth_date,
                gender=gender,
                address=address,
                notes=notes,
                admin_notes=admin_notes,
                insurance_company_id=insurance_company_id,
                insurance_member_number=insurance_member_number,
                marital_status=marital_status,
                is_pregnant=is_pregnant,
                pregnancy_weeks=pregnancy_weeks,
                last_menstruation_date=last_menstruation_date,
                pregnancy_notes=pregnancy_notes
            )
            
            db.session.add(patient)
            db.session.commit()
            
            if _wants_json():
                return jsonify({'success': True, 'patient_id': patient.id})
            flash('تم إضافة المريض بنجاح.', 'success')
            return redirect(url_for('reception.patients'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding patient: {str(e)}")
            if _wants_json():
                return jsonify({'success': False, 'message': 'تعذر إضافة المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى'}), 400
            flash('تعذر إضافة المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    # في طلبات GET نعيد التوجيه إلى قائمة المرضى مع فتح نموذج الإضافة داخل نفس القالب
    return redirect(url_for('reception.patients', show_add=1))

def _wants_json():
    """تحديد ما إذا كان الطلب يتوقع JSON (طلبات fetch)"""
    accept = (request.headers.get('Accept') or '').lower()
    xreq = (request.headers.get('X-Requested-With') or '').lower()
    return ('application/json' in accept) or (xreq == 'xmlhttprequest')

@reception_bp.route('/visits')
@login_required
@role_required('reception', 'manager')
def visits():
    """قائمة الزيارات - الوحدة المركزية"""
    # التحقق من الصلاحيات
    
    
    # البحث والفلترة
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    status = request.args.get('status', '')
    
    query = Visit.query
    
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
        query = query.filter(Visit.department_id == department_id)
    
    if status:
        query = query.filter(Visit.status == status)
    
    per_page = request.args.get('per_page', type=int) or 50
    per_page = max(10, min(per_page, 200))
    page = request.args.get('page', type=int) or 1
    page = max(1, page)
    total = query.count()
    visits = query.order_by(Visit.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
    departments = Department.query.all()
    
    return render_template('reception/visits.html', 
                         visits=visits, 
                         departments=departments,
                         search=search,
                         selected_department=department_id,
                         selected_status=status,
                         page=page,
                         per_page=per_page,
                         total=total)

@reception_bp.route('/visits/<int:visit_id>/archive', methods=['POST'])
@login_required
def archive_visit(visit_id):
    if current_user.role not in ['reception', 'super_admin']:
        flash('ليس لديك الصلاحيات لأرشفة الزيارة.', 'danger')
        return redirect(url_for('reception.visits'))
    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.visits'))
    can, msg = visit.can_be_archived()
    if not can:
        flash(msg, 'warning')
        return redirect(url_for('reception.visits'))
    try:
        visit.status = 'ARCHIVED'
        visit.archived_by = current_user.id
        from datetime import datetime as _dt, timezone
        visit.archived_at = _dt.now(timezone.utc)
        db.session.commit()
        flash('تمت أرشفة الزيارة بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error archiving visit: {str(e)}")
        flash('حدث خطأ أثناء الأرشفة', 'error')
    return redirect(url_for('reception.visits'))

# إنهاء الزيارة (اختصار للأرشفة) مع نفس قيود الدفع
@reception_bp.route('/visits/<int:visit_id>/end', methods=['POST'])
@login_required
def end_visit(visit_id):
    if current_user.role not in ['reception', 'super_admin']:
        flash('ليس لديك الصلاحيات لإنهاء الزيارة.', 'danger')
        return redirect(url_for('reception.visits'))
    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.visits'))
    # تأكد من أن الزيارة مكتملة قبل الأرشفة
    if visit.status != 'COMPLETED':
        flash('يجب إنهاء العلاج أولاً (حالة الزيارة مكتملة) قبل إنهاء الزيارة', 'warning')
        return redirect(url_for('reception.visits'))
    # استخدام نفس منطق الأرشفة لمنع إنهاء غير مدفوع
    can, msg = visit.can_be_archived()
    if not can:
        flash(msg, 'warning')
        return redirect(url_for('reception.visits'))
    try:
        visit.status = 'ARCHIVED'
        visit.archived_by = current_user.id
        from datetime import datetime as _dt, timezone
        visit.archived_at = _dt.now(timezone.utc)
        db.session.commit()
        flash('تم إنهاء الزيارة وأرشفتها بنجاح', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error ending visit: {str(e)}")
        flash('حدث خطأ أثناء إنهاء الزيارة', 'error')
    return redirect(url_for('reception.visits'))

@reception_bp.route('/export/visits')
@login_required
def export_visits():
    if current_user.role not in ['reception', 'manager', 'super_admin', 'accountant']:
        flash('ليس لديك الصلاحيات لتصدير الزيارات.', 'danger')
        return redirect(url_for('reception.visits'))
    import csv
    from io import StringIO
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    status = request.args.get('status', '')
    query = Visit.query
    if search:
        query = query.join(Patient).filter(
            db.or_(
                Patient.full_name.contains(search),
                Patient.phone.contains(search),
                Patient.national_id.contains(search)
            )
        )
    if department_id:
        query = query.filter(Visit.department_id == department_id)
    if status:
        query = query.filter(Visit.status == status)
    visits = query.order_by(Visit.created_at.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['VisitID','Patient','Department','Doctor','Type','Date','Total','Paid','PaymentStatus','Status'])
    for v in visits:
        writer.writerow([
            v.visit_number or v.id,
            getattr(v.patient, 'full_name', ''),
            getattr(getattr(v, 'department', None), 'name_ar', ''),
            getattr(getattr(v, 'doctor', None), 'full_name', ''),
            v.visit_type_display,
            v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else '',
            str(v.total_amount or 0),
            str(v.paid_amount or 0),
            v.payment_status,
            v.status
        ])
    resp = output.getvalue()
    from flask import Response
    return Response(
        resp,
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename=visits_export.csv'
        }
    )

@reception_bp.route('/api/pos/charge', methods=['POST'])
@login_required
def pos_charge():
    if current_user.role not in ['accountant', 'super_admin']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        amount_raw = request.form.get('amount') or request.json.get('amount') if request.is_json else None
        amount = float(amount_raw or 0)
        if amount <= 0:
            return jsonify({'success': False, 'message': 'قيمة المبلغ غير صحيحة'}), 400
        result = PosTerminalService.charge(amount)
        return jsonify(result), (200 if result.get('success') else 500)
    except Exception as e:
        logging.error(f"POS charge error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تنفيذ عملية الدفع حالياً'}), 500

@reception_bp.route('/visits/<int:visit_id>/transfer', methods=['POST'])
@login_required
def transfer_visit(visit_id):
    if current_user.role not in ['reception', 'super_admin']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    new_department_id = request.form.get('department_id') or (request.json.get('department_id') if request.is_json else None)
    new_doctor_id = request.form.get('doctor_id') or (request.json.get('doctor_id') if request.is_json else None)
    from services.queue_management_service import QueueManagementService
    ok, msg = QueueManagementService().transfer_visit(visit_id, new_department_id, new_doctor_id, transferred_by=current_user.id, source='reception')
    if ok:
        return jsonify({'success': True})
    status = 500
    if msg in {'invalid_department', 'doctor_required'}:
        status = 400
    elif msg in {'visit_not_found', 'department_not_found'}:
        status = 404
    elif msg == 'cannot_transfer_active_treatment':
        status = 409
    return jsonify({'success': False, 'message': msg}), status

@reception_bp.route('/visits/create', methods=['GET', 'POST'])
@login_required
@can_create_visits
def create_visit():
    """إنشاء زيارة جديدة - الوحدة المركزية المحسّنة"""
    
    if request.method == 'POST':
        try:
            # ========== المرحلة 1: جلب البيانات من النموذج ==========
            patient_id = request.form.get('patient_id')
            department_id = request.form.get('department_id')
            doctor_id = request.form.get('doctor_id')
            visit_type = request.form.get('visit_type', 'REGULAR')
            symptoms = request.form.get('symptoms', '')
            notes = request.form.get('notes', '')
            payment_method = request.form.get('payment_method')
            payment_method = (payment_method or '').lower()
            selected_tests = request.form.getlist('selected_tests')
            
            # بيانات التأمين
            insurance_provider = request.form.get('insurance_provider', '')
            insurance_policy_number = request.form.get('insurance_policy_number', '')
            insurance_coverage = request.form.get('insurance_coverage', '0')
            insurance_company_id = request.form.get('insurance_company_id')
            
            # بيانات البطاقة
            card_last_digits = request.form.get('card_last_digits', '')
            card_holder_name = request.form.get('card_holder_name', '')
            
            # بيانات الدفع القسري
            is_emergency = request.form.get('is_emergency') == 'on'
            is_force_payment = request.form.get('is_force_payment') == 'on'
            force_payment_reason = request.form.get('force_payment_reason', '')
            
            # مبلغ الدفع المبدئي
            amount_paid = request.form.get('amount_paid', '0')

            quick_emergency = str(request.form.get('quick_emergency') or '').lower() in ['1', 'true', 'on', 'yes']
            if quick_emergency:
                quick_patient_name = (request.form.get('quick_patient_name') or '').strip()
                quick_gender = (request.form.get('quick_gender') or '').strip() or None
                quick_age_raw = (request.form.get('quick_age') or '').strip()
                quick_reason = (request.form.get('quick_reason') or '').strip()

                if not patient_id:
                    if not quick_patient_name:
                        flash('اسم المريض (أو معرف مؤقت) مطلوب للطوارئ السريعة', 'error')
                        raise ValueError("Quick emergency patient name required")

                    parts = [p for p in quick_patient_name.split(' ') if p]
                    if len(parts) == 0:
                        flash('اسم المريض (أو معرف مؤقت) مطلوب للطوارئ السريعة', 'error')
                        raise ValueError("Quick emergency patient name required")
                    first_name = parts[0]
                    last_name = ' '.join(parts[1:]) if len(parts) > 1 else '-'

                    patient_notes_parts = []
                    if quick_age_raw:
                        patient_notes_parts.append(f"العمر التقريبي: {quick_age_raw}")
                    if quick_reason:
                        patient_notes_parts.append(f"سبب الدخول: {quick_reason}")
                    patient_notes = '\n'.join(patient_notes_parts) if patient_notes_parts else None

                    patient = Patient(
                        first_name=first_name,
                        last_name=last_name,
                        gender=quick_gender,
                        notes=patient_notes
                    )
                    db.session.add(patient)
                    db.session.flush()
                    patient_id = str(patient.id)

                try:
                    departments_all = Department.query.filter_by(is_active=True).all()
                    emergency_dept = next((d for d in departments_all if d.get_type() == 'emergency'), None)
                    if emergency_dept:
                        department_id = str(emergency_dept.id)
                except Exception:
                    pass

                doctor_id = None
                visit_type = 'EMERGENCY'
                is_emergency = True
                is_force_payment = True
                if not payment_method:
                    payment_method = 'force'
                if payment_method != 'force':
                    payment_method = 'force'
                if not force_payment_reason or len(force_payment_reason.strip()) < 10:
                    force_payment_reason = 'حالة طوارئ عاجلة، سيتم المراجعة من المدير لاحقاً'
                if quick_reason and not symptoms:
                    symptoms = quick_reason
                extra_notes = []
                if quick_age_raw:
                    extra_notes.append(f"العمر التقريبي: {quick_age_raw}")
                if quick_gender:
                    extra_notes.append(f"الجنس: {quick_gender}")
                if quick_reason:
                    extra_notes.append(f"سبب الدخول: {quick_reason}")
                if extra_notes:
                    extra_blob = '\n'.join(extra_notes)
                    notes = (notes or '').strip()
                    notes = f"{notes}\n{extra_blob}" if notes else extra_blob
            
            # ========== المرحلة 2: التحقق من البيانات الأساسية ==========
            if not patient_id:
                flash('يجب اختيار مريض', 'error')
                raise ValueError("Patient is required")
            
            if not department_id:
                flash('يجب اختيار قسم', 'error')
                raise ValueError("Department is required")
            
            # إلزام اختيار طبيب للأقسام التخصصية (غير المختبر/الأشعة/الطوارئ)
            try:
                dept_obj = db.session.get(Department, int(department_id))
            except Exception:
                dept_obj = None
            if not dept_obj:
                flash('القسم غير موجود', 'error')
                raise ValueError("Department not found")
            if getattr(dept_obj, 'get_type', lambda: 'general')() == 'general' and not doctor_id:
                flash('يجب اختيار طبيب للقسم التخصصي', 'error')
                raise ValueError("Doctor is required for general departments")

            if not payment_method:
                flash('يجب تحديد طريقة الدفع', 'error')
                raise ValueError("Payment method is required")
            
            # ========== المرحلة 3: التحقق من صلاحية طريقة الدفع ==========
            is_valid_method, method_message = GatekeeperService.validate_payment_method(
                payment_method, 
                amount_paid
            )
            if not is_valid_method:
                flash(method_message, 'error')
                raise ValueError(method_message)
            
            # ========== المرحلة 4: التحقق الخاص بكل طريقة دفع ==========
            
            # تأمين: التحقق من البيانات
            if payment_method == 'insurance':
                is_valid_ins, ins_message = GatekeeperService.validate_insurance(
                    insurance_provider,
                    insurance_policy_number,
                    insurance_coverage
                )
                if not is_valid_ins:
                    flash(ins_message, 'error')
                    raise ValueError(ins_message)
            
            # بطاقة: التحقق من البيانات
            elif payment_method in ['visa', 'card']:
                is_valid_card, card_message = GatekeeperService.validate_card_payment(
                    card_last_digits,
                    card_holder_name
                )
                if not is_valid_card:
                    flash(card_message, 'error')
                    raise ValueError(card_message)
            
            # دفع قسري: التحقق من الموافقة
            elif payment_method == 'force' or is_force_payment:
                # يجب أن يكون هناك سبب
                if not force_payment_reason or len(force_payment_reason.strip()) < 10:
                    flash('يجب تقديم سبب واضح للدفع القسري (10 أحرف على الأقل)', 'error')
                    raise ValueError("Force payment reason required")
                
                # ملاحظة: الموافقة ستكون من المدير لاحقاً
                # الاستقبال فقط يُنشئ الزيارة بانتظار الموافقة
                is_force_payment = True
            
            # ========== المرحلة 5: إنشاء الزيارة ==========
            visit = Visit(
                patient_id=patient_id,
                department_id=department_id,
                doctor_id=doctor_id if doctor_id else None,
                visit_type=visit_type,
                symptoms=symptoms,
                notes=notes,
                status='OPEN',
                payment_method=payment_method.upper(),
                payment_status='PENDING',
                is_emergency=is_emergency,
                is_force_payment=is_force_payment,
                created_by=current_user.id,
                currency='ILS',
                created_at=datetime.utcnow()
            )
            
            # ========== المرحلة 6: إضافة بيانات التأمين ==========
            if payment_method == 'insurance':
                visit.insurance_provider = insurance_provider
                visit.insurance_policy_number = insurance_policy_number
                visit.insurance_coverage_percentage = float(insurance_coverage)
                if insurance_company_id and str(insurance_company_id).isdigit():
                    try:
                        from models.insurance import InsuranceCompany
                        company = db.session.get(InsuranceCompany, int(insurance_company_id))
                        if company:
                            visit.insurance_company_id = company.id
                            if not visit.insurance_provider:
                                visit.insurance_provider = company.name_ar or company.name
                    except Exception:
                        pass
            
            # ========== المرحلة 7: إضافة بيانات البطاقة ==========
            elif payment_method in ['visa', 'card']:
                visit.card_number_last_digits = card_last_digits
                visit.card_holder_name = card_holder_name
            
            # ========== المرحلة 8: إضافة بيانات الدفع القسري ==========
            elif is_force_payment:
                visit.force_payment_reason = force_payment_reason
                # الموافقة ستكون لاحقاً من المدير
            
            # ========== المرحلة 9: حساب التكلفة ==========
            dt = dept_obj.get_type() if dept_obj else 'general'
            
            # حفظ الخدمات المختارة
            if selected_tests:
                from models.service import ServiceMaster
                from models.lab_request import LabRequest
                from models.radiology_request import RadiologyRequest
                
                ids = [int(x) for x in selected_tests if str(x).isdigit()]
                services = ServiceMaster.query.filter(ServiceMaster.id.in_(ids), ServiceMaster.is_active == True).all()
                
                total_cost = 0.0
                lab_services = []
                rad_services = []
                
                for s in services:
                    price = float(s.insurance_price or s.base_price) if payment_method == 'insurance' else float(s.base_price or 0)
                    total_cost += price
                    
                    if s.category == 'lab':
                        lab_services.append(s)
                    elif s.category == 'radiology':
                        rad_services.append(s)
                
                visit.total_amount = round(total_cost, 2)
                
                # إنشاء طلبات المختبر
                if lab_services:
                    lab_req = LabRequest(
                        visit=visit,
                        patient_id=patient_id,
                        requested_by=current_user.id,
                        status='REQUESTED',
                        notes=f"Generated from reception: {', '.join([s.name for s in lab_services])}"
                    )
                    db.session.add(lab_req)
                    # هنا يمكننا إضافة تفاصيل الخدمات إذا كان هناك جدول تفاصيل، 
                    # لكن حالياً سنكتفي بإنشاء الطلب ووضع الأسماء في الملاحظات 
                    # أو يمكننا تحسين LabRequest لاحقاً ليقبل قائمة خدمات
                
                # إنشاء طلبات الأشعة
                if rad_services:
                    for s in rad_services:
                        rad_req = RadiologyRequest(
                            visit=visit,
                            patient_id=patient_id,
                            requested_by=current_user.id,
                            status='REQUESTED',
                            modality='XRay', # افتراضي
                            body_part=s.name, # استخدام اسم الخدمة كجزء الجسم
                            notes=f"Service: {s.name}"
                        )
                        db.session.add(rad_req)

            else:
                visit_cost = calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method)
                visit.total_amount = visit_cost
            
            # حساب الضرائب
            tax_type = request.form.get('tax_type', 'none')
            TAX_RATE = 0.15
            
            visit.tax_percent = 0
            visit.tax_amount = 0
            visit.is_tax_inclusive = False
            
            if tax_type == 'inclusive':
                # المبلغ يشمل الضريبة
                visit.is_tax_inclusive = True
                visit.tax_percent = TAX_RATE * 100
                # total_amount هو المبلغ النهائي، نحسب الضريبة منه
                if visit.total_amount:
                    base_amount = float(visit.total_amount) / (1 + TAX_RATE)
                    visit.tax_amount = round(float(visit.total_amount) - base_amount, 2)
                # visit.total_amount يبقى كما هو
                
            elif tax_type == 'exclusive':
                # المبلغ لا يشمل الضريبة، نضيفها
                visit.is_tax_inclusive = False
                visit.tax_percent = TAX_RATE * 100
                if visit.total_amount:
                    tax_val = float(visit.total_amount) * TAX_RATE
                    visit.tax_amount = round(tax_val, 2)
                    visit.total_amount = round(float(visit.total_amount) + tax_val, 2)

            # حساب مبالغ التأمين
            if payment_method == 'insurance':
                visit.calculate_insurance_amounts()
            
            # ========== المرحلة 10: معالجة الدفع المبدئي ==========
            if payment_method in ['cash', 'visa', 'card']:
                # دفع مباشر
                if amount_paid and float(amount_paid) > 0:
                    visit.paid_amount = float(amount_paid)
                    
                    # إذا دفع كامل المبلغ
                    if visit.is_fully_paid:
                        visit.payment_status = 'PAID'
                    else:
                        visit.payment_status = 'PARTIAL'
                    
                    # إنشاء سجل دفع
                    from models.payment import PaymentMethod
                    payment_method_value = PaymentMethod.CARD if payment_method in ['visa', 'card'] else PaymentMethod.CASH
                    payment = Payment(
                        patient_id=patient_id,
                        visit_id=None,
                        method=payment_method_value,
                        amount=float(amount_paid),
                        currency='ILS',
                        status=PaymentStatus.CONFIRMED,
                        received_by=current_user.id,
                        payment_date=datetime.utcnow()
                    )
                    
                    # حفظ بيانات البطاقة في الدفع
                    if payment_method in ['visa', 'card']:
                        payment.reference = f"CARD-****{card_last_digits}"
                    
                    db.session.add(payment)
            
            elif payment_method == 'insurance':
                # دفع حصة المريض
                if amount_paid and float(amount_paid) >= float(visit.patient_share or 0):
                    visit.paid_amount = float(amount_paid)
                    visit.payment_status = 'PARTIAL'  # لأن التأمين لم يدفع بعد
                    
                    # إنشاء سجل دفع لحصة المريض
                    payment = Payment(
                        patient_id=patient_id,
                        method=PaymentMethod.CASH,  # حصة المريض نقداً
                        amount=float(amount_paid),
                        currency='ILS',
                        status=PaymentStatus.CONFIRMED,
                        received_by=current_user.id,
                        notes=f"حصة المريض من التأمين - {insurance_provider}",
                        payment_date=datetime.now(timezone.utc)
                    )
                    db.session.add(payment)
                else:
                    flash('يجب دفع حصة المريض على الأقل', 'warning')
            
            elif is_force_payment:
                # دفع قسري - بانتظار الموافقة
                visit.payment_status = 'PENDING'
                visit.paid_amount = 0
            
            # ========== المرحلة 11: حفظ الزيارة ==========
            db.session.add(visit)
            db.session.flush()  # للحصول على visit.id
            
            # تحديث visit_id في سجل الدفع
            if 'payment' in locals():
                payment.visit_id = visit.id
            if dt == 'lab' and selected_tests:
                from models.lab_request import LabRequest, LabResult
                lab_req = LabRequest(visit_id=visit.id, patient_id=patient_id, requested_by=current_user.id, status='REQUESTED')
                db.session.add(lab_req)
                db.session.flush()
                from models.service import ServiceMaster
                ids = [int(x) for x in selected_tests if str(x).isdigit()]
                services = ServiceMaster.query.filter(ServiceMaster.id.in_(ids), ServiceMaster.is_active == True).all()
                for s in services:
                    lr = LabResult(request_id=lab_req.id, patient_id=patient_id, test_code=s.code, test_name=s.name_ar or s.name, status='PENDING')
                    db.session.add(lr)
                visit.lab_tests_ordered = True
            elif dt == 'radiology' and selected_tests:
                from models.radiology_request import RadiologyRequest
                from models.service import ServiceMaster
                ids = [int(x) for x in selected_tests if str(x).isdigit()]
                services = ServiceMaster.query.filter(ServiceMaster.id.in_(ids), ServiceMaster.is_active == True).all()
                for s in services:
                    modality = 'XRay' if (s.code or '').upper().find('XRAY') != -1 else None
                    body_part = s.name_ar or s.name
                    rad_req = RadiologyRequest(visit_id=visit.id, patient_id=patient_id, requested_by=current_user.id, status='REQUESTED', modality=modality, body_part=body_part, notes=s.description)
                    db.session.add(rad_req)
                visit.radiology_ordered = True

            # تحديث عداد زيارات المريض
            try:
                from models.patient_visit_counter import PatientVisitCounter
                pvc = PatientVisitCounter.query.filter_by(patient_id=patient_id).first()
                if not pvc:
                    pvc = PatientVisitCounter(patient_id=patient_id, visit_count=0)
                    db.session.add(pvc)
                pvc.visit_count = (pvc.visit_count or 0) + 1
                from datetime import datetime as _dt, timezone
                pvc.last_visit_at = _dt.now(timezone.utc)
            except Exception as _counter_err:
                logging.warning(f"Could not update patient visit counter: {str(_counter_err)}")
            
            db.session.commit()
            
            # ========== المرحلة 12: إضافة للطابور ==========
            # نحاول إضافة المريض للطابور، والخدمة تتحقق من شروط الدفع والديون
            try:
                queue_result = add_patient_to_queue_auto(visit.id, department_id, doctor_id)
                
                # توحيد صيغة النتيجة (نجاح، رسالة)
                if isinstance(queue_result, tuple):
                    q_success, q_msg = queue_result
                else:
                    q_success, q_msg = queue_result, "خطأ غير محدد"

                if q_success:
                    flash(f'تمت إضافة المريض للطابور: {q_msg}', 'info')
                else:
                    # إذا فشل (مثلاً بسبب عدم الدفع)، نعرض رسالة تحذيرية
                    flash(f'تنبيه: لم يتم إضافة المريض للطابور ({q_msg})', 'warning')

            except Exception as queue_error:
                logging.warning(f"Could not add to queue: {str(queue_error)}")
                flash('حدث خطأ أثناء محاولة إضافة المريض للطابور', 'warning')
            
            # ========== المرحلة 13: الرسائل والتوجيه ==========
            if is_force_payment:
                flash('تم إنشاء الزيارة بنجاح. في انتظار موافقة المدير على الدفع القسري.', 'warning')
            elif visit.payment_status == 'PAID':
                flash('تم إنشاء الزيارة ودفع المبلغ بنجاح.', 'success')
            elif visit.payment_status == 'PARTIAL':
                remaining = visit.remaining_amount
                flash(f'تم إنشاء الزيارة. المبلغ المتبقي: {remaining:.2f} شيكل', 'info')
            else:
                flash('تم إنشاء الزيارة بنجاح.', 'success')
            
            # طباعة الإيصال إن طُلب
            print_receipt = request.form.get('print_receipt') == 'true'
            if print_receipt and visit.paid_amount > 0:
                return redirect(url_for('reception.print_receipt', visit_id=visit.id))
            
            return redirect(url_for('reception.visits'))
            
        except ValueError as ve:
            # أخطاء التحقق - تم عرضها بالفعل
            db.session.rollback()
            logging.warning(f"Validation error in create_visit: {str(ve)}")
        except Exception as e:
            # أخطاء غير متوقعة
            db.session.rollback()
            flash('تعذر إنشاء الزيارة، يرجى المحاولة مرة أخرى', 'error')
            logging.error(f"Error creating visit: {str(e)}", exc_info=True)
    
    # ========== GET Request: عرض النموذج ==========
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    from models.insurance import InsuranceCompany
    insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    preselected_patient_id = request.args.get('patient_id', type=int)
    preselected_department_id = request.args.get('department_id', type=int)
    preselected_doctor_id = request.args.get('doctor_id', type=int)
    preselected_patient = db.session.get(Patient, preselected_patient_id) if preselected_patient_id else None
    
    return render_template('reception/create_visit.html',
                         patients=patients,
                         departments=departments,
                         doctors=doctors,
                         insurance_companies=insurance_companies,
                         preselected_patient_id=preselected_patient_id,
                         preselected_department_id=preselected_department_id,
                         preselected_doctor_id=preselected_doctor_id,
                         preselected_patient=preselected_patient)

@reception_bp.route('/appointments')
@login_required
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
                Patient.full_name.contains(search),
                Patient.phone.contains(search),
                Patient.national_id.contains(search)
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
        except Exception:
            pass
    
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
    confirmed_count = db.session.query(func.count(Appointment.id)).filter(Appointment.status == 'CONFIRMED').scalar() or 0
    pending_count = db.session.query(func.count(Appointment.id)).filter(Appointment.status == 'SCHEDULED').scalar() or 0

    return render_template('reception/appointments.html', 
                         appointments=appointments, 
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
                Patient.full_name.contains(search),
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
        except Exception:
            pass

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
    appointment.status = 'CONFIRMED'
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
    if appointment.status == 'DONE':
        return jsonify({'success': False, 'message': 'لا يمكن إلغاء موعد مكتمل'}), 400
    appointment.status = 'CANCELLED'
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
    appointment.status = 'NO_SHOW'
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

@reception_bp.route('/staff/schedule', methods=['GET', 'POST'])
@login_required
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
@reception_bp.route('/view_patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    """عرض تفاصيل المريض - الوحدة المركزية"""
    allowed_roles = ['reception', 'manager']
    if current_user.role not in allowed_roles:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    
    # تقييد الوصول حسب الدور للمختبر والأشعة
    try:
        if current_user.role in ['lab', 'radiology']:
            from services.access_control_service import AccessControlService
            accessible_patients = AccessControlService.get_user_accessible_patients(current_user.id)
            if not any(p.id == patient_id for p in accessible_patients):
                flash('لا تملك صلاحية عرض هذا المريض', 'warning')
                return redirect(url_for('main.dashboard'))
    except Exception as e:
        logging.warning(f"Access check failed in view_patient: {str(e)}")
    
    visits = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.created_at.desc()).limit(10).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.starts_at.desc()).limit(10).all()
    
    # جلب طلبات المختبر والأشعة
    from models.lab_request import LabRequest
    from models.radiology_request import RadiologyRequest
    
    lab_requests = LabRequest.query.filter_by(patient_id=patient_id).order_by(LabRequest.created_at.desc()).limit(10).all()
    radiology_requests = RadiologyRequest.query.filter_by(patient_id=patient_id).order_by(RadiologyRequest.created_at.desc()).limit(10).all()
    
    template = 'reception/view_patient.html'
    
    return render_template(template, 
                         patient=patient, 
                         visits=visits, 
                         appointments=appointments,
                         lab_requests=lab_requests,
                         radiology_requests=radiology_requests)

@reception_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
@can_modify_patient_data
def edit_patient(patient_id):
    """تعديل بيانات المريض - الوحدة المركزية"""
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.queue_management'))
    
    if request.method == 'POST':
        try:
            national_id_raw = (request.form.get('national_id') or '').strip() or None
            phone_raw = (request.form.get('phone') or '').strip() or None
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            first_name_ar = (request.form.get('first_name_ar') or '').strip() or None
            last_name_ar = (request.form.get('last_name_ar') or '').strip() or None
            gender = request.form.get('gender') or None
            address = (request.form.get('address') or '').strip() or None
            notes = (request.form.get('notes') or '').strip() or None
            admin_notes = (request.form.get('admin_notes') or '').strip() or None
            insurance_company_id = request.form.get('insurance_company_id')
            insurance_company_id = int(insurance_company_id) if insurance_company_id and str(insurance_company_id).isdigit() else None
            insurance_member_number = (request.form.get('insurance_member_number') or '').strip() or None
            marital_status = (request.form.get('marital_status') or '').strip() or None
            is_pregnant = str(request.form.get('is_pregnant') or '').lower() in ['true', 'on', '1', 'yes']
            pregnancy_weeks_raw = request.form.get('pregnancy_weeks')
            pregnancy_weeks = int(pregnancy_weeks_raw) if pregnancy_weeks_raw and pregnancy_weeks_raw.isdigit() else None
            last_menstruation_date_raw = request.form.get('last_menstruation_date')
            last_menstruation_date = None
            if last_menstruation_date_raw:
                try:
                    from datetime import datetime
                    last_menstruation_date = datetime.strptime(last_menstruation_date_raw, '%Y-%m-%d').date()
                except Exception:
                    last_menstruation_date = None
            pregnancy_notes = (request.form.get('pregnancy_notes') or '').strip() or None

            def _normalize_phone(v):
                if not v:
                    return None
                s = ''.join([ch for ch in str(v).strip() if ch not in {' ', '-', '(', ')', '.'}])
                if not s:
                    return None
                if s.startswith('+'):
                    digits = ''.join([c for c in s[1:] if c.isdigit()])
                    return ('+' + digits) if digits else None
                digits = ''.join([c for c in s if c.isdigit()])
                return digits if digits else None

            def _normalize_national_id(v):
                if not v:
                    return None
                s = ''.join([c for c in str(v).strip() if c.isdigit()])
                return s if s else None

            def _validate_phone(v):
                if not v:
                    return False
                vv = v[1:] if v.startswith('+') else v
                return vv.isdigit() and (7 <= len(vv) <= 20)

            def _validate_national_id(v):
                if not v:
                    return True
                return v.isdigit() and (6 <= len(v) <= 32)

            phone = _normalize_phone(phone_raw)
            national_id = _normalize_national_id(national_id_raw)
            if not _validate_phone(phone):
                message = 'رقم الهاتف غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)
            if not _validate_national_id(national_id):
                message = 'رقم الهوية غير صالح'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            if not first_name or not last_name or not phone:
                message = 'يرجى ملء الاسم الأول واسم العائلة ورقم الهاتف'
                if _wants_json():
                    return jsonify({'success': False, 'message': message}), 400
                flash(message, 'error')
                raise ValueError(message)

            if national_id and national_id != (patient.national_id or None):
                existing_by_id = Patient.query.filter_by(national_id=national_id).first()
                if existing_by_id and existing_by_id.id != patient.id:
                    message = f"المريض موجود مسبقاً برقم الهوية {national_id}"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_id.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            if phone and phone != (patient.phone or None):
                existing_by_phone = Patient.query.filter(Patient.phone == phone, Patient.id != patient.id).first()
                if existing_by_phone:
                    message = f"يوجد مريض بنفس رقم الهاتف ({phone})"
                    if _wants_json():
                        return jsonify({'success': False, 'message': message, 'patient_id': existing_by_phone.id}), 409
                    flash(message, 'warning')
                    raise ValueError(message)

            birth_date_raw = request.form.get('birth_date')
            birth_date = None
            if birth_date_raw:
                try:
                    from datetime import datetime
                    birth_date = datetime.strptime(birth_date_raw, '%Y-%m-%d').date()
                except Exception:
                    birth_date = None

            patient.national_id = national_id
            patient.first_name = first_name
            patient.last_name = last_name
            patient.first_name_ar = first_name_ar
            patient.last_name_ar = last_name_ar
            patient.phone = phone
            patient.birth_date = birth_date
            patient.gender = gender
            patient.address = address
            patient.notes = notes
            patient.admin_notes = admin_notes
            patient.insurance_company_id = insurance_company_id
            patient.insurance_member_number = insurance_member_number
            patient.marital_status = marital_status
            patient.is_pregnant = is_pregnant
            patient.pregnancy_weeks = pregnancy_weeks
            patient.last_menstruation_date = last_menstruation_date
            patient.pregnancy_notes = pregnancy_notes
            
            db.session.commit()
            if _wants_json():
                return jsonify({'success': True, 'patient_id': patient.id})
            flash('تم تحديث بيانات المريض بنجاح.', 'success')
            return redirect(url_for('reception.view_patient', patient_id=patient_id))
            
        except Exception as e:
            db.session.rollback()
            if _wants_json():
                return jsonify({'success': False, 'message': 'تعذر تحديث بيانات المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى'}), 400
            flash('تعذر تحديث بيانات المريض، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
            logging.error(f"Error updating patient: {str(e)}")
    
    patients = Patient.query.order_by(Patient.created_at.desc()).limit(200).all()
    departments = Department.query.all()
    from models.insurance import InsuranceCompany
    insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    return render_template('reception/patients.html', 
                         patients=patients,
                         patient=patient,
                         departments=departments,
                         insurance_companies=insurance_companies,
                         mode='edit')

@reception_bp.route('/delete_patient/<int:patient_id>', methods=['POST'])
@login_required
@can_modify_patient_data
def delete_patient(patient_id):
    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('reception.patients'))
    try:
        from models.receipt import Receipt
        from models.medication import Prescription
        has_receipts = db.session.query(Receipt.id).filter_by(patient_id=patient_id).first() is not None
        has_prescriptions = db.session.query(Prescription.id).filter_by(patient_id=patient_id).first() is not None
        if has_receipts or has_prescriptions:
            parts = []
            if has_receipts:
                parts.append('سندات قبض')
            if has_prescriptions:
                parts.append('روشتات')
            flash('لا يمكن حذف المريض لوجود ' + ' و '.join(parts) + '. يرجى أرشفة/حذف السجلات المرتبطة أولاً.', 'warning')
            return redirect(url_for('reception.patients'))
        db.session.delete(patient)
        db.session.commit()
        flash('تم حذف المريض بنجاح.', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting patient: {str(e)}")
        flash('حدث خطأ أثناء حذف المريض.', 'error')
    return redirect(url_for('reception.patients'))

@reception_bp.route('/view_visit/<int:visit_id>')
@login_required
def view_visit(visit_id):
    """عرض تفاصيل الزيارة - الوحدة المركزية"""
    if current_user.role not in ['reception', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))
    return render_template('reception/visits.html', visit=visit, mode='view')

@reception_bp.route('/process_payment/<int:visit_id>', methods=['POST'])
@login_required
def process_payment(visit_id):
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))
    try:
        from models.invoice import Invoice, InvoiceService as InvoiceLine

        existing_invoice = Invoice.query.filter(Invoice.visit_id == visit.id).order_by(Invoice.created_at.desc()).first()
        if not existing_invoice:
            invoice = Invoice(
                invoice_number=f"INV-{visit.id}-{int(datetime.now(timezone.utc).timestamp())}",
                visit_id=visit.id,
                created_by=current_user.id,
                status='ISSUED',
                currency=getattr(visit, 'currency', None) or 'ILS',
                total_amount=visit.total_amount or 0,
                paid_amount=visit.paid_amount or 0,
            )
            db.session.add(invoice)
            db.session.flush()

            if float(visit.total_amount or 0) > 0:
                line = InvoiceLine(
                    invoice_id=invoice.id,
                    department_id=visit.department_id,
                    visit_id=visit.id,
                    service_code='VISIT',
                    service_name='خدمات زيارة',
                    quantity=1,
                    unit_price=visit.total_amount or 0,
                    total_price=visit.total_amount or 0,
                )
                db.session.add(line)

        remaining = float(visit.remaining_amount or 0)
        paid_amount = float(visit.paid_amount or 0)
        if remaining <= 0:
            visit.payment_status = 'PAID'
        elif paid_amount > 0:
            visit.payment_status = 'PARTIAL'
        else:
            visit.payment_status = 'PENDING'

        db.session.commit()
        flash('تم إرسال الزيارة للمحاسبة بنجاح.', 'success')
        return redirect(url_for('reception.view_visit', visit_id=visit_id))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error sending visit to accounting: {str(e)}")
        flash('حدث خطأ أثناء إرسال الزيارة للمحاسبة.', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/print_receipt/<int:visit_id>')
@login_required
def print_receipt(visit_id):
    """طباعة سند القبض - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))
    try:
        from models.queue_management import QueueManagement
        from models.patient_satisfaction import PatientSatisfactionSurvey
        queue_ticket = QueueManagement.query.filter_by(visit_id=visit_id).order_by(QueueManagement.created_at.desc()).first()
    except Exception:
        queue_ticket = None
    try:
        from decimal import Decimal, ROUND_HALF_UP
        from models.pricing import DoctorPricing
        total = Decimal(str(visit.total_amount or 0))
        doctor_fee = None
        # محاولة استخدام تسعير الطبيب إن وجد
        pricing = None
        try:
            pricing = DoctorPricing.query.filter(
                DoctorPricing.doctor_id == visit.doctor_id,
                DoctorPricing.department_id == visit.department_id,
                DoctorPricing.is_active == True
            ).order_by(DoctorPricing.effective_from.desc()).first()
        except Exception:
            pricing = None
        if pricing:
            if getattr(visit, 'visit_type', None) in ['FIRST', 'first', 'CONSULTATION', 'consultation']:
                if pricing.consultation_price:
                    doctor_fee = Decimal(str(pricing.consultation_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            elif getattr(visit, 'visit_type', None) in ['FOLLOW_UP', 'follow_up']:
                if pricing.follow_up_price:
                    doctor_fee = Decimal(str(pricing.follow_up_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            elif getattr(visit, 'is_emergency', False):
                if pricing.emergency_price:
                    doctor_fee = Decimal(str(pricing.emergency_price)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # إن لم تتوفر أسعار محددة، استخدم نسبة افتراضية 30%
        if doctor_fee is None:
            doctor_fee = (total * Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        # لا يتجاوز رسم الطبيب الإجمالي
        if doctor_fee > total:
            doctor_fee = total
        service_cost = (total - doctor_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        follow_up_discount = Decimal('0.00')
        if getattr(visit, 'visit_type', None) in ['FOLLOW_UP', 'follow_up']:
            # خصم المتابعة إن كان النظام يعتمد خصماً موحداً
            follow_up_discount = (total * Decimal('0.30')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        doctor_fee = None
        service_cost = None
        follow_up_discount = None
    try:
        last_payment = Payment.query.filter_by(visit_id=visit_id).order_by(Payment.created_at.desc()).first()
    except Exception:
        last_payment = None
    survey_url = None
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey
        survey = PatientSatisfactionSurvey.query.filter_by(visit_id=visit_id).first()
        if survey:
            survey_url = url_for('reception.survey', token=survey.token, _external=True)
    except Exception:
        survey_url = None
    return render_template(
        'print/receipt.html',
        visit=visit,
        queue_ticket=queue_ticket,
        printed_at=datetime.now(timezone.utc),
        service_cost=service_cost,
        doctor_fee=doctor_fee,
        follow_up_discount=follow_up_discount,
        last_payment=last_payment,
        survey_url=survey_url
    )

@reception_bp.route('/print_invoice/<int:invoice_id>')
@login_required
def print_invoice(invoice_id):
    """طباعة الفاتورة"""
    if current_user.role not in ['reception', 'super_admin', 'manager', 'accountant']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    from models.invoice import Invoice
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash('الفاتورة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))
    return render_template('print/invoice.html', invoice=invoice)

@reception_bp.route('/print_prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    """طباعة الروشتة الطبية"""
    if current_user.role not in ['doctor', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    from models.medical_record import Prescription
    prescription = db.session.get(Prescription, prescription_id)
    if not prescription:
        flash('الوصفة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))
    return render_template('print/prescription.html', prescription=prescription)

@reception_bp.route('/view_appointment/<int:appointment_id>')
@login_required
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
@reception_bp.route('/api/smart-patient-search')
@login_required
def api_smart_patient_search():
    """API للبحث الذكي عن المرضى"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'patients': []})
    
    try:
        from datetime import datetime
        parsed_date = None
        try:
            if len(search_term) >= 8:
                parsed_date = datetime.strptime(search_term, '%Y-%m-%d').date()
        except Exception:
            parsed_date = None
        filters = [
            Patient.first_name.ilike(f'%{search_term}%'),
            Patient.last_name.ilike(f'%{search_term}%'),
            Patient.national_id.ilike(f'%{search_term}%'),
            Patient.phone.ilike(f'%{search_term}%')
        ]
        query = Patient.query
        if parsed_date:
            query = query.filter(db.or_(*filters, Patient.birth_date == parsed_date))
        else:
            query = query.filter(db.or_(*filters))
        patients = query.order_by(Patient.created_at.desc()).limit(10).all()
        results = []
        for patient in patients:
            results.append({
                'id': patient.id,
                'full_name': patient.full_name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.strftime('%Y-%m-%d') if patient.birth_date else None,
                'gender': patient.gender,
                'address': patient.address
            })
        return jsonify({'patients': results})
    except Exception as e:
        logging.error(f"Error in smart patient search: {str(e)}")
        return jsonify({'error': 'حدث خطأ في البحث'}), 500

@reception_bp.route('/api/doctors')
@login_required
def api_doctors():
    """API لجلب الأطباء"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    
    department_id = request.args.get('department_id')
    appointment_type = request.args.get('appointment_type')
    
    query = User.query.filter_by(role='doctor', is_active=True)
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    doctors = query.all()
    
    return jsonify({
        'success': True,
        'doctors': [{'id': doctor.id, 'full_name': doctor.full_name} for doctor in doctors]
    })

@reception_bp.route('/api/department-staff')
@login_required
def api_department_staff():
    """API لجلب موظفي القسم المناسبين"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    
    department_id = request.args.get('department_id')
    if not department_id:
        return jsonify({'error': 'معرف القسم مطلوب'}), 400
    
    try:
        # جلب موظفي القسم حسب نوع القسم
        department = db.session.get(Department, department_id)
        if not department:
            return jsonify({'error': 'القسم غير موجود'}), 404
        
        staff = []
        
        dept_type = department.get_type()
        roles = ['doctor']
        if dept_type == 'lab':
            roles = ['lab', 'technician']
        elif dept_type == 'radiology':
            roles = ['radiology', 'technician']
        elif dept_type == 'emergency':
            roles = ['emergency', 'doctor', 'nurse']
        staff = User.query.filter(
            User.role.in_(roles) if len(roles) > 1 else (User.role == roles[0]),
            User.department_id == department_id,
            User.is_active == True
        ).all()
        
        results = []
        for person in staff:
            results.append({
                'id': person.id,
                'full_name': person.full_name,
                'role': person.role,
                'specialization': getattr(person, 'specialization', ''),
                'phone': getattr(person, 'phone', '')
            })
        
        return jsonify({'staff': results})
    except Exception as e:
        logging.error(f"Error getting department staff: {str(e)}")
        return jsonify({'error': 'حدث خطأ في جلب الموظفين'}), 500

@reception_bp.route('/api/visit-pricing')
@login_required
def api_visit_pricing():
    """API لحساب تكلفة الزيارة حسب إعدادات المدير"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    
    department_id = request.args.get('department_id')
    doctor_id = request.args.get('doctor_id')
    visit_type = request.args.get('visit_type', 'REGULAR')
    is_emergency = request.args.get('is_emergency', 'false').lower() == 'true'
    payment_method = request.args.get('payment_method', 'cash')
    tax_type = request.args.get('tax_type', 'none')  # none, inclusive, exclusive
    test_ids_param = request.args.get('test_ids', '').strip()
    
    TAX_RATE = 0.15  # نسبة الضريبة الافتراضية
    
    try:
        dept = db.session.get(Department, department_id)
        if dept and test_ids_param and dept.get_type() in ['lab', 'radiology']:
            from models.service import ServiceMaster
            ids = [int(x) for x in test_ids_param.split(',') if x.isdigit()]
            services = ServiceMaster.query.filter(ServiceMaster.id.in_(ids), ServiceMaster.is_active == True).all()
            breakdown = []
            total = 0.0
            for s in services:
                price = float(s.insurance_price or s.base_price) if payment_method == 'insurance' else float(s.base_price or 0)
                total += price
                breakdown.append({'item': s.name_ar or s.name, 'cost': price})
            
            # تطبيق الضريبة
            tax_amount = 0
            if tax_type == 'inclusive':
                # السعر شامل الضريبة: السعر الأساسي = الإجمالي / (1 + النسبة)
                base_total = total / (1 + TAX_RATE)
                tax_amount = total - base_total
                breakdown.append({'item': f'ضريبة ({int(TAX_RATE*100)}% شاملة)', 'cost': 0}) # للعرض فقط
            elif tax_type == 'exclusive':
                # السعر غير شامل: الضريبة = الإجمالي * النسبة
                tax_amount = total * TAX_RATE
                total += tax_amount
                breakdown.append({'item': f'ضريبة ({int(TAX_RATE*100)}%)', 'cost': tax_amount})
            
            return jsonify({'cost': round(total, 2), 'tests_total': round(total, 2), 'details': {'breakdown': breakdown}})
        else:
            cost = calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method)
            pricing_details = get_pricing_details(department_id, doctor_id, visit_type, is_emergency, payment_method)
            
            # تطبيق الضريبة
            if tax_type == 'inclusive':
                base_cost = cost / (1 + TAX_RATE)
                tax_amount = cost - base_cost
                pricing_details['breakdown'].append({
                    'item': f'ضريبة ({int(TAX_RATE*100)}% شاملة)',
                    'cost': 0  # لا نضيف تكلفة لأنها مشمولة
                })
                # يمكننا إضافة تفصيل الضريبة للعرض
                pricing_details['tax_info'] = f"يشمل ضريبة {round(tax_amount, 2)}"
            elif tax_type == 'exclusive':
                tax_amount = cost * TAX_RATE
                cost += tax_amount
                pricing_details['total'] = cost
                pricing_details['breakdown'].append({
                    'item': f'ضريبة ({int(TAX_RATE*100)}%)',
                    'cost': tax_amount
                })
            
            return jsonify({'cost': round(cost, 2), 'details': pricing_details})
    except Exception as e:
        logging.error(f"Error calculating visit cost: {str(e)}")
        return jsonify({'error': 'حدث خطأ في حساب التكلفة'}), 500

def get_pricing_details(department_id, doctor_id, visit_type, is_emergency, payment_method):
    """الحصول على تفاصيل التسعير"""
    try:
        details = {
            'service_cost': 0,
            'doctor_cost': 0,
            'discount': 0,
            'total': 0,
            'breakdown': []
        }
        
        # حساب تكلفة الخدمة
        department = db.session.get(Department, department_id)
        if department:
            service_type = get_service_type_by_department(department)
            service = get_service_by_department(department)
            
            if service:
                if is_emergency and service.emergency_price:
                    details['service_cost'] = float(service.emergency_price)
                elif payment_method == 'insurance' and service.insurance_price:
                    details['service_cost'] = float(service.insurance_price)
                else:
                    details['service_cost'] = float(service.base_price)
                
                details['breakdown'].append({
                    'item': f'خدمة {department.name_ar}',
                    'cost': details['service_cost']
                })
        
        # حساب تكلفة الطبيب
        used_doctor_pricing = False
        if doctor_id:
            doctor_cost = calculate_doctor_cost(doctor_id, department_id, visit_type, is_emergency, payment_method)
            details['doctor_cost'] = float(doctor_cost)
            if doctor_cost > 0:
                used_doctor_pricing = True
                # إذا وجد سعر للطبيب، نلغي سعر الخدمة العام ونعتمد سعر الطبيب
                details['service_cost'] = 0
                details['breakdown'] = [{
                    'item': 'رسوم الطبيب (شامل الكشفية)',
                    'cost': float(doctor_cost)
                }]
            elif doctor_cost > 0: # This condition is unreachable but keeping logic structure
                 details['breakdown'].append({
                    'item': 'رسوم الطبيب',
                    'cost': float(doctor_cost)
                })
        
        # حساب الخصم للمراجعة
        # لا نطبق الخصم إذا تم استخدام تسعير خاص للطبيب (لأنه يحدد سعر المتابعة بنفسه)
        if visit_type == 'FOLLOW_UP' and not used_doctor_pricing:
            total_before_discount = details['service_cost'] + details['doctor_cost']
            details['discount'] = total_before_discount * 0.3
            details['breakdown'].append({
                'item': 'خصم المراجعة (30%)',
                'cost': -details['discount']
            })
        
        # حساب الإجمالي
        details['total'] = details['service_cost'] + details['doctor_cost'] - details['discount']
        
        return details
    except Exception as e:
        logging.error(f"Error getting pricing details: {str(e)}")
        return {}

@reception_bp.route('/api/department-services')
@login_required
def api_department_services():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'error': 'ليس لديك الصلاحيات'}), 403
    department_id = request.args.get('department_id', type=int)
    if not department_id:
        return jsonify({'error': 'القسم مطلوب'}), 400
    dept = db.session.get(Department, department_id)
    if not dept:
        return jsonify({'error': 'القسم غير موجود'}), 404
    from models.service import ServiceMaster
    dt = dept.get_type()
    category = 'doctor' if dt == 'general' else dt
    services = ServiceMaster.query.filter(
        ServiceMaster.category == category,
        ServiceMaster.is_active == True
    ).all()
    resp = {
        'category': category,
        'services': [
            {
                'id': s.id,
                'code': s.code,
                'name': s.name,
                'name_ar': s.name_ar or s.name,
                'base_price': float(s.base_price or 0),
                'insurance_price': float(s.insurance_price or 0),
                'price': float(s.base_price or 0)
            } for s in services
        ]
    }
    return jsonify(resp)

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
        Appointment.status.in_(['SCHEDULED', 'CONFIRMED'])
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

# ===== مسارات الطابور =====

@reception_bp.route('/queue')
@login_required
def queue_management():
    """إدارة الطابور الموحد - الوحدة المركزية"""
    # التحقق من الصلاحيات
    if current_user.role not in ['reception', 'lab', 'radiology', 'admin', 'manager', 'super_admin', 'doctor', 'emergency']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        from models.department import Department
        from models.queue_management import QueueSettings
        
        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        
        dept_ids = AccessControlService.get_accessible_department_ids(current_user)
        if dept_ids is None:
            departments = all_departments
        elif dept_ids:
            departments = [d for d in all_departments if d.id in set(dept_ids)]
        else:
            departments = []
        
        settings_map = {}
        for dept in departments:
            s = QueueSettings.query.filter_by(department_id=dept.id).first()
            settings_map[dept.id] = s.to_dict() if s else None
        can_manage_queue_settings = AccessControlService.has_permission(current_user, 'queue_settings_manage')
        return render_template('reception/queue_management.html', 
                             departments=departments,
                             all_departments=all_departments if current_user.role in ['reception', 'super_admin', 'manager'] else departments,
                             queue_settings=settings_map,
                             can_manage_queue_settings=can_manage_queue_settings)
    except Exception as e:
        logging.error(f"Error loading queue management: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الطابور', 'error')
        return redirect(url_for('reception.dashboard'))

@reception_bp.route('/queue/add-patient', methods=['GET', 'POST'])
@login_required
def add_patient_to_queue():
    """إضافة مريض إلى الطابور - الوحدة المركزية"""
    if current_user.role not in ['reception']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        try:
            from services.queue_management_service import QueueManagementService
            
            queue_service = QueueManagementService()
            
            # جلب البيانات من النموذج
            patient_id = request.form.get('patient_id')
            department_id = request.form.get('department_id')
            doctor_id = request.form.get('doctor_id') or None
            visit_id = request.form.get('visit_id') or None
            appointment_id = request.form.get('appointment_id') or None
            queue_type = request.form.get('queue_type', 'normal')
            is_emergency = 'is_emergency' in request.form
            emergency_reason = request.form.get('emergency_reason') if is_emergency else None
            force_entry = 'force_entry' in request.form
            force_entry_reason = request.form.get('force_entry_reason') if force_entry else None
            payment_status = request.form.get('payment_status', 'PENDING')
            
            # إلزام اختيار طبيب للأقسام التخصصية
            try:
                dept_obj = db.session.get(Department, int(department_id))
            except Exception:
                dept_obj = None
            if not dept_obj:
                flash('القسم غير موجود', 'error')
                return redirect(url_for('reception.queue_management'))
            if getattr(dept_obj, 'get_type', lambda: 'general')() == 'general' and not doctor_id:
                flash('يجب اختيار طبيب للقسم التخصصي', 'error')
                return redirect(url_for('reception.add_patient_to_queue'))

            # إضافة المريض إلى الطابور
            success, message = queue_service.add_patient_to_queue(
                patient_id=patient_id,
                department_id=department_id,
                doctor_id=doctor_id,
                visit_id=visit_id,
                appointment_id=appointment_id,
                queue_type=queue_type,
                is_emergency=is_emergency,
                emergency_reason=emergency_reason,
                force_entry=force_entry,
                force_entry_reason=force_entry_reason,
                payment_status=payment_status,
                created_by=current_user.id
            )
            
            if success:
                flash(message, 'success')
            else:
                flash(message, 'error')
            return redirect(url_for('reception.queue_management'))
        except Exception as e:
            logging.error(f"Error adding patient to queue: {str(e)}")
            flash('تعذر إضافة المريض إلى الطابور، يرجى المحاولة مرة أخرى', 'error')
            return redirect(url_for('reception.queue_management'))

 

    # جلب البيانات المطلوبة للنموذج
    from models.patient import Patient
    from models.department import Department
    from models.user import User
    from models.visit import Visit
    from models.appointment import Appointment
    
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    visits = Visit.query.filter_by(status='OPEN').all()
    appointments = Appointment.query.filter_by(status='SCHEDULED').all()
    
    return render_template('reception/add_patient_to_queue.html',
                         patients=patients,
                         departments=departments,
                         doctors=doctors,
                         visits=visits,
                         appointments=appointments)

@reception_bp.route('/queue/call-next/<int:department_id>')
@login_required
def call_next_patient(department_id):
    """استدعاء المريض التالي"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        doctor_id = request.args.get('doctor_id', type=int)
        success, message = queue_service.call_next_patient(
            department_id=department_id,
            doctor_id=doctor_id,
            called_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))

    except Exception as e:
        logging.error(f"Error calling next patient: {str(e)}")
        flash('تعذر استدعاء المريض، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))


@reception_bp.route('/queue/start-treatment/<int:ticket_id>')
@login_required
def start_treatment(ticket_id):
    """بدء العلاج"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        success, message = queue_service.start_treatment(
            ticket_id=ticket_id,
            started_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('تعذر بدء العلاج، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/complete-treatment/<int:ticket_id>')
@login_required
def complete_treatment(ticket_id):
    """إكمال العلاج"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        success, message = queue_service.complete_treatment(
            ticket_id=ticket_id,
            completed_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error completing treatment: {str(e)}")
        flash('تعذر إكمال العلاج، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/skip-patient/<int:ticket_id>', methods=['POST'])
@login_required
def skip_patient(ticket_id):
    """تخطي المريض"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        reason = request.form.get('reason')
        
        success, message = queue_service.skip_patient(
            ticket_id=ticket_id,
            reason=reason,
            skipped_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error skipping patient: {str(e)}")
        flash('تعذر تخطي المريض، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/return-to-queue/<int:ticket_id>', methods=['POST'])
@login_required
def return_to_queue(ticket_id):
    """إرجاع المريض للطابور"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        queue_service = QueueManagementService()
        reason = request.form.get('reason')
        success, message = queue_service.return_to_queue(
            ticket_id=ticket_id,
            reason=reason,
            returned_by=current_user.id
        )
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        return redirect(url_for('reception.queue_management'))
    except Exception as e:
        logging.error(f"Error returning to queue: {str(e)}")
        flash('تعذر إرجاع المريض للطابور، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/cancel-ticket/<int:ticket_id>', methods=['POST'])
@login_required
def cancel_ticket(ticket_id):
    """إلغاء التذكرة"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        reason = request.form.get('reason')
        
        success, message = queue_service.cancel_ticket(
            ticket_id=ticket_id,
            reason=reason,
            cancelled_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error cancelling ticket: {str(e)}")
        flash('تعذر إلغاء التذكرة، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/approve-emergency-debt/<int:ticket_id>', methods=['POST'])
@login_required
def approve_emergency_debt(ticket_id):
    """الموافقة على دين الطوارئ"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        max_amount = request.form.get('max_amount')
        max_amount = float(max_amount) if max_amount else None
        
        success, message = queue_service.approve_emergency_debt(
            ticket_id=ticket_id,
            approved_by=current_user.id,
            max_amount=max_amount
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error approving emergency debt: {str(e)}")
        flash('تعذر الموافقة على دين الطوارئ، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/queue/approve-force-entry/<int:ticket_id>', methods=['POST'])
@login_required
def approve_force_entry(ticket_id):
    """الموافقة على الدخول القوي"""
    if current_user.role != 'reception':
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        reason = request.form.get('reason')
        
        success, message = queue_service.approve_force_entry(
            ticket_id=ticket_id,
            approved_by=current_user.id,
            reason=reason
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error approving force entry: {str(e)}")
        flash('تعذر الموافقة على الدخول القوي، يرجى المحاولة مرة أخرى', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/api/queue-status/<int:department_id>')
@login_required
def api_queue_status(department_id):
    """API لحالة الطابور"""
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        doctor_id = request.args.get('doctor_id', type=int)
        if current_user.role == 'doctor':
            doctor_id = current_user.id
        status = queue_service.get_queue_status(department_id, doctor_id=doctor_id)
        
        if status:
            return jsonify({'success': True, 'data': status})
        else:
            return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور'})
            
    except Exception as e:
        logging.error(f"Error getting queue status: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور حالياً'})

@reception_bp.route('/api/queue-status-all')
@login_required
def api_queue_status_all():
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        from services.queue_management_service import QueueManagementService
        from models.department import Department
        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [d for d in all_departments if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')]
        elif current_user.role == 'radiology':
            departments = [d for d in all_departments if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')]
        elif current_user.role == 'doctor':
            departments = [d for d in all_departments if d.id == current_user.department_id] if current_user.department_id else []
        else:
            departments = []
        dept_ids = [d.id for d in departments]
        doctor_id = request.args.get('doctor_id', type=int)
        if current_user.role == 'doctor':
            doctor_id = current_user.id
        status = request.args.get('status')
        priority = request.args.get('priority')
        search = (request.args.get('search') or '').strip() or None
        is_emergency = request.args.get('is_emergency')
        force_entry = request.args.get('force_entry')
        is_emergency = (is_emergency == '1' or is_emergency == 'true' or is_emergency == 'on') if is_emergency is not None else None
        force_entry = (force_entry == '1' or force_entry == 'true' or force_entry == 'on') if force_entry is not None else None
        # فلترة القسم المحدد ضمن الأقسام المسموح بها
        selected_dep = request.args.get('department_id', type=int)
        if selected_dep and selected_dep in dept_ids:
            dept_ids = [selected_dep]
        data = queue_service.get_queue_status_all(
            dept_ids,
            doctor_id=doctor_id,
            status=status,
            priority=priority,
            search=search,
            is_emergency=is_emergency,
            force_entry=force_entry
        )
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور الموحد'})
    except Exception as e:
        logging.error(f"Error getting all queue status: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب حالة الطابور الموحد حالياً'})


@reception_bp.route('/api/queue-wait-metrics')
@login_required
def api_queue_wait_metrics():
    if current_user.role not in ['reception', 'super_admin', 'manager', 'lab', 'radiology', 'doctor']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        from services.queue_management_service import QueueManagementService
        from models.department import Department

        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        elif current_user.role == 'lab':
            departments = [d for d in all_departments if 'lab' in (d.name or '').lower() or 'مختبر' in (d.name_ar or '')]
        elif current_user.role == 'radiology':
            departments = [d for d in all_departments if 'radiology' in (d.name or '').lower() or 'أشعة' in (d.name_ar or '')]
        elif current_user.role == 'doctor':
            departments = [d for d in all_departments if d.id == current_user.department_id] if current_user.department_id else []
        else:
            departments = []

        dept_ids = [d.id for d in departments]
        selected_dep = request.args.get('department_id', type=int)
        if selected_dep and selected_dep in dept_ids:
            dept_ids = [selected_dep]

        data = queue_service.get_wait_metrics_today(dept_ids)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        logging.error(f"Error getting queue wait metrics: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب مؤشرات الانتظار حالياً'})

@reception_bp.route('/api/fhir/patient/<int:patient_id>')
@login_required
def api_fhir_patient(patient_id):
    """تصدير بيانات المريض بصيغة FHIR Patient (مبسطة)"""
    try:
        from models.patient import Patient
        from models.visit import Visit
        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على المريض المطلوب'}]}), 404
        gender_map = {'M': 'male', 'F': 'female'}
        resource = {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'identifier': [{'system': 'urn:medical-system:national_id', 'value': patient.national_id}] if patient.national_id else [],
            'name': [{
                'text': patient.full_name,
                'given': [patient.first_name],
                'family': patient.last_name
            }],
            'telecom': ([{'system': 'phone', 'value': patient.phone}] if patient.phone else []),
            'gender': gender_map.get((patient.gender or '').upper(), 'unknown'),
            'birthDate': patient.birth_date.isoformat() if patient.birth_date else None,
            'address': ([{'text': patient.address}] if patient.address else []),
            'extension': [
                {'url': 'urn:medical-system:is_pregnant', 'valueBoolean': bool(patient.is_pregnant)}
            ],
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Patient']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Patient: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات المريض حالياً'}]}), 500

@reception_bp.route('/api/fhir/encounter/<int:visit_id>')
@login_required
def api_fhir_encounter(visit_id):
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from models.department import Department
        visit = db.session.get(Visit, visit_id)
        if not visit:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الزيارة المطلوبة'}]}), 404
        patient = db.session.get(Patient, visit.patient_id) if visit.patient_id else None
        doctor = db.session.get(User, visit.doctor_id) if visit.doctor_id else None
        dept = db.session.get(Department, visit.department_id) if visit.department_id else None
        status_map = {
            'OPEN': 'in-progress',
            'IN_PROGRESS': 'in-progress',
            'COMPLETED': 'finished',
            'ARCHIVED': 'cancelled'
        }
        start_dt = visit.visit_time or visit.created_at
        resource = {
            'resourceType': 'Encounter',
            'id': str(visit.id),
            'status': status_map.get(visit.status or '', 'unknown'),
            'class': {'system': 'http://terminology.hl7.org/CodeSystem/v3-ActCode', 'code': 'AMB'},
            'type': [{'text': visit.visit_type}] if visit.visit_type else [],
            'subject': {'reference': f'Patient/{visit.patient_id}', 'display': (patient.full_name if patient else None)},
            'participant': ([{'individual': {'reference': f'Practitioner/{doctor.id}', 'display': doctor.full_name}}] if doctor else []),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'period': {
                'start': (start_dt.isoformat() if start_dt else None),
                'end': (visit.completed_at.isoformat() if visit.completed_at else None)
            },
            'reasonCode': ([{'text': visit.symptoms}] if getattr(visit, 'symptoms', None) else []),
            'note': ([{'text': visit.notes}] if getattr(visit, 'notes', None) else []),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Encounter']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Encounter: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الزيارة حالياً'}]}), 500

@reception_bp.route('/api/fhir/appointment/<int:appointment_id>')
@login_required
def api_fhir_appointment(appointment_id):
    try:
        from models.appointment import Appointment
        from models.patient import Patient
        from models.user import User
        from models.department import Department
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الموعد المطلوب'}]}), 404
        patient = db.session.get(Patient, appt.patient_id) if appt.patient_id else None
        doctor = db.session.get(User, appt.doctor_id) if appt.doctor_id else None
        dept = db.session.get(Department, appt.department_id) if appt.department_id else None
        status_map = {
            'SCHEDULED': 'booked',
            'CONFIRMED': 'booked',
            'CANCELLED': 'cancelled',
            'NO_SHOW': 'noshow',
            'DONE': 'fulfilled'
        }
        participants = [
            {'actor': {'reference': f'Patient/{appt.patient_id}', 'display': (patient.full_name if patient else None)}, 'status': 'accepted'}
        ]
        if doctor:
            participants.append({'actor': {'reference': f'Practitioner/{doctor.id}', 'display': doctor.full_name}, 'status': 'accepted'})
        resource = {
            'resourceType': 'Appointment',
            'id': str(appt.id),
            'status': status_map.get(appt.status or '', 'booked'),
            'start': (appt.starts_at.isoformat() if appt.starts_at else None),
            'end': (appt.ends_at.isoformat() if appt.ends_at else None),
            'description': (appt.notes or None),
            'serviceType': ([{'text': (dept.name_ar or dept.name)}] if dept else []),
            'participant': participants,
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Appointment']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Appointment: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الموعد حالياً'}]}), 500

@reception_bp.route('/api/fhir/practitioner/<int:user_id>')
@login_required
def api_fhir_practitioner(user_id):
    try:
        from models.user import User
        from models.department import Department
        user = db.session.get(User, user_id)
        if not user or user.role != 'doctor':
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على الطبيب المطلوب'}]}), 404
        dept = db.session.get(Department, user.department_id) if user.department_id else None
        resource = {
            'resourceType': 'Practitioner',
            'id': str(user.id),
            'name': [{'text': user.full_name}],
            'telecom': ([{'system': 'phone', 'value': user.phone}] if user.phone else []) +
                       ([{'system': 'email', 'value': user.email}] if user.email else []),
            'qualification': [{'code': {'text': 'Doctor'}}],
            'extension': ([{'url': 'urn:medical-system:department', 'valueString': (dept.name_ar or dept.name)}] if dept else []),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Practitioner']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Practitioner: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الطبيب حالياً'}]}), 500

@reception_bp.route('/api/fhir/organization/<int:department_id>')
@login_required
def api_fhir_organization(department_id):
    try:
        from models.department import Department
        dept = db.session.get(Department, department_id)
        if not dept:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على القسم المطلوب'}]}), 404
        resource = {
            'resourceType': 'Organization',
            'id': str(dept.id),
            'name': (dept.name_ar or dept.name),
            'telecom': ([{'system': 'phone', 'value': dept.phone}] if getattr(dept, 'phone', None) else []) +
                       ([{'system': 'email', 'value': dept.email}] if getattr(dept, 'email', None) else []),
            'address': ([{'text': getattr(dept, 'location', None)}] if getattr(dept, 'location', None) else []),
            'active': bool(dept.is_active),
            'meta': {'profile': ['http://hl7.org/fhir/StructureDefinition/Organization']}
        }
        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Organization: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات القسم حالياً'}]}), 500

@reception_bp.route('/api/patient-queue-position/<int:patient_id>/<int:department_id>')
@login_required
def api_patient_queue_position(patient_id, department_id):
    """API لموقع المريض في الطابور"""
    if current_user.role != 'reception':
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        position, message = queue_service.get_patient_queue_position(patient_id, department_id)
        
        if position:
            return jsonify({'success': True, 'position': position, 'message': message})
        else:
            return jsonify({'success': False, 'message': message})
            
    except Exception as e:
        logging.error(f"Error getting queue position: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب موقع المريض في الطابور حالياً'})

@reception_bp.route('/api/queue-snapshot')
@login_required
def api_queue_snapshot():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        active_queue_items = QueueManagement.query.filter(
            QueueManagement.status.in_(['waiting', 'called', 'in_progress'])
        ).order_by(QueueManagement.queued_at.asc()).limit(50).all()
        items = []
        for item in active_queue_items:
            items.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'status': item.get_status_display(),
                'priority': item.get_priority_display(),
                'payment': item.get_payment_status_display()
            })
        stats = get_smart_queue_management()
        satisfaction = get_patient_satisfaction_ai()
        forecast = get_patient_demand_forecast()
        return jsonify({
            'success': True,
            'items': items,
            'stats': stats,
            'satisfaction': satisfaction,
            'forecast': forecast
        })
    except Exception as e:
        logging.error(f"Error getting queue snapshot: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب بيانات الطابور حالياً'}), 500

@reception_bp.route('/api/display/waiting')
@login_required
def api_display_waiting():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        waiting = QueueManagement.query.filter(
            QueueManagement.status == 'waiting'
        ).order_by(QueueManagement.queued_at.asc()).limit(60).all()
        called = QueueManagement.query.filter(
            QueueManagement.status == 'called'
        ).order_by(QueueManagement.called_at.desc()).limit(12).all()
        current = QueueManagement.query.filter(
            QueueManagement.status == 'in_progress'
        ).order_by(QueueManagement.started_at.desc()).limit(6).all()

        def _pack(item):
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            return {
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            }

        return jsonify({
            'success': True,
            'waiting': [_pack(i) for i in waiting],
            'called': [_pack(i) for i in called],
            'current': [_pack(i) for i in current]
        })
    except Exception as e:
        logging.error(f"Error getting waiting display: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة الانتظار حالياً'}), 500

@reception_bp.route('/api/display/calls')
@login_required
def api_display_calls():
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        called = QueueManagement.query.filter(
            QueueManagement.status.in_(['called', 'in_progress'])
        ).order_by(QueueManagement.called_at.desc()).limit(24).all()
        items = []
        for item in called:
            room_value = ''
            if item.visit and item.visit.doctor and item.visit.doctor.doctor_room:
                room_value = item.visit.doctor.doctor_room
            elif item.department and item.department.location:
                room_value = item.department.location
            items.append({
                'queue_number': item.queue_number,
                'patient_name': item.patient.full_name if item.patient else '',
                'department_name': item.department.name_ar if item.department else '',
                'doctor_name': item.visit.doctor.full_name if item.visit and item.visit.doctor else '',
                'room_name': room_value,
                'status': item.get_status_display()
            })
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        logging.error(f"Error getting calls display: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب شاشة النداء حالياً'}), 500

# ==================== الميزات الذكية للاستقبال ====================

def get_smart_queue_management():
    """إدارة الطابور الذكية"""
    try:
        from models.queue_management import QueueManagement
        from models.visit import Visit
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        # تحليل الطابور الحالي
        current_queue = QueueManagement.query.filter(
            QueueManagement.status.in_(['waiting', 'called', 'in_progress'])
        ).order_by(QueueManagement.created_at).all()
        
        # تحليل أوقات الانتظار
        avg_wait_time = db.session.query(func.avg(QueueManagement.estimated_wait_time)).scalar() or 0
        
        # تحليل الأولويات
        priority_analysis = {
            'urgent': QueueManagement.query.filter(QueueManagement.priority_level == 'urgent').count(),
            'normal': QueueManagement.query.filter(QueueManagement.priority_level == 'normal').count(),
            'low': QueueManagement.query.filter(QueueManagement.priority_level == 'low').count()
        }
        
        # تحليل ساعات الذروة
        try:
            peak_hours = db.session.query(
                func.extract('hour', QueueManagement.created_at).label('hour'),
                func.count(QueueManagement.id).label('count')
            ).group_by(func.extract('hour', QueueManagement.created_at)).all()
        except Exception:
            db.session.rollback()
            peak_hours = []
        
        peak_hour = max(peak_hours, key=lambda x: x.count) if peak_hours else None
        
        return {
            'current_queue_length': len(current_queue),
            'avg_wait_time': round(avg_wait_time, 2),
            'priority_analysis': priority_analysis,
            'peak_hour': peak_hour.hour if peak_hour else None,
            'peak_count': peak_hour.count if peak_hour else 0,
            'efficiency_score': calculate_queue_efficiency(current_queue)
        }
    except Exception as e:
        logging.error(f"Error getting smart queue management: {str(e)}")
        return {}

def get_patient_flow_analysis():
    """تحليل تدفق المرضى"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        # تحليل التدفق اليومي
        daily_flow = []
        for i in range(7):
            date = today - timedelta(days=i)
            visits_count = Visit.query.filter(Visit.created_at == date).count()
            patients_count = Patient.query.filter(Patient.created_at >= date, Patient.created_at < date + timedelta(days=1)).count()
            daily_flow.append({
                'date': date.strftime('%Y-%m-%d'),
                'visits': visits_count,
                'new_patients': patients_count
            })
        
        # تحليل ساعات الذروة
        try:
            hourly_flow = db.session.query(
                func.extract('hour', Visit.created_at).label('hour'),
                func.count(Visit.id).label('count')
            ).filter(Visit.created_at >= week_ago).group_by(func.extract('hour', Visit.created_at)).all()
        except Exception:
            db.session.rollback()
            hourly_flow = []
        
        # تحليل الأقسام
        department_flow = db.session.query(
            func.count(Visit.id).label('count'),
            Visit.department_id
        ).filter(Visit.created_at >= week_ago).group_by(Visit.department_id).all()
        
        return {
            'daily_flow': daily_flow,
            'hourly_flow': [{'hour': h.hour, 'count': h.count} for h in hourly_flow],
            'department_flow': [{'department_id': d.department_id, 'count': d.count} for d in department_flow],
            'trend': calculate_flow_trend(daily_flow)
        }
    except Exception as e:
        logging.error(f"Error getting patient flow analysis: {str(e)}")
        return {}

def get_appointment_optimization():
    """تحسين المواعيد"""
    try:
        from models.appointment import Appointment
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل المواعيد المتاحة
        today = datetime.now().date()
        week_ahead = today + timedelta(days=7)
        
        # تحليل كثافة المواعيد
        appointment_density = db.session.query(
            func.date(Appointment.starts_at).label('appointment_date'),
            func.count(Appointment.id).label('count')
        ).filter(
            Appointment.starts_at >= today,
            Appointment.starts_at <= week_ahead
        ).group_by(func.date(Appointment.starts_at)).all()
        
        # تحليل الأطباء
        doctor_workload = db.session.query(
            User.id,
            User.full_name,
            func.count(Appointment.id).label('appointments')
        ).join(Appointment, User.id == Appointment.doctor_id).filter(
            Appointment.starts_at >= today,
            Appointment.starts_at <= week_ahead
        ).group_by(User.id, User.full_name).all()
        
        # اقتراحات التحسين
        optimizations = []
        
        # تحليل الأيام المزدحمة
        if appointment_density:
            max_day = max(appointment_density, key=lambda x: x.count)
            if max_day.count > 20:
                optimizations.append({
                    'type': 'scheduling',
                    'title': 'توزيع المواعيد',
                    'description': f'اليوم {max_day.appointment_date} مزدحم جداً ({max_day.count} موعد)',
                    'suggestion': 'توزيع المواعيد على أيام أخرى'
                })
        
        # تحليل عبء العمل
        if doctor_workload:
            max_doctor = max(doctor_workload, key=lambda x: x.appointments)
            if max_doctor.appointments > 15:
                optimizations.append({
                    'type': 'workload',
                    'title': 'توزيع عبء العمل',
                    'description': f'الطبيب {max_doctor.full_name} محمل بكثرة ({max_doctor.appointments} موعد)',
                    'suggestion': 'إعادة توزيع المواعيد أو إضافة طبيب آخر'
                })
        
        return {
            'appointment_density': [{'date': str(d.appointment_date), 'count': d.count} for d in appointment_density],
            'doctor_workload': [{'doctor_id': d.id, 'doctor_name': d.full_name, 'appointments': d.appointments} for d in doctor_workload],
            'optimizations': optimizations
        }
    except Exception as e:
        logging.error(f"Error getting appointment optimization: {str(e)}")
        return {}

def get_real_time_alerts():
    """التنبيهات في الوقت الفعلي"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        alerts = []
        
        # تنبيهات المواعيد
        today = datetime.now().date()
        overdue_appointments = Appointment.query.filter(
            Appointment.starts_at < today,
            Appointment.status == 'SCHEDULED'
        ).count()
        
        if overdue_appointments > 0:
            alerts.append({
                'type': 'appointment',
                'priority': 'high',
                'title': 'مواعيد متأخرة',
                'message': f'يوجد {overdue_appointments} موعد متأخر',
                'action': 'مراجعة المواعيد المتأخرة'
            })
        
        # تنبيهات الطابور
        long_waiting = Visit.query.filter(
            Visit.status == 'PENDING',
            Visit.created_at < datetime.now() - timedelta(hours=2)
        ).count()
        
        if long_waiting > 0:
            alerts.append({
                'type': 'queue',
                'priority': 'medium',
                'title': 'انتظار طويل',
                'message': f'يوجد {long_waiting} مريض ينتظر أكثر من ساعتين',
                'action': 'مراجعة الطابور'
            })
        
        # تنبيهات السعة
        today_visits = Visit.query.filter(Visit.created_at >= today).count()
        if today_visits > 50:
            alerts.append({
                'type': 'capacity',
                'priority': 'medium',
                'title': 'سعة عالية',
                'message': f'عدد الزيارات اليوم: {today_visits} - قريب من السعة القصوى',
                'action': 'مراقبة الأداء'
            })
        
        return alerts
    except Exception as e:
        logging.error(f"Error getting real-time alerts: {str(e)}")
        return []

def get_workflow_automation():
    """أتمتة سير العمل"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        automation_suggestions = []
        
        # أتمتة المواعيد المتكررة
        recurring_patients = db.session.query(
            Patient.id,
            func.count(Visit.id).label('visit_count')
        ).join(Visit, Patient.id == Visit.patient_id).filter(
            Visit.created_at >= datetime.now().date() - timedelta(days=30)
        ).group_by(Patient.id).having(func.count(Visit.id) > 3).all()
        
        if recurring_patients:
            automation_suggestions.append({
                'type': 'recurring_appointments',
                'title': 'المواعيد المتكررة',
                'description': f'يوجد {len(recurring_patients)} مريض يحتاج مواعيد متكررة',
                'suggestion': 'إعداد مواعيد تلقائية للمرضى المتكررين'
            })
        
        # أتمتة التذكيرات
        tomorrow_appointments = Appointment.query.filter(
            Appointment.starts_at >= datetime.now().date() + timedelta(days=1),
            Appointment.starts_at < datetime.now().date() + timedelta(days=2)
        ).count()
        
        if tomorrow_appointments > 0:
            automation_suggestions.append({
                'type': 'reminders',
                'title': 'التذكيرات التلقائية',
                'description': f'يوجد {tomorrow_appointments} موعد غداً',
                'suggestion': 'إرسال تذكيرات تلقائية للمرضى'
            })
        
        # أتمتة المتابعة
        completed_visits = Visit.query.filter(
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        if completed_visits > 10:
            automation_suggestions.append({
                'type': 'follow_up',
                'title': 'المتابعة التلقائية',
                'description': f'تم إنجاز {completed_visits} زيارة هذا الأسبوع',
                'suggestion': 'إعداد نظام متابعة تلقائي للمرضى'
            })
        
        return automation_suggestions
    except Exception as e:
        logging.error(f"Error getting workflow automation: {str(e)}")
        return []

def get_patient_satisfaction_ai():
    """ذكاء اصطناعي لرضا المرضى"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.queue_management import QueueManagement
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل عوامل الرضا
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == 'ARCHIVED').count()
        
        # معدل الإنجاز
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # متوسط وقت الانتظار
        avg_wait_time = db.session.query(func.avg(QueueManagement.estimated_wait_time)).scalar() or 0
        
        # تحليل التكرار
        repeat_visits = db.session.query(
            Visit.patient_id,
            func.count(Visit.id).label('visit_count')
        ).group_by(Visit.patient_id).having(func.count(Visit.id) > 1).count()
        
        satisfaction_score = calculate_satisfaction_score(completion_rate, avg_wait_time, repeat_visits)

        avg_rating = db.session.query(func.avg(PatientSatisfactionSurvey.rating)).filter(
            PatientSatisfactionSurvey.rating.isnot(None)
        ).scalar()
        rating_count = db.session.query(func.count(PatientSatisfactionSurvey.id)).filter(
            PatientSatisfactionSurvey.rating.isnot(None)
        ).scalar() or 0
        rating_score = (float(avg_rating or 0) / 5 * 100) if avg_rating else None
        if rating_score is not None:
            satisfaction_score = (satisfaction_score * 0.6) + (rating_score * 0.4)
        
        # توصيات التحسين
        recommendations = []
        
        if completion_rate < 80:
            recommendations.append({
                'type': 'completion',
                'title': 'تحسين معدل الإنجاز',
                'description': f'معدل إنجاز الزيارات: {completion_rate:.1f}%',
                'suggestion': 'تحسين كفاءة العمليات'
            })
        
        if avg_wait_time > 30:
            recommendations.append({
                'type': 'wait_time',
                'title': 'تقليل أوقات الانتظار',
                'description': f'متوسط وقت الانتظار: {avg_wait_time:.1f} دقيقة',
                'suggestion': 'تحسين تدفق المرضى'
            })

        if avg_rating and avg_rating < 3.5:
            recommendations.append({
                'type': 'survey',
                'title': 'تحسين رضا المرضى',
                'description': f'متوسط التقييم: {avg_rating:.2f} من 5',
                'suggestion': 'تحليل الملاحظات وتحسين التجربة'
            })
        
        return {
            'satisfaction_score': round(satisfaction_score, 2),
            'avg_rating': round(float(avg_rating), 2) if avg_rating else None,
            'rating_count': int(rating_count),
            'completion_rate': round(completion_rate, 2),
            'avg_wait_time': round(avg_wait_time, 2),
            'repeat_visits': repeat_visits,
            'recommendations': recommendations,
            'status': 'excellent' if satisfaction_score > 90 else 'good' if satisfaction_score > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting patient satisfaction AI: {str(e)}")
        return {}

def get_patient_demand_forecast(hours_ahead=4, days_window=14):
    try:
        from models.visit import Visit
        from datetime import datetime, timedelta
        from sqlalchemy import func

        now = datetime.now()
        start_date = now - timedelta(days=days_window)

        hourly = []
        try:
            hourly = db.session.query(
                func.extract('hour', Visit.created_at).label('hour'),
                func.count(Visit.id).label('count')
            ).filter(Visit.created_at >= start_date).group_by(func.extract('hour', Visit.created_at)).all()
        except Exception:
            hourly = db.session.query(
                func.strftime('%H', Visit.created_at).label('hour'),
                func.count(Visit.id).label('count')
            ).filter(Visit.created_at >= start_date).group_by(func.strftime('%H', Visit.created_at)).all()

        avg_by_hour = {}
        for h in hourly:
            hour_val = int(getattr(h, 'hour', None) or 0)
            avg_by_hour[hour_val] = float(h.count or 0) / float(days_window)

        next_hours = []
        for i in range(hours_ahead):
            hour = (now.hour + i) % 24
            next_hours.append({
                'hour': hour,
                'expected': round(avg_by_hour.get(hour, 0), 2)
            })

        expected_total = round(sum(h['expected'] for h in next_hours), 2)

        return {
            'hours_ahead': hours_ahead,
            'expected_total': expected_total,
            'next_hours': next_hours
        }
    except Exception as e:
        logging.error(f"Error getting patient demand forecast: {str(e)}")
        return {}

def get_resource_planning():
    """تخطيط الموارد"""
    try:
        from models.user import User
        from models.visit import Visit
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل الموظفين
        total_staff = User.query.count()
        active_staff = User.query.filter(
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        # تحليل الأطباء
        total_doctors = User.query.filter(User.role == 'doctor').count()
        active_doctors = User.query.filter(
            User.role == 'doctor',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        # تحليل الأحمال
        today = datetime.now().date()
        today_visits = Visit.query.filter(Visit.created_at >= today).count()
        tomorrow_appointments = Appointment.query.filter(
            Appointment.starts_at >= today + timedelta(days=1),
            Appointment.starts_at < today + timedelta(days=2)
        ).count()
        
        # حساب الكفاءة
        efficiency_score = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        # توصيات التخطيط
        planning_recommendations = []
        
        if efficiency_score < 70:
            planning_recommendations.append({
                'type': 'staff_engagement',
                'title': 'تحسين مشاركة الموظفين',
                'description': f'معدل المشاركة: {efficiency_score:.1f}%',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        if today_visits > 30:
            planning_recommendations.append({
                'type': 'capacity_planning',
                'title': 'تخطيط السعة',
                'description': f'عدد الزيارات اليوم: {today_visits}',
                'suggestion': 'مراجعة القدرة الاستيعابية'
            })
        
        return {
            'total_staff': total_staff,
            'active_staff': active_staff,
            'total_doctors': total_doctors,
            'active_doctors': active_doctors,
            'today_visits': today_visits,
            'tomorrow_appointments': tomorrow_appointments,
            'efficiency_score': round(efficiency_score, 2),
            'planning_recommendations': planning_recommendations
        }
    except Exception as e:
        logging.error(f"Error getting resource planning: {str(e)}")
        return {}

def get_smart_recommendations():
    """التوصيات الذكية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل النمو
        week_ago = datetime.now().date() - timedelta(days=7)
        new_patients_week = Patient.query.filter(Patient.created_at >= week_ago).count()
        
        if new_patients_week > 20:
            recommendations.append({
                'type': 'growth',
                'title': 'نمو سريع',
                'description': f'تم تسجيل {new_patients_week} مريض جديد هذا الأسبوع',
                'suggestion': 'مراجعة القدرة الاستيعابية والموارد'
            })
        
        # تحليل المواعيد
        no_show_rate = calculate_no_show_rate()
        if no_show_rate > 20:
            recommendations.append({
                'type': 'no_show',
                'title': 'معدل عدم الحضور',
                'description': f'معدل عدم الحضور: {no_show_rate:.1f}%',
                'suggestion': 'تحسين نظام التذكيرات'
            })
        
        # تحليل الكفاءة
        try:
            avg_visit_duration = db.session.query(
                func.avg((func.extract('epoch', Visit.completed_at) - func.extract('epoch', Visit.created_at)) / 60.0)
            ).filter(Visit.completed_at.isnot(None)).scalar() or 0
        except Exception:
            db.session.rollback()
            avg_visit_duration = 0
        if avg_visit_duration > 45:
            recommendations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط مدة الزيارة: {avg_visit_duration:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتقليل مدة الزيارة'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart recommendations: {str(e)}")
        return []

# دوال مساعدة
def calculate_queue_efficiency(queue):
    """حساب كفاءة الطابور"""
    if not queue:
        return 100
    
    completed = len([t for t in queue if t.status == 'completed'])
    total = len(queue)
    return (completed / total * 100) if total > 0 else 0

def calculate_flow_trend(daily_flow):
    """حساب اتجاه التدفق"""
    if len(daily_flow) < 2:
        return 'stable'
    
    recent = daily_flow[0]['visits']
    previous = daily_flow[1]['visits']
    
    if recent > previous * 1.1:
        return 'growing'
    elif recent < previous * 0.9:
        return 'declining'
    else:
        return 'stable'

def calculate_satisfaction_score(completion_rate, avg_wait_time, repeat_visits):
    """حساب نقاط الرضا"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط وقت الانتظار (كلما قل الوقت كلما زادت النقاط)
    wait_score = max(0, 100 - (avg_wait_time / 60 * 20))
    
    # نقاط التكرار (كلما زاد التكرار كلما زادت النقاط)
    repeat_score = min(100, repeat_visits * 5)
    
    return (completion_score + wait_score + repeat_score) / 3

def calculate_no_show_rate():
    """حساب معدل عدم الحضور"""
    try:
        from models.appointment import Appointment
        total_appointments = Appointment.query.count()
        no_show_appointments = Appointment.query.filter(Appointment.status == 'no_show').count()
        return (no_show_appointments / total_appointments * 100) if total_appointments > 0 else 0
    except:
        return 0


# ===== وظائف مساعدة لتطبيق قيود البحث =====

def can_search_all_patients(user_role):
    """التحقق من صلاحية البحث في كل المرضى"""
    # الأدوار التي يمكنها البحث في كل المرضى
    return user_role in ['reception', 'doctor', 'emergency', 'super_admin', 'manager', 'accountant']


def get_accessible_departments_for_user(user_role, user_id=None, user_department_id=None):
    """الحصول على الأقسام المتاحة للمستخدم"""
    all_departments = Department.query.filter_by(is_active=True).all()
    try:
        from services.access_control_service import AccessControlService
        if user_id:
            from models.user import User
            user = db.session.get(User, user_id)
        else:
            user = None
        if user:
            dept_ids = AccessControlService.get_accessible_department_ids(user)
            if dept_ids is None:
                return all_departments
            if dept_ids:
                return [d for d in all_departments if d.id in set(dept_ids)]
            return []
    except Exception:
        pass

    if user_role in ['reception', 'super_admin', 'manager', 'doctor', 'emergency', 'accountant']:
        return all_departments
    if user_role in ['lab', 'radiology', 'nurse'] and user_department_id:
        return [d for d in all_departments if d.id == user_department_id]
    return []

# ===== وظائف مساعدة لسيناريو الزيارة =====

def calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method='cash'):
    """حساب تكلفة الزيارة تلقائياً حسب إعدادات المدير"""
    try:
        from models.pricing import PricingCatalog
        from models.service import ServiceMaster
        from models.pricing_management import PricingRule
        total_cost = 0
        department = db.session.get(Department, department_id)
        if not department:
            return 0
        service_type = get_service_type_by_department(department)
        pricing_entry = PricingCatalog.query.filter(
            PricingCatalog.service_type == service_type,
            PricingCatalog.is_active == True
        ).first()
        if pricing_entry:
            if payment_method == 'insurance':
                total_cost = pricing_entry.get_final_price('insurance')
            else:
                total_cost = pricing_entry.base_price
        else:
            service = get_service_by_department(department)
            if service:
                if is_emergency and service.emergency_price:
                    total_cost = float(service.emergency_price)
                elif payment_method == 'insurance' and service.insurance_price:
                    total_cost = float(service.insurance_price)
                else:
                    total_cost = float(service.base_price)
        used_doctor_pricing = False
        if doctor_id:
            doctor_cost = calculate_doctor_cost(doctor_id, department_id, visit_type, is_emergency, payment_method)
            # إذا كان للطبيب تسعير خاص، يتم اعتماده بدلاً من سعر الخدمة العام
            if doctor_cost > 0:
                total_cost = float(doctor_cost)
                used_doctor_pricing = True
            else:
                total_cost += float(doctor_cost)
        
        # تطبيق قواعد التسعير (الخصومات والزيادات)
        rules = PricingRule.query.filter(PricingRule.is_active == True).order_by(PricingRule.priority.asc()).all()
        for r in rules:
            matched = False
            if r.condition_type == 'visit_type':
                matched = (visit_type == r.condition_value)
            elif r.condition_type == 'payment_method':
                matched = (payment_method == r.condition_value)
            if matched:
                if r.price_adjustment_type == 'percentage':
                    total_cost = total_cost * (1 + (float(r.price_adjustment_value or 0)) / 100.0)
                elif r.price_adjustment_type == 'fixed_amount':
                    total_cost = total_cost + float(r.price_adjustment_value or 0)
        
        # خصم المتابعة فقط إذا لم يتم استخدام تسعير خاص للطبيب
        # لأن تسعير الطبيب للمتابعة يكون محدداً مسبقاً
        if visit_type == 'FOLLOW_UP' and not used_doctor_pricing:
            total_cost = total_cost * 0.7
        
        return round(total_cost, 2)
    except Exception as e:
        logging.error(f"Error calculating visit cost: {str(e)}")
        return 0

def get_service_type_by_department(department):
    """تحديد نوع الخدمة حسب القسم"""
    if not department:
        return 'consultation'
    dt = department.get_type()
    if dt == 'lab':
        return 'lab'
    if dt == 'radiology':
        return 'radiology'
    if dt == 'emergency':
        return 'emergency'
    return 'consultation'

def get_service_by_department(department):
    """البحث عن الخدمة حسب القسم"""
    if not department:
        return None
    from models.service import ServiceMaster
    dt = department.get_type()
    category = 'doctor'
    if dt == 'lab':
        category = 'lab'
    elif dt == 'radiology':
        category = 'radiology'
    elif dt == 'emergency':
        category = 'emergency'
    return ServiceMaster.query.filter(
        ServiceMaster.category == category,
        ServiceMaster.is_active == True
    ).first()

def calculate_doctor_cost(doctor_id, department_id, visit_type, is_emergency, payment_method):
    """حساب تكلفة الطبيب"""
    try:
        from models.pricing import DoctorPricing
        
        # البحث عن تسعير الطبيب
        doctor_pricing = DoctorPricing.query.filter(
            DoctorPricing.doctor_id == doctor_id,
            DoctorPricing.department_id == department_id,
            DoctorPricing.is_active == True
        ).first()
        
        if doctor_pricing:
            return doctor_pricing.get_price(visit_type, payment_method)
        
        # إذا لم يوجد تسعير محدد، البحث عن تسعير عام للطبيب
        general_pricing = DoctorPricing.query.filter(
            DoctorPricing.doctor_id == doctor_id,
            DoctorPricing.department_id.is_(None),
            DoctorPricing.is_active == True
        ).first()
        
        if general_pricing:
            return general_pricing.get_price(visit_type, payment_method)
        
        # إذا لم يوجد أي تسعير، استخدام السعر الافتراضي
        return 0
    except Exception as e:
        logging.error(f"Error calculating doctor cost: {str(e)}")
        return 0

def add_patient_to_queue_auto(visit_id, department_id, doctor_id=None):
    """إضافة المريض للطابور تلقائياً"""
    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        
        # جلب بيانات الزيارة
        visit = db.session.get(Visit, visit_id)
        if not visit:
            return False, "الزيارة غير موجودة"

        is_emergency = bool(getattr(visit, 'is_emergency', False)) or str(getattr(visit, 'visit_type', '') or '').upper() == 'EMERGENCY'
        emergency_reason = (getattr(visit, 'symptoms', None) or '').strip() if is_emergency else None
        is_force_payment = bool(getattr(visit, 'is_force_payment', False))
        force_payment_reason = (getattr(visit, 'force_payment_reason', None) or '').strip() if is_force_payment else None
        
        # إضافة المريض للطابور
        result = queue_service.add_patient_to_queue(
            patient_id=visit.patient_id,
            department_id=department_id,
            doctor_id=doctor_id,
            visit_id=visit_id,
            queue_type='normal',
            is_emergency=is_emergency,
            emergency_reason=emergency_reason,
            force_entry=is_force_payment,
            force_entry_reason=force_payment_reason,
            payment_status=visit.payment_status
        )
        
        return result
    except Exception as e:
        logging.error(f"Error adding patient to queue: {str(e)}")
        return False, f"خطأ في النظام: {str(e)}"

def get_payment_methods():
    """جلب طرق الدفع المتاحة"""
    return [
        {'value': 'cash', 'label': 'نقداً', 'fields': []},
        {'value': 'visa', 'label': 'فيزا', 'fields': ['card_number', 'card_holder', 'expiry_date']},
        {'value': 'wire', 'label': 'تحويل بنكي', 'fields': ['reference_number', 'bank_name']},
        {'value': 'insurance', 'label': 'تأمين', 'fields': ['insurance_provider', 'policy_number', 'coverage_percentage']},
        {'value': 'force', 'label': 'دفع قوي', 'fields': ['force_reason', 'approved_by']}
    ]

def validate_payment_data(payment_method, form_data):
    """التحقق من صحة بيانات الدفع"""
    required_fields = {
        'cash': [],
        'visa': ['card_last_digits', 'card_holder_name', 'expiry_date'],
        'insurance': ['insurance_provider', 'insurance_policy_number'],
        'force': ['force_payment_reason', 'approved_by']
    }
    
    if payment_method not in required_fields:
        return False, "طريقة دفع غير صحيحة"
    
    for field in required_fields[payment_method]:
        if not form_data.get(field):
            return False, f"الحقل {field} مطلوب"
    
    return True, "صحيح"




@reception_bp.route('/queue/save-settings/<int:department_id>', methods=['POST'])
@login_required
@AccessControlService.require_permission('queue_settings_manage')
def save_queue_settings(department_id):

    
    """حفظ إعدادات الطابور للقسم"""
    try:
        from models.queue_management import QueueSettings
        from models.department import Department
        dept = db.session.get(Department, department_id)
        if not dept:
            flash('القسم غير موجود', 'error')
            return redirect(url_for('reception.queue_management'))
        settings = QueueSettings.query.filter_by(department_id=department_id).first()
        if not settings:
            settings = QueueSettings(department_id=department_id)
            db.session.add(settings)
            db.session.flush()
        # تحديث القيم من النموذج
        settings.payment_required = 'payment_required' in request.form
        settings.allow_partial_payment = 'allow_partial_payment' in request.form
        settings.allow_debt = 'allow_debt' in request.form
        settings.emergency_payment_waived = 'emergency_payment_waived' in request.form
        settings.force_entry_allowed = 'force_entry_allowed' in request.form
        db.session.commit()
        flash('تم حفظ إعدادات الطابور للقسم.', 'success')
        return redirect(url_for('reception.queue_management'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving queue settings: {str(e)}")
        flash('حدث خطأ في حفظ الإعدادات', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/payments')
@login_required
def payments():
    """المدفوعات"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('accountant/payments.html')

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

@reception_bp.route('/cash-register')
@login_required
@role_required('reception', 'super_admin', 'manager')
def cash_register():
    """سجل الصندوق اليومي"""
    from models.cash_register import CashRegister
    from models.payment import Payment
    reg = CashRegister.get_or_create_today(current_user.id)
    today = db.func.current_date()
    # Calculate expected from payments
    payments = Payment.query.filter(
        db.func.date(Payment.created_at) == today,
        Payment.status.in_(['COMPLETED', 'PAID'])
    ).all()
    exp_cash = sum(float(p.amount or 0) for p in payments if p.method == 'cash')
    exp_card = sum(float(p.amount or 0) for p in payments if p.method == 'card')
    exp_ins = sum(float(p.amount or 0) for p in payments if p.method == 'insurance')
    reg.expected_cash = exp_cash
    reg.expected_card = exp_card
    reg.expected_insurance = exp_ins
    reg.expected_total = exp_cash + exp_card + exp_ins
    db.session.commit()
    return render_template('reception/cash_register.html', register=reg, payments=payments)


@reception_bp.route('/daily-close', methods=['GET', 'POST'])
@login_required
@role_required('reception', 'super_admin', 'manager')
def daily_close():
    """إغلاق اليومية"""
    from models.cash_register import CashRegister
    reg = CashRegister.get_or_create_today(current_user.id)
    if request.method == 'POST':
        reg.actual_cash = float(request.form.get('actual_cash', 0))
        reg.actual_card = float(request.form.get('actual_card', 0))
        reg.actual_insurance = float(request.form.get('actual_insurance', 0))
        reg.actual_total = (reg.actual_cash or 0) + (reg.actual_card or 0) + (reg.actual_insurance or 0)
        reg.variance = (reg.actual_total or 0) - (float(reg.expected_total or 0))
        reg.is_closed = True
        reg.is_open = False
        reg.closed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('تم إغلاق اليومية بنجاح', 'success')
        return redirect(url_for('reception.cash_register'))
    return render_template('reception/daily_close.html', register=reg)


