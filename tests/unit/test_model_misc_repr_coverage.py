"""Coverage for the remaining ``__repr__``/``to_dict`` gaps in the model layer.

The companions of :mod:`tests.unit.test_model_repr_to_dict_coverage`: a second
batch of models whose human-readable label or serialisation had never been
executed. Each test class is named after the module it covers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestProblemList:
    """models/problem_list.py"""

    def test_reprs(self):
        from models.problem_list import AllergyIntolerance, PatientProblem

        assert repr(PatientProblem(status='ACTIVE')) == '<PatientProblem ACTIVE>'
        assert repr(AllergyIntolerance(substance='Penicillin')) == (
            '<AllergyIntolerance Penicillin>'
        )


class TestRefundRequest:
    """models/refund_request.py"""

    def test_to_dict(self, app, db, test_tenant):
        from models.payment import Payment
        from models.refund_request import RefundRequest

        payment = Payment(
            tenant_id=test_tenant.id,
            amount=Decimal('100.00'),
            method='cash',
            currency='ILS',
            status='CONFIRMED',
        )
        db.session.add(payment)
        db.session.flush()

        request = RefundRequest(
            tenant_id=test_tenant.id,
            payment_id=payment.id,
            amount=Decimal('42.50'),
            reason='service not provided',
            status='PENDING',
            notes='patient request',
        )
        db.session.add(request)
        db.session.flush()

        data = request.to_dict()
        assert data['tenant_id'] == test_tenant.id
        assert data['payment_id'] == payment.id
        assert data['amount'] == 42.5
        assert data['reason'] == 'service not provided'
        assert data['status'] == 'PENDING'
        assert data['requested_at'] is not None
        assert data['approved_at'] is None
        assert data['notes'] == 'patient request'


class TestRadiologyResult:
    """models/radiology_result.py"""

    def test_repr(self):
        from models.radiology_result import RadiologyResult

        assert repr(RadiologyResult(request_id=17)) == '<RadiologyResult request=17>'


class TestVaccination:
    """models/vaccination.py"""

    def test_reprs(self):
        from models.vaccination import Immunization, Vaccine

        assert repr(Vaccine(name='Influenza')) == '<Vaccine Influenza>'
        assert repr(Immunization(dose_number=2)) == '<Immunization 2>'


class TestServiceMaster:
    """models/service.py"""

    def test_repr(self):
        from models.service import ServiceMaster

        assert repr(ServiceMaster(code='CONS')) == '<ServiceMaster CONS>'


class TestAiImaging:
    """models/ai_imaging.py"""

    def test_repr(self):
        from models.ai_imaging import AIImagingAnalysis

        analysis = AIImagingAnalysis(
            patient_id=5, analysis_type='TRIAGE', status='COMPLETED'
        )
        assert repr(analysis) == '<AIImagingAnalysis patient=5 type=TRIAGE status=COMPLETED>'


class TestTelemedicine:
    """models/telemedicine.py"""

    def test_repr(self):
        from models.telemedicine import TelemedicineAppointment

        appointment = TelemedicineAppointment(patient_id=8, status='SCHEDULED')
        assert repr(appointment) == '<TelemedicineAppointment patient=8 status=SCHEDULED>'


class TestMedicationReconciliation:
    """models/medication_reconciliation.py"""

    def test_repr(self):
        from models.medication_reconciliation import MedicationReconciliation

        reconciliation = MedicationReconciliation(status='COMPLETED')
        assert repr(reconciliation) == '<MedicationReconciliation COMPLETED>'


class TestQueueManagement:
    """models/queue_management.py"""

    def test_queue_repr_without_patient(self):
        from models.queue_management import QueueManagement

        entry = QueueManagement(queue_number='A-12')
        assert repr(entry) == '<QueueManagement A-12 - Unknown>'

    def test_queue_settings_repr_without_department(self):
        from models.queue_management import QueueSettings

        settings = QueueSettings()
        assert repr(settings) == '<QueueSettings for Unknown>'


class TestUnifiedMixins:
    """models/unified_mixins.py"""

    def test_declared_relationships_are_built(self):
        import warnings

        from models.unified_mixins import MedicalEntityMixin

        # ``declared_attr`` evaluates the relationship factory when the mixin is
        # applied to a model. Calling the factory directly is the same call the
        # ORM makes, so it proves the mixin produces real relationships for
        # Patient, Visit and User rather than plain attributes.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            relationships = {
                name: MedicalEntityMixin.__dict__[name].fget(MedicalEntityMixin)
                for name in ('patient', 'visit', 'doctor')
            }

        assert relationships['patient'].lazy == 'selectin'
        assert relationships['patient'].argument == 'Patient'
        assert relationships['visit'].lazy == 'selectin'
        assert relationships['visit'].argument == 'Visit'
        assert relationships['doctor'].lazy == 'selectin'
        assert relationships['doctor'].argument == 'User'


class TestVisit:
    """models/visit.py"""

    def test_repr(self):
        from models.visit import Visit

        visit = Visit(visit_number='V-1', patient_id=4)
        assert repr(visit) == '<Visit #V-1 patient=4>'

    def test_calculate_insurance_amounts_ignores_unparsable_percentage(self):
        from models.visit import Visit

        visit = Visit(
            payment_method='insurance',
            insurance_coverage_percentage='not-a-number',
            total_amount=Decimal('100.00'),
        )
        visit.calculate_insurance_amounts()
        assert visit.insurance_amount is None

    def test_calculate_insurance_amounts_ignores_out_of_range_percentage(self):
        from models.visit import Visit

        visit = Visit(
            payment_method='insurance',
            insurance_coverage_percentage=120,
            total_amount=Decimal('100.00'),
        )
        visit.calculate_insurance_amounts()
        assert visit.insurance_amount is None

    def test_calculate_insurance_amounts_clamps_negative_total(self):
        from models.visit import Visit

        visit = Visit(
            payment_method='insurance',
            insurance_coverage_percentage=50,
            total_amount=Decimal('-20.00'),
        )
        visit.calculate_insurance_amounts()
        assert visit.insurance_amount == Decimal('0')
        assert visit.patient_share == Decimal('0')


class TestReferral:
    """models/referral.py"""

    def test_repr(self):
        from models.referral import Referral

        assert repr(Referral(status='PENDING')) == '<Referral PENDING>'


class TestDepartment:
    """models/department.py"""

    def test_repr_prefers_the_arabic_name(self):
        from models.department import Department

        department = Department(name='Cardiology', name_ar='القلب')
        assert repr(department) == '<Department القلب>'

    def test_repr_falls_back_to_the_english_name(self):
        from models.department import Department

        department = Department(name='Cardiology', name_ar=None)
        assert repr(department) == '<Department Cardiology>'


class TestModuleModels:
    """app/core/module/models.py"""

    def test_module_definition_repr(self):
        from app.core.module.models import ModuleDefinition

        definition = ModuleDefinition(name='reception')
        assert repr(definition) == '<ModuleDefinition reception>'

    def test_tenant_module_repr(self):
        from app.core.module.models import TenantModule

        module = TenantModule(tenant_id=3, module_name='reception', is_active=True)
        assert repr(module) == '<TenantModule 3:reception=True>'
