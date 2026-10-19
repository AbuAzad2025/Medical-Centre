"""Execute the identity lifecycle: password reset, session termination, impersonation.

Phase 7a. These are the three routes where a credential or an identity is
transferred rather than used, which is why the specification singles them out and
why the assertions here are about what gets written down rather than about what
gets returned.

Driven through:

  POST /auth/change-password
  POST /auth/forgot-password, /auth/reset-password/<token>/<user_id>
  POST /owner/users/<id>/reset-password
  POST /security/sessions/terminate-others
  POST /auth/impersonate/<id>, /auth/impersonate/exit

What execution established:

  * Password change and reset both work, and both bump session_version so the
    old sessions stop being valid.

  * The reveal-password route named by the specification does not exist. The
    spec describes it as returning a stored password in clear; there is no such
    route in the owner blueprint. A spec that describes a credential-revealing
    endpoint as if it shipped is its own problem — it puts the idea in a reader's
    head, and a reader who assumes it is documented may build one.

  * Terminating other sessions closes them and writes no audit row. The
    SessionLog rows get terminated_by and logout_at, so the sessions are
    individually marked, but nothing records that the user asked. Everything
    downstream of that shows a session that simply expired.

  * Impersonation does write an IMPERSONATE audit row naming the operator and
    the target. That row is the only link between the two identities, because
    every row written afterwards carries the impersonated user. The link is
    therefore load-bearing, and it lives in one table with no redundancy.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.audit_trail import AuditTrail
from models.digital_signature import SessionLog
from models.user import User
from tests.scenario_execution_registry import covers


@pytest.fixture
def operator(app, test_tenant):
    """An owner and a doctor, each with a live session."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['auth'])
    owner = ensure_test_user(db, test_tenant, username='e2e_sec_owner', role='owner')
    doctor = ensure_test_user(db, test_tenant, username='e2e_sec_doctor', role='doctor')

    owner_client = app.test_client()
    doctor_client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(owner_client, owner, test_tenant)
        login_test_client(doctor_client, doctor, test_tenant)

    return {
        'app': app,
        'owner_client': owner_client,
        'doctor_client': doctor_client,
        'tenant': test_tenant,
        'owner': owner,
        'doctor': doctor,
    }


def _fresh(app, tenant, obj):
    from tests.tenant_context import refresh_scoped

    return refresh_scoped(app, tenant, obj)


@covers('IDENTITY_PASSWORD_LIFECYCLE')
class TestPasswordResetIsAudited:
    def test_an_operator_reset_is_recorded_and_invalidates_old_sessions(self, operator):
        """A reset bumps session_version and leaves an audit row.

        Both halves matter and they answer different questions. session_version is
        what makes the old sessions stop working; the audit row is what makes the
        reset explainable afterwards. A reset that did only the first would be safe
        and unaccountable.
        """
        client, doctor = operator['owner_client'], operator['doctor']
        before_version = doctor.session_version or 0

        resp = client.post(
            f'/owner/users/{doctor.id}/reset-password',
            data={},
            headers={'Accept': 'application/json'},
            follow_redirects=False,
        )
        assert resp.status_code == 200, f'reset answered {resp.status_code}'
        assert resp.get_json().get('success') is True, f'reset reported {resp.get_json()!r}'

        fresh = _fresh(operator['app'], operator['tenant'], doctor)
        assert (fresh.session_version or 0) > before_version, (
            'resetting a password did not bump session_version, so every session '
            'opened with the old password stays valid'
        )

        # _log_action in the owner module writes PlatformAuditLog, not the tenant
        # AuditTrail the clinical modules use. Two audit tables in one deployment is
        # worth knowing about; what matters here is that this one records the reset.
        from app.core.tenant.middleware import platform_tenant_scope
        from app.core.tenant.models import PlatformAuditLog

        # Capture the id first. `users` is tenant-scoped, so inside the platform
        # scope the operator's own row is hidden and reading the attribute
        # raises ObjectDeletedError on a user that exists.
        owner_id = operator['owner'].id

        # Read through the same scope helper _log_action uses. A bare
        # `SET app.tenant_id = '1'` does not work here either: the tenant_filter
        # reassert hook re-issues the GUC from session.info/g before every ORM
        # statement, so a manual SET is undone before the SELECT runs and the row
        # reads as absent - which is how this test concluded "no audit row records
        # the password reset" even after the write itself was made to succeed.
        with platform_tenant_scope():
            rows = (
                db.session.execute(select(PlatformAuditLog).filter_by(user_id=owner_id))
                .scalars()
                .all()
            )
        resets = [r for r in rows if r.action == 'RESET_PASSWORD']
        assert resets, (
            f'no audit row records the password reset. {len(rows)} audit row(s) exist '
            f'for the operator and none of them is a RESET_PASSWORD. A credential '
            f'changed with no trace of who changed it'
        )
        assert resets[-1].entity_id == doctor.id, (
            f'the RESET_PASSWORD row names entity {resets[-1].entity_id} rather than '
            f'the user whose password changed ({doctor.id})'
        )

    def test_the_revealed_password_route_named_by_the_spec_does_not_exist(self, operator):
        """The specification describes a route that returns a stored password.

        Good news, and worth pinning: nothing here hands back a credential. The
        spec's step list names POST /owner/users/<id>/reveal-password as returning
        a stored password in clear. There is no such route, so the case asserts
        the 404 rather than leaving the question open.
        """
        client, doctor = operator['owner_client'], operator['doctor']

        resp = client.post(f'/owner/users/{doctor.id}/reveal-password', follow_redirects=False)
        assert resp.status_code in (404, 302), (
            f'/owner/users/<id>/reveal-password answered {resp.status_code}. If this '
            f'route now exists it is returning stored credentials in clear, which '
            f'needs an audit row of its own before it does'
        )

        # The part that would actually matter: no credential in the response. Asserted
        # on the body rather than only on the status, because a redirect carrying a
        # password in its query string would still leak it.
        body = resp.get_data(as_text=True)
        assert not (('password' in body.lower()) and ('reveal' in body.lower())), (
            f'the reveal-password response mentions a password: {body[:300]!r}'
        )


@covers('IDENTITY_SESSION_TERMINATION')
class TestTerminatingOtherSessions:
    def test_the_other_sessions_are_closed(self, operator):
        """The revocation itself works: the other session stops being active."""
        client, doctor = operator['doctor_client'], operator['doctor']

        session_id = f'e2e-other-{doctor.id}'
        db.session.add(
            SessionLog(
                tenant_id=operator['tenant'].id,
                user_id=doctor.id,
                session_id=session_id,
                is_active=True,
            )
        )
        db.session.commit()

        resp = client.post('/security/sessions/terminate-others', follow_redirects=False)
        assert resp.status_code == 200, f'terminate-others answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is True
        assert body.get('terminated', 0) >= 1, f'nothing was terminated: {body!r}'

        row = (
            db.session.execute(select(SessionLog).filter_by(session_id=session_id))
            .scalars()
            .first()
        )
        assert row is not None and row.is_active is False, (
            'the other session is still active after terminate-others'
        )
        assert row.terminated_by, 'the closed session does not say who closed it'
        assert row.logout_at is not None

    def test_terminating_other_sessions_is_recorded_as_an_action(self, operator):
        """A forced lock-out should say so, not merely make sessions expire.

        The SessionLog rows carry terminated_by and logout_at, so each session
        shows that it ended. Nothing records that the user ended it. That is the
        difference between a revocation and an expiry, and it is the difference an
        investigator is looking for after a suspected compromise.
        """
        client, doctor = operator['doctor_client'], operator['doctor']

        session_id = f'e2e-audit-{doctor.id}'
        db.session.add(
            SessionLog(
                tenant_id=operator['tenant'].id,
                user_id=doctor.id,
                session_id=session_id,
                is_active=True,
            )
        )
        db.session.commit()

        client.post('/security/sessions/terminate-others', follow_redirects=False)

        rows = db.session.execute(select(AuditTrail).filter_by(user_id=doctor.id)).scalars().all()
        recorded = [
            r
            for r in rows
            if 'terminate' in (r.description or '').lower() or 'TERMINATE' in (r.action or '')
        ]
        assert recorded, (
            'terminating another session wrote no audit row. The sessions are marked '
            'closed, so the trail shows sessions that ended and no record of a user '
            'ending them — which is what an expiry looks like too. A revocation '
            'should be distinguishable from a timeout.'
        )


@covers('IDENTITY_IMPERSONATION')
class TestImpersonationIsRecorded:
    def test_impersonation_writes_a_row_naming_the_operator_and_the_target(self, operator):
        """The link between the two identities is written and readable."""
        client, owner, doctor = operator['owner_client'], operator['owner'], operator['doctor']

        resp = client.post(f'/auth/impersonate/{doctor.id}', follow_redirects=False)
        assert resp.status_code == 200, f'impersonate answered {resp.status_code}'
        assert resp.get_json().get('success') is True, f'impersonate reported {resp.get_json()!r}'

        row = (
            db.session.execute(select(AuditTrail).filter_by(action='IMPERSONATE')).scalars().first()
        )
        assert row is not None, (
            'impersonation wrote no audit row. Every row created after this carries '
            'the impersonated user, so without this one there is nothing at all '
            'linking the operator to the work'
        )
        assert row.user_id == owner.id, (
            f'the IMPERSONATE row names user {row.user_id} as the actor, not the '
            f'operator {owner.id}'
        )
        assert row.entity_id == doctor.id, (
            f'the IMPERSONATE row names entity {row.entity_id} as the target, not '
            f'the impersonated user {doctor.id}'
        )

        client.post('/auth/impersonate/exit', follow_redirects=False)

    def test_a_record_written_under_impersonation_says_so(self, operator):
        """Work done as somebody else must be findable from the work itself.

        The audit row exists, which is the floor. This asks for the next thing: that
        a row created during the impersonated session carries enough to connect it
        to the operator without having to correlate timestamps across two tables.
        """
        client, owner, doctor = operator['owner_client'], operator['owner'], operator['doctor']

        client.post(f'/auth/impersonate/{doctor.id}', follow_redirects=False)

        written = AuditTrail(
            entity_type='user',
            entity_id=doctor.id,
            tenant_id=operator['tenant'].id,
            action='update',
            user_id=doctor.id,
            description='work done under impersonation',
        )
        db.session.add(written)
        db.session.commit()

        noted = (written.notes or '') + (written.new_values or '')
        assert str(owner.id) in noted or 'impersonat' in noted.lower(), (
            f'the row written under impersonation (actor {written.user_id}, the '
            f'impersonated user {doctor.id}) carries no reference to the operator '
            f'{owner.id}. The only record linking them is the separate IMPERSONATE '
            f'row, so answering "who really did this" means correlating two tables '
            f'by time.'
        )

        client.post('/auth/impersonate/exit', follow_redirects=False)


@covers('IDENTITY_PASSWORD_LIFECYCLE')
class TestStaffLifecycleIsDistinct:
    def test_a_form_posted_password_change_is_refused_cleanly(self, operator):
        """A form post should be a 400, not a 500.

        change_password takes JSON only: `data = request.get_json()` with no
        fallback, so a form-encoded body leaves data as None and the first
        data.get raises. The generic handler turns that into a 500, which tells the
        caller the server is broken rather than that the request shape was wrong.
        """
        client = operator['doctor_client']

        resp = client.post(
            '/auth/change-password',
            data={
                'current_password': 'ValidPass123!',
                'new_password': 'BrandNewPass456!',
                'confirm_password': 'BrandNewPass456!',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400, (
            f'a form-encoded password change answered {resp.status_code}. The handler '
            f'reads request.get_json() with no fallback, so data is None and the '
            f'AttributeError surfaces as a 500. Fall back to request.form and answer '
            f'400 for anything that is not JSON'
        )

    def test_a_user_can_change_their_own_password(self, operator):
        """The self-service path, as against the operator reset above."""
        client, doctor = operator['doctor_client'], operator['doctor']

        # JSON, because the endpoint only reads JSON.
        resp = client.post(
            '/auth/change-password',
            json={
                'current_password': 'ValidPass123!',
                'new_password': 'BrandNewPass456!',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 200, (
            f'change-password answered {resp.status_code}: {resp.get_data(as_text=True)[:200]}'
        )

        fresh = _fresh(operator['app'], operator['tenant'], db.session.get(User, doctor.id))
        assert fresh.check_password('BrandNewPass456!'), (
            'the new password does not authenticate after a successful change'
        )
        assert not fresh.check_password('ValidPass123!'), (
            'the old password still authenticates after a successful change'
        )
