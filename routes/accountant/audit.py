"""audit routes - extracted from monolithic accountant.py"""

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
# AUDIT ROUTES
# =============================================

# ==================== مسارات التدقيق (الأسبوع الثاني) ====================

@accountant_bp.route('/audit/daily')
@login_required
@can_access_financial_reports
def daily_audit_report():
    """تقرير التدقيق اليومي"""
    try:
        date_str = request.args.get('date')
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        
        # الحصول على التقرير
        report = ReportService.get_daily_audit_report(target_date)
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/daily_audit_report.html', 
                             report=report,
                             target_date=target_date)
    
    except ValueError:
        flash('تنسيق التاريخ غير صحيح', 'error')
        return redirect(url_for('accountant.dashboard'))
    except Exception as e:
        logging.error(f"Error in daily_audit_report: {str(e)}")
        flash('تعذر تحميل تقرير التدقيق اليومي حالياً', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/monthly')
@login_required
@can_access_financial_reports
def monthly_audit_report():
    """تقرير التدقيق الشهري"""
    try:
        year = request.args.get('year', date.today().year, type=int)
        month = request.args.get('month', date.today().month, type=int)
        
        # الحصول على التقرير
        report = ReportService.get_monthly_audit_report(year, month)
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/monthly_audit_report.html',
                             report=report,
                             year=year,
                             month=month)
    
    except Exception as e:
        logging.error(f"Error in monthly_audit_report: {str(e)}")
        flash('تعذر تحميل تقرير التدقيق الشهري حالياً', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/debts')
@login_required
@can_access_financial_reports
def debt_tracking_report():
    """تقرير تتبع الديون"""
    try:
        # الحصول على التقرير
        report = ReportService.get_debt_tracking_report()
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        return render_template('accountant/debt_tracking_report.html',
                             report=report)
    
    except Exception as e:
        logging.error(f"Error in debt_tracking_report: {str(e)}")
        flash('تعذر تحميل تقرير تتبع الديون حالياً', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/audit/export/<report_type>')
@login_required
@can_access_financial_reports
def export_audit_report(report_type):
    """تصدير تقرير التدقيق"""
    try:
        format_type = request.args.get('format', 'json')
        
        # الحصول على التقرير المناسب
        if report_type == 'daily':
            date_str = request.args.get('date')
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
            report = ReportService.get_daily_audit_report(target_date)
        
        elif report_type == 'monthly':
            year = request.args.get('year', date.today().year, type=int)
            month = request.args.get('month', date.today().month, type=int)
            report = ReportService.get_monthly_audit_report(year, month)
        
        elif report_type == 'debts':
            report = ReportService.get_debt_tracking_report()
        
        else:
            flash('نوع تقرير غير معروف', 'error')
            return redirect(url_for('accountant.dashboard'))
        
        if not report['success']:
            flash(report['message'], 'error')
            return redirect(url_for('accountant.dashboard'))
        
        # تصدير بالتنسيق المطلوب
        if format_type == 'json':
            return jsonify(report)
        else:
            flash('تنسيق التصدير غير مدعوم حالياً', 'warning')
            return redirect(url_for('accountant.dashboard'))
    
    except Exception as e:
        logging.error(f"Error exporting report: {str(e)}")
        flash('تعذر تصدير التقرير حالياً', 'error')
        return redirect(url_for('accountant.dashboard'))
