"""payments routes - extracted from monolithic reception.py"""

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
from services.access_control_service import AccessControlService
from services.pos_terminal_service import PosTerminalService



# ═══════════════════════════════════════
# PAYMENT ROUTES
# ═══════════════════════════════════════

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

def payments():
    """المدفوعات"""
    if current_user.role not in ['reception', 'super_admin', 'manager']:
        flash('ليس لديك الصلاحيات للوصول إلى هذه الصفحة.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('accountant/payments.html')

@reception_bp.route('/survey/<token>', methods=['GET', 'POST'])
# ══════════════════════
# SECTION: SURVEY & CLOSE
# ══════════════════════



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
