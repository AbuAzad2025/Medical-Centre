"""SNOMED CT terminology model for clinical concepts."""
from __future__ import annotations

from datetime import UTC, datetime

from app_factory import db


class SNOMEDConcept(db.Model):
    """SNOMED CT concept for clinical terminology."""

    __tablename__ = 'snomed_concepts'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    concept_id = db.Column(db.String(20), nullable=False, unique=True, index=True)
    term = db.Column(db.Text, nullable=False)
    term_ar = db.Column(db.Text, nullable=True)
    semantic_tag = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    def __repr__(self):
        return f'<SNOMEDConcept {self.concept_id}: {self.term}>'


class SNOMEDRelationship(db.Model):
    """SNOMED CT relationships between concepts."""

    __tablename__ = 'snomed_relationships'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.String(20), nullable=False, index=True)
    target_id = db.Column(db.String(20), nullable=False, index=True)
    relationship_type = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    def __repr__(self):
        return f'<SNOMEDRelationship {self.source_id} -> {self.target_id}>'
