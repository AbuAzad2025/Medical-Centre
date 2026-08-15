"""Pure-logic tests for app/core/module/validators.py (permissive mode).

All modules can be activated freely. Only hard required_modules are checked.
"""

from __future__ import annotations

import pytest

import app.core.module.registry as R
import app.core.module.validators as V
from app.core.module.registry import ModuleMeta
from app.core.module.validators import (
    can_activate_module,
    validate_profile_modules,
)


def _meta(
    name, required_modules=(), required_any_of=(), standalone_allowed=True, category='clinical'
):
    return ModuleMeta(
        name=name,
        name_ar=name,
        category=category,
        required_modules=tuple(required_modules),
        required_any_of=tuple(required_any_of),
        standalone_allowed=standalone_allowed,
    )


@pytest.fixture
def patched(monkeypatch):
    """Centralized registry + active-set stub for validator isolation."""
    registry = {
        'reception': _meta('reception', category='administrative'),
        'doctor': _meta('doctor', standalone_allowed=True),
        'lab': _meta('lab', standalone_allowed=True),
        'radiology': _meta('radiology', standalone_allowed=True),
        'pharmacy': _meta('pharmacy', standalone_allowed=True),
        'emergency': _meta('emergency', standalone_allowed=True),
        'dental': _meta('dental', standalone_allowed=True),
    }
    clinical = {'doctor', 'lab', 'radiology', 'emergency', 'dental', 'pharmacy'}

    monkeypatch.setattr(V, 'MODULE_REGISTRY', registry)
    monkeypatch.setattr(R, 'get_clinical_modules', lambda: clinical)

    def _set_active(active):
        monkeypatch.setattr(V, 'get_active_modules_for_tenant', lambda _tenant_id: set(active))

    return _set_active


# ---------------------------------------------------------------------------
# can_activate_module - permissive behavior
# ---------------------------------------------------------------------------
class TestCanActivateModule:
    def test_already_active_short_circuits(self, patched):
        patched(active={'radiology'})
        assert can_activate_module(1, 'radiology') == (True, None)

    def test_unknown_module(self, patched):
        patched(active=set())
        ok, err = can_activate_module(1, 'ghost')
        assert ok is False
        assert 'Unknown module' in err

    def test_missing_required_module(self, patched):
        patched(active=set())
        # doctor has no required_modules now, so this should pass
        ok, _err = can_activate_module(1, 'doctor')
        assert ok is True

    def test_any_module_can_activate(self, patched):
        """All modules can be activated freely (no required_any_of, no standalone check)."""
        patched(active=set())
        for module in ['doctor', 'lab', 'radiology', 'pharmacy', 'emergency', 'dental']:
            ok, _err = can_activate_module(1, module)
            assert ok is True, f'{module} should activate: {_err}'

    def test_standalone_profile_allows_any_module(self, patched):
        """standalone profile does not restrict any module."""
        patched(active=set())
        for module in ['doctor', 'lab', 'radiology', 'pharmacy', 'emergency', 'dental']:
            ok, _err = can_activate_module(1, module, profile_code='standalone_clinic')
            assert ok is True, f'{module} in standalone: {_err}'

    def test_happy_path_success(self, patched):
        patched(active={'reception'})
        assert can_activate_module(1, 'lab') == (True, None)


class TestValidateProfileModules:
    def test_returns_empty_no_restrictions(self, patched):
        """validate_profile_modules returns empty list (no restrictions)."""
        patched(active=set())
        errors = validate_profile_modules('standalone_pharmacy', ['doctor', 'lab', 'pharmacy'])
        assert errors == []
