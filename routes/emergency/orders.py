"""orders routes - extracted from monolithic emergency.py"""

import json
import logging
from datetime import UTC, datetime

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_, select

from app.extensions import db
from app.shared.print_context import generate_qr_data_uri
from models.audit_trail import AuditTrail
from models.lab_request import LabRequest
from models.medication import Medication, Prescription
from models.radiology_request import RadiologyRequest
from routes.emergency import emergency_bp
from services.emergency_service import emergency_service
from services.prescription_service import prescription_service
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# ORDERS ROUTES
# =============================================


def _resolve_emergency_medication(name, tenant_id):
    return (
        db.session.execute(
            select(Medication).filter(
                Medication.tenant_id == tenant_id,
                or_(
                    Medication.trade_name.ilike(name),
                    Medication.generic_name.ilike(name),
                    Medication.scientific_name.ilike(name),
                ),
            )
        )
        .scalars()
        .first()
    )


@emergency_bp.route('/prescription/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def prescription(emergency_id):
    """وصفة طبية للطوارئ"""

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            names = [(n or '').strip() for n in request.form.getlist('medications[]')]
            dosages = request.form.getlist('dosages[]')
            frequencies = request.form.getlist('frequencies[]')
            durations = request.form.getlist('durations[]')
            instructions_list = request.form.getlist('instructions[]')

            items = []
            non_catalog = []
            for i, name in enumerate(names):
                if not name:
                    continue
                med = _resolve_emergency_medication(name, emergency.tenant_id)
                if not med:
                    non_catalog.append(name)
                    continue
                dosage = (dosages[i] if i < len(dosages) else '').strip()
                frequency = (frequencies[i] if i < len(frequencies) else '').strip()
                stored_dosage = f'{dosage} | {frequency}' if dosage and frequency else dosage
                stored_dosage = stored_dosage or frequency or name
                try:
                    duration_days = int((durations[i] if i < len(durations) else '').strip())
                except Exception:
                    duration_days = 7
                if duration_days <= 0:
                    duration_days = 7
                items.append(
                    {
                        'medication_id': med.id,
                        'dosage': stored_dosage,
                        'quantity': 1,
                        'duration_days': duration_days,
                        'instructions': (
                            instructions_list[i] if i < len(instructions_list) else ''
                        ).strip()
                        or None,
                    }
                )

            if not items:
                flash('يرجى إضافة دواء واحد على الأقل من القائمة', 'warning')
                return redirect(url_for('emergency.prescription', emergency_id=emergency_id))

            notes_parts = []
            extra_notes = (request.form.get('additional_notes') or '').strip()
            if extra_notes:
                notes_parts.append(extra_notes)
            if non_catalog:
                notes_parts.append('أدوية غير موجودة بالمخزون:\n' + '\n'.join(non_catalog))
            notes = '\n\n'.join(notes_parts) or None

            visit = emergency.visit
            prescriber_id = (visit.doctor_id if visit else None) or current_user.id

            ok, result = prescription_service.create_prescription(
                patient_id=emergency.patient_id,
                doctor_id=prescriber_id,
                visit_id=visit.id if visit else None,
                tenant_id=getattr(current_user, 'tenant_id', None) or emergency.tenant_id,
                items=items,
                notes=notes,
                diagnosis=emergency.diagnosis,
                prescription_number=f'RX-EM-{emergency.id}-{int(datetime.now(UTC).timestamp())}',
            )
            if not ok:
                flash(f'تعذر حفظ الوصفة: {result}', 'error')
                return redirect(url_for('emergency.prescription', emergency_id=emergency_id))

            try:
                db.session.add(
                    AuditTrail(
                        entity_type='visit' if visit else 'patient',
                        entity_id=visit.id if visit else emergency.patient_id,
                        action='create',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description=f'وصفة طبية لحالة الطوارئ #{emergency.id}',
                        new_values=json.dumps({'prescription_id': result.id}),
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')

            flash('تم إنشاء الوصفة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/prescription.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency prescription: %s')
        flash('حدث خطأ في إنشاء الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/lab-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def lab_request(emergency_id):
    """طلب فحوصات للطوارئ"""
    if 'lab' not in getattr(g, 'enabled_modules', set()):
        flash('وحدة المختبر غير مفعلة في باقة العيادة', 'error')
        return redirect(url_for('emergency.patient_queue'))

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            tests_requested = (
                request.form.getlist('tests[]')
                or request.form.getlist('tests')
                or [t.strip() for t in (request.form.get('tests') or '').split(',') if t.strip()]
            )
            if not tests_requested:
                flash('اختر فحصاً واحداً على الأقل', 'error')
                return redirect(request.referrer or url_for('emergency.patient_queue'))
            urgency = (request.form.get('urgency') or 'ROUTINE').strip()
            notes = (request.form.get('notes') or '').strip()
            notes_text = f'[{urgency}] {notes}' if notes else f'[{urgency}]'

            lab_request = LabRequest(
                tenant_id=emergency.tenant_id,
                patient_id=emergency.patient_id,
                visit_id=None,
                requested_by=current_user.id,
                status='REQUESTED',
                notes=notes_text,
            )
            db.session.add(lab_request)
            db.session.flush()
            emergency.lab_request_id = lab_request.id

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إرسال طلب الفحوصات بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/lab_request.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency lab request: %s')
        flash('حدث خطأ في إرسال طلب الفحوصات', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/radiology-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
@role_required('emergency', 'manager')
def radiology_request(emergency_id):
    """طلب أشعة للطوارئ"""
    if 'radiology' not in getattr(g, 'enabled_modules', set()):
        flash('وحدة الأشعة غير مفعلة في باقة العيادة', 'error')
        return redirect(url_for('emergency.patient_queue'))

    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        if request.method == 'POST':
            imaging_type = (request.form.get('imaging_type') or '').strip()
            body_part = (request.form.get('body_part') or '').strip()
            urgency = (request.form.get('urgency') or 'ROUTINE').strip()
            clinical_question = (request.form.get('clinical_question') or '').strip()
            notes = (request.form.get('notes') or '').strip()
            notes_parts = [p for p in (f'[{urgency}]', clinical_question, notes) if p]
            notes_text = ' | '.join(notes_parts)

            radiology_request_row = RadiologyRequest(
                tenant_id=emergency.tenant_id,
                patient_id=emergency.patient_id,
                visit_id=None,
                requested_by=current_user.id,
                status='REQUESTED',
                modality=imaging_type or None,
                body_part=body_part or None,
                notes=notes_text,
            )
            db.session.add(radiology_request_row)
            db.session.flush()
            emergency.radiology_request_id = radiology_request_row.id

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إرسال طلب الأشعة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/radiology_request.html', emergency=emergency)
    except Exception:
        logging.exception('Error in emergency radiology request: %s')
        flash('حدث خطأ في إرسال طلب الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))


@emergency_bp.route('/print-prescription/<int:prescription_id>')
@login_required
@role_required('emergency', 'manager')
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية للطوارئ"""

    try:
        prescription = (
            db.session.execute(select(Prescription).filter_by(id=prescription_id)).scalars().first()
        )
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))

        qr_data_uri = generate_qr_data_uri(
            f'RX|{prescription.id}|{prescription.patient_id}|{prescription.created_at.isoformat() if prescription.created_at else ""}'
        )
        return render_template(
            'print/prescription.html', prescription=prescription, qr_data_uri=qr_data_uri
        )
    except Exception:
        logging.exception('Error printing prescription: %s')
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))
