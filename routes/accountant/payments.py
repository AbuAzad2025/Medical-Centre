"""payments routes - extracted from monolithic accountant.py"""

from routes.accountant import accountant_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, abort
from flask_login import login_required, current_user
from utils.decorators import role_required, accountant_only, can_access_financial_reports
from models.patient import Patient
from models.visit import Visit
from models.payment import Payment
from models.invoice import Invoice
from models.user import User
from services.report_service import ReportService
from services.financial_service import financial_service
from app.extensions import db
from sqlalchemy import func, and_, select
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from app.shared.print_context import generate_qr_data_uri
from app.shared.enums import InvoiceStatus


# =============================================
# PAYMENTS ROUTES
# =============================================

@accountant_bp.route('/open-invoices')
@login_required
@role_required('accountant', 'admin', 'manager')
def open_invoices():
    """الفواتير المفتوحة"""
    
    
    try:
        # جلب الفواتير المفتوحة
        invoices = db.session.execute(select(Invoice).filter(
            Invoice.tenant_id == current_user.tenant_id,
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED])
        ).order_by(Invoice.created_at.desc())).scalars().all()
        
        return render_template('accountant/open_invoices.html', invoices=invoices)
    except Exception as e:
        logging.error(f"Error loading open invoices: {str(e)}")
        flash('حدث خطأ في تحميل الفواتير المفتوحة', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/payments')
@login_required
@role_required('accountant', 'admin', 'manager')
def payments():
    """سجل المدفوعات"""
    
    
    try:
        # جلب المدفوعات
        payments = db.session.execute(select(Payment).filter(
            Payment.tenant_id == current_user.tenant_id
        ).order_by(Payment.created_at.desc())).scalars().all()
        
        return render_template('accountant/payments.html', payments=payments)
    except Exception as e:
        logging.error(f"Error loading payments: {str(e)}")
        flash('حدث خطأ في تحميل سجل المدفوعات', 'error')
        return redirect(url_for('accountant.dashboard'))

@accountant_bp.route('/payment-documentation/<int:payment_id>')
@login_required
@role_required('accountant', 'admin', 'manager')
def payment_documentation(payment_id):
    """توثيق الدفع"""
    
    
    try:
        payment = db.session.get(Payment, payment_id)
        if not payment:
            abort(404)
        return render_template('accountant/payment_documentation.html', payment=payment)
    except Exception as e:
        logging.error(f"Error loading payment documentation: {str(e)}")
        flash('حدث خطأ في تحميل توثيق الدفع', 'error')
        return redirect(url_for('accountant.payments'))

@accountant_bp.route('/receipt/<int:payment_id>')
@login_required
@role_required('accountant', 'admin', 'manager')
def receipt(payment_id):
    """طباعة وصل القبض"""
    
    
    try:
        payment = db.session.get(Payment, payment_id)
        if not payment:
            abort(404)
        from datetime import datetime
        visit = payment.visit
        if not visit:
            flash('لا توجد زيارة مرتبطة بهذا الدفع', 'error')
            return redirect(url_for('accountant.payments'))
        survey_url = None
        try:
            from models.patient_satisfaction import PatientSatisfactionSurvey
            survey = db.session.execute(select(PatientSatisfactionSurvey).filter_by(visit_id=visit.id)).scalars().first()
            if survey:
                survey_url = url_for('reception.survey', token=survey.token, _external=True)
        except Exception:
            survey_url = None
        qr_data_uri = generate_qr_data_uri(f"RCPT|{visit.id}|{visit.patient_id}|{visit.total_amount}")
        return render_template('print/receipt.html', visit=visit, printed_at=datetime.now(timezone.utc), survey_url=survey_url, qr_data_uri=qr_data_uri)
    except Exception as e:
        logging.error(f"Error generating receipt: {str(e)}")
        flash('حدث خطأ في إنشاء وصل القبض', 'error')
        return redirect(url_for('accountant.payments'))
