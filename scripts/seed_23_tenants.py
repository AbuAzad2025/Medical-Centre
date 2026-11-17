#!/usr/bin/env python3
"""Seed one demo tenant per package (23 tenants) with realistic related data.

The script talks to PostgreSQL directly with :mod:`psycopg2` (no Flask/SQLAlchemy
imports, so the repository's shadowing ``inspect.py`` cannot interfere).

Design notes
------------
* Packages are *queried*, never hard-coded: every row in ``packages`` gets one
  tenant.
* Idempotency: the tenant uses ``INSERT ... ON CONFLICT (slug) DO NOTHING``;
  every child row is either checked by a deterministic key before insertion or
  protected by an ``ON CONFLICT DO NOTHING`` clause. Re-running the script
  therefore never duplicates data.
* Multi-tenancy: the tenant-scoped tables have FORCE ROW LEVEL SECURITY with a
  strict ``tenant_id = app.tenant_id`` policy (there is no bypass policy), so
  ``app.tenant_id`` is bound to the current tenant *before* any related insert
  or count. ``app.bypass_rls`` is also enabled for the session as requested.
* Everything happens in a single transaction that is committed only after all
  per-tenant assertions pass.

Run with::

    python scripts/seed_23_tenants.py
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import psycopg2

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5433,
    'user': 'postgres',
    'password': 'testpass',
    'dbname': 'Medical2026',
}

LOG = logging.getLogger('seed_23_tenants')

CHILD_TABLES = (
    'departments',
    'users',
    'patients',
    'visits',
    'appointments',
    'lab_requests',
    'radiology_requests',
)

#: Lower bounds asserted during the final verification (per tenant).
EXPECTED_MINIMUM = {
    'departments': 3,
    'users': 1,
    'patients': 5,
    'visits': 15,  # 3 per patient
    'appointments': 2,
    'lab_requests': 2,
    'radiology_requests': 1,
}

# --------------------------------------------------------------------------- #
# Realistic demo vocabulary
# --------------------------------------------------------------------------- #

DEPARTMENTS = (
    ('Internal Medicine', 'الطب الباطني'),
    ('General Surgery', 'الجراحة العامة'),
    ('Pediatrics', 'طب الأطفال'),
    ('Obstetrics & Gynecology', 'أمراض النساء والتوليد'),
    ('Cardiology', 'أمراض القلب'),
    ('Dermatology', 'الأمراض الجلدية'),
    ('Orthopedics', 'جراحة العظام'),
    ('Ophthalmology', 'طب العيون'),
    ('ENT', 'الأنف والأذن والحنجرة'),
    ('Emergency', 'الطوارئ'),
    ('Laboratory', 'المختبر'),
    ('Radiology', 'الأشعة'),
    ('Pharmacy', 'الصيدلية'),
    ('Reception', 'الاستقبال'),
    ('Nursing', 'التمريض'),
    ('Billing', 'الفوترة'),
)

MALE_FIRST_NAMES = (
    'أحمد',
    'محمد',
    'علي',
    'عبدالله',
    'يوسف',
    'عمر',
    'إبراهيم',
    'زياد',
    'كريم',
    'سعيد',
    'خالد',
    'طارق',
    'بدر',
    'فهد',
)

FEMALE_FIRST_NAMES = (
    'فاطمة',
    'مريم',
    'سارة',
    'خلود',
    'نور',
    'هند',
    'ليان',
    'عائشة',
    'زينب',
    'رنا',
    'دينا',
    'لمى',
    'جواهر',
    'مها',
)

LAST_NAMES = (
    'الخطيب',
    'الحداد',
    'النجار',
    'المصري',
    'العتيبي',
    'الزهراني',
    'الحربي',
    'القحطاني',
    'الشامي',
    'البركات',
    'السالم',
    'المطيري',
)

STREETS = ('الملك عبدالله', 'المدينة', 'الجامعة', 'السوق', 'النخيل', 'السلام')

#: Arabic display names for the 23 known package slugs. A sensible fallback is
#: used for any additional package that might be added later.
ARABIC_TENANT_NAMES = {
    'private_doctor_clinic': 'عيادة الطبيب الخاص',
    'doctor_clinic_reception': 'عيادة الطبيب مع الاستقبال',
    'doctor_clinic_full': 'عيادة الطبيب المتكاملة',
    'small_clinic': 'عيادة صغيرة',
    'clinic_with_lab': 'عيادة مع مختبر',
    'clinic_with_radiology': 'عيادة مع أشعة',
    'clinic_with_lab_radiology': 'عيادة مع مختبر وأشعة',
    'standalone_lab': 'مختبر مستقل',
    'lab_with_reception': 'مختبر مع استقبال',
    'standalone_radiology': 'مركز أشعة مستقل',
    'radiology_with_reception': 'مركز أشعة مع استقبال',
    'standalone_pharmacy': 'صيدلية مستقلة',
    'standalone_emergency': 'مركز طوارئ مستقل',
    'walkin_clinic': 'عيادة المرضى الخارجيين',
    'urgent_care': 'مركز رعاية عاجلة',
    'diagnostic_center': 'مركز تشخيص متقدم',
    'community_clinic': 'مركز صحة مجتمعي',
    'nursing_home': 'دار رعاية تمريضية',
    'multi_department_center': 'مركز طبي متعدد الأقسام',
    'polyclinic': 'مستوصف متعدد التخصصات',
    'hospital': 'مستشفى',
    'billing_only': 'مركز الفوترة والمواعيد',
    'custom': 'باقة مخصصة',
}

SYMPTOMS = (
    'صداع وارتفاع في الحرارة',
    'ألم في الصدر',
    'سعال مستمر',
    'ألم في البطن',
    'دوخة وضعف عام',
)

MODALITIES = ('XRay', 'CT', 'MRI', 'US')
BODY_PARTS = ('الصدر', 'البطن', 'الرأس', 'الركبة', 'العمود الفقري')

# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

_SLUG_UNSAFE = re.compile(r'[^a-z0-9]+')


def make_slug(package_id: int, package_slug: str) -> str:
    """Build a <=80 char, lower-case alnum/hyphen tenant slug."""
    raw = f'pkg-{package_id}-{package_slug}'.lower()
    slug = _SLUG_UNSAFE.sub('-', raw).strip('-')
    slug = slug[:80].rstrip('-')
    if not slug:
        slug = f'pkg-{package_id}'
    return slug


def row_exists(cur, table: str, where: str, params: tuple) -> bool:
    """True when at least one row matches ``WHERE`` (table/where are literals)."""
    cur.execute(f'SELECT 1 FROM {table} WHERE {where} LIMIT 1', params)
    return cur.fetchone() is not None


def bind_tenant(cur, tenant_id: int) -> None:
    """Bind the RLS context to ``tenant_id`` for the rest of the session."""
    cur.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))


def now_naive() -> datetime:
    """A timezone-naive UTC timestamp (the columns are TIMESTAMP WITHOUT TZ)."""
    return datetime.now(UTC).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Per-tenant seeders
# --------------------------------------------------------------------------- #


def seed_departments(cur, tenant_id: int, package_id: int, slug: str, stamp: datetime) -> list[int]:
    """Create 3-5 realistic departments; return their ids."""
    wanted = 3 + (package_id % 3)
    offset = (package_id * 3) % len(DEPARTMENTS)
    ids: list[int] = []

    for index in range(wanted):
        name, name_ar = DEPARTMENTS[(offset + index) % len(DEPARTMENTS)]
        if not row_exists(cur, 'departments', 'tenant_id = %s AND name = %s', (tenant_id, name)):
            cur.execute(
                """
                INSERT INTO departments (
                    tenant_id, name, name_ar, description, location, phone, email,
                    capacity, current_patients, is_active, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, TRUE, %s, %s
                )
                ON CONFLICT (tenant_id, name) DO NOTHING
                """,
                (
                    tenant_id,
                    name,
                    name_ar,
                    f'قسم {name_ar} في العيادة التجريبية',
                    f'الطابق {1 + index}',
                    f'+972 3-{6000000 + tenant_id:07d}',
                    f'dept{index + 1}.{slug}@medical.example.com',
                    20 + index * 5,
                    index * 2,
                    stamp,
                    stamp,
                ),
            )
        cur.execute(
            'SELECT id FROM departments WHERE tenant_id = %s AND name = %s',
            (tenant_id, name),
        )
        ids.append(cur.fetchone()[0])

    LOG.info('  departments: %d', len(ids))
    return ids


def seed_admin(cur, tenant_id: int, package_id: int, department_id: int, stamp: datetime) -> int:
    """Create the single admin user; return its id."""
    username = f'admin_pkg{package_id}'
    email = f'admin.pkg{package_id}@medical.example.com'
    full_name = f'مدير النظام - حزمة {package_id}'

    if not row_exists(cur, 'users', 'tenant_id = %s AND username = %s', (tenant_id, username)):
        cur.execute(
            """
            INSERT INTO users (
                tenant_id, username, email, password_hash, full_name, role,
                department_id, is_active, is_admin, session_version,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'admin', %s, TRUE, TRUE, 0, %s, %s)
            ON CONFLICT (tenant_id, username) DO NOTHING
            """,
            (
                tenant_id,
                username,
                email,
                'scrypt:dummy:hash',  # intentionally not a real Werkzeug hash
                full_name,
                department_id,
                stamp,
                stamp,
            ),
        )
    cur.execute(
        'SELECT id FROM users WHERE tenant_id = %s AND username = %s',
        (tenant_id, username),
    )
    admin_id = cur.fetchone()[0]
    LOG.info('  admin user: %s (id=%s)', username, admin_id)
    return admin_id


def seed_patients(cur, tenant_id: int, package_id: int, today: date, stamp: datetime) -> list[int]:
    """Create 5 patients with deterministic identity markers; return their ids."""
    ids: list[int] = []

    for index in range(5):
        marker = f'SEED:pkg-{package_id}:patient-{index + 1}'
        if not row_exists(cur, 'patients', 'tenant_id = %s AND notes = %s', (tenant_id, marker)):
            is_female = index % 2 == 1
            first_pool = FEMALE_FIRST_NAMES if is_female else MALE_FIRST_NAMES
            first_name = first_pool[(package_id + index * 3) % len(first_pool)]
            last_name = LAST_NAMES[(package_id * 3 + index * 5) % len(LAST_NAMES)]
            birth_date = date(
                1970 + (package_id + index * 4) % 40,
                1 + (package_id + index * 2) % 12,
                1 + (package_id * 7 + index * 4) % 28,
            )
            phone = (
                f'+972 5{2 + index % 4}-{1000000 + (package_id * 97 + index * 131) % 9000000:07d}'
            )
            national_id = f'{200000000 + package_id * 10007 + index:09d}'
            address = (
                f'شارع {STREETS[index % len(STREETS)]}، '
                f'مبنى {10 + (package_id + index) % 80}، المدينة'
            )
            cur.execute(
                """
                INSERT INTO patients (
                    tenant_id, first_name, last_name, first_name_ar, last_name_ar,
                    national_id, phone, birth_date, gender, address,
                    notes, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING id
                """,
                (
                    tenant_id,
                    first_name,
                    last_name,
                    first_name,
                    last_name,
                    national_id,
                    phone,
                    birth_date,
                    'F' if is_female else 'M',
                    address,
                    marker,
                    stamp,
                    stamp,
                ),
            )
            row = cur.fetchone()
            ids.append(row[0] if row else None)
        else:
            cur.execute(
                'SELECT id FROM patients WHERE tenant_id = %s AND notes = %s',
                (tenant_id, marker),
            )
            ids.append(cur.fetchone()[0])

    missing = [i for i, value in enumerate(ids, start=1) if value is None]
    if missing:
        raise RuntimeError(
            f'Failed to resolve patient ids for slots {missing} in tenant {tenant_id}'
        )

    LOG.info('  patients: %d', len(ids))
    return ids


def seed_visits(
    cur,
    tenant_id: int,
    package_id: int,
    patient_ids: list[int],
    department_ids: list[int],
    admin_id: int,
    today: date,
    stamp: datetime,
) -> dict[int, list[int]]:
    """Create 3 paid visits per patient; return {patient_id: [visit_id, ...]}."""
    per_patient: dict[int, list[int]] = {}
    visit_types = ('REGULAR', 'FOLLOW_UP', 'CONSULTATION')
    payment_methods = ('CASH', 'CARD', 'INSURANCE')

    for patient_index, patient_id in enumerate(patient_ids, start=1):
        per_patient[patient_id] = []
        for visit_index in range(3):
            visit_number = f'V-{package_id:03d}-{patient_index:02d}-{visit_index + 1:02d}'
            if not row_exists(cur, 'visits', 'visit_number = %s', (visit_number,)):
                amount = (
                    Decimal('120.00')
                    + Decimal(25 * ((package_id + 3 * patient_index + 7 * visit_index) % 16))
                    + Decimal('0.50')
                )
                visit_day = today - timedelta(
                    days=(package_id * 7 + patient_index * 11 + visit_index * 5) % 180
                )
                visit_time = datetime.combine(visit_day, time(9 + visit_index, 0))
                cur.execute(
                    """
                    INSERT INTO visits (
                        tenant_id, patient_id, department_id, doctor_id, visit_number,
                        status, payment_status, total_amount, paid_amount, currency,
                        visit_type, visit_date, visit_time, payment_method, symptoms,
                        notes, is_inpatient, pending_financial_settlement,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        'COMPLETED', 'PAID', %s, %s, 'ILS',
                        %s, %s, %s, %s, %s,
                        %s, FALSE, FALSE,
                        %s, %s
                    )
                    ON CONFLICT (visit_number) DO NOTHING
                    """,
                    (
                        tenant_id,
                        patient_id,
                        department_ids[(patient_index + visit_index) % len(department_ids)],
                        admin_id,
                        visit_number,
                        amount,
                        amount,
                        visit_types[visit_index],
                        visit_day,
                        visit_time,
                        payment_methods[(package_id + visit_index) % len(payment_methods)],
                        SYMPTOMS[(package_id + patient_index + visit_index) % len(SYMPTOMS)],
                        f'زيارة تجريبية {visit_number}',
                        stamp,
                        stamp,
                    ),
                )
            cur.execute('SELECT id FROM visits WHERE visit_number = %s', (visit_number,))
            per_patient[patient_id].append(cur.fetchone()[0])

    LOG.info('  visits: %d', sum(len(v) for v in per_patient.values()))
    return per_patient


def seed_appointments(
    cur,
    tenant_id: int,
    package_id: int,
    patient_ids: list[int],
    department_ids: list[int],
    admin_id: int,
    stamp: datetime,
    now: datetime,
) -> None:
    """Create 2 future appointments, using a stable notes marker for idempotency."""
    for index in range(2):
        marker = f'SEED:pkg-{package_id}:appointment-{index + 1}'
        if row_exists(cur, 'appointments', 'tenant_id = %s AND notes = %s', (tenant_id, marker)):
            continue
        starts_at = now + timedelta(days=1 + (package_id % 7) + index * 2, hours=9 + index)
        starts_at = starts_at.replace(minute=0, second=0, microsecond=0)
        if starts_at <= now:
            starts_at = now + timedelta(days=1)
        cur.execute(
            """
            INSERT INTO appointments (
                tenant_id, patient_id, doctor_id, department_id, created_by,
                starts_at, ends_at, status, notes, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'SCHEDULED', %s, %s, %s)
            ON CONFLICT ON CONSTRAINT uq_appointment_patient_time DO NOTHING
            """,
            (
                tenant_id,
                patient_ids[index % len(patient_ids)],
                admin_id,
                department_ids[0],
                admin_id,
                starts_at,
                starts_at + timedelta(minutes=30),
                marker,
                stamp,
                stamp,
            ),
        )
    LOG.info('  appointments: 2')


def seed_lab_and_radiology(
    cur,
    tenant_id: int,
    package_id: int,
    patient_ids: list[int],
    per_patient: dict[int, list[int]],
    admin_id: int,
    stamp: datetime,
) -> None:
    """Create 2 lab requests and 1 radiology request for the tenant."""
    for index in range(2):
        request_number = f'LAB-{package_id:03d}-{index + 1:02d}'
        if row_exists(cur, 'lab_requests', 'request_number = %s', (request_number,)):
            continue
        patient_id = patient_ids[index % len(patient_ids)]
        cur.execute(
            """
            INSERT INTO lab_requests (
                tenant_id, patient_id, visit_id, requested_by, request_number,
                status, barcode, notes, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (request_number) DO NOTHING
            """,
            (
                tenant_id,
                patient_id,
                per_patient[patient_id][0],
                admin_id,
                request_number,
                'REQUESTED' if index == 0 else 'IN_PROGRESS',
                f'LBC-{package_id:03d}-{index + 1:02d}',
                f'طلب مختبر تجريبي {request_number}',
                stamp,
                stamp,
            ),
        )

    request_number = f'RAD-{package_id:03d}-01'
    if not row_exists(cur, 'radiology_requests', 'request_number = %s', (request_number,)):
        patient_id = patient_ids[2 % len(patient_ids)]
        cur.execute(
            """
            INSERT INTO radiology_requests (
                tenant_id, patient_id, visit_id, requested_by, request_number,
                status, modality, body_part, notes, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (request_number) DO NOTHING
            """,
            (
                tenant_id,
                patient_id,
                per_patient[patient_id][0],
                admin_id,
                request_number,
                'REQUESTED',
                MODALITIES[package_id % len(MODALITIES)],
                BODY_PARTS[package_id % len(BODY_PARTS)],
                f'طلب أشعة تجريبي {request_number}',
                stamp,
                stamp,
            ),
        )
    LOG.info('  lab requests: 2, radiology requests: 1')


# --------------------------------------------------------------------------- #
# Tenant creation + verification
# --------------------------------------------------------------------------- #


def create_tenant(
    cur, package_id: int, package_slug: str, package_name: str, stamp: datetime, today: date
) -> int:
    """Insert-or-find the tenant for a package and return its id."""
    slug = make_slug(package_id, package_slug)
    arabic_base = ARABIC_TENANT_NAMES.get(package_slug)
    if not arabic_base:
        arabic_base = f'حزمة {package_name}'  # graceful fallback for new packages
    name_ar = f'{arabic_base} - نسخة تجريبية'

    cur.execute(
        """
        INSERT INTO tenants (
            slug, name, name_ar, contact_email, contact_phone,
            status, storage_mode, product_profile_code,
            subscription_type, subscription_start, subscription_end,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s,
            'ACTIVE'::tenantstatus, 'CLOUD'::storagemode, %s,
            'MONTHLY'::subscriptiontype, %s, %s,
            %s, %s
        )
        ON CONFLICT (slug) DO NOTHING
        """,
        (
            slug,
            f'{package_name} - Demo',
            name_ar,
            f'demo+{package_id}@medical.example.com',
            f'+972 3-{5000000 + package_id:07d}',
            package_slug,  # product_profile_code
            today,
            today + timedelta(days=365),
            stamp,
            stamp,
        ),
    )
    cur.execute('SELECT id FROM tenants WHERE slug = %s', (slug,))
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f'Could not resolve tenant for slug {slug!r}')
    return row[0]


def verify_tenant(cur, tenant_id: int, slug: str) -> None:
    """Print and assert the per-tenant row counts."""
    bind_tenant(cur, tenant_id)  # RLS is forced: counts are tenant-scoped
    counts: dict[str, int] = {}
    for table in CHILD_TABLES:
        cur.execute(f'SELECT count(*) FROM {table} WHERE tenant_id = %s', (tenant_id,))
        counts[table] = cur.fetchone()[0]

    summary = ', '.join(f'{table}={counts[table]}' for table in CHILD_TABLES)
    LOG.info('VERIFY tenant %s (id=%s): %s', slug, tenant_id, summary)

    for table, minimum in EXPECTED_MINIMUM.items():
        assert counts[table] >= minimum, (
            f'Tenant {slug!r} (id={tenant_id}) has only {counts[table]} {table}; '
            f'expected at least {minimum}'
        )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )

    stamp = now_naive()
    today = date.today()

    LOG.info('Connecting to %s:%s/%s', DB_CONFIG['host'], DB_CONFIG['port'], DB_CONFIG['dbname'])
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn, conn.cursor() as cur:
            # Cross-tenant session switch requested by the seeding contract.
            # (The tables' FORCE RLS policies are satisfied by app.tenant_id,
            # which is bound per tenant below.)
            cur.execute("SET app.bypass_rls = 'on'")

            cur.execute('SELECT id, slug, name FROM packages ORDER BY id')
            packages = cur.fetchall()
            LOG.info('Found %d packages to seed', len(packages))
            assert len(packages) == 23, f'Expected 23 packages, found {len(packages)}'

            seen_slugs: set[str] = set()
            for package_id, package_slug, package_name in packages:
                tenant_id = create_tenant(cur, package_id, package_slug, package_name, stamp, today)
                slug = make_slug(package_id, package_slug)
                assert slug not in seen_slugs, f'Duplicate tenant slug generated: {slug}'
                seen_slugs.add(slug)

                LOG.info('Seeding package %s -> tenant %s (id=%s)', package_id, slug, tenant_id)
                bind_tenant(cur, tenant_id)

                department_ids = seed_departments(cur, tenant_id, package_id, slug, stamp)
                admin_id = seed_admin(cur, tenant_id, package_id, department_ids[0], stamp)
                patient_ids = seed_patients(cur, tenant_id, package_id, today, stamp)
                per_patient = seed_visits(
                    cur,
                    tenant_id,
                    package_id,
                    patient_ids,
                    department_ids,
                    admin_id,
                    today,
                    stamp,
                )
                seed_appointments(
                    cur,
                    tenant_id,
                    package_id,
                    patient_ids,
                    department_ids,
                    admin_id,
                    stamp,
                    stamp,
                )
                seed_lab_and_radiology(
                    cur,
                    tenant_id,
                    package_id,
                    patient_ids,
                    per_patient,
                    admin_id,
                    stamp,
                )

            LOG.info('Seeding complete; verifying %d tenants', len(packages))
            for package_id, package_slug, _package_name in packages:
                slug = make_slug(package_id, package_slug)
                cur.execute('SELECT id FROM tenants WHERE slug = %s', (slug,))
                tenant_id = cur.fetchone()[0]
                verify_tenant(cur, tenant_id, slug)

        LOG.info('All tenants seeded and verified successfully. COMMITTED.')
    except Exception:
        LOG.exception('Seeding failed; transaction rolled back')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
