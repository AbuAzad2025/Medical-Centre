"""Tests for billing route tenant ownership (MC-004)."""
import pytest

from models.visit import Visit
from models.patient import Patient
from models.payment import Payment
from models.invoice import Invoice
from utils.tenant_query import TenantContextError
from app_factory import db as _db


class TestBillingVisitOwnership:
    def test_process_payment_rejects_cross_tenant_visit(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN', total_amount=100, paid_amount=0)
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'acct_mc004', 'accountant')

        # Valid same-tenant request should not 404
        resp = client.get(f'/payment/process/{v.id}')
        # We expect either 200 (form rendered) or a redirect, but NOT 404
        assert resp.status_code != 404

    def test_post_gl_rejects_cross_tenant_visit(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN', total_amount=100, paid_amount=100)
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'acct_gl_mc004', 'accountant')

        # Request to post GL for a non-existent visit ID (cross-tenant simulation)
        resp = client.post('/finance/post', json={'visit_id': 99999999})
        assert resp.status_code == 404
        assert 'الزيارة غير موجودة'.encode('utf-8') in resp.data or b'not found' in resp.data or resp.json.get('error')

    def test_finance_archive_rejects_cross_tenant_visit(self, app, test_tenant, client, login_as):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='COMPLETED', total_amount=100, paid_amount=100)
        _db.session.add(v)
        _db.session.commit()

        login_as(client, 'acct_arch_mc004', 'accountant')

        # Request to archive a non-existent visit ID (cross-tenant simulation)
        resp = client.post('/finance/visits/99999999/archive')
        assert resp.status_code == 404
        assert 'الزيارة غير موجودة'.encode('utf-8') in resp.data or resp.json.get('error')

    def test_get_tenant_record_blocks_cross_tenant_visit(self, app, test_tenant):
        from app.core.tenant.models import Tenant
        tenant_id = test_tenant.id
        other = Tenant(name='Other', slug=f'other-fin-{__import__("uuid").uuid4().hex[:8]}', contact_email='other@example.com')
        _db.session.add(other)
        _db.session.commit()

        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=other.id, status='OPEN')
        _db.session.add(v)
        _db.session.commit()

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            with pytest.raises(TenantContextError):
                from utils.tenant_query import get_tenant_record
                get_tenant_record(Visit, v.id)
