"""Unified work inbox — aggregates actionable tickets by role (UX1-003)."""
from __future__ import annotations

from typing import Any

from app.shared.enums import AppointmentState, InvoiceStatus, VisitState


# Capability keys gating premium inbox card families (EntitlementResolver)
_INBOX_ENTITLEMENTS: dict[str, str] = {
    'lab': 'lab_order',
    'radiology': 'radiology_order',
    'invoice': 'billing',
    'visit': 'reception',
}

_ROLE_VISIBLE_TYPES: dict[str, set[str]] = {
    'reception': {'appointment', 'visit', 'invoice'},
    'doctor': {'appointment', 'visit', 'lab', 'radiology'},
    'lab': {'lab', 'visit'},
    'technician': {'lab'},
    'radiology': {'radiology'},
    'pharmacist': {'visit', 'appointment'},
    'accountant': {'invoice', 'visit'},
    'manager': {'appointment', 'visit', 'lab', 'radiology', 'invoice'},
    'admin': {'appointment', 'visit', 'lab', 'radiology', 'invoice'},
    'emergency': {'visit', 'appointment'},
    'nurse': {'visit', 'appointment'},
}


def _entitled_for_type(item_type: str, is_entitled) -> bool:
    cap = _INBOX_ENTITLEMENTS.get(item_type)
    if not cap:
        return True
    try:
        return bool(is_entitled(cap))
    except Exception:
        return True


class WorkInboxService:
    @staticmethod
    def get_inbox_items(user, *, is_entitled=None, limit: int = 50) -> list[dict[str, Any]]:
        """Return normalized inbox rows filtered by role and entitlements."""
        role = getattr(user, 'role', None) or ''
        allowed_types = _ROLE_VISIBLE_TYPES.get(role, _ROLE_VISIBLE_TYPES['manager'])
        is_entitled = is_entitled or (lambda _k: True)
        items: list[dict[str, Any]] = []

        items.extend(WorkInboxService._visit_tickets(limit=15))
        items.extend(WorkInboxService._appointment_tickets(limit=10))
        items.extend(WorkInboxService._lab_tickets(limit=10))
        items.extend(WorkInboxService._radiology_tickets(limit=10))
        items.extend(WorkInboxService._invoice_tickets(limit=10))

        filtered = []
        for item in items:
            t = item.get('item_type', '')
            if t not in allowed_types:
                continue
            entitled = _entitled_for_type(t, is_entitled)
            item['entitled'] = entitled
            if not entitled:
                item['link'] = None
                item['title'] = f"{item['title']} (مقفول — باقة أعلى)"
            filtered.append(item)

        filtered.sort(key=lambda x: (0 if x.get('priority') == 'high' else 1, x.get('time_sort', '')))
        return filtered[:limit]

    @staticmethod
    def _visit_tickets(limit: int) -> list[dict[str, Any]]:
        from models.visit import Visit

        actionable = [
            VisitState.OPEN,
            VisitState.CHECKED_IN,
            VisitState.IN_PROGRESS,
        ]
        visits = Visit.query.filter(
            Visit.status.in_(actionable),
        ).order_by(Visit.created_at.desc()).limit(limit).all()
        rows = []
        for v in visits:
            patient_name = v.patient.full_name if v.patient else 'مريض'
            status = v.status.value if hasattr(v.status, 'value') else str(v.status)
            priority = 'high' if v.status in (VisitState.OPEN, VisitState.IN_PROGRESS) else 'medium'
            rows.append({
                'id': f'visit-{v.id}',
                'item_type': 'visit',
                'type': 'زيارة',
                'title': f"زيارة {patient_name} — {status}",
                'time': v.created_at.strftime('%Y-%m-%d %H:%M') if v.created_at else '-',
                'time_sort': v.created_at.isoformat() if v.created_at else '',
                'status': status,
                'priority': priority,
                'link': f'/reception/visits',
                'vsm_state': status,
            })
        return rows

    @staticmethod
    def _appointment_tickets(limit: int) -> list[dict[str, Any]]:
        from models.appointment import Appointment

        pending = Appointment.query.filter(
            Appointment.status.in_([
                AppointmentState.SCHEDULED,
                AppointmentState.CONFIRMED,
                AppointmentState.CHECKED_IN,
            ])
        ).order_by(Appointment.starts_at).limit(limit).all()
        rows = []
        for a in pending:
            status = a.status.value if hasattr(a.status, 'value') else str(a.status)
            rows.append({
                'id': f'appt-{a.id}',
                'item_type': 'appointment',
                'type': 'موعد',
                'title': f"موعد مع {a.patient.full_name if a.patient else 'مريض'}",
                'time': a.starts_at.strftime('%Y-%m-%d %H:%M') if a.starts_at else '-',
                'time_sort': a.starts_at.isoformat() if a.starts_at else '',
                'status': status,
                'priority': 'high' if status == AppointmentState.SCHEDULED.value else 'medium',
                'link': '/reception/appointments',
            })
        return rows

    @staticmethod
    def _lab_tickets(limit: int) -> list[dict[str, Any]]:
        from models.lab_request import LabRequest

        pending_labs = LabRequest.query.filter(
            LabRequest.status.in_(['REQUESTED', 'COLLECTED', 'IN_PROGRESS'])
        ).order_by(LabRequest.created_at.desc()).limit(limit).all()
        rows = []
        for r in pending_labs:
            rows.append({
                'id': f'lab-{r.id}',
                'item_type': 'lab',
                'type': 'مختبر',
                'title': f"طلب مختبر #{r.request_number or r.id}",
                'time': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '-',
                'time_sort': r.created_at.isoformat() if r.created_at else '',
                'status': r.status,
                'priority': 'high' if getattr(r, 'urgency', '') == 'URGENT' else 'medium',
                'link': '/lab/worklist',
            })
        return rows

    @staticmethod
    def _radiology_tickets(limit: int) -> list[dict[str, Any]]:
        from models.radiology_request import RadiologyRequest

        pending_radio = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_(['REQUESTED', 'SCHEDULED', 'IN_PROGRESS'])
        ).order_by(RadiologyRequest.created_at.desc()).limit(limit).all()
        rows = []
        for r in pending_radio:
            rows.append({
                'id': f'radio-{r.id}',
                'item_type': 'radiology',
                'type': 'أشعة',
                'title': f"طلب أشعة #{r.request_number or r.id}",
                'time': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '-',
                'time_sort': r.created_at.isoformat() if r.created_at else '',
                'status': r.status,
                'priority': 'high' if getattr(r, 'urgency', '') == 'URGENT' else 'medium',
                'link': '/radiology/worklist',
            })
        return rows

    @staticmethod
    def _invoice_tickets(limit: int) -> list[dict[str, Any]]:
        from models.invoice import Invoice

        open_invoices = Invoice.query.filter(
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED])
        ).order_by(Invoice.created_at.desc()).limit(limit).all()
        rows = []
        for inv in open_invoices:
            remaining = float((inv.total_amount or 0) - (inv.paid_amount or 0))
            status = inv.status.value if hasattr(inv.status, 'value') else str(inv.status)
            rows.append({
                'id': f'inv-{inv.id}',
                'item_type': 'invoice',
                'type': 'فاتورة',
                'title': f"فاتورة #{inv.invoice_number or inv.id} — متبقي {remaining:.2f}",
                'time': inv.created_at.strftime('%Y-%m-%d %H:%M') if inv.created_at else '-',
                'time_sort': inv.created_at.isoformat() if inv.created_at else '',
                'status': status,
                'priority': 'high' if remaining > 1000 else 'medium',
                'link': '/finance/invoices',
            })
        return rows

    @staticmethod
    def get_type_counts(items: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            t = item.get('type', 'أخرى')
            counts[t] = counts.get(t, 0) + 1
        return counts
