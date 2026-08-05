"""
Emergency Service - Business logic for emergency cases.
Extracted from routes/emergency/.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import case, or_, select

from app.extensions import db
from services.feature_gate_service import require_module
from utils.db_safety import safe_commit


class EmergencyService:
    """Centralized emergency case business logic"""

    # ==================== CASE QUERIES ====================

    @staticmethod
    @require_module('emergency')
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
                    EmergencyCase.chief_complaint.ilike(f'%{search}%'),
                    Patient.first_name.ilike(f'%{search}%'),
                    Patient.last_name.ilike(f'%{search}%'),
                    EmergencyCase.diagnosis.ilike(f'%{search}%'),
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
                (EmergencyCase.severity == 'CRITICAL', 0),
                (EmergencyCase.severity == 'HIGH', 1),
                (EmergencyCase.severity == 'MODERATE', 2),
                else_=3,
            ),
            EmergencyCase.created_at.desc(),
        )
        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    @require_module('emergency')
    def get_case(case_id: int):
        from models.emergency import EmergencyCase

        return db.session.execute(select(EmergencyCase).filter_by(id=case_id)).scalars().first()

    @staticmethod
    @require_module('emergency')
    def get_cases_by_status(status: str, limit: int = 50) -> list:
        from models.emergency import EmergencyCase

        return (
            db.session.execute(
                select(EmergencyCase)
                .filter_by(status=status)
                .order_by(EmergencyCase.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    @staticmethod
    @require_module('emergency')
    def get_patient_cases(patient_id: int) -> list:
        from models.emergency import EmergencyCase

        return (
            db.session.execute(
                select(EmergencyCase)
                .filter_by(patient_id=patient_id)
                .order_by(EmergencyCase.created_at.desc())
            )
            .scalars()
            .all()
        )

    @staticmethod
    @require_module('emergency')
    def get_triage_stats() -> dict:
        from sqlalchemy import func

        from models.emergency import EmergencyCase

        datetime.combine(date.today(), datetime.min.time())
        active = ['WAITING', 'TRIAGE', 'TREATMENT', 'IN_PROGRESS', 'OBSERVATION', 'RESUSCITATION']

        def _count(severity):
            return (
                db.session.execute(
                    select(func.count())
                    .select_from(EmergencyCase)
                    .where(
                        EmergencyCase.severity == severity,
                        EmergencyCase.status.in_(active),
                    )
                ).scalar()
                or 0
            )

        total = db.session.execute(select(func.count()).select_from(EmergencyCase)).scalar() or 0
        return {
            'critical': _count('CRITICAL'),
            'high': _count('HIGH'),
            'medium': _count('MODERATE'),
            'low': _count('LOW'),
            'total_today': total,
        }

    # ==================== CASE MANAGEMENT ====================

    @staticmethod
    @require_module('emergency')
    def create_case(
        patient_id: int,
        doctor_id: int | None = None,
        chief_complaint: str = '',
        priority: str = 'MEDIUM',
        diagnosis: str | None = None,
        notes: str | None = None,
    ) -> Any | None:
        from models.emergency import EmergencyCase
        from models.patient import Patient

        try:
            if not db.session.execute(select(Patient).filter_by(id=patient_id)).scalars().first():
                return None
            now = datetime.now(UTC)
            case_number = f'ER-{now.strftime("%Y%m%d%H%M%S")}-{patient_id}'
            case = EmergencyCase(
                patient_id=patient_id,
                chief_complaint=chief_complaint,
                diagnosis=diagnosis,
                triage_notes=notes,
                status='WAITING',
            )
            case.case_number = case_number
            if priority:
                case.priority = priority
            db.session.add(case)
            if not safe_commit(db.session, error_message='Failed to create emergency case'):
                return None
            return case
        except Exception:
            logging.exception("Error creating emergency case: %s")
            return None

    @staticmethod
    @require_module('emergency')
    def update_case_status(case_id: int, status: str) -> bool:
        from models.emergency import EmergencyCase

        case = db.session.execute(select(EmergencyCase).filter_by(id=case_id)).scalars().first()
        if not case:
            return False
        case.status = status
        if status == 'COMPLETED':
            case.completed_at = datetime.now(UTC)
        safe_commit(db.session, error_message='Failed to update case status', reraise=True)
        return True

    @staticmethod
    @require_module('emergency')
    def assign_doctor(case_id: int, doctor_id: int) -> bool:
        # NOTE: EmergencyCase has no doctor_id column; doctor assignment is modelled
        # via the linked visit. Persisting the assignment here requires a schema/
        # migration decision, so this method only advances the case status.
        from models.emergency import EmergencyCase

        case = db.session.execute(select(EmergencyCase).filter_by(id=case_id)).scalars().first()
        if not case:
            return False
        case.status = 'TREATMENT'
        safe_commit(db.session, error_message='Failed to assign doctor', reraise=True)
        return True

    # ==================== TRIAGE ====================

    @staticmethod
    @require_module('emergency')
    def triage_patient(case_id: int, priority: str, vital_signs: dict | None = None) -> bool:
        from models.emergency import EmergencyCase

        case = db.session.execute(select(EmergencyCase).filter_by(id=case_id)).scalars().first()
        if not case:
            return False
        # priority is a property that maps onto the real `severity` column
        case.priority = priority
        if vital_signs is not None:
            # vital_signs is a TEXT column storing a JSON string
            case.vital_signs = (
                json.dumps(vital_signs) if isinstance(vital_signs, (dict, list)) else vital_signs
            )
        safe_commit(db.session, error_message='Failed to triage patient', reraise=True)
        return True

    # ==================== NOTIFICATION ====================

    @staticmethod
    @require_module('emergency')
    def notify_staff(case: Any, event: str = 'new_case') -> None:
        try:
            from services.notification_service import NotificationService

            if event == 'new_case':
                NotificationService.send_notification(
                    recipient_role='emergency',
                    title='حالة طوارئ جديدة',
                    message=f'حالة جديدة: {case.chief_complaint} - أولوية {case.priority}',
                    notification_type='emergency',
                )
            elif event == 'priority_change':
                NotificationService.send_notification(
                    recipient_role='emergency',
                    title='تغيير أولوية الحالة',
                    message=f'تم تغيير أولوية الحالة #{case.id} إلى {case.priority}',
                    notification_type='warning',
                )
        except Exception:
            pass


# Singleton
emergency_service = EmergencyService()
