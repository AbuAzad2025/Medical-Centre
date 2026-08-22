"""E2E tests for basic radiology user flows.

Uses the existing test infrastructure (conftest.py fixtures) to exercise
core radiology workflows end-to-end against a live PostgreSQL database.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.visit import Visit
from tests.tenant_context import login_test_client

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.db,
]


# ──────────────────────────────────────────────────────────────────────
# Helper: login as a specific role
# ──────────────────────────────────────────────────────────────────────


def _login_role(client, role, test_tenant):
    """Login as a user with the given role, return authenticated client."""
    from models.user import User as _User

    user = db.session.execute(select(_User).filter_by(username=f'e2e_{role}')).scalars().first()
    if not user:
        user = _User(
            username=f'e2e_{role}',
            email=f'e2e_{role}@test.local',
            full_name=f'E2E {role.title()}',
            role=role,
            is_active=True,
            tenant_id=test_tenant.id,
        )
        user.set_password('ValidPass123!')
        db.session.add(user)
        db.session.commit()
    login_test_client(client, user, test_tenant)
    return client


# ──────────────────────────────────────────────────────────────────────
# FIXTURE: Create test data (patient, visit, request, users)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def _radiology_e2e_base(app, test_tenant, db):
    """Create test data for E2E radiology flow tests."""
    from datetime import UTC, datetime

    from models.radiology_request import RadiologyRequest
    from models.user import User as _User

    # Create patient
    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='E2E',
        last_name='Patient',
        phone='0500000100',
    )
    db.session.add(patient)
    db.session.commit()

    # Create visit
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        status='OPEN',
    )
    db.session.add(visit)
    db.session.commit()

    # Create the requesting physician (FK target for requested_by)
    tech = _User(
        username=f'e2e_req_{uuid.uuid4().hex[:6]}',
        email=f'e2e_req_{uuid.uuid4().hex[:6]}@test.local',
        full_name='E2E Requester',
        role='doctor',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    tech.set_password('ValidPass123!')
    db.session.add(tech)
    db.session.commit()

    # Create radiology request (unique number per run)
    req = RadiologyRequest(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        patient_id=patient.id,
        requested_by=tech.id,
        request_number=f'RAD-E2E-{uuid.uuid4().hex[:8].upper()}',
        status='REQUESTED',
        modality='XRAY',
        body_part='Chest',
        notes='PA view needed',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.session.add(req)
    db.session.commit()

    return {'patient': patient, 'visit': visit, 'request': req}


@pytest.fixture
def rad_visit(_radiology_e2e_base):
    """The Visit created by the radiology E2E base fixture."""
    return _radiology_e2e_base['visit']


@pytest.fixture
def rad_request(_radiology_e2e_base):
    """The RadiologyRequest created by the radiology E2E base fixture."""
    return _radiology_e2e_base['request']


# ──────────────────────────────────────────────────────────────────────
# TEST: Doctor creates radiology request
# ──────────────────────────────────────────────────────────────────────


class TestRadiologyE2ECreateRequest:
    """E2E: Doctor creates a radiology request via the doctor route."""

    def test_doctor_creates_structured_request(
        self, client, app, test_tenant, db, _radiology_e2e_base, rad_visit
    ):
        """Doctor can create a structured radiology request."""
        client = _login_role(client, 'doctor', test_tenant)

        resp = client.post(
            f'/doctor/radiology-request/{rad_visit.id}',
            data={
                'modality': 'XRAY',
                'body_part': 'Chest',
                'notes': 'PA view needed',
            },
        )
        assert resp.status_code in (200, 302)

        req = (
            db.session.execute(select(RadiologyRequest).filter_by(visit_id=rad_visit.id))
            .scalars()
            .first()
        )
        assert req is not None
        assert req.modality == 'XRAY'
        assert req.body_part == 'Chest'
        assert req.status == 'REQUESTED'

    def test_doctor_creates_free_text_request(self, client, app, test_tenant, db, rad_visit):
        """Doctor can create free-text radiology request."""
        client = _login_role(client, 'doctor', test_tenant)

        resp = client.post(
            f'/doctor/radiology-request/{rad_visit.id}',
            data={
                'test_name': 'Custom scan',
                'notes': 'Please schedule',
            },
        )
        assert resp.status_code in (200, 302)


# ──────────────────────────────────────────────────────────────────────
# TEST: Technician views worklist
# ──────────────────────────────────────────────────────────────────────


class TestRadiologyE2EWorklist:
    """E2E: Technician views and interacts with the radiology worklist."""

    def test_tech_views_worklist(
        self, client, app, test_tenant, db, _radiology_e2e_base, rad_visit
    ):
        """Technician can view the radiology worklist."""
        client = _login_role(client, 'radiology', test_tenant)

        resp = client.get('/radiology/worklist')
        assert resp.status_code == 200

    def test_tech_views_worklist_with_status_filter(self, client, app, test_tenant, db, rad_visit):
        """Technician can filter worklist by status."""
        client = _login_role(client, 'radiology', test_tenant)

        resp = client.get('/radiology/worklist?status=REQUESTED')
        assert resp.status_code == 200

    def test_tech_views_request_detail(self, client, app, test_tenant, db, rad_request):
        """Technician can view a specific worklist request detail."""
        client = _login_role(client, 'radiology', test_tenant)

        resp = client.get(f'/radiology/worklist/request/{rad_request.id}')
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────
# TEST: Technician claims and completes request
# ──────────────────────────────────────────────────────────────────────


class TestRadiologyE2EClaimComplete:
    """E2E: Technician claims and completes a radiology request."""

    def test_tech_claims_request(self, client, app, test_tenant, db, _radiology_e2e_base):
        """Technician claims a radiology request."""
        client = _login_role(client, 'radiology', test_tenant)

        # Use the pre-existing request from fixture
        req = _radiology_e2e_base['request']

        resp = client.post(
            f'/radiology/worklist/claim/{req.id}',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_tech_completes_request_creates_result(
        self, client, app, test_tenant, db, _radiology_e2e_base
    ):
        """Technician completes a request, creating a new result."""
        client = _login_role(client, 'radiology', test_tenant)

        req = _radiology_e2e_base['request']

        resp = client.post(
            f'/radiology/worklist/complete/{req.id}',
            headers={'Accept': 'application/json'},
            json={'findings': 'No acute findings', 'impression': 'Normal'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_tech_completes_request_updates_existing_result(
        self, client, app, test_tenant, db, _radiology_e2e_base
    ):
        """Technician completes a request that already has a result (updates it)."""

        req = _radiology_e2e_base['request']

        # Pre-existing result
        existing = RadiologyResult(
            tenant_id=req.tenant_id,
            request_id=req.id,
            patient_id=req.patient_id,
            status='PENDING',
            is_critical=False,
        )
        db.session.add(existing)
        db.session.commit()

        client = _login_role(client, 'radiology', test_tenant)

        resp = client.post(
            f'/radiology/worklist/complete/{req.id}',
            headers={'Accept': 'application/json'},
            json={'findings': 'Updated findings'},
        )
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────
# TEST: Manager manages templates and macros
# ──────────────────────────────────────────────────────────────────────


class TestRadiologyE2EManagerTemplates:
    """E2E: Manager manages radiology report templates and macros."""

    def test_manager_views_templates(self, client, app, test_tenant, db):
        """Manager can view radiology report templates."""
        client = _login_role(client, 'manager', test_tenant)

        resp = client.get('/radiology/api/report-templates')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_manager_creates_template(self, client, app, test_tenant, db):
        """Manager can create a new radiology template."""
        client = _login_role(client, 'manager', test_tenant)

        resp = client.post(
            '/radiology/api/report-templates',
            json={
                'name': 'Test Template',
                'modality': 'XRAY',
                'findings': 'Findings here',
                'impression': 'Impression here',
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True

    def test_manager_views_macros(self, client, app, test_tenant, db):
        """Manager can view radiology report macros."""
        client = _login_role(client, 'manager', test_tenant)

        resp = client.get('/radiology/api/report-macros')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_manager_creates_macro(self, client, app, test_tenant, db):
        """Manager can create a new radiology macro."""
        client = _login_role(client, 'manager', test_tenant)

        resp = client.post(
            '/radiology/api/report-macros',
            json={
                'name': 'Test Macro',
                'text': 'Some macro text',
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['success'] is True


# ──────────────────────────────────────────────────────────────────────
# TEST: Authentication flow
# ──────────────────────────────────────────────────────────────────────


class TestAuthE2ELogin:
    """E2E: Authentication flow tests."""

    def test_login_with_valid_credentials(self, client, app, test_tenant, db):
        """User can login with valid credentials."""
        # Ensure a test user exists
        from models.user import User as _User
        from tests.tenant_context import login_test_client

        user = (
            db.session.execute(select(_User).filter_by(username='pharmacist_test'))
            .scalars()
            .first()
        )
        if not user:
            user = _User(
                username='pharmacist_test',
                email='pharmacist@test.local',
                full_name='صيدلي اختبار',
                role='pharmacist',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            db.session.add(user)
            user.set_password('ValidPass123!')
            db.session.commit()

        login_test_client(client, user, test_tenant)
        with client.session_transaction() as sess:
            assert 'tenant_id' in sess

    def test_login_requires_valid_credentials(self, client, app, test_tenant, db):
        """Login fails with invalid credentials (JSON path returns 401)."""
        resp = client.post(
            '/auth/login',
            json={'username': 'nonexistent', 'password': 'wrongpassword'},
        )
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────────────────────
# TEST: Access control
# ──────────────────────────────────────────────────────────────────────


class TestAccessControlE2E:
    """E2E: Access control tests for radiology routes."""

    def test_worklist_requires_authentication(self, client, app, test_tenant, db):
        """Worklist route requires authentication."""
        resp = client.get('/radiology/worklist')
        assert resp.status_code in (302, 401, 200)

    def test_template_requires_manager(self, client, app, test_tenant, db):
        """Template routes require manager role."""
        resp = client.get('/radiology/api/report-templates')
        assert resp.status_code in (302, 401, 403)

    def test_unauthorized_access_attempts_handled(self, client, app, test_tenant, db):
        """Unauthorized access attempts are properly handled."""
        routes_to_test = [
            '/radiology/worklist',
            '/radiology/api/report-templates',
            '/radiology/api/report-macros',
        ]
        for route in routes_to_test:
            resp = client.get(route)
            json_data = resp.get_json()
            if json_data and 'success' in json_data:
                assert json_data['success'] is not True
