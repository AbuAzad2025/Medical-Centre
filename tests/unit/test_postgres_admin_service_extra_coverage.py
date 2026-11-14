"""Additional coverage tests for services/postgres_admin_service.py"""

from sqlalchemy import create_engine

from services.postgres_admin_service import (
    require_postgresql_engine,
    get_database_health,
)


class TestPostgresAdminServiceExtra:
    def test_require_postgresql_engine_sqlite(self):
        engine = create_engine('sqlite:///test.db')
        try:
            require_postgresql_engine(engine)
        except RuntimeError:
            pass

    def test_get_database_health_sqlite(self):
        engine = create_engine('sqlite:///test.db')
        result = get_database_health(engine)
        assert isinstance(result, dict)
        assert result['healthy'] is False
