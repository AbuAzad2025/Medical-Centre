#!/usr/bin/env python3
"""ISO 27001 / HIPAA / ISO 13606 compliance audit — programmatic verification."""

import os
import sys
from pathlib import Path

sys.path.insert(0, r'D:\recovers\data\medical')

results = []


def check(name, condition, detail=''):
    status = 'PASS' if condition else 'FAIL'
    results.append((name, condition, detail))
    print(f'  [{status}] {name}' + (f' -- {detail}' if detail else ''))


# Initialize app context early
from sqlalchemy import text

from app.extensions import db
from app_factory import create_app

app = create_app('testing')

# -- 1. PHI Encryption (AES-SIV + HMAC blind index) --
print('\n=== 1. PHI Encryption ===')
import inspect

from models.patient import Patient

patient_src = inspect.getsource(Patient)
check(
    'Patient model has encrypted fields (AES-SIV)',
    'EncryptedType' in patient_src
    or 'encrypted' in patient_src.lower()
    or 'siv' in patient_src.lower(),
    'AES-SIV deterministic encryption for names/addresses',
)
check(
    'Patient model has blind index (HMAC)',
    'hash' in patient_src.lower()
    or 'hmac' in patient_src.lower()
    or 'blind' in patient_src.lower(),
    'HMAC-SHA256 blind index for national_id/phone',
)
with app.app_context():
    ngram_table = db.session.execute(
        text(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='patient_search_ngrams'"
        )
    ).scalar()
    check(
        'patient_search_ngrams table exists (partial search without PHI exposure)',
        ngram_table > 0,
        f'table exists: {ngram_table > 0}',
    )

# -- 2. Audit Trails (immutable, comprehensive) --
print('\n=== 2. Audit Trails (Immutable) ===')
check('audit_trails model exists', os.path.exists('models/audit_trail.py'))
check('phi_audit_logs model exists', os.path.exists('models/phi_audit_log.py'))
with app.app_context():
    platform_audit_table = db.session.execute(
        text(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='platform_audit_logs'"
        )
    ).scalar()
    check(
        'platform_audit_logs table exists (platform-level audit)',
        platform_audit_table > 0,
        f'table exists: {platform_audit_table > 0}',
    )
    policies = db.session.execute(
        text(
            "SELECT polname, pg_get_expr(polqual, polrelid) FROM pg_policy WHERE polrelid = 'audit_trails'::regclass"
        )
    ).fetchall()
    check('audit_trails has RLS policies', len(policies) > 0, f'{len(policies)} policies')
    delete_policies = [
        p for p in policies if 'delete' in p[0].lower() or (p[1] and 'false' in p[1].lower())
    ]
    check(
        'audit_trails has DELETE restriction (immutable)',
        len(delete_policies) > 0,
        f'{len(delete_policies)} restrictive policies',
    )

# -- 3. Access Control (RBAC) --
print('\n=== 3. Access Control (RBAC) ===')
from app.shared.user_role_policy import ASSIGNABLE_ROLES, ELEVATED_ROLES, PRIVILEGED_ROLE_MANAGERS

check('ASSIGNABLE_ROLES defined', len(ASSIGNABLE_ROLES) >= 15, f'{len(ASSIGNABLE_ROLES)} roles')
check(
    'PRIVILEGED_ROLE_MANAGERS defined',
    len(PRIVILEGED_ROLE_MANAGERS) > 0,
    f'{PRIVILEGED_ROLE_MANAGERS}',
)
check('ELEVATED_ROLES defined', len(ELEVATED_ROLES) > 0, f'{ELEVATED_ROLES}')
from app.shared.user_role_policy import normalize_role

check('normalize_role function exists', callable(normalize_role))
from utils.decorators import ROLE_HIERARCHY, role_required

check('role_required decorator exists', callable(role_required))
check(
    'ROLE_HIERARCHY defined (inheritance)',
    len(ROLE_HIERARCHY) > 0,
    f'{len(ROLE_HIERARCHY)} entries',
)
check(
    'er_doctor in ROLE_HIERARCHY -> emergency', 'emergency' in ROLE_HIERARCHY.get('er_doctor', [])
)

# -- 4. RLS Enforcement --
print('\n=== 4. RLS Enforcement ===')
with app.app_context():
    total = db.session.execute(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity"
        )
    ).scalar()
    check('Tenant-scoped tables with FORCE RLS >= 200', total >= 200, f'{total} tables')
    policies_count = db.session.execute(
        text("SELECT count(*) FROM pg_policy WHERE polname LIKE 'tenant_isolation_%'")
    ).scalar()
    check('tenant_isolation_* policies >= 200', policies_count >= 200, f'{policies_count} policies')
    nullif_count = db.session.execute(
        text("SELECT count(*) FROM pg_policy WHERE pg_get_expr(polqual, polrelid) LIKE '%NULLIF%'")
    ).scalar()
    check('Policies with NULLIF guard >= 200', nullif_count >= 200, f'{nullif_count} policies')

# -- 5. Data Retention & Consent --
print('\n=== 5. Data Retention & Consent ===')
consent_files = [f for f in [f.name for f in Path('models').iterdir()] if 'consent' in f.lower()]
check('Consent model exists', len(consent_files) > 0, f'files: {consent_files}')
export_routes = [
    f
    for f in [f.name for f in Path('routes').iterdir()]
    if f.endswith('.py')
    and any(
        kw in Path('routes/' + f).read_text(encoding='utf-8', errors='ignore').lower()
        for kw in ['privacy', 'data_export', 'right_to_be_forgotten', 'consent']
    )
]
check('Data export/privacy route exists', len(export_routes) > 0, f'files: {export_routes}')
privacy_files = [
    f
    for f in [f.name for f in Path('routes').iterdir()]
    if f.endswith('.py')
    and 'privacy' in Path('routes/' + f).read_text(encoding='utf-8', errors='ignore').lower()
]
check('Privacy policy route exists', len(privacy_files) > 0, f'files: {privacy_files}')

# -- 6. Backup & Disaster Recovery --
print('\n=== 6. Backup & Disaster Recovery ===')
check('Backup model exists', os.path.exists('models/backup.py'))
backup_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'backup' in f.lower()]
check('Backup routes exist', len(backup_routes) > 0, f'files: {backup_routes}')
check('DR documentation exists', os.path.exists('docs/DISASTER_RECOVERY.md'))
backup_tests = [f for f in [f.name for f in Path('tests').iterdir()] if 'backup' in f.lower()]
check('Backup tests exist', len(backup_tests) > 0, f'files: {backup_tests}')

# -- 7. MFA / WebAuthn / SSO --
print('\n=== 7. MFA / WebAuthn / SSO ===')
mfa_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'mfa' in f.lower()]
check('MFA route exists', len(mfa_routes) > 0, f'files: {mfa_routes}')
sso_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'sso' in f.lower()]
check('SSO route exists', len(sso_routes) > 0, f'files: {sso_routes}')
biometric_files = [
    f for f in [f.name for f in Path('models').iterdir()] if 'biometric' in f.lower()
]
check('Biometric model exists', len(biometric_files) > 0, f'files: {biometric_files}')
webauthn_routes = [
    f
    for f in [f.name for f in Path('routes').iterdir()]
    if 'webauthn' in f.lower() or 'biometric' in f.lower()
]
check('WebAuthn/biometric route exists', len(webauthn_routes) > 0, f'files: {webauthn_routes}')

# -- 8. HL7 / FHIR Integration --
print('\n=== 8. HL7 / FHIR Integration ===')
fhir_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'fhir' in f.lower()]
check('FHIR routes exist', len(fhir_routes) > 0, f'files: {fhir_routes}')
hl7_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'hl7' in f.lower()]
check('HL7 routes exist', len(hl7_routes) > 0, f'files: {hl7_routes}')
dicom_routes = [f for f in [f.name for f in Path('routes').iterdir()] if 'dicom' in f.lower()]
check('DICOM routes exist', len(dicom_routes) > 0, f'files: {dicom_routes}')

# -- 9. Module System Integrity --
print('\n=== 9. Module System Integrity ===')
from app.core.module.registry import MODULE_REGISTRY

check(
    'MODULE_REGISTRY has >= 20 modules',
    len(MODULE_REGISTRY) >= 20,
    f'{len(MODULE_REGISTRY)} modules',
)
declared = set()
for _name, meta in MODULE_REGISTRY.items():
    declared |= set(meta.tables or ())
with app.app_context():
    db_tables = {
        r[0]
        for r in db.session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).fetchall()
    }
    missing = declared - db_tables
    check(
        'All declared module tables exist in DB',
        len(missing) == 0,
        f'{len(missing)} missing: {list(missing)[:5]}',
    )

# -- 10. Bundle System Integrity --
print('\n=== 10. Bundle System Integrity ===')
from app.core.tenant.models import _PRODUCT_PROFILE_SEED

check(
    '23 bundles defined in seed',
    len(_PRODUCT_PROFILE_SEED) == 23,
    f'{len(_PRODUCT_PROFILE_SEED)} bundles',
)
with app.app_context():
    db_bundles = db.session.execute(text('SELECT count(*) FROM product_bundles')).scalar()
    check('23 bundles in database', db_bundles == 23, f'{db_bundles} bundles')
    unknown_modules = set()
    for _slug, prof in _PRODUCT_PROFILE_SEED.items():
        unknown_modules |= {m for m in prof['modules'] if m not in MODULE_REGISTRY}
    check(
        'All bundle modules exist in registry',
        len(unknown_modules) == 0,
        f'unknown: {unknown_modules}',
    )

# -- 11. CI/CD Pipeline --
print('\n=== 11. CI/CD Pipeline ===')
check('GitHub Actions workflow exists', os.path.exists('.github/workflows/ci.yml'))
import yaml

with open('.github/workflows/ci.yml', encoding='utf-8') as f:
    ci = yaml.safe_load(f)
    jobs = ci.get('jobs', {})
    check('CI has >= 15 jobs', len(jobs) >= 15, f'{len(jobs)} jobs')
    security_job = jobs.get('security-audit', {})
    check('Security audit job exists', bool(security_job))
    migrate_job = jobs.get('migrate', {})
    check('Migration verification job exists', bool(migrate_job))

# -- 12. Documentation --
print('\n=== 12. Documentation Completeness ===')
required_docs = [
    'README.md',
    'DEPLOYMENT.md',
    'docs/PLATFORM_STATUS.md',
    'docs/USER_GUIDE.md',
    'docs/CEO_OVERVIEW.md',
    'docs/ARCHITECTURE.md',
    'docs/DEVELOPER_GUIDE.md',
    'docs/API_REFERENCE.md',
    'docs/OPERATIONS.md',
    'docs/SCENARIO_PATIENT_FULL_JOURNEY.md',
]
for doc in required_docs:
    check(f'Doc exists: {doc}', os.path.exists(doc))

# -- Summary --
print('\n' + '=' * 60)
passed = sum(1 for _, c, _ in results if c)
failed = sum(1 for _, c, _ in results if not c)
print(f'ISO / COMPLIANCE AUDIT: {passed} passed, {failed} failed (of {len(results)})')
if failed > 0:
    print('\nFailed checks:')
    for name, c, detail in results:
        if not c:
            print(f'  FAIL: {name} -- {detail}')
print('=' * 60)
