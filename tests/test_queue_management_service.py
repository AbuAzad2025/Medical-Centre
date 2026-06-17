import unittest
from app_factory import create_app, db
from services.queue_management_service import QueueManagementService
from models.queue_management import QueueManagement, QueueSettings
from models.patient import Patient
from models.department import Department
from models.user import User
from models.visit import Visit
from datetime import datetime, timedelta, timezone


class QueueManagementServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.dept = Department(name='General', name_ar='عام')
        db.session.add(self.dept)
        self.patient = Patient(first_name='Ali', last_name='Khaled')
        db.session.add(self.patient)
        self.doctor = User(username='doc_queue', email='dq@example.com', full_name='Doctor', role='doctor')
        self.doctor.set_password('p')
        db.session.add(self.doctor)
        db.session.commit()
        self.service = QueueManagementService()

    def tearDown(self):
        db.session.rollback()
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            for t in tables:
                db.session.execute(db.text(f"DELETE FROM {t}"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def test_add_emergency_patient_allows_entry(self):
        ok, msg = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=True,
            payment_status='PENDING'
        )
        self.assertTrue(ok)
        t = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).first()
        self.assertIsNotNone(t)
        self.assertEqual(t.priority_level, 'urgent')

    def test_add_pending_non_emergency_blocks_entry(self):
        ok, msg = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PENDING'
        )
        self.assertFalse(ok)
        cnt = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).count()
        self.assertEqual(cnt, 0)

    def test_add_paid_patient_enters_queue(self):
        ok, msg = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok)
        t = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).first()
        self.assertIsNotNone(t)
        self.assertEqual(t.priority_level, 'normal')

    def test_calculate_estimated_wait_time(self):
        ok1, _ = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok1)
        p2 = Patient(first_name='Omar', last_name='Salem')
        db.session.add(p2)
        db.session.commit()
        ok2, _ = self.service.add_patient_to_queue(
            patient_id=p2.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok2)
        est = self.service._calculate_estimated_wait_time(self.dept.id)
        self.assertEqual(est, 2 * 30)

    def test_call_start_complete_flow(self):
        ok1, _ = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok1)
        # أضف مريضاً آخر ليكون في الانتظار
        p2 = Patient(first_name='Sara', last_name='Nasser')
        db.session.add(p2)
        db.session.commit()
        ok2, _ = self.service.add_patient_to_queue(
            patient_id=p2.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok2)
        # استدعاء المريض التالي
        c_ok, _ = self.service.call_next_patient(self.dept.id, doctor_id=self.doctor.id)
        self.assertTrue(c_ok)
        t_called = QueueManagement.query.filter_by(department_id=self.dept.id, status='called').first()
        self.assertIsNotNone(t_called)
        # بدء العلاج من قبل الطبيب
        s_ok, _ = self.service.start_treatment(t_called.id, started_by=self.doctor.id)
        self.assertTrue(s_ok)
        t_prog = db.session.get(QueueManagement, t_called.id)
        self.assertEqual(t_prog.status, 'in_progress')
        # إنهاء العلاج
        e_ok, _ = self.service.complete_treatment(t_called.id, completed_by=self.doctor.id)
        self.assertTrue(e_ok)
        t_done = db.session.get(QueueManagement, t_called.id)
        self.assertEqual(t_done.status, 'completed')

    def test_start_treatment_requires_called(self):
        ok, _ = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok)
        t = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).first()
        s_ok, msg = self.service.start_treatment(t.id, started_by=self.doctor.id)
        self.assertFalse(s_ok)
        self.assertIn("يجب استدعاء المريض أولاً", msg)

    def test_position_and_approvals_and_cancel_skip(self):
        # تذاكر انتظار
        ok1, _ = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok1)
        p2 = Patient(first_name='Nada', last_name='Hassan')
        db.session.add(p2)
        db.session.commit()
        ok2, _ = self.service.add_patient_to_queue(
            patient_id=p2.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok2)
        # موقع المريض في الطابور
        pos, _ = self.service.get_patient_queue_position(self.patient.id, self.dept.id)
        self.assertIn(pos, (1, 2))
        # موافقة دين طوارئ
        t = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).first()
        apr_ok, _ = self.service.approve_emergency_debt(ticket_id=t.id, approved_by=self.doctor.id)
        self.assertTrue(apr_ok)
        t_ref = db.session.get(QueueManagement, t.id)
        self.assertEqual((t_ref.payment_status or '').lower(), 'waived')
        # موافقة دخول قوي
        fe_ok, _ = self.service.approve_force_entry(ticket_id=t.id, approved_by=self.doctor.id, reason='VIP case')
        self.assertTrue(fe_ok)
        t_ref2 = db.session.get(QueueManagement, t.id)
        self.assertTrue(t_ref2.force_entry)
        self.assertEqual(t_ref2.priority_level, 'high')
        # إلغاء وتخطي
        cn_ok, _ = self.service.cancel_ticket(ticket_id=t.id, reason='Cancelled by patient', cancelled_by=self.doctor.id)
        self.assertTrue(cn_ok)
        sk_ok, _ = self.service.skip_patient(ticket_id=t.id, reason='No show', skipped_by=self.doctor.id)
        self.assertTrue(sk_ok)

    def test_return_to_queue_and_priority_ordering(self):
        p2 = Patient(first_name='Mona', last_name='Sami')
        db.session.add(p2)
        db.session.commit()

        ok_normal, _ = self.service.add_patient_to_queue(
            patient_id=self.patient.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=False,
            payment_status='PAID'
        )
        self.assertTrue(ok_normal)

        ok_urgent, _ = self.service.add_patient_to_queue(
            patient_id=p2.id,
            department_id=self.dept.id,
            doctor_id=self.doctor.id,
            is_emergency=True,
            payment_status='PENDING'
        )
        self.assertTrue(ok_urgent)

        c_ok, _ = self.service.call_next_patient(self.dept.id, doctor_id=self.doctor.id)
        self.assertTrue(c_ok)
        called = QueueManagement.query.filter_by(department_id=self.dept.id, status='called').first()
        self.assertIsNotNone(called)
        self.assertEqual(called.patient_id, p2.id)

        r_ok, _ = self.service.return_to_queue(ticket_id=called.id, reason='Patient not ready', returned_by=self.doctor.id)
        self.assertTrue(r_ok)
        t_back = db.session.get(QueueManagement, called.id)
        self.assertEqual(t_back.status, 'waiting')
        self.assertIsNone(t_back.called_at)

    def test_call_next_prefers_emergency_then_scheduled(self):
        p2 = Patient(first_name='Maha', last_name='Yousef')
        p3 = Patient(first_name='Kareem', last_name='Ahmad')
        db.session.add_all([p2, p3])
        db.session.commit()

        now = datetime.now(timezone.utc)

        v_regular = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', payment_status='PAID', total_amount=0, paid_amount=0, visit_type='REGULAR', created_at=now)
        v_appt = Visit(patient_id=p2.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', payment_status='PAID', total_amount=0, paid_amount=0, visit_type='CONSULTATION', notes='x\n[APPOINTMENT:123]', created_at=now)
        v_em = Visit(patient_id=p3.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', payment_status='PAID', total_amount=0, paid_amount=0, visit_type='EMERGENCY', is_emergency=True, created_at=now)
        db.session.add_all([v_regular, v_appt, v_em])
        db.session.commit()

        ok_r, _ = self.service.add_patient_to_queue(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, visit_id=v_regular.id, is_emergency=False, payment_status='PAID')
        ok_a, _ = self.service.add_patient_to_queue(patient_id=p2.id, department_id=self.dept.id, doctor_id=self.doctor.id, visit_id=v_appt.id, is_emergency=False, payment_status='PAID')
        ok_e, _ = self.service.add_patient_to_queue(patient_id=p3.id, department_id=self.dept.id, doctor_id=self.doctor.id, visit_id=v_em.id, is_emergency=True, payment_status='PENDING')
        self.assertTrue(ok_r and ok_a and ok_e)

        c1, _ = self.service.call_next_patient(self.dept.id, doctor_id=self.doctor.id)
        self.assertTrue(c1)
        first_called = QueueManagement.query.filter_by(department_id=self.dept.id, status='called').order_by(QueueManagement.called_at.asc()).first()
        self.assertEqual(first_called.patient_id, p3.id)

        s_ok, _ = self.service.start_treatment(first_called.id, started_by=self.doctor.id)
        self.assertTrue(s_ok)
        e_ok, _ = self.service.complete_treatment(first_called.id, completed_by=self.doctor.id)
        self.assertTrue(e_ok)

        c2, _ = self.service.call_next_patient(self.dept.id, doctor_id=self.doctor.id)
        self.assertTrue(c2)
        second_called = QueueManagement.query.filter_by(department_id=self.dept.id, status='called').order_by(QueueManagement.called_at.asc()).first()
        self.assertEqual(second_called.patient_id, p2.id)

    def test_wait_metrics_today(self):
        now = datetime.now(timezone.utc)
        ok1, _ = self.service.add_patient_to_queue(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, is_emergency=False, payment_status='PAID')
        self.assertTrue(ok1)
        t = QueueManagement.query.filter_by(patient_id=self.patient.id, department_id=self.dept.id).first()
        t.queued_at = now - timedelta(minutes=30)
        t.called_at = now - timedelta(minutes=10)
        db.session.commit()

        metrics = self.service.get_wait_metrics_today([self.dept.id])
        self.assertEqual(metrics['by_department'][0]['department_id'], self.dept.id)
        self.assertIsInstance(metrics['by_department'][0]['avg_wait_minutes'], int)


if __name__ == '__main__':
    unittest.main()
