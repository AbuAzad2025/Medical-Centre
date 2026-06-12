"""
Biometric authentication interface (fingerprint / face recognition)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BiometricAuth:
    """
    Interface for biometric devices.
    Implementations can be swapped via strategy pattern.
    """

    def __init__(self, driver_name: Optional[str] = None):
        self.driver_name = driver_name or "mock"
        self._driver = self._load_driver()

    def _load_driver(self):
        # Future: load real SDKs (e.g., DigitalPersona, ZKTeco)
        return None

    def enroll(self, user_id: int, template: bytes) -> bool:
        """Store a new biometric template for a user."""
        logger.info("Enrolling biometric for user %s", user_id)
        # TODO: persist template in DB or external device
        return True

    def verify(self, user_id: int, template: bytes) -> bool:
        """Match a captured template against stored template."""
        logger.info("Verifying biometric for user %s", user_id)
        # TODO: implement real matching
        return True

    def is_enabled(self) -> bool:
        return False  # Disabled until hardware is configured
