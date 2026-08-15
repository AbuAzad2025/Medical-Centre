"""Tests for app.integrations.devices.biometric module.

Covers the BiometricAuth class - biometric credential management.
"""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

from app.integrations.devices.biometric import BiometricAuth, logger


class TestInit:
    """Tests for BiometricAuth.__init__."""

    def test_default_driver_name(self):
        """Test default driver name."""
        auth = BiometricAuth()
        assert auth.driver_name == 'db'

    def test_custom_driver_name(self):
        """Test custom driver name."""
        auth = BiometricAuth(driver_name='webauthn')
        assert auth.driver_name == 'webauthn'

    def test_default_tenant_id(self):
        """Test default tenant_id is None."""
        auth = BiometricAuth()
        assert auth.tenant_id is None

    def test_custom_tenant_id(self):
        """Test custom tenant_id."""
        auth = BiometricAuth(tenant_id=42)
        assert auth.tenant_id == 42


class TestResolveTenantId:
    """Tests for _resolve_tenant_id method."""

    def test_returns_explicit_tenant_id(self):
        """Test explicit tenant_id is returned."""
        auth = BiometricAuth()
        assert auth._resolve_tenant_id(tenant_id=99) == 99

    def test_returns_self_tenant_id_when_no_override(self):
        """Test self.tenant_id is returned when no explicit tenant_id."""
        auth = BiometricAuth(tenant_id=42)
        assert auth._resolve_tenant_id() == 42

    def test_falls_back_to_flask_g(self):
        """Test falls back to flask.g.tenant_id."""
        auth = BiometricAuth()
        mock_g = MagicMock()
        mock_g.tenant_id = 5
        with patch('flask.g', mock_g):
            assert auth._resolve_tenant_id() == 5

    def test_returns_none_when_flask_g_not_available(self):
        """Test returns None when flask.g doesn't have tenant_id."""
        auth = BiometricAuth()
        mock_g = MagicMock(spec=[])
        with patch('flask.g', mock_g):
            result = auth._resolve_tenant_id()
            assert result is None

    def test_explicit_tenant_overrides_g(self):
        """Test explicit tenant_id takes priority over flask.g."""
        auth = BiometricAuth()
        mock_g = MagicMock()
        mock_g.tenant_id = 5
        with patch('flask.g', mock_g):
            assert auth._resolve_tenant_id(tenant_id=99) == 99


class TestEnroll:
    """Tests for enroll method."""

    def test_enroll_with_credential_id(self):
        """Test enrolling with explicit credential_id."""
        auth = BiometricAuth(tenant_id=1)
        mock_db = MagicMock()
        with patch('app.integrations.devices.biometric.db', mock_db):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    credential_id='cred-123',
                    public_key='key-data',
                )
                assert result is True
                mock_db.session.add.assert_called_once()

    def test_enroll_with_dict_template(self):
        """Test enrolling with dict template."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    template={
                        'credential_id': 'cred-456',
                        'public_key': 'key-456',
                        'device_type': 'platform',
                        'device_name': 'Fingerprint',
                        'aaguid': 'test-aaguid',
                        'authenticator_attachment': 'platform',
                    },
                )
                assert result is True

    def test_enroll_with_bytes_template(self):
        """Test enrolling with bytes template."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    template=b'some-key-data',
                    public_key=None,
                )
                assert result is True

    def test_enroll_generates_credential_id(self):
        """Test that credential_id is auto-generated when not provided."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='generated-id'):
                    result = auth.enroll(user_id=1)
                    assert result is True

    def test_enroll_with_explicit_tenant_id(self):
        """Test enrolling with explicit tenant_id override."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    credential_id='cred',
                    public_key='key',
                    tenant_id=99,
                )
                assert result is True

    def test_enroll_resolves_tenant_from_g(self):
        """Test enrolling resolves tenant from flask.g."""
        auth = BiometricAuth()
        mock_g = MagicMock()
        mock_g.tenant_id = 5
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('flask.g', mock_g):
                    result = auth.enroll(
                        user_id=1,
                        credential_id='cred',
                        public_key='key',
                    )
                    assert result is True

    def test_enroll_with_kwargs(self):
        """Test enrolling with extra kwargs."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    credential_id='cred',
                    public_key='key',
                    aaguid='test-aaguid',
                    authenticator_attachment='platform',
                )
                assert result is True

    def test_enroll_generates_token_when_no_credential_id(self):
        """Test enrolling generates token when credential_id not in template."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='gen-token'):
                    result = auth.enroll(
                        user_id=1,
                        template={'public_key': 'pk'},
                        public_key=None,
                    )
                    assert result is True

    def test_enroll_generates_public_key_from_bytes(self):
        """Test enrolling uses template bytes as public_key."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    template=b'raw-template-data',
                    public_key=None,
                )
                assert result is True

    def test_enroll_no_public_key_no_bytes(self):
        """Test enrolling with no public_key and non-bytes template."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                result = auth.enroll(
                    user_id=1,
                    template={'public_key': 'from-payload'},
                    public_key=None,
                )
                assert result is True


class TestVerify:
    """Tests for verify method."""

    def test_verify_returns_false_without_credential_id(self):
        """Test verify returns False when no credential_id."""
        auth = BiometricAuth(tenant_id=1)
        result = auth.verify(user_id=1)
        assert result is False

    def test_verify_returns_false_when_credential_not_found(self):
        """Test verify returns False when credential not found."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = None

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.verify(user_id=1, credential_id='cred-123')
                assert result is False

    def test_verify_false_on_replay_attack(self):
        """Test verify returns False on sign_count replay."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100
        mock_credential.last_used_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db') as mock_db:
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(user_id=1, credential_id='cred-123', sign_count=50)
                    assert result is False

    def test_verify_updates_sign_count(self):
        """Test verify updates sign_count when valid."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100
        mock_credential.last_used_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db') as mock_db:
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(user_id=1, credential_id='cred-123', sign_count=150)
                    assert result is True
                    assert mock_credential.sign_count == 150

    def test_verify_sets_last_used_at(self):
        """Test verify sets last_used_at."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100
        mock_credential.last_used_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(user_id=1, credential_id='cred-123', sign_count=200)
                    assert result is True
                    assert mock_credential.last_used_at is not None

    def test_verify_with_tenant_filter(self):
        """Test verify with tenant filter."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(
                        user_id=1,
                        credential_id='cred-123',
                        sign_count=200,
                        tenant_id=99,
                    )
                    assert result is True

    def test_verify_from_payload(self):
        """Test verify with credential_id from payload dict."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(
                        user_id=1,
                        template={'credential_id': 'from-payload', 'sign_count': 200},
                    )
                    assert result is True

    def test_verify_no_sign_count_in_payload(self):
        """Test verify with no sign_count in payload."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.sign_count = 100

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.verify(
                        user_id=1,
                        credential_id='cred-123',
                    )
                    assert result is True

    def test_verify_with_tenant_id_in_resolve(self):
        """Test verify resolves tenant via _resolve_tenant_id."""
        auth = BiometricAuth()
        mock_credential = MagicMock()
        mock_credential.sign_count = 100

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_credential

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    with patch('flask.g', tenant_id=5):
                        result = auth.verify(
                            user_id=1,
                            credential_id='cred-123',
                            sign_count=200,
                        )
                        assert result is True


class TestListCredentials:
    """Tests for list_credentials method."""

    def test_list_credentials_empty(self):
        """Test listing credentials with no results."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = []

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.list_credentials(user_id=1)
                assert result == []

    def test_list_credentials_with_results(self):
        """Test listing credentials with results."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.id = 1
        mock_credential.credential_id = 'cred-1'
        mock_credential.device_type = 'security_key'
        mock_credential.device_name = 'Key'
        mock_credential.last_used_at = None
        mock_credential.created_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = [mock_credential]

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.list_credentials(user_id=1)
                assert isinstance(result, list)
                assert result[0]['id'] == 1
                assert result[0]['credential_id'] == 'cred-1'
                assert result[0]['device_type'] == 'security_key'
                assert result[0]['device_name'] == 'Key'
                assert result[0]['last_used_at'] is None
                assert result[0]['created_at'] is None

    def test_list_credentials_with_datetime(self):
        """Test listing credentials with datetime fields."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.id = 1
        mock_credential.credential_id = 'cred-1'
        mock_credential.device_type = 'security_key'
        mock_credential.device_name = 'Key'
        mock_credential.last_used_at = datetime.now(timezone.utc)
        mock_credential.created_at = datetime.now(timezone.utc)

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = [mock_credential]

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.list_credentials(user_id=1)
                assert isinstance(result, list)
                assert 'last_used_at' in result[0]
                assert 'created_at' in result[0]

    def test_list_credentials_no_user_id_filter(self):
        """Test listing credentials without user_id filter (no filter_by called)."""
        auth = BiometricAuth(tenant_id=1)
        mock_credential = MagicMock()
        mock_credential.id = 1
        mock_credential.credential_id = 'cred-1'
        mock_credential.device_type = 'key'
        mock_credential.device_name = 'Key'
        mock_credential.last_used_at = None
        mock_credential.created_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = [mock_credential]

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.list_credentials(user_id=1)
                assert isinstance(result, list)

    def test_list_credentials_with_tenant_filter(self):
        """Test listing credentials with tenant filter."""
        auth = BiometricAuth()
        mock_credential = MagicMock()
        mock_credential.id = 1
        mock_credential.credential_id = 'cred-1'
        mock_credential.device_type = 'key'
        mock_credential.device_name = 'Key'
        mock_credential.last_used_at = None
        mock_credential.created_at = None

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = [mock_credential]

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('flask.g', tenant_id=5):
                    result = auth.list_credentials(user_id=1)
                    assert isinstance(result, list)


class TestCreateChallenge:
    """Tests for create_challenge method."""

    def test_create_challenge_default(self):
        """Test creating challenge with defaults."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db') as mock_db:
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='challenge123'):
                    result = auth.create_challenge()
                    assert result == 'challenge123'
                    mock_db.session.add.assert_called_once()

    def test_create_challenge_with_parameters(self):
        """Test creating challenge with custom parameters."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db') as mock_db:
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='ch'):
                    result = auth.create_challenge(
                        user_id=42,
                        challenge_type='registration',
                        ttl_minutes=10,
                        tenant_id=5,
                    )
                    assert result == 'ch'
                    mock_db.session.add.assert_called_once()

    def test_create_challenge_resolves_tenant(self):
        """Test challenge resolves tenant from instance."""
        auth = BiometricAuth(tenant_id=1)
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='ch'):
                    result = auth.create_challenge()
                    assert result == 'ch'

    def test_create_challenge_resolves_tenant_from_g(self):
        """Test challenge resolves tenant from flask.g."""
        auth = BiometricAuth()
        mock_g = MagicMock()
        mock_g.tenant_id = 7
        with patch('app.integrations.devices.biometric.db'):
            with patch('app.integrations.devices.biometric.safe_commit'):
                with patch('app.integrations.devices.biometric.secrets.token_urlsafe', return_value='ch'):
                    with patch('flask.g', mock_g):
                        result = auth.create_challenge()
                        assert result == 'ch'


class TestConsumeChallenge:
    """Tests for consume_challenge method."""

    def test_consume_challenge_not_found(self):
        """Test when challenge not found."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = None

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.consume_challenge('nonexistent')
                assert result is False

    def test_consume_challenge_expired(self):
        """Test when challenge is expired."""
        auth = BiometricAuth(tenant_id=1)
        mock_challenge = MagicMock()
        mock_challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        mock_challenge.used = False

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_challenge

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.consume_challenge('expired-challenge')
                assert result is False

    def test_consume_challenge_success(self):
        """Test successful challenge consumption."""
        auth = BiometricAuth(tenant_id=1)
        mock_challenge = MagicMock()
        mock_challenge.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_challenge.used = False

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_challenge

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.consume_challenge('valid-challenge')
                    assert result is True
                    assert mock_challenge.used is True

    def test_consume_challenge_with_type_filter(self):
        """Test consuming with challenge_type filter."""
        auth = BiometricAuth(tenant_id=1)
        mock_challenge = MagicMock()
        mock_challenge.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_challenge.used = False

        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.first.return_value = mock_challenge

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.consume_challenge('ch', challenge_type='authentication')
                    assert result is True

    def test_consume_challenge_without_type_filter(self):
        """Test consuming without challenge_type filter."""
        auth = BiometricAuth(tenant_id=1)
        mock_challenge = MagicMock()
        mock_challenge.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_query = MagicMock()
        # When challenge_type is None, filter_by is not called
        mock_query.first.return_value = mock_challenge

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                with patch('app.integrations.devices.biometric.safe_commit'):
                    result = auth.consume_challenge('ch')
                    assert result is True


class TestIsEnabled:
    """Tests for is_enabled method."""

    def test_is_enabled_true(self):
        """Test is_enabled returns True when credentials exist."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 5

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.is_enabled(user_id=1)
                assert result is True

    def test_is_enabled_false(self):
        """Test is_enabled returns False when no credentials."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 0

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.is_enabled()
                assert result is False

    def test_is_enabled_with_user_id(self):
        """Test is_enabled with user_id filter."""
        auth = BiometricAuth()
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 1

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.is_enabled(user_id=1)
                assert result is True

    def test_is_enabled_resolves_tenant(self):
        """Test is_enabled resolves tenant."""
        auth = BiometricAuth(tenant_id=1)
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 1

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.is_enabled()
                assert result is True

    def test_is_enabled_no_user_id_no_tenant(self):
        """Test is_enabled with no user_id and no tenant."""
        auth = BiometricAuth()
        mock_query = MagicMock()
        mock_query.filter_by.return_value = mock_query
        mock_query.count.return_value = 3

        with patch('app.integrations.devices.biometric.select', return_value=mock_query):
            with patch('app.integrations.devices.biometric.db'):
                result = auth.is_enabled()
                assert result is True


class TestLogger:
    """Tests for module-level logger."""

    def test_logger_exists(self):
        """Test that module-level logger exists."""
        assert logger is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
