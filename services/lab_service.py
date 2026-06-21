"""
Lab Service - Business logic for lab operations.
Extracted from routes/lab/ to centralize validation, creation, and workflow.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from app_factory import db
from sqlalchemy import func


class LabService:
    """Centralized lab business logic"""

    # ==================== WORKLIST QUERIES ====================

    @staticmethod
    def get_worklist(status: str = "REQUESTED", limit: int = 200) -> list:
        from models.lab_request import LabRequest
        today = date.today()
        allowed = {"REQUESTED", "COLLECTED", "RECEIVED", "ANALYZING", "REVIEWED",
                    "APPROVED", "IN_PROGRESS", "DONE", "DONE_TODAY", "ALL"}
        if status not in allowed:
            status = "REQUESTED"
        q = LabRequest.query
        if status == "DONE_TODAY":
            q = q.filter(LabRequest.status == "DONE",
                         db.func.date(LabRequest.completed_at) == today)
        elif status != "ALL":
            q = q.filter(LabRequest.status == status)
        return q.order_by(LabRequest.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_request_counts() -> dict:
        from models.lab_request import LabRequest
        today = date.today()
        return {
            "requested": LabRequest.query.filter(LabRequest.status == "REQUESTED").count(),
            "in_progress": LabRequest.query.filter(
                LabRequest.status.in_(["COLLECTED", "RECEIVED", "ANALYZING", "REVIEWED", "APPROVED", "IN_PROGRESS"])
            ).count(),
            "done_today": LabRequest.query.filter(
                LabRequest.status == "DONE",
                db.func.date(LabRequest.completed_at) == today
            ).count(),
        }

    @staticmethod
    def get_request_by_id(request_id: int) -> Any | None:
        from models.lab_request import LabRequest
        return LabRequest.query.get(request_id)

    @staticmethod
    def get_results_by_request(request_id: int) -> list:
        from models.lab_request import LabResult
        return LabResult.query.filter_by(request_id=request_id).all()

    @staticmethod
    def get_results_by_patient(patient_id: int) -> list:
        from models.lab_request import LabResult, LabRequest
        return LabResult.query.join(LabRequest).filter(
            LabRequest.patient_id == patient_id,
            LabResult.status == "COMPLETED"
        ).order_by(LabResult.completed_at.desc()).all()

    # ==================== RESULT CREATION ====================

    @staticmethod
    def create_results_from_form(lab_request: Any, form_data: dict) -> tuple[list, list]:
        """Create LabResult entries from form data. Returns (created_ids, errors)."""
        from models.lab_request import LabResult
        result_ids = form_data.get("result_ids", [])
        test_names = form_data.get("test_names", [])
        values = form_data.get("values", [])
        units = form_data.get("units", [])
        ranges = form_data.get("ranges", [])
        statuses = form_data.get("statuses", [])
        notes_list = form_data.get("notes_list", [])

        created_ids = []
        errors = []

        for i in range(len(test_names)):
            try:
                result_id = int(result_ids[i]) if i < len(result_ids) and result_ids[i] else None
                if result_id:
                    result = LabResult.query.get(result_id)
                    if result:
                        result.value = values[i] if i < len(values) else ""
                        result.unit = units[i] if i < len(units) else ""
                        result.reference_range = ranges[i] if i < len(ranges) else ""
                        result.status = statuses[i] if i < len(statuses) else "PENDING"
                        result.notes = notes_list[i] if i < len(notes_list) else ""
                else:
                    result = LabResult(
                        request_id=lab_request.id,
                        test_name=test_names[i] if i < len(test_names) else "",
                        value=values[i] if i < len(values) else "",
                        unit=units[i] if i < len(units) else "",
                        reference_range=ranges[i] if i < len(ranges) else "",
                        status=statuses[i] if i < len(statuses) else "PENDING",
                        notes=notes_list[i] if i < len(notes_list) else "",
                    )
                    db.session.add(result)
                created_ids.append(result.id if not result_id else result_id)
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        return created_ids, errors

    @staticmethod
    def validate_lab_results(results: list) -> list[str]:
        """Basic validation of lab results. Returns list of error messages."""
        errors = []
        for r in results:
            if not r.test_name:
                errors.append("Test name is required")
            if r.value and not r.unit:
                errors.append(f"Unit required for {r.test_name}")
        return errors

    @staticmethod
    def finalize_results(request_id: int) -> bool:
        """Mark all results as COMPLETED and update request status to DONE."""
        from models.lab_request import LabRequest, LabResult
        try:
            results = LabResult.query.filter_by(request_id=request_id).all()
            now = datetime.now(timezone.utc)
            for r in results:
                r.status = "COMPLETED"
                r.completed_at = now
            req = LabRequest.query.get(request_id)
            if req:
                req.status = "DONE"
                req.completed_at = now
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error finalizing lab results: {str(e)}")
            return False

    # ==================== QUALITY CONTROL ====================

    @staticmethod
    def get_quality_entries(limit: int = 100) -> list:
        from models.lab_quality import LabQualityControlEntry
        return LabQualityControlEntry.query.order_by(
            LabQualityControlEntry.created_at.desc()
        ).limit(limit).all()

    @staticmethod
    def create_quality_entry(entry_data: dict) -> Any | None:
        from models.lab_quality import LabQualityControlEntry
        try:
            entry = LabQualityControlEntry(**entry_data)
            db.session.add(entry)
            db.session.commit()
            return entry
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating quality entry: {str(e)}")
            return None

    # ==================== REAGENT MANAGEMENT ====================

    @staticmethod
    def get_reagents() -> list:
        from models.lab_reagent import LabReagent
        return LabReagent.query.order_by(LabReagent.name).all()

    @staticmethod
    def get_low_stock_reagents(threshold: int | None = None) -> list:
        from models.lab_reagent import LabReagent
        q = LabReagent.query
        if threshold is not None:
            q = q.filter(LabReagent.quantity <= threshold)
        else:
            q = q.filter(LabReagent.quantity <= LabReagent.minimum_quantity)
        return q.order_by(LabReagent.quantity.asc()).all()

    @staticmethod
    def update_reagent_quantity(reagent_id: int, quantity: float) -> bool:
        from models.lab_reagent import LabReagent
        try:
            reagent = LabReagent.query.get(reagent_id)
            if not reagent:
                return False
            reagent.quantity = quantity
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating reagent: {str(e)}")
            return False

    # ==================== NOTIFICATION ====================

    @staticmethod
    def notify_results_ready(patient_id: int, request_id: int) -> None:
        """Send notification that lab results are ready."""
        try:
            from services.notification_service import NotificationService
            from models.patient import Patient
            from models.lab_request import LabRequest
            patient = Patient.query.get(patient_id)
            req = LabRequest.query.get(request_id)
            if patient and req:
                NotificationService.send_notification(
                    user_id=patient.user_id if hasattr(patient, "user_id") else None,
                    title="نتائج المختبر جاهزة",
                    message=f"نتائج المختبر للطلب #{request_id} جاهزة للمريض {patient.name}",
                    notification_type="lab_result",
                )
        except Exception as e:
            logging.error(f"Error sending lab notification: {str(e)}")

    # ==================== AUDIT ====================

    @staticmethod
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        """Log lab workflow action to audit trail."""
        from models.audit_trail import AuditTrail
        try:
            log = AuditTrail(
                action=action,
                details=details,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error logging lab action: {str(e)}")

    # ==================== DASHBOARD ====================

    @staticmethod
    def get_dashboard_stats() -> dict:
        """Aggregate stats for lab dashboard."""
        from models.lab_request import LabRequest
        today = date.today()
        return {
            "today_requests": LabRequest.query.filter(
                db.func.date(LabRequest.created_at) == today
            ).count(),
            "pending_requests": LabRequest.query.filter(
                LabRequest.status == "REQUESTED"
            ).count(),
            "completed_today": LabRequest.query.filter(
                LabRequest.status == "DONE",
                db.func.date(LabRequest.completed_at) == today
            ).count(),
        }


    # ==================== TEST CATALOG ====================

    @staticmethod
    def lookup_catalog_by_code(code: str, tenant_id: int | None = None) -> Any | None:
        from models.lab_test_catalog import LabTestCatalog
        q = LabTestCatalog.query.filter(
            LabTestCatalog.code == code,
            LabTestCatalog.is_active == True
        )
        if tenant_id:
            q = q.filter(LabTestCatalog.tenant_id == tenant_id)
        return q.first()

    @staticmethod
    def get_active_catalog(tenant_id: int | None = None) -> list:
        from models.lab_test_catalog import LabTestCatalog
        q = LabTestCatalog.query.filter(LabTestCatalog.is_active == True)
        if tenant_id:
            q = q.filter(LabTestCatalog.tenant_id == tenant_id)
        return q.order_by(LabTestCatalog.sort_order, LabTestCatalog.code).all()


# Singleton
lab_service = LabService()
