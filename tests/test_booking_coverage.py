"""Booking routes (was 24%)."""

import pytest


@pytest.fixture()
def _booking_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='book_test', role='reception')
    login_test_client(client, u, test_tenant)
    return client


class TestBookingRoutes:
    def test_booking_index(self, _booking_client):
        resp = _booking_client.get('/booking/')
        assert resp.status_code in (200, 302)

    def test_booking_dashboard(self, _booking_client):
        resp = _booking_client.get('/booking/dashboard')
        assert resp.status_code in (200, 302)

    def test_blueprint_registered(self, app):
        assert 'booking' in app.blueprints
