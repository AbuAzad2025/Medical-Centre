"""
Insurance Claim lifecycle service — bridges Visit/Invoice -> InsuranceClaim -> Payout/EOB
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)


class InsuranceClaimService:
    @staticmethod
    def list_claims(tenant_id: int | None) -> list[dict]:
        from models.insurance import InsuranceClaim

        q = select(InsuranceClaim)
        if tenant_id:
            q = q.filter(InsuranceClaim.tenant_id == tenant_id)
        rows = (
            db.session.execute(q.order_by(InsuranceClaim.created_at.desc()).limit(100))
            .scalars()
            .all()
        )
        return [
            {
                'id': r.id,
                'claim_number': r.claim_number,
                'status': r.status,
                'total_claim': str(r.total_claim),
                'visit_id': r.visit_id,
            }
            for r in rows
        ]

    @staticmethod
    def create_claim(visit_id, invoice_id, company_id, total_claim, tenant_id) -> tuple[bool, dict]:
        from models.insurance import InsuranceClaim

        if not visit_id and not invoice_id:
            return False, {'error': 'visit_id or invoice_id required'}
        claim_number = f'CLM-{int(datetime.now(UTC).timestamp())}-{visit_id or invoice_id}'
        claim = InsuranceClaim(
            tenant_id=tenant_id,
            visit_id=visit_id,
            invoice_id=invoice_id,
            company_id=company_id,
            claim_number=claim_number,
            status='DRAFT',
            total_claim=Decimal(str(total_claim or 0)),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.session.add(claim)
        if not safe_commit(db.session, error_message='create claim failed'):
            return False, {'error': 'db error'}
        return True, {'id': claim.id, 'claim_number': claim.claim_number, 'status': claim.status}

    @staticmethod
    def submit_claim(claim_id: int, tenant_id) -> tuple[bool, dict]:
        from models.insurance import InsuranceClaim

        claim = db.session.get(InsuranceClaim, claim_id)
        if not claim or (tenant_id and claim.tenant_id != tenant_id):
            return False, {'error': 'claim not found'}
        if claim.status != 'DRAFT':
            return False, {'error': f'cannot submit from {claim.status}'}
        claim.submit()
        claim.updated_at = datetime.now(UTC)
        if not safe_commit(db.session, error_message='submit failed'):
            return False, {'error': 'db error'}
        return True, {'id': claim.id, 'status': claim.status}

    @staticmethod
    def adjudicate_claim(claim_id, approved_amount, status, notes, tenant_id) -> tuple[bool, dict]:
        from app.shared.enums import InsuranceClaimStatus
        from models.insurance import InsuranceClaim

        claim = db.session.get(InsuranceClaim, claim_id)
        if not claim or (tenant_id and claim.tenant_id != tenant_id):
            return False, {'error': 'claim not found'}
        try:
            st = InsuranceClaimStatus(status) if status else InsuranceClaimStatus.APPROVED
        except ValueError:
            return False, {'error': 'invalid status'}
        claim.adjudicate(approved_amount, st.value if hasattr(st, 'value') else str(st), notes)
        claim.updated_at = datetime.now(UTC)
        if not safe_commit(db.session, error_message='adjudicate failed'):
            return False, {'error': 'db error'}
        # Auto-create EOB
        try:
            from models.insurance import EOB

            eob = EOB(
                tenant_id=tenant_id,
                claim_id=claim.id,
                eob_number=f'EOB-{claim.id}-{int(datetime.now(UTC).timestamp())}',
                adjudication_status=claim.status,
                total_billed=claim.total_claim,
                total_allowed=claim.approved_amount,
                patient_responsibility=claim.patient_share_amount,
                raw_payload=notes or '',
            )
            db.session.add(eob)
            safe_commit(db.session, error_message='eob failed')
        except Exception:
            pass
        return True, {
            'id': claim.id,
            'status': claim.status,
            'approved_amount': str(claim.approved_amount),
        }

    @staticmethod
    def settle_claim(claim_id, settled_amount, tenant_id) -> tuple[bool, dict]:
        from models.insurance import InsuranceClaim

        claim = db.session.get(InsuranceClaim, claim_id)
        if not claim or (tenant_id and claim.tenant_id != tenant_id):
            return False, {'error': 'claim not found'}
        claim.settle(settled_amount)
        claim.updated_at = datetime.now(UTC)
        if not safe_commit(db.session, error_message='settle failed'):
            return False, {'error': 'db error'}
        return True, {'id': claim.id, 'status': claim.status}

    @staticmethod
    def record_payout(claim_id, amount, method, reference, tenant_id) -> tuple[bool, dict]:
        from models.insurance import InsurancePayout

        try:
            payout = InsurancePayout(
                tenant_id=tenant_id,
                claim_id=claim_id,
                payout_number=f'PAY-{claim_id}-{int(datetime.now(UTC).timestamp())}',
                amount=Decimal(str(amount or 0)),
                method=method or 'WIRE',
                reference=reference,
            )
            db.session.add(payout)
            if not safe_commit(db.session, error_message='payout failed'):
                return False, {'error': 'db error'}
            return True, {'id': payout.id, 'payout_number': payout.payout_number}
        except Exception as exc:  # noqa: BLE001
            logger.warning('payout failed: %s', exc)
            return False, {'error': str(exc)}
