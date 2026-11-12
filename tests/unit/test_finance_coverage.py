"""HTTP-level coverage for the payment/finance surface.

Exercises the real routes over HTTP as authenticated accountant/manager/admin
users, against the transactional test database, and asserts the contracts the
routes actually implement: status codes, JSON payloads, database rows and
amounts. Modules covered:

  * routes/payment_routes.py   — dashboard, payment processing, refunds,
    insurance claims, pharmacy returns/POS lookup
  * routes/finance.py          — dashboard, GL posting, listings, invoice PDF,
    payment plans, insurance claims, billing summary
  * routes/manager/financial.py — settlements, budget, monthly comparison,
    exchange rates
  * routes/accountant/*.py     — financial reports, accounts, journals, trial
    balance, ledger, period close, refunds, audits, ERP export
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

pytest_plugins = ['tests._isolated_tenant']


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_patient(db, tenant_id: int, suffix: str):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=f'مريض{suffix}',
        last_name='الاختبار',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _mk_visit(
    db,
    tenant_id: int,
    patient_id: int,
    *,
    total: str = '100.00',
    paid: str = '0.00',
    status: str = 'COMPLETED',
    payment_status: str = 'PENDING',
    archive_status: str = 'ACTIVE',
    visit_date: date | None = None,
    department_id: int | None = None,
    doctor_id: int | None = None,
    visit_type: str = 'REGULAR',
    receipt_printed: bool = False,
    financial_locked: bool = False,
):
    from models.visit import Visit

    v = Visit(
        tenant_id=tenant_id,
        patient_id=patient_id,
        visit_type=visit_type,
        status=status,
        payment_status=payment_status,
        total_amount=Decimal(total),
        paid_amount=Decimal(paid),
        visit_date=visit_date or date.today(),
        currency='ILS',
        archive_status=archive_status,
        department_id=department_id,
        doctor_id=doctor_id,
        receipt_printed=receipt_printed,
        financial_locked=financial_locked,
        created_at=datetime.now(),
    )
    db.session.add(v)
    db.session.flush()
    return v


def _mk_invoice(
    db,
    tenant_id: int,
    visit_id: int | None,
    *,
    total: str = '100.00',
    paid: str = '0.00',
    status: str = 'ISSUED',
):
    from models.invoice import Invoice

    inv = Invoice(
        tenant_id=tenant_id,
        visit_id=visit_id,
        status=status,
        total_amount=Decimal(total),
        paid_amount=Decimal(paid),
        currency='ILS',
        invoice_number=f'TST-INV-{datetime.now().timestamp()}-{visit_id or 0}',
    )
    db.session.add(inv)
    db.session.flush()
    return inv


def _mk_invoice_line(db, tenant_id: int, invoice_id: int, visit_id: int | None):
    from models.invoice import InvoiceService

    line = InvoiceService(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        visit_id=visit_id,
        service_code='LAB-001',
        service_name='فحص دم شامل',
        quantity=1,
        unit_price=Decimal('100.00'),
        total_price=Decimal('100.00'),
    )
    db.session.add(line)
    db.session.flush()
    return line


def _mk_payment(
    db,
    tenant_id: int,
    *,
    patient_id: int | None = None,
    visit_id: int | None = None,
    invoice_id: int | None = None,
    amount: str = '100.00',
    method: str = 'CASH',
    status: str = 'CONFIRMED',
    received_by: int | None = None,
):
    from models.payment import Payment

    p = Payment(
        tenant_id=tenant_id,
        patient_id=patient_id,
        visit_id=visit_id,
        invoice_id=invoice_id,
        amount=Decimal(amount),
        method=method,
        status=status,
        received_by=received_by,
        payment_date=datetime.now(),
    )
    db.session.add(p)
    db.session.flush()
    return p


def _login(client, db, tenant, username, role):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role=role)
    login_test_client(client, user, tenant)
    return user


# ---------------------------------------------------------------------------
# /payment index + dashboard
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestPaymentIndexAndDashboard:
    def test_index_redirects_to_dashboard(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_index', 'accountant')
        resp = client.get('/payment/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/payment/dashboard' in resp.headers['Location']

    def test_dashboard_renders_for_accountant(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_dash', 'accountant')
        resp = client.get('/payment/dashboard')
        assert resp.status_code == 200

    def test_dashboard_forbidden_for_doctor(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_dash_doc', 'doctor')
        resp = client.get('/payment/dashboard')
        assert resp.status_code == 403

    def test_dashboard_anonymous_redirects_to_login(self, app, client, test_tenant):
        resp = client.get('/payment/dashboard', follow_redirects=False)
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']


# ---------------------------------------------------------------------------
# /payment/process/<visit_id> GET
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestPaymentProcessGet:
    def test_get_process_form_renders(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_get', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'get')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        db.session.commit()
        resp = client.get(f'/payment/process/{visit.id}')
        assert resp.status_code == 200

    def test_get_process_missing_visit_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_get404', 'accountant')
        resp = client.get('/payment/process/999999')
        assert resp.status_code == 404

    def test_get_process_archived_visit_json_422(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_arch', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'arch')
        visit = _mk_visit(db, test_tenant.id, patient.id, archive_status='ARCHIVED')
        db.session.commit()
        resp = client.get(f'/payment/process/{visit.id}', headers={'Accept': 'application/json'})
        # Archived visits cannot receive ordinary financial mutations/view processing.
        assert resp.status_code == 422
        body = resp.get_json()
        assert body['success'] is False
        assert 'مؤرشفة' in body['message']

    def test_post_archived_visit_json_422(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_archpost', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'archp')
        visit = _mk_visit(db, test_tenant.id, patient.id, archive_status='ARCHIVED')
        db.session.commit()
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '100'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 422
        body = resp.get_json()
        assert body['success'] is False

    def test_post_archived_visit_browser_redirect(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_archbr', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'archb')
        visit = _mk_visit(db, test_tenant.id, patient.id, archive_status='ARCHIVED')
        db.session.commit()
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '100'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# /payment/process/<visit_id> POST
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestPaymentProcessPost:
    def _visit_with_invoice(self, app, db, test_tenant, suffix, total='100.00', visit_kwargs=None):
        patient = _mk_patient(db, test_tenant.id, suffix)
        visit = _mk_visit(db, test_tenant.id, patient.id, total=total, **(visit_kwargs or {}))
        invoice = _mk_invoice(db, test_tenant.id, visit.id, total=total)
        db.session.commit()
        return patient, visit, invoice

    def test_cash_payment_full_and_fifo_allocation(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_full', 'accountant')
        _patient, visit, invoice = self._visit_with_invoice(app, db, test_tenant, 'full')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '100'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True
        assert body['replayed'] is False

        db.session.expire_all()
        from models.payment import Payment

        payments = db.session.execute(select(Payment).filter_by(visit_id=visit.id)).scalars().all()
        assert len(payments) == 1
        assert Decimal(str(payments[0].amount)) == Decimal('100.00')
        assert payments[0].status == 'CONFIRMED'

        v = db.session.get(type(visit), visit.id)
        assert Decimal(str(v.paid_amount)) == Decimal('100.00')
        assert v.payment_status == 'PAID'

        from models.invoice import Invoice

        inv = db.session.get(Invoice, invoice.id)
        assert Decimal(str(inv.paid_amount)) == Decimal('100.00')

    def test_partial_payment_marks_partial(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_part', 'accountant')
        from models.department import Department
        from models.queue_management import QueueSettings
        from models.system_config import SystemConfig

        # Partial payments are opt-in (no debt/partial unless explicitly
        # configured), so this test enables them for the visit's department.
        dept = Department(tenant_id=test_tenant.id, name='Partial Dept', name_ar='قسم الجزئي')
        db.session.add(dept)
        db.session.flush()
        db.session.add(
            QueueSettings(
                tenant_id=test_tenant.id, department_id=dept.id, allow_partial_payment=True
            )
        )
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key='allow_partial_payment_global')
            )
            .scalars()
            .first()
        )
        if not cfg:
            cfg = SystemConfig(
                tenant_id=test_tenant.id,
                config_key='allow_partial_payment_global',
                config_type='boolean',
                config_value='true',
                category='general',
            )
            db.session.add(cfg)
        cfg.set_value(True)
        db.session.flush()

        _patient, visit, _invoice = self._visit_with_invoice(
            app, db, test_tenant, 'part', visit_kwargs={'department_id': dept.id}
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '40'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert Decimal(str(v.paid_amount)) == Decimal('40.00')
        assert v.payment_status == 'PARTIAL'

    def test_overpayment_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_over', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'over')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '150'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_already_fully_paid_visit_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_paid', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(
            app,
            db,
            test_tenant,
            'paid',
            visit_kwargs={'paid': '100.00', 'payment_status': 'PAID'},
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '10'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert 'مدفوعة بالكامل' in resp.get_json()['message']

    def test_wire_payment_method_normalization(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_wire', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'wire')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'check', 'paid_amount': '100'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.payment_method == 'WIRE'

    def test_card_payment_records_last_digits(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_card', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'card')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'card',
                'paid_amount': '100',
                'card_last_digits': '4242',
                'card_holder_name': 'Test Cardholder',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.card_number_last_digits == '4242'
        from models.payment import Payment

        payment = db.session.execute(select(Payment).filter_by(visit_id=visit.id)).scalars().first()
        assert payment.reference == 'CARD-****4242'

    def test_card_payment_missing_fields_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_cardbad', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'cardbad')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'card', 'paid_amount': '100'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_insurance_payment_within_patient_share(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_ins', 'accountant')
        from models.department import Department
        from models.queue_management import QueueSettings
        from models.system_config import SystemConfig

        dept = Department(tenant_id=test_tenant.id, name='Ins Dept', name_ar='قسم التأمين')
        db.session.add(dept)
        db.session.flush()
        db.session.add(
            QueueSettings(
                tenant_id=test_tenant.id, department_id=dept.id, allow_partial_payment=True
            )
        )
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key='allow_partial_payment_global')
            )
            .scalars()
            .first()
        )
        if not cfg:
            cfg = SystemConfig(
                tenant_id=test_tenant.id,
                config_key='allow_partial_payment_global',
                config_type='boolean',
                config_value='true',
                category='general',
            )
            db.session.add(cfg)
        cfg.set_value(True)
        db.session.flush()

        _patient, visit, _invoice = self._visit_with_invoice(
            app, db, test_tenant, 'ins', visit_kwargs={'department_id': dept.id}
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'insurance',
                'paid_amount': '20',
                'insurance_provider': 'Test Insurance Co',
                'insurance_policy_number': 'POL-123456',
                'insurance_coverage': '80',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert Decimal(str(v.insurance_coverage_percentage)) == Decimal('80')
        assert Decimal(str(v.patient_share)) == Decimal('20.00')
        assert Decimal(str(v.insurance_amount)) == Decimal('80.00')

    def test_insurance_payment_above_patient_share_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_ins2', 'accountant')
        from models.department import Department
        from models.queue_management import QueueSettings
        from models.system_config import SystemConfig

        dept = Department(tenant_id=test_tenant.id, name='Ins2 Dept', name_ar='قسم التأمين2')
        db.session.add(dept)
        db.session.flush()
        db.session.add(
            QueueSettings(
                tenant_id=test_tenant.id, department_id=dept.id, allow_partial_payment=True
            )
        )
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key='allow_partial_payment_global')
            )
            .scalars()
            .first()
        )
        if not cfg:
            cfg = SystemConfig(
                tenant_id=test_tenant.id,
                config_key='allow_partial_payment_global',
                config_type='boolean',
                config_value='true',
                category='general',
            )
            db.session.add(cfg)
        cfg.set_value(True)
        db.session.flush()

        _patient, visit, _invoice = self._visit_with_invoice(
            app, db, test_tenant, 'ins2', visit_kwargs={'department_id': dept.id}
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'insurance',
                'paid_amount': '50',
                'insurance_provider': 'Test Insurance Co',
                'insurance_policy_number': 'POL-123456',
                'insurance_coverage': '80',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)[:300]

    def test_insurance_missing_provider_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_ins3', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'ins3')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'insurance', 'paid_amount': '20'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_insurance_with_company_lookup(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_ins4', 'accountant')
        from models.insurance import InsuranceCompany

        company = InsuranceCompany(
            tenant_id=test_tenant.id, name='Acme Health', name_ar='أكمي هيلث', is_active=True
        )
        db.session.add(company)
        db.session.flush()
        company_id = company.id

        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'ins4')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'insurance',
                'paid_amount': '20',
                'insurance_policy_number': 'POL-999',
                'insurance_coverage': '80',
                'insurance_company_id': str(company_id),
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.insurance_company_id == company_id
        assert v.insurance_provider == 'أكمي هيلث'

    def test_force_payment_requires_manager_role(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_force_acct', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'force1')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': '100',
                'is_force_payment': 'on',
                'force_reason': 'ظرف طارئ يمنع الدفع حالياً',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_force_payment_approved_by_manager(self, app, client, db, test_tenant):
        manager = _login(client, db, test_tenant, 'fc_pay_force_mgr', 'manager')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'force2')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': '100',
                'is_force_payment': 'on',
                'force_reason': 'ظرف طارئ يمنع الدفع حالياً',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.is_force_payment is True
        assert v.force_payment_approved_by == manager.id

    def test_force_payment_short_reason_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_force_short', 'manager')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'force3')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': '100',
                'is_force_payment': 'on',
                'force_reason': 'short',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400

    def test_debt_requires_responsibility_acceptance(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_debt1', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'debt1')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'is_debt': 'on', 'paid_amount': '0'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert 'المسؤولية' in resp.get_json()['message']

    def test_debt_with_responsibility_marks_debt(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_debt2', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'debt2')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'is_debt': 'on',
                'accept_responsibility': 'on',
                'debt_reason': 'مريض لا يملك نقداً حالياً',
                'paid_amount': '0',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.payment_status == 'DEBT'

    def test_zero_payment_debt_rejected_without_global_allowance(
        self, app, client, db, test_tenant
    ):
        _login(client, db, test_tenant, 'fc_pay_debt3', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'debt3')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '0'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert 'الدين غير مسموح' in resp.get_json()['message']

    def test_zero_payment_debt_allowed_with_global_and_dept_allowance(
        self, app, client, db, test_tenant
    ):
        _login(client, db, test_tenant, 'fc_pay_debt4', 'accountant')
        from models.department import Department
        from models.queue_management import QueueSettings
        from models.system_config import SystemConfig

        dept = Department(tenant_id=test_tenant.id, name='Debt Dept', name_ar='قسم الدين')
        db.session.add(dept)
        db.session.flush()
        db.session.add(
            QueueSettings(tenant_id=test_tenant.id, department_id=dept.id, allow_debt=True)
        )
        cfg = (
            db.session.execute(select(SystemConfig).filter_by(config_key='allow_debt_global'))
            .scalars()
            .first()
        )
        if not cfg:
            cfg = SystemConfig(
                config_key='allow_debt_global',
                config_type='boolean',
                config_value='true',
                category='general',
            )
            db.session.add(cfg)
        cfg.set_value(True)
        db.session.flush()

        _patient, visit, _invoice = self._visit_with_invoice(
            app,
            db,
            test_tenant,
            'debt4',
            visit_kwargs={'department_id': dept.id},
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '0'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert v.payment_status == 'DEBT'

    def test_partial_payment_blocked_when_dept_disallows(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_part2', 'accountant')
        from models.department import Department
        from models.queue_management import QueueSettings

        dept = Department(tenant_id=test_tenant.id, name='NoPartial Dept', name_ar='قسم الجزئي')
        db.session.add(dept)
        db.session.flush()
        db.session.add(
            QueueSettings(
                tenant_id=test_tenant.id, department_id=dept.id, allow_partial_payment=False
            )
        )
        _patient, visit, _invoice = self._visit_with_invoice(
            app,
            db,
            test_tenant,
            'part2',
            visit_kwargs={'department_id': dept.id},
        )
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '40'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert 'الجزئي غير مسموح' in resp.get_json()['message']

    def test_foreign_currency_without_rate_rejected(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_fx1', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'fx1')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': '10',
                'payment_currency': 'USD',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 400
        assert 'سعر صرف' in resp.get_json()['message']

    def test_foreign_currency_with_manual_rate_converts(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_fx2', 'accountant')
        from services.currency_service import CurrencyConverter

        CurrencyConverter.ensure_manual_rate('USD', 'ILS', sell_rate=Decimal('3.70'))

        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'fx2')
        resp = client.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': '10',
                'payment_currency': 'USD',
            },
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        db.session.expire_all()
        v = db.session.get(type(visit), visit.id)
        assert Decimal(str(v.paid_amount)) == Decimal('37.00')
        from models.payment import Payment

        payment = db.session.execute(select(Payment).filter_by(visit_id=visit.id)).scalars().first()
        assert payment.currency == 'USD'

    def test_replay_same_request_id_records_single_payment(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_replay', 'accountant')
        _patient, visit, _invoice = self._visit_with_invoice(app, db, test_tenant, 'replay')
        data = {
            'payment_method': 'cash',
            'paid_amount': '100',
            'payment_request_id': 'fc-replay-1',
        }
        resp1 = client.post(
            f'/payment/process/{visit.id}',
            data=data,
            headers={'Accept': 'application/json'},
        )
        assert resp1.status_code == 200
        assert resp1.get_json()['replayed'] is False
        resp2 = client.post(
            f'/payment/process/{visit.id}',
            data=data,
            headers={'Accept': 'application/json'},
        )
        assert resp2.status_code == 200
        assert resp2.get_json()['replayed'] is True

        db.session.expire_all()
        from models.payment import Payment

        count = db.session.execute(
            select(func.count()).select_from(Payment).filter_by(visit_id=visit.id)
        ).scalar()
        assert count == 1


# ---------------------------------------------------------------------------
# /payment/history, /payment/methods, /payment/reports
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestPaymentListingRoutes:
    def test_history_renders_with_filters(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_hist', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'hist')
        _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='55.00')
        db.session.commit()
        today = date.today().strftime('%Y-%m-%d')
        resp = client.get(
            f'/payment/history?status=CONFIRMED&payment_method=CASH'
            f'&date_from={today}&date_to={today}'
        )
        assert resp.status_code == 200

    def test_history_bad_date_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_histbad', 'accountant')
        resp = client.get('/payment/history?date_from=not-a-date', follow_redirects=False)
        assert resp.status_code == 302

    def test_methods_page_admin_ok(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_methods', 'admin')
        resp = client.get('/payment/methods')
        assert resp.status_code == 200

    def test_methods_page_manager_ok(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_methods_mgr', 'manager')
        resp = client.get('/payment/methods')
        assert resp.status_code == 200

    def test_methods_page_accountant_forbidden(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_methods_acct', 'accountant')
        resp = client.get('/payment/methods')
        assert resp.status_code == 403

    def test_payment_reports_renders(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pay_reports', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'reports')
        _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='70.00')
        db.session.commit()
        resp = client.get('/payment/reports')
        assert resp.status_code == 200

    def test_payment_reports_anonymous_redirects(self, app, client, test_tenant):
        resp = client.get('/payment/reports', follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Refund workflow — routes/payment_routes.py + routes/accountant/financial.py
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestRefundFlow:
    def _confirmed_payment(self, app, db, test_tenant, suffix, amount='100.00'):
        patient = _mk_patient(db, test_tenant.id, suffix)
        visit = _mk_visit(db, test_tenant.id, patient.id, paid=amount, payment_status='PAID')
        invoice = _mk_invoice(db, test_tenant.id, visit.id, paid=amount)
        payment = _mk_payment(
            db,
            test_tenant.id,
            patient_id=patient.id,
            visit_id=visit.id,
            invoice_id=invoice.id,
            amount=amount,
        )
        db.session.commit()
        return payment

    def test_request_refund_creates_pending_row(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_req', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'req')
        resp = client.post(
            f'/payment/payments/{payment.id}/refund',
            json={'amount': '25.00', 'reason': 'مريض طلب استرداداً'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.refund_request import RefundRequest

        rows = (
            db.session.execute(select(RefundRequest).filter_by(payment_id=payment.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == 'PENDING'
        assert Decimal(str(rows[0].amount)) == Decimal('25.00')

    def test_request_refund_over_payment_creates_nothing(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_over', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'over')
        resp = client.post(
            f'/payment/payments/{payment.id}/refund',
            json={'amount': '250.00', 'reason': 'محاولة تجاوز'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.refund_request import RefundRequest

        count = db.session.execute(
            select(func.count()).select_from(RefundRequest).filter_by(payment_id=payment.id)
        ).scalar()
        assert count == 0

    def test_request_refund_unknown_payment_creates_nothing(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_unknown', 'accountant')
        resp = client.post(
            '/payment/payments/999999/refund',
            json={'amount': '10.00', 'reason': 'لا يوجد'},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_request_refund_form_post_accepted(self, app, client, db, test_tenant):
        """The route reads request.form explicitly; a form post must work."""
        _login(client, db, test_tenant, 'fc_refund_form', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'form')
        resp = client.post(
            f'/payment/payments/{payment.id}/refund',
            data={'amount': '10.00', 'reason': 'استرداد عبر النموذج'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.refund_request import RefundRequest

        count = db.session.execute(
            select(func.count()).select_from(RefundRequest).filter_by(payment_id=payment.id)
        ).scalar()
        assert count == 1

    def test_payment_blueprint_approve_and_execute(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_exec', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'exec')

        client.post(
            f'/payment/payments/{payment.id}/refund',
            json={'amount': '40.00', 'reason': 'استرداد جزئي'},
        )
        from models.refund_request import RefundRequest

        refund = (
            db.session.execute(select(RefundRequest).filter_by(payment_id=payment.id))
            .scalars()
            .first()
        )
        assert refund is not None

        resp = client.post(f'/payment/refund-requests/{refund.id}/approve', follow_redirects=False)
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(RefundRequest, refund.id).status == 'APPROVED'

        resp = client.post(f'/payment/refund-requests/{refund.id}/execute', follow_redirects=False)
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(RefundRequest, refund.id).status == 'EXECUTED'
        from models.payment import Payment, PaymentStatus

        payment_row = db.session.get(Payment, payment.id)
        # Partial refund (40 of 100): original payment keeps the net amount and remains confirmed;
        # a separate REFUNDED payment row records the returned amount.
        assert payment_row.status == PaymentStatus.CONFIRMED
        assert Decimal(str(payment_row.amount)) == Decimal('60.00')
        refunded_rows = (
            db.session.execute(
                select(Payment).filter_by(
                    visit_id=payment.visit_id,
                    status=PaymentStatus.REFUNDED,
                    operation_type='refund',
                )
            )
            .scalars()
            .all()
        )
        assert len(refunded_rows) == 1
        assert Decimal(str(refunded_rows[0].amount)) == Decimal('40.00')

    def test_approve_unknown_refund_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_unk', 'accountant')
        resp = client.post('/payment/refund-requests/999999/approve', follow_redirects=False)
        assert resp.status_code == 302

    def test_accountant_refund_approve_reject_execute(self, app, client, db, test_tenant):
        """The accountant console owns approve/reject; execute is shared."""
        _login(client, db, test_tenant, 'fc_refund_acct', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'acct')

        client.post(
            f'/payment/payments/{payment.id}/refund',
            json={'amount': '30.00', 'reason': 'استرداد للمحاسب'},
        )
        from models.refund_request import RefundRequest

        refund = (
            db.session.execute(select(RefundRequest).filter_by(payment_id=payment.id))
            .scalars()
            .first()
        )

        # approve is gated to admin/manager, so an accountant must be denied
        resp = client.post(f'/accountant/refunds/{refund.id}/approve', follow_redirects=False)
        assert resp.status_code == 403

        # manager approves
        mgr_client = app.test_client()
        _login(mgr_client, db, test_tenant, 'fc_refund_mgr', 'manager')
        resp = mgr_client.post(f'/accountant/refunds/{refund.id}/approve', follow_redirects=False)
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(RefundRequest, refund.id).status == 'APPROVED'

        # accountant executes
        resp = client.post(f'/accountant/refunds/{refund.id}/execute', follow_redirects=False)
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(RefundRequest, refund.id).status == 'EXECUTED'

    def test_accountant_refund_reject(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_refund_rej', 'accountant')
        payment = self._confirmed_payment(app, db, test_tenant, 'rej')
        client.post(
            f'/payment/payments/{payment.id}/refund',
            json={'amount': '10.00', 'reason': 'استرداد للرفض'},
        )
        from models.refund_request import RefundRequest

        refund = (
            db.session.execute(select(RefundRequest).filter_by(payment_id=payment.id))
            .scalars()
            .first()
        )
        mgr_client = app.test_client()
        _login(mgr_client, db, test_tenant, 'fc_refund_rej_mgr', 'manager')
        resp = mgr_client.post(
            f'/accountant/refunds/{refund.id}/reject',
            data={'reason': 'مستندات غير مكتملة'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(RefundRequest, refund.id).status == 'REJECTED'


# ---------------------------------------------------------------------------
# Insurance claims API (payment blueprint)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestInsuranceClaimsApi:
    def _issued_unpaid_invoice(self, app, db, test_tenant, suffix):
        patient = _mk_patient(db, test_tenant.id, suffix)
        visit = _mk_visit(db, test_tenant.id, patient.id)
        invoice = _mk_invoice(db, test_tenant.id, visit.id, total='100.00', paid='0.00')
        db.session.commit()
        return invoice

    def test_generate_claim_requires_invoice_id(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_noid', 'accountant')
        resp = client.post('/payment/api/insurance/claims/generate', json={})
        assert resp.status_code == 400

    def test_generate_claim_unknown_invoice(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_inv404', 'accountant')
        resp = client.post('/payment/api/insurance/claims/generate', json={'invoice_id': 999999})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_generate_claim_from_issued_invoice(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_gen', 'accountant')
        invoice = self._issued_unpaid_invoice(app, db, test_tenant, 'gen')
        resp = client.post(
            '/payment/api/insurance/claims/generate', json={'invoice_id': invoice.id}
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True
        from models.insurance import InsuranceClaim

        claim = (
            db.session.execute(select(InsuranceClaim).filter_by(invoice_id=invoice.id))
            .scalars()
            .first()
        )
        assert claim is not None
        assert claim.status == 'DRAFT'
        assert Decimal(str(claim.total_claim)) == Decimal('100.00')

    def test_generate_claim_refuses_non_issued_invoice(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_draft', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'draft')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        invoice = _mk_invoice(db, test_tenant.id, visit.id, status='DRAFT')
        db.session.commit()
        resp = client.post(
            '/payment/api/insurance/claims/generate', json={'invoice_id': invoice.id}
        )
        assert resp.status_code == 400
        assert 'ISSUED' in resp.get_json()['error']

    def test_generate_claim_refuses_paid_invoice(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_paid', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'paid')
        visit = _mk_visit(db, test_tenant.id, patient.id, paid='100.00', payment_status='PAID')
        invoice = _mk_invoice(db, test_tenant.id, visit.id, paid='100.00')
        db.session.commit()
        resp = client.post(
            '/payment/api/insurance/claims/generate', json={'invoice_id': invoice.id}
        )
        assert resp.status_code == 400

    def test_get_claim_status_roundtrip(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_get', 'accountant')
        from models.insurance import InsuranceClaim

        claim = InsuranceClaim(
            tenant_id=test_tenant.id,
            claim_number=f'CLM-TEST-{datetime.now().timestamp()}',
            status='SUBMITTED',
            total_claim=Decimal('100.00'),
            approved_amount=Decimal('0.00'),
            claim_date=datetime.now(),
        )
        db.session.add(claim)
        db.session.commit()
        resp = client.get(f'/payment/api/insurance/claims/{claim.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['data']['claim_number'] == claim.claim_number
        assert body['data']['status'] == 'SUBMITTED'

    def test_get_claim_not_found(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_404', 'accountant')
        resp = client.get('/payment/api/insurance/claims/999999')
        assert resp.status_code == 404

    def test_adjudicate_requires_status(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_nostatus', 'accountant')
        resp = client.post('/payment/api/insurance/claims/1/adjudicate', json={})
        assert resp.status_code == 400

    def test_adjudicate_claim_approves(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_adj', 'accountant')
        from models.insurance import InsuranceClaim

        claim = InsuranceClaim(
            tenant_id=test_tenant.id,
            claim_number=f'CLM-ADJ-{datetime.now().timestamp()}',
            status='SUBMITTED',
            total_claim=Decimal('100.00'),
            approved_amount=Decimal('0.00'),
            patient_share_amount=Decimal('20.00'),
            insurance_share_amount=Decimal('0.00'),
        )
        db.session.add(claim)
        db.session.commit()
        resp = client.post(
            f'/payment/api/insurance/claims/{claim.id}/adjudicate',
            json={'status': 'APPROVED', 'approved_amount': '80.00', 'notes': 'تمت الموافقة'},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True
        db.session.expire_all()
        assert db.session.get(InsuranceClaim, claim.id).status == 'APPROVED'

    def test_adjudicate_claim_rejects_bad_status(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_claim_badst', 'accountant')
        from models.insurance import InsuranceClaim

        claim = InsuranceClaim(
            tenant_id=test_tenant.id,
            claim_number=f'CLM-BADST-{datetime.now().timestamp()}',
            status='SUBMITTED',
            total_claim=Decimal('100.00'),
        )
        db.session.add(claim)
        db.session.commit()
        resp = client.post(
            f'/payment/api/insurance/claims/{claim.id}/adjudicate',
            json={'status': 'NOT_A_STATUS'},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POS prescription lookup + pharmacy returns
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestPosAndPharmacyReturns:
    def test_pos_lookup_unknown_prescription_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pos_404', 'pharmacist')
        resp = client.get('/payment/api/pos/prescriptions/999999/lookup')
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_pos_lookup_returns_cart(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pos_ok', 'pharmacist')
        from models.medication import Medication, Prescription, PrescriptionItem

        patient = _mk_patient(db, test_tenant.id, 'pos')
        med = Medication(
            tenant_id=test_tenant.id,
            scientific_name='Paracetamol',
            trade_name='بانادول',
            dosage_form='tablet',
            strength='500mg',
            price=Decimal('5.00'),
            stock_quantity=50,
        )
        db.session.add(med)
        db.session.flush()
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            prescription_number=f'RX-{datetime.now().timestamp()}',
            status='active',
        )
        db.session.add(rx)
        db.session.flush()
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=2,
            duration_days=5,
            unit_price=Decimal('5.00'),
            total_price=Decimal('10.00'),
        )
        db.session.add(item)
        db.session.commit()

        resp = client.get(f'/payment/api/pos/prescriptions/{rx.id}/lookup')
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True
        data = body['data']
        assert data['prescription_number'] == rx.prescription_number
        assert len(data['items']) == 1
        assert data['items'][0]['quantity'] == 2
        assert data['items'][0]['unit_price'] == 5.0

    def test_process_pharmacy_return_requires_sale_item_id(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_ret_noid', 'pharmacist')
        resp = client.post('/payment/api/pharmacy/returns', json={})
        assert resp.status_code == 400

    def test_process_pharmacy_return_unknown_sale_item(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_ret_404', 'pharmacist')
        resp = client.post(
            '/payment/api/pharmacy/returns',
            json={'sale_item_id': 999999, 'quantity': 1},
        )
        assert resp.status_code == 400
        assert 'not found' in resp.get_json()['error']

    def test_process_pharmacy_return_restock_success(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_ret_ok', 'pharmacist')
        from models.medication import Medication, PharmacySale, PharmacySaleItem

        patient = _mk_patient(db, test_tenant.id, 'ret')
        med = Medication(
            tenant_id=test_tenant.id,
            scientific_name='Amoxicillin',
            trade_name='أموكسيسيلين',
            dosage_form='capsule',
            strength='250mg',
            price=Decimal('12.00'),
            stock_quantity=30,
        )
        db.session.add(med)
        db.session.flush()
        sale = PharmacySale(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            sale_number=f'SALE-{datetime.now().timestamp()}',
            total_amount=Decimal('24.00'),
            payment_method='cash',
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()
        sale_item = PharmacySaleItem(
            tenant_id=test_tenant.id,
            sale_id=sale.id,
            medication_id=med.id,
            medication_name=med.trade_name,
            quantity=2,
            unit_price=Decimal('12.00'),
            total_price=Decimal('24.00'),
        )
        db.session.add(sale_item)
        db.session.commit()

        resp = client.post(
            '/payment/api/pharmacy/returns',
            json={
                'sale_item_id': sale_item.id,
                'quantity': 1,
                'disposition': 'RESTOCK',
                'reason': 'مريض أعاد الدواء',
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        assert body['success'] is True

        from models.medication import PharmacyReturn

        ret = (
            db.session.execute(select(PharmacyReturn).filter_by(sale_item_id=sale_item.id))
            .scalars()
            .first()
        )
        assert ret is not None
        assert ret.quantity == 1
        assert ret.disposition == 'RESTOCK'

    def test_process_pharmacy_return_bad_disposition(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_ret_disp', 'pharmacist')
        from models.medication import Medication, PharmacySale, PharmacySaleItem

        patient = _mk_patient(db, test_tenant.id, 'retdisp')
        med = Medication(
            tenant_id=test_tenant.id,
            scientific_name='Ibuprofen',
            trade_name='إيبوبروفين',
            dosage_form='tablet',
            strength='400mg',
            price=Decimal('8.00'),
            stock_quantity=40,
        )
        db.session.add(med)
        db.session.flush()
        sale = PharmacySale(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            sale_number=f'SALE-D-{datetime.now().timestamp()}',
            total_amount=Decimal('8.00'),
            payment_method='cash',
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()
        sale_item = PharmacySaleItem(
            tenant_id=test_tenant.id,
            sale_id=sale.id,
            medication_id=med.id,
            medication_name=med.trade_name,
            quantity=1,
            unit_price=Decimal('8.00'),
            total_price=Decimal('8.00'),
        )
        db.session.add(sale_item)
        db.session.commit()

        resp = client.post(
            '/payment/api/pharmacy/returns',
            json={
                'sale_item_id': sale_item.id,
                'quantity': 1,
                'disposition': 'KEEP',
                'reason': 'اختبار',
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# routes/finance.py
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestFinanceCoreRoutes:
    def test_finance_index_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_index', 'accountant')
        resp = client.get('/finance/', follow_redirects=False)
        assert resp.status_code == 302

    def test_finance_dashboard_renders(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_dash', 'accountant')
        _mk_payment(db, test_tenant.id, amount='99.00')
        db.session.commit()
        resp = client.get('/finance/dashboard')
        assert resp.status_code == 200

    def test_finance_dashboard_forbidden_for_doctor(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_doc', 'doctor')
        resp = client.get('/finance/dashboard')
        assert resp.status_code == 403

    def test_post_gl_requires_visit_id(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_gl_noid', 'accountant')
        resp = client.post('/finance/post', json={})
        assert resp.status_code == 400

    def test_post_gl_unknown_visit_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_gl_404', 'accountant')
        resp = client.post('/finance/post', json={'visit_id': 999999})
        assert resp.status_code == 404

    def test_post_gl_success(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_gl_ok', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'gl')
        visit = _mk_visit(
            db,
            test_tenant.id,
            patient.id,
            paid='100.00',
            payment_status='PAID',
            receipt_printed=True,
        )
        db.session.commit()
        resp = client.post('/finance/post', json={'visit_id': visit.id})
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        assert db.session.get(type(visit), visit.id).gl_posted_at is not None

    def test_post_gl_unpaid_visit_422(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_gl_422', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'gl422')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        db.session.commit()
        resp = client.post('/finance/post', json={'visit_id': visit.id})
        assert resp.status_code == 422

    def test_visit_archive_is_reception_only(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_arch_admin', 'admin')
        patient = _mk_patient(db, test_tenant.id, 'archfin')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        db.session.commit()
        resp = client.post(f'/finance/visits/{visit.id}/archive')
        assert resp.status_code == 403

    def test_finance_payments_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_pays', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'fpays')
        _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='10.00')
        db.session.commit()
        resp = client.get('/finance/payments')
        assert resp.status_code == 200
        resp = client.get('/finance/payments?page=2&per_page=10')
        assert resp.status_code == 200

    def test_finance_invoices_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_inv', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'finv')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        _mk_invoice(db, test_tenant.id, visit.id)
        db.session.commit()
        resp = client.get('/finance/invoices')
        assert resp.status_code == 200

    def test_finance_audit_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_fin_audit', 'accountant')
        from models.audit_trail import AuditTrail

        db.session.add(
            AuditTrail(
                tenant_id=test_tenant.id,
                entity_type='payment',
                entity_id=1,
                action='create',
                description='test audit entry',
            )
        )
        db.session.commit()
        resp = client.get('/finance/audit')
        assert resp.status_code == 200

    def test_finance_slow_queries_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_sq', 'accountant')
        resp = client.get('/finance/slow-queries')
        assert resp.status_code == 200

    def test_finance_slow_queries_weekly_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_sqw', 'accountant')
        from models.audit_trail import SlowQueryReport

        report = SlowQueryReport(
            tenant_id=test_tenant.id,
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now(),
        )
        db.session.add(report)
        db.session.commit()
        resp = client.get('/finance/slow-queries/weekly')
        assert resp.status_code == 200

    def test_finance_slow_queries_weekly_detail_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_sqwd', 'accountant')
        from models.audit_trail import SlowQueryReport

        report = SlowQueryReport(
            tenant_id=test_tenant.id,
            period_start=datetime.now() - timedelta(days=7),
            period_end=datetime.now(),
        )
        db.session.add(report)
        db.session.commit()
        resp = client.get(f'/finance/slow-queries/weekly/{report.id}')
        assert resp.status_code == 200

    def test_finance_slow_queries_weekly_detail_missing_redirects(
        self, app, client, db, test_tenant
    ):
        _login(client, db, test_tenant, 'fc_sqwd404', 'accountant')
        resp = client.get('/finance/slow-queries/weekly/999999', follow_redirects=False)
        assert resp.status_code == 302

    def test_finance_slow_queries_capture_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_sqcap', 'accountant')
        resp = client.post('/finance/slow-queries/capture', data={'limit': '10'})
        assert resp.status_code == 302


@pytest.mark.usefixtures('rollback_db')
class TestInvoicePdfAndPaymentPlans:
    def test_invoice_pdf_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pdf', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'pdf')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        invoice = _mk_invoice(db, test_tenant.id, visit.id)
        _mk_invoice_line(db, test_tenant.id, invoice.id, visit.id)
        db.session.commit()
        resp = client.get(f'/finance/invoices/{invoice.id}/pdf')
        assert resp.status_code == 200
        assert resp.mimetype == 'application/pdf'
        assert resp.data.startswith(b'%PDF')
        assert f'invoice-{invoice.id}.pdf' in resp.headers.get('Content-Disposition', '')

    def test_invoice_pdf_legacy_alias_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pdf2', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'pdf2')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        invoice = _mk_invoice(db, test_tenant.id, visit.id)
        db.session.commit()
        assert client.get(f'/finance/invoice/{invoice.id}/pdf').status_code == 200
        assert client.get(f'/finance/invoices/{invoice.id}/download').status_code == 200

    def test_invoice_pdf_missing_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_pdf404', 'accountant')
        resp = client.get('/finance/invoices/999999/pdf')
        assert resp.status_code == 404

    def test_payment_plan_lifecycle(self, app, client, db, isolated_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(db, isolated_tenant, username='fc_plan_iso', role='accountant')
        login_test_client(client, user, isolated_tenant)

        resp = client.post(
            '/finance/payment-plans',
            json={'total_amount': 300, 'installments': 3, 'frequency': 'monthly'},
        )
        assert resp.status_code == 201, resp.get_data(as_text=True)[:300]
        plan = resp.get_json()['data']
        assert plan['installments'] == 3
        assert len(plan['schedule']) == 3
        assert plan['status'] == 'ACTIVE'
        plan_id = plan['id']

        resp = client.get('/finance/payment-plans')
        assert resp.status_code == 200
        plans = resp.get_json()['payment_plans']
        assert any(p['id'] == plan_id for p in plans)

        resp = client.get(f'/finance/payment-plans/{plan_id}')
        assert resp.status_code == 200
        assert resp.get_json()['data']['id'] == plan_id

        for n in (1, 2):
            resp = client.post(f'/finance/payment-plans/{plan_id}/pay', json={'installment': n})
            assert resp.status_code == 200
            assert resp.get_json()['data']['status'] == 'ACTIVE'

        resp = client.post(f'/finance/payment-plans/{plan_id}/pay', json={'installment': 3})
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['status'] == 'COMPLETED'
        assert all(i['status'] == 'PAID' for i in data['schedule'])

    def test_payment_plan_not_found(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_plan_404', 'accountant')
        assert client.get('/finance/payment-plans/999999').status_code == 404
        assert client.post('/finance/payment-plans/999999/pay', json={}).status_code == 404

    def test_payment_plan_bad_installment_count_coerced(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_plan_bad', 'accountant')
        resp = client.post(
            '/finance/payment-plans',
            json={'total_amount': 'abc', 'installments': 'xyz'},
        )
        assert resp.status_code == 201
        data = resp.get_json()['data']
        assert data['total_amount'] == 0.0
        assert data['installments'] == 1

    def test_billing_summary_exact_counts(self, app, client, db, isolated_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(db, isolated_tenant, username='fc_sum_iso', role='accountant')
        login_test_client(client, user, isolated_tenant)

        patient = _mk_patient(db, isolated_tenant.id, 'sum')
        visit = _mk_visit(db, isolated_tenant.id, patient.id)
        _mk_invoice(db, isolated_tenant.id, visit.id, total='80.00', paid='20.00')
        _mk_payment(db, isolated_tenant.id, patient_id=patient.id, amount='20.00')
        _mk_payment(db, isolated_tenant.id, patient_id=patient.id, amount='30.00')
        db.session.commit()

        resp = client.get('/finance/billing-summary')
        assert resp.status_code == 200
        data = resp.get_json()['data']
        assert data['total_invoices'] == 1
        assert data['total_payments'] == 2
        assert data['total_invoiced'] == 80.0
        assert data['total_paid'] == 50.0
        assert data['pending_invoices'] == 1
        assert data['outstanding'] == 30.0

    def test_finance_claims_list_and_filter(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_finclaims', 'accountant')
        from models.insurance import InsuranceClaim

        claim = InsuranceClaim(
            tenant_id=test_tenant.id,
            claim_number=f'CLM-LIST-{datetime.now().timestamp()}',
            status='DRAFT',
            total_claim=Decimal('42.00'),
        )
        db.session.add(claim)
        db.session.commit()

        resp = client.get('/finance/insurance-claims')
        assert resp.status_code == 200
        claims = resp.get_json()['claims']
        assert any(c['id'] == claim.id for c in claims)

        resp = client.get('/finance/insurance-claims?status=DRAFT')
        assert all(c['status'] == 'DRAFT' for c in resp.get_json()['claims'])

        resp = client.get('/finance/insurance-claims?status=SETTLED')
        assert all(c['status'] == 'SETTLED' for c in resp.get_json()['claims'])

    def test_finance_claim_status_endpoint(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_finclaimst', 'accountant')
        from models.insurance import InsuranceClaim

        claim = InsuranceClaim(
            tenant_id=test_tenant.id,
            claim_number=f'CLM-ST-{datetime.now().timestamp()}',
            status='UNDER_REVIEW',
            total_claim=Decimal('42.00'),
        )
        db.session.add(claim)
        db.session.commit()

        resp = client.get(f'/finance/insurance-claims/{claim.id}/status')
        assert resp.status_code == 200
        assert resp.get_json()['data']['status'] == 'UNDER_REVIEW'

        assert client.get('/finance/insurance-claims/999999/status').status_code == 404


# ---------------------------------------------------------------------------
# routes/manager/financial.py
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestManagerFinancial:
    def _doctor_and_visit(self, app, db, test_tenant, suffix):
        from werkzeug.security import generate_password_hash

        from models.user import User

        doctor = User(
            tenant_id=test_tenant.id,
            username=f'fc_doc_{suffix}',
            email=f'fc_doc_{suffix}@test.local',
            password_hash=generate_password_hash('ValidPass123!'),
            full_name=f'طبيب {suffix}',
            role='doctor',
            is_active=True,
        )
        db.session.add(doctor)
        db.session.flush()
        patient = _mk_patient(db, test_tenant.id, f'mgr{suffix}')
        visit = _mk_visit(
            db,
            test_tenant.id,
            patient.id,
            total='100.00',
            paid='100.00',
            payment_status='PAID',
            doctor_id=doctor.id,
            visit_type='FIRST',
        )
        return doctor, visit

    def test_settlements_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_set', 'manager')
        resp = client.get('/manager/settlements')
        assert resp.status_code == 200

    def test_settlements_doctor_mode_with_data(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_set2', 'manager')
        doctor, _visit = self._doctor_and_visit(app, db, test_tenant, 'set2')
        db.session.commit()
        resp = client.get(f'/manager/settlements?mode=doctor&doctor_id={doctor.id}')
        assert resp.status_code == 200

    def test_settlements_month_and_bad_month_params(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_set3', 'manager')
        resp = client.get('/manager/settlements?month=2026-01')
        assert resp.status_code == 200
        resp = client.get('/manager/settlements?month=garbage')
        assert resp.status_code == 200
        resp = client.get('/manager/settlements?month=2026-13')
        assert resp.status_code == 200

    def test_settlements_department_mode(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_set4', 'manager')
        from models.department import Department

        dept = Department(tenant_id=test_tenant.id, name='Settlement Dept', name_ar='قسم التسوية')
        db.session.add(dept)
        db.session.flush()
        patient = _mk_patient(db, test_tenant.id, 'set4')
        _mk_visit(db, test_tenant.id, patient.id, department_id=dept.id, total='80.00')
        db.session.commit()
        resp = client.get(f'/manager/settlements?mode=department&department_id={dept.id}')
        assert resp.status_code == 200

    def test_settlements_export_csv(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_exp', 'manager')
        from models.pricing import DoctorPricing

        doctor, visit = self._doctor_and_visit(app, db, test_tenant, 'exp')
        db.session.add(
            DoctorPricing(
                tenant_id=test_tenant.id,
                doctor_id=doctor.id,
                department_id=visit.department_id,
                consultation_price=Decimal('25.00'),
                follow_up_price=Decimal('15.00'),
                is_active=True,
            )
        )
        db.session.commit()
        resp = client.get(f'/manager/settlements/export?mode=doctor&doctor_id={doctor.id}')
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
        body = resp.data.decode('utf-8')
        assert 'رقم الزيارة' in body
        assert str(visit.id) in body
        # Doctor fee priced from DoctorPricing: 25.00, not the 30% fallback.
        assert '25.00' in body

    def test_settlements_export_fallback_fee_is_30_percent(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_exp2', 'manager')
        doctor, _visit = self._doctor_and_visit(app, db, test_tenant, 'exp2')
        db.session.commit()
        resp = client.get(f'/manager/settlements/export?mode=doctor&doctor_id={doctor.id}')
        assert resp.status_code == 200
        body = resp.data.decode('utf-8')
        # 30% of 100.00 = 30.00
        assert '30.00' in body

    def test_financial_reports_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_rep', 'manager')
        resp = client.get('/manager/financial-reports')
        assert resp.status_code == 200

    def test_financial_reports_forbidden_for_accountant(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_rep2', 'accountant')
        resp = client.get('/manager/financial-reports')
        assert resp.status_code == 403

    def test_budget_get_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_bud', 'manager')
        resp = client.get('/manager/budget')
        assert resp.status_code == 200

    def test_budget_post_creates_budget_row(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_bud2', 'manager')
        today = date.today()
        resp = client.post(
            '/manager/budget',
            data={
                'department_id': '',
                'revenue_target': '5000',
                'visits_target': '10',
                'new_patients_target': '2',
                'expenses_target': '1000',
                'notes': 'ميزانية اختبار',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.budget import Budget

        budget = (
            db.session.execute(
                select(Budget).filter_by(
                    tenant_id=test_tenant.id, year=today.year, month=today.month
                )
            )
            .scalars()
            .first()
        )
        assert budget is not None
        assert Decimal(str(budget.revenue_target)) == Decimal('5000.00')
        assert budget.visits_target == 10
        assert budget.new_patients_target == 2
        assert Decimal(str(budget.expenses_target)) == Decimal('1000.00')

    def test_budget_post_invalid_input_does_not_crash(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_bud3', 'manager')
        resp = client.post(
            '/manager/budget',
            data={
                'department_id': '',
                'revenue_target': 'not-a-number',
                'visits_target': '10',
                'new_patients_target': '2',
                'expenses_target': '1000',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_monthly_comparison_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_cmp', 'manager')
        _mk_payment(db, test_tenant.id, amount='1234.00')
        db.session.commit()
        resp = client.get('/manager/monthly-comparison')
        assert resp.status_code == 200

    def test_exchange_rates_get_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_fx', 'manager')
        resp = client.get('/manager/exchange-rates')
        assert resp.status_code == 200

    def test_exchange_rates_post_creates_manual_rate(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_fx2', 'manager')
        from models.exchange_rate import ExchangeRate

        resp = client.post(
            '/manager/exchange-rates',
            data={
                'from_currency': 'USD',
                'to_currency': 'ILS',
                'sell_rate': '3.60',
                'buy_rate': '',
                'notes': 'سعر اختبار',
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        rate = (
            db.session.execute(
                select(ExchangeRate)
                .filter_by(tenant_id=test_tenant.id, from_currency='USD', to_currency='ILS')
                .order_by(ExchangeRate.id.desc())
            )
            .scalars()
            .first()
        )
        assert rate is not None
        assert rate.is_active is True
        assert rate.source == 'MANUAL'
        assert Decimal(str(rate.sell_rate)) == Decimal('3.60')

    def test_exchange_rates_post_missing_fields(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_fx3', 'manager')
        from models.exchange_rate import ExchangeRate

        resp = client.post(
            '/manager/exchange-rates',
            data={'from_currency': '', 'to_currency': '', 'sell_rate': ''},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        count = db.session.execute(
            select(func.count())
            .select_from(ExchangeRate)
            .filter_by(tenant_id=test_tenant.id, from_currency='')
        ).scalar()
        assert count == 0

    def test_exchange_rates_fetch_api_with_mocked_http(
        self, app, client, db, test_tenant, monkeypatch
    ):
        _login(client, db, test_tenant, 'fc_mgr_fx4', 'manager')

        class _Resp:
            status_code = 200

            def json(self):
                return {'rates': {'EUR': 4.0, 'USD': 3.7, 'GBP': 4.6, 'JOD': 5.2, 'SAR': 1.0}}

        import requests

        monkeypatch.setattr(requests, 'get', lambda *_a, **_k: _Resp())

        resp = client.post(
            '/manager/exchange-rates/fetch-api',
            data={'base_currency': 'ILS'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.exchange_rate import ExchangeRate

        count = db.session.execute(
            select(func.count())
            .select_from(ExchangeRate)
            .filter_by(tenant_id=test_tenant.id, source='API')
        ).scalar()
        assert count >= 1

    def test_exchange_rates_fetch_api_failure_is_tolerated(
        self, app, client, db, test_tenant, monkeypatch
    ):
        _login(client, db, test_tenant, 'fc_mgr_fx5', 'manager')

        import requests

        def _boom(*a, **k):
            raise requests.ConnectionError('no network in tests')

        monkeypatch.setattr(requests, 'get', _boom)

        resp = client.post(
            '/manager/exchange-rates/fetch-api',
            data={'base_currency': 'ILS'},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        from models.exchange_rate import ExchangeRate

        count = db.session.execute(
            select(func.count())
            .select_from(ExchangeRate)
            .filter_by(tenant_id=test_tenant.id, source='API')
        ).scalar()
        assert count == 0

    def test_deactivate_exchange_rate(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_fx6', 'manager')
        from services.currency_service import CurrencyConverter

        rate = CurrencyConverter.ensure_manual_rate('EUR', 'ILS', sell_rate=Decimal('4.10'))
        resp = client.post(f'/manager/exchange-rates/deactivate/{rate.id}', follow_redirects=False)
        assert resp.status_code == 302
        db.session.expire_all()
        from models.exchange_rate import ExchangeRate

        assert db.session.get(ExchangeRate, rate.id).is_active is False

    def test_deactivate_unknown_exchange_rate(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_mgr_fx7', 'manager')
        resp = client.post('/manager/exchange-rates/deactivate/999999', follow_redirects=False)
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# routes/accountant/*.py
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures('rollback_db')
class TestAccountantShell:
    def test_index_redirects_to_dashboard(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_index', 'accountant')
        resp = client.get('/accountant/', follow_redirects=False)
        assert resp.status_code == 302
        assert '/accountant/dashboard' in resp.headers['Location']

    def test_dashboard_renders_for_accountant(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_dash', 'accountant')
        resp = client.get('/accountant/dashboard')
        assert resp.status_code == 200

    def test_dashboard_forbidden_for_doctor(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_doc', 'doctor')
        resp = client.get('/accountant/dashboard')
        assert resp.status_code == 403


@pytest.mark.usefixtures('rollback_db')
class TestAccountantFinancialPages:
    def test_financial_report_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_fr', 'accountant')
        _mk_payment(db, test_tenant.id, amount='60.00', method='CASH')
        _mk_payment(db, test_tenant.id, amount='30.00', method='CARD')
        db.session.commit()
        resp = client.get('/accountant/financial-report')
        assert resp.status_code == 200
        resp = client.get('/accountant/financial-report?start_date=2020-01-01&end_date=2099-12-31')
        assert resp.status_code == 200

    def test_financial_report_bad_dates_redirect(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_frbad', 'accountant')
        resp = client.get(
            '/accountant/financial-report?start_date=not-a-date', follow_redirects=False
        )
        assert resp.status_code == 302

    def test_daily_summary_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_ds', 'accountant')
        _mk_payment(db, test_tenant.id, amount='11.00')
        db.session.commit()
        resp = client.get('/accountant/daily-summary')
        assert resp.status_code == 200

    def test_reports_redirects_to_payment_reports(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_rep', 'accountant')
        resp = client.get('/accountant/reports', follow_redirects=False)
        assert resp.status_code == 302
        assert '/payment/reports' in resp.headers['Location']


@pytest.mark.usefixtures('rollback_db')
class TestAccountantLedger:
    def _seed_coa(self, db, test_tenant):
        from services.gl_service import GLService

        GLService.ensure_coa(test_tenant.id)
        db.session.commit()

    def _account(self, db, test_tenant, code):
        from models import Account

        return (
            db.session.execute(select(Account).filter_by(tenant_id=test_tenant.id, code=code))
            .scalars()
            .first()
        )

    def _balanced_journal(self, db, test_tenant, user_id, amount=Decimal('100.00')):
        from models.gl import GLJournal, GLJournalLine

        cash = self._account(db, test_tenant, '1000')
        revenue = self._account(db, test_tenant, '4000')
        journal = GLJournal(
            tenant_id=test_tenant.id,
            journal_number=f'JE-TEST-{datetime.now().timestamp()}',
            journal_date=datetime.now(),
            description='قيد اختبار',
            status='POSTED',
            source_type='MANUAL',
            source_id=1,
            posted_by=user_id,
        )
        journal.lines = [
            GLJournalLine(
                tenant_id=test_tenant.id,
                account_id=cash.id,
                debit_amount=amount,
                credit_amount=Decimal('0.00'),
                line_description='نقدية',
            ),
            GLJournalLine(
                tenant_id=test_tenant.id,
                account_id=revenue.id,
                debit_amount=Decimal('0.00'),
                credit_amount=amount,
                line_description='إيرادات',
            ),
        ]
        db.session.add(journal)
        db.session.commit()
        return journal

    def test_accounts_page_seeds_chart_of_accounts(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_coa', 'accountant')
        from models import Account

        resp = client.get('/accountant/accounts')
        assert resp.status_code == 200
        count = db.session.execute(
            select(func.count()).select_from(Account).filter_by(tenant_id=test_tenant.id)
        ).scalar()
        assert count >= 10

    def test_journals_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_journals', 'accountant')
        resp = client.get('/accountant/journals')
        assert resp.status_code == 200
        assert client.get('/accountant/journals?page=1').status_code == 200

    def test_trial_balance_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_tb', 'accountant')
        self._seed_coa(db, test_tenant)
        resp = client.get('/accountant/trial-balance')
        assert resp.status_code == 200
        resp = client.get('/accountant/trial-balance?from_date=2020-01-01&to_date=2099-12-31')
        assert resp.status_code == 200

    def test_trial_balance_balanced_journal_marks_equal(self, app, client, db, test_tenant):
        manager = _login(client, db, test_tenant, 'fc_acct_tb2', 'accountant')
        self._seed_coa(db, test_tenant)
        self._balanced_journal(db, test_tenant, manager.id)
        resp = client.get('/accountant/trial-balance?from_date=2020-01-01&to_date=2099-12-31')
        assert resp.status_code == 200
        assert b'text-success' in resp.data
        assert b'100.00' in resp.data

    def test_trial_balance_out_of_balance_marks_unequal(self, app, client, db, test_tenant):
        manager = _login(client, db, test_tenant, 'fc_acct_tb3', 'accountant')
        self._seed_coa(db, test_tenant)
        from models.gl import GLJournal, GLJournalLine

        cash = self._account(db, test_tenant, '1000')
        revenue = self._account(db, test_tenant, '4000')
        journal = GLJournal(
            tenant_id=test_tenant.id,
            journal_number=f'JE-UNBAL-{datetime.now().timestamp()}',
            journal_date=datetime.now(),
            description='قيد غير متوازن',
            status='POSTED',
            source_type='MANUAL',
            source_id=2,
            posted_by=manager.id,
        )
        journal.lines = [
            GLJournalLine(
                tenant_id=test_tenant.id,
                account_id=cash.id,
                debit_amount=Decimal('100.00'),
                credit_amount=Decimal('0.00'),
            ),
            GLJournalLine(
                tenant_id=test_tenant.id,
                account_id=revenue.id,
                debit_amount=Decimal('0.00'),
                credit_amount=Decimal('40.00'),
            ),
        ]
        db.session.add(journal)
        db.session.commit()
        resp = client.get('/accountant/trial-balance?from_date=2020-01-01&to_date=2099-12-31')
        assert resp.status_code == 200
        assert b'text-danger' in resp.data

    def test_account_ledger_200(self, app, client, db, test_tenant):
        manager = _login(client, db, test_tenant, 'fc_acct_ledger', 'accountant')
        self._seed_coa(db, test_tenant)
        self._balanced_journal(db, test_tenant, manager.id)
        cash = self._account(db, test_tenant, '1000')
        resp = client.get(f'/accountant/accounts/{cash.id}?from_date=2020-01-01&to_date=2099-12-31')
        assert resp.status_code == 200
        assert b'100.00' in resp.data

    def test_account_ledger_unknown_account_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_ledger404', 'accountant')
        resp = client.get('/accountant/accounts/999999')
        assert resp.status_code == 404

    def test_close_period_requires_period_id(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_close_noid', 'accountant')
        resp = client.post('/accountant/periods/close', data={}, follow_redirects=False)
        assert resp.status_code == 302

    def test_close_period_success(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_close', 'accountant')
        from models.gl import FinancialPeriod

        period = FinancialPeriod(
            tenant_id=test_tenant.id,
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
            is_closed=False,
        )
        db.session.add(period)
        db.session.commit()
        resp = client.post(
            '/accountant/periods/close',
            data={'period_id': str(period.id)},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        db.session.expire_all()
        assert db.session.get(FinancialPeriod, period.id).is_closed is True

    def test_close_period_already_closed_shows_error(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_close2', 'accountant')
        from models.gl import FinancialPeriod

        period = FinancialPeriod(
            tenant_id=test_tenant.id,
            start_date=date(2019, 1, 1),
            end_date=date(2019, 12, 31),
            is_closed=True,
            closed_at=datetime.now(),
        )
        db.session.add(period)
        db.session.commit()
        resp = client.post(
            '/accountant/periods/close',
            data={'period_id': str(period.id)},
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_close_period_unknown_id(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_close3', 'accountant')
        resp = client.post(
            '/accountant/periods/close',
            data={'period_id': '999999'},
            follow_redirects=False,
        )
        assert resp.status_code == 302


@pytest.mark.usefixtures('rollback_db')
class TestAccountantRefundsAndPatientAccounts:
    def test_refund_requests_list_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_refunds', 'accountant')
        _mk_payment(db, test_tenant.id, amount='10.00')
        db.session.commit()
        resp = client.get('/accountant/refunds')
        assert resp.status_code == 200
        assert client.get('/accountant/refunds?status=PENDING').status_code == 200

    def test_patient_accounts_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_patacc', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'patacc')
        acct_user = _login(app.test_client(), db, test_tenant, 'fc_acct_patacc_u', 'patient')
        from models.patient_account import PatientAccount

        db.session.add(
            PatientAccount(
                tenant_id=test_tenant.id,
                user_id=acct_user.id,
                patient_id=patient.id,
            )
        )
        db.session.commit()
        resp = client.get('/accountant/patient-accounts')
        assert resp.status_code == 200

    def test_open_invoices_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_openinv', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'openinv')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        _mk_invoice(db, test_tenant.id, visit.id, status='ISSUED')
        db.session.commit()
        resp = client.get('/accountant/open-invoices')
        assert resp.status_code == 200

    def test_accountant_payments_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_payments', 'accountant')
        _mk_payment(db, test_tenant.id, amount='77.00')
        db.session.commit()
        resp = client.get('/accountant/payments')
        assert resp.status_code == 200

    def test_payment_documentation_200_and_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_doc', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'doc')
        payment = _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='33.00')
        db.session.commit()
        assert client.get(f'/accountant/payment-documentation/{payment.id}').status_code == 200
        assert client.get('/accountant/payment-documentation/999999').status_code == 404

    def test_receipt_requires_visit(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_receipt', 'accountant')
        payment = _mk_payment(db, test_tenant.id, amount='44.00')
        db.session.commit()
        # No visit linked → redirects to payments list with a flash.
        resp = client.get(f'/accountant/receipt/{payment.id}', follow_redirects=False)
        assert resp.status_code == 302

    def test_receipt_with_visit_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_receipt2', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'receipt')
        visit = _mk_visit(db, test_tenant.id, patient.id, paid='100.00')
        payment = _mk_payment(
            db, test_tenant.id, patient_id=patient.id, visit_id=visit.id, amount='100.00'
        )
        db.session.commit()
        resp = client.get(f'/accountant/receipt/{payment.id}')
        assert resp.status_code == 200

    def test_receipt_unknown_payment_404(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_receipt404', 'accountant')
        resp = client.get('/accountant/receipt/999999')
        assert resp.status_code == 404

    def test_accountant_invoices_pending_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_pending', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'pending')
        _mk_visit(
            db,
            test_tenant.id,
            patient.id,
            total='100.00',
            paid='0.00',
            payment_status='PENDING',
        )
        db.session.commit()
        resp = client.get('/accountant/invoices')
        assert resp.status_code == 200

    def test_accountant_financial_page_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_acct_financial', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'financial')
        visit = _mk_visit(db, test_tenant.id, patient.id, paid='100.00')
        _mk_invoice(db, test_tenant.id, visit.id, paid='100.00')
        _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='100.00')
        db.session.commit()

        resp = client.get('/accountant/financial')
        assert resp.status_code == 200
        resp = client.get(f'/accountant/financial?patient_id={patient.id}')
        assert resp.status_code == 200
        resp = client.get('/accountant/financial?q=مريض')
        assert resp.status_code == 200


@pytest.mark.usefixtures('rollback_db')
class TestAccountantAuditRoutes:
    def test_daily_audit_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_daily', 'accountant')
        resp = client.get('/accountant/audit/daily')
        assert resp.status_code == 200

    def test_daily_audit_with_date_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_daily2', 'accountant')
        resp = client.get('/accountant/audit/daily?date=2026-01-15')
        assert resp.status_code == 200

    def test_daily_audit_bad_date_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_daily3', 'accountant')
        resp = client.get('/accountant/audit/daily?date=garbage', follow_redirects=False)
        assert resp.status_code == 302

    def test_monthly_audit_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_monthly', 'accountant')
        resp = client.get('/accountant/audit/monthly')
        assert resp.status_code == 200
        resp = client.get('/accountant/audit/monthly?year=2026&month=1')
        assert resp.status_code == 200

    def test_debt_tracking_200(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_debts', 'accountant')
        resp = client.get('/accountant/audit/debts')
        assert resp.status_code == 200

    def test_export_daily_json(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_exp1', 'accountant')
        resp = client.get('/accountant/audit/export/daily?format=json')
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True

    def test_export_monthly_json(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_exp2', 'accountant')
        resp = client.get('/accountant/audit/export/monthly?format=json')
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True

    def test_export_debts_json(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_exp3', 'accountant')
        resp = client.get('/accountant/audit/export/debts?format=json')
        assert resp.status_code == 200
        assert resp.get_json().get('success') is True

    def test_export_unknown_type_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_exp4', 'accountant')
        resp = client.get('/accountant/audit/export/bogus', follow_redirects=False)
        assert resp.status_code == 302

    def test_export_unsupported_format_redirects(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_exp5', 'accountant')
        resp = client.get('/accountant/audit/export/daily?format=csv', follow_redirects=False)
        assert resp.status_code == 302

    def test_audit_forbidden_for_doctor(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_audit_doc', 'doctor')
        resp = client.get('/accountant/audit/daily')
        assert resp.status_code == 403


@pytest.mark.usefixtures('rollback_db')
class TestAccountantErpExport:
    def test_erp_export_returns_invoices_and_payments(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_erp', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'erp')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        _mk_invoice(db, test_tenant.id, visit.id)
        _mk_payment(db, test_tenant.id, patient_id=patient.id, amount='55.00')
        db.session.commit()

        resp = client.get('/accountant/api/erp/export')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert len(body['invoices']) >= 1
        assert len(body['payments']) >= 1
        assert 'amount' in body['payments'][0]

    def test_erp_export_limit_param_accepted(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_erp2', 'accountant')
        resp = client.get('/accountant/api/erp/export?limit=50')
        assert resp.status_code == 200
        resp = client.get('/accountant/api/erp/export?limit=10000')
        assert resp.status_code == 200


@pytest.mark.usefixtures('rollback_db')
class TestPaymentLedgerGlue:
    """Cross-module: a confirmed HTTP payment is visible to the GL reports."""

    def test_confirmed_payment_produces_gl_journal(self, app, client, db, test_tenant):
        _login(client, db, test_tenant, 'fc_gl_bridge', 'accountant')
        patient = _mk_patient(db, test_tenant.id, 'bridge')
        visit = _mk_visit(db, test_tenant.id, patient.id)
        db.session.commit()

        resp = client.post(
            f'/payment/process/{visit.id}',
            data={'payment_method': 'cash', 'paid_amount': '100'},
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code == 200

        from models.gl import GLJournal

        journals = (
            db.session.execute(
                select(GLJournal).filter_by(tenant_id=test_tenant.id, source_type='payment')
            )
            .scalars()
            .all()
        )
        assert len(journals) >= 1
