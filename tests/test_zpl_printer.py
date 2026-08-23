"""ZPL Label Printer — full coverage (was 35%).

Uses `app` fixture to ensure Flask/SQLAlchemy context is initialized
before importing app package modules.
"""

import pytest


@pytest.fixture(autouse=True)
def _ensure_app(app):
    """Ensure app context exists before importing app package modules."""


class TestZPLLabelPrinter:
    def test_init_defaults(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        p = ZPLLabelPrinter()
        assert p.dpi == 203
        assert p.width_dots > 0

    def test_init_custom(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        p = ZPLLabelPrinter(dpi=300, width_mm=100, height_mm=50)
        assert p.dpi == 300

    def test_build_label_no_barcode(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        zpl = ZPLLabelPrinter()._build_label(['L1', 'L2'])
        assert zpl.startswith('^XA') and '^XZ' in zpl and 'L1' in zpl

    def test_build_label_with_barcode(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        zpl = ZPLLabelPrinter()._build_label(['Item'], barcode='ABC123')
        assert 'ABC123' in zpl and '^B3N' in zpl

    def test_medication_label_full(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        zpl = ZPLLabelPrinter().print_medication_label('Aspirin', 'B01', '2025-01', barcode='M1')
        assert all(x in zpl for x in ('Aspirin', 'B01', 'M1'))

    def test_medication_label_no_barcode(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        assert 'Ibuprofen' in ZPLLabelPrinter().print_medication_label('Ibuprofen', 'B2', '2026')

    def test_patient_label_full(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        zpl = ZPLLabelPrinter().print_patient_label('John', 'V-1', barcode='P1')
        assert all(x in zpl for x in ('John', 'V-1', 'P1'))

    def test_patient_label_no_barcode(self):
        from app.integrations.printing.zpl import ZPLLabelPrinter

        zpl = ZPLLabelPrinter().print_patient_label('Jane', 'V-2')
        assert 'Jane' in zpl and '^XZ' in zpl
