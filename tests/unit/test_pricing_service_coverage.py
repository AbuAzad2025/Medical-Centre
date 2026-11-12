"""Coverage for services/pricing_service.py.

The pricing service is what the reception desk asks "what does this visit
cost?" and what the manager asks "how much revenue did we make?". Its
methods had never been exercised, so the alias matching, the doctor pricing
lookup, the visit-cost calculation and the summary had never run.

Each test class is named after the method it covers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _service_price(db, tenant_id, name='Consultation', service_type='consultation',
                   base_price=100.0, insurance_price=80.0, cash_price=90.0, vip_price=70.0):
    from models.pricing import ServicePrice

    price = ServicePrice(
        tenant_id=tenant_id,
        service_name=name,
        service_type=service_type,
        base_price=Decimal(str(base_price)),
        insurance_price=Decimal(str(insurance_price)),
        cash_price=Decimal(str(cash_price)),
        vip_price=Decimal(str(vip_price)),
        is_active=True,
    )
    db.session.add(price)
    db.session.flush()
    return price


def _doctor_pricing(db, tenant_id, doctor_id, consultation_price=100.0, department_id=None):
    from models.pricing import DoctorPricing

    pricing = DoctorPricing(
        tenant_id=tenant_id,
        doctor_id=doctor_id,
        department_id=department_id,
        consultation_price=Decimal(str(consultation_price)),
        is_active=True,
    )
    db.session.add(pricing)
    db.session.flush()
    return pricing


def _doctor(db, tenant_id, username='pricing_doc'):
    from models.user import User

    doctor = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role='doctor',
        is_active=True,
        tenant_id=tenant_id,
    )
    doctor.set_password('test123')
    db.session.add(doctor)
    db.session.flush()
    return doctor


class TestGetServicePrice:
    """``get_service_price`` — the lookup used at the desk."""

    def test_a_configured_price_is_returned(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        _service_price(db, test_tenant.id, name='Consultation', service_type='consultation')

        assert PricingService.get_service_price('Consultation', 'consultation') == 90.0
        assert PricingService.get_service_price('Consultation', 'consultation', 'insurance') == 80.0
        assert PricingService.get_service_price('Consultation', 'consultation', 'cash') == 90.0
        assert PricingService.get_service_price('Consultation', 'consultation', 'vip') == 70.0

    def test_an_unknown_service_returns_zero(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        assert PricingService.get_service_price('No Such Service', 'consultation') == 0.0

    def test_an_alias_matches_the_standard_service(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        _service_price(db, test_tenant.id, name='CBC', service_type='lab_test')

        # 'cbc' is an alias for 'CBC' in the normaliser.
        assert PricingService.get_service_price('cbc', 'lab_test') == 90.0

    def test_a_failing_lookup_returns_zero(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        with patch('services.pricing_service.db.session.execute', side_effect=RuntimeError('db down')):
            assert PricingService.get_service_price('Consultation', 'consultation') == 0.0


class TestGetDoctorPrice:
    """``get_doctor_price`` — a doctor's price, or the department's."""

    def test_a_doctor_with_pricing_returns_it(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        doctor = _doctor(db, test_tenant.id)
        _doctor_pricing(db, test_tenant.id, doctor.id, consultation_price=250.0)

        assert PricingService.get_doctor_price(doctor.id) == 250.0

    def test_a_doctor_without_pricing_falls_back_to_the_department(self, app, db, test_tenant):
        from models.department import Department
        from models.user import User
        from services.pricing_service import PricingService

        department = Department(
            name=f'Dept-{datetime.now(UTC).strftime("%H%M%S%f")}',
            name_ar='قسم',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        db.session.add(department)
        db.session.flush()

        doctor = User(
            username='fallback_doc',
            email='fallback_doc@test.local',
            full_name='Fallback Doctor',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
            department_id=department.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.flush()

        # A department-level price (doctor_id is None) is the fallback.
        dept_pricing = _doctor_pricing(
            db, test_tenant.id, None, consultation_price=150.0, department_id=department.id
        )
        dept_pricing.doctor_id = None
        db.session.flush()

        assert PricingService.get_doctor_price(doctor.id) == 150.0

    def test_a_missing_doctor_returns_zero(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        assert PricingService.get_doctor_price(99999) == 0.0

    def test_a_failing_lookup_returns_zero(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        with patch('services.pricing_service.db.session.execute', side_effect=RuntimeError('db down')):
            assert PricingService.get_doctor_price(1) == 0.0


class TestCreateServicePrice:
    """``create_service_price`` — adding a price to the catalogue."""

    def test_a_valid_price_is_created(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.create_service_price(
            {
                'service_name': 'New Consultation',
                'service_type': 'consultation',
                'base_price': 120.0,
                'insurance_price': 100.0,
                'cash_price': 110.0,
                'vip_price': 90.0,
                'description': 'A consultation',
                'requires_doctor': True,
                'requires_department': False,
            }
        )
        assert result['success'] is True
        assert result['service_price_id']

    def test_a_failing_write_is_reported(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        with patch('services.pricing_service.safe_commit', return_value=False):
            result = PricingService.create_service_price(
                {'service_name': 'X', 'service_type': 'consultation', 'base_price': 10.0}
            )
        assert result['success'] is False


class TestCreateDoctorPricing:
    """``create_doctor_pricing`` — a doctor's own price list."""

    def test_a_valid_price_is_created(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        doctor = _doctor(db, test_tenant.id, username='pricing_doc_create')
        result = PricingService.create_doctor_pricing(
            doctor.id,
            {
                'consultation_price': 200.0,
                'visit_type': 'consultation',
                'payment_method': 'cash',
            },
        )
        assert result['success'] is True
        assert result['pricing_id']

    def test_a_missing_doctor_is_refused(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.create_doctor_pricing(99999, {'base_price': 200.0})
        assert result['success'] is False

    def test_a_failing_write_is_reported(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        doctor = _doctor(db, test_tenant.id, username='pricing_doc_fail')

        with patch('services.pricing_service.safe_commit', return_value=False):
            result = PricingService.create_doctor_pricing(
                doctor.id, {'consultation_price': 200.0}
            )
        assert result['success'] is False


class TestUpdateServicePrice:
    """``update_service_price`` — editing a price."""

    def test_an_existing_price_is_updated(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        price = _service_price(db, test_tenant.id, name='Editable', service_type='consultation')
        result = PricingService.update_service_price(
            price.id, {'base_price': 150.0, 'is_active': False}
        )
        assert result['success'] is True

        db.session.refresh(price)
        assert float(price.base_price) == 150.0
        assert price.is_active is False

    def test_an_unknown_price_is_refused(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.update_service_price(99999, {'base_price': 150.0})
        assert result['success'] is False

    def test_a_failing_write_is_reported(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        price = _service_price(db, test_tenant.id, name='UpdFail', service_type='consultation')

        with patch('services.pricing_service.safe_commit', return_value=False):
            result = PricingService.update_service_price(price.id, {'base_price': 150.0})
        assert result['success'] is False


class TestPricingSummary:
    """``get_pricing_summary`` — the manager's overview."""

    def test_it_returns_a_summary(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        _service_price(db, test_tenant.id, name='Summary Svc', service_type='consultation')

        summary = PricingService.get_pricing_summary()
        assert isinstance(summary, dict)

    def test_a_failing_lookup_returns_an_empty_summary(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        with patch('services.pricing_service.db.session.execute', side_effect=RuntimeError('db down')):
            summary = PricingService.get_pricing_summary()
        assert isinstance(summary, dict)


class TestCalculateVisitCost:
    """``calculate_visit_cost`` — what a visit costs."""

    def test_a_visit_without_services_costs_nothing(self, app, db, test_tenant):
        from services.pricing_service import PricingService

        result = PricingService.calculate_visit_cost(
            {'payment_method': 'cash'}
        )
        assert result['success'] is True
        assert result['total_cost'] == 0.0

    def test_a_visit_with_a_doctor_price(self, app, db, test_tenant):
        from models.user import User
        from services.pricing_service import PricingService

        doctor = User(
            username='calc_doc',
            email='calc_doc@test.local',
            full_name='Calc Doctor',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.flush()

        _doctor_pricing(db, test_tenant.id, doctor.id, consultation_price=200.0)

        result = PricingService.calculate_visit_cost(
            {'doctor_id': doctor.id, 'visit_type': 'consultation', 'payment_method': 'cash'}
        )
        assert result['success'] is True
        assert result['total_cost'] == 200.0
