"""
RadiologyWorkflowService - manages radiology request workflow
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db


class RadiologyWorkflowService:
    """Manages radiology request lifecycle."""

    @staticmethod
    def receive_request(request_id: int) -> dict:
        from models.radiology_request import RadiologyRequest
        req = RadiologyRequest.query.get(request_id)
        if not req:
            return {"error": "Request not found"}
        req.status = 'RECEIVED'
        db.session.commit()
        return {"request_id": request_id, "status": "RECEIVED"}

    @staticmethod
    def complete_request(request_id: int, findings: str = "") -> dict:
        from models.radiology_request import RadiologyRequest
        req = RadiologyRequest.query.get(request_id)
        if not req:
            return {"error": "Request not found"}
        req.status = 'DONE'
        if findings:
            req.findings = findings
        req.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return {"request_id": request_id, "status": "DONE"}
