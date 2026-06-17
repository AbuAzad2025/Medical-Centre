"""inventory routes - extracted from monolithic medication_routes.py"""

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
# INVENTORY ROUTES
# =============================================

@medication_bp.route('/stock-alerts')
@login_required
def stock_alerts():
    """تنبيهات المخزون"""
    if current_user.role not in ['pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # الأدوية منخفضة المخزون
        low_stock = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).all()
        
        # الأدوية المنتهية الصلاحية قريباً
        expiring_soon = Medication.query.filter(
            Medication.expiry_date <= datetime.now() + timedelta(days=30)
        ).all()
        
        return render_template('medication/stock_alerts.html', 
                             low_stock=low_stock,
                             expiring_soon=expiring_soon)
    except Exception as e:
        logging.error(f"Error loading stock alerts: {str(e)}")
        flash('حدث خطأ في تحميل تنبيهات المخزون', 'error')
        return redirect(url_for('medication.dashboard'))

@medication_bp.route('/supply-requests')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def supply_requests():
    status = (request.args.get('status') or '').strip().upper()
    q = MedicationSupplyRequest.query
    if status:
        q = q.filter(MedicationSupplyRequest.status == status)
    requests_list = q.order_by(MedicationSupplyRequest.created_at.desc()).limit(200).all()
    return render_template('medication/supply_requests.html', requests=requests_list, selected_status=status)


@medication_bp.route('/supply-requests/create', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def create_supply_request():
    if request.method == 'POST':
        try:
            med_ids = request.form.getlist('selected_medication_id[]')
            notes = (request.form.get('notes') or '').strip() or None

            items = []
            for mid_raw in (med_ids or []):
                mid_raw = (mid_raw or '').strip()
                if not mid_raw.isdigit():
                    continue
                mid = int(mid_raw)
                qraw = (request.form.get(f'requested_qty_{mid}') or '').strip()
                rq = int(qraw) if qraw.isdigit() else 0
                if rq <= 0:
                    continue
                med = db.session.get(Medication, mid)
                if not med:
                    continue
                items.append((med, rq))

            if not items:
                flash('يرجى اختيار أدوية وإدخال كميات صحيحة', 'warning')
                return redirect(url_for('medication.create_supply_request'))

            req = MedicationSupplyRequest(
                request_number=_generate_supply_request_number(),
                status='DRAFT',
                notes=notes,
                created_by=current_user.id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(req)
            db.session.flush()

            for med, rq in items:
                db.session.add(MedicationSupplyRequestItem(
                    request_id=req.id,
                    medication_id=med.id,
                    current_stock=int(med.stock_quantity or 0),
                    minimum_stock=int(med.minimum_stock or 0),
                    requested_qty=rq,
                    created_at=datetime.now(timezone.utc)
                ))
            db.session.commit()
            flash('تم إنشاء طلب التوريد', 'success')
            return redirect(url_for('medication.view_supply_request', request_id=req.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating supply request: {str(e)}")
            flash('حدث خطأ في إنشاء طلب التوريد', 'error')
            return redirect(url_for('medication.supply_requests'))

    low_stock = Medication.query.filter(Medication.stock_quantity <= Medication.minimum_stock).order_by(Medication.trade_name.asc()).all()
    suggested = {}
    for m in low_stock:
        cur = int(m.stock_quantity or 0)
        minv = int(m.minimum_stock or 0)
        target = max(minv * 2, 1)
        suggested[m.id] = max(target - cur, 1) if cur <= minv else 1
    return render_template('medication/create_supply_request.html', low_stock=low_stock, suggested=suggested)


@medication_bp.route('/supply-requests/<int:request_id>')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def view_supply_request(request_id: int):
    req = db.session.get(MedicationSupplyRequest, request_id)
    if not req:
        flash('طلب التوريد غير موجود', 'error')
        return redirect(url_for('medication.supply_requests'))
    return render_template('medication/supply_request_detail.html', req=req)


@medication_bp.route('/supply-requests/<int:request_id>/approve', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def approve_supply_request(request_id: int):
    req = db.session.get(MedicationSupplyRequest, request_id)
    if not req:
        return jsonify({'success': False, 'message': 'غير موجود'}), 404
    if req.status not in {'DRAFT'}:
        return jsonify({'success': False, 'message': 'لا يمكن اعتماد هذه الحالة'}), 400
    try:
        for it in req.items:
            if it.approved_qty is None:
                it.approved_qty = it.requested_qty
        req.status = 'APPROVED'
        req.approved_by = current_user.id
        req.approved_at = datetime.now(timezone.utc)
        req.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error approving supply request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500


@medication_bp.route('/supply-requests/<int:request_id>/fulfill', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def fulfill_supply_request(request_id: int):
    req = db.session.get(MedicationSupplyRequest, request_id)
    if not req:
        return jsonify({'success': False, 'message': 'غير موجود'}), 404
    if req.status not in {'APPROVED'}:
        return jsonify({'success': False, 'message': 'لا يمكن تنفيذ هذه الحالة'}), 400
    try:
        item_ids = request.form.getlist('item_id[]')
        qtys = request.form.getlist('fulfilled_qty[]')
        updates = {}
        for i in range(max(len(item_ids), len(qtys), 0)):
            iid_raw = (item_ids[i] if i < len(item_ids) else '').strip()
            qraw = (qtys[i] if i < len(qtys) else '').strip()
            if not (iid_raw.isdigit() and qraw.isdigit()):
                continue
            updates[int(iid_raw)] = int(qraw)

        for it in req.items:
            fq = updates.get(it.id)
            if fq is None:
                continue
            if fq < 0:
                fq = 0
            it.fulfilled_qty = fq
            med = db.session.get(Medication, it.medication_id)
            if med and fq:
                med.stock_quantity = int(med.stock_quantity or 0) + int(fq)
                med.updated_at = datetime.now(timezone.utc)
                db.session.add(med)

        req.status = 'FULFILLED'
        req.fulfilled_by = current_user.id
        req.fulfilled_at = datetime.now(timezone.utc)
        req.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error fulfilling supply request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
