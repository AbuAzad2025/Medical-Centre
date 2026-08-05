"""prescriptions routes - extracted from monolithic doctor.py"""

import json
import logging
from datetime import UTC, date, datetime, timedelta

# Imports
from flask import flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, select

from app.extensions import db
from app.shared.enums import VisitState
from app.shared.print_context import generate_qr_data_uri
from models.audit_trail import AuditTrail
from models.department import Department
from models.drug_interaction import DrugInteraction
from models.medication import Prescription
from models.visit import Visit
from routes.doctor import doctor_bp
from services.prescription_service import prescription_service
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# PRESCRIPTIONS ROUTES
# =============================================


def _check_drug_interaction_warnings(used_med_ids):
    """التحقق من التداخلات الدوائية بين الأدوية المختارة"""
    warnings = []
    try:
        med_ids_sorted = sorted({int(x) for x in used_med_ids if x})
        pairs = []
        for i in range(len(med_ids_sorted)):
            for j in range(i + 1, len(med_ids_sorted)):
                a = min(med_ids_sorted[i], med_ids_sorted[j])
                b = max(med_ids_sorted[i], med_ids_sorted[j])
                pairs.append((a, b))
        if pairs:
            from sqlalchemy import and_, or_

            conds = [
                and_(DrugInteraction.medication_a_id == a, DrugInteraction.medication_b_id == b)
                for a, b in pairs
            ]
            rows = (
                db.session.execute(
                    select(DrugInteraction)
                    .filter(DrugInteraction.is_active)
                    .filter(or_(*conds))
                )
                .scalars()
                .all()
            )
            for row in rows:
                a = prescription_service.get_medication(row.medication_a_id)
                b = prescription_service.get_medication(row.medication_b_id)
                warnings.append(
                    f'تحذير: تداخل دوائي {a.trade_name if a else row.medication_a_id} ↔ {b.trade_name if b else row.medication_b_id} ({row.severity})'
                )
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')
    return warnings


def _notify_pharmacy_non_catalog(non_catalog_medications, visit, current_user):
    """إرسال إشعار للصيدلية بوجود أدوية غير موجودة في النظام"""
    if not non_catalog_medications:
        return
    try:
        from models.notification import Notification

        dept = (
            db.session.execute(
                select(Department).filter(
                    db.or_(Department.name.ilike('%pharmacy%'), Department.name_ar.ilike('%صيدل%'))
                )
            )
            .scalars()
            .first()
        )
        dept_id = dept.id if dept else None
        notif = Notification(
            title='طلب إضافة أدوية غير موجودة',
            message=f'تمت كتابة وصفة تحتوي على أدوية غير موجودة في النظام:\n{non_catalog_medications}\nالزيارة رقم: {visit.id}\nالطبيب: {current_user.full_name}',
            notification_type='info',
            priority='normal',
            recipient_role='pharmacist',
            recipient_department_id=dept_id,
            sender_id=current_user.id,
        )
        db.session.add(notif)
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')


@doctor_bp.route('/prescription/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def prescription(visit_id):
    """كتابة الوصفة الطبية"""

    try:
        visit = (
            db.session.execute(
                select(Visit).filter(
                    Visit.id == visit_id,
                    Visit.tenant_id == g.tenant_id,
                    Visit.doctor_id == current_user.id,
                )
            )
            .scalars()
            .first()
        )
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != VisitState.IN_PROGRESS:
            flash('لا يمكن كتابة وصفة إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        from models.medication import Medication
        from models.system_config import SystemConfig

        medications = (
            db.session.execute(
                select(Medication)
                .filter_by(is_active=True)
                .order_by(Medication.trade_name.asc())
                .limit(1000)
            )
            .scalars()
            .all()
        )

        templates_key = f'doctor_rx_templates_{current_user.id}'
        doctor_templates = []
        try:
            cfg = (
                db.session.execute(select(SystemConfig).filter_by(config_key=templates_key))
                .scalars()
                .first()
            )
            if cfg and cfg.config_type == 'json':
                doctor_templates = cfg.get_value() or []
        except Exception:
            doctor_templates = []

        visit_prescriptions = (
            db.session.execute(
                select(Prescription)
                .filter(Prescription.visit_id == visit_id)
                .order_by(desc(Prescription.created_at))
                .limit(10)
            )
            .scalars()
            .all()
        )

        if request.method == 'POST':
            item_med_ids = request.form.getlist('item_medication_id[]')
            item_med_refs = request.form.getlist('item_medication_ref[]')
            item_dosages = request.form.getlist('item_dosage[]')
            item_frequencies = request.form.getlist('item_frequency[]')
            item_durations = request.form.getlist('item_duration_days[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_instructions = request.form.getlist('item_instructions[]')

            if not item_med_ids and item_med_refs:
                for ref in item_med_refs:
                    ref = (ref or '').strip()
                    if '|' in ref:
                        item_med_ids.append(ref.split('|', 1)[0].strip())
                    else:
                        item_med_ids.append('')

            additional_notes = (request.form.get('additional_notes') or '').strip()
            non_catalog_medications = (request.form.get('non_catalog_medications') or '').strip()

            legacy_medication_name = (request.form.get('medication_name') or '').strip()
            legacy_dosage = (request.form.get('dosage') or '').strip()
            legacy_frequency = (request.form.get('frequency') or '').strip()
            legacy_duration = (request.form.get('duration') or '').strip()
            legacy_instructions = (request.form.get('instructions') or '').strip()

            legacy_duration_days = 0
            if legacy_duration:
                for part in legacy_duration.replace('-', ' ').replace('/', ' ').split():
                    if part.isdigit():
                        legacy_duration_days = int(part)
                        break

            any_item = any((x or '').strip() for x in item_med_ids)
            if (not any_item) and legacy_medication_name:
                try:
                    med = (
                        db.session.execute(
                            select(Medication).filter(
                                db.or_(
                                    Medication.trade_name.ilike(legacy_medication_name),
                                    Medication.generic_name.ilike(legacy_medication_name),
                                    Medication.scientific_name.ilike(legacy_medication_name),
                                )
                            )
                        )
                        .scalars()
                        .first()
                    )
                except Exception:
                    med = None
                if med and legacy_dosage and legacy_frequency and legacy_duration_days > 0:
                    item_med_ids = [str(med.id)]
                    item_dosages = [legacy_dosage]
                    item_frequencies = [legacy_frequency]
                    item_durations = [str(legacy_duration_days)]
                    item_quantities = ['1']
                    item_instructions = [legacy_instructions]
                    any_item = True
                else:
                    legacy_line_parts = [legacy_medication_name]
                    if legacy_dosage:
                        legacy_line_parts.append(f'جرعة: {legacy_dosage}')
                    if legacy_frequency:
                        legacy_line_parts.append(f'تكرار: {legacy_frequency}')
                    if legacy_duration:
                        legacy_line_parts.append(f'المدة: {legacy_duration}')
                    if legacy_instructions:
                        legacy_line_parts.append(f'تعليمات: {legacy_instructions}')
                    legacy_line = ' | '.join([x for x in legacy_line_parts if x])
                    non_catalog_medications = (
                        non_catalog_medications + '\n' if non_catalog_medications else ''
                    ) + legacy_line

            if (not any_item) and (not additional_notes) and (not non_catalog_medications):
                flash('يرجى إضافة دواء واحد على الأقل من القائمة', 'warning')
                return render_template(
                    'doctor/prescription.html',
                    visit=visit,
                    medications=medications,
                    doctor_templates=doctor_templates,
                    visit_prescriptions=visit_prescriptions,
                )

            prescription_number = f'RX-{visit_id}-{int(datetime.now(UTC).timestamp())}'
            notes_parts = []
            if additional_notes:
                notes_parts.append(additional_notes)
            if non_catalog_medications:
                notes_parts.append('أدوية غير موجودة بالمخزون:\n' + non_catalog_medications)
            notes = '\n\n'.join([p for p in notes_parts if p]) or None

            warnings = []
            used_med_ids = set()
            items = []
            for i in range(
                max(
                    len(item_med_ids),
                    len(item_med_refs),
                    len(item_dosages),
                    len(item_frequencies),
                    len(item_durations),
                    len(item_instructions),
                    len(item_quantities),
                )
            ):
                med_id_raw = item_med_ids[i] if i < len(item_med_ids) else ''
                if not (med_id_raw or '').strip():
                    continue
                try:
                    med_id = int(str(med_id_raw).strip())
                except Exception:
                    continue

                med = prescription_service.get_medication(med_id)
                if not med:
                    continue
                used_med_ids.add(med.id)

                dosage = (item_dosages[i] if i < len(item_dosages) else '').strip()
                frequency = (item_frequencies[i] if i < len(item_frequencies) else '').strip()
                duration_days_raw = (item_durations[i] if i < len(item_durations) else '').strip()
                quantity_raw = (item_quantities[i] if i < len(item_quantities) else '').strip()
                instructions = (
                    item_instructions[i] if i < len(item_instructions) else ''
                ).strip() or None
                if not instructions:
                    instructions = (
                        getattr(med, 'standard_instructions', None) or ''
                    ).strip() or None

                if not dosage or not frequency:
                    continue

                try:
                    duration_days = int(duration_days_raw)
                except Exception:
                    duration_days = 0
                if duration_days <= 0:
                    continue

                try:
                    quantity = int(quantity_raw) if quantity_raw else 1
                except Exception:
                    quantity = 1
                if quantity <= 0:
                    quantity = 1

                stored_dosage = f'{dosage} | {frequency}' if frequency else dosage
                items.append(
                    {
                        'medication_id': med.id,
                        'dosage': stored_dosage,
                        'quantity': quantity,
                        'duration_days': duration_days,
                        'instructions': instructions,
                    }
                )

                try:
                    from models.patient import PatientAllergy

                    allergy_records = (
                        db.session.execute(
                            select(PatientAllergy).filter_by(patient_id=visit.patient_id)
                        )
                        .scalars()
                        .all()
                    )
                    med_names = [
                        x
                        for x in [
                            (med.trade_name or '').lower(),
                            (med.generic_name or '').lower(),
                            (med.scientific_name or '').lower(),
                        ]
                        if x
                    ]
                    for ar in allergy_records:
                        allergen = (ar.allergen or '').lower()
                        if not allergen:
                            continue
                        if any(allergen in n or n in allergen for n in med_names):
                            warnings.append(f'تحذير: حساسية مسجلة تجاه {med.trade_name}')
                            break
                except Exception as e:
                    logging.warning(f'Error in {__name__}: {e}')
            warnings.extend(_check_drug_interaction_warnings(used_med_ids))

            # P2-002: Delegate Prescription + PrescriptionItem creation to the service.
            ok, result = prescription_service.create_prescription(
                patient_id=visit.patient_id,
                doctor_id=current_user.id,
                visit_id=visit_id,
                tenant_id=getattr(current_user, 'tenant_id', None),
                items=items,
                notes=notes,
                diagnosis=visit.diagnosis,
                prescription_number=prescription_number,
            )
            if not ok:
                hard_stops = []
                if isinstance(result, str):
                    msg = result
                    if 'HARD STOP' in msg:
                        hard_stops.append(msg)
                from flask import request as _req

                if _req.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify(
                        {
                            'success': False,
                            'hard_stops': hard_stops,
                            'message': f'تعذر حفظ الوصفة: {result}',
                        }
                    ), 422
                flash(f'تعذر حفظ الوصفة: {result}', 'error')
                return redirect(url_for('doctor.patient_details', visit_id=visit_id))
            prescription = result
            visit.prescription_issued = True

            _notify_pharmacy_non_catalog(non_catalog_medications, visit, current_user)

            save_template = (request.form.get('save_as_template') or '') == 'on'
            template_name = (request.form.get('template_name') or '').strip()
            if save_template and template_name:
                try:
                    import secrets

                    tpl_items = []
                    for it in prescription.items.all():
                        label = ''
                        try:
                            m = it.medication
                            if m:
                                label = f'{m.trade_name}{f" ({m.generic_name})" if m.generic_name else ""} — {m.scientific_name} — {m.strength} {m.dosage_form}'
                        except Exception:
                            label = ''
                        dosage_part = it.dosage or ''
                        freq_part = ''
                        if ' | ' in dosage_part:
                            dosage_part, freq_part = dosage_part.split(' | ', 1)
                        tpl_items.append(
                            {
                                'medication_id': it.medication_id,
                                'medication_label': label,
                                'dosage': (dosage_part or '').strip(),
                                'frequency': (freq_part or '').strip(),
                                'duration_days': it.duration_days,
                                'quantity': it.quantity,
                                'instructions': it.instructions or '',
                            }
                        )
                    new_tpl = {
                        'id': secrets.token_hex(8),
                        'name': template_name,
                        'items': tpl_items,
                    }
                    cfg = (
                        db.session.execute(select(SystemConfig).filter_by(config_key=templates_key))
                        .scalars()
                        .first()
                    )
                    if not cfg:
                        cfg = SystemConfig(
                            config_key=templates_key,
                            config_type='json',
                            config_value='[]',
                            category='general',
                            description='قوالب وصفات الطبيب',
                            is_system=False,
                            is_encrypted=False,
                            created_by=current_user.id,
                            updated_by=current_user.id,
                        )
                        db.session.add(cfg)
                    existing = cfg.get_value() if cfg and cfg.config_type == 'json' else []
                    if not isinstance(existing, list):
                        existing = []
                    existing.append(new_tpl)
                    cfg.set_value(existing)
                    cfg.updated_by = current_user.id
                except Exception as e:
                    logging.warning(f'Error in {__name__}: {e}')
            safe_commit(db.session, error_message='database commit failed', reraise=True)

            for w in warnings:
                flash(w, 'warning')
            try:
                db.session.add(
                    AuditTrail(
                        entity_type='visit',
                        entity_id=visit_id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='إضافة وصفة طبية',
                        new_values=json.dumps(
                            {
                                'prescription_id': prescription.id,
                                'items_count': prescription.items.count(),
                            }
                        ),
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            flash('تم حفظ الوصفة بنجاح', 'success')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        return render_template(
            'doctor/prescription.html',
            visit=visit,
            medications=medications,
            doctor_templates=doctor_templates,
            visit_prescriptions=visit_prescriptions,
        )
    except Exception:
        logging.exception("Error in prescription: %s")
        flash('حدث خطأ في حفظ الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/print-prescription/<int:prescription_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية"""

    try:
        prescription = prescription_service.get_prescription(prescription_id)
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('doctor.patient_queue'))

        qr_data_uri = generate_qr_data_uri(
            f'RX|{prescription.id}|{prescription.patient_id}|{prescription.created_at.isoformat() if prescription.created_at else ""}'
        )
        return render_template(
            'print/prescription.html', prescription=prescription, qr_data_uri=qr_data_uri
        )
    except Exception:
        logging.exception("Error printing prescription: %s")
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/prescriptions')
@login_required
@role_required('doctor', 'admin', 'manager')
def prescriptions():
    """الوصفات الطبية — قائمة الوصفات الخاصة بالطبيب"""
    try:
        from sqlalchemy import func

        from models.medication import Prescription
        from models.visit import Visit

        today = date.today()
        page = request.args.get('page', 1, type=int)
        per_page = 20

        # Base query: prescriptions for this doctor's visits
        query = select(Prescription).join(Visit).filter(Visit.doctor_id == current_user.id)

        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar()
        prescriptions = (
            db.session.execute(query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        )
        pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Stats
        today_count = db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Visit)
            .filter(Visit.doctor_id == current_user.id, func.date(Prescription.created_at) == today)
        ).scalar()

        week_count = db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Visit)
            .filter(
                Visit.doctor_id == current_user.id,
                Prescription.created_at >= today - timedelta(days=7),
            )
        ).scalar()

        return render_template(
            'doctor/prescriptions.html',
            prescriptions=prescriptions,
            today_count=today_count,
            week_count=week_count,
            total=total,
            page=page,
            pages=pages,
        )
    except Exception:
        logging.exception("Error loading prescriptions: %s")
        flash('حدث خطأ في تحميل الوصفات', 'error')
        return redirect(url_for('doctor.dashboard'))
