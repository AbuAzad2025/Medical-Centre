"""Unified work inbox — UX1-003."""

from flask import Blueprint, render_template
from flask_login import login_required, current_user

inbox_bp = Blueprint('inbox', __name__)


@inbox_bp.route('/inbox')
@login_required
def dashboard():
    """لوحة العمل الموحدة — تجمع المهام المعلّقة للمستخدم."""
    items = []

    try:
        from models.appointment import Appointment
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.invoice import Invoice
        from app.shared.enums import AppointmentStatus, InvoiceStatus

        pending_appointments = Appointment.query.filter(
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).order_by(Appointment.starts_at).limit(10).all()
        for a in pending_appointments:
            items.append({
                'id': f'appt-{a.id}',
                'type': 'موعد',
                'title': f"موعد مع {a.patient.full_name if a.patient else 'مريض'}",
                'time': a.starts_at.strftime('%Y-%m-%d %H:%M') if a.starts_at else '-',
                'status': a.status.value if hasattr(a.status, 'value') else a.status,
                'priority': 'high' if a.status == AppointmentStatus.PENDING else 'medium',
                'link': f"/reception/appointments",
            })

        pending_labs = LabRequest.query.filter(
            LabRequest.status.in_(['REQUESTED', 'COLLECTED'])
        ).order_by(LabRequest.created_at.desc()).limit(10).all()
        for r in pending_labs:
            items.append({
                'id': f'lab-{r.id}',
                'type': 'مختبر',
                'title': f"طلب مختبر #{r.request_number or r.id}",
                'time': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '-',
                'status': r.status,
                'priority': 'high' if r.urgency == 'URGENT' else 'medium',
                'link': f"/lab/worklist",
            })

        pending_radio = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_(['REQUESTED', 'SCHEDULED'])
        ).order_by(RadiologyRequest.created_at.desc()).limit(10).all()
        for r in pending_radio:
            items.append({
                'id': f'radio-{r.id}',
                'type': 'أشعة',
                'title': f"طلب أشعة #{r.request_number or r.id}",
                'time': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '-',
                'status': r.status,
                'priority': 'high' if r.urgency == 'URGENT' else 'medium',
                'link': f"/radiology/worklist",
            })

        open_invoices = Invoice.query.filter(
            Invoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.ISSUED])
        ).order_by(Invoice.created_at.desc()).limit(10).all()
        for inv in open_invoices:
            remaining = float((inv.total_amount or 0) - (inv.paid_amount or 0))
            items.append({
                'id': f'inv-{inv.id}',
                'type': 'فاتورة',
                'title': f"فاتورة #{inv.invoice_number or inv.id} — متبقي {remaining:.2f}",
                'time': inv.created_at.strftime('%Y-%m-%d %H:%M') if inv.created_at else '-',
                'status': inv.status.value if hasattr(inv.status, 'value') else inv.status,
                'priority': 'high' if remaining > 1000 else 'medium',
                'link': f"/finance/invoices",
            })
    except Exception:
        items = []

    return render_template('inbox/dashboard.html', items=items, user_role=current_user.role)
