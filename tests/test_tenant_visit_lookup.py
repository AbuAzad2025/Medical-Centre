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

    def test_missing_tenant_context_raises(self, app, test_tenant):
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
            # Missing tenant context must fail closed for tenant-scoped models
            with pytest.raises(TenantContextError):
                get_tenant_record(Visit, v.id)

    def test_explicit_matching_tenant_id_allowed(self, app, test_tenant):
        """Ticket 3: explicit tenant_id that matches g.tenant_id is allowed."""
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
            record = get_tenant_record(Visit, v.id, tenant_id=tenant_id)
            assert record.id == v.id

    def test_explicit_conflicting_tenant_id_rejected(self, app, test_tenant):
        """Ticket 3: explicit tenant_id that conflicts with g.tenant_id is rejected."""
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
            with pytest.raises(TenantContextError):
                # explicit tenant_id differs from g.tenant_id -> must fail
                get_tenant_record(Visit, v.id, tenant_id=999999)

    def test_explicit_tenant_id_rejected_when_context_missing(self, app, test_tenant):
        """Ticket 3: explicit tenant_id is rejected when g.tenant_id is absent."""
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
            with pytest.raises(TenantContextError):
                # explicit tenant_id without g.tenant_id -> must fail closed
                get_tenant_record(Visit, v.id, tenant_id=tenant_id)


class TestReceptionRoutesFailClosedWithoutTenant:
    def test_view_visit_fails_without_tenant_context(self, app, test_tenant, client):
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        v = Visit(patient_id=p.id, tenant_id=tenant_id, status='OPEN')
        _db.session.add(v)
        _db.session.commit()

        # Simulate a request without tenant context (g.tenant_id = None)
        with app.test_request_context():
            from flask import g
            g.tenant_id = None
            # The route will catch TenantContextError and flash/redirect
            resp = client.get(f'/reception/view_visit/{v.id}', follow_redirects=False)
            # Should redirect (flash error) rather than exposing cross-tenant data
            assert resp.status_code == 302

    def test_edit_visit_fails_without_tenant_context(self, app, test_tenant, client):
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
            resp = client.get(f'/reception/edit_visit/{v.id}', follow_redirects=False)
            assert resp.status_code == 302

    def test_end_visit_fails_without_tenant_context(self, app, test_tenant, client):
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
            resp = client.post(f'/reception/visits/{v.id}/end', follow_redirects=False)
            assert resp.status_code == 302

    def test_archive_visit_fails_without_tenant_context(self, app, test_tenant, client):
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
            resp = client.post(f'/reception/visits/{v.id}/archive', follow_redirects=False)
            assert resp.status_code == 302
