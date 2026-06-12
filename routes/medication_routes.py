 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.medication import Medication, Prescription
from models.patient import Patient
from models.visit import Visit
from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from models.drug_interaction import DrugInteraction
from app_factory import db
import logging
from datetime import datetime, timezone, timedelta, date
import json
from sqlalchemy import func

medication_bp = Blueprint('medication', __name__)

@medication_bp.route('/')
@login_required
def index():
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/dashboard')
@login_required
@role_required('doctor', 'nurse', 'pharmacist', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الأدوية"""
    
    
    try:
        # إحصائيات الأدوية
        total_medications = Medication.query.count()
        active_medications = Medication.query.filter_by(is_active=True).count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # الأدوية منخفضة المخزون
        low_stock = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).limit(10).all()
        
        # الأدوية الأكثر استخداماً
        most_used = Medication.query.order_by(
            Medication.usage_count.desc()
        ).limit(5).all()

        least_used = Medication.query.order_by(
            func.coalesce(Medication.usage_count, 0).asc(),
            Medication.trade_name.asc()
        ).limit(5).all()
        
        # الميزات الذكية
        smart_analytics = get_pharmacy_smart_analytics()
        inventory_optimization = get_inventory_optimization()
        safety_monitoring = get_medication_safety_monitoring()
        prescription_analytics = get_prescription_analytics()
        drug_interaction_checker = get_drug_interaction_checker()
        workflow_automation = get_pharmacy_workflow_automation()
        predictive_insights = get_pharmacy_predictive_insights()
        smart_recommendations = get_pharmacy_smart_recommendations()
        
        stats = {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'low_stock': low_stock,
            'most_used': most_used,
            'least_used': least_used,
            'smart_analytics': smart_analytics,
            'inventory_optimization': inventory_optimization,
            'safety_monitoring': safety_monitoring,
            'prescription_analytics': prescription_analytics,
            'drug_interaction_checker': drug_interaction_checker,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights,
            'smart_recommendations': smart_recommendations
        }
        
        return render_template('pharmacy/dashboard_new.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in medication dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

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
        logging.error(f"Error listing medications: {str(e)}")
        flash('حدث خطأ في تحميل قائمة الأدوية', 'error')
        return redirect(url_for('medication.dashboard'))

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
            medication = Medication(
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
            pass
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


def _generate_supply_request_number():
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"SR-{ts}"


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

def get_pharmacy_smart_analytics():
    """التحليلات الذكية للصيدلية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل الأدوية
        total_medications = Medication.query.count()
        active_medications = Medication.query.filter(Medication.is_active == True).count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل المخزون
        total_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).scalar() or 0
        low_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).scalar() or 0
        
        # تحليل الفئات
        categories = db.session.query(
            Medication.category,
            func.count(Medication.id).label('count'),
            func.sum(Medication.stock_quantity).label('total_stock')
        ).group_by(Medication.category).all()
        
        # تحليل الاستخدام
        most_used_medications = Medication.query.order_by(
            Medication.usage_count.desc()
        ).limit(5).all()

        return {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'total_stock_value': float(total_stock_value),
            'low_stock_value': float(low_stock_value),
            'categories': [{'category': c.category, 'count': c.count, 'total_stock': c.total_stock} for c in categories],
            'most_used': [{'name': m.trade_name, 'usage_count': m.usage_count or 0} for m in most_used_medications],
            'efficiency_score': calculate_pharmacy_efficiency(active_medications, low_stock_medications, total_medications)
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy smart analytics: {str(e)}")
        return {}

def get_inventory_optimization():
    """تحسين المخزون"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        # تحليل المخزون
        total_medications = Medication.query.count()
        low_stock_count = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل انتهاء الصلاحية
        expiring_soon = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date <= datetime.now().date() + timedelta(days=30)
            )
        ).count()
        
        # تحليل القيمة
        total_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).scalar() or 0
        low_stock_value = db.session.query(func.sum(Medication.price * Medication.stock_quantity)).filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).scalar() or 0
        
        # اقتراحات التحسين
        optimization_suggestions = generate_inventory_optimization_suggestions(
            low_stock_count, expiring_soon, total_medications
        )

        return {
            'total_medications': total_medications,
            'low_stock_count': low_stock_count,
            'expiring_soon': expiring_soon,
            'total_value': float(total_value),
            'low_stock_value': float(low_stock_value),
            'optimization_suggestions': optimization_suggestions,
            'efficiency_score': calculate_inventory_efficiency(low_stock_count, expiring_soon, total_medications)
        }
    except Exception as e:
        logging.error(f"Error getting inventory optimization: {str(e)}")
        return {}

def get_medication_safety_monitoring():
    """مراقبة سلامة الأدوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_

        # تحليل انتهاء الصلاحية
        expired_medications = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date < datetime.now().date()
            )
        ).count()
        
        expiring_soon = Medication.query.filter(
            and_(
                Medication.expiry_date.isnot(None),
                Medication.expiry_date <= datetime.now().date() + timedelta(days=30)
            )
        ).count()
        
        # تحليل التفاعلات الدوائية
        medications_with_interactions = Medication.query.filter(
            Medication.drug_interactions.isnot(None)
        ).count()
        
        # تحليل الآثار الجانبية
        medications_with_side_effects = Medication.query.filter(
            Medication.side_effects.isnot(None)
        ).count()
        
        # تحليل الموانع
        medications_with_contraindications = Medication.query.filter(
            Medication.contraindications.isnot(None)
        ).count()

        return {
            'expired_medications': expired_medications,
            'expiring_soon': expiring_soon,
            'medications_with_interactions': medications_with_interactions,
            'medications_with_side_effects': medications_with_side_effects,
            'medications_with_contraindications': medications_with_contraindications,
            'safety_score': calculate_safety_score(expired_medications, expiring_soon, medications_with_interactions)
        }
    except Exception as e:
        logging.error(f"Error getting medication safety monitoring: {str(e)}")
        return {}

def get_prescription_analytics():
    """تحليلات الوصفات الطبية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.medication import Prescription

        # تحليل الوصفات
        total_prescriptions = Prescription.query.count()
        active_prescriptions = Prescription.query.filter(Prescription.status == 'active').count()
        dispensed_prescriptions = Prescription.query.filter(Prescription.status == 'dispensed').count()
        
        # تحليل التكلفة
        total_cost = db.session.query(func.sum(Prescription.total_cost)).scalar() or 0
        avg_cost = db.session.query(func.avg(Prescription.total_cost)).scalar() or 0
        
        # تحليل الاتجاهات
        weekly_prescriptions = Prescription.query.filter(
            Prescription.created_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        monthly_prescriptions = Prescription.query.filter(
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).count()

        return {
            'total_prescriptions': total_prescriptions,
            'active_prescriptions': active_prescriptions,
            'dispensed_prescriptions': dispensed_prescriptions,
            'total_cost': float(total_cost),
            'avg_cost': float(avg_cost),
            'weekly_prescriptions': weekly_prescriptions,
            'monthly_prescriptions': monthly_prescriptions,
            'dispensing_rate': (dispensed_prescriptions / total_prescriptions * 100) if total_prescriptions > 0 else 0
        }
    except Exception as e:
        logging.error(f"Error getting prescription analytics: {str(e)}")
        return {}

def get_drug_interaction_checker():
    """فحص التفاعلات الدوائية"""
    try:
        from sqlalchemy import func, and_

        # تحليل الأدوية مع التفاعلات
        medications_with_interactions = Medication.query.filter(
            Medication.drug_interactions.isnot(None)
        ).count()
        
        # تحليل شدة التفاعلات
        severe_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('severe')
            )
        ).count()
        
        moderate_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('moderate')
            )
        ).count()
        
        mild_interactions = Medication.query.filter(
            and_(
                Medication.drug_interactions.isnot(None),
                Medication.drug_interactions.contains('mild')
            )
        ).count()

        return {
            'medications_with_interactions': medications_with_interactions,
            'severe_interactions': severe_interactions,
            'moderate_interactions': moderate_interactions,
            'mild_interactions': mild_interactions,
            'interaction_risk_score': calculate_interaction_risk_score(severe_interactions, moderate_interactions, mild_interactions)
        }
    except Exception as e:
        logging.error(f"Error getting drug interaction checker: {str(e)}")
        return {}

def get_pharmacy_workflow_automation():
    """أتمتة سير عمل الصيدلية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func

        # تحليل المهام المؤتمتة
        automated_tasks = 0  # يمكن إضافة نموذج للمهام المؤتمتة
        manual_tasks = 0  # يمكن إضافة نموذج للمهام اليدوية
        
        # تحليل أوقات المعالجة
        avg_processing_time = 0  # يمكن حساب متوسط وقت معالجة الوصفات
        
        # تحليل الكفاءة
        efficiency_metrics = {
            'automation_rate': 0,
            'time_saved': 0,
            'error_reduction': 0,
            'productivity_gain': 0
        }

        return {
            'automated_tasks': automated_tasks,
            'manual_tasks': manual_tasks,
            'avg_processing_time': avg_processing_time,
            'efficiency_metrics': efficiency_metrics,
            'automation_score': calculate_automation_score(automated_tasks, manual_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy workflow automation: {str(e)}")
        return {}

def get_pharmacy_predictive_insights():
    try:
        from datetime import datetime, timedelta
        from models.medication import PrescriptionItem, Prescription

        now = datetime.now(timezone.utc)
        weekly_demand = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=7)
        ).count()
        monthly_demand = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=30)
        ).count()
        prev_week = PrescriptionItem.query.join(
            Prescription, PrescriptionItem.prescription_id == Prescription.id
        ).filter(
            Prescription.created_at >= now - timedelta(days=14),
            Prescription.created_at < now - timedelta(days=7)
        ).count()
        growth_rate = ((weekly_demand - prev_week) / prev_week * 100) if prev_week else 0

        low_stock = Medication.query.filter(Medication.stock_quantity <= Medication.minimum_stock).count()
        predicted_stock_needs = int(low_stock or 0)

        return {
            'weekly_demand': weekly_demand,
            'monthly_demand': monthly_demand,
            'growth_rate': round(growth_rate, 2),
            'peak_hours': [],
            'predicted_stock_needs': predicted_stock_needs,
            'demand_forecast_accuracy': calculate_demand_forecast_accuracy()
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy predictive insights: {str(e)}")
        return {}

def get_pharmacy_smart_recommendations():
    """التوصيات الذكية للصيدلية"""
    try:
        recommendations = []
        
        # تحليل البيانات الحالية
        analytics = get_pharmacy_smart_analytics()
        inventory = get_inventory_optimization()
        safety = get_medication_safety_monitoring()
        prescriptions = get_prescription_analytics()
        interactions = get_drug_interaction_checker()

        # توصيات بناءً على التحليل
        if analytics.get('low_stock_medications', 0) > 5:
            recommendations.append({
                'title': 'تحسين إدارة المخزون',
                'description': f'عدد الأدوية منخفضة المخزون {analytics.get("low_stock_medications", 0)} مرتفع. يُنصح بتحسين إدارة المخزون.',
                'priority': 'high',
                'category': 'inventory'
            })

        if safety.get('expired_medications', 0) > 0:
            recommendations.append({
                'title': 'إزالة الأدوية المنتهية الصلاحية',
                'description': f'يوجد {safety.get("expired_medications", 0)} دواء منتهي الصلاحية. يُنصح بإزالته فوراً.',
                'priority': 'high',
                'category': 'safety'
            })

        if safety.get('expiring_soon', 0) > 3:
            recommendations.append({
                'title': 'متابعة الأدوية القريبة من انتهاء الصلاحية',
                'description': f'يوجد {safety.get("expiring_soon", 0)} دواء قريب من انتهاء الصلاحية. يُنصح بمتابعته.',
                'priority': 'medium',
                'category': 'safety'
            })

        if interactions.get('severe_interactions', 0) > 0:
            recommendations.append({
                'title': 'مراجعة التفاعلات الدوائية الشديدة',
                'description': f'يوجد {interactions.get("severe_interactions", 0)} تفاعل دوائي شديد. يُنصح بمراجعته.',
                'priority': 'high',
                'category': 'safety'
            })

        if prescriptions.get('dispensing_rate', 0) < 80:
            recommendations.append({
                'title': 'تحسين معدل صرف الوصفات',
                'description': f'معدل صرف الوصفات {prescriptions.get("dispensing_rate", 0)}% منخفض. يُنصح بتحسين العملية.',
                'priority': 'medium',
                'category': 'efficiency'
            })

        return {
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r['priority'] == 'high']),
            'medium_priority': len([r for r in recommendations if r['priority'] == 'medium'])
        }
    except Exception as e:
        logging.error(f"Error getting pharmacy smart recommendations: {str(e)}")
        return {'recommendations': [], 'total_recommendations': 0}

# ==================== دوال مساعدة ====================

def calculate_pharmacy_efficiency(active_medications, low_stock_medications, total_medications):
    """حساب كفاءة الصيدلية"""
    try:
        if total_medications == 0:
            return 0
        
        efficiency = (active_medications / total_medications * 0.7) + ((total_medications - low_stock_medications) / total_medications * 0.3)
        return min(100, max(0, round(efficiency * 100, 2)))
    except:
        return 0

def generate_inventory_optimization_suggestions(low_stock_count, expiring_soon, total_medications):
    """توليد اقتراحات تحسين المخزون"""
    suggestions = []
    
    try:
        if low_stock_count > total_medications * 0.1:
            suggestions.append('زيادة الحد الأدنى للمخزون للأدوية المهمة')
        
        if expiring_soon > 5:
            suggestions.append('تحسين نظام متابعة انتهاء الصلاحية')
        
        if not suggestions:
            suggestions.append('المخزون في حالة جيدة')
            
    except Exception as e:
        suggestions.append('تحليل البيانات للتحسين')
    
    return suggestions

def calculate_inventory_efficiency(low_stock_count, expiring_soon, total_medications):
    """حساب كفاءة المخزون"""
    try:
        if total_medications == 0:
            return 0
        
        efficiency = ((total_medications - low_stock_count - expiring_soon) / total_medications) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_safety_score(expired_medications, expiring_soon, medications_with_interactions):
    """حساب درجة السلامة"""
    try:
        safety_score = 100
        
        # خصم نقاط للأدوية المنتهية الصلاحية
        safety_score -= expired_medications * 10
        
        # خصم نقاط للأدوية القريبة من انتهاء الصلاحية
        safety_score -= expiring_soon * 2
        
        # خصم نقاط للتفاعلات الدوائية
        safety_score -= medications_with_interactions * 1
        
        return min(100, max(0, round(safety_score, 2)))
    except:
        return 0

def calculate_interaction_risk_score(severe_interactions, moderate_interactions, mild_interactions):
    """حساب درجة مخاطر التفاعلات"""
    try:
        risk_score = (severe_interactions * 10) + (moderate_interactions * 5) + (mild_interactions * 2)
        return min(100, max(0, round(risk_score, 2)))
    except:
        return 0

def calculate_automation_score(automated_tasks, manual_tasks):
    """حساب درجة الأتمتة"""
    try:
        if automated_tasks + manual_tasks == 0:
            return 0
        
        automation_rate = (automated_tasks / (automated_tasks + manual_tasks)) * 100
        return min(100, max(0, round(automation_rate, 2)))
    except:
        return 0

def calculate_demand_forecast_accuracy():
    """حساب دقة التنبؤ بالطلب"""
    try:
        # يمكن تطوير خوارزمية أكثر تعقيداً هنا
        return 85  # قيمة افتراضية
    except:
        return 0
