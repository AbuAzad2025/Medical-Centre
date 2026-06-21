"""financial routes - extracted from monolithic accountant.py"""

from routes.accountant import accountant_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required, accountant_only, can_access_financial_reports
from models.patient import Patient
from models.visit import Visit
from models.payment import Payment
from models.invoice import Invoice
from models.user import User
from services.report_service import ReportService
from services.financial_service import financial_service
from app_factory import db
from sqlalchemy import func, and_
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal


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
        start_date = request.args.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
        
        # تحويل التواريخ
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # جلب البيانات المالية
        payments = Payment.query.filter(
            func.date(Payment.created_at) >= start_date,
            func.date(Payment.created_at) <= end_date
        ).all()
        
        # حساب الإحصائيات
        total_payments = sum(payment.amount for payment in payments)
        cash_payments = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CASH')
        card_payments = sum(p.amount for p in payments if getattr(p, 'method', None) == 'CARD')
        insurance_payments = sum(p.amount for p in payments if getattr(p, 'method', None) == 'INSURANCE')
        
        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'total_payments': float(total_payments),
            'cash_payments': float(cash_payments),
            'card_payments': float(card_payments),
            'insurance_payments': float(insurance_payments),
            'payments_count': len(payments)
        }
        
        return render_template('accountant/financial_report.html', report=report_data)
    except Exception as e:
        logging.error(f"Error generating financial report: {str(e)}")
        flash('حدث خطأ في إنشاء التقرير المالي', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/daily-summary')
@login_required
def daily_summary():
    """الملخص اليومي"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        today = date.today()
        
        # المدفوعات اليوم
        today_payments = Payment.query.filter(
            func.date(Payment.created_at) == today
        ).all()
        
        # الزيارات المكتملة اليوم
        completed_visits = Visit.query.filter(
            Visit.status == VisitState.ARCHIVED,
            Visit.completed_at >= datetime.combine(today, datetime.min.time()),
            Visit.completed_at <= datetime.combine(today, datetime.max.time())
        ).all()
        
        # الفواتير الجديدة
        new_invoices = Invoice.query.filter(
            Invoice.created_at >= datetime.combine(today, datetime.min.time()),
            Invoice.created_at <= datetime.combine(today, datetime.max.time())
        ).all()
        
        summary = {
            'date': today,
            'payments_count': len(today_payments),
            'payments_total': sum(p.amount for p in today_payments),
            'completed_visits': len(completed_visits),
            'new_invoices': len(new_invoices),
            'payments': today_payments,
            'visits': completed_visits
        }
        
        return render_template('accountant/daily_summary.html', summary=summary)
    except Exception as e:
        logging.error(f"Error generating daily summary: {str(e)}")
        flash('حدث خطأ في إنشاء الملخص اليومي', 'error')
        return redirect(url_for('accountant.dashboard'))

# ==================== الميزات الذكية للمحاسبة ====================

@accountant_bp.route('/reports')
@login_required
def reports():
    """التقارير المالية"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return redirect(url_for('payment.payment_reports'))
