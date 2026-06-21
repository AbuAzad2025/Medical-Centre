"""
مسارات الدفع - Payment Routes
Medical System Payment Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, abort
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.patient import Patient
from models.visit import Visit
from models.invoice import Invoice
from models.system_config import SystemConfig
from models.queue_management import QueueSettings
from services.gatekeeper_service import GatekeeperService
from app_factory import db
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

payment_bp = Blueprint('payment', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@payment_bp.before_request
def _guard_billing_module():
    guard_module('billing')

@payment_bp.route('/')
@login_required
def index():
    return redirect(url_for('payment.dashboard'))

@payment_bp.route('/dashboard')
@login_required
@role_required('accountant', 'manager', 'admin')
def dashboard():
    """لوحة تحكم الدفع"""
    
    
    try:
        # إحصائيات الدفع
        today = datetime.now().date()
        
        # المدفوعات اليوم
        payments_today = Payment.query.filter(
            db.func.date(Payment.created_at) == today
        ).count()
        
        # إجمال المدفوعات اليوم
        total_today = db.session.query(db.func.sum(Payment.amount)).filter(
            db.func.date(Payment.created_at) == today
        ).scalar() or 0
        
        # المدفوعات المعلقة
        pending_payments = Payment.query.filter(Payment.status == PaymentStatus.PENDING).count()
        
        # المدفوعات المرفوضة
        cancelled_payments = Payment.query.filter(Payment.status == PaymentStatus.CANCELLED).count()
        
        # طرق الدفع الأكثر استخداماً
        payment_methods = db.session.query(
            Payment.method,
            db.func.count(Payment.id).label('count')
        ).group_by(Payment.method).all()
        
        stats = {
            'payments_today': payments_today,
            'total_today': float(total_today),
            'pending_payments': pending_payments,
            'cancelled_payments': cancelled_payments,
            'payment_methods': payment_methods
        }
        
        return render_template('accountant/dashboard.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in payment dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@payment_bp.route('/process/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('accountant')
def process_payment(visit_id):
    """معالجة دفع"""
    
    
    visit = db.session.query(Visit).filter_by(id=visit_id).with_for_update().first()
    if not visit:
        abort(404)
    
    if request.method == 'POST':
        try:
            def _wants_json():
                accept = (request.headers.get('Accept') or '').lower()
                if request.is_json:
                    return True
                return ('application/json' in accept) and ('text/html' not in accept)
            method_input = (request.form.get('payment_method') or '').lower()
            normalized_method = 'cash'
            if method_input in {'bank_transfer', 'wire', 'check', 'other'}:
                method_value = PaymentMethod.WIRE
                normalized_method = 'wire'
            elif method_input in {'card', 'visa'}:
                method_value = PaymentMethod.CARD
                normalized_method = 'card'
            elif method_input == 'insurance':
                method_value = PaymentMethod.INSURANCE
                normalized_method = 'insurance'
            else:
                method_value = PaymentMethod.CASH

            card_last_digits = (request.form.get('card_last_digits') or '').strip()
            card_holder_name = (request.form.get('card_holder_name') or '').strip()
            insurance_provider = (request.form.get('insurance_provider') or '').strip()
            insurance_policy_number = (request.form.get('insurance_policy_number') or '').strip()
            payment_reference = (request.form.get('payment_reference') or '').strip()
            force_reason = (request.form.get('force_reason') or '').strip()
            insurance_coverage_raw = (request.form.get('insurance_coverage') or '').strip()
            insurance_company_id = (request.form.get('insurance_company_id') or '').strip()

            paid_amount_str = request.form.get('paid_amount') or request.form.get('amount') or '0'
            amount_value = Decimal(paid_amount_str)
            payment_currency = (request.form.get('payment_currency') or 'ILS').strip().upper()
            base_currency = 'ILS'  # العملة الأساسية للنظام
            converted_amount = amount_value
            if payment_currency != base_currency and amount_value > 0:
                from services.currency_service import CurrencyConverter
                rate = CurrencyConverter.get_rate(payment_currency, base_currency)
                if rate is not None:
                    converted_amount = Decimal(str(CurrencyConverter.convert(amount_value, payment_currency, base_currency)))
                else:
                    if _wants_json():
                        return jsonify({'success': False, 'message': f'سعر صرف {payment_currency}→{base_currency} غير متوفر'}), 400
                    flash(f'سعر صرف {payment_currency}→{base_currency} غير متوفر — يرجى إدخال السعر أولاً', 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))
            is_debt = (request.form.get('is_debt') == 'on')
            debt_reason = (request.form.get('debt_reason') or '').strip()
            accept_responsibility = (request.form.get('accept_responsibility') == 'on')
            return_to_reception = (request.form.get('return_to_reception') == 'on')
            is_force_payment = (request.form.get('is_force_payment') == 'on')

            valid_method, method_message = GatekeeperService.validate_payment_method(
                normalized_method,
                amount_value
            )
            if not valid_method:
                if _wants_json():
                    return jsonify({'success': False, 'message': method_message}), 400
                flash(method_message, 'error')
                return redirect(url_for('payment.process_payment', visit_id=visit_id))

            if normalized_method in {'card', 'visa'} and amount_value > 0:
                valid_card, card_message = GatekeeperService.validate_card_payment(card_last_digits, card_holder_name)
                if not valid_card:
                    if _wants_json():
                        return jsonify({'success': False, 'message': card_message}), 400
                    flash(card_message, 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))

            if normalized_method == 'insurance':
                coverage_value = insurance_coverage_raw or getattr(visit, 'insurance_coverage_percentage', None) or 0
                provider_value = insurance_provider or getattr(visit, 'insurance_provider', '')
                policy_value = insurance_policy_number or getattr(visit, 'insurance_policy_number', '')
                if insurance_company_id and insurance_company_id.isdigit():
                    try:
                        from models.insurance import InsuranceCompany
                        company = db.session.get(InsuranceCompany, int(insurance_company_id))
                        if company:
                            provider_value = company.name_ar or company.name or provider_value
                    except Exception as e:

                        logging.warning(f"Error in {__name__}: {e}")
                valid_ins, ins_message = GatekeeperService.validate_insurance(
                    provider_value,
                    policy_value,
                    coverage_value
                )
                if not valid_ins:
                    if _wants_json():
                        return jsonify({'success': False, 'message': ins_message}), 400
                    flash(ins_message, 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))

            if is_force_payment:
                valid_force, force_message = GatekeeperService.validate_force_payment(visit_id, current_user.id, force_reason)
                if not valid_force:
                    if _wants_json():
                        return jsonify({'success': False, 'message': force_message}), 400
                    flash(force_message, 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))

            sc_partial = SystemConfig.query.filter_by(config_key='allow_partial_payment_global').first()
            sc_debt = SystemConfig.query.filter_by(config_key='allow_debt_global').first()
            allow_partial_global = sc_partial.get_value() if sc_partial else True
            allow_debt_global = sc_debt.get_value() if sc_debt else False

            qs = None
            if visit.department_id:
                qs = QueueSettings.query.filter_by(department_id=visit.department_id).first()
            allow_partial_dept = (qs.allow_partial_payment if qs is not None else True)
            allow_debt_dept = (qs.allow_debt if qs is not None else False)

            allow_partial = bool(allow_partial_global) and bool(allow_partial_dept)
            allow_debt = bool(allow_debt_global) and bool(allow_debt_dept)

            remaining = visit.remaining_amount
            if amount_value > 0 and remaining <= 0:
                if _wants_json():
                    return jsonify({'success': False, 'message': 'الزيارة مدفوعة بالكامل'}), 400
                flash('الزيارة مدفوعة بالكامل', 'error')
                return redirect(url_for('payment.process_payment', visit_id=visit_id))
            if amount_value > remaining and remaining > 0:
                if _wants_json():
                    return jsonify({'success': False, 'message': 'المبلغ المدفوع يتجاوز المستحق'}), 400
                flash('المبلغ المدفوع يتجاوز المستحق', 'error')
                return redirect(url_for('payment.process_payment', visit_id=visit_id))

            if is_debt and visit.remaining_amount > 0:
                if not accept_responsibility:
                    if _wants_json():
                        return jsonify({'success': False, 'message': 'يتطلب تحمل المسؤولية من الاستقبال'}), 400
                    flash('يتطلب تحمل المسؤولية من الاستقبال', 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))
                visit.payment_method = method_value or visit.payment_method
                visit.payment_status = PaymentStatus.DEBT
                if debt_reason:
                    try:
                        note_prefix = f"DEBT[{current_user.id}] {debt_reason}"
                        visit.notes = f"{visit.notes or ''}\n{note_prefix}".strip()
                    except Exception as e:

                        logging.warning(f"Error in {__name__}: {e}")
                db.session.commit()
                if _wants_json():
                    return jsonify({'success': True})
                flash('تم تسجيل الدين وفق الشروط', 'info')
                if return_to_reception:
                    return redirect(url_for('reception.view_visit', visit_id=visit_id))
                return redirect(url_for('reception.print_receipt', visit_id=visit_id))

            if amount_value < visit.remaining_amount and visit.remaining_amount > 0 and not allow_partial:
                if _wants_json():
                    return jsonify({'success': False, 'message': 'الدفع الجزئي غير مسموح'}), 400
                flash('الدفع الجزئي غير مسموح', 'error')
                return redirect(url_for('payment.process_payment', visit_id=visit_id))

            if amount_value <= 0 and visit.remaining_amount > 0:
                if not allow_debt:
                    if _wants_json():
                        return jsonify({'success': False, 'message': 'الدين غير مسموح'}), 400
                    flash('الدين غير مسموح', 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))
                visit.payment_method = method_value or visit.payment_method
                visit.payment_status = PaymentStatus.DEBT
                db.session.commit()
                if _wants_json():
                    return jsonify({'success': True})
                flash('تم تسجيل الدين بنجاح', 'info')
                if return_to_reception:
                    return redirect(url_for('reception.view_visit', visit_id=visit_id))
                return redirect(url_for('reception.print_receipt', visit_id=visit_id))

            payment = Payment(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                amount=amount_value,
                currency=payment_currency,
                method=method_value,
                status=PaymentStatus.CONFIRMED,
                notes=request.form.get('payment_notes') or request.form.get('notes'),
                payment_date=datetime.now(timezone.utc),
                received_by=current_user.id,
            )
            if payment_reference:
                payment.reference = payment_reference
            elif method_value == PaymentMethod.CARD and card_last_digits:
                payment.reference = f"CARD-****{card_last_digits}"
            existing_invoice = Invoice.query.filter_by(visit_id=visit.id).order_by(Invoice.created_at.desc()).first()
            if existing_invoice:
                payment.invoice_id = existing_invoice.id
            db.session.add(payment)

            visit.paid_amount = Decimal(str(visit.paid_amount or 0)) + converted_amount
            visit.payment_method = method_value or visit.payment_method
            if method_value == PaymentMethod.CARD:
                if card_last_digits:
                    visit.card_number_last_digits = card_last_digits
                if card_holder_name:
                    visit.card_holder_name = card_holder_name
            if method_value == PaymentMethod.INSURANCE:
                if insurance_provider:
                    visit.insurance_provider = insurance_provider
                if insurance_policy_number:
                    visit.insurance_policy_number = insurance_policy_number
                if insurance_coverage_raw:
                    try:
                        visit.insurance_coverage_percentage = Decimal(insurance_coverage_raw)
                    except Exception as e:

                        logging.warning(f"Error in {__name__}: {e}")
                if insurance_company_id and insurance_company_id.isdigit():
                    try:
                        from models.insurance import InsuranceCompany
                        company = db.session.get(InsuranceCompany, int(insurance_company_id))
                        if company:
                            visit.insurance_company_id = company.id
                            if not visit.insurance_provider:
                                visit.insurance_provider = company.name_ar or company.name
                    except Exception as e:

                        logging.warning(f"Error in {__name__}: {e}")
                # حساب مبالغ التأمين وحصة المريض
                visit.calculate_insurance_amounts()
                # عند الدفع بالتأمين يجب أن يكون المبلغ مساوياً لحصة المريض
                if visit.patient_share and converted_amount > visit.patient_share:
                    msg = f"المبلغ المدخل ({converted_amount} {base_currency}) يتجاوز حصة المريض ({visit.patient_share} {base_currency})"
                    if _wants_json():
                        return jsonify({'success': False, 'message': msg}), 400
                    flash(msg, 'error')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))
            if is_force_payment:
                visit.is_force_payment = True
                if force_reason:
                    visit.force_payment_reason = force_reason
                visit.force_payment_approved_by = current_user.id
                visit.force_payment_approved_at = datetime.now(timezone.utc)
            if visit.remaining_amount <= 0:
                visit.payment_status = PaymentStatus.PAID
            elif converted_amount > 0:
                visit.payment_status = PaymentStatus.PARTIAL
            else:
                visit.payment_status = visit.payment_status or 'PENDING'

            # توليد رقم إيصال بسيط للزيارة عند الدفع
            try:
                if not visit.receipt_number:
                    visit.receipt_number = f"RCPT-{visit.id}-{int(datetime.now(timezone.utc).timestamp())}"
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
            db.session.commit()

            resp = {'success': True, 'payment_id': payment.id}
            if _wants_json():
                return jsonify(resp)
            flash('تم تسجيل الدفع بنجاح', 'success')
            if return_to_reception:
                return redirect(url_for('reception.view_visit', visit_id=visit_id))
            return redirect(url_for('reception.print_receipt', visit_id=visit_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error processing payment: {str(e)}")
            err = {'success': False, 'message': 'حدث خطأ في معالجة الدفع'}
            if _wants_json():
                return jsonify(err), 500
            flash('حدث خطأ في معالجة الدفع', 'error')
            return redirect(url_for('payment.process_payment', visit_id=visit_id))
    
    insurance_companies = []
    try:
        from models.insurance import InsuranceCompany
        insurance_companies = InsuranceCompany.query.filter_by(is_active=True).order_by(InsuranceCompany.name.asc()).all()
    except Exception:
        insurance_companies = []
    from models.exchange_rate import CurrencySettings
    return render_template('accountant/process_payment.html',
                           visit=visit,
                           insurance_companies=insurance_companies,
                           currencies=CurrencySettings.get_all(),
                           base_currency='ILS')

@payment_bp.route('/history')
@login_required
@role_required('accountant')
def payment_history():
    """تاريخ المدفوعات"""
    
    
    try:
        # فلترة المدفوعات
        status = request.args.get('status', '')
        payment_method = request.args.get('payment_method', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        query = Payment.query
        
        if status:
            query = query.filter(Payment.status == status.upper())
        
        if payment_method:
            pm = payment_method.upper()
            query = query.filter(Payment.method == pm)
        
        if date_from:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Payment.created_at) >= df)
        
        if date_to:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(db.func.date(Payment.created_at) <= dt)
        
        payments = query.order_by(Payment.created_at.desc()).all()
        
        return render_template('accountant/payment_management.html', 
                             payments=payments,
                             status=status,
                             payment_method=payment_method,
                             date_from=date_from,
                             date_to=date_to)
    except Exception as e:
        logging.error(f"Error loading payment history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ المدفوعات', 'error')
        return redirect(url_for('payment.dashboard'))

@payment_bp.route('/methods')
@login_required
@role_required('admin', 'manager')
def payment_methods():
    """طرق الدفع"""
    
    
    try:
        methods = [PaymentMethod.CASH, PaymentMethod.CARD, PaymentMethod.INSURANCE, PaymentMethod.WIRE, PaymentMethod.FORCE]
        return render_template('payment/methods.html', methods=methods)
    except Exception as e:
        logging.error(f"Error loading payment methods: {str(e)}")
        flash('حدث خطأ في تحميل طرق الدفع', 'error')
        return redirect(url_for('payment.dashboard'))

@payment_bp.route('/reports')
@login_required
@role_required('accountant', 'admin', 'manager')
def payment_reports():
    """تقارير الدفع"""
    
    
    try:
        # تقرير المدفوعات اليومية
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        
        daily_payments = db.session.query(
            db.func.date(Payment.created_at).label('date'),
            db.func.count(Payment.id).label('count'),
            db.func.sum(Payment.amount).label('total')
        ).filter(
            Payment.created_at >= datetime.combine(week_ago, datetime.min.time())
        ).group_by(db.func.date(Payment.created_at)).all()
        
        # تقرير طرق الدفع
        method_stats = db.session.query(
            Payment.method,
            db.func.count(Payment.id).label('count'),
            db.func.sum(Payment.amount).label('total')
        ).filter(
            Payment.created_at >= datetime.combine(week_ago, datetime.min.time())
        ).group_by(Payment.method).all()
        
        return render_template('accountant/financial_reports.html', 
                             daily_payments=daily_payments,
                             method_stats=method_stats)
    except Exception as e:
        logging.error(f"Error loading payment reports: {str(e)}")
        flash('حدث خطأ في تحميل تقارير الدفع', 'error')
        return redirect(url_for('payment.dashboard'))