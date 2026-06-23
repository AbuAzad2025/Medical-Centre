"""Pure-logic tests for app/core/module/validators.py.

LEAN: the only DB touch (get_active_modules_for_tenant) and the registry are
monkeypatched, so all branch logic is exercised without a database.
"""

from __future__ import annotations

import pytest

import app.core.module.validators as V
from app.core.module.registry import ModuleMeta
from app.core.module.validators import (
    ModuleValidationError,
    validate_reception_required,
    validate_required_any_of,
    can_activate_module,
)


def _meta(name, required_modules=(), required_any_of=(), standalone_allowed=False, category="clinical"):
    return ModuleMeta(
        name=name, name_ar=name, category=category,
        required_modules=tuple(required_modules),
        required_any_of=tuple(required_any_of),
        standalone_allowed=standalone_allowed,
    )


@pytest.fixture
def patched(monkeypatch):
    """Centralized registry + active-set stub for validator isolation."""
    registry = {
        "reception": _meta("reception", category="administrative"),
        "doctor": _meta("doctor", required_any_of=(("reception", "standalone_intake"),), standalone_allowed=True),
        "lab": _meta("lab", required_any_of=(("reception",),), standalone_allowed=True),
        "radiology": _meta("radiology", standalone_allowed=False),
        "pharmacy": _meta("pharmacy", required_modules=("reception",), standalone_allowed=False),
        "emergency": _meta("emergency", standalone_allowed=True),
        "dental": _meta("dental", standalone_allowed=True),
    }
    clinical = {"doctor", "lab", "radiology", "emergency", "dental", "pharmacy"}

    monkeypatch.setattr(V, "MODULE_REGISTRY", registry)
    monkeypatch.setattr(V, "get_clinical_modules", lambda: clinical)

    def _set_active(active):
        monkeypatch.setattr(V, "get_active_modules_for_tenant", lambda tenant_id: set(active))

    return _set_active


# ---------------------------------------------------------------------------
# validate_reception_required
# ---------------------------------------------------------------------------
class TestReceptionRequired:
    def test_more_than_three_clinical_without_reception_raises(self, patched):
        patched(active=set())
        with pytest.raises(ModuleValidationError):
            validate_reception_required(1, ["doctor", "lab", "radiology", "emergency"])

    def test_more_than_three_clinical_with_reception_ok(self, patched):
        patched(active={"reception"})
        # reception is administrative, so the 4 clinical + reception present
        validate_reception_required(1, ["doctor", "lab", "radiology", "emergency", "reception"])

    def test_exactly_three_clinical_ok_without_reception(self, patched):
        patched(active=set())
        validate_reception_required(1, ["doctor", "lab", "radiology"])

    def test_active_and_proposed_union_counts(self, patched):
        patched(active={"doctor", "lab"})
        with pytest.raises(ModuleValidationError):
            validate_reception_required(1, ["radiology", "emergency"])


# ---------------------------------------------------------------------------
# validate_required_any_of
# ---------------------------------------------------------------------------
class TestRequiredAnyOf:
    def test_no_meta_returns_ok(self, patched):
        patched(active=set())
        assert validate_required_any_of(1, "unknown", set()) == (True, None)

    def test_no_requirement_returns_ok(self, patched):
        patched(active=set())
        assert validate_required_any_of(1, "radiology", set()) == (True, None)

    def test_satisfied_by_active(self, patched):
        patched(active=set())
        ok, err = validate_required_any_of(1, "doctor", {"reception"})
        assert ok is True and err is None

    def test_satisfied_by_self(self, patched):
        patched(active=set())
        ok, err = validate_required_any_of(1, "doctor", set())
        # group contains neither reception nor standalone_intake in active,
        # and module_name 'doctor' is not in the group -> not satisfied
        assert ok is False
        assert "requires" in err

    def test_unsatisfied_returns_message(self, patched):
        patched(active=set())
        ok, err = validate_required_any_of(1, "lab", {"pharmacy"})
        assert ok is False
        assert "lab" in err


# ---------------------------------------------------------------------------
# can_activate_module
# ---------------------------------------------------------------------------
class TestCanActivateModule:
    def test_already_active_short_circuits(self, patched):
        patched(active={"radiology"})
        assert can_activate_module(1, "radiology") == (True, None)

    def test_unknown_module(self, patched):
        patched(active=set())
        ok, err = can_activate_module(1, "ghost")
        assert ok is False
        assert "Unknown module" in err

    def test_missing_required_module(self, patched):
        patched(active=set())
        ok, err = can_activate_module(1, "pharmacy")
        assert ok is False
        assert "requires 'reception'" in err

    def test_required_any_of_unsatisfied(self, patched):
        patched(active=set())
        ok, err = can_activate_module(1, "doctor")
        assert ok is False
        assert "requires" in err

    def test_standalone_profile_blocks_non_standalone_module(self, patched):
        patched(active={"reception"})
        ok, err = can_activate_module(1, "radiology", profile_code="standalone_imaging")
        assert ok is False
        assert "standalone" in err

    def test_standalone_profile_allows_standalone_module(self, patched):
        patched(active={"reception"})
        ok, err = can_activate_module(1, "doctor", profile_code="standalone_clinic")
        assert ok is True
        assert err is None

    def test_reception_rule_blocks_fourth_clinical(self, patched):
        patched(active={"doctor", "lab", "emergency"})
        ok, err = can_activate_module(1, "dental")
        assert ok is False
        assert "Reception" in err or "reception" in err

    def test_happy_path_success(self, patched):
        patched(active={"reception"})
        assert can_activate_module(1, "lab") == (True, None)
