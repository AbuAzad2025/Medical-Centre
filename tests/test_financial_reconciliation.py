"""Tests for P3-003: Invoice paid/balance projection and reconciliation."""

import pytest
from sqlalchemy import select

from app.extensions import db
from app_factory import db as _db
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.financial_service import FinancialService
from tests.tenant_context import login_test_client


@pytest.fixture(scope='function')
def recon_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Recon',
        last_name='Patient',
        phone='0500000060',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def recon_accountant(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='recon_accountant')).scalars().first()
    if not u:
        u = User(
            username='recon_accountant',
            email='recon_acc@example.com',
            full_name='Accountant Recon',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def recon_visit(app, test_tenant, recon_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=recon_patient.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def recon_invoice(app, test_tenant, recon_visit):
    inv = Invoice(
        tenant_id=test_tenant.id,
        visit_id=recon_visit.id,
        total_amount=100,
        paid_amount=0,
        status='ISSUED',
    )
    _db.session.add(inv)
    _db.session.flush()
    line = InvoiceService(
        tenant_id=test_tenant.id,
        invoice_id=inv.id,
        visit_id=recon_visit.id,
        service_code='SRV',
        service_name='Service',
        quantity=1,
        unit_price=100,
        total_price=100,
    )
    _db.session.add(line)
    _db.session.commit()
    return inv


class TestInvoiceBalanceDue:
    def test_balance_due_property(self, recon_invoice):
        assert recon_invoice.balance_due == 100.0
        recon_invoice.paid_amount = 30
        assert recon_invoice.balance_due == 70.0

    def test_balance_due_never_negative(self, recon_invoice):
        recon_invoice.paid_amount = 150
        assert recon_invoice.balance_due == 0.0

    def test_to_dict_includes_balance_due(self, recon_invoice):
        data = recon_invoice.to_dict()
        assert 'balance_due' in data
        assert data['balance_due'] == 100.0


class TestFinancialServiceReconcileVisitPayments:
    def test_reconcile_allocates_payment(
        self, recon_visit, recon_invoice, recon_accountant, test_tenant
    ):
        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=60,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 60
        assert recon_invoice.status == 'PARTIAL'
        assert recon_invoice.balance_due == 40

    def test_reconcile_resets_and_reallocates(
        self, recon_visit, recon_invoice, recon_accountant, test_tenant
    ):
        # Simulate an out-of-sync paid_amount
        recon_invoice.paid_amount = 999
        _db.session.commit()

        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=100,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 100
        assert recon_invoice.status == 'PAID'
        assert recon_invoice.balance_due == 0

    def test_reconcile_multiple_invoices_fifo(
        self, recon_visit, recon_invoice, recon_accountant, test_tenant
    ):
        inv2 = Invoice(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            total_amount=50,
            paid_amount=0,
            status='ISSUED',
        )
        _db.session.add(inv2)
        _db.session.commit()

        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=120,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        _db.session.refresh(inv2)
        assert float(recon_invoice.paid_amount) == 100
        assert recon_invoice.status == 'PAID'
        assert float(inv2.paid_amount) == 20
        assert inv2.status == 'PARTIAL'

    def test_reconcile_ignores_non_confirmed_payments(
        self, recon_visit, recon_invoice, recon_accountant, test_tenant
    ):
        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=100,
            method='CASH',
            status='PENDING',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 0
        assert recon_invoice.status == 'ISSUED'


# ===========================================================================
# Insurance Claim Tests
# ===========================================================================


class TestInsuranceClaim:
    """Tests for insurance claim generation, adjudication, and tenant isolation."""

    def _create_issued_invoice(self, app, test_tenant, recon_visit):
        """Helper: create an ISSUED invoice and return it."""
        from models.invoice import Invoice

        inv = Invoice(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            total_amount=200.0,
            paid_amount=0,
            status='ISSUED',
        )
        _db.session.add(inv)
        _db.session.commit()
        return inv

    def test_create_claim_from_invoice(self, app, test_tenant, recon_visit):
        """Successfully generate an insurance claim from an ISSUED invoice."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert result['ok'] is True, f"create_claim failed: {result}"
        assert 'claim_id' in result
        assert 'claim_number' in result

        from models.insurance import InsuranceClaim

        claim = (
            _db.session.execute(
                select(InsuranceClaim).filter(InsuranceClaim.id == result['claim_id'])
            )
            .scalars()
            .first()
        )
        assert claim is not None
        assert claim.status == 'DRAFT'
        assert claim.total_claim == 200.0
        assert claim.invoice_id == inv.id
        assert claim.visit_id == recon_visit.id
        assert claim.tenant_id == test_tenant.id

    def test_create_claim_rejects_non_issued_invoice(self, app, test_tenant, recon_visit):
        """Claim creation should fail for invoices that are not ISSUED."""
        from models.invoice import Invoice

        inv = Invoice(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            total_amount=100.0,
            paid_amount=0,
            status='DRAFT',
        )
        _db.session.add(inv)
        _db.session.commit()

        result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )

        assert result['ok'] is False
        assert 'ISSUED' in result['error']

    def test_create_claim_rejects_missing_invoice(self, app, test_tenant):
        """Claim creation should fail for a non-existent invoice."""
        result = FinancialService.create_insurance_claim(
            invoice_id=999_999,
            tenant_id=test_tenant.id,
            user_id=1,
        )

        assert result['ok'] is False
        assert 'not found' in result['error']

    def test_claim_status_transitions(self, app, test_tenant, recon_visit):
        """Claim should transition through SUBMITTED → UNDER_REVIEW → APPROVED."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        # Submit the claim
        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='SUBMITTED',
            tenant_id=test_tenant.id,
        )
        assert result['ok'] is True

        from models.insurance import InsuranceClaim

        claim = _db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'SUBMITTED'

        # Adjudicate as approved
        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='APPROVED',
            approved_amount=150.0,
            notes='Approved per policy',
            tenant_id=test_tenant.id,
        )
        if not result['ok']:
            print(f"DEBUG update_claim_status error: {result}")
        assert result['ok'] is True

        _db.session.refresh(claim)
        assert claim.status == 'APPROVED'
        assert claim.approved_amount == 150.0
        assert claim.insurance_share_amount == 150.0
        assert claim.patient_share_amount == 50.0

    def test_claim_partial_approval(self, app, test_tenant, recon_visit):
        """PARTIALLY_APPROVED should split insurance and patient shares."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='PARTIALLY_APPROVED',
            approved_amount=100.0,
            notes='Partial coverage',
            tenant_id=test_tenant.id,
        )
        assert result['ok'] is True

        from models.insurance import InsuranceClaim

        claim = _db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'PARTIALLY_APPROVED'
        assert claim.insurance_share_amount == 100.0
        assert claim.patient_share_amount == 100.0

    def test_claim_rejection(self, app, test_tenant, recon_visit):
        """REJECTED should set insurance share to 0 and patient share to total."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='REJECTED',
            approved_amount=0,
            notes='Claim denied - pre-existing condition',
            tenant_id=test_tenant.id,
        )
        assert result['ok'] is True

        from models.insurance import InsuranceClaim

        claim = _db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'REJECTED'
        assert claim.insurance_share_amount == 0
        assert claim.patient_share_amount == 200.0

    def test_claim_settlement(self, app, test_tenant, recon_visit):
        """SETTLED should mark the claim as settled with the settled amount."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        # First approve
        FinancialService.update_claim_status(
            claim_id=claim_id,
            status='APPROVED',
            approved_amount=180.0,
            tenant_id=test_tenant.id,
        )

        # Then settle
        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='SETTLED',
            approved_amount=180.0,
            tenant_id=test_tenant.id,
        )
        assert result['ok'] is True

        from models.insurance import InsuranceClaim

        claim = _db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'SETTLED'
        assert claim.approved_amount == 180.0
        assert claim.insurance_share_amount == 180.0

    def test_claim_tenant_isolation(self, app, test_tenant, recon_visit):
        """Claims should be isolated by tenant - one tenant cannot access another's claim."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        # Try to update with a different tenant_id
        result = FinancialService.update_claim_status(
            claim_id=claim_id,
            status='APPROVED',
            approved_amount=150.0,
            tenant_id=999_999,  # Wrong tenant
        )
        assert result['ok'] is False
        assert 'Tenant mismatch' in result['error']

    def test_claim_get_endpoint(self, app, test_tenant, recon_visit, recon_accountant):
        """GET /payment/api/insurance/claims/<id> should return claim details."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        with app.test_client() as client:
            login_test_client(client, recon_accountant, test_tenant, password='test123')

            resp = client.get(f'/payment/api/insurance/claims/{claim_id}')
            data = resp.get_json()
            if resp.status_code != 200:
                print(f"DEBUG get_claim: status={resp.status_code}, data={data}")

            assert resp.status_code == 200
            assert data['success'] is True
            assert data['data']['id'] == claim_id
            assert data['data']['status'] == 'DRAFT'
            assert data['data']['total_claim'] == 200.0

    def test_claim_adjudicate_endpoint(self, app, test_tenant, recon_visit, recon_accountant):
        """POST /payment/api/insurance/claims/<id>/adjudicate should update claim status."""
        inv = self._create_issued_invoice(app, test_tenant, recon_visit)

        create_result = FinancialService.create_insurance_claim(
            invoice_id=inv.id,
            tenant_id=test_tenant.id,
            user_id=1,
        )
        assert create_result['ok'] is True
        claim_id = create_result['claim_id']

        with app.test_client() as client:
            login_test_client(client, recon_accountant, test_tenant, password='test123')

            resp = client.post(
                f'/payment/api/insurance/claims/{claim_id}/adjudicate',
                json={
                    'status': 'APPROVED',
                    'approved_amount': 150.0,
                    'notes': 'Approved per policy',
                },
            )
            data = resp.get_json()

            assert resp.status_code == 200
            assert data['success'] is True

            from models.insurance import InsuranceClaim

            claim = _db.session.get(InsuranceClaim, claim_id)
            assert claim.status == 'APPROVED'
            assert claim.approved_amount == 150.0
