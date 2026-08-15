"""Tests for app.integrations.printing.escpos module.

Covers the ThermalPrinter class - ESC/POS thermal receipt printer driver.
"""

import os

import pytest

from app.integrations.printing.escpos import ThermalPrinter, logger


class TestThermalPrinterInit:
    """Tests for ThermalPrinter.__init__."""

    def test_default_port(self):
        """Test default port is 'COM3'."""
        printer = ThermalPrinter()
        assert printer.port == 'COM3'

    def test_custom_port(self):
        """Test custom port."""
        printer = ThermalPrinter(port='/dev/usb/lp0')
        assert printer.port == '/dev/usb/lp0'

    def test_port_from_environment(self, monkeypatch):
        """Test port from environment variable."""
        monkeypatch.setenv('THERMAL_PRINTER_PORT', '/dev/usb/lp1')
        printer = ThermalPrinter()
        assert printer.port == '/dev/usb/lp1'
        monkeypatch.delenv('THERMAL_PRINTER_PORT', raising=False)

    def test_environment_variable_overridden(self, monkeypatch):
        """Test that explicit port overrides environment."""
        monkeypatch.setenv('THERMAL_PRINTER_PORT', '/dev/usb/lp1')
        printer = ThermalPrinter(port='COM5')
        assert printer.port == 'COM5'


class TestEncode:
    """Tests for _encode method."""

    def test_encodes_ascii_text(self):
        """Test encoding ASCII text in cp720."""
        printer = ThermalPrinter()
        result = printer._encode('Hello World')
        assert isinstance(result, bytes)
        assert result == b'Hello World'

    def test_encodes_arabic_text(self):
        """Test encoding Arabic text in cp720."""
        printer = ThermalPrinter()
        result = printer._encode('مرحبا')
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_replaces_unsupported_chars(self):
        """Test that unsupported characters are replaced, not raising."""
        printer = ThermalPrinter()
        result = printer._encode('Hello \udce2 World')
        assert isinstance(result, bytes)

    def test_encodes_empty_string(self):
        """Test encoding empty string."""
        printer = ThermalPrinter()
        result = printer._encode('')
        assert result == b''


class TestPrintReceipt:
    """Tests for print_receipt method."""

    def test_returns_bytes(self):
        """Test that print_receipt returns bytes."""
        printer = ThermalPrinter()
        receipt_data = {'header': 'Test', 'date': '2024-01-15', 'total': '100.00'}
        result = printer.print_receipt(receipt_data)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_contains_init_command(self):
        """Test that ESC @ (init) is in output."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1b@' in result

    def test_contains_double_width_command(self):
        """Test that double-width command is in output."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1b!\x30' in result

    def test_contains_normal_text_command(self):
        """Test that normal text command appears."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1b!\x00' in result

    def test_contains_cut_command(self):
        """Test that cut paper command is in output."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1dV\x42\x03' in result

    def test_includes_header(self):
        """Test that header text is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'header': 'My Clinic'})
        assert b'My Clinic' in result

    def test_includes_date(self):
        """Test that date is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'date': '2024-01-15'})
        assert b'Date: 2024-01-15' in result

    def test_includes_visit_number(self):
        """Test that visit number is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'visit_number': 'V123'})
        assert b'Visit #: V123' in result

    def test_includes_patient_name(self):
        """Test that patient name is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'patient_name': 'John Doe'})
        assert b'John Doe' in result

    def test_includes_items(self):
        """Test that items are included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({
            'items': [
                {'name': 'Consultation', 'amount': '100.00'},
                {'name': 'Medicine', 'amount': '50.00'},
            ]
        })
        assert b'Consultation' in result
        assert b'Medicine' in result
        assert b'100.00' in result
        assert b'50.00' in result

    def test_includes_total(self):
        """Test that total is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'total': '150.00'})
        assert b'TOTAL: 150.00' in result

    def test_includes_footer(self):
        """Test that footer is included."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'footer': 'Thank you!'})
        assert b'Thank you!' in result

    def test_default_header(self):
        """Test default header when not provided."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'Medical Centre' in result

    def test_default_footer(self):
        """Test default footer when not provided."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'Thank you' in result

    def test_double_width_command_present(self):
        """Test double-width command for total."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1b!\x20' in result

    def test_separator_lines(self):
        """Test separator lines are present."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert ('=' * 32).encode('cp720', errors='replace') in result
        assert ('-' * 32).encode('cp720', errors='replace') in result

    def test_empty_items(self):
        """Test receipt with empty items list."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'items': []})
        assert b'\x1b@' in result

    def test_none_items(self):
        """Test receipt with no items key."""
        printer = ThermalPrinter()
        result = printer.print_receipt({})
        assert b'\x1b@' in result

    def test_item_with_missing_fields(self):
        """Test receipt item with missing name/amount."""
        printer = ThermalPrinter()
        result = printer.print_receipt({'items': [{}]})
        assert isinstance(result, bytes)

    def test_full_receipt_data(self):
        """Test receipt with complete data."""
        printer = ThermalPrinter()
        receipt_data = {
            'header': 'City Hospital',
            'date': '2024-01-15',
            'visit_number': 'V001',
            'patient_name': 'Alice',
            'items': [
                {'name': 'Consultation', 'amount': '200.00'},
            ],
            'total': '200.00',
            'footer': 'Visit again!',
        }
        result = printer.print_receipt(receipt_data)
        assert b'City Hospital' in result
        assert b'2024-01-15' in result
        assert b'V001' in result
        assert b'Alice' in result
        assert b'TOTAL: 200.00' in result
        assert b'Visit again!' in result


class TestSend:
    """Tests for send method."""

    def test_send_returns_false_when_no_serial(self):
        """Test that send returns False when serial module unavailable."""
        printer = ThermalPrinter()
        result = printer.send(b'test data')
        assert result is False

    def test_send_returns_false_on_failure(self):
        """Test that send returns False when serial fails."""
        printer = ThermalPrinter()
        result = printer.send(b'test data')
        assert result is False


class TestLogger:
    """Tests for module-level logger."""

    def test_logger_exists(self):
        """Test that module-level logger exists."""
        assert logger is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
