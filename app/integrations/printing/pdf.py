"""
PDF Report Printer — A4 medical reports
"""
import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

class PDFReportPrinter:
    """Generates A4 PDF reports using ReportLab (installed via requirements)."""

    def generate_report(self, title: str, patient_info: dict, sections: list[dict]) -> bytes:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError:
            logger.warning("reportlab not installed; returning empty PDF placeholder")
            return b"%PDF-1.4 placeholder"

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(20 * mm, height - 20 * mm, title)
        c.setFont("Helvetica", 10)
        y = height - 30 * mm
        for k, v in patient_info.items():
            c.drawString(20 * mm, y, f"{k}: {v}")
            y -= 5 * mm

        # Sections
        for section in sections:
            y -= 5 * mm
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20 * mm, y, section.get("heading", ""))
            y -= 5 * mm
            c.setFont("Helvetica", 10)
            for line in section.get("lines", []):
                c.drawString(25 * mm, y, line)
                y -= 4 * mm
                if y < 30 * mm:
                    c.showPage()
                    y = height - 20 * mm

        c.save()
        buffer.seek(0)
        return buffer.read()
