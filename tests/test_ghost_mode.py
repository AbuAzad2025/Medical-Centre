"""Tests for Ghost Mode (Master Impersonation) middleware."""
import json

import pytest
from flask import g, current_app
from flask_login import current_user


from app.core.tenant.ghost_mode import (
    ghost_mode_middleware,
    sign_impersonation,
    verify_ghost_signature,
    HEADER_TENANT_ID,
    HEADER_USER_ID,
    HEADER_TIMESTAMP,
    HEADER_SIGNATURE,
)
from seeds import production_baseline as pb
from seeds import local_dev_story as dev
from sqlalchemy import select
from models.audit_trail import AuditTrail
from app.extensions import db


SECRET = "test-ghost-secret"


@pytest.fixture
def ghost_env(app):
    # Ghost Mode must work without a tenant context on the owner, so we
    # exercise it with SaaS mode OFF (no forced tenant resolution). This is
    # localized: the original config is restored on teardown.
    #
    # NOTE: Flask-Login reads ``app.config["SESSION_PROTECTION"]`` to decide
    # its session-protection mode (login_manager.py:390). Setting that config
    # key to ``None`` disables protection GLOBALLY and leaks into later
    # tests (the original value is also ``None`` since the key is never set),
    # which breaks strong-protection tests. So we toggle the LoginManager's
    # own ``session_protection`` attribute and pop the config key instead of
    # setting it, keeping later tests protected.
    from app_factory import login_manager
    prev_saas = app.config.get("ENABLE_SAAS_MODE")
    prev_prot_attr = login_manager.session_protection
    prev_prot_cfg = app.config.pop("SESSION_PROTECTION", None)
    app.config["PLATFORM_OWNER_SECRET"] = SECRET
    app.config["ENABLE_SAAS_MODE"] = False
    login_manager.session_protection = None

    yield app
    app.config["ENABLE_SAAS_MODE"] = prev_saas
    login_manager.session_protection = prev_prot_attr
    if prev_prot_cfg is not None:
        app.config["SESSION_PROTECTION"] = prev_prot_cfg


@pytest.fixture
def master_and_target(app, rollback_db, ghost_env):
    pb.seed_master_account()
    tenant = dev.seed_dev_tenant()
    staff = dev.seed_staff(tenant)
    target = staff["doctor"]  # a normal tenant-scoped user
    # Seeders bind g.tenant_id to the seeded tenant; clear it so the test
    # request re-resolves tenant context from the logged-in user instead of
    # inheriting the leaked dev-tenant id.
    g.tenant_id = None
    g.current_tenant = None
    g.tenant_slug = None
    try:
        from app.extensions import db
        db.session.info.pop("_tenant_id", None)
    except Exception as e:
        pass
    return {"master": pb.seed_master_account(), "tenant": tenant, "target": target}


def _login(client, app, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = f"{user.id}:{int(getattr(user, 'session_version',0) or 0)}"
        sess["_fresh"] = True


def _signed_headers(tenant_id, user_id, secret=SECRET, timestamp=None):
    sig, ts = sign_impersonation(tenant_id, user_id, secret, timestamp)
    return {
        HEADER_TENANT_ID: str(tenant_id),
        HEADER_USER_ID: str(user_id),
        HEADER_TIMESTAMP: ts,
        HEADER_SIGNATURE: sig,
    }


# --- Signature unit tests ------------------------------------------------

def test_signature_valid_and_invalid(ghost_env):
    sig, ts = sign_impersonation(1, 5, SECRET)
    assert verify_ghost_signature(1, 5, ts, sig) is True
    assert verify_ghost_signature(1, 5, ts, "deadbeef") is False
    assert verify_ghost_signature(1, 6, ts, sig) is False  # wrong user


def test_signature_rejects_expired_timestamp(ghost_env):
    old_ts = "1000000000"  # far in the past
    sig, _ = sign_impersonation(1, 5, SECRET, timestamp=old_ts)
    assert verify_ghost_signature(1, 5, old_ts, sig) is False


def test_signature_requires_secret_configured(ghost_env):
    ghost_env.config["PLATFORM_OWNER_SECRET"] = None
    # Also unset the environment variable since _get_secret() falls back to it
    import os
    prev_env = os.environ.pop("PLATFORM_OWNER_SECRET", None)
    try:
        sig, ts = sign_impersonation(1, 5, SECRET)
        # With no secret configured, verification must fail.
        assert verify_ghost_signature(1, 5, ts, sig) is False
    finally:
        if prev_env is not None:
            os.environ["PLATFORM_OWNER_SECRET"] = prev_env


# --- End-to-end impersonation -------------------------------------------

def test_ghost_impersonation_rebinds_context(app, rollback_db, client, master_and_target):
    master = master_and_target["master"]
    tenant = master_and_target["tenant"]
    target = master_and_target["target"]
    _login(client, app, master)

    resp = client.get("/_ghost_whoami", headers=_signed_headers(tenant.id, target.id))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ghost"] is True
    assert data["user_id"] == target.id
    assert data["tenant_id"] == tenant.id
    assert data["username"] == target.username

    # Audit trail recorded for the impersonated request.
    audit = db.session.execute(select(AuditTrail).filter_by(
        action="IMPERSONATE", entity_id=target.id
    )).scalar()
    assert audit is not None
    assert audit.tenant_id == tenant.id
    details = json.loads(audit.new_values)
    assert details["real_actor_id"] == master.id
    assert details["impersonated_user_id"] == target.id


def test_ghost_rejects_bad_signature(app, rollback_db, client, master_and_target):
    master = master_and_target["master"]
    tenant = master_and_target["tenant"]
    target = master_and_target["target"]
    _login(client, app, master)

    headers = _signed_headers(tenant.id, target.id)
    headers[HEADER_SIGNATURE] = "invalid"
    resp = client.get("/_ghost_whoami", headers=headers)
    data = resp.get_json()
    # Not impersonated → actor remains the master, no ghost flag.
    assert data["ghost"] is False
    assert data["user_id"] == master.id


def test_ghost_ignored_for_non_owner(app, rollback_db, client, master_and_target):
    target = master_and_target["target"]  # normal doctor, NOT a platform owner
    tenant = master_and_target["tenant"]
    _login(client, app, target)

    # Even with a perfectly valid signature, a non-owner must NOT impersonate.
    resp = client.get("/_ghost_whoami", headers=_signed_headers(tenant.id, target.id))
    data = resp.get_json()
    assert data["ghost"] is False
    assert data["user_id"] == target.id


def test_ghost_no_headers_is_noop(app, rollback_db, client, master_and_target):
    master = master_and_target["master"]
    _login(client, app, master)
    resp = client.get("/_ghost_whoami")  # no impersonation headers
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ghost"] is False
    assert data["user_id"] == master.id