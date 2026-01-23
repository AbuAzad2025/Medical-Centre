import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app_factory import create_app, db
from models.user import User
from models.department import Department
from models.service import ServiceMaster
from models.pricing import DoctorPricing

def seed_data():
    app = create_app()
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        print("Creating Departments...")
        dept_general = Department(name="General Clinic", name_ar="العيادة العامة", is_active=True)
        dept_lab = Department(name="Laboratory", name_ar="المختبر", is_active=True)
        dept_rad = Department(name="Radiology", name_ar="الأشعة", is_active=True)
        dept_er = Department(name="Emergency", name_ar="الطوارئ", is_active=True)

        db.session.add_all([dept_general, dept_lab, dept_rad, dept_er])
        db.session.commit()

        print("Creating Users...")
        # Reception
        u_recep = User(username="reception", email="reception@med.local", full_name="موظف الاستقبال", role="reception")
        u_recep.set_password("123456")
        
        # Doctors (General)
        u_doc1 = User(username="doc_general", email="doc1@med.local", full_name="د. عام احمد", role="doctor", department_id=dept_general.id)
        u_doc1.set_password("123456")
        
        # Doctors (ER)
        u_doc_er = User(username="doc_er", email="er@med.local", full_name="د. طوارئ", role="emergency", department_id=dept_er.id)
        u_doc_er.set_password("123456")

        # Lab Techs
        u_lab = User(username="lab_tech", email="lab@med.local", full_name="فني مختبر", role="lab", department_id=dept_lab.id)
        u_lab.set_password("123456")

        # Radiology Techs
        u_rad = User(username="rad_tech", email="rad@med.local", full_name="فني أشعة", role="radiology", department_id=dept_rad.id)
        u_rad.set_password("123456")

        # Admin
        u_admin = User(username="admin", email="admin@med.local", full_name="المدير", role="super_admin")
        u_admin.set_password("123456")

        db.session.add_all([u_recep, u_doc1, u_doc_er, u_lab, u_rad, u_admin])
        db.session.commit()

        print("Creating Services...")
        # Lab Services
        svc_cbc = ServiceMaster(name="CBC", name_ar="تحليل دم شامل", code="L001", category="lab", base_price=50.0, insurance_price=40.0, is_active=True)
        svc_sugar = ServiceMaster(name="Blood Sugar", name_ar="تحليل سكر", code="L002", category="lab", base_price=20.0, insurance_price=15.0, is_active=True)
        
        # Radiology Services
        svc_xray_chest = ServiceMaster(name="Chest X-Ray", name_ar="أشعة صدر", code="R001", category="radiology", base_price=100.0, insurance_price=80.0, is_active=True)
        svc_mri = ServiceMaster(name="MRI Head", name_ar="رنين مغناطيسي رأس", code="R002", category="radiology", base_price=500.0, insurance_price=400.0, is_active=True)
        
        # General Services
        svc_consult = ServiceMaster(name="Consultation", name_ar="كشف عام", code="G001", category="general", base_price=30.0, insurance_price=20.0, is_active=True)

        db.session.add_all([svc_cbc, svc_sugar, svc_xray_chest, svc_mri, svc_consult])
        db.session.commit()

        print("Creating Doctor Pricing...")
        # Pricing for Dr. General
        pricing_doc1 = DoctorPricing(
            doctor_id=u_doc1.id,
            department_id=dept_general.id,
            consultation_price=150.0,
            follow_up_price=75.0,
            emergency_price=200.0,
            is_active=True
        )
        db.session.add(pricing_doc1)
        db.session.commit()

        print("Seed completed successfully!")

if __name__ == "__main__":
    seed_data()
