"""
Lab Service - Business logic for lab operations.
Extracted from routes/lab/ to centralize validation, creation, and workflow.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from flask import g
from sqlalchemy import func, select

from app.extensions import db
from services.feature_gate_service import require_module
from utils.db_safety import safe_commit


class LabService:
    """Centralized lab business logic"""

    # ==================== REQUEST CREATION ====================

    @staticmethod
    @require_module('lab')
    def create_request(
        visit_id: int,
        test_ids: list[int],
        *,
        requested_by: int | None = None,
        notes: str | None = None,
        tenant_id: int | None = None,
    ) -> tuple[bool, dict]:
        """Create a structured LabRequest with LabResult rows from catalog test IDs.

        P2-001: This is the canonical path for a clinician to order lab tests.
        Free-text notes are still preserved in the linked Treatment record (see
        P2-000 deprecation contract); this method creates the structured order.
        """
        from models.lab_request import LabRequest, LabResult
        from models.lab_test_catalog import LabTestCatalog
        from models.visit import Visit

        if not test_ids:
            return False, {'error': 'No test IDs provided'}

        visit = (
            db.session.execute(
                select(Visit).filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id)
            )
            .scalars()
            .first()
        )
        if not visit:
            return False, {'error': 'Visit not found'}

        tenant_id = tenant_id or visit.tenant_id

        from app.core.module.models import TenantModule

        if (
            not db.session.execute(
                select(TenantModule).filter_by(
                    tenant_id=tenant_id, module_name='lab', is_active=True
                )
            )
            .scalars()
            .first()
        ):
            raise PermissionError('Lab module is not enabled for this tenant')
        now = datetime.now(UTC)
        request_number = f'LR-{visit_id}-{int(now.timestamp())}'

        lab_request = LabRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            requested_by=requested_by,
            request_number=request_number,
            status='REQUESTED',
            notes=notes or '',
            created_at=now,
            updated_at=now,
        )
        db.session.add(lab_request)
        db.session.flush()

        catalog_items = (
            db.session.execute(
                select(LabTestCatalog).filter(
                    LabTestCatalog.id.in_(test_ids), LabTestCatalog.is_active
                )
            )
            .scalars()
            .all()
        )
        found_ids = {c.id for c in catalog_items}
        missing = set(test_ids) - found_ids
        if missing:
            safe_commit(db.session, error_message='Unknown or inactive test IDs')
            return False, {'error': f'Unknown or inactive test IDs: {sorted(missing)}'}

        for catalog in catalog_items:
            result = LabResult(
                tenant_id=tenant_id,
                request_id=lab_request.id,
                patient_id=visit.patient_id,
                test_code=catalog.code,
                test_name=catalog.name_ar or catalog.name_en or catalog.code,
                unit=catalog.unit,
                reference_range=catalog.default_reference_range,
                status='PENDING',
                created_at=now,
                updated_at=now,
            )
            db.session.add(result)

        return True, {'lab_request_id': lab_request.id, 'request_number': request_number}

    # ==================== WORKLIST QUERIES ====================

    @staticmethod
    @require_module('lab')
    def get_worklist(status: str = 'REQUESTED', limit: int = 200) -> list:
        from models.lab_request import LabRequest

        today = date.today()
        allowed = {
            'REQUESTED',
            'COLLECTED',
            'RECEIVED',
            'ANALYZING',
            'REVIEWED',
            'APPROVED',
            'IN_PROGRESS',
            'DONE',
            'DONE_TODAY',
            'ALL',
        }
        if status not in allowed:
            status = 'REQUESTED'
        q = LabRequest.query
        if status == 'DONE_TODAY':
            q = q.filter(
                LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today
            )
        elif status != 'ALL':
            q = q.filter(LabRequest.status == status)
        return q.order_by(LabRequest.created_at.desc()).limit(limit).all()

    @staticmethod
    @require_module('lab')
    def get_request_counts() -> dict:
        from models.lab_request import LabRequest

        today = date.today()
        return {
            'requested': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(LabRequest.status == 'REQUESTED')
            ).scalar(),
            'in_progress': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(
                    LabRequest.status.in_(
                        [
                            'COLLECTED',
                            'RECEIVED',
                            'ANALYZING',
                            'REVIEWED',
                            'APPROVED',
                            'IN_PROGRESS',
                        ]
                    )
                )
            ).scalar(),
            'done_today': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today)
            ).scalar(),
        }

    @staticmethod
    @require_module('lab')
    def get_request_by_id(request_id: int) -> Any | None:
        from models.lab_request import LabRequest

        return (
            db.session.execute(
                select(LabRequest).filter(
                    LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )

    @staticmethod
    @require_module('lab')
    def get_results_by_request(request_id: int) -> list:
        from models.lab_request import LabResult

        return (
            db.session.execute(select(LabResult).filter_by(request_id=request_id)).scalars().all()
        )

    @staticmethod
    @require_module('lab')
    def get_results_by_patient(patient_id: int) -> list:
        from models.lab_request import LabRequest, LabResult

        return (
            db.session.execute(
                select(LabResult)
                .join(LabRequest)
                .filter(LabRequest.patient_id == patient_id, LabResult.status == 'COMPLETED')
                .order_by(LabResult.updated_at.desc())
            )
            .scalars()
            .all()
        )

    # ==================== RESULT CREATION ====================

    @staticmethod
    @require_module('lab')
    def create_results_from_form(lab_request: Any, form_data: dict) -> tuple[list, list]:
        """Create LabResult entries from form data. Returns (created_ids, errors)."""
        from models.lab_request import LabResult

        result_ids = form_data.get('result_ids', [])
        test_names = form_data.get('test_names', [])
        values = form_data.get('values', [])
        units = form_data.get('units', [])
        ranges = form_data.get('ranges', [])
        statuses = form_data.get('statuses', [])
        notes_list = form_data.get('notes_list', [])

        created_ids = []
        errors = []

        for i in range(len(test_names)):
            try:
                result_id = int(result_ids[i]) if i < len(result_ids) and result_ids[i] else None
                if result_id:
                    result = (
                        db.session.execute(
                            select(LabResult).filter(
                                LabResult.id == result_id, LabResult.tenant_id == g.tenant_id
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if result:
                        result.value = values[i] if i < len(values) else ''
                        result.unit = units[i] if i < len(units) else ''
                        result.reference_range = ranges[i] if i < len(ranges) else ''
                        result.status = statuses[i] if i < len(statuses) else 'PENDING'
                        result.notes = notes_list[i] if i < len(notes_list) else ''
                else:
                    test_name = test_names[i] if i < len(test_names) else ''
                    result = LabResult(
                        tenant_id=getattr(lab_request, 'tenant_id', None),
                        request_id=lab_request.id,
                        patient_id=lab_request.patient_id,
                        test_code=test_name or 'NA',
                        test_name=test_name,
                        value=values[i] if i < len(values) else '',
                        unit=units[i] if i < len(units) else '',
                        reference_range=ranges[i] if i < len(ranges) else '',
                        status=statuses[i] if i < len(statuses) else 'PENDING',
                        notes=notes_list[i] if i < len(notes_list) else '',
                    )
                    db.session.add(result)
                    db.session.flush()
                created_ids.append(result_id if result_id else result.id)
            except Exception as e:
                errors.append(f'Row {i}: {e!s}')
        return created_ids, errors

    @staticmethod
    @require_module('lab')
    def validate_lab_results(results: list) -> list[str]:
        """Basic validation of lab results. Returns list of error messages."""
        errors = []
        for r in results:
            if not r.test_name:
                errors.append('Test name is required')
            if r.value and not r.unit:
                errors.append(f'Unit required for {r.test_name}')
        return errors

    @staticmethod
    @require_module('lab')
    def finalize_results(request_id: int) -> bool:
        """Mark all results as COMPLETED and update request status to DONE."""
        from models.lab_request import LabRequest, LabResult

        try:
            results = (
                db.session.execute(select(LabResult).filter_by(request_id=request_id))
                .scalars()
                .all()
            )
            now = datetime.now(UTC)
            for r in results:
                r.status = 'COMPLETED'
                r.updated_at = now
            req = (
                db.session.execute(
                    select(LabRequest).filter(
                        LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if req:
                req.status = 'DONE'
                req.completed_at = now
            return safe_commit(db.session, error_message='Error finalizing lab results')
        except Exception:
            logging.exception('Error finalizing lab results: %s')
            return False

    # ==================== QUALITY CONTROL ====================

    @staticmethod
    @require_module('lab')
    def get_quality_entries(limit: int = 100) -> list:
        from models.lab_quality import LabQualityControlEntry

        return (
            db.session.execute(
                select(LabQualityControlEntry)
                .order_by(LabQualityControlEntry.recorded_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    @staticmethod
    @require_module('lab')
    def create_quality_entry(entry_data: dict) -> Any | None:
        from models.lab_quality import LabQualityControlEntry

        try:
            entry = LabQualityControlEntry(**entry_data)
            db.session.add(entry)
            if not safe_commit(db.session, error_message='Error creating quality entry'):
                return None
            return entry
        except Exception:
            logging.exception('Error creating quality entry: %s')
            return None

    # ==================== REAGENT MANAGEMENT ====================

    @staticmethod
    @require_module('lab')
    def get_reagents() -> list:
        from models.lab_reagent import LabReagent

        return db.session.execute(select(LabReagent).order_by(LabReagent.name)).scalars().all()

    @staticmethod
    @require_module('lab')
    def get_low_stock_reagents(threshold: int | None = None) -> list:
        from models.lab_reagent import LabReagent

        q = LabReagent.query
        if threshold is not None:
            q = q.filter(LabReagent.stock_quantity <= threshold)
        else:
            q = q.filter(LabReagent.stock_quantity <= LabReagent.minimum_stock)
        return q.order_by(LabReagent.stock_quantity.asc()).all()

    @staticmethod
    @require_module('lab')
    def update_reagent_quantity(reagent_id: int, quantity: float) -> bool:
        from models.lab_reagent import LabReagent

        try:
            reagent = (
                db.session.execute(
                    select(LabReagent).filter(
                        LabReagent.id == reagent_id, LabReagent.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not reagent:
                return False
            reagent.stock_quantity = quantity
            return safe_commit(db.session, error_message='Error updating reagent')
        except Exception:
            logging.exception('Error updating reagent: %s')
            return False

    # ==================== NOTIFICATION ====================

    @staticmethod
    @require_module('lab')
    def notify_results_ready(patient_id: int, request_id: int) -> None:
        """Send notification that lab results are ready."""
        try:
            from models.lab_request import LabRequest
            from models.patient import Patient
            from services.notification_service import NotificationService

            patient = (
                db.session.execute(
                    select(Patient).filter(
                        Patient.id == patient_id, Patient.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            req = (
                db.session.execute(
                    select(LabRequest).filter(
                        LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if patient and req:
                NotificationService.send_notification(
                    user_id=patient.user_id if hasattr(patient, 'user_id') else None,
                    title='نتائج المختبر جاهزة',
                    message=f'نتائج المختبر للطلب #{request_id} جاهزة للمريض {patient.name}',
                    notification_type='lab_result',
                )
        except Exception:
            logging.exception('Error sending lab notification: %s')

    # ==================== AUDIT ====================

    @staticmethod
    @require_module('lab')
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        """Log lab workflow action to audit trail."""
        from models.audit_trail import AuditTrail

        _allowed = {'create', 'update', 'delete', 'view', 'export', 'import', 'security'}
        try:
            log = AuditTrail(
                entity_type='lab_test',
                entity_id=0,
                action=action if action in _allowed else 'update',
                description=f'[lab] {action}: {details}' if details else f'[lab] {action}',
                user_id=user_id,
                created_at=datetime.now(UTC),
            )
            db.session.add(log)
            safe_commit(db.session, error_message='Error logging lab action')
        except Exception:
            logging.exception('Error logging lab action: %s')

    # ==================== DASHBOARD ====================

    @staticmethod
    @require_module('lab')
    def get_dashboard_stats() -> dict:
        """Aggregate stats for lab dashboard."""
        from models.lab_request import LabRequest

        today = date.today()
        return {
            'today_requests': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(db.func.date(LabRequest.created_at) == today)
            ).scalar(),
            'pending_requests': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(LabRequest.status == 'REQUESTED')
            ).scalar(),
            'completed_today': db.session.execute(
                select(func.count())
                .select_from(LabRequest)
                .filter(LabRequest.status == 'DONE', db.func.date(LabRequest.completed_at) == today)
            ).scalar(),
        }

    # ==================== TEST CATALOG ====================

    @staticmethod
    @require_module('lab')
    def lookup_catalog_by_code(code: str, tenant_id: int | None = None) -> Any | None:
        from models.lab_test_catalog import LabTestCatalog

        q = select(LabTestCatalog).filter(LabTestCatalog.code == code)
        if tenant_id:
            q = q.filter(LabTestCatalog.tenant_id == tenant_id)
        return db.session.execute(q).scalars().first()

    @staticmethod
    @require_module('lab')
    def get_active_catalog(tenant_id: int | None = None) -> list:
        from models.lab_test_catalog import LabTestCatalog

        q = select(LabTestCatalog).filter(LabTestCatalog.is_active)
        if tenant_id:
            q = q.filter(LabTestCatalog.tenant_id == tenant_id)
        return (
            db.session.execute(q.order_by(LabTestCatalog.sort_order, LabTestCatalog.code))
            .scalars()
            .all()
        )


# Singleton
lab_service = LabService()
