import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app_factory import create_app, db
from models.user import User
from models.department import Department
from models.patient import Patient
from models.visit import Visit
from models.lab_request import LabRequest, LabResult


def ensure_triage_column():
    try:
        from sqlalchemy import inspect as _sa_inspect, text as _sa_text
        inspector = _sa_inspect(db.engine)
        cols = [c.get("name") if isinstance(c, dict) else c["name"] for c in inspector.get_columns("visits")]
        if "triage_level" not in cols:
            db.session.execute(_sa_text("ALTER TABLE visits ADD COLUMN triage_level VARCHAR(10)"))
            db.session.commit()
    except Exception:
        pass


def main():
    app = create_app()
    with app.app_context():
        ensure_triage_column()

        count_per_department = int(os.environ.get("FLOW_COUNT_PER_DEPT") or 10)
        total_patients = int(os.environ.get("FLOW_PATIENTS_COUNT") or 50)

        reception_user = User.query.filter_by(role="reception", is_active=True).first()
        lab_staff = User.query.filter_by(role="lab", is_active=True).first()
        doctors = User.query.filter_by(role="doctor", is_active=True).all()
        departments = Department.query.filter_by(is_active=True).all()

        patients = Patient.query.order_by(Patient.id.asc()).all()
        while len(patients) < total_patients:
            idx = len(patients) + 1
            p = Patient(
                first_name="مريض",
                last_name=f"تجريبي-{idx}",
                first_name_ar="مريض",
                last_name_ar=f"تجريبي-{idx}",
                national_id=f"T{idx:06d}{uuid.uuid4().hex[:4]}",
                phone=f"0599{idx:06d}"[:10],
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(p)
            db.session.flush()
            patients.append(p)
        db.session.commit()

        if not departments or not patients:
            print("MISSING_DEPARTMENT_OR_PATIENT")
            return

        visits_created = 0
        lab_requests_created = 0
        lab_results_created = 0

        for dept in departments:
            dept_type = dept.get_type()
            dept_doctors = [d for d in doctors if d.department_id == dept.id] or doctors
            for i in range(count_per_department):
                patient = patients[(i + dept.id) % len(patients)]
                doctor = dept_doctors[i % len(dept_doctors)] if dept_doctors else None
                visit = Visit(
                    patient_id=patient.id,
                    department_id=dept.id,
                    doctor_id=doctor.id if doctor else None,
                    status="IN_PROGRESS",
                    payment_status="PENDING",
                    total_amount=0,
                    paid_amount=0,
                    currency="ILS",
                    visit_type="EMERGENCY" if dept_type == "emergency" else "REGULAR",
                    visit_date=datetime.now(timezone.utc).date(),
                    visit_time=datetime.now(timezone.utc),
                    payment_method="CASH",
                    lab_tests_ordered=(dept_type == "lab"),
                    created_by=reception_user.id if reception_user else None,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    visit_number=f"{dept.id}-{uuid.uuid4().hex[:8]}",
                )
                db.session.add(visit)
                db.session.flush()
                visits_created += 1

                if dept_type == "lab":
                    lab_req = LabRequest(
                        visit_id=visit.id,
                        patient_id=patient.id,
                        requested_by=reception_user.id if reception_user else None,
                        request_number=f"LR-{uuid.uuid4().hex[:8]}",
                        status="IN_PROGRESS",
                        notes="طلب فحص تجريبي من الاستقبال"
                    )
                    db.session.add(lab_req)
                    db.session.flush()
                    lab_requests_created += 1

                    result = LabResult(
                        request_id=lab_req.id,
                        patient_id=patient.id,
                        performed_by=lab_staff.id if lab_staff else None,
                        test_code="CBC",
                        test_name="تحليل دم شامل",
                        value="Normal",
                        unit="",
                        reference_range="",
                        status="READY",
                        notes="نتيجة تجريبية"
                    )
                    db.session.add(result)
                    lab_results_created += 1

                    lab_req.status = "DONE"
                    lab_req.completed_at = datetime.now(timezone.utc)
                    visit.status = "OPEN"
                    visit.updated_at = datetime.now(timezone.utc)
                    visit.notes = (visit.notes or "").strip()
                    visit.notes = f"{visit.notes}\nأُجريت تحاليل المختبر وتمت العودة للاستقبال".strip()

        db.session.commit()

        print("FLOW_OK")
        print(f"VISITS_CREATED:{visits_created}")
        print(f"LAB_REQUESTS_CREATED:{lab_requests_created}")
        print(f"LAB_RESULTS_CREATED:{lab_results_created}")


if __name__ == "__main__":
    main()
