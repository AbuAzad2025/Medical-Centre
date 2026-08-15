"""Tests for app.integrations.devices.barcode module.

Covers the BarcodeScanner class for parsing barcode input.
"""

import pytest

from app.integrations.devices.barcode import BarcodeScanner


class TestHandleInput:
    """Tests for BarcodeScanner.handle_input method."""

    def test_patient_id_barcode(self):
        """Test parsing patient ID barcode (P-XXXXX)."""
        result = BarcodeScanner.handle_input('P-12345')
        assert result == {'type': 'patient', 'patient_id': '12345'}

    def test_patient_id_barcode_lowercase(self):
        """Test parsing lowercase patient ID barcode."""
        result = BarcodeScanner.handle_input('p-ABC123')
        assert result == {'type': 'patient', 'patient_id': 'ABC123'}

    def test_medication_barcode(self):
        """Test parsing medication batch barcode (M-XXXXX)."""
        result = BarcodeScanner.handle_input('M-XYZ789')
        assert result == {'type': 'medication', 'code': 'XYZ789'}

    def test_medication_barcode_lowercase(self):
        """Test parsing lowercase medication barcode."""
        result = BarcodeScanner.handle_input('m-abc123')
        assert result == {'type': 'medication', 'code': 'abc123'}

    def test_gtin_barcode_8_digits(self):
        """Test parsing GTIN barcode with 8 digits."""
        result = BarcodeScanner.handle_input('12345678')
        assert result == {'type': 'gtin', 'value': '12345678'}

    def test_gtin_barcode_14_digits(self):
        """Test parsing GTIN barcode with 14 digits."""
        result = BarcodeScanner.handle_input('12345678901234')
        assert result == {'type': 'gtin', 'value': '12345678901234'}

    def test_gtin_barcode_13_digits(self):
        """Test parsing EAN-13 barcode with 13 digits."""
        result = BarcodeScanner.handle_input('4006381333931')
        assert result == {'type': 'gtin', 'value': '4006381333931'}

    def test_gtin_barcode_10_digits(self):
        """Test parsing GTIN barcode with 10 digits (outside range)."""
        result = BarcodeScanner.handle_input('12345')
        assert result == {'type': 'raw', 'value': '12345'}

    def test_gtin_barcode_15_digits(self):
        """Test parsing barcode with 15 digits (outside range)."""
        result = BarcodeScanner.handle_input('123456789012345')
        assert result == {'type': 'raw', 'value': '123456789012345'}

    def test_generic_raw_barcode(self):
        """Test parsing generic raw barcode."""
        result = BarcodeScanner.handle_input('SOME-DATA-HERE')
        assert result == {'type': 'raw', 'value': 'SOME-DATA-HERE'}

    def test_empty_string(self):
        """Test handling empty string input."""
        result = BarcodeScanner.handle_input('')
        assert result == {'type': 'unknown', 'value': ''}

    def test_whitespace_only(self):
        """Test handling whitespace-only input."""
        result = BarcodeScanner.handle_input('   ')
        assert result == {'type': 'unknown', 'value': ''}

    def test_strips_whitespace(self):
        """Test that input is stripped of whitespace."""
        result = BarcodeScanner.handle_input('  P-12345  ')
        assert result == {'type': 'patient', 'patient_id': '12345'}

    def test_alphanumeric_not_p_or_m(self):
        """Test alphanumeric barcode doesn't match P or M prefix."""
        result = BarcodeScanner.handle_input('A-12345')
        assert result == {'type': 'raw', 'value': 'A-12345'}

    def test_p_with_digits(self):
        """Test P- prefix with various ID formats."""
        result = BarcodeScanner.handle_input('P-001')
        assert result == {'type': 'patient', 'patient_id': '001'}

    def test_m_with_digits(self):
        """Test M- prefix with various code formats."""
        result = BarcodeScanner.handle_input('M-999')
        assert result == {'type': 'medication', 'code': '999'}


class TestHandleInputEdgeCases:
    """Tests for edge cases in handle_input."""

    def test_single_digit_gtin(self):
        """Test single digit (not in GTIN range)."""
        result = BarcodeScanner.handle_input('5')
        assert result == {'type': 'raw', 'value': '5'}

    def test_seven_digits_gtin(self):
        """Test 7 digits (below GTIN range)."""
        result = BarcodeScanner.handle_input('1234567')
        assert result == {'type': 'raw', 'value': '1234567'}

    def test_exact_8_digits(self):
        """Test exactly 8 digits (lower bound for GTIN)."""
        result = BarcodeScanner.handle_input('00000000')
        assert result == {'type': 'gtin', 'value': '00000000'}

    def test_exact_14_digits(self):
        """Test exactly 14 digits (upper bound for GTIN)."""
        result = BarcodeScanner.handle_input('99999999999999')
        assert result == {'type': 'gtin', 'value': '99999999999999'}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
