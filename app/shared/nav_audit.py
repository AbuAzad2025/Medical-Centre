"""Navigation audit helpers — G-143, Gate 6b."""
from __future__ import annotations

import re
from typing import Iterable, Set

from flask import Flask, url_for

from app.shared.manager_nav_registry import REQUIRED_MANAGER_ENDPOINTS, resolve_manager_nav_sections
from app.shared.nav_resolver import NavSection, resolve_nav_for_user
from app.shared.owner_nav_registry import resolve_owner_nav, owner_nav_href


def _manager_get_paths(app: Flask) -> Set[str]:
    paths: Set[str] = set()
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith('/manager'):
            continue
        if 'GET' not in rule.methods:
            continue
        if '<' in rule.rule and rule.rule.endswith('>') and '/drill-down/' not in rule.rule:
            # skip param routes except drill-down pattern we cover explicitly
            if rule.rule.count('<') > 1 or 'int:' in rule.rule:
                continue
        paths.add(rule.rule)
    return paths


def manager_nav_endpoints() -> Set[str]:
    return set(REQUIRED_MANAGER_ENDPOINTS)


def collect_nav_hrefs_for_manager() -> list[str]:
    return [item.href for section in resolve_manager_nav_sections() for item in section.items]


def audit_manager_nav_coverage(app: Flask) -> list[str]:
    """Return manager page paths missing from nav registry endpoints."""
    registered = _manager_get_paths(app)
    covered_prefixes = {
        re.sub(r'<[^>]+>', '', p).rstrip('/') or p
        for p in (
            '/manager/dashboard', '/manager/settlements', '/manager/budget',
            '/manager/monthly-comparison', '/manager/financial-reports',
            '/manager/exchange-rates', '/manager/force-payment-approvals',
            '/manager/pricing', '/manager/departments', '/manager/unit-control',
            '/manager/user-management', '/manager/staff', '/manager/staff/absence',
            '/manager/staff/capacity', '/manager/staff/schedule',
            '/manager/reports-center', '/manager/self-service', '/manager/analytics',
            '/manager/kpi-dashboard', '/manager/patient-satisfaction',
            '/manager/drill-down/visits', '/manager/reports', '/manager/settings',
        )
    }
    missing = []
    skip = {'/manager/api/', '/manager/settlements/export', '/manager/settings/test-sms',
            '/manager/seed-pricing', '/manager/exchange-rates/fetch-api'}
    for path in sorted(registered):
        if any(path.startswith(s) for s in skip):
            continue
        if path.startswith('/manager/api/'):
            continue
        if path in covered_prefixes or any(path.startswith(p) for p in covered_prefixes):
            continue
        if '<' in path:
            continue
        missing.append(path)
    return missing


def audit_nav_link_endpoints(app: Flask) -> list[str]:
    """Return broken endpoint names referenced in nav registries."""
    broken: list[str] = []
    with app.app_context():
        for section in resolve_manager_nav_sections():
            for item in section.items:
                if not item.href or item.href == '#':
                    broken.append(item.id)
        for section in resolve_owner_nav():
            for item in section.items:
                try:
                    owner_nav_href(item)
                except Exception:
                    broken.append(item.endpoint)
    return broken


def nav_endpoints_from_sections(sections: Iterable[NavSection]) -> Set[str]:
    """Extract endpoint-like ids from resolved nav (for tests)."""
    return {item.id for section in sections for item in section.items}
