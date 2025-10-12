"""
مسارات الاستقبال - Reception Routes
نسخة محسّنة مع دعم كامل للتحقق من قواعد العمل
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.appointment import Appointment
from models.department import Department
from models.payment import Payment, PaymentMethod, PaymentStatus
from services.gatekeeper_service import GatekeeperService
from utils.decorators import can_create_visits, reception_only
from app_factory import db
import logging

reception_bp = Blueprint('reception', __name__)

@reception_bp.route('/')
@login_required
def index():
    """توجيه تلقائي إلى لوحة التحكم"""
    return redirect(url_for('reception.dashboard'))

@reception_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الاستقبال - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    # إحصائيات شاملة للوحدة المركزية
    total_patients = Patient.query.count()
    today_visits = Visit.query.filter(
        db.func.date(Visit.created_at) == db.func.current_date()
    ).count()
    pending_appointments = Appointment.query.filter_by(status='SCHEDULED').count()
    
    # إحصائيات الطوابير لكل قسم
    departments = Department.query.all()
    queue_stats = {}
    for dept in departments:
        queue_stats[dept.id] = {
            'name': dept.name_ar,
            'total_queue': 0,  # سيتم تحديثها لاحقاً
            'waiting': 0,
            'in_progress': 0
        }
    
    # الميزات الذكية
    smart_analytics = get_smart_queue_management()
    patient_flow = get_patient_flow_analysis()
    appointment_optimization = get_appointment_optimization()
    real_time_alerts = get_real_time_alerts()
    
    # تجميع الإحصائيات
    stats = {
        'smart_queue_management': smart_analytics,
        'patient_flow': patient_flow,
        'patient_flow_analysis': patient_flow,
        'appointment_optimization': appointment_optimization,
        'real_time_alerts': real_time_alerts
    }
    
    return render_template('reception/dashboard.html',
                         total_patients=total_patients,
                         today_visits=today_visits,
                         pending_appointments=pending_appointments,
                         departments=departments,
                         queue_stats=queue_stats,
                         smart_analytics=smart_analytics,
                         patient_flow=patient_flow,
                         appointment_optimization=appointment_optimization,
                         real_time_alerts=real_time_alerts,
                         stats=stats)

@reception_bp.route('/patients')
@login_required
def patients():
    """قائمة المرضى - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    # البحث والفلترة
    search = request.args.get('search', '')
    department_id = request.args.get('department_id', type=int)
    
    query = Patient.query
    
    if search:
        query = query.filter(
            db.or_(
                Patient.full_name.contains(search),
                Patient.phone.contains(search),
                Patient.national_id.contains(search)
            )
        )
    
    patients = query.all()
    departments = Department.query.all()
    
    return render_template('reception/patients.html', 
                         patients=patients, 
                         departments=departments,
                         search=search,
                         selected_department=department_id)

@reception_bp.route('/add_patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    """إضافة مريض جديد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            patient = Patient(
                national_id=request.form.get('national_id'),
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                first_name_ar=request.form.get('first_name_ar'),
                last_name_ar=request.form.get('last_name_ar'),
                phone=request.form.get('phone'),
                birth_date=request.form.get('birth_date'),
                gender=request.form.get('gender'),
                address=request.form.get('address'),
                notes=request.form.get('notes')
            )
            
            db.session.add(patient)
            db.session.commit()
            
            flash('تم إضافة المريض بنجاح.', 'success')
            return redirect(url_for('reception.patients'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في إضافة المريض: {str(e)}', 'error')
            logging.error(f"Error adding patient: {str(e)}")
    
    departments = Department.query.all()
    return render_template('reception/add_patient.html', departments=departments)

@reception_bp.route('/visits')
@login_required
def visits():
    """قائمة الزيارات - الوحدة المركزية"""
    # التحقق من الصلاحيات
    if current_user.role not in ['reception', 'accountant', 'admin', 'manager', 'super_admin']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    # البحث والفلترة
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
    departments = Department.query.all()
    
    return render_template('reception/visits.html', 
                         visits=visits, 
                         departments=departments,
                         search=search,
                         selected_department=department_id,
                         selected_status=status)

@reception_bp.route('/create_visit', methods=['GET', 'POST'])
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
            
            # بيانات التأمين
            insurance_provider = request.form.get('insurance_provider', '')
            insurance_policy_number = request.form.get('insurance_policy_number', '')
            insurance_coverage = request.form.get('insurance_coverage', '0')
            
            # بيانات البطاقة
            card_last_digits = request.form.get('card_last_digits', '')
            card_holder_name = request.form.get('card_holder_name', '')
            
            # بيانات الدفع القسري
            is_emergency = request.form.get('is_emergency') == 'on'
            is_force_payment = request.form.get('is_force_payment') == 'on'
            force_payment_reason = request.form.get('force_payment_reason', '')
            
            # مبلغ الدفع المبدئي
            amount_paid = request.form.get('amount_paid', '0')
            
            # ========== المرحلة 2: التحقق من البيانات الأساسية ==========
            if not patient_id:
                flash('يجب اختيار مريض', 'error')
                raise ValueError("Patient is required")
            
            if not department_id:
                flash('يجب اختيار قسم', 'error')
                raise ValueError("Department is required")
            
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
                payment_method=payment_method,
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
            
            # ========== المرحلة 7: إضافة بيانات البطاقة ==========
            elif payment_method in ['visa', 'card']:
                visit.card_number_last_digits = card_last_digits
                visit.card_holder_name = card_holder_name
            
            # ========== المرحلة 8: إضافة بيانات الدفع القسري ==========
            elif is_force_payment:
                visit.force_payment_reason = force_payment_reason
                # الموافقة ستكون لاحقاً من المدير
            
            # ========== المرحلة 9: حساب التكلفة ==========
            # TODO: استخدام خدمة التسعير لحساب التكلفة بدقة
            visit_cost = calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method)
            visit.total_amount = visit_cost
            
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
                    payment = Payment(
                        patient_id=patient_id,
                        visit_id=None,  # سيتم تحديثه بعد حفظ الزيارة
                        method=payment_method.upper(),
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
                        payment_date=datetime.utcnow()
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
            
            db.session.commit()
            
            # ========== المرحلة 12: إضافة للطابور ==========
            # فقط إذا تم الدفع أو موافقة الطوارئ
            if visit.payment_status in ['PAID', 'PARTIAL'] or is_emergency:
                try:
                    add_patient_to_queue_auto(visit.id, department_id, doctor_id)
                except Exception as queue_error:
                    logging.warning(f"Could not add to queue: {str(queue_error)}")
            
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
            flash(f'حدث خطأ غير متوقع: {str(e)}', 'error')
            logging.error(f"Error creating visit: {str(e)}", exc_info=True)
    
    # ========== GET Request: عرض النموذج ==========
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    
    return render_template('reception/create_visit.html',
                         patients=patients,
                         departments=departments,
                         doctors=doctors)

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
    status = request.args.get('status', '')
    
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
    
    if status:
        query = query.filter(Appointment.status == status)
    
    appointments = query.order_by(Appointment.starts_at.desc()).all()
    departments = Department.query.all()
    
    return render_template('reception/appointments.html', 
                         appointments=appointments, 
                         departments=departments,
                         search=search,
                         selected_department=department_id,
                         selected_status=status)

@reception_bp.route('/create_appointment', methods=['GET', 'POST'])
@login_required
def create_appointment():
    """إنشاء موعد جديد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        try:
            from datetime import datetime
            
            # دمج التاريخ والوقت
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            starts_at = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            
            appointment = Appointment(
                patient_id=request.form.get('patient_id'),
                doctor_id=request.form.get('doctor_id'),
                department_id=request.form.get('department_id'),
                starts_at=starts_at,
                notes=request.form.get('notes'),
                created_by=current_user.id
            )
            
            db.session.add(appointment)
            db.session.commit()
            
            flash('تم إنشاء الموعد بنجاح.', 'success')
            return redirect(url_for('reception.appointments'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في إنشاء الموعد: {str(e)}', 'error')
            logging.error(f"Error creating appointment: {str(e)}")
    
    # جلب البيانات المطلوبة للنموذج
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    
    return render_template('reception/create_appointment.html',
                         patients=patients,
                         departments=departments,
                         doctors=doctors)

# مسارات إضافية للاستقبال
@reception_bp.route('/view_patient/<int:patient_id>')
@login_required
def view_patient(patient_id):
    """عرض تفاصيل المريض - الوحدة المركزية"""
    # التحقق من الصلاحيات
    if current_user.role not in ['reception', 'doctor', 'emergency', 'admin', 'manager', 'super_admin', 'accountant']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = Patient.query.get_or_404(patient_id)
    visits = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.created_at.desc()).limit(10).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.starts_at.desc()).limit(10).all()
    
    # تحديد القالب حسب الدور
    if current_user.role == 'doctor':
        template = 'doctor/view_patient.html'
    elif current_user.role == 'emergency':
        template = 'emergency/view_patient.html'
    else:
        template = 'reception/view_patient.html'
    
    return render_template(template, 
                         patient=patient, 
                         visits=visits, 
                         appointments=appointments)

@reception_bp.route('/edit_patient/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def edit_patient(patient_id):
    """تعديل بيانات المريض - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        try:
            patient.national_id = request.form.get('national_id')
            patient.first_name = request.form.get('first_name')
            patient.last_name = request.form.get('last_name')
            patient.first_name_ar = request.form.get('first_name_ar')
            patient.last_name_ar = request.form.get('last_name_ar')
            patient.phone = request.form.get('phone')
            patient.birth_date = request.form.get('birth_date')
            patient.gender = request.form.get('gender')
            patient.address = request.form.get('address')
            patient.notes = request.form.get('notes')
            
            db.session.commit()
            flash('تم تحديث بيانات المريض بنجاح.', 'success')
            return redirect(url_for('reception.view_patient', patient_id=patient_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في تحديث بيانات المريض: {str(e)}', 'error')
            logging.error(f"Error updating patient: {str(e)}")
    
    departments = Department.query.all()
    return render_template('reception/patients.html', 
                         patient=patient,
                         departments=departments,
                         mode='edit')

@reception_bp.route('/view_visit/<int:visit_id>')
@login_required
def view_visit(visit_id):
    """عرض تفاصيل الزيارة - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    visit = Visit.query.get_or_404(visit_id)
    return render_template('reception/visits.html', visit=visit, mode='view')

@reception_bp.route('/process_payment/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def process_payment(visit_id):
    """معالجة الدفع وإضافة للطابور - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    visit = Visit.query.get_or_404(visit_id)
    
    if request.method == 'POST':
        try:
            payment_method = request.form.get('payment_method')
            is_force_payment = request.form.get('is_force_payment') == 'on'
            force_reason = request.form.get('force_reason', '')
            
            # تحديث حالة الدفع
            if is_force_payment or payment_method in ['cash', 'visa', 'insurance']:
                visit.payment_status = 'PAID'
                visit.paid_amount = visit.total_amount
                visit.payment_method = payment_method
                if is_force_payment:
                    visit.is_force_payment = True
                    visit.force_payment_reason = force_reason
                    visit.force_payment_approved_by = current_user.id
                
                db.session.commit()
                
                # إضافة المريض للطابور
                add_patient_to_queue_auto(visit.id, visit.department_id, visit.doctor_id)
                
                flash('تم معالجة الدفع وإضافة المريض للطابور بنجاح.', 'success')
                return redirect(url_for('reception.print_receipt', visit_id=visit.id))
            else:
                flash('يجب اختيار طريقة دفع صحيحة.', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في معالجة الدفع: {str(e)}', 'error')
            logging.error(f"Error processing payment: {str(e)}")
    
    return render_template('accountant/process_payment.html', visit=visit)

@reception_bp.route('/print_receipt/<int:visit_id>')
@login_required
def print_receipt(visit_id):
    """طباعة سند القبض - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    visit = Visit.query.get_or_404(visit_id)
    return render_template('print/receipt.html', visit=visit)

@reception_bp.route('/print_invoice/<int:invoice_id>')
@login_required
def print_invoice(invoice_id):
    """طباعة الفاتورة"""
    if current_user.role not in ['reception', 'super_admin', 'manager', 'accountant']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    from models.invoice import Invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('print/invoice.html', invoice=invoice)

@reception_bp.route('/print_prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    """طباعة الروشتة الطبية"""
    if current_user.role not in ['doctor', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    from models.medical_record import Prescription
    prescription = Prescription.query.get_or_404(prescription_id)
    return render_template('print/prescription.html', prescription=prescription)

@reception_bp.route('/view_appointment/<int:appointment_id>')
@login_required
def view_appointment(appointment_id):
    """عرض تفاصيل الموعد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    return render_template('reception/appointments.html', appointment=appointment, mode='view')

@reception_bp.route('/edit_appointment/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
def edit_appointment(appointment_id):
    """تعديل الموعد - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    
    if request.method == 'POST':
        try:
            from datetime import datetime
            
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            starts_at = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")
            
            appointment.doctor_id = request.form.get('doctor_id')
            appointment.department_id = request.form.get('department_id')
            appointment.starts_at = starts_at
            appointment.appointment_type = request.form.get('appointment_type')
            appointment.symptoms = request.form.get('symptoms')
            appointment.notes = request.form.get('notes')
            
            db.session.commit()
            flash('تم تحديث الموعد بنجاح.', 'success')
            return redirect(url_for('reception.view_appointment', appointment_id=appointment_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ في تحديث الموعد: {str(e)}', 'error')
            logging.error(f"Error updating appointment: {str(e)}")
    
    # جلب البيانات المطلوبة للنموذج
    patients = Patient.query.all()
    departments = Department.query.filter_by(is_active=True).all()
    doctors = User.query.filter_by(role='doctor', is_active=True).all()
    
    return render_template('reception/appointments.html', 
                         appointment=appointment,
                         patients=patients,
                         departments=departments,
                         doctors=doctors,
                         mode='edit')

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
        # البحث الذكي في عدة حقول
        patients = Patient.query.filter(
            db.or_(
                Patient.full_name.contains(search_term),
                Patient.first_name.contains(search_term),
                Patient.last_name.contains(search_term),
                Patient.national_id.contains(search_term),
                Patient.phone.contains(search_term),
                Patient.birth_date.contains(search_term)
            )
        ).limit(10).all()
        
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
        department = Department.query.get(department_id)
        if not department:
            return jsonify({'error': 'القسم غير موجود'}), 404
        
        staff = []
        
        # تحديد نوع الموظفين حسب القسم
        if 'lab' in department.name.lower() or 'مختبر' in department.name:
            # موظفو المختبر
            staff = User.query.filter(
                User.role.in_(['lab', 'technician']),
                User.department_id == department_id,
                User.is_active == True
            ).all()
        elif 'radiology' in department.name.lower() or 'أشعة' in department.name:
            # موظفو الأشعة
            staff = User.query.filter(
                User.role.in_(['radiology', 'technician']),
                User.department_id == department_id,
                User.is_active == True
            ).all()
        elif 'emergency' in department.name.lower() or 'طوارئ' in department.name or 'طواريء' in department.name:
            # موظفو الطوارئ
            staff = User.query.filter(
                User.role.in_(['emergency', 'doctor', 'nurse']),
                User.department_id == department_id,
                User.is_active == True
            ).all()
        else:
            # الأطباء العاديين
            staff = User.query.filter(
                User.role == 'doctor',
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
    
    try:
        cost = calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method)
        
        # إضافة تفاصيل التكلفة
        pricing_details = get_pricing_details(department_id, doctor_id, visit_type, is_emergency, payment_method)
        
        return jsonify({
            'cost': cost,
            'details': pricing_details
        })
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
        department = Department.query.get(department_id)
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
        if doctor_id:
            doctor_cost = calculate_doctor_cost(doctor_id, department_id, visit_type, is_emergency, payment_method)
            details['doctor_cost'] = doctor_cost
            if doctor_cost > 0:
                details['breakdown'].append({
                    'item': 'رسوم الطبيب',
                    'cost': doctor_cost
                })
        
        # حساب الخصم للمراجعة
        if visit_type == 'FOLLOW_UP':
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

@reception_bp.route('/api/available-times')
@login_required
def api_available_times():
    """API لجلب الأوقات المتاحة"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')

    if not doctor_id or not date:
        return jsonify({'success': False, 'message': 'معاملات مطلوبة'}), 400

    # جلب المواعيد الموجودة للطبيب في التاريخ المحدد
    existing_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.starts_at >= date,
        Appointment.status.in_(['SCHEDULED', 'CONFIRMED'])
    ).all()

    # الأوقات المتاحة (من 8 صباحاً إلى 5 مساءً)
    available_times = []
    for hour in range(8, 17):
        for minute in [0, 30]:
            time_str = f"{hour:02d}:{minute:02d}"
            is_available = True

            for appointment in existing_appointments:
                if appointment.appointment_time == time_str:
                    is_available = False
                    break

            if is_available:
                available_times.append(time_str)

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
        
        queue_service = QueueManagementService()
        all_departments = Department.query.filter_by(is_active=True).all()
        
        # فلترة الأقسام حسب الدور
        # الأدوار الإدارية ترى كل الأقسام
        if current_user.role in ['reception', 'super_admin', 'manager']:
            departments = all_departments
        # المختبر يرى فقط طابور المختبر
        elif current_user.role == 'lab':
            departments = [dept for dept in all_departments if 'lab' in dept.name.lower() or 'مختبر' in dept.name]
        # الأشعة ترى فقط طابور الأشعة
        elif current_user.role == 'radiology':
            departments = [dept for dept in all_departments if 'radiology' in dept.name.lower() or 'أشعة' in dept.name]
        # الطبيب يرى فقط طابور قسمه
        elif current_user.role == 'doctor':
            if current_user.department_id:
                departments = [dept for dept in all_departments if dept.id == current_user.department_id]
            else:
                departments = []
        # الطوارئ ترى فقط طابور الطوارئ
        elif current_user.role == 'emergency':
            departments = [dept for dept in all_departments if 'emergency' in dept.name.lower() or 'طوارئ' in dept.name or 'طواريء' in dept.name]
        else:
            departments = []
        
        # جلب حالة الطابور لكل قسم
        queue_status = {}
        for dept in departments:
            queue_status[dept.id] = queue_service.get_queue_status(dept.id)
        
        return render_template('reception/queue_management.html', 
                             departments=departments, 
                             queue_status=queue_status,
                             all_departments=all_departments if current_user.role in ['reception', 'super_admin', 'manager'] else departments)
    except Exception as e:
        logging.error(f"Error loading queue management: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الطابور', 'error')
        return redirect(url_for('reception.dashboard'))

@reception_bp.route('/queue/add-patient', methods=['GET', 'POST'])
@login_required
def add_patient_to_queue():
    """إضافة مريض إلى الطابور - الوحدة المركزية"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
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
            flash(f'حدث خطأ في إضافة المريض إلى الطابور: {str(e)}', 'error')
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
        success, message = queue_service.call_next_patient(
            department_id=department_id,
            called_by=current_user.id
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('reception.queue_management'))
        
    except Exception as e:
        logging.error(f"Error calling next patient: {str(e)}")
        flash(f'حدث خطأ في استدعاء المريض: {str(e)}', 'error')
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
        flash(f'حدث خطأ في بدء العلاج: {str(e)}', 'error')
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
        flash(f'حدث خطأ في إكمال العلاج: {str(e)}', 'error')
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
        flash(f'حدث خطأ في تخطي المريض: {str(e)}', 'error')
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
        flash(f'حدث خطأ في إلغاء التذكرة: {str(e)}', 'error')
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
        flash(f'حدث خطأ في الموافقة على دين الطوارئ: {str(e)}', 'error')
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
        flash(f'حدث خطأ في الموافقة على الدخول القوي: {str(e)}', 'error')
        return redirect(url_for('reception.queue_management'))

@reception_bp.route('/api/queue-status/<int:department_id>')
@login_required
def api_queue_status(department_id):
    """API لحالة الطابور"""
    if current_user.role != 'reception':
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403

    try:
        from services.queue_management_service import QueueManagementService
        
        queue_service = QueueManagementService()
        status = queue_service.get_queue_status(department_id)
        
        if status:
            return jsonify({'success': True, 'data': status})
        else:
            return jsonify({'success': False, 'message': 'خطأ في جلب حالة الطابور'})
            
    except Exception as e:
        logging.error(f"Error getting queue status: {str(e)}")
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

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
        return jsonify({'success': False, 'message': f'حدث خطأ: {str(e)}'})

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
            QueueManagement.status.in_(['WAITING', 'CALLED', 'IN_PROGRESS'])
        ).order_by(QueueManagement.created_at).all()
        
        # تحليل أوقات الانتظار
        avg_wait_time = db.session.query(func.avg(QueueManagement.estimated_wait_time)).scalar() or 0
        
        # تحليل الأولويات
        priority_analysis = {
            'urgent': QueueManagement.query.filter(QueueManagement.priority == 'URGENT').count(),
            'normal': QueueManagement.query.filter(QueueManagement.priority == 'NORMAL').count(),
            'low': QueueManagement.query.filter(QueueManagement.priority == 'LOW').count()
        }
        
        # تحليل ساعات الذروة
        peak_hours = db.session.query(
            func.strftime('%H', QueueManagement.created_at).label('hour'),
            func.count(QueueManagement.id).label('count')
        ).group_by(func.strftime('%H', QueueManagement.created_at)).all()
        
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
        hourly_flow = db.session.query(
            func.strftime('%H', Visit.created_at).label('hour'),
            func.count(Visit.id).label('count')
        ).filter(Visit.created_at >= week_ago).group_by(func.strftime('%H', Visit.created_at)).all()
        
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
            Appointment.status == 'pending'
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
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # تحليل عوامل الرضا
        total_visits = Visit.query.count()
        completed_visits = Visit.query.filter(Visit.status == 'ARCHIVED').count()
        
        # معدل الإنجاز
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # متوسط وقت الانتظار
        avg_wait_time = db.session.query(func.avg(Visit.duration)).scalar() or 0
        
        # تحليل التكرار
        repeat_visits = db.session.query(
            Visit.patient_id,
            func.count(Visit.id).label('visit_count')
        ).group_by(Visit.patient_id).having(func.count(Visit.id) > 1).count()
        
        # حساب نقاط الرضا
        satisfaction_score = calculate_satisfaction_score(completion_rate, avg_wait_time, repeat_visits)
        
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
        
        return {
            'satisfaction_score': satisfaction_score,
            'completion_rate': round(completion_rate, 2),
            'avg_wait_time': round(avg_wait_time, 2),
            'repeat_visits': repeat_visits,
            'recommendations': recommendations,
            'status': 'excellent' if satisfaction_score > 90 else 'good' if satisfaction_score > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting patient satisfaction AI: {str(e)}")
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
        avg_visit_duration = db.session.query(func.avg(Visit.duration)).scalar() or 0
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
    
    completed = len([t for t in queue if t.status == 'COMPLETED'])
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


def get_accessible_departments_for_user(user_role, user_department_id=None):
    """الحصول على الأقسام المتاحة للمستخدم"""
    all_departments = Department.query.filter_by(is_active=True).all()
    
    # الأدوار الإدارية والبحث الشامل ترى كل الأقسام
    if user_role in ['reception', 'super_admin', 'manager', 'doctor', 'emergency', 'accountant']:
        return all_departments
    
    # المختبر يرى فقط المختبر
    elif user_role == 'lab':
        return [dept for dept in all_departments if 'lab' in dept.name.lower() or 'مختبر' in dept.name]
    
    # الأشعة ترى فقط الأشعة
    elif user_role == 'radiology':
        return [dept for dept in all_departments if 'radiology' in dept.name.lower() or 'أشعة' in dept.name]
    
    # الصيدلية لا ترى أقسام
    elif user_role == 'pharmacist':
        return []
    
    # التمريض يرى فقط قسمه
    elif user_role == 'nurse':
        if user_department_id:
            return [dept for dept in all_departments if dept.id == user_department_id]
        else:
            return []
    
    # باقي الأدوار
    return []

# ===== وظائف مساعدة لسيناريو الزيارة =====

def calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method='cash'):
    """حساب تكلفة الزيارة تلقائياً حسب إعدادات المدير"""
    try:
        from models.pricing import ServicePrice, DoctorPricing, PricingCatalog
        from models.service import ServiceMaster
        
        total_cost = 0
        
        # 1. حساب تكلفة الخدمة الأساسية حسب القسم
        department = Department.query.get(department_id)
        if not department:
            return 0
        
        # البحث عن الخدمة في كتالوج التسعير المركزي
        service_type = get_service_type_by_department(department)
        pricing_entry = PricingCatalog.query.filter(
            PricingCatalog.service_type == service_type,
            PricingCatalog.is_active == True
        ).first()
        
        if pricing_entry:
            # استخدام السعر من كتالوج التسعير
            if payment_method == 'insurance':
                total_cost = pricing_entry.get_final_price('insurance')
            else:
                total_cost = pricing_entry.base_price
        else:
            # البحث في ServiceMaster كبديل
            service = get_service_by_department(department)
            if service:
                if is_emergency and service.emergency_price:
                    total_cost = float(service.emergency_price)
                elif payment_method == 'insurance' and service.insurance_price:
                    total_cost = float(service.insurance_price)
                else:
                    total_cost = float(service.base_price)
        
        # 2. إضافة تكلفة الطبيب إذا كان محدد
        if doctor_id:
            doctor_cost = calculate_doctor_cost(doctor_id, department_id, visit_type, is_emergency, payment_method)
            total_cost += doctor_cost
        
        # 3. تطبيق خصم المراجعة
        if visit_type == 'FOLLOW_UP':
            total_cost = total_cost * 0.7  # 30% خصم للمراجعة
        
        return round(total_cost, 2)
    except Exception as e:
        logging.error(f"Error calculating visit cost: {str(e)}")
        return 0

def get_service_type_by_department(department):
    """تحديد نوع الخدمة حسب القسم"""
    if not department:
        return 'consultation'
    
    dept_name = department.name.lower()
    if 'lab' in dept_name or 'مختبر' in dept_name:
        return 'lab'
    elif 'radiology' in dept_name or 'أشعة' in dept_name:
        return 'radiology'
    elif 'emergency' in dept_name or 'طوارئ' in dept_name or 'طواريء' in dept_name:
        return 'emergency'
    else:
        return 'consultation'

def get_service_by_department(department):
    """البحث عن الخدمة حسب القسم"""
    if not department:
        return None
    
    dept_name = department.name.lower()
    if 'lab' in dept_name or 'مختبر' in dept_name:
        return ServiceMaster.query.filter(
            ServiceMaster.category == 'lab',
            ServiceMaster.is_active == True
        ).first()
    elif 'radiology' in dept_name or 'أشعة' in dept_name:
        return ServiceMaster.query.filter(
            ServiceMaster.category == 'radiology',
            ServiceMaster.is_active == True
        ).first()
    elif 'emergency' in dept_name or 'طوارئ' in dept_name or 'طواريء' in dept_name:
        return ServiceMaster.query.filter(
            ServiceMaster.category == 'emergency',
            ServiceMaster.is_active == True
        ).first()
    else:
        return ServiceMaster.query.filter(
            ServiceMaster.category == 'doctor',
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
        visit = Visit.query.get(visit_id)
        if not visit:
            return False
        
        # إضافة المريض للطابور
        result = queue_service.add_patient_to_queue(
            patient_id=visit.patient_id,
            department_id=department_id,
            doctor_id=doctor_id,
            visit_id=visit_id,
            priority='NORMAL',
            notes=f'زيارة {visit.visit_type}'
        )
        
        return result
    except Exception as e:
        logging.error(f"Error adding patient to queue: {str(e)}")
        return False

def get_payment_methods():
    """جلب طرق الدفع المتاحة"""
    return [
        {'value': 'cash', 'label': 'نقداً', 'fields': []},
        {'value': 'visa', 'label': 'فيزا', 'fields': ['card_number', 'card_holder', 'expiry_date']},
        {'value': 'insurance', 'label': 'تأمين', 'fields': ['insurance_provider', 'policy_number', 'coverage_percentage']},
        {'value': 'force', 'label': 'دفع قوي', 'fields': ['force_reason', 'approved_by']}
    ]

def validate_payment_data(payment_method, form_data):
    """التحقق من صحة بيانات الدفع"""
    required_fields = {
        'cash': [],
        'visa': ['card_number', 'card_holder', 'expiry_date'],
        'insurance': ['insurance_provider', 'policy_number'],
        'force': ['force_reason', 'approved_by']
    }
    
    if payment_method not in required_fields:
        return False, "طريقة دفع غير صحيحة"
    
    for field in required_fields[payment_method]:
        if not form_data.get(field):
            return False, f"الحقل {field} مطلوب"
    
    return True, "صحيح"




@reception_bp.route('/queue')
@login_required
def queue():
    """إدارة الطوابير"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('reception/queue_management.html')

@reception_bp.route('/payments')
@login_required
def payments():
    """المدفوعات"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('accountant/payments.html')

