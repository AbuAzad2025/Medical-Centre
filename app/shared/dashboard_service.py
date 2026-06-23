"""Command Center data + render helper — §29."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from flask import g, render_template, url_for

from app.shared.dashboard_registry import (
    ROLE_QUICK_ACTIONS,
    WidgetMeta,
    resolve_dashboard_widgets,
)


def _enabled_modules() -> set:
    return set(getattr(g, 'enabled_modules', None) or [])


def _user_hidden_widgets(user) -> set:
    prefs = getattr(user, 'preferences', None)
    if isinstance(prefs, dict):
        dash = prefs.get('dashboard') or {}
        return set(dash.get('hidden_widgets') or [])
    if isinstance(prefs, str):
        try:
            import json
            data = json.loads(prefs)
            return set((data.get('dashboard') or {}).get('hidden_widgets') or [])
        except Exception:
            pass
    return set()


def build_hero_context(user) -> dict:
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


def _load_role_data(role: str, user) -> dict[str, Any]:
    from app_factory import db
    from app.shared.enums import (
        AppointmentState,
        OrderState,
        QueueState,
        VisitState,
    )
    from models.appointment import Appointment
    from models.lab_request import LabRequest
    from models.queue_management import QueueManagement
    from models.radiology_request import RadiologyRequest
    from models.visit import Visit
    from services.core_queries import core_queries

    today = date.today()
    data: dict[str, Any] = {'metrics': {}, 'lists': {}}

    if role in ('reception', 'manager'):
        stats = core_queries.get_basic_dashboard_stats()
        waiting = QueueManagement.query.filter(
            QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED])
        ).count()
        data['metrics']['queue_count'] = waiting
        data['metrics']['visits_today'] = stats.get('visits_today', 0)
        data['metrics']['total_patients'] = stats.get('total_patients', 0)
        data['lists']['active_queue'] = QueueManagement.query.filter(
            QueueManagement.status.in_([QueueState.WAITING, QueueState.CALLED, QueueState.IN_PROGRESS])
        ).order_by(QueueManagement.queued_at.asc()).limit(10).all()
        data['lists']['today_visits'] = Visit.query.filter(
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS, VisitState.COMPLETED]),
        ).order_by(Visit.created_at.desc()).limit(15).all()
        data['lists']['today_appointments'] = Appointment.query.filter(
            db.func.date(Appointment.starts_at) == today,
            Appointment.status.in_([
                AppointmentState.SCHEDULED,
                AppointmentState.CONFIRMED,
                AppointmentState.CHECKED_IN,
            ]),
        ).order_by(Appointment.starts_at.asc()).limit(10).all()

    if role == 'doctor':
        pending = Visit.query.filter(
            Visit.doctor_id == user.id,
            Visit.status == VisitState.OPEN,
        ).count()
        data['metrics']['waiting_patients'] = pending
        data['metrics']['today_visits'] = Visit.query.filter(
            Visit.doctor_id == user.id,
            Visit.visit_date == today,
        ).count()
        data['lists']['waiting_list'] = Visit.query.filter(
            Visit.doctor_id == user.id,
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.CHECKED_IN, VisitState.IN_PROGRESS]),
        ).order_by(Visit.created_at.asc()).limit(8).all()
        data['lists']['today_appointments'] = Appointment.query.filter(
            Appointment.doctor_id == user.id,
            db.func.date(Appointment.starts_at) == today,
        ).order_by(Appointment.starts_at.asc()).limit(8).all()
        data['lists']['pending_lab'] = LabRequest.query.join(Visit).filter(
            Visit.doctor_id == user.id,
            LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
        ).order_by(LabRequest.created_at.desc()).limit(6).all()
        data['lists']['pending_radiology'] = RadiologyRequest.query.join(Visit).filter(
            Visit.doctor_id == user.id,
            RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS]),
        ).order_by(RadiologyRequest.created_at.desc()).limit(6).all()

    if role in ('lab', 'technician'):
        try:
            from services.lab_service import lab_service
            ls = lab_service.get_dashboard_stats()
            data['metrics']['pending_requests'] = ls.get('pending_requests', 0)
            data['metrics']['completed_today'] = ls.get('completed_today', 0)
        except Exception:
            data['metrics']['pending_requests'] = LabRequest.query.filter(
                LabRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
            ).count()
        data['lists']['lab_pending'] = LabRequest.query.filter(
            LabRequest.status.in_([OrderState.REQUESTED, OrderState.RECEIVED, OrderState.IN_PROGRESS])
        ).order_by(LabRequest.created_at.asc()).limit(10).all()

    if role == 'radiology':
        data['metrics']['pending_reports'] = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
        ).count()
        data['lists']['pending_radiology'] = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
        ).order_by(RadiologyRequest.created_at.asc()).limit(10).all()

    if role == 'emergency':
        try:
            from models.emergency import EmergencyCase
            critical = EmergencyCase.query.filter(
                EmergencyCase.severity.in_(['HIGH', 'CRITICAL']),
                EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED']),
            ).count()
            active = EmergencyCase.query.filter(
                EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED'])
            ).count()
            data['metrics']['critical_count'] = critical
            data['metrics']['active_cases'] = active
            data['lists']['emergency_cases'] = EmergencyCase.query.filter(
                EmergencyCase.status.notin_(['COMPLETED', 'CANCELLED'])
            ).order_by(EmergencyCase.created_at.desc()).limit(10).all()
        except Exception:
            data['metrics']['critical_count'] = 0
            data['metrics']['active_cases'] = 0
            data['lists']['emergency_cases'] = []

    if role == 'accountant':
        try:
            from models.invoice import Invoice
            pending = Invoice.query.filter(Invoice.status.in_(['ISSUED', 'DRAFT'])).count()
            data['metrics']['pending_invoices'] = pending
        except Exception:
            data['metrics']['pending_invoices'] = 0

    if role == 'nurse':
        data['lists']['assigned'] = Visit.query.filter(
            Visit.visit_date == today,
            Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS, VisitState.CHECKED_IN]),
        ).order_by(Visit.created_at.desc()).limit(12).all()

    if role == 'pharmacist':
        data['metrics']['dispense_today'] = 0

    return data


def build_now_cards(widgets: List[WidgetMeta], data: dict) -> list[dict]:
    """High-priority metric cards for _now_panel."""
    metrics = data.get('metrics') or {}
    cards = []
    for w in widgets:
        if w.priority != 1:
            continue
        value = None
        if w.id == 'queue_live':
            value = metrics.get('queue_count', 0)
        elif w.id == 'my_queue':
            value = metrics.get('waiting_patients', 0)
        elif w.id == 'patients_waiting':
            value = metrics.get('waiting_patients', 0)
        elif w.id == 'cash_summary':
            value = metrics.get('visits_today', '—')
        elif w.id == 'worklist_urgent':
            value = metrics.get('pending_requests', 0)
        elif w.id == 'critical_count':
            value = metrics.get('critical_count', 0)
        elif w.id == 'triage_board':
            value = metrics.get('active_cases', 0)
        elif w.id == 'pending_payments':
            value = metrics.get('pending_invoices', 0)
        elif w.id == 'kpi_strip':
            value = metrics.get('visits_today', 0)
        elif w.id == 'nurse_assigned':
            value = len(data.get('lists', {}).get('assigned') or [])
        elif w.id == 'pharmacy_dispense':
            value = metrics.get('dispense_today', 0)
        else:
            value = '—'
        action_href = None
        if w.action_url:
            try:
                action_href = url_for(w.action_url)
            except Exception:
                action_href = None
        cards.append({
            'id': w.id,
            'title': w.title_ar,
            'value': value,
            'icon': w.icon,
            'action_href': action_href,
            'action_label': w.action_label,
        })
    return cards[:4]


def build_command_center_context(user, role: Optional[str] = None, **extra) -> dict:
    role = role or user.role
    enabled = _enabled_modules()
    hidden = _user_hidden_widgets(user)
    widgets = resolve_dashboard_widgets(role, enabled, hidden)
    now_widgets = [w for w in widgets if w.priority == 1]
    body_widgets = [w for w in widgets if w.size in ('md', 'lg', 'full')]
    data = _load_role_data(role, user)
    quick = ROLE_QUICK_ACTIONS.get(role, [])
    quick_actions = []
    for ep, icon, label in quick:
        try:
            quick_actions.append({'href': url_for(ep), 'icon': icon, 'label': label})
        except Exception:
            continue
    ctx = {
        'hero': build_hero_context(user),
        'widgets': widgets,
        'now_widgets': now_widgets,
        'body_widgets': body_widgets,
        'now_cards': build_now_cards(widgets, data),
        'widget_data': data,
        'quick_actions': quick_actions,
        'dashboard_role': role,
    }
    ctx.update(extra)
    return ctx


def render_command_center(user, role: Optional[str] = None, **extra):
    return render_template(
        'dashboards/command_center.html',
        **build_command_center_context(user, role=role, **extra),
    )


def snapshot_metrics(user, role: Optional[str] = None) -> dict:
    """Light JSON for dashboard-live.js polling."""
    role = role or user.role
    data = _load_role_data(role, user)
    return {
        'role': role,
        'metrics': data.get('metrics') or {},
        'ts': datetime.now(timezone.utc).isoformat(),
    }
