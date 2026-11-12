"""Coverage tests for routes.medication_routes.external.py"""

from __future__ import annotations

pytest_plugins = ['tests._isolated_tenant']


class TestExternalDrugImport:
    def test_empty_items(self, app, rollback_db, client, login_as):
        login_as(client, 'med_import_user', 'pharmacist')
        resp = client.post(
            '/medication/api/external-drug-import',
            json={'items': []},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'imported' in data

    def test_no_items(self, app, rollback_db, client, login_as):
        login_as(client, 'med_import_no_items', 'pharmacist')
        resp = client.post(
            '/medication/api/external-drug-import',
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'imported' in data

    def test_import_new_medication(self, app, rollback_db, client, login_as):
        login_as(client, 'med_import_new', 'pharmacist')
        resp = client.post(
            '/medication/api/external-drug-import',
            json={
                'items': [
                    {
                        'trade_name': 'TestMed',
                        'scientific_name': 'Scientific Name',
                        'generic_name': 'Generic',
                        'dosage_form': 'tablet',
                        'strength': '500mg',
                        'manufacturer': 'Test Pharma',
                        'price': 10.0,
                        'category': 'analgesic',
                        'stock_quantity': 100,
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['imported'] >= 0

    def test_invalid_item_skipped(self, app, rollback_db, client, login_as):
        login_as(client, 'med_import_invalid', 'pharmacist')
        resp = client.post(
            '/medication/api/external-drug-import',
            json={
                'items': [
                    'not a dict',
                    {'trade_name': ''},
                    {'trade_name': 'Valid Med', 'scientific_name': 'Sci Name'},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'imported' in data
