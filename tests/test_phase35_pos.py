"""Tests for §35 — POS charge + pharmacy payment (G-116, G-122)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.shared.user_messages import localize_pos_message, user_message
from models.medication import PharmacySale


class TestUserMessages:
    def test_pos_not_enabled_message(self):
        msg = localize_pos_message('خدمة الدفع غير مفعلة (not enabled)')
        assert 'not enabled' not in msg.lower()
        assert 'جهاز البطاقة' in msg

    def test_pos_connection_message(self):
        msg = localize_pos_message('تعذر الاتصال بجهاز الدفع حالياً (conn)')
        assert '(conn)' not in msg
        assert 'الاتصال' in msg

    def test_user_message_code(self):
        assert 'غير مصرح' in user_message('pos_unauthorized')


@pytest.fixture
def reception_user(app, test_tenant):
    from models.user import User
    from app_factory import db as _db

    u = User.query.filter_by(username='reception_pos_test').first()
    if not u:
        u = User(
            username='reception_pos_test',
            email='reception@test.local',
            full_name='استقبال اختبار',
            role='reception',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture
def reception_client(app, client, reception_user, test_tenant):
    from tests.tenant_context import login_test_client

    login_test_client(client, reception_user, test_tenant)
    return client


class TestReceptionPosCharge:
    @patch('services.pos_terminal_service.PosTerminalService.charge')
    def test_reception_role_allowed(self, mock_charge, reception_client):
        mock_charge.return_value = {
            'success': True,
            'transaction_id': 'TXN1',
            'card_last_digits': '1234',
            'amount': 50.0,
        }
        resp = reception_client.post(
            '/reception/pos/charge',
            data={'amount': '50'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['card_last_digits'] == '1234'

    @patch('services.pos_terminal_service.PosTerminalService.charge')
    def test_disabled_pos_friendly_message(self, mock_charge, reception_client):
        mock_charge.return_value = {
            'success': False,
            'message': 'خدمة الدفع الإلكتروني غير مفعلة حالياً (not enabled)',
        }
        resp = reception_client.post('/reception/pos/charge', data={'amount': '10'})
        assert resp.status_code == 500
        data = resp.get_json()
        assert 'not enabled' not in (data.get('message') or '').lower()

    def test_invalid_amount(self, reception_client):
        resp = reception_client.post('/reception/pos/charge', data={'amount': '0'})
        assert resp.status_code == 400


class TestPharmacyPosSell:
    @patch('services.pos_terminal_service.PosTerminalService.charge')
    def test_cash_sale(self, mock_charge, auth_client, test_medications):
        med = test_medications[0]
        resp = auth_client.post(
            '/medication/pos/sell',
            data=json.dumps({
                'items': [{'medication_id': med.id, 'quantity': 1}],
                'payment_method': 'cash',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        sale = PharmacySale.query.get(data['sale_id'])
        assert sale.payment_method == 'cash'

    def test_card_sale_requires_transaction(self, auth_client, test_medications):
        med = test_medications[0]
        resp = auth_client.post(
            '/medication/pos/sell',
            data=json.dumps({
                'items': [{'medication_id': med.id, 'quantity': 1}],
                'payment_method': 'card',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'بطاقة' in resp.get_json().get('message', '')

    def test_card_sale_with_transaction(self, auth_client, test_medications):
        med = test_medications[0]
        resp = auth_client.post(
            '/medication/pos/sell',
            data=json.dumps({
                'items': [{'medication_id': med.id, 'quantity': 1}],
                'payment_method': 'card',
                'transaction_id': 'TXN-99',
                'card_last_digits': '4321',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        sale = PharmacySale.query.get(resp.get_json()['sale_id'])
        assert sale.payment_method == 'card'
        assert sale.transaction_id == 'TXN-99'

    @patch('services.pos_terminal_service.PosTerminalService.charge')
    def test_pharmacy_pos_charge_endpoint(self, mock_charge, auth_client):
        mock_charge.return_value = {'success': True, 'transaction_id': 'P1', 'amount': 25}
        resp = auth_client.post('/medication/pos/charge', data={'amount': '25'})
        assert resp.status_code == 200
        assert resp.get_json()['transaction_id'] == 'P1'


class TestPaymentMethodMacro:
    def test_macro_renders_arabic_options(self, app):
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                "{% from 'partials/_payment_method_select.html' import payment_method_select %}"
                "{{ payment_method_select(id='pm', include_force=true) }}"
            )
        assert 'نقداً' in html
        assert 'بطاقة' in html
        assert 'تأمين' in html
        assert 'دفع قوي' in html
        assert 'value="CASH"' in html


class TestProcessPaymentTemplate:
    def test_no_duplicate_insurance_provider_field(self, app):
        with app.app_context():
            from flask import render_template_string
            html = render_template_string(
                "{% from 'partials/_payment_method_select.html' import payment_method_select %}"
                "{{ payment_method_select(id='paymentMethodSelect') }}"
                '<div id="insuranceFieldsRow" class="d-none">'
                '<select name="insurance_company_id" id="insuranceCompanyId"></select>'
                '</div>'
            )
        assert 'insurance_provider' not in html
        assert 'insurance_company_id' in html


class TestPharmacyPosPage:
    def test_pos_page_uses_external_js_and_macro(self, auth_client):
        resp = auth_client.get('/medication/pos')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'js/pages/pharmacy/pos.js' in text
        assert 'payment_method_radios' not in text  # rendered, not raw macro name
        assert 'name="paymentMethod"' in text
        assert 'alert(' not in text

    def test_insufficient_stock_arabic_message(self, auth_client, test_medications):
        med = test_medications[2]  # low stock ibuprofen (5 units)
        resp = auth_client.post(
            '/medication/pos/sell',
            data=json.dumps({
                'items': [{'medication_id': med.id, 'quantity': 99}],
                'payment_method': 'cash',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        msg = resp.get_json().get('message', '')
        assert 'medication_id' not in msg.lower()
        assert 'المخزون' in msg or med.trade_name in msg
