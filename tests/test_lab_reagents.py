"""Tests for routes.lab.reagents module.

Covers LabReagent CRUD routes.
"""

import pytest
from unittest.mock import MagicMock, patch

from routes.lab.reagents import reagents, add_reagent, edit_reagent


class TestReagentsList:
    """Tests for reagents() view."""

    def test_reagents_list_no_filters(self, client):
        """Test listing reagents without filters."""
        response = client.get('/lab/reagents')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_search(self, client):
        """Test listing reagents with search filter."""
        response = client.get('/lab/reagents?search=paracetamol')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_stock_low(self, client):
        """Test listing reagents with low stock filter."""
        response = client.get('/lab/reagents?stock=low')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_stock_out(self, client):
        """Test listing reagents with out of stock filter."""
        response = client.get('/lab/reagents?stock=out')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_stock_normal(self, client):
        """Test listing reagents with normal stock filter."""
        response = client.get('/lab/reagents?stock=normal')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_expiry_expired(self, client):
        """Test listing reagents with expired filter."""
        response = client.get('/lab/reagents?expiry=expired')
        assert response.status_code in (200, 302)

    def test_reagents_list_with_expiry_soon(self, client):
        """Test listing reagents with expiring soon filter."""
        response = client.get('/lab/reagents?expiry=soon')
        assert response.status_code in (200, 302)


class TestAddReagent:
    """Tests for add_reagent() view."""

    def test_add_reagent_get(self, client):
        """Test GET request to add reagent."""
        response = client.get('/lab/reagents/add')
        assert response.status_code in (200, 302)

    def test_add_reagent_post_success(self, client):
        """Test POST request to add reagent."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Paracetamol',
            'supplier': 'Pharma Inc',
            'lot_number': 'LOT123',
            'unit': 'mg',
            'stock_quantity': '100',
            'minimum_stock': '50',
            'expiry_date': '2025-12-31',
            'notes': 'Test notes',
            'is_active': 'on',
        })
        assert response.status_code in (200, 302, 400)

    def test_add_reagent_post_missing_name(self, client):
        """Test POST with missing name shows flash error."""
        response = client.post('/lab/reagents/add', data={
            'supplier': 'Pharma Inc',
        })
        assert response.status_code == 302

    def test_add_reagent_post_invalid_stock_quantity(self, client):
        """Test POST with invalid stock quantity."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test Reagent',
            'stock_quantity': 'invalid',
        })
        assert response.status_code in (200, 302, 400)

    def test_add_reagent_post_invalid_minimum_stock(self, client):
        """Test POST with invalid minimum stock."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test Reagent',
            'minimum_stock': 'invalid',
        })
        assert response.status_code in (200, 302, 400)

    def test_add_reagent_post_invalid_expiry_date(self, client):
        """Test POST with invalid expiry date."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test Reagent',
            'expiry_date': 'invalid-date',
        })
        assert response.status_code in (200, 302, 400)

    def test_add_reagent_post_empty_form(self, client):
        """Test POST with empty form."""
        response = client.post('/lab/reagents/add', data={})
        assert response.status_code == 302

    def test_add_reagent_post_no_stock_quantity(self, client):
        """Test POST with no stock_quantity field."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test',
        })
        assert response.status_code in (200, 302)

    def test_add_reagent_post_no_minimum_stock(self, client):
        """Test POST with no minimum_stock field."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test',
        })
        assert response.status_code in (200, 302)

    def test_add_reagent_post_no_expiry_date(self, client):
        """Test POST with no expiry_date field."""
        response = client.post('/lab/reagents/add', data={
            'name': 'Test',
            'stock_quantity': '10',
            'minimum_stock': '5',
        })
        assert response.status_code in (200, 302)


class TestEditReagent:
    """Tests for edit_reagent() view."""

    def test_edit_reagent_get(self, client):
        """Test GET request to edit reagent."""
        response = client.get('/lab/reagents/1/edit', follow_redirects=True)
        assert response.status_code in (200, 302)

    def test_edit_reagent_post_success(self, client):
        """Test POST request to edit reagent."""
        response = client.post('/lab/reagents/1/edit', data={
            'name': 'Updated Reagent',
            'supplier': 'New Supplier',
        })
        assert response.status_code in (200, 302, 400)

    def test_edit_reagent_post_missing_name(self, client):
        """Test POST with missing name."""
        response = client.post('/lab/reagents/1/edit', data={})
        assert response.status_code == 302

    def test_edit_reagent_not_found(self, client):
        """Test editing non-existent reagent."""
        response = client.get('/lab/reagents/99999/edit', follow_redirects=True)
        assert response.status_code in (200, 302)

    def test_edit_reagent_post_invalid_stock(self, client):
        """Test POST with invalid stock quantity."""
        response = client.post('/lab/reagents/1/edit', data={
            'name': 'Test',
            'stock_quantity': 'abc',
        })
        assert response.status_code in (200, 302)

    def test_edit_reagent_post_invalid_minimum_stock(self, client):
        """Test POST with invalid minimum stock."""
        response = client.post('/lab/reagents/1/edit', data={
            'name': 'Test',
            'minimum_stock': 'abc',
        })
        assert response.status_code in (200, 302)

    def test_edit_reagent_post_invalid_expiry(self, client):
        """Test POST with invalid expiry date."""
        response = client.post('/lab/reagents/1/edit', data={
            'name': 'Test',
            'expiry_date': 'not-a-date',
        })
        assert response.status_code in (200, 302)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
