"""HTTP route coverage for ``routes.lab.reagents``.

Real Flask test-client tests against the migrated test database. Every endpoint
and branch in ``routes/lab/reagents.py`` is exercised:

* GET    /lab/reagents        - list, search (name/supplier/lot), stock
                                (low/out/normal), expiry (expired/soon)
* GET/POST /lab/reagents/add
* GET/POST /lab/reagents/<id>/edit

Writes are rolled back per test through ``rollback_db`` and every seeded user or
reagent uses a unique name, so the suite stays robust no matter what rows
earlier runs (or the existing behavioural suite) left in the test database.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

import routes.lab.reagents as reagents_routes
from models.lab_reagent import LabReagent
from tests.tenant_context import ensure_test_user, login_test_client


def _suffix() -> str:
    return uuid4().hex[:8]


def _make_user(rollback_db, test_tenant, *, role: str = 'lab'):
    username = f'reagent_cov_{role}_{_suffix()}'
    return ensure_test_user(rollback_db, test_tenant, username=username, role=role)


def _login(client, rollback_db, test_tenant, *, role: str = 'lab'):
    user = _make_user(rollback_db, test_tenant, role=role)
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


def _seed_reagent(rollback_db, test_tenant, *, name, **kw):
    reagent = LabReagent(
        tenant_id=test_tenant.id,
        name=name,
        supplier=kw.get('supplier'),
        lot_number=kw.get('lot_number'),
        unit=kw.get('unit'),
        stock_quantity=kw.get('stock_quantity', 50),
        minimum_stock=kw.get('minimum_stock', 10),
        expiry_date=kw.get('expiry_date'),
        notes=kw.get('notes'),
        is_active=kw.get('is_active', True),
    )
    rollback_db.session.add(reagent)
    rollback_db.session.commit()
    return reagent


def _boom_commit(*_args, **_kwargs):
    raise RuntimeError('simulated commit failure')


def _row_by_name(rollback_db, name):
    return rollback_db.session.execute(select(LabReagent).filter_by(name=name)).scalars().first()


@pytest.fixture
def lab_client(app, client, rollback_db, test_tenant):
    _login(client, rollback_db, test_tenant, role='lab')
    return client


class TestReagentsList:
    def test_list_renders_seeded_reagent(self, lab_client, rollback_db, test_tenant):
        name = f'List Reagent {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name)
        resp = lab_client.get('/lab/reagents')
        assert resp.status_code == 200
        assert name in resp.get_data(as_text=True)

    def test_list_search_matches_name(self, lab_client, rollback_db, test_tenant):
        name = f'Search Target {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name)
        resp = lab_client.get(f'/lab/reagents?search={name}')
        assert resp.status_code == 200
        assert name in resp.get_data(as_text=True)

    def test_list_search_matches_supplier(self, lab_client, rollback_db, test_tenant):
        name = f'Supplier Reagent {_suffix()}'
        supplier = f'Acme Supplier {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name, supplier=supplier)
        resp = lab_client.get(f'/lab/reagents?search={supplier}')
        assert resp.status_code == 200
        assert name in resp.get_data(as_text=True)

    def test_list_search_matches_lot_number(self, lab_client, rollback_db, test_tenant):
        name = f'Lot Reagent {_suffix()}'
        lot_number = f'LOT-{_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name, lot_number=lot_number)
        resp = lab_client.get(f'/lab/reagents?search={lot_number}')
        assert resp.status_code == 200
        assert name in resp.get_data(as_text=True)

    def test_list_search_no_match(self, lab_client, rollback_db, test_tenant):
        name = f'Only Reagent {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name)
        resp = lab_client.get('/lab/reagents?search=zzz-no-match-qa')
        assert resp.status_code == 200
        assert name not in resp.get_data(as_text=True)

    def test_list_stock_low(self, lab_client, rollback_db, test_tenant):
        low_name = f'Low Stock {_suffix()}'
        normal_name = f'Normal Stock {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=low_name, stock_quantity=2, minimum_stock=10)
        _seed_reagent(
            rollback_db, test_tenant, name=normal_name, stock_quantity=100, minimum_stock=10
        )
        body = lab_client.get('/lab/reagents?stock=low').get_data(as_text=True)
        assert low_name in body
        assert normal_name not in body

    def test_list_stock_low_at_boundary(self, lab_client, rollback_db, test_tenant):
        # stock_quantity == minimum_stock (> 0) still counts as low.
        name = f'Boundary Low {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name, stock_quantity=10, minimum_stock=10)
        assert name in lab_client.get('/lab/reagents?stock=low').get_data(as_text=True)

    def test_list_stock_out(self, lab_client, rollback_db, test_tenant):
        name = f'Out Reagent {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name, stock_quantity=0, minimum_stock=10)
        assert name in lab_client.get('/lab/reagents?stock=out').get_data(as_text=True)

    def test_list_stock_normal(self, lab_client, rollback_db, test_tenant):
        normal_name = f'Normal Reagent {_suffix()}'
        low_name = f'Low Reagent {_suffix()}'
        _seed_reagent(
            rollback_db, test_tenant, name=normal_name, stock_quantity=100, minimum_stock=10
        )
        _seed_reagent(rollback_db, test_tenant, name=low_name, stock_quantity=2, minimum_stock=10)
        body = lab_client.get('/lab/reagents?stock=normal').get_data(as_text=True)
        assert normal_name in body
        assert low_name not in body

    def test_list_stock_unknown_value(self, lab_client, rollback_db, test_tenant):
        name = f'Any Stock {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name)
        resp = lab_client.get('/lab/reagents?stock=not-a-filter')
        assert resp.status_code == 200
        assert name in resp.get_data(as_text=True)

    def test_list_expiry_expired(self, lab_client, rollback_db, test_tenant):
        name = f'Expired Reagent {_suffix()}'
        _seed_reagent(
            rollback_db,
            test_tenant,
            name=name,
            expiry_date=date.today() - timedelta(days=1),
        )
        assert name in lab_client.get('/lab/reagents?expiry=expired').get_data(as_text=True)

    def test_list_expiry_soon(self, lab_client, rollback_db, test_tenant):
        name = f'Soon Reagent {_suffix()}'
        _seed_reagent(
            rollback_db,
            test_tenant,
            name=name,
            expiry_date=date.today() + timedelta(days=5),
        )
        assert name in lab_client.get('/lab/reagents?expiry=soon').get_data(as_text=True)

    def test_list_expiry_null_excluded(self, lab_client, rollback_db, test_tenant):
        name = f'No Expiry {_suffix()}'
        _seed_reagent(rollback_db, test_tenant, name=name, expiry_date=None)
        body_expired = lab_client.get('/lab/reagents?expiry=expired').get_data(as_text=True)
        body_soon = lab_client.get('/lab/reagents?expiry=soon').get_data(as_text=True)
        assert name not in body_expired
        assert name not in body_soon

    def test_list_requires_login(self, client):
        resp = client.get('/lab/reagents')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_list_blocks_reception_role(self, client, rollback_db, test_tenant):
        _login(client, rollback_db, test_tenant, role='reception')
        resp = client.get('/lab/reagents')
        assert resp.status_code == 403


class TestAddReagent:
    def test_add_get_form(self, lab_client):
        resp = lab_client.get('/lab/reagents/add')
        assert resp.status_code == 200

    def test_add_creates_row(self, lab_client, rollback_db, test_tenant):
        name = f'Brand New Reagent {_suffix()}'
        resp = lab_client.post(
            '/lab/reagents/add',
            data={
                'name': name,
                'supplier': 'Acme Labs',
                'lot_number': 'LOT-001',
                'unit': 'vial',
                'stock_quantity': '25',
                'minimum_stock': '5',
                'expiry_date': '2030-01-01',
                'notes': 'some notes',
                'is_active': 'on',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = _row_by_name(rollback_db, name)
        assert created is not None
        assert created.stock_quantity == 25
        assert created.minimum_stock == 5
        assert created.supplier == 'Acme Labs'
        assert created.lot_number == 'LOT-001'
        assert created.unit == 'vial'
        assert created.notes == 'some notes'
        assert created.is_active is True
        assert created.tenant_id == test_tenant.id

    def test_add_missing_name_redirects_without_row(self, lab_client, rollback_db):
        resp = lab_client.post('/lab/reagents/add', data={'supplier': 'Nobody'})
        assert resp.status_code == 302
        assert _row_by_name(rollback_db, 'Nobody') is None
        assert (
            rollback_db.session.execute(select(LabReagent).filter_by(supplier='Nobody'))
            .scalars()
            .first()
            is None
        )

    def test_add_invalid_numbers_default_zero(self, lab_client, rollback_db):
        name = f'Weird Numbers {_suffix()}'
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': name, 'stock_quantity': 'abc', 'minimum_stock': 'xyz'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = _row_by_name(rollback_db, name)
        assert created is not None
        assert created.stock_quantity == 0
        assert created.minimum_stock == 0

    def test_add_bad_expiry_becomes_none(self, lab_client, rollback_db):
        name = f'Bad Date Reagent {_suffix()}'
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': name, 'expiry_date': 'not-a-date'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = _row_by_name(rollback_db, name)
        assert created is not None
        assert created.expiry_date is None

    def test_add_is_active_off(self, lab_client, rollback_db):
        name = f'Inactive Reagent {_suffix()}'
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': name, 'is_active': 'off'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        created = _row_by_name(rollback_db, name)
        assert created is not None
        assert created.is_active is False

    def test_add_commit_failure_rolls_back(self, lab_client, rollback_db, monkeypatch):
        monkeypatch.setattr(reagents_routes, 'safe_commit', _boom_commit)
        name = f'No Commit Reagent {_suffix()}'
        resp = lab_client.post(
            '/lab/reagents/add',
            data={'name': name, 'stock_quantity': '10'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert _row_by_name(rollback_db, name) is None

    def test_add_requires_login(self, client):
        resp = client.post('/lab/reagents/add', data={'name': 'x'})
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']


class TestEditReagent:
    def test_edit_get_form(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(rollback_db, test_tenant, name=f'Edit Form {_suffix()}')
        resp = lab_client.get(f'/lab/reagents/{reagent.id}/edit')
        assert resp.status_code == 200

    def test_edit_updates_fields(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(
            rollback_db, test_tenant, name=f'Before Edit {_suffix()}', stock_quantity=5
        )
        new_name = f'After Edit {_suffix()}'
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={
                'name': new_name,
                'stock_quantity': '42',
                'minimum_stock': '7',
                'supplier': 'New Supplier',
                'lot_number': 'LOT-99',
                'unit': 'ampoule',
                'expiry_date': '2031-06-01',
                'notes': 'updated notes',
                'is_active': 'on',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.name == new_name
        assert row.stock_quantity == 42
        assert row.minimum_stock == 7
        assert row.supplier == 'New Supplier'
        assert row.lot_number == 'LOT-99'
        assert row.unit == 'ampoule'
        assert row.notes == 'updated notes'
        assert row.is_active is True

    def test_edit_unknown_id_redirects(self, lab_client):
        resp = lab_client.get('/lab/reagents/999999/edit')
        assert resp.status_code == 302

    def test_edit_missing_name_keeps_row(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(rollback_db, test_tenant, name=f'Keep Name {_suffix()}')
        original = reagent.name
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'supplier': 'Changed Supplier'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.name == original
        # Missing name returns early, so no field (including supplier) is updated.
        assert row.supplier is None

    def test_edit_bad_stock_defaults_zero(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(rollback_db, test_tenant, name=f'Bad Stock {_suffix()}')
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'name': reagent.name, 'stock_quantity': 'abc'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.stock_quantity == 0

    def test_edit_bad_minimum_defaults_zero(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(rollback_db, test_tenant, name=f'Bad Minimum {_suffix()}')
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'name': reagent.name, 'minimum_stock': 'xyz'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.minimum_stock == 0

    def test_edit_bad_expiry_becomes_none(self, lab_client, rollback_db, test_tenant):
        reagent = _seed_reagent(
            rollback_db, test_tenant, name=f'Bad Expiry {_suffix()}', expiry_date=date.today()
        )
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'name': reagent.name, 'expiry_date': 'not-a-date'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.expiry_date is None

    def test_edit_commit_failure_rolls_back(
        self, lab_client, rollback_db, test_tenant, monkeypatch
    ):
        original_name = f'Commit Edit {_suffix()}'
        reagent = _seed_reagent(rollback_db, test_tenant, name=original_name)
        monkeypatch.setattr(reagents_routes, 'safe_commit', _boom_commit)
        resp = lab_client.post(
            f'/lab/reagents/{reagent.id}/edit',
            data={'name': 'Attempted Rename', 'stock_quantity': '99'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        row = (
            rollback_db.session.execute(select(LabReagent).filter_by(id=reagent.id))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.name == original_name
        assert row.stock_quantity == 50

    def test_edit_requires_login(self, client):
        resp = client.post('/lab/reagents/1/edit', data={'name': 'x'})
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']
