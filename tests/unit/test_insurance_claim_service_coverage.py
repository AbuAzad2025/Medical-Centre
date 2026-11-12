"""Coverage tests for services.insurance_claim_service.py."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from models.user import User
from services.insurance_claim_service import InsuranceClaimService

pytest_plugins = ['tests._isolated_tenant']


def _make_user(db, tenant_id, username, role='doctor', is_active=True, department_id=None):
    u = User(
        username=username,
        email=f'{username}@test.local',
        full_name=username.replace('_', ' ').title(),
        role=role,
        is_active=is_active,
        tenant_id=tenant_id,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.flush()
    return u


def _make_department(db, tenant_id, name='Dept'):
    from models.department import Department

    d = Department(
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        tenant_id=tenant_id,
    )
    db.session.add(d)
    db.session.flush()
    return d


def _make_patient(db, tenant_id, first_name='Patient', last_name='Test'):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_visit(db, tenant_id, patient, department, status='COMPLETED'):
    from models.visit import Visit

    v = Visit(
        patient_id=patient.id,
        department_id=department.id,
        doctor_id=None,
        status=status,
        payment_status='PENDING',
        total_amount=0,
        paid_amount=0,
        visit_type='REGULAR',
        payment_method='cash',
        is_emergency=False,
        created_at=datetime.now(UTC),
        visit_date=datetime.now(UTC).date(),
    )
    db.session.add(v)
    db.session.flush()
    return v


def _make_invoice(db, tenant_id, visit, total_amount=Decimal('100.00')):
    from models.invoice import Invoice

    inv = Invoice(
        tenant_id=tenant_id,
        invoice_number=f'INV-{datetime.now(UTC).strftime("%H%M%S%f")}',
        visit_id=visit.id,
        total_amount=total_amount,
        currency='ILS',
        status='ISSUED',
        created_at=datetime.now(UTC),
    )
    db.session.add(inv)
    db.session.flush()
    return inv


def _make_insurance_company(db, tenant_id, name='Test Insurance'):
    from models.insurance import InsuranceCompany

    c = InsuranceCompany(
        tenant_id=tenant_id,
        name=f'{name}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        name_ar=name,
        is_active=True,
        created_at=datetime.now(UTC),
    )
    db.session.add(c)
    db.session.flush()
    return c


def _make_claim(
    db, tenant_id, visit, invoice, company, status='DRAFT', total_claim=Decimal('100.00')
):
    from models.insurance import InsuranceClaim

    claim = InsuranceClaim(
        tenant_id=tenant_id,
        visit_id=visit.id,
        invoice_id=invoice.id,
        company_id=company.id,
        claim_number=f'CLM-{datetime.now(UTC).strftime("%H%M%S%f")}',
        status=status,
        total_claim=total_claim,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.session.add(claim)
    db.session.flush()
    return claim


class TestInsuranceClaimService:
    def test_list_claims_no_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = InsuranceClaimService.list_claims(None)
        assert result == []

    def test_list_claims_with_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        _make_claim(db, test_tenant.id, visit, invoice, company, status='DRAFT')

        result = InsuranceClaimService.list_claims(test_tenant.id)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['claim_number'].startswith('CLM-')

    def test_list_claims_different_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        # Query with a different tenant_id should return empty
        result = InsuranceClaimService.list_claims(99999)
        assert result == []

    def test_create_claim_no_ids(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        ok, result = InsuranceClaimService.create_claim(
            visit_id=None,
            invoice_id=None,
            company_id=1,
            total_claim=Decimal('100'),
            tenant_id=test_tenant.id,
        )
        assert ok is False
        assert 'error' in result

    def test_create_claim_with_visit(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        _invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)

        ok, result = InsuranceClaimService.create_claim(
            visit_id=visit.id,
            invoice_id=None,
            company_id=company.id,
            total_claim=Decimal('200.00'),
            tenant_id=test_tenant.id,
        )
        assert ok is True
        assert 'id' in result
        assert 'claim_number' in result
        assert result['status'] == 'DRAFT'
        assert result['claim_number'].startswith('CLM-')

    def test_create_claim_with_invoice_only(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)

        ok, result = InsuranceClaimService.create_claim(
            visit_id=None,
            invoice_id=invoice.id,
            company_id=company.id,
            total_claim=Decimal('200.00'),
            tenant_id=test_tenant.id,
        )
        assert ok is True
        assert result['status'] == 'DRAFT'

    def test_create_claim_db_error(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        company = _make_insurance_company(db, test_tenant.id)

        def commit_false(*a, **k):
            return False

        import services.insurance_claim_service as ics_module

        monkeypatch.setattr(ics_module, 'safe_commit', commit_false)

        ok, result = InsuranceClaimService.create_claim(
            visit_id=visit.id,
            invoice_id=None,
            company_id=company.id,
            total_claim=Decimal('200.00'),
            tenant_id=test_tenant.id,
        )
        assert ok is False
        assert 'error' in result

    def test_submit_claim_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        ok, result = InsuranceClaimService.submit_claim(claim_id=99999, tenant_id=test_tenant.id)
        assert ok is False
        assert 'error' in result

    def test_submit_claim_wrong_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='DRAFT')

        ok, result = InsuranceClaimService.submit_claim(claim_id=claim.id, tenant_id=99999)
        assert ok is False
        assert 'error' in result

    def test_submit_claim_not_draft(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SUBMITTED')

        ok, result = InsuranceClaimService.submit_claim(claim_id=claim.id, tenant_id=test_tenant.id)
        assert ok is False
        assert 'cannot submit' in result['error']

    def test_submit_claim_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='DRAFT')

        ok, result = InsuranceClaimService.submit_claim(claim_id=claim.id, tenant_id=test_tenant.id)
        assert ok is True
        assert result['status'] == 'SUBMITTED'

    def test_adjudicate_claim_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        ok, _result = InsuranceClaimService.adjudicate_claim(
            claim_id=99999,
            approved_amount=Decimal('50'),
            status='APPROVED',
            notes='ok',
            tenant_id=test_tenant.id,
        )
        assert ok is False

    def test_adjudicate_claim_wrong_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SUBMITTED')

        ok, _result = InsuranceClaimService.adjudicate_claim(
            claim_id=claim.id,
            approved_amount=Decimal('50'),
            status='APPROVED',
            notes='ok',
            tenant_id=99999,
        )
        assert ok is False

    def test_adjudicate_claim_invalid_status(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='DRAFT')

        ok, result = InsuranceClaimService.adjudicate_claim(
            claim_id=claim.id,
            approved_amount=Decimal('50'),
            status='INVALID_STATUS',
            notes='ok',
            tenant_id=test_tenant.id,
        )
        assert ok is False
        assert 'invalid status' in result['error']

    def test_adjudicate_claim_success(self, app, db, test_tenant):
        from app.shared.enums import InsuranceClaimStatus
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SUBMITTED')

        ok, result = InsuranceClaimService.adjudicate_claim(
            claim_id=claim.id,
            approved_amount=Decimal('150.00'),
            status='APPROVED',
            notes='Approved',
            tenant_id=test_tenant.id,
        )
        assert ok is True
        assert result['status'] == InsuranceClaimStatus.APPROVED.value

    def test_settle_claim_not_found(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        ok, _result = InsuranceClaimService.settle_claim(
            claim_id=99999, settled_amount=Decimal('50'), tenant_id=test_tenant.id
        )
        assert ok is False

    def test_settle_claim_wrong_tenant(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SUBMITTED')

        ok, _result = InsuranceClaimService.settle_claim(
            claim_id=claim.id, settled_amount=Decimal('50'), tenant_id=99999
        )
        assert ok is False

    def test_settle_claim_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SUBMITTED')

        ok, result = InsuranceClaimService.settle_claim(
            claim_id=claim.id, settled_amount=Decimal('150.00'), tenant_id=test_tenant.id
        )
        assert ok is True
        assert result['status'] == 'SETTLED'

    def test_record_payout_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        dept = _make_department(db, test_tenant.id)
        patient = _make_patient(db, test_tenant.id)
        visit = _make_visit(db, test_tenant.id, patient, dept)
        invoice = _make_invoice(db, test_tenant.id, visit, Decimal('200.00'))
        company = _make_insurance_company(db, test_tenant.id)
        claim = _make_claim(db, test_tenant.id, visit, invoice, company, status='SETTLED')

        ok, result = InsuranceClaimService.record_payout(
            claim_id=claim.id,
            amount=Decimal('150.00'),
            method='WIRE',
            reference='REF-123',
            tenant_id=test_tenant.id,
        )
        assert ok is True
        assert 'id' in result
        assert 'payout_number' in result
        assert result['payout_number'].startswith('PAY-')

    def test_record_payout_exception(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)

        def commit_false(*a, **k):
            return False

        import services.insurance_claim_service as ics_module

        monkeypatch.setattr(ics_module, 'safe_commit', commit_false)

        ok, result = InsuranceClaimService.record_payout(
            claim_id=1,
            amount=Decimal('150.00'),
            method='WIRE',
            reference='REF-123',
            tenant_id=test_tenant.id,
        )
        assert ok is False
        assert 'error' in result
