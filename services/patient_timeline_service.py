"""Patient 360 timeline aggregation — UX1-004."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from flask import url_for


class PatientTimelineService:
    @staticmethod
    def build_events(patient_id: int, *, doctor_id: Optional[int] = None, filter_type: str = '') -> list[dict[str, Any]]:
        from models.appointment import Appointment
        from models.follow_up import FollowUpRequest
        from models.lab_request import LabRequest
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit

        events: list[dict[str, Any]] = []

        visits = Visit.query.filter(Visit.patient_id == patient_id).order_by(
            Visit.visit_date.desc(), Visit.created_at.desc()
        ).limit(200).all()
        for v in visits:
            dt = PatientTimelineService._visit_datetime(v)
            events.append({
                'type': 'visit',
                'dt': dt,
                'title': f"زيارة ({v.visit_type_display})",
                'status': v.status,
                'details': (v.diagnosis or v.symptoms or v.notes or ''),
                'link': url_for('doctor.patient_details', visit_id=v.id) if doctor_id and v.doctor_id == doctor_id else None,
            })

        prescriptions = Prescription.query.filter(Prescription.patient_id == patient_id).order_by(
            Prescription.created_at.desc()
        ).limit(200).all()
        for rx in prescriptions:
            events.append({
                'type': 'prescription',
                'dt': rx.created_at or datetime.now(),
                'title': 'وصفة طبية',
                'status': getattr(rx, 'status', None),
                'details': (getattr(rx, 'additional_notes', None) or getattr(rx, 'notes', None) or ''),
                'link': url_for('doctor.prescriptions_history', patient_id=patient_id),
            })

        lab_reqs = LabRequest.query.filter(LabRequest.patient_id == patient_id).order_by(
            LabRequest.created_at.desc()
        ).limit(200).all()
        for lr in lab_reqs:
            events.append({
                'type': 'lab',
                'dt': lr.created_at or datetime.now(),
                'title': f"مختبر: {getattr(lr, 'test_name', None) or getattr(lr, 'test_type', None) or 'طلب'}",
                'status': lr.status,
                'details': (getattr(lr, 'reason', None) or getattr(lr, 'notes', None) or ''),
                'link': None,
            })

        rad_reqs = RadiologyRequest.query.filter(RadiologyRequest.patient_id == patient_id).order_by(
            RadiologyRequest.created_at.desc()
        ).limit(200).all()
        for rr in rad_reqs:
            events.append({
                'type': 'radiology',
                'dt': rr.created_at or datetime.now(),
                'title': f"أشعة: {getattr(rr, 'test_name', None) or getattr(rr, 'modality', None) or 'طلب'}",
                'status': rr.status,
                'details': (getattr(rr, 'clinical_info', None) or getattr(rr, 'notes', None) or ''),
                'link': None,
            })

        records = MedicalRecord.query.filter(MedicalRecord.patient_id == patient_id).order_by(
            MedicalRecord.created_at.desc()
        ).limit(200).all()
        for mr in records:
            events.append({
                'type': 'record',
                'dt': mr.created_at or datetime.now(),
                'title': mr.title or 'سجل طبي',
                'status': None,
                'details': mr.details or '',
                'link': url_for('doctor.medical_history', patient_id=patient_id),
            })

        follow_ups = FollowUpRequest.query.filter(FollowUpRequest.patient_id == patient_id).order_by(
            FollowUpRequest.created_at.desc()
        ).limit(200).all()
        for fu in follow_ups:
            events.append({
                'type': 'follow_up',
                'dt': datetime.combine(fu.suggested_date, datetime.min.time()) if fu.suggested_date else (fu.created_at or datetime.now()),
                'title': 'متابعة مقترحة',
                'status': fu.status,
                'details': fu.notes or '',
                'link': None,
            })

        appointments = Appointment.query.filter(Appointment.patient_id == patient_id).order_by(
            Appointment.starts_at.desc()
        ).limit(200).all()
        for ap in appointments:
            events.append({
                'type': 'appointment',
                'dt': ap.starts_at or datetime.now(),
                'title': 'موعد',
                'status': ap.status,
                'details': ap.notes or '',
                'link': None,
            })

        ft = (filter_type or '').strip().lower()
        if ft:
            events = [e for e in events if e.get('type') == ft]
        events.sort(key=lambda e: e.get('dt') or datetime.now(), reverse=True)
        return events

    @staticmethod
    def _visit_datetime(visit) -> datetime:
        if getattr(visit, 'visit_date', None) and getattr(visit, 'visit_time', None):
            try:
                return datetime.combine(visit.visit_date, visit.visit_time)
            except Exception:
                pass
        return visit.created_at or datetime.now()

    @staticmethod
    def summarize(events: list[dict]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for e in events:
            t = e.get('type', 'other')
            summary[t] = summary.get(t, 0) + 1
        return summary
