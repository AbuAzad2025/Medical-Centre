"""
Emergency Service - Business logic for emergency cases.
Extracted from routes/emergency/.
"""
from __future__ import annotations

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
                    Patient.name.ilike(f"%{search}%"),
                    EmergencyCase.diagnosis.ilike(f"%{search}%"),
                )
            )
        if priority:
            query = query.filter(EmergencyCase.priority == priority)
        if status:
            query = query.filter(EmergencyCase.status == status)
        if doctor_id:
            query = query.filter(EmergencyCase.doctor_id == doctor_id)
        if today_only:
            query = query.filter(EmergencyCase.created_at >= date.today())
        query = query.order_by(
            case(
                (EmergencyCase.priority == "CRITICAL", 0),
                (EmergencyCase.priority == "HIGH", 1),
                (EmergencyCase.priority == "MEDIUM", 2),
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
        base = EmergencyCase.query.filter(EmergencyCase.created_at >= today_start)
        return {
            "critical": base.filter(EmergencyCase.priority == "CRITICAL", EmergencyCase.status.in_(["WAITING", "IN_TREATMENT"])).count(),
            "high": base.filter(EmergencyCase.priority == "HIGH", EmergencyCase.status.in_(["WAITING", "IN_TREATMENT"])).count(),
            "medium": base.filter(EmergencyCase.priority == "MEDIUM", EmergencyCase.status.in_(["WAITING", "IN_TREATMENT"])).count(),
            "low": base.filter(EmergencyCase.priority == "LOW", EmergencyCase.status.in_(["WAITING", "IN_TREATMENT"])).count(),
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
        from models.emergency import EmergencyCase
        case = EmergencyCase.query.get(case_id)
        if not case:
            return False
        case.doctor_id = doctor_id
        case.status = "IN_TREATMENT"
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
        case.priority = priority
        if vital_signs:
            case.vital_signs = vital_signs
        case.triaged_at = datetime.now(timezone.utc)
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
