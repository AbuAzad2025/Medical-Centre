from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import or_, select

from app.extensions import db
from services.feature_gate_service import require_module
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class NursingService:
    @staticmethod
    @require_module('nursing')
    def get_nurse_patients(nurse_id: int, search: str | None = None) -> list:
        from models.visit import Visit

        try:
            query = select(Visit)
            if search:
                from models.patient import Patient

                query = query.join(Patient).filter(
                    or_(
                        Patient.first_name.ilike(f'%{search}%'),
                        Patient.last_name.ilike(f'%{search}%'),
                        Patient.phone.ilike(f'%{search}%'),
                    )
                )
            return db.session.execute(query.order_by(Visit.created_at.desc())).scalars().all()
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def get_vitals(visit_id: int, limit: int = 20) -> list:
        try:
            from models.nurse import VitalSigns
            from models.visit import Visit

            try:
                get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return []
            return (
                db.session.execute(
                    select(VitalSigns)
                    .filter_by(visit_id=visit_id)
                    .order_by(VitalSigns.recorded_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def record_vitals(
        visit_id: int,
        recorded_by: int,
        temperature: float | None = None,
        heart_rate: int | None = None,
        blood_pressure_systolic: int | None = None,
        blood_pressure_diastolic: int | None = None,
        respiratory_rate: int | None = None,
        oxygen_saturation: float | None = None,
        blood_sugar: float | None = None,
        weight: float | None = None,
        height: float | None = None,
        notes: str | None = None,
    ) -> Any | None:
        from models.nurse import VitalSigns
        from models.visit import Visit

        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return None
            if temperature is not None and not 30 <= float(temperature) <= 45:
                return None
            if heart_rate is not None and not 20 <= int(heart_rate) <= 250:
                return None
            if (
                blood_pressure_systolic is not None
                and not 50 <= int(blood_pressure_systolic) <= 300
            ):
                return None
            if (
                blood_pressure_diastolic is not None
                and not 30 <= int(blood_pressure_diastolic) <= 200
            ):
                return None
            if respiratory_rate is not None and not 5 <= int(respiratory_rate) <= 80:
                return None
            if oxygen_saturation is not None and not 50 <= int(oxygen_saturation) <= 100:
                return None
            if blood_sugar is not None and not 10 <= float(blood_sugar) <= 800:
                return None
            if blood_pressure_systolic is not None and blood_pressure_diastolic is not None:
                if int(blood_pressure_diastolic) >= int(blood_pressure_systolic):
                    return None
            has_any = any(
                v is not None
                for v in [
                    temperature,
                    heart_rate,
                    blood_pressure_systolic,
                    blood_pressure_diastolic,
                    respiratory_rate,
                    oxygen_saturation,
                    blood_sugar,
                    weight,
                    height,
                ]
            )
            if not has_any and not notes:
                return None
            record = VitalSigns(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                temperature=temperature,
                heart_rate=heart_rate,
                blood_pressure_systolic=blood_pressure_systolic,
                blood_pressure_diastolic=blood_pressure_diastolic,
                respiratory_rate=respiratory_rate,
                oxygen_saturation=int(oxygen_saturation) if oxygen_saturation is not None else None,
                blood_sugar=blood_sugar,
                weight=weight,
                height=height,
                notes=notes.strip() if notes else None,
                nurse_id=recorded_by,
                recorded_at=datetime.now(UTC),
            )
            db.session.add(record)
            if not safe_commit(db.session, error_message='Failed to record vitals'):
                return None
            return record
        except Exception:
            logging.exception('Error recording vitals: %s')
            db.session.rollback()
            return None

    @staticmethod
    @require_module('nursing')
    def get_notes(visit_id: int, limit: int = 50) -> list:
        try:
            from models.nurse import NursingNote

            return (
                db.session.execute(
                    select(NursingNote)
                    .filter_by(visit_id=visit_id)
                    .order_by(NursingNote.created_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def add_note(
        visit_id: int, nurse_id: int, content: str, note_type: str = 'general'
    ) -> Any | None:
        try:
            from models.nurse import NursingNote

            if not content or not content.strip():
                return None
            note = NursingNote(
                visit_id=visit_id,
                nurse_id=nurse_id,
                content=content.strip(),
                note_type=note_type,
                created_at=datetime.now(UTC),
            )
            db.session.add(note)
            if not safe_commit(db.session, error_message='Failed to add nursing note'):
                return None
            return note
        except Exception:
            logging.exception('Error adding nursing note: %s')
            db.session.rollback()
            return None

    @staticmethod
    @require_module('nursing')
    def get_pending_administrations(visit_id: int | None = None) -> list:
        try:
            from models.nurse import MedicationAdministrationLog

            query = MedicationAdministrationLog.query
            if visit_id:
                try:
                    from models.visit import Visit

                    get_tenant_record(Visit, visit_id)
                except TenantContextError:
                    return []
                query = query.filter_by(visit_id=visit_id)
            return query.order_by(MedicationAdministrationLog.administered_at.asc()).all()
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def record_administration(
        administration_id: int,
        nurse_id: int,
        status: str = 'GIVEN',
        notes: str | None = None,
    ) -> bool:
        try:
            from models.nurse import MedicationAdministrationLog

            try:
                record = get_tenant_record(MedicationAdministrationLog, administration_id)
            except TenantContextError:
                return False
            record.notes = notes.strip() if notes else None
            return safe_commit(
                db.session, error_message='Failed to record medication administration'
            )
        except Exception:
            logging.exception('Error recording medication administration: %s')
            db.session.rollback()
            return False

    @staticmethod
    @require_module('nursing')
    def record_emar_administration(
        administration_id: int,
        nurse_id: int,
        status: str = 'GIVEN',
        notes: str | None = None,
        refusal_reason: str | None = None,
        patient_id: int | None = None,
        medication_id: int | None = None,
    ) -> dict:
        from app.shared.enums import eMARAdministrationStatus
        from models.emar import eMARAdministration

        try:
            try:
                record = get_tenant_record(eMARAdministration, administration_id)
            except TenantContextError:
                return {'success': False, 'message': 'سجل الدواء المجدول غير موجود'}
            requested = (status or eMARAdministrationStatus.GIVEN.value).strip().upper()
            allowed = {e.value for e in eMARAdministrationStatus}
            if requested not in allowed:
                return {'success': False, 'message': 'حالة التوثيق غير مدعومة'}
            if patient_id is not None and int(patient_id) != int(record.patient_id):
                return {'success': False, 'message': 'المريض غير مطابق للموعد المجدول'}
            if (
                medication_id is not None
                and record.medication_id is not None
                and int(medication_id) != int(record.medication_id)
            ):
                return {'success': False, 'message': 'الدواء غير مطابق للوصفة المجدولة'}
            current = (record.status or '').strip().upper()
            terminal = {
                eMARAdministrationStatus.GIVEN.value,
                eMARAdministrationStatus.REFUSED.value,
                eMARAdministrationStatus.HELD.value,
                eMARAdministrationStatus.NOT_GIVEN.value,
                eMARAdministrationStatus.PARTIAL.value,
                eMARAdministrationStatus.MISSED.value,
            }
            if current in terminal:
                return {'success': False, 'message': 'تم توثيق هذا الموعد مسبقاً ولا يمكن التعديل'}
            if requested == eMARAdministrationStatus.GIVEN.value:
                if current != eMARAdministrationStatus.SCHEDULED.value:
                    return {
                        'success': False,
                        'message': 'لا يمكن تسجيل الإعطاء إلا لسجل بحالة مجدول',
                    }
                record.status = eMARAdministrationStatus.GIVEN.value
                record.administered_time = datetime.now(UTC)
                record.nurse_id = nurse_id
                if notes:
                    record.notes = notes.strip()
            elif requested == eMARAdministrationStatus.REFUSED.value:
                reason = (refusal_reason or notes or '').strip()
                if not reason:
                    return {'success': False, 'message': 'سبب الرفض مطلوب'}
                if current != eMARAdministrationStatus.SCHEDULED.value:
                    return {'success': False, 'message': 'لا يمكن تسجيل الرفض إلا لسجل بحالة مجدول'}
                record.status = eMARAdministrationStatus.REFUSED.value
                record.refusal_reason = reason
                if notes:
                    record.notes = notes.strip()
                record.nurse_id = nurse_id
                record.administered_time = datetime.now(UTC)
            elif requested == eMARAdministrationStatus.HELD.value:
                reason = (refusal_reason or notes or '').strip()
                if not reason:
                    return {'success': False, 'message': 'سبب التعليق مطلوب'}
                if current != eMARAdministrationStatus.SCHEDULED.value:
                    return {'success': False, 'message': 'لا يمكن تعليق إلا سجل مجدول'}
                record.status = eMARAdministrationStatus.HELD.value
                record.hold_reason = reason
                if notes:
                    record.notes = notes.strip()
                record.nurse_id = nurse_id
            else:
                record.status = requested
                record.nurse_id = nurse_id
                if notes:
                    record.notes = notes.strip()
            if not safe_commit(db.session, error_message='Failed to record eMAR administration'):
                return {'success': False, 'message': 'تعذر حفظ سجل إعطاء الدواء'}
            return {'success': True}
        except Exception:
            logging.exception('Error recording eMAR administration: %s')
            db.session.rollback()
            return {'success': False, 'message': 'حدث خطأ في تسجيل إعطاء الدواء'}

    @staticmethod
    @require_module('nursing')
    def get_care_plans(visit_id: int) -> list:
        try:
            from models.clinical_pathway import PatientCarePlan
            from models.visit import Visit

            try:
                get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return []
            return (
                db.session.execute(
                    select(PatientCarePlan)
                    .filter_by(visit_id=visit_id)
                    .order_by(PatientCarePlan.created_at.desc())
                )
                .scalars()
                .all()
            )
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def create_care_plan(
        visit_id: int,
        created_by: int,
        plan_type: str,
        description: str,
        goals: str | None = None,
    ) -> Any | None:
        try:
            from models.clinical_pathway import PatientCarePlan
            from models.visit import Visit

            if not plan_type or not plan_type.strip():
                return None
            if not description or not description.strip():
                return None
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return None
            plan = PatientCarePlan(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                assigned_by_id=created_by,
                plan_name=plan_type.strip(),
                start_date=date.today(),
                notes=description.strip(),
                status='ACTIVE',
            )
            db.session.add(plan)
            if not safe_commit(db.session, error_message='Failed to create care plan'):
                return None
            return plan
        except Exception:
            logging.exception('Error creating care plan: %s')
            db.session.rollback()
            return None

    @staticmethod
    @require_module('nursing')
    def get_pending_tasks(nurse_id: int | None = None) -> list:
        try:
            from models.task_management import Task

            query = select(Task).filter(Task.status.notin_(['completed', 'cancelled']))
            if nurse_id:
                query = query.filter_by(assigned_to=nurse_id)
            return db.session.execute(query.order_by(Task.created_at.desc())).scalars().all()
        except Exception:
            return []

    @staticmethod
    @require_module('nursing')
    def complete_task(task_id: int, completed_by: int) -> bool:
        try:
            from models.task_management import Task

            try:
                task = get_tenant_record(Task, task_id)
            except TenantContextError:
                return False
            if task.status == 'completed':
                return False
            task.status = 'completed'
            task.completed_at = datetime.now(UTC)
            return safe_commit(db.session, error_message='Failed to complete task')
        except Exception:
            logging.exception('Error completing task: %s')
            db.session.rollback()
            return False

    @staticmethod
    @require_module('nursing')
    def get_dashboard_stats(nurse_id: int) -> dict:
        try:
            return {
                'assigned_patients': len(NursingService.get_nurse_patients(nurse_id)),
                'pending_tasks': len(NursingService.get_pending_tasks(nurse_id)),
                'pending_administrations': len(NursingService.get_pending_administrations()),
            }
        except Exception:
            return {'assigned_patients': 0, 'pending_tasks': 0, 'pending_administrations': 0}


nursing_service = NursingService()
