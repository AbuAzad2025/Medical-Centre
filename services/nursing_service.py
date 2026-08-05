"""
Nursing Service - Business logic for nursing operations.
Extracted from routes/nurse_routes/.
"""

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
    """Centralized nursing business logic"""

    # ==================== PATIENT CARE ====================

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
        notes: str | None = None,
    ) -> Any | None:
        from models.nurse import VitalSigns
        from models.visit import Visit

        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return None
            record = VitalSigns(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                temperature=temperature,
                heart_rate=heart_rate,
                blood_pressure_systolic=blood_pressure_systolic,
                blood_pressure_diastolic=blood_pressure_diastolic,
                respiratory_rate=respiratory_rate,
                oxygen_saturation=oxygen_saturation,
                weight=weight,
                notes=notes,
                nurse_id=recorded_by,
                recorded_at=datetime.now(UTC),
            )
            db.session.add(record)
            if not safe_commit(db.session, error_message='Failed to record vitals'):
                return None
            return record
        except Exception:
            logging.exception("Error recording vitals: %s")
            return None

    # ==================== NURSING NOTES ====================

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

            note = NursingNote(
                visit_id=visit_id,
                nurse_id=nurse_id,
                content=content,
                note_type=note_type,
                created_at=datetime.now(UTC),
            )
            db.session.add(note)
            if not safe_commit(db.session, error_message='Failed to add nursing note'):
                return None
            return note
        except Exception:
            logging.exception("Error adding nursing note: %s")
            return None

    # ==================== MEDICATION ADMINISTRATION ====================

    @staticmethod
    @require_module('nursing')
    def get_pending_administrations(visit_id: int | None = None) -> list:
        try:
            from models.nurse import MedicationAdministrationLog

            query = MedicationAdministrationLog.query
            if visit_id:
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
            record.notes = notes
            return safe_commit(
                db.session, error_message='Failed to record medication administration'
            )
        except Exception:
            logging.exception("Error recording medication administration: %s")
            return False

    # ==================== CARE PLAN ====================

    @staticmethod
    @require_module('nursing')
    def get_care_plans(visit_id: int) -> list:
        try:
            from models.clinical_pathway import PatientCarePlan

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

            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return None
            plan = PatientCarePlan(
                patient_id=visit.patient_id,
                visit_id=visit_id,
                assigned_by_id=created_by,
                plan_name=plan_type,
                start_date=date.today(),
                notes=description,
                status='ACTIVE',
            )
            db.session.add(plan)
            if not safe_commit(db.session, error_message='Failed to create care plan'):
                return None
            return plan
        except Exception:
            logging.exception("Error creating care plan: %s")
            return None

    # ==================== TASKS ====================

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
            task.status = 'completed'
            task.completed_at = datetime.now(UTC)
            return safe_commit(db.session, error_message='Failed to complete task')
        except Exception:
            logging.exception("Error completing task: %s")
            return False

    # ==================== DASHBOARD STATS ====================

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


# Singleton
nursing_service = NursingService()
