"""medication routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import nurse_bp, _accessible_department_ids

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from app.shared.enums import VisitState
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app_factory import db
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc


# =============================================
# MEDICATION ROUTES
# =============================================

@nurse_bp.route('/medication-administration')
@login_required
@role_required('nurse', 'admin', 'manager')
def medication_administration():
    """إدارة الأدوية"""
    
    
    try:
        from models.medication import Prescription, PrescriptionItem
        from models.nurse import MedicationAdministrationLog

        visit_id = request.args.get('visit_id', type=int)

        medications = Medication.query.filter_by(is_active=True).order_by(Medication.trade_name.asc()).all()
        needed_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).order_by(Medication.trade_name.asc()).all()

        visits_q = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]))
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            visits_q = visits_q.filter(Visit.department_id.in_(dept_ids))
        visits = visits_q.order_by(desc(Visit.created_at)).limit(50).all()
        selected_visit = db.session.get(Visit, visit_id) if visit_id else None

        prescribed_items = []
        administration_logs = []
        last_admin_by_item = {}
        if selected_visit:
            prescribed_items = PrescriptionItem.query.join(
                Prescription, PrescriptionItem.prescription_id == Prescription.id
            ).filter(
                Prescription.visit_id == selected_visit.id
            ).order_by(PrescriptionItem.id.desc()).all()

            administration_logs = MedicationAdministrationLog.query.filter_by(
                visit_id=selected_visit.id
            ).order_by(desc(MedicationAdministrationLog.administered_at)).limit(50).all()

            for row in administration_logs:
                if row.prescription_item_id and row.prescription_item_id not in last_admin_by_item:
                    last_admin_by_item[row.prescription_item_id] = row

        return render_template(
            'nurse/medication_administration.html',
            medications=medications,
            needed_medications=needed_medications,
            visits=visits,
            selected_visit=selected_visit,
            prescribed_items=prescribed_items,
            administration_logs=administration_logs,
            last_admin_by_item=last_admin_by_item
        )
    except Exception as e:
        logging.error(f"Error loading medication administration: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأدوية', 'error')
        return redirect(url_for('nurse.dashboard'))


@nurse_bp.route('/administer-medication/<int:prescription_item_id>', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def administer_medication(prescription_item_id):
    try:
        from models.medication import Prescription, PrescriptionItem
        from models.nurse import MedicationAdministrationLog

        nurse_profile = getattr(current_user, 'nurse_profile', None)
        if isinstance(nurse_profile, (list, tuple)):
            nurse_profile = nurse_profile[0] if nurse_profile else None
        if not nurse_profile:
            flash('لا يوجد ملف تمريض مرتبط بهذا المستخدم', 'error')
            return redirect(url_for('nurse.medication_administration'))

        item = db.session.get(PrescriptionItem, prescription_item_id)
        if not item:
            flash('عنصر الوصفة غير موجود', 'error')
            return redirect(url_for('nurse.medication_administration'))

        pres = db.session.get(Prescription, item.prescription_id)
        if not pres or not pres.visit_id:
            flash('لا يمكن ربط عنصر الوصفة بزيارة', 'error')
            return redirect(url_for('nurse.medication_administration'))

        visit = db.session.get(Visit, pres.visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('nurse.medication_administration'))

        notes = (request.form.get('notes') or '').strip() or None
        log_row = MedicationAdministrationLog(
            patient_id=pres.patient_id or visit.patient_id,
            visit_id=visit.id,
            prescription_id=pres.id,
            prescription_item_id=item.id,
            medication_id=item.medication_id,
            nurse_id=nurse_profile.id,
            administered_at=datetime.now(timezone.utc),
            notes=notes
        )
        db.session.add(log_row)
        db.session.commit()
        flash('تم توثيق تنفيذ الدواء', 'success')
        return redirect(url_for('nurse.medication_administration', visit_id=visit.id))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error administering medication: {str(e)}")
        flash('حدث خطأ في توثيق تنفيذ الدواء', 'error')
        return redirect(url_for('nurse.medication_administration'))

@nurse_bp.route('/medications')
@login_required
@role_required('nurse', 'admin', 'manager')
def medications():
    """الأدوية"""
    
    
    return render_template('nurse/medication_administration.html')
