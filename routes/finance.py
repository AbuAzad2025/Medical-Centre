 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.visit import Visit
from models.payment import Payment
from models.invoice import Invoice
from services.gatekeeper_service import GatekeeperService
from models.audit_trail import AuditTrail
from services.report_service import ReportService
from app_factory import db
from app.shared.enums import PaymentStatus, InvoiceStatus
import logging
from datetime import datetime, date

finance_bp = Blueprint('finance', __name__)

from services.feature_gate_service import guard_module

@finance_bp.before_request
def _guard_billing_module():
    guard_module('billing')

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
        total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.is_provisional == False
        ).scalar() or 0

        pending_payments = Payment.query.filter(
            Payment.is_provisional == True
        ).count()

        locked_visits = Visit.query.filter(
            Visit.receipt_printed == False,
            Visit.payment_status != PaymentStatus.PAID
        ).count()

        today_invoices = Invoice.query.filter(
            db.func.date(Invoice.created_at) == today
        ).count()

        today_payments = Payment.query.filter(
            Payment.is_provisional == False,
            db.func.date(Payment.created_at) == today
        ).count()

        pending_invoices = Invoice.query.filter(
            Invoice.status.in_([InvoiceStatus.ISSUED, InvoiceStatus.POSTED]),
            Invoice.paid_amount < Invoice.total_amount
        ).count()

        refunded_count = Payment.query.filter(
            Payment.status == PaymentStatus.REFUNDED
        ).count()

        recent_invoices = Invoice.query.order_by(
            Invoice.created_at.desc()
        ).limit(10).all()

        stats = {
            'total_revenue': total_revenue,
            'pending_payments': pending_payments,
            'locked_visits': locked_visits
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

    except Exception as e:
        logging.error(f"Error loading finance dashboard: {str(e)}")
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
        
        # استخدام حراسة الخدمة
        success, message = GatekeeperService.post_gl(visit_id, current_user.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 422
            
    except Exception as e:
        logging.error(f"Error posting GL: {str(e)}")
        return jsonify({'error': 'تعذر تنفيذ الترحيل المالي حالياً'}), 500

@finance_bp.route('/visits/<int:visit_id>/archive', methods=['POST'])
@login_required
@role_required_json('accountant', 'admin', 'manager')
def archive_visit(visit_id):
    """أرشفة الزيارة - Finance فقط"""
    
    
    try:
        # استخدام حراسة الخدمة
        success, message = GatekeeperService.archive_visit(visit_id, current_user.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({'error': message}), 422
            
    except Exception as e:
        logging.error(f"Error archiving visit: {str(e)}")
        return jsonify({'error': 'تعذر أرشفة الزيارة حالياً'}), 500

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
        payments = Payment.query.order_by(Payment.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
        return render_template('finance/payments.html', payments=payments)
        
    except Exception as e:
        logging.error(f"Error loading payments: {str(e)}")
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
        invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
        return render_template('finance/invoices.html', invoices=invoices)
        
    except Exception as e:
        logging.error(f"Error loading invoices: {str(e)}")
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
        audit_entries = AuditTrail.query.filter(
            AuditTrail.entity_type.in_(['visit', 'payment', 'invoice'])
        ).order_by(AuditTrail.created_at.desc()).limit(per_page).offset((page - 1) * per_page).all()
        
        return render_template('finance/audit.html', audit_entries=audit_entries)
        
    except Exception as e:
        logging.error(f"Error loading audit: {str(e)}")
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
    except Exception as e:
        logging.error(f"Error loading slow queries report: {str(e)}")
        flash('حدث خطأ في تحميل تقرير الاستعلامات البطيئة', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/slow-queries/weekly')
@login_required
@role_required('accountant', 'admin', 'manager')
def slow_queries_weekly():
    try:
        from models.audit_trail import SlowQueryReport
        reports = SlowQueryReport.query.order_by(SlowQueryReport.created_at.desc()).limit(50).all()
        return render_template('finance/slow_queries_weekly.html', reports=reports)
    except Exception as e:
        logging.error(f"Error loading weekly slow queries: {str(e)}")
        flash('حدث خطأ في تحميل التقرير الأسبوعي', 'error')
        return redirect(url_for('finance.dashboard'))

@finance_bp.route('/slow-queries/weekly/<int:report_id>')
@login_required
@role_required('accountant', 'admin', 'manager')
def slow_queries_weekly_detail(report_id):
    try:
        from models.audit_trail import SlowQueryReport
        report = db.session.get(SlowQueryReport, report_id)
        if not report:
            flash('التقرير غير موجود', 'error')
            return redirect(url_for('finance.slow_queries_weekly'))
        return render_template('finance/slow_queries_weekly_detail.html', report=report)
    except Exception as e:
        logging.error(f"Error loading weekly slow queries detail: {str(e)}")
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
        return redirect(url_for('finance.slow_queries_weekly_detail', report_id=result.get('report_id')))
    except Exception as e:
        logging.error(f"Error capturing weekly slow queries: {str(e)}")
        flash('حدث خطأ في إنشاء التقرير الأسبوعي', 'error')
        return redirect(url_for('finance.slow_queries'))
