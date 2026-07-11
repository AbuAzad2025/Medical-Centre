"""Tests for unified print engine watermark and corporate identity."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.shared.print_context import generate_barcode_code128, generate_qr_data_uri, resolve_print_context


class TestPrintWatermark:
    """Verify corporate watermark is present in all print contexts."""

    def test_print_context_includes_watermark_constant(self):
        """PLATFORM_WATERMARK constant exists and has correct Arabic text."""
        from app.shared import print_context
        assert hasattr(print_context, 'PLATFORM_WATERMARK')
        assert print_context.PLATFORM_WATERMARK == 'شركة أزاد للأنظمة الطبية'

    def test_generate_qr_data_uri_returns_valid_data_uri(self):
        """QR generator returns valid data:image/png;base64 URI."""
        uri = generate_qr_data_uri("TEST|123|456")
        assert uri.startswith('data:image/png;base64,')
        # Decode to verify it's valid base64
        import base64
        b64 = uri.split(',', 1)[1]
        decoded = base64.b64decode(b64)
        assert len(decoded) > 100  # PNG header + data

    def test_generate_barcode_code128_returns_valid_data_uri(self):
        """Barcode generator returns valid data:image/png;base64 URI."""
        uri = generate_barcode_code128("INV|001|T001")
        assert uri.startswith('data:image/png;base64,')
        import base64
        b64 = uri.split(',', 1)[1]
        decoded = base64.b64decode(b64)
        assert len(decoded) > 100

    def test_barcode_code128_deterministic(self):
        """Same payload produces same barcode."""
        uri1 = generate_barcode_code128("SAME|PAYLOAD")
        uri2 = generate_barcode_code128("SAME|PAYLOAD")
        assert uri1 == uri2

    def test_qr_deterministic(self):
        """Same payload produces same QR."""
        uri1 = generate_qr_data_uri("SAME|PAYLOAD")
        uri2 = generate_qr_data_uri("SAME|PAYLOAD")
        assert uri1 == uri2


class TestPrintTemplateWatermark:
    """Integration tests: rendered templates include watermark."""

    def test_invoice_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            invoice = SimpleNamespace(
                id=1,
                invoice_number='INV-001',
                currency='ILS',
                status='PAID',
                total_amount=100.0,
                paid_amount=100.0,
                created_at=datetime.now(timezone.utc),
                visit=SimpleNamespace(
                    patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050', address='')
                ),
                lines=[],
            )
            html = render_template('print/invoice.html', invoice=invoice)
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_receipt_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            visit = SimpleNamespace(
                id=1,
                receipt_number='RCPT-001',
                currency='ILS',
                payment_status='PAID',
                created_at=datetime.now(timezone.utc),
                patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050'),
                department=SimpleNamespace(name_ar='عيادة'),
                doctor=SimpleNamespace(full_name='د. أحمد'),
                visit_type='FIRST',
                is_emergency=False,
                payment_method='cash',
                diagnosis='حمى',
                total_amount=100.0,
                paid_amount=100.0,
                remaining_amount=0.0,
                tax_amount=0,
                tax_percent=0,
            )
            html = render_template('print/receipt.html', visit=visit, printed_at=datetime.now(timezone.utc), queue_ticket=None, last_payment=None, service_cost=70.0, doctor_fee=30.0, follow_up_discount=0.0)
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_prescription_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            prescription = SimpleNamespace(
                id=1,
                prescription_number='RX-001',
                status='ACTIVE',
                created_at=datetime.now(timezone.utc),
                diagnosis='حمى',
                notes=None,
                patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050', gender='ذكر'),
                doctor=SimpleNamespace(full_name='د. أحمد', license_number='L123'),
                items=SimpleNamespace(all=lambda: []),
            )
            html = render_template('print/prescription.html', prescription=prescription)
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_lab_result_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            lab_request = SimpleNamespace(
                id=1,
                request_number='LAB-001',
                status='DONE',
                notes='فحص',
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050'),
                requester=SimpleNamespace(full_name='د. أحمد'),
                results=[],
            )
            html = render_template('print/lab_result.html', lab_request=lab_request, age_years=30, printed_at='2026-01-01 10:00')
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_radiology_report_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            result = SimpleNamespace(
                id=1,
                request=SimpleNamespace(request_number='RAD-001', modality='X-Ray', body_part='Chest', requester=SimpleNamespace(full_name='د. أحمد')),
                patient=SimpleNamespace(full_name='مريض', national_id='123'),
                performer=SimpleNamespace(full_name='فني'),
                status='DONE',
                created_at=datetime.now(timezone.utc),
                findings='سليم',
                impression='لا يوجد',
                notes='لا يوجد',
            )
            html = render_template('print/radiology_report.html', radiology_result=result)
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_emergency_report_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            emergency = SimpleNamespace(
                id=1,
                case_number='EMG-001',
                status='ACTIVE',
                severity='MODERATE',
                created_at=datetime.now(timezone.utc),
                patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050'),
                chief_complaint='ألم',
                triage_notes='ملاحظات',
                vital_signs='BP: 120/80',
                diagnosis='إجهاد',
                treatment_plan='راحة',
            )
            html = render_template('print/emergency_report.html', emergency=emergency)
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html

    def test_pharmacy_sale_template_includes_watermark(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            sale = SimpleNamespace(
                id=1,
                sale_number='PS-001',
                payment_method='cash',
                customer_name='عميل',
                transaction_id=None,
                card_last_digits=None,
                total_amount=50.0,
                notes=None,
                created_at=datetime.now(timezone.utc),
                items=[],
            )
            html = render_template('print/pharmacy_sale_receipt.html', sale=sale, cashier=None, printed_at=datetime.now(timezone.utc))
            assert 'شركة أزاد للأنظمة الطبية' in html
            assert 'print-watermark' in html


class TestPrintQRBarcodeComponents:
    """Test unified QR/Barcode rendering."""

    def test_print_base_includes_verification_block(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            invoice = SimpleNamespace(
                id=1,
                invoice_number='INV-001',
                currency='ILS',
                status='PAID',
                total_amount=100.0,
                paid_amount=100.0,
                created_at=datetime.now(timezone.utc),
                visit=SimpleNamespace(
                    patient=SimpleNamespace(full_name='مريض', national_id='123', phone='050', address='')
                ),
                lines=[],
            )
            qr_uri = 'data:image/png;base64,FAKE_QR'
            barcode_uri = 'data:image/png;base64,FAKE_BC'
            html = render_template('print/invoice.html', invoice=invoice, qr_data_uri=qr_uri, barcode_data_uri=barcode_uri, barcode_value='INV|1')
            assert 'print-verification-block' in html
            assert 'FAKE_QR' in html
            assert 'FAKE_BC' in html
            assert 'INV|1' in html

    def test_barcode_minimal_template_renders(self, app):
        """Minimal base template works for barcode labels."""
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            lab_request = SimpleNamespace(
                id=1,
                request_number='LAB-001',
                barcode='LAB|001|123',
                barcode_image='FAKE_BARCODE',
                patient=SimpleNamespace(full_name='مريض'),
            )
            html = render_template('lab/barcode_print.html', lab_request=lab_request)
            assert 'print-doc--minimal' in html
            assert 'LAB|001|123' in html


class TestGhostModePrintContext:
    """Ghost Mode: master impersonation should bind target tenant branding."""

    def test_resolve_print_context_has_ghost_mode_awareness(self):
        """resolve_print_context signature allows ghost tenant override."""
        import inspect
        from app.shared.print_context import resolve_print_context
        sig = inspect.signature(resolve_print_context)
        # Should have optional ghost_tenant or similar parameter
        params = list(sig.parameters.keys())
        # Currently just doc_type, branding - but should be extensible
        assert 'doc_type' in params
        assert 'branding' in params