"""Create all real users with proper roles for comprehensive testing"""
import os, sys
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

sys.path.insert(0, os.getcwd())
from app_factory import create_app, db
from models.user import User
from models.department import Department
from datetime import datetime, timezone

app = create_app()

with app.app_context():
    users_data = [
        {'username': 'admin', 'password': 'admin123', 'role': 'admin', 'full_name': 'System Administrator', 'email': 'admin@medical.local'},
        {'username': 'manager', 'password': 'manager123', 'role': 'manager', 'full_name': 'General Manager', 'email': 'manager@medical.local'},
        {'username': 'doctor1', 'password': 'doctor123', 'role': 'doctor', 'full_name': 'Dr. Ahmed Hassan', 'email': 'doctor1@medical.local'},
        {'username': 'doctor2', 'password': 'doctor123', 'role': 'doctor', 'full_name': 'Dr. Sarah Khalil', 'email': 'doctor2@medical.local'},
        {'username': 'nurse1', 'password': 'nurse123', 'role': 'nurse', 'full_name': 'Nurse Fatima Ali', 'email': 'nurse1@medical.local'},
        {'username': 'nurse2', 'password': 'nurse123', 'role': 'nurse', 'full_name': 'Nurse Omar Youssef', 'email': 'nurse2@medical.local'},
        {'username': 'reception1', 'password': 'reception123', 'role': 'reception', 'full_name': 'Receptionist Lina Samir', 'email': 'reception1@medical.local'},
        {'username': 'reception2', 'password': 'reception123', 'role': 'reception', 'full_name': 'Receptionist Khaled Nour', 'email': 'reception2@medical.local'},
        {'username': 'emergency1', 'password': 'emergency123', 'role': 'emergency', 'full_name': 'Emergency Dr. Karim Fadi', 'email': 'emergency1@medical.local'},
        {'username': 'radiology1', 'password': 'radiology123', 'role': 'radiology', 'full_name': 'Radiologist Dr. Mona Hani', 'email': 'radiology1@medical.local'},
        {'username': 'lab1', 'password': 'lab123', 'role': 'lab', 'full_name': 'Lab Technician Rami Adel', 'email': 'lab1@medical.local'},
        {'username': 'accountant1', 'password': 'accountant123', 'role': 'accountant', 'full_name': 'Accountant Samira Tarek', 'email': 'accountant1@medical.local'},
        {'username': 'pharmacist1', 'password': 'pharmacy123', 'role': 'pharmacist', 'full_name': 'Pharmacist Huda Mansour', 'email': 'pharmacist1@medical.local'},
        {'username': 'superadmin', 'password': 'super123', 'role': 'super_admin', 'full_name': 'Super Admin Basel', 'email': 'superadmin@medical.local'},
    ]

    created = 0
    existing = 0
    for u in users_data:
        user = User.query.filter_by(username=u['username']).first()
        if user:
            existing += 1
            print(f"EXISTS: {u['username']} ({u['role']})")
        else:
            user = User(
                username=u['username'],
                email=u['email'],
                full_name=u['full_name'],
                role=u['role'],
                is_active=True,
                is_admin=(u['role'] in ['admin', 'super_admin']),
                tenant_id=1,
                created_at=datetime.now(timezone.utc)
            )
            user.set_password(u['password'])
            db.session.add(user)
            created += 1
            print(f"CREATED: {u['username']} ({u['role']}) / {u['password']}")

    db.session.commit()
    print(f"\nTotal: {created} created, {existing} already existed")
