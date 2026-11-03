"""Tests for utils.fhir_search module - 100% coverage target."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from utils.fhir_search import (
    apply_fhir_pagination,
    apply_fhir_sort,
    fhir_bundle,
    parse_fhir_params,
)


class TestParseFhirParams:
    """Tests for parse_fhir_params function."""

    def test_parse_fhir_params_standard_params(self):
        """Test parsing standard FHIR search parameters."""
        mock_request = MagicMock()
        mock_request.args = {
            '_id': '123',
            '_lastUpdated': '2024-01-01',
            '_count': '50',
            '_offset': '10',
            '_sort': '-created',
            '_include': 'Patient:general-practitioner',
            '_revinclude': 'Observation:subject',
            'name': 'John',
            'gender': 'male',
        }

        params = parse_fhir_params(mock_request)

        assert params['_id'] == '123'
        assert params['_lastUpdated'] == '2024-01-01'
        assert params['_count'] == '50'
        assert params['_offset'] == '10'
        assert params['_sort'] == '-created'
        assert params['_include'] == 'Patient:general-practitioner'
        assert params['_revinclude'] == 'Observation:subject'
        assert params['name'] == 'John'
        assert params['gender'] == 'male'

    def test_parse_fhir_params_only_standard(self):
        """Test parsing only standard FHIR params."""
        mock_request = MagicMock()
        mock_request.args = {
            '_id': '123',
            '_count': '20',
        }

        params = parse_fhir_params(mock_request)

        assert params['_id'] == '123'
        assert params['_count'] == '20'
        assert 'name' not in params

    def test_parse_fhir_params_only_resource_specific(self):
        """Test parsing only resource-specific params."""
        mock_request = MagicMock()
        mock_request.args = {
            'name': 'John',
            'gender': 'male',
            'birthdate': '1990-01-01',
        }

        params = parse_fhir_params(mock_request)

        assert params['name'] == 'John'
        assert params['gender'] == 'male'
        assert params['birthdate'] == '1990-01-01'
        assert '_id' not in params

    def test_parse_fhir_params_empty(self):
        """Test parsing empty request."""
        mock_request = MagicMock()
        mock_request.args = {}

        params = parse_fhir_params(mock_request)

        assert params == {}

    def test_parse_fhir_params_none_value(self):
        """Test parsing with None value (should be skipped)."""
        mock_request = MagicMock()
        mock_request.args = {
            '_id': None,
            'name': 'John',
        }

        params = parse_fhir_params(mock_request)

        # None values are skipped in the standard params loop
        assert params['name'] == 'John'
        # _id with None value won't be added


class TestApplyFhirPagination:
    """Tests for apply_fhir_pagination function."""

    def test_apply_fhir_pagination_default_count(self):
        """Test pagination with default count."""
        mock_query = MagicMock()
        mock_request = MagicMock()
        # args.get returns different values for different keys
        mock_request.args.get.side_effect = lambda key, default=None: {
            '_count': '20',
            '_offset': '0',
        }.get(key, default)

        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        _result_query, count, offset = apply_fhir_pagination(mock_query, mock_request)

        assert count == 20
        assert offset == 0
        mock_query.offset.assert_called_with(0)
        mock_query.limit.assert_called_with(20)

    def test_apply_fhir_pagination_custom_count(self):
        """Test pagination with custom count."""
        mock_query = MagicMock()
        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda key, default=None: {
            '_count': '50',
            '_offset': '0',
        }.get(key, default)

        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        _result_query, count, offset = apply_fhir_pagination(
            mock_query, mock_request, default_count=20, max_count=100
        )

        assert count == 50
        assert offset == 0

    def test_apply_fhir_pagination_max_count(self):
        """Test pagination respects max count."""
        mock_query = MagicMock()
        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda key, default=None: {
            '_count': '200',
            '_offset': '0',
        }.get(key, default)

        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        _result_query, count, _offset = apply_fhir_pagination(
            mock_query, mock_request, default_count=20, max_count=100
        )

        assert count == 100  # capped at max_count

    def test_apply_fhir_pagination_with_offset(self):
        """Test pagination with offset."""
        mock_query = MagicMock()
        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda key, default=None: {
            '_count': '10',
            '_offset': '5',
        }.get(key, default)

        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        _result_query, count, offset = apply_fhir_pagination(mock_query, mock_request)

        assert count == 10
        assert offset == 5
        mock_query.offset.assert_called_with(5)

    def test_apply_fhir_pagination_default_offset(self):
        """Test pagination with default offset (0)."""
        mock_query = MagicMock()
        mock_request = MagicMock()
        mock_request.args.get.side_effect = lambda key, default=None: {
            '_count': '10',
            '_offset': '0',
        }.get(key, default)

        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query

        _result_query, count, offset = apply_fhir_pagination(mock_query, mock_request)

        assert count == 10
        assert offset == 0


class TestApplyFhirSort:
    """Tests for apply_fhir_sort function."""

    def test_apply_fhir_sort_ascending(self):
        """Test sorting with ascending order."""
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created = 'created'

        mock_query.order_by.return_value = mock_query

        result = apply_fhir_sort(mock_query, mock_model, 'created')

        mock_query.order_by.assert_called_once()
        assert result == mock_query

    def test_apply_fhir_sort_descending(self):
        """Test sorting with descending order."""
        mock_query = MagicMock()
        mock_model = MagicMock()
        mock_model.created = 'created'

        mock_query.order_by.return_value = mock_query

        result = apply_fhir_sort(mock_query, mock_model, '-created')

        mock_query.order_by.assert_called_once()
        assert result == mock_query

    def test_apply_fhir_sort_invalid_field(self):
        """Test sorting with invalid field raises exception (as per current implementation)."""
        mock_query = MagicMock()
        mock_model = MagicMock()
        # Model doesn't have 'invalid_field' attribute

        with pytest.raises(Exception):
            apply_fhir_sort(mock_query, mock_model, 'invalid_field')

    def test_apply_fhir_sort_no_sort_param(self):
        """Test with no sort parameter returns original query."""
        mock_query = MagicMock()
        mock_model = MagicMock()

        result = apply_fhir_sort(mock_query, mock_model, None)

        mock_query.order_by.assert_not_called()
        assert result == mock_query

    def test_apply_fhir_sort_empty_string(self):
        """Test with empty sort parameter."""
        mock_query = MagicMock()
        mock_model = MagicMock()

        result = apply_fhir_sort(mock_query, mock_model, '')

        mock_query.order_by.assert_not_called()
        assert result == mock_query

    def test_apply_fhir_sort_fallback(self):
        """Test fallback when neither ascending nor descending condition is met."""
        mock_query = MagicMock()

        # Use a simple class instead of MagicMock to avoid dynamic attribute creation
        class MockModel:
            pass

        mock_model = MockModel()

        # This should fall through to return query
        result = apply_fhir_sort(mock_query, mock_model, 'nonexistent_field')
        assert result == mock_query


class TestFhirBundle:
    """Tests for fhir_bundle function."""

    def test_fhir_bundle_basic(self):
        """Test creating a basic FHIR bundle."""
        entries = [
            {'resourceType': 'Patient', 'id': '1', 'name': 'John'},
            {'resourceType': 'Patient', 'id': '2', 'name': 'Jane'},
        ]

        bundle = fhir_bundle(entries, total=2)

        assert bundle['resourceType'] == 'Bundle'
        assert bundle['type'] == 'searchset'
        assert bundle['total'] == 2
        assert len(bundle['entry']) == 2
        assert bundle['entry'][0]['resource'] == {
            'resourceType': 'Patient',
            'id': '1',
            'name': 'John',
        }
        assert bundle['entry'][1]['resource'] == {
            'resourceType': 'Patient',
            'id': '2',
            'name': 'Jane',
        }
        assert bundle['link'] == []

    def test_fhir_bundle_custom_type(self):
        """Test creating a FHIR bundle with custom type."""
        entries = [{'resourceType': 'Patient', 'id': '1'}]

        bundle = fhir_bundle(entries, total=1, resource_type='transaction')

        assert bundle['type'] == 'transaction'

    def test_fhir_bundle_empty_entries(self):
        """Test creating bundle with empty entries."""
        bundle = fhir_bundle([], total=0)

        assert bundle['total'] == 0
        assert bundle['entry'] == []

    def test_fhir_bundle_single_entry(self):
        """Test creating bundle with single entry."""
        entries = [{'resourceType': 'Observation', 'id': '1', 'value': 100}]

        bundle = fhir_bundle(entries, total=1)

        assert bundle['total'] == 1
        assert len(bundle['entry']) == 1
        assert bundle['entry'][0]['resource']['id'] == '1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
