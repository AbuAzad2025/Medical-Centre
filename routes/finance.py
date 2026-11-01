import logging
from datetime import date

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import InvoiceStatus, PaymentStatus
from models.audit_trail import AuditTrail
from models.invoice import Invoice
from models.payment import Payment
from models.visit import Visit
from services.gatekeeper_service import GatekeeperService
from services.report_service import ReportService
from utils.decorators import role_required, role_required_json
from utils.tenant_query import TenantContextError, get_tenant_record

finance_bp = Blueprint('finance', __name__)


@finance_bp.route('/')
@login_required
def index():
    return redirect(url_for('finance.dashboard'))


@finance_bp.route('/dashboard')
@login_required
@role_required('accountant', 'admin', 'manager')
def dashboard():
    """لوحة تحكم المالية"""
    try:
        today = date.today()

        # إحصائيات مالية
        total_revenue = (
            db.session.execute(
                select(db.func.sum(Payment.amount)).filter(~Payment.is_provisional)
            ).scalar()
            or 0
        )

        pending_payments = db.session.execute(
            select(func.count()).select_from(Payment).filter(Payment.is_provisional)
        ).scalar()

        locked_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(~Visit.receipt_printed, Visit.payment_status != PaymentStatus.PAID)
        ).scalar()

        today_invoices = db.session.execute(
            select(func.count())
            .select_from(Invoice)
            .filter(db.func.date(Invoice.created_at) == today)
        ).scalar()

        today_payments = db.session.execute(
            select(func.count())
            .select_from(Payment)
            .filter(~Payment.is_provisional, db.func.date(Payment.created_at) == today)
        ).scalar()

        pending_invoices = db.session.execute(
            select(func.count())
            .select_from(Invoice)
            .filter(
                Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.POSTED]),
                Invoice.paid_amount < Invoice.total_amount,
            )
        ).scalar()

        refunded_count = db.session.execute(
            select(func.count())
            .select_from(Payment)
            .filter(Payment.status == PaymentStatus.REFUNDED)
        ).scalar()

        recent_invoices = (
            db.session.execute(select(Invoice).order_by(Invoice.created_at.desc()).limit(10))
            .scalars()
            .all()
        )

        stats = {
            'total_revenue': total_revenue,
            'pending_payments': pending_payments,
            'locked_visits': locked_visits,
        }

        return render_template(
            'billing/dashboard_new.html',
            stats=stats,
            today_invoices=today_invoices,
            today_payments=today_payments,
            pending_invoices=pending_invoices,
            refunded_count=refunded_count,
            recent_invoices=recent_invoices,
        )

    except Exception:
        logging.exception('Error loading finance dashboard: %s')
        flash('حدث خطأ في تحميل لوحة التحكم المالية', 'error')
        return redirect(url_for('main.dashboard'))


@finance_bp.route('/post', methods=['POST'])
@login_required
@role_required_json('accountant', 'admin', 'manager')
def post_gl():
    """الترحيل المالي - Finance فقط"""

    try:
        data = request.get_json()
        visit_id = data.get('visit_id')

        if not visit_id:
            return jsonify({'error': 'معرف الزيارة مطلوب'}), 400

        # MC-004: validate visit ownership before delegating to service
        try:
            get_tenant_record(Visit, visit_id)
        except TenantContextError:
            return jsonify({'error': 'الزيارة غير موجودة'}), 404

        # استخدام حراسة الخدمة
        success, message = GatekeeperService.post_gl(visit_id, current_user.id)

        if success:
            return jsonify({'success': True, 'message': message})
        return jsonify({'error': message}), 422

    except Exception:
        logging.exception('Error posting GL: %s')
        return jsonify({'error': 'تعذر تنفيذ الترحيل المالي حالياً'}), 500


@finance_bp.route('/visits/<int:visit_id>/archive', methods=['POST'])
@login_required
@role_required_json('admin', 'manager')
def archive_visit(visit_id):
    """أرشفة الزيارة - Finance route disabled for admin/manager.

    Ticket 1: Reception alone controls the administrative archive decision.
    Accountant/admin/manager may process payment/GL but must not archive visits.
    Use routes/reception/visits.py for reception-initiated archive.
    """
    return jsonify({'error': 'Archive is handled by reception only.'}), 403


# تم نقل مسار الزيارات إلى routes/reception.py لتجنب التكرار
# يمكن الوصول إليه عبر /reception/visits


@finance_bp.route('/payments')
@login_required
@role_required('accountant', 'admin', 'manager')
def payments():
    """عرض المدفوعات"""

    try:
        per_page = request.args.get('per_page', type=int) or 50
        per_page = max(10, min(per_page, 200))
        page = request.args.get('page', type=int) or 1
        page = max(1, page)
        payments = (
            db.session.execute(
                select(Payment)
                .filter_by(tenant_id=g.tenant_id)
                .order_by(Payment.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            .scalars()
            .all()
        )
        return render_template('finance/payments.html', payments=payments)

    except Exception:
        logging.exception('Error loading payments: %s')
        flash('حدث خطأ في تحميل المدفوعات', 'error')
        return redirect(url_for('finance.dashboard'))


@finance_bp.route('/invoices')
@login_required
@role_required('accountant', 'admin', 'manager')
def invoices():
    """عرض الفواتير"""

    try:
        per_page = request.args.get('per_page', type=int) or 50
        per_page = max(10, min(per_page, 200))
        page = request.args.get('page', type=int) or 1
        page = max(1, page)
        invoices = (
            db.session.execute(
                select(Invoice)
                .filter_by(tenant_id=g.tenant_id)
                .order_by(Invoice.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            .scalars()
            .all()
        )
        return render_template('finance/invoices.html', invoices=invoices)

    except Exception:
        logging.exception('Error loading invoices: %s')
        flash('حدث خطأ في تحميل الفواتير', 'error')
        return redirect(url_for('finance.dashboard'))


@finance_bp.route('/audit')
@login_required
@role_required('accountant', 'admin', 'manager')
def audit():
    """عرض التدقيق المالي"""

    try:
        per_page = request.args.get('per_page', type=int) or 100
        per_page = max(20, min(per_page, 500))
        page = request.args.get('page', type=int) or 1
        page = max(1, page)
        audit_entries = (
            db.session.execute(
                select(AuditTrail)
                .filter(
                    AuditTrail.entity_type.in_(['visit', 'payment', 'invoice']),
                    AuditTrail.tenant_id == g.tenant_id,
                )
                .order_by(AuditTrail.created_at.desc())
                .limit(per_page)
                .offset((page - 1) * per_page)
            )
            .scalars()
            .all()
        )

        return render_template('finance/audit.html', audit_entries=audit_entries)

    except Exception:
        logging.exception('Error loading audit: %s')
        flash('حدث خطأ في تحميل التدقيق', 'error')
        return redirect(url_for('finance.dashboard'))


@finance_bp.route('/slow-queries')
@login_required
@role_required('accountant', 'admin', 'manager')
def slow_queries():
    try:
        limit = request.args.get('limit', type=int) or 10
        limit = max(5, min(limit, 50))
        report = ReportService.get_slow_queries_report(limit=limit)
        return render_template('finance/slow_queries.html', report=report, limit=limit)
    except Exception:
        logging.exception('Error loading slow queries report: %s')
        flash('حدث خطأ في تحميل تقرير الاستعلامات البطيئة', 'error')
        return redirect(url_for('finance.dashboard'))


@finance_bp.route('/slow-queries/weekly')
@login_required
@role_required('accountant', 'admin', 'manager')
def slow_queries_weekly():
    try:
        from models.audit_trail import SlowQueryReport

        reports = (
            db.session.execute(
                select(SlowQueryReport).order_by(SlowQueryReport.created_at.desc()).limit(50)
            )
            .scalars()
            .all()
        )
        return render_template('finance/slow_queries_weekly.html', reports=reports)
    except Exception:
        logging.exception('Error loading weekly slow queries: %s')
        flash('حدث خطأ في تحميل التقرير الأسبوعي', 'error')
        return redirect(url_for('finance.dashboard'))


@finance_bp.route('/slow-queries/weekly/<int:report_id>')
@login_required
@role_required('accountant', 'admin', 'manager')
def slow_queries_weekly_detail(report_id):
    try:
        from models.audit_trail import SlowQueryReport

        try:
            report = get_tenant_record(SlowQueryReport, report_id)
        except TenantContextError:
            flash('التقرير غير موجود', 'error')
            return redirect(url_for('finance.slow_queries_weekly'))
        return render_template('finance/slow_queries_weekly_detail.html', report=report)
    except Exception:
        logging.exception('Error loading weekly slow queries detail: %s')
        flash('حدث خطأ في تحميل تفاصيل التقرير', 'error')
        return redirect(url_for('finance.slow_queries_weekly'))


@finance_bp.route('/slow-queries/capture', methods=['POST'])
@login_required
@role_required('accountant', 'admin', 'manager')
def capture_slow_queries_weekly():
    try:
        limit = request.form.get('limit', type=int) or 10
        limit = max(5, min(limit, 50))
        result = ReportService.capture_weekly_slow_queries(limit=limit, created_by=current_user.id)
        if not result.get('success'):
            flash(result.get('message') or 'تعذر إنشاء التقرير الأسبوعي', 'error')
            return redirect(url_for('finance.slow_queries'))
        flash('تم حفظ التقرير الأسبوعي بنجاح', 'success')
        return redirect(
            url_for('finance.slow_queries_weekly_detail', report_id=result.get('report_id'))
        )
    except Exception:
        logging.exception('Error capturing weekly slow queries: %s')
        flash('حدث خطأ في إنشاء التقرير الأسبوعي', 'error')
        return redirect(url_for('finance.slow_queries'))


# --- Enhanced billing features ---


def _finance_enhancements_loaded():
    return True


from datetime import UTC, datetime

from flask import Response
from flask_login import login_required

from models.insurance import InsuranceClaim
from routes.finance import finance_bp
from utils.decorators import role_required

_PAYMENT_PLANS: dict[int, dict] = {}
_PAYMENT_PLAN_COUNTER = 0


def _next_payment_plan_id() -> int:
    global _PAYMENT_PLAN_COUNTER
    _PAYMENT_PLAN_COUNTER += 1
    return _PAYMENT_PLAN_COUNTER


@finance_bp.route('/invoices/<int:invoice_id>/pdf', methods=['GET'])
@finance_bp.route('/invoice/<int:invoice_id>/pdf', methods=['GET'])
@finance_bp.route('/invoices/<int:invoice_id>/download', methods=['GET'])
@login_required
@role_required('accountant', 'admin', 'manager')
def invoice_pdf(invoice_id: int):
    try:
        invoice = get_tenant_record(Invoice, invoice_id)
    except TenantContextError:
        return jsonify({'success': False, 'error': 'Invoice not found'}), 404
    try:
        from app.integrations.printing.pdf import PDFReportPrinter

        printer = PDFReportPrinter()
        lines = []
        for svc in getattr(invoice, 'lines', None) or []:
            lines.append(
                f'{getattr(svc, "service_name", "")} x{getattr(svc, "quantity", 1)} '
                f'= {getattr(svc, "total_price", 0)}'
            )
        if not lines:
            lines = ['No line items']
        sections = [{'heading': 'Line items', 'lines': lines}]
        patient_info = {
            'invoice_number': invoice.invoice_number or invoice.id,
            'total_amount': float(invoice.total_amount or 0),
            'paid_amount': float(invoice.paid_amount or 0),
            'balance_due': invoice.balance_due,
            'status': invoice.status,
            'currency': invoice.currency,
        }
        pdf = printer.generate_report(
            f'Invoice {invoice.invoice_number or invoice.id}', patient_info, sections
        )
        response = Response(pdf, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'attachment; filename=invoice-{invoice.id}.pdf'
        return response
    except Exception:
        import logging

        logging.exception('Error generating invoice PDF')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@finance_bp.route('/payment-plans', methods=['GET', 'POST'])
@finance_bp.route('/payment_plans', methods=['GET', 'POST'])
@finance_bp.route('/billing/payment-plans', methods=['GET', 'POST'])
@login_required
@role_required('accountant', 'admin', 'manager')
def payment_plans():
    tenant_id = getattr(g, 'tenant_id', None)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if not data and request.form:
            data = request.form.to_dict()
        try:
            total_amount = float(data.get('total_amount', 0) or 0)
        except (TypeError, ValueError):
            total_amount = 0.0
        try:
            installments = int(data.get('installments', 1) or 1)
        except (TypeError, ValueError):
            installments = 1
        installments = max(installments, 1)
        plan = {
            'id': _next_payment_plan_id(),
            'tenant_id': tenant_id,
            'invoice_id': data.get('invoice_id'),
            'total_amount': total_amount,
            'installments': installments,
            'frequency': data.get('frequency', 'monthly'),
            'status': 'ACTIVE',
            'created_at': datetime.now(UTC).isoformat(),
            'schedule': [],
        }
        per = round(total_amount / installments, 2) if installments else total_amount
        for i in range(installments):
            plan['schedule'].append({'installment': i + 1, 'amount': per, 'status': 'PENDING'})
        _PAYMENT_PLANS[plan['id']] = plan
        return jsonify({'success': True, 'data': plan}), 201
    plans = [p for p in _PAYMENT_PLANS.values() if p.get('tenant_id') == tenant_id]
    return jsonify({'success': True, 'payment_plans': plans})


@finance_bp.route('/payment-plans/<int:plan_id>', methods=['GET'])
@finance_bp.route('/payment_plans/<int:plan_id>', methods=['GET'])
@login_required
@role_required('accountant', 'admin', 'manager')
def get_payment_plan(plan_id: int):
    tenant_id = getattr(g, 'tenant_id', None)
    plan = _PAYMENT_PLANS.get(plan_id)
    if not plan or (tenant_id is not None and plan.get('tenant_id') != tenant_id):
        return jsonify({'success': False, 'error': 'Payment plan not found'}), 404
    return jsonify({'success': True, 'data': plan})


@finance_bp.route('/payment-plans/<int:plan_id>/pay', methods=['POST'])
@finance_bp.route('/payment-plans/<int:plan_id>/payment', methods=['POST'])
@login_required
@role_required('accountant', 'admin', 'manager')
def pay_payment_plan(plan_id: int):
    tenant_id = getattr(g, 'tenant_id', None)
    plan = _PAYMENT_PLANS.get(plan_id)
    if not plan or (tenant_id is not None and plan.get('tenant_id') != tenant_id):
        return jsonify({'success': False, 'error': 'Payment plan not found'}), 404
    data = request.get_json(silent=True) or {}
    installment_no = int(data.get('installment', 1) or 1)
    for item in plan.get('schedule', []):
        if item.get('installment') == installment_no:
            item['status'] = 'PAID'
            item['paid_at'] = datetime.now(UTC).isoformat()
    if all(i.get('status') == 'PAID' for i in plan.get('schedule', [])):
        plan['status'] = 'COMPLETED'
    return jsonify({'success': True, 'data': plan})


@finance_bp.route('/insurance-claims', methods=['GET'])
@finance_bp.route('/insurance/claims', methods=['GET'])
@finance_bp.route('/claims/status', methods=['GET'])
@login_required
@role_required('accountant', 'admin', 'manager')
def finance_insurance_claims():
    tenant_id = getattr(g, 'tenant_id', None)
    status = request.args.get('status')
    try:
        q = select(InsuranceClaim)
        if tenant_id is not None:
            q = q.filter(InsuranceClaim.tenant_id == tenant_id)
        if status:
            q = q.filter(InsuranceClaim.status == status)
        claims = db.session.execute(q.order_by(InsuranceClaim.created_at.desc())).scalars().all()
        data = []
        for c in claims:
            data.append(
                {
                    'id': c.id,
                    'claim_number': getattr(c, 'claim_number', None),
                    'status': c.status,
                    'total_claim': float(c.total_claim or 0)
                    if getattr(c, 'total_claim', None) is not None
                    else 0.0,
                    'approved_amount': float(c.approved_amount or 0)
                    if getattr(c, 'approved_amount', None) is not None
                    else 0.0,
                    'invoice_id': getattr(c, 'invoice_id', None),
                    'visit_id': getattr(c, 'visit_id', None),
                    'created_at': c.created_at.isoformat()
                    if getattr(c, 'created_at', None)
                    else None,
                }
            )
        return jsonify({'success': True, 'claims': data})
    except Exception:
        import logging

        logging.exception('Error listing insurance claims')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@finance_bp.route('/insurance-claims/<int:claim_id>/status', methods=['GET'])
@finance_bp.route('/insurance/claims/<int:claim_id>/status', methods=['GET'])
@login_required
@role_required('accountant', 'admin', 'manager')
def finance_insurance_claim_status(claim_id: int):
    tenant_id = getattr(g, 'tenant_id', None)
    try:
        claim = db.session.get(InsuranceClaim, claim_id)
        if claim is None or (
            tenant_id is not None and getattr(claim, 'tenant_id', None) != tenant_id
        ):
            return jsonify({'success': False, 'error': 'Claim not found'}), 404
        return jsonify(
            {
                'success': True,
                'data': {
                    'id': claim.id,
                    'status': claim.status,
                    'claim_number': getattr(claim, 'claim_number', None),
                },
            }
        )
    except Exception:
        import logging

        logging.exception('Error fetching claim status')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@finance_bp.route('/billing-summary', methods=['GET'])
@finance_bp.route('/billing/summary', methods=['GET'])
@finance_bp.route('/summary', methods=['GET'])
@login_required
@role_required('accountant', 'admin', 'manager')
def billing_summary():
    tenant_id = getattr(g, 'tenant_id', None)
    try:
        inv_q = select(Invoice)
        pay_q = select(Payment)
        if tenant_id is not None:
            inv_q = inv_q.filter(Invoice.tenant_id == tenant_id)
            pay_q = pay_q.filter(Payment.tenant_id == tenant_id)
        invoices = db.session.execute(inv_q).scalars().all()
        payments = db.session.execute(pay_q).scalars().all()
        total_invoiced = sum(float(i.total_amount or 0) for i in invoices)
        total_paid = sum(float(p.amount or 0) for p in payments)
        pending = sum(1 for i in invoices if (i.paid_amount or 0) < (i.total_amount or 0))
        return jsonify(
            {
                'success': True,
                'data': {
                    'total_invoices': len(invoices),
                    'total_payments': len(payments),
                    'total_invoiced': total_invoiced,
                    'total_paid': total_paid,
                    'pending_invoices': pending,
                    'outstanding': max(total_invoiced - total_paid, 0.0),
                },
            }
        )
    except Exception:
        import logging

        logging.exception('Error building billing summary')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
