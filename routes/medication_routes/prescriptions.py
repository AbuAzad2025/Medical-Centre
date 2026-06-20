"""prescriptions routes - extracted from monolithic medication_routes.py"""

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
from services.prescription_service import prescription_service
from app_factory import db
import logging, json
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func


# =============================================
# PRESCRIPTIONS ROUTES
# =============================================

@medication_bp.route('/prescriptions')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'doctor')
def prescriptions():
    """الروشتات"""
    
    
    try:
        from models.medication import Prescription
        
        # جلب جميع الروشتات
        prescriptions = Prescription.query.order_by(Prescription.created_at.desc()).all()
        
        return render_template('medication/prescriptions.html', prescriptions=prescriptions)
    
    except Exception as e:
        logging.error(f"Error loading prescriptions: {str(e)}")
        flash('حدث خطأ في تحميل الروشتات', 'error')
        return redirect(url_for('medication.dashboard'))

@medication_bp.route('/api/prescriptions')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'doctor')
def api_prescriptions():
    try:
        visit_id = request.args.get('visit_id', type=int)
        patient_id = request.args.get('patient_id', type=int)
        status = request.args.get('status', type=str)
        q = Prescription.query
        if visit_id:
            q = q.filter(Prescription.visit_id == visit_id)
        if patient_id:
            q = q.filter(Prescription.patient_id == patient_id)
        if status:
            q = q.filter(Prescription.status == status)
        items = q.order_by(Prescription.created_at.desc()).limit(50).all()
        data = []
        for p in items:
            data.append({'id': p.id, 'visit_id': p.visit_id, 'patient_id': p.patient_id, 'status': p.status})
        return jsonify({'success': True, 'prescriptions': data})
    except Exception as e:
        logging.error(f"Error loading prescriptions api: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@medication_bp.route('/prescriptions/dispense/<int:prescription_id>', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def dispense_prescription(prescription_id):
    try:
        from models.medication import Prescription, Medication, PrescriptionDispenseLog
        from models.medication import PrescriptionItem
        from models.visit import Visit
        prescription = db.session.get(Prescription, prescription_id)
        if not prescription:
            return jsonify({'success': False, 'message': 'الوصفة غير موجودة'}), 404
        if prescription.status == 'dispensed':
            return jsonify({'success': False, 'message': 'تم صرف هذه الوصفة مسبقاً'}), 400
        visit_id = prescription.visit_id
        if visit_id:
            visit = db.session.get(Visit, visit_id)
            if visit:
                if visit.payment_status == 'PENDING' and not visit.is_force_payment:
                    return jsonify({'success': False, 'message': 'يجب إتمام الدفع قبل صرف الأدوية'}), 402
                if visit.is_force_payment and not visit.force_payment_approved_by:
                    return jsonify({'success': False, 'message': 'الدفع القسري يحتاج موافقة المدير قبل الصرف'}), 403
        items = prescription.items.all()
        if not items:
            return jsonify({'success': False, 'message': 'لا توجد عناصر في الوصفة'}), 400
        med_ids = sorted({int(it.medication_id) for it in items if getattr(it, 'medication_id', None)})
        names = []
        for it in items:
            med = db.session.get(Medication, it.medication_id)
            if not med:
                return jsonify({'success': False, 'message': 'دواء غير موجود في النظام'}), 404
            names.append((med.trade_name or '', med.generic_name or ''))
        conflicts = []
        try:
            pairs = []
            for i in range(len(med_ids)):
                for j in range(i + 1, len(med_ids)):
                    a = med_ids[i]
                    b = med_ids[j]
                    pairs.append((a, b))
            if pairs:
                from sqlalchemy import or_, and_
                conds = [and_(DrugInteraction.medication_a_id == a, DrugInteraction.medication_b_id == b) for a, b in pairs]
                rows = DrugInteraction.query.filter(DrugInteraction.is_active == True).filter(or_(*conds)).all()
                for row in rows:
                    a = db.session.get(Medication, row.medication_a_id)
                    b = db.session.get(Medication, row.medication_b_id)
                    conflicts.append(f'{a.trade_name if a else row.medication_a_id} ↔ {b.trade_name if b else row.medication_b_id} ({row.severity})')
        except Exception:

            logging.warning(f"Error in {__name__}: {e}")
        for it in items:
            med = db.session.get(Medication, it.medication_id)
            if med.expiry_date and med.is_expired():
                return jsonify({'success': False, 'message': f'الدواء {med.trade_name} منتهي الصلاحية'}), 400
            if med.stock_quantity < it.quantity:
                return jsonify({'success': False, 'message': f'المخزون غير كافٍ للدواء {med.trade_name}'}), 400
            if med.drug_interactions:
                text = (med.drug_interactions or '').lower()
                for tn, gn in names:
                    other_names = [tn.lower(), gn.lower()]
                    if any(n and n in text for n in other_names) and (med.trade_name != tn):
                        conflicts.append(f'{med.trade_name} ↔ {tn}')
        if conflicts:
            return jsonify({'success': False, 'message': 'تفاعلات دوائية محتملة: ' + ', '.join(sorted(set(conflicts)))}), 400
        for it in items:
            med = db.session.get(Medication, it.medication_id)
            med.stock_quantity = int(med.stock_quantity or 0) - int(it.quantity or 0)
            med.updated_at = datetime.now(timezone.utc)
            db.session.add(med)
        prescription.status = 'dispensed'
        prescription.updated_at = datetime.now(timezone.utc)
        log_row = PrescriptionDispenseLog(
            prescription_id=prescription.id,
            patient_id=prescription.patient_id,
            visit_id=prescription.visit_id,
            dispensed_by=current_user.id,
            dispensed_at=datetime.now(timezone.utc)
        )
        db.session.add(log_row)
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم صرف الوصفة'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error dispensing prescription: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
