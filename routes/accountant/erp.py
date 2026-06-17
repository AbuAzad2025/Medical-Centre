"""erp routes - extracted from monolithic accountant.py"""

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
# ERP ROUTES
# =============================================

@accountant_bp.route('/api/erp/export')
@login_required
@role_required('accountant', 'admin', 'manager')
def api_erp_export():
    try:
        limit = request.args.get('limit', type=int) or 200
        limit = max(50, min(limit, 1000))
        invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(limit).all()
        payments = Payment.query.order_by(Payment.created_at.desc()).limit(limit).all()
        return jsonify({
            'success': True,
            'invoices': [i.to_dict() for i in invoices],
            'payments': [{'id': p.id, 'amount': float(p.amount or 0), 'method': str(p.method), 'status': str(p.status), 'created_at': p.created_at.isoformat() if p.created_at else None} for p in payments]
        }), 200
    except Exception as e:
        logging.error(f"Error exporting ERP payload: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تصدير بيانات ERP'}), 500
