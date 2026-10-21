"""The credential audit rows have to reach the database.

The application writes an audit row when a password changes and when other
sessions are revoked. The schema forbade those actions, so every write was
refused with a CheckViolation - and the handler around it swallowed the
failure. The trail said nothing about the credential change, which is the one
thing an investigator looks for.

These cases write the rows the application writes, against the schema the
migrations produce, and check they are there afterwards.
"""

from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from models.audit_trail import AuditTrail


def _audit_rows(**filters):
    return db.session.execute(select(AuditTrail).filter_by(**filters)).scalars().all()


def test_a_password_change_audit_row_is_written(app, test_tenant):
    """A credential change leaves a row naming who changed it."""
    from tests.tenant_context import ensure_test_user

    doctor = ensure_test_user(db, test_tenant, username='e2e_audit_doc', role='doctor')

    db.session.add(
        AuditTrail(
            entity_type='user',
            entity_id=doctor.id,
            tenant_id=test_tenant.id,
            action='PASSWORD_CHANGE',
            user_id=doctor.id,
            description='تغيير كلمة المرور بواسطة المستخدم',
        )
    )
    db.session.commit()

    rows = _audit_rows(action='PASSWORD_CHANGE', entity_id=doctor.id)
    assert len(rows) == 1, (
        'the password-change audit row was not persisted; the schema refused the '
        'action and the write was swallowed, so a credential change left no trail'
    )
    assert rows[0].user_id == doctor.id
    assert rows[0].tenant_id == test_tenant.id


def test_a_session_revocation_audit_row_is_written(app, test_tenant):
    """A session revocation leaves a row naming the user and the sessions."""
    from tests.tenant_context import ensure_test_user

    doctor = ensure_test_user(db, test_tenant, username='e2e_audit_doc2', role='doctor')

    db.session.add(
        AuditTrail(
            entity_type='user_session',
            entity_id=doctor.id,
            tenant_id=test_tenant.id,
            action='TERMINATE_OTHER_SESSIONS',
            user_id=doctor.id,
            description='إنهاء الجلسات النشطة',
        )
    )
    db.session.commit()

    rows = _audit_rows(action='TERMINATE_OTHER_SESSIONS', entity_id=doctor.id)
    assert len(rows) == 1, (
        'the session-revocation audit row was not persisted; a revocation left '
        'no record that anyone asked for it'
    )
    assert rows[0].entity_type == 'user_session'
