"""The audit trail is append-only, and it survives the people it names.

An audit entry records what happened. Once it is written, nobody may edit it
and nobody may remove it - not the application, not an operator with a
session, not a mistake. The general audit trail still granted UPDATE and
DELETE, so any of those was possible, and an investigation that relied on the
trail could not rely on it.

Closing it that way runs into a second problem, and the second problem is
the one that bites first. Both audit tables referenced the acting user with
ON DELETE SET NULL, so deleting a user made PostgreSQL rewrite the audit
rows that named that user. Rewriting is an UPDATE, and UPDATE is what
append-only withholds - so deleting a user failed with "permission denied for
table phi_audit_logs". The foreign keys are gone for that reason: the
identifier stays in the column as the historical fact it is.

The guarantee is a role-level one, so it is checked as a role that does not
bypass row level security. A superuser bypasses RLS by definition, and the
CI database is owned by one, so a test that connects as the owner would be
asserting that a superuser is prevented from editing a table - which is
false, and which PostgreSQL does not intend to make true.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from app.extensions import db
from models.audit_trail import AuditTrail


def _restricted_connection():
    """A connection to the same database as a role that does not bypass RLS.

    Skips when the database user is a superuser: PostgreSQL does not apply
    row level security to a superuser or a BYPASSRLS role, so the checks
    below would be asserting about a privilege the superuser keeps.
    """
    url = (
        os.environ.get('RLS_TEST_DATABASE_URL')
        or os.environ.get('TEST_DATABASE_URL')
        or os.environ.get('DATABASE_URL')
    )
    if not url or not url.startswith('postgresql'):
        pytest.skip('PostgreSQL required for the append-only checks')
    import psycopg2

    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        cur.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user')
        row = cur.fetchone()
        if row and (row[0] or row[1]):
            conn.close()
            pytest.skip('The database user bypasses row level security')
    return conn


def _write_row(tenant_id: int, user_id: int | None = None) -> int:
    row = AuditTrail(
        tenant_id=tenant_id,
        user_id=user_id,
        action='update',
        entity_type='visit',
        entity_id=1,
        description='a record of something that happened',
    )
    db.session.add(row)
    db.session.commit()
    return row.id


def _attempt(conn, statement: str, params: dict):
    """Run a write as the restricted role and report what happened.

    Two mechanisms enforce the guarantee, and which one is in force depends
    on the deployment: the role may not hold the privilege at all, or it may
    hold the privilege and be stopped by the row level policy. Both are
    correct answers, and the test is about the outcome - the row does not
    change and it does not go away - rather than about which one did it.
    """
    with conn.cursor() as cur:
        cur.execute('SET app.tenant_id = %(tenant_id)s', params)
        conn.commit()
        try:
            cur.execute(statement, params)
            affected = cur.rowcount
            conn.commit()
            return 'applied', affected
        except Exception as exc:  # noqa: BLE001 - the refusal is the point
            conn.rollback()
            return 'refused', str(exc)


def test_an_audit_row_cannot_be_edited(app, test_tenant):
    """The row that is written is the row that stays."""
    from tests.tenant_context import ensure_test_user

    doctor = ensure_test_user(db, test_tenant, username='e2e_append_only_doc', role='doctor')
    db.session.commit()
    row_id = _write_row(test_tenant.id, doctor.id)

    conn = _restricted_connection()
    try:
        outcome, detail = _attempt(
            conn,
            'UPDATE audit_trails SET description = %(d)s WHERE id = %(i)s',
            {'tenant_id': test_tenant.id, 'd': 'something else entirely', 'i': row_id},
        )
    finally:
        conn.close()

    assert outcome == 'refused' or detail == 0, (
        f'the audit row was editable ({outcome}), so what the trail says is not what happened'
    )
    description = db.session.execute(
        text('SELECT description FROM audit_trails WHERE id = :i'), {'i': row_id}
    ).scalar()
    assert description == 'a record of something that happened'


def test_an_audit_row_cannot_be_removed(app, test_tenant):
    """A row cannot be deleted either.

    The trail is closed to edits at two levels: the role may not hold the
    privilege, and the row level policy refuses the write outright. DELETE is
    the one operation the retention job needs, so it is allowed only when the
    session has declared itself the retention job - and the application never
    does. Without that declaration the delete reaches nothing, which is the
    guarantee: the row is simply not removable.
    """
    row_id = _write_row(test_tenant.id)

    conn = _restricted_connection()
    try:
        outcome, detail = _attempt(
            conn,
            'DELETE FROM audit_trails WHERE id = %(i)s',
            {'tenant_id': test_tenant.id, 'i': row_id},
        )
    finally:
        conn.close()

    assert outcome == 'refused' or detail == 0, (
        f'the audit row could be deleted ({outcome}), so the trail could be made '
        'to say that something never happened'
    )
    still_there = db.session.execute(
        text('SELECT count(*) FROM audit_trails WHERE id = :i'), {'i': row_id}
    ).scalar()
    assert still_there == 1


def test_deleting_a_user_leaves_their_audit_rows_alone(app, test_tenant):
    """The history is not rewritten because somebody left.

    The audit tables referenced the acting user with ON DELETE SET NULL, so
    deleting a user made PostgreSQL rewrite the rows that named them - and
    rewriting needs UPDATE, which append-only withholds. Deleting a user
    therefore failed with "permission denied for table phi_audit_logs". The
    user is deletable now, and the rows that name it stay exactly as they
    were written.
    """
    from models.user import User
    from tests.tenant_context import ensure_test_user

    doctor = ensure_test_user(db, test_tenant, username='e2e_append_only_leaver', role='doctor')
    db.session.commit()
    user_id = doctor.id
    row_id = _write_row(test_tenant.id, user_id)

    db.session.delete(doctor)
    db.session.commit()

    still_there = db.session.execute(
        text('SELECT count(*) FROM audit_trails WHERE id = :i'), {'i': row_id}
    ).scalar()
    assert still_there == 1, 'the audit row was removed when its user was deleted'

    gone = db.session.execute(
        text('SELECT count(*) FROM users WHERE id = :i'), {'i': user_id}
    ).scalar()
    assert gone == 0, 'the user was not deleted'

    # The row still names the user id it was written with.
    named = db.session.execute(
        text('SELECT user_id FROM audit_trails WHERE id = :i'), {'i': row_id}
    ).scalar()
    assert named == user_id
    assert not isinstance(named, User)


def test_the_retention_flag_does_not_outlive_the_pruning(app, test_tenant):
    """The purge's permission is not left behind when it is finished.

    The retention job is allowed to remove the rows past the retention
    window, and it says so with a session setting. The setting belongs to
    the transaction that did the pruning: a plain SET outlives the
    transaction, so every later write on that session - a write from the
    application, hours later - was still allowed to delete from the trail.
    """
    from tasks.system_tasks import _purge_old_audit_logs

    _purge_old_audit_logs()

    value = db.session.execute(text("SELECT current_setting('app.audit_purge', true)")).scalar()
    assert value is None or value == '', (
        'the retention flag survived the purge, so the session stayed the '
        'retention job for everything that followed'
    )
