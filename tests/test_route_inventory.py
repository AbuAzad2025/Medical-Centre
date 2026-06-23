"""Tests for P0A-003: route inventory and safety switches."""

import json
from pathlib import Path

import pytest


class TestRouteInventory:
    """Route inventory must exist, be valid JSON, and cover all registered routes."""

    def test_route_inventory_file_exists(self):
        inv_path = Path(__file__).parent.parent / "route_inventory.json"
        assert inv_path.exists(), "route_inventory.json is missing"

    def test_route_inventory_is_valid_json(self):
        inv_path = Path(__file__).parent.parent / "route_inventory.json"
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        assert "routes" in data
        assert "total_routes" in data
        assert data["total_routes"] == len(data["routes"])
        for route in data["routes"]:
            assert route["endpoint"]
            assert route["path"].startswith("/")
            assert route["classification"] in {
                "public", "internal", "admin", "super-admin", "authenticated"
            }

    def test_all_registered_routes_are_in_inventory(self, app):
        inv_path = Path(__file__).parent.parent / "route_inventory.json"
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        inventory_paths = {r["path"] for r in data["routes"]}
        registered_paths = {str(rule) for rule in app.url_map.iter_rules()}
        missing = registered_paths - inventory_paths
        assert not missing, f"Missing routes in inventory: {missing}"


class TestRouteAuthGates:
    """Route access classification smoke checks."""

    def test_login_page_is_public(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code in (200, 302)

    def test_doctor_dashboard_requires_login(self, client):
        resp = client.get("/doctor/dashboard")
        assert resp.status_code in (302, 401, 403)

    def test_reception_dashboard_requires_login(self, client):
        resp = client.get("/reception/dashboard")
        assert resp.status_code in (302, 401, 403)


class TestAdminRoutes:
    """Admin routes require admin privileges."""

    def test_manager_settings_requires_admin(self, client):
        resp = client.get("/manager/settings")
        assert resp.status_code in (302, 401, 403)


class TestSuperAdminRoutes:
    """Super-admin routes require super-admin privileges."""

    def test_super_admin_dashboard_requires_super_admin(self, client):
        resp = client.get("/super-admin/dashboard")
        assert resp.status_code in (302, 401, 403)

    def test_owner_dashboard_requires_super_admin(self, client):
        resp = client.get("/owner/dashboard")
        assert resp.status_code in (302, 401, 403)
