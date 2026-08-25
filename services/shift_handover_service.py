"""ShiftHandoverService — open/close/transfer/acknowledge lifecycle.

Business rules enforced here (each maps to a test):
  R1  Only ONE open shift per (tenant, role) at a time.
  R2  Close with non-zero cash difference REQUIRES a close note.
  R3  Transfer target must hold the same role as the shift.
  R4  Snapshots (cash + pending work) are captured once, at close, frozen.
  R5  Only the assigned successor can ACKNOWLEDGE a CLOSED shift.
"""

import logging
from datetime import UTC, datetime

from flask import g
from sqlalchemy import func, select

from app.extensions import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)


class HandoverError(Exception):
    """Domain error; str(e) is a stable machine code mapped to Arabic in routes."""


class ShiftHandoverService:
    @staticmethod
    def _build_cash_summary() -> dict:
        """Aggregate today's OPEN cash register for the current tenant."""
        from models.cash_register import CashRegister

        today = datetime.now(UTC).date()
        reg = (
            db.session.execute(
                select(CashRegister).filter_by(register_date=today).order_by(CashRegister.id.desc())
            )
            .scalars()
            .first()
        )
        if not reg:
            return {'register': None}

        expected = float(reg.expected_cash or 0)
        actual = float(reg.actual_cash) if reg.actual_cash is not None else None
        return {
            'register': {
                'id': reg.id,
                'date': str(today),
                'is_closed': reg.closed_at is not None,
                'expected_cash': expected,
                'actual_cash': actual,
                'difference': round((actual - expected), 2) if actual is not None else None,
            }
        }

    @staticmethod
    def _build_pending_items() -> dict:
        """Counts (+ids) of outstanding operational work for the tenant."""
        from models.lab_request import LabRequest
        from models.queue_management import QueueManagement

        waiting_rows = db.session.execute(
            select(QueueManagement.id, QueueManagement.patient_id).where(
                QueueManagement.status == 'waiting'
            )
        ).all()

        pending_labs = (
            db.session.execute(
                select(LabRequest.id).where(LabRequest.status.in_(['PENDING', 'IN_PROGRESS']))
            )
            .scalars()
            .all()
        )

        pending_radiology_ids: list[int] = []
        try:
            from models.radiology_request import RadiologyRequest

            pending_radiology_ids = list(
                db.session.execute(
                    select(RadiologyRequest.id).where(
                        RadiologyRequest.status.in_(['PENDING', 'IN_PROGRESS'])
                    )
                )
                .scalars()
                .all()
            )
        except Exception:
            logger.debug('radiology snapshot skipped', exc_info=True)

        pending_rx_ids: list[int] = []
        try:
            from models.prescription import Prescription

            pending_rx_ids = list(
                db.session.execute(
                    select(Prescription.id).where(Prescription.is_dispensed.is_(False))
                )
                .scalars()
                .all()
            )
        except Exception:
            logger.debug('prescription snapshot skipped', exc_info=True)

        return {
            'queue_waiting': {
                'count': len(waiting_rows),
                'ticket_ids': [r[0] for r in waiting_rows],
            },
            'pending_labs': {'count': len(pending_labs), 'ids': pending_labs[:100]},
            'pending_radiology': {
                'count': len(pending_radiology_ids),
                'ids': pending_radiology_ids[:100],
            },
            'pending_prescriptions': {'count': len(pending_rx_ids), 'ids': pending_rx_ids[:100]},
        }

    @staticmethod
    def open_shift(user_id: int, role: str, to_user_id: int | None = None, notes: str = '') -> dict:
        from models.shift_handover import ShiftHandover

        if not role:
            raise HandoverError('role_required')

        existing = (
            db.session.execute(
                select(func.count())
                .select_from(ShiftHandover)
                .where(ShiftHandover.status == 'OPEN', ShiftHandover.role == role)
            ).scalar()
            or 0
        )
        if existing:
            raise HandoverError('already_open')

        sh = ShiftHandover(
            tenant_id=getattr(g, 'tenant_id', None),
            opened_by_id=user_id,
            to_user_id=to_user_id,
            role=role,
            status='OPEN',
            notes=notes or None,
            opened_at=datetime.now(UTC),
        )
        db.session.add(sh)
        safe_commit(db.session, error_message='handover open failed', reraise=True)
        return sh.to_dict()

    @staticmethod
    def close_shift(
        shift_id: int, user_id: int, close_note: str = '', to_user_id: int | None = None
    ):
        """Close (or transfer-then-close) the shift and freeze snapshots."""
        from models.shift_handover import ShiftHandover

        sh = db.session.get(ShiftHandover, shift_id)
        if not sh or sh.tenant_id != getattr(g, 'tenant_id', None):
            raise HandoverError('not_found')
        if sh.status != 'OPEN':
            raise HandoverError('not_open')

        if to_user_id:
            from models.user import User

            target = db.session.get(User, to_user_id)
            if not target or not target.is_active:
                raise HandoverError('invalid_target')
            if target.role != sh.role:
                raise HandoverError('role_mismatch')
            sh.to_user_id = to_user_id

        sh.cash_summary = ShiftHandoverService._build_cash_summary()
        sh.pending_items = ShiftHandoverService._build_pending_items()

        diff = None
        try:
            reg = (sh.cash_summary or {}).get('register') or {}
            diff = reg.get('difference')
        except Exception:
            diff = None
        if diff not in (None, 0, 0.0) and not (close_note or '').strip():
            raise HandoverError('cash_diff_requires_note')

        sh.close_note = (close_note or '').strip() or None
        sh.closed_by_id = user_id
        sh.status = 'CLOSED'
        sh.closed_at = datetime.now(UTC)

        safe_commit(db.session, error_message='handover close failed', reraise=True)
        return sh.to_dict()

    @staticmethod
    def acknowledge(shift_id: int, user_id: int) -> dict:
        """Successor confirms receipt of the closed handover."""
        from models.shift_handover import ShiftHandover

        sh = db.session.get(ShiftHandover, shift_id)
        if not sh or sh.tenant_id != getattr(g, 'tenant_id', None):
            raise HandoverError('not_found')
        if sh.status != 'CLOSED':
            raise HandoverError('not_closed')

        if sh.to_user_id and sh.to_user_id != user_id:
            raise HandoverError('not_assignee')

        sh.status = 'ACKNOWLEDGED'
        sh.acknowledged_at = datetime.now(UTC)
        safe_commit(db.session, error_message='handover acknowledge failed', reraise=True)
        return sh.to_dict()

    @staticmethod
    def list_shifts(limit: int = 50) -> list[dict]:
        from models.shift_handover import ShiftHandover

        rows = (
            db.session.execute(
                select(ShiftHandover).order_by(ShiftHandover.opened_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        return [r.to_dict() for r in rows]
