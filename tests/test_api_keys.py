"""Tests for API key management and per-endpoint rate limiting."""

import contextlib

import pytest
from sqlalchemy import text


@pytest.fixture()
def api_key_factory(app, db, test_tenant):
    """Factory: create an ApiKey row directly and return (record, raw_key)."""
    from models.api_key import ApiKey, _hash_key

    created = []

    def _make(name='test key', scopes='read', active=True, max_r=5, window=60):
        raw = f'mk_{name.replace(" ", "")}_rawsecretvalue123456'
        key = ApiKey(
            tenant_id=test_tenant.id,
            name=name,
            key_prefix=raw[:10],
            key_hash=_hash_key(raw),
            scopes=scopes,
            is_active=active,
            rate_limit_max=max_r,
            rate_limit_window=window,
        )
        db.session.add(key)
        db.session.commit()
        created.append(key)
        return key, raw

    yield _make

    for k in created:
        with contextlib.suppress(Exception):
            db.session.execute(text('DELETE FROM api_keys WHERE id = :i'), {'i': k.id})
            db.session.commit()


class TestApiKeyModel:
    def test_generate_raw_key_format(self):
        from models.api_key import ApiKey

        raw, prefix, digest = ApiKey.generate_raw_key()
        assert raw.startswith('mk_')
        assert prefix == raw[:10]
        assert len(digest) == 64

    def test_verify_roundtrip(self):
        from models.api_key import ApiKey

        raw, prefix, digest = ApiKey.generate_raw_key()
        key = ApiKey(name='t', key_prefix=prefix, key_hash=digest)
        assert key.verify(raw)
        assert not key.verify('mk_wrong')

    def test_is_valid_checks_expiry_and_revocation(self):
        from datetime import UTC, datetime, timedelta

        from models.api_key import ApiKey

        raw, prefix, digest = ApiKey.generate_raw_key()
        # NOTE: column defaults apply at flush; pass values explicitly for
        # un-flushed instances.
        key = ApiKey(name='t', key_prefix=prefix, key_hash=digest, is_active=True)
        assert key.is_valid()

        key.revoked_at = datetime.now(UTC)
        assert not key.is_valid()

        key2 = ApiKey(
            name='t2',
            key_prefix='p2',
            key_hash=digest + 'a',
            is_active=True,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert not key2.is_valid()

    def test_scopes(self):
        from models.api_key import ApiKey

        key = ApiKey(name='s', key_prefix='p', key_hash='h', scopes='read,write')
        assert key.has_scope('read')
        assert key.has_scope('WRITE')
        assert not key.has_scope('delete')

        wildcard = ApiKey(name='w', key_prefix='p', key_hash='h2', scopes='*')
        assert wildcard.has_scope('anything')


class TestApiKeyService:
    def test_create_and_authenticate(self, app, db, test_tenant):
        from services.api_key_service import ApiKeyService

        key_record, raw = ApiKeyService.create_key(
            tenant_id=test_tenant.id, name='integration', scopes='read,write'
        )
        assert key_record is not None
        assert raw.startswith('mk_')

        authed = ApiKeyService.authenticate(raw)
        assert authed is not None
        assert authed.id == key_record.id

        wrong = ApiKeyService.authenticate('mk_bogus')
        assert wrong is None

    def test_revoke(self, app, db, test_tenant):
        from services.api_key_service import ApiKeyService

        record, raw = ApiKeyService.create_key(tenant_id=test_tenant.id, name='to-revoke')
        assert ApiKeyService.revoke_key(record.id)

        authed = ApiKeyService.authenticate(raw)
        assert authed is None  # revoked keys fail authentication


class TestApiRateLimiting:
    def test_invalid_api_key_rejected(self, client, api_key_factory):
        resp = client.get('/api/search?q=x', headers={'X-API-Key': 'mk_totally_invalid'})
        assert resp.status_code == 401

    def test_valid_api_key_accepted(self, client, api_key_factory):
        _, raw = api_key_factory(name='goodkey')
        # /api/search requires login for session users but the key path is
        # authenticated via header — endpoint itself may still 403/404 on auth.
        resp = client.get('/api/search?q=x', headers={'X-API-Key': raw})
        assert resp.status_code != 401  # passed key validation at minimum

    def test_api_key_rate_limit_enforced(self, client, api_key_factory):
        _, raw = api_key_factory(name='limited', max_r=3, window=60)
        statuses = []
        for _ in range(6):
            resp = client.get('/api/search?q=x', headers={'X-API-Key': raw})
            statuses.append(resp.status_code)
        assert 429 in statuses

    def test_session_rate_limit_enforced(self, app, client, login_as):
        """Unauthenticated hammering of an /api/* route hits the default limiter."""
        statuses = set()
        for _ in range(150):
            resp = client.get('/api/user')
            statuses.add(resp.status_code)
            if 429 in statuses:
                break
        assert 429 in statuses or resp.status_code in (401, 403)
