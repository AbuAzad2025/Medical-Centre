import unittest
from app_factory import create_app, db
from services.gatekeeper_service import GatekeeperService
from models.visit import Visit
from models.patient import Patient
from models.user import User


class GatekeeperServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.patient = Patient(first_name='John', last_name='Doe')
        db.session.add(self.patient)
        db.session.commit()
        self.manager = User(username='mgr_user', email='mgr@example.com', full_name='Manager', role='manager', is_admin=False)
        self.manager.set_password('p')
        self.super_admin = User(username='super_admin_user', email='sa@example.com', full_name='Super Admin', role='super_admin', is_admin=True)
        self.super_admin.set_password('p')
        db.session.add_all([self.manager, self.super_admin])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_validate_payment_method(self):
        ok1, msg1 = GatekeeperService.validate_payment_method(None)
        ok2, msg2 = GatekeeperService.validate_payment_method('bitcoin')
        ok3, msg3 = GatekeeperService.validate_payment_method('cash', amount=6000)
        ok4, msg4 = GatekeeperService.validate_payment_method('cash', amount=100)
        ok5, msg5 = GatekeeperService.validate_payment_method('visa')
        self.assertFalse(ok1)
        self.assertFalse(ok2)
        self.assertFalse(ok3)
        self.assertTrue(ok4)
        self.assertTrue(ok5)

    def test_validate_insurance(self):
        x1, m1 = GatekeeperService.validate_insurance('', 'PN', 60)
        x2, m2 = GatekeeperService.validate_insurance('ACME', '', 60)
        x3, m3 = GatekeeperService.validate_insurance('ACME', 'PN', 10)
        x4, m4 = GatekeeperService.validate_insurance('ACME', 'PN', 120)
        x5, m5 = GatekeeperService.validate_insurance('ACME', 'PN123', 70)
        self.assertFalse(x1)
        self.assertFalse(x2)
        self.assertFalse(x3)
        self.assertFalse(x4)
        self.assertTrue(x5)

    def test_validate_card_payment(self):
        a1, mm1 = GatekeeperService.validate_card_payment(None, 'John')
        a2, mm2 = GatekeeperService.validate_card_payment('12', 'John')
        a3, mm3 = GatekeeperService.validate_card_payment('1234', '')
        a4, mm4 = GatekeeperService.validate_card_payment('1234', 'John')
        self.assertFalse(a1)
        self.assertFalse(a2)
        self.assertFalse(a3)
        self.assertTrue(a4)

    def test_check_payment_rules(self):
        v = Visit(patient_id=self.patient.id, total_amount=0, paid_amount=10)
        db.session.add(v)
        db.session.commit()
        ok1, issues1 = GatekeeperService.check_payment_rules(v)
        self.assertFalse(ok1)
        self.assertTrue(any('الإجمالي' in str(i) or 'الإجمالي' in str(i) for i in issues1))
        v2 = Visit(patient_id=self.patient.id, total_amount=100, paid_amount=120)
        db.session.add(v2)
        db.session.commit()
        ok2, issues2 = GatekeeperService.check_payment_rules(v2)
        self.assertFalse(ok2)
        v3 = Visit(patient_id=self.patient.id, total_amount=200, paid_amount=50, payment_method='insurance')
        db.session.add(v3)
        db.session.commit()
        ok3, issues3 = GatekeeperService.check_payment_rules(v3)
        self.assertFalse(ok3)
        v4 = Visit(patient_id=self.patient.id, total_amount=200, paid_amount=200, payment_method='cash')
        db.session.add(v4)
        db.session.commit()
        ok4, issues4 = GatekeeperService.check_payment_rules(v4)
        self.assertTrue(ok4)
        self.assertEqual(len(issues4), 0)

    def test_validate_force_payment_and_stats(self):
        v = Visit(patient_id=self.patient.id, total_amount=100, paid_amount=0, is_force_payment=True, created_by=self.manager.id)
        db.session.add(v)
        db.session.commit()
        # إضافة زيارات لخفض نسبة الدفع القسري تحت 5%
        bulk = []
        for _ in range(21):
            bulk.append(Visit(patient_id=self.patient.id, total_amount=50, paid_amount=0))
        db.session.add_all(bulk)
        db.session.commit()
        ok1, msg1 = GatekeeperService.validate_force_payment(v.id, self.manager.id, reason='سبب مناسب للدفع القسري')
        self.assertFalse(ok1)  # فصل المهام: نفس المنشئ لا يوافق
        ok2, msg2 = GatekeeperService.validate_force_payment(v.id, self.super_admin.id, reason='سبب مناسب للدفع القسري')
        self.assertTrue(ok2)
        stats = GatekeeperService.get_force_payment_statistics(days=30)
        self.assertTrue(isinstance(stats, dict))

    def test_end_to_end_receipts_post_gl_and_archive(self):
        v = Visit(
            patient_id=self.patient.id,
            total_amount=100,
            paid_amount=0,
            is_emergency=True,
            receipt_printed=False
        )
        db.session.add(v)
        db.session.commit()
        ok_enq1, msg_enq1 = GatekeeperService.can_enqueue_visit(v.id, self.manager.id)
        self.assertFalse(ok_enq1)
        self.assertIn('إقرار المسؤولية', msg_enq1)
        ok_ack, msg_ack = GatekeeperService.acknowledge_liability(v.id, self.manager.id)
        self.assertTrue(ok_ack)
        v1 = db.session.get(Visit, v.id)
        self.assertTrue(v1.financial_locked)
        ok_prv, msg_prv = GatekeeperService.create_provisional_receipt(v.id, self.manager.id, amount=50, payment_method='cash', reason='EMERGENCY')
        self.assertTrue(ok_prv)
        v2 = db.session.get(Visit, v.id)
        self.assertEqual(float(v2.paid_amount), 50.0)
        self.assertFalse(v2.receipt_printed)
        ok_cpost1, m_cpost1 = GatekeeperService.can_post_gl(v.id, self.manager.id)
        self.assertFalse(ok_cpost1)
        self.assertIn('مقفلة', m_cpost1)
        ok_sys, msg_sys = GatekeeperService.create_system_receipt(v.id, self.manager.id, amount=100, payment_method='cash')
        self.assertTrue(ok_sys)
        v3 = db.session.get(Visit, v.id)
        self.assertTrue(v3.receipt_printed)
        self.assertEqual(float(v3.paid_amount), 100.0)
        self.assertFalse(v3.financial_locked)
        self.assertIsNotNone(v3.receipt_number)
        ok_cpost2, m_cpost2 = GatekeeperService.can_post_gl(v.id, self.manager.id)
        self.assertTrue(ok_cpost2)
        ok_post, m_post = GatekeeperService.post_gl(v.id, self.manager.id)
        self.assertTrue(ok_post)
        v4 = db.session.get(Visit, v.id)
        self.assertIsNotNone(v4.gl_posted_at)
        ok_carc, m_carc = GatekeeperService.can_archive_visit(v.id, self.manager.id)
        self.assertTrue(ok_carc)
        ok_arc, m_arc = GatekeeperService.archive_visit(v.id, self.manager.id)
        self.assertTrue(ok_arc)
        v5 = db.session.get(Visit, v.id)
        self.assertIsNotNone(v5.archived_at)


if __name__ == '__main__':
    unittest.main()
