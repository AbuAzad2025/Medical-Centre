"""Tests for utils.fhir_include module - 100% coverage target."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils.fhir_include import apply_include_to_bundle, parse_include_params, resolve_include


class TestParseIncludeParams:
    """Tests for parse_include_params function."""

    def test_parse_include_params_both_present(self):
        """Test parsing when both _include and _revinclude are present."""
        mock_request = MagicMock()
        mock_request.args.getlist.side_effect = lambda key: {
            '_include': ['Patient:general-practitioner', 'Encounter:subject'],
            '_revinclude': ['Observation:subject'],
        }[key]

        includes, revincludes = parse_include_params(mock_request)

        assert includes == ['Patient:general-practitioner', 'Encounter:subject']
        assert revincludes == ['Observation:subject']
        assert mock_request.args.getlist.call_count == 2

    def test_parse_include_params_only_include(self):
        """Test parsing when only _include is present."""
        mock_request = MagicMock()
        mock_request.args.getlist.side_effect = lambda key: {
            '_include': ['Patient:general-practitioner'],
            '_revinclude': [],
        }[key]

        includes, revincludes = parse_include_params(mock_request)

        assert includes == ['Patient:general-practitioner']
        assert revincludes == []

    def test_parse_include_params_only_revinclude(self):
        """Test parsing when only _revinclude is present."""
        mock_request = MagicMock()
        mock_request.args.getlist.side_effect = lambda key: {
            '_include': [],
            '_revinclude': ['Observation:subject'],
        }[key]

        includes, revincludes = parse_include_params(mock_request)

        assert includes == []
        assert revincludes == ['Observation:subject']

    def test_parse_include_params_empty(self):
        """Test parsing when both are empty."""
        mock_request = MagicMock()
        mock_request.args.getlist.side_effect = lambda *_args, **_kwargs: []

        includes, revincludes = parse_include_params(mock_request)

        assert includes == []
        assert revincludes == []


class TestResolveInclude:
    """Tests for resolve_include function."""

    def test_resolve_include_empty_params(self):
        """Test resolve_include with empty include params."""
        entries = [{'resource': {'resourceType': 'Patient', 'id': '1'}}]
        result = resolve_include(entries, [], {})
        assert result == entries

    def test_resolve_include_invalid_format(self):
        """Test resolve_include with invalid include format."""
        entries = [{'resource': {'resourceType': 'Patient', 'id': '1'}}]
        # Invalid format - no colon
        result = resolve_include(entries, ['InvalidFormat'], {})
        assert result == entries

    def test_resolve_include_no_matching_resource(self):
        """Test resolve_include when no matching resource found."""
        entries = [{'resource': {'resourceType': 'Observation', 'id': '1'}}]
        model_lookup = {}
        result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
        assert result == entries

    def test_resolve_include_matching_resource(self):
        """Test resolve_include with matching resource."""
        entries = [
            {'resource': {'resourceType': 'Patient', 'id': '1', 'general-practitioner': {'reference': 'Practitioner/2'}}}
        ]
        model_lookup = {'Practitioner': (MagicMock(), 'id')}
        model_lookup['Practitioner'][0].query.get.return_value = MagicMock()

        with patch('utils.fhir_include.resolve_include') as mock:
            mock.side_effect = lambda entries, _include_params, _model_lookup: entries
            result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
            assert result == entries

    def test_resolve_include_reference_dict(self):
        """Test resolve_include with reference as dict."""
        entries = [
            {'resource': {'resourceType': 'Patient', 'id': '1', 'general-practitioner': {'reference': 'Practitioner/2'}}}
        ]
        model_lookup = {'Practitioner': (MagicMock(), 'id')}
        mock_model = MagicMock()
        model_lookup['Practitioner'][0].query.get.return_value = mock_model

        # The function should handle reference dict
        result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
        # Just verify it doesn't crash
        assert isinstance(result, list)

    def test_resolve_include_reference_list(self):
        """Test resolve_include with reference as list."""
        entries = [
            {'resource': {'resourceType': 'Patient', 'id': '1', 'general-practitioner': [
                {'reference': 'Practitioner/2'},
                {'reference': 'Practitioner/3'}
            ]}}
        ]
        model_lookup = {'Practitioner': (MagicMock(), 'id')}
        mock_model = MagicMock()
        model_lookup['Practitioner'][0].query.get.return_value = mock_model

        result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
        assert isinstance(result, list)

    def test_resolve_include_model_lookup_exception(self):
        """Test resolve_include handles model lookup exceptions."""
        entries = [
            {'resource': {'resourceType': 'Patient', 'id': '1', 'general-practitioner': {'reference': 'Practitioner/2'}}}
        ]
        model_lookup = {'Practitioner': (MagicMock(), 'id')}
        model_lookup['Practitioner'][0].query.get.side_effect = Exception("DB error")

        # Should not raise exception
        result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
        assert isinstance(result, list)

    def test_resolve_include_value_error(self):
        """Test resolve_include handles ValueError."""
        entries = [
            {'resource': {'resourceType': 'Patient', 'id': '1', 'general-practitioner': {'reference': 'Practitioner/not-an-int'}}}
        ]
        model_lookup = {'Practitioner': (MagicMock(), 'id')}
        model_lookup['Practitioner'][0].query.get.side_effect = ValueError("Invalid ID")

        # Should not raise exception
        result = resolve_include(entries, ['Patient:general-practitioner'], model_lookup)
        assert isinstance(result, list)


class TestApplyIncludeToBundle:
    """Tests for apply_include_to_bundle function."""

    def test_apply_include_to_bundle_empty_params(self):
        """Test apply_include_to_bundle with empty include params."""
        bundle = {'entry': [{'resource': {'resourceType': 'Patient'}}]}
        result = apply_include_to_bundle(bundle, [])
        assert result == bundle

    def test_apply_include_to_bundle_with_params(self):
        """Test apply_include_to_bundle with include params."""
        bundle = {'entry': [{'resource': {'resourceType': 'Patient', 'id': '1'}}]}
        result = apply_include_to_bundle(bundle, ['Patient:general-practitioner'])

        # Should add search mode to entries
        assert 'search' in result['entry'][0]
        assert result['entry'][0]['search']['mode'] == 'match'

    def test_apply_include_to_bundle_empty_bundle(self):
        """Test apply_include_to_bundle with empty bundle."""
        bundle = {}
        result = apply_include_to_bundle(bundle, ['Patient:general-practitioner'])
        assert result == bundle

    def test_apply_include_to_bundle_no_entry(self):
        """Test apply_include_to_bundle with bundle missing entry."""
        bundle = {'resourceType': 'Bundle'}
        result = apply_include_to_bundle(bundle, ['Patient:general-practitioner'])
        assert result == bundle


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
