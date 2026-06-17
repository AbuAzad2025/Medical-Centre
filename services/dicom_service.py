"""
DICOM Service - DICOM/PACS study and series management.
Extracted from routes/dicom_routes.py.
"""
from __future__ import annotations

import logging
from typing import Any

from app_factory import db


class DICOMService:
    """Centralized DICOM/PACS business logic"""

    @staticmethod
    def get_studies(patient_id: int | None = None, modality: str | None = None, limit: int = 200) -> list:
        from models.dicom_pacs import DICOMStudy
        query = DICOMStudy.query
        if patient_id:
            query = query.filter_by(patient_id=patient_id)
        if modality:
            query = query.filter_by(modality=modality)
        return query.order_by(DICOMStudy.study_date.desc()).limit(limit).all()

    @staticmethod
    def get_study(study_id: int) -> Any | None:
        from models.dicom_pacs import DICOMStudy
        return DICOMStudy.query.get(study_id)

    @staticmethod
    def get_series(study_id: int) -> list:
        from models.dicom_pacs import DICOMSeries
        return DICOMSeries.query.filter_by(study_id=study_id).all()

    @staticmethod
    def get_instances(series_id: int) -> list:
        from models.dicom_pacs import DICOMInstance
        return DICOMInstance.query.filter_by(series_id=series_id).all()

    @staticmethod
    def get_patient_studies(patient_id: int) -> list:
        from models.dicom_pacs import DICOMStudy
        return DICOMStudy.query.filter_by(patient_id=patient_id).order_by(
            DICOMStudy.study_date.desc()
        ).all()

    @staticmethod
    def serialize_study(study: Any) -> dict:
        return {
            "id": study.id,
            "study_uid": getattr(study, "study_instance_uid", ""),
            "modality": study.modality,
            "description": getattr(study, "study_description", ""),
            "study_date": study.study_date.isoformat() if study.study_date else None,
            "series_count": getattr(study, "series_count", 0),
            "status": study.status,
        }

    @staticmethod
    def get_pacs_config() -> list:
        from models.dicom_pacs import PACSConfiguration
        return PACSConfiguration.query.filter_by(is_active=True).all()


# Singleton
dicom_service = DICOMService()
