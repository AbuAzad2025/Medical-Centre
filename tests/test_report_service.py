import unittest
from datetime import datetime, timedelta
from app_factory import create_app, db
from services.report_service import ReportService
from models.patient import Patient
from models.user import User
from models.department import Department
from models.visit import Visit
from models.appointment import Appointment
from models.payment import Payment, PaymentMethod, PaymentStatus
from models.invoice import Invoice, InvoiceService


class ReportServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.dept = Department(name='General', name_ar='عام')
        db.session.add(self.dept)
        self.doctor = User(username='rep_doc', email='rep_doc@example.com', full_name='Rep Doctor', role='doctor', department_id=None)
        self.doctor.set_password('p')
        db.session.add(self.doctor)
        self.patient = Patient(first_name='Report', last_name='Patient')
        db.session.add(self.patient)
        db.session.commit()
        # زيارات
        v1 = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', total_amount=200, paid_amount=50, payment_method='CASH')
        v2 = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='COMPLETED', total_amount=300, paid_amount=300, payment_method='insurance', insurance_amount=250, patient_share=50)
        v3 = Visit(patient_id=self.patient.id, department_id=self.dept.id, doctor_id=self.doctor.id, status='OPEN', total_amount=150, paid_amount=0, is_force_payment=True, force_payment_reason='No funds')
        db.session.add_all([v1, v2, v3])
        db.session.flush()
        # مواعيد
        ap = Appointment(patient_id=self.patient.id, doctor_id=self.doctor.id, department_id=self.dept.id, starts_at=datetime.now() + timedelta(hours=2), status='SCHEDULED')
        db.session.add(ap)
        # مدفوعات
        p1 = Payment(patient_id=self.patient.id, visit_id=v1.id, amount=50, method=PaymentMethod.CASH, status=PaymentStatus.CONFIRMED)
        p2 = Payment(patient_id=self.patient.id, visit_id=v2.id, amount=300, method=PaymentMethod.INSURANCE, status=PaymentStatus.CONFIRMED)
        p3 = Payment(patient_id=self.patient.id, visit_id=v1.id, amount=20, method=PaymentMethod.CARD, status=PaymentStatus.CANCELLED)
        db.session.add_all([p1, p2, p3])
        # فاتورة وخط خدمة
        inv = Invoice(visit_id=v2.id, total_amount=300, paid_amount=300, status='PAID')
        db.session.add(inv)
        db.session.flush()
        line = InvoiceService(invoice_id=inv.id, department_id=self.dept.id, visit_id=v2.id, service_code='CONSULT', service_name='Consultation', quantity=1, unit_price=300, total_price=300)
        db.session.add(line)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        # Use TRUNCATE TABLE instead of DROP SCHEMA to avoid enum type recreation issues
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if tables:
            db.session.execute(db.text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        db.session.commit()
        db.engine.dispose()
        db.session.remove()
        self.ctx.pop()

    def test_dashboard_summary(self):
        res = ReportService.get_dashboard_summary()
        self.assertTrue(res['success'])
        self.assertIn('summary', res)
        self.assertIn('patients', res['summary'])

    def test_patient_report(self):
        res = ReportService.get_patient_report(self.patient.id)
        self.assertTrue(res['success'])
        self.assertEqual(res['patient']['id'], self.patient.id)
        self.assertGreaterEqual(len(res['visits']), 1)

    def test_department_report(self):
        res = ReportService.get_department_report(self.dept.id)
        self.assertTrue(res['success'])
        self.assertEqual(res['department']['id'], self.dept.id)
        self.assertIn('statistics', res)

    def test_financial_report(self):
        res = ReportService.get_financial_report()
        self.assertTrue(res['success'])
        self.assertIn('summary', res)
        self.assertGreater(res['summary']['total_revenue'], 0)

    def test_financial_report_breakdown_totals(self):
        res = ReportService.get_financial_report()
        self.assertTrue(res['success'])
        s = res['summary']
        methods = s['payment_methods']
        # في مجموعة الإعداد لدينا: CASH=50, INSURANCE=300, CARD=20 (ملغي لكنه محسوب ضمن الإجمالي)
        self.assertEqual(float(s['total_revenue']), 370.0)
        self.assertEqual(float(s['cash_revenue']), 50.0)
        self.assertEqual(float(s['insurance_revenue']), 300.0)
        self.assertEqual(float(s['card_revenue']), 20.0)
        # تحقق من تجميع الطرق
        self.assertEqual(float(methods.get('CASH', 0)), 50.0)
        self.assertEqual(float(methods.get('INSURANCE', 0)), 300.0)
        self.assertEqual(float(methods.get('CARD', 0)), 20.0)
        # تحقق من وجود تجميع يومي
        self.assertTrue(len(s['daily_revenue']) >= 1)

    def test_patient_report_details(self):
        res = ReportService.get_patient_report(self.patient.id)
        self.assertTrue(res['success'])
        self.assertGreaterEqual(len(res['appointments']), 1)
        self.assertGreaterEqual(len(res['payments']), 1)
        self.assertIn('period', res)
        self.assertIn('start_date', res['period'])
        self.assertIn('end_date', res['period'])

    def test_doctor_performance_report(self):
        res = ReportService.get_doctor_performance_report(self.doctor.id)
        self.assertTrue(res['success'])
        self.assertIn('statistics', res)
        st = res['statistics']
        self.assertTrue(st['total_visits'] >= 1)
        self.assertTrue(st['total_appointments'] >= 1)

    def test_export_report_json_csv(self):
        data = [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
        j = ReportService.export_report('any', data, format='json')
        self.assertTrue(j['success'])
        c = ReportService.export_report('any', data, format='csv')
        self.assertTrue(c['success'])
        self.assertIn('a,b', c['data'])

    def test_daily_audit_report(self):
        res = ReportService.get_daily_audit_report()
        self.assertTrue(res['success'])
        self.assertIn('summary', res)
        self.assertGreaterEqual(res['summary']['total_visits'], 1)

    def test_monthly_audit_report(self):
        now = datetime.now()
        res = ReportService.get_monthly_audit_report(year=now.year, month=now.month)
        self.assertTrue(res['success'])
        self.assertIn('summary', res)

    def test_debt_tracking_report(self):
        res = ReportService.get_debt_tracking_report()
        self.assertTrue(res['success'])
        self.assertIn('summary', res)


if __name__ == '__main__':
    unittest.main()
