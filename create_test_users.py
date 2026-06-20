"""
Create test users for each tenant so we can log in and test each bundle/profile
"""
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
from app_factory import create_app, db
from models.user import User
from werkzeug.security import generate_password_hash

app = create_app()

TENANT_USERS = [
    {"username": "drsamer", "password": "Test@123", "role": "doctor", "tenant_slug": "clinic-samer", "email": "drsamer@clinic-samer.com"},
    {"username": "recep_samer", "password": "Test@123", "role": "reception", "tenant_slug": "clinic-samer", "email": "recep@clinic-samer.com"},
    {"username": "dral_snan", "password": "Test@123", "role": "doctor", "tenant_slug": "clinic-alsnan", "email": "dr@clinic-alsnan.com"},
    {"username": "recep_alsnan", "password": "Test@123", "role": "reception", "tenant_slug": "clinic-alsnan", "email": "recep@clinic-alsnan.com"},
    {"username": "tech_lab", "password": "Test@123", "role": "lab_tech", "tenant_slug": "lab-albaraa", "email": "tech@lab-albaraa.com"},
    {"username": "tech_rad", "password": "Test@123", "role": "radiology", "tenant_slug": "radiology-daw", "email": "tech@radiology-daw.com"},
    {"username": "pharmacist1", "password": "Test@123", "role": "pharmacist", "tenant_slug": "pharmacy-shifa", "email": "ph@pharmacy-shifa.com"},
    {"username": "admin_quds", "password": "Test@123", "role": "admin", "tenant_slug": "quds-medical", "email": "admin@quds-medical.com"},
    {"username": "dr_quds", "password": "Test@123", "role": "doctor", "tenant_slug": "quds-medical", "email": "dr@quds-medical.com"},
    {"username": "recep_quds", "password": "Test@123", "role": "reception", "tenant_slug": "quds-medical", "email": "recep@quds-medical.com"},
    {"username": "nurse_quds", "password": "Test@123", "role": "nurse", "tenant_slug": "quds-medical", "email": "nurse@quds-medical.com"},
    {"username": "dr_eyes", "password": "Test@123", "role": "doctor", "tenant_slug": "complex-eyes", "email": "dr@complex-eyes.com"},
    {"username": "dr_heart", "password": "Test@123", "role": "doctor", "tenant_slug": "clinic-heart", "email": "dr@clinic-heart.com"},
    {"username": "dr_digest", "password": "Test@123", "role": "doctor", "tenant_slug": "center-digestive", "email": "dr@center-digestive.com"},
    {"username": "tech_lab2", "password": "Test@123", "role": "lab_tech", "tenant_slug": "lab-amal", "email": "tech@lab-amal.com"},
]

def create_users():
    with app.app_context():
        from app.core.tenant.models import Tenant
        tenants = {t.slug: t for t in Tenant.query.all()}
        existing = {u.username for u in User.query.all()}
        created = 0
        for data in TENANT_USERS:
            if data["username"] in existing:
                print(f"  SKIP {data['username']} - already exists")
                continue
            t = tenants.get(data["tenant_slug"])
            if not t:
                print(f"  SKIP {data['username']} - tenant {data['tenant_slug']} not found")
                continue
            u = User(
                username=data["username"],
                email=data.get("email", f'{data["username"]}@tenant.local'),
                password_hash=generate_password_hash(data["password"]),
                role=data["role"],
                tenant_id=t.id,
                is_active=True,
                is_admin=False,
                full_name=data["username"]
            )
            db.session.add(u)
            print(f"  OK {data['username']} ({data['role']}) @ {data['tenant_slug']}")
            created += 1
        db.session.commit()
        print(f"\nOK Created {created} users. Total: {User.query.count()}")

if __name__ == "__main__":
    create_users()
