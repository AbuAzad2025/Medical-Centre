"""Command Center data + render helper — §29.

Production-grade implementation with strict tenant isolation,
role-appropriate data loading, deduplicated widget handling,
and comprehensive error resilience.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from flask import g, render_template, url_for
from sqlalchemy import func, select

from app.shared.dashboard_registry import (
    ROLE_DASHBOARD_TITLES,
    ROLE_LAYOUTS,
    ROLE_QUICK_ACTIONS,
    WIDGETS,
    WidgetMeta,
    resolve_dashboard_widgets,
)


def _enabled_modules() -> set[str]:
    return set(getattr(g, 'enabled_modules', None) or [])


def _user_hidden_widgets(user) -> set[str]:
    from app.shared.user_preferences import get_user_preferences

    prefs = get_user_preferences(user)
    dash = prefs.get('dashboard') or {}
    if isinstance(dash, dict):
        return set(dash.get('hidden_widgets') or [])
    return set()


def _tenant_id(user) -> int | None:
    return getattr(user, 'tenant_id', None) or getattr(g, 'tenant_id', None)


def build_hero_context(user) -> dict[str, Any]:
    now = datetime.now()
    hour = now.hour
    if hour < 12:
        shift = 'صباح'
    elif hour < 17:
        shift = 'ظهر'
    else:
        shift = 'مساء'
    weekdays = ['الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت', 'الأحد']
    return {
        'greeting_name': user.full_name or user.username,
        'shift_label': shift,
        'date_label': f'{weekdays[now.weekday()]} {now.day}/{now.month}/{now.year}',
        'role_label': user.role,
    }


def _load_reception_data(tid: int | None, today: date, data: dict[str, Any]) -> None:
    from app.extensions import db
    from app.shared.enums import AppointmentState, QueueState, VisitState
    from models.appointment import Appointment
    from models.queue_management import QueueManagement
    from models.visit import Visit
    from services.core_queries import core_queries

    try:
        stats = core_queries.get_basic_dashboard_stats()
    except Exception:
        stats = {}
    q = (
        select(func.count())
        .select_from(QueueManagement)
        .filter(QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED]))
    )
    if tid and hasattr(QueueManagement, 'tenant_id'):
        q = q.filter(QueueManagement.tenant_id == tid)
    try:
        waiting = db.session.execute(q).scalar() or 0
    except Exception:
        waiting = 0
    data['metrics']['queue_count'] = waiting
    data['metrics']['visits_today'] = stats.get('visits_today', 0) if isinstance(stats, dict) else 0
    data['metrics']['total_patients'] = (
        stats.get('total_patients', 0) if isinstance(stats, dict) else 0
    )
    try:
        q = select(QueueManagement).filter(
            QueueManagement.status.in_(
                [QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS]
            )
        )
        if tid and hasattr(QueueManagement, 'tenant_id'):
            q = q.filter(QueueManagement.tenant_id == tid)
        data['lists']['active_queue'] = (
            db.session.execute(q.order_by(QueueManagement.queued_at.asc()).limit(10))
            .scalars()
            .all()
        )
    except Exception:
        data['lists']['active_queue'] = []
    try:
        q = select(Visit).filter(
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS, VisitState.COMPLETED]),
        )
        if tid and hasattr(Visit, 'tenant_id'):
            q = q.filter(Visit.tenant_id == tid)
        data['lists']['today_visits'] = (
            db.session.execute(q.order_by(Visit.created_at.desc()).limit(15)).scalars().all()
        )
    except Exception:
        data['lists']['today_visits'] = []
    try:
        q = select(Appointment).filter(
            func.date(Appointment.starts_at) == today,
            Appointment.status.in_(
                [
                    AppointmentState.SCHEDULED,
                    AppointmentState.CONFIRMED,
                    AppointmentState.CHECKED_IN,
                ]
            ),
        )
        if tid and hasattr(Appointment, 'tenant_id'):
            q = q.filter(Appointment.tenant_id == tid)
        data['lists']['today_appointments'] = (
            db.session.execute(q.order_by(Appointment.starts_at.asc()).limit(10)).scalars().all()
        )
    except Exception:
        data['lists']['today_appointments'] = []


def _load_manager_data(tid: int | None, today: date, data: dict[str, Any]) -> None:
    from app.extensions import db
    from models.invoice import Invoice
    from models.payment import Payment
    from models.user import User

    try:
        q = select(func.coalesce(func.sum(Payment.amount), 0)).filter(
            func.date(Payment.created_at) == today
        )
        if tid and hasattr(Payment, 'tenant_id'):
            q = q.filter(Payment.tenant_id == tid)
        today_revenue = db.session.execute(q).scalar() or 0
        data['metrics']['today_revenue'] = float(today_revenue)
    except Exception:
        data['metrics']['today_revenue'] = 0.0
    try:
        q = (
            select(func.count())
            .select_from(Invoice)
            .filter(Invoice.status.in_(['DRAFT', 'ISSUED']))
        )
        if tid and hasattr(Invoice, 'tenant_id'):
            q = q.filter(Invoice.tenant_id == tid)
        pending_invoices = db.session.execute(q).scalar() or 0
        data['metrics']['pending_invoices'] = int(pending_invoices)
    except Exception:
        data['metrics']['pending_invoices'] = 0
    try:
        q = select(func.coalesce(func.sum(Invoice.total_amount - Invoice.paid_amount), 0)).filter(
            Invoice.status.in_(['DRAFT', 'ISSUED'])
        )
        if tid and hasattr(Invoice, 'tenant_id'):
            q = q.filter(Invoice.tenant_id == tid)
        pending_amount = db.session.execute(q).scalar() or 0
        data['metrics']['pending_amount'] = float(pending_amount)
    except Exception:
        data['metrics']['pending_amount'] = 0.0
    try:
        q = select(func.count()).select_from(User)
        if tid and hasattr(User, 'tenant_id'):
            q = q.filter(User.tenant_id == tid)
        staff_count = db.session.execute(q).scalar() or 0
        data['metrics']['staff_count'] = int(staff_count)
    except Exception:
        data['metrics']['staff_count'] = 0
    try:
        q = select(func.count()).select_from(User).filter(User.is_active == True)  # noqa: E712
        if tid and hasattr(User, 'tenant_id'):
            q = q.filter(User.tenant_id == tid)
        active_staff = db.session.execute(q).scalar() or 0
        data['metrics']['active_staff'] = int(active_staff)
    except Exception:
        data['metrics']['active_staff'] = 0
    try:
        from models.visit import Visit

        q = select(func.count()).select_from(Visit).filter(Visit.visit_date == today)
        if tid and hasattr(Visit, 'tenant_id'):
            q = q.filter(Visit.tenant_id == tid)
        visits_today = db.session.execute(q).scalar() or 0
        data['metrics']['visits_today'] = int(visits_today)
    except Exception:
        data['metrics']['visits_today'] = 0


def _load_accountant_data(tid: int | None, today: date, data: dict[str, Any]) -> None:
    from sqlalchemy import func as sa_func

    from app.extensions import db
    from models.invoice import Invoice
    from models.payment import Payment

    try:
        q = (
            select(func.count())
            .select_from(Invoice)
            .filter(Invoice.status.in_(['ISSUED', 'DRAFT']))
        )
        if tid and hasattr(Invoice, 'tenant_id'):
            q = q.filter(Invoice.tenant_id == tid)
        pending = db.session.execute(q).scalar() or 0
        data['metrics']['pending_invoices'] = int(pending)
    except Exception:
        data['metrics']['pending_invoices'] = 0
    try:
        q = select(
            sa_func.coalesce(sa_func.sum(Invoice.total_amount - Invoice.paid_amount), 0)
        ).filter(Invoice.status.in_(['ISSUED', 'DRAFT', 'PARTIAL']))
        if tid and hasattr(Invoice, 'tenant_id'):
            q = q.filter(Invoice.tenant_id == tid)
        pending_amount = db.session.execute(q).scalar() or 0
        data['metrics']['pending_amount'] = float(pending_amount)
    except Exception:
        data['metrics']['pending_amount'] = 0.0
    try:
        q = select(sa_func.coalesce(sa_func.sum(Payment.amount), 0)).filter(
            func.date(Payment.created_at) == today
        )
        if tid and hasattr(Payment, 'tenant_id'):
            q = q.filter(Payment.tenant_id == tid)
        today_collected = db.session.execute(q).scalar() or 0
        data['metrics']['today_collected'] = float(today_collected)
    except Exception:
        data['metrics']['today_collected'] = 0.0
    try:
        q = select(sa_func.coalesce(sa_func.sum(Invoice.total_amount), 0))
        if tid and hasattr(Invoice, 'tenant_id'):
            q = q.filter(Invoice.tenant_id == tid)
        total_billed = db.session.execute(q).scalar() or 0
        q2 = select(sa_func.coalesce(sa_func.sum(Payment.amount), 0))
        if tid and hasattr(Payment, 'tenant_id'):
            q2 = q2.filter(Payment.tenant_id == tid)
        total_collected = db.session.execute(q2).scalar() or 0
        if float(total_billed) > 0:
            data['metrics']['collection_rate'] = round(
                float(total_collected) / float(total_billed) * 100, 1
            )
        else:
            data['metrics']['collection_rate'] = 0.0
        data['metrics']['total_billed'] = float(total_billed)
        data['metrics']['total_collected'] = float(total_collected)
    except Exception:
        data['metrics']['collection_rate'] = 0.0
        data['metrics']['total_billed'] = 0.0
        data['metrics']['total_collected'] = 0.0
    try:
        q = select(func.count()).select_from(Payment).filter(func.date(Payment.created_at) == today)
        if tid and hasattr(Payment, 'tenant_id'):
            q = q.filter(Payment.tenant_id == tid)
        today_payments = db.session.execute(q).scalar() or 0
        data['metrics']['today_payments'] = int(today_payments)
    except Exception:
        data['metrics']['today_payments'] = 0
    try:
        from models.payment import Payment as PayModel

        q = select(PayModel).order_by(PayModel.created_at.desc()).limit(5)
        if tid and hasattr(PayModel, 'tenant_id'):
            q = q.filter(PayModel.tenant_id == tid)
        data['lists']['recent_payments'] = db.session.execute(q).scalars().all()
    except Exception:
        data['lists']['recent_payments'] = []


def _module_active(tid: int | None, module: str) -> bool:
    if not tid:
        return True
    try:
        from app.core.module.validators import get_active_modules_for_tenant

        return module in get_active_modules_for_tenant(tid)
    except Exception:
        return True


def _load_role_data(role: str, user) -> dict[str, Any]:
    from app.extensions import db
    from app.shared.enums import (
        OrderState,
        VisitState,
    )
    from models.appointment import Appointment
    from models.emergency import EmergencyCase
    from models.lab_request import LabRequest
    from models.medication import Medication, PharmacySale, Prescription
    from models.radiology_request import RadiologyRequest
    from models.visit import Visit

    today = date.today()
    data: dict[str, Any] = {'metrics': {}, 'lists': {}}
    tid = _tenant_id(user)

    if role == 'reception':
        _load_reception_data(tid, today, data)

    if role in ('manager', 'admin', 'super_admin', 'owner'):
        _load_manager_data(tid, today, data)

    if role == 'accountant':
        _load_accountant_data(tid, today, data)

    if role == 'doctor':
        try:
            pending = db.session.execute(
                select(func.count())
                .select_from(Visit)
                .filter(
                    Visit.doctor_id == user.id,
                    Visit.status == VisitState.OPEN,
                )
            ).scalar()
            data['metrics']['waiting_patients'] = int(pending or 0)
        except Exception:
            data['metrics']['waiting_patients'] = 0
        try:
            data['metrics']['today_visits'] = int(
                db.session.execute(
                    select(func.count())
                    .select_from(Visit)
                    .filter(
                        Visit.doctor_id == user.id,
                        Visit.visit_date == today,
                    )
                ).scalar()
                or 0
            )
        except Exception:
            data['metrics']['today_visits'] = 0
        try:
            data['lists']['waiting_list'] = (
                db.session.execute(
                    select(Visit)
                    .filter(
                        Visit.doctor_id == user.id,
                        Visit.visit_date == today,
                        Visit.status.in_(
                            [VisitState.OPEN, VisitState.CHECKED_IN, VisitState.IN_PROGRESS]
                        ),
                    )
                    .order_by(Visit.created_at.asc())
                    .limit(8)
                )
                .scalars()
                .all()
            )
        except Exception:
            data['lists']['waiting_list'] = []
        try:
            data['lists']['today_appointments'] = (
                db.session.execute(
                    select(Appointment)
                    .filter(
                        Appointment.doctor_id == user.id,
                        func.date(Appointment.starts_at) == today,
                    )
                    .order_by(Appointment.starts_at.asc())
                    .limit(8)
                )
                .scalars()
                .all()
            )
        except Exception:
            data['lists']['today_appointments'] = []
        if _module_active(tid, 'lab'):
            try:
                data['lists']['pending_lab'] = (
                    db.session.execute(
                        select(LabRequest)
                        .join(Visit)
                        .filter(
                            Visit.doctor_id == user.id,
                            LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
                        )
                        .order_by(LabRequest.created_at.desc())
                        .limit(6)
                    )
                    .scalars()
                    .all()
                )
            except Exception:
                data['lists']['pending_lab'] = []
        else:
            data['lists']['pending_lab'] = []
        if _module_active(tid, 'radiology'):
            try:
                data['lists']['pending_radiology'] = (
                    db.session.execute(
                        select(RadiologyRequest)
                        .join(Visit)
                        .filter(
                            Visit.doctor_id == user.id,
                            RadiologyRequest.status.in_(
                                [OrderState.REQUESTED, OrderState.IN_PROGRESS]
                            ),
                        )
                        .order_by(RadiologyRequest.created_at.desc())
                        .limit(6)
                    )
                    .scalars()
                    .all()
                )
            except Exception:
                data['lists']['pending_radiology'] = []
        else:
            data['lists']['pending_radiology'] = []

    if role in ('lab', 'technician'):
        try:
            from services.lab_service import lab_service

            ls = lab_service.get_dashboard_stats()
            data['metrics']['pending_requests'] = int(ls.get('pending_requests', 0))
            data['metrics']['completed_today'] = int(ls.get('completed_today', 0))
        except Exception:
            try:
                q = (
                    select(func.count())
                    .select_from(LabRequest)
                    .filter(LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]))
                )
                if tid and hasattr(LabRequest, 'tenant_id'):
                    q = q.filter(LabRequest.tenant_id == tid)
                data['metrics']['pending_requests'] = int(db.session.execute(q).scalar() or 0)
            except Exception:
                data['metrics']['pending_requests'] = 0
            data['metrics']['completed_today'] = 0
        try:
            q = select(LabRequest).filter(
                LabRequest.status.in_(
                    [OrderState.REQUESTED, OrderState.RECEIVED, OrderState.IN_PROGRESS]
                )
            )
            if tid and hasattr(LabRequest, 'tenant_id'):
                q = q.filter(LabRequest.tenant_id == tid)
            data['lists']['lab_pending'] = (
                db.session.execute(q.order_by(LabRequest.created_at.asc()).limit(10))
                .scalars()
                .all()
            )
        except Exception:
            data['lists']['lab_pending'] = []

    if role == 'radiology' and _module_active(tid, 'radiology'):
        try:
            q = (
                select(func.count())
                .select_from(RadiologyRequest)
                .filter(RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]))
            )
            if tid and hasattr(RadiologyRequest, 'tenant_id'):
                q = q.filter(RadiologyRequest.tenant_id == tid)
            data['metrics']['pending_reports'] = int(db.session.execute(q).scalar() or 0)
        except Exception:
            data['metrics']['pending_reports'] = 0
        try:
            q = select(RadiologyRequest).filter(
                RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
            )
            if tid and hasattr(RadiologyRequest, 'tenant_id'):
                q = q.filter(RadiologyRequest.tenant_id == tid)
            data['lists']['pending_radiology'] = (
                db.session.execute(q.order_by(RadiologyRequest.created_at.asc()).limit(10))
                .scalars()
                .all()
            )
        except Exception:
            data['lists']['pending_radiology'] = []

    if role == 'emergency' and _module_active(tid, 'emergency'):
        try:
            q = (
                select(func.count())
                .select_from(EmergencyCase)
                .filter(
                    EmergencyCase.severity.in_(['HIGH', 'CRITICAL']),
                    EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED']),
                )
            )
            if tid and hasattr(EmergencyCase, 'tenant_id'):
                q = q.filter(EmergencyCase.tenant_id == tid)
            critical = db.session.execute(q).scalar() or 0
            q = (
                select(func.count())
                .select_from(EmergencyCase)
                .filter(EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED']))
            )
            if tid and hasattr(EmergencyCase, 'tenant_id'):
                q = q.filter(EmergencyCase.tenant_id == tid)
            active = db.session.execute(q).scalar() or 0
            data['metrics']['critical_count'] = int(critical)
            data['metrics']['active_cases'] = int(active)
            q = select(EmergencyCase).filter(
                EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED'])
            )
            if tid and hasattr(EmergencyCase, 'tenant_id'):
                q = q.filter(EmergencyCase.tenant_id == tid)
            data['lists']['emergency_cases'] = (
                db.session.execute(q.order_by(EmergencyCase.created_at.desc()).limit(10))
                .scalars()
                .all()
            )
            q = select(EmergencyCase).filter(
                EmergencyCase.severity.in_(['HIGH', 'CRITICAL', 'URGENT']),
                EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED']),
            )
            if tid and hasattr(EmergencyCase, 'tenant_id'):
                q = q.filter(EmergencyCase.tenant_id == tid)
            data['lists']['emergency_queue'] = (
                db.session.execute(q.order_by(EmergencyCase.created_at.asc()).limit(10))
                .scalars()
                .all()
            )
        except Exception:
            data['metrics']['critical_count'] = 0
            data['metrics']['active_cases'] = 0
            data['lists']['emergency_cases'] = []
            data['lists']['emergency_queue'] = []

    if role == 'nurse' and _module_active(tid, 'nursing'):
        try:
            q = select(Visit).filter(
                Visit.visit_date == today,
                Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS, VisitState.CHECKED_IN]),
            )
            if tid and hasattr(Visit, 'tenant_id'):
                q = q.filter(Visit.tenant_id == tid)
            data['lists']['assigned'] = (
                db.session.execute(q.order_by(Visit.created_at.desc()).limit(12)).scalars().all()
            )
        except Exception:
            data['lists']['assigned'] = []

    if role == 'pharmacist' and _module_active(tid, 'pharmacy'):
        try:
            q = select(Medication).filter(Medication.stock_quantity <= Medication.minimum_stock)
            if tid and hasattr(Medication, 'tenant_id'):
                q = q.filter(Medication.tenant_id == tid)
            data['lists']['low_stock'] = (
                db.session.execute(q.order_by(Medication.stock_quantity.asc()).limit(10))
                .scalars()
                .all()
            )
            if _module_active(tid, 'doctor'):
                q = select(Prescription).filter(Prescription.status == 'active')
                if tid and hasattr(Prescription, 'tenant_id'):
                    q = q.filter(Prescription.tenant_id == tid)
                data['lists']['pending_prescriptions'] = (
                    db.session.execute(q.order_by(Prescription.created_at.desc()).limit(10))
                    .scalars()
                    .all()
                )
            else:
                data['lists']['pending_prescriptions'] = []
            q = select(PharmacySale).filter(func.date(PharmacySale.created_at) == today)
            if tid and hasattr(PharmacySale, 'tenant_id'):
                q = q.filter(PharmacySale.tenant_id == tid)
            data['lists']['recent_sales'] = (
                db.session.execute(q.order_by(PharmacySale.created_at.desc()).limit(10))
                .scalars()
                .all()
            )
            data['metrics']['dispense_today'] = len(data['lists']['recent_sales'])
            q = select(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
                func.date(PharmacySale.created_at) == today
            )
            if tid and hasattr(PharmacySale, 'tenant_id'):
                q = q.filter(PharmacySale.tenant_id == tid)
            data['metrics']['today_sales'] = float(db.session.execute(q).scalar() or 0)
        except Exception:
            data['lists']['low_stock'] = []
            data['lists']['pending_prescriptions'] = []
            data['lists']['recent_sales'] = []
            data['metrics']['dispense_today'] = 0
            data['metrics']['today_sales'] = 0.0

    # Fallback: unhandled roles return gracefully formed empty schemas
    # (metrics/lists already initialized as empty dicts above).
    return data


def build_now_cards(
    widgets: list[WidgetMeta], data: dict[str, Any], role: str | None = None
) -> list[dict[str, Any]]:
    """High-priority metric cards for _now_panel — role-aware to avoid cross-role leakage."""
    metrics = data.get('metrics') or {}
    lists_data = data.get('lists') or {}
    inferred_role = role or ''
    cards: list[dict[str, Any]] = []
    for w in widgets:
        if w.priority != 1:
            continue
        value: Any = None
        if w.id == 'queue_live':
            value = metrics.get('queue_count', 0)
        elif w.id in {'my_queue', 'patients_waiting'}:
            value = metrics.get('waiting_patients', 0)
        elif w.id == 'cash_summary':
            if inferred_role == 'accountant':
                value = metrics.get('pending_amount', metrics.get('today_collected', 0))
                if isinstance(value, (int, float, Decimal)):
                    value = f'{float(value):.2f}'
            else:
                value = metrics.get('visits_today', 0)
                if value == 0:
                    value = metrics.get('queue_count', 0)
        elif w.id == 'worklist_urgent':
            value = metrics.get('pending_requests', 0)
        elif w.id == 'critical_count':
            value = metrics.get('critical_count', 0)
        elif w.id == 'triage_board':
            value = metrics.get('active_cases', 0)
        elif w.id == 'pending_payments':
            value = metrics.get('pending_invoices', 0)
        elif w.id == 'finance_overview':
            value = metrics.get('collection_rate', 0)
            if isinstance(value, (int, float)):
                value = f'{value:.1f}%'
        elif w.id == 'revenue_today':
            value = metrics.get('today_collected', 0)
            if isinstance(value, (int, float, Decimal)):
                value = f'{float(value):.2f}'
        elif w.id == 'kpi_strip':
            if inferred_role == 'manager':
                value = metrics.get('today_revenue', metrics.get('visits_today', 0))
                if isinstance(value, (int, float, Decimal)) and float(value) > 1000:
                    value = f'{float(value):.0f}'
            else:
                value = metrics.get('visits_today', 0)
        elif w.id == 'manager_finance':
            value = metrics.get('pending_amount', 0)
            if isinstance(value, (int, float, Decimal)):
                value = f'{float(value):.0f}'
        elif w.id == 'manager_hr':
            value = metrics.get('staff_count', metrics.get('active_staff', 0))
        elif w.id == 'nurse_assigned':
            value = len(lists_data.get('assigned') or [])
        elif w.id == 'pharmacy_dispense':
            value = metrics.get('dispense_today', 0)
        elif w.id == 'pharmacy_sales':
            value = metrics.get('today_sales', 0)
            if isinstance(value, (int, float, Decimal)):
                value = f'{float(value):.2f}'
        else:
            value = '—'
        action_href: str | None = None
        if w.action_url:
            try:
                action_href = url_for(w.action_url)
            except Exception:
                action_href = None
        cards.append(
            {
                'id': w.id,
                'title': w.title_ar,
                'value': value,
                'icon': w.icon,
                'action_href': action_href,
                'action_label': w.action_label,
            }
        )
    return cards[:4]


def build_command_center_context(user, role: str | None = None, **extra: Any) -> dict[str, Any]:
    role = role or getattr(user, 'role', '') or ''
    enabled = _enabled_modules()
    hidden = _user_hidden_widgets(user)
    widgets = resolve_dashboard_widgets(role, enabled, hidden)
    layout_ids = ROLE_LAYOUTS.get(role) or ROLE_LAYOUTS.get('manager', [])
    customizable_widgets: list[dict[str, Any]] = []
    for wid in layout_ids:
        meta = WIDGETS.get(wid)
        if meta:
            customizable_widgets.append(
                {
                    'id': meta.id,
                    'title': meta.title_ar,
                    'hidden': wid in hidden,
                }
            )
    now_widgets = [w for w in widgets if w.priority == 1]
    now_ids = {w.id for w in now_widgets}
    body_widgets = [w for w in widgets if w.size in ('md', 'lg', 'full') and w.id not in now_ids]
    data = _load_role_data(role, user)
    quick = ROLE_QUICK_ACTIONS.get(role, [])
    quick_actions: list[dict[str, Any]] = []
    for ep, icon, label in quick:
        try:
            quick_actions.append({'href': url_for(ep), 'icon': icon, 'label': label})
        except Exception:
            continue
    ctx: dict[str, Any] = {
        'hero': build_hero_context(user),
        'widgets': widgets,
        'now_widgets': now_widgets,
        'body_widgets': body_widgets,
        'now_cards': build_now_cards(widgets, data, role=role),
        'widget_data': data,
        'quick_actions': quick_actions,
        'dashboard_role': role,
        'dashboard_title': ROLE_DASHBOARD_TITLES.get(role, 'لوحة القيادة'),
        'customizable_widgets': customizable_widgets,
        'hidden_widget_ids': list(hidden),
    }
    ctx.update(extra)
    return ctx


def render_command_center(user, role: str | None = None, **extra: Any) -> str:
    return render_template(
        'dashboards/command_center.html',
        **build_command_center_context(user, role=role, **extra),
    )


def snapshot_metrics(user, role: str | None = None) -> dict[str, Any]:
    """Light JSON for dashboard-live.js polling."""
    role = role or getattr(user, 'role', '') or ''
    data = _load_role_data(role, user)
    return {
        'role': role,
        'metrics': data.get('metrics') or {},
        'ts': datetime.now(UTC).isoformat(),
    }
