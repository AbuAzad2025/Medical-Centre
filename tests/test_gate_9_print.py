"""Gate 9 — print_base adoption for pharmacy sale + prescription branding (G-114, G-155)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.shared.print_context import resolve_print_context


class TestPrintContextPharmacySale:
    def test_pharmacy_sale_doc_type_registered(self):
        ctx = resolve_print_context('pharmacy_sale')
        assert ctx['doc_type'] == 'pharmacy_sale'
        assert 'primary_color' in ctx


class TestPharmacySalePrintTemplate:
    def test_print_template_uses_print_shell(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            sale = SimpleNamespace(
                id=1,
                sale_number='PS-001',
                customer_name='عميل',
                payment_method='cash',
                transaction_id=None,
                card_last_digits=None,
                total_amount=50.0,
                notes=None,
                created_at=datetime.now(timezone.utc),
                items=[
                    SimpleNamespace(
                        medication_name='باراسيتامول',
                        quantity=2,
                        unit_price=25.0,
                        total_price=50.0,
                    ),
                ],
            )
            html = render_template(
                'print/pharmacy_sale_receipt.html',
                sale=sale,
                cashier=None,
                printed_at=datetime.now(timezone.utc),
            )
        assert 'print-doc' in html
        assert 'print.css' in html
        assert 'باراسيتامول' in html
        assert 'إيصال بيع صيدلية' in html


class TestPrescriptionPrintBranding:
    def test_prescription_shows_tenant_org_not_hardcoded_clinic(self, app, test_tenant):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            prescription = SimpleNamespace(
                id=1,
                prescription_number='RX-1',
                status='ACTIVE',
                diagnosis='حمى',
                notes=None,
                created_at=datetime.now(timezone.utc),
                patient=SimpleNamespace(
                    full_name='مريض اختبار',
                    national_id='123',
                    phone='0599000000',
                    gender='ذكر',
                ),
                doctor=SimpleNamespace(full_name='د. أحمد', license_number='L1'),
                items=SimpleNamespace(all=lambda: []),
            )
            html = render_template('print/prescription.html', prescription=prescription)
        assert 'المنشأة' in html
        assert 'مريض اختبار' in html
        assert 'print-doc--prescription' in html


class TestLabResultPrintTemplate:
    def test_lab_result_uses_print_shell_and_localizes_status(self, app):
        with app.app_context():
            from flask import render_template
            from types import SimpleNamespace

            lab_request = SimpleNamespace(
                id=7,
                request_number='LAB-7',
                status='DONE',
                notes='فحص دوري',
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                patient=SimpleNamespace(
                    full_name='مريض مختبر',
                    national_id='999',
                    phone='0599111222',
                ),
                requester=SimpleNamespace(full_name='د. سارة'),
                results=[
                    SimpleNamespace(
                        test_name='CBC',
                        value='5.2',
                        unit='10^9/L',
                        reference_range='4-11',
                        status='VALIDATED',
                        performer=SimpleNamespace(full_name='فني المختبر'),
                    ),
                ],
            )
            html = render_template(
                'print/lab_result.html',
                lab_request=lab_request,
                qr_data_uri=None,
                age_years=30,
                printed_at='2026-06-23 22:30',
            )
        assert 'print-doc--lab_result' in html
        assert 'print.css' in html
        assert 'مريض مختبر' in html
        assert 'منتهٍ' in html  # OrderState.DONE localized
        assert 'مُعتمد' in html  # LabResultStatus.VALIDATED localized
        assert 'DONE' not in html
        assert 'VALIDATED' not in html


class TestPharmacySalePrintRoute:
    def test_print_route_renders_print_shell(self, auth_client, test_medications):
        med = test_medications[0]
        sell = auth_client.post(
            '/medication/pos/sell',
            data=json.dumps({
                'items': [{'medication_id': med.id, 'quantity': 1}],
                'payment_method': 'cash',
                'customer_name': 'زبون',
            }),
            content_type='application/json',
        )
        assert sell.status_code == 200
        sale_id = sell.get_json()['sale_id']
        resp = auth_client.get(f'/medication/sales/{sale_id}/print')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'print-doc--pharmacy_sale' in text
        assert 'زبون' in text
        assert 'inline' not in text.lower() or '<style>' not in text.split('<style id="print-brand-vars">')[0]
