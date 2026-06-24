"""
Emergency Service - Business logic for emergency cases.
Extracted from routes/emergency/.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, date, timezone
from typing import Any

from app_factory import db
from sqlalchemy import and_, or_, case


class EmergencyService:
    """Centralized emergency case business logic"""

    # ==================== CASE QUERIES ====================

    @staticmethod
    def list_cases(
        search: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        doctor_id: int | None = None,
        today_only: bool = False,
        page: int = 1,
        per_page: int = 12,
    ):
        from models.emergency import EmergencyCase
        from models.patient import Patient
        query = EmergencyCase.query
        if search:
            query = query.join(Patient).filter(
                or_(
                    EmergencyCase.chief_complaint.ilike(f"%{search}%"),
                    Patient.first_name.ilike(f"%{search}%"),
                    Patient.last_name.ilike(f"%{search}%"),
                    EmergencyCase.diagnosis.ilike(f"%{search}%"),
                )
            )
        if priority:
            # EmergencyCase.priority is an instance-only property over `severity`;
            # filtering happens on the real `severity` column.
            query = query.filter(EmergencyCase.severity == priority.upper())
        if status:
            query = query.filter(EmergencyCase.status == status)
        # NOTE: EmergencyCase has no doctor_id column (doctor is linked via the visit);
        # filtering by doctor requires a schema/migration decision and is intentionally
        # not applied here. `doctor_id` is accepted for signature compatibility only.
        if today_only:
            query = query.filter(EmergencyCase.created_at >= date.today())
        query = query.order_by(
            case(
                (EmergencyCase.severity == "CRITICAL", 0),
                (EmergencyCase.severity == "HIGH", 1),
                (EmergencyCase.severity == "MODERATE", 2),
                else_=3,
            ),
            EmergencyCase.created_at.desc(),
        )
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_case(case_id: int):
        from models.emergency import EmergencyCase
        return EmergencyCase.query.get(case_id)

    @staticmethod
    def get_cases_by_status(status: str, limit: int = 50) -> list:
        from models.emergency import EmergencyCase
        return EmergencyCase.query.filter_by(status=status).order_by(
            EmergencyCase.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def get_patient_cases(patient_id: int) -> list:
        from models.emergency import EmergencyCase
        return EmergencyCase.query.filter_by(patient_id=patient_id).order_by(
            EmergencyCase.created_at.desc()
        ).all()

    @staticmethod
    def get_triage_stats() -> dict:
        from models.emergency import EmergencyCase
        today_start = datetime.combine(date.today(), datetime.min.time())
        active = ["WAITING", "TRIAGE", "TREATMENT", "IN_PROGRESS", "OBSERVATION", "RESUSCITATION"]
        base = EmergencyCase.query.filter(EmergencyCase.created_at >= today_start)
        return {
            "critical": base.filter(EmergencyCase.severity == "CRITICAL", EmergencyCase.status.in_(active)).count(),
            "high": base.filter(EmergencyCase.severity == "HIGH", EmergencyCase.status.in_(active)).count(),
            "medium": base.filter(EmergencyCase.severity == "MODERATE", EmergencyCase.status.in_(active)).count(),
            "low": base.filter(EmergencyCase.severity == "LOW", EmergencyCase.status.in_(active)).count(),
            "total_today": base.count(),
        }

    # ==================== CASE MANAGEMENT ====================

    @staticmethod
    def create_case(
        patient_id: int, doctor_id: int | None = None,
        chief_complaint: str = "", priority: str = "MEDIUM",
        diagnosis: str | None = None, notes: str | None = None,
    ) -> Any | None:
        from models.emergency import EmergencyCase
        try:
            now = datetime.now(timezone.utc)
            case_number = f"ER-{now.strftime('%Y%m%d%H%M%S')}-{patient_id}"
            case = EmergencyCase(
                patient_id=patient_id,
                chief_complaint=chief_complaint,
                diagnosis=diagnosis,
                triage_notes=notes,
                status="WAITING",
            )
            case.case_number = case_number
            if priority:
                case.priority = priority
            db.session.add(case)
            db.session.commit()
            return case
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating emergency case: {str(e)}")
            return None

    @staticmethod
    def update_case_status(case_id: int, status: str) -> bool:
        from models.emergency import EmergencyCase
        case = EmergencyCase.query.get(case_id)
        if not case:
            return False
        case.status = status
        if status == "COMPLETED":
            case.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return True

    @staticmethod
    def assign_doctor(case_id: int, doctor_id: int) -> bool:
        # NOTE: EmergencyCase has no doctor_id column; doctor assignment is modelled
        # via the linked visit. Persisting the assignment here requires a schema/
        # migration decision, so this method only advances the case status.
        from models.emergency import EmergencyCase
        case = EmergencyCase.query.get(case_id)
        if not case:
            return False
        case.status = "TREATMENT"
        db.session.commit()
        return True

    # ==================== TRIAGE ====================

    @staticmethod
    def triage_patient(
        case_id: int, priority: str, vital_signs: dict | None = None
    ) -> bool:
        from models.emergency import EmergencyCase
        case = EmergencyCase.query.get(case_id)
        if not case:
            return False
        # priority is a property that maps onto the real `severity` column
        case.priority = priority
        if vital_signs is not None:
            # vital_signs is a TEXT column storing a JSON string
            case.vital_signs = json.dumps(vital_signs) if isinstance(vital_signs, (dict, list)) else vital_signs
        db.session.commit()
        return True

    # ==================== NOTIFICATION ====================

    @staticmethod
    def notify_staff(case: Any, event: str = "new_case") -> None:
        try:
            from services.notification_service import NotificationService
            if event == "new_case":
                NotificationService.send_notification(
                    recipient_role="emergency",
                    title="حالة طوارئ جديدة",
                    message=f"حالة جديدة: {case.chief_complaint} - أولوية {case.priority}",
                    notification_type="emergency",
                )
            elif event == "priority_change":
                NotificationService.send_notification(
                    recipient_role="emergency",
                    title="تغيير أولوية الحالة",
                    message=f"تم تغيير أولوية الحالة #{case.id} إلى {case.priority}",
                    notification_type="warning",
                )
        except Exception:
            pass


# Singleton
emergency_service = EmergencyService()
