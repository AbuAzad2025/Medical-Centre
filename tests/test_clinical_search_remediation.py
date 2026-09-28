"""DB-backed proof that the refactored clinical search paths actually work.

These are the interfaces the directive calls life-and-death: a nurse searching
visits by a patient name, a doctor searching the patient list, an emergency
lookup. Each asserts real database state under RLS, not that a function is
callable. A search that returns nothing is the exact bug being fixed, so an
empty result must fail the test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.extensions import db
from models.patient import Patient
from models.visit import Visit

pytestmark = pytest.mark.usefixtures('rollback_db', 'test_tenant')


def _patient(**kw):
    p = Patient(
        first_name=kw.get('first_name', 'Sara'),
        last_name=kw.get('last_name', 'Ahmed'),
        first_name_ar=kw.get('first_name_ar'),
        last_name_ar=kw.get('last_name_ar'),
        phone=kw.get('phone'),
        national_id=kw.get('national_id'),
        gender='female',
        tenant_id=kw.get('tenant_id'),
    )
    db.session.add(p)
    db.session.commit()
    return p


class TestSearchIds:
    def test_finds_by_partial_name(self, test_tenant):
        p = _patient(first_name='Sara', last_name='Ahmed', tenant_id=test_tenant.id)
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('ara'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'partial name search returned nothing'

    def test_finds_by_partial_phone(self, test_tenant):
        p = _patient(phone='0599123456', tenant_id=test_tenant.id)
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('1234'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'partial phone search returned nothing'

    def test_finds_by_partial_national_id(self, test_tenant):
        p = _patient(national_id='ID-998877', tenant_id=test_tenant.id)
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('9988'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'partial national id search returned nothing'

    def test_finds_by_arabic_name(self, test_tenant):
        p = _patient(
            first_name='Sara',
            last_name='Ahmed',
            first_name_ar='سارة',
            last_name_ar='أحمد',
            tenant_id=test_tenant.id,
        )
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('سارة'))))
            .scalars()
            .all()
        )
        assert p.id in found, 'arabic name search returned nothing'

    def test_does_not_match_an_unrelated_patient(self, test_tenant):
        other = _patient(first_name='Zainab', last_name='Othman', tenant_id=test_tenant.id)
        found = (
            db.session.execute(select(Patient.id).where(Patient.id.in_(Patient.search_ids('Sara'))))
            .scalars()
            .all()
        )
        assert other.id not in found

    def test_respects_tenant_isolation(self, test_tenant):
        """A search must not reach another tenant's patient."""
        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant

        p = _patient(first_name='Sara', last_name='Ahmed', tenant_id=test_tenant.id)
        # Capture the id as a plain int: after the tenant switch the ORM
        # instance is no longer visible under the new RLS binding.
        patient_id = p.id
        other = Tenant(
            name='Search Other',
            slug=f'search-{p.id}-{test_tenant.id}',
            status='active',
            contact_email='search-other@example.test',
        )
        db.session.add(other)
        db.session.commit()
        bind_g_tenant(other)
        try:
            found = (
                db.session.execute(
                    select(Patient.id).where(Patient.id.in_(Patient.search_ids('Sara')))
                )
                .scalars()
                .all()
            )
            assert patient_id not in found, 'search crossed the tenant boundary'
        finally:
            bind_g_tenant(test_tenant)


class TestClinicalSearchServices:
    def test_nursing_search_finds_the_visit(self, test_tenant):
        from services.nursing_service import NursingService

        p = _patient(first_name='Sara', last_name='Ahmed', tenant_id=test_tenant.id)
        v = Visit(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            status='OPEN',
            payment_status='PENDING',
        )
        db.session.add(v)
        db.session.commit()

        hits = NursingService.get_nurse_patients('Sara')
        assert hits, 'nursing search returned no visits'
        assert any(x.patient_id == p.id for x in hits)

    def test_emergency_search_finds_the_patient(self, test_tenant):
        from models.emergency import EmergencyCase
        from services.emergency_service import EmergencyService

        p = _patient(first_name='Sara', last_name='Ahmed', tenant_id=test_tenant.id)
        case = EmergencyCase(
            tenant_id=test_tenant.id,
            patient_id=p.id,
            case_number=f'EC-TEST-{p.id}',
            chief_complaint='ألم',
            status='OPEN',
        )
        db.session.add(case)
        db.session.commit()

        rows = EmergencyService.list_cases(search='Sara')
        assert rows, 'emergency search returned nothing'
        assert any(r.patient_id == p.id for r in rows)
