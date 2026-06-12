"""
ZPL Label Printer driver
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ZPLLabelPrinter:
    """Generates ZPL II commands for label printers (e.g., Zebra)."""

    def __init__(self, dpi: int = 203, width_mm: int = 50, height_mm: int = 25):
        self.dpi = dpi
        self.width_dots = int(width_mm / 25.4 * dpi)
        self.height_dots = int(height_mm / 25.4 * dpi)

    def _build_label(self, lines: list[str], barcode: Optional[str] = None) -> str:
        zpl = f"^XA^PW{self.width_dots}^LL{self.height_dots}"
        zpl += "^FO20,10^A0N,20,20^FD" + "\\&".join(lines) + "^FS"
        if barcode:
            zpl += f"^FO20,{self.height_dots - 40}^B3N,N,30,N,N^FD{barcode}^FS"
        zpl += "^XZ"
        return zpl

    def print_medication_label(self, medication_name: str, batch: str, expiry: str,
                                barcode: Optional[str] = None) -> str:
        zpl = self._build_label(
            [medication_name, f"Batch: {batch}", f"Exp: {expiry}"],
            barcode=barcode
        )
        logger.info("ZPL label generated for %s", medication_name)
        return zpl

    def print_patient_label(self, patient_name: str, visit_number: str,
                           barcode: Optional[str] = None) -> str:
        zpl = self._build_label(
            [patient_name, f"Visit: {visit_number}"],
            barcode=barcode
        )
        return zpl
