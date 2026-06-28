"""PostgreSQL-native database administration helpers (production dialect only)."""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def is_postgresql_uri(database_uri: str | None) -> bool:
    if not database_uri:
        return False
    scheme = urlparse(database_uri).scheme.lower()
    return scheme in ('postgresql', 'postgres')


def require_postgresql_engine(engine: Engine) -> None:
    if not is_postgresql_uri(str(engine.url)):
        raise RuntimeError('PostgreSQL engine required; SQLite is not supported in production')


def get_database_size_bytes(engine: Engine) -> int:
    """Return pg_database_size for the current connection database."""
    require_postgresql_engine(engine)
    with engine.connect() as conn:
        size = conn.execute(text('SELECT pg_database_size(current_database())')).scalar()
    return int(size or 0)


def format_byte_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f'{size_bytes} B'
    if size_bytes < 1024 ** 2:
        return f'{size_bytes / 1024:.2f} KB'
    if size_bytes < 1024 ** 3:
        return f'{size_bytes / (1024 ** 2):.2f} MB'
    return f'{size_bytes / (1024 ** 3):.2f} GB'


def get_database_size_display(engine: Engine) -> str:
    try:
        return format_byte_size(get_database_size_bytes(engine))
    except Exception as exc:
        logger.warning('Could not read PostgreSQL database size: %s', exc)
        return 'غير متاح'


def get_active_connection_count(engine: Engine) -> int:
    require_postgresql_engine(engine)
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()")
        ).scalar()
    return int(count or 0)


def get_postgres_server_version(engine: Engine) -> str:
    require_postgresql_engine(engine)
    with engine.connect() as conn:
        version = conn.execute(text('SHOW server_version')).scalar()
    return str(version or 'unknown')


def get_database_health(engine: Engine) -> dict[str, Any]:
    """Structured diagnostics for super-admin dashboards."""
    try:
        require_postgresql_engine(engine)
        return {
            'dialect': 'postgresql',
            'server_version': get_postgres_server_version(engine),
            'database_size_bytes': get_database_size_bytes(engine),
            'database_size_display': get_database_size_display(engine),
            'active_connections': get_active_connection_count(engine),
            'healthy': True,
        }
    except Exception as exc:
        logger.error('PostgreSQL health check failed: %s', exc)
        return {
            'dialect': 'unsupported',
            'healthy': False,
            'error': str(exc),
        }
