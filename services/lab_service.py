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
        visit_id: int | None,
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

        Dynamic bundle isolation: ``visit_id`` is optional for standalone-lab
        bundles (no ``doctor`` / ``reception`` module). When those modules are
        active a visit is required; otherwise a walk-in request is accepted.
        """
        from models.lab_request import LabRequest, LabResult
        from models.lab_test_catalog import LabTestCatalog
        from models.visit import Visit

        if not test_ids:
            return False, {'error': 'No test IDs provided'}

        resolved_tenant_id = tenant_id or getattr(g, 'tenant_id', None)

        # Dynamic cross-module check
        from services.feature_gate_service import FeatureGateService

        doctor_or_reception_active = False
        if resolved_tenant_id:
            doctor_or_reception_active = (
                FeatureGateService.module_enabled(resolved_tenant_id, 'doctor')
                or FeatureGateService.module_enabled(resolved_tenant_id, 'reception')
            )

        if visit_id is not None:
            visit = (
                db.session.execute(
                    select(Visit).filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id)
                )
                .scalars()
                .first()
            )
            if not visit:
                return False, {'error': 'Visit not found'}
            resolved_tenant_id = resolved_tenant_id or visit.tenant_id
        elif doctor_or_reception_active:
            # visit_id is mandatory when doctor/reception module is enabled
            return False, {
                'error': 'visit_id is required when the doctor or reception module is enabled'
            }
        else:
            # Standalone lab walk-in: no visit required
            visit = None

        if requested_by is None and FeatureGateService.module_enabled(resolved_tenant_id, 'doctor'):
            return False, {
                'error': 'Prescriber (requested_by) is required when the doctor module is enabled'
            }

        now = datetime.now(UTC)
        request_number = f'LR-{visit_id or 0}-{int(now.timestamp())}'

        lab_request = LabRequest(
            tenant_id=resolved_tenant_id,
            visit_id=visit.id if visit else None,
            patient_id=visit.patient_id if visit else None,
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
        tid = getattr(g, 'tenant_id', None)
        q = LabRequest.query.filter(LabRequest.tenant_id == tid) if tid else LabRequest.query
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
        from models.lab_request import LabResult
        from models.lab_test_catalog import LabTestCatalog

        def _parse_critical_raw(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            if isinstance(v, str):
                return v.strip().lower() in {'1', 'true', 'yes', 'on'}
            return False

        def _auto_critical(val, code, explicit):
            if explicit:
                return True
            if not val or not code:
                return False
            try:
                fv = float(str(val).strip())
            except Exception:
                return False
            try:
                cat = (
                    db.session.execute(
                        select(LabTestCatalog).filter(
                            LabTestCatalog.code == code,
                            LabTestCatalog.tenant_id == getattr(lab_request, 'tenant_id', None),
                        )
                    )
                    .scalars()
                    .first()
                )
                if not cat:
                    return False
                lo = None
                hi = None
                try:
                    lo = float(cat.critical_low) if cat.critical_low not in (None, '') else None
                except Exception:
                    lo = None
                try:
                    hi = float(cat.critical_high) if cat.critical_high not in (None, '') else None
                except Exception:
                    hi = None
                if lo is not None and fv <= lo:
                    return True
                if hi is not None and fv >= hi:
                    return True
            except Exception:
                return False
            return False

        rows = form_data.get('rows')
        if isinstance(rows, list) and rows:
            created_ids = []
            errors = []
            for idx, row in enumerate(rows):
                try:
                    if not isinstance(row, dict):
                        errors.append(f'Row {idx}: invalid row')
                        continue
                    raw_id = row.get('result_id') or row.get('id') or row.get('result_ids')
                    result_id = None
                    try:
                        result_id = int(str(raw_id).strip()) if raw_id not in (None, '') else None
                    except Exception:
                        result_id = None
                    test_code = (row.get('test_code') or row.get('code') or '').strip()
                    test_name = (row.get('test_name') or row.get('name') or test_code or '').strip()
                    value = (row.get('value') or '').strip() if row.get('value') is not None else ''
                    unit = (row.get('unit') or '').strip() if row.get('unit') is not None else ''
                    ref = (
                        (row.get('reference_range') or row.get('range') or '').strip()
                        if (row.get('reference_range') or row.get('range')) is not None
                        else ''
                    )
                    status_val = (row.get('status') or 'PENDING').strip().upper() or 'PENDING'
                    notes = (row.get('notes') or '').strip() if row.get('notes') is not None else ''
                    explicit_critical = _parse_critical_raw(row.get('is_critical'))
                    if not test_code and not test_name and not value:
                        continue
                    is_critical = _auto_critical(value, test_code or test_name, explicit_critical)
                    tenant_id = getattr(lab_request, 'tenant_id', None) or getattr(
                        g, 'tenant_id', None
                    )
                    if result_id:
                        result = (
                            db.session.execute(
                                select(LabResult).filter(
                                    LabResult.id == result_id, LabResult.tenant_id == tenant_id
                                )
                            )
                            .scalars()
                            .first()
                        )
                        if not result:
                            errors.append(f'Row {idx}: result not found')
                            continue
                        if test_code:
                            result.test_code = test_code
                        if test_name:
                            result.test_name = test_name
                        result.value = value
                        result.unit = unit
                        result.reference_range = ref
                        result.status = (
                            status_val
                            if status_val in {'PENDING', 'READY', 'VALIDATED', 'COMPLETED'}
                            else 'PENDING'
                        )
                        result.notes = notes
                        result.is_critical = is_critical
                        created_ids.append(result.id)
                    else:
                        if not test_code and not test_name:
                            errors.append(f'Row {idx}: test_code or test_name required')
                            continue
                        result = LabResult(
                            tenant_id=tenant_id,
                            request_id=lab_request.id,
                            patient_id=lab_request.patient_id,
                            test_code=test_code or test_name or 'NA',
                            test_name=test_name or test_code or 'NA',
                            value=value,
                            unit=unit,
                            reference_range=ref,
                            status=status_val
                            if status_val in {'PENDING', 'READY', 'VALIDATED', 'COMPLETED'}
                            else 'PENDING',
                            notes=notes,
                            is_critical=is_critical,
                        )
                        db.session.add(result)
                        db.session.flush()
                        created_ids.append(result.id)
                except Exception as e:
                    errors.append(f'Row {idx}: {e!s}')
            return created_ids, errors

        result_ids = list(form_data.get('result_ids') or [])
        test_codes = list(form_data.get('test_codes') or [])
        test_names = list(form_data.get('test_names') or [])
        values = list(form_data.get('values') or [])
        units = list(form_data.get('units') or [])
        ranges = list(form_data.get('ranges') or [])
        statuses = list(form_data.get('statuses') or [])
        notes_list = list(form_data.get('notes_list') or [])
        is_critical_list = list(
            form_data.get('is_critical')
            or form_data.get('is_critical_list')
            or form_data.get('critical_flags')
            or []
        )

        if not test_codes and test_names:
            test_codes = test_names[:]

        n = max(
            len(result_ids),
            len(test_codes),
            len(test_names),
            len(values),
            len(units),
            len(ranges),
            len(statuses),
            len(notes_list),
            len(is_critical_list),
            0,
        )
        created_ids = []
        errors = []
        tenant_id = getattr(lab_request, 'tenant_id', None) or getattr(g, 'tenant_id', None)
        for i in range(n):
            try:
                raw_id = result_ids[i] if i < len(result_ids) else None
                result_id = None
                if raw_id not in (None, ''):
                    try:
                        result_id = int(str(raw_id).strip())
                    except Exception:
                        result_id = None
                test_code = (
                    (test_codes[i] if i < len(test_codes) else '').strip()
                    if i < len(test_codes) and test_codes[i] is not None
                    else ''
                )
                test_name = (
                    (test_names[i] if i < len(test_names) else '').strip()
                    if i < len(test_names) and test_names[i] is not None
                    else ''
                )
                if not test_code and test_name:
                    test_code = test_name
                if not test_name and test_code:
                    test_name = test_code
                value = values[i] if i < len(values) else ''
                value = '' if value is None else str(value).strip()
                unit = units[i] if i < len(units) else ''
                unit = '' if unit is None else str(unit).strip()
                ref = ranges[i] if i < len(ranges) else ''
                ref = '' if ref is None else str(ref).strip()
                status_val = statuses[i] if i < len(statuses) else 'PENDING'
                if status_val is None:
                    status_val = 'PENDING'
                else:
                    status_val = str(status_val).strip().upper() or 'PENDING'
                notes = notes_list[i] if i < len(notes_list) else ''
                notes = '' if notes is None else str(notes).strip()
                raw_critical = is_critical_list[i] if i < len(is_critical_list) else False
                explicit_critical = _parse_critical_raw(raw_critical)
                if (
                    not test_code
                    and not test_name
                    and not value
                    and not unit
                    and not ref
                    and not notes
                ):
                    continue
                is_critical = _auto_critical(value, test_code, explicit_critical)
                if result_id:
                    result = (
                        db.session.execute(
                            select(LabResult).filter(
                                LabResult.id == result_id, LabResult.tenant_id == tenant_id
                            )
                        )
                        .scalars()
                        .first()
                    )
                    if not result:
                        errors.append(f'Row {i}: result not found')
                        continue
                    if test_code:
                        result.test_code = test_code
                    if test_name:
                        result.test_name = test_name
                    result.value = value
                    result.unit = unit
                    result.reference_range = ref
                    result.status = (
                        status_val
                        if status_val in {'PENDING', 'READY', 'VALIDATED', 'COMPLETED'}
                        else 'PENDING'
                    )
                    result.notes = notes
                    result.is_critical = is_critical
                    created_ids.append(result.id)
                else:
                    if not test_code and not test_name:
                        continue
                    result = LabResult(
                        tenant_id=tenant_id,
                        request_id=lab_request.id,
                        patient_id=lab_request.patient_id,
                        test_code=test_code or test_name or 'NA',
                        test_name=test_name or test_code or 'NA',
                        value=value,
                        unit=unit,
                        reference_range=ref,
                        status=status_val
                        if status_val in {'PENDING', 'READY', 'VALIDATED', 'COMPLETED'}
                        else 'PENDING',
                        notes=notes,
                        is_critical=is_critical,
                    )
                    db.session.add(result)
                    db.session.flush()
                    created_ids.append(result.id)
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

    # ==================== CANCEL & AMEND ====================

    _LAB_TERMINAL_STATUSES = {'DONE', 'CANCELLED'}

    @staticmethod
    @require_module('lab')
    def cancel_request(
        request_id: int, cancelled_by: int, reason: str | None = None
    ) -> tuple[bool, dict]:
        """Cancel a lab request. Only non-terminal requests can be cancelled.

        Returns ``(ok, payload)`` so the route layer can translate to HTTP without
        try/except in the view, mirroring the FinancialService contract.
        """
        from models.lab_request import LabRequest

        try:
            req = (
                db.session.execute(
                    select(LabRequest).filter(
                        LabRequest.id == request_id, LabRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not req:
                return False, {'error': 'Lab request not found'}
            if req.status in LabService._LAB_TERMINAL_STATUSES:
                return False, {'error': f'Cannot cancel a request in status {req.status}'}
            now = datetime.now(UTC)
            req.status = 'CANCELLED'
            req.cancelled_at = now
            req.cancelled_by = cancelled_by
            req.updated_at = now
            if reason:
                prefix = f'{req.notes}\n' if req.notes else ''
                req.notes = f'{prefix}[CANCELLED by {cancelled_by}] {reason}'
            LabService.log_action('update', f'cancelled request {req.id}', user_id=cancelled_by)
            if not safe_commit(db.session, error_message='Error cancelling lab request'):
                return False, {'error': 'Error cancelling lab request'}
            return True, {'lab_request_id': req.id, 'status': req.status}
        except Exception:
            logging.exception('Error cancelling lab request: %s')
            return False, {'error': 'Error cancelling lab request'}

    @staticmethod
    @require_module('lab')
    def amend_result(
        result_id: int,
        *,
        value: str | None = None,
        unit: str | None = None,
        notes: str | None = None,
        is_critical: bool = False,
        amended_by: int | None = None,
    ) -> tuple[bool, dict]:
        """Amend a lab result, recording amendment audit fields + is_critical flag."""
        from models.lab_request import LabResult

        try:
            result = (
                db.session.execute(
                    select(LabResult).filter(
                        LabResult.id == result_id, LabResult.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not result:
                return False, {'error': 'Lab result not found'}
            now = datetime.now(UTC)
            if value is not None:
                result.value = value
            if unit is not None:
                result.unit = unit
            if notes is not None:
                result.notes = notes
            result.is_critical = is_critical
            result.amended_by = amended_by
            result.amended_at = now
            result.updated_at = now
            LabService.log_action('update', f'amended result {result.id}', user_id=amended_by)
            if not safe_commit(db.session, error_message='Error amending lab result'):
                return False, {'error': 'Error amending lab result'}
            return True, {'result_id': result.id, 'is_critical': result.is_critical}
        except Exception:
            logging.exception('Error amending lab result: %s')
            return False, {'error': 'Error amending lab result'}

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
