import unittest
import uuid
from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.payment import Payment, PaymentMethod, PaymentStatus
from services.access_control_service import AccessControlService
from datetime import datetime, timedelta, timezone


class AccessControlServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        suf = uuid.uuid4().hex[:6]
        self.admin = User(username=f'admin_{suf}', email=f'admin_{suf}@ex.com', full_name='Admin', role='admin', is_admin=True)
        self.manager = User(username=f'manager_{suf}', email=f'manager_{suf}@ex.com', full_name='Manager', role='manager', is_admin=False)
        self.reception = User(username=f'reception_{suf}', email=f'reception_{suf}@ex.com', full_name='Reception', role='reception', is_admin=False)
        self.doctor = User(username=f'doctor_{suf}', email=f'doctor_{suf}@ex.com', full_name='Doctor', role='doctor', is_admin=False)
        self.lab = User(username=f'lab_{suf}', email=f'lab_{suf}@ex.com', full_name='Lab', role='lab', is_admin=False)
        self.radiology = User(username=f'rad_{suf}', email=f'rad_{suf}@ex.com', full_name='Radiology', role='radiology', is_admin=False)
        self.emergency = User(username=f'em_{suf}', email=f'em_{suf}@ex.com', full_name='Emergency', role='emergency', is_admin=False)
        self.admin.set_password('p')
        self.manager.set_password('p')
        self.reception.set_password('p')
        self.doctor.set_password('p')
        self.lab.set_password('p')
        self.radiology.set_password('p')
        self.emergency.set_password('p')
        db.session.add_all([self.admin, self.manager, self.reception, self.doctor, self.lab, self.radiology, self.emergency])
        db.session.commit()
        self.patient = Patient(first_name='Test', last_name='Patient')
        db.session.add(self.patient)
        db.session.commit()
        self.visit = Visit(patient_id=self.patient.id, doctor_id=self.doctor.id, status='OPEN', created_by=self.reception.id)
        db.session.add(self.visit)
        db.session.commit()
        self.visit_lab = Visit(patient_id=self.patient.id, doctor_id=self.doctor.id, status='OPEN', lab_tests_ordered=True)
        db.session.add(self.visit_lab)
        db.session.commit()
        self.payment = Payment(patient_id=self.patient.id, visit_id=self.visit.id, method=PaymentMethod.CASH, amount=50, status=PaymentStatus.CONFIRMED)
        db.session.add(self.payment)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_has_permission_admin_object(self):
        ok = AccessControlService.has_permission(self.admin, 'manage_users')
        self.assertTrue(ok)

    def test_has_permission_doctor_object(self):
        ok1 = AccessControlService.has_permission(self.doctor, 'view_own_visits')
        ok2 = AccessControlService.has_permission(self.doctor, 'manage_users')
        self.assertTrue(ok1)
        self.assertFalse(ok2)

    def test_can_access_visit_admin_and_reception(self):
        a = AccessControlService.can_access_visit(self.admin.id, self.visit.id)
        r = AccessControlService.can_access_visit(self.reception.id, self.visit.id)
        self.assertTrue(a)
        self.assertTrue(r)

    def test_can_access_visit_doctor_own(self):
        d = AccessControlService.can_access_visit(self.doctor.id, self.visit.id)
        self.assertTrue(d)

    def test_can_access_visit_emergency_status(self):
        self.visit.status = 'EMERGENCY'
        db.session.commit()
        e = AccessControlService.can_access_visit(self.emergency.id, self.visit.id)
        self.assertTrue(e)

    def test_can_modify_visit_admin_archived(self):
        self.visit.status = 'ARCHIVED'
        db.session.commit()
        m = AccessControlService.can_modify_visit(self.admin.id, self.visit.id)
        self.assertTrue(m)

    def test_can_modify_visit_reception_time_window(self):
        self.visit.status = 'OPEN'
        self.visit.created_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        db.session.commit()
        self.visit.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
        db.session.commit()
        r2 = AccessControlService.can_modify_visit(self.reception.id, self.visit.id)
        self.assertFalse(r2)

    def test_can_modify_visit_doctor_not_archived(self):
        self.visit.status = 'OPEN'
        db.session.commit()
        d1 = AccessControlService.can_modify_visit(self.doctor.id, self.visit.id)
        self.assertTrue(d1)
        self.visit.status = 'ARCHIVED'
        db.session.commit()
        d2 = AccessControlService.can_modify_visit(self.doctor.id, self.visit.id)
        self.assertFalse(d2)

    def test_get_user_dashboard_route(self):
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.admin.id), '/admin/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.doctor.id), '/doctor/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.reception.id), '/reception/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.lab.id), '/lab/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.radiology.id), '/radiology/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.emergency.id), '/emergency/dashboard')
        self.assertEqual(AccessControlService.get_user_dashboard_route(self.manager.id), '/admin/dashboard')

    def test_get_user_menu_items(self):
        admin_menu = AccessControlService.get_user_menu_items(self.admin.id)
        doctor_menu = AccessControlService.get_user_menu_items(self.doctor.id)
        self.assertTrue(len(admin_menu) > 0)
        self.assertTrue(any(item.get('url') == '/admin/dashboard' for item in admin_menu))
        self.assertTrue(len(doctor_menu) > 0)
        self.assertTrue(any(item.get('url') == '/doctor/dashboard' for item in doctor_menu))

    def test_get_user_accessible_visits_by_role(self):
        # reception sees all
        rec_visits = AccessControlService.get_user_accessible_visits(self.reception.id)
        self.assertTrue(len(rec_visits) >= 2)
        # doctor sees all (per implementation)
        doc_visits = AccessControlService.get_user_accessible_visits(self.doctor.id)
        self.assertTrue(len(doc_visits) >= 2)
        # lab sees visits with lab tests ordered
        lab_visits = AccessControlService.get_user_accessible_visits(self.lab.id)
        self.assertTrue(all(getattr(v, 'lab_tests_ordered', False) for v in lab_visits))

    def test_get_user_accessible_patients_by_role(self):
        # reception sees all patients
        rec_patients = AccessControlService.get_user_accessible_patients(self.reception.id)
        self.assertTrue(len(rec_patients) >= 1)
        # accountant sees patients with payments
        accountant = User(username='acc_test', email='acc_test@example.com', full_name='Accountant', role='accountant', is_admin=False)
        accountant.set_password('p')
        db.session.add(accountant)
        db.session.commit()
        acc_patients = AccessControlService.get_user_accessible_patients(accountant.id)
        self.assertTrue(any(p.id == self.patient.id for p in acc_patients))

if __name__ == '__main__':
    unittest.main()
