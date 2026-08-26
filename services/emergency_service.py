from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any

from flask import g
from sqlalchemy import case, or_, select

from app.extensions import db
from app.shared.enums import EmergencyStatus
from services.feature_gate_service import require_module
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


def _normalize_priority(priority: str | None) -> str | None:
    if not priority:
        return None
    val = priority.strip().upper()
    mapping = {
        'CRITICAL': 'CRITICAL',
        'RED': 'CRITICAL',
        'URGENT': 'HIGH',
        'HIGH': 'HIGH',
        'YELLOW': 'HIGH',
        'NORMAL': 'MODERATE',
        'MODERATE': 'MODERATE',
        'MEDIUM': 'MODERATE',
        'GREEN': 'MODERATE',
        'LOW': 'LOW',
    }
    return mapping.get(val)


def _severity_priority_map():
    return {
        'CRITICAL': 'CRITICAL',
        'HIGH': 'HIGH',
        'MODERATE': 'MODERATE',
        'LOW': 'LOW',
    }


def _is_valid_status(status: str) -> bool:
    if not status:
        return False
    try:
        EmergencyStatus(status)
        return True
    except ValueError:
        return status.upper() in {e.value for e in EmergencyStatus}


def _record_history(emergency_id: int, from_status: str | None, to_status: str):
    try:
        from models.emergency_status_history import EmergencyStatusHistory

        db.session.add(
            EmergencyStatusHistory(
                emergency_id=emergency_id,
                from_status=from_status,
                to_status=to_status,
                changed_by=(getattr(g, 'tenant_id', None) and getattr(g, '_current_user_id', None))
                or getattr(getattr(g, 'current_user', None), 'id', None),
            )
        )
    except Exception:
        pass


class EmergencyService:
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
            mapped = _normalize_priority(priority)
            if mapped:
                query = query.filter(EmergencyCase.severity == mapped)
            else:
                query = query.filter(EmergencyCase.severity == priority.upper())
        if status:
            query = query.filter(EmergencyCase.status == status.upper())
        if today_only:
            start = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
            query = query.filter(EmergencyCase.created_at >= start)
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

        try:
            return get_tenant_record(EmergencyCase, case_id)
        except TenantContextError:
            return None

    @staticmethod
    @require_module('emergency')
    def get_cases_by_status(status: str, limit: int = 50) -> list:
        from models.emergency import EmergencyCase

        return (
            db.session.execute(
                select(EmergencyCase)
                .filter_by(status=status.upper())
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

        active = [
            EmergencyStatus.WAITING.value,
            EmergencyStatus.TRIAGE.value,
            EmergencyStatus.TREATMENT.value,
            EmergencyStatus.IN_PROGRESS.value,
            EmergencyStatus.OBSERVATION.value,
            EmergencyStatus.RESUSCITATION.value,
        ]

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

        start_today = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
        total_today = (
            db.session.execute(
                select(func.count())
                .select_from(EmergencyCase)
                .where(EmergencyCase.created_at >= start_today)
            ).scalar()
            or 0
        )
        total_all = (
            db.session.execute(select(func.count()).select_from(EmergencyCase)).scalar() or 0
        )
        return {
            'critical': _count('CRITICAL'),
            'high': _count('HIGH'),
            'medium': _count('MODERATE'),
            'low': _count('LOW'),
            'total_today': total_today,
            'total': total_all,
        }

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
            if not chief_complaint or not chief_complaint.strip():
                return None
            try:
                patient = get_tenant_record(Patient, patient_id)
            except TenantContextError:
                return None
            mapped = _normalize_priority(priority)
            if priority and not mapped:
                return None
            if patient_id != patient.id:
                return None
            now = datetime.now(UTC)
            case_number = f'ER-{now.strftime("%Y%m%d%H%M%S")}-{patient_id}'
            case = EmergencyCase(
                patient_id=patient_id,
                chief_complaint=chief_complaint.strip(),
                diagnosis=diagnosis.strip() if diagnosis else None,
                triage_notes=notes.strip() if notes else None,
                status=EmergencyStatus.WAITING.value,
            )
            case.case_number = case_number
            if mapped:
                case.severity = mapped
            else:
                case.severity = 'MODERATE'
            db.session.add(case)
            db.session.flush()
            _record_history(case.id, None, case.status)
            if not safe_commit(db.session, error_message='Failed to create emergency case'):
                return None
            return case
        except ValueError:
            db.session.rollback()
            return None
        except Exception:
            logging.exception('Error creating emergency case: %s')
            db.session.rollback()
            return None

    @staticmethod
    @require_module('emergency')
    def update_case_status(case_id: int, status: str) -> bool:
        from models.emergency import EmergencyCase

        if not status or not _is_valid_status(status):
            return False
        normalized = status.strip().upper()
        alias = {'ACTIVE': 'WAITING', 'RESOLVED': 'COMPLETED'}
        normalized = alias.get(normalized, normalized)
        try:
            case = get_tenant_record(EmergencyCase, case_id)
        except TenantContextError:
            return False
        if not case:
            return False
        if (
            case.status == EmergencyStatus.COMPLETED.value
            and normalized != EmergencyStatus.COMPLETED.value
        ):
            return False
        if case.status == normalized:
            return True
        old = case.status
        case.status = normalized
        if normalized == EmergencyStatus.COMPLETED.value:
            case.completed_at = datetime.now(UTC)
        _record_history(case.id, old, normalized)
        safe_commit(db.session, error_message='Failed to update case status', reraise=True)
        return True

    @staticmethod
    @require_module('emergency')
    def assign_doctor(case_id: int, doctor_id: int) -> bool:
        from models.emergency import EmergencyCase

        try:
            case = get_tenant_record(EmergencyCase, case_id)
        except TenantContextError:
            return False
        if not case:
            return False
        if case.status == EmergencyStatus.COMPLETED.value:
            return False
        old = case.status
        case.status = EmergencyStatus.TREATMENT.value
        if doctor_id and case.visit_id:
            try:
                from models.visit import Visit

                visit = get_tenant_record(Visit, case.visit_id)
                if visit:
                    visit.doctor_id = doctor_id
            except TenantContextError:
                pass
        _record_history(case.id, old, case.status)
        safe_commit(db.session, error_message='Failed to assign doctor', reraise=True)
        return True

    @staticmethod
    @require_module('emergency')
    def triage_patient(case_id: int, priority: str, vital_signs: dict | None = None) -> bool:
        from models.emergency import EmergencyCase

        if not priority:
            return False
        mapped = _normalize_priority(priority)
        if not mapped:
            return False
        try:
            case = get_tenant_record(EmergencyCase, case_id)
        except TenantContextError:
            return False
        if not case:
            return False
        if case.status == EmergencyStatus.COMPLETED.value:
            return False
        try:
            case.severity = mapped
        except ValueError:
            return False
        if vital_signs is not None:
            if isinstance(vital_signs, (dict, list)):
                try:
                    case.vital_signs = json.dumps(vital_signs, ensure_ascii=False)
                except Exception:
                    return False
            elif isinstance(vital_signs, str):
                try:
                    json.loads(vital_signs)
                    case.vital_signs = vital_signs
                except Exception:
                    return False
            else:
                return False
        if case.status == EmergencyStatus.WAITING.value:
            old = case.status
            case.status = EmergencyStatus.TRIAGE.value
            _record_history(case.id, old, case.status)
        safe_commit(db.session, error_message='Failed to triage patient', reraise=True)
        return True

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


emergency_service = EmergencyService()
