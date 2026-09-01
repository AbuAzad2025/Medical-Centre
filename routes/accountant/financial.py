"""financial routes - extracted from monolithic accountant.py"""

import logging
from datetime import date, datetime, timedelta

# Imports
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import VisitArchiveStatus
from models import Account
from models.gl import GLJournal, GLJournalLine
from models.invoice import Invoice
from models.payment import Payment
from models.visit import Visit
from routes.accountant import accountant_bp
from services.gl_service import gl_service
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
        logging.exception('Error generating financial report: %s')
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
        logging.exception('Error generating daily summary: %s')
        flash('حدث خطأ في إنشاء الملخص اليومي', 'error')
        return redirect(url_for('accountant.dashboard'))


# ==================== الميزات الذكية للمحاسبة ====================


@accountant_bp.route('/reports')
@login_required
@role_required('accountant', 'admin', 'manager')
def reports():
    """التقارير المالية"""

    return redirect(url_for('payment.payment_reports'))


# ==================== دليل الحسابات و الدفتر اليومي ====================


@accountant_bp.route('/accounts')
@login_required
@role_required('accountant', 'admin', 'manager')
def accounts():
    """دليل الحسابات"""
    gl_service.ensure_coa(current_user.tenant_id)
    tenant_id = current_user.tenant_id
    stmt = select(Account).where(Account.tenant_id == tenant_id).order_by(Account.code)
    accounts = db.session.execute(stmt).scalars().all()
    line_stmt = (
        select(
            GLJournalLine.account_id,
            func.sum(GLJournalLine.debit_amount).label('total_debit'),
            func.sum(GLJournalLine.credit_amount).label('total_credit'),
        )
        .where(GLJournalLine.tenant_id == tenant_id)
        .group_by(GLJournalLine.account_id)
    )
    lines = db.session.execute(line_stmt).all()
    balances = {row.account_id: (row.total_debit or 0, row.total_credit or 0) for row in lines}
    rows = []
    for a in accounts:
        td, tc = balances.get(a.id, (0, 0))
        balance = td - tc if a.normal_balance == 'DEBIT' else tc - td
        rows.append(
            {
                'id': a.id,
                'code': a.code,
                'name': a.name,
                'name_ar': a.name_ar,
                'type': a.account_type,
                'normal_balance': a.normal_balance,
                'total_debit': float(td),
                'total_credit': float(tc),
                'balance': float(balance),
            }
        )
    return render_template('accountant/accounts.html', accounts=rows)


@accountant_bp.route('/journals')
@login_required
@role_required('accountant', 'admin', 'manager')
def journals():
    """الدفتر اليومي"""
    tenant_id = current_user.tenant_id
    page = request.args.get('page', 1, type=int)
    per_page = 30
    journals = (
        db.session.execute(
            select(GLJournal)
            .where(GLJournal.tenant_id == tenant_id)
            .order_by(GLJournal.created_at.desc())
            .limit(per_page)
            .offset((page - 1) * per_page)
        )
        .scalars()
        .all()
    )
    total = db.session.execute(
        select(func.count()).where(GLJournal.tenant_id == tenant_id)
    ).scalar()
    total_pages = (total + per_page - 1) // per_page if total else 1
    return render_template(
        'accountant/journals.html',
        journals=journals,
        page=page,
        total_pages=total_pages,
        total=total,
    )


# ==================== الميزانية المرجعية و الدفتر التفصيلي ====================


@accountant_bp.route('/trial-balance')
@login_required
@role_required('accountant', 'admin', 'manager')
def trial_balance():
    """الميزانية المرجعية"""
    gl_service.ensure_coa(current_user.tenant_id)
    tenant_id = current_user.tenant_id
    start_date = request.args.get(
        'from_date', type=lambda v: datetime.strptime(v, '%Y-%m-%d').date()
    )
    end_date = request.args.get('to_date', type=lambda v: datetime.strptime(v, '%Y-%m-%d').date())
    if not start_date or not end_date:
        today = date.today()
        start_date = today.replace(month=1, day=1)
        end_date = today
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    stmt = (
        select(Account)
        .where(Account.tenant_id == tenant_id, Account.is_active == True)  # noqa: E712
        .order_by(Account.code)
    )
    accounts = db.session.execute(stmt).scalars().all()
    line_stmt = (
        select(
            GLJournalLine.account_id,
            func.sum(GLJournalLine.debit_amount).label('total_debit'),
            func.sum(GLJournalLine.credit_amount).label('total_credit'),
        )
        .join(GLJournal)
        .where(
            GLJournal.tenant_id == tenant_id,
            GLJournalLine.tenant_id == tenant_id,
            GLJournal.journal_date >= start_dt,
            GLJournal.journal_date <= end_dt,
            GLJournal.status == 'POSTED',
        )
        .group_by(GLJournalLine.account_id)
    )
    lines = db.session.execute(line_stmt).all()
    balances = {row.account_id: (row.total_debit or 0, row.total_credit or 0) for row in lines}
    rows = []
    for a in accounts:
        td, tc = balances.get(a.id, (0, 0))
        balance = td - tc if a.normal_balance == 'DEBIT' else tc - td
        rows.append(
            {
                'code': a.code,
                'name': a.name,
                'name_ar': a.name_ar,
                'type': a.account_type,
                'normal_balance': a.normal_balance,
                'total_debit': float(td),
                'total_credit': float(tc),
                'balance': float(balance),
            }
        )
    total_debit = sum(r['total_debit'] for r in rows)
    total_credit = sum(r['total_credit'] for r in rows)
    equal = abs(total_debit - total_credit) < 0.01
    return render_template(
        'accountant/trial_balance.html',
        accounts=rows,
        start_date=start_date,
        end_date=end_date,
        total_debit=total_debit,
        total_credit=total_credit,
        equal=equal,
    )


@accountant_bp.route('/accounts/<int:account_id>')
@login_required
@role_required('accountant', 'admin', 'manager')
def account_ledger(account_id: int):
    """الدفتر التفصيلي للحساب"""
    tenant_id = current_user.tenant_id
    start_date = request.args.get(
        'from_date', type=lambda v: datetime.strptime(v, '%Y-%m-%d').date()
    )
    end_date = request.args.get('to_date', type=lambda v: datetime.strptime(v, '%Y-%m-%d').date())
    if not start_date or not end_date:
        today = date.today()
        start_date = today.replace(month=1, day=1)
        end_date = today
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    account = db.session.get(Account, account_id)
    if account is None or account.tenant_id != tenant_id:
        abort(404)

    lines_stmt = (
        select(GLJournalLine)
        .join(GLJournal)
        .where(
            GLJournalLine.account_id == account_id,
            GLJournal.tenant_id == tenant_id,
            GLJournal.journal_date >= start_dt,
            GLJournal.journal_date <= end_dt,
            GLJournal.status == 'POSTED',
        )
        .order_by(GLJournal.journal_date, GLJournal.created_at, GLJournalLine.id)
    )
    all_lines = db.session.execute(lines_stmt).scalars().all()
    running = 0
    rows = []
    for line in all_lines:
        debit = float(line.debit_amount or 0)
        credit = float(line.credit_amount or 0)
        if account.normal_balance == 'DEBIT':
            running += debit - credit
        else:
            running += credit - debit
        rows.append(
            {
                'date': line.journal.journal_date,
                'journal_number': line.journal.journal_number or str(line.journal.id),
                'description': line.line_description or line.journal.description or '',
                'debit': debit,
                'credit': credit,
                'running_balance': running,
            }
        )
    return render_template(
        'accountant/account_ledger.html',
        account=account,
        lines=rows,
        start_date=start_date,
        end_date=end_date,
        running_balance=running,
    )


@accountant_bp.route('/periods/close', methods=['POST'])
@login_required
@role_required('accountant', 'admin', 'manager')
def close_period():
    """إغلاق فترة مالية"""
    period_id = request.form.get('period_id', type=int)
    if not period_id:
        flash('رقم الفترة مطلوب', 'error')
        return redirect(url_for('accountant.dashboard'))
    try:
        result = gl_service.close_period(
            current_user.tenant_id, period_id, closed_by=current_user.id
        )
        flash(f'تم إغلاق الفترة بنجاح: {result["closed_at"]}', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('accountant.journals'))
