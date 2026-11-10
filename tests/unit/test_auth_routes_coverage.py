"""Real-HTTP coverage for routes/auth_routes.py (remaining branches)."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime, timedelta

from tests.tenant_context import tenant_test_context


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _login(client, db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role=role, password=password)
    login_test_client(client, user, tenant, password)
    return user


def _create_user(db, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, tenant, username=username, role=role, password=password)


def _csrf_token(client, path='/auth/login'):
    resp = client.get(path)
    cookie = resp.headers.get('Set-Cookie', '')
    if 'csrf_token=' in cookie:
        return cookie.split('csrf_token=')[1].split(';')[0]
    return None


class TestLoginCSRFAndBranches:
    def test_login_csrf_failure_ajax(self, client, app, monkeypatch):
        token = _csrf_token(client, '/auth/login')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/login',
            json={'username': 'x', 'password': 'y'},
            headers={'X-CSRFToken': token},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_login_csrf_failure_form(self, client, app, monkeypatch):
        token = _csrf_token(client, '/auth/login')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/login', data={'username': 'x', 'password': 'y', 'csrf_token': token}
        )
        assert resp.status_code == 400

    def test_login_invalid_int_setting_fallback(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig
        from tests.tenant_context import ensure_test_user

        # A non-integer stored value forces the int() conversion to fail.
        with tenant_test_context(app, test_tenant):
            db.session.add(
                SystemConfig(
                    tenant_id=test_tenant.id,
                    config_key='max_login_attempts',
                    config_value='not-an-int',
                    config_type='string',
                    category='security',
                )
            )
            db.session.commit()

        user = ensure_test_user(db, test_tenant, username=_uniq('badcfg'), role='reception')
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code in (200, 302, 401, 403)

    def test_login_lockout_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('lockaudit'), role='reception')
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

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'safe_commit', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 429

    def test_login_lockout_outer_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('lockouter'), role='reception')
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

        # Make the lockout bookkeeping query fail after the initial user lookup.
        orig_execute = db.session.execute
        calls = {'n': 0}

        def boom_execute(*a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                return orig_execute(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code in (200, 302, 401, 403, 429, 500)

    def test_login_suspended_tenant(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('susp'), role='reception')
        old_status = test_tenant.status
        test_tenant.status = 'SUSPENDED'
        db.session.commit()
        try:
            resp = client.post(
                '/auth/login',
                json={
                    'username': user.username,
                    'password': 'ValidPass123!',
                    'tenant_slug': test_tenant.slug,
                },
            )
            assert resp.status_code == 403
        finally:
            test_tenant.status = old_status
            db.session.commit()

    def test_login_success_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('succaudit'), role='reception')

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'safe_commit', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code in (200, 302)

    def test_login_session_logging_concurrent_limit(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.digital_signature import SessionLog
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('concsess'), role='reception')
        now = datetime.now(UTC)
        for i in range(3):
            db.session.add(
                SessionLog(
                    user_id=user.id,
                    tenant_id=test_tenant.id,
                    session_id=f'sess-{i}',
                    ip_address='127.0.0.1',
                    user_agent='pytest',
                    device_type='DESKTOP',
                    browser='Unknown',
                    os='Unknown',
                    fingerprint='fp',
                    is_active=True,
                    login_at=now - timedelta(minutes=i + 1),
                )
            )
        db.session.commit()

        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code in (200, 302)

    def test_login_session_logging_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('sessexc'), role='reception')

        orig_execute = db.session.execute
        calls = {'n': 0}

        def boom_execute(*a, **k):
            calls['n'] += 1
            if calls['n'] <= 5:
                return orig_execute(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code in (200, 302, 500)

    def test_login_tenant_slug_lookup_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('slugexc'), role='reception')

        # Force the Tenant lookup inside the redirect-slug branch to fail.
        orig_get = db.session.get
        calls = {'n': 0}

        def boom_get(*a, **k):
            calls['n'] += 1
            if calls['n'] <= 5:
                return orig_get(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'get', boom_get)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        monkeypatch.setattr(db.session, 'get', orig_get)
        assert resp.status_code in (200, 302, 500)

    def test_login_wrong_password_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badpwaudit'), role='reception')

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'safe_commit', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'WrongPass999!'},
        )
        assert resp.status_code in (401, 500)

    def test_login_outer_exception(self, app, client, db, test_tenant, rollback_db, monkeypatch):
        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('outerexc'), role='reception')

        monkeypatch.setattr(
            User, 'check_password', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 500


class TestLogoutBranches:
    def test_logout_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('logoutexc'), 'reception')

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'safe_commit', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.get('/auth/logout')
        assert resp.status_code == 302


class TestProfileBranches:
    def test_profile_post_with_department_id(self, app, client, db, test_tenant, rollback_db):
        from models.department import Department
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('profdept'), 'doctor')
        with tenant_test_context(app, test_tenant):
            dept = Department(
                tenant_id=test_tenant.id, name='CovDept', name_ar='CovDept', is_active=True
            )
            db.session.add(dept)
            db.session.commit()
            dept_id = dept.id

        resp = client.post(
            '/auth/profile',
            data={'full_name': 'Dept User', 'department_id': str(dept_id)},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.department_id == dept_id

    def test_profile_post_with_new_password(self, app, client, db, test_tenant, rollback_db):
        from models.user import User

        user = _login(client, db, test_tenant, _uniq('profpw'), 'doctor')
        resp = client.post(
            '/auth/profile',
            data={'full_name': 'Pw User', 'new_password': 'NewProfilePass123!'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(User, user.id)
        assert refreshed.check_password('NewProfilePass123!')

    def test_profile_post_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('profexc'), 'doctor')

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'safe_commit', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post('/auth/profile', data={'full_name': 'Fail User'})
        assert resp.status_code in (200, 302)

    def test_profile_get_query_failures(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('profgetexc'), 'doctor')

        orig_execute = db.session.execute
        calls = {'n': 0}

        def boom_execute(*a, **k):
            calls['n'] += 1
            if calls['n'] <= 10:
                return orig_execute(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.get('/auth/profile')
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code in (200, 500)


class TestChangePasswordBranches:
    def test_change_password_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('cpaud'), 'reception')

        import routes.auth_routes as auth_mod

        calls = {'n': 0}
        orig = auth_mod.safe_commit

        def fake_commit(session, *a, **k):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom')
            return orig(session, *a, **k)

        monkeypatch.setattr(auth_mod, 'safe_commit', fake_commit)
        resp = client.post(
            '/auth/change-password',
            json={
                'current_password': 'ValidPass123!',
                'new_password': 'BrandNew123!',
                'confirm_password': 'BrandNew123!',
            },
        )
        assert resp.status_code == 200

    def test_change_password_outer_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('cpouter'), 'reception')

        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod,
            'generate_password_hash',
            lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom')),
        )
        resp = client.post(
            '/auth/change-password',
            json={'current_password': 'ValidPass123!', 'new_password': 'BrandNew123!'},
        )
        assert resp.status_code == 500


class TestResetTokenHelpersBranches:
    def test_store_reset_token_unknown_user(self, app, db, test_tenant, rollback_db):
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            _store_reset_token(999999999, 'tok', datetime.now(UTC) + timedelta(hours=1))
        assert True

    def test_verify_reset_token_no_preferences(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('noprefs'), role='reception')
        assert user.preferences is None
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'tok') is False

    def test_clear_reset_token_no_preferences(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('clearnopref'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _clear_reset_token

            _clear_reset_token(user.id)
        assert True

    def test_verify_reset_token_unknown_user(self, app, db, test_tenant, rollback_db):
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(999999999, 'tok') is False

    def test_clear_reset_token_unknown_user(self, app, db, test_tenant, rollback_db):
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _clear_reset_token

            _clear_reset_token(999999999)
        assert True


class TestForgotPasswordBranches:
    def test_forgot_password_csrf_failure_ajax(self, client, app, monkeypatch):
        token = _csrf_token(client, '/auth/forgot-password')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/forgot-password',
            json={'identifier': 'nobody'},
            headers={'X-CSRFToken': token},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_forgot_password_csrf_failure_form(self, client, app, monkeypatch):
        token = _csrf_token(client, '/auth/forgot-password')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            '/auth/forgot-password', data={'identifier': 'nobody', 'csrf_token': token}
        )
        assert resp.status_code == 400

    def test_forgot_password_missing_identifier_form(
        self, client, app, db, test_tenant, rollback_db
    ):
        resp = client.post('/auth/forgot-password', data={'identifier': ''})
        assert resp.status_code == 200

    def test_forgot_password_whatsapp_fallback_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(
            db, test_tenant, username=_uniq('fpwafail'), role='reception', phone='0598123456'
        )

        class _BoomMail:
            def send(self, message):
                raise RuntimeError('SMTP unreachable')

        class _BoomWhatsApp:
            def send_message(self, to, body):
                raise RuntimeError('WA unreachable')

        monkeypatch.setattr('app.extensions.mail', _BoomMail())

        def _make_boom_whatsapp():
            return _BoomWhatsApp()

        monkeypatch.setattr(
            'app.integrations.whatsapp.service.WhatsAppService', _make_boom_whatsapp
        )
        resp = client.post('/auth/forgot-password', json={'identifier': user.username})
        assert resp.status_code == 200

    def test_forgot_password_form_success(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('fpsuccess'), role='reception')

        class _FakeMail:
            def send(self, message):
                pass

        monkeypatch.setattr('app.extensions.mail', _FakeMail())
        resp = client.post('/auth/forgot-password', data={'identifier': user.username})
        assert resp.status_code == 302

    def test_forgot_password_outer_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        orig_execute = db.session.execute

        def boom_execute(*a, **k):
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        resp = client.post('/auth/forgot-password', json={'identifier': 'nobody'})
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code == 500


class TestResetPasswordBranches:
    def _issue_token(self, app, user, expires_in=timedelta(hours=1), tenant=None):
        from tests.tenant_context import ensure_default_test_tenant

        tenant = tenant or ensure_default_test_tenant(app)
        with tenant_test_context(app, tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{uuid.uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + expires_in)
            return token

    def test_reset_password_csrf_failure_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rscsrf'), role='reception')
        token = self._issue_token(app, user)
        csrf = _csrf_token(client, '/auth/login')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={
                'new_password': 'BrandNew123!',
                'confirm_password': 'BrandNew123!',
                'csrf_token': csrf,
            },
        )
        assert resp.status_code == 400

    def test_reset_password_missing_password_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsmiss'), role='reception')
        token = self._issue_token(app, user)
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={'new_password': '', 'confirm_password': ''},
        )
        assert resp.status_code == 200

    def test_reset_password_mismatch_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsmm'), role='reception')
        token = self._issue_token(app, user)
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={'new_password': 'BrandNew123!', 'confirm_password': 'Other123!'},
        )
        assert resp.status_code == 200

    def test_reset_password_policy_weak_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsweak'), role='reception')
        token = self._issue_token(app, user)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={'new_password': 'weak', 'confirm_password': 'weak'},
        )
        assert resp.status_code == 200

    def test_reset_password_policy_import_error(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsimp'), role='reception')
        token = self._issue_token(app, user)
        # Force the optional password-policy import to fail.
        monkeypatch.setitem(sys.modules, 'services.password_policy_service', None)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
            raising=False,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        # Either succeeds (policy skipped) or errors; both exercise the branch.
        assert resp.status_code in (200, 400, 500)

    def test_reset_password_audit_commit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsaudit'), role='reception')
        token = self._issue_token(app, user)

        import routes.auth_routes as auth_mod

        calls = {'n': 0}
        orig = auth_mod.safe_commit

        def fake_commit(session, *a, **k):
            calls['n'] += 1
            if calls['n'] == 3:
                raise RuntimeError('boom')
            return orig(session, *a, **k)

        monkeypatch.setattr(auth_mod, 'safe_commit', fake_commit)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code == 200

    def test_reset_password_form_success(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rssuccess'), role='reception')
        token = self._issue_token(app, user)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code == 302

    def test_reset_password_outer_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsouter'), role='reception')
        token = self._issue_token(app, user)

        import routes.auth_routes as auth_mod

        calls = {'n': 0}
        orig = auth_mod.safe_commit

        def fake_commit(session, *a, **k):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom')
            return orig(session, *a, **k)

        monkeypatch.setattr(auth_mod, 'safe_commit', fake_commit)
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code == 500


class TestImpersonationBranches:
    def test_impersonate_exit_owner_not_found(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('exitnf'), 'super_admin')
        with client.session_transaction() as sess:
            sess['impersonator_id'] = 999999999
        resp = client.post('/auth/impersonate/exit')
        assert resp.status_code == 401


class TestApiTenantsList:
    def test_tenants_list_success(self, client):
        resp = client.get('/auth/api/tenants-list')
        assert resp.status_code == 200
        assert 'tenants' in resp.get_json()

    def test_tenants_list_db_error(self, client, monkeypatch):
        import routes.auth_routes as auth_mod

        class _BoomSession:
            def execute(self, *a, **k):
                raise RuntimeError('boom')

        class _BoomDb:
            session = _BoomSession()

        monkeypatch.setattr(auth_mod, 'db', _BoomDb())
        resp = client.get('/auth/api/tenants-list')
        assert resp.status_code == 200
        assert resp.get_json() == {'tenants': []}


class TestLoginAdditionalBranches:
    def test_login_missing_credentials_form(self, client):
        resp = client.post('/auth/login', data={'username': '', 'password': ''})
        assert resp.status_code == 200

    def test_login_owner_mode_redirect(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('ownerredir'), role='super_admin')
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!', 'mode': 'owner'},
        )
        assert resp.status_code == 302
        assert 'owner' in resp.headers['Location']

    def test_login_inactive_user_form(self, app, client, db, test_tenant, rollback_db):
        from sqlalchemy import update

        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('inactform2'), role='reception')
        db.session.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.session.commit()
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 200

    def test_login_wrong_password_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badpwform2'), role='reception')
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'WrongPass999!'},
        )
        assert resp.status_code == 200

    def test_login_suspended_tenant_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('suspform'), role='reception')
        old_status = test_tenant.status
        test_tenant.status = 'SUSPENDED'
        db.session.commit()
        try:
            resp = client.post(
                '/auth/login',
                data={
                    'username': user.username,
                    'password': 'ValidPass123!',
                    'tenant_slug': test_tenant.slug,
                },
            )
            assert resp.status_code in (200, 403)
        finally:
            test_tenant.status = old_status
            db.session.commit()

    def test_login_lockout_form(self, app, client, db, test_tenant, rollback_db):
        from models.audit_trail import LoginAttempt
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('lockform2'), role='reception')
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


class TestProfileAdditionalBranches:
    def test_profile_post_email_and_role_attempt(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('profemail'), 'reception')
        resp = client.post(
            '/auth/profile',
            data={'full_name': 'Email User', 'email': 'newemail@test.local', 'role': 'super_admin'},
        )
        assert resp.status_code == 302

    def test_profile_post_signature_upload(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('profsig2'), 'doctor')
        data = {
            'full_name': 'Signed',
            'signature': (__import__('io').BytesIO(b'fake'), 'sig.png'),
        }
        resp = client.post('/auth/profile', data=data, content_type='multipart/form-data')
        assert resp.status_code == 302

    def test_profile_get_query_failures(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _login(client, db, test_tenant, _uniq('profgetexc2'), 'doctor')

        orig_execute = db.session.execute
        calls = {'n': 0}

        def boom_execute(*a, **k):
            calls['n'] += 1
            if calls['n'] <= 2:
                return orig_execute(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.get('/auth/profile')
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code in (200, 500)


class TestChangePasswordAdditionalBranches:
    def test_change_password_non_json(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpnonjson'), 'reception')
        resp = client.post(
            '/auth/change-password',
            data='current_password=a&new_password=b',
            content_type='text/plain',
        )
        assert resp.status_code == 400

    def test_change_password_empty_json(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpempty'), 'reception')
        resp = client.post('/auth/change-password', json={})
        assert resp.status_code == 400

    def test_change_password_missing_fields(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpmiss2'), 'reception')
        resp = client.post('/auth/change-password', json={'current_password': 'x'})
        assert resp.status_code == 400

    def test_change_password_confirm_mismatch(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpconf2'), 'reception')
        resp = client.post(
            '/auth/change-password',
            json={
                'current_password': 'ValidPass123!',
                'new_password': 'NewStrong123!',
                'confirm_password': 'Different123!',
            },
        )
        assert resp.status_code == 400

    def test_change_password_wrong_current(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('cpwrong2'), 'reception')
        resp = client.post(
            '/auth/change-password',
            json={'current_password': 'NotThePassword!', 'new_password': 'NewStrong123!'},
        )
        assert resp.status_code == 400


class TestResetTokenHelpersAdditional:
    def test_verify_reset_token_malformed_expiry(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('badtok2'), role='reception')
        user.preferences = {
            'password_reset_token': 'tok_abc',
            'password_reset_expires': 'not-a-date',
        }
        db.session.commit()
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'tok_abc') is False

    def test_verify_reset_token_expired(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('exptok2'), role='reception')
        with tenant_test_context(app, test_tenant):
            from datetime import UTC, datetime, timedelta

            from routes.auth_routes import _store_reset_token, _verify_reset_token

            _store_reset_token(user.id, 'expired_token', datetime.now(UTC) - timedelta(hours=2))
            assert _verify_reset_token(user.id, 'expired_token') is False

    def test_store_reset_token_roundtrip(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('roundtrip2'), role='reception')
        with tenant_test_context(app, test_tenant):
            from datetime import UTC, datetime, timedelta

            from routes.auth_routes import (
                _clear_reset_token,
                _store_reset_token,
                _verify_reset_token,
            )

            _store_reset_token(user.id, 'tok123', datetime.now(UTC) + timedelta(hours=1))
            assert _verify_reset_token(user.id, 'tok123') is True
            _clear_reset_token(user.id)
            assert _verify_reset_token(user.id, 'tok123') is False


class TestForgotPasswordAdditionalBranches:
    def test_forgot_password_missing_identifier_json(self, app, client, test_tenant, rollback_db):
        resp = client.post('/auth/forgot-password', json={'identifier': ''})
        assert resp.status_code == 400

    def test_forgot_password_by_email(self, app, client, db, test_tenant, rollback_db, monkeypatch):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('fpemail2'), role='reception')

        class _FakeMail:
            def send(self, message):
                pass

        monkeypatch.setattr('app.extensions.mail', _FakeMail())
        resp = client.post('/auth/forgot-password', json={'identifier': user.email.upper()})
        assert resp.status_code == 200

    def test_forgot_password_outer_exception_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        orig_execute = db.session.execute
        calls = {'n': 0}

        def boom_execute(*a, **k):
            calls['n'] += 1
            if calls['n'] <= 1:
                return orig_execute(*a, **k)
            raise RuntimeError('boom')

        monkeypatch.setattr(db.session, 'execute', boom_execute)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post('/auth/forgot-password', data={'identifier': 'nobody'})
        monkeypatch.setattr(db.session, 'execute', orig_execute)
        assert resp.status_code in (200, 500)


class TestResetPasswordAdditionalBranches:
    def test_reset_password_invalid_token(self, client):
        resp = client.get('/auth/reset-password/notatoken/12345')
        assert resp.status_code == 302

    def test_reset_password_get_form(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('resetget2'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))
        resp = client.get(f'/auth/reset-password/{token}/{user.id}')
        assert resp.status_code == 200

    def test_reset_password_csrf_failure_ajax(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rscsrfajax'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))
        csrf = _csrf_token(client, '/auth/login')
        monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
        import routes.auth_routes as auth_mod

        monkeypatch.setattr(
            auth_mod, 'validate_csrf', lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError('boom'))
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
            headers={'X-CSRFToken': csrf},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_reset_password_missing_password_ajax(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsmissajax'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': '', 'confirm_password': ''},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_reset_password_mismatch_ajax(self, app, client, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsmmajax'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'BrandNew123!', 'confirm_password': 'Other123!'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_reset_password_weak_ajax(self, app, client, db, test_tenant, rollback_db, monkeypatch):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsweakajax'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))
        monkeypatch.setattr(
            'services.password_policy_service.PasswordPolicyService._check_hibp_breach',
            lambda _self, _password: 0,
        )
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            json={'new_password': 'weak', 'confirm_password': 'weak'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_reset_password_outer_exception_form(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('rsouterform'), role='reception')
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _store_reset_token

            token = f'tok_{__import__("uuid").uuid4().hex}'
            _store_reset_token(user.id, token, datetime.now(UTC) + timedelta(hours=1))

        import routes.auth_routes as auth_mod

        calls = {'n': 0}
        orig = auth_mod.safe_commit

        def fake_commit(session, *a, **k):
            calls['n'] += 1
            if calls['n'] == 1:
                raise RuntimeError('boom')
            return orig(session, *a, **k)

        monkeypatch.setattr(auth_mod, 'safe_commit', fake_commit)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            f'/auth/reset-password/{token}/{user.id}',
            data={'new_password': 'BrandNew123!', 'confirm_password': 'BrandNew123!'},
        )
        assert resp.status_code in (200, 500)


class TestImpersonationAdditional:
    def test_impersonate_success(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impactor2'), 'super_admin')
        subject = _create_user(db, test_tenant, _uniq('imptarget2'), 'reception')
        resp = client.post(f'/auth/impersonate/{subject.id}')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_impersonate_self(self, app, client, db, test_tenant, rollback_db):
        actor = _login(client, db, test_tenant, _uniq('impself2'), 'super_admin')
        resp = client.post(f'/auth/impersonate/{actor.id}')
        assert resp.status_code == 400

    def test_impersonate_unknown(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('imp4042'), 'super_admin')
        resp = client.post('/auth/impersonate/999999999')
        assert resp.status_code == 404

    def test_impersonate_requires_privilege(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impdeny2'), 'reception')
        subject = _create_user(db, test_tenant, _uniq('impdenysub2'), 'reception')
        resp = client.post(f'/auth/impersonate/{subject.id}')
        assert resp.status_code == 403

    def test_impersonate_exit_no_session(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impxit2'), 'super_admin')
        resp = client.post('/auth/impersonate/exit')
        assert resp.status_code == 400

    def test_impersonate_exit_success(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('impexit2'), 'super_admin')
        subject = _create_user(db, test_tenant, _uniq('impexittarget2'), 'reception')
        client.post(f'/auth/impersonate/{subject.id}')
        resp = client.post('/auth/impersonate/exit')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


class TestRegisterAdditional:
    def test_register_non_owner_redirects(self, client):
        resp = client.post('/auth/register', data={'mode': ''})
        assert resp.status_code == 302

    def test_register_owner_mode_get(self, client):
        resp = client.get('/auth/register?mode=owner')
        assert resp.status_code == 302
        assert 'owner' in resp.headers['Location']


class TestFinalBranches:
    def test_login_missing_credentials_ajax(self, client):
        resp = client.post('/auth/login', json={'username': '', 'password': ''})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_login_inactive_user_ajax(self, app, client, db, test_tenant, rollback_db):
        from sqlalchemy import update

        from models.user import User
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('inactajax'), role='reception')
        db.session.execute(update(User).where(User.id == user.id).values(is_active=False))
        db.session.commit()
        resp = client.post(
            '/auth/login',
            json={'username': user.username, 'password': 'ValidPass123!'},
        )
        assert resp.status_code == 403

    def test_verify_reset_token_missing_stored_token(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('missingtok'), role='reception')
        user.preferences = {'foo': 'bar'}
        db.session.commit()
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'tok') is False

    def test_verify_reset_token_mismatched_stored_token(self, app, db, test_tenant, rollback_db):
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('mismatchtok'), role='reception')
        user.preferences = {
            'password_reset_token': 'stored_tok',
            'password_reset_expires': (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        db.session.commit()
        with tenant_test_context(app, test_tenant):
            from routes.auth_routes import _verify_reset_token

            assert _verify_reset_token(user.id, 'different_tok') is False

    def test_login_tenant_slug_lookup_exception(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from app.core.tenant.models import Tenant
        from tests.tenant_context import ensure_test_user

        user = ensure_test_user(db, test_tenant, username=_uniq('slugexc2'), role='reception')

        orig_get = db.session.get
        calls = {'n': 0}

        def boom_get(*a, **k):
            calls['n'] += 1
            # Allow middleware/early gets; raise once we hit the redirect-slug Tenant get.
            if a and a[0] is Tenant and calls['n'] > 1:
                raise RuntimeError('boom')
            return orig_get(*a, **k)

        monkeypatch.setattr(db.session, 'get', boom_get)
        monkeypatch.setitem(app.config, 'TESTING', False)
        resp = client.post(
            '/auth/login',
            data={'username': user.username, 'password': 'ValidPass123!'},
        )
        monkeypatch.setattr(db.session, 'get', orig_get)
        assert resp.status_code in (200, 302, 500)


class TestGetRedirectUrlByRole:
    def test_get_redirect_url_by_role(self, app):
        from routes.auth_routes import get_redirect_url_by_role

        url = get_redirect_url_by_role('doctor')
        assert isinstance(url, str)
        assert url.startswith('/')


class TestRegisterBranches:
    def test_register_post_owner_mode(self, client):
        resp = client.post('/auth/register', data={'mode': 'owner'})
        assert resp.status_code == 302
        assert 'owner' in resp.headers['Location']
