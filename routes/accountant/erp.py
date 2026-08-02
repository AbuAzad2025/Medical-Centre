"""erp routes - extracted from monolithic accountant.py"""

import logging

# Imports
from flask import jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.invoice import Invoice
from models.payment import Payment
from routes.accountant import accountant_bp
from utils.decorators import role_required

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
        invoices = (
            db.session.execute(
                select(Invoice)
                .filter(Invoice.tenant_id == current_user.tenant_id)
                .order_by(Invoice.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        payments = (
            db.session.execute(
                select(Payment)
                .filter(Payment.tenant_id == current_user.tenant_id)
                .order_by(Payment.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return jsonify(
            {
                'success': True,
                'invoices': [i.to_dict() for i in invoices],
                'payments': [
                    {
                        'id': p.id,
                        'amount': float(p.amount or 0),
                        'method': str(p.method),
                        'status': str(p.status),
                        'created_at': p.created_at.isoformat() if p.created_at else None,
                    }
                    for p in payments
                ],
            }
        ), 200
    except Exception as e:
        logging.exception(f'Error exporting ERP payload: {e!s}')
        return jsonify({'success': False, 'message': 'تعذر تصدير بيانات ERP'}), 500
