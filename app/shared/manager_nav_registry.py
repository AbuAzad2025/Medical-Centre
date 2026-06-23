"""Manager navigation registry — Gate 6b (G-142)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from flask import url_for

from app.shared.nav_resolver import NavItem, NavSection, _tenant_path


@dataclass(frozen=True)
class _MgrSpec:
    id: str
    label_ar: str
    icon: str
    endpoint: str
    path_prefix: str
    url_kwargs: Optional[dict[str, Any]] = None


@dataclass
class _MgrSectionSpec:
    id: str
    title_ar: str
    items: List[_MgrSpec] = field(default_factory=list)


_MANAGER_SECTIONS: List[_MgrSectionSpec] = [
    _MgrSectionSpec(
        id='manager_finance',
        title_ar='مالية',
        items=[
            _MgrSpec('settlements', 'التسويات', 'fas fa-balance-scale', 'manager.settlements', '/manager/settlements'),
            _MgrSpec('budget', 'الميزانية', 'fas fa-wallet', 'manager.budget_dashboard', '/manager/budget'),
            _MgrSpec('monthly_comparison', 'مقارنة شهرية', 'fas fa-chart-bar', 'manager.monthly_comparison', '/manager/monthly-comparison'),
            _MgrSpec('financial_reports', 'تقارير مالية', 'fas fa-file-invoice-dollar', 'manager.financial_reports', '/manager/financial-reports'),
            _MgrSpec('exchange_rates', 'أسعار الصرف', 'fas fa-exchange-alt', 'manager.exchange_rates', '/manager/exchange-rates'),
            _MgrSpec('force_payment', 'اعتماد الدفع الإجباري', 'fas fa-gavel', 'manager.force_payment_approvals', '/manager/force-payment-approvals'),
            _MgrSpec('pricing', 'تسعير الخدمات', 'fas fa-tags', 'manager.pricing', '/manager/pricing'),
        ],
    ),
    _MgrSectionSpec(
        id='manager_hr',
        title_ar='موارد بشرية',
        items=[
            _MgrSpec('departments', 'الأقسام', 'fas fa-sitemap', 'manager.departments', '/manager/departments'),
            _MgrSpec('unit_control', 'التحكم بالوحدات', 'fas fa-th-large', 'manager.unit_control', '/manager/unit-control'),
            _MgrSpec('user_management', 'إدارة المستخدمين', 'fas fa-users-cog', 'manager.user_management', '/manager/user-management'),
            _MgrSpec('staff', 'الموظفون', 'fas fa-id-badge', 'manager.staff', '/manager/staff'),
            _MgrSpec('staff_absence', 'الغياب', 'fas fa-user-clock', 'manager.staff_absence', '/manager/staff/absence'),
            _MgrSpec('staff_capacity', 'القدرة الاستيعابية', 'fas fa-chart-pie', 'manager.staff_capacity', '/manager/staff/capacity'),
            _MgrSpec('staff_schedule', 'جداول العمل', 'fas fa-calendar-alt', 'manager.staff_schedule', '/manager/staff/schedule'),
        ],
    ),
    _MgrSectionSpec(
        id='manager_reports',
        title_ar='تقارير',
        items=[
            _MgrSpec('dashboard', 'لوحة المدير', 'fas fa-tachometer-alt', 'manager.dashboard', '/manager/dashboard'),
            _MgrSpec('reports_center', 'مركز التقارير', 'fas fa-chart-bar', 'manager.reports_center', '/manager/reports-center'),
            _MgrSpec('self_service', 'تقارير ذاتية', 'fas fa-file-alt', 'manager.self_service', '/manager/self-service'),
            _MgrSpec('analytics', 'التحليلات', 'fas fa-chart-line', 'manager.analytics', '/manager/analytics'),
            _MgrSpec('kpi', 'مؤشرات الأداء', 'fas fa-bullseye', 'manager.kpi_dashboard', '/manager/kpi-dashboard'),
            _MgrSpec('satisfaction', 'رضا المرضى', 'fas fa-smile', 'manager.patient_satisfaction_dashboard', '/manager/patient-satisfaction'),
            _MgrSpec('drill_down', 'تفاصيل الزيارات', 'fas fa-search-plus', 'manager.drill_down', '/manager/drill-down/visits', {'report_type': 'visits'}),
            _MgrSpec('reports', 'التقارير', 'fas fa-folder-open', 'manager.reports', '/manager/reports'),
            _MgrSpec('settings', 'إعدادات المركز', 'fas fa-cog', 'manager.manager_settings', '/manager/settings'),
        ],
    ),
]

# §15.4 / §37.6 — endpoints that must appear in manager nav
REQUIRED_MANAGER_ENDPOINTS = tuple(
    spec.endpoint for section in _MANAGER_SECTIONS for spec in section.items
)


def resolve_manager_nav_sections() -> List[NavSection]:
    sections: List[NavSection] = []
    for block in _MANAGER_SECTIONS:
        section = NavSection(id=block.id, title_ar=block.title_ar)
        for spec in block.items:
            kwargs = dict(spec.url_kwargs or {})
            href = _tenant_path(spec.path_prefix)
            try:
                href = _tenant_path(url_for(spec.endpoint, **kwargs))
            except Exception:
                pass
            section.items.append(NavItem(
                id=spec.id,
                label_ar=spec.label_ar,
                icon=spec.icon,
                href=href,
                active_prefix=_tenant_path(spec.path_prefix),
                module='reporting',
            ))
        if section.items:
            sections.append(section)
    return sections
