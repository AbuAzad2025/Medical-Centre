"""dashboard routes - extracted from monolithic medication_routes.py"""

import logging
from datetime import date

# Imports
from flask import flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from models.medication import Medication, PharmacySale, Prescription
from routes.medication_routes import medication_bp
from utils.decorators import role_required

# =============================================
# DASHBOARD ROUTES
# =============================================


@medication_bp.route('/')
@login_required
def index():
    return redirect(url_for('medication.dashboard'))


@medication_bp.route('/dashboard')
@login_required
@role_required('doctor', 'nurse', 'pharmacist', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الأدوية"""
    try:
        tid = current_user.tenant_id
        db.session.execute(
            select(func.count()).select_from(Medication).filter(Medication.tenant_id == tid)
        ).scalar()
        db.session.execute(
            select(func.count())
            .select_from(Medication)
            .filter(
                Medication.stock_quantity <= Medication.minimum_stock, Medication.tenant_id == tid
            )
        ).scalar()
        today = date.today()
        db.session.execute(
            select(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
                func.date(PharmacySale.created_at) == today, PharmacySale.tenant_id == tid
            )
        ).scalar()
        db.session.execute(
            select(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
                func.extract('month', PharmacySale.created_at) == today.month,
                func.extract('year', PharmacySale.created_at) == today.year,
                PharmacySale.tenant_id == tid,
            )
        ).scalar()
        db.session.execute(
            select(func.count())
            .select_from(Medication)
            .filter(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date < today,
                Medication.tenant_id == tid,
            )
        ).scalar()
        db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .filter(func.date(Prescription.created_at) == today, Prescription.tenant_id == tid)
        ).scalar()
        (
            db.session.execute(
                select(Medication)
                .filter(
                    Medication.stock_quantity <= Medication.minimum_stock,
                    Medication.tenant_id == tid,
                )
                .limit(10)
            )
            .scalars()
            .all()
        )

        (
            db.session.execute(
                select(Prescription)
                .filter(Prescription.status == 'active', Prescription.tenant_id == tid)
                .order_by(Prescription.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        (
            db.session.execute(
                select(PharmacySale)
                .filter(func.date(PharmacySale.created_at) == today, PharmacySale.tenant_id == tid)
                .order_by(PharmacySale.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)
    except Exception as e:
        logging.error(f'Error in medication dashboard: {e!s}', exc_info=True)
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('auth.login'))
