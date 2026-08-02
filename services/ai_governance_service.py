"""
AIRecommendationGovernanceService - governance and audit for AI recommendations
"""

from datetime import UTC, datetime

from flask import g
from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit


class AIRecommendationGovernanceService:
    """Audits and governs AI-generated clinical recommendations."""

    @staticmethod
    def log_recommendation(
        patient_id: int,
        model_name: str,
        input_data: dict,
        output_data: dict,
        confidence: float,
        accepted: bool = False,
    ) -> dict:
        from models.ai_analytics import ModelPrediction

        tenant_id = getattr(g, 'tenant_id', None)
        prediction = ModelPrediction(
            model_name=model_name,
            patient_id=patient_id,
            input_data=str(input_data),
            output_data=str(output_data),
            confidence_score=float(confidence),
            is_accepted=accepted,
            created_at=datetime.now(UTC),
        )
        db.session.add(prediction)
        safe_commit(db.session, error_message='Failed to log AI recommendation', reraise=True)
        return {'prediction_id': prediction.id, 'status': 'logged'}

    @staticmethod
    def get_recommendation_history(patient_id: int, limit: int = 20) -> list[dict]:
        from models.ai_analytics import ModelPrediction

        predictions = (
            db.session.execute(
                select(ModelPrediction)
                .filter_by(patient_id=patient_id)
                .order_by(ModelPrediction.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                'id': p.id,
                'model': p.model_name,
                'confidence': float(p.confidence_score) if p.confidence_score else 0,
                'accepted': p.is_accepted,
                'created_at': str(p.created_at),
            }
            for p in predictions
        ]
