"""patient routes - extracted from monolithic accountant.py"""

import logging

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from models.visit import Visit
from routes.accountant import accountant_bp
from utils.decorators import role_required

# =============================================
# PATIENT ROUTES
# =============================================


@accountant_bp.route('/invoices')
@login_required
@role_required('accountant', 'admin', 'manager')
def invoices():
    """الفواتير"""

    page = request.args.get('page', 1, type=int)
    per_page = 25

    try:
        query = select(Visit).filter(
            Visit.tenant_id == current_user.tenant_id,
            Visit.payment_status.in_(['PENDING', 'PARTIAL', 'DEBT']),
        )

        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
        pages = (total + per_page - 1) // per_page

        visits = (
            db.session.execute(query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        )
    except Exception:
        logging.exception("Error loading pending visits: %s")
        visits = []
        total = 0
        pages = 0

    return render_template(
        'accountant/pending_payments.html', visits=visits, page=page, pages=pages, total=total
    )


@accountant_bp.route('/financial')
@login_required
@role_required('accountant', 'admin', 'manager')
def financial():
    """الإدارة المالية"""

    try:
        from models.invoice import Invoice
        from models.patient import Patient
        from models.payment import Payment, PaymentStatus

        q = (request.args.get('q') or '').strip()
        patient_id = request.args.get('patient_id', type=int)

        patients = []
        if q:
            pq = select(Patient)
            if q.isdigit():
                pq = pq.filter(Patient.id == int(q))
            else:
                pq = pq.filter(
                    db.or_(
                        Patient.first_name.ilike(f'%{q}%'),
                        Patient.last_name.ilike(f'%{q}%'),
                        Patient.phone.ilike(f'%{q}%'),
                        Patient.national_id.ilike(f'%{q}%'),
                    )
                )
            patients = pq.order_by(Patient.created_at.desc()).limit(50).all()

        statement = None
        selected_patient = None
        if patient_id:
            selected_patient = db.session.get(Patient, patient_id)
            if selected_patient:
                visits = (
                    db.session.execute(
                        select(Visit)
                        .filter(
                            Visit.tenant_id == current_user.tenant_id,
                            Visit.patient_id == patient_id,
                        )
                        .order_by(Visit.created_at.desc())
                        .limit(200)
                    )
                    .scalars()
                    .all()
                )
                visit_ids = [v.id for v in visits]
                invoices = []
                if visit_ids:
                    invoices = (
                        db.session.execute(
                            select(Invoice)
                            .filter(
                                Invoice.tenant_id == current_user.tenant_id,
                                Invoice.visit_id.in_(visit_ids),
                            )
                            .order_by(Invoice.created_at.desc())
                        )
                        .scalars()
                        .all()
                    )
                payments = (
                    db.session.execute(
                        select(Payment)
                        .filter(
                            Payment.tenant_id == current_user.tenant_id,
                            Payment.patient_id == patient_id,
                            Payment.status == PaymentStatus.CONFIRMED,
                        )
                        .order_by(Payment.payment_date.desc())
                        .limit(500)
                    )
                    .scalars()
                    .all()
                )

                totals = {
                    'visits_count': len(visits),
                    'invoices_count': len(invoices),
                    'payments_count': len(payments),
                    'total_billed': float(sum(float(i.total_amount or 0) for i in invoices)),
                    'total_paid': float(sum(float(p.amount or 0) for p in payments)),
                    'total_remaining': float(
                        sum(
                            float(v.remaining_amount or 0)
                            for v in visits
                            if getattr(v, 'payment_status', None) in {'PENDING', 'PARTIAL', 'DEBT'}
                        )
                    ),
                }
                statement = {
                    'totals': totals,
                    'visits': visits,
                    'invoices': invoices,
                    'payments': payments,
                }

        return render_template(
            'accountant/payment_management.html',
            q=q,
            patients=patients,
            selected_patient=selected_patient,
            statement=statement,
        )
    except Exception:
        logging.exception("Error loading accountant financial page: %s")
        flash('حدث خطأ في تحميل الإدارة المالية', 'error')
        return redirect(url_for('accountant.dashboard'))


# ==================== مسارات التدقيق (الأسبوع الثاني) ====================
