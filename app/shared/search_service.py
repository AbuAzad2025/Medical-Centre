"""Unified search layer — tenant-scoped (G-84)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_


class SearchService:
    """Single entry for patient/staff search APIs."""

    @staticmethod
    def search_patients(query: str, *, limit: int = 20) -> list[dict[str, Any]]:
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

        # These six columns hold ciphertext, so an ilike on them can never
        # match: the same plaintext encrypts differently on every write. The
        # blind index plus the trigram table answer it. Patient has no `code`
        # column, so that guarded branch is gone with them.
        filters = [Patient.id.in_(Patient.search_ids(query, limit=limit))]

        from utils.tenant_query import tenant_filter

        q = tenant_filter(Patient)
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
