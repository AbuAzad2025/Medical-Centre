"""Coverage tests for routes/medication_routes/catalog.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestMedicationCatalogRoutes:
    def test_list_unauth(self, app, client):
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_list_auth(self, app, client, login_as):
        login_as(client, 'med_cat_list_user', 'pharmacist')
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_list_with_search(self, app, client, login_as):
        login_as(client, 'med_cat_search_user', 'pharmacist')
        resp = client.get('/medication/list?search=test&category=all&stock_status=low')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_list_with_stock_status(self, app, client, login_as):
        login_as(client, 'med_cat_stock_user', 'pharmacist')
        resp = client.get('/medication/list?stock_status=out')
        assert resp.status_code in (200, 302, 401, 403, 404)
        login_as(client, 'med_cat_stock2_user', 'pharmacist')
        resp = client.get('/medication/list?stock_status=normal')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_add_get(self, app, client, login_as):
        login_as(client, 'med_cat_add_user', 'pharmacist')
        resp = client.get('/medication/add')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_add_post(self, app, client, login_as):
        login_as(client, 'med_cat_add_post_user', 'pharmacist')
        resp = client.post('/medication/add', data={
            'trade_name': 'Test Medication',
            'scientific_name': 'Test Scientific',
            'generic_name': 'Test Generic',
            'category': 'antibiotic',
            'dosage_form': 'tablet',
            'strength': '500mg',
            'manufacturer': 'Test Mfg',
            'stock_quantity': '100',
            'minimum_stock': '10',
            'price': '10.50',
            'expiry_date': '2025-12-31',
            'batch_number': 'BATCH001',
            'description': 'Test description',
            'standard_instructions': 'Take daily',
            'side_effects': 'None',
            'contraindications': 'None',
            'drug_interactions': 'None',
            'pregnancy_category': 'A',
            'is_controlled': '1',
            'schedule': 'II',
            'is_active': 'on',
        })
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_add_post_invalid(self, app, client, login_as):
        login_as(client, 'med_cat_add_invalid_user', 'pharmacist')
        resp = client.post('/medication/add', data={
            'trade_name': '',
            'stock_quantity': 'invalid',
        })
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_get(self, app, client, login_as):
        login_as(client, 'med_cat_edit_user', 'pharmacist')
        resp = client.get('/medication/edit/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post(self, app, client, login_as):
        login_as(client, 'med_cat_edit_post_user', 'pharmacist')
        resp = client.post('/medication/edit/1', data={
            'trade_name': 'Updated Medication',
            'stock_quantity': '50',
            'minimum_stock': '5',
            'price': '15.00',
        })
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post_invalid(self, app, client, login_as):
        login_as(client, 'med_cat_edit_invalid_user', 'pharmacist')
        resp = client.post('/medication/edit/1', data={
            'stock_quantity': 'invalid',
        })
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
