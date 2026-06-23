"""Isolation tests for app/core/tenant/service.py.

The Flask `g` proxy is monkeypatched with a plain namespace so tenant-scoping
logic is verified with zero app context and zero DB — this is the data-leak
firewall, so every branch is asserted.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.core.tenant.service as S
from app.core.tenant.service import TenantContextService


@pytest.fixture
def fake_g(monkeypatch):
    """Replace the module-level `g` with a controllable namespace (getattr-based)."""
    ns = SimpleNamespace()
    monkeypatch.setattr(S, "g", ns)
    return ns


# ---------------------------------------------------------------------------
# get_current_tenant / id
# ---------------------------------------------------------------------------
def test_get_current_tenant_none_when_absent(fake_g):
    assert TenantContextService.get_current_tenant() is None
    assert TenantContextService.get_current_tenant_id() is None


def test_get_current_tenant_present(fake_g):
    tenant = SimpleNamespace(id=7)
    fake_g.current_tenant = tenant
    fake_g.tenant_id = 7
    assert TenantContextService.get_current_tenant() is tenant
    assert TenantContextService.get_current_tenant_id() == 7


# ---------------------------------------------------------------------------
# tenant_filter
# ---------------------------------------------------------------------------
class _FakeQuery:
    def __init__(self):
        self.filtered_with = None

    def filter(self, expr):
        self.filtered_with = expr
        return self


class _ModelWithTenant:
    tenant_id = 0  # acts as a sentinel column for hasattr


class _ModelNoTenant:
    pass


def test_tenant_filter_applies_when_tenant_and_column(fake_g):
    fake_g.tenant_id = 5
    q = _FakeQuery()
    out = TenantContextService.tenant_filter(q, _ModelWithTenant)
    assert out is q
    assert q.filtered_with is not None


def test_tenant_filter_skips_without_tenant(fake_g):
    q = _FakeQuery()
    out = TenantContextService.tenant_filter(q, _ModelWithTenant)
    assert out is q
    assert q.filtered_with is None


def test_tenant_filter_skips_model_without_column(fake_g):
    fake_g.tenant_id = 5
    q = _FakeQuery()
    out = TenantContextService.tenant_filter(q, _ModelNoTenant)
    assert out is q
    assert q.filtered_with is None


# ---------------------------------------------------------------------------
# apply_to_model
# ---------------------------------------------------------------------------
def test_apply_to_model_assigns_tenant_id(fake_g):
    fake_g.tenant_id = 9
    inst = _ModelWithTenant()
    TenantContextService.apply_to_model(inst)
    assert inst.tenant_id == 9


def test_apply_to_model_noop_without_tenant(fake_g):
    inst = _ModelWithTenant()
    TenantContextService.apply_to_model(inst)
    assert inst.tenant_id == 0


def test_apply_to_model_noop_without_column(fake_g):
    fake_g.tenant_id = 9
    inst = _ModelNoTenant()
    TenantContextService.apply_to_model(inst)
    assert not hasattr(inst, "tenant_id")


# ---------------------------------------------------------------------------
# ensure_tenant_active
# ---------------------------------------------------------------------------
def test_ensure_tenant_active_raises_without_tenant(fake_g):
    with pytest.raises(PermissionError):
        TenantContextService.ensure_tenant_active()


def test_ensure_tenant_active_raises_when_inactive(fake_g):
    tenant = SimpleNamespace(is_active_and_paid=lambda: False)
    with pytest.raises(PermissionError):
        TenantContextService.ensure_tenant_active(tenant)


def test_ensure_tenant_active_passes_when_active(fake_g):
    tenant = SimpleNamespace(is_active_and_paid=lambda: True)
    TenantContextService.ensure_tenant_active(tenant)  # no raise


# ---------------------------------------------------------------------------
# is_cross_tenant_allowed
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("role,allowed", [
    ("super_admin", True),
    ("owner", True),
    ("doctor", False),
    ("manager", False),
])
def test_is_cross_tenant_allowed(fake_g, role, allowed):
    fake_g.current_user = SimpleNamespace(role=role)
    assert TenantContextService.is_cross_tenant_allowed() is allowed


def test_is_cross_tenant_allowed_no_user(fake_g):
    assert TenantContextService.is_cross_tenant_allowed() is False


# ---------------------------------------------------------------------------
# assert_tenant_access — the cross-tenant firewall
# ---------------------------------------------------------------------------
def test_assert_tenant_access_noop_when_no_context(fake_g):
    rec = SimpleNamespace(tenant_id=99)
    TenantContextService.assert_tenant_access(rec)  # tenant_id None -> skip


def test_assert_tenant_access_same_tenant_ok(fake_g):
    fake_g.tenant_id = 3
    rec = SimpleNamespace(tenant_id=3)
    TenantContextService.assert_tenant_access(rec)  # no raise


def test_assert_tenant_access_cross_tenant_aborts(fake_g):
    from werkzeug.exceptions import Forbidden
    fake_g.tenant_id = 3
    rec = SimpleNamespace(tenant_id=4)
    with pytest.raises(Forbidden):
        TenantContextService.assert_tenant_access(rec)
