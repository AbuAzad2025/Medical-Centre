"""Command Center widget registry — §29.3."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class WidgetMeta:
    id: str
    title_ar: str
    roles: Tuple[str, ...]
    modules: Tuple[str, ...]
    size: str  # sm | md | lg | full
    priority: int  # 1 = now panel
    template: str
    data_endpoint: Optional[str] = None
    icon: str = 'fa-chart-line'
    action_url: Optional[str] = None
    action_label: Optional[str] = None


WIDGETS: dict[str, WidgetMeta] = {
    'queue_live': WidgetMeta(
        id='queue_live', title_ar='الطابور الآن', roles=('reception', 'manager'),
        modules=('reception',), size='md', priority=1,
        template='dashboards/widgets/_queue_live.html',
        data_endpoint='/api/dashboard/snapshot', icon='fa-list-ol',
        action_url='reception.queue_management', action_label='افتح الطابور',
    ),
    'visits_today': WidgetMeta(
        id='visits_today', title_ar='زيارات اليوم', roles=('reception', 'manager'),
        modules=('reception',), size='lg', priority=2,
        template='dashboards/widgets/_visits_today.html', icon='fa-calendar-check',
    ),
    'appointments_pending': WidgetMeta(
        id='appointments_pending', title_ar='مواعيد اليوم', roles=('reception', 'doctor', 'manager'),
        modules=('appointments',), size='md', priority=2,
        template='dashboards/widgets/_appointments_today.html', icon='fa-calendar',
        action_url='reception.appointments', action_label='المواعيد',
    ),
    'cash_summary': WidgetMeta(
        id='cash_summary', title_ar='ملخص الصندوق', roles=('reception', 'accountant'),
        modules=('billing',), size='sm', priority=1,
        template='dashboards/widgets/_cash_summary.html', icon='fa-cash-register',
        action_url='reception.cash_register', action_label='الصندوق',
    ),
    'my_queue': WidgetMeta(
        id='my_queue', title_ar='طابوري', roles=('doctor',),
        modules=('doctor',), size='md', priority=1,
        template='dashboards/widgets/_my_queue.html',
        data_endpoint='/api/dashboard/snapshot', icon='fa-stethoscope',
        action_url='doctor.patient_queue', action_label='ابدأ الكشف',
    ),
    'patients_waiting': WidgetMeta(
        id='patients_waiting', title_ar='مرضى بالانتظار', roles=('doctor',),
        modules=('doctor',), size='sm', priority=1,
        template='dashboards/widgets/_patients_waiting.html', icon='fa-user-clock',
    ),
    'lab_pending': WidgetMeta(
        id='lab_pending', title_ar='طلبات المختبر', roles=('doctor', 'lab'),
        modules=('lab',), size='md', priority=2,
        template='dashboards/widgets/_lab_pending.html', icon='fa-flask',
        action_url='lab.worklist', action_label='قائمة العمل',
    ),
    'radiology_pending': WidgetMeta(
        id='radiology_pending', title_ar='طلبات الأشعة', roles=('doctor', 'radiology'),
        modules=('radiology',), size='md', priority=2,
        template='dashboards/widgets/_radiology_pending.html', icon='fa-x-ray',
    ),
    'worklist_urgent': WidgetMeta(
        id='worklist_urgent', title_ar='عاجل — مختبر', roles=('lab',),
        modules=('lab',), size='md', priority=1,
        template='dashboards/widgets/_lab_worklist.html', icon='fa-vial',
        action_url='lab.worklist', action_label='قائمة العمل',
    ),
    'triage_board': WidgetMeta(
        id='triage_board', title_ar='الحالات النشطة', roles=('emergency',),
        modules=('emergency',), size='lg', priority=1,
        template='dashboards/widgets/_triage_board.html', icon='fa-ambulance',
        action_url='emergency.queue', action_label='حالات الطوارئ',
    ),
    'critical_count': WidgetMeta(
        id='critical_count', title_ar='حالات حرجة', roles=('emergency',),
        modules=('emergency',), size='sm', priority=1,
        template='dashboards/widgets/_critical_count.html', icon='fa-heart-pulse',
    ),
    'pending_payments': WidgetMeta(
        id='pending_payments', title_ar='مدفوعات معلقة', roles=('accountant',),
        modules=('billing',), size='md', priority=1,
        template='dashboards/widgets/_pending_payments.html', icon='fa-file-invoice-dollar',
    ),
    'kpi_strip': WidgetMeta(
        id='kpi_strip', title_ar='مؤشرات اليوم', roles=('manager',),
        modules=(), size='full', priority=1,
        template='dashboards/widgets/_kpi_strip.html', icon='fa-chart-bar',
        action_url='manager.monitoring', action_label='المراقبة',
    ),
    'nurse_assigned': WidgetMeta(
        id='nurse_assigned', title_ar='مرضاي', roles=('nurse',),
        modules=(), size='lg', priority=1,
        template='dashboards/widgets/_nurse_assigned.html', icon='fa-user-nurse',
    ),
    'pharmacy_dispense': WidgetMeta(
        id='pharmacy_dispense', title_ar='صرف اليوم', roles=('pharmacist',),
        modules=(), size='md', priority=1,
        template='dashboards/widgets/_pharmacy_dispense.html', icon='fa-pills',
        action_url='medication.pos', action_label='نقطة البيع',
    ),
    'pharmacy_low_stock': WidgetMeta(
        id='pharmacy_low_stock', title_ar='أدوية منخفضة المخزون', roles=('pharmacist',),
        modules=(), size='md', priority=2,
        template='dashboards/widgets/_pharmacy_low_stock.html', icon='fa-exclamation-triangle',
        action_url='medication.stock_alerts', action_label='عرض الكل',
    ),
    'pharmacy_prescriptions': WidgetMeta(
        id='pharmacy_prescriptions', title_ar='روشتات في الانتظار', roles=('pharmacist',),
        modules=(), size='md', priority=2,
        template='dashboards/widgets/_pharmacy_prescriptions.html', icon='fa-prescription',
    ),
    'pharmacy_sales': WidgetMeta(
        id='pharmacy_sales', title_ar='مبيعات اليوم', roles=('pharmacist',),
        modules=(), size='md', priority=2,
        template='dashboards/widgets/_pharmacy_sales.html', icon='fa-shopping-cart',
        action_url='medication.pos', action_label='نقطة البيع',
    ),
    'lab_recent': WidgetMeta(
        id='lab_recent', title_ar='آخر طلبات المختبر', roles=('lab', 'technician'),
        modules=('lab',), size='lg', priority=2,
        template='dashboards/widgets/_lab_recent.html', icon='fa-vial',
        action_url='lab.worklist', action_label='قائمة العمل',
    ),
    'emergency_waitlist': WidgetMeta(
        id='emergency_waitlist', title_ar='قائمة الانتظار', roles=('emergency',),
        modules=('emergency',), size='lg', priority=2,
        template='dashboards/widgets/_emergency_waitlist.html', icon='fa-list',
        action_url='emergency.queue', action_label='حالات الطوارئ',
    ),
}

ROLE_DASHBOARD_TITLES: dict[str, str] = {
    'reception': 'لوحة تحكم الاستقبال',
    'doctor': 'لوحة تحكم الأطباء',
    'lab': 'قسم المختبر',
    'radiology': 'قسم الأشعة',
    'pharmacist': 'لوحة تحكم الصيدلية',
    'emergency': 'لوحة تحكم الطوارئ',
    'accountant': 'لوحة تحكم الفوترة',
    'manager': 'لوحة القيادة',
    'nurse': 'لوحة القيادة',
}

ROLE_LAYOUTS: dict[str, list[str]] = {
    'reception': ['queue_live', 'cash_summary', 'visits_today', 'appointments_pending'],
    'doctor': ['my_queue', 'appointments_pending', 'lab_pending', 'radiology_pending'],
    'lab': ['lab_recent', 'lab_pending'],
    'radiology': ['radiology_pending'],
    'nurse': ['nurse_assigned'],
    'accountant': ['pending_payments', 'cash_summary'],
    'manager': ['kpi_strip', 'queue_live', 'visits_today'],
    'emergency': ['critical_count', 'triage_board', 'emergency_waitlist'],
    'pharmacist': ['pharmacy_low_stock', 'pharmacy_prescriptions', 'pharmacy_sales'],
    'technician': ['worklist_urgent', 'lab_pending'],
}

ROLE_QUICK_ACTIONS: dict[str, list[tuple[str, str, str]]] = {
    'reception': [
        ('reception.create_visit', 'fa-plus', 'زيارة جديدة'),
        ('reception.queue_management', 'fa-list-ol', 'الطابور'),
        ('reception.appointments', 'fa-calendar', 'المواعيد'),
        ('reception.cash_register', 'fa-cash-register', 'الصندوق'),
        ('reception.patients', 'fa-users', 'المرضى'),
        ('inbox.dashboard', 'fa-inbox', 'صندوق العمل'),
    ],
    'doctor': [
        ('doctor.patient_queue', 'fa-list-ol', 'طابور المرضى'),
        ('doctor.prescriptions', 'fa-prescription', 'الروشتات'),
        ('doctor.lab_requests', 'fa-flask', 'المختبر'),
        ('doctor.radiology_requests', 'fa-x-ray', 'الأشعة'),
        ('inbox.dashboard', 'fa-inbox', 'صندوق العمل'),
    ],
    'lab': [
        ('lab.worklist', 'fa-vial', 'قائمة العمل'),
        ('lab.lab_requests', 'fa-flask', 'الطلبات'),
    ],
    'emergency': [
        ('emergency.queue', 'fa-ambulance', 'الحالات'),
        ('emergency.triage', 'fa-heart-pulse', 'الفرز'),
    ],
    'pharmacist': [
        ('medication.pos', 'fa-cash-register', 'نقطة البيع'),
        ('medication.prescriptions', 'fa-prescription', 'الروشتات'),
        ('inbox.dashboard', 'fa-inbox', 'صندوق العمل'),
    ],
    'accountant': [
        ('finance.invoices', 'fa-file-invoice-dollar', 'الفواتير'),
        ('finance.payments', 'fa-money-bill-wave', 'المدفوعات'),
        ('inbox.dashboard', 'fa-inbox', 'صندوق العمل'),
    ],
    'manager': [
        ('manager.analytics', 'fa-chart-line', 'المراقبة'),
        ('manager.reports_center', 'fa-chart-bar', 'التقارير'),
    ],
}


def resolve_dashboard_widgets(role: str, enabled_modules: set, hidden: Optional[set] = None) -> list[WidgetMeta]:
    """Widgets for role filtered by tenant modules and user hidden list."""
    hidden = hidden or set()
    layout = ROLE_LAYOUTS.get(role) or ROLE_LAYOUTS.get('manager', [])
    out: list[WidgetMeta] = []
    for wid in layout:
        if wid in hidden:
            continue
        meta = WIDGETS.get(wid)
        if not meta:
            continue
        if role not in meta.roles and role != 'manager':
            continue
        if meta.modules and not all(m in enabled_modules for m in meta.modules):
            # Staff role dashboards: layout is authoritative (role already gates access).
            if role == 'manager' or wid not in layout:
                continue
        out.append(meta)
    return out
