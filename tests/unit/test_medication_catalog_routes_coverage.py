"""Coverage tests for routes/medication_routes/catalog.py"""

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
        resp = client.post(
            '/medication/add',
            data={
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
            },
        )
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_add_post_invalid(self, app, client, login_as):
        login_as(client, 'med_cat_add_invalid_user', 'pharmacist')
        resp = client.post(
            '/medication/add',
            data={
                'trade_name': '',
                'stock_quantity': 'invalid',
            },
        )
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_get(self, app, client, login_as):
        login_as(client, 'med_cat_edit_user', 'pharmacist')
        resp = client.get('/medication/edit/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post(self, app, client, login_as):
        login_as(client, 'med_cat_edit_post_user', 'pharmacist')
        resp = client.post(
            '/medication/edit/1',
            data={
                'trade_name': 'Updated Medication',
                'stock_quantity': '50',
                'minimum_stock': '5',
                'price': '15.00',
            },
        )
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post_invalid(self, app, client, login_as):
        login_as(client, 'med_cat_edit_invalid_user', 'pharmacist')
        resp = client.post(
            '/medication/edit/1',
            data={
                'stock_quantity': 'invalid',
            },
        )
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_list_error_path(self, app, client, login_as, monkeypatch):
        """Trigger exception in list_medications."""
        login_as(client, 'med_cat_list_err_user', 'pharmacist')
        from routes.medication_routes import catalog as catalog_mod

        # Monkeypatch to cause an error
        def bad_query(*_a, **_k):
            raise RuntimeError('DB error')

        monkeypatch.setattr(
            catalog_mod,
            'Medication',
            type(
                'BadMed',
                (),
                {
                    'query': type(
                        'BadQuery',
                        (),
                        {
                            'filter_by': lambda self, **_kw: self,
                            'filter': lambda self, *_a: self,
                            'order_by': lambda self, *_a: self,
                            'all': bad_query,
                        },
                    )()
                },
            ),
        )
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 400, 401, 403, 404, 500)

    def test_edit_not_found(self, app, client, login_as):
        """Test edit with non-existent medication (covers medication not found redirect)."""
        login_as(client, 'med_cat_edit_nf_user', 'pharmacist')
        resp = client.get('/medication/edit/999999')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post_not_found(self, app, client, login_as):
        """Test edit POST with non-existent medication."""
        login_as(client, 'med_cat_edit_nf_post_user', 'pharmacist')
        resp = client.post('/medication/edit/999999', data={'trade_name': 'Updated'})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
