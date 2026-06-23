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
from app.shared.enums import InvoiceStatus
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
        today = date.today()

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

        # دفعات اليوم
        today_payments = Payment.query.filter(
            func.date(Payment.created_at) == today
        ).all()

        # الميزات الذكية — imported here to avoid circular imports during blueprint registration.
        from routes.accountant import (
            get_accounting_smart_analytics,
            get_financial_forecasting,
            get_cash_flow_analysis,
            get_payment_optimization,
            get_financial_health_monitoring,
            get_smart_recommendations,
            get_revenue_cycle_metrics,
            get_erp_integration_status,
            get_margin_analytics,
        )

        def _with_defaults(value, **defaults):
            d = value if isinstance(value, dict) else {}
            for k, v in defaults.items():
                d.setdefault(k, v)
            return d

        smart_analytics = _with_defaults(
            get_accounting_smart_analytics(),
            billing_accuracy=0, audit_compliance=0, collection_rate=0, efficiency_score=0,
            total_payments=0, today_payments=0, total_invoices=0, open_invoices=0,
            paid_invoices=0, payment_methods=[], weekly_trend=0, monthly_trend=0,
        )
        financial_forecasting = _with_defaults(
            get_financial_forecasting(),
            monthly_forecast=0, annual_forecast=0, growth_rate=0, monthly_data=[],
        )
        cash_flow_analysis = _with_defaults(get_cash_flow_analysis(), net_cash_flow=0, inflow=0, outflow=0)
        payment_optimization = _with_defaults(
            get_payment_optimization(), automation_rate=0, time_saved=0, late_payments=0,
        )
        financial_health = _with_defaults(
            get_financial_health_monitoring(),
            overall_score=100, health_score=100, collection_rate=0,
            outstanding_amount=0, total_revenue=0, risk_indicators=[], financial_alerts=[],
        )
        smart_recommendations = _with_defaults(
            get_smart_recommendations(), recommendations=[], total_recommendations=0, high_priority=0, medium_priority=0,
        )
        revenue_cycle = _with_defaults(
            get_revenue_cycle_metrics(),
            avg_collection_time=0, collection_rate=0, denial_rate=0,
            total_claims=0, submitted=0, approved=0, rejected=0, paid=0, outstanding_amount=0,
        )
        erp_integration = _with_defaults(get_erp_integration_status(), status='idle', last_sync=None)
        margin_analytics = _with_defaults(
            get_margin_analytics(),
            total_invoiced=0, total_revenue=0, collection_rate=0, gross_margin=0,
        )

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
        
        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"Error in accountant dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user)