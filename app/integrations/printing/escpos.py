"""
ESC/POS Thermal Printer driver
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ThermalPrinter:
    """Sends ESC/POS commands to a thermal receipt printer."""

    def __init__(self, port: Optional[str] = None):
        self.port = port or os.environ.get("THERMAL_PRINTER_PORT", "COM3")

    def _encode(self, text: str) -> bytes:
        return text.encode("cp720", errors="replace")

    def print_receipt(self, receipt_data: dict) -> bytes:
        """Build ESC/POS byte stream for a receipt."""
        buf = bytearray()
        buf += b"\x1b@"          # Initialize
        buf += b"\x1b!\x30"     # Double-width, double-height
        buf += self._encode(receipt_data.get("header", "Medical Centre\n"))
        buf += b"\x1b!\x00"     # Normal text
        buf += self._encode("=" * 32 + "\n")
        buf += self._encode(f"Date: {receipt_data.get('date', '')}\n")
        buf += self._encode(f"Visit #: {receipt_data.get('visit_number', '')}\n")
        buf += self._encode(f"Patient: {receipt_data.get('patient_name', '')}\n")
        buf += self._encode("-" * 32 + "\n")
        for item in receipt_data.get("items", []):
            line = f"{item.get('name', '')[:20]:<20} {item.get('amount', ''):>10}\n"
            buf += self._encode(line)
        buf += self._encode("-" * 32 + "\n")
        buf += b"\x1b!\x20"     # Double-width
        buf += self._encode(f"TOTAL: {receipt_data.get('total', '')}\n")
        buf += b"\x1b!\x00"     # Normal
        buf += self._encode("=" * 32 + "\n")
        buf += self._encode(receipt_data.get("footer", "Thank you\n"))
        buf += b"\x1dV\x42\x03"  # Cut paper (partial)
        return bytes(buf)

    def send(self, data: bytes) -> bool:
        """Send bytes to printer port (Windows COM / Linux /dev/usb/lp0)."""
        try:
            import serial
            with serial.Serial(self.port, 9600, timeout=5) as ser:
                ser.write(data)
            return True
        except Exception as e:
            logger.error(f"Thermal printer error: {e}")
            return False
