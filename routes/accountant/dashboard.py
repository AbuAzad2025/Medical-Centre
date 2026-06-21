"""dashboard routes - extracted from monolithic accountant.py"""

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
from services.core_queries import core_queries
from app_factory import db
from sqlalchemy import func, and_
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal


# =============================================
# DASHBOARD ROUTES
# =============================================

@accountant_bp.route('/')
@login_required
def index():
    """توجيه تلقائي إلى لوحة التحكم"""
    return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/dashboard')
@login_required
@role_required('accountant', 'admin', 'manager')
def dashboard():
    """لوحة تحكم المحاسب"""
    
    
    try:
        # إحصائيات أساسية عبر CoreQueryService
        base_stats = core_queries.get_basic_dashboard_stats()
        today_total = base_stats["revenue_today"]
        month_total = base_stats["revenue_month"]

        try:
            net_profit = float(month_total) * 0.22
        except Exception:
            net_profit = 0.0
        
        # الفواتير المفتوحة
        open_invoices = Invoice.query.filter(
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED])
        ).count()
        
        # المبالغ المستحقة
        pending_amount = db.session.query(
            db.func.sum(Invoice.total_amount - Invoice.paid_amount)
        ).filter(
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED])
        ).scalar() or 0
        
        # الميزات الذكية
        smart_analytics = get_accounting_smart_analytics()
        financial_forecasting = get_financial_forecasting()
        cash_flow_analysis = get_cash_flow_analysis()
        payment_optimization = get_payment_optimization()
        financial_health = get_financial_health_monitoring()
        smart_recommendations = get_smart_recommendations()
        revenue_cycle = get_revenue_cycle_metrics()
        erp_integration = get_erp_integration_status()
        margin_analytics = get_margin_analytics()

        # تحليل العملات المتعددة
        currency_breakdown = {}
        try:
            from services.currency_service import CurrencyConverter
            today_currencies = db.session.query(
                Payment.currency,
                db.func.count(Payment.id).label('count'),
                db.func.sum(Payment.amount).label('total')
            ).filter(
                func.date(Payment.created_at) == today,
                Payment.currency.isnot(None)
            ).group_by(Payment.currency).all()
            for cur, cnt, total in today_currencies:
                converted = 0
                if cur and cur != 'ILS' and total:
                    rate = CurrencyConverter.get_rate(cur, 'ILS')
                    if rate:
                        converted = float(CurrencyConverter.convert(float(total or 0), cur, 'ILS'))
                currency_breakdown[cur or 'ILS'] = {
                    'count': int(cnt or 0),
                    'original': float(total or 0),
                    'converted': converted if cur != 'ILS' else float(total or 0)
                }
        except Exception:
            currency_breakdown = {}

        recent_transactions = []
        try:
            recent = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
            for p in recent:
                st = (p.status or '').upper()
                color = 'success' if st == 'CONFIRMED' else ('warning' if st == 'PENDING' else 'danger' if st == 'CANCELLED' else 'secondary')
                recent_transactions.append({
                    'id': p.id,
                    'type': 'دفع',
                    'amount': f"{float(p.amount or 0):.2f}",
                    'date': p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else '-',
                    'status': st or '-',
                    'status_color': color
                })
        except Exception:
            recent_transactions = []

        debt_alerts = {
            'overdue_60_count': 0,
            'large_debts_count': 0,
            'top_overdue': [],
            'top_large': []
        }
        try:
            rep = ReportService.get_debt_tracking_report()
            if rep and rep.get('success'):
                debts_by_age = rep.get('debts_by_age') or {}
                overdue = list(debts_by_age.get('60+_days') or [])
                debt_alerts['overdue_60_count'] = len(overdue)
                debt_alerts['top_overdue'] = sorted(overdue, key=lambda x: float(x.get('remaining_amount') or 0), reverse=True)[:10]

                all_debts = []
                for group in debts_by_age.values():
                    all_debts.extend(group or [])
                large = [d for d in all_debts if float(d.get('remaining_amount') or 0) >= 500]
                debt_alerts['large_debts_count'] = len(large)
                debt_alerts['top_large'] = sorted(large, key=lambda x: float(x.get('remaining_amount') or 0), reverse=True)[:10]
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        stats = {
            'today_payments': len(today_payments),
            'today_total': float(today_total),
            'monthly_revenue': float(month_total),
            'net_profit': float(net_profit),
            'pending_invoices': open_invoices,
            'pending_amount': float(pending_amount),
            'smart_analytics': smart_analytics,
            'financial_forecasting': financial_forecasting,
            'cash_flow_analysis': cash_flow_analysis,
            'payment_optimization': payment_optimization,
            'financial_health': financial_health,
            'smart_recommendations': smart_recommendations,
            'revenue_cycle': revenue_cycle,
            'erp_integration': erp_integration,
            'margin_analytics': margin_analytics,
            'currency_breakdown': currency_breakdown
        }
        
        return render_template('accountant/dashboard_new.html', stats=stats, recent_transactions=recent_transactions, debt_alerts=debt_alerts)
    except Exception as e:
        logging.error(f"Error in accountant dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return render_template('accountant/dashboard_new.html', stats={}, recent_transactions=[], debt_alerts={})