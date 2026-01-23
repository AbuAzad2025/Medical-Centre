"""
مسارات الحجز عن بعد - Online Booking Routes
Medical System Online Booking Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user, login_user
from models.online_booking import OnlineBooking, PaymentTransaction
from models.patient import Patient
from models.patient_account import PatientAccount
from models.appointment import Appointment
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from app_factory import db
import logging
from datetime import datetime, timedelta, timezone
import json
import secrets

booking_bp = Blueprint('booking', __name__)

def _extract_meeting_link(notes):
    if not notes:
        return None
    for part in notes.split():
        if part.startswith('MEET:'):
            return part.replace('MEET:', '')
    return None

@booking_bp.route('/register', methods=['GET', 'POST'])
@booking_bp.route('/booking/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            full_name = (request.form.get('full_name') or '').strip()
            phone = (request.form.get('phone') or '').strip()
            email = (request.form.get('email') or '').strip() or None
            national_id = (request.form.get('national_id') or '').strip() or None
            password = (request.form.get('password') or '').strip()

            if not full_name:
                raise ValueError('الاسم مطلوب')
            if not phone:
                raise ValueError('رقم الهاتف مطلوب')
            if not password:
                raise ValueError('كلمة المرور مطلوبة')

            if not email:
                import uuid
                email = f"patient_{phone}_{uuid.uuid4().hex[:6]}@booking.local"

            if User.query.filter_by(email=email).first():
                raise ValueError('البريد الإلكتروني مستخدم مسبقاً')

            base_username = f"patient_{phone}".replace('+', '').replace(' ', '')
            username = base_username
            i = 0
            while User.query.filter_by(username=username).first():
                i += 1
                username = f"{base_username}_{i}"

            parts = [p for p in full_name.split(' ') if p]
            first_name = parts[0] if parts else full_name
            last_name = ' '.join(parts[1:]) if len(parts) > 1 else '-'

            patient = None
            if national_id:
                patient = Patient.query.filter_by(national_id=national_id).first()
            if not patient and phone:
                patient = Patient.query.filter_by(phone=phone).first()
            if not patient:
                patient = Patient(first_name=first_name, last_name=last_name, national_id=national_id, phone=phone)
                db.session.add(patient)
                db.session.flush()

            user = User(username=username, email=email, full_name=full_name, role='patient', phone=phone, is_active=True)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            existing_link = PatientAccount.query.filter_by(patient_id=patient.id).first()
            if existing_link:
                raise ValueError('هذا المريض مرتبط بحساب آخر')
            db.session.add(PatientAccount(user_id=user.id, patient_id=patient.id))
            db.session.commit()

            login_user(user, remember=True)
            flash('تم إنشاء الحساب بنجاح', 'success')
            return redirect(url_for('booking.dashboard_portal'))
        except Exception as e:
            db.session.rollback()
            flash('تعذر إنشاء الحساب، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')

    return render_template('booking/register.html')


@booking_bp.route('/dashboard')
@booking_bp.route('/booking/dashboard')
@login_required
def dashboard_portal():
    if current_user.role not in ['patient', 'admin', 'super_admin', 'manager', 'reception']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    link = PatientAccount.query.filter_by(user_id=current_user.id).first() if current_user.role == 'patient' else None
    patient = db.session.get(Patient, link.patient_id) if link else None

    bookings = []
    if patient:
        bookings = OnlineBooking.query.filter(
            OnlineBooking.patient_id == patient.id
        ).order_by(OnlineBooking.created_at.desc()).limit(50).all()

    return render_template('booking/dashboard.html', patient=patient, bookings=bookings)


@booking_bp.route('/cancel/<int:booking_id>', methods=['POST'])
@booking_bp.route('/booking/cancel/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    if current_user.role != 'patient':
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'message': 'غير مصرح'}), 403
        flash('ليس لديك صلاحية', 'error')
        return redirect(url_for('booking.dashboard_portal'))
    try:
        link = PatientAccount.query.filter_by(user_id=current_user.id).first()
        if not link:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'لا يوجد حساب مريض مرتبط'}), 403
            flash('لا يوجد حساب مريض مرتبط', 'error')
            return redirect(url_for('booking.dashboard_portal'))
        booking = db.session.get(OnlineBooking, booking_id)
        if not booking or booking.patient_id != link.patient_id:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'الحجز غير موجود'}), 404
            flash('الحجز غير موجود', 'error')
            return redirect(url_for('booking.dashboard_portal'))
        if not booking.can_be_cancelled():
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'لا يمكن إلغاء هذا الحجز حالياً'}), 409
            flash('لا يمكن إلغاء هذا الحجز', 'warning')
            return redirect(url_for('booking.dashboard_portal'))
        booking.status = 'cancelled'
        booking.cancelled_at = datetime.now(timezone.utc)
        db.session.commit()
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role='reception',
                title='إلغاء حجز',
                message=f"تم إلغاء الحجز {booking.booking_reference} بواسطة المريض.",
                notification_type='warning',
                is_urgent=False
            )
            if booking.email:
                NotificationService.add_to_notification_queue(
                    user_id=current_user.id,
                    notification_type='email',
                    recipient=booking.email,
                    subject='إلغاء حجز',
                    content=f"تم إلغاء حجزك رقم {booking.booking_reference}.",
                    priority='normal',
                    scheduled_at=datetime.now(timezone.utc)
                )
            NotificationService.send_notification(
                recipient_id=current_user.id,
                title='تم إلغاء الحجز',
                message=f"تم إلغاء حجزك رقم {booking.booking_reference}.",
                notification_type='info',
                is_urgent=False
            )
        except Exception:
            pass
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': True}), 200
        flash('تم إلغاء الحجز', 'success')
        return redirect(url_for('booking.dashboard_portal'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Cancel booking error: {str(e)}")
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'message': 'تعذر إلغاء الحجز حالياً'}), 500
        flash('حدث خطأ', 'error')
        return redirect(url_for('booking.dashboard_portal'))

@booking_bp.route('/')
@booking_bp.route('/booking')
def index():
    """صفحة الحجز الرئيسية"""
    try:
        # جلب الأقسام المتاحة للحجز
        departments = Department.query.filter_by(is_active=True).all()
        
        # جلب الأطباء المتاحين
        doctors = User.query.filter_by(role='doctor', is_active=True).all()
        
        return render_template('booking/index.html', 
                             departments=departments, 
                             doctors=doctors)
    except Exception as e:
        logging.error(f"Error loading booking page: {str(e)}")
        flash('حدث خطأ في تحميل صفحة الحجز', 'error')
        return redirect(url_for('main.dashboard'))

@booking_bp.route('/create', methods=['GET', 'POST'])
@booking_bp.route('/booking/create', methods=['GET', 'POST'])
def create_booking():
    """إنشاء حجز جديد"""
    if request.method == 'POST':
        try:
            first_name = (request.form.get('first_name') or '').strip()
            last_name = (request.form.get('last_name') or '').strip()
            if not first_name and not last_name:
                patient_name = (request.form.get('patient_name') or '').strip()
                parts = [p for p in patient_name.split(' ') if p]
                if len(parts) == 0:
                    raise ValueError('اسم المريض مطلوب')
                if len(parts) == 1:
                    first_name = parts[0]
                    last_name = '-'
                else:
                    first_name = parts[0]
                    last_name = ' '.join(parts[1:])

            phone = (request.form.get('phone') or request.form.get('patient_phone') or '').strip()
            if not phone:
                raise ValueError('رقم الهاتف مطلوب')

            email = (request.form.get('email') or request.form.get('patient_email') or '').strip() or None

            department_id = request.form.get('department_id')
            department_id = int(department_id) if department_id else None
            if not department_id:
                raise ValueError('القسم مطلوب')

            doctor_id = request.form.get('doctor_id')
            doctor_id = int(doctor_id) if doctor_id else None

            date_str = request.form.get('appointment_date') or request.form.get('preferred_date')
            if not date_str:
                raise ValueError('تاريخ الموعد مطلوب')
            appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()

            time_str = (request.form.get('appointment_time') or request.form.get('preferred_time') or '').strip()
            if not time_str:
                raise ValueError('وقت الموعد مطلوب')
            try:
                appointment_time = datetime.strptime(time_str, '%H:%M').time()
            except ValueError:
                appointment_time = datetime.strptime(time_str, '%H:%M:%S').time()

            visit_type = (request.form.get('visit_type') or 'first').strip()
            if visit_type not in {'first', 'follow_up', 'emergency', 'telemedicine'}:
                visit_type = 'first'

            booking = OnlineBooking(
                booking_reference=OnlineBooking.generate_booking_reference(),
                confirmation_code=OnlineBooking.generate_confirmation_code(),
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                department_id=department_id,
                doctor_id=doctor_id,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                visit_type=visit_type,
                notes=request.form.get('notes'),
                status='pending'
            )

            try:
                if current_user.is_authenticated and current_user.role == 'patient':
                    link = PatientAccount.query.filter_by(user_id=current_user.id).first()
                    if link:
                        booking.patient_id = link.patient_id
                        booking.is_new_patient = False
            except Exception:
                pass
            
            db.session.add(booking)
            db.session.commit()

            if visit_type == 'telemedicine':
                meeting_token = secrets.token_urlsafe(8)
                meeting_link = url_for('booking.telemedicine_room', booking_id=booking.id, _external=True) + f"?token={meeting_token}"
                booking.notes = (booking.notes or '').strip()
                booking.notes = (booking.notes + ' ' if booking.notes else '') + f"MEET:{meeting_link}"
                db.session.commit()

            try:
                from services.notification_service import NotificationService
                dept = db.session.get(Department, booking.department_id) if booking.department_id else None
                doctor = db.session.get(User, booking.doctor_id) if booking.doctor_id else None
                dt_str = f"{booking.appointment_date} {booking.appointment_time.strftime('%H:%M') if booking.appointment_time else ''}".strip()
                msg = f"حجز جديد {booking.booking_reference} للمريض {booking.get_full_name()} بتاريخ {dt_str} في {dept.name_ar if dept else 'القسم'} {('مع ' + doctor.full_name) if doctor else ''}".strip()
                NotificationService.send_notification(
                    recipient_role='reception',
                    title='حجز جديد',
                    message=msg,
                    notification_type='info',
                    is_urgent=False
                )
                if booking.email:
                    queue_user_id = None
                    try:
                        queue_user_id = current_user.id if current_user.is_authenticated else None
                    except Exception:
                        queue_user_id = None
                    if not queue_user_id:
                        queue_user_id = doctor.id if doctor else None
                    if not queue_user_id:
                        any_user = User.query.first()
                        queue_user_id = any_user.id if any_user else 1
                    NotificationService.add_to_notification_queue(
                        user_id=queue_user_id,
                        notification_type='email',
                        recipient=booking.email,
                        subject='تأكيد حجز',
                        content=f"تم استلام حجزك رقم {booking.booking_reference} بتاريخ {dt_str}.",
                        priority='normal',
                        scheduled_at=datetime.now(timezone.utc)
                    )
                if current_user.is_authenticated and current_user.role == 'patient':
                    NotificationService.send_notification(
                        recipient_id=current_user.id,
                        title='تم استلام الحجز',
                        message=f"تم استلام حجزك رقم {booking.booking_reference} بتاريخ {dt_str}.",
                        notification_type='success',
                        is_urgent=False
                    )
            except Exception:
                pass
            
            flash('تم إنشاء الحجز بنجاح', 'success')
            return redirect(url_for('booking.confirmation', booking_id=booking.id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating booking: {str(e)}")
            flash('تعذر إنشاء الحجز، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    preset_department_id = request.args.get('department_id', type=int)
    preset_doctor_id = request.args.get('doctor_id', type=int)
    preset_date = request.args.get('appointment_date') or None
    preset_time = request.args.get('appointment_time') or None

    patient_prefill = None
    if current_user.is_authenticated and current_user.role == 'patient':
        link = PatientAccount.query.filter_by(user_id=current_user.id).first()
        if link:
            patient_prefill = db.session.get(Patient, link.patient_id)

    # جلب البيانات المطلوبة للنموذج
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    
    return render_template('booking/create.html', 
                         departments=departments, 
                         doctors=doctors,
                         preset_department_id=preset_department_id,
                         preset_doctor_id=preset_doctor_id,
                         preset_date=preset_date,
                         preset_time=preset_time,
                         patient_prefill=patient_prefill)

@booking_bp.route('/confirmation/<int:booking_id>')
@booking_bp.route('/booking/confirmation/<int:booking_id>')
def confirmation(booking_id):
    """تأكيد الحجز"""
    try:
        booking = db.session.get(OnlineBooking, booking_id)
        if not booking:
            abort(404)
        meeting_link = _extract_meeting_link(booking.notes or '')
        return render_template('booking/confirmation.html', booking=booking, meeting_link=meeting_link)
    except Exception as e:
        logging.error(f"Error loading booking confirmation: {str(e)}")
        flash('حدث خطأ في تحميل تأكيد الحجز', 'error')
        return redirect(url_for('booking.index'))

@booking_bp.route('/telemedicine/<int:booking_id>')
@booking_bp.route('/booking/telemedicine/<int:booking_id>')
def telemedicine_room(booking_id):
    try:
        booking = db.session.get(OnlineBooking, booking_id)
        if not booking:
            abort(404)
        meeting_link = _extract_meeting_link(booking.notes or '')
        return render_template('booking/telemedicine_room.html', booking=booking, meeting_link=meeting_link)
    except Exception as e:
        logging.error(f"Error loading telemedicine room: {str(e)}")
        flash('تعذر تحميل جلسة التطبيب عن بُعد', 'error')
        return redirect(url_for('booking.index'))

@booking_bp.route('/payment/<int:booking_id>', methods=['GET', 'POST'])
@booking_bp.route('/booking/payment/<int:booking_id>', methods=['GET', 'POST'])
def payment(booking_id):
    """دفع رسوم الحجز"""
    booking = db.session.get(OnlineBooking, booking_id)
    if not booking:
        abort(404)
    
    if request.method == 'POST':
        try:
            amount_raw = request.form.get('amount', 50.0)
            try:
                amount_val = float(amount_raw)
            except Exception:
                amount_val = 50.0
            payment_method = (request.form.get('payment_method') or 'CASH').strip().upper()

            # إنشاء معاملة دفع
            payment = PaymentTransaction(
                booking_id=booking_id,
                transaction_reference=PaymentTransaction.generate_transaction_reference(),
                amount=amount_val,
                payment_method=payment_method,
                status='pending'
            )
            
            db.session.add(payment)
            db.session.commit()
            
            flash('تم إنشاء معاملة الدفع بنجاح', 'success')
            return redirect(url_for('booking.confirmation', booking_id=booking_id))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing payment: {str(e)}")
            flash('تعذر معالجة الدفع حالياً، يرجى المحاولة مرة أخرى', 'error')
    
    return render_template('booking/payment.html', booking=booking)

@booking_bp.route('/api/available-doctors')
def api_available_doctors():
    """API لجلب الأطباء المتاحين مع تصفية حسب القسم ونوع الموعد (اختياري)"""
    try:
        department_id = request.args.get('department_id', type=int)
        appointment_type = request.args.get('appointment_type', type=str)

        query = User.query.filter_by(role='doctor', is_active=True)
        if department_id:
            query = query.filter(User.department_id == department_id)

        # يمكن لاحقًا استخدام appointment_type لفلترة الأطباء بحسب التسعير أو جدول العمل
        doctors = query.order_by(User.full_name.asc()).all()
        
        return jsonify({
            'success': True,
            'doctors': [{'id': doctor.id, 'full_name': doctor.full_name} for doctor in doctors]
        })
        
    except Exception as e:
        logging.error(f"Error getting available doctors: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب الأطباء المتاحين حالياً'})

@booking_bp.route('/api/available-times')
def api_available_times():
    """API لجلب الأوقات المتاحة"""
    try:
        doctor_id = request.args.get('doctor_id', type=int)
        date_str = request.args.get('date')
        
        if not doctor_id or not date_str:
            return jsonify({'success': False, 'message': 'معاملات مطلوبة'}), 400
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        from sqlalchemy import func, inspect

        insp = inspect(db.engine)

        existing_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            func.date(Appointment.starts_at) == date_obj
        ).all()

        taken_times = set()
        for apt in existing_appointments:
            try:
                taken_times.add(apt.starts_at.strftime('%H:%M'))
            except Exception:
                continue

        available_times = []

        has_schedule = insp.has_table('staff_work_schedules')
        has_absence = insp.has_table('staff_absences')

        if has_absence:
            absent = StaffAbsence.query.filter(
                StaffAbsence.user_id == doctor_id,
                StaffAbsence.start_date <= date_obj,
                StaffAbsence.end_date >= date_obj
            ).first()
            if absent:
                return jsonify({'success': True, 'available_times': []})

        if has_schedule:
            dow = date_obj.weekday()
            sched = StaffWorkSchedule.query.filter(
                StaffWorkSchedule.user_id == doctor_id,
                StaffWorkSchedule.day_of_week == dow,
                StaffWorkSchedule.is_active == True
            ).first()
            if sched:
                start_hour = sched.start_time.hour
                end_hour = sched.end_time.hour
                for hour in range(start_hour, end_hour):
                    time_str = f"{hour:02d}:00"
                    if time_str not in taken_times:
                        available_times.append(time_str)
            else:
                for hour in range(9, 17):
                    time_str = f"{hour:02d}:00"
                    if time_str not in taken_times:
                        available_times.append(time_str)
        else:
            for hour in range(9, 17):
                time_str = f"{hour:02d}:00"
                if time_str not in taken_times:
                    available_times.append(time_str)
        
        return jsonify({
            'success': True,
            'available_times': available_times
        })
        
    except Exception as e:
        logging.error(f"Error getting available times: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر جلب الأوقات المتاحة حالياً'})

@booking_bp.route('/api/smart-slots')
def api_smart_slots():
    try:
        doctor_id = request.args.get('doctor_id', type=int)
        date_str = request.args.get('date')
        if not doctor_id or not date_str:
            return jsonify({'success': False, 'message': 'معاملات مطلوبة'}), 400
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        from sqlalchemy import func, inspect
        insp = inspect(db.engine)
        existing_appointments = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            func.date(Appointment.starts_at) == date_obj
        ).all()
        taken_times = set()
        for apt in existing_appointments:
            try:
                taken_times.add(apt.starts_at.strftime('%H:%M'))
            except Exception:
                continue
        available_times = []
        has_schedule = insp.has_table('staff_work_schedules')
        if has_schedule:
            dow = date_obj.weekday()
            sched = StaffWorkSchedule.query.filter(
                StaffWorkSchedule.user_id == doctor_id,
                StaffWorkSchedule.day_of_week == dow,
                StaffWorkSchedule.is_active == True
            ).first()
            if sched:
                start_hour = sched.start_time.hour
                end_hour = sched.end_time.hour
            else:
                start_hour = 9
                end_hour = 17
        else:
            start_hour = 9
            end_hour = 17
        for hour in range(start_hour, end_hour):
            time_str = f"{hour:02d}:00"
            if time_str not in taken_times:
                available_times.append(time_str)
        suggested = []
        for t in available_times:
            if t.startswith('10') or t.startswith('11'):
                suggested.append(t)
        if not suggested:
            suggested = available_times[:3]
        else:
            suggested = suggested[:3]
        return jsonify({'success': True, 'suggested_times': suggested, 'available_times': available_times}), 200
    except Exception as e:
        logging.error(f"Error getting smart slots: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر اقتراح الأوقات'}), 500
