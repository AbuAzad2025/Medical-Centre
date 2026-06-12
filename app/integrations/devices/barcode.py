"""
Barcode Scanner input handler
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class BarcodeScanner:
    """Parses barcode input from USB HID scanner devices."""

    @staticmethod
    def handle_input(raw: str) -> dict:
        """Parse raw barcode string into structured data."""
        raw = raw.strip()
        if not raw:
            return {"type": "unknown", "value": ""}

        # Patient ID: P-12345
        if raw.upper().startswith("P-"):
            return {"type": "patient", "patient_id": raw[2:]}

        # Medication / Inventory batch: M-XXXXX
        if raw.upper().startswith("M-"):
            return {"type": "medication", "code": raw[2:]}

        # GS1 / GTIN-14 / EAN-13 (all digits, 8-14 chars)
        if raw.isdigit() and 8 <= len(raw) <= 14:
            return {"type": "gtin", "value": raw}

        # Generic
        return {"type": "raw", "value": raw}
