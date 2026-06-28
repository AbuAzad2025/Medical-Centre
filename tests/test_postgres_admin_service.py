"""PostgreSQL admin service — dialect and size helpers."""

from unittest.mock import MagicMock, patch

import pytest

from services.postgres_admin_service import (
    format_byte_size,
    get_database_health,
    get_database_size_bytes,
    is_postgresql_uri,
    require_postgresql_engine,
)


class TestDialectDetection:
    def test_postgresql_uri_detected(self):
        assert is_postgresql_uri('postgresql://user:pass@localhost:5432/medical') is True
        assert is_postgresql_uri('postgres://user@db/medical') is True

    def test_sqlite_uri_rejected(self):
        assert is_postgresql_uri('sqlite:///:memory:') is False

    def test_require_postgresql_raises_for_sqlite(self):
        engine = MagicMock()
        engine.url = 'sqlite:///:memory:'
        with pytest.raises(RuntimeError, match='PostgreSQL'):
            require_postgresql_engine(engine)


class TestDatabaseSize:
    def test_get_database_size_bytes(self):
        engine = MagicMock()
        engine.url = 'postgresql://localhost/medical'
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = 1048576
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=conn)
        cm.__exit__ = MagicMock(return_value=False)
        engine.connect.return_value = cm

        assert get_database_size_bytes(engine) == 1048576

    def test_format_byte_size(self):
        assert 'MB' in format_byte_size(5 * 1024 * 1024)

    def test_health_payload_postgresql(self):
        engine = MagicMock()
        engine.url = 'postgresql://localhost/medical'
        with patch('services.postgres_admin_service.get_postgres_server_version', return_value='16.2'), \
             patch('services.postgres_admin_service.get_database_size_bytes', return_value=2048), \
             patch('services.postgres_admin_service.get_active_connection_count', return_value=3):
            health = get_database_health(engine)
        assert health['dialect'] == 'postgresql'
        assert health['healthy'] is True
        assert health['active_connections'] == 3
