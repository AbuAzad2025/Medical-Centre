"""
IHE PIX/PDQ Service — Patient Identifier Cross-referencing & Patient Demographics Query.

PIX (ITI-8/9): cross-reference patient identifiers across assigning authorities.
PDQ (ITI-21): query demographics by name/birthdate/phone.

Implemented against the local Patient table; assigning authority is tenant_id.
No external PIX manager required. HTTP JSON endpoints expose the same contracts.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)


class IHEPixPdqService:
    """PIX/PDQ operations scoped by tenant_id (assigning authority)."""

    @staticmethod
    def pix_query(
        patient_id: str, domain: str | None = None, tenant_id: int | None = None
    ) -> dict[str, Any]:
        """
        PIX Query — return all identifiers for the patient across domains.
        For single-tenant deployment, the patient has one identifier; for SaaS,
        we return tenant-scoped cross-reference.
        """
        from app.extensions import db
        from models.patient import Patient

        # Try national_id, then id
        q = select(Patient)
        if tenant_id:
            q = q.filter(Patient.tenant_id == tenant_id)
        # numeric id lookup
        candidates: list[Patient] = []
        try:
            pid_int = int(str(patient_id).strip())
            row = db.session.execute(q.filter(Patient.id == pid_int)).scalars().first()
            if row:
                candidates.append(row)
        except ValueError:
            pass
        if not candidates:
            # national_id lookup (encrypted — decrypt comparison)
            try:
                rows = db.session.execute(q.limit(200)).scalars().all()
                for p in rows:
                    if p.national_id == patient_id:
                        candidates.append(p)
                        break
            except Exception:
                pass

        if not candidates:
            return {'found': False, 'identifiers': []}

        pat = candidates[0]
        identifiers = [
            {'domain': f'TENANT-{pat.tenant_id}', 'id': str(pat.id), 'type': 'MR'},
        ]
        if pat.national_id:
            identifiers.append({'domain': 'NATIONAL_ID', 'id': pat.national_id, 'type': 'NI'})
        if domain:
            identifiers = [i for i in identifiers if i['domain'] == domain]
        return {
            'found': True,
            'patient_id': pat.id,
            'identifiers': identifiers,
            'domain': domain or 'ALL',
        }

    @staticmethod
    def pdq_query(
        family_name: str | None = None,
        given_name: str | None = None,
        birth_date: str | None = None,
        phone: str | None = None,
        tenant_id: int | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """PDQ Query — demographics search with pagination."""
        from app.extensions import db
        from models.patient import Patient

        q = select(Patient)
        if tenant_id:
            q = q.filter(Patient.tenant_id == tenant_id)

        # Fetch candidates (encrypted names require post-filter)
        rows = db.session.execute(q.limit(200)).scalars().all()
        matched: list[Patient] = []
        for p in rows:
            ok = True
            if family_name and family_name.strip().lower() not in (p.last_name or '').lower():
                # Also check first_name_ar/last_name_ar
                if family_name.strip().lower() not in (p.last_name_ar or '').lower():
                    ok = False
            if given_name and given_name.strip().lower() not in (p.first_name or '').lower():
                if given_name.strip().lower() not in (p.first_name_ar or '').lower():
                    ok = False
            if birth_date:
                bd = p.birth_date.isoformat() if p.birth_date else ''
                if birth_date.strip() not in bd:
                    ok = False
            if phone and phone.strip() not in (p.phone or ''):
                ok = False
            if ok:
                matched.append(p)
            if len(matched) >= limit:
                break

        return {
            'total': len(matched),
            'patients': [
                {
                    'id': p.id,
                    'full_name': p.full_name,
                    'first_name': p.first_name,
                    'last_name': p.last_name,
                    'birth_date': p.birth_date.isoformat() if p.birth_date else None,
                    'gender': p.gender,
                    'phone': p.phone,
                    'national_id': '***'
                    + (p.national_id[-4:] if p.national_id and len(p.national_id) >= 4 else ''),
                }
                for p in matched
            ],
        }

    @staticmethod
    def atna_audit(
        event_type: str, user_id: int | None, patient_id: int | None, outcome: str = '0'
    ):
        """ATNA audit record — writes to SecurityEvent / AuditTrail."""
        try:
            from datetime import UTC, datetime

            from app.extensions import db
            from models.audit_trail import SecurityEvent

            evt = SecurityEvent(
                event_type=event_type[:50] if event_type else 'IHE',
                severity='low',
                description=f'ATNA {event_type} patient={patient_id} outcome={outcome}',
                user_id=user_id,
                ip_address='127.0.0.1',
                is_resolved=False,
                created_at=datetime.now(UTC),
            )
            db.session.add(evt)
            from utils.db_safety import safe_commit

            safe_commit(db.session, error_message='ATNA audit failed')
        except Exception as exc:  # noqa: BLE001
            logger.debug('ATNA audit skipped: %s', exc)


ihe_service = IHEPixPdqService()
