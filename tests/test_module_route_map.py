"""Tests for app.core.module_route_map module.

Covers module-to-route mapping and core blueprint identification utilities.
"""

import pytest

from app.core.module_route_map import (
    MODULE_ROUTE_MAP,
    CORE_BLUEPRINTS,
    get_module_for_prefix,
    get_prefixes_for_module,
    is_core_blueprint,
)


class TestGetModuleForPrefix:
    """Tests for get_module_for_prefix function."""

    def test_finds_module_for_known_prefix(self):
        """Test finding module for known prefix."""
        assert get_module_for_prefix('/reception') == 'reception'
        assert get_module_for_prefix('/doctor') == 'doctor'
        assert get_module_for_prefix('/lab') == 'lab'
        assert get_module_for_prefix('/radiology') == 'radiology'
        assert get_module_for_prefix('/dicom') == 'radiology'
        assert get_module_for_prefix('/medication') == 'pharmacy'
        assert get_module_for_prefix('/emergency') == 'emergency'
        assert get_module_for_prefix('/nurse') == 'nursing'
        assert get_module_for_prefix('/finance') == 'billing'
        assert get_module_for_prefix('/payment') == 'billing'
        assert get_module_for_prefix('/booking') == 'appointments'
        assert get_module_for_prefix('/manager') == 'reporting'
        assert get_module_for_prefix('/quality') == 'reporting'
        assert get_module_for_prefix('/owner') == 'owner'
        assert get_module_for_prefix('/portal') == 'portal'
        assert get_module_for_prefix('/ai-imaging') == 'ai_imaging'
        assert get_module_for_prefix('/api/fhir') == 'integration'
        assert get_module_for_prefix('/sso') == 'integration'

    def test_returns_none_for_unknown_prefix(self):
        """Test returning None for unknown prefix."""
        assert get_module_for_prefix('/unknown') is None
        assert get_module_for_prefix('/api') is None
        assert get_module_for_prefix('') is None

    def test_all_modules_have_prefixes(self):
        """Test that every module in the map has at least one prefix."""
        for module, info in MODULE_ROUTE_MAP.items():
            assert 'prefixes' in info
            assert len(info['prefixes']) > 0
            assert 'blueprints' in info
            assert len(info['blueprints']) > 0


class TestGetPrefixesForModule:
    """Tests for get_prefixes_for_module function."""

    def test_get_prefixes_for_known_module(self):
        """Test getting prefixes for known modules."""
        assert '/reception' in get_prefixes_for_module('reception')
        assert '/doctor' in get_prefixes_for_module('doctor')
        assert '/lab' in get_prefixes_for_module('lab')

    def test_get_prefixes_for_unknown_module(self):
        """Test getting prefixes for unknown module."""
        assert get_prefixes_for_module('unknown_module') == []
        assert get_prefixes_for_module(None) == []
        assert get_prefixes_for_module('') == []

    def test_all_prefixes_are_strings(self):
        """Test that all prefixes in the map are strings."""
        for module in MODULE_ROUTE_MAP:
            for prefix in get_prefixes_for_module(module):
                assert isinstance(prefix, str)


class TestIsCoreBlueprint:
    """Tests for is_core_blueprint function."""

    def test_identifies_core_blueprints(self):
        """Test identifying core blueprints."""
        assert is_core_blueprint('main_bp') is True
        assert is_core_blueprint('auth_bp') is True
        assert is_core_blueprint('security_bp') is True
        assert is_core_blueprint('mfa_bp') is True
        assert is_core_blueprint('backup_bp') is True
        assert is_core_blueprint('backup_restore_bp') is True
        assert is_core_blueprint('biometric_bp') is True

    def test_returns_false_for_non_core_blueprint(self):
        """Test returning False for non-core blueprints."""
        assert is_core_blueprint('reception_bp') is False
        assert is_core_blueprint('doctor_bp') is False
        assert is_core_blueprint('quality_bp') is False
        assert is_core_blueprint('unknown_bp') is False
        assert is_core_blueprint('') is False
        assert is_core_blueprint(None) is False

    def test_core_blueprints_is_set(self):
        """Test that CORE_BLUEPRINTS is a set."""
        assert isinstance(CORE_BLUEPRINTS, set)


class TestModuleRouteMapStructure:
    """Tests for the module route map data structure integrity."""

    def test_module_route_map_is_dict(self):
        """Test that MODULE_ROUTE_MAP is a dictionary."""
        assert isinstance(MODULE_ROUTE_MAP, dict)

    def test_each_module_has_expected_keys(self):
        """Test that each module entry has the expected keys."""
        for module, info in MODULE_ROUTE_MAP.items():
            assert isinstance(module, str)
            assert isinstance(info, dict)
            assert 'blueprints' in info
            assert 'prefixes' in info
            assert isinstance(info['blueprints'], list)
            assert isinstance(info['prefixes'], list)

    def test_no_duplicate_prefixes_across_modules(self):
        """Test that prefixes are unique across modules."""
        all_prefixes = []
        for info in MODULE_ROUTE_MAP.values():
            all_prefixes.extend(info['prefixes'])
        assert len(all_prefixes) == len(set(all_prefixes))

    def test_doctor_module_has_many_blueprints(self):
        """Test the doctor module has expected blueprints."""
        doctor_bps = MODULE_ROUTE_MAP['doctor']['blueprints']
        assert 'doctor_bp' in doctor_bps
        assert 'vaccination_bp' in doctor_bps
        assert 'cds_bp' in doctor_bps

    def test_nursing_module_structure(self):
        """Test the nursing module structure."""
        nursing = MODULE_ROUTE_MAP['nursing']
        assert '/nursing-assessment' in nursing['prefixes']
        assert 'nursing_assessment_bp' in nursing['blueprints']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
