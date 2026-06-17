"""interactions routes - extracted from monolithic medication_routes.py"""

from routes.medication_routes import medication_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.medication import Medication, Prescription
from models.patient import Patient
from models.visit import Visit
from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from models.drug_interaction import DrugInteraction
from app_factory import db
import logging, json
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func


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
            exists = DrugInteraction.query.filter_by(medication_a_id=a, medication_b_id=b).first()
            if exists:
                exists.severity = severity
                exists.description = description
                exists.is_active = is_active
                exists.updated_at = datetime.now(timezone.utc)
            else:
                db.session.add(DrugInteraction(
                    medication_a_id=a,
                    medication_b_id=b,
                    severity=severity,
                    description=description,
                    is_active=is_active,
                    created_by=current_user.id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                ))
            db.session.commit()
            flash('تم حفظ التداخل', 'success')
            return redirect(url_for('medication.interactions'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error saving interaction: {str(e)}")
            flash('حدث خطأ في حفظ التداخل', 'error')
            return redirect(url_for('medication.interactions'))

    meds = Medication.query.filter_by(is_active=True).order_by(Medication.trade_name.asc()).limit(2000).all()
    rows = DrugInteraction.query.order_by(DrugInteraction.created_at.desc()).limit(500).all()
    return render_template('medication/interactions.html', medications=meds, interactions=rows)


@medication_bp.route('/interactions/<int:interaction_id>/toggle', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def toggle_interaction(interaction_id: int):
    row = db.session.get(DrugInteraction, interaction_id)
    if not row:
        return jsonify({'success': False, 'message': 'غير موجود'}), 404
    try:
        row.is_active = not bool(row.is_active)
        row.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True, 'is_active': bool(row.is_active)}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error toggling interaction: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
