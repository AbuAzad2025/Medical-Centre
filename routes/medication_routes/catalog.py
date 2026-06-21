"""catalog routes - extracted from monolithic medication_routes.py"""

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
# CATALOG ROUTES
# =============================================

@medication_bp.route('/list')
@login_required
@role_required('doctor', 'nurse', 'pharmacist', 'admin', 'manager')
def list_medications():
    """قائمة الأدوية"""
    
    
    try:
        # جلب الأدوية مع فلترة
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        stock_status = request.args.get('stock_status', '')
        per_page = request.args.get('per_page', type=int) or 50
        per_page = max(10, min(per_page, 200))
        page = request.args.get('page', type=int) or 1
        page = max(1, page)
        
        query = Medication.query
        
        if search:
            query = query.filter(
                Medication.trade_name.contains(search) |
                Medication.scientific_name.contains(search) |
                Medication.generic_name.contains(search)
            )
        
        if category:
            query = query.filter(Medication.category == category)

        if stock_status == 'low':
            query = query.filter(Medication.stock_quantity <= Medication.minimum_stock, Medication.stock_quantity > 0)
        elif stock_status == 'out':
            query = query.filter(Medication.stock_quantity <= 0)
        elif stock_status == 'normal':
            query = query.filter(Medication.stock_quantity > Medication.minimum_stock)
        
        total = query.count()
        medications = query.order_by(Medication.trade_name.asc()).limit(per_page).offset((page - 1) * per_page).all()
        
        return render_template('medication/list.html', 
                             medications=medications,
                             search=search,
                             category=category,
                             stock_status=stock_status,
                             page=page,
                             per_page=per_page,
                             total=total)
    except Exception as e:
        logging.error(f"Error listing medications: {str(e)}", exc_info=True)
        flash('حدث خطأ في تحميل قائمة الأدوية', 'error')
        return redirect(url_for('auth.login'))

@medication_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_medication():
    """إضافة دواء جديد"""
    if current_user.role not in ['pharmacist', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        try:
            expiry_date = request.form.get('expiry_date')
            exp_val = None
            if expiry_date:
                try:
                    exp_val = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                except Exception:
                    exp_val = None
            _tid_input = current_user.tenant_id
            import sys; print(f"[DD] cur_user.id={current_user.id}, cur_user.role={current_user.role}, tenant_id_from_user={_tid_input}", file=sys.stderr, flush=True)
            medication = Medication(
                tenant_id=_tid_input,
                trade_name=(request.form.get('trade_name') or '').strip(),
                scientific_name=(request.form.get('scientific_name') or '').strip(),
                generic_name=(request.form.get('generic_name') or '').strip() or None,
                category=request.form.get('category'),
                dosage_form=request.form.get('dosage_form'),
                strength=request.form.get('strength'),
                manufacturer=(request.form.get('manufacturer') or '').strip() or None,
                stock_quantity=int(request.form.get('stock_quantity', 0)),
                minimum_stock=int(request.form.get('minimum_stock', 10)),
                price=float(request.form.get('price', 0)),
                expiry_date=exp_val,
                batch_number=(request.form.get('batch_number') or '').strip() or None,
                description=(request.form.get('description') or '').strip() or None,
                standard_instructions=(request.form.get('standard_instructions') or '').strip() or None,
                is_active=(request.form.get('is_active') == 'on')
            )
            
            db.session.add(medication)
            db.session.commit()
            
            flash('تم إضافة الدواء بنجاح', 'success')
            return redirect(url_for('medication.list_medications'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding medication: {str(e)}")
            flash('تعذر إضافة الدواء، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    return render_template('medication/add.html')

@medication_bp.route('/edit/<int:medication_id>', methods=['GET', 'POST'])
@login_required
@role_required('pharmacist', 'admin', 'manager')
def edit_medication(medication_id):
    """تعديل دواء"""
    
    medication = db.session.get(Medication, medication_id)
    if not medication:
        flash('الدواء غير موجود', 'error')
        return redirect(url_for('medication.list_medications'))
    
    if request.method == 'POST':
        try:
            expiry_date = request.form.get('expiry_date')
            exp_val = None
            if expiry_date:
                try:
                    exp_val = datetime.strptime(expiry_date, '%Y-%m-%d').date()
                except Exception:
                    exp_val = None

            medication.trade_name = (request.form.get('trade_name') or '').strip() or medication.trade_name
            medication.scientific_name = (request.form.get('scientific_name') or '').strip() or medication.scientific_name
            medication.generic_name = (request.form.get('generic_name') or '').strip() or None
            medication.manufacturer = (request.form.get('manufacturer') or '').strip() or None
            medication.category = (request.form.get('category') or '').strip() or None
            medication.dosage_form = (request.form.get('dosage_form') or '').strip() or medication.dosage_form
            medication.strength = (request.form.get('strength') or '').strip() or medication.strength
            medication.stock_quantity = int(request.form.get('stock_quantity', medication.stock_quantity or 0))
            medication.minimum_stock = int(request.form.get('minimum_stock', medication.minimum_stock or 10))
            medication.price = float(request.form.get('price', medication.price or 0))
            medication.batch_number = (request.form.get('batch_number') or '').strip() or None
            medication.expiry_date = exp_val
            medication.standard_instructions = (request.form.get('standard_instructions') or '').strip() or None
            medication.description = (request.form.get('description') or '').strip() or None
            
            db.session.commit()
            
            flash('تم تحديث الدواء بنجاح', 'success')
            return redirect(url_for('medication.list_medications'))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error editing medication: {str(e)}")
            flash('تعذر تحديث الدواء، يرجى التحقق من البيانات والمحاولة مرة أخرى', 'error')
    
    return render_template('medication/edit.html', medication=medication)
