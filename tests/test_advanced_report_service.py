import unittest
from datetime import datetime, timedelta, date
from app_factory import create_app, db
from sqlalchemy import and_, func
from services.advanced_report_service import AdvancedReportService
from models.patient import Patient
from models.visit import Visit
from models.payment import Payment, PaymentMethod
from models.invoice import Invoice, InvoiceService
from models.user import User
from models.department import Department
from models.appointment import Appointment


class AdvancedReportServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.department = Department(name='Analytics', name_ar='تحليلات')
        self.doctor = User(username='analytics_doc', email='analytics_doc@example.com', full_name='Analytics Doc', role='doctor')
        self.doctor.set_password('p')
        db.session.add(self.department)
        db.session.add(self.doctor)
        db.session.commit()
        p1 = Patient(first_name='Ali', last_name='A', gender='M', birth_date=date(2010, 1, 1))
        p2 = Patient(first_name='Sara', last_name='B', gender='F', birth_date=date(1988, 6, 1))
        p3 = Patient(first_name='Omar', last_name='C', gender='M', birth_date=date(1955, 3, 15))
        db.session.add_all([p1, p2, p3])
        db.session.commit()
        v1 = Visit(patient_id=p1.id, department_id=self.department.id, doctor_id=self.doctor.id, status='OPEN', visit_type='CONSULTATION')
        v2 = Visit(patient_id=p2.id, department_id=self.department.id, doctor_id=self.doctor.id, status='COMPLETED', visit_type='FOLLOW_UP')
        v3 = Visit(patient_id=p3.id, department_id=self.department.id, doctor_id=self.doctor.id, status='ARCHIVED', visit_type='EMERGENCY')
        db.session.add_all([v1, v2, v3])
        db.session.commit()
        pay1 = Payment(visit_id=v1.id, patient_id=p1.id, method=PaymentMethod.CASH, amount=50)
        pay2 = Payment(visit_id=v2.id, patient_id=p2.id, method=PaymentMethod.INSURANCE, amount=120)
        pay3 = Payment(visit_id=v3.id, patient_id=p3.id, method=PaymentMethod.CARD, amount=70)
        db.session.add_all([pay1, pay2, pay3])
        db.session.commit()
        inv1 = Invoice(visit_id=v1.id, status='PAID', total_amount=50, paid_amount=50)
        inv2 = Invoice(visit_id=v2.id, status='ISSUED', total_amount=120, paid_amount=0)
        db.session.add_all([inv1, inv2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def test_generate_patient_analytics_basic(self):
        res = AdvancedReportService.generate_patient_analytics()
        self.assertTrue(res['success'])
        a = res['analytics']
        self.assertIn('total_patients', a)
        self.assertIn('gender_distribution', a)
        self.assertIn('age_groups', a)
        self.assertIn('status_distribution', a)
        gd = a['gender_distribution']
        self.assertTrue(gd.get('M', 0) >= 1)
        self.assertTrue(gd.get('F', 0) >= 1)

    def test_generate_visit_analytics_basic(self):
        res = AdvancedReportService.generate_visit_analytics()
        self.assertTrue(res['success'])
        a = res['analytics']
        self.assertIn('total_visits', a)
        sd = a['status_distribution']
        vtd = a['visit_type_distribution']
        self.assertTrue(sd.get('OPEN', 0) >= 1)
        self.assertTrue(sd.get('COMPLETED', 0) >= 1)
        self.assertTrue(sd.get('ARCHIVED', 0) >= 1)
        self.assertTrue(vtd.get('CONSULTATION', 0) >= 1)
        self.assertTrue(vtd.get('FOLLOW_UP', 0) >= 1)
        self.assertTrue(vtd.get('EMERGENCY', 0) >= 1)
        self.assertTrue(len(a.get('daily_visits', {})) >= 1)

    def test_generate_financial_analytics_basic(self):
        res = AdvancedReportService.generate_financial_analytics()
        self.assertTrue(res['success'])
        a = res['analytics']
        self.assertIn('payments', a)
        self.assertIn('invoices', a)
        pm = a['payments']['method_distribution']
        self.assertTrue(pm.get('CASH', {}).get('count', 0) >= 1)
        self.assertTrue(pm.get('INSURANCE', {}).get('count', 0) >= 1)
        self.assertTrue(pm.get('CARD', {}).get('count', 0) >= 1)
        self.assertTrue(len(a['payments'].get('daily_revenue', {})) >= 1)

    def test_generate_comprehensive_report_basic(self):
        res = AdvancedReportService.generate_comprehensive_report()
        self.assertTrue(res['success'])
        cr = res['comprehensive_report']
        self.assertIn('patient_analytics', cr)
        self.assertIn('visit_analytics', cr)
        self.assertIn('financial_analytics', cr)
        self.assertIn('doctor_performance', cr)
        self.assertIn('department_analytics', cr)
        self.assertIn('system_usage', cr)

    def test_patient_analytics_age_groups_counts(self):
        dep = Department(name='AgeDept', name_ar='قسم الأعمار')
        db.session.add(dep)
        db.session.commit()
        p4 = Patient(first_name='Child', last_name='D', gender='M', birth_date=date(date.today().year - 8, 1, 1))
        p5 = Patient(first_name='Adult', last_name='E', gender='F', birth_date=date(date.today().year - 25, 1, 1))
        p6 = Patient(first_name='Mid', last_name='F', gender='M', birth_date=date(date.today().year - 45, 1, 1))
        p7 = Patient(first_name='Senior', last_name='G', gender='F', birth_date=date(date.today().year - 60, 1, 1))
        p8 = Patient(first_name='Elder', last_name='H', gender='M', birth_date=date(date.today().year - 70, 1, 1))
        db.session.add_all([p4, p5, p6, p7, p8])
        db.session.commit()
        v4 = Visit(patient_id=p4.id, department_id=dep.id, status='OPEN', visit_type='REGULAR')
        v5 = Visit(patient_id=p5.id, department_id=dep.id, status='OPEN', visit_type='REGULAR')
        v6 = Visit(patient_id=p6.id, department_id=dep.id, status='OPEN', visit_type='REGULAR')
        v7 = Visit(patient_id=p7.id, department_id=dep.id, status='OPEN', visit_type='REGULAR')
        v8 = Visit(patient_id=p8.id, department_id=dep.id, status='OPEN', visit_type='REGULAR')
        db.session.add_all([v4, v5, v6, v7, v8])
        db.session.commit()
        start = datetime.now() - timedelta(days=1)
        end = datetime.now()
        res = AdvancedReportService.generate_patient_analytics(start, end, dep.id)
        self.assertTrue(res['success'])
        age = res['analytics']['age_groups']
        self.assertEqual(age.get('0-18'), 1)
        self.assertEqual(age.get('19-35'), 1)
        self.assertEqual(age.get('36-50'), 1)
        self.assertEqual(age.get('51-65'), 1)
        self.assertEqual(age.get('65+'), 1)
        st = res['analytics']['status_distribution']
        self.assertEqual(st.get('active'), 5)
        self.assertEqual(st.get('inactive'), 0)

    def test_visit_analytics_daily_distribution_precise(self):
        dep = Department(name='VisitDist', name_ar='توزيع الزيارات')
        db.session.add(dep)
        db.session.commit()
        base = datetime.now() - timedelta(days=3)
        d1 = base.date()
        d2 = (base + timedelta(days=1)).date()
        d3 = (base + timedelta(days=2)).date()
        p = Patient(first_name='Daily', last_name='X')
        db.session.add(p)
        db.session.commit()
        v1 = Visit(patient_id=p.id, department_id=dep.id, status='OPEN', visit_type='REGULAR', visit_date=d1)
        v2 = Visit(patient_id=p.id, department_id=dep.id, status='COMPLETED', visit_type='CONSULTATION', visit_date=d2)
        v3 = Visit(patient_id=p.id, department_id=dep.id, status='ARCHIVED', visit_type='FOLLOW_UP', visit_date=d2)
        v4 = Visit(patient_id=p.id, department_id=dep.id, status='OPEN', visit_type='EMERGENCY', visit_date=d3)
        db.session.add_all([v1, v2, v3, v4])
        db.session.commit()
        start = base
        end = base + timedelta(days=2)
        res = AdvancedReportService.generate_visit_analytics(start, end, dep.id)
        self.assertTrue(res['success'])
        a = res['analytics']
        self.assertEqual(a['total_visits'], 4)
        sd = a['status_distribution']
        self.assertEqual(sd.get('OPEN'), 2)
        self.assertEqual(sd.get('COMPLETED'), 1)
        self.assertEqual(sd.get('ARCHIVED'), 1)
        dv = a['daily_visits']
        self.assertEqual(dv.get(d1.strftime('%Y-%m-%d')), 1)
        self.assertEqual(dv.get(d2.strftime('%Y-%m-%d')), 2)
        self.assertEqual(dv.get(d3.strftime('%Y-%m-%d')), 1)

    def test_doctor_performance_metrics_precise(self):
        dep = Department(name='PerfDept', name_ar='قسم أداء')
        doc = User(username='perf_doc', email='perf_doc@example.com', full_name='Perf Doc', role='doctor')
        doc.set_password('p')
        db.session.add(dep)
        db.session.add(doc)
        db.session.commit()
        p = Patient(first_name='Perf', last_name='Y')
        db.session.add(p)
        db.session.commit()
        base = datetime.now() - timedelta(days=2)
        v1 = Visit(patient_id=p.id, department_id=dep.id, doctor_id=doc.id, status='COMPLETED', total_amount=100, paid_amount=80, visit_date=base.date())
        v2 = Visit(patient_id=p.id, department_id=dep.id, doctor_id=doc.id, status='OPEN', total_amount=50, paid_amount=0, visit_date=(base + timedelta(days=1)).date())
        v3 = Visit(patient_id=p.id, department_id=dep.id, doctor_id=doc.id, status='COMPLETED', total_amount=150, paid_amount=150, visit_date=(base + timedelta(days=1)).date())
        db.session.add_all([v1, v2, v3])
        db.session.commit()
        ap1 = Appointment(patient_id=p.id, doctor_id=doc.id, department_id=dep.id, starts_at=base, status='DONE')
        ap2 = Appointment(patient_id=p.id, doctor_id=doc.id, department_id=dep.id, starts_at=base + timedelta(hours=2), status='CANCELLED')
        ap3 = Appointment(patient_id=p.id, doctor_id=doc.id, department_id=dep.id, starts_at=base + timedelta(days=1), status='DONE')
        db.session.add_all([ap1, ap2, ap3])
        db.session.commit()
        start = base
        end = datetime.now()
        res = AdvancedReportService.generate_doctor_performance_analytics(start, end, doc.id)
        self.assertTrue(res['success'])
        a = res['analytics']['doctor_performance']
        self.assertEqual(len(a), 1)
        m = a[0]
        self.assertEqual(m['total_visits'], 3)
        self.assertEqual(m['completed_visits'], 2)
        self.assertEqual(m['total_appointments'], 3)
        self.assertEqual(m['completed_appointments'], 2)
        self.assertEqual(m['cancelled_appointments'], 1)
        self.assertEqual(m['total_revenue'], 300)
        self.assertEqual(m['paid_revenue'], 230)
        self.assertEqual(m['completion_rate'], round(2/3*100, 2))
        self.assertEqual(m['appointment_completion_rate'], round(2/3*100, 2))

    def test_department_analytics_metrics_precise(self):
        dep = Department(name='DeptMetrics', name_ar='مقاييس قسم')
        db.session.add(dep)
        db.session.commit()
        p = Patient(first_name='Dept', last_name='Z')
        db.session.add(p)
        db.session.commit()
        base = datetime.now() - timedelta(days=90)
        v1 = Visit(patient_id=p.id, department_id=dep.id, status='COMPLETED', total_amount=200, paid_amount=200, visit_date=base.date())
        v2 = Visit(patient_id=p.id, department_id=dep.id, status='OPEN', total_amount=100, paid_amount=0, visit_date=base.date())
        db.session.add_all([v1, v2])
        db.session.commit()
        ap1 = Appointment(patient_id=p.id, department_id=dep.id, starts_at=base, status='DONE')
        ap2 = Appointment(patient_id=p.id, department_id=dep.id, starts_at=base + timedelta(hours=1), status='SCHEDULED')
        db.session.add_all([ap1, ap2])
        db.session.commit()
        start = base - timedelta(days=1)
        end = datetime.now()
        res = AdvancedReportService.generate_department_analytics(start, end, dep.id)
        self.assertTrue(res['success'])
        a = res['analytics']['department_analytics']
        self.assertEqual(len(a), 1)
        m = a[0]
        self.assertEqual(m['total_visits'], 2)
        self.assertEqual(m['completed_visits'], 1)
        self.assertEqual(m['total_appointments'], 2)
        self.assertEqual(m['completed_appointments'], 1)
        self.assertEqual(m['total_revenue'], 300)
        self.assertEqual(m['paid_revenue'], 200)
        self.assertEqual(m['completion_rate'], round(1/2*100, 2))
        self.assertEqual(m['appointment_completion_rate'], round(1/2*100, 2))

    def test_financial_analytics_payment_methods_and_daily_sum(self):
        base = datetime.now() - timedelta(days=4)
        d1 = base.replace(hour=10, minute=0, second=0, microsecond=0)
        d2 = (base + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
        d3 = (base + timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0)
        p = Patient(first_name='Fin', last_name='A')
        db.session.add(p)
        db.session.commit()
        pay1 = Payment(patient_id=p.id, method=PaymentMethod.CASH, amount=50, payment_date=d1)
        pay2 = Payment(patient_id=p.id, method=PaymentMethod.INSURANCE, amount=120, payment_date=d2)
        pay3 = Payment(patient_id=p.id, method=PaymentMethod.CARD, amount=70, payment_date=d2)
        pay4 = Payment(patient_id=p.id, method=PaymentMethod.WIRE, amount=30, payment_date=d3)
        db.session.add_all([pay1, pay2, pay3, pay4])
        db.session.commit()
        start = d1.replace(hour=0, minute=0, second=0, microsecond=0)
        end = d3.replace(hour=23, minute=59, second=59, microsecond=0)
        res = AdvancedReportService.generate_financial_analytics(start, end)
        self.assertTrue(res['success'])
        a = res['analytics']['payments']
        self.assertEqual(float(a['total_revenue']), 270.0)
        md = a['method_distribution']
        self.assertEqual(md['CASH']['count'], 1)
        self.assertEqual(md['INSURANCE']['count'], 1)
        self.assertEqual(md['CARD']['count'], 1)
        self.assertEqual(md['WIRE']['count'], 1)
        self.assertEqual(md['CASH']['amount'], 50.0)
        self.assertEqual(md['INSURANCE']['amount'], 120.0)
        self.assertEqual(md['CARD']['amount'], 70.0)
        self.assertEqual(md['WIRE']['amount'], 30.0)
        dr = a['daily_revenue']
        self.assertEqual(float(dr[d1.strftime('%Y-%m-%d')]), 50.0)
        self.assertEqual(float(dr[d2.strftime('%Y-%m-%d')]), 190.0)
        self.assertEqual(float(dr[d3.strftime('%Y-%m-%d')]), 30.0)

    def test_financial_analytics_time_window_and_department_filter(self):
        dep1 = Department(name='FinDept1', name_ar='مالية 1')
        dep2 = Department(name='FinDept2', name_ar='مالية 2')
        db.session.add_all([dep1, dep2])
        db.session.commit()
        p = Patient(first_name='Fin', last_name='B')
        db.session.add(p)
        db.session.commit()
        base = datetime.now() - timedelta(days=3)
        day_in = base.replace(hour=9, minute=0, second=0, microsecond=0)
        day_out = (base - timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
        v1 = Visit(patient_id=p.id, department_id=dep1.id)
        v2 = Visit(patient_id=p.id, department_id=dep2.id)
        db.session.add_all([v1, v2])
        db.session.commit()
        pay_in_dep1 = Payment(patient_id=p.id, visit_id=v1.id, method=PaymentMethod.CASH, amount=80, payment_date=day_in)
        pay_in_dep2 = Payment(patient_id=p.id, visit_id=v2.id, method=PaymentMethod.CARD, amount=40, payment_date=day_in)
        pay_out_window = Payment(patient_id=p.id, visit_id=v1.id, method=PaymentMethod.INSURANCE, amount=200, payment_date=day_out)
        db.session.add_all([pay_in_dep1, pay_in_dep2, pay_out_window])
        db.session.commit()
        start = base - timedelta(days=1)
        end = base + timedelta(days=1)
        res_all = AdvancedReportService.generate_financial_analytics(start, end)
        self.assertTrue(res_all['success'])
        a_all = res_all['analytics']['payments']
        self.assertEqual(float(a_all['total_revenue']), 120.0)
        res_dep1 = AdvancedReportService.generate_financial_analytics(start, end, dep1.id)
        self.assertTrue(res_dep1['success'])
        a_dep1 = res_dep1['analytics']['payments']
        self.assertEqual(float(a_dep1['total_revenue']), 80.0)
        md_dep1 = a_dep1['method_distribution']
        self.assertEqual(md_dep1['CASH']['count'], 1)
        self.assertEqual(md_dep1['CASH']['amount'], 80.0)
        self.assertEqual(md_dep1['CARD']['count'], 0)
        res_dep2 = AdvancedReportService.generate_financial_analytics(start, end, dep2.id)
        self.assertTrue(res_dep2['success'])
        a_dep2 = res_dep2['analytics']['payments']
        self.assertEqual(float(a_dep2['total_revenue']), 40.0)
        md_dep2 = a_dep2['method_distribution']
        self.assertEqual(md_dep2['CARD']['count'], 1)
        self.assertEqual(md_dep2['CARD']['amount'], 40.0)
        res_dep1_invoices = AdvancedReportService.generate_financial_analytics(start, end, dep1.id)
        inv_total_dep1 = res_dep1_invoices['analytics']['invoices']['total_count']
        self.assertIsNotNone(inv_total_dep1)

    def test_comprehensive_report_consistency_across_sections(self):
        dep1 = Department(name='CompDept1', name_ar='شامل 1')
        dep2 = Department(name='CompDept2', name_ar='شامل 2')
        db.session.add_all([dep1, dep2])
        db.session.commit()
        u1 = User(username='comp_doc1', email='comp_doc1@example.com', full_name='Doc1', role='doctor', department_id=dep1.id, is_active=True)
        u1.set_password('p')
        u2 = User(username='comp_doc2', email='comp_doc2@example.com', full_name='Doc2', role='doctor', department_id=dep2.id, is_active=True)
        u2.set_password('p')
        db.session.add_all([u1, u2])
        db.session.commit()
        p = Patient(first_name='Comp', last_name='Z')
        db.session.add(p)
        db.session.commit()
        v1 = Visit(patient_id=p.id, department_id=dep1.id, doctor_id=u1.id, status='COMPLETED', total_amount=150, paid_amount=100)
        v2 = Visit(patient_id=p.id, department_id=dep2.id, doctor_id=u2.id, status='OPEN', total_amount=200, paid_amount=50)
        db.session.add_all([v1, v2])
        db.session.commit()
        base = datetime.now() - timedelta(days=1)
        d1 = base.replace(hour=10, minute=0, second=0, microsecond=0)
        d2 = (base + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        pay1 = Payment(patient_id=p.id, visit_id=v1.id, method=PaymentMethod.CASH, amount=100, payment_date=d1)
        pay2 = Payment(patient_id=p.id, visit_id=v2.id, method=PaymentMethod.CARD, amount=50, payment_date=d2)
        db.session.add_all([pay1, pay2])
        db.session.flush()
        u1.created_at = d1
        u2.created_at = d2
        db.session.add_all([u1, u2])
        inv1 = Invoice(visit_id=v1.id, total_amount=150, paid_amount=100, status='PAID', created_at=d1)
        inv2 = Invoice(visit_id=v2.id, total_amount=200, paid_amount=0, status='ISSUED', created_at=d2)
        db.session.add_all([inv1, inv2])
        db.session.flush()
        il1 = InvoiceService(invoice_id=inv1.id, department_id=dep1.id, visit_id=v1.id, service_code='CONSULT', service_name='Consultation', quantity=1, unit_price=150, total_price=150)
        il2 = InvoiceService(invoice_id=inv2.id, department_id=dep2.id, visit_id=v2.id, service_code='XR', service_name='X-Ray', quantity=1, unit_price=200, total_price=200)
        db.session.add_all([il1, il2])
        db.session.commit()
        start = d1.replace(hour=0, minute=0, second=0, microsecond=0)
        end = d2.replace(hour=23, minute=59, second=59, microsecond=0)
        res = AdvancedReportService.generate_comprehensive_report(start, end)
        self.assertTrue(res['success'])
        cr = res['comprehensive_report']
        fa = cr['financial_analytics']['payments']
        expected_total = db.session.query(func.sum(Payment.amount)).filter(and_(Payment.payment_date >= start, Payment.payment_date <= end)).scalar() or 0
        self.assertEqual(float(fa['total_revenue']), float(expected_total))
        md = fa['method_distribution']
        for method in ['CASH', 'CARD', 'INSURANCE', 'WIRE']:
            exp_count = Payment.query.filter(and_(Payment.payment_date >= start, Payment.payment_date <= end, Payment.method == method)).count()
            exp_amount = db.session.query(func.sum(Payment.amount)).filter(and_(Payment.payment_date >= start, Payment.payment_date <= end, Payment.method == method)).scalar() or 0
            self.assertEqual(md[method]['count'], exp_count)
            self.assertEqual(float(md[method]['amount']), float(exp_amount))
        dr = fa['daily_revenue']
        d1_sum = db.session.query(func.sum(Payment.amount)).filter(and_(Payment.payment_date >= d1.replace(hour=0, minute=0, second=0, microsecond=0), Payment.payment_date < d1.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))).scalar() or 0
        d2_sum = db.session.query(func.sum(Payment.amount)).filter(and_(Payment.payment_date >= d2.replace(hour=0, minute=0, second=0, microsecond=0), Payment.payment_date < d2.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))).scalar() or 0
        self.assertEqual(float(dr[d1.strftime('%Y-%m-%d')]), float(d1_sum))
        self.assertEqual(float(dr[d2.strftime('%Y-%m-%d')]), float(d2_sum))
        da = cr['department_analytics']['department_analytics']
        d1m = next((x for x in da if x.get('department_id') == dep1.id or x.get('department_name') == dep1.name), None)
        d2m = next((x for x in da if x.get('department_id') == dep2.id or x.get('department_name') == dep2.name), None)
        self.assertIsNotNone(d1m)
        self.assertIsNotNone(d2m)
        self.assertEqual(float(d1m['paid_revenue']), 100.0)
        self.assertEqual(float(d2m['paid_revenue']), 50.0)
        invs = cr['financial_analytics']['invoices']
        exp_inv_count = Invoice.query.filter(and_(Invoice.created_at >= start, Invoice.created_at <= end)).count()
        exp_inv_amount = db.session.query(func.sum(Invoice.total_amount)).filter(and_(Invoice.created_at >= start, Invoice.created_at <= end)).scalar() or 0
        self.assertEqual(int(invs['total_count']), exp_inv_count)
        self.assertEqual(float(invs['total_amount']), float(exp_inv_amount))
        su = cr['system_usage']
        self.assertTrue(su.get('total_users', 0) >= 1)


if __name__ == '__main__':
    unittest.main()
