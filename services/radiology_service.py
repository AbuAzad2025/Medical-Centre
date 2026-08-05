"""
Radiology Service - Business logic for radiology operations.
Extracted from routes/radiology/ to centralize validation, creation, and workflow.
"""

from __future__ import annotations

import logging
import os
import secrets
from datetime import UTC, date, datetime
from typing import Any

from flask import g
from sqlalchemy import func, select
from werkzeug.utils import secure_filename

from app.extensions import db
from services.feature_gate_service import require_module
from utils.db_safety import safe_commit, safe_rollback


class RadiologyService:
    """Centralized radiology business logic"""

    # ==================== REQUEST CREATION ====================

    @staticmethod
    @require_module('radiology')
    def create_request(
        visit_id: int,
        *,
        requested_by: int | None = None,
        modality: str | None = None,
        body_part: str | None = None,
        notes: str | None = None,
        tenant_id: int | None = None,
    ) -> tuple[bool, dict]:
        """Create a structured RadiologyRequest from a clinician order.

        P2-003: Canonical path for ordering radiology studies. Free-text notes
        are still preserved in the linked Visit record (P2-000 contract).
        """
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit

        tid = tenant_id or getattr(g, 'tenant_id', None)
        visit = (
            db.session.execute(select(Visit).filter(Visit.id == visit_id, Visit.tenant_id == tid))
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
                    tenant_id=tenant_id, module_name='radiology', is_active=True
                )
            )
            .scalars()
            .first()
        ):
            raise PermissionError('Radiology module is not enabled for this tenant')
        now = datetime.now(UTC)
        request_number = f'RAD-{visit_id}-{int(now.timestamp())}'

        rad_request = RadiologyRequest(
            tenant_id=tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            requested_by=requested_by,
            request_number=request_number,
            status='REQUESTED',
            modality=(modality or '').upper() or None,
            body_part=(body_part or '').strip() or None,
            notes=notes or '',
            created_at=now,
            updated_at=now,
        )
        db.session.add(rad_request)
        db.session.flush()
        return True, {
            'radiology_request_id': rad_request.id,
            'request_number': request_number,
        }

    # ==================== WORKLIST QUERIES ====================

    @staticmethod
    @require_module('radiology')
    def get_request_counts() -> dict:
        from models.radiology_request import RadiologyRequest

        today = date.today()
        return {
            'requested': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(RadiologyRequest.status == 'REQUESTED')
            ).scalar(),
            'in_progress': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(RadiologyRequest.status == 'IN_PROGRESS')
            ).scalar(),
            'done_today': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(
                    RadiologyRequest.status == 'DONE',
                    db.func.date(RadiologyRequest.updated_at) == today,
                )
            ).scalar(),
        }

    @staticmethod
    @require_module('radiology')
    def get_worklist(status: str = 'REQUESTED') -> list:
        from models.radiology_request import RadiologyRequest

        today = date.today()
        q = RadiologyRequest.query
        if status == 'DONE_TODAY':
            q = q.filter(
                RadiologyRequest.status == 'DONE',
                db.func.date(RadiologyRequest.updated_at) == today,
            )
        elif status:
            q = q.filter(RadiologyRequest.status == status)
        return q.order_by(RadiologyRequest.created_at.desc()).all()

    @staticmethod
    @require_module('radiology')
    def get_request_by_id(request_id: int) -> Any | None:
        from models.radiology_request import RadiologyRequest

        return (
            db.session.execute(
                select(RadiologyRequest).filter(
                    RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )

    @staticmethod
    @require_module('radiology')
    def get_results_for_request(request_id: int) -> Any | None:
        from models.radiology_request import RadiologyRequest

        req = (
            db.session.execute(
                select(RadiologyRequest).filter(
                    RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )
        if req and req.results:
            return req.results[0]
        return None

    @staticmethod
    @require_module('radiology')
    def get_uploads_for_result(result_id: int) -> list:
        from models.file_management import FileUpload

        return (
            db.session.execute(
                select(FileUpload)
                .filter_by(related_entity_type='radiology_result', related_entity_id=result_id)
                .order_by(FileUpload.uploaded_at.desc())
            )
            .scalars()
            .all()
        )

    @staticmethod
    @require_module('radiology')
    def build_visit_map(requests_list: list) -> dict:
        """Build visit_id -> Visit mapping for a list of radiology requests."""
        from models.visit import Visit

        visit_ids = [r.visit_id for r in requests_list if getattr(r, 'visit_id', None)]
        if not visit_ids:
            return {}
        visits = db.session.execute(select(Visit).filter(Visit.id.in_(visit_ids))).scalars().all()
        return {v.id: v for v in visits}

    # ==================== RESULT CREATION ====================

    @staticmethod
    @require_module('radiology')
    def create_or_update_result(
        request_id: int, report_text: str, conclusion: str | None = None, is_critical: bool = False
    ) -> Any | None:
        from models.radiology_request import RadiologyRequest
        from models.radiology_result import RadiologyResult

        try:
            req = (
                db.session.execute(
                    select(RadiologyRequest).filter(
                        RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not req:
                return None
            result = (
                req.results[0]
                if req.results
                else RadiologyResult(
                    request_id=request_id, patient_id=req.patient_id, status='PENDING'
                )
            )
            result.findings = report_text
            if conclusion is not None:
                result.impression = conclusion
            result.is_critical = is_critical
            if not result.id:
                db.session.add(result)
            db.session.flush()
            return result
        except Exception:
            safe_rollback(db.session, error_message='فشل إنشاء نتيجة الأشعة')
            logging.exception('Error creating radiology result: %s')
            return None

    @staticmethod
    @require_module('radiology')
    def finalize_result(request_id: int) -> bool:
        from models.radiology_request import RadiologyRequest

        try:
            req = (
                db.session.execute(
                    select(RadiologyRequest).filter(
                        RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not req:
                return False
            result = req.results[0] if req.results else None
            if result:
                result.status = 'COMPLETED'
                result.completed_at = datetime.now(UTC)
            req.status = 'DONE'
            req.updated_at = datetime.now(UTC)
            safe_commit(db.session, error_message='فشل اعتماد نتيجة الأشعة', reraise=True)
            return True
        except Exception:
            logging.exception('Error finalizing radiology result: %s')
            return False

    @staticmethod
    @require_module('radiology')
    def claim_request(request_id: int, user_id: int) -> bool:
        from models.radiology_request import RadiologyRequest

        try:
            req = (
                db.session.execute(
                    select(RadiologyRequest).filter(
                        RadiologyRequest.id == request_id, RadiologyRequest.tenant_id == g.tenant_id
                    )
                )
                .scalars()
                .first()
            )
            if not req or req.status != 'REQUESTED':
                return False
            req.status = 'IN_PROGRESS'
            safe_commit(db.session, error_message='فشل استلام طلب الأشعة', reraise=True)
            return True
        except Exception:
            logging.exception('Error claiming radiology request: %s')
            return False

    # ==================== FILE UPLOADS ====================

    @staticmethod
    @require_module('radiology')
    def save_uploaded_files(files: list, result_id: int, payload: dict | None = None) -> list:
        from flask import current_app

        from models.file_management import FileUpload

        saved = []
        upload_root = current_app.config.get('UPLOAD_FOLDER') or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'uploads'
        )
        target_dir = os.path.join(upload_root, 'radiology', str(result_id))
        os.makedirs(target_dir, exist_ok=True)
        for f in files:
            if not f or not getattr(f, 'filename', None):
                continue
            original_name = f.filename
            safe_name = secure_filename(original_name) or f'file_{secrets.token_hex(4)}'
            _, ext = os.path.splitext(safe_name)
            stored_name = (
                f'{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}_{secrets.token_hex(8)}{ext.lower()}'
            )
            file_path = os.path.join(target_dir, stored_name)
            f.save(file_path)
            size = 0
            try:
                size = os.path.getsize(file_path)
            except Exception:
                size = 0
            fu = FileUpload(
                filename=stored_name,
                original_filename=original_name,
                file_path=file_path,
                file_size=(size or 1),
                file_type=(getattr(f, 'mimetype', None) or 'application/octet-stream'),
                file_extension=(ext.lower().lstrip('.') or 'bin'),
                description=(payload.get('file_description') if payload else None),
                related_entity_type='radiology_result',
                related_entity_id=result_id,
                uploaded_by=0,
            )
            db.session.add(fu)
            saved.append(fu)
        return saved

    # ==================== NOTIFICATION ====================

    @staticmethod
    @require_module('radiology')
    def notify_complete(req: Any, is_critical: bool = False) -> None:
        try:
            from services.notification_service import NotificationService

            doctor_id = req.requester.id if getattr(req, 'requester', None) else None
            if doctor_id:
                NotificationService.send_notification(
                    recipient_id=doctor_id,
                    title='نتيجة الأشعة جاهزة',
                    message=f'تم اعتماد تقرير الأشعة لطلب #{req.id}'
                    + (' (حرج)' if is_critical else ''),
                    notification_type=('warning' if is_critical else 'info'),
                    is_urgent=is_critical,
                )
                if is_critical:
                    NotificationService.send_notification(
                        recipient_role='reception',
                        title='نتيجة أشعة حرجة',
                        message=f'يوجد تقرير أشعة حرج لطلب #{req.id} للمريض #{req.patient_id}',
                        notification_type='warning',
                        is_urgent=True,
                    )
        except Exception:
            pass

    # ==================== AUDIT ====================

    @staticmethod
    @require_module('radiology')
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        from models.audit_trail import AuditTrail

        _allowed = {'create', 'update', 'delete', 'view', 'export', 'import', 'security'}
        try:
            log = AuditTrail(
                entity_type='radiology_test',
                entity_id=0,
                action=action if action in _allowed else 'update',
                description=f'[radiology] {action}: {details}'
                if details
                else f'[radiology] {action}',
                user_id=user_id,
                created_at=datetime.now(UTC),
            )
            db.session.add(log)
            safe_commit(db.session, error_message='فشل تسجيل إجراء الأشعة')
        except Exception:
            logging.exception('Error logging radiology action: %s')

    # ==================== DASHBOARD ====================

    @staticmethod
    @require_module('radiology')
    def get_dashboard_stats() -> dict:
        from models.radiology_request import RadiologyRequest

        today = date.today()
        return {
            'today_requests': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(db.func.date(RadiologyRequest.created_at) == today)
            ).scalar(),
            'pending': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS']))
            ).scalar(),
            'completed_today': db.session.execute(
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(
                    RadiologyRequest.status == 'DONE',
                    db.func.date(RadiologyRequest.updated_at) == today,
                )
            ).scalar(),
        }


# Singleton
radiology_service = RadiologyService()
