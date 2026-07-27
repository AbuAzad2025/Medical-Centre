"""Pharmacy Supplier management routes"""
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from datetime import datetime, timezone
import logging

from routes.medication_routes import medication_bp
from models.medication import Supplier, MedicationPurchase, Medication
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from sqlalchemy import select


@medication_bp.route('/suppliers')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def suppliers():
    suppliers = db.session.execute(select(Supplier).filter(
        Supplier.tenant_id == current_user.tenant_id
    ).order_by(Supplier.name)).scalars().all()
    return render_template('pharmacy/suppliers.html', suppliers=suppliers)


@medication_bp.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def add_supplier():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('اسم المورد مطلوب', 'error')
            return render_template('pharmacy/add_supplier.html')
        try:
            supplier = Supplier(
                tenant_id=current_user.tenant_id,
                name=name,
                contact_person=request.form.get('contact_person', '').strip(),
                phone=request.form.get('phone', '').strip(),
                email=request.form.get('email', '').strip(),
                address=request.form.get('address', '').strip(),
                tax_id=request.form.get('tax_id', '').strip(),
                notes=request.form.get('notes', '').strip(),
            )
            db.session.add(supplier)
            safe_commit(db.session, error_message="database commit failed", reraise=True)
            flash('تم إضافة المورد بنجاح', 'success')
            return redirect(url_for('medication.suppliers'))
        except Exception as e:
            safe_rollback(db.session, error_message="database rollback")
            flash('حدث خطأ في إضافة المورد', 'error')
    return render_template('pharmacy/add_supplier.html')


@medication_bp.route('/suppliers/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def edit_supplier(supplier_id):
    supplier = db.session.execute(select(Supplier).filter(
        Supplier.tenant_id == current_user.tenant_id,
        Supplier.id == supplier_id
    )).scalars().first()
    if not supplier:
        flash('المورد غير موجود', 'error')
        return redirect(url_for('medication.suppliers'))
    if request.method == 'POST':
        try:
            supplier.name = request.form.get('name', '').strip()
            supplier.contact_person = request.form.get('contact_person', '').strip()
            supplier.phone = request.form.get('phone', '').strip()
            supplier.email = request.form.get('email', '').strip()
            supplier.address = request.form.get('address', '').strip()
            supplier.tax_id = request.form.get('tax_id', '').strip()
            supplier.notes = request.form.get('notes', '').strip()
            supplier.updated_at = datetime.now(timezone.utc)
            safe_commit(db.session, error_message="database commit failed", reraise=True)
            flash('تم تحديث المورد بنجاح', 'success')
            return redirect(url_for('medication.suppliers'))
        except Exception as e:
            safe_rollback(db.session, error_message="database rollback")
            flash('حدث خطأ في تحديث المورد', 'error')
    return render_template('pharmacy/add_supplier.html', supplier=supplier)


@medication_bp.route('/suppliers/<int:supplier_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'manager')
def delete_supplier(supplier_id):
    supplier = db.session.execute(select(Supplier).filter(
        Supplier.tenant_id == current_user.tenant_id,
        Supplier.id == supplier_id
    )).scalars().first()
    if not supplier:
        flash('المورد غير موجود', 'error')
        return redirect(url_for('medication.suppliers'))
    try:
        db.session.delete(supplier)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        flash('تم حذف المورد بنجاح', 'success')
        return redirect(url_for('medication.suppliers'))
    except Exception as e:
        safe_rollback(db.session, error_message="database rollback")
        flash('حدث خطأ في حذف المورد', 'error')
        return redirect(url_for('medication.suppliers'))


@medication_bp.route('/purchases')
@login_required
@role_required('pharmacist', 'admin', 'manager')
def purchases():
    purchases = db.session.execute(select(MedicationPurchase).filter(
        MedicationPurchase.tenant_id == current_user.tenant_id
    ).order_by(MedicationPurchase.created_at.desc())).scalars().all()
    return render_template('pharmacy/purchases.html', purchases=purchases)


@medication_bp.route('/purchases/add', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def add_purchase():
    if request.method == 'POST':
        medication_id = request.form.get('medication_id', type=int)
        supplier_id = request.form.get('supplier_id', type=int)
        batch_number = request.form.get('batch_number', '').strip()
        quantity = request.form.get('quantity', 0, type=int)
        purchase_price = request.form.get('purchase_price', 0, type=float)
        selling_price = request.form.get('selling_price', 0, type=float)
        expiry_date_str = request.form.get('expiry_date', '').strip()
        invoice_number = request.form.get('invoice_number', '').strip()
        notes = request.form.get('notes', '').strip()

        if not medication_id or not batch_number or not quantity:
            flash('الدواء ورقم التشغيلة والكمية مطلوبة', 'error')
            return redirect(url_for('medication.add_purchase'))

        tenant_id = current_user.tenant_id
        medication = db.session.execute(select(Medication).filter(
            Medication.tenant_id == tenant_id,
            Medication.id == medication_id
        )).scalars().first()
        if not medication:
            flash('الدواء غير موجود', 'error')
            return redirect(url_for('medication.add_purchase'))

        if supplier_id:
            supplier = db.session.execute(select(Supplier).filter(
                Supplier.tenant_id == tenant_id,
                Supplier.id == supplier_id
            )).scalars().first()
            if not supplier:
                flash('المورد غير موجود', 'error')
                return redirect(url_for('medication.add_purchase'))

        expiry_date = None
        if expiry_date_str:
            try:
                from datetime import date
                expiry_date = date.fromisoformat(expiry_date_str)
            except (ValueError, TypeError):
                logging.warning(f"Invalid expiry date format: {expiry_date_str}")

        purchase = MedicationPurchase(
            tenant_id=current_user.tenant_id,
            supplier_id=supplier_id,
            medication_id=medication_id,
            batch_number=batch_number,
            quantity=quantity,
            remaining_quantity=quantity,
            purchase_price=purchase_price,
            selling_price=selling_price or None,
            expiry_date=expiry_date,
            purchase_date=datetime.now(timezone.utc).date(),
            invoice_number=invoice_number,
            notes=notes,
            created_by=current_user.id,
        )
        db.session.add(purchase)

        if medication:
            medication.stock_quantity = (medication.stock_quantity or 0) + quantity
            medication.updated_at = datetime.now(timezone.utc)

        try:
            safe_commit(db.session, error_message="database commit failed", reraise=True)
            flash('تم إضافة المشتريات بنجاح', 'success')
            return redirect(url_for('medication.purchases'))
        except Exception as e:
            safe_rollback(db.session, error_message="database rollback")
            flash('حدث خطأ في إضافة المشتريات', 'error')

    medications = db.session.execute(select(Medication).filter(
        Medication.tenant_id == current_user.tenant_id,
        Medication.is_active == True
    ).order_by(Medication.trade_name)).scalars().all()
    suppliers = db.session.execute(select(Supplier).filter(
        Supplier.tenant_id == current_user.tenant_id,
        Supplier.is_active == True
    ).order_by(Supplier.name)).scalars().all()
    return render_template('pharmacy/add_purchase.html', medications=medications, suppliers=suppliers)
