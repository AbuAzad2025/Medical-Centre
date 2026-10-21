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

These cases check both halves. They write a row, try to change it and try to
remove it, and check that the database refuses. Then they delete a user who
owns audit rows, and check that the rows are still there.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.extensions import db
from models.audit_trail import AuditTrail


def _write_row(tenant_id: int, user_id: int | None = None) -> int:
    row = AuditTrail(
        tenant_id=tenant_id,
        user_id=user_id,
        action='update',
        entity_type='visit',
        entity_id='1',
        description='a record of something that happened',
    )
    db.session.add(row)
    db.session.commit()
    return row.id


def test_an_audit_row_cannot_be_edited(app, test_tenant):
    """The row that is written is the row that stays."""
    from tests.tenant_context import ensure_test_user

    doctor = ensure_test_user(db, test_tenant, username='e2e_append_only_doc', role='doctor')
    db.session.commit()
    row_id = _write_row(test_tenant.id, doctor.id)

    with pytest.raises(Exception) as excinfo:
        db.session.execute(
            text('UPDATE audit_trails SET description = :d WHERE id = :i'),
            {'d': 'something else entirely', 'i': row_id},
        )
        db.session.commit()
    db.session.rollback()

    assert 'permission denied' in str(excinfo.value).lower(), (
        'the audit row was editable, so what the trail says is not what happened'
    )
    description = db.session.execute(
        text('SELECT description FROM audit_trails WHERE id = :i'), {'i': row_id}
    ).scalar()
    assert description == 'a record of something that happened'


def test_an_audit_row_cannot_be_removed(app, test_tenant):
    """A row cannot be deleted either."""
    row_id = _write_row(test_tenant.id)

    with pytest.raises(Exception) as excinfo:
        db.session.execute(text('DELETE FROM audit_trails WHERE id = :i'), {'i': row_id})
        db.session.commit()
    db.session.rollback()

    assert 'permission denied' in str(excinfo.value).lower(), (
        'the audit row could be deleted, so the trail could be made to say '
        'that something never happened'
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
