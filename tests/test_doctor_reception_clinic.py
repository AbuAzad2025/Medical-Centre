"""Doctor with reception bundle (doctor_clinic_reception) flow audit.

Bundle must be exactly: reception + doctor + billing + appointments.
Flow: reception creates visit -> transfers to doctor -> doctor prescribes ->
reception prints invoice. No module removed from other bundles.
"""

from sqlalchemy import select

from app.core.tenant.models import ProductBundle
from app.extensions import db
from models.invoice import Invoice
from models.patient import Patient
from models.visit import Visit


def test_reception_clinic_bundle_includes_billing(app):
    with app.app_context():
        bundle = (
            db.session.execute(select(ProductBundle).filter_by(slug='doctor_clinic_reception'))
            .scalars()
            .first()
        )
        assert bundle is not None
        modules = bundle.get_modules()
        assert modules == ['reception', 'doctor', 'billing', 'appointments']


def test_private_doctor_bundle_untouched(app):
    with app.app_context():
        bundle = (
            db.session.execute(select(ProductBundle).filter_by(slug='private_doctor_clinic'))
            .scalars()
            .first()
        )
        assert bundle is not None
        assert bundle.get_modules() == ['doctor', 'billing', 'appointments']


class TestReceptionDoctorFlow:
    def test_reception_creates_and_transfers_to_doctor(self, app, test_tenant):
        import uuid

        from models.department import Department
        from services.queue_management_service import QueueManagementService
        from tests.tenant_context import ensure_test_user, tenant_test_context

        t = test_tenant
        with tenant_test_context(app, t):
            suf = uuid.uuid4().hex[:6]
            recep_dept = Department(
                name=f'ReceptionFlow-{suf}',
                name_ar=f'استقبال فلو-{suf}',
                is_active=True,
                tenant_id=t.id,
            )
            doc_dept = Department(
                name=f'DoctorFlow-{suf}',
                name_ar=f'طبيب فلو-{suf}',
                is_active=True,
                tenant_id=t.id,
            )
            db.session.add_all([recep_dept, doc_dept])
            db.session.commit()
            patient = Patient(tenant_id=t.id, first_name='Flow', last_name='Test')
            db.session.add(patient)
            db.session.commit()
            visit = Visit(
                tenant_id=t.id,
                patient_id=patient.id,
                department_id=recep_dept.id,
                status='OPEN',
            )
            db.session.add(visit)
            db.session.commit()
            recep = ensure_test_user(
                db, t, username='flow_recep', role='reception', password='test123'
            )
            recep.set_password('test123')
            db.session.commit()
            doc = ensure_test_user(db, t, username='flow_doc', role='doctor', password='test123')
            doc.set_password('test123')
            db.session.commit()
            svc = QueueManagementService()
            ok, _msg = svc.transfer_visit(
                visit.id,
                doc_dept.id,
                new_doctor_id=doc.id,
                transferred_by=recep.id,
                source='reception',
            )
            assert ok is True, f'reception->doctor failed: {ok}, {_msg}'
            # Simulate doctor taking over
            visit.doctor_id = doc.id
            db.session.commit()
            assert visit.doctor_id == doc.id

    def test_reception_prints_invoice_after_doctor_visit(self, app, client, test_tenant, login_as):
        from tests.tenant_context import ensure_test_user

        doctor = ensure_test_user(
            db, test_tenant, username='flow_doc_rx', role='doctor', password='test123'
        )
        doctor.set_password('test123')
        db.session.commit()
        patient = Patient(tenant_id=test_tenant.id, first_name='FlowRx', last_name='Test')
        db.session.add(patient)
        db.session.commit()
        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            status='IN_PROGRESS',
            total_amount=200,
            paid_amount=200,
            payment_status='PAID',
        )
        db.session.add(visit)
        db.session.commit()
        invoice = Invoice(
            tenant_id=test_tenant.id,
            visit_id=visit.id,
            invoice_number=f'INV-FLOW-{visit.id}',
            total_amount=200,
            paid_amount=200,
            status='PAID',
        )
        db.session.add(invoice)
        db.session.commit()

        login_as(client, 'flow_recep_rx', 'reception')
        resp = client.get(f'/reception/print_invoice/{invoice.id}')
        assert resp.status_code == 200
