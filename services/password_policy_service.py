"""
Password Policy Service — enforce NIST SP 800-63B compliant passwords
Medical System Password Policy Enforcement
"""

import re
import hashlib
import requests
from typing import Dict, List, Tuple, Optional


class PasswordPolicyError(Exception):
    """Raised when a password fails policy validation."""
    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__("Password policy violations: " + "; ".join(violations))


class PasswordPolicyService:
    """
    Configurable password policy enforcement for commercial medical systems.
    
    Defaults align with NIST SP 800-63B + healthcare hardening:
    - Minimum 12 characters (NIST recommends 8, healthcare should be 12+)
    - Complexity: upper, lower, digit, special
    - No common passwords (HIBP breach database check)
    - No password reuse (history check)
    - Maximum 128 characters (prevent DoS via hashing)
    """

    DEFAULT_CONFIG = {
        'min_length': 12,
        'max_length': 128,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_digit': True,
        'require_special': True,
        'special_chars': r"!@#$%^&*()_+-=[]{}|;:,.<>?",
        'check_breach_database': True,
        'max_breach_count': 0,  # 0 = never allow breached passwords
        'prevent_reuse_count': 5,  # remember last N passwords
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

    def validate(self, password: str, user_context: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        """
        Validate a password against the configured policy.
        
        Args:
            password: The plaintext password to validate
            user_context: Optional dict with user info (username, email, etc.)
                         to prevent password containing personal info
        
        Returns:
            (is_valid, list_of_violation_messages)
        """
        violations = []
        cfg = self.config

        # Length checks
        if len(password) < cfg['min_length']:
            violations.append(
                f"Password must be at least {cfg['min_length']} characters long"
            )
        if len(password) > cfg['max_length']:
            violations.append(
                f"Password must not exceed {cfg['max_length']} characters"
            )

        # Complexity checks
        if cfg['require_uppercase'] and not re.search(r'[A-Z]', password):
            violations.append("Password must contain at least one uppercase letter")
        if cfg['require_lowercase'] and not re.search(r'[a-z]', password):
            violations.append("Password must contain at least one lowercase letter")
        if cfg['require_digit'] and not re.search(r'\d', password):
            violations.append("Password must contain at least one digit")
        if cfg['require_special']:
            special_pattern = f"[{re.escape(cfg['special_chars'])}]"
            if not re.search(special_pattern, password):
                violations.append(
                    f"Password must contain at least one special character ({cfg['special_chars']})"
                )

        # Personal info check
        if user_context:
            lowered = password.lower()
            for key in ('username', 'email', 'first_name', 'last_name', 'phone'):
                value = (user_context.get(key) or '').lower().strip()
                if value and len(value) >= 3 and value in lowered:
                    violations.append(
                        f"Password must not contain your {key.replace('_', ' ')}"
                    )

        # Breach database check
        if cfg['check_breach_database'] and not violations:
            breach_count = self._check_hibp_breach(password)
            if breach_count > cfg['max_breach_count']:
                violations.append(
                    "This password has appeared in known data breaches. Please choose a different password."
                )

        return (len(violations) == 0, violations)

    def validate_or_raise(self, password: str, user_context: Optional[Dict] = None) -> None:
        """Validate and raise PasswordPolicyError if violations exist."""
        is_valid, violations = self.validate(password, user_context)
        if not is_valid:
            raise PasswordPolicyError(violations)

    def _check_hibp_breach(self, password: str) -> int:
        """
        Check password against Have I Been Pwned API using k-anonymity.
        Returns the breach count (0 if not found or API unavailable).
        """
        try:
            # SHA1 is required by the HIBP k-anonymity API (lookup key, not
            # a security control) — only the first 5 chars leave the process.
            sha1 = hashlib.sha1(password.encode('utf-8'), usedforsecurity=False).hexdigest().upper()
            prefix = sha1[:5]
            suffix = sha1[5:]
            resp = requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                timeout=(3, 5),
                headers={'Add-Padding': 'true'}
            )
            resp.raise_for_status()
            for line in resp.text.splitlines():
                parts = line.split(':')
                if len(parts) == 2 and parts[0].upper() == suffix:
                    return int(parts[1])
        except Exception as e:
            # Fail-open on API unavailability — log but don't block registration
            pass
        return 0

    def check_history(self, password: str, history_hashes: List[str]) -> bool:
        """
        Check if password matches any in the provided history list.
        Uses Werkzeug check_password_hash compatible comparison.
        """
        from werkzeug.security import check_password_hash
        for old_hash in history_hashes:
            if check_password_hash(old_hash, password):
                return False
        return True

    def generate_password(self, length: int = 16) -> str:
        """Generate a compliant random password."""
        import secrets
        import string
        alphabet = (
            string.ascii_uppercase +
            string.ascii_lowercase +
            string.digits +
            self.config['special_chars']
        )
        while True:
            password = ''.join(secrets.choice(alphabet) for _ in range(length))
            is_valid, _ = self.validate(password)
            if is_valid:
                return password


# Module-level singleton for import convenience
_default_service = None

def get_password_policy_service(config: Optional[Dict] = None) -> PasswordPolicyService:
    """Get or create the default password policy service."""
    global _default_service
    if _default_service is None or config is not None:
        _default_service = PasswordPolicyService(config)
    return _default_service
