"""
PII Redaction tests.
Verifies that PiiRedactingFormatter scrubs SSN, national ID, email, phone, credit card,
password, and API keys from log messages.
"""

from __future__ import annotations

import logging
import re

from config import PII_PATTERNS, PiiRedactingFormatter


class TestPiiRedaction:
    """Test PII redaction in log messages."""

    def make_record(self, msg):
        """Create a log record with the given message."""
        return logging.LogRecord(
            name='test.logger',
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_ssn_redacted(self):
        """US SSN pattern is redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('User SSN: 123-45-6789 verified')
        result = formatter.format(record)
        assert '[SSN]' in result
        assert '123-45-6789' not in result

    def test_national_id_redacted(self):
        """14-digit national ID is redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('Patient national ID 12345678901234 on file')
        result = formatter.format(record)
        assert '[NATIONAL_ID]' in result
        assert '12345678901234' not in result

    def test_email_redacted(self):
        """Email addresses are redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('Contact doctor@hospital.com for details')
        result = formatter.format(record)
        assert '[EMAIL]' in result
        assert 'doctor@hospital.com' not in result

    def test_phone_redacted(self):
        """Phone numbers are redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('Call +966 50 123 4567 now')
        result = formatter.format(record)
        assert '[PHONE]' in result
        assert '50 123 4567' not in result

    def test_credit_card_redacted(self):
        """Credit card numbers are redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('Payment with 4111 1111 1111 1111 approved')
        result = formatter.format(record)
        assert '[CARD]' in result
        assert '4111 1111 1111 1111' not in result

    def test_password_redacted(self):
        """Passwords in logs are redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('User login password=secret123 success')
        result = formatter.format(record)
        assert 'password=[REDACTED]' in result
        assert 'secret123' not in result

    def test_api_key_redacted(self):
        """API keys in logs are redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('API call with api_key=sk_live_abcdef123456')
        result = formatter.format(record)
        assert 'api_key=[REDACTED]' in result
        assert 'sk_live_abcdef123456' not in result

    def test_multiple_pii_in_one_message(self):
        """Multiple PII types in one message all get redacted."""
        formatter = PiiRedactingFormatter('%(message)s')
        msg = 'User john@doe.com with SSN 123-45-6789 paid with card 4111-1111-1111-1111'
        record = self.make_record(msg)
        result = formatter.format(record)
        assert '[EMAIL]' in result
        assert '[SSN]' in result
        assert '[CARD]' in result
        assert 'john@doe.com' not in result
        assert '123-45-6789' not in result
        assert '4111-1111-1111-1111' not in result

    def test_non_pii_preserved(self):
        """Non-PII content is preserved."""
        formatter = PiiRedactingFormatter('%(message)s')
        record = self.make_record('Patient John Doe visited clinic')
        result = formatter.format(record)
        assert result == 'Patient John Doe visited clinic'

    def test_patterns_compile(self):
        """All PII patterns compile without error."""
        for pattern, replacement in PII_PATTERNS:
            assert isinstance(pattern, re.Pattern)
            assert isinstance(replacement, str)
            assert len(replacement) > 0
