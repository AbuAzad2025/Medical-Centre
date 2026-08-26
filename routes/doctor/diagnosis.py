"""diagnosis routes - extracted from monolithic doctor.py"""

import json
import logging
from datetime import datetime

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case, func, select

from app.extensions import db
from app.shared.enums import VisitArchiveStatus, VisitState
from models.audit_trail import AuditTrail
from models.medical_record import MedicalRecord
from models.visit import Visit
from routes.doctor import (
    _sync_follow_up_request_for_visit,
    calculate_medical_performance_score,
    doctor_bp,
)
from services.visit_state_machine_service import VisitStateMachineService
from utils.db_safety import safe_commit
from utils.decorators import role_required

# =============================================
# DIAGNOSIS ROUTES
# =============================================


@doctor_bp.route('/diagnosis/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def diagnosis(visit_id):
    """إدخال التشخيص"""

    try:
        from ast import literal_eval

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
        if visit.status == 'COMPLETED' or visit.is_archived:
            flash('لا يمكن تعديل التشخيص بعد اكتمال أو أرشفة الزيارة', 'warning')
            return redirect(url_for('doctor.patient_queue'))

        if request.method == 'POST':
            chief_complaint = (request.form.get('chief_complaint') or '').strip() or None
            symptoms = (request.form.get('symptoms') or '').strip() or None
            diagnosis = (request.form.get('diagnosis') or '').strip() or None
            differential_diagnosis = (
                request.form.get('differential_diagnosis') or ''
            ).strip() or None
            treatment_plan = (request.form.get('treatment_plan') or '').strip() or None
            follow_up_notes = (request.form.get('follow_up_notes') or '').strip() or None
            raw_follow_up = (request.form.get('follow_up_required') or '').strip().lower()
            follow_up_required = (
                raw_follow_up in {'on', '1', 'true', 'yes'} if raw_follow_up else False
            )
            follow_up_date_raw = (request.form.get('follow_up_date') or '').strip()
            additional_notes = (request.form.get('notes') or '').strip()
            if chief_complaint and len(chief_complaint) > 2000:
                flash('الشكوى الرئيسية طويلة جداً', 'warning')
                return redirect(url_for('doctor.diagnosis', visit_id=visit_id))
            if diagnosis and len(diagnosis) > 2000:
                flash('التشخيص طويل جداً', 'warning')
                return redirect(url_for('doctor.diagnosis', visit_id=visit_id))
            if additional_notes and len(additional_notes) > 5000:
                flash('الملاحظات طويلة جداً', 'warning')
                return redirect(url_for('doctor.diagnosis', visit_id=visit_id))

            vital_signs = {
                'blood_pressure': (request.form.get('blood_pressure') or '').strip() or None,
                'heart_rate': (request.form.get('heart_rate') or '').strip() or None,
                'temperature': (request.form.get('temperature') or '').strip() or None,
                'respiratory_rate': (request.form.get('respiratory_rate') or '').strip() or None,
            }

            visit.chief_complaint = chief_complaint
            visit.symptoms = symptoms
            visit.diagnosis = diagnosis
            visit.differential_diagnosis = differential_diagnosis
            visit.treatment_plan = treatment_plan
            visit.follow_up_notes = follow_up_notes
            visit.follow_up_required = follow_up_required
            if follow_up_date_raw:
                try:
                    visit.follow_up_date = datetime.strptime(follow_up_date_raw, '%Y-%m-%d').date()
                except Exception:
                    flash('صيغة تاريخ المتابعة غير صحيحة', 'warning')
                    visit.follow_up_date = None
            else:
                visit.follow_up_date = None
            visit.vital_signs = json.dumps(vital_signs, ensure_ascii=False)
            try:
                VisitStateMachineService.ensure_in_progress(visit, actor=current_user)
            except ValueError:
                visit.status = VisitState.IN_PROGRESS
            if additional_notes:
                memo_text = '[ملاحظات طبية]\n' + additional_notes
                visit.notes = visit.notes or ''
                visit.notes += ('\n\n' if visit.notes else '') + memo_text

            try:
                _sync_follow_up_request_for_visit(visit, current_user.id)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            medical_record = MedicalRecord(
                tenant_id=visit.tenant_id,
                patient_id=visit.patient_id,
                visit_id=visit.id,
                title='تشخيص طبي',
                details=f'الشكوى الرئيسية: {chief_complaint}\nالأعراض: {symptoms}\nالتشخيص: {diagnosis}',
                created_by=current_user.id,
            )

            db.session.add(medical_record)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            try:
                db.session.add(
                    AuditTrail(
                        tenant_id=visit.tenant_id,
                        entity_type='visit',
                        entity_id=visit_id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='حفظ التشخيص',
                        new_values=json.dumps(
                            {'diagnosis': diagnosis, 'treatment_plan': treatment_plan}
                        ),
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')
            flash('تم حفظ التشخيص بنجاح', 'success')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        structured_vital_signs = {}
        raw_vital_signs = getattr(visit, 'vital_signs', None)
        if raw_vital_signs:
            try:
                parsed = json.loads(raw_vital_signs)
                if isinstance(parsed, dict):
                    structured_vital_signs = parsed
                else:
                    raise ValueError('not dict')
            except Exception:
                try:
                    parsed = literal_eval(raw_vital_signs)
                    if isinstance(parsed, dict):
                        structured_vital_signs = parsed
                except Exception:
                    structured_vital_signs = {}
        return render_template(
            'doctor/diagnosis.html', visit=visit, structured_vital_signs=structured_vital_signs
        )
    except Exception:
        logging.exception('Error in diagnosis: %s')
        flash('حدث خطأ في حفظ التشخيص', 'error')
        return redirect(url_for('doctor.patient_queue'))


# ==================== الميزات الذكية للطبيب ====================


def get_ai_diagnostic_assistant():
    """مساعد التشخيص بالذكاء الاصطناعي"""
    try:
        from datetime import datetime, timedelta

        from models.medical_record import MedicalRecord
        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        # تحليل التشخيصات الشائعة
        common_diagnoses = (
            db.session.execute(
                select(MedicalRecord.diagnosis, func.count(MedicalRecord.id).label('count'))
                .join(Visit, MedicalRecord.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    MedicalRecord.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(MedicalRecord.diagnosis)
                .order_by(func.count(MedicalRecord.id).desc())
                .limit(5)
            )
            .scalars()
            .all()
        )

        # تحليل الأدوية الموصوفة
        common_medications = (
            db.session.execute(
                select(
                    Medication.trade_name.label('medication_name'),
                    func.count(func.distinct(Prescription.id)).label('count'),
                )
                .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                .join(Visit, Prescription.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Prescription.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(Medication.trade_name)
                .order_by(func.count(func.distinct(Prescription.id)).desc())
                .limit(5)
            )
            .scalars()
            .all()
        )

        # اقتراحات التشخيص
        diagnostic_suggestions = []

        # تحليل الأعراض الشائعة
        if common_diagnoses:
            top_diagnosis = common_diagnoses[0]
            diagnostic_suggestions.append(
                {
                    'type': 'common_diagnosis',
                    'title': 'التشخيص الأكثر شيوعاً',
                    'diagnosis': top_diagnosis.diagnosis,
                    'frequency': top_diagnosis.count,
                    'suggestion': f'هذا التشخيص شائع في ممارستك ({top_diagnosis.count} مرة)',
                }
            )

        # تحليل الأدوية
        if common_medications:
            top_medication = common_medications[0]
            diagnostic_suggestions.append(
                {
                    'type': 'common_medication',
                    'title': 'الدواء الأكثر وصفاً',
                    'medication': top_medication.medication_name,
                    'frequency': top_medication.count,
                    'suggestion': f'هذا الدواء شائع في وصفاتك ({top_medication.count} مرة)',
                }
            )

        return {
            'common_diagnoses': [
                {'diagnosis': d.diagnosis, 'count': d.count} for d in common_diagnoses
            ],
            'common_medications': [
                {'medication': m.medication_name, 'count': m.count} for m in common_medications
            ],
            'diagnostic_suggestions': diagnostic_suggestions,
        }
    except Exception as e:
        logging.debug(f'Error getting AI diagnostic assistant: {e!s}')
        return {}


def get_standardized_pathways(diagnosis_text: str):
    diagnosis_text = (diagnosis_text or '').strip().lower()
    if not diagnosis_text:
        return []
    pathways = [
        {
            'id': 'diabetes_basic',
            'keywords': ['سكري', 'diabetes'],
            'title': 'مسار السكري الأساسي',
            'steps': ['قياس HbA1c', 'تثقيف غذائي', 'خطة متابعة خلال 4 أسابيع'],
        },
        {
            'id': 'hypertension_basic',
            'keywords': ['ضغط', 'hypertension'],
            'title': 'مسار ارتفاع الضغط',
            'steps': ['قياس ضغط متكرر', 'تقييم عوامل الخطر', 'تعديل نمط الحياة'],
        },
        {
            'id': 'asthma_basic',
            'keywords': ['ربو', 'asthma'],
            'title': 'مسار الربو',
            'steps': ['تقييم شدة الأعراض', 'خطة بخاخات', 'تثقيف عن المحفزات'],
        },
        {
            'id': 'uti_basic',
            'keywords': ['التهاب بول', 'uti'],
            'title': 'مسار التهاب المسالك البولية',
            'steps': ['تحليل بول', 'تقييم عوامل الخطورة', 'خطة علاج قصيرة'],
        },
    ]
    matched = []
    for p in pathways:
        if any(k in diagnosis_text for k in p['keywords']):
            matched.append({'id': p['id'], 'title': p['title'], 'steps': p['steps']})
    return matched


def get_data_based_recommendations(diagnosis_text: str):
    diagnosis_text = (diagnosis_text or '').strip()
    if not diagnosis_text:
        return []
    try:
        from datetime import datetime, timedelta

        from models.medication import Medication, Prescription, PrescriptionItem

        since = datetime.now() - timedelta(days=120)
        rows = (
            db.session.execute(
                select(Medication.trade_name, func.count(PrescriptionItem.id).label('cnt'))
                .join(PrescriptionItem.prescription)
                .join(PrescriptionItem.medication)
                .filter(
                    Prescription.diagnosis.ilike(f'%{diagnosis_text}%'),
                    Prescription.created_at >= since,
                    Prescription.doctor_id == current_user.id,
                )
                .group_by(Medication.trade_name)
                .order_by(func.count(PrescriptionItem.id).desc())
                .limit(5)
            )
            .scalars()
            .all()
        )
        out = []
        for r in rows:
            out.append({'medication': r.trade_name, 'count': int(r.cnt)})
        return out
    except Exception:
        return []


def evaluate_clinical_rules(visit, prescriptions, structured_vital_signs=None):
    warnings = []
    try:
        from models.patient import PatientAllergy

        allergies = (
            db.session.execute(select(PatientAllergy).filter_by(patient_id=visit.patient_id))
            .scalars()
            .all()
        )
        allergens = [a.allergen.lower() for a in allergies if a.allergen]
    except Exception:
        allergens = []
    med_names = []
    durations = []
    for rx in prescriptions or []:
        for item in rx.items:
            if item.medication and item.medication.trade_name:
                med_names.append(item.medication.trade_name.lower())
            if item.duration_days:
                durations.append(item.duration_days)
    dupes = {m for m in med_names if med_names.count(m) > 1}
    if dupes:
        warnings.append(
            {
                'type': 'duplicate_medication',
                'title': 'تكرار دواء',
                'message': 'هناك تكرار لأدوية في الوصفة الحالية',
            }
        )
    if allergens:
        for med in med_names:
            if any(a in med for a in allergens):
                warnings.append(
                    {
                        'type': 'allergy',
                        'title': 'تحذير حساسية',
                        'message': 'قد يتعارض دواء مع حساسية مسجلة للمريض',
                    }
                )
                break
    if any((d or 0) > 30 for d in durations):
        warnings.append(
            {
                'type': 'long_duration',
                'title': 'مدة علاج طويلة',
                'message': 'هناك أدوية بمدة تتجاوز 30 يوماً',
            }
        )
    diag = (visit.diagnosis or '').lower()
    vitals = structured_vital_signs or {}
    if ('ضغط' in diag or 'hypertension' in diag) and not vitals.get('blood_pressure'):
        warnings.append(
            {
                'type': 'missing_vitals',
                'title': 'ضغط الدم غير مسجل',
                'message': 'التشخيص يتطلب تسجيل ضغط الدم',
            }
        )
    if ('سكري' in diag or 'diabetes' in diag) and not vitals.get('blood_pressure'):
        warnings.append(
            {
                'type': 'missing_vitals',
                'title': 'علامات حيوية ناقصة',
                'message': 'يفضل تسجيل العلامات الحيوية لتقييم الحالة',
            }
        )
    return warnings


def get_patient_medical_history_ai():
    """ذكاء اصطناعي لتاريخ المريض الطبي"""
    try:
        from datetime import datetime, timedelta

        from models.medical_record import MedicalRecord
        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        # تحليل المرضى المتكررين
        frequent_patients = (
            db.session.execute(
                select(
                    Visit.patient_id,
                    func.count(Visit.id).label('visit_count'),
                    func.max(Visit.visit_date).label('last_visit'),
                )
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date >= datetime.now().date() - timedelta(days=90),
                )
                .group_by(Visit.patient_id)
                .having(func.count(Visit.id) > 2)
            )
            .scalars()
            .all()
        )

        # تحليل الحالات المزمنة
        chronic_conditions = (
            db.session.execute(
                select(MedicalRecord.diagnosis, func.count(MedicalRecord.id).label('frequency'))
                .join(Visit, MedicalRecord.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    MedicalRecord.diagnosis.in_(['السكري', 'الضغط', 'القلب', 'الربو', 'السرطان']),
                )
                .group_by(MedicalRecord.diagnosis)
            )
            .scalars()
            .all()
        )

        # تحليل الأدوية طويلة المدى
        long_term_medications = (
            db.session.execute(
                select(
                    Medication.trade_name.label('medication_name'),
                    func.count(func.distinct(Prescription.id)).label('frequency'),
                )
                .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                .join(Visit, Prescription.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Prescription.created_at >= datetime.now() - timedelta(days=90),
                )
                .group_by(Medication.trade_name)
                .having(func.count(func.distinct(Prescription.id)) > 3)
            )
            .scalars()
            .all()
        )

        return {
            'frequent_patients': [
                {
                    'patient_id': p.patient_id,
                    'visit_count': p.visit_count,
                    'last_visit': p.last_visit.strftime('%Y-%m-%d') if p.last_visit else None,
                }
                for p in frequent_patients
            ],
            'chronic_conditions': [
                {'condition': c.diagnosis, 'frequency': c.frequency} for c in chronic_conditions
            ],
            'long_term_medications': [
                {'medication': m.medication_name, 'frequency': m.frequency}
                for m in long_term_medications
            ],
        }
    except Exception as e:
        logging.debug(f'Error getting patient medical history AI: {e!s}')
        return {}


def get_treatment_recommendations():
    """توصيات العلاج الذكية"""
    try:
        from datetime import datetime, timedelta

        from models.medical_record import MedicalRecord
        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        recommendations = []

        # تحليل نجاح العلاجات
        successful_treatments = (
            db.session.execute(
                select(
                    MedicalRecord.diagnosis,
                    Medication.trade_name.label('medication_name'),
                    func.count(func.distinct(MedicalRecord.id)).label('success_count'),
                )
                .join(Visit, MedicalRecord.visit_id == Visit.id)
                .join(Prescription, Visit.id == Prescription.visit_id)
                .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.archive_status == VisitArchiveStatus.ARCHIVED,
                    MedicalRecord.created_at >= datetime.now() - timedelta(days=60),
                )
                .group_by(MedicalRecord.diagnosis, Medication.trade_name)
            )
            .scalars()
            .all()
        )

        # تحليل العلاجات الفعالة
        if successful_treatments:
            top_treatment = max(successful_treatments, key=lambda x: x.success_count)
            recommendations.append(
                {
                    'type': 'effective_treatment',
                    'title': 'علاج فعال',
                    'diagnosis': top_treatment.diagnosis,
                    'medication': top_treatment.medication_name,
                    'success_rate': top_treatment.success_count,
                    'suggestion': f'هذا العلاج فعال للتشخيص: {top_treatment.diagnosis}',
                }
            )

        # تحليل الأدوية المتفاعلة
        drug_interactions = check_drug_interactions()
        if drug_interactions:
            recommendations.append(
                {
                    'type': 'drug_interaction',
                    'title': 'تفاعل دوائي',
                    'interactions': drug_interactions,
                    'suggestion': 'تحقق من التفاعلات الدوائية قبل الوصف',
                }
            )

        return recommendations
    except Exception:
        logging.exception('Error getting treatment recommendations: %s')
        return []


def get_drug_interaction_checker():
    """فحص التفاعلات الدوائية"""
    try:
        from datetime import datetime, timedelta

        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        # قائمة التفاعلات المعروفة (مبسطة)
        known_interactions = {
            'وارفارين': ['أسبرين', 'إيبوبروفين'],
            'ديجوكسين': ['فوروسيميد', 'سبيرونولاكتون'],
            'ميثوتريكسات': ['فوليك أسيد', 'تريميثوبريم'],
        }

        # فحص الوصفات الحديثة
        recent_prescriptions = (
            db.session.execute(
                select(Prescription)
                .join(Visit)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Prescription.created_at >= datetime.now() - timedelta(days=7),
                )
            )
            .scalars()
            .all()
        )

        interactions_found = []

        for prescription in recent_prescriptions:
            medications = (
                db.session.execute(
                    select(Medication)
                    .join(PrescriptionItem)
                    .filter(PrescriptionItem.prescription_id == prescription.id)
                )
                .scalars()
                .all()
            )
            for medication in medications:
                med_name = medication.trade_name
                if med_name in known_interactions:
                    for other_med in known_interactions[med_name]:
                        # فحص إذا كان المريض يتناول الدواء الآخر
                        other_prescription = (
                            db.session.execute(
                                select(Prescription)
                                .join(Visit)
                                .join(
                                    PrescriptionItem,
                                    PrescriptionItem.prescription_id == Prescription.id,
                                )
                                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                                .filter(
                                    Visit.patient_id == prescription.visit.patient_id,
                                    Medication.trade_name == other_med,
                                    Prescription.created_at >= datetime.now() - timedelta(days=30),
                                )
                            )
                            .scalars()
                            .first()
                        )

                        if other_prescription:
                            interactions_found.append(
                                {
                                    'medication1': med_name,
                                    'medication2': other_med,
                                    'severity': 'متوسط',
                                    'description': f'تفاعل محتمل بين {med_name} و {other_med}',
                                }
                            )

        return {
            'interactions_found': interactions_found,
            'total_prescriptions_checked': len(recent_prescriptions),
            'interaction_rate': len(interactions_found) / len(recent_prescriptions) * 100
            if recent_prescriptions
            else 0,
        }
    except Exception:
        logging.exception('Error getting drug interaction checker: %s')
        return {}


def get_clinical_decision_support():
    """دعم القرارات السريرية"""
    try:
        from datetime import datetime, timedelta

        from models.medical_record import MedicalRecord
        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        support_recommendations = []

        # تحليل معدل نجاح التشخيصات
        diagnosis_success = (
            db.session.execute(
                select(
                    MedicalRecord.diagnosis,
                    func.count(MedicalRecord.id).label('total_cases'),
                    func.sum(
                        case((Visit.archive_status == VisitArchiveStatus.ARCHIVED, 1), else_=0)
                    ).label('successful_cases'),
                )
                .join(Visit, MedicalRecord.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    MedicalRecord.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(MedicalRecord.diagnosis)
            )
            .scalars()
            .all()
        )

        for diagnosis in diagnosis_success:
            success_rate = (
                (diagnosis.successful_cases / diagnosis.total_cases * 100)
                if diagnosis.total_cases > 0
                else 0
            )
            if success_rate < 70:
                support_recommendations.append(
                    {
                        'type': 'diagnosis_improvement',
                        'title': 'تحسين التشخيص',
                        'diagnosis': diagnosis.diagnosis,
                        'success_rate': round(success_rate, 2),
                        'suggestion': f'معدل نجاح التشخيص {diagnosis.diagnosis} منخفض - يحتاج مراجعة',
                    }
                )

        # تحليل فعالية الأدوية
        medication_effectiveness = (
            db.session.execute(
                select(
                    Medication.trade_name.label('medication_name'),
                    func.count(func.distinct(Prescription.id)).label('total_prescriptions'),
                    func.sum(
                        case((Visit.archive_status == VisitArchiveStatus.ARCHIVED, 1), else_=0)
                    ).label('successful_treatments'),
                )
                .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                .join(Visit, Prescription.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Prescription.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(Medication.trade_name)
            )
            .scalars()
            .all()
        )

        for medication in medication_effectiveness:
            effectiveness_rate = (
                (medication.successful_treatments / medication.total_prescriptions * 100)
                if medication.total_prescriptions > 0
                else 0
            )
            if effectiveness_rate < 60:
                support_recommendations.append(
                    {
                        'type': 'medication_effectiveness',
                        'title': 'فعالية الدواء',
                        'medication': medication.medication_name,
                        'effectiveness_rate': round(effectiveness_rate, 2),
                        'suggestion': f'فعالية الدواء {medication.medication_name} منخفضة - يحتاج مراجعة',
                    }
                )

        return support_recommendations
    except Exception:
        logging.exception('Error getting clinical decision support: %s')
        return []


def get_medical_analytics():
    """التحليلات الطبية"""
    try:
        from datetime import datetime, timedelta

        from models.medical_record import MedicalRecord
        from models.medication import Medication, Prescription, PrescriptionItem
        from models.visit import Visit

        # تحليل الأداء الطبي
        total_visits = db.session.execute(
            select(func.count()).select_from(Visit).filter(Visit.doctor_id == current_user.id)
        ).scalar()
        completed_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == current_user.id,
                Visit.archive_status == VisitArchiveStatus.ARCHIVED,
            )
        ).scalar()

        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0

        # تحليل متوسط مدة الزيارة
        avg_visit_duration = (
            db.session.execute(
                select(func.avg(Visit.duration)).filter(Visit.doctor_id == current_user.id)
            ).scalar()
            or 0
        )

        # تحليل التشخيصات
        diagnosis_distribution = (
            db.session.execute(
                select(MedicalRecord.diagnosis, func.count(MedicalRecord.id).label('count'))
                .join(Visit, MedicalRecord.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    MedicalRecord.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(MedicalRecord.diagnosis)
            )
            .scalars()
            .all()
        )

        # تحليل الأدوية
        medication_distribution = (
            db.session.execute(
                select(
                    Medication.trade_name.label('medication_name'),
                    func.count(func.distinct(Prescription.id)).label('count'),
                )
                .join(PrescriptionItem, PrescriptionItem.prescription_id == Prescription.id)
                .join(Medication, Medication.id == PrescriptionItem.medication_id)
                .join(Visit, Prescription.visit_id == Visit.id)
                .filter(
                    Visit.doctor_id == current_user.id,
                    Prescription.created_at >= datetime.now() - timedelta(days=30),
                )
                .group_by(Medication.trade_name)
            )
            .scalars()
            .all()
        )

        return {
            'completion_rate': round(completion_rate, 2),
            'avg_visit_duration': round(avg_visit_duration, 2),
            'diagnosis_distribution': [
                {'diagnosis': d.diagnosis, 'count': d.count} for d in diagnosis_distribution
            ],
            'medication_distribution': [
                {'medication': m.medication_name, 'count': m.count} for m in medication_distribution
            ],
            'performance_score': calculate_medical_performance_score(
                completion_rate, avg_visit_duration
            ),
        }
    except Exception:
        logging.exception('Error getting medical analytics: %s')
        return {}


def get_workflow_optimization():
    """تحسين سير العمل"""
    try:
        from datetime import datetime, timedelta

        from models.appointment import Appointment
        from models.visit import Visit

        optimizations = []

        # تحليل أوقات الذروة
        peak_hours = (
            db.session.execute(
                select(
                    func.extract('hour', Visit.visit_time).label('hour'),
                    func.count(Visit.id).label('count'),
                )
                .filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date >= datetime.now().date() - timedelta(days=30),
                )
                .group_by(func.extract('hour', Visit.visit_time))
            )
            .scalars()
            .all()
        )

        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 10:
                optimizations.append(
                    {
                        'type': 'peak_hours',
                        'title': 'ساعات الذروة',
                        'description': f'الساعة {max_hour.hour}:00 هي الأكثر ازدحاماً ({max_hour.count} زيارة)',
                        'suggestion': 'توزيع المواعيد على ساعات أخرى',
                    }
                )

        # تحليل المواعيد
        today = datetime.now().date()
        tomorrow_appointments = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id,
                db.func.date(Appointment.starts_at) == today + timedelta(days=1),
            )
        ).scalar()

        if tomorrow_appointments > 15:
            optimizations.append(
                {
                    'type': 'appointment_load',
                    'title': 'عبء المواعيد',
                    'description': f'لديك {tomorrow_appointments} موعد غداً',
                    'suggestion': 'مراجعة توزيع المواعيد',
                }
            )

        # تحليل الكفاءة
        avg_duration = (
            db.session.execute(
                select(func.avg(Visit.duration)).filter(Visit.doctor_id == current_user.id)
            ).scalar()
            or 0
        )

        if avg_duration > 45:
            optimizations.append(
                {
                    'type': 'efficiency',
                    'title': 'تحسين الكفاءة',
                    'description': f'متوسط مدة الزيارة: {avg_duration:.1f} دقيقة',
                    'suggestion': 'تحسين العمليات لتقليل مدة الزيارة',
                }
            )

        return optimizations
    except Exception:
        logging.exception('Error getting workflow optimization: %s')
        return []


def get_smart_reminders():
    """التذكيرات الذكية"""
    try:
        from datetime import datetime, timedelta

        from models.appointment import Appointment
        from models.medication import Prescription
        from models.visit import Visit

        reminders = []

        # تذكيرات المواعيد
        today = datetime.now().date()
        tomorrow_appointments = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id,
                db.func.date(Appointment.starts_at) == today + timedelta(days=1),
            )
        ).scalar()

        if tomorrow_appointments > 0:
            reminders.append(
                {
                    'type': 'appointments',
                    'title': 'مواعيد غداً',
                    'message': f'لديك {tomorrow_appointments} موعد غداً',
                    'priority': 'medium',
                }
            )

        # تذكيرات المتابعة
        follow_up_visits = db.session.execute(
            select(func.count())
            .select_from(Visit)
            .filter(
                Visit.doctor_id == current_user.id,
                Visit.archive_status == VisitArchiveStatus.ARCHIVED,
                Visit.completed_at >= datetime.now() - timedelta(days=7),
            )
        ).scalar()

        if follow_up_visits > 5:
            reminders.append(
                {
                    'type': 'follow_up',
                    'title': 'متابعة المرضى',
                    'message': f'تم إنجاز {follow_up_visits} زيارة هذا الأسبوع - يحتاج متابعة',
                    'priority': 'low',
                }
            )

        # تذكيرات الأدوية
        recent_prescriptions = db.session.execute(
            select(func.count())
            .select_from(Prescription)
            .join(Visit)
            .filter(
                Visit.doctor_id == current_user.id,
                Prescription.created_at >= datetime.now() - timedelta(days=3),
            )
        ).scalar()

        if recent_prescriptions > 10:
            reminders.append(
                {
                    'type': 'medications',
                    'title': 'مراجعة الأدوية',
                    'message': f'تم وصف {recent_prescriptions} دواء في آخر 3 أيام',
                    'priority': 'low',
                }
            )

        return reminders
    except Exception:
        logging.exception('Error getting smart reminders: %s')
        return []


# دوال مساعدة
def check_drug_interactions():
    """فحص التفاعلات الدوائية"""
    # قائمة مبسطة للتفاعلات المعروفة
    return [
        {'drug1': 'وارفارين', 'drug2': 'أسبرين', 'severity': 'عالي'},
        {'drug1': 'ديجوكسين', 'drug2': 'فوروسيميد', 'severity': 'متوسط'},
        {'drug1': 'ميثوتريكسات', 'drug2': 'تريميثوبريم', 'severity': 'عالي'},
    ]
