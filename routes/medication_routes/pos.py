"""Pharmacy POS and Sales routes"""
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from sqlalchemy import func
from decimal import Decimal
from datetime import datetime, timezone, date
import logging, json

from routes.medication_routes import medication_bp
from models.medication import Medication, PharmacySale, PharmacySaleItem, PharmacyReturn
from app_factory import db
from app.shared.pos_charge import execute_pos_charge
from app.shared.user_messages import user_message
from services.pos_terminal_service import PosTerminalService


@medication_bp.route('/pos')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def pos():
    """Point of Sale interface"""
    medications = Medication.query.filter(
        Medication.tenant_id == current_user.tenant_id,
        Medication.is_active == True,
        Medication.stock_quantity > 0
    ).order_by(Medication.trade_name).all()
    return render_template(
        'pharmacy/pos.html',
        medications=medications,
        pos_enabled=PosTerminalService.is_enabled(),
    )


@medication_bp.route('/pos/charge', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def pharmacy_pos_charge():
    """Charge card via local POS terminal (same device as reception)."""
    amount_raw = None
    if request.is_json:
        amount_raw = (request.json or {}).get('amount')
    else:
        amount_raw = request.form.get('amount')
    result, status = execute_pos_charge(amount_raw)
    return jsonify(result), status


@medication_bp.route('/api/medications/search')
@login_required
def api_medications_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify([])
    items = Medication.query.filter(
        Medication.tenant_id == current_user.tenant_id,
        Medication.is_active == True,
        Medication.stock_quantity > 0,
        db.or_(
            Medication.trade_name.ilike(f'%{q}%'),
            Medication.scientific_name.ilike(f'%{q}%'),
            Medication.generic_name.ilike(f'%{q}%'),
        )
    ).order_by(Medication.trade_name).limit(20).all()
    data = [{
        'id': m.id,
        'trade_name': m.trade_name,
        'scientific_name': m.scientific_name,
        'price': float(m.price or 0),
        'stock': m.stock_quantity or 0,
        'dosage': m.get_dosage_display(),
        'category': m.category or '',
    } for m in items]
    return jsonify(data)


@medication_bp.route('/pos/sell', methods=['POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def pos_sell():
    """Process a POS sale (no patient required)"""
    try:
        data = request.get_json(force=True)
        if not data or 'items' not in data or not data['items']:
            return jsonify({'success': False, 'message': 'لا توجد أصناف في الفاتورة'}), 400

        items_data = data['items']
        customer_name = data.get('customer_name', '').strip()
        notes = data.get('notes', '').strip()
        payment_method = (data.get('payment_method') or 'cash').strip().lower()
        card_last_digits = (data.get('card_last_digits') or '').strip() or None
        transaction_id = (data.get('transaction_id') or '').strip() or None

        if payment_method in ('card', 'visa', 'mada') and not transaction_id:
            return jsonify({
                'success': False,
                'message': 'يرجى تحصيل المبلغ عبر جهاز البطاقة قبل إتمام البيع',
            }), 400

        sale = PharmacySale(
            tenant_id=current_user.tenant_id,
            total_amount=0,
            payment_method=payment_method,
            card_last_digits=card_last_digits,
            transaction_id=transaction_id,
            status='completed',
            customer_name=customer_name or None,
            notes=notes,
            created_by=current_user.id,
        )
        db.session.add(sale)
        db.session.flush()

        total = Decimal('0.00')
        sale_items = []
        for idx, item in enumerate(items_data):
            med_id = item.get('medication_id')
            qty = int(item.get('quantity', 0))
            if not med_id or qty < 1:
                continue

            med = Medication.query.filter(
                Medication.tenant_id == current_user.tenant_id,
                Medication.id == med_id
            ).first()
            if not med:
                return jsonify({'success': False, 'message': f'الدواء غير موجود (الرقم {med_id})'}), 400
            if med.stock_quantity < qty:
                return jsonify({'success': False, 'message': f'المخزون غير كافٍ لـ {med.trade_name} (المتوفر: {med.stock_quantity})'}), 400

            unit_price = Decimal(str(med.price or 0))
            total_price = unit_price * qty

            sale_item = PharmacySaleItem(
                tenant_id=current_user.tenant_id,
                sale_id=sale.id,
                medication_id=med.id,
                medication_name=med.trade_name,
                quantity=qty,
                unit_price=unit_price,
                total_price=total_price,
            )
            db.session.add(sale_item)
            sale_items.append(sale_item)

            med.stock_quantity -= qty
            med.updated_at = datetime.now(timezone.utc)

            total += total_price

        sale.total_amount = total
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'تمت عملية البيع بنجاح',
            'sale_id': sale.id,
            'sale_number': sale.sale_number,
            'total': float(total),
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"POS sell error: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ أثناء عملية البيع'}), 500


@medication_bp.route('/sales-history')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'accountant')
def sales_history():
    page = request.args.get('page', 1, type=int)
    per_page = 25
    pagination = PharmacySale.query.filter(
        PharmacySale.tenant_id == current_user.tenant_id
    ).order_by(
        PharmacySale.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    return render_template('pharmacy/sales_history.html', pagination=pagination)


@medication_bp.route('/sales/<int:sale_id>')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'accountant')
def sale_detail(sale_id):
    sale = PharmacySale.query.filter(
        PharmacySale.tenant_id == current_user.tenant_id,
        PharmacySale.id == sale_id
    ).first()
    if not sale:
        flash('الفاتورة غير موجودة', 'error')
        return redirect(url_for('medication.sales_history'))
    return render_template('pharmacy/sale_receipt.html', sale=sale)


@medication_bp.route('/sales/api/list')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def api_sales_list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    q = PharmacySale.query.filter(PharmacySale.tenant_id == current_user.tenant_id)
    if date_from:
        try:
            q = q.filter(PharmacySale.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
        except:
            pass
    if date_to:
        try:
            q = q.filter(PharmacySale.created_at <= datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except:
            pass
    pagination = q.order_by(PharmacySale.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    data = [{
        'id': s.id,
        'sale_number': s.sale_number or f'#{s.id:06d}',
        'customer_name': s.notes or '-',
        'total': float(s.total_amount or 0),
        'items_count': len(s.items),
        'created_at': s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '',
        'status': s.status,
    } for s in pagination.items]
    return jsonify({
        'success': True,
        'data': data,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page,
    })


@medication_bp.route('/sales/api/totals')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def api_sales_totals():
    today = date.today()
    base_q = db.session.query(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
        PharmacySale.tenant_id == current_user.tenant_id
    )
    today_sales = base_q.filter(func.date(PharmacySale.created_at) == today).scalar()
    month_sales = db.session.query(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
        PharmacySale.tenant_id == current_user.tenant_id,
        func.extract('month', PharmacySale.created_at) == today.month,
        func.extract('year', PharmacySale.created_at) == today.year
    ).scalar()
    total_sales = db.session.query(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
        PharmacySale.tenant_id == current_user.tenant_id
    ).scalar()
    return jsonify({
        'success': True,
        'today': float(today_sales),
        'month': float(month_sales),
        'total': float(total_sales),
    })


@medication_bp.route('/sales/api/report')
@login_required
@role_required('pharmacist', 'admin', 'manager', 'accountant')
def api_sales_report():
    from_date = request.args.get('from', '')
    to_date = request.args.get('to', '')
    q = db.session.query(
        func.date(PharmacySale.created_at).label('sale_date'),
        func.count(PharmacySale.id).label('count'),
        func.sum(PharmacySale.total_amount).label('total'),
    ).filter(PharmacySale.tenant_id == current_user.tenant_id)
    if from_date:
        try:
            q = q.filter(func.date(PharmacySale.created_at) >= datetime.strptime(from_date, '%Y-%m-%d').date())
        except:
            pass
    if to_date:
        try:
            q = q.filter(func.date(PharmacySale.created_at) <= datetime.strptime(to_date, '%Y-%m-%d').date())
        except:
            pass
    rows = q.group_by(func.date(PharmacySale.created_at)).order_by(func.date(PharmacySale.created_at).desc()).all()
    data = [{
        'date': str(r.sale_date),
        'count': r.count,
        'total': float(r.total or 0),
    } for r in rows]
    return jsonify({'success': True, 'data': data})


@medication_bp.route('/sales/<int:sale_id>/receipt')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def sale_receipt(sale_id):
    sale = PharmacySale.query.filter(
        PharmacySale.tenant_id == current_user.tenant_id,
        PharmacySale.id == sale_id
    ).first()
    if not sale:
        return jsonify({'success': False, 'message': 'الفاتورة غير موجودة'}), 404
    data = {
        'id': sale.id,
        'sale_number': sale.sale_number or f'#{sale.id:06d}',
        'total': float(sale.total_amount or 0),
        'items': [{
            'medication_name': i.medication_name,
            'quantity': i.quantity,
            'unit_price': float(i.unit_price or 0),
            'total_price': float(i.total_price or 0),
        } for i in sale.items],
        'created_at': sale.created_at.strftime('%Y-%m-%d %H:%M') if sale.created_at else '',
        'status': sale.status,
    }
    return jsonify({'success': True, 'sale': data})
