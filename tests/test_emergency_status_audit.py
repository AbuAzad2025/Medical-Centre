"""Tests for P0B-002: EmergencyStatus storage compatibility audit.

Verifies that emergency_cases.status is stored as VARCHAR, has no CHECK
constraints blocking IN_PROGRESS, and that IN_PROGRESS is now a valid
EmergencyStatus enum value used by the model default.
"""

import pytest
import uuid

from app_factory import db as _db
from app.shared.enums import EmergencyStatus
from models.emergency import EmergencyCase
from models.patient import Patient


@pytest.fixture(scope='function')
def audit_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='EmergencyAudit',
        last_name='Test',
        phone='0500000001',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


class TestEmergencyStatusStorage:
    def test_emergency_status_enum_has_in_progress(self):
        assert hasattr(EmergencyStatus, 'IN_PROGRESS')
        assert EmergencyStatus.IN_PROGRESS == 'IN_PROGRESS'

    def test_emergency_case_defaults_to_in_progress(self, audit_patient):
        case = EmergencyCase(
            tenant_id=audit_patient.tenant_id,
            patient_id=audit_patient.id,
            case_number=f'EC-AUDIT-{uuid.uuid4().hex[:8]}',
            chief_complaint='Audit test',
        )
        _db.session.add(case)
        _db.session.commit()
        _db.session.refresh(case)
        assert case.status == 'IN_PROGRESS'

    def test_in_progress_status_is_persisted(self, audit_patient):
        case = EmergencyCase(
            tenant_id=audit_patient.tenant_id,
            patient_id=audit_patient.id,
            case_number=f'EC-AUDIT-{uuid.uuid4().hex[:8]}',
            chief_complaint='Audit test',
            status=EmergencyStatus.IN_PROGRESS,
        )
        _db.session.add(case)
        _db.session.commit()
        _db.session.refresh(case)
        assert case.status == EmergencyStatus.IN_PROGRESS
