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
                select(db.func.sum(Payment.amount)).filter(not Payment.is_provisional)
            ).scalar()
            or 0
        )

        pending_payments = db.session.execute(
            select(func.count()).select_from(Payment).filter(Payment.is_provisional)
        ).scalar()

        locked_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(not Visit.receipt_printed, Visit.payment_status != PaymentStatus.PAID)
        ).scalar()

        today_invoices = db.session.execute(
            select(func.count())
            .select_from(Invoice)
            .filter(db.func.date(Invoice.created_at) == today)
        ).scalar()

        today_payments = db.session.execute(
            select(func.count())
            .select_from(Payment)
            .filter(not Payment.is_provisional, db.func.date(Payment.created_at) == today)
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
