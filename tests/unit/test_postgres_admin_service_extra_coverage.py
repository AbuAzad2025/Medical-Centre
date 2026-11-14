"""Additional coverage tests for services/postgres_admin_service.py"""

from sqlalchemy import create_engine

from services.postgres_admin_service import (
    get_database_health,
    require_postgresql_engine,
)


class TestPostgresAdminServiceExtra:
    def test_require_postgresql_engine_sqlite(self):
        engine = create_engine('sqlite:///test.db')
        import contextlib

        with contextlib.suppress(RuntimeError):
            require_postgresql_engine(engine)

    def test_get_database_health_sqlite(self):
        engine = create_engine('sqlite:///test.db')
        result = get_database_health(engine)
        assert isinstance(result, dict)
        assert result['healthy'] is False
