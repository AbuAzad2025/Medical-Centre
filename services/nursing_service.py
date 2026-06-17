"""
Nursing Service - Business logic for nursing operations.
Extracted from routes/nurse_routes/.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timezone
from typing import Any

from app_factory import db
from sqlalchemy import and_, or_


class NursingService:
    """Centralized nursing business logic"""

    # ==================== PATIENT CARE ====================

    @staticmethod
    def get_nurse_patients(nurse_id: int, search: str | None = None) -> list:
        from models.visit import Visit
        try:
            query = Visit.query.filter(
                Visit.assigned_nurse_id == nurse_id,
                Visit.status.in_(["INPATIENT", "OBSERVATION", "WAITING"]),
            )
            if search:
                from models.patient import Patient
                query = query.join(Patient).filter(
                    or_(
                        Patient.first_name.ilike(f"%{search}%"),
                        Patient.last_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                    )
                )
            return query.order_by(Visit.created_at.desc()).all()
        except Exception:
            return []

    @staticmethod
    def get_vitals(visit_id: int, limit: int = 20) -> list:
        try:
            from models.nurse import VitalSigns
            return VitalSigns.query.filter_by(visit_id=visit_id).order_by(
                VitalSigns.recorded_at.desc()
            ).limit(limit).all()
        except Exception:
            return []

    @staticmethod
    def record_vitals(
        visit_id: int, recorded_by: int,
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
        try:
            record = VitalSigns(
                visit_id=visit_id,
                temperature=temperature,
                heart_rate=heart_rate,
                blood_pressure_systolic=blood_pressure_systolic,
                blood_pressure_diastolic=blood_pressure_diastolic,
                respiratory_rate=respiratory_rate,
                oxygen_saturation=oxygen_saturation,
                weight=weight,
                notes=notes,
                nurse_id=recorded_by,
                recorded_at=datetime.now(timezone.utc),
            )
            db.session.add(record)
            db.session.commit()
            return record
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error recording vitals: {str(e)}")
            return None

    # ==================== NURSING NOTES ====================

    @staticmethod
    def get_notes(visit_id: int, limit: int = 50) -> list:
        try:
            from models.nurse import NursingNote
            return NursingNote.query.filter_by(visit_id=visit_id).order_by(
                NursingNote.created_at.desc()
            ).limit(limit).all()
        except Exception:
            return []

    @staticmethod
    def add_note(visit_id: int, nurse_id: int, content: str, note_type: str = "general") -> Any | None:
        try:
            from models.nurse import NursingNote
            note = NursingNote(
                visit_id=visit_id,
                nurse_id=nurse_id,
                content=content,
                note_type=note_type,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(note)
            db.session.commit()
            return note
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding nursing note: {str(e)}")
            return None

    # ==================== MEDICATION ADMINISTRATION ====================

    @staticmethod
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
    def record_administration(
        administration_id: int, nurse_id: int,
        status: str = "GIVEN",
        notes: str | None = None,
    ) -> bool:
        try:
            from models.nurse import MedicationAdministrationLog
            record = MedicationAdministrationLog.query.get(administration_id)
            if not record:
                return False
            record.notes = notes
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error recording medication administration: {str(e)}")
            return False

    # ==================== CARE PLAN ====================

    @staticmethod
    def get_care_plans(visit_id: int) -> list:
        try:
            from models.clinical_pathway import PatientCarePlan
            return PatientCarePlan.query.filter_by(visit_id=visit_id).order_by(
                PatientCarePlan.created_at.desc()
            ).all()
        except Exception:
            return []

    @staticmethod
    def create_care_plan(
        visit_id: int, created_by: int,
        plan_type: str, description: str,
        goals: str | None = None,
    ) -> Any | None:
        try:
            from models.clinical_pathway import PatientCarePlan
            plan = PatientCarePlan(
                visit_id=visit_id,
                assigned_by_id=created_by,
                plan_name=plan_type,
                start_date=date.today(),
                notes=description,
                status="ACTIVE",
            )
            db.session.add(plan)
            db.session.commit()
            return plan
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating care plan: {str(e)}")
            return None

    # ==================== TASKS ====================

    @staticmethod
    def get_pending_tasks(nurse_id: int | None = None) -> list:
        try:
            from models.task_management import Task
            query = Task.query.filter(Task.status != "COMPLETED")
            if nurse_id:
                query = query.filter_by(assigned_to_id=nurse_id)
            return query.order_by(Task.created_at.desc()).all()
        except Exception:
            return []

    @staticmethod
    def complete_task(task_id: int, completed_by: int) -> bool:
        try:
            from models.task_management import Task
            task = Task.query.get(task_id)
            if not task:
                return False
            task.status = "COMPLETED"
            task.completed_by_id = completed_by
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error completing task: {str(e)}")
            return False

    # ==================== DASHBOARD STATS ====================

    @staticmethod
    def get_dashboard_stats(nurse_id: int) -> dict:
        try:
            return {
                "assigned_patients": len(NursingService.get_nurse_patients(nurse_id)),
                "pending_tasks": len(NursingService.get_pending_tasks(nurse_id)),
                "pending_administrations": len(NursingService.get_pending_administrations()),
            }
        except Exception:
            return {"assigned_patients": 0, "pending_tasks": 0, "pending_administrations": 0}


# Singleton
nursing_service = NursingService()
