"""Make the audit trail append-only, and stop its foreign keys from rewriting it.

Two things happen here, and they are the same thing.

An entry in the audit trail records what happened. It must not be editable or
removable afterwards, or it records nothing: the general audit trail still
granted UPDATE and DELETE on it, while the PHI access log had already been
closed off that way.

Closing the general audit trail the same way runs straight into a foreign
key. Both audit tables carry a reference to the acting user, and both declare
it ON DELETE SET NULL - so deleting a user made PostgreSQL rewrite the audit
rows that named that user. Rewriting is an UPDATE, and UPDATE is exactly what
append-only withholds. The result was that deleting a user failed with
"permission denied for table phi_audit_logs", and the audit trail could not
be corrected either. The append-only guarantee was not what broke the
deletion; the foreign key was, and it was only reachable because the table
had been closed off.

So the foreign keys to users are dropped. The column keeps the identifier,
because the identifier is the historical fact: an entry says which user id
was acting at the time, and that stays true whether or not the user still
exists. This is also what makes the guarantee mean something - the history is
never rewritten, not even to tidy a reference that now points nowhere.

The tenant foreign keys stay. A tenant is deleted with its rows, and that
is a deletion of the whole tenant, not an edit of its history.

Revision: s3_020_append_only_audit_trails
Revises: s3_019_audit_credential_actions
Create Date: 2026-10-21
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

revision = 's3_020_append_only_audit_trails'
down_revision = 's3_019_audit_credential_actions'
branch_labels = None
depends_on = None

# The constraints that rewrite the audit rows when a user is deleted.
USER_REFERENCE_CONSTRAINTS = (
    ('audit_trails', 'audit_trails_user_id_fkey'),
    ('phi_audit_logs', 'phi_audit_logs_actor_id_fkey'),
)

# The tables whose history may no longer be edited.
APPEND_ONLY_TABLES = ('audit_trails', 'phi_audit_logs')


def _get_app_user() -> str | None:
    """The database role the application connects as, if it can be determined.

    The role is read from the connection URL - the same way s2_003 reads it
    when it closes the PHI access log - so the two migrations revoke from the
    same role. An explicit environment variable wins over the URL, because a
    deployment may connect for migrations as a different role than the one
    the application uses.
    """
    for name in ('APP_DB_USER', 'DATABASE_USER', 'DB_USER'):
        value = os.environ.get(name)
        if value:
            return value
    try:
        url = op.get_bind().engine.url
        if url.username and url.username != 'postgres':
            return url.username
    except Exception:
        pass
    return None


def _constraint_exists(table: str, constraint: str) -> bool:
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    if table not in inspector.get_table_names():
        return False
    existing = {fk['name'] for fk in inspector.get_foreign_keys(table)}
    return constraint in existing


def upgrade() -> None:
    # 1. Drop the foreign keys that would rewrite the history.
    for table, constraint in USER_REFERENCE_CONSTRAINTS:
        if _constraint_exists(table, constraint):
            op.drop_constraint(constraint, table, type_='foreignkey')

    # 2. Close the general audit trail the way the PHI access log already is.
    #    The grants are revoked from the application role, not from the owner,
    #    so the role that owns the schema can still administer it.
    app_user = _get_app_user()
    if app_user:
        for table in APPEND_ONLY_TABLES:
            for stmt in (
                f'REVOKE UPDATE ON {table} FROM "{app_user}"',
                f'REVOKE DELETE ON {table} FROM "{app_user}"',
            ):
                op.execute(stmt)

    # 3. The row-level half of the guarantee. The grants are the database's
    #    answer; these policies are the application's. Without them a
    #    connection that bypasses the grants can still edit the history, and
    #    the retention purge - which runs with a privileged connection on
    #    purpose - can still do the one deletion that is allowed.
    for table in APPEND_ONLY_TABLES:
        for action in ('update', 'delete'):
            policy = f'{table}_no_{action}'
            if not _policy_exists(table, policy):
                op.execute(
                    sa.text(f'CREATE POLICY {policy} ON {table} '
                            f'FOR {action.upper()} USING (false)')
                )


def _policy_exists(table: str, policy: str) -> bool:
    """Is a row-level policy already in place on this table?"""
    from sqlalchemy import text

    bind = op.get_bind()
    row = bind.execute(
        text(
            'SELECT 1 FROM pg_policies '
            'WHERE schemaname = current_schema() AND tablename = :table AND policyname = :policy'
        ),
        {'table': table, 'policy': policy},
    ).first()
    return row is not None


def downgrade() -> None:
    for table in APPEND_ONLY_TABLES:
        for action in ('update', 'delete'):
            policy = f'{table}_no_{action}'
            if _policy_exists(table, policy):
                op.execute(sa.text(f'DROP POLICY IF EXISTS {policy} ON {table}'))

    app_user = _get_app_user()
    if app_user:
        for table in APPEND_ONLY_TABLES:
            for stmt in (
                f'GRANT UPDATE ON {table} TO "{app_user}"',
                f'GRANT DELETE ON {table} TO "{app_user}"',
            ):
                op.execute(stmt)

    for table, constraint in USER_REFERENCE_CONSTRAINTS:
        if not _constraint_exists(table, constraint):
            op.create_foreign_key(
                constraint,
                table,
                'users',
                ['user_id' if table == 'audit_trails' else 'actor_id'],
                ['id'],
                ondelete='SET NULL',
            )
