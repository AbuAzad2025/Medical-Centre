"""Coverage tests for services/postgres_admin_service.py"""

from sqlalchemy import create_engine

from services.postgres_admin_service import (
    is_postgresql_uri,
    require_postgresql_engine,
    get_database_size_bytes,
    format_byte_size,
    get_database_size_display,
    get_active_connection_count,
    get_postgres_server_version,
    get_database_health,
)


class TestPostgresAdminService:
    def test_is_postgresql_uri_true(self):
        assert is_postgresql_uri('postgresql://user:pass@host/db') is True

    def test_is_postgresql_uri_false(self):
        assert is_postgresql_uri('sqlite:///test.db') is False

    def test_is_postgresql_uri_none(self):
        assert is_postgresql_uri(None) is False

    def test_format_byte_size_bytes(self):
        assert format_byte_size(500) == '500 B'

    def test_format_byte_size_kb(self):
        assert format_byte_size(2048) == '2.00 KB'

    def test_format_byte_size_mb(self):
        assert format_byte_size(2 * 1024 * 1024) == '2.00 MB'

    def test_format_byte_size_gb(self):
        assert format_byte_size(2 * 1024 * 1024 * 1024) == '2.00 GB'

    def test_require_postgresql_engine_valid(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        # Should not raise
        require_postgresql_engine(engine)

    def test_get_database_size_bytes(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        result = get_database_size_bytes(engine)
        assert isinstance(result, int)

    def test_get_database_size_display(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        result = get_database_size_display(engine)
        assert isinstance(result, str)

    def test_get_active_connection_count(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        result = get_active_connection_count(engine)
        assert isinstance(result, int)

    def test_get_postgres_server_version(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        result = get_postgres_server_version(engine)
        assert isinstance(result, str)

    def test_get_database_health(self, app):
        engine = create_engine('postgresql://postgres:@127.0.0.1:5432/medical_test')
        result = get_database_health(engine)
        assert isinstance(result, dict)
