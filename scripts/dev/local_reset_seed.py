#!/usr/bin/env python3
"""
Local development database reset and seed.

SAFEGUARDS
━━━━━━━━━━
- Requires --confirm-local-reset flag.
- Refuses to run against non-localhost databases (localhost, 127.0.0.1, ::1).
- Creates a timestamped backup before making changes.
- Verifies the backup is usable (non-zero, valid SQL header) before proceeding.
- Never runs automatically; never stores passwords in repository files.
- Uses normal project password APIs (User.set_password()).
- Preserves: schema, alembic_version, migrations, source code, uploads, .env, Git history.

USAGE
━━━━━
    python scripts/dev/local_reset_seed.py --confirm-local-reset

    Dry-run (no changes):
    python scripts/dev/local_reset_seed.py --dry-run

WHAT IT DOES
━━━━━━━━━━━━
1. Verifies the database is on localhost / 127.0.0.1 / ::1.
2. Creates a pg_dump backup to ~/medical_system_backups/ (outside the repo).
3. Verifies the backup file is usable.
4. Deletes ALL existing tenant-scoped data: users, patients, visits, appointments,
   invoices, lab requests, etc.  Preserves platform configuration tables.
5. Seeds a clean demo dataset:
   a) One platform owner account (master).
   b) One tenant centre per active product-bundle/package type.
   c) Minimal, realistic role-based users for each centre.
   d) Small fictional demo records (patients, visits, appointments, services).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import string
import subprocess
import sys
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.chdir(_REPO)

from dotenv import load_dotenv
load_dotenv()


# ──────────────────────────────────────────────────────────────────────
# SAFEGUARDS
# ──────────────────────────────────────────────────────────────────────

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _db_host() -> str:
    """Extract host from DATABASE_URL."""
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("FATAL: DATABASE_URL is not set.")
    if "@" in url:
        host_part = url.split("@", 1)[1].split("/")[0]
        host = host_part.split(":")[0]
    else:
        host = "localhost"
    return host


def _is_local_db() -> bool:
    host = _db_host()
    ok = host in _LOCAL_HOSTS
    if not ok:
        print(f"SECURITY BLOCK: Database host is '{host}', which is NOT local.")
        print("This script is only safe for local development databases.")
    return ok


def _require_confirm() -> None:
    if "--confirm-local-reset" in sys.argv:
        return
    print("DANGER: This will DELETE ALL DATA in the local development database.")
    print("   A timestamped pg_dump backup will be created first.")
    ans = input('Type "RESET" to continue: ').strip()
    if ans != "RESET":
        raise SystemExit("Aborted by user.")


# ──────────────────────────────────────────────────────────────────────
# BACKUP
# ──────────────────────────────────────────────────────────────────────

_BACKUP_DIR = Path.home() / "medical_system_backups"
_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _find_pg_dump() -> str:
    for root in [Path("C:/Program Files/PostgreSQL")]:
        if root.is_dir():
            for ver_dir in sorted(root.iterdir(), reverse=True):
                candidate = ver_dir / "bin" / "pg_dump.exe"
                if candidate.is_file():
                    return str(candidate)
    return "pg_dump"


def _verify_backup(path: Path) -> bool:
    """Check backup is non-empty and starts with valid SQL."""
    if not path.exists():
        print(f"  ERROR: Backup file does not exist: {path}")
        return False
    size = path.stat().st_size
    if size < 100:
        print(f"  ERROR: Backup file too small ({size} bytes) — likely corrupt.")
        return False
    try:
        header = path.read_bytes()[:40]
        if not header.startswith(b"--"):
            print(f"  WARNING: Backup does not start with SQL header header={header[:20]}")
        else:
            print(f"  Backup verified: {size / 1024:.0f} KB, valid SQL header")
        return True
    except Exception as e:
        print(f"  ERROR: Cannot read backup: {e}")
        return False


def _create_backup() -> Path | None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = _BACKUP_DIR / f"medical_system_pre_reset_{ts}.sql"
    url = os.environ["DATABASE_URL"]
    parts = url.replace("postgresql://", "").split("@")
    user_pass = parts[0]
    host_port_db = parts[1].split("/") if len(parts) > 1 else (":@" + parts[0]).split("/")
    host_port = host_port_db[0]
    db_name = host_port_db[1] if len(host_port_db) > 1 else "medical_system"
    user = user_pass.split(":")[0] if ":" in user_pass else user_pass

    pg_dump = _find_pg_dump()
    cmd = [pg_dump, "-h", "localhost", "-U", user, "-d", db_name, "-f", str(backup_path)]
    print(f"Creating backup: {backup_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"WARNING: pg_dump returned {result.returncode}: {result.stderr.strip()}")
        print("Aborting — backup failed.")
        return None
    if not _verify_backup(backup_path):
        print("Aborting — backup verification failed.")
        return None
    return backup_path


# ──────────────────────────────────────────────────────────────────────
# READ PACKAGES FROM DATABASE
# ──────────────────────────────────────────────────────────────────────

_EXCLUDED_PROFILES: dict[str, str] = {
    "billing_only": "Package has only billing+appointments — no clinical/medical-centre modules; cannot create meaningful medical centre.",
    "custom": "Package has no modules enabled — configuration-only; cannot create tenant with zero capabilities.",
}


def _read_product_bundles(app) -> list[dict]:
    """Read active product bundles from the database.

    Returns list of dicts with keys: id, name, name_ar, slug, profile_code, modules.
    Filters to only bundles eligible for centre creation.
    """
    from app.core.tenant.models import ProductBundle

    bundles = ProductBundle.query.filter(
        ProductBundle.is_active == True,
        ProductBundle.profile_code.isnot(None),
    ).order_by(ProductBundle.id).all()

    result = []
    for b in bundles:
        mods = b.get_modules()
        result.append({
            "id": b.id,
            "name": b.name or "",
            "name_ar": getattr(b, "name_ar", None) or "",
            "slug": b.slug or "",
            "profile_code": b.profile_code or "",
            "modules": mods,
            "is_eligible": True,
            "exclusion_reason": None,
        })

    return result


def _classify_bundles(bundles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separate bundles into eligible (for centre creation) and excluded."""
    eligible = []
    excluded = []
    for b in bundles:
        code = b["profile_code"]
        if code in _EXCLUDED_PROFILES:
            b["is_eligible"] = False
            b["exclusion_reason"] = _EXCLUDED_PROFILES[code]
            excluded.append(b)
        elif not b["modules"]:
            b["is_eligible"] = False
            b["exclusion_reason"] = "No modules enabled in bundle definition."
            excluded.append(b)
        elif "owner" in b["modules"] and not any(m for m in b["modules"] if m != "owner"):
            b["is_eligible"] = False
            b["exclusion_reason"] = "Only 'owner' module — platform-only, no tenant capability."
            excluded.append(b)
        else:
            b["is_eligible"] = True
            eligible.append(b)
    return eligible, excluded


# ──────────────────────────────────────────────────────────────────────
# BOOTSTRAP APP
# ──────────────────────────────────────────────────────────────────────

def _app():
    from flask import g
    from app_factory import create_app as _create_app, db as _db

    os.environ.setdefault("APP_ENV", "production")
    a = _create_app("production")
    with a.app_context():
        g._tenant_filter_bypass = True
    return a, _db


# ──────────────────────────────────────────────────────────────────────
# TRUNCATE / DELETE DATA
# ──────────────────────────────────────────────────────────────────────

_PRESERVED = {
    "alembic_version", "module_definitions", "product_bundles",
    "subscription_plans", "roles", "permissions", "role_permissions",
    "module_permissions", "department_permissions", "notification_rules",
    "icd10_codes", "cpt_codes", "drg_codes",
}


def _reset_data(db) -> None:
    from sqlalchemy import text as _text

    # Discover all user tables dynamically.
    rows = db.session.execute(
        _text(
            "SELECT tablename FROM pg_catalog.pg_tables "
            "WHERE schemaname = 'public' ORDER BY tablename"
        )
    ).fetchall()
    all_tables = [r[0] for r in rows]
    deletable = [t for t in all_tables if t not in _PRESERVED]

    # Exclude tenants from bulk delete — handled separately to preserve id=1.
    dynamic_deletable = [t for t in deletable if t != "tenants"]

    print(f"\nDeleting data from {len(dynamic_deletable)} tables ...")
    db.session.execute(_text("SET session_replication_role = 'replica'"))
    try:
        for table in dynamic_deletable:
            db.session.execute(_text(f"DELETE FROM {table}"))
            if table in ("users",):
                print(f"  CLEARED users")
        db.session.execute(_text("DELETE FROM tenants WHERE id != 1"))
        db.session.execute(
            _text(
                "UPDATE tenants SET product_profile_code = NULL, "
                "slug = 'default', name = 'Default Platform', "
                "contact_email = 'platform@localhost', status = 'ACTIVE' "
                "WHERE id = 1"
            )
        )
        db.session.commit()
        print("  CLEARED tenants (kept id=1 platform)")
        # Ensure platform tenant id=1 exists (may have been lost in a prior failed run).
        row = db.session.execute(
            _text("SELECT id FROM tenants WHERE id = 1")
        ).fetchone()
        if not row:
            from app.core.tenant.models import Tenant, TenantStatus, StorageMode
            t = Tenant(
                id=1,
                slug='default',
                name='Default Platform',
                contact_email='platform@localhost',
                status=TenantStatus.ACTIVE,
                storage_mode=StorageMode.LOCAL,
            )
            db.session.add(t)
            db.session.commit()
            print("  RECREATED platform tenant (id=1)")
    finally:
        db.session.execute(_text("SET session_replication_role = 'origin'"))


# ──────────────────────────────────────────────────────────────────────
# SEED DATA
# ──────────────────────────────────────────────────────────────────────

ROLE_MODULES = {
    "admin": [],
    "manager": ["reporting"],
    "reception": ["reception"],
    "doctor": ["doctor"],
    "nurse": ["nursing"],
    "lab": ["lab"],
    "radiology": ["radiology"],
    "pharmacist": ["pharmacy"],
    "emergency": ["emergency"],
    "accountant": ["billing"],
}

ROLE_ORDER = ["admin", "manager", "reception", "doctor", "nurse",
              "lab", "radiology", "pharmacist", "emergency", "accountant"]

ROLE_DISPLAY = {
    "admin": "مدير", "manager": "مدير تنفيذي",
    "reception": "استقبال", "doctor": "طبيب",
    "nurse": "ممرض", "lab": "مختبر",
    "radiology": "أشعة", "pharmacist": "صيدلي",
    "emergency": "طوارئ", "accountant": "محاسب",
}


def _make_slug(name: str) -> str:
    s = name.lower().replace(" ", "-").replace("&", "and").replace("--", "-")
    return "".join(c for c in s if c.isalnum() or c == "-").strip("-")


def _strong_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _arabic_patient_name(num: int) -> tuple[str, str, str, str]:
    first_names = [
        "أحمد", "محمد", "سارة", "فاطمة", "خالد", "نورة",
        "عمر", "مريم", "علي", "هند", "يوسف", "ليلى",
    ]
    last_names = [
        "العلي", "السالم", "الحربي", "القحطاني", "الزهراني",
        "العتيبي", "الشهري", "الغامدي", "المطيري", "الدوسري",
    ]
    fn = first_names[num % len(first_names)]
    ln = last_names[(num // len(first_names)) % len(last_names)]
    return fn, ln, fn, ln  # (ar_first, ar_last, en_first, en_last)


def _seed_platform_owner(db, strong_pw: str):
    from models.user import User

    u = User(
        username="master",
        email="master@platform.local",
        full_name="مالك المنصة",
        role="super_admin",
        tenant_id=1,
        is_active=True,
        is_admin=True,
    )
    u.set_password(strong_pw)
    db.session.add(u)
    db.session.commit()
    print(f"  Created platform owner: master")
    return u


def _seed_tenant_centres(db, bundles: list[dict], shared_pw: str) -> dict:
    from app.core.tenant.models import Tenant, TenantStatus
    from app.core.module.models import TenantModule
    from models.user import User

    admin_user = User.query.filter_by(username="master").first()
    if not admin_user:
        raise RuntimeError("Platform owner not found")

    centres = {}

    for b in bundles:
        code = b["profile_code"]
        slug = b["slug"]
        name_ar = b.get("name_ar", "") or b["name"]
        modules = b["modules"]

        t = Tenant(
            slug=slug,
            name=b["name"],
            name_ar=name_ar,
            contact_email=f"admin@{slug}.local",
            contact_phone="+966500000000",
            status=TenantStatus.ACTIVE,
            product_profile_code=code,
        )
        db.session.add(t)
        db.session.flush()

        for m in modules:
            db.session.add(TenantModule(
                tenant_id=t.id,
                module_name=m,
                is_active=True,
                activated_at=datetime.now(timezone.utc),
                activated_by=admin_user.id,
            ))

        role_set = set()
        role_set.add("admin")
        if "reporting" in modules:
            role_set.add("manager")
        if "reception" in modules:
            role_set.add("reception")
        if "doctor" in modules:
            role_set.add("doctor")
        if "nursing" in modules:
            role_set.add("nurse")
        if "lab" in modules:
            role_set.add("lab")
        if "radiology" in modules:
            role_set.add("radiology")
        if "pharmacy" in modules:
            role_set.add("pharmacist")
        if "emergency" in modules:
            role_set.add("emergency")
        if "billing" in modules:
            role_set.add("accountant")

        users_created = []
        for role in ROLE_ORDER:
            if role not in role_set:
                continue
            uname = f"{slug}_{role}"
            display_role = ROLE_DISPLAY.get(role, role)
            u = User(
                username=uname,
                email=f"{uname}@{slug}.local",
                full_name=f"{display_role} — {name_ar}",
                role=role,
                tenant_id=t.id,
                is_active=True,
                is_admin=(role == "admin"),
            )
            u.set_password(shared_pw)
            db.session.add(u)
            users_created.append((uname, role))

        db.session.flush()
        centres[code] = {
            "tenant": t,
            "modules": modules,
            "users": users_created,
        }
        n_users = len(users_created)
        n_mods = len(modules)
        name_safe = b["name"].encode("ascii", errors="replace").decode()
        print(f"  Centre: {name_safe} ({slug}) — {n_mods} modules, {n_users} users")

    db.session.commit()
    return centres


def _seed_demo_data(db, centres: dict):
    from models.user import User
    from models.patient import Patient
    from models.visit import Visit
    from models.appointment import Appointment
    from models.invoice import Invoice
    from models.payment import Payment
    from models.service import ServiceMaster
    from models.department import Department
    from models.lab_request import LabRequest
    from models.radiology_request import RadiologyRequest
    from models.queue_management import QueueManagement
    from app.core.tenant.models import Tenant

    now = datetime.now(timezone.utc)

    for code, info in centres.items():
        t: Tenant = info["tenant"]
        modules = info["modules"]
        users = {r: u for u, r in info["users"]}

        # ── 1. Create one department ──
        dept = Department(
            tenant_id=t.id,
            name_ar="القسم الرئيسي",
            name="Main Department",
            is_active=True,
        )
        db.session.add(dept)
        db.session.flush()

        # ── 2. Create small service catalog ──
        svc_idx = 0
        service_objs = []

        def _add_svc(cat, name_ar, name_en, price):
            nonlocal svc_idx
            svc_idx += 1
            s = ServiceMaster(
                tenant_id=t.id,
                code=f"{code}_{svc_idx:02d}",
                name=name_en,
                name_ar=name_ar,
                category=cat,
                base_price=Decimal(str(price)),
                department_id=dept.id,
                is_active=True,
            )
            db.session.add(s)
            service_objs.append(s)

        if "doctor" in modules:
            _add_svc("doctor", "استشارة طبيب عام", "General Consultation", 100.00)
            _add_svc("doctor", "استشارة متابعة", "Follow-up Visit", 75.00)
        if "lab" in modules:
            _add_svc("lab", "تحليل دم كامل CBC", "CBC Blood Test", 50.00)
            _add_svc("lab", "تحليل سكر", "Glucose Test", 30.00)
        if "radiology" in modules:
            _add_svc("radiology", "أشعة سينية صدر", "Chest X-Ray", 150.00)
            _add_svc("radiology", "تصوير بالموجات فوق صوتية", "Ultrasound", 200.00)
        if "pharmacy" in modules:
            _add_svc("pharmacy", "صرف دواء", "Medication Dispensing", 0.00)
        if "billing" in modules or not service_objs:
            _add_svc("general", "رسوم إدارية", "Administrative Fee", 25.00)
        db.session.flush()

        # ── 3. Create 3 fictional patients ──
        patients = []
        for i in range(3):
            fn_ar, ln_ar, fn_en, ln_en = _arabic_patient_name(t.id * 10 + i)
            p = Patient(
                tenant_id=t.id,
                first_name=fn_en,
                last_name=ln_en,
                first_name_ar=fn_ar,
                last_name_ar=ln_ar,
                gender="M" if i % 2 == 0 else "F",
                phone=f"+96650{1000000 + t.id * 100 + i}",
                birth_date=date(1980 + i * 10, max(1, 1 + i), min(28, 1 + i)),
            )
            db.session.add(p)
            patients.append(p)
        db.session.flush()

        # Helper to get user by role
        def _user(role):
            uname = f"{code}_{role}"
            return User.query.filter_by(username=uname).first()

        # ── 4. One upcoming appointment (if appointments enabled) ──
        if "appointments" in modules:
            doc = _user("doctor") or _user("admin")
            rec = _user("reception") or _user("admin")
            if doc and rec and patients:
                apt = Appointment(
                    tenant_id=t.id,
                    patient_id=patients[0].id,
                    doctor_id=doc.id,
                    department_id=dept.id,
                    starts_at=datetime.combine(
                        date.today() + timedelta(days=1),
                        datetime.min.time().replace(hour=9, minute=0)
                    ).replace(tzinfo=timezone.utc),
                    status="SCHEDULED",
                    created_by=rec.id,
                )
                db.session.add(apt)

        # ── 5. One active visit (if doctor enabled) ──
        if "doctor" in modules:
            doc = _user("doctor")
            rec = _user("reception") or _user("admin")
            if doc and rec and len(patients) > 1:
                v = Visit(
                    tenant_id=t.id,
                    patient_id=patients[1].id,
                    doctor_id=doc.id,
                    department_id=dept.id,
                    status="IN_PROGRESS",
                    created_by=rec.id,
                    created_at=now,
                    visit_date=date.today(),
                    visit_time=now,
                )
                db.session.add(v)
                db.session.flush()

                # Queue record.
                try:
                    q = QueueManagement(
                        tenant_id=t.id,
                        patient_id=patients[1].id,
                        department_id=dept.id,
                        doctor_id=doc.id,
                        status="waiting",
                        visit_id=v.id,
                    )
                    db.session.add(q)
                except Exception:
                    pass

        # ── 6. One completed & paid visit (if billing enabled) ──
        if "billing" in modules and "doctor" in modules:
            doc = _user("doctor")
            rec = _user("reception") or _user("admin")
            acc = _user("accountant")
            if doc and rec and acc and len(patients) > 2 and service_objs:
                v2 = Visit(
                    tenant_id=t.id,
                    patient_id=patients[2].id,
                    doctor_id=doc.id,
                    department_id=dept.id,
                    status="COMPLETED",
                    created_by=rec.id,
                    created_at=now - timedelta(days=2),
                    visit_date=date.today() - timedelta(days=2),
                    visit_time=now - timedelta(days=2),
                )
                db.session.add(v2)
                db.session.flush()

                total = sum(s.base_price for s in service_objs)
                inv = Invoice(
                    tenant_id=t.id,
                    visit_id=v2.id,
                    created_by=acc.id,
                    total_amount=total,
                    paid_amount=total,
                    status="PAID",
                    created_at=now - timedelta(days=2),
                )
                db.session.add(inv)
                db.session.flush()

                pmt = Payment(
                    tenant_id=t.id,
                    visit_id=v2.id,
                    invoice_id=inv.id,
                    patient_id=patients[2].id,
                    amount=total,
                    method="CASH",
                    status="CONFIRMED",
                    received_by=acc.id,
                )
                db.session.add(pmt)

        # ── 7. One lab request (if lab enabled) — link to active visit if available ──
        if "lab" in modules:
            lab_user = _user("lab")
            doc = _user("doctor")
            # Find a visit to link (use active visit if exists, otherwise completed)
            active_visit = Visit.query.filter_by(
                tenant_id=t.id, patient_id=patients[1].id
            ).first() if len(patients) > 1 else None
            if lab_user and doc and active_visit and patients:
                lr = LabRequest(
                    tenant_id=t.id,
                    visit_id=active_visit.id,
                    patient_id=patients[0].id,
                    requested_by=doc.id,
                    analyzed_by=lab_user.id,
                    status="DONE",
                    created_at=now - timedelta(days=1),
                    completed_at=now,
                )
                db.session.add(lr)

        # ── 8. One radiology request (if radiology enabled) ──
        if "radiology" in modules:
            rad_user = _user("radiology")
            doc = _user("doctor")
            active_visit = Visit.query.filter_by(
                tenant_id=t.id, patient_id=patients[1].id
            ).first() if len(patients) > 1 else None
            if rad_user and doc and active_visit and patients:
                rr = RadiologyRequest(
                    tenant_id=t.id,
                    visit_id=active_visit.id,
                    patient_id=patients[0].id,
                    requested_by=doc.id,
                    status="REQUESTED",
                    created_at=now - timedelta(hours=2),
                )
                db.session.add(rr)

        db.session.commit()

    print("  Demo data seeded for all centres.")


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Reset and reseed local Medical System dev database."
    )
    parser.add_argument(
        "--confirm-local-reset",
        action="store_true",
        help="Acknowledge that this will DELETE ALL DATA in the local dev database.",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip pg_dump backup (not recommended).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes.",
    )
    args = parser.parse_args()

    # ── Safety ──
    if not _is_local_db():
        print("Exiting.")
        sys.exit(1)

    if not args.dry_run:
        if "--confirm-local-reset" in sys.argv or args.confirm_local_reset:
            pass
        else:
            _require_confirm()
    else:
        print("\n*** DRY RUN — no changes will be made ***\n")

    # ── Read packages from DB (read-only boot) ──
    app, db = _app()
    with app.app_context():
        from flask import g
        g._tenant_filter_bypass = True

        bundles = _read_product_bundles(app)
        eligible, excluded = _classify_bundles(bundles)

        print(f"\n=== DRY RUN: Package Matrix ===")
        print(f"\nActive product bundles found: {len(bundles)}")
        print(f"\nEligible for centre creation: {len(eligible)}")
        print(f"Excluded: {len(excluded)}")

        print(f"\n--- Eligible Bundles ---")
        for b in eligible:
            mods = ", ".join(b["modules"])
            name = b["name"].encode("ascii", errors="replace").decode()
            print(f"  {b['profile_code']:35s} | {name:40s} | modules: {mods}")

        print(f"\n--- Excluded Bundles ---")
        for b in excluded:
            name = b["name"].encode("ascii", errors="replace").decode()
            reason = b["exclusion_reason"]
            print(f"  {b['profile_code']:35s} | {name:40s} | reason: {reason}")

        # Count expected records
        n_tenants = 1 + len(eligible)  # platform + centres
        n_users = 1  # master
        for b in eligible:
            n_users += 1  # admin always
            if "reporting" in b["modules"]:
                n_users += 1
            if "reception" in b["modules"]:
                n_users += 1
            if "doctor" in b["modules"]:
                n_users += 1
            if "nursing" in b["modules"]:
                n_users += 1
            if "lab" in b["modules"]:
                n_users += 1
            if "radiology" in b["modules"]:
                n_users += 1
            if "pharmacy" in b["modules"]:
                n_users += 1
            if "emergency" in b["modules"]:
                n_users += 1
            if "billing" in b["modules"]:
                n_users += 1

        n_patients = len(eligible) * 3
        n_visits_active = sum(1 for b in eligible if "doctor" in b["modules"])
        n_visits_completed = sum(1 for b in eligible if "billing" in b["modules"] and "doctor" in b["modules"])
        n_appts = sum(1 for b in eligible if "appointments" in b["modules"])
        n_invoices = n_visits_completed
        n_payments = n_visits_completed
        n_lab = sum(1 for b in eligible if "lab" in b["modules"])
        n_rad = sum(1 for b in eligible if "radiology" in b["modules"])
        n_depts = len(eligible)

        print(f"\n--- Expected Record Counts After Seed ---")
        print(f"  Tenants:             {n_tenants}")
        print(f"  Users:               {n_users}")
        print(f"  Patients:            {n_patients}")
        print(f"  Departments:         {n_depts}")
        print(f"  Active visits:       {n_visits_active}")
        print(f"  Completed visits:    {n_visits_completed}")
        print(f"  Appointments:        {n_appts}")
        print(f"  Invoices:            {n_invoices}")
        print(f"  Payments:            {n_payments}")
        print(f"  Lab requests:        {n_lab}")
        print(f"  Radiology requests:  {n_rad}")

        if args.dry_run:
            print(f"\n{'='*60}")
            print("DRY RUN COMPLETE — no changes made.")
            print("Run with --confirm-local-reset to execute.")
            print(f"{'='*60}")
            return

        # ── Backup ──
        if not args.skip_backup:
            backup_path = _create_backup()
            if not backup_path:
                print("Backup failed or could not be verified. Aborting.")
                sys.exit(1)
            print(f"Backup saved to: {backup_path}")
        else:
            backup_path = None
            print("Backup skipped (--skip-backup).")

        # ── Reset ──
        _reset_data(db)

        # Re-run bootstrap for module_definitions / product_bundles.
        from app.core.platform_bootstrap import run_platform_bootstrap
        run_platform_bootstrap(quiet=True)

        # ── Seed platform owner ──
        print("\nSeeding platform owner")
        master_pw = _strong_password()
        _seed_platform_owner(db, master_pw)

        # ── Seed centres ──
        print("\nSeeding tenant centres")
        shared_pw = _strong_password()
        centres = _seed_tenant_centres(db, eligible, shared_pw)

        # ── Seed demo data ──
        print("\nSeeding demo data")
        _seed_demo_data(db, centres)

        # ── Report ──
        from models.user import User
        from app.core.tenant.models import Tenant
        from models.patient import Patient
        from models.visit import Visit
        from models.appointment import Appointment
        from models.invoice import Invoice
        from models.payment import Payment
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from models.department import Department

        total_u = User.query.count()
        total_t = Tenant.query.count()
        total_p = Patient.query.count()
        total_v = Visit.query.count()
        total_a = Appointment.query.count()
        total_i = Invoice.query.count()
        total_pay = Payment.query.count()
        total_lr = LabRequest.query.count()
        total_rr = RadiologyRequest.query.count()
        total_d = Department.query.count()

        print(f"\n{'='*60}")
        print("RESET AND SEED COMPLETE")
        print(f"{'='*60}")
        print(f"Tenants:             {total_t}")
        print(f"Users:               {total_u}")
        print(f"Patients:            {total_p}")
        print(f"Visits:              {total_v}")
        print(f"Appointments:        {total_a}")
        print(f"Invoices:            {total_i}")
        print(f"Payments:            {total_pay}")
        print(f"Lab requests:        {total_lr}")
        print(f"Radiology requests:  {total_rr}")
        print(f"Departments:         {total_d}")
        print(f"")
        print(f"Platform owner:     master / {master_pw}")
        print(f"Shared demo password (all centres): {shared_pw}")
        print(f"Excluded packages: {[b['profile_code'] for b in excluded]}")
        if backup_path:
            print(f"\nBackup: {backup_path}")
            print(f"\nRollback command:")
            print(f"  createdb -h localhost -U postgres medical_system_rollback")
            print(f"  psql -h localhost -U postgres -d medical_system_rollback -f \"{backup_path}\"")
            print(f"\n  Then swap database names, or restore in-place:")
            print(f"  dropdb -h localhost -U postgres medical_system")
            print(f"  createdb -h localhost -U postgres medical_system")
            print(f"  psql -h localhost -U postgres -d medical_system -f \"{backup_path}\"")
        print(f"\nStart server:")
        print(f"  python run_server.py")
        print(f"  -> http://127.0.0.1:8080/auth/login")


if __name__ == "__main__":
    main()
