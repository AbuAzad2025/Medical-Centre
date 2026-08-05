"""financial routes - extracted from monolithic accountant.py"""

import logging
from datetime import date, datetime, timedelta

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import VisitArchiveStatus
from models.invoice import Invoice
from models.payment import Payment
from models.visit import Visit
from routes.accountant import accountant_bp
from utils.decorators import role_required

# =============================================
# FINANCIAL ROUTES
# =============================================


@accountant_bp.route('/financial-report')
@login_required
@role_required('accountant', 'admin', 'manager')
def financial_report():
    """التقرير المالي"""

    try:
        # تحديد الفترة الزمنية
        start_date = request.args.get(
            'start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        )
        end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))

        # تحويل التواريخ
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # جلب البيانات المالية
        payments = (
            db.session.execute(
                select(Payment).filter(
                    Payment.tenant_id == current_user.tenant_id,
                    func.date(Payment.created_at) >= start_date,
                    func.date(Payment.created_at) <= end_date,
                )
            )
            .scalars()
            .all()
        )

        # حساب الإحصائيات
        total_payments = sum(payment.amount for payment in payments)
        cash_payments = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CASH')
        card_payments = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CARD')
        insurance_payments = sum(
            p.amount for p in payments if getattr(p, 'method', None) == 'INSURANCE'
        )

        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'total_payments': float(total_payments),
            'cash_payments': float(cash_payments),
            'card_payments': float(card_payments),
            'insurance_payments': float(insurance_payments),
            'payments_count': len(payments),
        }

        return render_template('accountant/financial_report.html', report=report_data)
    except Exception:
        logging.exception("Error generating financial report: %s")
        flash('حدث خطأ في إنشاء التقرير المالي', 'error')
        return redirect(url_for('accountant.dashboard'))


@accountant_bp.route('/daily-summary')
@login_required
@role_required('accountant', 'admin', 'manager')
def daily_summary():
    """الملخص اليومي"""

    try:
        today = date.today()

        # المدفوعات اليوم
        today_payments = (
            db.session.execute(
                select(Payment).filter(
                    Payment.tenant_id == current_user.tenant_id,
                    func.date(Payment.created_at) == today,
                )
            )
            .scalars()
            .all()
        )

        # الزيارات المكتملة اليوم
        completed_visits = (
            db.session.execute(
                select(Visit).filter(
                    Visit.tenant_id == current_user.tenant_id,
                    Visit.archive_status == VisitArchiveStatus.ARCHIVED,
                    Visit.completed_at >= datetime.combine(today, datetime.min.time()),
                    Visit.completed_at <= datetime.combine(today, datetime.max.time()),
                )
            )
            .scalars()
            .all()
        )

        # الفواتير الجديدة
        new_invoices = (
            db.session.execute(
                select(Invoice).filter(
                    Invoice.tenant_id == current_user.tenant_id,
                    Invoice.created_at >= datetime.combine(today, datetime.min.time()),
                    Invoice.created_at <= datetime.combine(today, datetime.max.time()),
                )
            )
            .scalars()
            .all()
        )

        summary = {
            'date': today,
            'payments_count': len(today_payments),
            'payments_total': sum(p.amount for p in today_payments),
            'completed_visits': len(completed_visits),
            'new_invoices': len(new_invoices),
            'payments': today_payments,
            'visits': completed_visits,
        }

        return render_template('accountant/daily_summary.html', summary=summary)
    except Exception:
        logging.exception("Error generating daily summary: %s")
        flash('حدث خطأ في إنشاء الملخص اليومي', 'error')
        return redirect(url_for('accountant.dashboard'))


# ==================== الميزات الذكية للمحاسبة ====================


@accountant_bp.route('/reports')
@login_required
@role_required('accountant', 'admin', 'manager')
def reports():
    """التقارير المالية"""

    return redirect(url_for('payment.payment_reports'))
