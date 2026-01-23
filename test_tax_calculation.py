import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from app_factory import create_app, db
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.department import Department
from models.pricing import DoctorPricing

def test_tax_calculation():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        
        # 1. Setup Data
        # Get or create a patient
        patient = Patient(
            first_name="Tax",
            last_name="Test Patient",
            national_id="999999999",
            phone="0599999999",
            gender="M",
            birth_date=datetime(1990, 1, 1).date()
        )
        db.session.add(patient)
        db.session.flush()

        # Get a doctor and department
        dept = Department(name='General', name_ar='العيادة العامة', is_active=True)
        db.session.add(dept)
        db.session.flush()

        doctor = User(username='dr_tax', email='dr_tax@example.com', full_name='د. عام احمد', role='doctor', department_id=dept.id, is_active=True)
        doctor.set_password('p')
        db.session.add(doctor)
        db.session.flush()

        reception = User(username='reception', email='reception@example.com', full_name='Reception', role='reception', is_active=True)
        reception.set_password('123456')
        db.session.add(reception)
        db.session.flush()
            
        # Ensure Doctor Pricing exists
        pricing = DoctorPricing(
            doctor_id=doctor.id,
            consultation_price=100.0,
            follow_up_price=50.0,
            emergency_price=150.0
        )
        db.session.add(pricing)
        db.session.commit()

        # 2. Test API Calculation (Inclusive)
        with app.test_client() as client:
            page = client.get('/auth/login')
            html = page.data.decode('utf-8', errors='ignore')
            import re
            m = re.search(r'name="csrf_token" value="([^"]+)"', html)
            token = m.group(1) if m else ''
            client.post('/auth/login', data={'username': 'reception', 'password': '123456', 'csrf_token': token}, follow_redirects=False)
            
            # Cost = 100, Tax Rate = 0.15
            # Inclusive: Base = 100 / 1.15 = 86.96, Tax = 100 - 86.96 = 13.04
            response = client.get(
                f'/reception/api/visit-pricing?department_id={dept.id}&doctor_id={doctor.id}&visit_type=CONSULTATION&tax_type=inclusive'
            )
            data = response.get_json()
            assert response.status_code == 200
            
            # Verify Inclusive
            # Cost should remain 100 (user pays 100)
            assert data['cost'] == 100.0, f"Expected 100.0, got {data['cost']}"
            
            # Cost = 100, Tax Rate = 0.15
            # Exclusive: Tax = 100 * 0.15 = 15.0, Total = 115.0
            response = client.get(
                f'/reception/api/visit-pricing?department_id={dept.id}&doctor_id={doctor.id}&visit_type=CONSULTATION&tax_type=exclusive'
            )
            data = response.get_json()
            assert response.status_code == 200

            # Verify Exclusive
            # Cost should be 115 (user pays 115)
            assert data['cost'] == 115.0, f"Expected 115.0, got {data['cost']}"

        # 3. Test Visit Creation (Inclusive)
        TAX_RATE = 0.15
        base_price = 100.0 # From DoctorPricing
        
        # Inclusive Logic
        visit_inc = Visit(
            patient_id=patient.id,
            department_id=dept.id,
            doctor_id=doctor.id,
            visit_type='CONSULTATION',
            total_amount=base_price # 100
        )
        
        visit_inc.is_tax_inclusive = True
        visit_inc.tax_percent = TAX_RATE * 100
        
        base_amount_inc = float(visit_inc.total_amount) / (1 + TAX_RATE)
        visit_inc.tax_amount = round(float(visit_inc.total_amount) - base_amount_inc, 2)
        
        assert visit_inc.tax_amount == 13.04, f"Expected Tax 13.04, got {visit_inc.tax_amount}"
        
        # Exclusive Logic
        visit_exc = Visit(
            patient_id=patient.id,
            department_id=dept.id,
            doctor_id=doctor.id,
            visit_type='CONSULTATION',
            total_amount=base_price # 100
        )
        
        visit_exc.is_tax_inclusive = False
        visit_exc.tax_percent = TAX_RATE * 100
        
        tax_val_exc = float(visit_exc.total_amount) * TAX_RATE
        visit_exc.tax_amount = round(tax_val_exc, 2)
        visit_exc.total_amount = round(float(visit_exc.total_amount) + tax_val_exc, 2)
        
        assert visit_exc.total_amount == 115.0, f"Expected Total 115.0, got {visit_exc.total_amount}"
        assert visit_exc.tax_amount == 15.0, f"Expected Tax 15.0, got {visit_exc.tax_amount}"

if __name__ == "__main__":
    test_tax_calculation()
