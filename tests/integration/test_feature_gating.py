"""Integration tests for blueprint-level module gating (403 enforcement).

Validates that the before_request guards in lab, radiology, nurse, and
medication blueprints correctly block requests when the tenant has the
module deactivated in TenantModule, and allow through when active.
"""

import pytest

from app.core.module.models import TenantModule
from app.extensions import db


# (module_name_in_TenantModule, route_prefix)
BLUEPRINT_ROUTES = [
    ("lab", "/lab/"),
    ("radiology", "/radiology/"),
    ("nursing", "/nurse/"),
    ("pharmacy", "/medication/"),
    ("reception", "/reception/"),
    ("doctor", "/doctor/"),
    ("emergency", "/emergency/"),
    ("billing", "/accountant/"),
]

LOGIN_ROLE = {
    "lab": "lab",
    "radiology": "radiology",
    "nursing": "nurse",
    "pharmacy": "pharmacist",
    "reception": "reception",
    "doctor": "doctor",
    "emergency": "emergency",
    "billing": "accountant",
}


class TestBlueprintModuleGuards:
    @pytest.mark.parametrize("module_name,route", BLUEPRINT_ROUTES)
    def test_module_disabled_returns_403(self, app, client, test_tenant, login_as, module_name, route):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, f"{module_name}_403_user", LOGIN_ROLE[module_name])

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name=module_name
        ).first()
        assert tm is not None, f"No TenantModule row for '{module_name}'"
        tm.is_active = False
        db.session.commit()

        resp = client.get(route)
        assert resp.status_code == 403, (
            f"Expected 403 for {module_name} (disabled), got {resp.status_code}"
        )

    @pytest.mark.parametrize("module_name,route", BLUEPRINT_ROUTES)
    def test_module_enabled_passes_guard(self, app, client, test_tenant, login_as, module_name, route):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, f"{module_name}_ok_user", LOGIN_ROLE[module_name])

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name=module_name
        ).first()
        assert tm is not None, f"No TenantModule row for '{module_name}'"
        tm.is_active = True
        db.session.commit()

        resp = client.get(route)
        assert resp.status_code != 403, (
            f"Expected non-403 for {module_name} (enabled), got {resp.status_code}"
        )

    def test_lab_disabled_blocks_subroute_too(self, app, client, test_tenant, login_as):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, "lab_subroute_user", "lab")

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name="lab"
        ).first()
        tm.is_active = False
        db.session.commit()

        resp = client.get("/lab/api/test-catalog")
        assert resp.status_code == 403

    def test_pharmacy_disabled_blocks_subroute_too(self, app, client, test_tenant, login_as):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, "pharm_subroute_user", "pharmacist")

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name="pharmacy"
        ).first()
        tm.is_active = False
        db.session.commit()

        resp = client.get("/medication/api/medications/search")
        assert resp.status_code == 403

    def test_reception_disabled_blocks_subroute_too(self, app, client, test_tenant, login_as):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, "recep_subroute_user", "reception")

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name="reception"
        ).first()
        tm.is_active = False
        db.session.commit()

        resp = client.get("/reception/queue")
        assert resp.status_code == 403

    def test_doctor_disabled_blocks_subroute_too(self, app, client, test_tenant, login_as):
        app.config["ENABLE_SAAS_MODE"] = True
        login_as(client, "doc_subroute_user", "doctor")

        tm = TenantModule.query.filter_by(
            tenant_id=test_tenant.id, module_name="doctor"
        ).first()
        tm.is_active = False
        db.session.commit()

        resp = client.get("/doctor/visits")
        assert resp.status_code == 403
