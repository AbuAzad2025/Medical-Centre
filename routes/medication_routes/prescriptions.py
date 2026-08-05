"""prescriptions routes - extracted from monolithic medication_routes.py"""

import logging
from datetime import UTC, datetime

# Imports
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.modules.workflows.pharmacy import PharmacyStockService
from app.shared.enums import PaymentStatus, PrescriptionState
from models.drug_interaction import DrugInteraction
from models.medication import Prescription
from routes.medication_routes import medication_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

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
        prescriptions = (
            db.session.execute(
                select(Prescription)
                .filter(Prescription.tenant_id == current_user.tenant_id)
                .order_by(Prescription.created_at.desc())
            )
            .scalars()
            .all()
        )

        return render_template('medication/prescriptions.html', prescriptions=prescriptions)

    except Exception:
        logging.exception('Error loading prescriptions: %s')
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
        q = select(Prescription)
        if visit_id:
            q = q.filter(Prescription.visit_id == visit_id)
        if patient_id:
            q = q.filter(Prescription.patient_id == patient_id)
        if status:
            q = q.filter(Prescription.status == status)
        items = (
            db.session.execute(q.order_by(Prescription.created_at.desc()).limit(50)).scalars().all()
        )
        data = []
        for p in items:
            data.append(
                {'id': p.id, 'visit_id': p.visit_id, 'patient_id': p.patient_id, 'status': p.status}
            )
        return jsonify({'success': True, 'prescriptions': data})
    except Exception:
        logging.exception('Error loading prescriptions api: %s')
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500


@medication_bp.route('/prescriptions/dispense/<int:prescription_id>', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def dispense_prescription(prescription_id):
    try:
        from models.medication import (
            Medication,
            Prescription,
            PrescriptionDispenseLog,
        )
        from models.visit import Visit

        prescription = (
            db.session.execute(
                select(Prescription).filter(
                    Prescription.id == prescription_id,
                    Prescription.tenant_id == current_user.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not prescription:
            return jsonify({'success': False, 'message': 'الوصفة غير موجودة'}), 404
        if prescription.status == PrescriptionState.DISPENSED:
            return jsonify({'success': False, 'message': 'تم صرف هذه الوصفة مسبقاً'}), 400
        visit_id = prescription.visit_id
        if visit_id:
            visit = (
                db.session.execute(
                    select(Visit).filter(
                        Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if visit:
                if visit.payment_status == PaymentStatus.PENDING and not visit.is_force_payment:
                    return jsonify(
                        {'success': False, 'message': 'يجب إتمام الدفع قبل صرف الأدوية'}
                    ), 402
                if visit.is_force_payment and not visit.force_payment_approved_by:
                    return jsonify(
                        {'success': False, 'message': 'الدفع القسري يحتاج موافقة المدير قبل الصرف'}
                    ), 403
        items = prescription.items.all()
        if not items:
            return jsonify({'success': False, 'message': 'لا توجد عناصر في الوصفة'}), 400
        med_ids = sorted(
            {int(it.medication_id) for it in items if getattr(it, 'medication_id', None)}
        )
        names = []
        for it in items:
            med = (
                db.session.execute(
                    select(Medication).filter(
                        Medication.id == it.medication_id,
                        Medication.tenant_id == current_user.tenant_id,
                    )
                )
                .scalars()
                .first()
            )
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
                from sqlalchemy import and_, or_

                conds = [
                    and_(DrugInteraction.medication_a_id == a, DrugInteraction.medication_b_id == b)
                    for a, b in pairs
                ]
                rows = (
                    db.session.execute(
                        select(DrugInteraction)
                        .filter(DrugInteraction.is_active)
                        .filter(or_(*conds))
                    )
                    .scalars()
                    .all()
                )
                for row in rows:
                    a = (
                        db.session.execute(
                            select(Medication).filter(
                                Medication.id == row.medication_a_id,
                                Medication.tenant_id == current_user.tenant_id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    b = (
                        db.session.execute(
                            select(Medication).filter(
                                Medication.id == row.medication_b_id,
                                Medication.tenant_id == current_user.tenant_id,
                            )
                        )
                        .scalars()
                        .first()
                    )
                    conflicts.append(
                        f'{a.trade_name if a else row.medication_a_id} ↔ {b.trade_name if b else row.medication_b_id} ({row.severity})'
                    )
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
        for it in items:
            med = (
                db.session.execute(
                    select(Medication).filter(
                        Medication.id == it.medication_id,
                        Medication.tenant_id == current_user.tenant_id,
                    )
                )
                .scalars()
                .first()
            )
            if med.expiry_date and med.is_expired():
                return jsonify(
                    {'success': False, 'message': f'الدواء {med.trade_name} منتهي الصلاحية'}
                ), 400
            if med.stock_quantity < it.quantity:
                return jsonify(
                    {'success': False, 'message': f'المخزون غير كافٍ للدواء {med.trade_name}'}
                ), 400
            if med.drug_interactions:
                text = (med.drug_interactions or '').lower()
                for tn, gn in names:
                    other_names = [tn.lower(), gn.lower()]
                    if any(n and n in text for n in other_names) and (med.trade_name != tn):
                        conflicts.append(f'{med.trade_name} ↔ {tn}')
        if conflicts:
            return jsonify(
                {
                    'success': False,
                    'message': 'تفاعلات دوائية محتملة: ' + ', '.join(sorted(set(conflicts))),
                }
            ), 400
        for it in items:
            med = (
                db.session.execute(
                    select(Medication)
                    .filter(
                        Medication.id == it.medication_id,
                        Medication.tenant_id == current_user.tenant_id,
                    )
                    .with_for_update()
                )
                .scalars()
                .first()
            )
            try:
                PharmacyStockService.adjust_stock(
                    medication_id=med.id,
                    quantity_change=-int(it.quantity or 0),
                    movement_type='sale',
                    reference_type='PrescriptionItem',
                    reference_id=it.id,
                    performed_by=current_user.id,
                    notes=f'Dispensed for prescription {prescription.id}',
                )
            except ValueError:
                return jsonify(
                    {'success': False, 'message': f'المخزون غير كافٍ للدواء {med.trade_name}'}
                ), 400
        prescription.status = PrescriptionState.DISPENSED
        prescription.updated_at = datetime.now(UTC)
        log_row = PrescriptionDispenseLog(
            prescription_id=prescription.id,
            patient_id=prescription.patient_id,
            visit_id=prescription.visit_id,
            dispensed_by=current_user.id,
            dispensed_at=datetime.now(UTC),
        )
        db.session.add(log_row)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        return jsonify({'success': True, 'message': 'تم صرف الوصفة'}), 200
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('Error dispensing prescription: %s')
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
