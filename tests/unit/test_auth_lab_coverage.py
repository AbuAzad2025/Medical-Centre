"""
Coverage for AUTH and LAB route modules.

Targets: routes/auth_routes.py, routes/compliance_routes.py,
routes/backup_routes.py and the routes/lab/* package.

These tests exercise the real HTTP surface (Flask test client against the
migrated test schema). Writes go through ``rollback_db`` so the session-scoped
test database stays pristine; external side effects (pg_dump subprocesses,
SMTP, WhatsApp, HIBP) are replaced with explicit fakes whose behaviour the
tests assert on. When pg_dump/psql are absent from the environment, the
backup tests assert the real failure contract rather than pretending a dump
succeeded.
"""

from __future__ import annotations

import gzip
import io
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from tests.tenant_context import tenant_test_context


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _login(client, db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role=role, password=password)
    login_test_client(client, user, tenant, password)
    return user


def _make_patient(db, tenant, **kw):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant.id,
        first_name=kw.get('first_name', 'Test'),
        last_name=kw.get('last_name', f'Patient{uuid.uuid4().hex[:6]}'),
        gender=kw.get('gender', 'F'),
        phone=kw.get('phone', f'059{uuid.uuid4().int % 10**7:07d}'),
        national_id=kw.get('national_id', f'NAT-{uuid.uuid4().hex[:8]}'),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _make_lab_request(db, tenant, patient_id, **kw):
    from models.lab_request import LabRequest

    req = LabRequest(
        tenant_id=tenant.id,
        visit_id=kw.get('visit_id'),
        patient_id=patient_id,
        requested_by=kw.get('requested_by'),
        status=kw.get('status', 'REQUESTED'),
        request_number=kw.get('request_number', f'LAB-T-{uuid.uuid4().hex[:10]}'),
        notes=kw.get('notes'),
    )
    db.session.add(req)
    db.session.commit()
    return req


def _make_lab_result(db, tenant, request_id, patient_id, **kw):
    from models.lab_request import LabResult

    res = LabResult(
        tenant_id=tenant.id,
        request_id=request_id,
        patient_id=patient_id,
        performed_by=kw.get('performed_by'),
        test_code=kw.get('test_code', 'HB'),
        test_name=kw.get('test_name', 'Hemoglobin'),
        value=kw.get('value'),
        unit=kw.get('unit'),
        reference_range=kw.get('reference_range'),
        status=kw.get('status', 'PENDING'),
        notes=kw.get('notes'),
        is_critical=kw.get('is_critical', False),
    )
    db.session.add(res)
    db.session.commit()
    return res


# ---------------------------------------------------------------------------
# AUTH: login / logout / profile
# ---------------------------------------------------------------------------
class TestAuthLogin:
    def test_login_get_renders_form_and_sets_csrf_cookie(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        cookie_header = resp.headers.get('Set-Cookie', '')
        assert 'csrf_token=' in cookie_header

    def test_login_get_with_owner_mode(self, client):
        resp = client.get('/auth/login?mode=owner')
        assert resp.status_code == 200

    def test_logout_requires_authentication(self, client):
        resp = client.get('/auth/logout')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_login_json_success(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('logok'), role='doctor')
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['user']['username'] == user.username
        assert data['redirect_url']

    def test_login_form_redirects_to_role_dashboard(
        self, app, client, db, test_tenant, rollback_db
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('formlogin'), role='doctor')
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 302
        # Tenant slug from test_tenant context is prepended for tenant users
        assert resp.headers['Location'].startswith('/t/')

    def test_login_owner_mode_redirects_to_owner_dashboard(
        self, app, client, db, test_tenant, rollback_db
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('ownermode'), role='super_admin')
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!', 'mode': 'owner'},
        )
        assert resp.status_code == 302
        location = resp.headers['Location']
        assert not location.startswith('/t/')
        assert 'owner' in location

    def test_login_json_wrong_password_401(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badpw'), role='reception')
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'WrongPass999!'},
        )
        assert resp.status_code == 401
        assert resp.get_json()['success'] is False

    def test_login_form_wrong_password_renders_200(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badpwform'), role='reception')
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'WrongPass999!'},
        )
        assert resp.status_code == 200

    def test_login_missing_credentials_400(self, app, client, db, test_tenant, rollback_db):
        resp = client.post('/auth/login', json={'username': '', 'password': ''})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_login_form_missing_credentials_renders(self, app, client, test_tenant, rollback_db):
        resp = client.post('/auth/login', data={'username': '', 'password': ''})
        assert resp.status_code == 200

    def test_login_inactive_user_json_403(self, app, client, db, test_tenant, rollback_db):
        from sqlalchemy import update

        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('inact'), role='reception')
        db.session.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.session.commit()
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 403

    def test_login_inactive_user_form_renders_200(self, app, client, db, test_tenant, rollback_db):
        from sqlalchemy import update

        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('inactform'), role='reception')
        db.session.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.session.commit()
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 200

    def test_login_lockout_after_repeated_failures_429(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('lockout'), role='reception')
        now = datetime.now(UTC)
        for _ in range(6):
            db.session.add(
                LoginAttempt(
                    tenant_id=test_tenant.id,
                    username=user.username,
                    user_id=user.id,
                    success=False,
                    user_ip='127.0.0.1',
                    created_at=now - timedelta(minutes=1),
                )
            )
        db.session.commit()
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 429
        assert resp.get_json()['success'] is False

    def test_login_lockout_form_variant_429(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('lockoutform'), role='reception')
        now = datetime.now(UTC)
        for _ in range(6):
            db.session.add(
                LoginAttempt(
                    tenant_id=test_tenant.id,
                    username=user.username,
                    user_id=user.id,
                    success=False,
                    user_ip='127.0.0.1',
                    created_at=now - timedelta(minutes=1),
                )
            )
        db.session.commit()
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 429

    def test_login_records_successful_attempt(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        username = _uniq('logreco')
        ensure_test_user(db, test_tenant, username=username, role='doctor')
        client.post(
            '/auth/login',
            json={'username': username, 'password': 'ValidPass123!'},
        )
        rows = (
            db.session.execute(select(LoginAttempt).filter(LoginAttempt.username == username))
            .scalars()
            .all()
        )
        assert any(r.success for r in rows)


class TestTenantsListApi:
    def test_tenants_list_returns_json(self, client):
        resp = client.get('/auth/api/tenants-list')
        assert resp.status_code == 200
        assert 'tenants' in resp.get_json()

    def test_tenants_list_db_error_returns_empty(self, client, monkeypatch):
        import routes.auth_routes as auth_module

        class _BoomSession:
            def execute(self, *args, **kwargs):
                raise RuntimeError('database unavailable')

        class _BoomDb:
            session = _BoomSession()

        # Only the route module's reference is replaced; the tenant middleware
        # keeps the real session object.
        monkeypatch.setattr(auth_module, 'db', _BoomDb())
        resp = client.get('/auth/api/tenants-list')
        assert resp.status_code == 200
        assert resp.get_json() == {'tenants': []}


class TestLogoutAudit:
    def test_logout_writes_audit_trail(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import AuditTrail

        user = _login(client, db, test_tenant, _uniq('logout'), 'reception')
        resp = client.get('/auth/logout')
        assert resp.status_code == 302
        rows = (
            db.session.execute(
                select(AuditTrail).filter(
                    AuditTrail.action == 'logout', AuditTrail.user_id == user.id
                )
            )
            .scalars()
            .all()
        )
        assert rows, 'expected an audit trail row for logout'


class TestProfile:
    def test_profile_get_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('profile'), 'doctor')
        resp = client.get('/auth/profile')
        assert resp.status_code == 200

    def test_profile_requires_login(self, client):
        resp = client.get('/auth/profile')
        assert resp.status_code == 302

    def test_profile_post_updates_fields(self, app, client, db, test_tenant, rollback_db):
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('profpost'), 'doctor')
        resp = client.post(
            '/auth/profile',
            data={
                'full_name': 'Profile Updated Name',
                'phone': '0512345678',
                'email': 'updated-profile@example.com',
                'doctor_room': 'R-42',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.full_name == 'Profile Updated Name'
        assert refreshed.doctor_room == 'R-42'

    def test_profile_post_cannot_escalate_role(self, app, client, db, test_tenant, rollback_db):
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('profrole'), 'reception')
        resp = client.post(
            '/auth/profile',
            data={'full_name': 'Still Reception', 'role': 'super_admin'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.role == 'reception'

    def test_profile_post_signature_upload_stores_data_uri(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('profsig'), 'doctor')
        data = {
            'full_name': 'Signed Name',
            'signature': (io.BytesIO(b'\x89PNG-fake-image-bytes'), 'sig.png'),
        }
        resp = client.post(
            '/auth/profile',
            data=data,
            content_type='multipart/form-data',
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.digital_signature.startswith('data:')
        assert 'base64,' in refreshed.digital_signature


class TestChangePassword:
    def test_change_password_requires_json_body(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpjson'), 'reception')
        resp = client.post(
            '/auth/change-password',
            data='current_password=a&new_password=b',
            content_type='text/plain',
        )
        assert resp.status_code == 400

    def test_change_password_empty_json_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpemp'), 'reception')
        resp = client.post('/auth/change-password', json={})
        assert resp.status_code == 400

    def test_change_password_missing_fields_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpmiss'), 'reception')
        resp = client.post('/auth/change-password', json={'current_password': 'x'})
        assert resp.status_code == 400

    def test_change_password_confirm_mismatch_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpconf'), 'reception')
        resp = client.post(
            '/auth/change-password',
            json={
                'current_password': 'ValidPass123!',
                'new_password': 'NewStrong123!',
                'confirm_password': 'Different123!',
            },
        )
        assert resp.status_code == 400
        assert resp.get_json()['message'], 'expected a non-empty mismatch message'

    def test_change_password_wrong_current_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpwrong'), 'reception')
        resp = client.post(
            '/auth/change-password',
            json={'current_password': 'NotThePassword!', 'new_password': 'NewStrong123!'},
        )
        assert resp.status_code == 400

    def test_change_password_success_bumps_session_version_and_audits(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.audit_trail import AuditTrail
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('cpok'), 'reception')
        before = int(user.session_version or 0)
        resp = client.post(
            '/auth/change-password',
            json={
                'current_password': 'ValidPass123!',
                'new_password': 'BrandNew123!',
                'confirm_password': 'BrandNew123!',
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert int(refreshed.session_version or 0) == before + 1
        assert refreshed.check_password('BrandNew123!')
        rows = (
            db.session.execute(
                select(AuditTrail).filter(
                    AuditTrail.action == 'PASSWORD_CHANGE',
                    AuditTrail.user_id == user.id,
                )
            )
            .scalars()
            .all()
        )
        assert rows, 'expected PASSWORD_CHANGE audit row'

    def test_change_password_invalidates_existing_session(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('cpinv'), 'reception')
        resp = client.post(
            '/auth/change-password',
            json={'current_password': 'ValidPass123!', 'new_password': 'BrandNew123!'},
        )
        assert resp.status_code == 200
        # The session cookie still carries the old session_version, so the
        # user_loader rejects it and the next protected page redirects.
        profile = client.get('/auth/profile')
        assert profile.status_code == 302
        assert '/auth/login' in profile.headers['Location']


class TestForgotPassword:
    def test_forgot_password_get_renders(self, client):
        resp = client.get('/auth/forgot-password')
        assert resp.status_code == 200
        assert 'csrf_token=' in resp.headers.get('Set-Cookie', '')

    def test_forgot_password_missing_identifier_400(self, app, client, test_tenant, rollback_db):
        resp = client.post('/auth/forgot-password', json={'identifier': ''})
        assert resp.status_code == 400

    def test_forgot_password_unknown_identifier_still_200(
        self, app, client, test_tenant, rollback_db
    ):
        resp = client.post('/auth/forgot-password', json={'identifier': _uniq('nouser')})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_forgot_password_sends_mail_and_stores_token(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('fpmail'), role='reception')

        class _FakeMail:
            def __init__(self):
                self.sent = []

            def send(self, message):
                self.sent.append(message)

        fake_mail = _FakeMail()
        monkeypatch.setattr('app.extensions.mail', fake_mail)

        resp = client.post('/auth/forgot-password', json={'identifier': user.username})
        assert resp.status_code == 200
        assert len(fake_mail.sent) == 1
        message = fake_mail.sent[0]
        assert user.email in message.recipients
        assert 'reset-password' in (message.html or '')

        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        prefs = refreshed.preferences or {}
        assert prefs.get('password_reset_token')
        assert prefs.get('password_reset_expires')

    def test_forgot_password_finds_user_by_email_case_insensitive(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('fpemail'), role='reception')

        class _FakeMail:
            def __init__(self):
                self.sent = []

            def send(self, message):
                self.sent.append(message)

        fake_mail = _FakeMail()
        monkeypatch.setattr('app.extensions.mail', fake_mail)

        resp = client.post('/auth/forgot-password', json={'identifier': user.email.upper()})
        assert resp.status_code == 200
        assert len(fake_mail.sent) == 1

    def test_forgot_password_mail_failure_falls_back_to_whatsapp(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(
            db,
            test_tenant,
            username=_uniq('fpwa'),
            role='reception',
            phone='0598123456',
        )

        class _BoomMail:
            def send(self, message):
                raise RuntimeError('SMTP unreachable')

        class _FakeWhatsApp:
            def __init__(self):
                self.sent = []

            def send_message(self, to, body):
                self.sent.append({'to': to, 'body': body})

        fake_wa = _FakeWhatsApp()
        monkeypatch.setattr('app.extensions.mail', _BoomMail())
        monkeypatch.setattr('app.integrations.whatsapp.service.WhatsAppService', lambda: fake_wa)

        resp = client.post('/auth/forgot-password', json={'identifier': user.username})
        assert resp.status_code == 200
        assert len(fake_wa.sent) == 1
        assert user.phone == fake_wa.sent[0]['to']

    def test_forgot_password_inactive_user_sends_nothing(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from sqlalchemy import update

        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('fpdead'), role='reception')
        db.session.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.session.commit()

        class _FakeMail:
            def __init__(self):
                self.sent = []

            def send(self, message):
                self.sent.append(message)

        fake_mail = _FakeMail()
        monkeypatch.setattr('app.extensions.mail', fake_mail)

        resp = client.post('/auth/forgot-password', json={'identifier': user.username})
        assert resp.status_code == 200
        assert fake_mail.sent == []
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert (refreshed.preferences or {}).get('password_reset_token') is None


class TestResetTokenHelpers:
    def test_generate_token_is_urlsafe_and_unique(self, app):
        with app.app_context():
            from routes.auth_routes import _generate_reset_token

            t1, t2 = _generate_reset_token(), _generate_reset_token()
            assert len(t1) >= 32
            assert t1 != t2

    def test_verify_reset_token_unknown_user(self, app, db, test_tenant, rollback_db):
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(999999999, 'whatever') is False

    def test_verify_reset_token_no_preferences(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('ntok'), role='reception')
        assert user.preferences is None
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'tok') is False

    def test_verify_reset_token_malformed_expiry(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badtok'), role='reception')
        user.preferences = {
            'password_reset_token': 'tok_abc',
            'password_reset_expires': 'not-a-date',
        }
        db.session.commit()
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'tok_abc') is False

    def test_store_and_clear_roundtrip(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('roundtrip'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import (
                _clear_reset_token,
                _store_reset_token,
                _verify_reset_token,
            )

            expires = datetime.now(UTC) + timedelta(hours=1)
            _store_reset_token(user.id, 'roundtrip_tok', expires)
            assert _verify_reset_token(user.id, 'roundtrip_tok') is True
            assert _verify_reset_token(user.id, 'other_tok') is False
            _clear_reset_token(user.id)
            assert _verify_reset_token(user.id, 'roundtrip_tok') is False

    def test_stored_token_actually_lands_in_db(self, app, db, test_tenant, rollback_db):
        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('storead'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            expires = datetime.now(UTC) + timedelta(hours=1)
            _store_reset_token(user.id, 'persisted_tok', expires)
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.preferences['password_reset_token'] == 'persisted_tok'


class TestResetPassword:
    def _issue_token(self, app, user, expires_in=timedelta(hours=1), tenant=None):
        from tests.tenant_context import ensure_default_test_tenant

        tenant = tenant or ensure_default_test_tenant(app)
        with tenant_test_context(app, tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{uuid.uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + expires_in)
            return token

    def test_reset_password_invalid_token_redirects(self, app, client, test_tenant, rollback_db):
        resp = client.get('/auth/reset-password/notatoken/12345')
        assert resp.status_code == 302
        assert 'forgot-password' in resp.headers['Location']

    def test_reset_password_expired_token_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('exptok'), role='reception')
        token = self._issue_token(app, user, expires_in=timedelta(hours=-2))
        resp = client.get(f'/auth/reset-password/{token}/{user.id}')
        assert resp.status_code == 302
        assert 'forgot-password' in resp.headers['Location']

    def test_reset_password_get_renders_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetget'), role='reception')
        token = self._issue_token(app, user)
        resp = client.get(f'/auth/reset-password/{token}/{user.id}')
        assert resp.status_code == 200

    def test_reset_password_mismatched_confirmation_400(
        self, app, client, db, test_tenant, rollback_db
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetmm'), role='reception')
        token = self._issue_token(app, user)
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'Other123!'},
        )
        assert resp.status_code == 400

    def test_reset_password_policy_rejects_weak_password(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetweak'), role='reception')
        token = self._issue_token(app, user)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'weak', 'confirm_password': 'weak'},
        )
        assert resp.status_code == 400
        assert 'at least' in resp.get_json()['message']

    def test_reset_password_success_clears_token_and_bumps_session(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.audit_trail import AuditTrail
        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetok'), role='reception')
        old_version = int(user.session_version or 0)
        token = self._issue_token(app, user)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.check_password('BrandNew123!')
        assert int(refreshed.session_version or 0) == old_version + 1
        prefs = refreshed.preferences or {}
        assert 'password_reset_token' not in prefs

        rows = (
            db.session.execute(
                select(AuditTrail).filter(
                    AuditTrail.action == 'PASSWORD_CHANGE',
                    AuditTrail.user_id == user.id,
                )
            )
            .scalars()
            .all()
        )
        assert rows, 'expected PASSWORD_CHANGE audit row for reset'

    def test_reset_password_csrf_failure_returns_400(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetcsrf'), role='reception')
        token = self._issue_token(app, user)
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code == 400


class TestImpersonation:
    def test_super_admin_can_impersonate_and_exit(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('imp_actor'), 'super_admin')
        subject = _create_user(db, test_tenant, _uniq('imp_target'), 'reception')
        resp = client.post(f'/auth/impersonate/{subject.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

        resp = client.post('/auth/impersonate/exit')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_impersonate_writes_audit_row(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import AuditTrail

        _login(client, db, test_tenant, _uniq('impaud'), 'super_admin')
        subject = _create_user(db, test_tenant, _uniq('impaudsub'), 'reception')
        client.post(f'/auth/impersonate/{subject.id}')
        rows = (
            db.session.execute(
                select(AuditTrail).filter(
                    AuditTrail.action == 'IMPERSONATE',
                    AuditTrail.entity_id == subject.id,
                )
            )
            .scalars()
            .all()
        )
        assert rows, 'expected IMPERSONATE audit row'

    def test_impersonate_self_rejected(self, app, client, db, test_tenant, rollback_db):
        actor = _login(client, db, test_tenant, _uniq('impself'), 'super_admin')
        resp = client.post(f'/auth/impersonate/{actor.id}')
        assert resp.status_code == 400

    def test_impersonate_unknown_user_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('imp404'), 'super_admin')
        resp = client.post('/auth/impersonate/999999999')
        assert resp.status_code == 404

    def test_impersonate_requires_privileged_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impdeny'), 'reception')
        subject = _create_user(db, test_tenant, _uniq('impdenysub'), 'reception')
        resp = client.post(
            f'/auth/impersonate/{subject.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 403

    def test_impersonate_exit_without_session_400(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impxit'), 'super_admin')
        resp = client.post('/auth/impersonate/exit')
        assert resp.status_code == 400


def _create_user(db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, tenant, username=username, role=role, password=password)


class TestRoleRedirectHelper:
    def test_get_redirect_url_by_role_returns_path(self, app):
        from routes.auth_routes import get_redirect_url_by_role

        url = get_redirect_url_by_role('doctor')
        assert isinstance(url, str)
        assert url.startswith('/')


class TestRegisterRoute:
    def test_register_redirects_to_saas_signup(self, client):
        resp = client.get('/auth/register')
        assert resp.status_code == 302

    def test_register_owner_mode_redirects_to_owner(self, client):
        resp = client.get('/auth/register?mode=owner')
        assert resp.status_code == 302
        assert 'owner' in resp.headers['Location']


# ---------------------------------------------------------------------------
# COMPLIANCE (routes/compliance_routes.py)
# ---------------------------------------------------------------------------
class TestComplianceRBAC:
    def test_audit_summary_requires_privilege(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('rbacrec'), 'reception')
        resp = client.get('/compliance/audit-summary')
        assert resp.status_code == 403

    def test_audit_summary_allows_manager(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('rbacmgr'), 'manager')
        resp = client.get('/compliance/audit-summary')
        assert resp.status_code == 200

    def test_breach_check_blocks_manager(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('mgrbreach'), 'manager')
        resp = client.get('/compliance/breach-check')
        assert resp.status_code == 403

    def test_data_export_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('rbacexp'), 'reception')
        resp = client.get('/compliance/data-export/1')
        assert resp.status_code == 403

    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get('/compliance/audit-summary')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']


class TestAuditSummary:
    def test_audit_summary_counts_24h_window(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import LoginAttempt
        from models.phi_audit_log import PHIAuditLog

        actor = _login(client, db, test_tenant, _uniq('sumadm'), 'super_admin')
        now = datetime.now(UTC)
        for _ in range(3):
            db.session.add(
                LoginAttempt(
                    tenant_id=test_tenant.id,
                    username=_uniq('attempt'),
                    success=False,
                    user_ip='198.51.100.7',
                    created_at=now - timedelta(minutes=10),
                )
            )
        for _ in range(2):
            db.session.add(
                PHIAuditLog(
                    tenant_id=test_tenant.id,
                    actor_id=actor.id,
                    target_model='Patient',
                    target_id=1,
                    action='UPDATE',
                    created_at=now - timedelta(minutes=10),
                )
            )
        db.session.commit()

        resp = client.get('/compliance/audit-summary')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['period'] == '24h'
        assert data['failed_logins'] >= 3
        assert data['phi_access_count'] >= 2
        assert data['unique_phi_users'] >= 1
        assert data['status'] in ('healthy', 'warning')


class TestBreachCheck:
    def test_breach_check_clean_shape(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('breachadm'), 'super_admin')
        resp = client.get('/compliance/breach-check')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['period'] == '1h'
        assert isinstance(data['indicators'], list)
        assert data['breach_detected'] == (len(data['indicators']) > 0)
        assert data['status'] in ('alert', 'clean')

    def test_breach_check_flags_brute_force_ip(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import LoginAttempt

        _login(client, db, test_tenant, _uniq('breachbf'), 'super_admin')
        suspicious_ip = f'203.0.113.{uuid.uuid4().int % 250 + 1}'
        now = datetime.now(UTC)
        for _ in range(6):
            db.session.add(
                LoginAttempt(
                    tenant_id=test_tenant.id,
                    username=_uniq('bf'),
                    success=False,
                    user_ip=suspicious_ip,
                    created_at=now - timedelta(minutes=5),
                )
            )
        db.session.commit()

        resp = client.get('/compliance/breach-check')
        assert resp.status_code == 200
        data = resp.get_json()
        brute_force = [
            i for i in data['indicators'] if i['type'] == 'brute_force' and i['ip'] == suspicious_ip
        ]
        assert brute_force, 'expected a brute_force indicator for the seeded IP'
        assert brute_force[0]['attempts'] == 6
        assert data['breach_detected'] is True

    def test_breach_check_flags_high_volume_phi_access(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.phi_audit_log import PHIAuditLog

        admin = _login(client, db, test_tenant, _uniq('breachhv'), 'admin')
        now = datetime.now(UTC)
        for i in range(101):
            db.session.add(
                PHIAuditLog(
                    tenant_id=test_tenant.id,
                    actor_id=admin.id,
                    target_model='Patient',
                    target_id=i,
                    action='UPDATE',
                    created_at=now - timedelta(minutes=1),
                )
            )
        db.session.commit()

        resp = client.get('/compliance/breach-check')
        assert resp.status_code == 200
        data = resp.get_json()
        high_volume = [
            i
            for i in data['indicators']
            if i['type'] == 'high_volume_access' and i['user_id'] == admin.id
        ]
        assert high_volume, 'expected a high_volume_access indicator'
        assert high_volume[0]['count'] == 101
        assert data['status'] == 'alert'


class TestDataRetention:
    def test_data_retention_reports_policy(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('retadm'), 'super_admin')
        resp = client.get('/compliance/data-retention')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['retention_policy'] == '7 years (HIPAA)'
        assert data['status'] == 'compliant'
        assert 'audit_trail_oldest' in data
        assert 'phi_audit_oldest' in data


class TestEncryptionAtRest:
    @pytest.mark.parametrize(
        'path',
        [
            '/compliance/encryption-at-rest',
            '/compliance/encryption-at-rest-verification',
            '/compliance/encryption_at_rest',
            '/compliance/encryption-verification',
        ],
    )
    def test_encryption_at_rest_variants_return_report(
        self, app, client, db, test_tenant, rollback_db, path
    ):
        _login(client, db, test_tenant, _uniq('encadm'), 'super_admin')
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['records_scanned'], int)
        assert 'patients.national_id' in data['checked_columns']
        assert data['status'] in ('compliant', 'non_compliant')
        assert 'verified_at' in data


class TestAccessControlReview:
    def test_access_control_review_flags_privileged_users(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('acradmin'), 'super_admin')
        resp = client.get('/compliance/access-control-review')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['users'], list)
        assert data['count'] == len(data['users'])
        assert any('privileged_role' in (u.get('reasons') or []) for u in data['users']), (
            'expected at least one privileged user to be flagged'
        )
        assert data['threshold'] == 10

    def test_access_control_review_honours_threshold_parameter(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('acrparam'), 'admin')
        resp = client.get('/compliance/access-control-review?threshold=1')
        assert resp.status_code == 200
        assert resp.get_json()['threshold'] == 1


class TestDataExport:
    def test_data_export_requires_patient_id(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('exp400'), 'doctor')
        resp = client.get('/compliance/data-export')
        assert resp.status_code == 400

    def test_data_export_unknown_patient_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('exp404'), 'doctor')
        resp = client.get('/compliance/data-export/999999999')
        assert resp.status_code == 404

    def test_data_export_full_patient_bundle(self, app, client, db, test_tenant, rollback_db):
        from models.appointment import Appointment
        from models.consent_management import PatientConsent
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from models.patient import PatientAllergy
        from models.visit import Visit

        doctor = _login(client, db, test_tenant, _uniq('expdoc'), 'doctor')
        patient = _make_patient(db, test_tenant)

        now = datetime.now(UTC)
        db.session.add(
            Visit(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                status='OPEN',
                payment_status='PENDING',
                total_amount=0,
                paid_amount=0,
                visit_type='REGULAR',
            )
        )
        db.session.add(
            Appointment(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                starts_at=now + timedelta(days=1),
            )
        )
        db.session.commit()
        visit = (
            db.session.execute(select(Visit).filter(Visit.patient_id == patient.id))
            .scalars()
            .first()
        )

        lab_req = _make_lab_request(db, test_tenant, patient.id, requested_by=doctor.id)
        _make_lab_result(
            db,
            test_tenant,
            lab_req.id,
            patient.id,
            test_code='HB',
            test_name='Hemoglobin',
            value='13.2',
            status='VALIDATED',
        )
        db.session.add(
            Prescription(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                prescription_number=f'RX-{uuid.uuid4().hex[:10]}',
                diagnosis='Checkup',
            )
        )
        db.session.add(
            MedicalRecord(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                visit_id=visit.id,
                title='Annual checkup',
                details='All good',
                created_by=doctor.id,
            )
        )
        db.session.add(
            PatientAllergy(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                allergen='Penicillin',
                severity='high',
            )
        )
        db.session.add(
            PatientConsent(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                consent_type='treatment',
                scope_description='Treatment consent',
                version=1,
                status='granted',
                capture_method='digital_signature',
                recorded_by_user_id=doctor.id,
            )
        )
        db.session.commit()

        resp = client.get(f'/compliance/data-export/{patient.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'exported'
        assert data['patient_id'] == patient.id
        assert data['exported_by'] == doctor.id
        assert data['patient']['id'] == patient.id
        assert len(data['visits']) == 1
        assert len(data['appointments']) == 1
        assert len(data['lab_results']) == 1
        assert len(data['prescriptions']) == 1
        assert len(data['medical_records']) == 1
        assert len(data['allergies']) == 1
        assert len(data['consents']) == 1
        assert 'exported_at' in data


class TestConsentManagementVerification:
    def test_consent_verification_counts_states(self, app, client, db, test_tenant, rollback_db):
        from models.consent_management import PatientConsent

        actor = _login(client, db, test_tenant, _uniq('consadmin'), 'super_admin')
        patient = _make_patient(db, test_tenant)
        now = datetime.now(UTC)

        def _consent(status, expires_at=None, tag=''):
            db.session.add(
                PatientConsent(
                    tenant_id=test_tenant.id,
                    patient_id=patient.id,
                    consent_type=f'treatment{tag}',
                    scope_description='Test consent scope',
                    version=1,
                    status=status,
                    expires_at=expires_at,
                    capture_method='written',
                    recorded_by_user_id=actor.id,
                )
            )

        _consent('granted')
        _consent('granted', expires_at=now - timedelta(days=1), tag='_exp')
        _consent('withdrawn', tag='_wd')
        _consent('pending_review', tag='_pr')
        db.session.commit()

        resp = client.get(f'/compliance/consent-verification?patient_id={patient.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_consents'] == 4
        assert data['active_consents'] == 1
        assert data['expired_consents'] == 1
        assert data['withdrawn_consents'] == 1
        assert data['pending_consents'] == 1
        assert data['status'] == 'review_required'
        assert data['compliant'] is False

    def test_consent_verification_all_granted_is_compliant(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.consent_management import PatientConsent

        actor = _login(client, db, test_tenant, _uniq('consdoc'), 'doctor')
        patient = _make_patient(db, test_tenant)
        db.session.add(
            PatientConsent(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                consent_type='treatment',
                scope_description='Test consent scope',
                version=1,
                status='granted',
                capture_method='written',
                recorded_by_user_id=actor.id,
            )
        )
        db.session.commit()
        resp = client.get(f'/compliance/consent-verification?patient_id={patient.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_consents'] == 1
        assert data['active_consents'] == 1
        assert data['status'] == 'compliant'
        assert data['compliant'] is True


class TestAuditLogRetentionCheck:
    def test_audit_log_retention_reports(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('retadm2'), 'super_admin')
        resp = client.get('/compliance/audit-log-retention')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['retention_period_years'] == 7
        assert data['total_audit_logs'] >= 0
        assert data['logs_older_than_retention_period'] >= 0
        assert data['policy'] == '7 years (HIPAA)'


class TestSoc2Controls:
    ENDPOINTS = {
        '/compliance/soc2/cc1-control-environment': 'CC1',
        '/compliance/soc2/cc2-communication': 'CC2',
        '/compliance/soc2/cc3-risk-assessment': 'CC3',
        '/compliance/soc2/cc4-monitoring': 'CC4',
        '/compliance/soc2/cc5-control-activities': 'CC5',
        '/compliance/soc2/cc6-logical-access': 'CC6',
        '/compliance/soc2/cc7-system-operations': 'CC7',
        '/compliance/soc2/cc8-change-management': 'CC8',
        '/compliance/soc2/cc9-risk-mitigation': 'CC9',
    }

    def test_all_soc2_controls_return_structured_report(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('soc2adm'), 'super_admin')
        for path, control in self.ENDPOINTS.items():
            resp = client.get(path)
            assert resp.status_code == 200, f'{path} -> {resp.status_code}'
            data = resp.get_json()
            assert data['control'] == control
            assert data['control_id'] == control
            assert isinstance(data['checks'], list) and data['checks'], path
            assert isinstance(data['score'], int)
            assert 0 <= data['score'] <= 100
            assert data['status'] in ('compliant', 'review_required')
            assert 'verified_at' in data

    def test_soc2_cc3_exposes_breach_indicators(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('soc2cc3'), 'super_admin')
        resp = client.get('/compliance/soc2/cc3-risk-assessment')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['indicators'], list)
        assert data['breach_detected'] == (len(data['indicators']) > 0)

    def test_soc2_cc5_exposes_role_distribution(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('soc2cc5'), 'super_admin')
        resp = client.get('/compliance/soc2/cc5-control-activities')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['role_distribution'], dict)

    def test_soc2_cc8_reports_migration_version_key(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('soc2cc8'), 'super_admin')
        resp = client.get('/compliance/soc2/cc8-change-management')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'migration_version' in data
        assert 'schema_version' in data

    def test_soc2_requires_authentication(self, client):
        resp = client.get('/compliance/soc2/cc1-control-environment')
        assert resp.status_code == 302

    def test_soc2_score_aggregates_nine_controls(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('soc2sum'), 'super_admin')
        resp = client.get('/compliance/soc2/score')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['total_controls'] == 9
        assert data['passed_controls'] + data['failed_controls'] == 9
        assert 0 <= data['score'] <= 100
        assert len(data['controls']) == 9
        assert len(data['controls_list']) == 9
        assert data['status'] in ('compliant', 'review_required')

    def test_soc2_score_requires_authentication(self, client):
        resp = client.get('/compliance/soc2/score')
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# BACKUP (routes/backup_routes.py)
# ---------------------------------------------------------------------------
class TestBackupAccess:
    def test_dashboard_requires_login(self, client):
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_dashboard_rejects_non_admin_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakrec'), 'reception')
        resp = client.get('/backup/dashboard')
        # super_admin_required redirects non-privileged users to the main page
        assert resp.status_code == 302

    def test_dashboard_renders_for_super_admin(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('baksuper'), 'super_admin')
        resp = client.get('/backup/dashboard')
        assert resp.status_code == 200

    def test_create_page_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakcreate'), 'super_admin')
        resp = client.get('/backup/create')
        assert resp.status_code == 200

    def test_list_page_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('baklist'), 'super_admin')
        resp = client.get('/backup/list')
        assert resp.status_code == 200


def _patch_backup_paths(monkeypatch, tmp_path):
    target = tmp_path / 'backups' / 'test_backup.sql.gz'

    def _fake_build_backup_path(base_dir, backup_name, when=None):
        target.parent.mkdir(parents=True, exist_ok=True)
        return str(target)

    monkeypatch.setattr('routes.backup_routes.build_backup_path', _fake_build_backup_path)
    return target


def _force_sync_backup_path(monkeypatch):
    monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
    monkeypatch.setattr('celery_app.task_always_eager', lambda: False)


def _make_fake_popen(recorded, stdout_bytes, returncode, stderr_bytes=b'dump: connection refused'):
    """Build a fake subprocess.Popen constructor recording argv+env."""

    def _ctor(cmd, env=None, stdout=None, stderr=None):
        recorded.append({'cmd': list(cmd), 'env': env or {}})
        proc = type('FakePopen', (), {})()
        proc.cmd = list(cmd)
        proc.env = env or {}
        proc.stdout = io.BytesIO(stdout_bytes)
        proc.stderr = io.BytesIO(b'' if returncode == 0 else stderr_bytes)
        proc.returncode = returncode

        def _wait(**_kwargs):
            return returncode

        proc.wait = _wait
        proc.poll = lambda: returncode
        proc.kill = lambda: None
        return proc

    return _ctor


class TestBackupCreation:
    def test_sync_backup_success_builds_command_and_marks_completed(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import subprocess
        from types import SimpleNamespace

        from models.backup import Backup

        admin = _login(client, db, test_tenant, _uniq('bakok'), 'super_admin')
        backup_path = _patch_backup_paths(monkeypatch, tmp_path)
        _force_sync_backup_path(monkeypatch)
        monkeypatch.setenv(
            'DATABASE_URL', 'postgresql://dumpuser:dumppass@dbhost.internal:5544/dumpdb'
        )
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)

        recorded = []
        popen = _make_fake_popen(recorded, b'-- mock pg_dump output\nCREATE TABLE t(id int);\n', 0)
        monkeypatch.setattr(
            'services.pg_backup_service.subprocess',
            SimpleNamespace(Popen=popen, PIPE=-1, TimeoutExpired=subprocess.TimeoutExpired),
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/fake/{name}'
        )

        resp = client.post(
            '/backup/create',
            data={
                'backup_name': 'nightly backup',
                'backup_type': 'full',
                'description': 'nightly snapshot',
                'is_encrypted': 'on',
            },
        )
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'COMPLETED'
        assert row.backup_size and row.backup_size > 0
        assert row.is_encrypted is True
        assert row.description == 'nightly snapshot'
        assert row.created_by == admin.id

        # pg_dump was invoked exactly once, with the DSN we pinned
        assert len(recorded) == 1
        cmd = recorded[0]['cmd']
        assert cmd[0] == '/fake/pg_dump'
        assert '--host' in cmd and 'dbhost.internal' in cmd
        assert '--port' in cmd and '5544' in cmd
        assert '--username' in cmd and 'dumpuser' in cmd
        assert '--dbname' in cmd and 'dumpdb' in cmd
        assert '--no-owner' in cmd and '--no-acl' in cmd
        assert recorded[0]['env'].get('PGPASSWORD') == 'dumppass'

        # the artifact really is a gzip stream of the dump bytes
        with gzip.open(backup_path, 'rb') as fh:
            assert fh.read() == b'-- mock pg_dump output\nCREATE TABLE t(id int);\n'

    def test_sync_backup_failure_marks_failed_and_removes_artifact(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import subprocess
        from types import SimpleNamespace

        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakfail'), 'super_admin')
        backup_path = _patch_backup_paths(monkeypatch, tmp_path)
        _force_sync_backup_path(monkeypatch)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://dumpuser:dumppass@dbhost:5432/dumpdb')
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)

        recorded = []
        popen = _make_fake_popen(recorded, b'', 1)
        monkeypatch.setattr(
            'services.pg_backup_service.subprocess',
            SimpleNamespace(Popen=popen, PIPE=-1, TimeoutExpired=subprocess.TimeoutExpired),
        )
        monkeypatch.setattr(
            'services.pg_backup_service._find_executable', lambda name: f'/fake/{name}'
        )

        resp = client.post('/backup/create', data={'backup_name': 'doomed'})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'FAILED'
        assert 'connection refused' in (row.backup_notes or '')
        assert not os.path.exists(backup_path)

    def test_real_environment_without_pg_dump_fails_honestly(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        # No subprocess fakes: with pg_dump missing the row must end FAILED.
        import shutil

        from models.backup import Backup

        if shutil.which('pg_dump'):
            pytest.skip('pg_dump is available here; command construction is covered by fakes')

        _login(client, db, test_tenant, _uniq('bakreal'), 'super_admin')
        _patch_backup_paths(monkeypatch, tmp_path)
        _force_sync_backup_path(monkeypatch)

        resp = client.post('/backup/create', data={'backup_name': 'real_missing_binary'})
        assert resp.status_code == 302

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'FAILED'
        assert 'pg_dump' in (row.backup_notes or '')

    def test_create_queues_when_celery_eager(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakqueue'), 'super_admin')
        backup_path = _patch_backup_paths(monkeypatch, tmp_path)
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: False)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: True)

        queued = []

        def _fake_queue(backup_id, tenant_id=None):
            queued.append({'backup_id': backup_id, 'tenant_id': tenant_id})
            return 'task-123'

        monkeypatch.setattr(queue_service, 'queue_system_backup', _fake_queue)

        resp = client.post('/backup/create', data={'backup_name': 'queued backup'})
        assert resp.status_code == 302
        assert '/backup/dashboard' in resp.headers['Location']

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'IN_PROGRESS'
        assert queued and queued[0]['backup_id'] == row.id
        assert not backup_path.exists()

    def test_create_queue_error_redirects_with_flash(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        import services.backup_queue_service as queue_service
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakqerr'), 'super_admin')
        _patch_backup_paths(monkeypatch, tmp_path)
        monkeypatch.setattr('celery_app.celery_is_enabled', lambda: True)
        monkeypatch.setattr('celery_app.task_always_eager', lambda: False)

        def _boom_queue(backup_id, tenant_id=None):
            raise queue_service.BackupQueueError('celery_not_configured')

        monkeypatch.setattr(queue_service, 'queue_system_backup', _boom_queue)

        resp = client.post('/backup/create', data={'backup_name': 'queue fail backup'})
        assert resp.status_code == 302
        assert 'create' in resp.headers['Location']

        row = (
            db.session.execute(select(Backup).order_by(Backup.id.desc()).limit(1)).scalars().first()
        )
        assert row.backup_status == 'IN_PROGRESS'


class TestBackupRestore:
    def _completed_backup(self, db, tenant, tmp_path, name='restore_source'):
        from models.backup import Backup

        artifact = tmp_path / f'{name}.sql.gz'
        with gzip.open(artifact, 'wb') as fh:
            fh.write(b'SELECT 1;\n')
        row = Backup(
            tenant_id=tenant.id,
            backup_name=name,
            backup_type='full',
            backup_path=str(artifact),
            backup_status='COMPLETED',
            restore_count=0,
        )
        db.session.add(row)
        db.session.commit()
        return row, artifact

    def test_restore_success_increments_counters(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        _login(client, db, test_tenant, _uniq('bakrestore'), 'super_admin')
        row, _artifact = self._completed_backup(db, test_tenant, tmp_path)

        calls = []

        def _fake_restore(path):
            calls.append(path)

        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', _fake_restore)

        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302
        assert calls == [row.backup_path]

        db.session.expire_all()
        from models.backup import Backup

        refreshed = db.session.get(Backup, row.id)
        assert refreshed.restore_count == 1
        assert refreshed.last_restore is not None
        assert refreshed.last_restore_by is not None

    def test_restore_failure_keeps_counters(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from services.pg_backup_service import PgBackupError

        _login(client, db, test_tenant, _uniq('bakresfail'), 'super_admin')
        row, _artifact = self._completed_backup(db, test_tenant, tmp_path, 'restore_fail')

        def _boom(path):
            raise PgBackupError('simulated restore failure')

        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', _boom)

        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302

        db.session.expire_all()
        from models.backup import Backup

        refreshed = db.session.get(Backup, row.id)
        assert refreshed.restore_count == 0

    def test_restore_rejects_non_completed_backup(
        self, app, client, db, test_tenant, rollback_db, monkeypatch, tmp_path
    ):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakpend'), 'super_admin')
        row = Backup(
            tenant_id=test_tenant.id,
            backup_name='pending_one',
            backup_type='full',
            backup_path=str(tmp_path / 'pending_one.sql.gz'),
            backup_status='IN_PROGRESS',
        )
        db.session.add(row)
        db.session.commit()

        called = []
        monkeypatch.setattr('routes.backup_routes.restore_pg_sql_gz', called.append)
        resp = client.post(f'/backup/restore/{row.id}')
        assert resp.status_code == 302
        assert called == []

    def test_restore_missing_backup_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bak404'), 'super_admin')
        resp = client.post('/backup/restore/999999999')
        assert resp.status_code == 404


class TestBackupDownloadAndDelete:
    def test_download_sends_artifact_bytes(
        self, app, client, db, test_tenant, rollback_db, tmp_path
    ):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdl'), 'super_admin')
        payload = b'\x1f\x8b-fake-artifact-bytes'
        artifact = tmp_path / 'download_me.sql.gz'
        artifact.write_bytes(payload)
        row = Backup(
            tenant_id=test_tenant.id,
            backup_name='download_me',
            backup_type='full',
            backup_path=str(artifact),
            backup_status='COMPLETED',
        )
        db.session.add(row)
        db.session.commit()

        resp = client.get(f'/backup/download/{row.id}')
        assert resp.status_code == 200
        assert resp.data == payload
        assert 'download_me' in (resp.headers.get('Content-Disposition') or '')

    def test_download_missing_file_redirects(
        self, app, client, db, test_tenant, rollback_db, tmp_path
    ):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdlmiss'), 'super_admin')
        row = Backup(
            tenant_id=test_tenant.id,
            backup_name='ghost',
            backup_type='full',
            backup_path=str(tmp_path / 'does_not_exist.sql.gz'),
            backup_status='COMPLETED',
        )
        db.session.add(row)
        db.session.commit()
        resp = client.get(f'/backup/download/{row.id}')
        assert resp.status_code == 302

    def test_download_missing_row_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakdl404'), 'super_admin')
        resp = client.get('/backup/download/999999999')
        assert resp.status_code == 404

    def test_delete_removes_file_and_row(self, app, client, db, test_tenant, rollback_db, tmp_path):
        from models.backup import Backup

        _login(client, db, test_tenant, _uniq('bakdel'), 'super_admin')
        artifact = tmp_path / 'delete_me.sql.gz'
        artifact.write_bytes(b'data')
        row = Backup(
            tenant_id=test_tenant.id,
            backup_name='delete_me',
            backup_type='full',
            backup_path=str(artifact),
            backup_status='COMPLETED',
        )
        db.session.add(row)
        db.session.commit()
        row_id = row.id

        resp = client.post(f'/backup/delete/{row_id}')
        assert resp.status_code == 302
        assert not artifact.exists()
        assert db.session.get(Backup, row_id) is None

    def test_delete_missing_row_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('bakdel404'), 'super_admin')
        resp = client.post('/backup/delete/999999999')
        assert resp.status_code == 404


class TestPgRestoreServiceContract:
    """Command construction for the psql restore helper, no DB touched."""

    def _write_dump(self, tmp_path, name='service.sql.gz', payload=b'SELECT 1;\n'):
        artifact = tmp_path / name
        with gzip.open(artifact, 'wb') as fh:
            fh.write(payload)
        return artifact

    def test_restore_invokes_psql_with_safe_flags(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        import services.pg_backup_service as svc

        artifact = self._write_dump(tmp_path)
        monkeypatch.setenv(
            'DATABASE_URL', 'postgresql://restoreuser:restorepass@restoredb:5544/restoredb_name'
        )
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)

        calls = []

        def _fake_run(cmd, env=None, input=None, capture_output=None, check=None):
            calls.append({'cmd': list(cmd), 'env': env, 'input': input})
            return SimpleNamespace(returncode=0, stderr=b'', stdout=b'')

        monkeypatch.setattr(svc, '_find_executable', lambda name: f'/fake/{name}')
        monkeypatch.setattr(svc, 'subprocess', SimpleNamespace(run=_fake_run))

        svc.restore_pg_sql_gz(str(artifact))

        assert len(calls) == 1
        cmd = calls[0]['cmd']
        assert cmd[0] == '/fake/psql'
        assert '--dbname' in cmd and 'restoredb_name' in cmd
        assert '--port' in cmd and '5544' in cmd
        assert '--host' in cmd and 'restoredb' in cmd
        assert '--username' in cmd and 'restoreuser' in cmd
        assert '--single-transaction' in cmd
        assert 'ON_ERROR_STOP=1' in cmd
        assert calls[0]['env'].get('PGPASSWORD') == 'restorepass'
        assert calls[0]['input'] == b'SELECT 1;\n'

    def test_restore_raises_on_psql_failure(self, tmp_path, monkeypatch):
        from types import SimpleNamespace

        import pytest as _pytest

        import services.pg_backup_service as svc

        artifact = self._write_dump(tmp_path, 'fail.sql.gz')
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:5432/d')
        monkeypatch.delenv('SQLALCHEMY_DATABASE_URI', raising=False)
        monkeypatch.setattr(svc, '_find_executable', lambda name: f'/fake/{name}')
        monkeypatch.setattr(
            svc,
            'subprocess',
            SimpleNamespace(
                run=lambda *_a, **_k: SimpleNamespace(
                    returncode=3, stderr=b'psql: boom', stdout=b''
                )
            ),
        )

        with _pytest.raises(svc.PgBackupError):
            svc.restore_pg_sql_gz(str(artifact))

    def test_restore_rejects_missing_file(self, tmp_path, monkeypatch):
        import pytest as _pytest

        import services.pg_backup_service as svc

        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:5432/d')
        with _pytest.raises(svc.PgBackupError):
            svc.restore_pg_sql_gz(str(tmp_path / 'nope.sql.gz'))

    def test_restore_rejects_wrong_extension(self, tmp_path, monkeypatch):
        import pytest as _pytest

        import services.pg_backup_service as svc

        artifact = tmp_path / 'backup.dump'
        artifact.write_bytes(b'\x00')
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:5432/d')
        with _pytest.raises(svc.PgBackupError):
            svc.restore_pg_sql_gz(str(artifact))

    def test_restore_rejects_empty_dump(self, tmp_path, monkeypatch):
        import pytest as _pytest

        import services.pg_backup_service as svc

        artifact = self._write_dump(tmp_path, 'empty.sql.gz', payload=b'   ')
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@h:5432/d')
        with _pytest.raises(svc.PgBackupError):
            svc.restore_pg_sql_gz(str(artifact))


# ---------------------------------------------------------------------------
# LAB (routes/lab/*)
# ---------------------------------------------------------------------------
class TestLabWorklistApi:
    def test_api_worklist_returns_requests(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('labapi'), 'lab')
        patient = _make_patient(db, test_tenant)
        _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert any(r['patient_id'] == patient.id for r in data['requests'])

    def test_api_worklist_filters_by_visit(self, app, client, db, test_tenant, rollback_db):
        from models.visit import Visit

        lab = _login(client, db, test_tenant, _uniq('labapifv'), 'lab')
        patient = _make_patient(db, test_tenant)
        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=lab.id,
            status='OPEN',
            payment_status='PENDING',
            total_amount=0,
            paid_amount=0,
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()
        wanted = _make_lab_request(
            db, test_tenant, patient.id, requested_by=lab.id, visit_id=visit.id
        )
        _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.get(f'/lab/api/worklist?visit_id={visit.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [r['id'] for r in data['requests']]
        assert wanted.id in ids
        assert all(r['visit_id'] == visit.id for r in data['requests'])

    def test_api_worklist_filters_by_status(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('labapifs'), 'lab')
        patient = _make_patient(db, test_tenant)
        done = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id, status='DONE')
        _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id, status='REQUESTED')

        resp = client.get('/lab/api/worklist?status=DONE')
        assert resp.status_code == 200
        data = resp.get_json()
        assert [r['id'] for r in data['requests']] == [done.id]

    def test_api_worklist_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('labapi403'), 'reception')
        resp = client.get('/lab/api/worklist')
        assert resp.status_code == 403


class TestFhirServiceRequest:
    def test_service_request_requires_fields(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('fhir400'), 'lab')
        resp = client.post('/lab/api/fhir/servicerequest', json={})
        assert resp.status_code == 400
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_service_request_creates_request_and_results(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabRequest, LabResult

        lab = _login(client, db, test_tenant, _uniq('fhrok'), 'lab')
        patient = _make_patient(db, test_tenant)
        from models.visit import Visit

        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=lab.id,
            status='OPEN',
            payment_status='PENDING',
            total_amount=0,
            paid_amount=0,
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()

        resp = client.post(
            '/lab/api/fhir/servicerequest',
            json={
                'patient_id': patient.id,
                'visit_id': visit.id,
                'tests': [
                    {'test_code': 'HB', 'test_name': 'Hemoglobin'},
                    'not-a-dict',
                    {'test_code': '', 'test_name': ''},
                ],
            },
        )
        assert resp.status_code == 201
        resource = resp.get_json()
        assert resource['resourceType'] == 'ServiceRequest'
        assert resource['subject']['reference'] == f'Patient/{patient.id}'
        assert resource['encounter']['reference'] == f'Encounter/{visit.id}'

        req = db.session.get(LabRequest, int(resource['id']))
        assert req is not None
        assert req.patient_id == patient.id

        results = (
            db.session.execute(select(LabResult).filter(LabResult.request_id == req.id))
            .scalars()
            .all()
        )
        assert len(results) == 1
        assert results[0].test_code == 'HB'
        assert results[0].status == 'PENDING'

    def test_service_request_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('fhir403'), 'reception')
        resp = client.post(
            '/lab/api/fhir/servicerequest',
            json={'patient_id': 1, 'visit_id': 1},
        )
        assert resp.status_code == 403


class TestFhirObservationImport:
    def test_import_requires_fields(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('ob400'), 'lab')
        resp = client.post('/lab/api/fhir/observation', json={})
        assert resp.status_code == 400

    def test_import_unknown_request_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('ob404'), 'lab')
        resp = client.post(
            '/lab/api/fhir/observation',
            json={'request_id': 999999999, 'patient_id': 1, 'test_code': 'HB'},
        )
        assert resp.status_code == 404

    def test_import_creates_validated_result(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('obok'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'GL',
                'test_name': 'Glucose',
                'value': '5.2',
                'unit': 'mmol/L',
                'reference_range': '3.9-5.5',
            },
        )
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Observation'
        assert resource['status'] == 'final'

        res = db.session.get(LabResult, int(resource['id']))
        assert res.value == '5.2'
        assert res.status == 'VALIDATED'
        assert res.performed_by == lab.id

    def test_import_updates_existing_result_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('obupd'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        existing = _make_lab_result(
            db,
            test_tenant,
            req.id,
            patient.id,
            test_code='HB',
            test_name='Hemoglobin',
            value=None,
            status='PENDING',
        )

        resp = client.post(
            '/lab/api/fhir/observation',
            json={
                'request_id': req.id,
                'patient_id': patient.id,
                'test_code': 'HB',
                'value': '14.1',
                'unit': 'g/dL',
            },
        )
        assert resp.status_code == 200
        db.session.expire_all()
        res = db.session.get(LabResult, existing.id)
        assert res.value == '14.1'
        assert res.status == 'VALIDATED'
        count = (
            db.session.execute(
                select(LabResult).filter(
                    LabResult.request_id == req.id, LabResult.test_code == 'HB'
                )
            )
            .scalars()
            .all()
        )
        assert len(count) == 1

    def test_import_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('ob403'), 'reception')
        resp = client.post(
            '/lab/api/fhir/observation',
            json={'request_id': 1, 'patient_id': 1},
        )
        assert resp.status_code == 403


class TestFhirObservationExport:
    def _seed_result(self, db, tenant, lab_user, req=None):
        from models.visit import Visit

        patient = _make_patient(db, tenant)
        if req is None:
            visit = Visit(
                tenant_id=tenant.id,
                patient_id=patient.id,
                doctor_id=lab_user.id,
                status='OPEN',
                payment_status='PENDING',
                total_amount=0,
                paid_amount=0,
                visit_type='REGULAR',
            )
            db.session.add(visit)
            db.session.commit()
            req = _make_lab_request(
                db, tenant, patient.id, requested_by=lab_user.id, visit_id=visit.id
            )
        res = _make_lab_result(
            db,
            tenant,
            req.id,
            patient.id,
            test_code='HB',
            test_name='Hemoglobin',
            value='13.2',
            unit='g/dL',
            reference_range='12-16',
            status='VALIDATED',
            notes='dentro del rango',
            performed_by=lab_user.id,
        )
        return patient, req, res

    def test_export_numeric_value_as_value_quantity(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('obsnum'), 'lab')
        _patient, req, res = self._seed_result(db, test_tenant, lab)

        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'Observation'
        assert resource['status'] == 'final'
        assert resource['valueQuantity']['value'] == 13.2
        assert resource['valueQuantity']['unit'] == 'g/dL'
        assert resource['effectiveDateTime']
        assert resource['code']['text'] == 'Hemoglobin'
        assert resource['referenceRange'] == [{'text': '12-16'}]
        assert resource['encounter']['reference'] == f'Encounter/{req.visit_id}'
        assert resource['performer'] == [{'reference': f'Practitioner/{lab.id}'}]
        assert resource['note'] == [{'text': 'dentro del rango'}]

    def test_export_non_numeric_value_as_value_string(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('obsstr'), 'lab')
        _patient, _req, res = self._seed_result(db, test_tenant, lab)
        res.value = 'POSITIVE'
        db.session.commit()

        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource.get('valueString') == 'POSITIVE'
        assert 'valueQuantity' not in resource

    def test_export_pending_result_maps_to_preliminary(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('obsprep'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        res = _make_lab_result(
            db,
            test_tenant,
            req.id,
            patient.id,
            test_code='HB',
            test_name='Hemoglobin',
            value='13.0',
            status='PENDING',
        )
        resp = client.get(f'/lab/api/fhir/observation/lab/{res.id}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'preliminary'

    def test_export_unknown_result_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('ob404x'), 'lab')
        resp = client.get('/lab/api/fhir/observation/lab/999999999')
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_export_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('ob403x'), 'reception')
        resp = client.get('/lab/api/fhir/observation/lab/1')
        assert resp.status_code == 403


class TestFhirDiagnosticReport:
    def test_diagnostic_report_bundle(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('drrep'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        res = _make_lab_result(
            db,
            test_tenant,
            req.id,
            patient.id,
            test_code='HB',
            test_name='Hemoglobin',
            value='15.0',
            status='VALIDATED',
            notes='normales',
            performed_by=lab.id,
        )
        resp = client.get(f'/lab/api/fhir/diagnosticreport/lab/{res.id}')
        assert resp.status_code == 200
        resource = resp.get_json()
        assert resource['resourceType'] == 'DiagnosticReport'
        assert resource['status'] == 'final'
        assert resource['result'] == [{'reference': f'Observation/{res.id}'}]
        assert resource['subject']['reference'] == f'Patient/{patient.id}'
        assert resource['conclusion'] == 'normales'
        assert resource['performer'] == [{'reference': f'Practitioner/{lab.id}'}]
        assert 'issued' in resource

    def test_diagnostic_report_unknown_result_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dr404'), 'lab')
        resp = client.get('/lab/api/fhir/diagnosticreport/lab/999999999')
        assert resp.status_code == 404
        assert resp.get_json()['resourceType'] == 'OperationOutcome'

    def test_diagnostic_report_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dr403'), 'reception')
        resp = client.get('/lab/api/fhir/diagnosticreport/lab/1')
        assert resp.status_code == 403


class TestHl7Import:
    def test_hl7_import_requires_fields(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl7400'), 'lab')
        resp = client.post('/lab/api/hl7/import', json={})
        assert resp.status_code == 400

    def test_hl7_import_creates_request_and_results(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabResult

        lab = _login(client, db, test_tenant, _uniq('hl7ok'), 'lab')
        patient = _make_patient(db, test_tenant)
        from models.visit import Visit

        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=lab.id,
            status='OPEN',
            payment_status='PENDING',
            total_amount=0,
            paid_amount=0,
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()

        resp = client.post(
            '/lab/api/hl7/import',
            json={
                'patient_id': patient.id,
                'visit_id': visit.id,
                'tests': [
                    {
                        'test_code': 'GL',
                        'test_name': 'Glucose',
                        'value': '5.2',
                        'unit': 'mmol/L',
                        'reference_range': '3.9-5.5',
                    },
                    'junk-row',
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True
        request_id = data['request_id']

        results = (
            db.session.execute(select(LabResult).filter(LabResult.request_id == request_id))
            .scalars()
            .all()
        )
        assert len(results) == 1
        assert results[0].test_code == 'GL'
        assert results[0].value == '5.2'

    def test_hl7_import_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hl7403'), 'reception')
        resp = client.post('/lab/api/hl7/import', json={'patient_id': 1, 'visit_id': 1})
        assert resp.status_code == 403


class TestCatalogCrud:
    def _add_catalog(self, db, tenant, code, **kw):
        from models.lab_test_catalog import LabTestCatalog

        row = LabTestCatalog(
            tenant_id=tenant.id,
            code=code,
            name_ar=kw.get('name_ar', f'فحص {code}'),
            name_en=kw.get('name_en', code),
            category=kw.get('category', 'chemistry'),
            unit=kw.get('unit', 'mg/dL'),
            default_reference_range=kw.get('default_reference_range', '1-10'),
            critical_low=kw.get('critical_low', '2'),
            critical_high=kw.get('critical_high', '20'),
            price=kw.get('price', 100),
            preparation_instructions=kw.get('preparation_instructions', ''),
            is_active=kw.get('is_active', True),
            sort_order=kw.get('sort_order', 10),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def test_catalog_page_lists_tests_and_filters(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catlist'), 'lab')
        self._add_catalog(db, test_tenant, 'TC-ALPHA', category='chemistry')
        resp = client.get('/lab/test-catalog/')
        assert resp.status_code == 200
        assert b'TC-ALPHA' in resp.data

        resp = client.get('/lab/test-catalog/?category=chemistry')
        assert resp.status_code == 200
        assert b'TC-ALPHA' in resp.data

        resp = client.get('/lab/test-catalog/?category=microbiology')
        assert resp.status_code == 200
        assert b'TC-ALPHA' not in resp.data

    def test_catalog_page_blocks_reception(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cat403'), 'reception')
        resp = client.get('/lab/test-catalog/')
        assert resp.status_code == 403

    def test_catalog_add_persists_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('catadd'), 'lab')
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': 'TC-ADD1',
                'name_ar': 'اختبار الإضافة',
                'name_en': 'Add Test',
                'category': 'hematology',
                'unit': 'g/dL',
                'default_reference_range': '12-16',
                'critical_low': '8',
                'critical_high': '18',
                'price': '123.5',
                'preparation_instructions': 'صائم',
                'is_active': '1',
                'sort_order': '4',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(select(LabTestCatalog).filter(LabTestCatalog.code == 'TC-ADD1'))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.category == 'hematology'
        assert float(row.price) == 123.5
        assert row.sort_order == 4
        assert row.is_active is True
        assert row.tenant_id == test_tenant.id

    def test_catalog_add_duplicate_code_rolls_back(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('catdup'), 'lab')
        self._add_catalog(db, test_tenant, 'TC-DUP1')
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': 'TC-DUP1',
                'name_ar': 'مكرر',
                'name_en': 'Dup',
                'category': 'chemistry',
            },
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(LabTestCatalog).filter(LabTestCatalog.code == 'TC-DUP1'))
            .scalars()
            .all()
        )
        assert len(rows) == 1, 'duplicate catalog code must not be stored twice'

    def test_catalog_edit_updates_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('catedit'), 'manager')
        row = self._add_catalog(db, test_tenant, 'TC-EDIT1', name_en='Before')
        resp = client.post(
            f'/lab/test-catalog/{row.id}/edit',
            data={
                'code': 'TC-EDIT1',
                'name_ar': 'بعد التعديل',
                'name_en': 'After',
                'category': 'serology',
                'price': '77',
                'is_active': '1',
                'sort_order': '9',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestCatalog, row.id)
        assert refreshed.name_en == 'After'
        assert refreshed.category == 'serology'
        assert float(refreshed.price) == 77.0

    def test_catalog_edit_unknown_id_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catedit404'), 'lab')
        resp = client.post(
            '/lab/test-catalog/999999999/edit',
            data={'code': 'X', 'name_ar': 'X', 'name_en': 'X', 'category': 'other'},
        )
        assert resp.status_code == 302

    def test_catalog_delete_removes_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('catdel'), 'admin')
        row = self._add_catalog(db, test_tenant, 'TC-DEL1')
        resp = client.post(f'/lab/test-catalog/{row.id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestCatalog, row.id) is None

    def test_catalog_delete_unknown_id_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catdel404'), 'lab')
        resp = client.post('/lab/test-catalog/999999999/delete')
        assert resp.status_code == 302

    def test_api_catalog_list_and_item(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catapi'), 'doctor')
        row = self._add_catalog(db, test_tenant, 'TC-API1', price=55)
        resp = client.get('/lab/api/test-catalog')
        assert resp.status_code == 200
        payload = resp.get_json()
        codes = [t['code'] for t in payload]
        assert 'TC-API1' in codes

        resp = client.get(f'/lab/api/test-catalog/{row.id}')
        assert resp.status_code == 200
        item = resp.get_json()
        assert item['code'] == 'TC-API1'
        assert item['price'] == 55.0

    def test_api_catalog_item_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catapi404'), 'lab')
        resp = client.get('/lab/api/test-catalog/999999999')
        assert resp.status_code == 404

    def test_api_catalog_rejects_non_staff_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('catapatient'), 'patient')
        resp = client.get(
            '/lab/api/test-catalog',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 403


class TestPanelCrud:
    def _add_panel(self, db, tenant, name_ar='لوحة الاختبار', **kw):
        from models.lab_test_catalog import LabTestPanel

        panel = LabTestPanel(
            tenant_id=tenant.id,
            name_ar=name_ar,
            name_en=kw.get('name_en', 'Test Panel'),
            description=kw.get('description', ''),
            is_active=kw.get('is_active', True),
        )
        db.session.add(panel)
        db.session.commit()
        return panel

    def _make_item(self, test_id, sort_order=0):
        from models.lab_test_catalog import LabTestPanelItem

        return LabTestPanelItem(test_id=test_id, sort_order=sort_order)

    def _add_catalog_test(self, db, tenant, code):
        from models.lab_test_catalog import LabTestCatalog

        row = LabTestCatalog(
            tenant_id=tenant.id,
            code=code,
            name_ar=f'فحص {code}',
            category='chemistry',
            is_active=True,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def test_panels_page_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('panpage'), 'lab')
        resp = client.get('/lab/test-panels/')
        assert resp.status_code == 200

    def test_panels_add_with_items(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel

        _login(client, db, test_tenant, _uniq('panadd'), 'lab')
        t1 = self._add_catalog_test(db, test_tenant, 'P-ITEM1')
        t2 = self._add_catalog_test(db, test_tenant, 'P-ITEM2')
        resp = client.post(
            '/lab/test-panels/add',
            data={
                'name_ar': 'لوحة كاملة',
                'name_en': 'Full Panel',
                'description': 'desc',
                'is_active': '1',
                'test_ids': [str(t1.id), 'not-a-number', str(t2.id), '999999999'],
            },
        )
        assert resp.status_code == 302
        panel = (
            db.session.execute(select(LabTestPanel).order_by(LabTestPanel.id.desc()))
            .scalars()
            .first()
        )
        assert panel.name_en == 'Full Panel'
        assert {item.test_id for item in panel.items} == {t1.id, t2.id}

    def test_panels_edit_replaces_items(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel

        _login(client, db, test_tenant, _uniq('panedit'), 'manager')
        t1 = self._add_catalog_test(db, test_tenant, 'P-EDIT1')
        t2 = self._add_catalog_test(db, test_tenant, 'P-EDIT2')
        panel = self._add_panel(db, test_tenant)
        panel.items.append(self._make_item(t1.id, sort_order=0))
        db.session.commit()

        resp = client.post(
            f'/lab/test-panels/{panel.id}/edit',
            data={
                'name_ar': 'لوحة معدلة',
                'name_en': 'Edited Panel',
                'is_active': '1',
                'test_ids': [str(t2.id)],
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestPanel, panel.id)
        assert refreshed.name_en == 'Edited Panel'
        assert [item.test_id for item in refreshed.items] == [t2.id]

    def test_panels_edit_unknown_panel_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('panedit404'), 'lab')
        resp = client.post(
            '/lab/test-panels/999999999/edit',
            data={'name_ar': 'x', 'is_active': '1'},
        )
        assert resp.status_code == 302

    def test_panels_delete_removes_panel_and_items(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel, LabTestPanelItem

        _login(client, db, test_tenant, _uniq('pandel'), 'admin')
        t1 = self._add_catalog_test(db, test_tenant, 'P-DEL1')
        panel = self._add_panel(db, test_tenant)
        panel.items.append(self._make_item(t1.id, sort_order=0))
        db.session.commit()

        resp = client.post(f'/lab/test-panels/{panel.id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestPanel, panel.id) is None
        remaining = (
            db.session.execute(
                select(LabTestPanelItem).filter(LabTestPanelItem.panel_id == panel.id)
            )
            .scalars()
            .all()
        )
        assert remaining == []

    def test_panels_delete_unknown_panel_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('pandel404'), 'lab')
        resp = client.post('/lab/test-panels/999999999/delete')
        assert resp.status_code == 302


class TestQualityControl:
    def test_quality_control_page_lists_entries(self, app, client, db, test_tenant, rollback_db):
        from models.lab_quality import LabQualityControlEntry

        _login(client, db, test_tenant, _uniq('qcpage'), 'lab')
        db.session.add(
            LabQualityControlEntry(
                tenant_id=test_tenant.id,
                test_code='QC-PAGE1',
                control_level='NORMAL',
                measured_value='5.0',
                status='PASS',
                recorded_at=datetime.now(UTC),
            )
        )
        db.session.commit()
        resp = client.get('/lab/quality-control')
        assert resp.status_code == 200
        assert b'QC-PAGE1' in resp.data

    def test_quality_control_post_records_fail_entry(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_quality import LabQualityControlEntry

        lab = _login(client, db, test_tenant, _uniq('qcpost'), 'lab')
        resp = client.post(
            '/lab/quality-control',
            data={
                'test_code': 'QC-FAIL1',
                'test_name': 'Control serum',
                'control_level': 'HIGH',
                'measured_value': '7.7',
                'unit': 'mmol/L',
                'expected_range': '4-6',
                'status': 'FAIL',
                'notes': 'drifted',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(
                select(LabQualityControlEntry).filter(
                    LabQualityControlEntry.test_code == 'QC-FAIL1'
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.status == 'FAIL'
        assert row.control_level == 'HIGH'
        assert row.recorded_by == lab.id

    def test_quality_control_post_normalizes_bad_values(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_quality import LabQualityControlEntry

        _login(client, db, test_tenant, _uniq('qcnorm'), 'lab')
        resp = client.post(
            '/lab/quality-control',
            data={
                'test_code': 'QC-NORM1',
                'control_level': 'SUPER_HIGH',
                'measured_value': '1.0',
                'status': 'MAYBE',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(
                select(LabQualityControlEntry).filter(
                    LabQualityControlEntry.test_code == 'QC-NORM1'
                )
            )
            .scalars()
            .first()
        )
        assert row.control_level == 'NORMAL'
        assert row.status == 'PASS'

    def test_quality_control_post_missing_value_records_nothing(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_quality import LabQualityControlEntry

        _login(client, db, test_tenant, _uniq('qcmis'), 'lab')
        resp = client.post(
            '/lab/quality-control',
            data={'test_code': 'QC-MIS1', 'measured_value': ''},
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(
                select(LabQualityControlEntry).filter(LabQualityControlEntry.test_code == 'QC-MIS1')
            )
            .scalars()
            .all()
        )
        assert rows == []

    def test_quality_page_renders_with_date_params(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('qcdash'), 'lab')
        resp = client.get('/lab/quality?start_date=2020-01-01&end_date=2030-01-01')
        assert resp.status_code == 200

    def test_quality_page_tolerates_bad_dates(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('qcbaddate'), 'lab')
        resp = client.get('/lab/quality?start_date=not-a-date&end_date=also-bad')
        assert resp.status_code == 200


class TestWorklistFlow:
    def test_worklist_page_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('wlpage'), 'lab')
        resp = client.get('/lab/worklist')
        assert resp.status_code == 200

    def test_worklist_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('wlredir'), 'lab')
        assert client.get('/lab/requests').status_code == 302
        assert client.get('/lab/results').status_code == 302
        assert client.get('/lab/tests').status_code == 302

    def test_worklist_request_collect_sets_timestamps(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wlcollect'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.post(
            f'/lab/worklist/request/{req.id}',
            data={'action': 'collect'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        updated = db.session.get(LabRequest, req.id)
        assert updated.status == 'COLLECTED'
        assert updated.collection_time is not None

    def test_worklist_request_get_detail_renders(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('wlget'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.get(f'/lab/worklist/request/{req.id}')
        assert resp.status_code == 200

    def test_worklist_claim_marks_received(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wlclaim'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.post(f'/lab/worklist/claim/{req.id}')
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(LabRequest, req.id).status == 'RECEIVED'

    def test_worklist_claim_twice_rejected(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('wlclaim2'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        first = client.post(f'/lab/worklist/claim/{req.id}')
        assert first.status_code == 200
        second = client.post(f'/lab/worklist/claim/{req.id}')
        assert second.status_code == 400

    def test_worklist_complete_without_results_400(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('wlnop'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.post(f'/lab/worklist/complete/{req.id}', json={})
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['success'] is False

    def test_worklist_complete_with_result_marks_done(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wldone'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        _make_lab_result(db, test_tenant, req.id, patient.id, value='5.5', status='READY')
        resp = client.post(f'/lab/worklist/complete/{req.id}', json={})
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        updated = db.session.get(LabRequest, req.id)
        assert updated.status == 'DONE'
        assert updated.completed_at is not None

    def test_worklist_complete_with_inline_result_payload(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabRequest, LabResult

        lab = _login(client, db, test_tenant, _uniq('wlinline'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.post(
            f'/lab/worklist/complete/{req.id}',
            json={'test_code': 'GL', 'test_name': 'Glucose', 'value': '4.9'},
        )
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(LabRequest, req.id).status == 'DONE'
        results = (
            db.session.execute(select(LabResult).filter(LabResult.request_id == req.id))
            .scalars()
            .all()
        )
        assert any(r.test_code == 'GL' and r.value == '4.9' for r in results)

    def test_finalize_blocked_when_result_missing_value(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wlfin1'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        _make_lab_result(db, test_tenant, req.id, patient.id, value=None, status='PENDING')
        resp = client.post(
            f'/lab/worklist/request/{req.id}',
            data={'action': 'finalize'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(LabRequest, req.id).status != 'DONE'

    def test_finalize_blocked_when_no_results(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wlfin0'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.post(
            f'/lab/worklist/request/{req.id}',
            data={'action': 'finalize'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(LabRequest, req.id).status != 'DONE'

    def test_finalize_marks_request_done(self, app, client, db, test_tenant, rollback_db):
        from models.lab_request import LabRequest

        lab = _login(client, db, test_tenant, _uniq('wlfinok'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        _make_lab_result(db, test_tenant, req.id, patient.id, value='13.3', status='READY')
        resp = client.post(
            f'/lab/worklist/request/{req.id}',
            data={'action': 'finalize'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        updated = db.session.get(LabRequest, req.id)
        assert updated.status == 'DONE'
        assert updated.completed_at is not None

    def test_results_form_autofills_unit_and_range_from_catalog(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_request import LabResult
        from models.lab_test_catalog import LabTestCatalog

        lab = _login(client, db, test_tenant, _uniq('wlauto'), 'lab')
        catalog = LabTestCatalog(
            tenant_id=test_tenant.id,
            code='AUTO1',
            name_ar='تلقائي',
            category='chemistry',
            unit='u/u',
            default_reference_range='1-9',
            is_active=True,
        )
        db.session.add(catalog)
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)

        resp = client.post(
            f'/lab/worklist/request/{req.id}',
            data={
                'action': 'save',
                'test_code[]': 'AUTO1',
                'test_name[]': 'Auto Test',
                'value[]': '7',
                'unit[]': '',
                'reference_range[]': '',
                'status[]': 'PENDING',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(
                select(LabResult).filter(
                    LabResult.request_id == req.id, LabResult.test_code == 'AUTO1'
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.unit == 'u/u'
        assert row.reference_range == '1-9'


class TestResultTemplatesAndDerivedValues:
    def test_create_and_list_result_templates(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('tmpl1'), 'lab')
        resp = client.post(
            '/lab/result-templates',
            json={
                'name': 'CBC panel template',
                'test_code': 'CBC',
                'test_name': 'Complete Blood Count',
                'unit': 'x10^9/L',
                'reference_range': '4-11',
            },
        )
        assert resp.status_code == 201
        template = resp.get_json()['data']
        assert template['name'] == 'CBC panel template'
        assert template['id'] >= 1

        resp = client.get('/lab/result-templates')
        assert resp.status_code == 200
        payload = resp.get_json()
        assert any(t['name'] == 'CBC panel template' for t in payload['templates'])

    def test_result_template_detail_get_and_delete(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('tmpl2'), 'doctor')
        resp = client.post(
            '/lab/result-templates',
            json={'name': 'DeleteMe', 'test_code': 'DM'},
        )
        template_id = resp.get_json()['data']['id']

        resp = client.get(f'/lab/result-templates/{template_id}')
        assert resp.status_code == 200
        assert resp.get_json()['data']['name'] == 'DeleteMe'

        resp = client.delete(f'/lab/result-templates/{template_id}')
        assert resp.status_code == 200

        resp = client.get(f'/lab/result-templates/{template_id}')
        assert resp.status_code == 404

    def test_derived_values_bmi(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dv1'), 'lab')
        resp = client.post(
            '/lab/calculate',
            json={'formula': 'bmi', 'values': {'weight': 80, 'height': 180}},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert abs(data['result'] - 24.69) < 0.1

    def test_derived_values_sum_and_ratio(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dv2'), 'manager')
        resp = client.post(
            '/lab/calculate',
            json={'formula': 'sum', 'values': {'a': 1, 'b': 2, 'c': 3}},
        )
        assert resp.get_json()['result'] == 6

        resp = client.post(
            '/lab/calculate',
            json={'formula': 'ratio', 'values': {'a': 10, 'b': 4}},
        )
        assert resp.get_json()['result'] == 2.5

    def test_derived_values_unsupported_expression_400(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('dv3'), 'lab')
        resp = client.post(
            '/lab/calculate',
            json={'formula': '__import__("os").system("echo hi")', 'values': {}},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_derived_values_rejects_non_staff(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dv4'), 'patient')
        resp = client.post(
            '/lab/calculate',
            json={'formula': 'sum', 'values': {'a': 1}},
        )
        assert resp.status_code == 403

    def test_critical_value_alerts_lists_critical_results(
        self, app, client, db, test_tenant, rollback_db
    ):
        lab = _login(client, db, test_tenant, _uniq('crit1'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        _make_lab_result(
            db,
            test_tenant,
            req.id,
            patient.id,
            test_code='K',
            test_name='Potassium',
            value='6.8',
            is_critical=True,
        )
        resp = client.get('/lab/api/critical-alerts')
        assert resp.status_code == 200
        data = resp.get_json()
        codes = [a['test_code'] for a in data['alerts']]
        assert 'K' in codes

    def test_result_history_seed_and_append(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('hist1'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        res = _make_lab_result(db, test_tenant, req.id, patient.id, value='9.1', status='READY')
        resp = client.get(f'/lab/results/{res.id}/history')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['count'] >= 1
        assert data['history'][0]['value'] == '9.1'

        resp = client.post(
            f'/lab/results/{res.id}/history',
            json={'value': '9.4', 'notes': 'corrected'},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['data']['value'] == '9.4'

    def test_result_history_unknown_result_404(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('hist404'), 'lab')
        resp = client.get('/lab/results/999999999/history')
        assert resp.status_code == 404


class TestLisImportRoutes:
    def _upload(self, client, content: bytes, filename='results.csv'):
        import io as _io

        return client.post(
            '/lab/lis/preview',
            data={'file': (_io.BytesIO(content), filename)},
            content_type='multipart/form-data',
        )

    def test_lis_preview_requires_file(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('lis400'), 'lab')
        resp = client.post('/lab/lis/preview', data={})
        assert resp.status_code == 400

    def test_lis_preview_rejects_non_utf8_file(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('lisenc'), 'lab')
        resp = self._upload(client, b'\xff\xfe\x00bad')
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_lis_preview_rejects_missing_required_columns(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('lismiss'), 'lab')
        resp = self._upload(client, b'foo,bar\n1,2\n')
        assert resp.status_code == 400

    def test_lis_preview_matches_catalog_codes(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('lisok'), 'lab')
        db.session.add(
            LabTestCatalog(
                tenant_id=test_tenant.id,
                code='LIS- HB',
                name_ar='تحليل',
                category='hematology',
                is_active=True,
            )
        )
        db.session.commit()
        resp = self._upload(client, b'test_code,value\nLIS- HB,13.2\n')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert len(data['matched']) == 1
        assert data['confirmable'] is True

    def test_lis_confirm_rejects_empty_rows(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('lisconf'), 'lab')
        resp = client.post('/lab/lis/confirm', json={'rows': []})
        assert resp.status_code == 400

    def test_lis_confirm_imports_matched_rows(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        lab = _login(client, db, test_tenant, _uniq('lisimpok'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        db.session.add(
            LabTestCatalog(
                tenant_id=test_tenant.id,
                code='LIS-GLU',
                name_ar='جلوكوز',
                category='chemistry',
                unit='mmol/L',
                is_active=True,
            )
        )
        db.session.commit()
        resp = client.post(
            '/lab/lis/confirm',
            json={
                'rows': [
                    {
                        'test_code': 'LIS-GLU',
                        'value': '5.2',
                        'request_id': req.id,
                        'unit': 'mmol/L',
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['imported_count'] == 1


class TestLabReports:
    def test_reports_page_renders(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('rep1'), 'lab')
        resp = client.get('/lab/reports')
        assert resp.status_code == 200

    def test_print_request_renders_document(self, app, client, db, test_tenant, rollback_db):
        lab = _login(client, db, test_tenant, _uniq('repprint'), 'lab')
        patient = _make_patient(db, test_tenant)
        req = _make_lab_request(db, test_tenant, patient.id, requested_by=lab.id)
        resp = client.get(f'/lab/print_request/{req.id}')
        assert resp.status_code == 200
        assert resp.headers.get('Cache-Control') == 'no-store, no-cache, must-revalidate, max-age=0'

    def test_print_request_unknown_id_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('repprint404'), 'lab')
        resp = client.get('/lab/print_request/999999999')
        assert resp.status_code == 302


class TestLabDashboardAndAnalytics:
    def test_lab_dashboard_renders_or_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dash1'), 'lab')
        resp = client.get('/lab/dashboard')
        assert resp.status_code in (200, 302)

    def test_lab_index_redirects_to_dashboard(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('dash2'), 'lab')
        resp = client.get('/lab/')
        assert resp.status_code == 302

    def test_analytics_helpers_return_dicts(self, app, client, db, test_tenant, rollback_db):
        with app.test_request_context():
            from routes.lab import (
                calculate_lab_efficiency,
                calculate_test_efficiency,
                generate_optimization_suggestions,
                get_lab_equipment_monitoring,
                get_lab_predictive_insights,
                get_lab_quality_control,
                get_lab_result_analysis,
                get_lab_smart_analytics,
                get_lab_test_optimization,
                get_lab_workflow_automation,
            )

            assert calculate_lab_efficiency(80, 5) == 70
            assert calculate_lab_efficiency(10, 50) == 0
            assert calculate_test_efficiency(1.5, 100) == 95
            assert calculate_test_efficiency(3, 100) == 85
            assert calculate_test_efficiency(5, 100) == 75
            assert calculate_test_efficiency(9, 100) == 60
            assert generate_optimization_suggestions(3) == []
            assert 'تحسين تدفق العينات' in generate_optimization_suggestions(5)
            assert 'إضافة معدات جديدة' in generate_optimization_suggestions(7)
            assert 'زيادة عدد الفنيين' in generate_optimization_suggestions(9)

            assert isinstance(get_lab_smart_analytics(), dict)
            assert isinstance(get_lab_test_optimization(), dict)
            assert isinstance(get_lab_quality_control(), dict)
            assert isinstance(get_lab_equipment_monitoring(), dict)
            assert isinstance(get_lab_result_analysis(), dict)
            assert isinstance(get_lab_workflow_automation(), dict)
            assert isinstance(get_lab_predictive_insights(), dict)


class TestLabUnauthenticated:
    def test_lab_routes_redirect_to_login(self, client):
        for path in ('/lab/worklist', '/lab/test-catalog/', '/lab/quality', '/lab/api/worklist'):
            resp = client.get(path)
            assert resp.status_code in (302, 401), f'{path} -> {resp.status_code}'
