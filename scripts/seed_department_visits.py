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


def ensure_user(username, email, full_name, role, password, department_id):
    u = User.query.filter_by(username=username).first()
    if u:
        u.email = email
        u.full_name = full_name
        u.role = role
        u.department_id = department_id
        u.is_active = True
        u.set_password(password)
        db.session.commit()
        return False
    u = User(
        username=username,
        email=email,
        full_name=full_name,
        role=role,
        department_id=department_id,
        is_active=True,
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return True


def ensure_patient(first_name, last_name, national_id, phone=None):
    p = Patient.query.filter_by(national_id=national_id).first()
    if p:
        return p, False
    p = Patient(
        first_name=first_name,
        last_name=last_name,
        first_name_ar=first_name,
        last_name_ar=last_name,
        national_id=national_id,
        phone=phone,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(p)
    db.session.commit()
    return p, True


def seed_visits_for_department(dept, doctor, created_by, target_count):
    existing = Visit.query.filter_by(department_id=dept.id).count()
    to_create = max(0, target_count - existing)
    created = 0
    for i in range(to_create):
        national_id = f"{dept.id}{i:04d}{uuid.uuid4().hex[:4]}"
        patient, _ = ensure_patient(
            first_name="مريض",
            last_name=f"{dept.name_ar or dept.name}-{i+1}",
            national_id=national_id,
            phone=f"0599{dept.id:02d}{i:04d}",
        )
        visit_type = "EMERGENCY" if dept.get_type() == "emergency" else "REGULAR"
        is_emergency = dept.get_type() == "emergency"
        v = Visit(
            patient_id=patient.id,
            department_id=dept.id,
            doctor_id=doctor.id if doctor else None,
            status="COMPLETED",
            payment_status="PAID",
            total_amount=50,
            paid_amount=50,
            currency="ILS",
            visit_type=visit_type,
            visit_date=datetime.now(timezone.utc).date(),
            visit_time=datetime.now(timezone.utc),
            payment_method="CASH",
            is_emergency=is_emergency,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            visit_number=f"V-{dept.id}-{uuid.uuid4().hex[:6]}",
        )
        db.session.add(v)
        created += 1
    if created:
        db.session.commit()
    return created


def main():
    app = create_app()
    with app.app_context():
        try:
            from sqlalchemy import inspect as _sa_inspect, text as _sa_text
            inspector = _sa_inspect(db.engine)
            cols = [c.get("name") if isinstance(c, dict) else c["name"] for c in inspector.get_columns("visits")]
            if "triage_level" not in cols:
                db.session.execute(_sa_text("ALTER TABLE visits ADD COLUMN triage_level VARCHAR(10)"))
                db.session.commit()
        except Exception:
            pass
        default_pass = os.environ.get("DEFAULT_PASSWORD") or "123456"
        departments = Department.query.filter_by(is_active=True).all()
        reception = User.query.filter_by(username="reception").first()
        created_by = reception.id if reception else None

        accounts = []
        visits_created = {}

        for dept in departments:
            dept_type = dept.get_type()
            doctor_username = f"doctor_{dept.id}"
            staff_username = f"staff_{dept.id}"

            doctor_role = "doctor"
            staff_role = "nurse"
            if dept_type == "lab":
                staff_role = "lab"
            elif dept_type == "radiology":
                staff_role = "radiology"
            elif dept_type == "emergency":
                staff_role = "emergency"

            doctor_full = f"د. {dept.name_ar or dept.name}"
            staff_full = f"موظف {dept.name_ar or dept.name}"

            ensure_user(
                doctor_username,
                f"{doctor_username}@med.local",
                doctor_full,
                doctor_role,
                default_pass,
                dept.id,
            )
            ensure_user(
                staff_username,
                f"{staff_username}@med.local",
                staff_full,
                staff_role,
                default_pass,
                dept.id,
            )

            accounts.append((dept.name_ar or dept.name, doctor_username, doctor_role, default_pass))
            accounts.append((dept.name_ar or dept.name, staff_username, staff_role, default_pass))

            doctor_user = User.query.filter_by(username=doctor_username).first()
            created_count = seed_visits_for_department(dept, doctor_user, created_by, target_count=5)
            visits_created[dept.name_ar or dept.name] = created_count

        print("ACCOUNTS")
        for dept_name, username, role, pwd in accounts:
            print(f"{dept_name}|{username}|{role}|{pwd}")

        print("VISITS_CREATED")
        for dept_name, cnt in visits_created.items():
            print(f"{dept_name}:{cnt}")


if __name__ == "__main__":
    main()
