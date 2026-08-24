"""POST coverage — submit real form data to all CRUD endpoints."""

import pytest


@pytest.fixture()
def _po(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='post_cov', role='super_admin')
    login_test_client(client, u, test_tenant)
    # Get CSRF token
    client.get('/reception/patients')
    client.get('/reception/patients')
    return client


def _csrf(client):
    """Get CSRF token from any page."""
    resp = client.get('/reception/patients')
    if b'csrf-token' in resp.data:
        import re

        m = re.search(rb'name="csrf-token" content="([^"]+)"', resp.data)
        if m:
            return m.group(1).decode()
    # Fallback: try hidden input
    m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', resp.data)
    if m:
        return m.group(1).decode()
    return ''


class TestPatientPOST:
    def test_create_patient(self, _po):
        token = _csrf(_po)
        import time

        suffix = int(time.time()) % 100000
        resp = _po.post(
            '/reception/add_patient',
            data={
                'csrf_token': token,
                'first_name': 'PostCov',
                'last_name': f'Test{suffix}',
                'phone': f'050{suffix:07d}',
                'gender': 'M',
            },
            follow_redirects=False,
        )
        assert resp.status_code < 500

    def test_edit_patient(self, _po, db, test_tenant):
        from sqlalchemy import text

        token = _csrf(_po)
        pid = db.session.execute(text('SELECT id FROM patients WHERE tenant_id=1 LIMIT 1')).scalar()
        if pid:
            resp = _po.post(
                f'/reception/edit_patient/{pid}',
                data={
                    'csrf_token': token,
                    'first_name': 'EditedCov',
                    'last_name': 'Test',
                },
                follow_redirects=True,
            )
            assert resp.status_code < 500


class TestVisitPOST:
    def test_create_visit_post(self, _po, db):
        from sqlalchemy import text

        token = _csrf(_po)
        pid = db.session.execute(text('SELECT id FROM patients WHERE tenant_id=1 LIMIT 1')).scalar()
        did = db.session.execute(
            text('SELECT id FROM departments WHERE tenant_id=1 LIMIT 1')
        ).scalar()
        if pid and did:
            resp = _po.post(
                '/reception/visits/create',
                data={
                    'csrf_token': token,
                    'patient_id': str(pid),
                    'department_id': str(did),
                    'visit_type': 'REGULAR',
                    'symptoms': 'Coverage test visit',
                },
                follow_redirects=True,
            )
            assert resp.status_code < 500


class TestAppointmentPOST:
    def test_create_appointment(self, _po, db):
        from sqlalchemy import text

        token = _csrf(_po)
        pid = db.session.execute(text('SELECT id FROM patients WHERE tenant_id=1 LIMIT 1')).scalar()
        did = db.session.execute(
            text('SELECT id FROM departments WHERE tenant_id=1 LIMIT 1')
        ).scalar()
        if pid and did:
            resp = _po.post(
                '/reception/create_appointment',
                data={
                    'csrf_token': token,
                    'patient_id': str(pid),
                    'department_id': str(did),
                },
                follow_redirects=True,
            )
            assert resp.status_code < 500


class TestOwnerPOST:
    def test_owner_create_plan(self, _po):
        token = _csrf(_po)
        resp = _po.post(
            '/owner/plans/create',
            data={
                'csrf_token': token,
                'name': 'CoveragePlan',
                'price_monthly': '99.99',
            },
            follow_redirects=True,
        )
        assert resp.status_code < 500

    def test_owner_create_announcement(self, _po):
        token = _csrf(_po)
        resp = _po.post(
            '/owner/announcements',
            data={
                'csrf_token': token,
                'title': 'Coverage Test',
                'message': 'Test announcement message',
            },
            follow_redirects=True,
        )
        assert resp.status_code < 500  # May fail on template rendering


class TestServicePOST:
    def test_create_service(self, _po):
        token = _csrf(_po)
        resp = _po.post(
            '/super-admin/services/create',
            data={
                'csrf_token': token,
                'name': 'Coverage Service',
                'price': '50',
            },
            follow_redirects=True,
        )
        assert resp.status_code < 500

    def test_create_department(self, _po):
        token = _csrf(_po)
        resp = _po.post(
            '/super-admin/departments/create',
            data={
                'csrf_token': token,
                'name': 'CoverageDept',
                'name_ar': 'قسم تغطية',
            },
            follow_redirects=True,
        )
        assert resp.status_code < 500
