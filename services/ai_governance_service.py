"""
AIRecommendationGovernanceService - governance and audit for AI recommendations
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db


class AIRecommendationGovernanceService:
    """Audits and governs AI-generated clinical recommendations."""

    @staticmethod
    def log_recommendation(patient_id: int, model_name: str, input_data: dict,
                           output_data: dict, confidence: float, accepted: bool = False) -> dict:
        from models.ai_analytics import ModelPrediction
        from models.patient import Patient
        from models.visit import Visit

        tenant_id = getattr(g, 'tenant_id', None)
        prediction = ModelPrediction(
            model_name=model_name,
            patient_id=patient_id,
            input_data=str(input_data),
            output_data=str(output_data),
            confidence_score=float(confidence),
            is_accepted=accepted,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(prediction)
        db.session.commit()
        return {"prediction_id": prediction.id, "status": "logged"}

    @staticmethod
    def get_recommendation_history(patient_id: int, limit: int = 20) -> list[dict]:
        from models.ai_analytics import ModelPrediction
        predictions = ModelPrediction.query.filter_by(
            patient_id=patient_id
        ).order_by(ModelPrediction.created_at.desc()).limit(limit).all()
        return [{
            "id": p.id,
            "model": p.model_name,
            "confidence": float(p.confidence_score) if p.confidence_score else 0,
            "accepted": p.is_accepted,
            "created_at": str(p.created_at),
        } for p in predictions]
