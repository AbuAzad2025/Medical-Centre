"""Owner platform navigation — separate from tenant NavResolver (G-137)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from flask import url_for


@dataclass(frozen=True)
class OwnerNavItem:
    id: str
    label_ar: str
    icon: str
    endpoint: str
    active_prefix: str = ''


@dataclass
class OwnerNavSection:
    id: str
    title_ar: str
    items: List[OwnerNavItem] = field(default_factory=list)


def resolve_owner_nav() -> List[OwnerNavSection]:
    sections: List[OwnerNavSection] = []

    main = OwnerNavSection(id='main', title_ar='')
    main.items.append(OwnerNavItem(
        id='dashboard',
        label_ar='نظرة عامة',
        icon='fas fa-chart-line',
        endpoint='owner.owner_dashboard',
        active_prefix='/owner/dashboard',
    ))
    sections.append(main)

    clients = OwnerNavSection(id='clients', title_ar='العملاء')
    clients.items.extend([
        OwnerNavItem('provision', 'تزويد عميل', 'fas fa-rocket', 'owner.owner_provision', '/owner/provision'),
        OwnerNavItem('subscriptions', 'الاشتراكات', 'fas fa-file-contract', 'owner.owner_subscriptions', '/owner/subscriptions'),
        OwnerNavItem('packages', 'حزم SaaS', 'fas fa-box-open', 'owner.owner_packages', '/owner/packages'),
        OwnerNavItem('users', 'إدارة المستخدمين', 'fas fa-users-cog', 'owner.owner_users', '/owner/users'),
    ])
    sections.append(clients)

    product = OwnerNavSection(id='product', title_ar='المنتج والتسعير')
    product.items.extend([
        OwnerNavItem('plans', 'خطط الاشتراك', 'fas fa-tags', 'owner.owner_plans', '/owner/plans'),
        OwnerNavItem('bundles', 'باقات المنتج', 'fas fa-cubes', 'owner.owner_bundles', '/owner/bundles'),
        OwnerNavItem('billing', 'الفوترة', 'fas fa-coins', 'owner.owner_billing', '/owner/billing'),
    ])
    sections.append(product)

    platform = OwnerNavSection(id='platform', title_ar='المنصة')
    platform.items.extend([
        OwnerNavItem('branding', 'هوية المنصة', 'fas fa-palette', 'owner.owner_branding', '/owner/branding'),
        OwnerNavItem('themes', 'ثيمات النظام', 'fas fa-paint-brush', 'owner.owner_themes', '/owner/themes'),
        OwnerNavItem('modules', 'الوحدات العالمية', 'fas fa-puzzle-piece', 'owner.owner_modules', '/owner/modules'),
        OwnerNavItem('announcements', 'إعلانات', 'fas fa-bullhorn', 'owner.owner_announcements', '/owner/announcements'),
    ])
    sections.append(platform)

    ops = OwnerNavSection(id='ops', title_ar='التشغيل')
    ops.items.extend([
        OwnerNavItem('tasks', 'المهام والمشاريع', 'fas fa-tasks', 'owner.owner_tasks', '/owner/tasks'),
        OwnerNavItem('support', 'الدعم', 'fas fa-headset', 'owner.owner_support_tickets', '/owner/support-tickets'),
        OwnerNavItem('audit', 'سجل التدقيق', 'fas fa-clipboard-list', 'owner.owner_audit_logs', '/owner/audit-logs'),
        OwnerNavItem('resources', 'استخدام الموارد', 'fas fa-server', 'owner.owner_resource_usage', '/owner/resource-usage'),
        OwnerNavItem('notifications', 'قواعد الإشعار', 'fas fa-bell', 'owner.owner_notifications', '/owner/notifications'),
        OwnerNavItem('webhooks', 'Webhooks', 'fas fa-plug', 'owner.owner_webhooks', '/owner/webhooks'),
        OwnerNavItem('api_keys', 'API Keys', 'fas fa-key', 'owner.owner_api_keys_page', '/owner/api-keys'),
        OwnerNavItem('system_config', 'إعدادات النظام', 'fas fa-cogs', 'owner.owner_system_config', '/owner/system-config'),
    ])
    sections.append(ops)

    monitoring = OwnerNavSection(id='monitoring', title_ar='المراقبة والتحكم')
    monitoring.items.extend([
        OwnerNavItem('monitoring', 'لوحة المراقبة', 'fas fa-heartbeat', 'owner.owner_monitoring', '/owner/monitoring'),
        OwnerNavItem('control', 'مركز التحكم', 'fas fa-sliders-h', 'owner.owner_control', '/owner/control'),
        OwnerNavItem('backups', 'النسخ الاحتياطي', 'fas fa-database', 'owner.owner_backups', '/owner/backups'),
        OwnerNavItem('emergency', 'مفاتيح الطوارئ', 'fas fa-exclamation-triangle', 'owner.owner_emergency_switches', '/owner/emergency-switches'),
    ])
    sections.append(monitoring)

    return sections


def owner_nav_href(item: OwnerNavItem) -> str:
    try:
        return url_for(item.endpoint)
    except Exception:
        return item.active_prefix or '#'
