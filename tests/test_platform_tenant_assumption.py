"""MC-005: Platform tenant assumption tests.

Scenarios:
  1. Normal user accessing their own tenant → allowed
  2. Platform user (super_admin, tenant_id=NULL) accessing tenant route → blocked
  3. Platform user with active assumption → allowed
  4. Platform user with expired assumption → blocked
  5. Assumption revoked → blocked after revocation
  6. Non-platform user cross-tenant access → blocked
  7. Owner API: create, list, revoke assumptions
"""
import uuid
from datetime import datetime, timedelta, timezone
import sys

import pytest
from flask import g

from app.extensions import db
from app.core.tenant.models import Tenant, PlatformTenantAssumption
from app.core.tenant.assumption_service import (
    PlatformAssumptionService, PlatformAssumptionError,
)
from models.user import User


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _create_tenant(slug: str | None = None) -> Tenant:
    slug = slug or _unique_slug("mc005")
    # Bypass tenant filter during setup; restored after commit
    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        t = Tenant(
            slug=slug,
            name=f"MC-005 Tenant {slug}",
            contact_email="mc005@test.local",
            status="active",
            product_profile_code="multi_department_center",
        )
        db.session.add(t)
        db.session.flush()
        # Ensure the reception module is enabled so guard_module doesn't 403
        from app.core.module.models import TenantModule
        existing = TenantModule.query.filter_by(tenant_id=t.id, module_name="reception").first()
        if not existing:
            tm = TenantModule(tenant_id=t.id, module_name="reception", is_active=True)
            db.session.add(tm)
        db.session.commit()
    finally:
        g._tenant_filter_bypass = prev
    return t


def _create_user(username: str, role: str, tenant_id: int | None = None) -> User:
    """Create a user, handling platform users (tenant_id=None) correctly.

    The auto_assign_tenant hook prevents creating users with tenant_id=NULL
    when no tenant context is set.  We work around this by creating the user
    with a temporary tenant reference, then nullifying tenant_id via SQL.
    """
    if tenant_id is not None:
        u = User(
            username=username,
            email=f"{username}@test.local",
            full_name=f"User {username}",
            role=role,
            is_active=True,
            tenant_id=tenant_id,
        )
        u.set_password("test123")
        db.session.add(u)
        db.session.commit()
        return u

    # Platform user (tenant_id=None) — create with dummy tenant then nullify
    dummy = Tenant(
        slug=_unique_slug("dummy"),
        name="Dummy",
        contact_email="dummy@test.local",
        status="active",
        product_profile_code="standalone_clinic",
    )
    db.session.add(dummy)
    db.session.flush()
    u = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"User {username}",
        role=role,
        is_active=True,
        tenant_id=dummy.id,
    )
    u.set_password("test123")
    db.session.add(u)
    db.session.commit()
    # Nullify tenant_id via raw SQL to bypass auto_assign_tenant
    db.session.execute(
        db.text("UPDATE users SET tenant_id = NULL WHERE id = :uid"),
        {"uid": u.id},
    )
    db.session.commit()
    db.session.refresh(u)
    # Clean up dummy tenant
    db.session.delete(dummy)
    db.session.commit()
    return u


def _login(client, user, tenant_slug: str | None = None):
    """Set up Flask session for a given user.

    ``user`` may be a User instance or a user_id (int).  When an int is
    passed, tenant_id is inferred as None (platform-user pattern).

    Uses Flask-Login's ``login_user()`` inside a request context that
    matches the Werkzeug test client's effective environment (same
    ``REMOTE_ADDR`` and ``HTTP_USER_AGENT``) so that
    ``_create_identifier()`` produces the same ``_id`` hash that
    ``session_protection='strong'`` will verify on the next real request.
    Tenant-context extras are added afterward via
    ``session_transaction()``.
    """
    import werkzeug
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()

    if isinstance(user, int):
        user_id = user
        user_tenant_id = None
    else:
        user_id = user.id
        user_tenant_id = getattr(user, "tenant_id", None)

    from flask_login import login_user
    from models.user import User as UserModel
    from app.extensions import db as _db
    from flask import g as _g

    # Match the Werkzeug test client's request environment so that
    # Flask-Login's _create_identifier() (which hashes remote_addr +
    # User-Agent) produces the same _id as the subsequent client.get().
    # Under session_protection='strong', a mismatch would cause an
    # immediate logout on the next request.
    _test_client_environ = {
        "REMOTE_ADDR": "127.0.0.1",
        "HTTP_USER_AGENT": f"Werkzeug/{werkzeug.__version__}",
    }

    with client.application.app_context():
        with client.application.test_request_context(
            environ_base=_test_client_environ,
        ):
            prev = _g.get('_tenant_filter_bypass', False)
            _g._tenant_filter_bypass = True
            try:
                u = _db.session.get(UserModel, user_id)
            finally:
                if prev:
                    _g._tenant_filter_bypass = True
                else:
                    _g.pop('_tenant_filter_bypass', None)
            if u is None:
                raise RuntimeError(f"User id={user_id} not found for _login")
            login_user(u)
            from flask import session as _flask_sess
            _login_user_id = _flask_sess["_user_id"]
            _login_fresh = _flask_sess["_fresh"]
            _login_id = _flask_sess["_id"]

    with client.session_transaction() as sess:
        sess["_user_id"] = _login_user_id
        sess["_fresh"] = _login_fresh
        sess["_id"] = _login_id
        if user_tenant_id is not None:
            sess["tenant_id"] = int(user_tenant_id)
        if tenant_slug:
            sess["tenant_slug"] = tenant_slug


# ─────────────────────────────────────────────
# Service-layer tests (does not require HTTP middleware)
# ─────────────────────────────────────────────

@pytest.mark.no_tenant_context
class TestAssumptionService:

    def test_create_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_create", "super_admin", tenant_id=None)

            a = PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Test assumption creation",
            )
            assert a.id is not None
            assert a.is_active is True
            assert a.user_id == user.id
            assert a.assumed_tenant_id == tenant.id

    def test_create_assumption_requires_reason(self, app):
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_reason", "super_admin", tenant_id=None)

            with pytest.raises(PlatformAssumptionError):
                PlatformAssumptionService.create_assumption(
                    user_id=user.id,
                    assumed_tenant_id=tenant.id,
                    reason="short",
                )

    def test_has_valid_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_valid", "super_admin", tenant_id=None)

            PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Test valid assumption",
            )

            assert PlatformAssumptionService.has_valid_assumption(user.id, tenant.id) is True
            assert PlatformAssumptionService.has_valid_assumption(user.id, 99999) is False

    def test_expired_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_expired", "super_admin", tenant_id=None)

            a = PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Test expired assumption",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )

            assert PlatformAssumptionService.has_valid_assumption(user.id, tenant.id) is False

    def test_revoked_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_revoke", "super_admin", tenant_id=None)

            a = PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Test revoked assumption",
            )

            assert PlatformAssumptionService.has_valid_assumption(user.id, tenant.id) is True

            PlatformAssumptionService.revoke_assumption(
                assumption_id=a.id,
                revoked_by=user.id,
                revoke_reason="Test revocation",
            )

            assert PlatformAssumptionService.has_valid_assumption(user.id, tenant.id) is False

    def test_get_active_assumptions(self, app):
        with app.app_context():
            t1 = _create_tenant()
            t2 = _create_tenant()
            user = _create_user("sa_list", "super_admin", tenant_id=None)

            PlatformAssumptionService.create_assumption(
                user_id=user.id, assumed_tenant_id=t1.id, reason="Assumption for t1",
            )
            PlatformAssumptionService.create_assumption(
                user_id=user.id, assumed_tenant_id=t2.id, reason="Assumption for t2",
            )

            active = PlatformAssumptionService.get_active_assumptions(user_id=user.id)
            assert len(active) == 2

    def test_owner_role_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            owner_user = _create_user("owner_as", "owner", tenant_id=None)

            PlatformAssumptionService.create_assumption(
                user_id=owner_user.id,
                assumed_tenant_id=tenant.id,
                reason="Owner needs to troubleshoot",
            )

            assert PlatformAssumptionService.has_valid_assumption(owner_user.id, tenant.id) is True

    def test_non_platform_user_has_no_assumption(self, app):
        with app.app_context():
            tenant = _create_tenant()
            reception_user = _create_user("rec_noas", "reception", tenant_id=tenant.id)

            assert PlatformAssumptionService.has_valid_assumption(reception_user.id, tenant.id) is False


# ─────────────────────────────────────────────
# Middleware integration tests (require HTTP requests)
# ─────────────────────────────────────────────

@pytest.mark.no_tenant_context
class TestMiddlewareTenantAssumption:

    def test_normal_user_own_tenant_allowed(self, app, client):
        """A normal reception user can access their own tenant's route."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("rec_own", "reception", tenant_id=tenant.id)
            slug = tenant.slug
            _login(client, user, slug)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 200, f"Own-tenant access blocked (got {resp.status_code})"

    def test_super_admin_no_assumption_blocked(self, app, client):
        """Super admin without assumption accessing non-exempt tenant route → 403."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_blocked", "super_admin", tenant_id=None)
            slug = tenant.slug
            _login(client, user.id, None)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_super_admin_with_assumption_allowed(self, app, client):
        """Super admin with active assumption can access tenant route."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_allow", "super_admin", tenant_id=None)
            PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Need to help tenant support",
            )
            slug = tenant.slug
            _login(client, user.id, None)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code != 403, f"Super admin with assumption blocked (got {resp.status_code})"

    def test_super_admin_expired_assumption_blocked(self, app, client):
        """Super admin with expired assumption → 403."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_exp", "super_admin", tenant_id=None)
            PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Short-lived support task",
                expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
            slug = tenant.slug
            _login(client, user.id, None)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_revoked_assumption_blocked(self, app, client):
        """Revoked assumption → 403."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("sa_rev", "super_admin", tenant_id=None)
            a = PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Will be revoked",
            )
            PlatformAssumptionService.revoke_assumption(
                assumption_id=a.id,
                revoked_by=user.id,
                revoke_reason="Test: revoking",
            )
            slug = tenant.slug
            _login(client, user.id, None)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_non_platform_user_cross_tenant_blocked(self, app, client):
        """A reception user from Tenant A cannot access Tenant B."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant_a = _create_tenant(_unique_slug("ta"))
            tenant_b = _create_tenant(_unique_slug("tb"))
            user = _create_user("rec_cross", "reception", tenant_id=tenant_a.id)
            slug_a = tenant_a.slug
            slug_b = tenant_b.slug
            _login(client, user.id, slug_a)

            with client.session_transaction() as sess:
                sess["tenant_slug"] = slug_b

        resp = client.get(f"/t/{slug_b}/reception/visits")
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_super_admin_exempt_path_not_blocked(self, app, client):
        """Super admin can access /super-admin/ and /owner/ paths without assumption."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            user = _create_user("sa_exempt", "super_admin", tenant_id=None)
            _login(client, user.id, None)

        resp = client.get("/super-admin/dashboard")
        assert resp.status_code == 200, f"Exempt path blocked (got {resp.status_code})"

    def test_owner_with_assumption_allowed(self, app, client):
        """Platform owner with assumption can access tenant route."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("owner_ok", "owner", tenant_id=None)
            PlatformAssumptionService.create_assumption(
                user_id=user.id,
                assumed_tenant_id=tenant.id,
                reason="Owner testing",
            )
            slug = tenant.slug
            _login(client, user.id, None)

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 200, f"Owner with assumption blocked (got {resp.status_code})"


# ─────────────────────────────────────────────
# Owner API tests
# ─────────────────────────────────────────────

@pytest.mark.no_tenant_context
class TestAssumptionOwnerAPI:

    def _login_owner(self, client, app):
        """Create and login an owner user for API tests."""
        with app.app_context():
            user = _create_user("owner_api", "owner", tenant_id=None)
            _login(client, user, None)
        return user.id

    def test_create_assumption_api(self, app, client):
        """POST /owner/api/assumptions creates an assumption."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            target_user = _create_user("target_u", "super_admin", tenant_id=None)
            target_user_id = target_user.id
            tenant_id = tenant.id

        self._login_owner(client, app)

        resp = client.post("/owner/api/assumptions", json={
            "user_id": target_user_id,
            "assumed_tenant_id": tenant_id,
            "reason": "Owner initiated support access",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["assumption"]["user_id"] == target_user_id
        assert data["assumption"]["assumed_tenant_id"] == tenant_id
        assert data["assumption"]["is_active"] is True

    def test_list_assumptions_api(self, app, client):
        """GET /owner/api/assumptions lists active assumptions."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            target_user = _create_user("target_l", "super_admin", tenant_id=None)

            PlatformAssumptionService.create_assumption(
                user_id=target_user.id,
                assumed_tenant_id=tenant.id,
                reason="List test reason (10 chars min)",
            )

        self._login_owner(client, app)

        resp = client.get("/owner/api/assumptions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] >= 1

    def test_revoke_assumption_api(self, app, client):
        """POST /owner/api/assumptions/<id>/revoke revokes an assumption."""
        app.config["ENABLE_SAAS_MODE"] = True

        with app.app_context():
            tenant = _create_tenant()
            target_user = _create_user("target_r", "super_admin", tenant_id=None)

            a = PlatformAssumptionService.create_assumption(
                user_id=target_user.id,
                assumed_tenant_id=tenant.id,
                reason="Will be revoked via API",
            )
            a_id = a.id

        self._login_owner(client, app)

        resp = client.post(f"/owner/api/assumptions/{a_id}/revoke", json={
            "revoke_reason": "Revoked via API test",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["assumption"]["is_active"] is False
        assert data["assumption"]["revoke_reason"] == "Revoked via API test"

    def test_create_assumption_requires_fields(self, app, client):
        """POST /owner/api/assumptions without required fields → 400."""
        app.config["ENABLE_SAAS_MODE"] = True
        self._login_owner(client, app)

        resp = client.post("/owner/api/assumptions", json={
            "reason": "Missing fields",
        })
        assert resp.status_code == 400


# ─────────────────────────────────────────────
# Regression: Flask-Login session_protection="strong" requires _id
# ─────────────────────────────────────────────

@ pytest.mark.no_tenant_context
class TestStrongSessionProtection:

    def test_real_login_remains_authenticated_under_strong(self, app, client):
        """A real POST /auth/login (calls login_user() which sets _id) stays
        authenticated on the next request under session_protection='strong'."""
        app.config["ENABLE_SAAS_MODE"] = True
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("strong_real", "reception", tenant_id=tenant.id)
            slug = tenant.slug

        resp = client.post("/auth/login", data={
            "username": "strong_real",
            "password": "test123",
            "tenant_slug": slug,
        })
        assert resp.status_code in (200, 302), f"Login failed: {resp.status_code}"

        with client.session_transaction() as sess:
            assert sess.get("_id") is not None, "_id was NOT set by login_user()"

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 200, (
            f"Authenticated user got {resp.status_code} under strong "
            f"(Location: {resp.headers.get('Location','')})"
        )

    def test_repaired_helper_remains_authenticated_under_strong(self, app, client):
        """The fixed _login() helper (which now uses login_user()) stays
        authenticated on the next request under session_protection='strong'."""
        import sys as _sys
        app.config["ENABLE_SAAS_MODE"] = True
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("strong_hlp", "reception", tenant_id=tenant.id)
            slug = tenant.slug
            _login(client, user, slug)

        # Debug: check session before request
        with client.session_transaction() as sess:
            print(f"[PRE-GET] _id={sess.get('_id')!r} _uid={sess.get('_user_id')!r} keys={list(sess.keys())}", file=_sys.stderr)

        resp = client.get(f"/t/{slug}/reception/visits")
        print(f"[POST-GET] status={resp.status_code} loc={resp.headers.get('Location','')}", file=_sys.stderr)
        assert resp.status_code == 200, (
            f"Fixed-helper user got {resp.status_code} under strong "
            f"(Location: {resp.headers.get('Location','')})"
        )

    def test_missing_id_is_rejected_under_strong(self, app, client):
        """A session with _user_id but no _id is rejected (302 to login)."""
        app.config["ENABLE_SAAS_MODE"] = True
        with app.app_context():
            tenant = _create_tenant()
            user = _create_user("strong_bad", "reception", tenant_id=tenant.id)
            user_id = user.id
            slug = tenant.slug

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True
            # Intentionally omit _id

        with client.session_transaction() as sess:
            assert sess.get("_id") is None, "_id should be absent in broken-helper test"

        resp = client.get(f"/t/{slug}/reception/visits")
        assert resp.status_code == 302, f"Expected 302 redirect to login, got {resp.status_code}"
        assert "/auth/login" in resp.headers.get("Location", "")
