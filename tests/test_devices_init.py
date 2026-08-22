"""Tests for app.integrations.devices.__init__ module.

Covers the device integrations package exports.
"""

import pytest


class TestDevicePackage:
    """Tests for the devices package __init__."""

    def test_imports_barcode_scanner(self):
        """Test BarcodeScanner is importable from package."""
        from app.integrations.devices import BarcodeScanner

        assert BarcodeScanner is not None

    def test_imports_biometric_auth(self):
        """Test BiometricAuth is importable from package."""
        from app.integrations.devices import BiometricAuth

        assert BiometricAuth is not None

    def test_all_exports(self):
        """Test __all__ exports are correct."""
        from app.integrations.devices import __all__

        assert 'BarcodeScanner' in __all__
        assert 'BiometricAuth' in __all__

    def test_importable_as_module(self):
        """Test package can be imported as module."""
        from app.integrations.devices import barcode, biometric

        assert barcode.BarcodeScanner is not None
        assert biometric.BiometricAuth is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
