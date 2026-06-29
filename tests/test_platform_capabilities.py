"""Tests for platform capability flags."""

from __future__ import annotations

import pytest

from app.core.platform_capabilities import get_capabilities, platform_capability


@pytest.fixture(autouse=True)
def _clear_platform_caps(monkeypatch):
    for name in (
        'PLATFORM_CAP_SMS_LIVE',
        'PLATFORM_CAP_WEBAUTHN',
        'PLATFORM_CAP_FHIR',
        'PLATFORM_CAP_SSO',
    ):
        monkeypatch.delenv(name, raising=False)


def test_capabilities_default_false():
    assert platform_capability('sms_live') is False
    assert platform_capability('webauthn') is False
    assert platform_capability('fhir_api') is False
    assert platform_capability('sso') is False
    assert get_capabilities() == {
        'sms_live': False,
        'webauthn': False,
        'fhir_api': False,
        'sso': False,
    }


def test_capabilities_read_env(monkeypatch):
    monkeypatch.setenv('PLATFORM_CAP_WEBAUTHN', 'true')
    monkeypatch.setenv('PLATFORM_CAP_FHIR', '1')
    assert platform_capability('webauthn') is True
    assert platform_capability('fhir_api') is True
    assert platform_capability('sso') is False


def test_template_context_injects_platform_capability(app):
    with app.test_request_context('/'):
        from flask import render_template_string
        html = render_template_string(
            '{% if platform_capability("webauthn") %}on{% else %}off{% endif %}'
        )
        assert html == 'off'


@pytest.mark.parametrize('cap_env,path', [
    ('PLATFORM_CAP_WEBAUTHN', '/biometric/'),
    ('PLATFORM_CAP_FHIR', '/api/fhir/Patient'),
    ('PLATFORM_CAP_SSO', '/sso/config'),
])
def test_gated_routes_404_when_disabled(client, login_as, cap_env, path):
    login_as(client, 'cap_mgr', 'manager')
    resp = client.get(path)
    assert resp.status_code == 404


@pytest.mark.parametrize('cap_env,path', [
    ('PLATFORM_CAP_WEBAUTHN', '/biometric/'),
    ('PLATFORM_CAP_FHIR', '/api/fhir/Patient'),
    ('PLATFORM_CAP_SSO', '/sso/config'),
])
def test_gated_routes_available_when_enabled(client, login_as, monkeypatch, cap_env, path):
    monkeypatch.setenv(cap_env, 'true')
    login_as(client, 'cap_mgr2', 'super_admin')
    resp = client.get(path)
    assert resp.status_code != 404


def test_sms_test_endpoint_404_when_disabled(client, login_as):
    login_as(client, 'cap_sa', 'super_admin')
    resp = client.post('/super-admin/system/sms/test', json={'phone_number': '+15551234567'})
    assert resp.status_code == 404


def test_sms_test_endpoint_reachable_when_enabled(client, login_as, monkeypatch):
    monkeypatch.setenv('PLATFORM_CAP_SMS_LIVE', 'true')
    login_as(client, 'cap_sa2', 'super_admin')
    resp = client.post('/super-admin/system/sms/test', json={'phone_number': ''})
    assert resp.status_code == 400
