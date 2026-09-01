"""Mobile bottom navigation items by role — §25.3."""

from __future__ import annotations

from flask import request, url_for

_ROLE_MOBILE_NAV = {
    'reception': [
        ('reception.dashboard', 'fa-home', 'الرئيسية'),
        ('reception.queue_management', 'fa-list-ol', 'الطابور'),
        ('reception.patients', 'fa-users', 'المرضى'),
        ('reception.appointments', 'fa-calendar', 'مواعيد'),
    ],
    'doctor': [
        ('doctor.dashboard', 'fa-home', 'الرئيسية'),
        ('doctor.patient_queue', 'fa-list-ol', 'الطابور'),
        ('doctor.prescriptions', 'fa-prescription', 'الوصفات'),
        ('reception.patients', 'fa-users', 'المرضى'),
    ],
    'pharmacist': [
        ('medication.dashboard', 'fa-home', 'الرئيسية'),
        ('medication.pos', 'fa-cash-register', 'البيع'),
        ('medication.stock_alerts', 'fa-exclamation-triangle', 'المخزون'),
        ('medication.prescriptions', 'fa-pills', 'روشتات'),
    ],
    'lab': [
        ('lab.dashboard', 'fa-home', 'الرئيسية'),
        ('lab.worklist', 'fa-vial', 'العمل'),
        ('lab.reports', 'fa-file-medical', 'التقارير'),
    ],
    'emergency': [
        ('emergency.dashboard', 'fa-home', 'الرئيسية'),
        ('emergency.queue', 'fa-ambulance', 'الحالات'),
        ('emergency.triage', 'fa-heart-pulse', 'الفرز'),
    ],
    'manager': [
        ('manager.dashboard', 'fa-home', 'الرئيسية'),
        ('manager.analytics', 'fa-chart-line', 'المراقبة'),
        ('reception.queue_management', 'fa-list-ol', 'الطابور'),
        ('reception.appointments', 'fa-calendar', 'مواعيد'),
    ],
    'admin': [
        ('manager.dashboard', 'fa-home', 'الرئيسية'),
        ('manager.analytics', 'fa-chart-line', 'المراقبة'),
        ('reception.queue_management', 'fa-list-ol', 'الطابور'),
        ('reception.appointments', 'fa-calendar', 'مواعيد'),
    ],
    'super_admin': [
        ('manager.dashboard', 'fa-home', 'الرئيسية'),
        ('manager.analytics', 'fa-chart-line', 'المراقبة'),
        ('reception.queue_management', 'fa-list-ol', 'الطابور'),
        ('reception.appointments', 'fa-calendar', 'مواعيد'),
    ],
    'nurse': [
        ('nurse.dashboard', 'fa-home', 'الرئيسية'),
        ('nurse.vitals', 'fa-heartbeat', 'العلامات'),
        ('nurse.tasks', 'fa-tasks', 'المهام'),
    ],
    'radiology': [
        ('radiology.dashboard', 'fa-home', 'الرئيسية'),
        ('radiology.worklist', 'fa-x-ray', 'العمل'),
        ('radiology.requests', 'fa-file-medical', 'الطلبات'),
    ],
    'technician': [
        ('lab.dashboard', 'fa-home', 'الرئيسية'),
        ('lab.worklist', 'fa-vial', 'العمل'),
        ('lab.reports', 'fa-file-medical', 'التقارير'),
    ],
    'owner': [
        ('owner.dashboard', 'fa-crown', 'لوحة المالك'),
        ('super_admin.dashboard', 'fa-cogs', 'الإدارة'),
    ],
    'patient': [
        ('portal.dashboard', 'fa-home', 'الرئيسية'),
        ('portal.appointments', 'fa-calendar', 'مواعيد'),
        ('portal.visits', 'fa-list', 'الزيارات'),
    ],
}


def resolve_mobile_nav_items(user) -> list[dict]:
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    role = getattr(user, 'role', None) or ''
    items = []
    for ep, icon, label in _ROLE_MOBILE_NAV.get(role, [('main.dashboard', 'fa-home', 'الرئيسية')]):
        try:
            href = url_for(ep)
            active = request.endpoint == ep
            if not active and request.endpoint:
                active = request.endpoint.startswith(ep.split('.')[0] + '.') and ep.split('.')[
                    -1
                ] in (request.endpoint or '')
            items.append(
                {'href': href, 'icon': icon, 'label': label, 'active': active, 'endpoint': ep}
            )
        except Exception:
            continue
    return items[:4]
