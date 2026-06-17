"""external routes - extracted from monolithic medication_routes.py"""

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
# EXTERNAL ROUTES
# =============================================

@medication_bp.route('/api/external-drug-import', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def api_external_drug_import():
    try:
        data = request.get_json() or {}
        items = data.get('items') or []
        imported = 0
        updated = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            trade_name = (item.get('trade_name') or '').strip()
            scientific_name = (item.get('scientific_name') or '').strip() or trade_name
            if not trade_name:
                continue
            med = Medication.query.filter(
                Medication.trade_name == trade_name
            ).first()
            if not med:
                med = Medication(
                    trade_name=trade_name,
                    scientific_name=scientific_name,
                    generic_name=item.get('generic_name'),
                    dosage_form=item.get('dosage_form') or 'tablet',
                    strength=item.get('strength') or '',
                    manufacturer=item.get('manufacturer'),
                    price=item.get('price') or 0,
                    category=item.get('category'),
                    description=item.get('description'),
                    standard_instructions=item.get('standard_instructions'),
                    side_effects=item.get('side_effects'),
                    contraindications=item.get('contraindications'),
                    drug_interactions=item.get('drug_interactions'),
                    stock_quantity=item.get('stock_quantity') or 0,
                    minimum_stock=item.get('minimum_stock') or 10,
                )
                db.session.add(med)
                imported += 1
            else:
                med.scientific_name = scientific_name or med.scientific_name
                med.generic_name = item.get('generic_name') or med.generic_name
                med.dosage_form = item.get('dosage_form') or med.dosage_form
                med.strength = item.get('strength') or med.strength
                med.manufacturer = item.get('manufacturer') or med.manufacturer
                if item.get('price') is not None:
                    med.price = item.get('price')
                med.category = item.get('category') or med.category
                med.description = item.get('description') or med.description
                med.standard_instructions = item.get('standard_instructions') or med.standard_instructions
                med.side_effects = item.get('side_effects') or med.side_effects
                med.contraindications = item.get('contraindications') or med.contraindications
                med.drug_interactions = item.get('drug_interactions') or med.drug_interactions
                if item.get('stock_quantity') is not None:
                    med.stock_quantity = item.get('stock_quantity')
                if item.get('minimum_stock') is not None:
                    med.minimum_stock = item.get('minimum_stock')
                updated += 1
        db.session.commit()
        return jsonify({'success': True, 'imported': imported, 'updated': updated}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error importing external drug catalog: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر استيراد الدليل الدوائي'}), 500

@medication_bp.route('/api/external-drug-search')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'doctor', 'nurse')
def api_external_drug_search():
    try:
        q = (request.args.get('q') or '').strip()
        if not q:
            return jsonify({'success': True, 'items': []}), 200
        meds = Medication.query.filter(
            Medication.trade_name.contains(q) |
            Medication.scientific_name.contains(q) |
            Medication.generic_name.contains(q)
        ).order_by(Medication.trade_name.asc()).limit(20).all()
        return jsonify({'success': True, 'items': [m.to_dict() for m in meds]}), 200
    except Exception as e:
        logging.error(f"Error searching external drug catalog: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر البحث حالياً'}), 500

@medication_bp.route('/consumption-report')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def consumption_report():
    from models.medication import Prescription, PrescriptionItem, PrescriptionDispenseLog
    from models.department import Department
    from models.user import User

    group = (request.args.get('group') or 'medication').strip().lower()
    start_raw = (request.args.get('start_date') or '').strip()
    end_raw = (request.args.get('end_date') or '').strip()
    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
    except Exception:
        start_date = date.today() - timedelta(days=30)
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
    except Exception:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    q = db.session.query(
        func.sum(PrescriptionItem.quantity).label('total_qty'),
        func.sum(PrescriptionItem.total_price).label('total_value'),
        func.count(func.distinct(Prescription.id)).label('rx_count')
    ).select_from(PrescriptionDispenseLog).join(
        Prescription, Prescription.id == PrescriptionDispenseLog.prescription_id
    ).join(
        PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id
    ).filter(
        PrescriptionDispenseLog.dispensed_at >= start_dt,
        PrescriptionDispenseLog.dispensed_at <= end_dt
    )

    rows = []
    if group == 'doctor':
        q2 = q.add_columns(User.id.label('key_id'), User.full_name.label('label')).join(User, User.id == Prescription.doctor_id).group_by(User.id, User.full_name).order_by(func.sum(PrescriptionItem.total_price).desc())
        rows = [{'label': r.label, 'total_qty': int(r.total_qty or 0), 'total_value': float(r.total_value or 0), 'rx_count': int(r.rx_count or 0)} for r in q2.all()]
    elif group == 'department':
        q2 = q.add_columns(Department.id.label('key_id'), Department.name_ar.label('label')).join(Visit, Visit.id == PrescriptionDispenseLog.visit_id).join(Department, Department.id == Visit.department_id).group_by(Department.id, Department.name_ar).order_by(func.sum(PrescriptionItem.total_price).desc())
        rows = [{'label': (r.label or 'غير محدد'), 'total_qty': int(r.total_qty or 0), 'total_value': float(r.total_value or 0), 'rx_count': int(r.rx_count or 0)} for r in q2.all()]
    else:
        q2 = q.add_columns(Medication.id.label('key_id'), Medication.trade_name.label('label')).join(Medication, Medication.id == PrescriptionItem.medication_id).group_by(Medication.id, Medication.trade_name).order_by(func.sum(PrescriptionItem.total_price).desc())
        rows = [{'label': r.label, 'total_qty': int(r.total_qty or 0), 'total_value': float(r.total_value or 0), 'rx_count': int(r.rx_count or 0)} for r in q2.all()]

    return render_template('medication/consumption_report.html', rows=rows, group=group, start_date=start_date, end_date=end_date)

# ==================== الميزات الذكية للصيدلية ====================
