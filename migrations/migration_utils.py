"""Idempotent helpers for migrations that may overlap prod_baseline."""
from alembic import op
import sqlalchemy as sa


def _insp():
    return sa.inspect(op.get_bind())


def table_exists(name: str) -> bool:
    return name in _insp().get_table_names()


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    return column in {c['name'] for c in _insp().get_columns(table)}


def index_exists(table: str, index_name: str) -> bool:
    if not table_exists(table):
        return False
    names = {i['name'] for i in _insp().get_indexes(table)}
    return index_name in names


def fk_exists(table: str, fk_name: str) -> bool:
    if not table_exists(table):
        return False
    names = {fk['name'] for fk in _insp().get_foreign_keys(table) if fk.get('name')}
    return fk_name in names


def check_constraint_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    names = {c['name'] for c in _insp().get_check_constraints(table)}
    return name in names
