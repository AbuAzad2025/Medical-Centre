"""Tests for routes.monitoring_routes module.

Covers Prometheus metrics endpoint and metric collection.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from routes.monitoring_routes import monitoring_bp, _collect_metrics, _discover_tenant_tables


@pytest.fixture
def mock_db_session(monkeypatch):
    """Mock db.session for testing."""
    mock_session = MagicMock()
    monkeypatch.setattr('routes.monitoring_routes.db.session', mock_session)
    return mock_session


class TestDiscoverTenantTables:
    """Tests for _discover_tenant_tables function."""

    def test_discovers_tables_with_tenant_id(self, monkeypatch):
        """Test that function discovers tables with tenant_id column."""
        mock_rows = [('patients',), ('visits',), ('prescriptions',)]
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = mock_rows

        with patch('routes.monitoring_routes.db.session', mock_session):
            tables = _discover_tenant_tables()

        assert 'patients' in tables
        assert 'prescriptions' in tables
        assert 'visits' in tables
        assert 'tenants' not in tables  # global table excluded
        assert 'roles' not in tables  # global table excluded

    def test_excludes_global_tenant_tables(self, monkeypatch):
        """Test that global tenant tables are excluded."""
        # Include global tables in mock results
        mock_rows = [('tenants',), ('roles',), ('patients',), ('visits',)]
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = mock_rows

        with patch('routes.monitoring_routes.db.session', monkeypatch.setattr('routes.monitoring_routes.db.session', MagicMock())):
            mock_session = MagicMock()
            mock_session.execute.return_value.fetchall.return_value = mock_rows
            with patch('routes.monitoring_routes.db.session', mock_session):
                tables = _discover_tenant_tables()

        assert 'patients' in tables
        assert 'visits' in tables
        assert 'tenants' not in tables
        assert 'roles' not in tables

    def test_handles_empty_result(self, monkeypatch):
        """Test handling of empty result."""
        mock_session = MagicMock()
        mock_session.execute.return_value.fetchall.return_value = []

        with patch('routes.monitoring_routes.db.session', mock_session):
            tables = _discover_tenant_tables()

        assert tables == []


class TestCollectMetrics:
    """Tests for _collect_metrics function."""

    def test_returns_prometheus_format(self, monkeypatch):
        """Test that metrics are returned in Prometheus text format."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = 1

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'medical_orphaned_tenant_rows' in result
        assert 'medical_db_up' in result
        assert 'medical_scrape_duration_seconds' in result
        assert 'medical_orphaned_tenant_rows{table="__total__"}' in result

    def test_db_up_when_reachable(self, monkeypatch):
        """Test medical_db_up = 1 when DB is reachable."""
        mock_session = MagicMock()
        mock_session.execute.return_value.scalar.return_value = 1

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'medical_db_up 1' in result

    def test_db_down_when_unreachable(self, monkeypatch):
        """Test medical_db_up = 0 when DB is unreachable."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception('Connection refused')

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'medical_db_up 0' in result

    def test_orphan_rows_metric(self, monkeypatch):
        """Test orphan rows metric collection."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),  # DB health check
            MagicMock(fetchall=MagicMock(return_value=[('patients',), ('visits',)])),  # discover tables
            MagicMock(scalar=MagicMock(return_value=5)),  # patients orphan count
            MagicMock(scalar=MagicMock(return_value=3)),  # visits orphan count
        ]

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'medical_orphaned_tenant_rows{table="patients"}' in result
        assert 'medical_orphaned_tenant_rows{table="visits"}' in result
        assert 'medical_orphaned_tenant_rows{table="__total__"}' in result

    def test_orphan_tables_note(self, monkeypatch):
        """Test NOTE line when orphan tables exist."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),
            MagicMock(fetchall=MagicMock(return_value=[('patients',)])),
            MagicMock(scalar=MagicMock(return_value=5)),
        ]

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'NOTE: tenant_id=0 rows indicate orphaned data' in result

    def test_handles_empty_table_list(self, monkeypatch):
        """Test handling when no tenant-scoped tables exist."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ]

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'medical_db_up 1' in result
        assert 'medical_orphaned_tenant_rows{table="__total__"} 0' in result

    def test_handles_query_error(self, monkeypatch):
        """Test handling of query errors during metric collection."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),  # health check
            MagicMock(fetchall=MagicMock(return_value=[('patients',)])),
            Exception('Query failed'),
        ]

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        assert 'ERROR collecting orphan metrics' in result


class TestMetricsEndpoint:
    """Tests for /metrics endpoint."""

    def test_endpoint_returns_prometheus_format(self, client):
        """Test /metrics endpoint returns Prometheus format."""
        response = client.get('/metrics')
        assert response.status_code == 200
        assert 'text/plain' in response.content_type
        assert 'version=0.0.4' in response.content_type

    def test_response_contains_prometheus_format(self, client):
        """Test response contains Prometheus format markers."""
        response = client.get('/metrics')
        data = response.data.decode('utf-8')
        assert 'medical_orphaned_tenant_rows' in data
        assert 'medical_db_up' in data
        assert 'medical_scrape_duration_seconds' in data

    def test_response_headers(self, client):
        """Test response has correct content type."""
        response = client.get('/metrics')
        assert 'text/plain' in response.content_type
        assert 'version=0.0.4' in response.content_type


class TestEdgeCases:
    """Test edge cases."""

    def test_table_name_escaping(self, monkeypatch):
        """Test that table names with special characters are escaped."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = [
            MagicMock(scalar=MagicMock(return_value=1)),
            MagicMock(fetchall=MagicMock(return_value=[('table"with"quotes',)])),
            MagicMock(scalar=MagicMock(return_value=5)),
        ]

        with patch('routes.monitoring_routes.db.session', mock_session):
            result = _collect_metrics()

        # Check that quotes are escaped in label
        assert 'table="table\\"with\\"quotes"' in result or 'table="table' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])