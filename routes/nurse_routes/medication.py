"""medication routes - extracted from monolithic nurse_routes.py"""

import logging
from datetime import UTC, datetime

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.extensions import db
from models.medication import Medication
from models.visit import Visit
from routes.nurse_routes import _accessible_department_ids, nurse_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

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

        medications = (
            db.session.execute(
                select(Medication).filter_by(is_active=True).order_by(Medication.trade_name.asc())
            )
            .scalars()
            .all()
        )
        needed_medications = (
            db.session.execute(
                select(Medication)
                .filter(Medication.stock_quantity <= Medication.minimum_stock)
                .order_by(Medication.trade_name.asc())
            )
            .scalars()
            .all()
        )

        visits_q = select(Visit)
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            visits_q = visits_q.filter(Visit.department_id.in_(dept_ids))
        visits = (
            db.session.execute(visits_q.order_by(desc(Visit.created_at)).limit(50)).scalars().all()
        )
        selected_visit = (
            db.session.execute(
                select(Visit).filter(
                    Visit.id == visit_id, Visit.tenant_id == current_user.tenant_id
                )
            )
            .scalars()
            .first()
            if visit_id
            else None
        )

        prescribed_items = []
        administration_logs = []
        last_admin_by_item = {}
        if selected_visit:
            prescribed_items = (
                db.session.execute(
                    select(PrescriptionItem)
                    .join(Prescription, PrescriptionItem.prescription_id == Prescription.id)
                    .filter(Prescription.visit_id == selected_visit.id)
                    .order_by(PrescriptionItem.id.desc())
                )
                .scalars()
                .all()
            )

            administration_logs = (
                db.session.execute(
                    select(MedicationAdministrationLog)
                    .filter_by(visit_id=selected_visit.id)
                    .order_by(desc(MedicationAdministrationLog.administered_at))
                    .limit(50)
                )
                .scalars()
                .all()
            )

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
            last_admin_by_item=last_admin_by_item,
        )
    except Exception:
        logging.exception("Error loading medication administration: %s")
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

        item = (
            db.session.execute(
                select(PrescriptionItem).filter(
                    PrescriptionItem.id == prescription_item_id,
                    PrescriptionItem.tenant_id == current_user.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not item:
            flash('عنصر الوصفة غير موجود', 'error')
            return redirect(url_for('nurse.medication_administration'))

        pres = (
            db.session.execute(
                select(Prescription).filter(
                    Prescription.id == item.prescription_id,
                    Prescription.tenant_id == current_user.tenant_id,
                )
            )
            .scalars()
            .first()
        )
        if not pres or not pres.visit_id:
            flash('لا يمكن ربط عنصر الوصفة بزيارة', 'error')
            return redirect(url_for('nurse.medication_administration'))

        visit = (
            db.session.execute(
                select(Visit).filter(
                    Visit.id == pres.visit_id, Visit.tenant_id == current_user.tenant_id
                )
            )
            .scalars()
            .first()
        )
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
            administered_at=datetime.now(UTC),
            notes=notes,
        )
        db.session.add(log_row)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم توثيق تنفيذ الدواء', 'success')
        return redirect(url_for('nurse.medication_administration', visit_id=visit.id))
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception("Error administering medication: %s")
        flash('حدث خطأ في توثيق تنفيذ الدواء', 'error')
        return redirect(url_for('nurse.medication_administration'))


@nurse_bp.route('/medications')
@login_required
@role_required('nurse', 'admin', 'manager')
def medications():
    """الأدوية"""

    return render_template('nurse/medication_administration.html')
