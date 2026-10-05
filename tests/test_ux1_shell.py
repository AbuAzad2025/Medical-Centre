"""Tests for UX1-001: Clinical Clean design system and app shell."""

import contextlib
import uuid

import pytest
from sqlalchemy import delete

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def owner_user_for_shell(app, rollback_db):
    # rollback_db, not a bare app: this fixture commits, and without the
    # transaction those commits are real, so the user outlived the test. Measured
    # with a per-test row-count audit: this was one of seven tests in the suite
    # leaving a committed user behind.
    from flask import g

    username = f'owner_shell_{uuid.uuid4().hex[:8]}'
    u = User(
        username=username,
        email=f'{username}@example.com',
        full_name='Owner Shell Test',
        role='owner',
        is_active=True,
        tenant_id=g.get('tenant_id'),
    )
    u.set_password('owner123')
    db.session.add(u)
    db.session.commit()
    yield u
    try:
        from models.audit_trail import LoginAttempt

        db.session.execute(delete(LoginAttempt).filter_by(user_id=u.id))
    except Exception:
        db.session.rollback()
    db.session.delete(u)
    db.session.commit()


@pytest.fixture(scope='function')
def logged_in_owner_shell_client(client, owner_user_for_shell):
    resp = client.post(
        '/auth/login',
        data={'username': owner_user_for_shell.username, 'password': 'owner123'},
        follow_redirects=True,
    )
    if resp.status_code != 200:
        with contextlib.suppress(Exception):
            txt = resp.get_data(as_text=True)
            print(f'LOGIN FAILED shell {resp.status_code}: {txt[:2000]}')
            if 'الاشتراك' in txt:
                print('SUBSCRIPTION ERROR')
    assert resp.status_code == 200
    yield client
    client.get('/auth/logout')


class TestUX1Shell:
    def test_base_html_loads_design_tokens(self, logged_in_owner_shell_client):
        resp = logged_in_owner_shell_client.get('/owner/packages')
        text = resp.get_data(as_text=True)
        assert 'design-tokens.css' in text
        assert 'clinical-theme' in text
        assert 'tenant-branding-vars' in text
