"""financial routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from services.manager_service import manager_service
from app_factory import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# FINANCIAL ROUTES
# =============================================

@manager_bp.route('/settlements')
@login_required
@role_required('manager', 'admin', 'super_admin', 'accountant')
def settlements():
    """تسويات شهرية/فترية حسب القسم أو الطبيب"""
    try:
        # مصادر الفلاتر
        doctors = User.query.filter_by(role='doctor', is_active=True).order_by(User.full_name.asc()).all()
        departments = Department.query.filter_by(is_active=True).order_by(Department.name.asc()).all()

        mode = (request.args.get('mode') or 'doctor').lower()  # doctor | department
        doctor_id = request.args.get('doctor_id', type=int)
        department_id = request.args.get('department_id', type=int)
        month = request.args.get('month')  # yyyy-mm
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # تحديد المدى الزمني
        today = date.today()
        if month:
            try:
                y, m = map(int, month.split('-'))
                period_start = date(y, m, 1)
            except Exception:
                period_start = date(today.year, today.month, 1)
        else:
            period_start = date(today.year, today.month, 1)
        if end_date:
            try:
                period_end = datetime.strptime(end_date, '%Y-%m-%d').date()
            except Exception:
                period_end = date(period_start.year, period_start.month, 28)
        else:
            # نهاية الشهر
            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_end = next_month - timedelta(days=1)

        # استعلام الزيارات ضمن الفترة
        q = Visit.query.filter(
            Visit.visit_date >= period_start,
            Visit.visit_date <= period_end,
            Visit.status == 'COMPLETED'
        )
        target_name = None
        if mode == 'doctor' and doctor_id:
            q = q.filter(Visit.doctor_id == doctor_id)
            d = db.session.get(User, doctor_id)
            target_name = d.full_name if d else None
        elif mode == 'department' and department_id:
            q = q.filter(Visit.department_id == department_id)
            dep = db.session.get(Department, department_id)
            target_name = dep.name_ar or dep.name if dep else None

        visits = q.order_by(Visit.visit_date.asc()).all()

        # حساب التسوية
        def compute_doctor_fee(v: Visit) -> Decimal:
            total = Decimal(str(v.total_amount or 0))
            fee = None
            try:
                from models.pricing import DoctorPricing
                pricing = DoctorPricing.query.filter(
                    DoctorPricing.doctor_id == v.doctor_id,
                    DoctorPricing.department_id == v.department_id,
                    DoctorPricing.is_active == True
                ).order_by(DoctorPricing.effective_from.desc()).first()
            except Exception:
                pricing = None
            vt = (v.visit_type or '').upper()
            if pricing:
                if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                    fee = Decimal(str(pricing.consultation_price))
                elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                    fee = Decimal(str(pricing.follow_up_price))
                elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                    fee = Decimal(str(pricing.emergency_price))
            if fee is None:
                fee = total * Decimal('0.30')
            if fee > total:
                fee = total
            return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        items = []
        for v in visits:
            tot = Decimal(str(v.total_amount or 0))
            paid = Decimal(str(v.paid_amount or 0))
            fee = compute_doctor_fee(v)
            center = (tot - fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            items.append({
                'visit': v,
                'total': float(tot),
                'paid': float(paid),
                'remaining': float((tot - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
                'doctor_fee': float(fee),
                'center_share': float(center)
            })
        total_amount = sum(Decimal(str(i['total'])) for i in items) if items else Decimal('0.00')
        paid_amount = sum(Decimal(str(i['paid'])) for i in items) if items else Decimal('0.00')
        doctor_fee_total = sum(Decimal(str(i['doctor_fee'])) for i in items) if items else Decimal('0.00')
        service_share_total = (total_amount - doctor_fee_total).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        remaining_amount = (total_amount - paid_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        stats = {
            'period_start': period_start,
            'period_end': period_end,
            'mode': mode,
            'target_name': target_name,
            'count': len(visits),
            'total_amount': float(total_amount),
            'paid_amount': float(paid_amount),
            'remaining_amount': float(remaining_amount),
            'doctor_fee_total': float(doctor_fee_total),
            'service_share_total': float(service_share_total)
        }

        return render_template(
            'manager/settlements.html',
            doctors=doctors,
            departments=departments,
            stats=stats,
            visits=visits,
            items=items,
            selected_doctor_id=doctor_id,
            selected_department_id=department_id,
            selected_month=month
        )
    except Exception as e:
        logging.error(f"Error in settlements: {str(e)}")
        flash('حدث خطأ في تحميل التسويات', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/settlements/export')
@login_required
@role_required('manager', 'admin', 'super_admin', 'accountant')
def settlements_export():
    """تصدير التسوية CSV طبقاً للفلاتر"""
    try:
        # إعادة استخدام نفس منطق الفلاتر
        mode = (request.args.get('mode') or 'doctor').lower()
        doctor_id = request.args.get('doctor_id', type=int)
        department_id = request.args.get('department_id', type=int)
        month = request.args.get('month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        today = date.today()
        if month:
            try:
                y, m = map(int, month.split('-'))
                period_start = date(y, m, 1)
            except Exception:
                period_start = date(today.year, today.month, 1)
        else:
            period_start = date(today.year, today.month, 1)
        if end_date:
            try:
                period_end = datetime.strptime(end_date, '%Y-%m-%d').date()
            except Exception:
                period_end = date(period_start.year, period_start.month, 28)
        else:
            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            period_end = next_month - timedelta(days=1)

        q = Visit.query.filter(Visit.visit_date >= period_start, Visit.visit_date <= period_end, Visit.status == 'COMPLETED')
        if mode == 'doctor' and doctor_id:
            q = q.filter(Visit.doctor_id == doctor_id)
        elif mode == 'department' and department_id:
            q = q.filter(Visit.department_id == department_id)
        visits = q.order_by(Visit.visit_date.asc()).all()

        def compute_doctor_fee(v: Visit) -> Decimal:
            total = Decimal(str(v.total_amount or 0))
            fee = None
            try:
                from models.pricing import DoctorPricing
                pricing = DoctorPricing.query.filter(DoctorPricing.doctor_id == v.doctor_id, DoctorPricing.department_id == v.department_id, DoctorPricing.is_active == True).order_by(DoctorPricing.effective_from.desc()).first()
            except Exception:
                pricing = None
            vt = (v.visit_type or '').upper()
            if pricing:
                if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                    fee = Decimal(str(pricing.consultation_price))
                elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                    fee = Decimal(str(pricing.follow_up_price))
                elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                    fee = Decimal(str(pricing.emergency_price))
            if fee is None:
                fee = total * Decimal('0.30')
            if fee > total:
                fee = total
            return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        import io
        output = io.StringIO()
        output.write('رقم الزيارة,التاريخ,القسم,الطبيب,المريض,الإجمالي,المدفوع,المتبقي,حصة الطبيب,حصة المركز\n')
        for v in visits:
            total = Decimal(str(v.total_amount or 0))
            paid = Decimal(str(v.paid_amount or 0))
            remaining = (total - paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            fee = compute_doctor_fee(v)
            center = (total - fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            output.write(','.join([
                str(v.id),
                (v.visit_date.strftime('%Y-%m-%d') if v.visit_date else ''),
                (v.department.name_ar if v.department else ''),
                (v.doctor.full_name if v.doctor else ''),
                (v.patient.full_name if v.patient else ''),
                f"{float(total):.2f}",
                f"{float(paid):.2f}",
                f"{float(remaining):.2f}",
                f"{float(fee):.2f}",
                f"{float(center):.2f}"
            ]) + '\n')
        from flask import Response
        filename = f"settlements_{mode}_{(doctor_id or department_id or 'all')}_{period_start}_{period_end}.csv"
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})
    except Exception as e:
        logging.error(f"Error exporting settlements: {str(e)}")
        flash('حدث خطأ في تصدير التسويات', 'error')
        return redirect(url_for('manager.dashboard'))
    
    try:
        # جلب المستخدمين (باستثناء السوبر أدمن)
        users = User.query.filter(User.role != 'super_admin').all()
        
        return render_template('manager/user_management.html', users=users)
    except Exception as e:
        logging.error(f"Error in user management: {str(e)}")
        flash('حدث خطأ في تحميل إدارة المستخدمين', 'error')
        return redirect(url_for('manager.dashboard'))

@manager_bp.route('/financial-reports')
@login_required
def financial_reports():
    """التقارير المالية"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('manager/reports.html')

@manager_bp.route('/budget', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def budget_dashboard():
    """إدارة الميزانية - Budget vs Actual"""
    from models.budget import Budget
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    if request.method == 'POST':
        dept_id = request.form.get('department_id')
        dept_id = int(dept_id) if dept_id else None
        b = Budget.get_or_create(year, month, dept_id, current_user.id)
        b.revenue_target = Decimal(request.form.get('revenue_target', 0))
        b.visits_target = int(request.form.get('visits_target', 0))
        b.new_patients_target = int(request.form.get('new_patients_target', 0))
        b.expenses_target = Decimal(request.form.get('expenses_target', 0))
        b.notes = request.form.get('notes', '')
        db.session.commit()
        flash('تم حفظ الميزانية', 'success')
        return redirect(url_for('manager.budget_dashboard', year=year, month=month))

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)

    actual_revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.payment_date >= start, Payment.payment_date < end,
        Payment.status.in_(['COMPLETED', 'PAID'])
    ).scalar() or 0

    actual_visits = Visit.query.filter(Visit.visit_date >= start, Visit.visit_date < end).count()
    actual_new_patients = Patient.query.filter(Patient.created_at >= start, Patient.created_at < end).count()

    budgets = Budget.query.filter_by(year=year, month=month).all()
    dept_budgets = {b.department_id: b for b in budgets}

    return render_template('manager/budget.html',
                           year=year, month=month,
                           actual_revenue=float(actual_revenue),
                           actual_visits=actual_visits,
                           actual_new_patients=actual_new_patients,
                           dept_budgets=dept_budgets,
                           departments=Department.query.all())


@manager_bp.route('/monthly-comparison')
@login_required
@role_required('manager', 'admin', 'super_admin')
def monthly_comparison():
    """مقارنة شهرية - MoM / YoY"""
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1)
        else:
            end = date(y, m + 1, 1)

        rev = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= start, Payment.payment_date < end
        ).scalar() or 0
        vis = Visit.query.filter(Visit.visit_date >= start, Visit.visit_date < end).count()
        newp = Patient.query.filter(Patient.created_at >= start, Patient.created_at < end).count()

        months.append({'label': f"{y}-{m:02d}", 'revenue': float(rev), 'visits': vis, 'new_patients': newp})

    for i in range(1, len(months)):
        prev = months[i - 1]
        curr = months[i]
        curr['revenue_growth'] = round(((curr['revenue'] - prev['revenue']) / (prev['revenue'] or 1)) * 100, 1)
        curr['visits_growth'] = round(((curr['visits'] - prev['visits']) / (prev['visits'] or 1)) * 100, 1)

    return render_template('manager/monthly_comparison.html', months=months)

@manager_bp.route('/exchange-rates', methods=['GET', 'POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def exchange_rates():
    """إدارة أسعار الصرف"""
    from models.exchange_rate import ExchangeRate, CurrencySettings
    from services.currency_service import CurrencyConverter
    from decimal import Decimal

    if request.method == 'POST':
        try:
            from_currency = request.form.get('from_currency', '').strip().upper()
            to_currency = request.form.get('to_currency', '').strip().upper()
            sell_rate = request.form.get('sell_rate', '').strip()
            buy_rate = request.form.get('buy_rate', '').strip() or sell_rate
            notes = request.form.get('notes', '').strip()

            if not from_currency or not to_currency or not sell_rate:
                flash('جميع الحقول المطلوبة يجب تعبئتها', 'error')
                return redirect(url_for('manager.exchange_rates'))

            CurrencyConverter.ensure_manual_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                sell_rate=Decimal(sell_rate),
                buy_rate=Decimal(buy_rate) if buy_rate else None,
                user_id=current_user.id,
            )
            flash(f'تم تحديث سعر الصرف {from_currency} → {to_currency}', 'success')
        except Exception as e:
            logging.error(f"Error saving exchange rate: {e}")
            flash('حدث خطأ أثناء حفظ سعر الصرف', 'error')
        return redirect(url_for('manager.exchange_rates'))

    active_rates = CurrencyConverter.get_all_active_rates()
    missing_pairs = CurrencyConverter.get_missing_pairs()
    currencies = CurrencySettings.get_all()
    return render_template('manager/exchange_rates.html',
                           rates=active_rates,
                           missing_pairs=missing_pairs,
                           currencies=currencies)


@manager_bp.route('/exchange-rates/fetch-api', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def fetch_api_exchange_rates():
    """جلب أسعار الصرف من API خارجي"""
    from models.exchange_rate import CurrencySettings
    from services.currency_service import CurrencyConverter
    base = request.form.get('base_currency', 'ILS').upper()
    imported = 0
    failed = 0
    for code in CurrencySettings.SUPPORTED_CURRENCIES:
        if code == base:
            continue
        try:
            rate = CurrencyConverter.fetch_external_rate(base, code)
            if rate:
                imported += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    flash(f'تم جلب {imported} سعر صرف | فشل {failed}', 'info' if failed == 0 else 'warning')
    return redirect(url_for('manager.exchange_rates'))


@manager_bp.route('/exchange-rates/deactivate/<int:rate_id>', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def deactivate_exchange_rate(rate_id):
    """تعطيل سعر صرف"""
    from models.exchange_rate import ExchangeRate
    rate = ExchangeRate.query.get_or_404(rate_id)
    rate.is_active = False
    db.session.commit()
    flash(f'تم تعطيل سعر {rate.from_currency} → {rate.to_currency}', 'success')
    return redirect(url_for('manager.exchange_rates'))
