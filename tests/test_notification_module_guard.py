"""Tests for cross-module notification guard in NotificationService.

When a notification targets a role that maps to a disabled module (SaaS mode),
``send_notification`` / ``send_bulk_notification`` must drop it (no DB row) to
prevent side-effects from inactive modules. In standalone mode (SAAS off) all
notifications deliver as before.
"""
import types

import pytest

from services.notification_service import NotificationService, ROLE_TO_MODULE
from models.notification import Notification
from sqlalchemy import select, func
from app.extensions import db


@pytest.fixture
def saas(app, monkeypatch):
    """Enable SaaS mode, bind a fake tenant, and control which modules are disabled."""
    app.config["ENABLE_SAAS_MODE"] = True
    state = {"disabled": set()}

    def _enabled(tenant_id, module):
        return module not in state["disabled"]

    monkeypatch.setattr(
        "services.feature_gate_service.FeatureGateService.module_enabled",
        staticmethod(_enabled),
    )
    with app.test_request_context():
        import flask
        flask.g.current_tenant = types.SimpleNamespace(id=1, slug="pharmacy-shifa")
        yield state


def _count(role):
    return db.session.execute(select(func.count()).select_from(Notification).filter_by(recipient_role=role)).scalar()


def test_disabled_module_notification_is_dropped(saas, rollback_db):
    saas["disabled"].add("pharmacy")
    before = _count("pharmacist")
    result = NotificationService.send_notification(
        recipient_role="pharmacist", title="t", message="m"
    )
    after = _count("pharmacist")
    assert after == before, "Notification must NOT be written when module disabled"
    assert result.get("success") is False


def test_enabled_module_notification_is_sent(saas, rollback_db):
    before = _count("pharmacist")
    NotificationService.send_notification(
        recipient_role="pharmacist", title="t", message="m"
    )
    after = _count("pharmacist")
    assert after == before + 1, "Notification must be written when module enabled"


def test_unmapped_role_always_delivered(saas, rollback_db):
    saas["disabled"].add("pharmacy")
    before = _count("manager")
    NotificationService.send_notification(
        recipient_role="manager", title="t", message="m"
    )
    after = _count("manager")
    assert after == before + 1, "Unmapped (non-module) role must always deliver"


def test_bulk_skips_disabled_role_only(saas, rollback_db):
    saas["disabled"].add("pharmacy")
    ph_before = _count("pharmacist")
    rec_before = _count("reception")
    NotificationService.send_bulk_notification(
        recipient_roles=["pharmacist", "reception"], title="t", message="m"
    )
    assert _count("pharmacist") == ph_before, "Disabled pharmacy role must be skipped"
    assert _count("reception") == rec_before + 1, "Active reception role must deliver"


def test_standalone_mode_always_delivers(rollback_db):
    """Default testing config is SaaS-off: guard is a no-op."""
    before = _count("pharmacist")
    NotificationService.send_notification(
        recipient_role="pharmacist", title="t", message="m"
    )
    assert _count("pharmacist") == before + 1
