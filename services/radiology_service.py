"""
Radiology Service - Business logic for radiology operations.
Extracted from routes/radiology/ to centralize validation, creation, and workflow.
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import date, datetime, timezone
from typing import Any

from app_factory import db
from werkzeug.utils import secure_filename


class RadiologyService:
    """Centralized radiology business logic"""

    # ==================== WORKLIST QUERIES ====================

    @staticmethod
    def get_request_counts() -> dict:
        from models.radiology_request import RadiologyRequest
        today = date.today()
        return {
            "requested": RadiologyRequest.query.filter(RadiologyRequest.status == "REQUESTED").count(),
            "in_progress": RadiologyRequest.query.filter(RadiologyRequest.status == "IN_PROGRESS").count(),
            "done_today": RadiologyRequest.query.filter(
                RadiologyRequest.status == "DONE",
                db.func.date(RadiologyRequest.updated_at) == today
            ).count(),
        }

    @staticmethod
    def get_worklist(status: str = "REQUESTED") -> list:
        from models.radiology_request import RadiologyRequest
        today = date.today()
        q = RadiologyRequest.query
        if status == "DONE_TODAY":
            q = q.filter(RadiologyRequest.status == "DONE",
                         db.func.date(RadiologyRequest.updated_at) == today)
        elif status:
            q = q.filter(RadiologyRequest.status == status)
        return q.order_by(RadiologyRequest.created_at.desc()).all()

    @staticmethod
    def get_request_by_id(request_id: int) -> Any | None:
        from models.radiology_request import RadiologyRequest
        return RadiologyRequest.query.get(request_id)

    @staticmethod
    def get_results_for_request(request_id: int) -> Any | None:
        from models.radiology_test import RadiologyResult
        from models.radiology_request import RadiologyRequest
        req = RadiologyRequest.query.get(request_id)
        if req and req.results:
            return req.results[0]
        return None

    @staticmethod
    def get_uploads_for_result(result_id: int) -> list:
        from models.file_management import FileUpload
        return FileUpload.query.filter_by(
            related_entity_type="radiology_result",
            related_entity_id=result_id
        ).order_by(FileUpload.uploaded_at.desc()).all()

    @staticmethod
    def build_visit_map(requests_list: list) -> dict:
        """Build visit_id -> Visit mapping for a list of radiology requests."""
        from models.visit import Visit
        visit_ids = [r.visit_id for r in requests_list if getattr(r, "visit_id", None)]
        if not visit_ids:
            return {}
        visits = Visit.query.filter(Visit.id.in_(visit_ids)).all()
        return {v.id: v for v in visits}

    # ==================== RESULT CREATION ====================

    @staticmethod
    def create_or_update_result(request_id: int, report_text: str,
                                conclusion: str | None = None, is_critical: bool = False) -> Any | None:
        from models.radiology_test import RadiologyResult
        from models.radiology_request import RadiologyRequest
        try:
            req = RadiologyRequest.query.get(request_id)
            if not req:
                return None
            result = req.results[0] if req.results else RadiologyResult(
                request_id=request_id,
                patient_id=req.patient_id,
                status="PENDING"
            )
            result.report_text = report_text
            if conclusion is not None:
                result.conclusion = conclusion
            result.is_critical = is_critical
            if not result.id:
                db.session.add(result)
            db.session.flush()
            return result
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating radiology result: {str(e)}")
            return None

    @staticmethod
    def finalize_result(request_id: int) -> bool:
        from models.radiology_request import RadiologyRequest
        try:
            req = RadiologyRequest.query.get(request_id)
            if not req:
                return False
            result = req.results[0] if req.results else None
            if result:
                result.status = "COMPLETED"
                result.completed_at = datetime.now(timezone.utc)
            req.status = "DONE"
            req.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error finalizing radiology result: {str(e)}")
            return False

    @staticmethod
    def claim_request(request_id: int, user_id: int) -> bool:
        from models.radiology_request import RadiologyRequest
        try:
            req = RadiologyRequest.query.get(request_id)
            if not req or req.status != "REQUESTED":
                return False
            req.assigned_to = user_id
            req.status = "IN_PROGRESS"
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error claiming radiology request: {str(e)}")
            return False

    # ==================== FILE UPLOADS ====================

    @staticmethod
    def save_uploaded_files(files: list, result_id: int, payload: dict | None = None) -> list:
        from models.file_management import FileUpload
        from flask import current_app
        saved = []
        upload_root = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "static", "uploads")
        target_dir = os.path.join(upload_root, "radiology", str(result_id))
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            if not f or not getattr(f, "filename", None):
                continue
            original_name = f.filename
            safe_name = secure_filename(original_name) or f"file_{secrets.token_hex(4)}"
            _, ext = os.path.splitext(safe_name)
            stored_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}{ext.lower()}"
            file_path = os.path.join(target_dir, stored_name)
            f.save(file_path)
            size = 0
            try:
                size = os.path.getsize(file_path)
            except Exception:
                size = 0
            fu = FileUpload(
                filename=stored_name, original_filename=original_name,
                file_path=file_path, file_size=(size or 1),
                file_type=(getattr(f, "mimetype", None) or "application/octet-stream"),
                file_extension=(ext.lower().lstrip(".") or "bin"),
                description=(payload.get("file_description") if payload else None),
                related_entity_type="radiology_result",
                related_entity_id=result_id,
                uploaded_by=0,
            )
            db.session.add(fu)
            saved.append(fu)
        return saved

    # ==================== NOTIFICATION ====================

    @staticmethod
    def notify_complete(req: Any, is_critical: bool = False) -> None:
        try:
            from services.notification_service import NotificationService
            doctor_id = req.requester.id if getattr(req, "requester", None) else None
            if doctor_id:
                NotificationService.send_notification(
                    recipient_id=doctor_id,
                    title="نتيجة الأشعة جاهزة",
                    message=f"تم اعتماد تقرير الأشعة لطلب #{req.id}" + (" (حرج)" if is_critical else ""),
                    notification_type=("warning" if is_critical else "info"),
                    is_urgent=is_critical,
                )
                if is_critical:
                    NotificationService.send_notification(
                        recipient_role="reception",
                        title="نتيجة أشعة حرجة",
                        message=f"يوجد تقرير أشعة حرج لطلب #{req.id} للمريض #{req.patient_id}",
                        notification_type="warning", is_urgent=True,
                    )
        except Exception:
            pass

    # ==================== AUDIT ====================

    @staticmethod
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        from models.audit_trail import AuditTrail
        try:
            log = AuditTrail(
                action=action, details=details,
                user_id=user_id, created_at=datetime.now(timezone.utc),
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error logging radiology action: {str(e)}")

    # ==================== DASHBOARD ====================

    @staticmethod
    def get_dashboard_stats() -> dict:
        from models.radiology_request import RadiologyRequest
        today = date.today()
        return {
            "today_requests": RadiologyRequest.query.filter(
                db.func.date(RadiologyRequest.created_at) == today
            ).count(),
            "pending": RadiologyRequest.query.filter(
                RadiologyRequest.status.in_(["REQUESTED", "IN_PROGRESS"])
            ).count(),
            "completed_today": RadiologyRequest.query.filter(
                RadiologyRequest.status == "DONE",
                db.func.date(RadiologyRequest.updated_at) == today
            ).count(),
        }


# Singleton
radiology_service = RadiologyService()
