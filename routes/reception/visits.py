"""visits routes - extracted from monolithic reception.py"""

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
from utils.decorators import can_create_visits, reception_only, role_required, role_required_json, can_modify_patient_data, can_delete_patient
from app_factory import db
import logging
from app.shared.enums import VisitState
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService
from routes.reception.queue import add_patient_to_queue_auto



# ═══════════════════════════════════════
# VISIT ROUTES
# ═══════════════════════════════════════

@reception_bp.route('/visits')
@login_required
@role_required('reception', 'super_admin', 'manager')
def visits():
    """قائمة الزيارات - الوحدة المركزية"""
    
    
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
    try:
        ok, msg = GatekeeperService.archive_visit(visit_id, current_user.id)
        if ok:
            flash('تمت أرشفة الزيارة بنجاح', 'success')
        else:
            flash(msg or 'لا يمكن أرشفة الزيارة', 'warning')
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
    if visit.status != VisitState.COMPLETED:
        flash('يجب إنهاء العلاج أولاً (حالة الزيارة مكتملة) قبل إنهاء الزيارة', 'warning')
        return redirect(url_for('reception.visits'))
    try:
        ok, msg = GatekeeperService.archive_visit(visit_id, current_user.id)
        if ok:
            flash('تم إنهاء الزيارة وأرشفتها بنجاح', 'success')
        else:
            flash(msg or 'لا يمكن إنهاء الزيارة', 'warning')
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

def _process_custom_services(custom_names, custom_prices, department_id, current_user):
    """إنشاء خدمات يدوية غير مدرجة وإرجاع قائمة معرفات الخدمات"""
    ids = []
    if not custom_names or not department_id:
        return ids
    from models.service import ServiceMaster
    dept_obj = db.session.get(Department, int(department_id))
    if not dept_obj:
        return ids
    dept_type = dept_obj.get_type()
    category = 'lab' if dept_type == 'lab' else ('radiology' if dept_type == 'radiology' else 'general')
    for cs_name, cs_price_raw in zip(custom_names, custom_prices):
        name = (cs_name or '').strip()
        if not name:
            continue
        try:
            price = float(cs_price_raw or 0)
        except ValueError:
            price = 0.0
        existing = ServiceMaster.query.filter(
            db.func.lower(ServiceMaster.name) == db.func.lower(name),
            ServiceMaster.department_id == int(department_id),
            ServiceMaster.is_active == True
        ).first()
        if existing:
            ids.append(str(existing.id))
        else:
            import uuid
            code = f"CUSTOM-{int(department_id)}-{uuid.uuid4().hex[:6].upper()}"
            svc = ServiceMaster(
                code=code, name=name, name_ar=name,
                description=f"خدمة يدوية مضافة من الاستقبال بواسطة {current_user.full_name or current_user.username}",
                category=category, department_id=int(department_id),
                base_price=price, emergency_price=price, insurance_price=price,
                currency='ILS', is_active=True
            )
            db.session.add(svc)
            db.session.flush()
            ids.append(str(svc.id))
    return ids


def _calculate_visit_tax(visit, tax_type):
    """تطبيق الضريبة على الزيارة حسب النوع (inclusive/exclusive)"""
    TAX_RATE = 0.15
    visit.tax_percent = 0
    visit.tax_amount = 0
    visit.is_tax_inclusive = False
    if tax_type == 'inclusive' and visit.total_amount:
        visit.is_tax_inclusive = True
        visit.tax_percent = TAX_RATE * 100
        base = float(visit.total_amount) / (1 + TAX_RATE)
        visit.tax_amount = round(float(visit.total_amount) - base, 2)
    elif tax_type == 'exclusive' and visit.total_amount:
        visit.is_tax_inclusive = False
        visit.tax_percent = TAX_RATE * 100
        tax_val = float(visit.total_amount) * TAX_RATE
        visit.tax_amount = round(tax_val, 2)
        visit.total_amount = round(float(visit.total_amount) + tax_val, 2)


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
            
            # ========== خدمات يدوية غير مدرجة ==========
            custom_services_ids = _process_custom_services(
                request.form.getlist('custom_service_name'),
                request.form.getlist('custom_service_price'),
                department_id, current_user
            )
            selected_tests = selected_tests + custom_services_ids
            
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
                except Exception as e:

                    logging.warning(f"Error in {__name__}: {e}")
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
                    except Exception as e:

                        logging.warning(f"Error in {__name__}: {e}")
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
                    db.session.flush()
                    from services.barcode_service import setup_barcode_for_lab_request
                    setup_barcode_for_lab_request(lab_req, current_user=current_user, tenant_id=getattr(current_user, 'tenant_id', None))
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
            _calculate_visit_tax(visit, tax_type)

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
                        visit.payment_status = PaymentStatus.PAID
                    else:
                        visit.payment_status = PaymentStatus.PARTIAL
                    
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
                    visit.payment_status = PaymentStatus.PARTIAL  # لأن التأمين لم يدفع بعد
                    
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
                visit.payment_status = PaymentStatus.PENDING
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
                from services.barcode_service import setup_barcode_for_lab_request
                setup_barcode_for_lab_request(lab_req, current_user=current_user, tenant_id=getattr(current_user, 'tenant_id', None))
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
            elif visit.payment_status == PaymentStatus.PAID:
                flash('تم إنشاء الزيارة ودفع المبلغ بنجاح.', 'success')
            elif visit.payment_status == PaymentStatus.PARTIAL:
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

@reception_bp.route('/view_visit/<int:visit_id>')
@login_required
@role_required('reception', 'super_admin', 'manager')
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
        dept = db.session.get(Department, department_id) if department_id else None
        
        # خدمات يدوية من الطلب
        custom_names = request.args.getlist('custom_service_name')
        custom_prices = request.args.getlist('custom_service_price')
        custom_total = 0.0
        custom_breakdown = []
        for cname, cprice in zip(custom_names, custom_prices):
            name = (cname or '').strip()
            if not name:
                continue
            try:
                price = float(cprice or 0)
            except ValueError:
                price = 0.0
            custom_total += price
            custom_breakdown.append({'item': f"(يدوي) {name}", 'cost': price})
        
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
            # إضافة الخدمات اليدوية
            total += custom_total
            breakdown.extend(custom_breakdown)
            
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
            # إضافة الخدمات اليدوية
            cost += custom_total
            if pricing_details:
                pricing_details['total'] = pricing_details.get('total', 0) + custom_total
                pricing_details['breakdown'].extend(custom_breakdown)
            
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
        department = db.session.get(Department, department_id) if department_id else None
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

def calculate_visit_cost(department_id, doctor_id, visit_type, is_emergency, payment_method='cash'):
    """حساب تكلفة الزيارة تلقائياً حسب إعدادات المدير"""
    try:
        from models.pricing import PricingCatalog
        from models.service import ServiceMaster
        from models.pricing_management import PricingRule
        total_cost = 0
        department = db.session.get(Department, department_id) if department_id else None
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


@reception_bp.route('/edit_visit/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def edit_visit(visit_id):
    if current_user.role not in ['reception', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))

    visit = db.session.get(Visit, visit_id)
    if not visit:
        flash('الزيارة غير موجودة', 'error')
        return redirect(url_for('reception.queue_management'))

    if request.method == 'POST':
        try:
            department_id = request.form.get('department_id')
            doctor_id = request.form.get('doctor_id')
            visit_type = request.form.get('visit_type', 'REGULAR')
            symptoms = request.form.get('symptoms', '')
            notes = request.form.get('notes', '')
            payment_method = request.form.get('payment_method', 'CASH')

            if department_id:
                visit.department_id = int(department_id)
            if doctor_id:
                visit.doctor_id = int(doctor_id)
            visit.visit_type = visit_type
            visit.symptoms = symptoms
            visit.notes = notes
            visit.payment_method = payment_method

            db.session.commit()
            flash('تم تعديل الزيارة بنجاح', 'success')
            return redirect(url_for('reception.view_visit', visit_id=visit.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editing visit: {str(e)}")
            flash('حدث خطأ أثناء تعديل الزيارة', 'error')
            return redirect(url_for('reception.edit_visit', visit_id=visit_id))

    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    doctors = User.query.filter(User.role.in_(['doctor', 'emergency']), User.is_active == True).order_by(User.full_name).all()
    return render_template('reception/edit_visit.html', visit=visit, departments=departments, doctors=doctors)

# Import submodules (must be at bottom after all helpers)
from . import patients
