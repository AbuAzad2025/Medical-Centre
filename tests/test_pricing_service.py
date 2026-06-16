import unittest
from app_factory import create_app, db
from services.pricing_service import PricingService
from models.pricing import ServicePrice, DoctorPricing
from models.user import User
from models.department import Department


class PricingServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        sp = ServicePrice(
            service_name='Consultation',
            service_type='consultation',
            base_price=50,
            cash_price=60,
            insurance_price=30,
            vip_price=100,
            is_active=True
        )
        db.session.add(sp)
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

    def test_get_service_price_variants(self):
        c = PricingService.get_service_price('Consultation', 'consultation', payment_method='cash')
        i = PricingService.get_service_price('Consultation', 'consultation', payment_method='insurance')
        v = PricingService.get_service_price('Consultation', 'consultation', payment_method='vip')
        b = PricingService.get_service_price('Consultation', 'consultation', payment_method='wire')
        self.assertEqual(float(c), 60.0)
        self.assertEqual(float(i), 30.0)
        self.assertEqual(float(v), 100.0)
        self.assertEqual(float(b), 50.0)

    def test_get_doctor_price_direct_and_fallback(self):
        dept = Department(name='General Clinic', name_ar='العيادة العامة', is_active=True)
        db.session.add(dept)
        db.session.commit()
        doc = User(username='doc_price', email='doc_price@example.com', full_name='Doc Price', role='doctor', department_id=dept.id, is_active=True)
        doc.set_password('p')
        db.session.add(doc)
        db.session.commit()
        dp = DoctorPricing(doctor_id=doc.id, department_id=dept.id, consultation_price=75, vip_price=150, is_active=True)
        db.session.add(dp)
        db.session.commit()
        price1 = PricingService.get_doctor_price(doc.id, visit_type='consultation', payment_method='cash')
        price2 = PricingService.get_doctor_price(doc.id, visit_type='consultation', payment_method='vip')
        self.assertEqual(float(price1), 75.0)
        self.assertEqual(float(price2), 150.0)
        # when no doctor-specific pricing exists, expect 0.0 (model does not allow department-only row)
        doc2 = User(username='doc_fallback', email='doc_fallback@example.com', full_name='Doc Fallback', role='doctor', department_id=dept.id, is_active=True)
        doc2.set_password('p')
        db.session.add(doc2)
        db.session.commit()
        price_fb = PricingService.get_doctor_price(doc2.id, visit_type='consultation', payment_method='cash')
        price_fb_vip = PricingService.get_doctor_price(doc2.id, visit_type='consultation', payment_method='vip')
        self.assertEqual(float(price_fb), 0.0)
        self.assertEqual(float(price_fb_vip), 0.0)

    def test_create_service_price_and_summary(self):
        data = {
            'service_name': 'X-Ray Scan',
            'service_type': 'radiology_scan',
            'service_code': 'XR001',
            'base_price': 80.0,
            'insurance_price': 60.0,
            'cash_price': 80.0,
            'vip_price': 150.0,
            'is_active': True,
            'requires_doctor': False,
            'requires_department': True
        }
        result = PricingService.create_service_price(data)
        self.assertTrue(result.get('success'))
        summary = PricingService.get_pricing_summary()
        self.assertTrue(summary.get('success'))
        self.assertTrue(summary['summary']['total_services'] >= 2)

    def test_create_doctor_pricing(self):
        dept = Department(name='Cardiology', name_ar='القلبية', is_active=True)
        db.session.add(dept)
        db.session.commit()
        doc = User(username='doc_cardio', email='doc_cardio@example.com', full_name='Doc Cardio', role='doctor', department_id=dept.id, is_active=True)
        doc.set_password('p')
        db.session.add(doc)
        db.session.commit()
        res = PricingService.create_doctor_pricing(doc.id, {
            'department_id': dept.id,
            'consultation_price': 120.0,
            'vip_price': 220.0,
            'is_active': True
        })
        self.assertTrue(res.get('success'))

    def test_seed_departments(self):
        out = PricingService.seed_departments()
        self.assertTrue(out.get('success'))
        self.assertTrue(out.get('created') >= 0)

    def test_purge_users_keep_policy(self):
        dept = Department(name='General Clinic', name_ar='العيادة العامة', is_active=True)
        db.session.add(dept)
        db.session.commit()
        su = User(username='su_main', email='su_main@example.com', full_name='Super Admin', role='super_admin', is_admin=True, is_active=True)
        su.set_password('p')
        mg = User(username='mg_main', email='mg_main@example.com', full_name='Manager', role='manager', is_admin=True, is_active=True)
        mg.set_password('p')
        rc = User(username='rc_main', email='rc_main@example.com', full_name='Reception', role='reception', is_admin=False, is_active=True)
        rc.set_password('p')
        d1 = User(username='doc_main', email='doc_main@example.com', full_name='Doc Main', role='doctor', department_id=dept.id, is_active=True)
        d1.set_password('p')
        d2 = User(username='doc_extra', email='doc_extra@example.com', full_name='Doc Extra', role='doctor', department_id=dept.id, is_active=True)
        d2.set_password('p')
        db.session.add_all([su, mg, rc, d1, d2])
        db.session.commit()
        result = PricingService.purge_users_keep_policy()
        self.assertTrue(result.get('success'))
        self.assertTrue(result.get('deleted', 0) >= 1)
        self.assertTrue(result.get('kept', 0) >= 3)
        self.assertIsNotNone(User.query.filter_by(username='su_main').first())
        self.assertIsNone(User.query.filter_by(username='doc_extra').first())

    def test_calculate_visit_cost_doctor_only(self):
        dept = Department(name='CostDept', name_ar='تكلفة', is_active=True)
        db.session.add(dept)
        db.session.commit()
        doc = User(username='doc_cost', email='doc_cost@example.com', full_name='Doc Cost', role='doctor', department_id=dept.id, is_active=True)
        doc.set_password('p')
        db.session.add(doc)
        db.session.commit()
        visit_data = {
            'doctor_id': doc.id,
            'visit_type': 'consultation',
            'payment_method': 'cash'
        }
        out = PricingService.calculate_visit_cost(visit_data)
        self.assertTrue(out.get('success'))
        self.assertEqual(float(out.get('total_cost', 0)), 0.0)
        self.assertEqual(len(out.get('services', [])), 0)

    def test_calculate_visit_cost_with_lab_and_radiology(self):
        # إنشاء أسعار خدمة افتراضية للتحاليل والأشعة
        sp_lab = ServicePrice(
            service_name='CBC',
            service_type='lab_test',
            base_price=30.0,
            cash_price=30.0,
            insurance_price=25.0,
            vip_price=60.0,
            is_active=True
        )
        sp_rad = ServicePrice(
            service_name='Chest X-Ray',
            service_type='radiology_scan',
            base_price=80.0,
            cash_price=80.0,
            insurance_price=60.0,
            vip_price=150.0,
            is_active=True
        )
        db.session.add_all([sp_lab, sp_rad])
        db.session.commit()
        # إنشاء كيانات لازمة
        dept = Department(name='DiagDept', name_ar='قسم تشخيص', is_active=True)
        db.session.add(dept)
        db.session.commit()
        doc = User(username='doc_diag', email='doc_diag@example.com', full_name='Doc Diag', role='doctor', department_id=dept.id, is_active=True)
        doc.set_password('p')
        db.session.add(doc)
        db.session.commit()
        # مريض وزيارة
        from models.patient import Patient
        from models.visit import Visit
        p = Patient(first_name='Cost', last_name='Test')
        db.session.add(p)
        db.session.commit()
        v = Visit(patient_id=p.id, department_id=dept.id, doctor_id=doc.id, status='OPEN')
        db.session.add(v)
        db.session.commit()
        # طلب مختبر ونتيجة أشعة
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.radiology_test import RadiologyResult
        lab_req = LabRequest(visit_id=v.id, patient_id=p.id)
        db.session.add(lab_req)
        db.session.commit()
        rad_req = RadiologyRequest(visit_id=v.id, patient_id=p.id, status='COMPLETED')
        db.session.add(rad_req)
        db.session.commit()
        rad_res = RadiologyResult(request_id=rad_req.id, patient_id=p.id)
        db.session.add(rad_res)
        db.session.commit()
        # حساب التكلفة
        visit_data = {
            'payment_method': 'cash',
            'lab_tests': [lab_req.id],
            'radiology_tests': [rad_res.id]
        }
        out = PricingService.calculate_visit_cost(visit_data)
        self.assertTrue(out.get('success'))
        self.assertEqual(float(out.get('total_cost', 0)), 110.0)
        self.assertEqual(len(out.get('services', [])), 2)

    def test_get_service_price_aliases(self):
        # تأكد من إنشاء الأسعار الافتراضية التي تشمل CBC وChest X-Ray
        PricingService.create_default_pricing()
        PricingService.seed_service_prices()
        c_cash = PricingService.get_service_price('cbc', 'lab_test', payment_method='cash')
        c_ar = PricingService.get_service_price('صورة دم كاملة', 'lab_test', payment_method='cash')
        cxr_cash = PricingService.get_service_price('Chest X-Ray', 'radiology_scan', payment_method='cash')
        cxr_alias = PricingService.get_service_price('أشعة سينية صدر', 'radiology_scan', payment_method='cash')
        self.assertEqual(float(c_cash), 30.0)
        self.assertEqual(float(c_ar), 30.0)
        self.assertEqual(float(cxr_cash), 80.0)
        self.assertEqual(float(cxr_alias), 80.0)
        # مرادفات إضافية
        esr_cash = PricingService.get_service_price('ESR', 'lab_test', payment_method='cash')
        esr_ar = PricingService.get_service_price('سرعة الترسيب', 'lab_test', payment_method='cash')
        crp_cash = PricingService.get_service_price('CRP', 'lab_test', payment_method='cash')
        crp_en = PricingService.get_service_price('c-reactive protein', 'lab_test', payment_method='cash')
        uri_cash = PricingService.get_service_price('Urinalysis', 'lab_test', payment_method='cash')
        uri_ar = PricingService.get_service_price('تحليل بول', 'lab_test', payment_method='cash')
        stool_cash = PricingService.get_service_price('Stool Analysis', 'lab_test', payment_method='cash')
        stool_ar = PricingService.get_service_price('تحليل براز', 'lab_test', payment_method='cash')
        abd_cash = PricingService.get_service_price('Abdomen X-Ray', 'radiology_scan', payment_method='cash')
        abd_alias = PricingService.get_service_price('أشعة سينية بطن', 'radiology_scan', payment_method='cash')
        pel_cash = PricingService.get_service_price('Pelvis X-Ray', 'radiology_scan', payment_method='cash')
        pel_alias = PricingService.get_service_price('أشعة سينية حوض', 'radiology_scan', payment_method='cash')
        pa_chest = PricingService.get_service_price('PA Chest', 'radiology_scan', payment_method='cash')
        self.assertEqual(float(esr_cash), 20.0)
        self.assertEqual(float(esr_ar), 20.0)
        self.assertEqual(float(crp_cash), 30.0)
        self.assertEqual(float(crp_en), 30.0)
        self.assertEqual(float(uri_cash), 20.0)
        self.assertEqual(float(uri_ar), 20.0)
        self.assertEqual(float(stool_cash), 20.0)
        self.assertEqual(float(stool_ar), 20.0)
        self.assertEqual(float(abd_cash), 80.0)
        self.assertEqual(float(abd_alias), 80.0)
        self.assertEqual(float(pel_cash), 80.0)
        self.assertEqual(float(pel_alias), 80.0)
        self.assertEqual(float(pa_chest), 80.0)
        # اختبارات موسعة لفحوص الهرمونات والمعامل
        lft = PricingService.get_service_price('lft', 'lab_test', payment_method='cash')
        rft = PricingService.get_service_price('rft', 'lab_test', payment_method='cash')
        tsh = PricingService.get_service_price('TSH', 'lab_test', payment_method='cash')
        ft3 = PricingService.get_service_price('free t3', 'lab_test', payment_method='cash')
        ft4 = PricingService.get_service_price('Free T4', 'lab_test', payment_method='cash')
        ferr = PricingService.get_service_price('فيريتين', 'lab_test', payment_method='cash')
        iron = PricingService.get_service_price('Iron Studies', 'lab_test', payment_method='cash')
        vitd = PricingService.get_service_price('فيتامين D', 'lab_test', payment_method='cash')
        dd = PricingService.get_service_price('دي دايمر', 'lab_test', payment_method='cash')
        psa = PricingService.get_service_price('psa', 'lab_test', payment_method='cash')
        prl = PricingService.get_service_price('برولاكتين', 'lab_test', payment_method='cash')
        afp = PricingService.get_service_price('AFP', 'lab_test', payment_method='cash')
        ca125 = PricingService.get_service_price('CA-125', 'lab_test', payment_method='cash')
        ca199 = PricingService.get_service_price('CA 19-9', 'lab_test', payment_method='cash')
        self.assertEqual(float(lft), 45.0)
        self.assertEqual(float(rft), 45.0)
        self.assertEqual(float(tsh), 35.0)
        self.assertEqual(float(ft3), 35.0)
        self.assertEqual(float(ft4), 35.0)
        self.assertEqual(float(ferr), 50.0)
        self.assertEqual(float(iron), 55.0)
        self.assertEqual(float(vitd), 70.0)
        self.assertEqual(float(dd), 60.0)
        self.assertEqual(float(psa), 55.0)
        self.assertEqual(float(prl), 45.0)
        self.assertEqual(float(afp), 55.0)
        self.assertEqual(float(ca125), 65.0)
        self.assertEqual(float(ca199), 65.0)

    def test_radiology_aliases_ct_mri_ultrasound(self):
        PricingService.seed_service_prices()
        cxr_pa = PricingService.get_service_price('CXR PA', 'radiology_scan', payment_method='cash')
        chest_pa = PricingService.get_service_price('Chest PA', 'radiology_scan', payment_method='cash')
        chest_ap = PricingService.get_service_price('Chest AP', 'radiology_scan', payment_method='cash')
        us_abd = PricingService.get_service_price('US Abdomen', 'radiology_scan', payment_method='cash')
        us_pel = PricingService.get_service_price('US Pelvis', 'radiology_scan', payment_method='cash')
        us_thy = PricingService.get_service_price('US Thyroid', 'radiology_scan', payment_method='cash')
        us_obs = PricingService.get_service_price('Obstetric Ultrasound', 'radiology_scan', payment_method='cash')
        us_dop = PricingService.get_service_price('Doppler Ultrasound', 'radiology_scan', payment_method='cash')
        ct_head = PricingService.get_service_price('CT Head', 'radiology_scan', payment_method='cash')
        ct_brain = PricingService.get_service_price('CT Brain', 'radiology_scan', payment_method='cash')
        ct_chest = PricingService.get_service_price('CT Chest', 'radiology_scan', payment_method='cash')
        ct_ap = PricingService.get_service_price('CT Abdomen and Pelvis', 'radiology_scan', payment_method='cash')
        ct_angio = PricingService.get_service_price('CT Angio', 'radiology_scan', payment_method='cash')
        mri_brain = PricingService.get_service_price('MRI Brain', 'radiology_scan', payment_method='cash')
        mri_spine = PricingService.get_service_price('MRI Spine', 'radiology_scan', payment_method='cash')
        mri_knee = PricingService.get_service_price('MRI Knee', 'radiology_scan', payment_method='cash')
        mri_shoulder = PricingService.get_service_price('MRI Shoulder', 'radiology_scan', payment_method='cash')
        mri_abd = PricingService.get_service_price('MRI Abdomen', 'radiology_scan', payment_method='cash')
        self.assertEqual(float(cxr_pa), 80.0)
        self.assertEqual(float(chest_pa), 80.0)
        self.assertEqual(float(chest_ap), 80.0)
        self.assertEqual(float(us_abd), 100.0)
        self.assertEqual(float(us_pel), 90.0)
        self.assertEqual(float(us_thy), 90.0)
        self.assertEqual(float(us_obs), 120.0)
        self.assertEqual(float(us_dop), 140.0)
        self.assertEqual(float(ct_head), 250.0)
        self.assertEqual(float(ct_brain), 250.0)
        self.assertEqual(float(ct_chest), 280.0)
        self.assertEqual(float(ct_ap), 300.0)
        self.assertEqual(float(ct_angio), 350.0)
        self.assertEqual(float(mri_brain), 350.0)
        self.assertEqual(float(mri_spine), 400.0)
        self.assertEqual(float(mri_knee), 350.0)
        self.assertEqual(float(mri_shoulder), 350.0)
        self.assertEqual(float(mri_abd), 450.0)

if __name__ == '__main__':
    unittest.main()
