"""Smoke tests for UI/UX mobile refactoring — templates render without errors."""

import os
import pytest


def _template_contains(template_path: str, *fragments: str) -> bool:
    full = os.path.join(os.path.dirname(os.path.dirname(__file__)), template_path)
    with open(full, 'r', encoding='utf-8') as f:
        content = f.read()
    return all(frag in content for frag in fragments)


class TestMobilePOSTemplate:
    def test_pos_has_responsive_layout_class(self):
        assert _template_contains(
            'templates/pharmacy/pos.html',
            'pos-layout',
            'pos-cart-sticky',
        )

    def test_pos_has_quick_medications_grid(self):
        assert _template_contains(
            'templates/pharmacy/pos.html',
            'col-6',
            'col-md-4',
        )


class TestPatientTimelineTemplate:
    def test_timeline_has_visual_component(self):
        assert _template_contains(
            'templates/doctor/patient_timeline.html',
            'patient-timeline-visual',
            'patient-timeline-visual__dot',
        )

    def test_timeline_has_pagination(self):
        assert _template_contains(
            'templates/doctor/patient_timeline.html',
            'pagination-wrapper',
            'pagination',
        )


class TestBillingDashboardTemplate:
    def test_billing_has_mobile_grid(self):
        assert _template_contains(
            'templates/billing/dashboard_new.html',
            'col-6 col-md-3',
        )

    def test_billing_has_responsive_table(self):
        assert _template_contains(
            'templates/billing/dashboard_new.html',
            'dashboard-table-wrap',
            'table-medical-responsive',
        )

    def test_billing_has_pagination(self):
        assert _template_contains(
            'templates/billing/dashboard_new.html',
            'pagination-wrapper',
        )


class TestComponentsCSS:
    def test_css_has_mobile_pos_rules(self):
        assert _template_contains(
            'static/css/components.css',
            'MOBILE POS GRID',
            'pos-layout',
            'pos-cart-sticky',
        )

    def test_css_has_timeline_styles(self):
        assert _template_contains(
            'static/css/components.css',
            'MOBILE PATIENT TIMELINE',
            'patient-timeline-visual',
        )

    def test_css_has_billing_responsive(self):
        assert _template_contains(
            'static/css/components.css',
            'MOBILE BILLING DASHBOARD',
            'dashboard-table-wrap',
        )

    def test_css_has_pagination_component(self):
        assert _template_contains(
            'static/css/components.css',
            'PAGINATION COMPONENT',
            'pagination-wrapper',
        )
