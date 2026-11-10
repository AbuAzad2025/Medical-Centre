"""
Coverage for routes/lab/test_catalog.py.

Exercises the real HTTP surface of the lab test catalog and panel CRUD
endpoints plus the JSON auto-fill API, against the migrated test schema.
Writes go through ``rollback_db`` so the shared test database stays pristine.
Failure branches (commit errors) are triggered either naturally (duplicate
tenant-scoped code violates the unique index) or by monkeypatching
``routes.lab.test_catalog.safe_commit`` to raise, which is the same contract
the production code path sees when the database rejects a write.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


def _login(client, db_handle, tenant, username, role, password='ValidPass123!'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db_handle, tenant, username=username, role=role, password=password)
    login_test_client(client, user, tenant, password)
    return user


def _add_catalog(db_handle, tenant, code, **kw):
    from models.lab_test_catalog import LabTestCatalog

    row = LabTestCatalog(
        tenant_id=tenant.id,
        code=code,
        name_ar=kw.get('name_ar', f'فحص {code}'),
        name_en=kw.get('name_en', code),
        category=kw.get('category', 'chemistry'),
        unit=kw.get('unit', 'mg/dL'),
        default_reference_range=kw.get('default_reference_range', '1-10'),
        critical_low=kw.get('critical_low', '2'),
        critical_high=kw.get('critical_high', '20'),
        price=kw.get('price', 100),
        preparation_instructions=kw.get('preparation_instructions', ''),
        is_active=kw.get('is_active', True),
        sort_order=kw.get('sort_order', 10),
    )
    db_handle.session.add(row)
    db_handle.session.commit()
    return row


def _add_panel(db_handle, tenant, name_en='Coverage Panel', **kw):
    from models.lab_test_catalog import LabTestPanel

    panel = LabTestPanel(
        tenant_id=tenant.id,
        name_ar=kw.get('name_ar', f'لوحة {name_en}'),
        name_en=name_en,
        description=kw.get('description', ''),
        is_active=kw.get('is_active', True),
    )
    db_handle.session.add(panel)
    db_handle.session.commit()
    return panel


# ---------------------------------------------------------------------------
# Test catalog pages
# ---------------------------------------------------------------------------


class TestCatalogPage:
    def test_catalog_page_lists_and_filters(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covcatlist'), 'lab')
        code = _uniq('COV-CAT')
        _add_catalog(db, test_tenant, code, category='chemistry')

        resp = client.get('/lab/test-catalog/')
        assert resp.status_code == 200
        assert code.encode() in resp.data

        resp = client.get('/lab/test-catalog/?category=chemistry')
        assert resp.status_code == 200
        assert code.encode() in resp.data

        resp = client.get('/lab/test-catalog/?category=microbiology')
        assert resp.status_code == 200
        assert code.encode() not in resp.data

    def test_catalog_page_blocks_reception_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covcat403'), 'reception')
        resp = client.get('/lab/test-catalog/')
        assert resp.status_code == 403

    def test_catalog_page_requires_authentication(self, app, client, db, test_tenant, rollback_db):
        resp = client.get('/lab/test-catalog/')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']


class TestCatalogAdd:
    def test_add_persists_row_with_defaults(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcatadd'), 'lab')
        code = _uniq('COV-ADD')
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': f'  {code}  ',
                'name_ar': 'اختبار التغطية',
                'name_en': 'Coverage Test',
                'category': 'hematology',
                'unit': 'g/dL',
                'default_reference_range': '12-16',
                'critical_low': '8',
                'critical_high': '18',
                'price': '',
                'sort_order': '',
                'is_active': '0',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(select(LabTestCatalog).filter(LabTestCatalog.code == code))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.category == 'hematology'
        assert float(row.price) == 0.0
        assert row.sort_order == 0
        assert row.is_active is False
        assert row.tenant_id == test_tenant.id
        assert 'category=hematology' in resp.headers['Location']

    def test_add_defaults_is_active_when_checkbox_absent(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcatadddef'), 'manager')
        code = _uniq('COV-ADDEF')
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': code,
                'name_ar': 'بدون حالة',
                'name_en': 'No Flag',
                'category': 'serology',
                'price': '42.5',
                'sort_order': '3',
            },
        )
        assert resp.status_code == 302
        row = (
            db.session.execute(select(LabTestCatalog).filter(LabTestCatalog.code == code))
            .scalars()
            .first()
        )
        assert row is not None
        assert row.is_active is True
        assert float(row.price) == 42.5
        assert row.sort_order == 3

    def test_add_duplicate_code_rolls_back(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcatdup'), 'lab')
        code = _uniq('COV-DUP')
        _add_catalog(db, test_tenant, code)
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': code,
                'name_ar': 'مكرر',
                'name_en': 'Duplicate',
                'category': 'chemistry',
            },
        )
        assert resp.status_code == 302
        rows = (
            db.session.execute(select(LabTestCatalog).filter(LabTestCatalog.code == code))
            .scalars()
            .all()
        )
        assert len(rows) == 1

    def test_add_commit_failure_flashes_danger(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.lab.test_catalog as catalog_module

        def _boom(*_args, **_kwargs):
            raise RuntimeError('forced commit failure')

        monkeypatch.setattr(catalog_module, 'safe_commit', _boom)
        _login(client, db, test_tenant, _uniq('covcatboom'), 'admin')
        resp = client.post(
            '/lab/test-catalog/add',
            data={
                'code': _uniq('COV-BOOM'),
                'name_ar': 'فشل',
                'name_en': 'Boom',
                'category': 'other',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200


class TestCatalogEdit:
    def test_edit_updates_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcatedit'), 'lab')
        row = _add_catalog(db, test_tenant, _uniq('COV-EDIT'), name_en='Before', price=10)
        resp = client.post(
            f'/lab/test-catalog/{row.id}/edit',
            data={
                'code': row.code,
                'name_ar': 'بعد التعديل',
                'name_en': 'After',
                'category': 'coagulation',
                'unit': 'sec',
                'default_reference_range': '11-13',
                'critical_low': '',
                'critical_high': '',
                'price': '',
                'preparation_instructions': 'صائم',
                'is_active': '0',
                'sort_order': '',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestCatalog, row.id)
        assert refreshed.name_en == 'After'
        assert refreshed.category == 'coagulation'
        assert float(refreshed.price) == 0.0
        assert refreshed.sort_order == 0
        assert refreshed.is_active is False
        assert refreshed.updated_at is not None

    def test_edit_unknown_id_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covcatedit404'), 'lab')
        resp = client.post(
            '/lab/test-catalog/999999999/edit',
            data={'code': 'X', 'name_ar': 'X', 'name_en': 'X', 'category': 'other'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'].rstrip('/').endswith('/lab/test-catalog')

    def test_edit_duplicate_code_rolls_back(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcateditdup'), 'lab')
        keep = _add_catalog(db, test_tenant, _uniq('COV-KEEP'))
        row = _add_catalog(db, test_tenant, _uniq('COV-EDITDUP'), name_en='Original')
        resp = client.post(
            f'/lab/test-catalog/{row.id}/edit',
            data={
                'code': keep.code,
                'name_ar': row.name_ar,
                'name_en': 'Should Not Persist',
                'category': 'chemistry',
                'price': '10',
                'sort_order': '1',
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestCatalog, row.id)
        assert refreshed.code != keep.code
        assert refreshed.name_en == 'Original'


class TestCatalogDelete:
    def test_delete_removes_row(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestCatalog

        _login(client, db, test_tenant, _uniq('covcatdel'), 'admin')
        row = _add_catalog(db, test_tenant, _uniq('COV-DEL'))
        resp = client.post(f'/lab/test-catalog/{row.id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestCatalog, row.id) is None

    def test_delete_unknown_id_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covcatdel404'), 'lab')
        resp = client.post('/lab/test-catalog/999999999/delete')
        assert resp.status_code == 302
        assert resp.headers['Location'].rstrip('/').endswith('/lab/test-catalog')

    def test_delete_commit_failure_keeps_row(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.lab.test_catalog as catalog_module
        from models.lab_test_catalog import LabTestCatalog

        def _boom(*_args, **_kwargs):
            raise RuntimeError('forced commit failure')

        _login(client, db, test_tenant, _uniq('covcatdelboom'), 'lab')
        row = _add_catalog(db, test_tenant, _uniq('COV-DELBOOM'))
        monkeypatch.setattr(catalog_module, 'safe_commit', _boom)
        resp = client.post(f'/lab/test-catalog/{row.id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestCatalog, row.id) is not None


# ---------------------------------------------------------------------------
# Test panels pages
# ---------------------------------------------------------------------------


class TestPanelsPage:
    def test_panels_page_renders_with_panel(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covpanpage'), 'lab')
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV PANEL'))
        resp = client.get('/lab/test-panels/')
        assert resp.status_code == 200
        assert panel.name_en.encode() in resp.data

    def test_panels_page_blocks_reception_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covpan403'), 'reception')
        resp = client.get('/lab/test-panels/')
        assert resp.status_code == 403

    def test_panels_page_requires_authentication(self, app, client, db, test_tenant, rollback_db):
        resp = client.get('/lab/test-panels/')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']


class TestPanelsAdd:
    def test_add_panel_with_mixed_test_ids(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel

        _login(client, db, test_tenant, _uniq('covpanadd'), 'lab')
        t1 = _add_catalog(db, test_tenant, _uniq('COV-P-ADD1'))
        t2 = _add_catalog(db, test_tenant, _uniq('COV-P-ADD2'))
        panel_name = _uniq('COV Panel Add')
        resp = client.post(
            '/lab/test-panels/add',
            data={
                'name_ar': 'لوحة التغطية',
                'name_en': panel_name,
                'description': 'coverage panel',
                'is_active': '1',
                'test_ids': [str(t1.id), 'not-a-number', '', f' {t2.id} ', '999999999'],
            },
        )
        assert resp.status_code == 302
        panel = (
            db.session.execute(select(LabTestPanel).filter(LabTestPanel.name_en == panel_name))
            .scalars()
            .first()
        )
        assert panel is not None
        assert {item.test_id for item in panel.items} == {t1.id, t2.id}
        sort_orders = {item.test_id: item.sort_order for item in panel.items}
        assert sort_orders[t1.id] == 0

    def test_add_panel_without_test_ids(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel

        _login(client, db, test_tenant, _uniq('covpanaddempty'), 'manager')
        panel_name = _uniq('COV Panel Empty')
        resp = client.post(
            '/lab/test-panels/add',
            data={
                'name_ar': 'لوحة فارغة',
                'name_en': panel_name,
                'is_active': '0',
            },
        )
        assert resp.status_code == 302
        panel = (
            db.session.execute(select(LabTestPanel).filter(LabTestPanel.name_en == panel_name))
            .scalars()
            .first()
        )
        assert panel is not None
        assert panel.is_active is False
        assert list(panel.items) == []

    def test_add_panel_commit_failure_rolls_back(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.lab.test_catalog as catalog_module
        from models.lab_test_catalog import LabTestPanel

        def _boom(*_args, **_kwargs):
            raise RuntimeError('forced commit failure')

        monkeypatch.setattr(catalog_module, 'safe_commit', _boom)
        _login(client, db, test_tenant, _uniq('covpanaddboom'), 'lab')
        panel_name = _uniq('COV Panel Boom')
        resp = client.post(
            '/lab/test-panels/add',
            data={'name_ar': 'فشل', 'name_en': panel_name},
        )
        assert resp.status_code == 302
        panel = (
            db.session.execute(select(LabTestPanel).filter(LabTestPanel.name_en == panel_name))
            .scalars()
            .first()
        )
        assert panel is None


class TestPanelsEdit:
    def test_edit_replaces_items(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel, LabTestPanelItem

        _login(client, db, test_tenant, _uniq('covpanedit'), 'manager')
        t1 = _add_catalog(db, test_tenant, _uniq('COV-P-EDIT1'))
        t2 = _add_catalog(db, test_tenant, _uniq('COV-P-EDIT2'))
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV Panel Edit'))
        panel.items.append(LabTestPanelItem(test_id=t1.id, sort_order=0))
        db.session.commit()

        resp = client.post(
            f'/lab/test-panels/{panel.id}/edit',
            data={
                'name_ar': 'لوحة معدلة',
                'name_en': 'Edited Panel',
                'description': 'updated',
                'is_active': '1',
                'test_ids': ['junk-id', str(t2.id), '999999999'],
            },
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestPanel, panel.id)
        assert refreshed.name_en == 'Edited Panel'
        assert [item.test_id for item in refreshed.items] == [t2.id]

    def test_edit_clears_items_when_none_selected(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel, LabTestPanelItem

        _login(client, db, test_tenant, _uniq('covpaneditclr'), 'lab')
        t1 = _add_catalog(db, test_tenant, _uniq('COV-P-EDITC'))
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV Panel Clear'))
        panel.items.append(LabTestPanelItem(test_id=t1.id, sort_order=0))
        db.session.commit()

        resp = client.post(
            f'/lab/test-panels/{panel.id}/edit',
            data={'name_ar': 'فارغة', 'name_en': 'Cleared', 'is_active': '0'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestPanel, panel.id)
        assert refreshed.name_en == 'Cleared'
        assert refreshed.is_active is False
        assert list(refreshed.items) == []

    def test_edit_unknown_panel_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covpanedit404'), 'lab')
        resp = client.post(
            '/lab/test-panels/999999999/edit',
            data={'name_ar': 'x', 'is_active': '1'},
        )
        assert resp.status_code == 302
        assert resp.headers['Location'].rstrip('/').endswith('/lab/test-panels')

    def test_edit_commit_failure_keeps_panel(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.lab.test_catalog as catalog_module
        from models.lab_test_catalog import LabTestPanel

        def _boom(*_args, **_kwargs):
            raise RuntimeError('forced commit failure')

        _login(client, db, test_tenant, _uniq('covpaneditboom'), 'lab')
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV Panel EditBoom'))
        monkeypatch.setattr(catalog_module, 'safe_commit', _boom)
        resp = client.post(
            f'/lab/test-panels/{panel.id}/edit',
            data={'name_ar': 'فشل', 'name_en': 'Should Roll Back', 'is_active': '1'},
        )
        assert resp.status_code == 302
        db.session.expire_all()
        refreshed = db.session.get(LabTestPanel, panel.id)
        assert refreshed is not None
        assert refreshed.name_en != 'Should Roll Back'


class TestPanelsDelete:
    def test_delete_removes_panel_and_items(self, app, client, db, test_tenant, rollback_db):
        from models.lab_test_catalog import LabTestPanel, LabTestPanelItem

        _login(client, db, test_tenant, _uniq('covpandel'), 'admin')
        t1 = _add_catalog(db, test_tenant, _uniq('COV-P-DEL'))
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV Panel Del'))
        panel.items.append(LabTestPanelItem(test_id=t1.id, sort_order=0))
        db.session.commit()
        panel_id = panel.id

        resp = client.post(f'/lab/test-panels/{panel_id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestPanel, panel_id) is None
        remaining = (
            db.session.execute(
                select(LabTestPanelItem).filter(LabTestPanelItem.panel_id == panel_id)
            )
            .scalars()
            .all()
        )
        assert remaining == []

    def test_delete_unknown_panel_redirects(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covpandel404'), 'lab')
        resp = client.post('/lab/test-panels/999999999/delete')
        assert resp.status_code == 302
        assert resp.headers['Location'].rstrip('/').endswith('/lab/test-panels')

    def test_delete_commit_failure_keeps_panel(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import routes.lab.test_catalog as catalog_module
        from models.lab_test_catalog import LabTestPanel

        def _boom(*_args, **_kwargs):
            raise RuntimeError('forced commit failure')

        _login(client, db, test_tenant, _uniq('covpandelboom'), 'lab')
        panel = _add_panel(db, test_tenant, name_en=_uniq('COV Panel DelBoom'))
        monkeypatch.setattr(catalog_module, 'safe_commit', _boom)
        resp = client.post(f'/lab/test-panels/{panel.id}/delete')
        assert resp.status_code == 302
        assert db.session.get(LabTestPanel, panel.id) is not None


# ---------------------------------------------------------------------------
# JSON auto-fill API
# ---------------------------------------------------------------------------


class TestApiTestCatalog:
    def test_api_list_returns_active_tests_only(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covapi'), 'doctor')
        active_code = _uniq('COV-API-ACT')
        inactive_code = _uniq('COV-API-INACT')
        _add_catalog(db, test_tenant, active_code, sort_order=1)
        _add_catalog(db, test_tenant, inactive_code, is_active=False)

        resp = client.get('/lab/api/test-catalog')
        assert resp.status_code == 200
        payload = resp.get_json()
        codes = [t['code'] for t in payload]
        assert active_code in codes
        assert inactive_code not in codes

        entry = next(t for t in payload if t['code'] == active_code)
        assert entry['unit'] == 'mg/dL'
        assert entry['default_reference_range'] == '1-10'
        assert entry['critical_low'] == '2'
        assert entry['critical_high'] == '20'
        assert set(entry) == {
            'id',
            'code',
            'name_ar',
            'name_en',
            'category',
            'unit',
            'default_reference_range',
            'critical_low',
            'critical_high',
        }

    def test_api_list_null_fields_become_empty_strings(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('covapinull'), 'nurse')
        code = _uniq('COV-API-NULL')
        _add_catalog(
            db,
            test_tenant,
            code,
            unit=None,
            default_reference_range=None,
            critical_low=None,
            critical_high=None,
        )
        resp = client.get('/lab/api/test-catalog')
        assert resp.status_code == 200
        entry = next(t for t in resp.get_json() if t['code'] == code)
        assert entry['unit'] == ''
        assert entry['default_reference_range'] == ''
        assert entry['critical_low'] == ''
        assert entry['critical_high'] == ''

    def test_api_item_returns_full_payload(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covapiitem'), 'lab')
        row = _add_catalog(
            db,
            test_tenant,
            _uniq('COV-API-ITEM'),
            price=Decimal('55.25'),
            preparation_instructions='صائم 12 ساعة',
        )
        resp = client.get(f'/lab/api/test-catalog/{row.id}')
        assert resp.status_code == 200
        item = resp.get_json()
        assert item['id'] == row.id
        assert item['price'] == 55.25
        assert item['preparation_instructions'] == 'صائم 12 ساعة'
        assert item['unit'] == 'mg/dL'

    def test_api_item_with_null_price_and_fields_returns_zeros(
        self, app, client, db, test_tenant, rollback_db
    ):
        _login(client, db, test_tenant, _uniq('covapiitem0'), 'lab')
        row = _add_catalog(
            db,
            test_tenant,
            _uniq('COV-API-ZERO'),
            unit=None,
            default_reference_range=None,
            critical_low=None,
            critical_high=None,
            price=None,
            preparation_instructions=None,
        )
        resp = client.get(f'/lab/api/test-catalog/{row.id}')
        assert resp.status_code == 200
        item = resp.get_json()
        assert item['price'] == 0
        assert item['unit'] == ''
        assert item['default_reference_range'] == ''
        assert item['critical_low'] == ''
        assert item['critical_high'] == ''
        assert item['preparation_instructions'] == ''

    def test_api_item_404_for_unknown_id(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covapi404'), 'lab')
        resp = client.get('/lab/api/test-catalog/999999999')
        assert resp.status_code == 404
        assert resp.get_json() == {'error': 'not found'}

    def test_api_list_rejects_non_staff_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covapi403'), 'patient')
        resp = client.get('/lab/api/test-catalog', headers={'Accept': 'application/json'})
        assert resp.status_code == 403

    def test_api_item_rejects_non_staff_role(self, app, client, db, test_tenant, rollback_db):
        _login(client, db, test_tenant, _uniq('covapi403b'), 'patient')
        resp = client.get('/lab/api/test-catalog/1', headers={'Accept': 'application/json'})
        assert resp.status_code == 403

    def test_api_list_unauthenticated_with_json_accept_returns_401(
        self, app, client, db, test_tenant, rollback_db
    ):
        resp = client.get('/lab/api/test-catalog', headers={'Accept': 'application/json'})
        assert resp.status_code == 401

    def test_api_list_unauthenticated_without_json_accept_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        resp = client.get('/lab/api/test-catalog')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']
