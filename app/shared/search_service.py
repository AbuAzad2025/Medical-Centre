"""Unified search layer — tenant-scoped (G-84)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, List

from sqlalchemy import or_

from app_factory import db


class SearchService:
    """Single entry for patient/staff search APIs."""

    @staticmethod
    def search_patients(query: str, *, limit: int = 20) -> List[dict[str, Any]]:
        query = (query or '').strip()
        if not query:
            return []

        from models.patient import Patient

        limit = max(1, min(int(limit or 20), 50))
        parsed_date = None
        if len(query) >= 8:
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    parsed_date = datetime.strptime(query, fmt).date()
                    break
                except ValueError:
                    continue

        filters = [
            Patient.first_name.ilike(f'%{query}%'),
            Patient.last_name.ilike(f'%{query}%'),
            Patient.first_name_ar.ilike(f'%{query}%'),
            Patient.last_name_ar.ilike(f'%{query}%'),
            Patient.national_id.ilike(f'%{query}%'),
            Patient.phone.ilike(f'%{query}%'),
        ]
        if hasattr(Patient, 'code'):
            filters.append(Patient.code.ilike(f'%{query}%'))

        q = Patient.query
        if parsed_date:
            q = q.filter(or_(*filters, Patient.birth_date == parsed_date))
        else:
            q = q.filter(or_(*filters))

        rows = q.order_by(Patient.created_at.desc()).limit(limit).all()
        return [
            {
                'id': p.id,
                'full_name': p.full_name,
                'national_id': p.national_id,
                'phone': p.phone,
                'birth_date': p.birth_date.strftime('%Y-%m-%d') if p.birth_date else None,
                'gender': getattr(p, 'gender', None),
                'address': getattr(p, 'address', None),
            }
            for p in rows
        ]
