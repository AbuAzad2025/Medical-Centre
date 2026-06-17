"""patient routes - extracted from monolithic accountant.py"""

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
# PATIENT ROUTES
# =============================================

@accountant_bp.route('/invoices')
@login_required
def invoices():
    """الفواتير"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        query = Visit.query.filter(
            Visit.payment_status.in_(['PENDING', 'PARTIAL', 'DEBT'])
        ).order_by(Visit.created_at.desc())
        
        total = query.count()
        pages = (total + per_page - 1) // per_page
        
        visits = query.offset((page - 1) * per_page).limit(per_page).all()
    except Exception as e:
        logging.error(f"Error loading pending visits: {str(e)}")
        visits = []
        total = 0
        pages = 0

    return render_template('accountant/pending_payments.html', visits=visits, page=page, pages=pages, total=total)

@accountant_bp.route('/financial')
@login_required
def financial():
    """الإدارة المالية"""
    if current_user.role not in ['accountant', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.patient import Patient
        from models.payment import Payment, PaymentStatus
        from models.invoice import Invoice

        q = (request.args.get('q') or '').strip()
        patient_id = request.args.get('patient_id', type=int)

        patients = []
        if q:
            pq = Patient.query
            if q.isdigit():
                pq = pq.filter(Patient.id == int(q))
            else:
                pq = pq.filter(
                    db.or_(
                        Patient.first_name.ilike(f"%{q}%"),
                        Patient.last_name.ilike(f"%{q}%"),
                        Patient.phone.ilike(f"%{q}%"),
                        Patient.national_id.ilike(f"%{q}%")
                    )
                )
            patients = pq.order_by(Patient.created_at.desc()).limit(50).all()

        statement = None
        selected_patient = None
        if patient_id:
            selected_patient = db.session.get(Patient, patient_id)
            if selected_patient:
                visits = Visit.query.filter(Visit.patient_id == patient_id).order_by(Visit.created_at.desc()).limit(200).all()
                visit_ids = [v.id for v in visits]
                invoices = []
                if visit_ids:
                    invoices = Invoice.query.filter(Invoice.visit_id.in_(visit_ids)).order_by(Invoice.created_at.desc()).all()
                payments = Payment.query.filter(
                    Payment.patient_id == patient_id,
                    Payment.status == PaymentStatus.CONFIRMED
                ).order_by(Payment.payment_date.desc()).limit(500).all()

                totals = {
                    'visits_count': len(visits),
                    'invoices_count': len(invoices),
                    'payments_count': len(payments),
                    'total_billed': float(sum(float(i.total_amount or 0) for i in invoices)),
                    'total_paid': float(sum(float(p.amount or 0) for p in payments)),
                    'total_remaining': float(sum(float(v.remaining_amount or 0) for v in visits if getattr(v, 'payment_status', None) in {'PENDING', 'PARTIAL', 'DEBT'})),
                }
                statement = {
                    'totals': totals,
                    'visits': visits,
                    'invoices': invoices,
                    'payments': payments,
                }

        return render_template('accountant/payment_management.html', q=q, patients=patients, selected_patient=selected_patient, statement=statement)
    except Exception as e:
        logging.error(f"Error loading accountant financial page: {str(e)}")
        flash('حدث خطأ في تحميل الإدارة المالية', 'error')
        return redirect(url_for('accountant.dashboard'))

# ==================== مسارات التدقيق (الأسبوع الثاني) ====================
