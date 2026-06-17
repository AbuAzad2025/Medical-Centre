"""reagents routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from services.lab_service import lab_service
from app_factory import db
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# REAGENTS ROUTES
# =============================================

@lab_bp.route('/reagents')
@login_required
@role_required('lab', 'admin', 'manager')
def reagents():
    search = (request.args.get('search') or '').strip()
    stock = (request.args.get('stock') or '').strip().lower()
    expiry = (request.args.get('expiry') or '').strip().lower()

    q = LabReagent.query
    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                LabReagent.name.ilike(like),
                LabReagent.supplier.ilike(like),
                LabReagent.lot_number.ilike(like)
            )
        )
    if stock == 'low':
        q = q.filter(LabReagent.stock_quantity <= LabReagent.minimum_stock, LabReagent.stock_quantity > 0)
    elif stock == 'out':
        q = q.filter(LabReagent.stock_quantity <= 0)
    elif stock == 'normal':
        q = q.filter(LabReagent.stock_quantity > LabReagent.minimum_stock)

    today = date.today()
    soon_date = today + timedelta(days=30)
    if expiry == 'expired':
        q = q.filter(LabReagent.expiry_date.isnot(None), LabReagent.expiry_date < today)
    elif expiry == 'soon':
        q = q.filter(LabReagent.expiry_date.isnot(None), LabReagent.expiry_date <= soon_date)

    reagents_list = q.order_by(LabReagent.is_active.desc(), LabReagent.name.asc()).limit(1000).all()
    return render_template('lab/reagents.html', reagents=reagents_list, search=search, stock=stock, expiry=expiry, today=today, soon_date=soon_date)


@lab_bp.route('/reagents/add', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'admin', 'manager')
def add_reagent():
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            supplier = (request.form.get('supplier') or '').strip() or None
            lot_number = (request.form.get('lot_number') or '').strip() or None
            unit = (request.form.get('unit') or '').strip() or None
            stock_quantity = request.form.get('stock_quantity')
            minimum_stock = request.form.get('minimum_stock')
            expiry_raw = (request.form.get('expiry_date') or '').strip()
            notes = (request.form.get('notes') or '').strip() or None
            is_active = (request.form.get('is_active') or '') == 'on'

            if not name:
                flash('يرجى إدخال اسم المادة', 'warning')
                return redirect(url_for('lab.add_reagent'))
            try:
                stock_quantity = int(stock_quantity) if stock_quantity is not None and str(stock_quantity).strip() != '' else 0
            except Exception:
                stock_quantity = 0
            try:
                minimum_stock = int(minimum_stock) if minimum_stock is not None and str(minimum_stock).strip() != '' else 0
            except Exception:
                minimum_stock = 0

            expiry_date = None
            if expiry_raw:
                try:
                    expiry_date = datetime.strptime(expiry_raw, '%Y-%m-%d').date()
                except Exception:
                    expiry_date = None

            db.session.add(LabReagent(
                name=name,
                supplier=supplier,
                lot_number=lot_number,
                unit=unit,
                stock_quantity=stock_quantity,
                minimum_stock=minimum_stock,
                expiry_date=expiry_date,
                notes=notes,
                is_active=is_active
            ))
            db.session.commit()
            flash('تمت إضافة المادة', 'success')
            return redirect(url_for('lab.reagents'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding reagent: {str(e)}")
            flash('حدث خطأ أثناء الإضافة', 'error')
            return redirect(url_for('lab.add_reagent'))
    return render_template('lab/reagent_form.html', reagent=None)


@lab_bp.route('/reagents/<int:reagent_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'admin', 'manager')
def edit_reagent(reagent_id: int):
    reagent = db.session.get(LabReagent, reagent_id)
    if not reagent:
        flash('المادة غير موجودة', 'error')
        return redirect(url_for('lab.reagents'))
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            supplier = (request.form.get('supplier') or '').strip() or None
            lot_number = (request.form.get('lot_number') or '').strip() or None
            unit = (request.form.get('unit') or '').strip() or None
            stock_quantity = request.form.get('stock_quantity')
            minimum_stock = request.form.get('minimum_stock')
            expiry_raw = (request.form.get('expiry_date') or '').strip()
            notes = (request.form.get('notes') or '').strip() or None
            is_active = (request.form.get('is_active') or '') == 'on'

            if not name:
                flash('يرجى إدخال اسم المادة', 'warning')
                return redirect(url_for('lab.edit_reagent', reagent_id=reagent_id))
            try:
                stock_quantity = int(stock_quantity) if stock_quantity is not None and str(stock_quantity).strip() != '' else 0
            except Exception:
                stock_quantity = 0
            try:
                minimum_stock = int(minimum_stock) if minimum_stock is not None and str(minimum_stock).strip() != '' else 0
            except Exception:
                minimum_stock = 0

            expiry_date = None
            if expiry_raw:
                try:
                    expiry_date = datetime.strptime(expiry_raw, '%Y-%m-%d').date()
                except Exception:
                    expiry_date = None

            reagent.name = name
            reagent.supplier = supplier
            reagent.lot_number = lot_number
            reagent.unit = unit
            reagent.stock_quantity = stock_quantity
            reagent.minimum_stock = minimum_stock
            reagent.expiry_date = expiry_date
            reagent.notes = notes
            reagent.is_active = is_active
            reagent.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash('تم تحديث المادة', 'success')
            return redirect(url_for('lab.reagents'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editing reagent: {str(e)}")
            flash('حدث خطأ أثناء التحديث', 'error')
            return redirect(url_for('lab.edit_reagent', reagent_id=reagent_id))
    return render_template('lab/reagent_form.html', reagent=reagent)
