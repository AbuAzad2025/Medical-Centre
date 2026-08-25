"""Procurement UI — purchase order lifecycle over ProcurementService.

Blueprint guarded by the 'inventory' module (pharmacy/manager roles reach it
through RBAC role gates on top of the module guard).
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.medication import Medication, Supplier
from services.procurement_service import ProcurementError, ProcurementService
from utils.decorators import role_required

procurement_bp = Blueprint('procurement', __name__)


@procurement_bp.route('/')
@login_required
@role_required('manager', 'admin', 'owner', 'super_admin', 'accountant')
def list_purchases():
    """PO list — every MedicationPurchase row is a PO line item."""
    purchases = ProcurementService.list_purchases()

    orders = {}
    for p in purchases:
        key = (p.supplier_id, str(p.purchase_date))
        o = orders.setdefault(
            key,
            {
                'supplier_id': p.supplier_id,
                'purchase_date': p.purchase_date,
                'items': [],
                'total': 0.0,
                'open_lines': 0,
            },
        )
        o['items'].append(p)
        o['total'] += float(p.purchase_price or 0) * (p.quantity or 0)
        if (p.remaining_quantity or 0) > 0:
            o['open_lines'] += 1

    suppliers = (
        db.session.execute(select(Supplier).filter_by(is_active=True).order_by(Supplier.name))
        .scalars()
        .all()
    )
    return render_template(
        'procurement/list.html',
        orders=sorted(orders.values(), key=lambda o: str(o['purchase_date']), reverse=True),
        suppliers=suppliers,
    )


@procurement_bp.route('/new', methods=['GET'])
@login_required
@role_required('manager', 'admin', 'owner', 'super_admin')
def new_po_form():
    medications = (
        db.session.execute(
            select(Medication).filter_by(is_active=True).order_by(Medication.trade_name)
        )
        .scalars()
        .all()
    )
    suppliers = (
        db.session.execute(select(Supplier).filter_by(is_active=True).order_by(Supplier.name))
        .scalars()
        .all()
    )
    return render_template('procurement/new.html', medications=medications, suppliers=suppliers)


@procurement_bp.route('/new', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'owner', 'super_admin')
def create_po():
    data = request.get_json(silent=True) or request.form

    supplier_id = int(data.get('supplier_id') or 0)
    items = []

    raw_items = data.get('items')
    if isinstance(raw_items, list):
        items = raw_items
    else:
        med_ids = request.form.getlist('medication_id[]')
        qtys = request.form.getlist('quantity[]')
        prices = request.form.getlist('purchase_price[]')
        batches = request.form.getlist('batch_number[]')
        expiries = request.form.getlist('expiry_date[]')
        for i in range(len(med_ids)):
            items.append(
                {
                    'medication_id': med_ids[i],
                    'quantity': qtys[i],
                    'purchase_price': prices[i],
                    'batch_number': batches[i],
                    'expiry_date': expiries[i] or None,
                }
            )

    try:
        result = ProcurementService.create_purchase_order(
            supplier_id=supplier_id, items=items, created_by=current_user.id
        )
    except ProcurementError as e:
        msg = {
            'no_items': 'أضف صنفاً واحداً على الأقل لأمر الشراء',
            'supplier_not_found': 'المورد غير موجود أو غير مفعل',
            'invalid_item': 'تحقق من الأصناف: الكمية والسعر ورقم التشغيلة مطلوبة',
        }.get(str(e), 'تعذر إنشاء أمر الشراء. حاول مرة أخرى.')
        if request.accept_mimetypes.best == 'application/json' or request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('procurement.new_po_form'))

    if request.is_json:
        return jsonify({'success': True, **result})
    flash(f'تم إنشاء أمر الشراء بنجاح ({result["item_count"]} صنف)', 'success')
    return redirect(url_for('procurement.list_purchases'))


@procurement_bp.route('/receive/<int:purchase_id>', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'owner', 'super_admin', 'pharmacist')
def receive_po(purchase_id):
    """Receive a PO line → stock increment.

    Idempotency: the service rejects lines already fully received
    (remaining_quantity == 0), so double submission cannot double-stock.
    """
    try:
        result = ProcurementService.receive_purchase(purchase_id, received_by=current_user.id)
    except ProcurementError as e:
        msg = {
            'purchase_not_found': 'أمر الشراء غير موجود',
            'already_received': 'تم استلام هذا الصنف مسبقاً — لا يمكن الاستلام مرتين',
        }.get(str(e), 'تعذر استلام أمر الشراء')
        return jsonify({'success': False, 'message': msg}), 409

    from models.audit_trail import AuditTrail

    db.session.add(
        AuditTrail(
            entity_type='system',
            entity_id=purchase_id,
            tenant_id=getattr(current_user, 'tenant_id', None),
            action='update',
            user_id=current_user.id,
            user_ip=request.remote_addr,
            description=f'استلام شراء: دواء #{result["medication_id"]} كمية {result["qty_received"]}',
        )
    )
    from utils.db_safety import safe_commit

    safe_commit(db.session, error_message='procurement audit write failed')

    return jsonify(
        {'success': True, 'message': f'تم استلام {result["qty_received"]} وحدة وإضافتها للمخزون'}
    )


@procurement_bp.route('/supplier/<int:supplier_id>/summary', methods=['GET'])
@login_required
@role_required('manager', 'admin', 'owner', 'super_admin')
def supplier_summary(supplier_id):
    try:
        return jsonify({'success': True, **ProcurementService.get_supplier_summary(supplier_id)})
    except ProcurementError:
        return jsonify({'success': False, 'message': 'المورد غير موجود'}), 404
