"""Behavioural tests for routes.lab.reagents with an authenticated lab user."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.extensions import db
from models.lab_reagent import LabReagent
from tests.tenant_context import ensure_test_user, login_test_client


@pytest.fixture
def lab_client(app, client, db, test_tenant):
    user = ensure_test_user(db, test_tenant, username='reagents_lab', role='lab')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def reagent(app, db, test_tenant, lab_client):
    r = LabReagent(
        tenant_id=test_tenant.id,
        name='Reagent Test A',
        supplier='PharmaCo',
        lot_number='LOT-001',
        stock_quantity=100,
        minimum_stock=10,
        expiry_date=date.today() + timedelta(days=60),
        is_active=True,
    )
    db.session.add(r)
    db.session.commit()
    return r


class TestReagentsList:
    def test_list_renders(self, lab_client, reagent):
        resp = lab_client.get('/lab/reagents')
        assert resp.status_code == 200
        assert 'Reagent Test A' in resp.get_data(as_text=True)

    def test_list_search_matches_and_misses(self, lab_client, reagent):
        resp = lab_client.get('/lab/reagents?search=Reagent Test A')
        assert resp.status_code == 200
        assert 'Reagent Test A' in resp.get_data(as_text=True)
        resp = lab_client.get('/lab/reagents?search=no-such-reagent-xyz')
        assert resp.status_code == 200
        assert 'Reagent Test A' not in resp.get_data(as_text=True)

    def test_stock_filters(self, lab_client, reagent, db, test_tenant):
        low = LabReagent(
            tenant_id=test_tenant.id, name='LowStock Reagent', stock_quantity=2,
            minimum_stock=10, is_active=True,
        )
        db.session.add(low)
        db.session.commit()
        assert 'LowStock' in lab_client.get('/lab/reagents?stock=low').get_data(as_text=True)
        assert 'Reagent Test A' in lab_client.get('/lab/reagents?stock=normal').get_data(as_text=True)
        assert lab_client.get('/lab/reagents?stock=out').status_code == 200

    def test_expiry_filters(self, lab_client, reagent):
        assert lab_client.get('/lab/reagents?expiry=expired').status_code == 200
        assert lab_client.get('/lab/reagents?expiry=soon').status_code == 200


class TestAddReagent:
    def test_add_get_form(self, lab_client):
        resp = lab_client.get('/lab/reagents/add')
        assert resp.status_code == 200

    def test_add_creates_row(self, lab_client, test_tenant):
        resp = lab_client.post(
            '/lab/reagents/add',
            data={
                'name': 'Brand New Reagent',
                'supplier': 'Acme Labs',
                'stock_quantity': '25',
                'minimum_stock': '5',
                'expiry_date': '2030-01-01',
                'is_active': 'on',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = db.session.execute(
            select(LabReagent).filter_by(name='Brand New Reagent')
        ).scalars().first()
        assert created is not None
        assert created.stock_quantity == 25
        assert created.tenant_id == test_tenant.id

    def test_add_missing_name_redirects_without_row(self, lab_client):
        resp = lab_client.post('/lab/reagents/add', data={'supplier': 'Nobody'})
        assert resp.status_code == 302
        assert db.session.execute(
            select(LabReagent).filter_by(supplier='Nobody')
        ).scalars().first() is None

    def test_add_invalid_numbers_defaults_zero(self, lab_client):
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': 'Weird Numbers', 'stock_quantity': 'abc', 'minimum_stock': 'xyz'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = db.session.execute(
            select(LabReagent).filter_by(name='Weird Numbers')
        ).scalars().first()
        assert created.stock_quantity == 0
        assert created.minimum_stock == 0

    def test_add_bad_expiry_becomes_none(self, lab_client):
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': 'Bad Date Reagent', 'expiry_date': 'not-a-date'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = db.session.execute(
            select(LabReagent).filter_by(name='Bad Date Reagent')
        ).scalars().first()
        assert created.expiry_date is None


class TestEditReagent:
    def test_edit_get_form(self, lab_client, reagent):
        resp = lab_client.get(f'/lab/reagents/{reagent.id}/edit')
        assert resp.status_code == 200

    def test_edit_updates_fields(self, lab_client, reagent):
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={
                'name': 'Renamed Reagent',
                'stock_quantity': '42',
                'minimum_stock': '7',
                'supplier': 'New Supplier',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(reagent)
        assert reagent.name == 'Renamed Reagent'
        assert reagent.stock_quantity == 42
        assert reagent.minimum_stock == 7
        assert reagent.supplier == 'New Supplier'

    def test_edit_unknown_id_redirects(self, lab_client):
        resp = lab_client.get('/lab/reagents/999999/edit')
        assert resp.status_code == 302

    def test_edit_missing_name_keeps_row(self, lab_client, reagent):
        original = reagent.name
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'supplier': 'Changed Supplier'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.refresh(reagent)
        assert reagent.name == original
