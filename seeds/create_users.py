import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from typing import List, Dict
from app_factory import create_app, db
ALLOWED_ROLES = {
    "super_admin",
    "admin",
    "manager",
    "reception",
    "doctor",
    "nurse",
    "lab",
    "radiology",
    "emergency",
    "accountant",
    "pharmacist",
    "user",
}

def create_users(users: List[Dict]):
    app = create_app()
    with app.app_context():
        from models.user import User
        from sqlalchemy import inspect as _sa_inspect
        try:
            inspector = _sa_inspect(db.engine)
            user_cols = [c.get("name") if isinstance(c, dict) else c["name"] for c in inspector.get_columns("users")]
            has_signature_col = "digital_signature" in user_cols
        except Exception:
            has_signature_col = False
        created = 0
        for u in users:
            username = u.get("username")
            password = u.get("password")
            role = u.get("role")
            full_name = u.get("full_name") or username
            email = u.get("email") or f"{username}@example.com"
            if not username or not password or not role:
                continue
            if role not in ALLOWED_ROLES:
                continue
            if User.query.filter_by(username=username).first():
                continue
            if User.query.filter_by(email=email).first():
                continue
            user = User(username=username, email=email, full_name=full_name, role=role, is_active=True)
            try:
                user.set_password(password)
            except Exception:
                continue
            try:
                if has_signature_col:
                    ds = u.get("digital_signature")
                    if not ds and role == "doctor":
                        ds = os.environ.get("DEFAULT_DOCTOR_SIGNATURE") or f"توقيع رقمي للطبيب: {full_name}"
                    user.digital_signature = ds
            except Exception:
                pass
            db.session.add(user)
            created += 1
        if created:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                created = 0
        return created

if __name__ == "__main__":
    spec_path = os.environ.get("USER_SEED_JSON") or (len(os.sys.argv) > 1 and os.sys.argv[1]) or ""
    users = []
    if spec_path and os.path.exists(spec_path):
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = data if isinstance(data, list) else data.get("users") or []
        except Exception:
            users = []
    else:
        admin_user = os.environ.get("ADMIN_USERNAME")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        default_pass = os.environ.get("DEFAULT_PASSWORD") or "123456"
        if admin_user and admin_pass:
            users = [{"username": admin_user, "password": admin_pass, "role": "admin", "full_name": "Admin"}]
        else:
            roles = [
                ("super_admin", "super"),
                ("admin", "admin"),
                ("manager", "manager"),
                ("reception", "reception"),
                ("doctor", "doctor"),
                ("lab", "lab"),
                ("radiology", "radiology"),
                ("nurse", "nurse"),
                ("emergency", "emergency"),
                ("accountant", "accountant"),
                ("pharmacist", "pharmacist"),
            ]
            users = [{"username": uname, "password": default_pass, "role": role, "full_name": uname.capitalize()} for role, uname in roles]
    cnt = create_users(users)
    print(f"created: {cnt}")
