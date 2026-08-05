"""interactions routes - extracted from monolithic medication_routes.py"""

import logging
from datetime import UTC, datetime

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.drug_interaction import DrugInteraction
from models.medication import Medication
from routes.medication_routes import medication_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

# =============================================
# INTERACTIONS ROUTES
# =============================================


@medication_bp.route('/interactions', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def interactions():
    if request.method == 'POST':
        try:
            a_id = request.form.get('medication_a_id', type=int)
            b_id = request.form.get('medication_b_id', type=int)
            severity = (request.form.get('severity') or 'MODERATE').strip().upper()
            description = (request.form.get('description') or '').strip() or None
            is_active = (request.form.get('is_active') or '') == 'on'
            if not a_id or not b_id or a_id == b_id:
                flash('يرجى اختيار دوائين مختلفين', 'warning')
                return redirect(url_for('medication.interactions'))
            a = min(a_id, b_id)
            b = max(a_id, b_id)
            if severity not in {'LOW', 'MODERATE', 'HIGH'}:
                severity = 'MODERATE'
            exists = (
                db.session.execute(
                    select(DrugInteraction).filter_by(medication_a_id=a, medication_b_id=b)
                )
                .scalars()
                .first()
            )
            if exists:
                exists.severity = severity
                exists.description = description
                exists.is_active = is_active
                exists.updated_at = datetime.now(UTC)
            else:
                db.session.add(
                    DrugInteraction(
                        medication_a_id=a,
                        medication_b_id=b,
                        severity=severity,
                        description=description,
                        is_active=is_active,
                        created_by=current_user.id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم حفظ التداخل', 'success')
            return redirect(url_for('medication.interactions'))
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            logging.exception("Error saving interaction: %s")
            flash('حدث خطأ في حفظ التداخل', 'error')
            return redirect(url_for('medication.interactions'))

    meds = (
        db.session.execute(
            select(Medication)
            .filter_by(is_active=True)
            .filter(Medication.tenant_id == current_user.tenant_id)
            .order_by(Medication.trade_name.asc())
            .limit(2000)
        )
        .scalars()
        .all()
    )
    rows = (
        db.session.execute(
            select(DrugInteraction).order_by(DrugInteraction.created_at.desc()).limit(500)
        )
        .scalars()
        .all()
    )
    return render_template('medication/interactions.html', medications=meds, interactions=rows)


@medication_bp.route('/interactions/<int:interaction_id>/toggle', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def toggle_interaction(interaction_id: int):
    row = (
        db.session.execute(select(DrugInteraction).filter(DrugInteraction.id == interaction_id))
        .scalars()
        .first()
    )
    if not row:
        return jsonify({'success': False, 'message': 'التداخل غير موجود'}), 404
    try:
        row.is_active = not bool(row.is_active)
        row.updated_at = datetime.now(UTC)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'is_active': bool(row.is_active)}), 200
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception("Error toggling interaction: %s")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
