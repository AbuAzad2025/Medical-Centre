"""Tests for utils.tenant_query.get_tenant_record (reception visit lookup)."""
import uuid

import pytest

from models.visit import Visit
from models.patient import Patient
from app.core.tenant.models import Tenant
from utils.tenant_query import get_tenant_record, TenantContextError
from app_factory import db as _db


class TestGetTenantRecordVisit:
    def test_same_tenant_visit_found(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN')
        _db.session.add(v)
        _db.session.commit()

        with app.test_request_context():
            from flask import g
            g.tenant_id = tenant_id
            record = get_tenant_record(Visit, v.id)
            assert record.id == v.id

    def test_cross_tenant_visit_raises(self, app, test_tenant):
        tenant_id = test_tenant.id
        other_slug = f'other-tenant-{uuid.uuid4().hex[:8]}'
        other = Tenant(name='Other', slug=other_slug, contact_email='other@example.com')
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
                get_tenant_record(Visit, v.id)

    def test_missing_visit_raises(self, app, test_tenant):
        with app.test_request_context():
            from flask import g
            g.tenant_id = test_tenant.id
            with pytest.raises(TenantContextError):
                get_tenant_record(Visit, 99999999)

    def test_no_tenant_context_skips_check(self, app, test_tenant):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN')
        _db.session.add(v)
        _db.session.commit()

        with app.test_request_context():
            from flask import g
            g.tenant_id = None
            # When tenant_id is None, get_tenant_record should not enforce tenant check
            # but should still return the record if it exists
            record = get_tenant_record(Visit, v.id)
            assert record.id == v.id
