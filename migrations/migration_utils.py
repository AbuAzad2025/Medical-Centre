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


def unique_constraint_exists(table: str, name: str) -> bool:
    if not table_exists(table):
        return False
    names = {c['name'] for c in _insp().get_unique_constraints(table) if c.get('name')}
    return name in names


def drop_unique_index_if_exists(table: str, index_name: str) -> None:
    if index_exists(table, index_name):
        op.drop_index(index_name, table_name=table)


def drop_unique_constraint_if_exists(table: str, constraint_name: str) -> None:
    if unique_constraint_exists(table, constraint_name):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(constraint_name, type_='unique')


def replace_global_unique_with_tenant(
    table: str,
    column: str,
    new_constraint: str,
    *,
    index_names: tuple[str, ...] = (),
    constraint_names: tuple[str, ...] = (),
) -> None:
    """Drop global unique (index or constraint) and add (tenant_id, column) unique."""
    if unique_constraint_exists(table, new_constraint):
        return
    for idx in index_names:
        drop_unique_index_if_exists(table, idx)
    for name in constraint_names:
        drop_unique_constraint_if_exists(table, name)
    # SQLAlchemy may auto-name UniqueConstraint(column) as {table}_{column}_key
    drop_unique_constraint_if_exists(table, f'{table}_{column}_key')
    with op.batch_alter_table(table, schema=None) as batch_op:
        batch_op.create_unique_constraint(new_constraint, ['tenant_id', column])
